import unittest
from unittest.mock import patch
from types import SimpleNamespace

from src.emulator import EmulatorManager
from src.input_studio import InputStudioEngine, normalize_axis


class InputStudioEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = InputStudioEngine()
        self.engine.apply_profile('sniper')

    def test_axis_normalization_keeps_hid_endpoints_exact(self):
        self.assertEqual(normalize_axis(0), -1.0)
        self.assertEqual(normalize_axis(128), 0.0)
        self.assertEqual(normalize_axis(255), 1.0)

    def test_radial_deadzone_outer_range_and_antideadzone(self):
        self.engine.update_config(
            'sniper', 'right', inner_deadzone=0.20, outer_deadzone=0.10,
            anti_deadzone=0.10, curve='linear', drift_correction=False,
        )
        self.assertEqual(self.engine.process_stick('right', 150, 128), (0.0, 0.0))
        x, y = self.engine.process_stick('right', 191, 128)
        self.assertAlmostEqual(y, 0.0, places=6)
        # (63/127 - .20) / .70, con anti-deadzone 10%.
        self.assertAlmostEqual(x, 0.4809, places=3)

    def test_custom_curve_and_axis_sensitivity_are_applied(self):
        self.engine.update_config(
            'sniper', 'left', inner_deadzone=0, outer_deadzone=0,
            anti_deadzone=0, curve='custom',
            custom_curve=[[0, 0], [0.5, 0.2], [1, 1]],
            sensitivity_x=1.5, sensitivity_y=1.0, drift_correction=False,
        )
        # Entrada 0.5 -> curva 0.2 -> sensibilidad X 1.5 = 0.3.
        output_x, output_y = self.engine.process_stick('left', 191.5, 128)
        self.assertAlmostEqual(output_x, 0.3, places=2)
        self.assertAlmostEqual(output_y, 0.0, places=6)

    def test_telemetry_is_separate_for_both_sticks(self):
        self.engine.update_config('sniper', 'left', inner_deadzone=0, drift_correction=False)
        self.engine.update_config('sniper', 'right', inner_deadzone=0, drift_correction=False)
        self.engine.process_stick('left', 255, 128)
        self.engine.process_stick('right', 128, 0)

        left = self.engine.get_telemetry('left')
        right = self.engine.get_telemetry('right')
        self.assertAlmostEqual(left['physical_x'], 1.0)
        self.assertAlmostEqual(left['physical_y'], 0.0)
        self.assertAlmostEqual(right['physical_x'], 0.0)
        self.assertAlmostEqual(right['physical_y'], -1.0)
        self.assertNotEqual((left['output_x'], left['output_y']), (right['output_x'], right['output_y']))

    def test_drift_calibration_is_per_profile_and_can_be_inverted(self):
        self.engine.begin_drift_calibration('sniper', 'right', samples=12)
        for _ in range(12):
            self.engine.process_stick('right', 134, 124)
        calibration = self.engine.get_drift_calibration('right')
        self.assertTrue(calibration['completed'])
        self.assertEqual(calibration['progress'], 1.0)
        self.engine.update_config('sniper', 'right', inner_deadzone=0, invert_x=True)
        self.assertEqual(self.engine.process_stick('right', 134, 124), (0.0, 0.0))
        output_x, output_y = self.engine.process_stick('right', 160, 124)
        self.assertLess(output_x, 0.0)
        self.assertAlmostEqual(output_y, 0.0, places=6)

    def test_reset_clears_stale_drift_calibration_state(self):
        self.engine.begin_drift_calibration('sniper', 'left', samples=12)
        for _ in range(12):
            self.engine.process_stick('left', 132, 126)
        self.assertTrue(self.engine.get_drift_calibration('left')['completed'])

        self.engine.reset_stick('sniper', 'left')
        calibration = self.engine.get_drift_calibration('left')
        self.assertFalse(calibration['active'])
        self.assertFalse(calibration['completed'])

    def test_export_is_copy_safe_and_profiles_are_separate(self):
        self.engine.update_config('sniper', 'right', sensitivity_x=1.75)
        self.engine.apply_profile('assault_rifle')
        self.assertEqual(self.engine.get_config('assault_rifle', 'right')['sensitivity_x'], 1.0)
        exported = self.engine.export_profiles()
        exported['sniper']['right']['sensitivity_x'] = 0.1
        self.assertEqual(self.engine.get_config('sniper', 'right')['sensitivity_x'], 1.75)


    def test_hot_path_reuses_validated_profile_without_rebuilding_defaults(self):
        # El perfil ya existe; procesar a 120 Hz no debe clonar ni volver a
        # sanear toda la configuración en cada lectura.
        self.engine.update_config('sniper', 'right', inner_deadzone=0, drift_correction=False)
        with patch.object(self.engine, '_default_profile', side_effect=AssertionError('hot path lento')):
            self.assertEqual(self.engine.process_stick('right', 128, 128), (0.0, 0.0))

    def test_emulator_uses_processed_input_for_virtual_preview(self):
        self.engine.update_config(
            'sniper', 'right', inner_deadzone=0.25, outer_deadzone=0,
            anti_deadzone=0, drift_correction=False,
        )
        emulator = EmulatorManager()
        emulator.set_input_processor(self.engine)
        state = SimpleNamespace(
            left_stick_x=255, left_stick_y=128,
            right_stick_x=148, right_stick_y=128,
        )
        emulator.update_from_dualsense(state)
        self.assertAlmostEqual(emulator.get_virtual_stick_output('left')[0], 1.0)
        self.assertEqual(emulator.get_virtual_stick_output('right'), (0.0, 0.0))


if __name__ == '__main__':
    unittest.main()
