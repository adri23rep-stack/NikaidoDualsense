import src.emulator as emulator_module
from src.emulator import EmulationMode, EmulatorManager


class FakeGamepad:
    def __init__(self):
        self.callback = None
        self.unregistered = False
        self.reset_count = 0
        self.update_count = 0

    def register_notification(self, callback_function=None):
        self.callback = callback_function

    def unregister_notification(self):
        self.unregistered = True

    def reset(self):
        self.reset_count += 1

    def update(self):
        self.update_count += 1


class FakeVG:
    def __init__(self):
        self.created = []

    def VX360Gamepad(self):
        gamepad = FakeGamepad()
        self.created.append(gamepad)
        return gamepad

    def VDS4Gamepad(self):
        gamepad = FakeGamepad()
        self.created.append(gamepad)
        return gamepad


def test_vigem_feedback_callback_is_registered_published_and_removed(monkeypatch):
    fake_vg = FakeVG()
    monkeypatch.setattr(emulator_module, "vg", fake_vg)
    monkeypatch.setattr(emulator_module, "VGAMEPAD_AVAILABLE", True)
    manager = EmulatorManager()
    received = []
    manager.on_feedback(received.append)

    assert manager.set_mode(EmulationMode.XBOX) is True
    gamepad = fake_vg.created[-1]
    assert callable(gamepad.callback)
    gamepad.callback(None, None, 220, 45, 3, None)

    assert received[-1]["large_motor"] == 220
    assert received[-1]["small_motor"] == 45
    assert received[-1]["led_number"] == 3
    snapshot = manager.get_diagnostics_snapshot()
    assert snapshot["feedback_registered"] is True
    assert snapshot["feedback_count"] >= 2  # incluye neutralización al cambiar modo

    assert manager.set_mode(EmulationMode.NONE) is True
    assert gamepad.unregistered is True
    assert manager.get_diagnostics_snapshot()["feedback_registered"] is False
