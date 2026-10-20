from pathlib import Path

from tests.gui_source_catalog import GUI_SOURCE as SOURCE, classes, methods

ROOT = Path(__file__).resolve().parents[1]


def _classes():
    return classes()


def _method_names(class_name):
    return methods(class_name)


def test_vibration_and_adaptive_triggers_are_separate_pages():
    classes = _classes()
    assert "VibrationPage" in classes
    assert "AdaptiveTriggersPage" in classes


def test_adaptive_triggers_has_its_own_navigation_key():
    assert '"triggers": ("triggers_page", "gui.pages.triggers", "AdaptiveTriggersPage")' in SOURCE
    assert '("triggers", "↯", "Gatillos adaptativos", "Rigidez, efectos y curvas")' in SOURCE
    assert '"triggers": ("Gatillos adaptativos"' in SOURCE


def test_pages_include_cross_navigation_for_new_users():
    assert "open_triggers" in _method_names("VibrationPage")
    assert "open_vibration" in _method_names("AdaptiveTriggersPage")
    assert "¿Buscas la rigidez de L2 y R2?" in SOURCE


def test_cross_navigation_preserves_selected_profile():
    assert 'page = self.window.ensure_page("triggers")' in SOURCE
    assert 'page = self.window.ensure_page("vibration")' in SOURCE
    assert 'page.select_profile(str(profile_id))' in SOURCE


def test_sidebar_uses_dark_transparent_scroll_surface_and_modern_nav_cards():
    design_source = (ROOT / "gui" / "design_system.py").read_text(encoding="utf-8")
    assert 'side.setFixedWidth(320)' in SOURCE
    assert 'self.nav_scroll.setObjectName("navScroll")' in SOURCE
    assert 'nav_body.setObjectName("navBody")' in SOURCE
    assert 'class SidebarNavButton(QPushButton):' in SOURCE
    assert 'self.setProperty("hasSubtitle", bool(subtitle))' in SOURCE
    assert 'self.setMinimumHeight(64 if subtitle else 50)' in SOURCE
    assert 'QScrollArea#navScroll > QWidget > QWidget' in design_source
    assert 'QWidget#navBody' in design_source
    assert 'QPushButton[nav="true"] QLabel#navIcon' in design_source
