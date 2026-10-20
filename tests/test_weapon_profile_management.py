import json
import tempfile
import unittest
from pathlib import Path

from src.input_studio import InputStudioEngine
from src.profile_manager import ProfileManager
from src.trigger_engine import TriggerEngine, WeaponProfile


class WeaponProfileManagementTests(unittest.TestCase):
    def test_only_custom_profiles_can_be_deleted_and_are_exported_separately(self):
        engine = TriggerEngine(None)
        template = engine.get_profile('sniper')
        custom = WeaponProfile.from_dict(template.to_dict())
        custom.name = 'Mi sniper'

        self.assertTrue(engine.add_custom_profile('custom_mi_sniper', custom))
        self.assertTrue(engine.is_custom_profile('custom_mi_sniper'))
        self.assertIn('custom_mi_sniper', engine.export_custom_profiles_to_dict())

        self.assertFalse(engine.remove_profile('sniper'))
        self.assertIsNotNone(engine.get_profile('sniper'))
        self.assertTrue(engine.remove_profile('custom_mi_sniper'))
        self.assertNotIn('custom_mi_sniper', engine.get_all_profiles())

    def test_loading_custom_profiles_cannot_override_an_included_profile(self):
        engine = TriggerEngine(None)
        original_name = engine.get_profile('sniper').name
        engine.load_profiles_from_dict({
            'sniper': {'name': 'No debe reemplazar'},
            'custom_imported': {
                'name': 'Importado',
                'description': 'Perfil de prueba',
                'left_trigger': {'name': 'Off', 'effect_type': 'off'},
                'right_trigger': {'name': 'Off', 'effect_type': 'off'},
            },
        })

        self.assertEqual(engine.get_profile('sniper').name, original_name)
        self.assertTrue(engine.is_custom_profile('custom_imported'))
        self.assertEqual(engine.get_profile('custom_imported').name, 'Importado')

    def test_export_can_include_an_included_profile_from_the_engine(self):
        engine = TriggerEngine(None)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'sniper.json'
            manager = ProfileManager(tmp)
            self.assertTrue(
                manager.export_profile('sniper', str(target), engine.get_profile('sniper').to_dict())
            )
            exported = json.loads(target.read_text(encoding='utf-8'))

        self.assertEqual(exported['profile']['name'], engine.get_profile('sniper').name)
        self.assertIn('left_trigger', exported['profile'])

    def test_removing_input_studio_profile_clears_its_saved_settings(self):
        studio = InputStudioEngine()
        studio.apply_profile('custom_test')
        studio.update_config('custom_test', 'left', sensitivity_x=1.8)
        self.assertIn('custom_test', studio.export_profiles())

        self.assertTrue(studio.remove_profile('custom_test'))
        self.assertNotIn('custom_test', studio.export_profiles())
        self.assertEqual(studio.get_active_profile(), 'assault_rifle')


if __name__ == '__main__':
    unittest.main()
