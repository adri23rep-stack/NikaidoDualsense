import time
import unittest
from types import SimpleNamespace

from src.gyro_config import GyroConfig
from src.gyro_engine import GyroEngine


class FakeEmulator:
    def __init__(self):
        self.override = None
        self.passthrough = False
        self.passthrough_options = {}
        self.clear_count = 0
        self.recenter_count = 0

    def set_right_stick_override(self, x, y):
        self.override = (x, y)

    def clear_right_stick_override(self):
        self.override = None
        self.clear_count += 1

    def set_ds4_motion_passthrough(self, enabled, **kwargs):
        self.passthrough = bool(enabled)
        self.passthrough_options = dict(kwargs)

    def recenter_ds4_motion(self):
        self.recenter_count += 1

    def is_mouse_to_gyro_running(self):
        return False


class FakeConnection:
    def __init__(self, emulator):
        self.emulator = emulator
        self.state_callbacks = []
        self.connect_callbacks = []
        self.disconnect_callbacks = []

    def on_state_update(self, callback):
        self.state_callbacks.append(callback)

    def on_connect(self, callback):
        self.connect_callbacks.append(callback)

    def on_disconnect(self, callback):
        self.disconnect_callbacks.append(callback)

    def connect(self):
        for callback in self.connect_callbacks:
            callback(SimpleNamespace(value="usb"))

    def emit(self, state):
        for callback in self.state_callbacks:
            callback(state)


class MouseRecorder:
    def __init__(self):
        self.moves = []
        self.resets = 0

    def move(self, x, y):
        self.moves.append((x, y))
        return True

    def reset(self):
        self.resets += 1

    def stop(self):
        self.reset()

    def is_available(self):
        return True


def make_state(**changes):
    data = dict(
        gyro_pitch=0, gyro_yaw=0, gyro_roll=0,
        accel_x=0, accel_y=0, accel_z=0,
        left_trigger=0, right_trigger=0,
        right_stick_x=128, right_stick_y=128,
        touchpad_active=False, buttons={},
    )
    data.update(changes)
    return SimpleNamespace(**data)


