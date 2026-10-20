import json
from pathlib import Path

from PIL import Image

from src.profile_catalog import (
    BUILTIN_PROFILE_SPECS,
    LEGACY_PROFILE_ALIASES,
    PROFILE_CATALOG_REVISION,
    VISIBLE_BUILTIN_PROFILE_IDS,
    ordered_builtin_ids,
)
from src.profile_manager import ProfileManager
from src.trigger_engine import TriggerEngine, WeaponProfile


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets" / "profile_library"
GALLERY_SOURCE = (ROOT / "gui" / "profile_gallery.py").read_text(encoding="utf-8")
PAGE_SOURCE = (ROOT / "gui" / "pages" / "profiles.py").read_text(encoding="utf-8")
GENERATOR_SOURCE = (ROOT / "tools" / "generate_profile_library_assets.py").read_text(
    encoding="utf-8"
)
BUILD_SOURCE = (ROOT / "build.py").read_text(encoding="utf-8")


def test_catalog_has_eight_unique_profiles_in_the_approved_order():
    assert ordered_builtin_ids() == VISIBLE_BUILTIN_PROFILE_IDS
    assert len(BUILTIN_PROFILE_SPECS) == 8
    assert len(set(VISIBLE_BUILTIN_PROFILE_IDS)) == 8
    assert [item.name for item in BUILTIN_PROFILE_SPECS] == [
        "Call of Duty: Warzone",
        "Forza Horizon 5",
        "Resident Evil 4",
        "Elden Ring",
        "EA Sports FC",
        "Street Fighter 6",
        "Minecraft",
        "Ghost of Tsushima",
    ]
    assert [item.presentation.sort_order for item in BUILTIN_PROFILE_SPECS] == list(
        range(10, 90, 10)
    )


def test_original_profile_art_is_present_small_and_decodable():
    expected = {Path(item.presentation.cover_asset).name for item in BUILTIN_PROFILE_SPECS}
    assert {path.name for path in ASSET_DIR.glob("*.png")} == expected
    for filename in expected:
        path = ASSET_DIR / filename
        assert 10_000 < path.stat().st_size < 400_000
        with Image.open(path) as image:
            assert image.format == "PNG"
            assert image.size == (1200, 520)
            image.verify()


def test_asset_generator_is_offline_and_uses_no_external_artwork():
    lowered = GENERATOR_SOURCE.lower()
    assert "no descarga imágenes" in lowered
    assert "requests" not in lowered
    assert "urllib" not in lowered
    assert "http://" not in lowered
    assert "https://" not in lowered
    assert "image.open(" not in lowered
    assert set(path.name for path in ASSET_DIR.glob("*.png")) == {
        "warzone.png",
        "forza_horizon_5.png",
        "resident_evil_4.png",
        "elden_ring.png",
        "ea_sports_fc.png",
        "street_fighter_6.png",
        "minecraft.png",
        "ghost_of_tsushima.png",
    }


def test_gallery_has_no_continuous_card_animation_or_network_loading():
    assert "QTimer(" not in GALLERY_SOURCE
    assert "requests" not in GALLERY_SOURCE
    assert "urllib" not in GALLERY_SOURCE
    assert "fetch(" not in GALLERY_SOURCE
    assert "ProfileCoverWidget" in GALLERY_SOURCE
    assert "_pixmap_cache" in GALLERY_SOURCE
    assert "_filter_timer.setInterval(180)" in PAGE_SOURCE
    assert "_responsive_timer.setInterval(120)" in PAGE_SOURCE


