from pathlib import Path

from PIL import Image

from src.profile_manager import ProfileManager
from src.wallpapers import (
    BUNDLED_WALLPAPERS,
    available_wallpapers,
    find_wallpaper,
    image_path,
    thumbnail_path,
    wallpapers_dir,
)

ROOT = Path(__file__).resolve().parents[1]
SETTINGS_SOURCE = (ROOT / "gui" / "pages" / "settings.py").read_text(encoding="utf-8")


def test_every_bundled_wallpaper_ships_image_thumbnail_and_credit():
    credits = (wallpapers_dir() / "CREDITS.txt").read_text(encoding="utf-8")
    assert (wallpapers_dir() / "LICENSE-CC0.txt").is_file()
    assert "CC0" in credits
    assert len(available_wallpapers()) == len(BUNDLED_WALLPAPERS) == 6
    assert len({item.key for item in BUNDLED_WALLPAPERS}) == len(BUNDLED_WALLPAPERS)
    for item in BUNDLED_WALLPAPERS:
        assert item.filename in credits
        assert image_path(item).stat().st_size < 1_500_000
        with Image.open(image_path(item)) as full:
            assert full.size == (2560, 1440)
        with Image.open(thumbnail_path(item)) as thumb:
            assert thumb.size == (480, 270)


def test_bundled_wallpaper_is_stored_and_remembered(tmp_path):
    manager = ProfileManager(str(tmp_path / "config"))

    stored = manager.store_bundled_wallpaper("roraima")

    assert stored and Path(stored).is_file()
    assert Path(stored).parent == manager.ui_backgrounds_dir
    assert manager.current_wallpaper_key() == "roraima"
    assert manager.store_bundled_wallpaper("no-existe") == ""
    assert manager.current_wallpaper_key() == "roraima"


def test_custom_image_or_removal_forgets_bundled_choice(tmp_path):
    manager = ProfileManager(str(tmp_path / "config"))
    manager.store_bundled_wallpaper("villarrica")
    own = tmp_path / "mio.png"
    Image.new("RGB", (64, 48), (10, 20, 30)).save(own)

    assert manager.store_ui_background(str(own))
    assert manager.current_wallpaper_key() == ""

    manager.store_bundled_wallpaper("neuquen")
    assert manager.current_wallpaper_key() == "neuquen"
    manager.remove_ui_background()
    assert manager.current_wallpaper_key() == ""
    assert not list(manager.ui_backgrounds_dir.glob("background.*"))


def test_find_wallpaper_rejects_unknown_keys():
    assert find_wallpaper("lencois").name == "Lençóis Maranhenses"
    assert find_wallpaper("../../etc/passwd") is None


def test_wizard_and_settings_both_offer_the_gallery():
    assert SETTINGS_SOURCE.count("WallpaperGallery(columns=3)") == 2
    assert "self.wizard_wallpaper_gallery.selected.connect(self.choose_wizard_bundled_background)" in SETTINGS_SOURCE
    assert "self.wallpaper_gallery.selected.connect(self.choose_bundled_background)" in SETTINGS_SOURCE
    assert SETTINGS_SOURCE.count("store_bundled_wallpaper(key)") == 2
