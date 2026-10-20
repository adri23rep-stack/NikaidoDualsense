from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "gui" / "pages" / "emulation.py").read_text(encoding="utf-8")
VISUAL = (ROOT / "gui" / "controller_visual.py").read_text(encoding="utf-8")


def test_emulation_hub_has_four_output_choices_and_dynamic_preview():
    assert '"Emulación e Integración"' in PAGE
    assert '"DualSense nativo"' in PAGE
    assert '"DualShock 4"' in PAGE
    assert '"Xbox 360"' in PAGE
    assert '"KeyBridge"' in PAGE
    assert "ControllerVisual()" in PAGE
    assert "set_emulation_mode(display_mode, keybridge=keybridge_running)" in PAGE


def test_emulation_hub_keeps_existing_engines_and_editor():
    assert "self.keybridge_editor = self._build_keybridge_card()" in PAGE
    assert "set_touchpad_enabled" in PAGE
    assert "set_gyro_enabled" in PAGE
    assert "set_mouse_gyro_enabled" in PAGE
    assert "set_keybridge_enabled" in PAGE
    assert "set_emulation" in PAGE


def test_emulation_hub_exposes_status_and_quick_tools():
    for text in (
        "Control físico",
        "Modo actual",
        "Dispositivo virtual",
        "Latencia interna",
        "Conexión",
        "Perfil activo",
        "Batería",
        "Probar entrada",
        "Probar vibración",
        "Reset virtual",
        "Modo pánico",
    ):
        assert f'"{text}"' in PAGE


def test_controller_visual_changes_identity_without_touching_backend():
    assert "def set_emulation_mode" in VISUAL
    assert 'self.emulation_mode = "none"' in VISUAL
    assert 'emblem, emblem_color, emblem_size = "X"' in VISUAL
    assert 'emblem, emblem_color, emblem_size = "PS\\n4"' in VISUAL
    assert 'emblem, emblem_color, emblem_size = "SONY\\n5"' in VISUAL
    assert 'emblem, emblem_color, emblem_size = "⌨"' in VISUAL