class GyroEngineTests(unittest.TestCase):
    def setUp(self):
        self.emulator = FakeEmulator()
        self.connection = FakeConnection(self.emulator)
        self.engine = GyroEngine(self.connection, self.emulator)
        self.engine.start()

    def tearDown(self):
        self.engine.stop()

    def test_right_stick_output_and_release(self):
        cfg = GyroConfig.from_dict({
            "enabled": True, "mode": "right_stick", "activation": "always",
            "deadzone": 0, "min_threshold": 0, "smoothing": 0,
            "stick_deadzone": 0, "stick_anti_deadzone": 0,
            "stick_sensitivity_x": 0.01, "stick_sensitivity_y": 0.01,
            "stick_mix_mode": "replace", "invert_y": False,
        })
        self.engine.apply_config(cfg, "test")
        self.connection.emit(make_state(gyro_yaw=800, gyro_pitch=400))
        self.assertIsNotNone(self.emulator.override)
        self.assertGreater(self.emulator.override[0], 0)
        self.assertGreater(self.emulator.override[1], 0)

        self.engine.update_config(mode="passthrough_ds4")
        self.assertIsNone(self.emulator.override)
        self.assertTrue(self.emulator.passthrough)

        self.engine.update_config(enabled=False)
        self.assertIsNone(self.emulator.override)
        self.assertFalse(self.emulator.passthrough)
        self.assertGreater(self.emulator.clear_count, 0)

    def test_mouse_pipeline(self):
        recorder = MouseRecorder()
        self.engine.mouse = recorder
        self.engine.apply_config({
            "enabled": True, "mode": "mouse", "activation": "always",
            "deadzone": 0, "min_threshold": 0, "smoothing": 0,
            "sensitivity_x": 2, "sensitivity_y": 2, "invert_y": False,
        }, "mouse")
        self.connection.emit(make_state(gyro_yaw=1600, gyro_pitch=800))
        self.assertEqual(len(recorder.moves), 1)
        self.assertGreater(recorder.moves[0][0], 0)
        self.assertGreater(recorder.moves[0][1], 0)

    def test_calibration_uses_average_and_is_persistable(self):
        saved = []
        self.engine.on_config_change(lambda profile, config: saved.append((profile, config)))
        self.engine.apply_config({"enabled": True, "mode": "mouse"}, "cal")
        self.engine.begin_calibration(30)
        for _ in range(30):
            self.connection.emit(make_state(gyro_pitch=160, gyro_yaw=-80, gyro_roll=32))
        deadline = time.time() + 1
        while not saved and time.time() < deadline:
            time.sleep(0.01)
        cal = self.engine.get_config().calibration
        self.assertAlmostEqual(cal.pitch_bias, 160)
        self.assertAlmostEqual(cal.yaw_bias, -80)
        self.assertAlmostEqual(cal.roll_bias, 32)
        self.assertEqual(cal.version, 3)
        self.assertTrue(cal.valid)
        self.assertTrue(saved)

    def test_passthrough_receives_profile_calibration_bias(self):
        self.engine.apply_config({
            "enabled": True,
            "mode": "passthrough_ds4",
            "calibration": {
                "pitch_bias": 12,
                "yaw_bias": -34,
                "roll_bias": 56,
            },
        }, "ds4")
        self.assertEqual(
            self.emulator.passthrough_options.get("gyro_bias"),
            (12.0, -34.0, 56.0),
        )
        self.assertFalse(self.emulator.passthrough_options.get("gyro_bias_trusted"))

        self.engine.apply_config({
            "enabled": True,
            "mode": "passthrough_ds4",
            "calibration": {
                "version": 3, "valid": True,
                "pitch_bias": 12, "yaw_bias": -34, "roll_bias": 56,
            },
        }, "ds4")
        self.assertTrue(self.emulator.passthrough_options.get("gyro_bias_trusted"))

    def test_recenter_resets_virtual_motion_source(self):
        self.engine.apply_config({"enabled": True, "mode": "passthrough_ds4"}, "ds4")
        self.engine.recenter()
        self.assertEqual(self.emulator.recenter_count, 1)

    def test_passthrough_toggle_disconnect_and_reconnect(self):
        self.engine.apply_config({"enabled": True, "mode": "passthrough_ds4"}, "ds4")
        self.assertTrue(self.emulator.passthrough)
        for callback in self.connection.disconnect_callbacks:
            callback()
        self.assertFalse(self.emulator.passthrough)
        self.assertIsNone(self.emulator.override)
        self.connection.connect()
        self.assertTrue(self.emulator.passthrough)


    def test_activation_modes_use_physical_state_and_toggle_edges(self):
        recorder = MouseRecorder()
        self.engine.mouse = recorder
        base = {
            "enabled": True, "mode": "mouse",
            "deadzone": 0, "min_threshold": 0, "smoothing": 0,
            "sensitivity_x": 1, "sensitivity_y": 1, "invert_y": False,
        }

        self.engine.apply_config({**base, "activation": "hold_l2", "activation_threshold": 20}, "act")
        self.connection.emit(make_state(gyro_yaw=800, left_trigger=19))
        self.assertEqual(len(recorder.moves), 0)
        self.connection.emit(make_state(gyro_yaw=800, left_trigger=20))
        self.assertEqual(len(recorder.moves), 1)

        recorder.moves.clear()
        self.engine.apply_config({**base, "activation": "touchpad"}, "act")
        self.connection.emit(make_state(gyro_yaw=800, touchpad_active=False))
        self.assertEqual(len(recorder.moves), 0)
        self.connection.emit(make_state(gyro_yaw=800, touchpad_active=True))
        self.assertEqual(len(recorder.moves), 1)

        recorder.moves.clear()
        self.engine.apply_config({**base, "activation": "toggle", "activation_button": "R1"}, "act")
        # Primer flanco activa; mantener no vuelve a alternar.
        self.connection.emit(make_state(gyro_yaw=800, buttons={"R1": True}))
        self.connection.emit(make_state(gyro_yaw=800, buttons={"R1": True}))
        self.assertEqual(len(recorder.moves), 2)
        # Soltar conserva el estado; el siguiente flanco lo apaga.
        self.connection.emit(make_state(gyro_yaw=800, buttons={"R1": False}))
        self.connection.emit(make_state(gyro_yaw=800, buttons={"R1": True}))
        self.assertEqual(len(recorder.moves), 3)
        self.assertFalse(self.engine.get_telemetry().active)

        recorder.moves.clear()
        self.engine.apply_config({**base, "activation": "inverted", "activation_button": "R1"}, "act")
        self.connection.emit(make_state(gyro_yaw=800, buttons={"R1": False}))
        self.connection.emit(make_state(gyro_yaw=800, buttons={"R1": True}))
        self.assertEqual(len(recorder.moves), 1)

    def test_passthrough_active_telemetry_and_disabled_cleanup(self):
        self.engine.apply_config({"enabled": True, "mode": "passthrough_ds4", "activation": "hold_l2"}, "ds4")
        self.connection.emit(make_state(left_trigger=0))
        self.assertTrue(self.engine.get_telemetry().active)
        self.engine.update_config(enabled=False)
        self.connection.emit(make_state())
        self.assertFalse(self.engine.get_telemetry().active)
        self.assertFalse(self.emulator.passthrough)

    def test_precision_curve_and_prioritize_mix_are_bounded(self):
        self.assertEqual(self.engine._apply_response_curve(0.5, -0.5, "precision"), (0.25, -0.25))
        cfg = GyroConfig.from_dict({
            "enabled": True, "mode": "right_stick", "activation": "always",
            "deadzone": 0, "min_threshold": 0, "smoothing": 0,
            "stick_deadzone": 0, "stick_anti_deadzone": 0,
            "stick_sensitivity_x": 0.01, "stick_sensitivity_y": 0.01,
            "stick_mix_mode": "prioritize", "stick_mix": 0.75,
            "invert_y": False,
        })
        self.engine.apply_config(cfg, "mix")
        # Gyro X ~= 0.5 y stick fisico X ~= -0.5: debe dominar gyro sin saltar.
        self.connection.emit(make_state(gyro_yaw=800, right_stick_x=64))
        self.assertIsNotNone(self.emulator.override)
        self.assertGreater(self.emulator.override[0], 0.2)
        self.assertLessEqual(abs(self.emulator.override[0]), 1.0)


