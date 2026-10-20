import unittest
from types import SimpleNamespace

import src.connection_manager as connection_module
from src.connection_manager import ConnectionManager


class FakeDualSense:
    def __init__(self):
        self.state = SimpleNamespace(
            L2=201, R2=202, L2Btn=True, R2Btn=True,
            LX=-128, LY=0, RX=127, RY=-1,
            cross=True, circle=False, square=False, triangle=False,
            L1=True, R1=False, L3=True, R3=False,
            share=True, options=True, ps=True, touchBtn=True, micBtn=False,
            DpadUp=True, DpadDown=False, DpadLeft=False, DpadRight=True,
            trackPadTouch0=SimpleNamespace(isActive=True, X=1234, Y=567, ID=9),
            gyro=SimpleNamespace(Pitch=111, Yaw=-222, Roll=333),
            accelerometer=SimpleNamespace(X=1000, Y=-2000, Z=3000),
        )
        self.battery = SimpleNamespace(Level=75, State=1)


class ConnectionManagerGyroTests(unittest.TestCase):
    def test_reads_motion_touch_and_real_trigger_buttons(self):
        manager = ConnectionManager()
        manager.dualsense = FakeDualSense()
        manager._connected = True
        captured = []
        manager.on_state_update(captured.append)
        manager._read_controller_state()
        self.assertEqual(len(captured), 1)
        state = captured[0]
        self.assertEqual((state.gyro_pitch, state.gyro_yaw, state.gyro_roll), (111, -222, 333))
        self.assertEqual((state.accel_x, state.accel_y, state.accel_z), (1000, -2000, 3000))
        self.assertEqual((state.touchpad_x, state.touchpad_y, state.touchpad_id), (1234, 567, 9))
        self.assertTrue(state.touchpad_active)
        self.assertTrue(state.buttons['L2_btn'])
        self.assertTrue(state.buttons['R2_btn'])
        self.assertEqual((state.left_trigger, state.right_trigger), (201, 202))
        self.assertEqual((state.left_stick_x, state.left_stick_y), (0, 128))
        self.assertEqual((state.right_stick_x, state.right_stick_y), (255, 127))
        self.assertEqual(state.battery_level, 75)

    def test_player_led_uses_pydualsense_player_ids(self):
        original = connection_module.PlayerID
        fake_ids = SimpleNamespace(PLAYER_1=4, PLAYER_2=10, PLAYER_3=21, PLAYER_4=27, ALL=31)
        light = SimpleNamespace(selected=None)
        light.setPlayerID = lambda value: setattr(light, 'selected', value)
        manager = ConnectionManager()
        manager.dualsense = SimpleNamespace(light=light)
        try:
            connection_module.PlayerID = fake_ids
            manager.set_player_led(3)
            self.assertEqual(light.selected, 21)
            manager.set_player_led(5)
            self.assertEqual(light.selected, 31)
        finally:
            connection_module.PlayerID = original


if __name__ == '__main__':
    unittest.main()


def test_realtime_processors_run_before_vigem_and_observers_after():
    manager = ConnectionManager()
    manager.dualsense = FakeDualSense()
    manager._connected = True
    order = []
    manager.on_realtime_state_update(lambda _state: order.append("realtime"))
    manager.on_state_update(lambda _state: order.append("observer"))
    manager.emulator.update_from_dualsense = lambda _state: order.append("vigem")
    manager._read_controller_state()
    assert order == ["realtime", "vigem", "observer"]


def test_late_connection_and_battery_subscribers_receive_current_snapshot():
    manager = ConnectionManager()
    with manager._lock:
        manager._connected = True
        manager._connection_type = connection_module.ConnectionType.USB
        manager._state.connected = True
        manager._state.connection_type = connection_module.ConnectionType.USB
        manager._state.battery_level = 65
        manager._state.charging_status = connection_module.ChargingStatus.CHARGING

    connections = []
    batteries = []
    manager.on_connect(connections.append)
    manager.on_battery_change(lambda level, status: batteries.append((level, status)))

    assert connections == [connection_module.ConnectionType.USB]
    assert batteries == [(65, connection_module.ChargingStatus.CHARGING)]


def test_registering_same_late_subscriber_twice_does_not_replay_twice():
    manager = ConnectionManager()
    with manager._lock:
        manager._connected = True
        manager._connection_type = connection_module.ConnectionType.BLUETOOTH
        manager._state.connected = True
        manager._state.connection_type = connection_module.ConnectionType.BLUETOOTH

    received = []
    callback = received.append
    manager.on_connect(callback)
    manager.on_connect(callback)

    assert received == [connection_module.ConnectionType.BLUETOOTH]
