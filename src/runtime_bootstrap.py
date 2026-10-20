"""Selecciona el runtime aislado antes de cargar dependencias externas.

PySide6 contiene recursos QML con rutas internas muy profundas. Si el entorno
virtual vive dentro de una carpeta larga de Descargas, Windows puede superar el
límite histórico de 260 caracteres durante ``pip install``. Nikaido usa por
defecto un runtime corto en ``%LOCALAPPDATA%\\NKB\\rt`` y conserva compatibilidad
con la antigua ``.venv`` local.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable, Iterable, Mapping, MutableMapping, Optional, Sequence

BOOTSTRAP_MARKER = "NIKAIDO_LOCAL_VENV_ACTIVE"
DISABLE_MARKER = "NIKAIDO_DISABLE_VENV_BOOTSTRAP"
RUNTIME_DIR_ENV = "NIKAIDO_VENV_DIR"
RUNTIME_HOME_ENV = "NIKAIDO_RUNTIME_HOME"


def project_venv_python(project_root: Path, *, platform_name: Optional[str] = None) -> Path:
    """Ejecutable de la antigua ``.venv`` colocada junto al código."""
    platform_name = platform_name or sys.platform
    if platform_name == "win32":
        return project_root / ".venv" / "Scripts" / "python.exe"
    return project_root / ".venv" / "bin" / "python"


def short_runtime_dir(
    *,
    platform_name: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> Optional[Path]:
    """Devuelve la carpeta corta administrada por Nikaido.

    Una ruta explícita tiene prioridad. En Windows el valor normal es
    ``%LOCALAPPDATA%\\NKB\\rt``; ``TEMP`` queda como respaldo para cuentas sin
    ``LOCALAPPDATA``.
    """
    platform_name = platform_name or sys.platform
    environ = os.environ if environ is None else environ

    explicit = str(environ.get(RUNTIME_DIR_ENV, "") or "").strip()
    if explicit:
        return Path(explicit).expanduser()

    home = str(environ.get(RUNTIME_HOME_ENV, "") or "").strip()
    if home:
        return Path(home).expanduser() / "rt"

    if platform_name != "win32":
        return None

    base = str(environ.get("LOCALAPPDATA", "") or "").strip()
    if not base:
        base = str(environ.get("TEMP", "") or environ.get("TMP", "") or "").strip()
    if not base:
        return None
    return Path(base).expanduser() / "NKB" / "rt"


def short_venv_python(
    *,
    platform_name: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> Optional[Path]:
    """Ejecutable del runtime corto, o ``None`` si no puede resolverse."""
    platform_name = platform_name or sys.platform
    runtime_dir = short_runtime_dir(platform_name=platform_name, environ=environ)
    if runtime_dir is None:
        return None
    if platform_name == "win32":
        return runtime_dir / "Scripts" / "python.exe"
    return runtime_dir / "bin" / "python"


def local_venv_python(project_root: Path, *, platform_name: Optional[str] = None) -> Path:
    """Alias compatible para integraciones antiguas que esperan ``.venv``."""
    return project_venv_python(project_root, platform_name=platform_name)


def runtime_candidates(
    project_root: Path,
    *,
    platform_name: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> Iterable[Path]:
    """Runtimes permitidos, de mayor a menor prioridad, sin duplicados."""
    platform_name = platform_name or sys.platform
    environ = os.environ if environ is None else environ
    candidates = [
        short_venv_python(platform_name=platform_name, environ=environ),
        project_venv_python(project_root, platform_name=platform_name),
    ]
    seen: set[str] = set()
    for candidate in candidates:
        if candidate is None:
            continue
        key = os.path.normcase(os.path.abspath(str(candidate)))
        if key in seen:
            continue
        seen.add(key)
        yield candidate


def _same_path(left: str | Path, right: str | Path) -> bool:
    try:
        return Path(left).resolve() == Path(right).resolve()
    except OSError:
        return os.path.normcase(os.path.abspath(str(left))) == os.path.normcase(
            os.path.abspath(str(right))
        )


def choose_local_runtime(
    project_root: Path,
    *,
    platform_name: Optional[str] = None,
    executable: Optional[str] = None,
    frozen: Optional[bool] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> Optional[Path]:
    """Decide si el proceso debe cambiarse al runtime administrado.

    Solo se activa en Windows para la distribución de código fuente. Los EXE
    empaquetados, las pruebas que lo deshabilitan y procesos que ya usan uno de
    los runtimes permitidos continúan sin cambios.
    """
    platform_name = platform_name or sys.platform
    executable = executable or sys.executable
    frozen = bool(getattr(sys, "frozen", False)) if frozen is None else bool(frozen)
    environ = os.environ if environ is None else environ

    if platform_name != "win32" or frozen:
        return None
    if environ.get(DISABLE_MARKER) == "1" or environ.get(BOOTSTRAP_MARKER) == "1":
        return None

    candidates = tuple(runtime_candidates(project_root, platform_name=platform_name, environ=environ))
    for candidate in candidates:
        if _same_path(executable, candidate):
            return None
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def bootstrap_local_venv(
    project_root: Path,
    *,
    argv: Optional[Sequence[str]] = None,
    executable: Optional[str] = None,
    environ: Optional[MutableMapping[str, str]] = None,
    execv: Optional[Callable[[str, Sequence[str]], object]] = None,
    platform_name: Optional[str] = None,
) -> bool:
    """Reemplaza el proceso por el runtime administrado cuando procede.

    ``True`` solo se devuelve en pruebas con una función ``execv`` simulada;
    ``os.execv`` real no regresa si el reemplazo fue exitoso.
    """
    argv = list(sys.argv if argv is None else argv)
    environ = os.environ if environ is None else environ
    target = choose_local_runtime(
        project_root,
        platform_name=platform_name,
        executable=executable,
        environ=environ,
    )
    if target is None:
        return False

    script = project_root / "main.py"
    forwarded = list(argv[1:]) if argv else []
    command = [str(target), str(script), *forwarded]
    environ[BOOTSTRAP_MARKER] = "1"
    environ[RUNTIME_DIR_ENV] = str(target.parent.parent)
    runner = os.execv if execv is None else execv
    try:
        runner(str(target), command)
    except OSError:
        environ.pop(BOOTSTRAP_MARKER, None)
        raise
    return True
