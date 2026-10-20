import threading
import time
from pathlib import Path

from src.emulator import EmulationMode, EmulatorManager
from src.keyboard_gamepad import DEFAULT_MAPPING, KeyboardGamepadEngine
from src.mouse_to_gyro import MouseGyroSource


class FakeUser32:
    def GetAsyncKeyState(self, _code):
        return 0


class FakeEmulator:
    def __init__(self):
        self.source = "dualsense"
        self.mode = EmulationMode.NONE
        self.states = []

    def set_input_source(self, source):
        self.source = source

    def set_mode(self, mode):
        self.mode = mode
        return True

    def update_from_keyboard(self, state):
        self.states.append(state)

    def release_all_inputs(self):
        return None


class FakeMouseSource:
    def __init__(self):
        self._running = False
        self._delta = [0.0, 0.0]
        self.backend = "raw_input"
        self.last_error = ""
        self._packets = 0
        self._lock = threading.Lock()

    def start(self):
        self._running = True
        return True

    def stop(self):
        self._running = False
        self.reset()

    def is_running(self):
        return self._running

    def reset(self):
        with self._lock:
            self._delta = [0.0, 0.0]

    def feed_delta(self, dx, dy):
        with self._lock:
            self._delta[0] += dx
            self._delta[1] += dy
            self._packets += 1

    def consume_delta(self):
        with self._lock:
            result = tuple(self._delta)
            self._delta = [0.0, 0.0]
            return result

    def get_status(self):
        return {"packets": self._packets}


def test_mouse_status_counts_real_deltas_and_consumes_once():
    source = MouseGyroSource()
    source.feed_delta(7, -3)
    status = source.get_status()
    assert status["packets"] == 1
    assert status["pending_delta"] == (7.0, -3.0)
    assert source.consume_delta() == (7.0, -3.0)
    assert source.consume_delta() == (0.0, 0.0)


def test_keybridge_keeps_mouse_motion_when_nikaido_has_focus():
    emulator = FakeEmulator()
    engine = KeyboardGamepadEngine(
        emulator,
        {
            "mode": "xbox",
            "mapping": DEFAULT_MAPPING,
            "mouse_stick_enabled": True,
            "mouse_sensitivity": 0.10,
            "mouse_smoothing": 0,
            "mouse_decay_ms": 100,
            "poll_hz": 250,
            "stick_ramp_ms": 0,
            "stick_release_ms": 0,
            "trigger_ramp_ms": 0,
            "ignore_when_nikaido_focused": True,
        },
    )
    fake_mouse = FakeMouseSource()
    engine._mouse = fake_mouse
    engine._user32 = FakeUser32()
    engine.is_available = lambda: True
    engine._nikaido_has_focus = lambda: True

    assert engine.start() is True
    fake_mouse.feed_delta(8, -4)
    time.sleep(0.04)
    engine.stop()

    assert any(state.right_stick_x != 128 for state in emulator.states)
    assert all(not any(state.buttons.values()) for state in emulator.states)


def test_mouse_capture_uses_raw_input_and_pointer_sized_windows_types():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src" / "mouse_to_gyro.py").read_text(encoding="utf-8")
    assert "RegisterRawInputDevices" in source
    assert 'self._backend = "raw_input"' in source
    assert "WPARAM_T = ctypes.c_size_t" in source
    assert "LPARAM_T = ctypes.c_ssize_t" in source
    assert 'self._backend = "low_level_hook"' in source
    assert 'self._backend = "cursor_poll"' in source


def test_emulator_exposes_mouse_capture_diagnostics():
    emulator = EmulatorManager()
    status = emulator.get_mouse_to_gyro_status()
    assert set(("available", "running", "backend", "last_error", "packets")) <= set(status)
