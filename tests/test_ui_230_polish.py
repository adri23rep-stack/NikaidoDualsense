from pathlib import Path

from src.appearance import (
    APPEARANCE_PRESETS,
    appearance_background_signature,
    appearance_style_signature,
    normalize_appearance,
)
from tests.gui_source_catalog import GUI_SOURCE

ROOT = Path(__file__).resolve().parents[1]
MODERN = GUI_SOURCE


def test_appearance_normalization_keeps_layout_and_validates_choices():
    clean = normalize_appearance(
        {
            "accent_style": "invalid",
            "ui_density": "tiny",
            "background_fit": "crop-weird",
            "background_position": "left",
            "sidebar_collapsed": 1,
            "background_zoom": 999,
        }
    )
    assert clean["accent_style"] == "violet"
    assert clean["ui_density"] == "comfortable"
    assert clean["background_fit"] == "cover"
    assert clean["background_position"] == "center"
    assert clean["sidebar_collapsed"] is True
    assert clean["background_zoom"] == 180
    assert len(APPEARANCE_PRESETS) >= 5


def test_appearance_rejects_infinite_numbers_without_crashing():
    clean = normalize_appearance(
        {
            "background_dim": "1e309",
            "background_zoom": float("inf"),
            "panel_opacity": float("-inf"),
        }
    )

    assert clean["background_dim"] == 58
    assert clean["background_zoom"] == 100
    assert clean["panel_opacity"] == 88


def test_background_only_changes_do_not_force_full_stylesheet_rebuild():
    base = normalize_appearance()
    changed = dict(base, background_dim=90, background_zoom=130)
    assert appearance_style_signature(base) == appearance_style_signature(changed)
    assert appearance_background_signature(base) != appearance_background_signature(changed)


def test_sidebar_can_collapse_and_preserves_navigation_accessibility():
    assert 'def set_sidebar_collapsed(' in MODERN
    assert 'target_width = 104 if collapsed else 320' in MODERN
    assert 'nav_button.set_compact(not expanded)' in MODERN
    assert 'values["sidebar_collapsed"] = collapsed' in MODERN
    assert 'self.sidebar_toggle.setAccessibleName("Contraer o expandir barra lateral")' in MODERN


def test_heavy_pages_are_lazy_and_failures_are_isolated():
    assert 'self._page_factories: Dict[str, tuple[str, str, str]]' in MODERN
    assert 'class PageLoadError(ScrollPage):' in MODERN
    assert 'widget = PageLoadError(self, page, exc)' in MODERN
    assert 'def retry_page(self, page: str)' in MODERN


def test_command_palette_refreshes_profiles_and_visual_presets_dynamically():
    assert 'self._build_entries()\n        self.search.clear()' in MODERN
    assert 'for profile_id, profile_name in trigger.get_profile_names()' in MODERN
    assert 'for preset_id, preset in APPEARANCE_PRESETS.items()' in MODERN
    assert 'self.window.apply_profile(str(pid))' in MODERN


def test_accent_palette_updates_both_qss_and_custom_painted_widgets():
    design = (ROOT / "gui" / "design_system.py").read_text(encoding="utf-8")
    assert 'def apply_runtime_palette(' in design
    assert 'C["accent"] = palette["accent"]' in design
    assert '_BASE_ACCENT["accent"]' in design
    assert 'apply_runtime_palette(self._appearance)' in MODERN
    assert 'for widget in self.findChildren(QWidget):' in MODERN


def test_nexus_controller_is_keyboard_accessible():
    assert 'self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)' in MODERN
    assert 'def _move_keyboard_selection(' in MODERN
    assert 'Qt.Key.Key_Left' in MODERN
    assert 'Qt.Key.Key_Return' in MODERN
    assert 'self.selected.emit(self._selected)' in MODERN
