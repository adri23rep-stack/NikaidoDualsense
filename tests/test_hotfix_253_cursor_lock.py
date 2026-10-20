import threading
from pathlib import Path

from tests.gui_source_catalog import GUI_SOURCE

from src.emulator import EmulatorManager
from src.gyro_engine import GyroEngine
from src.keyboard_gamepad import KeyboardGamepadEngine
from src.mouse_to_gyro import MouseGyroSource


class FakeEmulator:
    def release_all_inputs(self):
        return None


class FakeMouse:
    def __init__(self):
        self.stopped = False
        self.running = False
        self.pending = False
        self.started_delayed = 0
        self.started_immediate = 0
        self.toggle_action = ""

    def stop(self):
        self.stopped = True
        self.running = False
        self.pending = False

    def start_delayed(self, _seconds):
        self.started_delayed += 1
        self.pending = True
        return True

    def start(self):
        self.started_immediate += 1
        self.pending = False
        self.running = True
        return True

    def is_running(self):
        return self.running

    def is_activation_pending(self):
        return self.pending

    def note_toggle_action(self, action):
        self.toggle_action = action

    def arm_hotkey_toggle(self, _enabled):
        return True

    @property
    def backend(self):
        return "stopped"

    @property
    def last_error(self):
        return ""

    def get_status(self):
        return {"packets": 0}


def test_mouse_source_exposes_centering_and_escape_status():
    source = MouseGyroSource()
    status = source.get_status()
    assert status["escape_hotkey"] == "CTRL+M"
    assert status["cursor_centering"] is False
    assert status["emergency_stop_count"] == 0


def test_cursor_warp_is_ignored_but_physical_motion_is_kept():
    source = MouseGyroSource()
    source._last_center = (500, 400)
    source._last_position = (500, 400)
    source._ignore_next_warp = True

    assert source._accept_position(500, 400) is False
    assert source.consume_delta() == (0.0, 0.0)

    assert source._accept_position(512, 391) is True
    assert source.consume_delta() == (12.0, -9.0)




class FakeCursorApi:
    def __init__(self):
        self.positions = []

    def SetCursorPos(self, x, y):
        self.positions.append((x, y))
        return 1


def test_recenter_places_cursor_at_active_monitor_center():
    source = MouseGyroSource()
    source._running = True
    source._monitor_center = lambda _user32: (960, 540)
    api = FakeCursorApi()

    source._recenter_cursor(api, force=True)

    assert api.positions == [(960, 540)]
    assert source._last_center == (960, 540)
    assert source._ignore_next_warp is True
    assert source.get_status()["recenter_count"] == 1


def test_ctrl_m_emergency_callback_runs_once_and_clears_deltas():
    source = MouseGyroSource()
    called = threading.Event()
    source.set_emergency_stop_callback(called.set)
    source._running = True
    source.feed_delta(20, -4)

    source._request_emergency_stop()
    source._request_emergency_stop()

    assert called.wait(0.5)
    status = source.get_status()
    assert status["emergency_stop_count"] == 1
    assert status["emergency_stop_reason"] == "Ctrl+M"
    assert source.consume_delta() == (0.0, 0.0)
    # Desde 2.5.4 la fuente solo avisa; el propietario decide si pausa o arma.
    assert source._running is True


def test_keybridge_ctrl_m_temporarily_pauses_and_rearms_mouse_stick():
    engine = KeyboardGamepadEngine(FakeEmulator(), {"mouse_stick_enabled": True})
    fake_mouse = FakeMouse()
    fake_mouse.running = True
    engine._mouse = fake_mouse
    engine._running = True
    engine._mouse_axis = [0.7, -0.4]
    engine._axis["rx"] = 0.5
    engine._axis["ry"] = -0.5

    engine._handle_mouse_emergency_stop()

    assert engine.get_config()["mouse_stick_enabled"] is True
    assert engine._mouse_hotkey_paused is True
    assert engine._mouse_axis == [0.0, 0.0]
    assert engine._axis["rx"] == 0.0
    assert engine._axis["ry"] == 0.0
    assert fake_mouse.stopped is True
    assert fake_mouse.toggle_action == "disabled"

    engine._handle_mouse_emergency_stop()

    assert engine._mouse_hotkey_paused is False
    assert fake_mouse.started_immediate == 1
    assert fake_mouse.started_delayed == 0
    assert fake_mouse.toggle_action == "enabled"


def test_mouse_gyro_ctrl_m_keeps_gyro_profile_config_enabled():
    emulator = EmulatorManager()
    engine = GyroEngine(emulator=emulator)
    engine.apply_config({
        "enabled": True,
        "mode": "passthrough_ds4",
        "mouse_to_gyro_enabled": True,
    }, profile_id="default")
    assert engine.get_config().mouse_to_gyro_enabled is True

    fake_mouse = FakeMouse()
    fake_mouse.running = True
    emulator._mouse_to_gyro = fake_mouse
    emulator._mouse_to_gyro_enabled = True
    emulator._handle_mouse_to_gyro_emergency_stop()

    assert engine.get_config().mouse_to_gyro_enabled is True
    assert emulator._mouse_to_gyro_hotkey_paused is True
    assert fake_mouse.toggle_action == "disabled"


def test_hotfix_253_uses_global_safety_watchdog_and_cursor_recentering():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src" / "mouse_to_gyro.py").read_text(encoding="utf-8")
    ui = GUI_SOURCE
    main = (root / "main.py").read_text(encoding="utf-8")

    assert "NikaidoMouseSafety" in source
    assert "GetAsyncKeyState" in source
    assert "SetCursorPos" in source
    assert "MonitorFromWindow" in source
    assert 'self.VK_CONTROL' in source and 'self.VK_M' in source
    assert "Ctrl + M" in ui
    assert "Ctrl+M es una pausa de sesión" in main
    assert "persist_keybridge_mouse_escape" not in main
    assert "persist_mouse_gyro_escape" not in main
