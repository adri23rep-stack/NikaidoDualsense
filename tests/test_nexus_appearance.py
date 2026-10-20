from pathlib import Path

from PIL import Image

from src.profile_manager import ProfileManager
from tests.gui_source_catalog import GUI_SOURCE


ROOT = Path(__file__).resolve().parents[1]
MODERN = GUI_SOURCE
DESIGN = (ROOT / "gui" / "design_system.py").read_text(encoding="utf-8")
APPEARANCE_SOURCE = (ROOT / "src" / "appearance.py").read_text(encoding="utf-8")


def test_nexus_reuses_advanced_mapper_instead_of_new_runtime_engine():
    assert 'class NexusControllerView(QWidget):' in MODERN
    assert 'self.tabs.addTab(self._build_nexus_tab(), "Nikaido Nexus")' in MODERN
    assert 'AdvancedBindingDialog(' in MODERN
    assert 'self._apply_advanced("Acción añadida desde Nexus")' in MODERN
    assert '"Nikaido Nexus", "Control visual, capas y acciones"' in MODERN


def test_appearance_is_live_and_persisted():
    assert 'class BackgroundRoot(QWidget):' in MODERN
    assert 'self.window.profile_manager.store_ui_background(path)' in MODERN
    assert 'self.window.apply_appearance(values)' in MODERN
    assert '"panel_opacity": 88' in APPEARANCE_SOURCE
    assert 'def build_app_qss(' in DESIGN
    assert 'self._appearance_apply_timer.start(90)' in MODERN


def test_profile_manager_copies_background_to_stable_config_dir(tmp_path):
    manager = ProfileManager(str(tmp_path / "config"))
    source = tmp_path / "wallpaper.png"
    Image.new("RGB", (64, 48), (28, 74, 116)).save(source)

    stored = manager.store_ui_background(str(source))

    assert stored
    stored_path = Path(stored)
    assert stored_path.is_file()
    assert stored_path.parent == manager.ui_backgrounds_dir
    with Image.open(stored_path) as image:
        assert image.size == (64, 48)
        assert image.format in {"PNG", "JPEG"}

    manager.set_setting("appearance.background_path", stored)
    manager.set_setting("appearance.background_enabled", True)
    manager.remove_ui_background()
    assert manager.get_setting("appearance.background_path") == ""
    assert manager.get_setting("appearance.background_enabled") is False
    assert not stored_path.exists()
