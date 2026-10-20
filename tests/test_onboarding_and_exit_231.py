from pathlib import Path

from src.profile_manager import ProfileManager
from tests.gui_source_catalog import GUI_SOURCE, class_source


ROOT = Path(__file__).resolve().parents[1]
UI_SOURCE = GUI_SOURCE
MAIN_SOURCE = (ROOT / "main.py").read_text(encoding="utf-8")
DESIGN_SOURCE = (ROOT / "gui" / "design_system.py").read_text(encoding="utf-8")


def _method_block(name: str, next_name: str) -> str:
    source = class_source("NikaidoWindow")
    start = source.index(f"    def {name}(")
    end = source.index(f"    def {next_name}(", start)
    return source[start:end]


def test_close_and_minimize_are_separate_actions():
    assert '("−", "Minimizar", window.request_minimize)' in UI_SOURCE
    assert '("×", "Cerrar", window.request_close)' in UI_SOURCE
    close_block = _method_block("request_close", "exit_app")
    minimize_block = _method_block("request_minimize", "request_close")
    assert "minimize_to_tray" not in close_block
    assert "self.exit_app()" in close_block
    assert "minimize_to_tray" in minimize_block
    assert "self.hide()" in minimize_block


def test_shutdown_stops_interface_last_and_catches_external_qt_exit():
    assert MAIN_SOURCE.index('(\"bandeja\", lambda: self.tray_manager.stop()') < MAIN_SOURCE.index(
        '(\"interfaz\", lambda: self.gui.stop()'
    )
    assert "self.gui.run()\n            if not self._shutdown_started:\n                self.shutdown()" in MAIN_SOURCE


def test_onboarding_defaults_are_backward_compatible(tmp_path):
    manager = ProfileManager(config_dir=str(tmp_path))
    assert manager.get_setting("onboarding.completed") is False
    assert manager.get_setting("onboarding.version") == 0
    assert manager.get_setting("minimize_to_tray") is True


def test_wizard_exists_and_can_be_reopened_from_settings():
    assert "class WelcomeWizard(QDialog):" in UI_SOURCE
    version_source = (ROOT / "nikaido_version.py").read_text(encoding="utf-8")
    assert "ONBOARDING_VERSION = 6" in version_source
    assert 'button("Volver a iniciar el asistente de bienvenida", self.restart_wizard)' in UI_SOURCE
    assert "self.window.show_welcome_wizard(force=True)" in UI_SOURCE
    assert "self.call_later(900, self.maybe_show_welcome_wizard)" in UI_SOURCE


def test_wizard_saves_completion_and_core_preferences():
    for key in (
        "onboarding.completed",
        "onboarding.version",
        "auto_connect",
        "start_minimized",
        "minimize_to_tray",
        "game_profiles_enabled",
        "vibration_enabled",
        "appearance",
    ):
        assert f'pm.set_setting("{key}"' in UI_SOURCE


def test_wizard_has_dedicated_visual_system():
    for selector in (
        "QDialog#welcomeWizard",
        "QFrame#wizardHeader",
        "QFrame#wizardRail",
        'QLabel[wizardStep="true"]',
        'QPushButton[wizardDestination="true"]',
    ):
        assert selector in DESIGN_SOURCE


def test_runtime_shutdown_releases_tray_before_qt_interface():
    from types import SimpleNamespace
    from main import DualSenseApp

    calls = []

    class Stopper:
        def __init__(self, name, method="stop"):
            self.name = name
            setattr(self, method, self._record)

        def _record(self):
            calls.append(self.name)

    app = DualSenseApp(SimpleNamespace())
    app._running = True
    app.gyro_engine = Stopper("gyro")
    app.light_effect_engine = Stopper("lights", method="shutdown")
    app.trigger_engine = Stopper("triggers")
    app.touchpad_mouse = Stopper("touchpad")
    app.advanced_mapper = Stopper("mapper")
    app.game_profile_watcher = Stopper("games")
    app.connection_manager = Stopper("connection")
    app.tray_manager = Stopper("tray")
    app.gui = Stopper("gui")

    app.shutdown()

    assert calls[-2:] == ["tray", "gui"]
    assert app._running is False
