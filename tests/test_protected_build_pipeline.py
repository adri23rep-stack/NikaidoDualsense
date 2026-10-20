import os
from pathlib import Path

import pytest

import build_protected


def test_protected_pipeline_is_separate_from_normal_build():
    root = Path(build_protected.__file__).resolve().parent
    assert build_protected.RELEASE_PATH == root / "release_protected"

    configured = os.environ.get("NIKAIDO_PROTECTED_WORKDIR", "").strip()
    expected_work_root = (
        Path(configured).expanduser().resolve()
        if configured
        else root / ".nikaido_protected_build"
    )
    assert build_protected.BUILD_ROOT == expected_work_root
    assert build_protected.BUILD_ROOT != build_protected.RELEASE_PATH
    assert (root / "build.py").is_file()
    assert (root / "COMPILAR_NIKAIDO.bat").is_file()


def test_nuitka_command_compiles_owned_dynamic_packages(tmp_path, monkeypatch):
    monkeypatch.setattr(build_protected, "BUILD_ROOT", tmp_path / "work")
    monkeypatch.setattr(build_protected, "ENTRY_ROOT", tmp_path / "work" / "entry")
    monkeypatch.setattr(build_protected, "NUITKA_OUTPUT", tmp_path / "work" / "nuitka")
    monkeypatch.setattr(build_protected, "REPORT_PATH", tmp_path / "work" / "report.xml")

    command = build_protected.build_command(onefile=False, console=False, jobs=3)
    joined = "\n".join(command)

    assert "--mode=standalone" in command
    assert "--enable-plugins=pyside6" in command
    assert "--windows-console-mode=disable" in command
    assert "--include-package=gui" in command
    assert "--include-package=src" in command
    assert "--include-module=main" in command
    assert "--include-module=hid" in command
    assert "--include-package=pydualsense" in command
    assert "--include-data-dir=" in joined and "=assets" in joined
    assert "--jobs=3" in command


def test_temporary_entry_preserves_frozen_resource_behavior(tmp_path, monkeypatch):
    monkeypatch.setattr(build_protected, "ENTRY_ROOT", tmp_path / "entry")
    path = build_protected.write_protected_entry()
    source = path.read_text(encoding="utf-8")
    assert 'setattr(sys, "frozen", True)' in source
    assert 'setattr(sys, "_MEIPASS"' in source
    assert "from main import main" in source


def test_release_validation_rejects_source_or_bytecode(tmp_path, monkeypatch):
    release = tmp_path / "release_protected"
    app = release / "Nikaido"
    app.mkdir(parents=True)
    (app / "Nikaido.exe").write_bytes(b"native")
    (app / "qwindows.dll").write_bytes(b"qt")
    vigem = app / build_protected.VIGEM_X64_DLL_RELATIVE
    vigem.parent.mkdir(parents=True)
    vigem.write_bytes(b"vigem")
    monkeypatch.setattr(build_protected, "RELEASE_PATH", release)
    monkeypatch.setattr(build_protected, "APP_RELEASE_PATH", app)

    assert build_protected.validate_source_free_release(onefile=False)["source_files"] == 0

    leaked = app / "secret.pyc"
    leaked.write_bytes(b"bytecode")
    with pytest.raises(RuntimeError, match="código fuente/bytecode"):
        build_protected.validate_source_free_release(onefile=False)


def test_protected_installer_uses_protected_release():
    root = Path(build_protected.__file__).resolve().parent
    installer = (root / "installer" / "NikaidoProtected.iss").read_text(encoding="utf-8")
    assert "release_protected" in installer
    assert "Protected-Setup" in installer
    assert "LicenseFile=..\\EULA_NIKAIDO.txt" in installer
    assert "PrivilegesRequired=lowest" in installer


def test_normal_source_hashes_are_not_rewritten_by_pipeline_files():
    root = Path(build_protected.__file__).resolve().parent
    # El pipeline protegido se añade como archivos nuevos; no sustituye los
    # puntos de entrada ni el compilador normal.
    assert "Nuitka" not in (root / "build.py").read_text(encoding="utf-8")
    assert "nikaido_protected_entry" not in (root / "main.py").read_text(encoding="utf-8")


