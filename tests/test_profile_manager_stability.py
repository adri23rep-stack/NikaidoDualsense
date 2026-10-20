import json
import zipfile

from src.profile_manager import ProfileManager


def test_save_config_is_idempotent_and_leaves_no_temp_file(tmp_path):
    manager = ProfileManager(str(tmp_path / "config"))
    manager.set_setting("ui.test_value", 42)
    assert manager.save_config()
    first_backups = list(manager.backup_dir.glob("profiles_backup_*.json"))
    first_contents = manager.config_file.read_text(encoding="utf-8")

    assert manager.save_config()
    assert manager.config_file.read_text(encoding="utf-8") == first_contents
    assert list(manager.backup_dir.glob("profiles_backup_*.json")) == first_backups
    assert not manager.config_file.with_suffix(".json.tmp").exists()
    assert json.loads(first_contents)["settings"]["ui"]["test_value"] == 42


def test_newer_nika_format_is_rejected_without_mutating_profiles(tmp_path):
    manager = ProfileManager(str(tmp_path / "config"))
    package = tmp_path / "future.Nika"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "format": "Nikaido Profile Package",
                    "format_version": 999,
                    "image_file": "",
                }
            ),
        )
        archive.writestr(
            "profile.json",
            json.dumps({"name": "Futuro", "left_trigger": {}, "right_trigger": {}}),
        )

    before = manager.get_custom_profiles()
    assert manager.import_profile(str(package)) is None
    assert manager.get_custom_profiles() == before


def test_nested_setting_recovers_from_legacy_scalar(tmp_path):
    manager = ProfileManager(str(tmp_path / "config"))
    manager.set_setting("window_geometry", "legacy-bad-value")
    manager.set_setting("window_geometry.width", 1280)
    assert manager.get_setting("window_geometry.width") == 1280


def test_corrupt_config_restores_valid_backup_and_defaults(tmp_path):
    config_dir = tmp_path / "config"
    manager = ProfileManager(str(config_dir))
    manager.set_setting("custom.flag", True)
    manager.save_config()
    backup = manager.backup_dir / "profiles_backup_99999999_999999_999999.json"
    backup.write_text(json.dumps({"settings": {"custom": {"flag": True}}}), encoding="utf-8")
    manager.config_file.write_text("{broken", encoding="utf-8")

    restored = ProfileManager(str(config_dir))
    assert restored.get_setting("custom.flag") is True
    assert restored.get_setting("minimize_to_tray") is True
    assert json.loads(restored.config_file.read_text(encoding="utf-8"))


def test_old_config_is_marked_with_current_schema_version(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "profiles.json").write_text(
        json.dumps({"version": "0.1", "settings": {"custom": 7}}),
        encoding="utf-8",
    )
    manager = ProfileManager(str(config_dir))
    assert manager._config["version"] == "2.0.0"
    assert manager.get_setting("custom") == 7


def test_reset_can_purge_orphaned_profile_and_background_assets(tmp_path):
    manager = ProfileManager(str(tmp_path / "config"))
    profile_asset = manager.profile_images_dir / "old.png"
    background_asset = manager.ui_backgrounds_dir / "background.jpg"
    profile_asset.write_bytes(b"old")
    background_asset.write_bytes(b"old")

    manager.reset_to_defaults(purge_assets=True)

    assert not profile_asset.exists()
    assert not background_asset.exists()
    assert manager.get_setting("appearance.background_path", "missing") == ""


def test_malformed_known_config_containers_are_repaired(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    malformed = {
        "settings": [],
        "profiles": "bad",
        "custom_profiles": [],
        "macros": "bad",
        "button_map": None,
        "game_profiles": 7,
        "favorites": {"not": "a list"},
        "unknown_extension_data": {"preserved": True},
    }
    (config_dir / "profiles.json").write_text(json.dumps(malformed), encoding="utf-8")

    manager = ProfileManager(str(config_dir))

    assert manager.get_setting("auto_connect") is True
    assert manager.get_custom_profiles() == {}
    assert manager.get_macros() == {}
    assert manager.get_button_map() == {}
    assert manager.get_game_profiles() == {}
    assert manager.get_favorites() == ["assault_rifle", "racing", "bow"]
    assert manager._config["profiles"] == {}
    assert manager._config["unknown_extension_data"] == {"preserved": True}
