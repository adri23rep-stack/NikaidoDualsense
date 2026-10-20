import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

import gui.ui_theme as ui_theme
import src.hidhide_manager as hidhide_module
from gui.ui_theme import (
    MAX_THEME_ELEMENTS,
    ThemeError,
    UILayout,
    _safe_extract_zip,
    load_layout,
    validate_layout,
)
from src.bluetooth_utils import BluetoothManager
from src.hidhide_manager import HidHideManager
from src.macro_engine import MAX_MACRO_STEPS
from src.profile_manager import ProfileManager
from src.security_utils import (
    SecurityValidationError,
    redact_private_text,
    safe_json_loads,
    validate_zip_member_name,
)


def test_security_json_limits_depth_and_nodes():
    value = current = {}
    for index in range(30):
        current["next"] = {}
        current = current["next"]
    with pytest.raises(SecurityValidationError, match="anidado"):
        safe_json_loads(json.dumps(value), label="Prueba")


def test_profile_import_rejects_unsafe_zip_names(tmp_path):
    package = tmp_path / "unsafe.Nika"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("manifest.json", json.dumps({
            "format": "Nikaido Profile Package",
            "format_version": 1,
        }))
        archive.writestr("profile.json", json.dumps({"name": "Seguro"}))
        archive.writestr("../outside.txt", "no")
    manager = ProfileManager(str(tmp_path / "config"))
    assert manager.import_profile(str(package)) is None


def test_profile_import_sanitizes_macro_size_and_strings(tmp_path):
    package = tmp_path / "macro.Nika"
    steps = [{"type": "wait", "ms": 1} for _ in range(MAX_MACRO_STEPS + 80)]
    macro = {
        "id": "old",
        "name": "N" * 500,
        "description": "D" * 10_000,
        "steps": steps,
    }
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps({
            "format": "Nikaido Profile Package",
            "format_version": 1,
            "profile_id": "source",
        }))
        archive.writestr("profile.json", json.dumps({"name": "Importado"}))
        archive.writestr("macros.json", json.dumps({"old": macro}))
        archive.writestr("light_effects.json", "{}")
    manager = ProfileManager(str(tmp_path / "config"))
    profile_id = manager.import_profile(str(package))
    assert profile_id
    imported = next(iter(manager.get_macros().values()))
    assert len(imported["steps"]) == MAX_MACRO_STEPS
    assert len(imported["name"]) == 120
    assert len(imported["description"]) == 2_000


