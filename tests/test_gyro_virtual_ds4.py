import ctypes
import unittest
from types import SimpleNamespace

from src.gyro_virtual_ds4 import DS4ExtendedReportAdapter, _FallbackDS4ReportEx


class Charging:
    value = "cargando"


class FakeGamepad:
    def __init__(self):
        self.report = SimpleNamespace(
            bThumbLX=10, bThumbLY=20, bThumbRX=30, bThumbRY=40,
            wButtons=0xBEEF, bSpecial=3, bTriggerL=55, bTriggerR=66,
        )
        self.extended = None

    def update_extended_report(self, report):
        self.extended = report


class DS4ExtendedReportTests(unittest.TestCase):
    def setUp(self):
        self.adapter = DS4ExtendedReportAdapter()
        # Fuerza la estructura portable para que el test no dependa de Windows.
        self.adapter._native_report_cls = None
        # Las pruebas de empaquetado validan fidelidad exacta, no el centrado.
        self.adapter.set_motion_transform(deadzone=0)
        self.adapter.set_gyro_bias((0, 0, 0), trusted=True)

    def test_report_preserves_base_and_adds_motion(self):
        state = SimpleNamespace(
            gyro_pitch=100, gyro_yaw=-200, gyro_roll=300,
            accel_x=1000, accel_y=-2000, accel_z=3000,
            battery_level=70, charging_status=Charging(),
            touchpad_active=True, touchpad_x=1234, touchpad_y=567, touchpad_id=9,
        )
        packet = self.adapter.make_packet(state, gyro_signs=(-1, 1, -1), accel_signs=(1, -1, 1))
        base = SimpleNamespace(
            bThumbLX=10, bThumbLY=20, bThumbRX=30, bThumbRY=40,
            wButtons=0xBEEF, bSpecial=3, bTriggerL=55, bTriggerR=66,
        )
        ex = self.adapter.build_report(base, packet).Report
        self.assertEqual((ex.bThumbLX, ex.bThumbLY, ex.bThumbRX, ex.bThumbRY), (10, 20, 30, 40))
        self.assertEqual(ex.wButtons, 0xBEEF)
        self.assertEqual((ex.bTriggerL, ex.bTriggerR), (55, 66))
        self.assertEqual((ex.wGyroX, ex.wGyroY, ex.wGyroZ), (-100, -200, -300))
        self.assertEqual((ex.wAccelX, ex.wAccelY, ex.wAccelZ), (1000, 2000, 3000))
        self.assertEqual(ex.bBatteryLvlSpecial & 0x10, 0x10)
        self.assertEqual(ex.sCurrentTouch.bIsUpTrackingNum1 & 0x80, 0)
        self.assertEqual(ctypes.sizeof(_FallbackDS4ReportEx), 63)


    def test_signed_vgamepad_bytes_are_reinterpreted_not_clamped(self):
        state = SimpleNamespace(
            gyro_pitch=0, gyro_yaw=0, gyro_roll=0,
            accel_x=0, accel_y=0, accel_z=0,
            battery_level=50, charging_status=SimpleNamespace(value="descargando"),
            touchpad_active=False, touchpad_x=0, touchpad_y=0, touchpad_id=0,
        )
        # Valores observados desde ctypes.c_byte para 200, 255, 128, etc.
        base = SimpleNamespace(
            bThumbLX=-56, bThumbLY=-1, bThumbRX=-128, bThumbRY=127,
            wButtons=0x4321, bSpecial=2, bTriggerL=-36, bTriggerR=-6,
        )
        report = self.adapter.build_report(base, self.adapter.make_packet(state)).Report
        self.assertEqual((report.bThumbLX, report.bThumbLY, report.bThumbRX, report.bThumbRY),
                         (200, 255, 128, 127))
        self.assertEqual((report.bTriggerL, report.bTriggerR), (220, 250))


    def test_native_vgamepad_wrapper_keeps_packed_wire_offsets(self):
        class BrokenNativeReport(ctypes.Union):
            # Simula una declaracion de vgamepad cuyo miembro estructurado es
            # mayor a 63 bytes, pero conserva ReportBuffer al inicio.
            _fields_ = [("ReportBuffer", ctypes.c_ubyte * 63),
                        ("oversized_member", ctypes.c_ubyte * 72)]

        self.adapter._native_report_cls = BrokenNativeReport
        state = SimpleNamespace(
            gyro_pitch=0x1234, gyro_yaw=-321, gyro_roll=654,
            accel_x=111, accel_y=222, accel_z=-333,
            battery_level=80, charging_status=SimpleNamespace(value="descargando"),
            touchpad_active=True, touchpad_x=900, touchpad_y=400, touchpad_id=4,
        )
        packet = self.adapter.make_packet(state)
        base = SimpleNamespace(
            bThumbLX=1, bThumbLY=2, bThumbRX=3, bThumbRY=4,
            wButtons=0xA55A, bSpecial=2, bTriggerL=77, bTriggerR=88,
        )
        native = self.adapter.build_report(base, packet)
        self.assertIsInstance(native, BrokenNativeReport)

        packed = _FallbackDS4ReportEx()
        ctypes.memmove(ctypes.addressof(packed), ctypes.addressof(native), 63)
        report = packed.Report
        self.assertEqual(report.wButtons, 0xA55A)
        self.assertEqual(report.wTimestamp, packet.timestamp)
        self.assertEqual((report.wGyroX, report.wGyroY, report.wGyroZ), packet.gyro)
        self.assertEqual((report.wAccelX, report.wAccelY, report.wAccelZ), packet.accel)
        self.assertEqual(report.sCurrentTouch.bIsUpTrackingNum1 & 0x80, 0)

    def test_direct_extended_update_path(self):
        gamepad = FakeGamepad()
        state = SimpleNamespace(
            gyro_pitch=10, gyro_yaw=20, gyro_roll=30,
            accel_x=4, accel_y=5, accel_z=6,
            battery_level=50, charging_status=SimpleNamespace(value="descargando"),
            touchpad_active=False, touchpad_x=0, touchpad_y=0, touchpad_id=0,
        )
        self.assertTrue(self.adapter.update(gamepad, state))
        self.assertIsNotNone(gamepad.extended)
        self.assertEqual(gamepad.extended.Report.wButtons, 0xBEEF)
        self.assertEqual(gamepad.extended.Report.wGyroY, 20)