def test_protected_batch_uses_short_external_environment():
    root = Path(build_protected.__file__).resolve().parent
    batch = (root / "COMPILAR_NIKAIDO_PROTEGIDO.bat").read_text(encoding="utf-8")
    assert "%LOCALAPPDATA%\\NKB" in batch
    assert "NIKAIDO_PROTECTED_WORKDIR" in batch
    assert "requirements-protected.txt" in batch
    assert "Ejecuta primero install.bat" not in batch
    assert "%CD%\\.venv" not in batch


def test_protected_cleanup_does_not_delete_release_or_sources():
    root = Path(build_protected.__file__).resolve().parent
    cleanup = (root / "LIMPIAR_ENTORNO_PROTEGIDO.bat").read_text(encoding="utf-8")
    assert "%LOCALAPPDATA%\\NKB" in cleanup
    assert "release_protected" in cleanup
    assert 'rmdir /s /q "%NKB_HOME%"' in cleanup
    assert 'rmdir /s /q "%CD%"' not in cleanup

def test_protected_requirements_include_pytest_for_prebuild_suite():
    root = Path(build_protected.__file__).resolve().parent
    requirements = (root / "requirements-protected.txt").read_text(encoding="utf-8")
    assert "pytest>=8,<10" in requirements


def test_protected_batch_preflights_pytest_before_running_suite():
    root = Path(build_protected.__file__).resolve().parent
    batch = (root / "COMPILAR_NIKAIDO_PROTEGIDO.bat").read_text(encoding="utf-8")
    assert 'import pytest' in batch
    assert 'pip install --prefer-binary --disable-pip-version-check "pytest>=8,<10"' in batch
    assert batch.index('import pytest') < batch.index('-m pytest -q')



def test_protected_installer_batch_reuses_existing_build_without_recompile():
    root = Path(build_protected.__file__).resolve().parent
    batch = (root / "CREAR_INSTALADOR_PROTEGIDO.bat").read_text(encoding="utf-8")
    assert "release_protected\\Nikaido\\Nikaido.exe" in batch
    assert "%LOCALAPPDATA%\\NKB" in batch
    assert "build_protected.py --installer-only" in batch
    assert "-m pytest" not in batch
    assert "requirements-protected.txt" not in batch
    assert "build_protected.py --installer\n" not in batch


def test_installer_only_cli_is_available():
    source = (Path(build_protected.__file__).resolve()).read_text(encoding="utf-8")
    assert '"--installer-only"' in source
    assert "build_windows_installer()" in source


def test_vgamepad_runtime_is_copied_to_expected_ctypes_path(tmp_path, monkeypatch):
    package = tmp_path / "site-packages" / "vgamepad"
    source = package / "win" / "vigem" / "client" / "x64" / "ViGEmClient.dll"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"vigem-client")
    x86 = package / "win" / "vigem" / "client" / "x86" / "ViGEmClient.dll"
    x86.parent.mkdir(parents=True)
    x86.write_bytes(b"vigem-client-x86")
    monkeypatch.setattr(build_protected, "_package_directory", lambda name: package)

    release_app = tmp_path / "release" / "Nikaido"
    copied = build_protected.copy_vgamepad_runtime_binaries(release_app)

    expected = release_app / build_protected.VIGEM_X64_DLL_RELATIVE
    assert expected.read_bytes() == b"vigem-client"
    assert any(path.name == "ViGEmClient.dll" for path in copied)
    monkeypatch.setattr(build_protected, "APP_RELEASE_PATH", release_app)
    assert build_protected.validate_required_runtime_files(onefile=False)["vigem_client_x64"]


def test_repair_runtime_batch_reuses_existing_compilation():
    root = Path(build_protected.__file__).resolve().parent
    batch = (root / "REPARAR_RUNTIME_PROTEGIDO.bat").read_text(encoding="utf-8")
    assert "build_protected.py --repair-runtime-only" in batch
    assert "COMPILAR_NIKAIDO_PROTEGIDO.bat" in batch
    assert r"release_protected\Nikaido\Nikaido.exe" in batch
    assert "-m nuitka" not in batch


def test_repair_runtime_cli_and_vigem_validation_are_present():
    source = Path(build_protected.__file__).read_text(encoding="utf-8")
    assert '"--repair-runtime-only"' in source
    assert "copy_vgamepad_runtime_binaries(APP_RELEASE_PATH)" in source
    assert "VIGEM_X64_DLL_RELATIVE" in source
