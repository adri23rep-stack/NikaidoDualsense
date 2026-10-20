"""Comprobación de solo lectura del toolchain VHF para Visual Studio 2026.

La presencia aislada de ``vhf.h`` o ``VhfKm.lib`` no demuestra que MSBuild
pueda construir un driver. Este módulo valida también el toolset de C++, la
integración de WDK con MSBuild y un conjunto SDK/WDK coherente.

Alpha 2.3.0 también informa cada componente del kit por separado. Esto evita
convertir un único archivo ausente en una recomendación genérica de reinstalar
Visual Studio o todo el entorno de desarrollo.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


MINIMUM_VS_MAJOR = 18
MINIMUM_MSVC = (14, 50)
MINIMUM_KIT_BUILD = 28000

KIT_COMPONENTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ntddk.h", ("Include", "{version}", "km", "ntddk.h")),
    ("vhf.h", ("Include", "{version}", "shared", "vhf.h")),
    ("guiddef.h", ("Include", "{version}", "shared", "guiddef.h")),
    ("Windows.h", ("Include", "{version}", "um", "Windows.h")),
    ("VhfKm.lib", ("Lib", "{version}", "km", "x64", "VhfKm.lib")),
    ("SetupAPI.lib", ("Lib", "{version}", "um", "x64", "SetupAPI.lib")),
    (
        "WindowsDriver.KernelMode.Driver.props",
        ("build", "{version}", "WindowsDriver.KernelMode.Driver.props"),
    ),
    (
        "Microsoft.DriverKit.Build.Tasks.18.0.dll",
        ("build", "{version}", "bin", "Microsoft.DriverKit.Build.Tasks.18.0.dll"),
    ),
)

EXIT_CODES = {
    "msbuild": 20,
    "visual_studio_2026": 21,
    "v145_toolset": 22,
    "wdk_msbuild_integration": 23,
    "sdk_wdk_pair": 24,
    "spectre_x64": 25,
}


@dataclass(frozen=True, slots=True)
class ToolchainCheck:
    check_id: str
    ok: bool
    summary: str
    guidance: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.check_id,
            "status": "ok" if self.ok else "blocked",
            "summary": self.summary,
            "guidance": self.guidance if not self.ok else "",
        }


@dataclass(frozen=True, slots=True)
class KitComponentCheck:
    name: str
    present: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": "ok" if self.present else "missing",
        }


@dataclass(frozen=True, slots=True)
class KitInspection:
    version: str
    build: int
    supported_family: bool
    components: tuple[KitComponentCheck, ...]

    @property
    def complete(self) -> bool:
        return all(component.present for component in self.components)

    @property
    def missing_components(self) -> tuple[str, ...]:
        return tuple(component.name for component in self.components if not component.present)

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "build_family": self.build,
            "supported_family": self.supported_family,
            "complete": self.complete,
            "components": [component.to_dict() for component in self.components],
        }


@dataclass(frozen=True, slots=True)
class ToolchainReport:
    checks: tuple[ToolchainCheck, ...]
    msbuild_version: str | None
    selected_kit_version: str | None
    available_kit_builds: tuple[int, ...]
    kit_inspections: tuple[KitInspection, ...]

    @property
    def ready(self) -> bool:
        return all(check.ok for check in self.checks)

    @property
    def exit_code(self) -> int:
        for check in self.checks:
            if not check.ok:
                return EXIT_CODES[check.check_id]
        return 0

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 2,
            "product": "Nikaido DualSense",
            "publisher": "Team Nikaido",
            "release": "3.0.0-alpha.2.3.0",
            "toolchain_ready": self.ready,
            "msbuild_version": self.msbuild_version,
            "selected_kit_version": self.selected_kit_version,
            "available_kit_builds": list(self.available_kit_builds),
            "kit_inspections": [inspection.to_dict() for inspection in self.kit_inspections],
            "checks": [check.to_dict() for check in self.checks],
            "privacy": {
                "contains_username": False,
                "contains_hostname": False,
                "contains_private_paths": False,
            },
            "mutations_performed": False,
        }


def _numeric_version(value: str | None) -> tuple[int, ...] | None:
    if not value:
        return None
    match = re.search(r"(?<!\d)(\d+)\.(\d+)(?:\.(\d+))?(?:\.(\d+))?", value)
    if not match:
        return None
    return tuple(int(part) for part in match.groups(default="0"))


def _unique_existing_directories(paths: Iterable[Path]) -> tuple[Path, ...]:
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in paths:
        try:
            normalized = candidate.resolve()
        except OSError:
            normalized = candidate
        key = os.path.normcase(str(normalized))
        if key in seen or not candidate.is_dir():
            continue
        seen.add(key)
        unique.append(candidate)
    return tuple(unique)


def _toolset_props_present(vs_install: Path | None, toolset: str) -> bool:
    if vs_install is None or not vs_install.is_dir():
        return False
    vc_msbuild = vs_install / "MSBuild" / "Microsoft" / "VC"
    if not vc_msbuild.is_dir():
        return False
    try:
        return any(
            path.parent.name.lower() == toolset.lower()
            for path in vc_msbuild.rglob("Toolset.props")
        )
    except OSError:
        return False


def _vc_tool_roots(vs_install: Path | None, explicit_roots: Sequence[Path]) -> tuple[Path, ...]:
    candidates = list(explicit_roots)
    if vs_install is not None:
        parent = vs_install / "VC" / "Tools" / "MSVC"
        if parent.is_dir():
            try:
                candidates.extend(path for path in parent.iterdir() if path.is_dir())
            except OSError:
                pass
    return _unique_existing_directories(candidates)


def _has_msvc_145(vc_roots: Sequence[Path]) -> bool:
    for root in vc_roots:
        version = _numeric_version(root.name)
        compiler = root / "bin" / "Hostx64" / "x64" / "cl.exe"
        if version is not None and version[:2] >= MINIMUM_MSVC and compiler.is_file():
            return True
    return False


def _has_spectre_x64(vc_roots: Sequence[Path]) -> bool:
    return any((root / "lib" / "spectre" / "x64" / "libcmt.lib").is_file() for root in vc_roots)


def _normalize_kit_root(path: Path) -> Path:
    if path.name.lower() in {"include", "lib", "bin", "build"}:
        return path.parent
    return path


def _kit_candidates(kit_roots: Sequence[Path]) -> tuple[tuple[tuple[int, ...], str], ...]:
    candidates: dict[str, tuple[int, ...]] = {}
    for supplied_root in kit_roots:
        root = _normalize_kit_root(supplied_root)
        include = root / "Include"
        if not include.is_dir():
            continue
        try:
            version_directories = tuple(path for path in include.iterdir() if path.is_dir())
        except OSError:
            continue
        for directory in version_directories:
            parsed = _numeric_version(directory.name)
            if parsed is not None and parsed[0:2] == (10, 0):
                candidates[directory.name] = parsed
    ordered = sorted(
        ((version, name) for name, version in candidates.items()),
        reverse=True,
    )
    return tuple(ordered)


def _inspect_kit(root: Path, version: str, parsed: tuple[int, ...]) -> KitInspection:
    components: list[KitComponentCheck] = []
    for name, relative_parts in KIT_COMPONENTS:
        relative = Path(*(part.format(version=version) for part in relative_parts))
        components.append(KitComponentCheck(name=name, present=(root / relative).is_file()))
    build = parsed[2] if len(parsed) >= 3 else 0
    return KitInspection(
        version=version,
        build=build,
        supported_family=build >= MINIMUM_KIT_BUILD,
        components=tuple(components),
    )


def _inspect_kits(kit_roots: Sequence[Path]) -> tuple[KitInspection, ...]:
    normalized_roots = _unique_existing_directories(
        _normalize_kit_root(path) for path in kit_roots
    )
    inspections: list[KitInspection] = []
    for version, name in _kit_candidates(normalized_roots):
        candidates = [_inspect_kit(root, name, version) for root in normalized_roots]
        if not candidates:
            continue
        # Nunca se combinan headers y bibliotecas de raíces distintas. Si la
        # misma versión aparece en más de una raíz, se muestra la copia con más
        # componentes presentes.
        inspections.append(
            max(candidates, key=lambda item: sum(component.present for component in item.components))
        )
    inspections.sort(key=lambda item: _numeric_version(item.version) or (), reverse=True)
    return tuple(inspections)


def _select_kit(
    kit_roots: Sequence[Path],
) -> tuple[str | None, tuple[int, ...], tuple[KitInspection, ...]]:
    inspections = _inspect_kits(kit_roots)
    available_builds: set[int] = set()
    valid: list[KitInspection] = []
    for inspection in inspections:
        available_builds.add(inspection.build)
        if inspection.supported_family and inspection.complete:
            valid.append(inspection)
    return (
        valid[0].version if valid else None,
        tuple(sorted(available_builds)),
        inspections,
    )


def _pair_failure_summary(inspections: Sequence[KitInspection]) -> tuple[str, str]:
    eligible = [inspection for inspection in inspections if inspection.supported_family]
    if eligible:
        selected = eligible[0]
        missing = ", ".join(selected.missing_components)
        summary = f"SDK/WDK {selected.version} incompleto; falta: {missing}"
        if selected.missing_components == ("vhf.h",):
            guidance = (
                "Falta únicamente vhf.h. No repitas la reparación de Visual Studio: "
                "comprueba el instalador independiente del WDK de la misma familia. "
                "No copies el header desde otro kit."
            )
        else:
            guidance = (
                "Completa en el WDK de esa misma versión solamente los componentes "
                f"indicados: {missing}. No mezcles archivos entre kits."
            )
        return summary, guidance

    if inspections:
        detected = ", ".join(inspection.version for inspection in inspections)
        return (
            f"No hay un conjunto SDK/WDK de la familia 28000; detectados: {detected}",
            "Instala un SDK y WDK 28000 emparejados; no mezcles headers o bibliotecas 26100.",
        )
    return (
        "No se detectaron archivos de SDK/WDK",
        "Instala el SDK y el WDK independientes de la misma familia 28000.",
    )


def evaluate_toolchain(
    *,
    msbuild_version: str | None,
    vs_install: Path | None,
    kit_roots: Sequence[Path],
    explicit_vc_tool_roots: Sequence[Path] = (),
) -> ToolchainReport:
    """Evalúa rutas ya resueltas y devuelve únicamente metadatos sanitizados."""

    checks: list[ToolchainCheck] = []
    parsed_msbuild = _numeric_version(msbuild_version)
    checks.append(
        ToolchainCheck(
            "msbuild",
            parsed_msbuild is not None,
            f"MSBuild {msbuild_version} detectado" if parsed_msbuild else "MSBuild no está disponible",
            "Abre Developer Command Prompt for VS 2026.",
        )
    )

    vs2026 = parsed_msbuild is not None and parsed_msbuild[0] == MINIMUM_VS_MAJOR
    checks.append(
        ToolchainCheck(
            "visual_studio_2026",
            vs2026,
            "MSBuild pertenece a Visual Studio 2026"
            if vs2026
            else "Se requiere MSBuild 18 de Visual Studio 2026",
            "Instala o abre Visual Studio 2026; no es necesario quitar otras versiones.",
        )
    )

    vc_roots = _vc_tool_roots(vs_install, explicit_vc_tool_roots)
    v145 = _toolset_props_present(vs_install, "v145") and _has_msvc_145(vc_roots)
    checks.append(
        ToolchainCheck(
            "v145_toolset",
            v145,
            "PlatformToolset v145 y compilador MSVC 14.5x x64 detectados"
            if v145
            else "PlatformToolset v145 o compilador MSVC 14.5x x64 incompleto",
            "Agrega Desktop development with C++ y las herramientas MSVC más recientes.",
        )
    )

    wdk_integration = _toolset_props_present(vs_install, "WindowsKernelModeDriver10.0")
    checks.append(
        ToolchainCheck(
            "wdk_msbuild_integration",
            wdk_integration,
            "Integración WindowsKernelModeDriver10.0 de WDK detectada"
            if wdk_integration
            else "WDK existe parcialmente, pero su integración con MSBuild no está disponible",
            "En Visual Studio Installer agrega el componente individual Windows Driver Kit.",
        )
    )

    selected_kit, builds, kit_inspections = _select_kit(kit_roots)
    pair_ready = selected_kit is not None
    if pair_ready:
        pair_summary = f"SDK/WDK x64 compatibles detectados ({selected_kit})"
        pair_guidance = ""
    else:
        pair_summary, pair_guidance = _pair_failure_summary(kit_inspections)
    checks.append(
        ToolchainCheck(
            "sdk_wdk_pair",
            pair_ready,
            pair_summary,
            pair_guidance,
        )
    )

    spectre = _has_spectre_x64(vc_roots)
    checks.append(
        ToolchainCheck(
            "spectre_x64",
            spectre,
            "Bibliotecas Spectre x64 de MSVC detectadas"
            if spectre
            else "Faltan las bibliotecas Spectre x64 de MSVC",
            "Agrega C++ Spectre-mitigated libraries for x64/x86 (Latest MSVC).",
        )
    )

    return ToolchainReport(
        checks=tuple(checks),
        msbuild_version=msbuild_version if parsed_msbuild else None,
        selected_kit_version=selected_kit,
        available_kit_builds=builds,
        kit_inspections=kit_inspections,
    )


def _capture(command: Sequence[str]) -> str | None:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _env_get(environment: Mapping[str, str], key: str) -> str | None:
    """Obtiene variables sin depender de mayúsculas en mappings simulados."""

    expected = key.casefold()
    for candidate, value in environment.items():
        if candidate.casefold() == expected:
            return value
    return None


def _find_vs_install(environment: Mapping[str, str], msbuild: str | None) -> Path | None:
    direct = _env_get(environment, "VSINSTALLDIR")
    if direct:
        candidate = Path(direct)
        if candidate.is_dir():
            return candidate

    program_files_x86 = _env_get(environment, "ProgramFiles(x86)")
    if program_files_x86:
        vswhere = (
            Path(program_files_x86)
            / "Microsoft Visual Studio"
            / "Installer"
            / "vswhere.exe"
        )
        if vswhere.is_file():
            result = _capture(
                (
                    str(vswhere),
                    "-latest",
                    "-products",
                    "*",
                    "-requires",
                    "Microsoft.Component.MSBuild",
                    "-property",
                    "installationPath",
                )
            )
            if result:
                candidate = Path(result.splitlines()[-1].strip())
                if candidate.is_dir():
                    return candidate

    if msbuild:
        path = Path(msbuild)
        for parent in path.parents:
            if parent.name.lower() == "msbuild" and parent.parent.is_dir():
                return parent.parent
    return None


def inspect_installed_toolchain(
    environment: Mapping[str, str] | None = None,
) -> ToolchainReport:
    env = dict(os.environ if environment is None else environment)
    msbuild = shutil.which("msbuild")
    version_output = _capture((msbuild, "-nologo", "-version")) if msbuild else None
    parsed = _numeric_version(version_output)
    version = ".".join(str(part) for part in parsed) if parsed else None
    vs_install = _find_vs_install(env, msbuild)

    kit_roots: list[Path] = []
    for variable in ("WDKContentRoot", "WindowsSdkDir"):
        value = _env_get(env, variable)
        if value:
            kit_roots.append(Path(value))
    program_files_x86 = _env_get(env, "ProgramFiles(x86)")
    if program_files_x86:
        kit_roots.append(Path(program_files_x86) / "Windows Kits" / "10")

    explicit_vc_roots: list[Path] = []
    vc_tools_install = _env_get(env, "VCToolsInstallDir")
    if vc_tools_install:
        explicit_vc_roots.append(Path(vc_tools_install))

    return evaluate_toolchain(
        msbuild_version=version,
        vs_install=vs_install,
        kit_roots=kit_roots,
        explicit_vc_tool_roots=explicit_vc_roots,
    )


def _human_report(report: ToolchainReport) -> str:
    lines = [
        "Nikaido DualSense 3.0.0 Alpha 2.3.0 — Microsoft Signing Readiness",
        "",
    ]
    for check in report.checks:
        label = "OK" if check.ok else "BLOQUEADO"
        lines.append(f"[{label:9}] {check.summary}")
        if check.check_id == "sdk_wdk_pair" and not check.ok:
            eligible = [
                inspection
                for inspection in report.kit_inspections
                if inspection.supported_family
            ]
            if eligible:
                lines.append(f"            Componentes de {eligible[0].version}:")
                for component in eligible[0].components:
                    state = "OK" if component.present else "FALTA"
                    lines.append(f"              [{state:5}] {component.name}")
        if not check.ok and check.guidance:
            lines.append(f"            Acción: {check.guidance}")
    lines.extend(
        [
            "",
            "[SEGURIDAD] Comprobación de solo lectura; no instala ni configura componentes.",
            "[SEGURIDAD] No carga drivers ni cambia Secure Boot, HVCI o test signing.",
            "",
            "[LISTO] Toolchain compatible para compilar fuente."
            if report.ready
            else "[BLOQUEADO] No se iniciará MSBuild hasta resolver las dependencias indicadas.",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Comprueba VS2026, MSVC, SDK y WDK sin modificar Windows")
    parser.add_argument("--json", action="store_true", help="Imprime un informe JSON sanitizado")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = inspect_installed_toolchain()
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(_human_report(report))
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