if __name__ == "__main__":
    unittest.main()


def test_passthrough_uses_profile_bias_and_auto_centers_stationary_sensor():
    adapter = DS4ExtendedReportAdapter()
    adapter._native_report_cls = None
    adapter.set_gyro_bias((10, -20, 30))
    calibrated = SimpleNamespace(
        gyro_pitch=30, gyro_yaw=5, gyro_roll=45,
        accel_x=0, accel_y=0, accel_z=0,
        battery_level=50, charging_status=SimpleNamespace(value="descargando"),
        touchpad_active=False, touchpad_x=0, touchpad_y=0, touchpad_id=0,
    )
    packet = adapter.make_packet(calibrated)
    assert packet.gyro == (20, 25, 15)

    adapter.set_gyro_bias((0, 0, 0))
    adapter.reset()
    stationary = SimpleNamespace(
        gyro_pitch=8, gyro_yaw=-10, gyro_roll=4,
        accel_x=0, accel_y=0, accel_z=0,
        battery_level=50, charging_status=SimpleNamespace(value="descargando"),
        touchpad_active=False, touchpad_x=0, touchpad_y=0, touchpad_id=0,
    )
    packet = None
    for _ in range(60):
        packet = adapter.make_packet(stationary)
    assert packet is not None
    assert packet.gyro == (0, 0, 0)

    moving = SimpleNamespace(**vars(stationary))
    moving.gyro_yaw = 190
    assert adapter.make_packet(moving).gyro == (0, 200, 0)


def test_passthrough_does_not_emit_opposite_drift_after_bad_startup_center():
    adapter = DS4ExtendedReportAdapter()
    adapter._native_report_cls = None
    adapter.reset()

    def state(yaw):
        return SimpleNamespace(
            gyro_pitch=0, gyro_yaw=yaw, gyro_roll=0,
            accel_x=0, accel_y=0, accel_z=0,
            battery_level=50, charging_status=SimpleNamespace(value="descargando"),
            touchpad_active=False, touchpad_x=0, touchpad_y=0, touchpad_id=0,
        )

    # Simula activar passthrough mientras el usuario todavía mueve el mando.
    for _ in range(60):
        adapter.make_packet(state(70))

    # Al soltarlo, el hotfix anterior enviaba -70 durante varias décimas.
    # Debe quedar neutral desde el primer reporte y corregir el centro después.
    assert adapter.make_packet(state(0)).gyro == (0, 0, 0)
    packet = None
    for _ in range(60):
        packet = adapter.make_packet(state(0))
    assert packet is not None
    assert packet.gyro == (0, 0, 0)


def test_passthrough_does_not_learn_a_sustained_real_turn_as_thermal_drift():
    adapter = DS4ExtendedReportAdapter()
    adapter._native_report_cls = None
    adapter.reset()

    resting = SimpleNamespace(
        gyro_pitch=8, gyro_yaw=-10, gyro_roll=4,
        accel_x=0, accel_y=0, accel_z=0,
        battery_level=50, charging_status=SimpleNamespace(value="descargando"),
        touchpad_active=False, touchpad_x=0, touchpad_y=0, touchpad_id=0,
    )
    for _ in range(60):
        adapter.make_packet(resting)

    turning = SimpleNamespace(**vars(resting))
    turning.gyro_yaw = 70
    first = adapter.make_packet(turning).gyro[1]
    last = first
    for _ in range(240):
        last = adapter.make_packet(turning).gyro[1]
    assert first >= 70
    assert last >= 70


