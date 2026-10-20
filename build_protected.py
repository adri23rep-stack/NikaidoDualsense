"""Compilación secundaria protegida de Nikaido DualSense con Nuitka.

Este archivo NO reemplaza ``build.py`` ni modifica el código fuente original.
Genera una distribución independiente dentro de ``release_protected`` donde
los módulos propios se compilan a código nativo y no se distribuyen archivos
``.py`` o bytecode ``.pyc``.

Uso recomendado en Windows:
    COMPILAR_NIKAIDO_PROTEGIDO.bat

El BAT crea un entorno aislado en una ruta corta fuera del proyecto para
evitar el límite histórico MAX_PATH de Windows al instalar PySide6.

La compilación normal de PyInstaller sigue disponible con ``build.py``.
"""

from __future__ import annotations

import argparse
import hashlib
from importlib import metadata as importlib_metadata
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import textwrap
import zipfile
from pathlib import Path
from typing import Iterable, Sequence

from nikaido_version import APP_NAME, APP_VERSION, RELEASE_STAGE
from tools.privacy_audit import require_private_release, write_audit_report

ROOT = Path(__file__).resolve().parent


def _protected_work_root() -> Path:
    """Devuelve una ruta de trabajo corta para evitar MAX_PATH en Windows.

    El compilador protegido puede definir ``NIKAIDO_PROTECTED_WORKDIR`` desde
    el BAT. Si no existe, se conserva la ubicación histórica dentro del
    proyecto para desarrollo y pruebas.
    """
    configured = os.environ.get("NIKAIDO_PROTECTED_WORKDIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return ROOT / ".nikaido_protected_build"


BUILD_ROOT = _protected_work_root()
ENTRY_ROOT = BUILD_ROOT / "entry"
NUITKA_OUTPUT = BUILD_ROOT / "nuitka"
RELEASE_PATH = ROOT / "release_protected"
APP_RELEASE_PATH = RELEASE_PATH / "Nikaido"
REPORT_PATH = BUILD_ROOT / "nuitka-compilation-report.xml"
PRIVACY_REPORT_PATH = RELEASE_PATH / "PRIVACY_AUDIT_PROTECTED.json"

LEGAL_DOCUMENTS = (
    "LICENSE",
    "EULA_NIKAIDO.txt",
    "EULA_ES.txt",
    "EULA_EN.txt",
    "EULA_PT_BR.txt",
    "THIRD_PARTY_NOTICES.txt",
)

THIRD_PARTY_DISTRIBUTIONS = (
    "PySide6",
    "shiboken6",
    "pydualsense",
    "vgamepad",
    "pywin32",
    "pillow",
    "pystray",
    "hidapi",
    "hidapi-usb",
    "psutil",
    "pycaw",
    "comtypes",
    "nuitka",
)

# Paquetes propios. ``--include-package`` obliga a Nuitka a compilar incluso
# los módulos cargados dinámicamente con importlib, como las páginas de la GUI.
OWN_PACKAGES = ("gui", "src")
OWN_MODULES = ("main", "nikaido_version")

# Imports que el programa o sus dependencias resuelven dinámicamente.
DYNAMIC_PACKAGES = ("pydualsense", "vgamepad", "pystray", "PIL", "pycaw", "comtypes")
DYNAMIC_MODULES = (
    "hid",
    "hidapi",
    "psutil",
    "win32api",
    "win32gui",
    "win32con",
    "pystray._win32",
    "vgamepad.win.vigem_commons",
    "vgamepad.win.vigem_client",
)

FORBIDDEN_RELEASE_SUFFIXES = {
    ".py",
    ".pyc",
    ".pyo",
    ".pyw",
    ".spec",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
}


VIGEM_CLIENT_RELATIVE = Path("vgamepad") / "win" / "vigem" / "client"
VIGEM_X64_DLL_RELATIVE = VIGEM_CLIENT_RELATIVE / "x64" / "ViGEmClient.dll"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crear una compilación secundaria protegida de Nikaido con Nuitka"
    )
    parser.add_argument("--clean", action="store_true", help="Borrar salida protegida y temporales")
    parser.add_argument("--console", action="store_true", help="Conservar consola para depuración")
    parser.add_argument(
        "--installer",
        action="store_true",
        help="Crear instalador Inno Setup después de validar la distribución",
    )
    parser.add_argument(
        "--installer-only",
        action="store_true",
        help="Crear solo el instalador desde release_protected sin recompilar Nuitka",
    )
    parser.add_argument(
        "--repair-runtime-only",
        action="store_true",
        help="Reparar DLL/runtime de una salida standalone existente sin recompilar Nuitka",
    )
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="Generar un solo EXE (no compatible con --installer)",
    )
    parser.add_argument(
        "--keep-work",
        action="store_true",
        help="Conservar temporales y reporte de Nuitka para depuración",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=max(1, min(os.cpu_count() or 2, 8)),
        help="Procesos máximos del compilador C (predeterminado: hasta 8)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar el comando sin compilar; útil para validar el entorno",
    )
    return parser.parse_args()


