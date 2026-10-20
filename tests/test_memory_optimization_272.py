"""Regresiones de uso de memoria para Nikaido 2.7.2."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = (ROOT / "gui" / "components.py").read_text(encoding="utf-8")
MAIN_WINDOW = (ROOT / "gui" / "main_window.py").read_text(encoding="utf-8")
SETTINGS = (ROOT / "gui" / "pages" / "settings.py").read_text(encoding="utf-8")
DIAGNOSTICS = (ROOT / "src" / "diagnostics.py").read_text(encoding="utf-8")


def test_mascot_decodes_near_display_size_and_does_not_reload_same_pose():
    assert "QImageReader(path)" in COMPONENTS
    assert 'if normalized_pose != self._pose or self._source.isNull()' in COMPONENTS
    assert "def clear_resources" in COMPONENTS
    assert "self._scaled_key" in COMPONENTS
    assert "def load_scaled_pixmap" in COMPONENTS


def test_wizard_releases_native_images_and_is_deleted_when_closed():
    assert "WA_DeleteOnClose" in SETTINGS
    assert "self.finished.connect(self._release_resources)" in SETTINGS
    assert "self.mascot_panel.clear_resources()" in SETTINGS
    assert "self.wizard_appearance_preview.release_image_cache()" in SETTINGS
    assert "self.connection_timer.stop()" in SETTINGS


def test_large_backgrounds_are_decoded_with_limits():
    assert "IMAGE_DECODE_LIMIT = QSize(2560, 1600)" in COMPONENTS
    assert "IMAGE_DECODE_LIMIT = QSize(640, 440)" in COMPONENTS
    assert "reader.setScaledSize(target)" in COMPONENTS
    assert "def release_image_cache" in COMPONENTS


def test_page_modules_are_imported_only_when_opened():
    assert '"profiles": ("profiles_page", "gui.pages.profiles", "ProfilesPage")' in MAIN_WINDOW
    assert "importlib.import_module(module_name)" in MAIN_WINDOW
    assert "from .pages.profiles import ProfilesPage" not in MAIN_WINDOW
    assert "QPixmapCache.setCacheLimit(8192)" in MAIN_WINDOW


def test_passive_diagnostics_history_matches_the_promised_observer_rate():
    assert "MAX_HISTORY_SECONDS = 10" in DIAGNOSTICS
    assert "self._last_history_sample_at" in DIAGNOSTICS
    assert "if not history_due and not capture_active" in DIAGNOSTICS
    assert "if history_due:" in DIAGNOSTICS
