"""Prepara un paquete VHF sin firma para validación, nunca para instalación.

El flujo de Alpha 2.3.0 mantiene separadas tres operaciones con riesgos distintos:
compilar, validar/empaquetar y firmar. Este módulo solo implementa la segunda.
No contiene comandos de instalación, no solicita elevación y no invoca SignTool.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import locale
import os
import re
import shutil
import struct
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

try:
    from .check_vs2026_wdk import inspect_installed_toolchain
except ImportError:  # Ejecución directa desde el wrapper .bat.
    from check_vs2026_wdk import inspect_installed_toolchain


PRODUCT = "Nikaido DualSense"
PUBLISHER = "Team Nikaido"
COPYRIGHT = "© Team Nikaido"
VERSION = "3.0.0-alpha.2.3.0"
RELEASE = "Alpha 2.3.0"
LAB_NAME = "Microsoft Signing Readiness"

PACKAGE_DIRECTORY_NAME = "NikaidoVhfA230"
PACKAGE_MANIFEST_NAME = f"{PACKAGE_DIRECTORY_NAME}.manifest.json"
BUILD_RECORD_NAME = f"{PACKAGE_DIRECTORY_NAME}.build.json"
BUILD_RECORD_SCHEMA_VERSION = 3
INF_NAME = "NikaidoVirtualHid.inf"
DRIVER_NAME = "NikaidoVirtualHid.sys"
PDB_NAME = "NikaidoVirtualHid.pdb"
CATALOG_NAME = "NikaidoVirtualHid.cat"
INF2CAT_TARGETS = (
    "10_VB_X64",
    "10_CO_X64",
    "10_NI_X64",
    "10_GE_X64",
    "10_25H2_X64",
)

MINIMUM_KIT_BUILD = 28000
MINIMUM_COMPATIBLE_INF2CAT_BUILD = 26100
MAX_INFVERIF_PATH = 259
IMAGE_FILE_MACHINE_AMD64 = 0x8664
IMAGE_FILE_EXECUTABLE_IMAGE = 0x0002
IMAGE_FILE_SYSTEM = 0x1000
IMAGE_NT_OPTIONAL_HDR64_MAGIC = 0x20B
IMAGE_SUBSYSTEM_NATIVE = 1

EXIT_TOOLCHAIN = 40
EXIT_INFVERIF_MISSING = 41
EXIT_INF2CAT_MISSING = 42
EXIT_ARTIFACT_MISSING = 43
EXIT_ARTIFACT_INVALID = 44
EXIT_PATH_TOO_LONG = 45
EXIT_INFVERIF_FAILED = 46
EXIT_INF2CAT_FAILED = 47
EXIT_CATALOG_MISSING = 48
EXIT_PACKAGE_IO = 49
EXIT_BUILD_RECORD_INVALID = 50


@dataclass(frozen=True, slots=True)
class ToolResolution:
    name: str
    path: Path | None
    location: str
    architecture: str | None
    kit_version: str | None = None

    @property
    def available(self) -> bool:
        return self.path is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "available": self.available,
            "location": self.location if self.available else None,
            "architecture": self.architecture if self.available else None,
            "kit_version": self.kit_version if self.available else None,
        }


@dataclass(frozen=True, slots=True)
class PackageToolReport:
    toolchain_ready: bool
    selected_kit_version: str | None
    infverif: ToolResolution
    inf2cat: ToolResolution
    process_elevated: bool | None = None

    @property
    def ready(self) -> bool:
        return self.toolchain_ready and self.infverif.available and self.inf2cat.available

    @property
    def exit_code(self) -> int:
        if not self.toolchain_ready or self.selected_kit_version is None:
            return EXIT_TOOLCHAIN
        if not self.infverif.available:
            return EXIT_INFVERIF_MISSING
        if not self.inf2cat.available:
            return EXIT_INF2CAT_MISSING
        return 0

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 2,
            "product": PRODUCT,
            "publisher": PUBLISHER,
            "release": VERSION,
            "package_tools_ready": self.ready,
            "selected_kit_version": self.selected_kit_version,
            "build_kit_version": self.selected_kit_version,
            "process_elevated": self.process_elevated,
            "tools": [self.infverif.to_dict(), self.inf2cat.to_dict()],
            "mutations_performed": False,
            "privacy": {
                "contains_username": False,
                "contains_hostname": False,
                "contains_private_paths": False,
            },
        }


@dataclass(frozen=True, slots=True)
class PeInspection:
    machine: int
    optional_magic: int
    number_of_sections: int
    characteristics: int
    subsystem: int
    address_of_entry_point: int
    certificate_size: int

    @property
    def valid_unsigned_x64_driver(self) -> bool:
        return (
            self.machine == IMAGE_FILE_MACHINE_AMD64
            and self.optional_magic == IMAGE_NT_OPTIONAL_HDR64_MAGIC
            and self.number_of_sections > 0
            and bool(self.characteristics & IMAGE_FILE_EXECUTABLE_IMAGE)
            and self.subsystem == IMAGE_SUBSYSTEM_NATIVE
            and self.address_of_entry_point != 0
            and self.certificate_size == 0
        )

    @property
    def system_characteristic_present(self) -> bool:
        """El bit IMAGE_FILE_SYSTEM es informativo, no un requisito de /DRIVER."""

        return bool(self.characteristics & IMAGE_FILE_SYSTEM)


@dataclass(frozen=True, slots=True)
class ToolExecution:
    returncode: int
    output: str


class PackagePreparationError(RuntimeError):
    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


ToolRunner = Callable[[Sequence[str], Sequence[str]], ToolExecution]


def _version_tuple(value: str) -> tuple[int, ...] | None:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def _environment_value(environment: Mapping[str, str], key: str) -> str | None:
    wanted = key.casefold()
    for candidate, value in environment.items():
        if candidate.casefold() == wanted:
            return value
    return None


def _kit_roots(environment: Mapping[str, str]) -> tuple[Path, ...]:
    candidates: list[Path] = []
    for variable in ("WDKContentRoot", "WindowsSdkDir"):
        value = _environment_value(environment, variable)
        if value:
            candidates.append(Path(value))
    program_files_x86 = _environment_value(environment, "ProgramFiles(x86)")
    if program_files_x86:
        candidates.append(Path(program_files_x86) / "Windows Kits" / "10")

    roots: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate.name.casefold() in {"include", "lib", "bin", "build", "tools"}:
            candidate = candidate.parent
        key = os.path.normcase(str(candidate.resolve(strict=False)))
        if key in seen or not candidate.is_dir():
            continue
        seen.add(key)
        roots.append(candidate)
    return tuple(roots)


def _first_tool(candidates: Sequence[tuple[Path, str, str]]) -> ToolResolution:
    name = candidates[0][0].name if candidates else "tool"
    for path, location, architecture in candidates:
        if path.is_file():
            return ToolResolution(name, path, location, architecture)
    return ToolResolution(name, None, "", None)


def evaluate_package_tools(kit_root: Path, version: str) -> tuple[ToolResolution, ToolResolution]:
    """Resuelve primero las herramientas que coinciden con el kit de compilación."""

    infverif = _first_tool(
        (
            (
                kit_root / "Tools" / version / "x64" / "InfVerif.exe",
                "Tools/<kit>/x64",
                "x64",
            ),
            (kit_root / "Tools" / "x64" / "InfVerif.exe", "Tools/x64", "x64"),
            (
                kit_root / "bin" / version / "x64" / "InfVerif.exe",
                "bin/<kit>/x64",
                "x64",
            ),
            (kit_root / "Tools" / version / "x86" / "InfVerif.exe", "Tools/<kit>/x86", "x86"),
            (kit_root / "Tools" / "x86" / "InfVerif.exe", "Tools/x86", "x86"),
        )
    )
    inf2cat = _first_tool(
        (
            (
                kit_root / "bin" / version / "x64" / "Inf2Cat.exe",
                "bin/<kit>/x64",
                "x64",
            ),
            (
                kit_root / "bin" / version / "x86" / "Inf2Cat.exe",
                "bin/<kit>/x86",
                "x86",
            ),
            (kit_root / "bin" / "x64" / "Inf2Cat.exe", "bin/x64", "x64"),
            (kit_root / "bin" / "x86" / "Inf2Cat.exe", "bin/x86", "x86"),
        )
    )
    if infverif.available:
        infverif = ToolResolution(
            infverif.name,
            infverif.path,
            infverif.location,
            infverif.architecture,
            version if "<kit>" in infverif.location else None,
        )
    if inf2cat.available:
        inf2cat = ToolResolution(
            inf2cat.name,
            inf2cat.path,
            inf2cat.location,
            inf2cat.architecture,
            version if "<kit>" in inf2cat.location else None,
        )
    return infverif, inf2cat


def evaluate_compatible_inf2cat(kit_root: Path, selected_version: str) -> ToolResolution:
    """Busca Inf2Cat en otra versión instalada de la misma raíz Windows Kits.

    Inf2Cat valida un paquete ya compilado y no participa en la selección de
    headers, bibliotecas o toolset. Por eso puede resolverse de manera
    independiente, pero únicamente dentro de la misma instalación de Windows
    Kits y desde una familia suficientemente reciente. La compatibilidad real
    de los identificadores de Windows se confirma al ejecutar Inf2Cat.
    """

    bin_root = kit_root / "bin"
    if not bin_root.is_dir():
        return ToolResolution("Inf2Cat.exe", None, "", None)

    versions: list[tuple[tuple[int, ...], str]] = []
    try:
        directories = tuple(path for path in bin_root.iterdir() if path.is_dir())
    except OSError:
        directories = ()
    for directory in directories:
        parsed = _version_tuple(directory.name)
        if (
            parsed is None
            or parsed[2] < MINIMUM_COMPATIBLE_INF2CAT_BUILD
            or directory.name == selected_version
        ):
            continue
        versions.append((parsed, directory.name))

    for _parsed, version in sorted(versions, reverse=True):
        for architecture in ("x64", "x86"):
            path = bin_root / version / architecture / "Inf2Cat.exe"
            if path.is_file():
                return ToolResolution(
                    "Inf2Cat.exe",
                    path,
                    f"bin/<compatible-kit>/{architecture}",
                    architecture,
                    version,
                )
    return ToolResolution("Inf2Cat.exe", None, "", None)


def _process_elevated() -> bool | None:
    if os.name != "nt":
        return None
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return None


def inspect_package_tools(
    environment: Mapping[str, str] | None = None,
) -> PackageToolReport:
    env = dict(os.environ if environment is None else environment)
    toolchain = inspect_installed_toolchain(env)
    version = toolchain.selected_kit_version
    missing = ToolResolution("InfVerif.exe", None, "", None)
    missing_cat = ToolResolution("Inf2Cat.exe", None, "", None)
    if version is None:
        return PackageToolReport(False, None, missing, missing_cat, _process_elevated())

    parsed = _version_tuple(version)
    if parsed is None or parsed[2] < MINIMUM_KIT_BUILD:
        return PackageToolReport(False, version, missing, missing_cat, _process_elevated())

    candidates: list[tuple[int, ToolResolution, ToolResolution]] = []
    for root in _kit_roots(env):
        if not (root / "Include" / version).is_dir():
            continue
        infverif, inf2cat = evaluate_package_tools(root, version)
        if not inf2cat.available:
            inf2cat = evaluate_compatible_inf2cat(root, version)
        score = int(infverif.available) + int(inf2cat.available)
        if inf2cat.kit_version == version:
            score += 1
        candidates.append((score, infverif, inf2cat))
    if not candidates:
        return PackageToolReport(
            toolchain.ready,
            version,
            missing,
            missing_cat,
            _process_elevated(),
        )

    _, infverif, inf2cat = max(candidates, key=lambda item: item[0])
    return PackageToolReport(
        toolchain.ready,
        version,
        infverif,
        inf2cat,
        _process_elevated(),
    )


def inspect_pe_driver(path: Path) -> PeInspection:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise PackagePreparationError(
            f"No se pudo leer {DRIVER_NAME}: {type(exc).__name__}",
            EXIT_ARTIFACT_MISSING,
        ) from exc

    try:
        if len(payload) < 256 or payload[:2] != b"MZ":
            raise ValueError("cabecera DOS ausente")
        pe_offset = struct.unpack_from("<I", payload, 0x3C)[0]
        if pe_offset + 24 > len(payload) or payload[pe_offset : pe_offset + 4] != b"PE\0\0":
            raise ValueError("cabecera PE ausente")
        machine, sections, _timestamp, _symbols, _symbol_count, optional_size, characteristics = (
            struct.unpack_from("<HHIIIHH", payload, pe_offset + 4)
        )
        optional_offset = pe_offset + 24
        if optional_offset + optional_size > len(payload):
            raise ValueError("cabecera opcional truncada")
        optional_magic = struct.unpack_from("<H", payload, optional_offset)[0]
        if optional_magic != IMAGE_NT_OPTIONAL_HDR64_MAGIC or optional_size < 152:
            raise ValueError("cabecera opcional PE32+ inválida")
        address_of_entry_point = struct.unpack_from("<I", payload, optional_offset + 16)[0]
        subsystem = struct.unpack_from("<H", payload, optional_offset + 68)[0]
        certificate_size = struct.unpack_from("<I", payload, optional_offset + 112 + 36)[0]
    except (struct.error, ValueError) as exc:
        raise PackagePreparationError(
            f"{DRIVER_NAME} no es un PE x64 válido: {exc}",
            EXIT_ARTIFACT_INVALID,
        ) from exc

    inspection = PeInspection(
        machine=machine,
        optional_magic=optional_magic,
        number_of_sections=sections,
        characteristics=characteristics,
        subsystem=subsystem,
        address_of_entry_point=address_of_entry_point,
        certificate_size=certificate_size,
    )
    if not inspection.valid_unsigned_x64_driver:
        reasons: list[str] = []
        if machine != IMAGE_FILE_MACHINE_AMD64:
            reasons.append("arquitectura distinta de x64")
        if optional_magic != IMAGE_NT_OPTIONAL_HDR64_MAGIC:
            reasons.append("formato distinto de PE32+")
        if sections <= 0:
            reasons.append("no contiene secciones")
        if not characteristics & IMAGE_FILE_EXECUTABLE_IMAGE:
            reasons.append("no está marcado como imagen ejecutable")
        if subsystem != IMAGE_SUBSYSTEM_NATIVE:
            reasons.append("subsistema distinto de Native")
        if address_of_entry_point == 0:
            reasons.append("no contiene punto de entrada")
        if certificate_size != 0:
            reasons.append("contiene una firma incrustada inesperada")
        raise PackagePreparationError(
            f"{DRIVER_NAME} rechazado: {', '.join(reasons)}",
            EXIT_ARTIFACT_INVALID,
        )
    return inspection


def validate_source_inf(path: Path) -> None:
    try:
        source = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise PackagePreparationError(
            f"No se pudo leer {INF_NAME}: {type(exc).__name__}",
            EXIT_ARTIFACT_MISSING,
        ) from exc

    compact = source.replace(" ", "")
    required = (
        'Signature="$WINDOWSNT$"',
        "Class=HIDClass",
        "Provider=%Publisher%",
        "CatalogFile=NikaidoVirtualHid.cat",
        "PnpLockdown=1",
        "ROOT\\NIKAIDO_VHF_ALPHA2",
        'Publisher="TeamNikaido"',
        'HKR,,"LowerFilters",0x00010000,"vhf"',
        "DriverVer=07/23/2026,3.0.0.230",
    )
    missing = [token for token in required if token not in compact]
    if missing:
        raise PackagePreparationError(
            f"{INF_NAME} no contiene la identidad o directivas esperadas de Alpha 2.3.0",
            EXIT_ARTIFACT_INVALID,
        )
    if re.search(r"(?i)[A-Z]:\\(?:Users|Documents and Settings)\\", source):
        raise PackagePreparationError(
            f"{INF_NAME} contiene una ruta privada",
            EXIT_ARTIFACT_INVALID,
        )


def _decode_tool_output(payload: bytes) -> str:
    encodings = ["utf-8", locale.getpreferredencoding(False), "cp1252"]
    for encoding in dict.fromkeys(encodings):
        try:
            return payload.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return payload.decode("utf-8", errors="replace")


def sanitize_tool_output(text: str, private_values: Sequence[str]) -> str:
    sanitized = text
    replacements = sorted(
        {value for value in private_values if value and len(value) >= 3},
        key=len,
        reverse=True,
    )
    for value in replacements:
        for variant in {value, value.replace("/", "\\"), value.replace("\\", "/")}:
            sanitized = re.sub(re.escape(variant), "<PRIVATE>", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(
        r"(?i)\b[A-Z]:[\\/](?:Users|Documents and Settings)[\\/][^\\/\r\n]+",
        r"C:\\Users\\<PRIVATE>",
        sanitized,
    )
    return sanitized.strip()


def _run_tool(command: Sequence[str], private_values: Sequence[str]) -> ToolExecution:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            timeout=180,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return ToolExecution(1, f"No se pudo ejecutar la herramienta: {type(exc).__name__}")
    combined = completed.stdout
    if completed.stderr:
        combined += (b"\n" if combined else b"") + completed.stderr
    return ToolExecution(
        completed.returncode,
        sanitize_tool_output(_decode_tool_output(combined), private_values),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_remove_generated(path: Path, output_root: Path) -> None:
    allowed = {
        PACKAGE_DIRECTORY_NAME,
        f"{PACKAGE_DIRECTORY_NAME}.staging",
        PACKAGE_MANIFEST_NAME,
        f"{PACKAGE_MANIFEST_NAME}.tmp",
    }
    if path.name not in allowed or path.parent.resolve() != output_root.resolve():
        raise PackagePreparationError(
            "Se rechazó una ruta de salida fuera del directorio controlado",
            EXIT_PACKAGE_IO,
        )
    if path.is_symlink():
        raise PackagePreparationError(
            "Se rechazó un enlace simbólico en la salida controlada",
            EXIT_PACKAGE_IO,
        )
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _driver_build_files(
    project_root: Path,
) -> tuple[Path, Path, tuple[Path, ...], Path]:
    vhf_root = project_root / "native" / "vhf"
    sources = (
        vhf_root / "driver" / "driver.c",
        vhf_root / "shared" / "nikaido_vhf_protocol.h",
        vhf_root / "driver" / "NikaidoVirtualHid.vcxproj",
        vhf_root / "driver" / INF_NAME,
    )
    driver = vhf_root / "driver" / "x64" / "Release" / DRIVER_NAME
    symbols = vhf_root / "driver" / "x64" / "Release" / PDB_NAME
    record = driver.parent / BUILD_RECORD_NAME
    return driver, symbols, sources, record


def clear_build_record(project_root: Path) -> bool:
    """Elimina solamente el comprobante generado, nunca fuentes ni binarios."""

    project_root = project_root.resolve()
    _driver, _symbols, _sources, record = _driver_build_files(project_root)
    temporary = record.with_suffix(record.suffix + ".tmp")
    removed = False
    for path in (record, temporary):
        if path.is_symlink() or path.is_file():
            path.unlink()
            removed = True
        elif path.exists():
            raise PackagePreparationError(
                "El registro de compilación tiene un tipo inesperado",
                EXIT_BUILD_RECORD_INVALID,
            )
    return removed


def _file_record(project_root: Path, path: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(project_root).as_posix(),
        "size": path.stat().st_size,
        "sha256": _sha256(path),
    }


def record_successful_build(project_root: Path) -> dict[str, object]:
    """Registra hashes solo después de que el wrapper completó ambos proyectos."""

    project_root = project_root.resolve()
    driver, symbols, sources, record = _driver_build_files(project_root)
    missing = [path for path in (*sources, driver, symbols) if not path.is_file()]
    if missing:
        raise PackagePreparationError(
            "No se puede registrar la compilación: falta una fuente, el driver o su PDB Release x64",
            EXIT_ARTIFACT_MISSING,
        )

    inspection = inspect_pe_driver(driver)
    validate_source_inf(sources[-1])
    payload: dict[str, object] = {
        "schema_version": BUILD_RECORD_SCHEMA_VERSION,
        "product": PRODUCT,
        "publisher": PUBLISHER,
        "copyright": COPYRIGHT,
        "version": VERSION,
        "release": RELEASE,
        "status": "successful",
        "output": _file_record(project_root, driver),
        "symbols": _file_record(project_root, symbols),
        "inputs": [_file_record(project_root, source) for source in sources],
        "pe_validation": {
            "machine": "AMD64",
            "format": "PE32+",
            "subsystem": "Native",
            "number_of_sections": inspection.number_of_sections,
            "executable_image": True,
            "entry_point_present": True,
            "system_characteristic_present": inspection.system_characteristic_present,
            "embedded_certificate_present": False,
        },
        "privacy": {
            "contains_username": False,
            "contains_hostname": False,
            "contains_private_paths": False,
        },
    }
    temporary = record.with_suffix(record.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(record)
    except OSError as exc:
        if temporary.is_file() or temporary.is_symlink():
            temporary.unlink()
        raise PackagePreparationError(
            f"No se pudo guardar el registro de compilación: {type(exc).__name__}",
            EXIT_PACKAGE_IO,
        ) from exc
    return payload


def _assert_fresh_build(
    project_root: Path,
    driver: Path,
    symbols: Path,
    sources: Sequence[Path],
) -> dict[str, object]:
    if not driver.is_file():
        raise PackagePreparationError(
            f"Falta {DRIVER_NAME}; ejecuta BUILD_VHF_ALPHA230.bat primero",
            EXIT_ARTIFACT_MISSING,
        )
    if not symbols.is_file():
        raise PackagePreparationError(
            f"Falta {PDB_NAME}; ejecuta BUILD_VHF_ALPHA230.bat primero",
            EXIT_ARTIFACT_MISSING,
        )

    _expected_driver, _expected_symbols, _expected_sources, record = _driver_build_files(
        project_root
    )
    if not record.is_file() or record.is_symlink():
        raise PackagePreparationError(
            "Falta el registro de compilación por hashes; ejecuta BUILD_VHF_ALPHA230.bat",
            EXIT_BUILD_RECORD_INVALID,
        )
    try:
        payload = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PackagePreparationError(
            f"El registro de compilación no es válido: {type(exc).__name__}",
            EXIT_BUILD_RECORD_INVALID,
        ) from exc

    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != BUILD_RECORD_SCHEMA_VERSION
        or payload.get("product") != PRODUCT
        or payload.get("publisher") != PUBLISHER
        or payload.get("version") != VERSION
        or payload.get("status") != "successful"
    ):
        raise PackagePreparationError(
            "El registro de compilación pertenece a otra versión o está incompleto",
            EXIT_BUILD_RECORD_INVALID,
        )

    expected_inputs = {
        source.relative_to(project_root).as_posix(): source for source in sources
    }
    stored_inputs = payload.get("inputs")
    if not isinstance(stored_inputs, list):
        raise PackagePreparationError(
            "El registro de compilación no contiene sus fuentes",
            EXIT_BUILD_RECORD_INVALID,
        )
    indexed_inputs: dict[str, dict[str, object]] = {}
    for entry in stored_inputs:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise PackagePreparationError(
                "El registro de compilación contiene una entrada inválida",
                EXIT_BUILD_RECORD_INVALID,
            )
        path = entry["path"]
        if path in indexed_inputs:
            raise PackagePreparationError(
                "El registro de compilación contiene fuentes duplicadas",
                EXIT_BUILD_RECORD_INVALID,
            )
        indexed_inputs[path] = entry
    if set(indexed_inputs) != set(expected_inputs):
        raise PackagePreparationError(
            "Las fuentes registradas no coinciden con Alpha 2.3.0",
            EXIT_BUILD_RECORD_INVALID,
        )

    try:
        for relative, source in expected_inputs.items():
            stored = indexed_inputs[relative]
            if (
                stored.get("size") != source.stat().st_size
                or stored.get("sha256") != _sha256(source)
            ):
                raise PackagePreparationError(
                    f"Una fuente cambió después de compilar: {relative}",
                    EXIT_BUILD_RECORD_INVALID,
                )

        output = payload.get("output")
        expected_output_path = driver.relative_to(project_root).as_posix()
        if (
            not isinstance(output, dict)
            or output.get("path") != expected_output_path
            or output.get("size") != driver.stat().st_size
            or output.get("sha256") != _sha256(driver)
        ):
            raise PackagePreparationError(
                "El driver cambió después de la compilación registrada",
                EXIT_BUILD_RECORD_INVALID,
            )

        stored_symbols = payload.get("symbols")
        expected_symbols_path = symbols.relative_to(project_root).as_posix()
        if (
            not isinstance(stored_symbols, dict)
            or stored_symbols.get("path") != expected_symbols_path
            or stored_symbols.get("size") != symbols.stat().st_size
            or stored_symbols.get("sha256") != _sha256(symbols)
        ):
            raise PackagePreparationError(
                "El PDB cambió después de la compilación registrada",
                EXIT_BUILD_RECORD_INVALID,
            )
    except OSError as exc:
        raise PackagePreparationError(
            f"No se pudo verificar el registro de compilación: {type(exc).__name__}",
            EXIT_BUILD_RECORD_INVALID,
        ) from exc
    return payload


def _write_manifest(
    path: Path,
    package_dir: Path,
    tools: PackageToolReport,
    build_record: Mapping[str, object],
) -> dict[str, object]:
    files = []
    for name in (INF_NAME, DRIVER_NAME, CATALOG_NAME):
        file_path = package_dir / name
        files.append(
            {
                "path": name,
                "size": file_path.stat().st_size,
                "sha256": _sha256(file_path),
            }
        )
    payload: dict[str, object] = {
        "schema_version": 2,
        "product": PRODUCT,
        "publisher": PUBLISHER,
        "copyright": COPYRIGHT,
        "version": VERSION,
        "release": RELEASE,
        "lab_name": LAB_NAME,
        "package_directory": PACKAGE_DIRECTORY_NAME,
        "target_operating_systems": list(INF2CAT_TARGETS),
        "files": files,
        "symbols": build_record["symbols"],
        "validation": {
            "pe_x64_native": "passed",
            "pe_executable_image": "passed",
            "pe_entry_point": "present",
            "pe_system_characteristic": "informational_not_required",
            "embedded_driver_signature": "absent",
            "infverif_universal": "passed",
            "inf2cat": "passed",
            "catalog_generated": True,
            "catalog_signature": "absent_by_design",
            "build_freshness": "verified_by_hash_record",
            "build_record_schema_version": BUILD_RECORD_SCHEMA_VERSION,
            "kit_version": tools.selected_kit_version,
            "build_kit_version": tools.selected_kit_version,
            "infverif_kit_version": tools.infverif.kit_version,
            "inf2cat_kit_version": tools.inf2cat.kit_version,
            "inf2cat_separate_compatible_kit": (
                tools.inf2cat.kit_version is not None
                and tools.inf2cat.kit_version != tools.selected_kit_version
            ),
            "infverif_architecture": tools.infverif.architecture,
            "inf2cat_architecture": tools.inf2cat.architecture,
        },
        "security": {
            "driver_installed": False,
            "driver_loaded": False,
            "driver_signed": False,
            "automatic_elevation": False,
            "secure_boot_changes": False,
            "memory_integrity_changes": False,
            "test_signing_changes": False,
        },
        "privacy": {
            "contains_username": False,
            "contains_hostname": False,
            "contains_private_paths": False,
        },
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return payload


def prepare_package(
    project_root: Path,
    tools: PackageToolReport,
    *,
    runner: ToolRunner = _run_tool,
) -> dict[str, object]:
    if not tools.ready or tools.infverif.path is None or tools.inf2cat.path is None:
        raise PackagePreparationError(
            "Las herramientas de paquete no están disponibles",
            tools.exit_code or EXIT_TOOLCHAIN,
        )

    project_root = project_root.resolve()
    vhf_root = project_root / "native" / "vhf"
    driver_source = vhf_root / "driver" / "driver.c"
    protocol_source = vhf_root / "shared" / "nikaido_vhf_protocol.h"
    project_source = vhf_root / "driver" / "NikaidoVirtualHid.vcxproj"
    inf_source = vhf_root / "driver" / INF_NAME
    built_driver = vhf_root / "driver" / "x64" / "Release" / DRIVER_NAME
    built_symbols = vhf_root / "driver" / "x64" / "Release" / PDB_NAME
    output_root = vhf_root / "out"
    final_dir = output_root / PACKAGE_DIRECTORY_NAME
    staging_dir = output_root / f"{PACKAGE_DIRECTORY_NAME}.staging"
    manifest_path = output_root / PACKAGE_MANIFEST_NAME
    manifest_temporary = manifest_path.with_suffix(manifest_path.suffix + ".tmp")

    build_record = _assert_fresh_build(
        project_root,
        built_driver,
        built_symbols,
        (driver_source, protocol_source, project_source, inf_source),
    )
    inspect_pe_driver(built_driver)
    validate_source_inf(inf_source)

    output_root.mkdir(parents=True, exist_ok=True)
    for generated in (staging_dir,):
        if generated.exists() or generated.is_symlink():
            _safe_remove_generated(generated, output_root)
    staging_dir.mkdir()
    published = False

    try:
        shutil.copy2(inf_source, staging_dir / INF_NAME)
        shutil.copy2(built_driver, staging_dir / DRIVER_NAME)
        staged_inf = staging_dir / INF_NAME
        if len(str(staged_inf.resolve())) > MAX_INFVERIF_PATH:
            raise PackagePreparationError(
                "La ruta completa del INF supera 259 caracteres; extrae el laboratorio más cerca de la raíz del disco",
                EXIT_PATH_TOO_LONG,
            )

        private_values = (
            str(project_root),
            str(Path.home()),
            os.environ.get("USERPROFILE", ""),
            os.environ.get("USERNAME", ""),
            os.environ.get("COMPUTERNAME", ""),
        )
        infverif = runner(
            (str(tools.infverif.path), "/v", "/u", str(staged_inf)),
            private_values,
        )
        if infverif.output:
            print(infverif.output)
        if infverif.returncode != 0:
            raise PackagePreparationError(
                f"InfVerif rechazó el INF con código {infverif.returncode}",
                EXIT_INFVERIF_FAILED,
            )

        inf2cat = runner(
            (
                str(tools.inf2cat.path),
                f"/driver:{staging_dir}",
                f"/os:{','.join(INF2CAT_TARGETS)}",
                "/uselocaltime",
                "/verbose",
            ),
            private_values,
        )
        if inf2cat.output:
            print(inf2cat.output)
        if inf2cat.returncode != 0:
            raise PackagePreparationError(
                f"Inf2Cat rechazó el paquete con código {inf2cat.returncode}",
                EXIT_INF2CAT_FAILED,
            )

        catalog = staging_dir / CATALOG_NAME
        if not catalog.is_file() or catalog.stat().st_size == 0:
            raise PackagePreparationError(
                "Inf2Cat terminó sin producir el catálogo esperado",
                EXIT_CATALOG_MISSING,
            )

        if final_dir.exists() or final_dir.is_symlink():
            _safe_remove_generated(final_dir, output_root)
        if manifest_path.exists() or manifest_path.is_symlink():
            _safe_remove_generated(manifest_path, output_root)
        staging_dir.replace(final_dir)
        published = True
        return _write_manifest(manifest_path, final_dir, tools, build_record)
    except Exception:
        if staging_dir.exists() and not staging_dir.is_symlink():
            _safe_remove_generated(staging_dir, output_root)
        if published and (final_dir.exists() or final_dir.is_symlink()):
            _safe_remove_generated(final_dir, output_root)
        if published and (manifest_path.exists() or manifest_path.is_symlink()):
            _safe_remove_generated(manifest_path, output_root)
        if manifest_temporary.exists() or manifest_temporary.is_symlink():
            _safe_remove_generated(manifest_temporary, output_root)
        raise


def _human_tool_report(report: PackageToolReport) -> str:
    lines = [
        "Nikaido DualSense 3.0.0 Alpha 2.3.0 — Microsoft Signing Readiness",
        "",
    ]
    if report.selected_kit_version:
        lines.append(f"[OK       ] Kit seleccionado: {report.selected_kit_version}")
    else:
        lines.append("[BLOQUEADO] No hay un SDK/WDK 28000 completo seleccionado")
    for tool in (report.infverif, report.inf2cat):
        if tool.available:
            kit_suffix = f", kit {tool.kit_version}" if tool.kit_version else ""
            lines.append(
                f"[OK       ] {tool.name} detectado "
                f"({tool.location}, {tool.architecture}{kit_suffix})"
            )
        else:
            lines.append(
                f"[BLOQUEADO] {tool.name} no está disponible en una ubicación compatible"
            )
    if (
        report.inf2cat.available
        and report.inf2cat.kit_version
        and report.inf2cat.kit_version != report.selected_kit_version
    ):
        lines.append(
            "[INFO     ] Inf2Cat pertenece a otro kit candidato y solo se usará "
            "después de compilar"
        )
        lines.append(
            "[INFO     ] Headers, bibliotecas, MSBuild y VHF permanecen íntegramente "
            f"en {report.selected_kit_version}"
        )
        lines.append(
            "[INFO     ] La compatibilidad de los destinos se confirmará al ejecutar Inf2Cat"
        )
    if report.process_elevated is True:
        lines.append("[INFO     ] Consola elevada detectada; el laboratorio no hará cambios del sistema")
    elif report.process_elevated is False:
        lines.append(
            "[WARNING  ] La consola no está elevada; Inf2Cat puede rechazar la operación por permisos"
        )
    else:
        lines.append("[INFO     ] Elevación no aplicable o no verificable en este entorno")
    lines.extend(
        (
            "",
            "[SEGURIDAD] Comprobación de solo lectura; no solicita elevación.",
            "[SEGURIDAD] No firma, instala, carga ni configura drivers.",
            "[LISTO] Herramientas disponibles para validar y generar un catálogo sin firma."
            if report.ready
            else "[BLOQUEADO] No se preparará ningún paquete hasta resolver lo indicado.",
        )
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Comprueba o prepara el paquete VHF Alpha 2.3.0 sin firmarlo ni instalarlo"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check-tools", help="Comprueba InfVerif e Inf2Cat")
    check.add_argument("--json", action="store_true", help="Emite un informe sanitizado")
    prepare = subparsers.add_parser("prepare", help="Valida y crea el catálogo sin firma")
    clear = subparsers.add_parser(
        "clear-build-record",
        help="Elimina el comprobante de una compilación anterior",
    )
    record = subparsers.add_parser(
        "record-build",
        help="Registra hashes después de una compilación correcta",
    )
    for command in (prepare, clear, record):
        command.add_argument(
            "--project-root",
            type=Path,
            default=Path(__file__).resolve().parents[3],
            help=argparse.SUPPRESS,
        )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command in {"clear-build-record", "record-build"}:
        try:
            if args.command == "clear-build-record":
                removed = clear_build_record(args.project_root)
                message = (
                    "[OK] Registro de compilación anterior eliminado."
                    if removed
                    else "[OK] No había un registro de compilación anterior."
                )
                print(message)
                print("[SEGURIDAD] No se eliminaron fuentes ni binarios.")
            else:
                payload = record_successful_build(args.project_root)
                pe_validation = payload["pe_validation"]
                print("[OK] Compilación registrada mediante hashes.")
                print("[OK] SYS PE32+ AMD64 Native ejecutable con punto de entrada.")
                system_bit = (
                    "presente"
                    if pe_validation["system_characteristic_present"]
                    else "ausente"
                )
                print(
                    f"[INFO] IMAGE_FILE_SYSTEM {system_bit}; "
                    "es informativo y no bloquea el paquete."
                )
                print("[OK] La preparación ya no depende de fechas del ZIP o del reloj.")
            return 0
        except PackagePreparationError as exc:
            print(f"[BLOQUEADO] {exc}")
            return exc.exit_code
        except OSError as exc:
            print(f"[BLOQUEADO] Fallo de E/S en el registro: {type(exc).__name__}")
            return EXIT_PACKAGE_IO

    report = inspect_package_tools()
    if args.command == "check-tools":
        if args.json:
            print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(_human_tool_report(report))
        return report.exit_code

    try:
        manifest = prepare_package(args.project_root, report)
    except PackagePreparationError as exc:
        print(f"[BLOQUEADO] {exc}")
        print("[SEGURIDAD] No se conservó ningún paquete parcial.")
        return exc.exit_code
    except OSError as exc:
        print(f"[BLOQUEADO] Fallo de E/S durante el empaquetado: {type(exc).__name__}")
        print("[SEGURIDAD] No se instaló ni cargó ningún driver.")
        return EXIT_PACKAGE_IO

    print("")
    print("[OK] Registro de compilación por hashes aprobado.")
    print("[OK] InfVerif /u aprobó el INF Universal.")
    print("[OK] Inf2Cat generó un catálogo sin firma.")
    print(f"[OK] Archivos del paquete: {len(manifest['files'])}")
    for entry in manifest["files"]:
        print(f"[SHA-256] {entry['path']}: {entry['sha256']}")
    print(f"[SALIDA] native\\vhf\\out\\{PACKAGE_DIRECTORY_NAME}")
    print(f"[MANIFIESTO] native\\vhf\\out\\{PACKAGE_MANIFEST_NAME}")
    print("[BLOQUEADO] El catálogo no está firmado; el paquete no está autorizado para instalarse.")
    print("[IMPORTANTE] Esta validación no demuestra enumeración HID ni estabilidad en kernel.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
