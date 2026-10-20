import threading
import time
from pathlib import Path

from tests.gui_source_catalog import GUI_SOURCE

from src.keyboard_gamepad import KeyboardGamepadEngine
from src.mouse_to_gyro import MouseGyroSource


class FakeEmulator:
    def release_all_inputs(self):
        return None


class DelayedSource(MouseGyroSource):
    def __init__(self):
        super().__init__()
        self.started = threading.Event()

    def is_available(self):
        return True

    def start(self):
        self.cancel_delayed_start()
        self.started.set()
        return True


def test_delayed_start_exposes_visible_countdown_state():
    source = DelayedSource()
    assert source.start_delayed(0.12) is True
    status = source.get_status()
    assert status["activation_pending"] is True
    assert 0.0 < status["activation_remaining_seconds"] <= 0.12
    assert status["backend"] == "countdown"
    assert source.started.wait(0.5)
    assert source.get_status()["activation_pending"] is False


def test_delayed_start_can_be_cancelled_before_cursor_capture():
    source = DelayedSource()
    source.start_delayed(0.20)
    source.stop()
    time.sleep(0.25)
    assert source.started.is_set() is False
    assert source.get_status()["activation_pending"] is False


def test_keybridge_diagnostics_distinguish_countdown_and_hotkey_pause():
    engine = KeyboardGamepadEngine(FakeEmulator(), {"mouse_stick_enabled": True})

    class FakeMouse:
        backend = "countdown"
        last_error = ""

        def is_running(self):
            return False

        def get_status(self):
            return {
                "activation_pending": True,
                "activation_remaining_seconds": 4.2,
                "hotkey_armed": True,
                "last_toggle_action": "arming",
                "emergency_stop_count": 1,
                "emergency_stop_reason": "Ctrl+M",
            }

    engine._mouse = FakeMouse()
    engine._running = True
    engine._thread = threading.current_thread()
    status = engine.get_diagnostics_snapshot()
    assert status["mouse_activation_pending"] is True
    assert status["mouse_activation_remaining_seconds"] == 4.2
    assert status["mouse_hotkey_armed"] is True
    assert status["mouse_last_toggle_action"] == "arming"


def test_repeated_delayed_start_does_not_restart_visible_countdown():
    source = DelayedSource()
    assert source.start_delayed(0.30) is True
    first = source.get_status()["activation_remaining_seconds"]
    time.sleep(0.06)
    assert source.start_delayed(0.30) is True
    second = source.get_status()["activation_remaining_seconds"]
    assert second < first - 0.03
    source.stop()


def test_keybridge_ctrl_m_is_reversible_without_erasing_configuration():
    engine = KeyboardGamepadEngine(FakeEmulator(), {"mouse_stick_enabled": True})

    class ToggleMouse:
        backend = "raw_input"
        last_error = ""

        def __init__(self):
            self.running = True
            self.pending = False
            self.stopped = 0
            self.delayed = 0
            self.immediate = 0
            self.action = ""

        def is_running(self):
            return self.running

        def is_activation_pending(self):
            return self.pending

        def stop(self):
            self.running = False
            self.pending = False
            self.stopped += 1

        def start_delayed(self, _delay):
            self.pending = True
            self.delayed += 1
            return True

        def start(self):
            self.pending = False
            self.running = True
            self.immediate += 1
            return True

        def arm_hotkey_toggle(self, _enabled):
            return True

        def note_toggle_action(self, action):
            self.action = action

        def get_status(self):
            return {
                "activation_pending": self.pending,
                "activation_remaining_seconds": 5.0 if self.pending else 0.0,
                "hotkey_armed": True,
                "last_toggle_action": self.action,
            }

    mouse = ToggleMouse()
    engine._mouse = mouse
    engine._running = True
    engine._thread = threading.current_thread()

    engine._handle_mouse_emergency_stop()
    assert mouse.stopped == 1
    assert engine.get_config()["mouse_stick_enabled"] is True
    assert engine.get_diagnostics_snapshot()["mouse_hotkey_paused"] is True

    engine._handle_mouse_emergency_stop()
    assert mouse.immediate == 1
    assert mouse.delayed == 0
    assert engine.get_config()["mouse_stick_enabled"] is True
    assert engine.get_diagnostics_snapshot()["mouse_activation_pending"] is False
    assert engine.get_diagnostics_snapshot()["mouse_hotkey_paused"] is False


def test_hotfix_254_has_top_level_countdown_and_true_ctrl_m_toggle():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src" / "mouse_to_gyro.py").read_text(encoding="utf-8")
    keybridge = (root / "src" / "keyboard_gamepad.py").read_text(encoding="utf-8")
    emulator = (root / "src" / "emulator.py").read_text(encoding="utf-8")
    ui = (root / "gui" / "design_system.py").read_text(encoding="utf-8")
    modern = GUI_SOURCE

    assert "DEFAULT_ACTIVATION_DELAY_SECONDS = 5.0" in source
    assert "NikaidoMouseHotkey" in source
    assert "start_delayed" in source
    assert "mouse_hotkey_paused" in keybridge
    assert "_mouse_to_gyro_hotkey_paused" in emulator
    assert "class MouseCaptureOverlay" in ui
    assert "MOUSE ACTIVADO" in ui
    assert "CTRL + M  ·  ACTIVAR / DESACTIVAR EL MOUSE" in ui
    assert "_sync_mouse_capture_overlay" in modern
