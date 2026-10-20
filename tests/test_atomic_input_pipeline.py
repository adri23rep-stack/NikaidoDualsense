import time
from types import SimpleNamespace

from src.connection_manager import ChargingStatus, ConnectionManager


def put_s16(report, offset, value):
    value &= 0xFFFF
    report[offset] = value & 0xFF
    report[offset + 1] = (value >> 8) & 0xFF


def make_report():
    report = [0] * 64
    report[0] = 1
    report[1:7] = [10, 20, 30, 40, 50, 60]
    report[7] = 91
    report[8] = 0xF0 | 0x01  # cuatro caras + noreste
    report[9] = 0xFF
    report[10] = 0x07
    # DualSense real: gyro primero, acelerómetro después.
    put_s16(report, 16, 111)
    put_s16(report, 18, -222)
    put_s16(report, 20, 333)
    put_s16(report, 22, 1000)
    put_s16(report, 24, -2000)
    put_s16(report, 26, 3000)
    report[33] = 9
    x, y = 1234, 567
    report[34] = x & 0xFF
    report[35] = ((x >> 8) & 0x0F) | ((y & 0x0F) << 4)
    report[36] = (y >> 4) & 0xFF
    report[53] = 0x10 | 7
    return report


class AtomicDualSense:
    def __init__(self):
        self.states = make_report()
        # Estado deliberadamente viejo: nunca debe ganar al reporte atómico.
        self.state = SimpleNamespace(
            LX=0, LY=0, RX=0, RY=0, L2_value=0, R2_value=0,
            cross=False, circle=False, square=False, triangle=False,
            L1=False, R1=False, L2Btn=False, R2Btn=False,
            L3=False, R3=False, share=False, options=False,
            ps=False, touchBtn=False, micBtn=False,
            DpadUp=False, DpadDown=False, DpadLeft=False, DpadRight=False,
            gyro=SimpleNamespace(Pitch=9000, Yaw=9000, Roll=9000),
            accelerometer=SimpleNamespace(X=8, Y=8, Z=8),
        )


def test_atomic_report_wins_over_partially_updated_state():
    manager = ConnectionManager()
    manager.dualsense = AtomicDualSense()
    manager._connected = True
    captured = []
    manager.on_realtime_state_update(captured.append)
    manager._read_controller_state()
    state = captured[-1]
    assert (state.left_stick_x, state.left_stick_y, state.right_stick_x, state.right_stick_y) == (10, 20, 30, 40)
    assert (state.left_trigger, state.right_trigger) == (50, 60)
    assert all(state.buttons[name] for name in ("cross", "circle", "square", "triangle", "L1", "R1", "L2_btn", "R2_btn", "L3", "R3", "create", "options", "ps", "touchpad", "mute"))
    assert state.buttons["dpad_up"] and state.buttons["dpad_right"]
    assert not state.buttons["dpad_down"] and not state.buttons["dpad_left"]
    assert (state.gyro_pitch, state.gyro_yaw, state.gyro_roll) == (111, -222, 333)
    assert (state.accel_x, state.accel_y, state.accel_z) == (1000, -2000, 3000)
    assert (state.touchpad_x, state.touchpad_y, state.touchpad_id) == (1234, 567, 9)
    assert state.battery_level == 75
    assert state.charging_status == ChargingStatus.CHARGING


def test_dpad_nibble_decodes_all_directions_without_button_state_delay():
    expected = {
        0: (1, 0, 0, 0), 1: (1, 1, 0, 0), 2: (0, 1, 0, 0),
        3: (0, 1, 1, 0), 4: (0, 0, 1, 0), 5: (0, 0, 1, 1),
        6: (0, 0, 0, 1), 7: (1, 0, 0, 1), 8: (0, 0, 0, 0),
    }
    for value, flags in expected.items():
        decoded = ConnectionManager._decode_dpad(value)
        assert tuple(int(decoded[key]) for key in ("dpad_up", "dpad_right", "dpad_down", "dpad_left")) == flags


def test_slow_observers_do_not_throttle_realtime_buttons_or_vigem():
    manager = ConnectionManager()
    manager.dualsense = AtomicDualSense()
    manager._connected = True
    order = []
    manager.on_realtime_state_update(lambda _state: order.append("realtime"))
    manager.on_state_update(lambda _state: order.append("observer"))
    manager.emulator.update_from_dualsense = lambda _state: order.append("vigem")
    manager._last_observer_notification = time.perf_counter()
    manager._read_controller_state()
    assert order == ["realtime", "vigem"]


def test_face_button_press_and_release_reach_vigem_in_the_same_read():
    manager = ConnectionManager()
    controller = AtomicDualSense()
    manager.dualsense = controller
    manager._connected = True
    sent = []
    manager.emulator.update_from_dualsense = lambda state: sent.append(dict(state.buttons))

    controller.states[8] = 0x20 | 0x08  # cross + dpad neutral
    manager._read_controller_state()
    assert sent[-1]["cross"] is True

    controller.states = list(controller.states)
    controller.states[7] = (controller.states[7] + 1) & 0xFF
    controller.states[8] = 0x08
    manager._read_controller_state()
    assert sent[-1]["cross"] is False
