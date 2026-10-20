from pathlib import Path


import src.trigger_engine as trigger_module
from src.game_profile_watcher import (
    MAX_GAME_PROFILE_RULES,
    MAX_LEGACY_GAME_MAPPINGS,
    GameProfileWatcher,
)
from src.input_studio import (
    MAX_CUSTOM_CURVE_POINTS,
    MAX_INPUT_PROFILES,
    InputStudioEngine,
)
from src.light_effects import MAX_CUSTOM_LIGHT_EFFECTS, LightEffectEngine
from src.trigger_engine import TriggerEffect, TriggerEffectType, TriggerEngine, WeaponProfile
from tests.gui_source_catalog import class_source


def _profile(name: str = "Perfil") -> WeaponProfile:
    off = TriggerEffect(name="Libre", effect_type=TriggerEffectType.OFF)
    return WeaponProfile(name=name, description="", left_trigger=off, right_trigger=off)


def test_input_studio_caps_curve_points_and_profile_count():
    points = [[index / 199, index / 199] for index in range(200)]
    config = InputStudioEngine.sanitize_config({"curve": "custom", "custom_curve": points})
    assert len(config["custom_curve"]) <= MAX_CUSTOM_CURVE_POINTS
    assert config["custom_curve"][0] == [0.0, 0.0]
    assert config["custom_curve"][-1] == [1.0, 1.0]

    engine = InputStudioEngine()
    engine.load_profiles({f"profile_{index}": {} for index in range(MAX_INPUT_PROFILES + 80)})
    assert len(engine.export_profiles()) == MAX_INPUT_PROFILES


def test_automatic_profile_rules_and_legacy_mapping_are_bounded():
    watcher = GameProfileWatcher()
    watcher.set_rules([
        {"executable": f"game_{index}.exe", "profile_id": "assault_rifle"}
        for index in range(MAX_GAME_PROFILE_RULES + 50)
    ])
    assert len(watcher.get_rules()) == MAX_GAME_PROFILE_RULES

    watcher.set_mapping({
        f"legacy_{index}.exe": "assault_rifle"
        for index in range(MAX_LEGACY_GAME_MAPPINGS + 50)
    })
    assert len(watcher.get_mapping()) == MAX_LEGACY_GAME_MAPPINGS


def test_custom_light_effect_library_is_bounded():
    engine = LightEffectEngine()
    engine.load_custom_effects({
        f"effect_{index}": {
            "name": "Ola",
            "palette": [[255, 0, 0], [0, 0, 255]],
            "speed": 1,
        }
        for index in range(MAX_CUSTOM_LIGHT_EFFECTS + 40)
    })
    assert len(engine.get_custom_effects()) == MAX_CUSTOM_LIGHT_EFFECTS


def test_trigger_payloads_are_clamped_and_sections_are_bounded():
    effect = TriggerEffect.from_dict({
        "name": "X" * 500,
        "effect_type": "not-real",
        "intensity": 9999,
        "start_position": -20,
        "end_position": 999,
        "frequency": -10,
        "animation_speed": 1e100,
        "animation_curve": "unknown",
        "custom_params": {"sections": [[index, 999] for index in range(50)]},
    })
    assert effect.effect_type is TriggerEffectType.OFF
    assert effect.intensity == 255
    assert effect.start_position == 0
    assert effect.end_position == 9
    assert effect.frequency == 0
    assert effect.animation_speed == 10.0
    assert effect.animation_curve == "linear"
    assert len(effect.custom_params["sections"]) == trigger_module.MAX_TRIGGER_SECTIONS
    assert all(0 <= position <= 9 and 0 <= strength <= 255 for position, strength in effect.custom_params["sections"])


def test_trigger_profile_library_refuses_new_entries_after_limit(monkeypatch):
    monkeypatch.setattr(trigger_module, "MAX_CUSTOM_TRIGGER_PROFILES", 2)
    engine = TriggerEngine()
    assert engine.add_custom_profile("one", _profile("Uno")) is True
    assert engine.add_custom_profile("two", _profile("Dos")) is True
    assert engine.add_custom_profile("three", _profile("Tres")) is False


def test_profile_images_are_probed_before_full_decode():
    source = Path(__file__).resolve().parents[1] / "src" / "profile_manager.py"
    text = source.read_text(encoding="utf-8")
    probe = text.index("with Image.open(source) as probe:")
    verify = text.index("probe.verify()", probe)
    decode = text.index("with Image.open(source) as opened:", verify)
    load = text.index("image.load()", decode)
    assert probe < verify < decode < load


def test_macro_import_and_profile_preview_do_not_use_unbounded_or_qt_file_decode():
    macro_source = class_source("MacrosPage")
    macro_start = macro_source.index("    def import_macros(")
    macro_block = macro_source[macro_start:]
    assert "read_json_file_limited(" in macro_block
    assert "json.load(" not in macro_block
    assert "MAX_LOADED_MACROS" in macro_block

    image_source = class_source("ProfileEditorDialog")
    image_start = image_source.index("    def choose_image(")
    image_end = image_source.index("    def clear_image(", image_start)
    image_block = image_source[image_start:image_end]
    assert "validate_profile_image" in image_block
    assert "ImageQt" in image_block
    assert "QPixmap(path)" not in image_block