if __name__ == "__main__":
    unittest.main()


def test_flick_stick_mouse_queues_directional_turn():
    emulator = FakeEmulator()
    connection = FakeConnection(emulator)
    engine = GyroEngine(connection, emulator)
    recorder = MouseRecorder()
    engine.mouse = recorder
    engine.start()
    engine.apply_config({
        'enabled': True, 'mode': 'mouse', 'activation': 'always',
        'deadzone': 0, 'min_threshold': 0, 'smoothing': 0,
        'sensitivity_x': 0.01, 'sensitivity_y': 0.01,
        'flick_stick_enabled': True, 'flick_threshold': 0.8,
        'flick_release_threshold': 0.5, 'flick_pixels_per_degree': 2.0,
        'flick_duration_ms': 80,
    }, 'flick')
    connection.emit(make_state(right_stick_x=255, right_stick_y=128))
    assert recorder.moves
    assert recorder.moves[-1][0] > 0
    telemetry = engine.get_telemetry()
    assert telemetry.flick_active
    assert 80 <= telemetry.flick_angle <= 100
    engine.stop()


def test_flick_stick_ignores_stick_below_threshold():
    emulator = FakeEmulator()
    connection = FakeConnection(emulator)
    engine = GyroEngine(connection, emulator)
    recorder = MouseRecorder()
    engine.mouse = recorder
    engine.start()
    engine.apply_config({
        'enabled': True, 'mode': 'mouse', 'activation': 'always',
        'deadzone': 0, 'min_threshold': 0, 'smoothing': 0,
        'sensitivity_x': 0.01, 'sensitivity_y': 0.01,
        'flick_stick_enabled': True, 'flick_threshold': 0.85,
    }, 'flick')
    connection.emit(make_state(right_stick_x=180, right_stick_y=128))
    assert recorder.moves[-1][0] == 0
    assert not engine.get_telemetry().flick_active
    engine.stop()


def test_calibration_counts_only_unique_raw_hid_reports():
    emulator = FakeEmulator()
    connection = FakeConnection(emulator)
    engine = GyroEngine(connection, emulator)
    engine.start()
    engine.apply_config({"enabled": True, "mode": "mouse"}, "cal")
    engine.begin_calibration(30)

    duplicate = make_state(
        source="raw_hid",
        sequence=9,
        gyro_pitch=16,
        gyro_yaw=-8,
        gyro_roll=4,
    )
    for _ in range(30):
        connection.emit(duplicate)

    assert engine.get_telemetry().calibrating
    assert engine._calibration_count == 1

    for sequence in range(10, 39):
        connection.emit(make_state(
            source="raw_hid",
            sequence=sequence,
            gyro_pitch=16,
            gyro_yaw=-8,
            gyro_roll=4,
        ))

    assert not engine.get_telemetry().calibrating
    assert engine.get_config().calibration.valid
    engine.stop()


def test_dynamic_bias_does_not_learn_duplicate_raw_hid_snapshot():
    emulator = FakeEmulator()
    connection = FakeConnection(emulator)
    engine = GyroEngine(connection, emulator)
    engine.start()
    engine.apply_config({
        "enabled": True,
        "mode": "mouse",
        "activation": "always",
        "deadzone": 10,
        "drift_filter": True,
    }, "drift")

    sample = make_state(source="raw_hid", sequence=12, gyro_yaw=16)
    connection.emit(sample)
    first_bias = tuple(engine._dynamic_bias)
    for _ in range(100):
        connection.emit(sample)

    assert tuple(engine._dynamic_bias) == first_bias
    engine.stop()
