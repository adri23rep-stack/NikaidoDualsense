from pathlib import Path

from src.profile_catalog import LEGACY_PROFILE_ALIASES, ordered_builtin_ids
from src.trigger_engine import TriggerEffectType, TriggerEngine


ROOT = Path(__file__).resolve().parents[1]
PROFILES_UI = (ROOT / "gui" / "pages" / "profiles.py").read_text(encoding="utf-8")
EDITOR_UI = (ROOT / "gui" / "profile_editor.py").read_text(encoding="utf-8")
GALLERY_UI = (ROOT / "gui" / "profile_gallery.py").read_text(encoding="utf-8")
VISUALS = (ROOT / "gui" / "profile_visuals.py").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "gui" / "pages" / "dashboard.py").read_text(encoding="utf-8")


def test_factory_library_exposes_exactly_eight_game_profiles():
    engine = TriggerEngine()
    profiles = engine.get_all_profiles()
    assert tuple(profiles) == ordered_builtin_ids()
    assert len(profiles) == 8
    assert [profile.name for profile in profiles.values()] == [
        "Call of Duty: Warzone",
        "Forza Horizon 5",
        "Resident Evil 4",
        "Elden Ring",
        "EA Sports FC",
        "Street Fighter 6",
        "Minecraft",
        "Ghost of Tsushima",
    ]


def test_retired_ids_remain_readable_without_appearing_as_duplicate_cards():
    engine = TriggerEngine()
    profiles = engine.get_all_profiles()
    for legacy_id, canonical_id in LEGACY_PROFILE_ALIASES.items():
        assert legacy_id not in profiles
        assert engine.get_profile(legacy_id) is engine.get_profile(canonical_id)
    assert engine.apply_profile("sniper") is True
    assert engine.get_current_profile() == "assault_rifle"


def test_game_profiles_have_distinct_trigger_rgb_and_input_identities():
    engine = TriggerEngine()
    profiles = engine.get_all_profiles()
    assert profiles["racing"].left_trigger.effect_type == TriggerEffectType.SECTIONS
    assert profiles["racing"].right_trigger.effect_type == TriggerEffectType.SECTIONS
    assert profiles["horror"].light_config["effect"] == "heartbeat"
    assert profiles["pistol"].left_trigger.effect_type == TriggerEffectType.OFF
    assert profiles["shotgun"].right_trigger.effect_type == TriggerEffectType.OFF
    assert profiles["bow"].right_trigger.effect_type == TriggerEffectType.SECTIONS
    assert all(profile.icon.startswith("theme:") for profile in profiles.values())
    assert all(profile.tags for profile in profiles.values())
    assert all(profile.input_studio_config for profile in profiles.values())


def test_profile_gallery_is_static_and_split_into_reviewable_modules():
    assert "class ProfilesPage" in PROFILES_UI
    assert "ProfileGalleryCard" in PROFILES_UI
    assert "ProfileDetailPanel" in PROFILES_UI
    assert "class ProfileGalleryCard" in GALLERY_UI
    assert "class ProfileDetailPanel" in GALLERY_UI
    assert "class ProfileEditorDialog" in EDITOR_UI
    assert "_animation_timer" not in PROFILES_UI
    assert "QTimer(" not in GALLERY_UI


def test_profile_editor_keeps_trigger_presets_tags_and_low_rate_preview():
    assert "ICON_THEME_CHOICES" in EDITOR_UI
    assert "get_trigger_presets" in EDITOR_UI
    assert "Cargar preset" in EDITOR_UI
    assert "_copy_trigger_to_other" in EDITOR_UI
    assert "self.tags_edit" in EDITOR_UI
    assert "self._preview_timer.setInterval(250)" in EDITOR_UI
    assert "appearance.reduce_motion" in EDITOR_UI
    assert "theme:ghost" in VISUALS
    assert "theme:warzone" in VISUALS


def test_dashboard_does_not_render_theme_token_as_plain_text():
    assert 'fallback.startswith("theme:")' in DASHBOARD
    assert "fallback_glyph" in DASHBOARD
