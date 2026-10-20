import json
import zipfile
from pathlib import Path

from PIL import Image

from src.profile_manager import ProfileManager
from src.trigger_engine import TriggerEngine


def test_nika_package_contains_profile_image_macros_and_lights(tmp_path):
    manager = ProfileManager(str(tmp_path / 'cfg'))
    engine = TriggerEngine()
    profile = engine.get_profile('sniper')
    image = tmp_path / 'cover.png'
    Image.new('RGB', (96, 64), (42, 76, 122)).save(image)
    profile.image_path = str(image)
    profile.light_config = {'effect': 'custom', 'custom_id': 'neon', 'palette': [[1,2,3]]}
    manager.set_setting('custom_light_effects', {'neon': {'name': 'Neon', 'palette': [[1,2,3]]}})
    manager.set_macros({'m1': {'id':'m1','name':'Combo','profile_ids':['sniper'],'steps':[]}})
    output = tmp_path / 'sniper.Nika'
    assert manager.export_profile('sniper', str(output), profile.to_dict())
    assert zipfile.is_zipfile(output)
    with zipfile.ZipFile(output) as z:
        assert {'manifest.json','profile.json','macros.json','light_effects.json'} <= set(z.namelist())
        assert json.loads(z.read('macros.json'))['m1']['name'] == 'Combo'
        assert json.loads(z.read('manifest.json'))['contents']['image'] is True

    imported_id = manager.import_profile(str(output))
    imported = manager.get_custom_profiles()[imported_id]
    assert Path(imported['image_path']).is_file()
    imported_macros = [m for m in manager.get_macros().values() if m.get('profile_ids') == [imported_id]]
    assert imported_macros and imported_macros[0]['name'] == 'Combo'


def test_nika_roundtrip_preserves_audio_profile_configuration(tmp_path):
    manager = ProfileManager(str(tmp_path / "cfg"))
    engine = TriggerEngine()
    profile = engine.get_profile("sniper")
    profile.audio_config = {
        "enabled": True,
        "button_enabled": True,
        "target_mode": "all_except_dualsense",
        "device_id": "{0.0.1.00000000}.headset-mic",
        "led_sync": False,
        "apply_volume": True,
        "volume": 43,
        "profile_mute_mode": "unmuted",
    }

    output = tmp_path / "sniper-audio.Nika"
    assert manager.export_profile("sniper", str(output), profile.to_dict())
    with zipfile.ZipFile(output) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        exported = json.loads(archive.read("profile.json"))
    assert manifest["contents"]["audio"] is True
    assert exported["audio_config"] == profile.audio_config

    imported_id = manager.import_profile(str(output))
    imported = manager.get_custom_profiles()[imported_id]
    assert imported["audio_config"] == profile.audio_config


def test_json_legacy_profile_still_imports(tmp_path):
    manager = ProfileManager(str(tmp_path / 'cfg'))
    old = tmp_path / 'old.json'
    old.write_text(json.dumps({'version':'2.0','profile': {'name':'Viejo','left_trigger':{},'right_trigger':{}}}), encoding='utf-8')
    assert manager.import_profile(str(old))


def test_import_does_not_overwrite_existing_custom_light_effect(tmp_path):
    manager = ProfileManager(str(tmp_path / "cfg"))
    manager.set_setting("custom_light_effects", {"neon": {"name": "Original", "palette": [[1, 2, 3], [4, 5, 6]]}})
    package = tmp_path / "collision.Nika"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("manifest.json", json.dumps({
            "format": "Nikaido Profile Package",
            "format_version": 1,
            "profile_id": "source",
        }))
        archive.writestr("profile.json", json.dumps({
            "name": "Importado",
            "light_config": {"effect": "custom", "custom_id": "neon"},
        }))
        archive.writestr("light_effects.json", json.dumps({
            "neon": {"name": "Importado", "palette": [[10, 20, 30], [40, 50, 60]]},
        }))

    imported_id = manager.import_profile(str(package))
    effects = manager.get_setting("custom_light_effects")
    imported = manager.get_custom_profiles()[imported_id]

    assert effects["neon"]["name"] == "Original"
    assert imported["light_config"]["custom_id"] != "neon"
    assert effects[imported["light_config"]["custom_id"]]["name"] == "Importado"


def test_nika_roundtrip_preserves_per_profile_advanced_mapping(tmp_path):
    manager = ProfileManager(str(tmp_path / "cfg"))
    engine = TriggerEngine()
    profile = engine.get_profile("sniper")
    profile.advanced_mapping_config = {
        "version": 2,
        "enabled": True,
        "default_layer": "base",
        "layers": {
            "base": {
                "touchpad": [
                    {
                        "action_type": "gyro",
                        "value": "recenter",
                        "activation": "double",
                        "exclusive_double": True,
                        "block_original": True,
                    }
                ]
            },
            "precision": {
                "cross": [
                    {
                        "action_type": "controller",
                        "value": "R1",
                        "activation": "hold",
                        "block_original": True,
                    }
                ]
            },
        },
    }

    output = tmp_path / "sniper-mapper.Nika"
    assert manager.export_profile("sniper", str(output), profile.to_dict())

    with zipfile.ZipFile(output) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        exported = json.loads(archive.read("profile.json"))
        assert manifest["format_version"] == 1
        assert manifest["contents"]["advanced_mapping"] is True
        assert exported["advanced_mapping"] == profile.advanced_mapping_config

    imported_id = manager.import_profile(str(output))
    imported = manager.get_custom_profiles()[imported_id]
    assert imported["advanced_mapping"] == profile.advanced_mapping_config


