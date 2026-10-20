from pathlib import Path

from tests.gui_source_catalog import class_source


ROOT = Path(__file__).resolve().parents[1]

def _class_block(name: str, _next_name: str) -> str:
    return class_source(name)


def _method_block(class_source: str, name: str, next_name: str) -> str:
    start = class_source.index(f"    def {name}(")
    end = class_source.index(f"    def {next_name}(", start)
    return class_source[start:end]


def test_appearance_preview_initializes_font_even_when_svg_logo_exists():
    block = _class_block("AppearancePreview", "CommandPalette")
    paint = block[block.index("    def paintEvent("):]
    font_init = paint.index("font = painter.font()")
    logo_branch = paint.index("if not logo.isNull():")
    first_font_use_after_logo = paint.index("font.setPointSize(11)")
    assert font_init < logo_branch < first_font_use_after_logo


def test_nexus_action_dialog_creates_validation_label_before_save_buttons():
    block = _class_block("AdvancedBindingDialog", "NexusControllerView")
    validation = block.index('self.validation = QLabel("")')
    button_box = block.index("buttons = QDialogButtonBox(")
    assert validation < button_box
    assert "self.validation.hide()" in block
    assert "self.validation.setText(error)" in block


def test_nexus_timing_fields_remain_editable_and_are_persisted():
    block = _class_block("AdvancedBindingDialog", "NexusControllerView")
    refresh = _method_block(block, "_refresh_timing", "accept")
    assert "for widget in (self.long_ms, self.double_ms, self.pulse_ms, self.turbo_hz):" in refresh
    assert "widget.setEnabled(True)" in refresh
    assert 'self.long_ms.setEnabled(activation in ("short", "long"))' not in refresh
    assert "self.double_ms.setEnabled(activation == \"double\")" not in refresh
    assert "self.pulse_ms.setEnabled(" not in refresh
    assert "self.turbo_hz.setEnabled(" not in refresh

    result = block[block.index("    def result_data("):]
    for key, widget in (
        ("long_press_ms", "self.long_ms.value()"),
        ("double_tap_ms", "self.double_ms.value()"),
        ("pulse_ms", "self.pulse_ms.value()"),
        ("turbo_hz", "self.turbo_hz.value()"),
    ):
        assert f'"{key}": {widget}' in result


def test_hotfix_251_changes_remain_present_after_newer_hotfixes():
    version_source = (ROOT / "nikaido_version.py").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    from nikaido_version import APP_VERSION

    assert f'APP_VERSION = "{APP_VERSION}"' in version_source
    assert f'version = "{APP_VERSION}"' in pyproject
