"""Regresiones de idiomas y curva visual de Nikaido 2.9.0."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT_PAGE = ROOT / "gui" / "pages" / "input.py"
CURVE_EDITOR = ROOT / "gui" / "curve_editor.py"
SETTINGS = ROOT / "gui" / "pages" / "settings.py"
MAIN_WINDOW = ROOT / "gui" / "main_window.py"
DASHBOARD = ROOT / "gui" / "pages" / "dashboard.py"
DEVICE_PAGE = ROOT / "gui" / "pages" / "device.py"
I18N = ROOT / "gui" / "i18n.py"
PROFILE_MANAGER = ROOT / "src" / "profile_manager.py"
BUILD = ROOT / "build.py"


def _class_method_source(path: Path, class_name: str, method_name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    class_node = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    method = next(
        node
        for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == method_name
    )
    return ast.get_source_segment(source, method) or ""


def test_curve_selector_refreshes_the_visual_and_saves():
    source = INPUT_PAGE.read_text(encoding="utf-8")
    assert "self.curve.currentIndexChanged.connect(self._curve_selected)" in source
    method = _class_method_source(INPUT_PAGE, "InputStudioPage", "_curve_selected")
    assert "self.curve_editor.set_curve" in method
    assert "self._update_curve_help()" in method
    assert "self.save()" in method


def test_curve_visual_matches_the_real_input_studio_presets():
    source = CURVE_EDITOR.read_text(encoding="utf-8")
    assert 'self.curve_mode == "exponential"' in source
    assert "value * value" in source
    assert 'self.curve_mode == "aggressive"' in source
    assert "value ** 0.5" in source
    assert 'self.curve_mode == "custom"' in source
    assert 'self.editable = self.allow_editing and self.curve_mode == "custom"' in source
    assert "DashLine" in source


def test_curve_widget_is_not_disabled_for_builtin_presets():
    source = INPUT_PAGE.read_text(encoding="utf-8")
    assert "self.curve_editor.setEnabled" not in source
    assert "Selecciona Personalizada para mover los puntos interiores." in source


def test_language_options_are_available_in_wizard_and_settings():
    i18n = I18N.read_text(encoding="utf-8")
    settings = SETTINGS.read_text(encoding="utf-8")
    assert '("es", "Español")' in i18n
    assert '("en", "English")' in i18n
    assert '("pt_BR", "Português (Brasil)")' in i18n
    assert "def _build_language_page" in settings
    assert 'choice.setProperty("languageChoice", True)' in settings
    assert "self.language_combo = QComboBox()" in settings
    assert 'pm.set_setting("language", self._language)' in settings


def test_language_switch_is_live_and_persistent():
    method = _class_method_source(MAIN_WINDOW, "NikaidoWindow", "set_language")
    assert 'self.profile_manager.set_setting("language", code)' in method
    assert "translate_widget_tree(self, code)" in method
    assert "palette._build_entries()" in method
    assert "self.page_meta(self._current_page)" in method


def test_language_default_and_packaging_are_present():
    profile = PROFILE_MANAGER.read_text(encoding="utf-8")
    build = BUILD.read_text(encoding="utf-8")
    assert "'language': 'es'" in profile
    assert '"gui.i18n"' in build
    assert '"gui.curve_editor"' in build


def test_dashboard_imports_i18n_helpers_used_at_runtime():
    source = DASHBOARD.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "i18n"
        for alias in node.names
    }
    assert {"tr", "translate_widget_tree"} <= imported


def test_audio_page_keeps_new_microphone_controls_translatable():
    i18n = I18N.read_text(encoding="utf-8")
    page = DEVICE_PAGE.read_text(encoding="utf-8")
    assert '"Botón MIC, volumen y LED": "MIC button, volume and LED"' in i18n
    assert '"Botón MIC, volumen y LED": "Botão MIC, volume e LED"' in i18n
    assert '"Micrófono silenciado": "Microphone muted"' in i18n
    assert '"Micrófono silenciado": "Microfone silenciado"' in i18n
    assert '"Todos los micrófonos activos": "All active microphones"' in i18n
    assert '"Todos los micrófonos activos": "Todos os microfones ativos"' in i18n
    assert '"Todos excepto el micrófono del DualSense"' in i18n
    assert 'self.target_mode.addItem' in page
    assert '"all_except_dualsense"' in page
    assert "def _set_runtime_text" in page
    assert "_nikaido_i18n_combo_sources" in page