def test_nika_exports_macros_referenced_by_nexus_even_without_profile_assignment(tmp_path):
    manager = ProfileManager(str(tmp_path / "cfg"))
    engine = TriggerEngine()
    profile = engine.get_profile("sniper")
    profile.advanced_mapping_config = {
        "version": 2,
        "enabled": True,
        "default_layer": "base",
        "layers": {
            "base": {
                "cross": [
                    {
                        "action_type": "macro",
                        "value": "shared_combo",
                        "activation": "press",
                    }
                ]
            }
        },
    }
    manager.set_macros(
        {
            "shared_combo": {
                "id": "shared_combo",
                "name": "Combo compartido",
                "profile_ids": [],
                "steps": [],
            }
        }
    )

    output = tmp_path / "referenced.Nika"
    assert manager.export_profile("sniper", str(output), profile.to_dict())
    with zipfile.ZipFile(output) as archive:
        exported = json.loads(archive.read("macros.json"))
    assert "shared_combo" in exported


def test_nika_import_remaps_macro_and_self_profile_references(tmp_path):
    manager = ProfileManager(str(tmp_path / "cfg"))
    package = tmp_path / "references.Nika"
    profile = {
        "name": "Referencias",
        "advanced_mapping": {
            "version": 2,
            "enabled": True,
            "default_layer": "base",
            "layers": {
                "base": {
                    "cross": [{"action_type": "macro", "value": "old_macro"}],
                    "circle": [{"action_type": "profile", "value": "source_profile"}],
                }
            },
        },
    }
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "format": "Nikaido Profile Package",
                    "format_version": 1,
                    "profile_id": "source_profile",
                }
            ),
        )
        archive.writestr("profile.json", json.dumps(profile))
        archive.writestr(
            "macros.json",
            json.dumps({"old_macro": {"id": "old_macro", "name": "Vieja", "steps": []}}),
        )

    imported_id = manager.import_profile(str(package))
    assert imported_id
    imported = manager.get_custom_profiles()[imported_id]
    bindings = imported["advanced_mapping"]["layers"]["base"]
    new_macro_id = bindings["cross"][0]["value"]
    assert new_macro_id != "old_macro"
    assert manager.get_macros()[new_macro_id]["profile_ids"] == [imported_id]
    assert bindings["circle"][0]["value"] == imported_id


def test_invalid_embedded_image_does_not_leave_partial_profile(tmp_path):
    manager = ProfileManager(str(tmp_path / "cfg"))
    package = tmp_path / "bad-image.Nika"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "format": "Nikaido Profile Package",
                    "format_version": 1,
                    "profile_id": "source",
                    "image_file": "assets/profile.png",
                }
            ),
        )
        archive.writestr("profile.json", json.dumps({"name": "No parcial"}))
        archive.writestr("assets/profile.png", b"not-an-image")

    before = manager.get_custom_profiles()
    assert manager.import_profile(str(package)) is None
    assert manager.get_custom_profiles() == before
    assert not list(manager.profile_images_dir.glob("imported_no_parcial_*"))


def test_export_skips_invalid_legacy_profile_image(tmp_path):
    manager = ProfileManager(str(tmp_path / "cfg"))
    engine = TriggerEngine()
    profile = engine.get_profile("sniper")
    invalid = tmp_path / "broken.png"
    invalid.write_bytes(b"not-image")
    profile.image_path = str(invalid)

    output = tmp_path / "clean.Nika"
    assert manager.export_profile("sniper", str(output), profile.to_dict())
    with zipfile.ZipFile(output) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        exported = json.loads(archive.read("profile.json"))
    assert manifest["contents"]["image"] is False
    assert exported["image_path"] == ""


def test_import_normalizes_malformed_profile_and_custom_light_effects(tmp_path):
    manager = ProfileManager(str(tmp_path / "cfg"))
    package = tmp_path / "malformed-values.Nika"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("manifest.json", json.dumps({
            "format": "Nikaido Profile Package",
            "format_version": 1,
            "profile_id": "unsafe_source",
        }))
        archive.writestr("profile.json", json.dumps({
            "name": "Perfil roto",
            "rumble_intensity": 99_999,
            "left_trigger": {"intensity": -500, "start_position": 99},
            "right_trigger": "not-a-trigger",
            "gyro": {"sensitivity": 999, "deadzone": -20},
            "light_config": {
                "effect": "unknown-effect",
                "speed": 999,
                "brightness": -4,
                "custom_id": "valid_neon",
            },
            "input_studio": "not-a-dict",
            "advanced_mapping": {"layers": "not-a-dict"},
        }))
        archive.writestr("light_effects.json", json.dumps({
            "valid_neon": {
                "name": "N" * 200,
                "palette": [[-50, 20, 999], [10, 20, 30]],
                "speed": 900,
            },
            "invalid_single_color": {"palette": [[1, 2, 3]]},
        }))

    imported_id = manager.import_profile(str(package))

    assert imported_id
    imported = manager.get_custom_profiles()[imported_id]
    assert imported["rumble_intensity"] == 255
    assert imported["light_config"]["effect"] == "static"
    assert imported["light_config"]["speed"] == 8.0
    assert imported["light_config"]["brightness"] == 0.02
    assert isinstance(imported["input_studio"], dict)
    assert isinstance(imported["advanced_mapping"], dict)
    effects = manager.get_setting("custom_light_effects")
    assert effects["valid_neon"]["palette"] == [[0, 20, 255], [10, 20, 30]]
    assert effects["valid_neon"]["speed"] == 8.0
    assert len(effects["valid_neon"]["name"]) == 60
    assert "invalid_single_color" not in effects