def _remove_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    print(f"  Eliminado: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")


def clean_build() -> None:
    print("Limpiando compilación protegida...")
    _remove_path(BUILD_ROOT)
    _remove_path(RELEASE_PATH)
    print("Limpieza completada.")


def _version_quad(version: str) -> str:
    parts: list[int] = []
    for raw in version.split("."):
        digits = "".join(char for char in raw if char.isdigit())
        if digits:
            parts.append(int(digits))
    while len(parts) < 4:
        parts.append(0)
    return ".".join(str(value) for value in parts[:4])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_legal_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value)


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def check_dependencies(*, dry_run: bool = False) -> bool:
    """Comprueba el entorno sin importar la GUI ni iniciar servicios."""
    print("Verificando entorno de compilación protegida...")
    required = {
        "nuitka": "nuitka",
        "PySide6": "PySide6",
        "PIL": "pillow",
        "pydualsense": "pydualsense",
        "hid": "hidapi",
        "psutil": "psutil",
        "pystray": "pystray",
        "pycaw": "pycaw",
        "comtypes": "comtypes",
    }
    if os.name == "nt":
        required.update({"vgamepad": "vgamepad", "win32api": "pywin32"})

    missing: list[str] = []
    for module, package in required.items():
        if _module_available(module):
            print(f"  OK  {package}")
        else:
            print(f"  FALTA  {package}")
            missing.append(package)

    if os.name != "nt" and not dry_run:
        print("  ERROR  La distribución final de Windows debe compilarse dentro de Windows.")
        return False

    if missing:
        print("\nEjecuta COMPILAR_NIKAIDO_PROTEGIDO.bat para preparar el entorno corto.")
        return False

    print("Entorno protegido listo.\n")
    return True


def write_protected_entry() -> Path:
    """Crea un arranque temporal; no modifica ``main.py``.

    Nuitka no usa necesariamente ``sys.frozen`` ni ``sys._MEIPASS`` como
    PyInstaller. El adaptador mantiene las rutas de recursos y el inicio con
    Windows compatibles con ambos motores de compilación.
    """
    ENTRY_ROOT.mkdir(parents=True, exist_ok=True)
    entry = ENTRY_ROOT / "nikaido_protected_entry.py"
    entry.write_text(
        textwrap.dedent(
            '''
            """Entrada temporal para la compilación protegida de Nikaido."""
            from pathlib import Path
            import sys

            setattr(sys, "frozen", True)
            setattr(sys, "_MEIPASS", str(Path(sys.executable).resolve().parent))

            from main import main

            if __name__ == "__main__":
                main()
            '''
        ).lstrip(),
        encoding="utf-8",
    )
    return entry


