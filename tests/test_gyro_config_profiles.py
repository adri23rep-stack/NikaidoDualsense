import json
import tempfile
import unittest
from pathlib import Path

from src.gyro_config import GyroConfig
from src.profile_manager import ProfileManager
from src.trigger_engine import TriggerEffectType, TriggerEngine, WeaponProfile


class GyroConfigProfileTests(unittest.TestCase):
    def test_safe_defaults_for_old_profile(self):
        old = {
            "name": "Viejo",
            "description": "Perfil anterior al gyro",
            "left_trigger": {"name": "Off", "effect_type": "off"},
            "right_trigger": {"name": "Off", "effect_type": "off"},
        }
        profile = WeaponProfile.from_dict(old)
        self.assertIsInstance(profile.gyro_config, GyroConfig)
        self.assertFalse(profile.gyro_config.enabled)
        self.assertEqual(profile.gyro_config.mode, "disabled")
        self.assertEqual(profile.left_trigger.effect_type, TriggerEffectType.OFF)

    def test_gyro_roundtrip(self):
        cfg = GyroConfig.from_dict({
            "enabled": True,
            "mode": "right_stick",
            "sensitivity_x": 2.3,
            "activation": "toggle",
            "stick_mix_mode": "prioritize",
            "mouse_to_gyro_enabled": True,
            "mouse_to_gyro_sensitivity": 0.22,
            "mouse_to_gyro_invert_x": True,
            "mouse_to_gyro_combine_physical": True,
            "calibration": {"version": 3, "valid": True, "pitch_bias": 12, "yaw_bias": -8, "roll_bias": 3},
        })
        restored = GyroConfig.from_dict(cfg.to_dict())
        self.assertEqual(restored.to_dict(), cfg.to_dict())



    def test_old_sensor_calibration_is_loaded_but_not_marked_current(self):
        old = GyroConfig.from_dict({
            "calibration": {
                "version": 2, "valid": True,
                "pitch_bias": 100, "yaw_bias": -50, "roll_bias": 25,
            }
        })
        self.assertEqual(old.calibration.version, 2)
        self.assertTrue(old.calibration.valid)
        self.assertFalse(old.calibration.valid and old.calibration.version >= 3)

        current = GyroConfig.from_dict({
            "calibration": {
                "version": 3, "valid": True,
                "pitch_bias": 4, "yaw_bias": -3, "roll_bias": 2,
            }
        })
        self.assertTrue(current.calibration.valid and current.calibration.version >= 3)

    def test_weapon_profile_and_predefined_override_persist_gyro(self):
        cfg = GyroConfig.from_dict({
            "enabled": True, "mode": "mouse", "activation": "hold_l2",
            "calibration": {"pitch_bias": 10, "yaw_bias": -20, "roll_bias": 5},
        })
        old = {
            "name": "Personalizado", "description": "Con gyro",
            "left_trigger": {"name": "Off", "effect_type": "off"},
            "right_trigger": {"name": "Off", "effect_type": "off"},
            "gyro": cfg.to_dict(),
        }
        profile = WeaponProfile.from_dict(old)
        restored = WeaponProfile.from_dict(profile.to_dict())
        self.assertEqual(restored.gyro_config.to_dict(), cfg.to_dict())

        engine = TriggerEngine(None)
        self.assertTrue(engine.update_profile_gyro_config("assault_rifle", cfg))
        exported = engine.export_gyro_overrides()
        other = TriggerEngine(None)
        other.load_gyro_overrides(exported)
        self.assertEqual(other.get_profile_gyro_config("assault_rifle").to_dict(), cfg.to_dict())

    def test_profile_manager_merges_legacy_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "profiles.json"
            config_path.write_text(json.dumps({
                "version": "1.0",
                "active_profile": "assault_rifle",
                "settings": {"auto_connect": False},
            }), encoding="utf-8")
            manager = ProfileManager(tmp)
            self.assertFalse(manager.get_setting("auto_connect", True))
            self.assertEqual(manager.get_setting("profile_gyro", {}), {})
            self.assertIn("touchpad_mouse", manager._config["settings"])


if __name__ == "__main__":
    unittest.main()
