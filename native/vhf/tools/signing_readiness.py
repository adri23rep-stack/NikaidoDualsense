"""Prepara y verifica artefactos de firma sin firmar ni instalar drivers.

Alpha 2.3.0 crea un CAB de presentación sin firma a partir de un paquete que ya
aprobó el registro por hashes, InfVerif e Inf2Cat. También puede verificar, de
forma separada y de solo lectura, un directorio devuelto por Microsoft.

Este módulo no consulta certificados, no contiene claves, no solicita
elevación, no usa red y no ejecuta comandos de instalación o carga.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

try:
    from .package_driver import (
        BUILD_RECORD_SCHEMA_VERSION,
        CATALOG_NAME,
        COPYRIGHT,
        DRIVER_NAME,
        INF_NAME,
        LAB_NAME,
        PACKAGE_DIRECTORY_NAME,
        PACKAGE_MANIFEST_NAME,
        PDB_NAME,
        PRODUCT,
        PUBLISHER,
        RELEASE,
        VERSION,
        PackagePreparationError,
        ToolExecution,
        ToolResolution,
        _kit_roots,
        _run_tool,
        _sha256,
        _version_tuple,
        inspect_package_tools,
        validate_source_inf,
    )
except ImportError:  # Ejecución directa desde el wrapper .bat.
    from package_driver import (
        BUILD_RECORD_SCHEMA_VERSION,
        CATALOG_NAME,
        COPYRIGHT,
        DRIVER_NAME,
        INF_NAME,
        LAB_NAME,
        PACKAGE_DIRECTORY_NAME,
        PACKAGE_MANIFEST_NAME,
        PDB_NAME,
        PRODUCT,
        PUBLISHER,
        RELEASE,
        VERSION,
        PackagePreparationError,
        ToolExecution,
        ToolResolution,
        _kit_roots,
        _run_tool,
        _sha256,
        _version_tuple,
        inspect_package_tools,
        validate_source_inf,
    )


SUBMISSION_DRIVER_FOLDER = "NikaidoVhfA230"
SUBMISSION_CAB_NAME = "NikaidoVhfA230Submission.cab"
SUBMISSION_MANIFEST_NAME = "NikaidoVhfA230Submission.manifest.json"
SUBMISSION_STAGING_NAME = "NikaidoVhfA230Submission.staging"
DDF_NAME = "NikaidoVhfA230Submission.ddf"

EXIT_MAKECAB_MISSING = 60
EXIT_SIGNTOOL_MISSING = 61
EXIT_PACKAGE_INVALID = 62
EXIT_PRIVACY = 63
EXIT_CAB_FAILED = 64
EXIT_CAB_INVALID = 65
EXIT_SIGNATURE_INVALID = 66
EXIT_RETURN_INVALID = 67
EXIT_SUBMISSION_IO = 68

IMAGE_NT_OPTIONAL_HDR64_MAGIC = 0x20B
IMAGE_DIRECTORY_ENTRY_SECURITY = 4
WIN_CERTIFICATE_MINIMUM_SIZE = 8


@dataclass(frozen=True, slots=True)
class SigningToolReport:
    """Herramientas locales; nunca incluye certificados ni identidades."""

    selected_kit_version: str | None
    makecab: ToolResolution
    signtool: ToolResolution

    @property
    def cab_ready(self) -> bool:
        return self.makecab.available

    @property
    def return_verification_ready(self) -> bool:
        return self.signtool.available

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "product": PRODUCT,
            "publisher": PUBLISHER,
            "release": VERSION,
            "selected_kit_version": self.selected_kit_version,
            "cab_ready": self.cab_ready,
            "return_verification_ready": self.return_verification_ready,
            "tools": [self.makecab.to_dict(), self.signtool.to_dict()],
            "certificate_store_inspected": False,
            "certificate_or_key_loaded": False,
            "mutations_performed": False,
            "privacy": {
                "contains_username": False,
                "contains_hostname": False,
                "contains_private_paths": False,
            },
        }


@dataclass(frozen=True, slots=True)
class PePayload:
    """Campos necesarios para comparar un SYS antes y después de firmarlo."""

    payload_sha256: str
    certificate_offset: int
    certificate_size: int
    number_of_sections: int

    @property
    def embedded_signature_present(self) -> bool:
        return self.certificate_size >= WIN_CERTIFICATE_MINIMUM_SIZE


class SigningReadinessError(RuntimeError):
    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


ToolRunner = Callable[[Sequence[str], Sequence[str]], ToolExecution]


def _environment_value(environment: Mapping[str, str], key: str) -> str | None:
    wanted = key.casefold()
    for candidate, value in environment.items():
        if candidate.casefold() == wanted:
            return value
    return None


def _existing_tool(
    name: str,
    candidates: Sequence[tuple[Path, str, str, str | None]],
) -> ToolResolution:
    for path, location, architecture, kit_version in candidates:
        if path.is_file():
            return ToolResolution(name, path, location, architecture, kit_version)
    return ToolResolution(name, None, "", None)


def _installed_kit_versions(kit_root: Path) -> tuple[str, ...]:
    bin_root = kit_root / "bin"
    if not bin_root.is_dir():
        return ()
    versions: list[tuple[tuple[int, ...], str]] = []
    try:
        directories = tuple(path for path in bin_root.iterdir() if path.is_dir())
    except OSError:
        return ()
    for directory in directories:
        parsed = _version_tuple(directory.name)
        if parsed is not None:
            versions.append((parsed, directory.name))
    return tuple(name for _parsed, name in sorted(versions, reverse=True))


def inspect_signing_tools(
    environment: Mapping[str, str] | None = None,
) -> SigningToolReport:
    """Localiza MakeCab y SignTool sin consultar el almacén de certificados."""

    env = dict(os.environ if environment is None else environment)
    package_tools = inspect_package_tools(env)
    selected = package_tools.selected_kit_version

    system_root_value = _environment_value(env, "SystemRoot")
    makecab_candidates: list[tuple[Path, str, str, str | None]] = []
    if system_root_value:
        system32 = Path(system_root_value) / "System32"
        makecab_candidates.append(
            (system32 / "makecab.exe", "System32", "native", None)
        )
    if os.name == "nt":
        resolved = shutil.which("makecab.exe")
        if resolved:
            makecab_candidates.append(
                (Path(resolved), "PATH", "native", None)
            )
    makecab = _existing_tool("MakeCab.exe", makecab_candidates)

    signtool_candidates: list[tuple[Path, str, str, str | None]] = []
    for root in _kit_roots(env):
        versions = list(_installed_kit_versions(root))
        if selected in versions:
            versions.remove(selected)
            versions.insert(0, selected)
        for version in versions:
            for architecture in ("x64", "x86"):
                signtool_candidates.append(
                    (
                        root / "bin" / version / architecture / "signtool.exe",
                        f"bin/<kit>/{architecture}",
                        architecture,
                        version,
                    )
                )
        for architecture in ("x64", "x86"):
            signtool_candidates.append(
                (
                    root / "bin" / architecture / "signtool.exe",
                    f"bin/{architecture}",
                    architecture,
                    None,
                )
            )
    signtool = _existing_tool("SignTool.exe", signtool_candidates)
    return SigningToolReport(selected, makecab, signtool)


def _read_json_object(path: Path, *, label: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SigningReadinessError(
            f"{label} no se puede leer o no es JSON válido: {type(exc).__name__}",
            EXIT_PACKAGE_INVALID,
        ) from exc
    if not isinstance(payload, dict):
        raise SigningReadinessError(
            f"{label} no contiene un objeto JSON",
            EXIT_PACKAGE_INVALID,
        )
    return payload


def _expected_file_entries(
    manifest: Mapping[str, object],
) -> dict[str, Mapping[str, object]]:
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise SigningReadinessError(
            "El manifiesto del paquete no contiene la lista de archivos",
            EXIT_PACKAGE_INVALID,
        )
    indexed: dict[str, Mapping[str, object]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise SigningReadinessError(
                "El manifiesto del paquete contiene una entrada inválida",
                EXIT_PACKAGE_INVALID,
            )
        name = entry["path"]
        if name in indexed:
            raise SigningReadinessError(
                "El manifiesto del paquete contiene archivos duplicados",
                EXIT_PACKAGE_INVALID,
            )
        indexed[name] = entry
    expected = {INF_NAME, DRIVER_NAME, CATALOG_NAME}
    if set(indexed) != expected:
        raise SigningReadinessError(
            "El paquete debe contener exactamente INF, SYS y CAT",
            EXIT_PACKAGE_INVALID,
        )
    return indexed


def _verify_recorded_file(
    path: Path,
    record: Mapping[str, object],
    *,
    expected_relative: str | None = None,
) -> None:
    if not path.is_file() or path.is_symlink():
        raise SigningReadinessError(
            f"Falta el artefacto requerido: {path.name}",
            EXIT_PACKAGE_INVALID,
        )
    if expected_relative is not None and record.get("path") != expected_relative:
        raise SigningReadinessError(
            f"El registro de {path.name} usa una ruta inesperada",
            EXIT_PACKAGE_INVALID,
        )
    try:
        size = path.stat().st_size
        digest = _sha256(path)
    except OSError as exc:
        raise SigningReadinessError(
            f"No se pudo verificar {path.name}: {type(exc).__name__}",
            EXIT_PACKAGE_INVALID,
        ) from exc
    if record.get("size") != size or record.get("sha256") != digest:
        raise SigningReadinessError(
            f"{path.name} no coincide con el hash registrado",
            EXIT_PACKAGE_INVALID,
        )


def validate_unsigned_package(
    project_root: Path,
) -> tuple[dict[str, object], dict[str, Path]]:
    """Valida la salida Alpha 2.3.0 antes de crear el CAB."""

    project_root = project_root.resolve()
    vhf_root = project_root / "native" / "vhf"
    output_root = vhf_root / "out"
    package_dir = output_root / PACKAGE_DIRECTORY_NAME
    manifest_path = output_root / PACKAGE_MANIFEST_NAME
    manifest = _read_json_object(manifest_path, label="El manifiesto del paquete")
    if (
        manifest.get("product") != PRODUCT
        or manifest.get("publisher") != PUBLISHER
        or manifest.get("version") != VERSION
        or manifest.get("package_directory") != PACKAGE_DIRECTORY_NAME
    ):
        raise SigningReadinessError(
            "El manifiesto pertenece a otro producto o versión",
            EXIT_PACKAGE_INVALID,
        )
    validation = manifest.get("validation")
    security = manifest.get("security")
    if (
        not isinstance(validation, dict)
        or validation.get("infverif_universal") != "passed"
        or validation.get("inf2cat") != "passed"
        or validation.get("catalog_signature") != "absent_by_design"
        or validation.get("build_record_schema_version")
        != BUILD_RECORD_SCHEMA_VERSION
        or not isinstance(security, dict)
        or security.get("driver_signed") is not False
        or security.get("driver_installed") is not False
    ):
        raise SigningReadinessError(
            "El paquete no acredita las validaciones previas requeridas",
            EXIT_PACKAGE_INVALID,
        )

    entries = _expected_file_entries(manifest)
    files = {
        name: package_dir / name
        for name in (INF_NAME, DRIVER_NAME, CATALOG_NAME)
    }
    for name, path in files.items():
        _verify_recorded_file(path, entries[name])
    if files[CATALOG_NAME].stat().st_size == 0:
        raise SigningReadinessError(
            "El catálogo sin firma está vacío",
            EXIT_PACKAGE_INVALID,
        )
    validate_source_inf(files[INF_NAME])

    symbols_record = manifest.get("symbols")
    if not isinstance(symbols_record, dict):
        raise SigningReadinessError(
            "El manifiesto no contiene el PDB registrado",
            EXIT_PACKAGE_INVALID,
        )
    symbols = vhf_root / "driver" / "x64" / "Release" / PDB_NAME
    _verify_recorded_file(
        symbols,
        symbols_record,
        expected_relative=f"native/vhf/driver/x64/Release/{PDB_NAME}",
    )
    if symbols.stat().st_size == 0:
        raise SigningReadinessError(
            "El PDB requerido está vacío",
            EXIT_PACKAGE_INVALID,
        )
    files[PDB_NAME] = symbols
    return manifest, files


def _marker_encodings(value: str) -> tuple[bytes, ...]:
    normalized = value.strip().rstrip("\\/")
    if len(normalized) < 3:
        return ()
    variants = {
        normalized,
        normalized.replace("/", "\\"),
        normalized.replace("\\", "/"),
    }
    encoded: set[bytes] = set()
    for variant in variants:
        encoded.add(variant.casefold().encode("utf-8", errors="ignore"))
        encoded.add(variant.casefold().encode("utf-16le", errors="ignore"))
    return tuple(item for item in encoded if item)


def private_markers(environment: Mapping[str, str] | None = None) -> tuple[bytes, ...]:
    env = dict(os.environ if environment is None else environment)
    values = (
        _environment_value(env, "USERPROFILE"),
        _environment_value(env, "USERNAME"),
        _environment_value(env, "COMPUTERNAME"),
        str(Path.home()) if environment is None else None,
        "C:\\Users\\",
        "C:\\Documents and Settings\\",
    )
    markers: set[bytes] = set()
    for value in values:
        if value:
            markers.update(_marker_encodings(value))
    return tuple(sorted(markers, key=len, reverse=True))


def assert_no_private_markers(
    files: Mapping[str, Path],
    markers: Sequence[bytes],
) -> None:
    """Bloquea rutas privadas conocidas en binarios destinados al CAB."""

    for name, path in files.items():
        try:
            payload = path.read_bytes().lower()
        except OSError as exc:
            raise SigningReadinessError(
                f"No se pudo auditar privacidad en {name}: {type(exc).__name__}",
                EXIT_PRIVACY,
            ) from exc
        if any(marker.lower() in payload for marker in markers if marker):
            raise SigningReadinessError(
                f"{name} contiene una ruta o identidad privada del entorno de compilación",
                EXIT_PRIVACY,
            )


def _ddf_quote(value: str) -> str:
    if any(character in value for character in ('"', "\r", "\n")):
        raise SigningReadinessError(
            "Una ruta no puede representarse de forma segura en el DDF",
            EXIT_CAB_INVALID,
        )
    return f'"{value}"'


def write_submission_ddf(
    path: Path,
    *,
    cabinet_output_directory: Path,
    source_files: Mapping[str, Path],
) -> None:
    if (
        len(SUBMISSION_DRIVER_FOLDER) >= 40
        or re.fullmatch(r"[A-Za-z0-9]+", SUBMISSION_DRIVER_FOLDER) is None
    ):
        raise SigningReadinessError(
            "La subcarpeta del CAB no cumple la restricción de Partner Center",
            EXIT_CAB_INVALID,
        )
    if set(source_files) != {INF_NAME, DRIVER_NAME, PDB_NAME, CATALOG_NAME}:
        raise SigningReadinessError(
            "El DDF requiere exactamente INF, SYS, PDB y CAT",
            EXIT_CAB_INVALID,
        )
    lines = [
        "; Nikaido DualSense Alpha 2.3.0 - DDF temporal",
        ".OPTION EXPLICIT",
        ".Set CabinetFileCountThreshold=0",
        ".Set FolderFileCountThreshold=0",
        ".Set FolderSizeThreshold=0",
        ".Set MaxCabinetSize=0",
        ".Set MaxDiskFileCount=0",
        ".Set MaxDiskSize=0",
        ".Set CompressionType=MSZIP",
        ".Set Cabinet=on",
        ".Set Compress=on",
        f".Set CabinetNameTemplate={SUBMISSION_CAB_NAME}",
        f".Set DiskDirectoryTemplate={_ddf_quote(str(cabinet_output_directory.resolve()))}",
        f".Set DestinationDir={SUBMISSION_DRIVER_FOLDER}",
    ]
    for name in (INF_NAME, DRIVER_NAME, PDB_NAME, CATALOG_NAME):
        source = source_files[name].resolve()
        lines.append(f"{_ddf_quote(str(source))} {_ddf_quote(name)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_cab_file_names(path: Path) -> tuple[str, ...]:
    """Lee solamente la tabla CFFILE de un CAB y devuelve sus nombres."""

    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise SigningReadinessError(
            f"No se pudo leer el CAB: {type(exc).__name__}",
            EXIT_CAB_INVALID,
        ) from exc
    try:
        if len(payload) < 36 or payload[:4] != b"MSCF":
            raise ValueError("firma MSCF ausente")
        cabinet_size = struct.unpack_from("<I", payload, 8)[0]
        files_offset = struct.unpack_from("<I", payload, 16)[0]
        file_count = struct.unpack_from("<H", payload, 28)[0]
        if cabinet_size > len(payload) or files_offset < 36 or files_offset >= len(payload):
            raise ValueError("cabecera fuera de rango")
        if file_count == 0 or file_count > 64:
            raise ValueError("cantidad de archivos fuera de rango")
        cursor = files_offset
        names: list[str] = []
        for _index in range(file_count):
            if cursor + 16 > len(payload):
                raise ValueError("registro CFFILE truncado")
            cursor += 16
            terminator = payload.find(b"\0", cursor)
            if terminator < 0:
                raise ValueError("nombre CFFILE sin terminador")
            raw_name = payload[cursor:terminator]
            if not raw_name:
                raise ValueError("nombre CFFILE vacío")
            name = raw_name.decode("ascii")
            names.append(name.replace("/", "\\"))
            cursor = terminator + 1
    except (UnicodeError, struct.error, ValueError) as exc:
        raise SigningReadinessError(
            f"El CAB no tiene una estructura válida: {exc}",
            EXIT_CAB_INVALID,
        ) from exc
    if len(set(name.casefold() for name in names)) != len(names):
        raise SigningReadinessError(
            "El CAB contiene nombres duplicados",
            EXIT_CAB_INVALID,
        )
    return tuple(names)


def _safe_remove(path: Path, output_root: Path) -> None:
    allowed = {
        SUBMISSION_STAGING_NAME,
        SUBMISSION_CAB_NAME,
        SUBMISSION_MANIFEST_NAME,
        f"{SUBMISSION_MANIFEST_NAME}.tmp",
    }
    if path.name not in allowed or path.parent.resolve() != output_root.resolve():
        raise SigningReadinessError(
            "Se rechazó una ruta fuera de la salida controlada",
            EXIT_SUBMISSION_IO,
        )
    if path.is_symlink():
        raise SigningReadinessError(
            "Se rechazó un enlace simbólico en la salida controlada",
            EXIT_SUBMISSION_IO,
        )
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _source_file_records(files: Mapping[str, Path]) -> list[dict[str, object]]:
    records = []
    for name in (INF_NAME, DRIVER_NAME, PDB_NAME, CATALOG_NAME):
        path = files[name]
        records.append(
            {
                "path": f"{SUBMISSION_DRIVER_FOLDER}/{name}",
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return records


def _write_submission_manifest(
    path: Path,
    *,
    cab: Path,
    package_manifest_path: Path,
    source_files: Mapping[str, Path],
    tools: SigningToolReport,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "product": PRODUCT,
        "publisher": PUBLISHER,
        "copyright": COPYRIGHT,
        "version": VERSION,
        "release": RELEASE,
        "lab_name": LAB_NAME,
        "submission_type": "attestation_testing_candidate",
        "cab": {
            "path": SUBMISSION_CAB_NAME,
            "size": cab.stat().st_size,
            "sha256": _sha256(cab),
        },
        "cab_structure": {
            "driver_folder": SUBMISSION_DRIVER_FOLDER,
            "files_at_root": 0,
            "files": _source_file_records(source_files),
        },
        "source_package_manifest": {
            "path": f"native/vhf/out/{PACKAGE_MANIFEST_NAME}",
            "sha256": _sha256(package_manifest_path),
        },
        "validation": {
            "package_hashes": "passed",
            "infverif_universal": "passed_before_cab",
            "inf2cat": "passed_before_cab",
            "pdb_present": True,
            "private_build_markers": "absent",
            "cab_header": "MSCF",
            "cab_file_table": "passed",
            "cab_driver_subfolder": "passed",
        },
        "signing": {
            "cab_signature": "absent_by_design",
            "microsoft_signature": "not_requested",
            "certificate_store_inspected": False,
            "certificate_or_key_loaded": False,
            "ready_for_ev_signature": True,
            "ready_for_partner_center_submission": False,
            "partner_center_blocker": "cab_requires_registered_certificate_signature",
            "signtool_detected_for_future_verification": tools.signtool.available,
        },
        "security": {
            "driver_installed": False,
            "driver_loaded": False,
            "automatic_elevation": False,
            "secure_boot_changes": False,
            "memory_integrity_changes": False,
            "test_signing_changes": False,
            "network_access": False,
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


def create_submission_cab(
    project_root: Path,
    tools: SigningToolReport,
    *,
    environment: Mapping[str, str] | None = None,
    runner: ToolRunner = _run_tool,
) -> dict[str, object]:
    if not tools.makecab.available or tools.makecab.path is None:
        raise SigningReadinessError(
            "MakeCab.exe no está disponible",
            EXIT_MAKECAB_MISSING,
        )

    project_root = project_root.resolve()
    package_manifest, source_files = validate_unsigned_package(project_root)
    del package_manifest
    assert_no_private_markers(source_files, private_markers(environment))

    output_root = project_root / "native" / "vhf" / "out"
    package_manifest_path = output_root / PACKAGE_MANIFEST_NAME
    staging = output_root / SUBMISSION_STAGING_NAME
    final_cab = output_root / SUBMISSION_CAB_NAME
    final_manifest = output_root / SUBMISSION_MANIFEST_NAME
    manifest_temporary = final_manifest.with_suffix(final_manifest.suffix + ".tmp")
    if staging.exists() or staging.is_symlink():
        _safe_remove(staging, output_root)
    staging.mkdir(parents=True)
    ddf = staging / DDF_NAME
    staged_cab = staging / SUBMISSION_CAB_NAME

    private_values = (
        str(project_root),
        str(Path.home()),
        _environment_value(dict(os.environ if environment is None else environment), "USERPROFILE")
        or "",
        _environment_value(dict(os.environ if environment is None else environment), "USERNAME")
        or "",
        _environment_value(dict(os.environ if environment is None else environment), "COMPUTERNAME")
        or "",
    )
    try:
        write_submission_ddf(
            ddf,
            cabinet_output_directory=staging,
            source_files=source_files,
        )
        execution = runner(
            (str(tools.makecab.path), "/F", str(ddf)),
            private_values,
        )
        if execution.output:
            print(execution.output)
        if execution.returncode != 0:
            raise SigningReadinessError(
                f"MakeCab rechazó la presentación con código {execution.returncode}",
                EXIT_CAB_FAILED,
            )
        if ddf.is_file():
            ddf.unlink()
        if not staged_cab.is_file() or staged_cab.stat().st_size == 0:
            raise SigningReadinessError(
                "MakeCab terminó sin producir el CAB esperado",
                EXIT_CAB_INVALID,
            )
        expected_names = {
            f"{SUBMISSION_DRIVER_FOLDER}\\{name}".casefold()
            for name in (INF_NAME, DRIVER_NAME, PDB_NAME, CATALOG_NAME)
        }
        actual_names = {name.casefold() for name in read_cab_file_names(staged_cab)}
        if actual_names != expected_names:
            raise SigningReadinessError(
                "El CAB no contiene exactamente la subcarpeta y los cuatro archivos esperados",
                EXIT_CAB_INVALID,
            )

        if final_cab.exists() or final_cab.is_symlink():
            _safe_remove(final_cab, output_root)
        staged_cab.replace(final_cab)
        if final_manifest.exists() or final_manifest.is_symlink():
            _safe_remove(final_manifest, output_root)
        manifest = _write_submission_manifest(
            final_manifest,
            cab=final_cab,
            package_manifest_path=package_manifest_path,
            source_files=source_files,
            tools=tools,
        )
        _safe_remove(staging, output_root)
        return manifest
    except Exception:
        if staging.exists() and not staging.is_symlink():
            _safe_remove(staging, output_root)
        if manifest_temporary.exists() or manifest_temporary.is_symlink():
            _safe_remove(manifest_temporary, output_root)
        raise


def inspect_pe_payload(path: Path) -> PePayload:
    """Calcula una huella de cabeceras y secciones, excluyendo la firma PE."""

    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise SigningReadinessError(
            f"No se pudo leer {path.name}: {type(exc).__name__}",
            EXIT_RETURN_INVALID,
        ) from exc
    try:
        if len(payload) < 256 or payload[:2] != b"MZ":
            raise ValueError("cabecera DOS ausente")
        pe_offset = struct.unpack_from("<I", payload, 0x3C)[0]
        if pe_offset + 24 > len(payload) or payload[pe_offset : pe_offset + 4] != b"PE\0\0":
            raise ValueError("cabecera PE ausente")
        number_of_sections = struct.unpack_from("<H", payload, pe_offset + 6)[0]
        optional_size = struct.unpack_from("<H", payload, pe_offset + 20)[0]
        optional_offset = pe_offset + 24
        if optional_offset + optional_size > len(payload):
            raise ValueError("cabecera opcional truncada")
        if struct.unpack_from("<H", payload, optional_offset)[0] != IMAGE_NT_OPTIONAL_HDR64_MAGIC:
            raise ValueError("el SYS no es PE32+")
        if optional_size < 152:
            raise ValueError("cabecera opcional demasiado corta")
        size_of_headers = struct.unpack_from("<I", payload, optional_offset + 60)[0]
        checksum_offset = optional_offset + 64
        security_offset = optional_offset + 112 + IMAGE_DIRECTORY_ENTRY_SECURITY * 8
        certificate_offset, certificate_size = struct.unpack_from(
            "<II", payload, security_offset
        )
        section_table = optional_offset + optional_size
        if (
            number_of_sections == 0
            or section_table + number_of_sections * 40 > len(payload)
            or size_of_headers < section_table + number_of_sections * 40
            or size_of_headers > len(payload)
        ):
            raise ValueError("tabla de secciones inválida")
        if certificate_size:
            if (
                certificate_size < WIN_CERTIFICATE_MINIMUM_SIZE
                or certificate_offset < size_of_headers
                or certificate_offset + certificate_size > len(payload)
            ):
                raise ValueError("tabla de certificados fuera de rango")

        normalized_headers = bytearray(payload[:size_of_headers])
        normalized_headers[checksum_offset : checksum_offset + 4] = b"\0" * 4
        normalized_headers[security_offset : security_offset + 8] = b"\0" * 8
        digest = hashlib.sha256()
        digest.update(normalized_headers)
        sections: list[tuple[int, int]] = []
        for index in range(number_of_sections):
            entry = section_table + index * 40
            raw_size = struct.unpack_from("<I", payload, entry + 16)[0]
            raw_offset = struct.unpack_from("<I", payload, entry + 20)[0]
            if raw_size == 0:
                continue
            if raw_offset < size_of_headers or raw_offset + raw_size > len(payload):
                raise ValueError("sección fuera de rango")
            sections.append((raw_offset, raw_size))
        for raw_offset, raw_size in sorted(sections):
            digest.update(payload[raw_offset : raw_offset + raw_size])
    except (struct.error, ValueError) as exc:
        raise SigningReadinessError(
            f"{path.name} no es un SYS PE válido: {exc}",
            EXIT_RETURN_INVALID,
        ) from exc
    return PePayload(
        payload_sha256=digest.hexdigest(),
        certificate_offset=certificate_offset,
        certificate_size=certificate_size,
        number_of_sections=number_of_sections,
    )


def _direct_return_files(directory: Path) -> dict[str, Path]:
    if not directory.is_dir() or directory.is_symlink():
        raise SigningReadinessError(
            "La ruta devuelta debe ser un directorio local extraído",
            EXIT_RETURN_INVALID,
        )
    files = {
        name: directory / name
        for name in (INF_NAME, DRIVER_NAME, CATALOG_NAME)
    }
    missing = [name for name, path in files.items() if not path.is_file() or path.is_symlink()]
    if missing:
        raise SigningReadinessError(
            "El directorio devuelto no contiene INF, SYS y CAT en su raíz",
            EXIT_RETURN_INVALID,
        )
    pdb = directory / PDB_NAME
    if pdb.is_file() and not pdb.is_symlink():
        files[PDB_NAME] = pdb
    return files


def validate_submission_manifest(
    project_root: Path,
    manifest: Mapping[str, object],
) -> None:
    """Comprueba que la respuesta se compare con el CAB local manifestado."""

    output_root = project_root / "native" / "vhf" / "out"
    if (
        manifest.get("product") != PRODUCT
        or manifest.get("publisher") != PUBLISHER
        or manifest.get("version") != VERSION
    ):
        raise SigningReadinessError(
            "El manifiesto de presentación pertenece a otra versión",
            EXIT_RETURN_INVALID,
        )
    cab_record = manifest.get("cab")
    source_record = manifest.get("source_package_manifest")
    signing = manifest.get("signing")
    if (
        not isinstance(cab_record, dict)
        or not isinstance(source_record, dict)
        or not isinstance(signing, dict)
        or signing.get("cab_signature") != "absent_by_design"
        or signing.get("microsoft_signature") != "not_requested"
    ):
        raise SigningReadinessError(
            "El manifiesto de presentación está incompleto",
            EXIT_RETURN_INVALID,
        )
    _verify_recorded_file(
        output_root / SUBMISSION_CAB_NAME,
        cab_record,
        expected_relative=SUBMISSION_CAB_NAME,
    )
    _verify_recorded_file(
        output_root / PACKAGE_MANIFEST_NAME,
        source_record,
        expected_relative=f"native/vhf/out/{PACKAGE_MANIFEST_NAME}",
    )


def verify_microsoft_return(
    project_root: Path,
    returned_directory: Path,
    tools: SigningToolReport,
    *,
    runner: ToolRunner = _run_tool,
) -> dict[str, object]:
    """Verifica firmas y procedencia sin copiar ni instalar el paquete."""

    if not tools.signtool.available or tools.signtool.path is None:
        raise SigningReadinessError(
            "SignTool.exe no está disponible para verificar la respuesta",
            EXIT_SIGNTOOL_MISSING,
        )
    project_root = project_root.resolve()
    output_root = project_root / "native" / "vhf" / "out"
    _package_manifest, _source_files = validate_unsigned_package(project_root)
    submission_manifest = _read_json_object(
        output_root / SUBMISSION_MANIFEST_NAME,
        label="El manifiesto de presentación",
    )
    validate_submission_manifest(project_root, submission_manifest)
    unsigned_package = output_root / PACKAGE_DIRECTORY_NAME
    original_inf = unsigned_package / INF_NAME
    original_driver = unsigned_package / DRIVER_NAME
    original_pdb = (
        project_root / "native" / "vhf" / "driver" / "x64" / "Release" / PDB_NAME
    )
    returned = _direct_return_files(returned_directory.resolve())
    if _sha256(returned[INF_NAME]) != _sha256(original_inf):
        raise SigningReadinessError(
            "El INF devuelto no coincide con el presentado",
            EXIT_RETURN_INVALID,
        )
    unsigned_payload = inspect_pe_payload(original_driver)
    signed_payload = inspect_pe_payload(returned[DRIVER_NAME])
    if unsigned_payload.embedded_signature_present:
        raise SigningReadinessError(
            "El SYS de origen ya contiene una firma inesperada",
            EXIT_RETURN_INVALID,
        )
    if not signed_payload.embedded_signature_present:
        raise SigningReadinessError(
            "El SYS devuelto no contiene una firma PE incrustada",
            EXIT_SIGNATURE_INVALID,
        )
    if unsigned_payload.payload_sha256 != signed_payload.payload_sha256:
        raise SigningReadinessError(
            "Las cabeceras o secciones del SYS cambiaron además de la firma",
            EXIT_RETURN_INVALID,
        )
    if PDB_NAME in returned and _sha256(returned[PDB_NAME]) != _sha256(original_pdb):
        raise SigningReadinessError(
            "El PDB devuelto no coincide con el presentado",
            EXIT_RETURN_INVALID,
        )

    private_values = (
        str(project_root),
        str(returned_directory.resolve()),
        str(Path.home()),
        os.environ.get("USERPROFILE", ""),
        os.environ.get("USERNAME", ""),
        os.environ.get("COMPUTERNAME", ""),
    )
    commands = (
        (
            str(tools.signtool.path),
            "verify",
            "/kp",
            "/v",
            "/all",
            str(returned[CATALOG_NAME]),
        ),
        (
            str(tools.signtool.path),
            "verify",
            "/kp",
            "/v",
            "/all",
            str(returned[DRIVER_NAME]),
        ),
        (
            str(tools.signtool.path),
            "verify",
            "/kp",
            "/v",
            "/c",
            str(returned[CATALOG_NAME]),
            str(returned[INF_NAME]),
        ),
        (
            str(tools.signtool.path),
            "verify",
            "/kp",
            "/v",
            "/c",
            str(returned[CATALOG_NAME]),
            str(returned[DRIVER_NAME]),
        ),
    )
    for command in commands:
        result = runner(command, private_values)
        if result.output:
            print(result.output)
        if result.returncode != 0:
            raise SigningReadinessError(
                f"SignTool rechazó una verificación con código {result.returncode}",
                EXIT_SIGNATURE_INVALID,
            )

    return {
        "schema_version": 1,
        "product": PRODUCT,
        "publisher": PUBLISHER,
        "version": VERSION,
        "release": RELEASE,
        "verification": {
            "inf_matches_submission": True,
            "sys_payload_matches_submission": True,
            "sys_embedded_signature": "passed_signtool_kp",
            "catalog_signature": "passed_signtool_kp",
            "inf_catalog_membership": "passed_signtool_kp",
            "sys_catalog_membership": "passed_signtool_kp",
            "pdb_matches_submission": (
                True if PDB_NAME in returned else "not_returned"
            ),
        },
        "security": {
            "driver_installed": False,
            "driver_loaded": False,
            "automatic_elevation": False,
            "system_changes": False,
        },
        "privacy": {
            "contains_username": False,
            "contains_hostname": False,
            "contains_private_paths": False,
        },
    }


def _human_tool_report(report: SigningToolReport) -> str:
    lines = [
        "Nikaido DualSense 3.0.0 Alpha 2.3.0 — Microsoft Signing Readiness",
        "",
    ]
    if report.makecab.available:
        lines.append(
            f"[OK       ] {report.makecab.name} detectado ({report.makecab.location})"
        )
    else:
        lines.append("[BLOQUEADO] MakeCab.exe no está disponible")
    if report.signtool.available:
        suffix = (
            f", kit {report.signtool.kit_version}"
            if report.signtool.kit_version
            else ""
        )
        lines.append(
            f"[OK       ] {report.signtool.name} detectado "
            f"({report.signtool.location}, {report.signtool.architecture}{suffix})"
        )
    else:
        lines.append(
            "[INFO     ] SignTool.exe no está disponible; solo bloqueará la verificación futura"
        )
    lines.extend(
        (
            "",
            "[SEGURIDAD] No se inspeccionó el almacén de certificados.",
            "[SEGURIDAD] No se cargaron claves, no se firmó y no se solicitó elevación.",
            "[SEGURIDAD] No se instaló, cargó ni registró ningún driver.",
            (
                "[LISTO] Entorno disponible para crear un CAB sin firma."
                if report.cab_ready
                else "[BLOQUEADO] No se puede crear el CAB hasta disponer de MakeCab.exe."
            ),
        )
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepara o verifica la firma Alpha 2.3.0 sin instalar drivers"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser(
        "check-tools",
        help="Comprueba MakeCab y SignTool sin consultar certificados",
    )
    check.add_argument("--json", action="store_true")
    create = subparsers.add_parser(
        "create-submission",
        help="Crea un CAB de presentación sin firma",
    )
    verify = subparsers.add_parser(
        "verify-return",
        help="Verifica un directorio firmado devuelto por Microsoft",
    )
    for command in (create, verify):
        command.add_argument(
            "--project-root",
            type=Path,
            default=Path(__file__).resolve().parents[3],
            help=argparse.SUPPRESS,
        )
    verify.add_argument(
        "returned_directory",
        type=Path,
        help="Directorio extraído que contiene INF, SYS y CAT firmados",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tools = inspect_signing_tools()
    if args.command == "check-tools":
        if args.json:
            print(json.dumps(tools.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(_human_tool_report(tools))
        return 0 if tools.cab_ready else EXIT_MAKECAB_MISSING

    try:
        if args.command == "create-submission":
            manifest = create_submission_cab(args.project_root, tools)
            print("")
            print("[OK] CAB de presentación creado con INF, SYS, PDB y CAT.")
            print("[OK] El CAB usa una subcarpeta corta y no contiene archivos en la raíz.")
            print(f"[SHA-256] {SUBMISSION_CAB_NAME}: {manifest['cab']['sha256']}")
            print(f"[SALIDA] native\\vhf\\out\\{SUBMISSION_CAB_NAME}")
            print(f"[MANIFIESTO] native\\vhf\\out\\{SUBMISSION_MANIFEST_NAME}")
            print("[BLOQUEADO] El CAB sigue sin firma y no debe enviarse ni instalarse todavía.")
            print("[SIGUIENTE] Firma manualmente el CAB según tu proveedor y Partner Center.")
        else:
            result = verify_microsoft_return(
                args.project_root,
                args.returned_directory,
                tools,
            )
            print("")
            print("[OK] SignTool /kp aprobó SYS, CAT y pertenencia del paquete.")
            print("[OK] El contenido PE del SYS coincide con el presentado; solo se admite la firma.")
            print(
                "[INFO] PDB: "
                + (
                    "coincide con el presentado."
                    if result["verification"]["pdb_matches_submission"] is True
                    else "Microsoft no lo devolvió; no es un bloqueo."
                )
            )
            print("[BLOQUEADO] La verificación no instala ni enumera el dispositivo.")
            print("[IMPORTANTE] Una firma válida todavía no demuestra estabilidad en kernel.")
        return 0
    except (SigningReadinessError, PackagePreparationError) as exc:
        print(f"[BLOQUEADO] {exc}")
        print("[SEGURIDAD] No se firmó, instaló ni cargó ningún driver.")
        return exc.exit_code
    except OSError as exc:
        print(f"[BLOQUEADO] Fallo de E/S: {type(exc).__name__}")
        print("[SEGURIDAD] No se modificó Windows.")
        return EXIT_SUBMISSION_IO


if __name__ == "__main__":
    sys.exit(main())
