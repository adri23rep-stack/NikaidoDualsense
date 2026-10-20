from pathlib import Path

from tests.gui_source_catalog import GUI_SOURCE

MODERN = GUI_SOURCE
DESIGN = (Path(__file__).resolve().parents[1] / "gui" / "design_system.py").read_text(encoding="utf-8")


def test_ui_uses_non_modal_toasts_and_debounced_saves():
    assert "class ToastOverlay" in DESIGN
    assert "def request_config_save" in MODERN
    assert "self.config_save_timer.setSingleShot(True)" in MODERN
    assert "self._persist_timer.timeout.connect(self._persist_now)" in MODERN


def test_live_updates_are_limited_to_visible_page():
    assert 'if self._current_page == "input"' in MODERN
    assert 'elif self._current_page == "gyro"' in MODERN
    assert 'elif self._current_page == "calibration"' in MODERN


def test_sidebar_and_profile_cards_are_responsive():
    assert "self.nav_scroll = QScrollArea()" in MODERN
    assert "def _refresh_if_layout_changed" in MODERN
    assert "def _column_count" in MODERN
    assert "self._responsive_timer.setInterval(120)" in MODERN


def test_tray_actions_are_forwarded_through_qt_signals():
    assert "show_requested = Signal()" in MODERN
    assert "exit_requested = Signal()" in MODERN
    assert "profile_requested = Signal(str)" in MODERN
    assert "self._lifecycle.show_requested.emit()" in MODERN


def test_tabs_use_modern_non_elided_scrollable_style():
    assert "def configure_tabs" in DESIGN
    assert "ElideNone" in DESIGN
    assert "setUsesScrollButtons(True)" in DESIGN
    assert "configure_tabs(QTabWidget())" in MODERN
