from pathlib import Path

import pytest

import build


def test_build_uses_hidden_workdir_and_release_output():
    source = Path(build.__file__).read_text(encoding="utf-8")
    assert 'WORK_ROOT = ROOT / ".nikaido_build"' in source
    assert 'RELEASE_PATH = ROOT / "release"' in source
    assert '"--workpath"' in source
    assert '"--distpath"' in source
    assert '"--contents-directory"' in source
    assert '"_internal"' in source


def test_onedir_validation_requires_complete_python_runtime(tmp_path, monkeypatch):
    release = tmp_path / "release"
    app = release / "Nikaido"
    internal = app / "_internal"
    internal.mkdir(parents=True)
    (app / "Nikaido.exe").write_bytes(b"exe")
    monkeypatch.setattr(build, "RELEASE_PATH", release)

    with pytest.raises(RuntimeError, match="python3xx.dll"):
        build.validate_release_layout(onefile=False)

    (internal / "python310.dll").write_bytes(b"runtime")
    with pytest.raises(RuntimeError, match="backend HID"):
        build.validate_release_layout(onefile=False)

    (internal / "hid.cp310-win_amd64.pyd").write_bytes(b"hid")
    with pytest.raises(RuntimeError, match="qwindows.dll"):
        build.validate_release_layout(onefile=False)

    platforms = internal / "PySide6" / "plugins" / "platforms"
    platforms.mkdir(parents=True)
    (platforms / "qwindows.dll").write_bytes(b"qt")
    assert build.validate_release_layout(onefile=False) == app / "Nikaido.exe"


def test_release_helpers_point_only_to_valid_executable(tmp_path, monkeypatch):
    release = tmp_path / "release"
    release.mkdir()
    monkeypatch.setattr(build, "RELEASE_PATH", release)

    helpers = build.write_release_helpers(onefile=False)
    readme = (release / "LEEME_PRIMERO.txt").read_text(encoding="utf-8")
    launcher = (release / "ABRIR_NIKAIDO.bat").read_text(encoding="utf-8")

    assert len(helpers) == 2
    assert r"Nikaido\Nikaido.exe" in readme
    assert r"%~dp0Nikaido\Nikaido.exe" in launcher
    assert "No ejecutes archivos desde build" in readme


def test_build_collects_pydualsense_and_native_hid_backend():
    source = Path(build.__file__).read_text(encoding="utf-8")
    assert 'command.extend(["--collect-all", "pydualsense"])' in source
    assert '"pydualsense.hidguardian"' in source
    assert '"hid"' in source
    assert '"src.hid_backend"' in source
    assert 'internal.rglob("hid*.pyd")' in source


def test_build_embeds_version_metadata_and_runtime_safety_modules(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "WORK_ROOT", tmp_path / "work")
    version_file = build.write_version_info()
    content = version_file.read_text(encoding="utf-8")
    assert build.APP_VERSION in content
    assert "Nikaido DualSense Control Center" in content

    source = Path(build.__file__).read_text(encoding="utf-8")
    for module in ("src.appearance", "src.edit_history", "src.single_instance", "src.crash_reporting"):
        assert f'"{module}"' in source


def test_release_manifest_contains_executable_hash(tmp_path, monkeypatch):
    release = tmp_path / "release"
    app_dir = release / "Nikaido"
    app_dir.mkdir(parents=True)
    executable = app_dir / "Nikaido.exe"
    executable.write_bytes(b"nikaido-test-executable")
    (app_dir / "support.dll").write_bytes(b"support")
    monkeypatch.setattr(build, "RELEASE_PATH", release)

    manifest_path = build.write_release_manifest(onefile=False, executable=executable)
    import json

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["version"] == build.APP_VERSION
    assert manifest["executable"] == "Nikaido/Nikaido.exe"
    assert len(manifest["executable_sha256"]) == 64
    assert manifest["files"] == 2
    assert len(manifest["file_hashes"]) == 2
    assert {item["path"] for item in manifest["file_hashes"]} == {
        "Nikaido/Nikaido.exe",
        "Nikaido/support.dll",
    }
    assert all(len(item["sha256"]) == 64 for item in manifest["file_hashes"])


def test_bundled_runtime_self_test_covers_dynamic_tray_icon():
    build_source = Path(build.__file__).read_text(encoding="utf-8")
    main_source = (Path(build.__file__).resolve().parent / "main.py").read_text(encoding="utf-8")

    assert '"tray_imported": False' in main_source
    assert '"tray_backend_imported": False' in main_source
    assert '"tray_icon_rendered": False' in main_source
    assert '"audio_imported": False' in main_source
    assert "pystray._win32" in main_source
    assert 'command.extend(["--collect-all", "pystray"])' in build_source
    assert 'command.extend(["--collect-all", "pycaw"])' in build_source
    assert 'command.extend(["--collect-all", "comtypes"])' in build_source
    assert "TrayManager" in main_source
    assert "el icono dinámico de batería no pudo renderizarse" in main_source
    assert "El EXE no pudo cargar o renderizar la bandeja con batería" in build_source
    assert "El EXE no pudo cargar pycaw/comtypes" in build_source


def test_25_installer_is_optional_and_uses_validated_onedir_source():
    source = Path(build.__file__).read_text(encoding="utf-8")
    installer = Path(build.__file__).resolve().parent / "installer" / "Nikaido.iss"
    content = installer.read_text(encoding="utf-8")
    assert '"--installer"' in source
    assert "def build_windows_installer" in source
    assert 'source_dir = RELEASE_PATH / "Nikaido"' in source
    assert 'Source: "{#SourceDir}\\*"' in content
    assert "Nikaido_DualSense-{#MyAppVersion}-Setup" in content
    assert "LicenseFile=..\\EULA_NIKAIDO.txt" in content
    assert "PrivilegesRequired=lowest" in content
    assert "DefaultDirName={localappdata}\\Programs\\Nikaido DualSense" in content
    assert "PrivilegesRequired=admin" not in content


def test_25_runtime_modules_are_explicitly_collected():
    source = Path(build.__file__).read_text(encoding="utf-8")
    for module in ("src.virtual_feedback", "src.game_profile_watcher", "src.hidhide_manager"):
        assert f'"{module}"' in source



def test_developer_install_uses_short_isolated_virtual_environment():
    root = Path(build.__file__).resolve().parent
    script = (root / "install.bat").read_text(encoding="utf-8")
    helper = (root / "NIKAIDO_RUNTIME.bat").read_text(encoding="utf-8")
    assert 'call "%~dp0NIKAIDO_RUNTIME.bat"' in script
    assert 'python -m venv "%VENV_DIR%"' in script
    assert '"%VENV_PY%" -m pip install --prefer-binary --disable-pip-version-check -r requirements.txt' in script
    assert r"%LOCALAPPDATA%\NKB" in helper
    assert r'set "VENV_DIR=%NKB_HOME%\rt"' in helper
    assert "python -m venv .venv" not in script
    assert "Intenta ejecutar como Administrador" not in script
