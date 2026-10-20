from pathlib import Path

from src.profile_manager import ProfileManager
from src.system_tray import TrayManager

ROOT = Path(__file__).resolve().parents[1]


def test_low_profile_default_is_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    manager = ProfileManager()
    assert manager.get_setting("low_profile_on_minimize", False) is True


def test_tray_tracks_low_profile_and_dispatches_action():
    tray = TrayManager()
    calls = []
    unsubscribe = tray.on_low_profile(lambda: calls.append("low"))
    tray.set_low_profile(True)
    tray._activate_low_profile()
    assert tray._low_profile_active is True
    assert calls == ["low"]
    unsubscribe()
    tray._activate_low_profile()
    assert calls == ["low"]


def test_runtime_destroys_and_rebuilds_only_the_gui():
    source = (ROOT / "gui" / "low_profile_runtime.py").read_text(encoding="utf-8")
    assert "setQuitOnLastWindowClosed(False)" in source
    assert "old_window.stop()" in source
    assert "old_window, self.window = self.window, None" in source
    assert "QPixmapCache.clear()" in source
    assert "gc.collect()" in source
    assert "self._create_window().show_window()" in source
    assert 'backends["low_profile_handler"] = self.enter_low_profile' in source


def test_minimize_setting_and_tray_wiring_are_present():
    window = (ROOT / "gui" / "main_window.py").read_text(encoding="utf-8")
    settings = (ROOT / "gui" / "pages" / "settings.py").read_text(encoding="utf-8")
    dashboard = (ROOT / "gui" / "pages" / "dashboard.py").read_text(encoding="utf-8")
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    assert 'get_setting("low_profile_on_minimize", True)' in window
    assert '"low_profile_on_minimize", True' in settings
    assert '"low_profile_on_minimize", True' in dashboard
    assert "on_low_profile(self.gui.enter_low_profile)" in main
