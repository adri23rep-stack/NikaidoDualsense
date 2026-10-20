"""Compilador de Nikaido DualSense para Windows.

Genera una distribución lista para usar dentro de ``release`` y mantiene los
archivos temporales fuera de la vista. La carpeta de trabajo de PyInstaller no
es una distribución válida y se elimina al terminar para evitar que alguien
ejecute accidentalmente su copia incompleta del .exe.

Uso:
    python build.py               # Carpeta portable recomendada
    python build.py --onefile     # Un solo archivo ejecutable
    python build.py --console     # Mantener consola visible
    python build.py --clean       # Borrar compilaciones anteriores
    python build.py --keep-work   # Conservar temporales para depuración
"""

from __future__ import annotations

import argparse
import hashlib
from importlib import metadata as importlib_metadata
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Iterable, List, Optional

from nikaido_version import APP_NAME, APP_VERSION, RELEASE_STAGE
from tools.privacy_audit import require_private_release, write_audit_report

ROOT = Path(__file__).resolve().parent
WORK_ROOT = ROOT / ".nikaido_build"
WORK_PATH = WORK_ROOT / "work"
SPEC_PATH = WORK_ROOT / "spec"
RELEASE_PATH = ROOT / "release"
PRIVACY_REPORT_PATH = RELEASE_PATH / "PRIVACY_AUDIT.json"
LEGACY_PATHS = (ROOT / "build", ROOT / "dist")

