"""Pruebas sin hardware del modo oficial 0x26 y vibracion por perfil."""

import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import src.trigger_engine as trigger_module
from src.trigger_engine import TriggerEffect, TriggerEffectType, TriggerEngine


class FakeTrigger:
    def __init__(self):
        self.mode = None
        self.forces = [0] * 7
        self.history = []

    def setMode(self, mode):
        self.mode = mode
        self.history.append(("mode", int(mode)))

    def setForce(self, index, value):
        self.forces[index] = value
        self.history.append(("force", index, value))


class FakeManager:
    def __init__(self):
        self.is_connected = True
        self.dualsense_instance = SimpleNamespace(
            triggerL=FakeTrigger(), triggerR=FakeTrigger()
        )
        self.callbacks = []
        self.rumble = (0, 0)

    def on_state_update(self, callback):
        self.callbacks.append(callback)

    def set_rumble(self, left, right):
        self.rumble = (left, right)


def unpack_vibration(params):
    active = params[0] | (params[1] << 8)
    packed = params[2] | (params[3] << 8) | (params[4] << 16) | (params[5] << 24)
    strengths = []
    for zone in range(10):
        strengths.append(((packed >> (zone * 3)) & 0x07) + 1 if active & (1 << zone) else 0)
    return strengths, params[6]


def test_packing_and_mode():
    engine = TriggerEngine()
    params = engine._pack_vibration_zones(2, 5, 255, 40)
    strengths, frequency = unpack_vibration(params)
    assert strengths == [0, 0, 8, 8, 8, 8, 0, 0, 0, 0], strengths
    assert frequency == 40

    effect = TriggerEffect(
        name="Vibracion",
        effect_type=TriggerEffectType.CONTINUOUS_VIBRATION,
        intensity=255,
        frequency=40,
        start_position=2,
        end_position=5,
    )
    assert int(engine._map_effect_to_mode(effect)) == 0x26
    assert engine._calculate_force_params(effect) == params


def test_serialization_and_overrides():
    effect = TriggerEffect(
        name="Base", effect_type=TriggerEffectType.RIGID,
        vibration_enabled=True, vibration_intensity=173,
        vibration_frequency=31, vibration_start_position=3,
        vibration_end_position=8,
    )
    restored = TriggerEffect.from_dict(effect.to_dict())
    assert restored.vibration_enabled is True
    assert restored.vibration_intensity == 173
    assert restored.vibration_frequency == 31
    assert restored.vibration_start_position == 3
    assert restored.vibration_end_position == 8

    engine = TriggerEngine()
    assert engine.update_profile_vibration(
        "pistol", "right", enabled=True, intensity=180,
        frequency=27, start_position=4, end_position=9
    )
    saved = engine.export_vibration_overrides()
    other = TriggerEngine()
    other.load_vibration_overrides(saved)
    cfg = other.get_profile_vibration_settings("pistol")["right"]
    assert cfg == {
        "enabled": True, "intensity": 180, "frequency": 27,
        "start_position": 4, "end_position": 9,
    }


def test_send_test_and_profile_overlay():
    manager = FakeManager()
    engine = TriggerEngine(manager)

    old_available = trigger_module.PYDUALSENSE_AVAILABLE
    trigger_module.PYDUALSENSE_AVAILABLE = True
    try:
        effect = TriggerEffect(
            name="Vibracion", effect_type=TriggerEffectType.CONTINUOUS_VIBRATION,
            intensity=220, frequency=33, start_position=1, end_position=9,
        )
        assert engine.apply_effect("right", effect)
        assert int(manager.dualsense_instance.triggerR.mode) == 0x26
        assert manager.dualsense_instance.triggerR.forces[6] == 33

        assert engine.test_trigger_vibration(
            target="both", intensity=200, frequency=44,
            start_position=2, end_position=7, duration=1
        )
        assert int(manager.dualsense_instance.triggerL.mode) == 0x26
        assert int(manager.dualsense_instance.triggerR.mode) == 0x26
        assert manager.dualsense_instance.triggerL.forces[6] == 44
        engine.stop_trigger_vibration_test(restore=True)

        engine.update_profile_vibration(
            "pistol", "right", enabled=True, intensity=210,
            frequency=29, start_position=4, end_position=9
        )
        assert engine.apply_profile("pistol")
        base_mode = int(manager.dualsense_instance.triggerR.mode)
        assert base_mode != 0x26

        state = SimpleNamespace(left_trigger=0, right_trigger=150)
        engine._on_controller_state_update(state)
        assert int(manager.dualsense_instance.triggerR.mode) == 0x26
        assert manager.dualsense_instance.triggerR.forces[6] == 29

        time.sleep(0.05)
        state.right_trigger = 0
        engine._on_controller_state_update(state)
        assert int(manager.dualsense_instance.triggerR.mode) == base_mode
    finally:
        engine.stop()
        trigger_module.PYDUALSENSE_AVAILABLE = old_available


def main():
    test_packing_and_mode()
    test_serialization_and_overrides()
    test_send_test_and_profile_overlay()
    print("OK: vibracion oficial 0x26, pruebas y perfiles")


if __name__ == "__main__":
    main()
