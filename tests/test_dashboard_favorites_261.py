"""Regresiones del Dashboard personalizable de Nikaido 2.6.2."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "gui" / "pages" / "dashboard.py"
PROFILE_MANAGER = ROOT / "src" / "profile_manager.py"


def _method_source(name: str) -> str:
    source = DASHBOARD.read_text(encoding="utf-8")
    tree = ast.parse(source)
    dashboard = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DashboardPage"
    )
    method = next(
        node for node in dashboard.body if isinstance(node, ast.FunctionDef) and node.name == name
    )
    return ast.get_source_segment(source, method) or ""


def test_dashboard_profile_preview_loads_the_custom_image_path():
    method = _method_source("_set_profile_image")
    assert 'getattr(profile, "image_path"' in method
    assert "load_scaled_pixmap" in method
    assert 'getattr(profile, "icon"' in method


def test_dashboard_starts_with_nexus_and_uses_the_pencil_menu_for_favorites():
    method = _method_source("_workbench")
    assert 'self._append_workbench_tab("mapper", fixed=True)' in method
    assert "for destination in self._favorite_destinations" in method
    assert "setTabsClosable(False)" in method
    assert 'QPushButton("✎")' in method
    assert "setCornerWidget" in method


def test_favorites_menu_supports_add_and_remove_without_close_buttons():
    method = _method_source("_rebuild_favorite_menu")
    assert 'addMenu(tr("Añadir favorito"' in method
    assert 'addMenu(tr("Eliminar favorito"' in method
    assert '"Solo está Nikaido Nexus"' in method


def test_quick_cards_offer_simple_controls_and_a_shortcut_button():
    preview = _method_source("_favorite_preview")
    emulation = _method_source("_emulation_quick_controls")
    settings = _method_source("_settings_quick_controls")
    assert '"Abrir sección"' in preview
    assert '"Usa el lápiz para agregar o quitar favoritos."' in preview
    assert '"Gyro"' in emulation
    assert '"Touchpad"' in emulation
    assert '"Mouse"' in emulation
    assert '"Windows"' in settings
    assert '"Bandeja"' in settings


def test_nexus_tab_is_protected_and_favorites_are_persisted():
    protect = _method_source("_protect_nexus_tab")
    remove = _method_source("_remove_favorite_destination")
    persist = _method_source("_persist_favorite_destinations")
    assert "QTabBar.ButtonPosition.LeftSide" in protect
    assert "QTabBar.ButtonPosition.RightSide" in protect
    assert "if not destination or destination not in self._favorite_destinations" in remove
    assert '"dashboard.favorite_tabs"' in persist


def test_profile_manager_has_an_empty_dashboard_favorites_default():
    source = PROFILE_MANAGER.read_text(encoding="utf-8")
    assert "'dashboard': {" in source
    assert "'favorite_tabs': []" in source


def test_profile_manager_migrates_old_configs_with_empty_dashboard_favorites(tmp_path):
    from src.profile_manager import ProfileManager

    manager = ProfileManager(str(tmp_path))
    assert manager.get_setting("dashboard.favorite_tabs") == []