def test_old_profile_ids_migrate_without_losing_user_owned_settings(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    old_config = {
        "active_profile": "sniper",
        "favorites": ["sniper", "smg", "bow", "sniper"],
        "game_profiles": {"game.exe": "smg"},
        "macros": {
            "m1": {"id": "m1", "profile_ids": ["sniper", "smg", "bow"]},
        },
        "settings": {
            "profile_library": {"revision": 0},
            "game_profile_rules": [
                {"id": "rule", "profile_id": "sniper", "executable": "game.exe"}
            ],
            "profile_input_studio": {
                "sniper": {"right": {"curve": "aggressive", "inner_deadzone": 0.04}},
            },
            "profile_overrides": {
                "sniper": {
                    "name": "Nombre viejo",
                    "left_trigger": {"effect_type": "off"},
                    "image_path": "saved/profile.png",
                    "input_studio": {"right": {"curve": "aggressive"}},
                    "advanced_mapping": {"layers": {"base": {}}},
                    "audio_config": {"profile_mute_mode": "muted"},
                },
                "mi_perfil": {
                    "name": "Mi perfil",
                    "left_trigger": {"effect_type": "rigid"},
                },
            },
        },
    }
    (config_dir / "profiles.json").write_text(json.dumps(old_config), encoding="utf-8")

    manager = ProfileManager(str(config_dir))

    assert manager.get_active_profile() == "assault_rifle"
    assert manager.get_favorites() == ["assault_rifle", "bow"]
    assert manager.get_game_profiles() == {"game.exe": "assault_rifle"}
    assert manager.get_macros()["m1"]["profile_ids"] == ["assault_rifle", "bow"]
    assert manager.get_setting("game_profile_rules")[0]["profile_id"] == "assault_rifle"
    assert manager.get_setting("profile_library.revision") == PROFILE_CATALOG_REVISION

    overrides = manager.get_setting("profile_overrides")
    assert overrides["assault_rifle"] == {
        "image_path": "saved/profile.png",
        "input_studio": {"right": {"curve": "aggressive"}},
        "advanced_mapping": {"layers": {"base": {}}},
        "audio_config": {"profile_mute_mode": "muted"},
    }
    assert overrides["mi_perfil"]["name"] == "Mi perfil"
    assert "left_trigger" not in overrides["assault_rifle"]


def test_builtin_restore_and_legacy_aliases_do_not_duplicate_profiles():
    engine = TriggerEngine()
    original = engine.get_profile("assault_rifle").to_dict()
    edited = WeaponProfile.from_dict(original)
    edited.name = "Editado"
    edited.light_config = {"effect": "static", "color": [255, 255, 255]}
    assert engine.update_profile("sniper", edited)
    assert engine.get_profile("assault_rifle").name == "Editado"
    assert engine.reset_builtin_profile("sniper")
    assert engine.get_profile("assault_rifle").to_dict() == original
    assert set(engine.get_all_profiles()) == set(VISIBLE_BUILTIN_PROFILE_IDS)
    assert not set(LEGACY_PROFILE_ALIASES).intersection(engine.get_all_profiles())


def test_profile_override_loading_sanitizes_untrusted_values():
    engine = TriggerEngine()
    engine.load_profile_overrides(
        {
            "assault_rifle": {
                "name": "X" * 500,
                "category": "Y" * 500,
                "origin": "unknown-origin",
                "tags": ["Uno", "Uno", "Dos"],
                "rumble_intensity": 9999,
                "image_path": "Z" * 5000,
                "light_config": {
                    "effect": "not-real",
                    "color": [-80, 900, "bad"],
                    "brightness": 999,
                },
                "input_studio": {
                    "left": {"inner_deadzone": -9, "sensitivity_x": 999},
                    "right": {"curve": "not-real"},
                },
                "advanced_mapping": {"layers": "bad"},
            }
        }
    )
    profile = engine.get_profile("assault_rifle")
    assert len(profile.name) == 120
    assert len(profile.category) == 80
    assert profile.origin == "builtin"
    assert profile.tags == ["Uno", "Dos"]
    assert profile.rumble_intensity == 255
    assert len(profile.image_path) == 2048
    assert profile.light_config["effect"] == "static"
    assert 0.0 <= profile.light_config["brightness"] <= 1.0
    assert set(profile.input_studio_config) == {"left", "right"}
    assert isinstance(profile.advanced_mapping_config, dict)


def test_profile_metadata_roundtrips_for_custom_and_imported_profiles():
    engine = TriggerEngine()
    source = WeaponProfile.from_dict(engine.get_profile("bow").to_dict())
    source.tags = ["Aventura", "Arco"]
    source.origin = "imported"
    source.created_at = "2026-07-18T12:00:00+00:00"
    source.updated_at = "2026-07-18T13:00:00+00:00"
    restored = WeaponProfile.from_dict(source.to_dict())
    assert restored.tags == source.tags
    assert restored.origin == "imported"
    assert restored.created_at == source.created_at
    assert restored.updated_at == source.updated_at


def test_build_pipeline_includes_catalog_gallery_editor_and_visuals():
    for module in (
        "src.profile_catalog",
        "gui.profile_gallery",
        "gui.profile_editor",
        "gui.profile_visuals",
    ):
        assert module in BUILD_SOURCE
