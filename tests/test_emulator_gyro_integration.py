import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import src.emulator as emulator_module
from src.emulator import EmulationMode, EmulatorManager


class Constants:
    pass


def constants(**values):
    obj = Constants()
    for key, value in values.items():
        setattr(obj, key, value)
    return obj


class FakeDS4:
    def __init__(self):
        self.report = SimpleNamespace(
            bThumbLX=128, bThumbLY=128, bThumbRX=128, bThumbRY=128,
            wButtons=0, bSpecial=0, bTriggerL=0, bTriggerR=0,
        )
        self.extended = None
        self.update_count = 0
        self.reset_count = 0

    def press_button(self, button):
        self.report.wButtons |= int(button)

    def release_button(self, button):
        self.report.wButtons &= ~int(button)

    def press_special_button(self, special_button):
        self.report.bSpecial |= int(special_button)

    def release_special_button(self, special_button):
        self.report.bSpecial &= ~int(special_button)

    def directional_pad(self, direction):
        self.report.wButtons = (self.report.wButtons & ~0x0F) | int(direction)

    def left_trigger(self, value): self.report.bTriggerL = value
    def right_trigger(self, value): self.report.bTriggerR = value
    def left_joystick(self, x_value, y_value):
        self.report.bThumbLX, self.report.bThumbLY = x_value, y_value
    def right_joystick(self, x_value, y_value):
        self.report.bThumbRX, self.report.bThumbRY = x_value, y_value
    def update_extended_report(self, report): self.extended = report
    def update(self): self.update_count += 1
    def reset(self):
        self.reset_count += 1
        self.report = SimpleNamespace(
            bThumbLX=128, bThumbLY=128, bThumbRX=128, bThumbRY=128,
            wButtons=0, bSpecial=0, bTriggerL=0, bTriggerR=0,
        )


class FakeXbox:
    def __init__(self):
        self.right = None
        self.update_count = 0
        self.reset_count = 0
    def press_button(self, button): pass
    def release_button(self, button): pass
    def left_trigger(self, value): pass
    def right_trigger(self, value): pass
    def left_joystick(self, x_value, y_value): pass
    def right_joystick(self, x_value, y_value): self.right = (x_value, y_value)
    def update(self): self.update_count += 1
    def reset(self):
        self.reset_count += 1
        self.right = (0, 0)


class FakeVG:
    VDS4Gamepad = FakeDS4
    VX360Gamepad = FakeXbox
    DS4_BUTTONS = constants(
        DS4_BUTTON_CROSS=0x20, DS4_BUTTON_CIRCLE=0x40, DS4_BUTTON_SQUARE=0x10,
        DS4_BUTTON_TRIANGLE=0x80, DS4_BUTTON_SHOULDER_LEFT=0x100,
        DS4_BUTTON_SHOULDER_RIGHT=0x200, DS4_BUTTON_TRIGGER_LEFT=0x400,
        DS4_BUTTON_TRIGGER_RIGHT=0x800, DS4_BUTTON_THUMB_LEFT=0x1000,
        DS4_BUTTON_THUMB_RIGHT=0x2000, DS4_BUTTON_OPTIONS=0x4000,
        DS4_BUTTON_SHARE=0x8000,
    )
    DS4_SPECIAL_BUTTONS = constants(DS4_SPECIAL_BUTTON_PS=1, DS4_SPECIAL_BUTTON_TOUCHPAD=2)
    DS4_DPAD_DIRECTIONS = constants(
        DS4_BUTTON_DPAD_NORTH=0, DS4_BUTTON_DPAD_NORTHEAST=1,
        DS4_BUTTON_DPAD_EAST=2, DS4_BUTTON_DPAD_SOUTHEAST=3,
        DS4_BUTTON_DPAD_SOUTH=4, DS4_BUTTON_DPAD_SOUTHWEST=5,
        DS4_BUTTON_DPAD_WEST=6, DS4_BUTTON_DPAD_NORTHWEST=7,
        DS4_BUTTON_DPAD_NONE=8,
    )
    XUSB_BUTTON = constants(
        XUSB_GAMEPAD_A=1, XUSB_GAMEPAD_B=2, XUSB_GAMEPAD_X=4, XUSB_GAMEPAD_Y=8,
        XUSB_GAMEPAD_LEFT_SHOULDER=16, XUSB_GAMEPAD_RIGHT_SHOULDER=32,
        XUSB_GAMEPAD_LEFT_THUMB=64, XUSB_GAMEPAD_RIGHT_THUMB=128,
        XUSB_GAMEPAD_START=256, XUSB_GAMEPAD_BACK=512,
        XUSB_GAMEPAD_DPAD_UP=1024, XUSB_GAMEPAD_DPAD_DOWN=2048,
        XUSB_GAMEPAD_DPAD_LEFT=4096, XUSB_GAMEPAD_DPAD_RIGHT=8192,
    )


