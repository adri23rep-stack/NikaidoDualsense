from pathlib import Path

from tests.gui_source_catalog import GUI_SOURCE

from src.emulator import EmulationMode, EmulatorManager
from src.keyboard_gamepad import KeyboardGamepadEngine


class FakeOutput:
    def release_all_inputs(self):
        return None


class InstantMouse:
    backend = "raw_input"
    last_error = ""

    def __init__(self, running=False):
        self.running = running
        self.pending = False
        self.immediate_starts = 0
        self.delayed_starts = 0
        self.stops = 0
        self.action = ""

    def is_running(self):
        return self.running

    def is_activation_pending(self):
        return self.pending

    def start(self):
        self.running = True
        self.pending = False
        self.immediate_starts += 1
        return True

    def start_delayed(self, _seconds):
        self.pending = True
        self.delayed_starts += 1
        return True

    def stop(self):
        self.running = False
        self.pending = False
        self.stops += 1

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


def test_keybridge_ctrl_m_reactivation_is_immediate():
    engine = KeyboardGamepadEngine(FakeOutput(), {"mouse_stick_enabled": True})
    mouse = InstantMouse(running=False)
    engine._mouse = mouse
    engine._running = True
    engine._mouse_hotkey_paused = True

    engine._handle_mouse_emergency_stop()

    assert mouse.immediate_starts == 1
    assert mouse.delayed_starts == 0
    assert mouse.running is True
    assert engine._mouse_hotkey_paused is False
    assert mouse.action == "enabled"


def test_mouse_gyro_ctrl_m_reactivation_is_immediate():
    emulator = EmulatorManager()
    mouse = InstantMouse(running=False)
    emulator._mouse_to_gyro = mouse
    emulator._mouse_to_gyro_enabled = True
    emulator._mouse_to_gyro_hotkey_paused = True
    emulator.mode = EmulationMode.PS4
    emulator.is_active = True
    emulator._input_source = "dualsense"

    emulator._handle_mouse_to_gyro_emergency_stop()

    assert mouse.immediate_starts == 1
    assert mouse.delayed_starts == 0
    assert mouse.running is True
    assert emulator._mouse_to_gyro_hotkey_paused is False
    assert mouse.action == "enabled"


def test_initial_activation_still_keeps_five_second_delay():
    engine = KeyboardGamepadEngine(FakeOutput(), {"mouse_stick_enabled": True})
    mouse = InstantMouse(running=False)
    engine._mouse = mouse

    assert engine._start_mouse_capture_delayed() is True
    assert mouse.delayed_starts == 1
    assert mouse.immediate_starts == 0


def test_overlay_is_click_through_in_qt_and_native_windows():
    root = Path(__file__).resolve().parents[1]
    ui = (root / "gui" / "design_system.py").read_text(encoding="utf-8")
    modern = GUI_SOURCE

    assert "WindowTransparentForInput" in ui
    assert "WA_TransparentForMouseEvents" in ui
    assert "WS_EX_TRANSPARENT" in ui
    assert "WS_EX_NOACTIVATE" in ui
    assert "WM_NCHITTEST" in ui
    assert "HTTRANSPARENT" in ui
    assert "_apply_native_click_through()" in ui
    assert "reactivarlo al instante" in modern
