"""Regresiones para crear y editar perfiles desde Profile Gallery."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EDITOR_SOURCE = (ROOT / "gui" / "profile_editor.py").read_text(encoding="utf-8")
PAGE_SOURCE = (ROOT / "gui" / "pages" / "profiles.py").read_text(encoding="utf-8")


def test_editor_imports_every_ui_helper_used_during_construction():
    assert "    label,\n" in EDITOR_SOURCE
    assert 'label("Vista previa del efecto", "heading")' in EDITOR_SOURCE


def test_new_profile_has_a_source_even_before_a_profile_is_applied():
    assert "engine.get_current_profile()" in PAGE_SOURCE
    assert "or self.selected_profile_id" in PAGE_SOURCE
    assert "or DEFAULT_PROFILE_ID" in PAGE_SOURCE
    assert "No hay un perfil base disponible" in PAGE_SOURCE



def test_profile_feature_row_stylesheet_closes_with_one_brace():
    source = (ROOT / "gui" / "profile_gallery.py").read_text(encoding="utf-8")
    assert '"border-radius:12px;padding:0; }}"' not in source
    assert '"border-radius:12px;padding:0; }"' in source

def _qt_modules():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QPushButton, QWidget

    return QApplication, QPushButton, QWidget


def _fake_window(QWidget):
    from src.light_effects import LightEffectEngine
    from src.profile_manager import ProfileManager
    from src.trigger_engine import TriggerEngine

    class InputStudioStub:
        def __init__(self):
            self.data = {}

        def get_profile_config(self, profile_id):
            return self.data.get(profile_id, {})

        def copy_profile(self, source_id, target_id):
            self.data[target_id] = dict(self.data.get(source_id, {}))

        def remove_profile(self, profile_id):
            self.data.pop(profile_id, None)

        def export_profiles(self):
            return dict(self.data)

        def set_profile_config(self, profile_id, config):
            self.data[profile_id] = dict(config or {})

    class FakeWindow(QWidget):
        def __init__(self):
            super().__init__()
            self.profile_manager = ProfileManager(tempfile.mkdtemp())
            self.trigger_engine = TriggerEngine()
            self.light_effect_engine = LightEffectEngine()
            self.input_studio = InputStudioStub()
            self.macro_engine = None
            self.language = "es"
            self.messages = []

        def request_config_save(self):
            self.profile_manager.save_config(force=True)

        def refresh_profiles(self):
            return None

        def toast(self, message):
            self.messages.append(("toast", message))

        def alert(self, message):
            self.messages.append(("alert", message))

        def navigate(self, destination):
            self.messages.append(("navigate", destination))

        def apply_profile(self, profile_id, force=False):
            del force
            resolved = self.trigger_engine.canonical_profile_id(profile_id)
            self.trigger_engine._current_profile = resolved
            self.profile_manager.set_active_profile(resolved)

    return FakeWindow()


def test_real_editor_constructs_and_accepts_for_all_builtin_profiles(monkeypatch):
    QApplication, _QPushButton, QWidget = _qt_modules()
    app = QApplication.instance() or QApplication([])
    window = _fake_window(QWidget)

    from gui.profile_editor import ProfileEditorDialog

    for profile_id, profile in window.trigger_engine.get_all_profiles().items():
        dialog = ProfileEditorDialog(window, profile_id, profile)
        dialog.name_edit.setText(f"{profile.name} prueba")
        dialog._accept_changes()
        assert dialog.result() == dialog.DialogCode.Accepted
        assert dialog.profile.name.endswith("prueba")
        dialog.deleteLater()
    app.processEvents()


def test_new_and_edit_buttons_complete_the_full_profile_flow(monkeypatch):
    QApplication, QPushButton, QWidget = _qt_modules()
    app = QApplication.instance() or QApplication([])
    window = _fake_window(QWidget)

    import gui.pages.profiles as profiles_module
    from gui.pages.profiles import ProfilesPage

    real_dialog = profiles_module.ProfileEditorDialog

    class AutoAcceptDialog(real_dialog):
        calls = 0

        def exec(self):
            AutoAcceptDialog.calls += 1
            self.name_edit.setText(
                "Perfil prueba creado"
                if self.creating
                else f"{self.name_edit.text()} editado"
            )
            self._accept_changes()
            return self.result()

    monkeypatch.setattr(profiles_module, "ProfileEditorDialog", AutoAcceptDialog)

    page = ProfilesPage(window)
    page.resize(1400, 900)
    page.show()
    app.processEvents()

    # Debe funcionar aun cuando el control no ha aplicado ningún perfil todavía.
    assert window.trigger_engine.get_current_profile() is None
    new_button = next(
        button for button in page.findChildren(QPushButton) if "Nuevo perfil" in button.text()
    )
    new_button.click()
    app.processEvents()
    assert window.trigger_engine.get_profile("perfil_prueba_creado") is not None

    page.select_profile("assault_rifle")
    app.processEvents()
    edit_button = next(
        button
        for button in page.detail_panel.findChildren(QPushButton)
        if button.text() == "Editar perfil"
    )
    edit_button.click()
    app.processEvents()
    assert window.trigger_engine.get_profile("assault_rifle").name.endswith("editado")
    assert AutoAcceptDialog.calls == 2
    assert ("toast", "Perfil creado") in window.messages
    assert ("toast", "Perfil guardado") in window.messages