def test_theme_package_rejects_zip_bomb_and_ambiguous_names(tmp_path):
    bomb = tmp_path / "bomb.nikaido-theme"
    with zipfile.ZipFile(bomb, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", b"0" * (1024 * 1024))
    with pytest.raises(ThemeError, match="compresión sospechosa"):
        _safe_extract_zip(bomb, tmp_path / "bomb-out")

    duplicate = tmp_path / "duplicate.nikaido-theme"
    with zipfile.ZipFile(duplicate, "w") as archive:
        archive.writestr("manifest.json", "{}")
        archive.writestr("MANIFEST.JSON", "{}")
    with pytest.raises(ThemeError, match="duplicados"):
        _safe_extract_zip(duplicate, tmp_path / "duplicate-out")


def test_theme_assets_are_confined_and_remote_paths_are_rejected(tmp_path):
    image = tmp_path / "outside.png"
    image.write_bytes(b"not-used")
    theme = tmp_path / "theme.json"
    theme.write_text(json.dumps({
        "schema_version": 3,
        "name": "Untrusted",
        "canvas": {"width": 900, "height": 560, "background": "#111111", "scale_mode": "contain"},
        "pages": [{"id": "main", "name": "Inicio"}],
        "default_page": "main",
        "elements": [{
            "id": "image",
            "type": "image",
            "x": 0,
            "y": 0,
            "width": 100,
            "height": 100,
            "source": str(image.resolve()),
        }],
    }), encoding="utf-8")

    untrusted = load_layout(theme)
    errors, _ = validate_layout(untrusted, check_assets=True)
    assert any("no se encontró" in item for item in errors)

    trusted_editor = load_layout(theme, allow_external_assets=True)
    assert trusted_editor.resolve_asset(str(image.resolve())) == image.resolve()
    assert trusted_editor.resolve_asset(r"\\server\share\image.png") is None
    assert trusted_editor.resolve_asset("https://example.invalid/image.png") is None


def test_theme_rejects_too_many_elements():
    data = {
        "schema_version": 3,
        "canvas": {"width": 900, "height": 560, "background": "#111111", "scale_mode": "contain"},
        "pages": [{"id": "main", "name": "Inicio"}],
        "default_page": "main",
        "elements": [{} for _ in range(MAX_THEME_ELEMENTS + 1)],
    }
    with pytest.raises(ThemeError, match="elementos"):
        UILayout.from_dict(data)


def test_hidhide_rejects_control_characters_in_device_id(monkeypatch):
    manager = HidHideManager(command_runner=lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(manager, "_require_cli", lambda: r"C:\Program Files\HidHide\HidHideCLI.exe")
    with pytest.raises(ValueError):
        manager.set_device_hidden("HID\\VID_054C\n--cloak-off", True)


def test_bluetooth_rejects_arbitrary_powershell_and_keeps_other_pairings(monkeypatch):
    manager = BluetoothManager()
    called = []
    monkeypatch.setattr(manager, "_powershell_path", lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")
    monkeypatch.setattr("src.bluetooth_utils.subprocess.run", lambda command, **kwargs: called.append(command) or SimpleNamespace(returncode=0, stdout="", stderr=""))
    ok, _ = manager._run_powershell("Remove-Item HKLM:\\Everything -Recurse", "Prueba")
    assert ok is False
    assert called == []
    source = Path(__file__).resolve().parents[1] / "src" / "bluetooth_utils.py"
    text = source.read_text(encoding="utf-8")
    assert "BTHPORT\\\\Parameters\\\\Keys" not in text
    assert "ExecutionPolicy" not in text


def test_private_text_redaction(monkeypatch):
    monkeypatch.setenv("USERPROFILE", r"C:\Users\ExampleUser")
    monkeypatch.setenv("USERNAME", "ExampleUser")
    value = redact_private_text(r"Fallo C:\Users\ExampleUser\AppData\secret.txt\x00")
    assert "ExampleUser" not in value
    assert "<RUTA_USUARIO>" in value


@pytest.mark.parametrize("payload", ["NaN", "Infinity", "-Infinity"])
def test_json_rejects_non_finite_numbers(payload):
    with pytest.raises(SecurityValidationError, match="numérica no válida"):
        safe_json_loads('{"value": ' + payload + '}', label="Prueba")


@pytest.mark.parametrize(
    "name",
    ["assets/photo.png:evil.exe", "CON", "folder/NUL.txt", "folder/name. ", "folder/name."],
)
def test_zip_names_reject_windows_ads_reserved_and_ambiguous_parts(name):
    with pytest.raises(SecurityValidationError, match="Windows"):
        validate_zip_member_name(name, label="prueba")


def test_theme_image_limits_decoded_pixels_and_animation_budget(tmp_path, monkeypatch):
    image_path = tmp_path / "large.png"
    image_path.write_bytes(b"fake")

    class FakeImage:
        def __init__(self, size, frames):
            self.size = size
            self.n_frames = frames

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def verify(self):
            return None

    monkeypatch.setattr(ui_theme.Image, "open", lambda _path: FakeImage((5000, 5000), 1))
    assert "dimensiones" in ui_theme._theme_asset_error(image_path)

    monkeypatch.setattr(ui_theme.Image, "open", lambda _path: FakeImage((1000, 1000), 100))
    assert "animación" in ui_theme._theme_asset_error(image_path)


def test_theme_save_is_atomic_and_leaves_no_temp_file(tmp_path):
    destination = tmp_path / "theme.json"
    layout = UILayout()
    saved = ui_theme.save_layout(layout, destination)
    assert saved == destination.resolve()
    assert destination.is_file()
    assert not destination.with_suffix(".json.tmp").exists()


def test_hidhide_ignores_registry_paths_outside_program_files(monkeypatch):
    monkeypatch.setenv("ProgramFiles", r"C:\Program Files")
    monkeypatch.delenv("ProgramW6432", raising=False)
    monkeypatch.delenv("ProgramFiles(x86)", raising=False)

    untrusted = HidHideManager._known_roots(r"C:\Users\ExampleUser\Downloads\HidHide")
    normalized = {str(item).replace("/", "\\").lower() for item in untrusted}
    assert r"c:\users\exampleuser\downloads\hidhide" not in normalized

    trusted = HidHideManager._known_roots(r"C:\Program Files\Nefarius Software Solutions e.U\HidHide")
    normalized = {str(item).replace("/", "\\").lower() for item in trusted}
    assert r"c:\program files\nefarius software solutions e.u\hidhide" in normalized


def test_hidhide_install_button_opens_only_official_release_page(monkeypatch):
    opened = []
    monkeypatch.setattr(hidhide_module.os, "name", "nt")
    monkeypatch.setattr(hidhide_module.webbrowser, "open", lambda url, new=0: opened.append((url, new)) or True)
    manager = HidHideManager()
    assert manager.launch_installer() is True
    assert opened == [("https://github.com/nefarius/HidHide/releases/latest", 2)]


def test_theme_package_install_is_transactional(tmp_path):
    package = tmp_path / "same.nikaido-theme"
    valid = {
        "schema_version": 3,
        "name": "Seguro",
        "canvas": {"width": 900, "height": 560, "background": "#111111", "scale_mode": "contain"},
        "pages": [{"id": "main", "name": "Inicio"}],
        "default_page": "main",
        "elements": [],
    }
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("manifest.json", json.dumps(valid))

    installed = load_layout(package, extract_dir=tmp_path / "themes")
    marker = installed.base_dir / "keep.txt"
    marker.write_text("old", encoding="utf-8")

    invalid = dict(valid)
    invalid["canvas"] = {"width": 1, "height": 1, "background": "#111111", "scale_mode": "contain"}
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("manifest.json", json.dumps(invalid))

    with pytest.raises(ThemeError, match="Tema inválido"):
        load_layout(package, extract_dir=tmp_path / "themes")
    assert marker.read_text(encoding="utf-8") == "old"


def test_diagnostic_sanitizer_removes_private_paths_and_control_characters(monkeypatch):
    from src.diagnostics import DiagnosticEngine

    monkeypatch.setenv("USERPROFILE", r"C:\Users\ExampleUser")
    sanitized = DiagnosticEngine._sanitize_value({
        "error": "Fallo C:\\Users\\ExampleUser\\secret.log\x00\x1b[31m",
    })
    assert "ExampleUser" not in sanitized["error"]
    assert "\x00" not in sanitized["error"]
    assert "\x1b" not in sanitized["error"]
    assert "<RUTA_USUARIO>" in sanitized["error"]