def make_state(**changes):
    data = dict(
        buttons={"cross": True, "L3": True, "ps": True, "touchpad": True},
        left_trigger=25, right_trigger=50,
        left_stick_x=100, left_stick_y=110, right_stick_x=120, right_stick_y=130,
        gyro_pitch=111, gyro_yaw=-222, gyro_roll=333,
        accel_x=1000, accel_y=2000, accel_z=-3000,
        battery_level=60, charging_status=SimpleNamespace(value="descargando"),
        touchpad_active=True, touchpad_x=960, touchpad_y=471, touchpad_id=4,
    )
    data.update(changes)
    return SimpleNamespace(**data)


class EmulatorGyroIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.patches = [
            patch.object(emulator_module, 'vg', FakeVG),
            patch.object(emulator_module, 'VGAMEPAD_AVAILABLE', True),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()

    def test_ds4_extended_tick_preserves_normal_state(self):
        manager = EmulatorManager()
        # vgamepad 0.1.0 expone en Windows una vista estructurada con offsets
        # incorrectos para DS4_REPORT_EX. El buffer enviado a ViGEm sí usa los
        # 63 bytes empaquetados correctos; forzamos esa vista portable para que
        # la prueba valide el wire report y no la declaración defectuosa del SDK.
        manager._ds4_report_adapter._native_report_cls = None
        self.assertTrue(manager.set_mode(EmulationMode.PS4))
        manager.set_ds4_motion_passthrough(True)
        manager.update_from_dualsense(make_state())
        report = manager.gamepad.extended.Report
        self.assertEqual((report.bThumbLX, report.bThumbLY), (100, 110))
        self.assertEqual((report.bThumbRX, report.bThumbRY), (120, 130))
        self.assertEqual((report.bTriggerL, report.bTriggerR), (25, 50))
        self.assertTrue(report.wButtons & FakeVG.DS4_BUTTONS.DS4_BUTTON_CROSS)
        self.assertTrue(report.wButtons & FakeVG.DS4_BUTTONS.DS4_BUTTON_THUMB_LEFT)
        self.assertEqual((report.wGyroX, report.wGyroY, report.wGyroZ), (111, -222, 333))
        self.assertEqual((report.wAccelX, report.wAccelY, report.wAccelZ), (1000, 2000, -3000))
        self.assertEqual(manager.gamepad.update_count, 0)

    def test_stick_override_works_in_both_virtual_modes(self):
        manager = EmulatorManager()
        manager.set_right_stick_override(0.5, -0.25)
        manager.set_mode(EmulationMode.PS4)
        # set_mode intentionally clears stale output; apply current engine output again.
        manager.set_right_stick_override(0.5, -0.25)
        manager.update_from_dualsense(make_state(buttons={}))
        self.assertEqual((manager.gamepad.report.bThumbRX, manager.gamepad.report.bThumbRY), (192, 96))

        manager.set_mode(EmulationMode.XBOX)
        manager.set_right_stick_override(0.5, -0.25)
        manager.update_from_dualsense(make_state(buttons={}))
        self.assertEqual(manager.gamepad.right, (16384, 8192))
        self.assertEqual(manager.gamepad.update_count, 1)



    def test_macro_can_override_both_sticks_and_analog_triggers(self):
        manager = EmulatorManager()
        manager.set_mode(EmulationMode.PS4)
        manager.macro_set_stick("left", -1.0, 0.5)
        manager.macro_set_stick("right", 0.25, -0.75)
        manager.macro_set_trigger("left", 200)
        manager.macro_set_trigger("right", 90)
        manager.update_from_dualsense(make_state(buttons={}))
        self.assertEqual((manager.gamepad.report.bThumbLX, manager.gamepad.report.bThumbLY), (0, 192))
        self.assertEqual((manager.gamepad.report.bThumbRX, manager.gamepad.report.bThumbRY), (160, 32))
        self.assertEqual((manager.gamepad.report.bTriggerL, manager.gamepad.report.bTriggerR), (200, 90))

        manager.macro_clear_sticks()
        manager.macro_clear_triggers()
        manager.update_from_dualsense(make_state(buttons={}))
        self.assertEqual((manager.gamepad.report.bThumbLX, manager.gamepad.report.bThumbLY), (100, 110))
        self.assertEqual((manager.gamepad.report.bTriggerL, manager.gamepad.report.bTriggerR), (25, 50))

    def test_macro_analog_overrides_reject_non_finite_or_invalid_values(self):
        manager = EmulatorManager()

        manager.macro_set_stick("left", float("inf"), float("nan"))
        manager.macro_set_trigger("right", float("inf"))

        self.assertEqual(manager._macro_stick("left"), (0.0, 0.0))
        self.assertEqual(manager._macro_trigger("right", 77), 0)

        manager.macro_set_stick("right", "not-a-number", None)
        manager.macro_set_trigger("left", "not-a-number")

        self.assertEqual(manager._macro_stick("right"), (0.0, 0.0))
        self.assertEqual(manager._macro_trigger("left", 77), 0)

    def test_release_all_inputs_neutralizes_virtual_device(self):
        manager = EmulatorManager()
        manager.set_mode(EmulationMode.PS4)
        manager.update_from_dualsense(make_state())
        self.assertNotEqual(manager.gamepad.report.wButtons, 0)
        manager.set_right_stick_override(1.0, 1.0)
        manager.macro_press("circle")
        manager.release_all_inputs()
        self.assertEqual(manager.gamepad.report.wButtons, 0)
        self.assertEqual((manager.gamepad.report.bThumbRX, manager.gamepad.report.bThumbRY), (128, 128))
        self.assertEqual((manager.gamepad.report.bTriggerL, manager.gamepad.report.bTriggerR), (0, 0))
        self.assertEqual(manager.gamepad.reset_count, 1)
        self.assertEqual(manager.gamepad.update_count, 2)
        self.assertIsNone(manager._right_stick_override)
        self.assertEqual(manager._macro_overrides, set())
        self.assertEqual(manager._macro_stick_overrides, {})
        self.assertEqual(manager._macro_trigger_overrides, {})


if __name__ == '__main__':
    unittest.main()


def test_concurrent_macros_do_not_release_each_others_button_override():
    manager = EmulatorManager()
    first_pressed = threading.Event()
    second_pressed = threading.Event()
    release_first = threading.Event()
    release_second = threading.Event()

    def first_macro():
        manager.macro_press("cross")
        first_pressed.set()
        release_first.wait(1.0)
        manager.macro_release("cross")

    def second_macro():
        first_pressed.wait(1.0)
        manager.macro_press("cross")
        second_pressed.set()
        release_second.wait(1.0)
        manager.macro_release("cross")

    first = threading.Thread(target=first_macro)
    second = threading.Thread(target=second_macro)
    first.start()
    second.start()
    assert second_pressed.wait(1.0)
    assert "cross" in manager._macro_overrides

    release_first.set()
    first.join(1.0)
    assert "cross" in manager._macro_overrides

    release_second.set()
    second.join(1.0)
    assert "cross" not in manager._macro_overrides


def test_latest_concurrent_macro_analog_override_falls_back_to_previous_owner():
    manager = EmulatorManager()
    first_ready = threading.Event()
    second_ready = threading.Event()
    clear_second = threading.Event()
    clear_first = threading.Event()

    def first_macro():
        manager.macro_set_stick("right", 0.25, 0.5)
        manager.macro_set_trigger("right", 90)
        first_ready.set()
        clear_first.wait(1.0)
        manager.macro_clear_stick("right")
        manager.macro_clear_trigger("right")

    def second_macro():
        first_ready.wait(1.0)
        manager.macro_set_stick("right", -0.75, -0.5)
        manager.macro_set_trigger("right", 220)
        second_ready.set()
        clear_second.wait(1.0)
        manager.macro_clear_stick("right")
        manager.macro_clear_trigger("right")

    first = threading.Thread(target=first_macro)
    second = threading.Thread(target=second_macro)
    first.start()
    second.start()
    assert second_ready.wait(1.0)
    assert manager._macro_stick("right") == (-0.75, -0.5)
    assert manager._macro_trigger("right", 0) == 220

    clear_second.set()
    second.join(1.0)
    assert manager._macro_stick("right") == (0.25, 0.5)
    assert manager._macro_trigger("right", 0) == 90

    clear_first.set()
    first.join(1.0)
    assert manager._macro_stick("right") is None
    assert manager._macro_trigger("right", 33) == 33
