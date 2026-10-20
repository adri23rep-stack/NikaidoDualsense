"""Pruebas sin hardware para touchpad-mouse y curvas multizona."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import src.touchpad_mouse as touchpad_module
from src.trigger_engine import TriggerEffect, TriggerEffectType, TriggerEngine


def unpack_feedback(params):
    active = params[0] | (params[1] << 8)
    packed = params[2] | (params[3] << 8) | (params[4] << 16) | (params[5] << 24)
    result = []
    for zone in range(10):
        if not (active & (1 << zone)):
            result.append(0)
        else:
            result.append(((packed >> (zone * 3)) & 0x07) + 1)
    return result


def test_multizone():
    engine = TriggerEngine()
    points = [(0, 40), (3, 120), (6, 180), (9, 220)]
    zones = engine.get_section_zone_strengths(points)
    assert zones == [1, 1, 1, 4, 4, 4, 6, 6, 6, 7], zones

    effect = TriggerEffect(
        name="test",
        effect_type=TriggerEffectType.SECTIONS,
        custom_params={"sections": points},
    )
    params = engine._calculate_force_params(effect)
    assert len(params) == 7, params
    assert unpack_feedback(params) == zones
    assert int(engine._map_effect_to_mode(effect)) == 0x21

    class FakeTrigger:
        def __init__(self):
            self.mode = None
            self.forces = [99] * 7

        def setMode(self, mode):
            self.mode = mode

        def setForce(self, index, value):
            self.forces[index] = value

    fake = SimpleNamespace(triggerL=FakeTrigger(), triggerR=FakeTrigger())
    import src.trigger_engine as trigger_module
    old_available = trigger_module.PYDUALSENSE_AVAILABLE
    try:
        trigger_module.PYDUALSENSE_AVAILABLE = True
        engine._send_trigger_command(fake, "right", effect)
        assert int(fake.triggerR.mode) == 0x21
        assert fake.triggerR.forces == params
    finally:
        trigger_module.PYDUALSENSE_AVAILABLE = old_available


def test_touchpad_mouse():
    events = []

    class FakeApi:
        @staticmethod
        def mouse_event(flag, dx, dy, data, extra):
            events.append((flag, dx, dy, data, extra))

    class FakeCon:
        MOUSEEVENTF_MOVE = 0x0001
        MOUSEEVENTF_LEFTDOWN = 0x0002
        MOUSEEVENTF_LEFTUP = 0x0004

    class FakeManager:
        def __init__(self):
            self.callback = None

        def on_state_update(self, callback):
            self.callback = callback

    old_available = touchpad_module.WIN32_AVAILABLE
    old_api = getattr(touchpad_module, "win32api", None)
    old_con = getattr(touchpad_module, "win32con", None)
    try:
        touchpad_module.WIN32_AVAILABLE = True
        touchpad_module.win32api = FakeApi
        touchpad_module.win32con = FakeCon

        manager = FakeManager()
        controller = touchpad_module.TouchpadMouseController(manager)
        controller.set_sensitivity(1.0)
        controller.set_enabled(True)

        manager.callback(SimpleNamespace(
            touchpad_active=True, touchpad_x=100, touchpad_y=100,
            buttons={"touchpad": False},
        ))
        manager.callback(SimpleNamespace(
            touchpad_active=True, touchpad_x=112, touchpad_y=105,
            buttons={"touchpad": False},
        ))
        assert (FakeCon.MOUSEEVENTF_MOVE, 12, 5, 0, 0) in events

        manager.callback(SimpleNamespace(
            touchpad_active=True, touchpad_x=112, touchpad_y=105,
            buttons={"touchpad": True},
        ))
        controller.set_enabled(False)
        assert any(event[0] == FakeCon.MOUSEEVENTF_LEFTDOWN for event in events)
        assert events[-1][0] == FakeCon.MOUSEEVENTF_LEFTUP
    finally:
        touchpad_module.WIN32_AVAILABLE = old_available
        if old_api is not None:
            touchpad_module.win32api = old_api
        if old_con is not None:
            touchpad_module.win32con = old_con


def main():
    test_multizone()
    test_touchpad_mouse()
    print("OK: touchpad-mouse y curva multizona")


if __name__ == "__main__":
    main()
