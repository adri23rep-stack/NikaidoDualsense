from pathlib import Path

from src.system_tray import PIL_AVAILABLE, TrayManager
from tests.gui_source_catalog import GUI_SOURCE


ROOT = Path(__file__).resolve().parents[1]
TRAY_SOURCE = (ROOT / "src" / "system_tray.py").read_text(encoding="utf-8")
UI_SOURCE = GUI_SOURCE


class FakeIcon:
    def __init__(self):
        self.icon = None
        self.title = ""
        self.menu = None
        self.notifications = []
        self.menu_updates = 0

    def update_menu(self):
        self.menu_updates += 1

    def notify(self, message, title):
        self.notifications.append((title, message))


def test_tray_icon_renderer_changes_with_battery_and_connection():
    assert PIL_AVAILABLE
    tray = TrayManager()
    high = tray._create_icon_image(battery_level=90, charging=False, connected=True)
    low = tray._create_icon_image(battery_level=10, charging=False, connected=True)
    charging = tray._create_icon_image(battery_level=55, charging=True, connected=True)
    disconnected = tray._create_icon_image(battery_level=None, charging=False, connected=False)

    assert high.size == (64, 64)
    assert high.mode == "RGBA"
    assert high.tobytes() != low.tobytes()
    assert charging.tobytes() != high.tobytes()
    assert disconnected.tobytes() != high.tobytes()


def test_battery_refresh_updates_image_and_exact_tooltip():
    tray = TrayManager()
    fake = FakeIcon()
    tray.icon = fake
    tray._visible = True

    tray.set_status("Conectado · USB")
    tray.set_battery(75, charging=True)
    tray.set_profiles([("fps", "FPS Competitivo")])
    tray.set_current_profile("fps")

    assert fake.icon is not None
    assert "Conectado · USB" in fake.title
    assert "Cargando · 75%" in fake.title
    assert "Perfil · FPS Competitivo" in fake.title


def test_disconnected_status_does_not_get_mistaken_for_connected():
    tray = TrayManager()
    tray.set_status("Conectado · BLUETOOTH")
    tray.set_battery(40)
    assert tray._connected is True
    assert tray._battery_level == 40

    tray.set_status("Desconectado")
    assert tray._connected is False
    assert tray._battery_level is None
    assert "Batería" not in tray._tooltip_text()


def test_minimize_notification_is_only_sent_once_per_session():
    tray = TrayManager()
    fake = FakeIcon()
    tray.icon = fake
    tray._visible = True

    tray.notify_minimized()
    tray.notify_minimized()

    assert len(fake.notifications) == 1
    assert "bandeja" in fake.notifications[0][0].casefold()


def test_left_click_default_action_and_gui_minimize_notification_are_wired():
    assert 'pystray.MenuItem("Abrir Nikaido", self._show_window, default=True)' in TRAY_SOURCE
    assert 'notify = getattr(tray, "notify_minimized", None)' in UI_SOURCE
    assert "if callable(notify):" in UI_SOURCE
