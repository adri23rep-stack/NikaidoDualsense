"""Comprueba solo paquetes del runtime, sin importar código de Nikaido.

Los archivos BAT ejecutan esta comprobación antes de cargar la interfaz. Así
pueden distinguir una dependencia ausente de una excepción dentro del proyecto.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys

if os.name != "nt":
    # El helper se prueba también en CI sin servidor gráfico. En Windows se
    # conserva el backend real de bandeja que usará la aplicación.
    os.environ.setdefault("PYSTRAY_BACKEND", "dummy")


COMMON_MODULES = (
    "PySide6",
    "PIL",
    "psutil",
    "pystray",
    "hid",
    "hidapi",
    "pydualsense",
)

WINDOWS_MODULES = (
    "comtypes",
    "pycaw.constants",
    "pycaw.pycaw",
    "win32api",
    "win32con",
    "vgamepad",
)

# Nikaido puede sustituir ``hidapi`` por el backend nativo ``hid`` antes de
# importar pydualsense. Importarlos aquí sin ese adaptador daría un falso fallo
# aun cuando el runtime tiene exactamente el fallback que usa la aplicación.
PRESENCE_ONLY_MODULES = {"hidapi", "pydualsense"}


def check_dependencies() -> list[tuple[str, str]]:
    failures: list[tuple[str, str]] = []
    modules = COMMON_MODULES + (WINDOWS_MODULES if os.name == "nt" else ())
    for module_name in modules:
        try:
            if module_name in PRESENCE_ONLY_MODULES:
                if importlib.util.find_spec(module_name) is None:
                    raise ModuleNotFoundError(module_name)
            else:
                importlib.import_module(module_name)
        except Exception as exc:
            failures.append(
                (module_name, f"{type(exc).__name__}: {exc}")
            )
    return failures


def main() -> int:
    failures = check_dependencies()
    if failures:
        print("[ERROR] El runtime tiene dependencias ausentes o que no pueden cargar:")
        for module_name, detail in failures:
            print(f"  - {module_name}: {detail}")
        return 1
    print(f"[OK] Dependencias del runtime disponibles en {sys.executable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
