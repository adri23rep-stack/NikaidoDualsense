import time
from pathlib import Path

from tests.gui_source_catalog import GUI_SOURCE

from src.emulator import EmulationMode, EmulatorManager
from src.keyboard_gamepad import (
    DEFAULT_MAPPING,
    KeyboardGamepadEngine,
    key_to_vk,
    normalize_key_name,
    sanitize_keyboard_gamepad_config,
)


class FakeUser32:
    def __init__(self):
        self.down = set()

    def GetAsyncKeyState(self, code):
        return 0x8000 if int(code) in self.down else 0


class FakeEmulator:
    def __init__(self):
        self.source = "dualsense"
        self.mode = EmulationMode.NONE
        self.states = []
        self.releases = 0

    def set_input_source(self, source):
        self.source = source

    def set_mode(self, mode):
        self.mode = mode
        return True

    def update_from_keyboard(self, state):
        self.states.append(state)

    def release_all_inputs(self):
        self.releases += 1


def test_key_names_and_virtual_codes_are_stable():
    assert normalize_key_name("ctrl + f") == "CTRL+F"
    assert normalize_key_name("leftmouse") == "MOUSE1"
    assert key_to_vk("CTRL+F") == (0x11, ord("F"))
    assert key_to_vk("MOUSE2") == (0x02,)
    assert key_to_vk("\\") == (0xDC,)


def test_config_sanitizes_invalid_values_and_fills_default_mapping():
    config = sanitize_keyboard_gamepad_config(
        {
            "mode": "invalid",
            "mapping": {"cross": "space", "circle": "not-a-real-key"},
            "poll_hz": 9999,
            "mouse_sensitivity": -4,
        }
    )
    assert config["mode"] == "xbox"
    assert config["mapping"]["cross"] == "SPACE"
    assert config["mapping"]["circle"] == ""
    assert config["mapping"]["left_up"] == DEFAULT_MAPPING["left_up"]
    assert config["poll_hz"] == 500
    assert config["mouse_sensitivity"] == 0.002


def test_keyboard_state_builds_sticks_buttons_and_triggers():
    emulator = FakeEmulator()
    engine = KeyboardGamepadEngine(
        emulator,
        {
            "mode": "xbox",
            "mapping": DEFAULT_MAPPING,
            "mouse_stick_enabled": False,
            "stick_ramp_ms": 0,
            "stick_release_ms": 0,
            "trigger_ramp_ms": 0,
            "ignore_when_nikaido_focused": False,
        },
    )
    user32 = FakeUser32()
    engine._user32 = user32
    user32.down.update((ord("W"), 0x20, 0x01))  # W, Space, Mouse1

    state = engine._build_state(0.01, engine.get_config())
    assert state.left_stick_y == 0
    assert state.left_stick_x == 128
    assert state.buttons["cross"] is True
    assert state.buttons["R2_btn"] is True
    assert state.right_trigger == 255
    assert state.left_trigger == 0


def test_keybridge_reserves_emulator_and_restores_dualsense_source():
    emulator = FakeEmulator()
    engine = KeyboardGamepadEngine(
        emulator,
        {
            "mode": "ps4",
            "mapping": DEFAULT_MAPPING,
            "mouse_stick_enabled": False,
            "poll_hz": 250,
            "stick_ramp_ms": 0,
            "stick_release_ms": 0,
            "trigger_ramp_ms": 0,
            "ignore_when_nikaido_focused": False,
        },
    )
    engine._user32 = FakeUser32()
    engine.is_available = lambda: True

    assert engine.start() is True
    time.sleep(0.025)
    assert emulator.source == "keyboard"
    assert emulator.mode == EmulationMode.PS4
    assert emulator.states

    assert engine.stop() is True
    assert emulator.source == "dualsense"
    assert emulator.mode == EmulationMode.NONE
    assert emulator.releases >= 1


def test_emulator_ignores_physical_updates_while_keyboard_owns_vigem(monkeypatch):
    emulator = EmulatorManager()
    calls = []
    monkeypatch.setattr(
        emulator,
        "_update_from_state",
        lambda state, **kwargs: calls.append((state, kwargs)),
    )
    marker = object()

    emulator.set_input_source("keyboard")
    emulator.update_from_dualsense(marker)
    emulator.update_from_keyboard(marker)
    assert calls == [(marker, {"remap_buttons": False, "allow_motion": False})]

    emulator.set_input_source("dualsense")
    emulator.update_from_dualsense(marker)
    assert calls[-1] == (marker, {"remap_buttons": True, "allow_motion": True})


def test_keybridge_ui_and_lifecycle_are_wired_into_application():
    root = Path(__file__).resolve().parents[1]
    ui = GUI_SOURCE
    main = (root / "main.py").read_text(encoding="utf-8")
    assert "class KeyCaptureButton(QPushButton):" in ui
    assert "NIKAIDO KEYBRIDGE" in ui
    assert "Teclado y mouse → control virtual" in ui
    assert 'keyboard_gamepad=self.keyboard_gamepad' in main
    assert '("KeyBridge", lambda: self.keyboard_gamepad.stop()' in main


def test_keybridge_concurrent_start_creates_one_worker():
    import threading

    emulator = FakeEmulator()
    engine = KeyboardGamepadEngine(
        emulator,
        {
            "mode": "xbox",
            "mapping": DEFAULT_MAPPING,
            "mouse_stick_enabled": False,
            "ignore_when_nikaido_focused": False,
        },
    )
    engine._user32 = FakeUser32()
    engine.is_available = lambda: True
    gate = threading.Barrier(9)
    results = []

    def starter():
        gate.wait()
        results.append(engine.start())

    workers = [threading.Thread(target=starter) for _ in range(8)]
    for worker in workers:
        worker.start()
    gate.wait()
    for worker in workers:
        worker.join(1.0)

    assert all(results)
    assert engine._thread is not None and engine._thread.is_alive()
    assert len([
        thread for thread in threading.enumerate()
        if thread.name == "NikaidoKeyBridge" and thread.is_alive()
    ]) == 1
    engine.stop()
