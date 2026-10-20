"""Regresiones de arranque corregidas en Nikaido 2.9.5.1."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui"


def _top_level_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _design_system_imports() -> set[str]:
    requested: set[str] = set()
    for path in GUI.rglob("*.py"):
        if path.name == "design_system.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module == "design_system" and node.level in {1, 2}:
                requested.update(alias.name for alias in node.names if alias.name != "*")
    return requested


def test_design_system_exports_every_symbol_requested_by_the_gui():
    """Evita que la GUI falle antes de abrir por un re-export olvidado."""
    available = _top_level_names(GUI / "design_system.py")
    requested = _design_system_imports()
    assert requested
    assert requested <= available, f"Faltan exports de GUI: {sorted(requested - available)}"


def test_runtime_declares_comtypes_explicitly_for_windows_audio():
    requirements = (ROOT / "requirements-runtime.txt").read_text(encoding="utf-8")
    assert 'comtypes>=1.4.10,<2; platform_system == "Windows"' in requirements


def test_installer_verifies_gui_and_audio_imports_after_installing():
    installer = (ROOT / "install.bat").read_text(encoding="utf-8")
    dependency_check = (ROOT / "tools" / "check_runtime_dependencies.py").read_text(
        encoding="utf-8"
    )
    assert "check_runtime_dependencies.py" in installer
    assert '"comtypes"' in dependency_check
    assert "from gui.modern_app import DualSenseGUI" in installer


@pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None,
    reason="PySide6 no está instalado en este entorno",
)
def test_real_gui_import_smoke_when_qt_is_available(monkeypatch):
    """Ejecuta el mismo import que usa main.py cuando Qt está disponible."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from gui.design_system import APPEARANCE_PRESETS, DEFAULT_APPEARANCE
    from gui.modern_app import DualSenseGUI

    assert APPEARANCE_PRESETS
    assert DEFAULT_APPEARANCE
    assert DualSenseGUI.__name__ == "DualSenseGUI"

    gui = DualSenseGUI()
    gui.window.show()
    gui.app.processEvents()
    assert gui.window.windowTitle().startswith("Nikaido DualSense")
    assert gui.window.isVisible()
    gui.window.hide()
    gui.app.processEvents()
