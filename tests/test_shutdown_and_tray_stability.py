from types import SimpleNamespace

from main import DualSenseApp
from src.system_tray import TrayManager


def test_tray_profile_name_is_reflected_in_tooltip_state():
    tray = TrayManager()
    tray.set_profiles([("a", "Perfil A"), ("b", "Perfil B")])
    tray.set_current_profile("b")
    assert tray._profile_text == "Perfil B"


def test_shutdown_continues_when_one_module_fails():
    app = DualSenseApp(SimpleNamespace())
    app._running = True
    calls = []

    class Broken:
        def stop(self):
            calls.append("broken")
            raise RuntimeError("boom")

    class Healthy:
        def stop(self):
            calls.append("healthy")

    app.trigger_engine = Broken()
    app.connection_manager = Healthy()
    app.shutdown()

    assert calls == ["broken", "healthy"]
    assert app._running is False