def build_command(*, onefile: bool, console: bool, jobs: int) -> list[str]:
    """Construye el comando de Nuitka sin ejecutarlo."""
    entry = write_protected_entry()
    NUITKA_OUTPUT.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "nuitka",
        "--mode=onefile" if onefile else "--mode=standalone",
        f"--output-dir={NUITKA_OUTPUT}",
        "--output-filename=Nikaido.exe",
        "--remove-output",
        "--assume-yes-for-downloads",
        "--enable-plugins=pyside6",
        "--windows-console-mode=force" if console else "--windows-console-mode=disable",
        f"--windows-icon-from-ico={ROOT / 'assets' / 'icon.ico'}",
        "--company-name=Team Nikaido",
        f"--product-name={APP_NAME}",
        "--file-description=Nikaido DualSense Control Center",
        f"--file-version={_version_quad(APP_VERSION)}",
        f"--product-version={_version_quad(APP_VERSION)}",
        "--copyright=© Team Nikaido",
        "--trademarks=Team Nikaido",
        f"--include-data-dir={ROOT / 'assets'}=assets",
        "--nofollow-import-to=tests",
        "--nofollow-import-to=legacy",
        "--nofollow-import-to=comtypes.test",
        "--nofollow-import-to=comtypes.tests",
        "--noinclude-data-files=comtypes/test/**",
        "--noinclude-data-files=comtypes/tests/**",
        "--noinclude-pytest-mode=nofollow",
        "--noinclude-unittest-mode=nofollow",
        # Nuitka no ofrece un modo anti-bloat separado para ``doctest``.
        # Los imports que lo arrastraban pertenecen a ``comtypes.test`` y ya
        # quedan fuera mediante --nofollow-import-to y --noinclude-data-files.
        "--noinclude-setuptools-mode=nofollow",
        f"--jobs={max(1, jobs)}",
        f"--report={REPORT_PATH}",
    ]

    for package in OWN_PACKAGES:
        command.append(f"--include-package={package}")
    for module in OWN_MODULES:
        command.append(f"--include-module={module}")
    for package in DYNAMIC_PACKAGES:
        command.append(f"--include-package={package}")
        command.append(f"--include-package-data={package}")
    for module in DYNAMIC_MODULES:
        command.append(f"--include-module={module}")

    command.append(str(entry))
    return command


def _print_command(command: Sequence[str]) -> None:
    print("Comando protegido preparado:\n")
    print(subprocess.list2cmdline(list(command)))
    print()


def locate_nuitka_result(*, onefile: bool) -> Path:
    candidates = [path for path in NUITKA_OUTPUT.rglob("Nikaido.exe") if path.is_file()]
    if not candidates:
        raise RuntimeError("Nuitka no generó Nikaido.exe")

    if onefile:
        direct = [path for path in candidates if not path.parent.name.endswith(".dist")]
        return min(direct or candidates, key=lambda path: len(path.parts))

    standalone = [path for path in candidates if path.parent.name.endswith(".dist")]
    if not standalone:
        raise RuntimeError("Nuitka no generó una carpeta standalone .dist")
    return min(standalone, key=lambda path: len(path.parts))


def stage_release(*, onefile: bool, executable: Path) -> Path:
    _remove_path(RELEASE_PATH)
    RELEASE_PATH.mkdir(parents=True, exist_ok=True)

    if onefile:
        destination = RELEASE_PATH / "Nikaido.exe"
        shutil.copy2(executable, destination)
        return destination

    shutil.copytree(executable.parent, APP_RELEASE_PATH)
    destination = APP_RELEASE_PATH / "Nikaido.exe"
    if not destination.is_file():
        raise RuntimeError("La copia protegida no contiene Nikaido.exe")
    return destination


def _package_directory(package_name: str) -> Path:
    """Ubica el directorio real de un paquete instalado en el entorno de build."""
    spec = importlib.util.find_spec(package_name)
    if spec is None:
        raise RuntimeError(f"No se encontró el paquete requerido: {package_name}")
    locations = list(spec.submodule_search_locations or ())
    if locations:
        return Path(locations[0]).resolve()
    if spec.origin:
        return Path(spec.origin).resolve().parent
    raise RuntimeError(f"No se pudo resolver la ubicación de {package_name}")