UI_RUNTIME_MODULES = (
    "gui.modern_app",
    "gui.main_window",
    "gui.assistant_tips",
    "gui.update_mixin",
    "gui.components",
    "gui.controller_visual",
    "gui.light_studio",
    "gui.curve_editor",
    "gui.i18n",
    "gui.ui_common",
    "gui.design_system",
    "gui.profile_editor",
    "gui.profile_gallery",
    "gui.profile_visuals",
    "gui.pages.dashboard",
    "gui.pages.profiles",
    "gui.pages.nexus",
    "gui.pages.input",
    "gui.pages.macros",
    "gui.pages.device",
    "gui.pages.triggers",
    "gui.pages.system",
    "gui.pages.settings",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compilar Nikaido.exe")
    parser.add_argument("--onefile", action="store_true", help="Crear un solo archivo .exe")
    parser.add_argument("--clean", action="store_true", help="Limpiar compilaciones anteriores")
    parser.add_argument("--console", action="store_true", help="Mantener la consola visible")
    parser.add_argument(
        "--installer",
        action="store_true",
        help="Crear también un instalador con Inno Setup 6 (solo onedir)",
    )
    parser.add_argument(
        "--keep-work",
        action="store_true",
        help="Conservar la carpeta temporal .nikaido_build para depuración",
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
    """Elimina salidas actuales, temporales y carpetas antiguas de PyInstaller."""
    print("Limpiando compilaciones anteriores...")
    for path in (*LEGACY_PATHS, WORK_ROOT, RELEASE_PATH, ROOT / "__pycache__"):
        _remove_path(path)
    for spec_file in ROOT.glob("*.spec"):
        _remove_path(spec_file)
    print("Limpieza completada.\n")


def check_dependencies() -> bool:
    """Comprueba dependencias y valida el backend HID que usará el ejecutable."""
    print("Verificando dependencias...")
    required = {
        "hid": "hidapi",
        "vgamepad": "vgamepad",
        "PySide6": "PySide6",
        "PIL": "pillow",
        "pystray": "pystray",
        "win32api": "pywin32",
        "psutil": "psutil",
        "pycaw": "pycaw",
        "comtypes": "comtypes",
    }

    missing: List[str] = []
    for module, package in required.items():
        try:
            __import__(module)
            print(f"  OK  {package}")
        except (ImportError, OSError) as exc:
            missing.append(package)
            print(f"  FALTA  {package}: {exc}")

    if "hidapi" not in missing:
        try:
            from src.hid_backend import ensure_hidapi_backend

            status = ensure_hidapi_backend()
            if not status.available:
                raise RuntimeError(status.error)
            __import__("pydualsense")
            print(f"  OK  pydualsense ({status.name})")
        except Exception as exc:
            missing.append("pydualsense")
            print(f"  FALTA  pydualsense/backend HID: {exc}")

    try:
        import PyInstaller  # noqa: F401

        print("  OK  pyinstaller")
    except ImportError:
        missing.append("pyinstaller")
        print("  FALTA  pyinstaller")

    if missing:
        print("\nInstala lo que falta con:")
        print(f"  {sys.executable} -m pip install {' '.join(sorted(set(missing)))}")
        return False

    print("Dependencias listas.\n")
    return True


def create_icon() -> str | None:
    """Crea el icono de Windows si no existe o está vacío."""
    icon_path = ROOT / "assets" / "icon.ico"
    if icon_path.exists() and icon_path.stat().st_size > 0:
        return str(icon_path)

    print("Creando icono de la aplicación...")
    try:
        from PIL import Image, ImageDraw

        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        images = []
        for size in sizes:
            image = Image.new("RGBA", size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            unit = size[0] / 64.0
            draw.rounded_rectangle(
                [0, 0, size[0] - 1, size[1] - 1],
                radius=max(2, round(14 * unit)),
                fill=(16, 23, 42, 255),
            )

            def points(values: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
                return [(round(x * unit), round(y * unit)) for x, y in values]

            draw.polygon(points([(13, 49), (13, 15), (25, 23), (25, 36)]), fill=(72, 217, 239, 255))
            draw.polygon(points([(26, 23), (39, 41), (39, 49), (26, 36)]), fill=(123, 63, 242, 255))
            draw.polygon(points([(40, 41), (40, 15), (51, 10), (51, 49)]), fill=(211, 64, 244, 255))
            images.append(image)

        icon_path.parent.mkdir(parents=True, exist_ok=True)
        images[-1].save(icon_path, format="ICO", sizes=sizes)
        print(f"  Icono creado: {icon_path}\n")
        return str(icon_path)
    except Exception as exc:  # pragma: no cover - depende del entorno de build
        print(f"  Advertencia: no se pudo crear el icono: {exc}\n")
        return None


def find_msvc_runtime_dlls() -> list[Path]:
    """Encuentra runtimes de Visual C++ incluidos con la instalación de Python.

    PyInstaller suele detectarlos por sí solo. Se agregan explícitamente cuando
    están disponibles para evitar el error genérico de LoadLibrary al cargar
    ``python310.dll`` en equipos donde el runtime no está instalado globalmente.
    """
    if os.name != "nt":
        return []

    names = ("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll")
    roots = {
        Path(sys.executable).resolve().parent,
        Path(sys.base_prefix).resolve(),
        Path(sys.prefix).resolve(),
        Path(sys.base_prefix).resolve() / "DLLs",
    }
    found: list[Path] = []
    seen: set[str] = set()
    for name in names:
        for root in roots:
            candidate = root / name
            key = str(candidate).lower()
            if candidate.is_file() and key not in seen:
                found.append(candidate)
                seen.add(key)
                break
    return found


def write_version_info() -> Path:
    """Genera metadatos visibles en Propiedades del ejecutable de Windows."""
    parts = [int(item) for item in APP_VERSION.split('.') if item.isdigit()]
    while len(parts) < 4:
        parts.append(0)
    parts = parts[:4]
    version_file = WORK_ROOT / "version_info.txt"
    version_file.parent.mkdir(parents=True, exist_ok=True)
    version_file.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={tuple(parts)}, prodvers={tuple(parts)}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', 'Team Nikaido'),
    StringStruct('LegalCopyright', '© Team Nikaido'),
    StringStruct('FileDescription', 'Nikaido DualSense Control Center'),
    StringStruct('FileVersion', '{APP_VERSION}'),
    StringStruct('InternalName', 'Nikaido'),
    StringStruct('OriginalFilename', 'Nikaido.exe'),
    StringStruct('ProductName', '{APP_NAME}'),
    StringStruct('ProductVersion', '{APP_VERSION}')
  ])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])]
)
""",
        encoding="utf-8",
    )
    return version_file


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_update_manifest(installer: Path) -> Path:
    """Genera el feed verificado por hash que consumirá el actualizador.

    Define NIKAIDO_UPDATE_DOWNLOAD_BASE_URL al compilar la release pública para
    reemplazar el dominio marcador por el servidor real.
    """
    base_url = os.environ.get(
        "NIKAIDO_UPDATE_DOWNLOAD_BASE_URL",
        "https://REPLACE-ME.invalid/downloads",
    ).strip().rstrip("/")
    channel = "beta" if "beta" in RELEASE_STAGE.lower() else "stable"
    manifest = {
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
    destination.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return destination


def write_release_manifest(*, onefile: bool, executable: Path) -> Path:
    files = [executable] if onefile else [item for item in (RELEASE_PATH / "Nikaido").rglob("*") if item.is_file()]
    file_records = [
        {
            "path": str(item.relative_to(RELEASE_PATH)).replace('\\', '/'),
            "bytes": item.stat().st_size,
            "sha256": _sha256(item),
        }
        for item in sorted(files)
    ]
    manifest = {
        "product": APP_NAME,
        "version": APP_VERSION,
        "layout": "onefile" if onefile else "onedir",
        "executable": str(executable.relative_to(RELEASE_PATH)).replace('\\', '/'),
        "executable_sha256": _sha256(executable),
        "files": len(files),
        "total_bytes": sum(item.stat().st_size for item in files),
        "file_hashes": file_records,
    }
    destination = RELEASE_PATH / "MANIFEST.json"
    destination.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return destination


def build_command(*, onefile: bool, console: bool) -> list[str]:
    """Construye el comando de PyInstaller sin ejecutarlo."""
    WORK_PATH.mkdir(parents=True, exist_ok=True)
    SPEC_PATH.mkdir(parents=True, exist_ok=True)
    RELEASE_PATH.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "Nikaido",
        "--noconfirm",
        "--clean",
        "--onefile" if onefile else "--onedir",
        "--console" if console else "--noconsole",
        "--workpath",
        str(WORK_PATH),
        "--specpath",
        str(SPEC_PATH),
        "--distpath",
        str(RELEASE_PATH),
        "--contents-directory",
        "_internal",
    ]

    command.extend(["--version-file", str(write_version_info())])

    icon_path = create_icon()
    if icon_path:
        command.extend(["--icon", icon_path])

    command.extend(["--add-data", f"{ROOT / 'assets'}{os.pathsep}assets"])
    # pydualsense importa hidguardian en tiempo de ejecución y su backend HID
    # también puede resolverse de forma dinámica. Recolectar el paquete entero
    # evita un EXE que abre bien pero queda permanentemente en "Buscando".
    command.extend(["--collect-all", "pydualsense"])
    command.extend(["--collect-all", "vgamepad"])
    command.extend(["--collect-all", "pystray"])
    command.extend(["--collect-all", "pycaw"])
    command.extend(["--collect-all", "comtypes"])

    for runtime in find_msvc_runtime_dlls():
        command.extend(["--add-binary", f"{runtime}{os.pathsep}."])

    hidden_imports = [
        "pydualsense",
        "pydualsense.hidguardian",
        "pydualsense.checksum",
        "pydualsense.enums",
        "pydualsense.event_system",
        "hid",
        "src.hid_backend",
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        *UI_RUNTIME_MODULES,
        "nikaido_version",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "src.input_studio",
        "src.profile_catalog",
        "src.advanced_mapping",
        "src.light_effects",
        "src.audio_manager",
        "src.edit_history",
        "src.appearance",
        "src.single_instance",
        "src.crash_reporting",
        "src.virtual_feedback",
        "src.update_manager",
        "src.ui_sounds",
        "src.game_profile_watcher",
        "src.hidhide_manager",
        "src.keyboard_gamepad",
        "src.mouse_to_gyro",
        "pystray",
        "pystray._base",
        "pystray._win32",
        "vgamepad",
        "vgamepad.win.vigem_commons",
        "vgamepad.win.vigem_client",
        "win32api",
        "win32gui",
        "win32con",
        "pycaw",
        "pycaw.pycaw",
        "pycaw.constants",
        "comtypes",
    ]
    for hidden_import in hidden_imports:
        command.extend(["--hidden-import", hidden_import])

    command.append(str(ROOT / "main.py"))
    return command


def validate_release_layout(*, onefile: bool) -> Path:
    """Verifica que la salida contiene una distribución ejecutable completa."""
    if onefile:
        executable = RELEASE_PATH / "Nikaido.exe"
        if not executable.is_file():
            raise RuntimeError(f"No se generó el ejecutable esperado: {executable}")
        return executable

    app_dir = RELEASE_PATH / "Nikaido"
    executable = app_dir / "Nikaido.exe"
    internal = app_dir / "_internal"
    if not executable.is_file():
        raise RuntimeError(f"No se generó el ejecutable esperado: {executable}")
    if not internal.is_dir():
        raise RuntimeError(f"Falta la carpeta de runtime: {internal}")

    python_dlls = list(internal.glob("python3*.dll"))
    if not python_dlls:
        raise RuntimeError(
            "La distribución no contiene python3xx.dll dentro de _internal. "
            "No compartas esta compilación."
        )

    # El adaptador interno usa la extensión de cython-hidapi. Sin este .pyd la
    # interfaz abre, pero pydualsense no puede enumerar ningún control.
    hid_extensions = [
        path for path in internal.rglob("hid*.pyd")
        if path.is_file() and "hide" not in path.name.lower()
    ]
    if not hid_extensions:
        raise RuntimeError(
            "La distribución no contiene el backend HID nativo (hid*.pyd). "
            "Reinstala requirements.txt y vuelve a compilar."
        )
    qt_platforms = list(internal.rglob("qwindows.dll"))
    if not qt_platforms:
        raise RuntimeError(
            "La distribución no contiene el plugin qwindows.dll de Qt. "
            "La interfaz no podría abrir en otro equipo."
        )
    return executable


def validate_bundled_hid(executable: Path) -> dict:
    """Ejecuta una prueba real dentro del EXE para detectar imports/DLL faltantes."""
    if os.name != "nt":
        return {"ok": True, "backend": "not-tested-non-windows"}

    result_path = WORK_ROOT / "hid-self-test.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    if result_path.exists():
        result_path.unlink()

    try:
        completed = subprocess.run(
            [
                str(executable),
                "--self-test-hid",
                "--self-test-output",
                str(result_path),
            ],
            cwd=executable.parent,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("El auto-test HID del ejecutable agotó el tiempo") from exc

    if not result_path.is_file():
        raise RuntimeError(
            "El ejecutable no pudo generar el auto-test HID. "
            "Puede faltar una DLL o un módulo de PyInstaller."
        )

    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError("El resultado del auto-test HID es inválido") from exc
    finally:
        try:
            result_path.unlink()
        except OSError:
            pass

    if completed.returncode != 0 or not data.get("ok"):
        detail = data.get("error") or f"código {completed.returncode}"
        raise RuntimeError(f"El backend HID empaquetado no funciona: {detail}")
    if not data.get("pydualsense_imported") or not data.get("enumeration_ok"):
        raise RuntimeError("El EXE no pudo cargar pydualsense o enumerar dispositivos HID")
    if not data.get("audio_imported"):
        raise RuntimeError("El EXE no pudo cargar pycaw/comtypes para el control del micrófono")
    if (
        not data.get("tray_imported")
        or not data.get("tray_backend_imported")
        or not data.get("tray_icon_rendered")
    ):
        raise RuntimeError(
            "El EXE no pudo cargar o renderizar la bandeja con batería. "
            "Reinstala Pillow y pystray antes de compilar."
        )

    print(
        "  Auto-test runtime OK: "
        f"HID {data.get('backend', 'desconocido')} · "
        f"Sony visibles: {data.get('sony_devices', 0)} · audio y bandeja listos"
    )
    return data



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
    "pyinstaller",
)


def _safe_legal_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value)


def copy_legal_documents(*, onefile: bool) -> Path:
    """Copia EULA, aviso propietario y licencias de terceros a la distribución."""
    destination = RELEASE_PATH if onefile else RELEASE_PATH / "Nikaido"
    destination.mkdir(parents=True, exist_ok=True)
    for name in LEGAL_DOCUMENTS:
        source = ROOT / name
        if not source.is_file():
            raise RuntimeError(f"Falta el documento legal requerido: {source}")
        shutil.copy2(source, destination / name)

    licenses_dir = destination / "THIRD_PARTY_LICENSES"
    licenses_dir.mkdir(parents=True, exist_ok=True)
    metadata_lines = [
        f"{APP_NAME} {APP_VERSION} — third-party package metadata",
        "Generated from the Python distributions installed at build time.",
        "",
    ]
    copied = set()
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
            relative_key = f"{package_name}/{file_ref}"
            if relative_key in copied:
                continue
            copied.add(relative_key)
            target_name = _safe_legal_name(
                f"{package_name}-{package_version}-{Path(str(file_ref)).name}"
            )
            shutil.copy2(source, licenses_dir / target_name)
    (licenses_dir / "PACKAGE_METADATA.txt").write_text(
        "\n".join(metadata_lines) + "\n", encoding="utf-8"
    )
    return destination


def write_release_helpers(*, onefile: bool) -> list[Path]:
    """Crea instrucciones y un lanzador inequívoco dentro de ``release``."""
    readme = RELEASE_PATH / "LEEME_PRIMERO.txt"
    if onefile:
        launch_target = "Nikaido.exe"
        launcher_body = '@echo off\r\nstart "" "%~dp0Nikaido.exe"\r\n'
    else:
        launch_target = r"Nikaido\Nikaido.exe"
        launcher_body = '@echo off\r\nstart "" "%~dp0Nikaido\\Nikaido.exe"\r\n'

    readme.write_text(
        (
            f"{APP_NAME} {APP_VERSION}\n\n"
            "EJECUTABLE CORRECTO:\n"
            f"  {launch_target}\n\n"
            "También puedes usar ABRIR_NIKAIDO.bat.\n\n"
            "IMPORTANTE:\n"
            "- No ejecutes archivos desde build, dist o .nikaido_build.\n"
            "- Esas carpetas son temporales y pueden tener un runtime incompleto.\n"
            "- Para compartir Nikaido, usa el ZIP generado dentro de release.\n"
        ),
        encoding="utf-8",
    )
    launcher = RELEASE_PATH / "ABRIR_NIKAIDO.bat"
    launcher.write_text(launcher_body, encoding="utf-8")
    return [readme, launcher]


def create_release_zip(*, onefile: bool, helpers: list[Path]) -> Path:
    """Empaqueta solamente la distribución válida, nunca la carpeta temporal."""
    zip_path = RELEASE_PATH / f"Nikaido_DualSense-{APP_VERSION}-Windows.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for helper in helpers:
            archive.write(helper, helper.name)

        if onefile:
            executable = RELEASE_PATH / "Nikaido.exe"
            archive.write(executable, executable.name)
            for legal_name in LEGAL_DOCUMENTS:
                legal_path = RELEASE_PATH / legal_name
                archive.write(legal_path, legal_path.name)
            licenses_dir = RELEASE_PATH / "THIRD_PARTY_LICENSES"
            for file_path in sorted(licenses_dir.rglob("*")):
                if file_path.is_file():
                    archive.write(file_path, file_path.relative_to(RELEASE_PATH))
        else:
            app_dir = RELEASE_PATH / "Nikaido"
            for file_path in sorted(app_dir.rglob("*")):
                if file_path.is_file():
                    archive.write(file_path, file_path.relative_to(RELEASE_PATH))
    return zip_path


def build_executable(*, onefile: bool = False, console: bool = False, keep_work: bool = False) -> bool:
    """Compila, valida y crea el paquete portable final."""
    print(f"Iniciando Nikaido {APP_VERSION} ({'onefile' if onefile else 'onedir'})...")

    # Evita mezclar una distribución nueva con archivos de una compilación vieja.
    for path in (*LEGACY_PATHS, RELEASE_PATH, WORK_ROOT):
        _remove_path(path)

    command = build_command(onefile=onefile, console=console)
    print("Comando de compilación preparado.\n")
    result = subprocess.run(command, cwd=ROOT, text=True)
    if result.returncode != 0:
        print("\nBUILD FALLIDO")
        return False

    try:
        executable = validate_release_layout(onefile=onefile)
        validate_bundled_hid(executable)
        copy_legal_documents(onefile=onefile)
        helpers = write_release_helpers(onefile=onefile)
        helpers.append(write_release_manifest(onefile=onefile, executable=executable))
        privacy_target = executable if onefile else RELEASE_PATH / "Nikaido"
        privacy_audit = require_private_release([privacy_target, *helpers])
        privacy_report = write_audit_report(privacy_audit, PRIVACY_REPORT_PATH)
        zip_path = create_release_zip(onefile=onefile, helpers=[*helpers, privacy_report])
        require_private_release([zip_path])
    except Exception as exc:
        print(f"\nBUILD INVÁLIDO: {exc}")
        return False
    finally:
        if not keep_work:
            _remove_path(WORK_ROOT)

    print("\n" + "=" * 62)
    print("BUILD EXITOSO Y VALIDADO")
    print("=" * 62)
    print(f"Ejecutable correcto: {executable}")
    print(f"Paquete para compartir: {zip_path}")
    print("No ejecutes nada desde build, dist o .nikaido_build.")
    print("=" * 62)
    return True


def find_inno_compiler() -> Optional[Path]:
    """Localiza ISCC.exe sin depender de que Inno Setup esté en PATH."""
    candidates = []
    for env_name in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(env_name)
        if base:
            candidates.append(Path(base) / "Inno Setup 6" / "ISCC.exe")
    return next((path for path in candidates if path.is_file()), None)


def build_windows_installer() -> Path:
    """Compila el instalador solo después de validar la distribución onedir."""
    if os.name != "nt":
        raise RuntimeError("El instalador de Windows solo puede compilarse en Windows")
    source_dir = RELEASE_PATH / "Nikaido"
    executable = source_dir / "Nikaido.exe"
    if not executable.is_file():
        raise RuntimeError("Primero genera y valida la distribución onedir")
    compiler = find_inno_compiler()
    if compiler is None:
        raise RuntimeError("Inno Setup 6 no está instalado o ISCC.exe no fue encontrado")
    script = ROOT / "installer" / "Nikaido.iss"
    if not script.is_file():
        raise RuntimeError(f"Falta el script del instalador: {script}")
    command = [
        str(compiler),
        f"/DMyAppVersion={APP_VERSION}",
        f"/DSourceDir={source_dir}",
        str(script),
    ]
    result = subprocess.run(command, cwd=ROOT, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Inno Setup terminó con código {result.returncode}")
    installer = RELEASE_PATH / f"Nikaido_DualSense-{APP_VERSION}-Setup.exe"
    if not installer.is_file():
        raise RuntimeError("Inno Setup no generó el archivo esperado")
    installer_audit = require_private_release([installer])
    write_audit_report(installer_audit, RELEASE_PATH / "PRIVACY_AUDIT_INSTALLER.json")
    return installer


def create_installer_batch() -> None:
    """Conserva el instalador de dependencias para desarrollo desde código fuente."""
    batch_content = r'''@echo off
chcp 65001 >nul
echo ==========================================
echo  Nikaido DualSense - Dependencias
echo ==========================================
echo.
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado o no esta en PATH.
    pause
    exit /b 1
)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] No se pudieron instalar las dependencias.
    pause
    exit /b 1
)
echo.
echo Dependencias instaladas.
echo Para compilar usa: python build.py
pause
'''
    (ROOT / "install.bat").write_text(batch_content, encoding="utf-8")


def main() -> None:
    args = parse_args()
    if args.clean:
        clean_build()
        return

    print("=" * 62)
    print(f"{APP_NAME} {APP_VERSION} - Compilador")
    print("=" * 62 + "\n")

    if not check_dependencies():
        create_installer_batch()
        print("\nEjecuta install.bat para instalar las dependencias de desarrollo.")
        raise SystemExit(1)

    if args.installer and args.onefile:
        print("El instalador requiere la distribución onedir; quita --onefile.")
        raise SystemExit(2)

    success = build_executable(
        onefile=args.onefile,
        console=args.console,
        keep_work=args.keep_work,
    )
    if success:
        create_installer_batch()
        if args.installer:
            try:
                installer = build_windows_installer()
                update_manifest = write_update_manifest(installer)
                print(f"Instalador validado: {installer}")
                print(f"Manifiesto de actualización: {update_manifest}")
            except Exception as exc:
                print(f"No se pudo crear el instalador: {exc}")
                success = False
    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()
