"""Regresiones de Estilo A e identidad visual separada de perfiles."""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from src.profile_manager import ProfileManager
from src.trigger_engine import TriggerEngine, WeaponProfile

ROOT = Path(__file__).resolve().parents[1]


def _image(path: Path, size: tuple[int, int], color: tuple[int, int, int]) -> Path:
    Image.new("RGB", size, color).save(path)
    return path


def test_weapon_profile_roundtrip_separates_icon_and_banner(tmp_path):
    profile = TriggerEngine().get_profile("assault_rifle")
    profile.icon_path = str(tmp_path / "icon.png")
    profile.image_path = profile.icon_path
    profile.banner_path = str(tmp_path / "banner.png")

    payload = profile.to_dict()
    assert payload["image_path"] == profile.icon_path
    assert payload["icon_path"] == profile.icon_path
    assert payload["banner_path"] == profile.banner_path

    restored = WeaponProfile.from_dict(payload)
    assert restored.icon_path == profile.icon_path
    assert restored.image_path == profile.icon_path
    assert restored.banner_path == profile.banner_path


def test_legacy_image_path_migrates_to_both_visual_slots():
    restored = WeaponProfile.from_dict(
        {
            "name": "Legado",
            "image_path": "legacy/profile.png",
            "left_trigger": {},
            "right_trigger": {},
        }
    )
    assert restored.icon_path == "legacy/profile.png"
    assert restored.banner_path == "legacy/profile.png"


def test_nika_roundtrip_preserves_independent_icon_and_banner(tmp_path):
    manager = ProfileManager(str(tmp_path / "config"))
    icon = _image(tmp_path / "icon.png", (256, 256), (30, 120, 220))
    banner = _image(tmp_path / "banner.png", (1280, 480), (95, 30, 150))
    profile = TriggerEngine().get_profile("assault_rifle")
    profile.icon_path = str(icon)
    profile.image_path = str(icon)
    profile.banner_path = str(banner)

    package = tmp_path / "media.Nika"
    assert manager.export_profile("assault_rifle", str(package), profile.to_dict())
    with zipfile.ZipFile(package) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["contents"]["icon"] is True
        assert manifest["contents"]["banner"] is True
        assert manifest["icon_file"] in archive.namelist()
        assert manifest["banner_file"] in archive.namelist()

    imported_id = manager.import_profile(str(package))
    assert imported_id
    imported = manager.get_custom_profiles()[imported_id]
    assert Path(imported["icon_path"]).is_file()
    assert Path(imported["banner_path"]).is_file()
    assert imported["icon_path"] != imported["banner_path"]
    assert imported["image_path"] == imported["icon_path"]


def test_old_nika_single_image_is_copied_to_two_independent_files(tmp_path):
    manager = ProfileManager(str(tmp_path / "config"))
    image = _image(tmp_path / "legacy.png", (320, 180), (20, 80, 120))
    package = tmp_path / "legacy.Nika"
    manifest = {
        "format": "Nikaido Profile Package",
        "format_version": 1,
        "profile_id": "legacy",
        "image_file": "assets/profile.png",
    }
    profile = {"name": "Legado", "left_trigger": {}, "right_trigger": {}}
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("profile.json", json.dumps(profile))
        archive.writestr("macros.json", "{}")
        archive.writestr("light_effects.json", "{}")
        archive.write(image, "assets/profile.png")

    imported_id = manager.import_profile(str(package))
    assert imported_id
    imported = manager.get_custom_profiles()[imported_id]
    assert Path(imported["icon_path"]).is_file()
    assert Path(imported["banner_path"]).is_file()
    assert imported["icon_path"] != imported["banner_path"]


def test_style_a_keeps_selection_out_of_border_logic():
    source = (ROOT / "gui" / "profile_gallery.py").read_text(encoding="utf-8")
    assert "Estilo A · Sobrio premium" in source
    assert "border:1px solid {C['border']}" in source
    assert "shadow_visible = self.is_selected or self._hovered" in source
    assert "primary if self.selected" not in source


def _qt_modules():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QPushButton, QWidget

    return QApplication, QPushButton, QWidget


def test_style_a_shadow_only_runs_for_selected_or_hovered():
    QApplication, _QPushButton, QWidget = _qt_modules()
    app = QApplication.instance() or QApplication([])
    from gui.profile_gallery import ProfileGalleryCard

    class Page(QWidget):
        def apply_profile(self, _profile_id): pass
        def edit_profile(self, _profile_id): pass
        def duplicate_profile(self, _profile_id): pass
        def export_profile(self, _profile_id): pass
        def toggle_favorite(self, _profile_id): pass
        def delete_profile(self, _profile_id): pass
        def reset_builtin_profile(self, _profile_id): pass

    page = Page()
    profile = TriggerEngine().get_profile("assault_rifle")
    card = ProfileGalleryCard(
        page, "assault_rifle", profile,
        active=False, favorite=False, selected=False, custom=False,
    )
    assert not card._shadow.isEnabled()
    card.set_selected_state(True)
    assert card._shadow.isEnabled()
    assert "border:1px solid" in card.root.styleSheet()
    card.set_selected_state(False)
    assert not card._shadow.isEnabled()
    card.deleteLater()
    app.processEvents()


def test_create_and_edit_keep_icon_and_banner_independent(monkeypatch, tmp_path):
    QApplication, _QPushButton, QWidget = _qt_modules()
    app = QApplication.instance() or QApplication([])
    from tests.test_hotfix_2986_profile_editor_actions import _fake_window
    import gui.pages.profiles as profiles_module
    from gui.pages.profiles import ProfilesPage

    icon = _image(tmp_path / "icon.png", (256, 256), (10, 140, 200))
    banner = _image(tmp_path / "banner.png", (1200, 500), (100, 30, 160))
    window = _fake_window(QWidget)
    real_dialog = profiles_module.ProfileEditorDialog

    class AutoDialog(real_dialog):
        call = 0

        def exec(self):
            AutoDialog.call += 1
            if self.creating:
                self.name_edit.setText("Perfil multimedia")
                self.icon_source = str(icon)
                self.icon_changed = True
                self.image_source = self.icon_source
                self.image_changed = True
                self.banner_source = str(banner)
                self.banner_changed = True
            else:
                # Quitar solamente el icono no debe borrar ni alterar el banner.
                self.icon_source = ""
                self.icon_changed = True
                self.image_source = ""
                self.image_changed = True
                self.banner_changed = False
            self._accept_changes()
            return self.result()

    monkeypatch.setattr(profiles_module, "ProfileEditorDialog", AutoDialog)
    page = ProfilesPage(window)
    page.create_from_active()
    created = window.trigger_engine.get_profile("perfil_multimedia")
    assert created is not None
    assert Path(created.icon_path).is_file()
    assert Path(created.banner_path).is_file()
    saved_banner = created.banner_path

    page.edit_profile("perfil_multimedia")
    edited = window.trigger_engine.get_profile("perfil_multimedia")
    assert edited.icon_path == ""
    assert edited.image_path == ""
    assert edited.banner_path == saved_banner
    assert Path(edited.banner_path).is_file()
    page.deleteLater()
    app.processEvents()