def copy_vgamepad_runtime_binaries(destination: Path) -> list[Path]:
    """Copia el runtime nativo de ViGEm que Nuitka puede omitir.

    ``vgamepad`` carga ``ViGEmClient.dll`` mediante ``ctypes`` usando una ruta
    relativa al propio paquete. Como esa DLL no es un módulo Python, algunas
    compilaciones standalone de Nuitka no la copian aunque el paquete completo
    esté incluido. Se replica aquí el árbol exacto esperado por vgamepad.
    """
    package_root = _package_directory("vgamepad")
    source = package_root / "win" / "vigem" / "client"
    if not source.is_dir():
        raise RuntimeError(f"vgamepad no contiene el runtime ViGEm esperado: {source}")

    target = destination / VIGEM_CLIENT_RELATIVE
    target.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for item in source.rglob("*"):
        if not item.is_file():
            continue
        relative = item.relative_to(source)
        output = target / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, output)
        copied.append(output)

    required = destination / VIGEM_X64_DLL_RELATIVE
    if not required.is_file():
        raise RuntimeError(f"No se pudo copiar ViGEmClient.dll: {required}")
    print(f"  Runtime ViGEm copiado: {required}")
    return copied


def validate_required_runtime_files(*, onefile: bool) -> dict[str, object]:
    if onefile:
        return {"vigem_client_x64": "embedded-onefile"}
    required = APP_RELEASE_PATH / VIGEM_X64_DLL_RELATIVE
    if not required.is_file():
        raise RuntimeError(
            "Falta vgamepad/win/vigem/client/x64/ViGEmClient.dll; "
            "la emulación virtual no podría iniciar"
        )
    return {"vigem_client_x64": str(required.relative_to(APP_RELEASE_PATH)).replace("\\", "/")}


def validate_source_free_release(*, onefile: bool) -> dict[str, object]:
    target = RELEASE_PATH if onefile else APP_RELEASE_PATH
    if not target.exists():
        raise RuntimeError(f"No existe la salida protegida esperada: {target}")

    forbidden = [
        path
        for path in target.rglob("*")
        if path.is_file() and path.suffix.lower() in FORBIDDEN_RELEASE_SUFFIXES
    ]
    if forbidden:
        preview = ", ".join(str(path.relative_to(target)) for path in forbidden[:8])
        raise RuntimeError(f"La salida protegida contiene código fuente/bytecode: {preview}")

    executable = target / "Nikaido.exe" if target.is_dir() else target
    if not executable.is_file():
        executable = RELEASE_PATH / "Nikaido.exe"
    if not executable.is_file():
        raise RuntimeError("Falta Nikaido.exe en la salida protegida")

    native_modules = [path for path in target.rglob("*.pyd") if path.is_file()]
    qt_platforms = [path for path in target.rglob("qwindows.dll") if path.is_file()]
    if not onefile and not qt_platforms:
        raise RuntimeError("Falta qwindows.dll; la GUI no abriría en otro equipo")

    runtime_files = validate_required_runtime_files(onefile=onefile)
    return {
        "source_files": 0,
        "bytecode_files": 0,
        "native_modules": len(native_modules),
        "qt_platform_plugins": len(qt_platforms),
        **runtime_files,
    }