def test_passthrough_keeps_axes_isolated_after_startup_center():
    adapter = DS4ExtendedReportAdapter()
    adapter._native_report_cls = None
    adapter.reset()

    resting = SimpleNamespace(
        gyro_pitch=8, gyro_yaw=-10, gyro_roll=4,
        accel_x=0, accel_y=0, accel_z=8192,
        battery_level=50, charging_status=SimpleNamespace(value="descargando"),
        touchpad_active=False, touchpad_x=0, touchpad_y=0, touchpad_id=0,
    )
    for _ in range(60):
        adapter.make_packet(resting)

    pitch_motion = SimpleNamespace(**vars(resting))
    pitch_motion.gyro_pitch = 408
    pitch_motion.gyro_yaw = -5  # fuga mínima del sensor / mano
    pitch_motion.gyro_roll = 8
    packet = adapter.make_packet(pitch_motion)
    # No se inventan ejes: conserva el pitch y solo las fugas físicas reales.
    assert packet.gyro == (400, 5, 4)


def test_passthrough_does_not_center_while_accelerometer_detects_tilt():
    adapter = DS4ExtendedReportAdapter()
    adapter._native_report_cls = None
    adapter.reset()

    for index in range(60):
        moving = SimpleNamespace(
            gyro_pitch=35, gyro_yaw=0, gyro_roll=0,
            accel_x=index * 40, accel_y=0, accel_z=8192,
            battery_level=50, charging_status=SimpleNamespace(value="descargando"),
            touchpad_active=False, touchpad_x=0, touchpad_y=0, touchpad_id=0,
        )
        adapter.make_packet(moving)

    released = SimpleNamespace(
        gyro_pitch=0, gyro_yaw=0, gyro_roll=0,
        accel_x=0, accel_y=0, accel_z=8192,
        battery_level=50, charging_status=SimpleNamespace(value="descargando"),
        touchpad_active=False, touchpad_x=0, touchpad_y=0, touchpad_id=0,
    )
    assert adapter.make_packet(released).gyro == (0, 0, 0)


def test_profile_calibration_is_never_relearned_by_passthrough():
    adapter = DS4ExtendedReportAdapter()
    adapter._native_report_cls = None
    adapter.set_gyro_bias((10, -20, 30))
    adapter.reset()

    state = SimpleNamespace(
        gyro_pitch=110, gyro_yaw=-20, gyro_roll=30,
        accel_x=0, accel_y=0, accel_z=8192,
        battery_level=50, charging_status=SimpleNamespace(value="descargando"),
        touchpad_active=False, touchpad_x=0, touchpad_y=0, touchpad_id=0,
    )
    first = adapter.make_packet(state).gyro
    last = first
    for _ in range(240):
        last = adapter.make_packet(state).gyro
    assert first == (100, 0, 0)
    assert last == first


def test_passthrough_axis_permutation_and_signs_are_explicit():
    adapter = DS4ExtendedReportAdapter()
    adapter._native_report_cls = None
    adapter.set_motion_transform(gyro_axes=(1, 0, 2), accel_axes=(2, 1, 0), deadzone=0)
    adapter.set_gyro_bias((0, 0, 0), trusted=True)
    state = SimpleNamespace(
        gyro_pitch=100, gyro_yaw=200, gyro_roll=300,
        accel_x=1000, accel_y=2000, accel_z=3000,
        battery_level=50, charging_status=SimpleNamespace(value="descargando"),
        touchpad_active=False, touchpad_x=0, touchpad_y=0, touchpad_id=0,
    )
    packet = adapter.make_packet(
        state,
        gyro_signs=(-1, 1, -1),
        accel_signs=(1, -1, 1),
    )
    assert packet.gyro == (-200, 100, -300)
    assert packet.accel == (3000, -2000, 1000)


def test_mouse_gyro_can_replace_or_combine_physical_vector():
    adapter = DS4ExtendedReportAdapter()
    adapter._native_report_cls = None
    adapter.set_motion_transform(deadzone=0)
    adapter.set_gyro_bias((0, 0, 0), trusted=True)
    state = SimpleNamespace(
        gyro_pitch=10, gyro_yaw=20, gyro_roll=30,
        accel_x=0, accel_y=0, accel_z=8192,
        battery_level=50, charging_status=SimpleNamespace(value="descargando"),
        touchpad_active=False, touchpad_x=0, touchpad_y=0, touchpad_id=0,
    )
    assert adapter.make_packet(
        state, synthetic_gyro=(100, 200, 0), replace_physical=True
    ).gyro == (100, 200, 0)
    assert adapter.make_packet(
        state, synthetic_gyro=(100, 200, 0), replace_physical=False
    ).gyro == (110, 220, 30)
