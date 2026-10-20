"""Regresiones de arranque para Profile Gallery 2.9.8.5."""

from __future__ import annotations

import ast
from pathlib import Path

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
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def test_modern_app_profile_symbols_come_from_their_real_modules():
    source = (GUI / "modern_app.py").read_text(encoding="utf-8")
    assert "from .profile_editor import ProfileEditorDialog, profile_image_widget" in source
    assert "from .pages.profiles import ProfilesPage" in source
    assert "from .pages.profiles import ProfileEditorDialog" not in source


def test_profile_editor_exports_every_symbol_used_by_the_public_facade():
    available = _top_level_names(GUI / "profile_editor.py")
    assert {"ProfileEditorDialog", "profile_image_widget"} <= available


def test_profiles_page_keeps_the_legacy_image_widget_export():
    available = _top_level_names(GUI / "pages" / "profiles.py")
    assert {"ProfilesPage", "ProfileEditorDialog", "profile_image_widget"} <= available
    source = (GUI / "pages" / "profiles.py").read_text(encoding="utf-8")
    assert '__all__ = ["ProfileEditorDialog", "ProfilesPage", "profile_image_widget"]' in source


def test_safe_launcher_does_not_reinstall_dependencies_for_source_errors():
    source = (ROOT / "INICIAR_NIKAIDO.bat").read_text(encoding="utf-8")
    dependency_check = "check_runtime_dependencies.py"
    gui_check = "from gui.modern_app import DualSenseGUI"
    assert dependency_check in source
    assert gui_check in source
    assert ":repair_dependencies" in source
    assert ":source_error" in source
    assert "No se reinstalara el runtime" in source
    assert source.index(dependency_check) < source.index(gui_check)


def test_installer_separates_package_validation_from_project_validation():
    source = (ROOT / "install.bat").read_text(encoding="utf-8")
    dependency_check = "check_runtime_dependencies.py"
    gui_check = "from gui.modern_app import DualSenseGUI"
    assert dependency_check in source
    assert gui_check in source
    assert ":source_error" in source
    assert "Reinstalar paquetes no corregira este error" in source
    assert source.index(dependency_check) < source.index(gui_check)