def validate_runtime(executable: Path) -> dict[str, object]:
    """Ejecuta el mismo auto-test HID usado por la compilación normal."""
    if os.name != "nt":
        return {"ok": True, "backend": "not-tested-non-windows"}

    result_path = BUILD_ROOT / "hid-self-test.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.unlink(missing_ok=True)
    try:
        completed = subprocess.run(
            [
                str(executable),
                "--self-test-hid",
                "--self-test-output",
                str(result_path),
            ],
            cwd=executable.parent,
            timeout=90,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("El auto-test protegido agotó el tiempo") from exc

    if not result_path.is_file():
        raise RuntimeError("El EXE protegido no pudo generar el auto-test HID")
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    finally:
        result_path.unlink(missing_ok=True)

    if completed.returncode != 0 or not data.get("ok"):
        detail = data.get("error") or f"código {completed.returncode}"
        raise RuntimeError(f"El runtime protegido no funciona: {detail}")
    if not data.get("audio_imported"):
        raise RuntimeError("El runtime protegido no pudo cargar pycaw/comtypes")
    return data


def copy_legal_documents(*, onefile: bool) -> Path:
    destination = RELEASE_PATH if onefile else APP_RELEASE_PATH
    destination.mkdir(parents=True, exist_ok=True)
    for name in LEGAL_DOCUMENTS:
        source = ROOT / name
        if not source.is_file():
            raise RuntimeError(f"Falta el documento legal requerido: {source}")
        shutil.copy2(source, destination / name)

    licenses_dir = destination / "THIRD_PARTY_LICENSES"
    licenses_dir.mkdir(parents=True, exist_ok=True)
    metadata_lines = [
        f"{APP_NAME} {APP_VERSION} — protected build third-party metadata",
        "Generated from the Python distributions installed at build time.",
        "",
    ]
    copied: set[str] = set()
    for distribution_name in THIRD_PARTY_DISTRIBUTIONS:
        try:
            dist = importlib_metadata.distribution(distribution_name)
        except importlib_metadata.PackageNotFoundError:
            metadata_lines.append(f"{distribution_name}: not installed in this build environment")
            continue
        package_name = dist.metadata.get("Name", distribution_name)
        package_version = dist.version
        license_expression = (
            dist.metadata.get("License-Expression")
            or dist.metadata.get("License")
            or "not declared in package metadata"
        )
        metadata_lines.append(f"{package_name} {package_version}: {license_expression}")
        for file_ref in dist.files or ():
            base = Path(str(file_ref)).name.lower()
            if not any(token in base for token in ("license", "copying", "notice")):
                continue
            source = Path(dist.locate_file(file_ref))
            if not source.is_file():
                continue
            key = f"{package_name}/{file_ref}"
            if key in copied:
                continue
            copied.add(key)
            target_name = _safe_legal_name(
                f"{package_name}-{package_version}-{Path(str(file_ref)).name}"
            )
            shutil.copy2(source, licenses_dir / target_name)

    (licenses_dir / "PACKAGE_METADATA.txt").write_text(
        "\n".join(metadata_lines) + "\n", encoding="utf-8"
    )
    return destination


def write_release_helpers(*, onefile: bool) -> list[Path]:
    if onefile:
        target = "Nikaido.exe"
        launcher_body = '@echo off\r\nstart "" "%~dp0Nikaido.exe"\r\n'
    else:
        target = r"Nikaido\Nikaido.exe"
        launcher_body = '@echo off\r\nstart "" "%~dp0Nikaido\\Nikaido.exe"\r\n'

    readme = RELEASE_PATH / "LEEME_PRIMERO.txt"
    readme.write_text(
        (
            f"{APP_NAME} {APP_VERSION} — compilación protegida\n\n"
            f"EJECUTABLE CORRECTO:\n  {target}\n\n"
            "Esta salida fue compilada con Nuitka. No contiene el código fuente "
            "propietario ni bytecode .pyc de Nikaido.\n\n"
            "También puedes usar ABRIR_NIKAIDO.bat.\n"
            "No compartas la carpeta .nikaido_protected_build.\n"
        ),
        encoding="utf-8",
    )
    launcher = RELEASE_PATH / "ABRIR_NIKAIDO.bat"
    launcher.write_text(launcher_body, encoding="utf-8")
    return [readme, launcher]


def _release_files(*, onefile: bool) -> list[Path]:
    if onefile:
        return [path for path in RELEASE_PATH.rglob("*") if path.is_file()]
    return [path for path in APP_RELEASE_PATH.rglob("*") if path.is_file()]


def write_release_manifest(
    *, onefile: bool, executable: Path, source_free: dict[str, object], runtime: dict[str, object]
) -> Path:
    files = sorted(_release_files(onefile=onefile))
    records = [
        {
            "path": str(path.relative_to(RELEASE_PATH)).replace("\\", "/"),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in files
    ]
    manifest = {
        "product": APP_NAME,
        "version": APP_VERSION,
        "layout": "onefile" if onefile else "standalone",
        "build_flavor": "protected",
        "protection_engine": "Nuitka native compilation",
        "original_source_modified": False,
        "executable": str(executable.relative_to(RELEASE_PATH)).replace("\\", "/"),
        "executable_sha256": _sha256(executable),
        "source_validation": source_free,
        "runtime_self_test": runtime,
        "files": len(files),
        "total_bytes": sum(path.stat().st_size for path in files),
        "file_hashes": records,
    }
    destination = RELEASE_PATH / "MANIFEST_PROTECTED.json"
    destination.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return destination


def create_release_zip(*, onefile: bool, helpers: Iterable[Path], manifest: Path) -> Path:
    zip_path = RELEASE_PATH / f"Nikaido_DualSense-{APP_VERSION}-Windows-Protected.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for helper in helpers:
            archive.write(helper, helper.name)
        archive.write(manifest, manifest.name)
        if onefile:
            for path in sorted(RELEASE_PATH.rglob("*")):
                if path.is_file() and path not in {*helpers, manifest, zip_path}:
                    archive.write(path, path.relative_to(RELEASE_PATH))
        else:
            for path in sorted(APP_RELEASE_PATH.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(RELEASE_PATH))
    return zip_path


def find_inno_compiler() -> Path | None:
    candidates: list[Path] = []
    for env_name in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(env_name)
        if base:
            candidates.append(Path(base) / "Inno Setup 6" / "ISCC.exe")
    return next((path for path in candidates if path.is_file()), None)


def write_update_manifest(installer: Path) -> Path:
    base_url = os.environ.get(
        "NIKAIDO_UPDATE_DOWNLOAD_BASE_URL",
        "https://REPLACE-ME.invalid/downloads",
    ).strip().rstrip("/")
    channel = "beta" if "beta" in RELEASE_STAGE.lower() else "stable"
    payload = {
        "product": APP_NAME,
        "channel": channel,
        "version": APP_VERSION,
        "title": f"{APP_NAME} {APP_VERSION} · {RELEASE_STAGE}",
        "notes": "Consulta las notas de la versión antes de publicar este manifiesto.",
        "download_url": f"{base_url}/{installer.name}",
        "sha256": _sha256(installer),
        "size_bytes": installer.stat().st_size,
        "silent_args": ["/SP-", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"],
    }
    destination = RELEASE_PATH / "Nikaido-update-manifest.json"
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return destination


def build_windows_installer() -> Path:
    if os.name != "nt":
        raise RuntimeError("El instalador protegido solo puede compilarse en Windows")
    executable = APP_RELEASE_PATH / "Nikaido.exe"
    if not executable.is_file():
        raise RuntimeError("Primero genera la distribución protegida standalone")
    compiler = find_inno_compiler()
    if compiler is None:
        raise RuntimeError("Inno Setup 6 no está instalado")
    script = ROOT / "installer" / "NikaidoProtected.iss"
    if not script.is_file():
        raise RuntimeError(f"Falta el script protegido: {script}")
    command = [
        str(compiler),
        f"/DMyAppVersion={APP_VERSION}",
        f"/DSourceDir={APP_RELEASE_PATH}",
        str(script),
    ]
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"Inno Setup terminó con código {completed.returncode}")
    installer = RELEASE_PATH / f"Nikaido_DualSense-{APP_VERSION}-Protected-Setup.exe"
    if not installer.is_file():
        raise RuntimeError("Inno Setup no generó el instalador protegido esperado")
    installer_audit = require_private_release([installer])
    write_audit_report(installer_audit, RELEASE_PATH / "PRIVACY_AUDIT_PROTECTED_INSTALLER.json")
    return installer


def build_protected(
    *, onefile: bool, console: bool, keep_work: bool, jobs: int, dry_run: bool
) -> bool:
    print(f"Iniciando {APP_NAME} {APP_VERSION} — compilación protegida...")
    command = build_command(onefile=onefile, console=console, jobs=jobs)
    _print_command(command)
    if dry_run:
        return True

    _remove_path(RELEASE_PATH)
    _remove_path(NUITKA_OUTPUT)
    NUITKA_OUTPUT.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode != 0:
        print("\nCOMPILACIÓN PROTEGIDA FALLIDA")
        return False

    try:
        generated = locate_nuitka_result(onefile=onefile)
        executable = stage_release(onefile=onefile, executable=generated)
        if not onefile:
            copy_vgamepad_runtime_binaries(APP_RELEASE_PATH)
        source_free = validate_source_free_release(onefile=onefile)
        runtime = validate_runtime(executable)
        copy_legal_documents(onefile=onefile)
        helpers = write_release_helpers(onefile=onefile)
        # Revalidar después de copiar documentos para impedir que un archivo
        # de código se cuele en la etapa final.
        source_free = validate_source_free_release(onefile=onefile)
        manifest = write_release_manifest(
            onefile=onefile,
            executable=executable,
            source_free=source_free,
            runtime=runtime,
        )
        privacy_target = executable if onefile else APP_RELEASE_PATH
        privacy_audit = require_private_release([privacy_target, *helpers, manifest])
        privacy_report = write_audit_report(privacy_audit, PRIVACY_REPORT_PATH)
        zip_path = create_release_zip(
            onefile=onefile, helpers=[*helpers, privacy_report], manifest=manifest
        )
        require_private_release([zip_path])
    except Exception as exc:
        print(f"\nBUILD PROTEGIDO INVÁLIDO: {exc}")
        return False
    finally:
        if not keep_work:
            _remove_path(BUILD_ROOT)

    print("\n" + "=" * 66)
    print("BUILD PROTEGIDO EXITOSO Y VALIDADO")
    print("=" * 66)
    print(f"Ejecutable: {executable}")
    print(f"Paquete: {zip_path}")
    print("El código original permanece intacto y la salida no contiene .py/.pyc.")
    print("=" * 66)
    return True


def repair_existing_runtime() -> tuple[Path, Path]:
    """Repara una distribución ya compilada sin volver a ejecutar Nuitka."""
    executable = APP_RELEASE_PATH / "Nikaido.exe"
    if not executable.is_file():
        raise RuntimeError(
            "No existe release_protected/Nikaido/Nikaido.exe; "
            "primero debe existir una compilación standalone"
        )
    copy_vgamepad_runtime_binaries(APP_RELEASE_PATH)
    source_free = validate_source_free_release(onefile=False)
    runtime = validate_runtime(executable)
    helpers = write_release_helpers(onefile=False)
    manifest = write_release_manifest(
        onefile=False,
        executable=executable,
        source_free=source_free,
        runtime=runtime,
    )
    privacy_audit = require_private_release([APP_RELEASE_PATH, *helpers, manifest])
    privacy_report = write_audit_report(privacy_audit, PRIVACY_REPORT_PATH)
    zip_path = create_release_zip(
        onefile=False, helpers=[*helpers, privacy_report], manifest=manifest
    )
    require_private_release([zip_path])
    print("Runtime protegido reparado y validado sin recompilar Nuitka.")
    print(f"Ejecutable: {executable}")
    print(f"Paquete actualizado: {zip_path}")
    return executable, zip_path


def main() -> None:
    args = parse_args()
    if args.clean:
        clean_build()
        return
    if args.repair_runtime_only:
        if args.onefile or args.installer or args.installer_only or args.dry_run or args.clean:
            raise SystemExit(
                "--repair-runtime-only no se combina con otras acciones de build/installer"
            )
        if not check_dependencies(dry_run=False):
            raise SystemExit(1)
        try:
            repair_existing_runtime()
        except Exception as exc:
            print(f"No se pudo reparar el runtime protegido: {exc}")
            raise SystemExit(1)
        raise SystemExit(0)
    if args.installer_only:
        if args.onefile or args.installer or args.dry_run:
            raise SystemExit("--installer-only no se combina con --onefile, --installer ni --dry-run")
        try:
            installer = build_windows_installer()
            update_manifest = write_update_manifest(installer)
            print(f"Instalador protegido: {installer}")
            print(f"Manifiesto de actualización: {update_manifest}")
        except Exception as exc:
            print(f"No se pudo crear el instalador protegido: {exc}")
            raise SystemExit(1)
        raise SystemExit(0)
    if args.installer and args.onefile:
        raise SystemExit("--installer requiere la distribución standalone; quita --onefile")
    if not check_dependencies(dry_run=args.dry_run):
        raise SystemExit(1)
    success = build_protected(
        onefile=args.onefile,
        console=args.console,
        keep_work=args.keep_work,
        jobs=args.jobs,
        dry_run=args.dry_run,
    )
    if success and args.installer and not args.dry_run:
        try:
            installer = build_windows_installer()
            update_manifest = write_update_manifest(installer)
            print(f"Instalador protegido: {installer}")
            print(f"Manifiesto de actualización: {update_manifest}")
        except Exception as exc:
            print(f"No se pudo crear el instalador protegido: {exc}")
            success = False
    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()
