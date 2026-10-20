"""Prueba visual mínima de Nikaido UI Studio sin requerir un DualSense.

Windows:
    python tools/smoke_test_ui_studio.py

Linux sin escritorio:
    xvfb-run -a python tools/smoke_test_ui_studio.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from gui.app import DualSenseGUI  # noqa: E402
from gui.ui_theme import load_layout, validate_layout  # noqa: E402


def main() -> int:
    sample = PROJECT_ROOT / "examples" / "nikaido_modern.nikaido-theme"
    if not sample.is_file():
        print(f"No se encontró la plantilla: {sample}")
        return 1

    extract_context = None
    app = DualSenseGUI()
    try:
        extract_context = tempfile.TemporaryDirectory(prefix="nikaido_ui_smoke_")
        layout = load_layout(sample, extract_dir=extract_context.name)
        errors, warnings = validate_layout(layout, check_assets=True)
        if errors:
            print("Tema inválido:")
            for error in errors:
                print(f"- {error}")
            return 1

        app.root.update_idletasks()
        app._activate_custom_ui(layout, persist=False)
        app.root.update()
        renderer = app._custom_ui_renderer
        if renderer is None or not renderer.winfo_exists():
            print("El renderer no se creó.")
            return 1
        if len(renderer._items) < 10:
            print(f"Se renderizaron muy pocos elementos: {len(renderer._items)}")
            return 1
        if not renderer.open_page("profiles"):
            print("No se pudo abrir la pantalla profiles.")
            return 1
        app.root.update()
        if not renderer.go_back_page():
            print("No se pudo volver a la pantalla anterior.")
            return 1
        app._show_standard_ui()
        app._show_custom_ui()
        app.root.update()
        print(f"UI Studio OK: {len(layout.elements)} elementos, {len(warnings)} advertencias")
        return 0
    finally:
        try:
            app.root.destroy()
        except Exception:
            pass
        if extract_context is not None:
            extract_context.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
