"""Regresiones del hotfix 2.9.5.3 para elegir el Python correcto."""

from pathlib import Path

from src.runtime_bootstrap import (
    BOOTSTRAP_MARKER,
    bootstrap_local_venv,
    choose_local_runtime,
)


ROOT = Path(__file__).resolve().parents[1]


def _fake_windows_venv(tmp_path: Path) -> Path:
    target = tmp_path / ".venv" / "Scripts" / "python.exe"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"fake")
    (tmp_path / "main.py").write_text("print('nikaido')\n", encoding="utf-8")
    return target


def test_external_windows_python_selects_the_local_venv(tmp_path):
    target = _fake_windows_venv(tmp_path)
    selected = choose_local_runtime(
        tmp_path,
        platform_name="win32",
        executable=r"C:\\Python310\\python.exe",
        frozen=False,
        environ={},
    )
    assert selected == target


def test_process_already_inside_local_venv_is_not_restarted(tmp_path):
    target = _fake_windows_venv(tmp_path)
    selected = choose_local_runtime(
        tmp_path,
        platform_name="win32",
        executable=str(target),
        frozen=False,
        environ={},
    )
    assert selected is None


def test_bootstrap_forwards_arguments_and_marks_the_replacement(tmp_path):
    target = _fake_windows_venv(tmp_path)
    environment = {}
    calls = []

    assert bootstrap_local_venv(
        tmp_path,
        argv=[str(tmp_path / "main.py"), "--minimized", "--profile", "chat"],
        executable=r"C:\\Python310\\python.exe",
        environ=environment,
        platform_name="win32",
        execv=lambda executable, argv: calls.append((executable, list(argv))),
    )
    assert environment[BOOTSTRAP_MARKER] == "1"
    assert calls == [
        (
            str(target),
            [str(target), str(tmp_path / "main.py"), "--minimized", "--profile", "chat"],
        )
    ]


def test_marker_prevents_a_reexecution_loop(tmp_path):
    _fake_windows_venv(tmp_path)
    assert choose_local_runtime(
        tmp_path,
        platform_name="win32",
        executable=r"C:\\Python310\\python.exe",
        frozen=False,
        environ={BOOTSTRAP_MARKER: "1"},
    ) is None


def test_main_bootstraps_before_loading_normal_application_modules():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    call = "bootstrap_local_venv(Path(__file__).resolve().parent)"
    assert call in source
    assert source.index(call) < source.index("from nikaido_version import APP_NAME, APP_VERSION")


def test_safe_launcher_uses_the_short_runtime_and_repairs_dependencies_once():
    source = (ROOT / "INICIAR_NIKAIDO.bat").read_text(encoding="utf-8")
    helper = (ROOT / "NIKAIDO_RUNTIME.bat").read_text(encoding="utf-8")
    assert 'call "%~dp0NIKAIDO_RUNTIME.bat"' in source
    assert r'set "VENV_DIR=%NKB_HOME%\rt"' in helper
    assert r'"%VENV_PY%" "%CD%\main.py" %*' in source
    assert "check_runtime_dependencies.py" in source
    assert "-r requirements-runtime.txt" in source
    assert "--force-reinstall --no-cache-dir" not in source


def test_audio_missing_dependency_message_names_runtime_and_safe_launcher():
    source = (ROOT / "src" / "audio_manager.py").read_text(encoding="utf-8")
    assert "Path(sys.executable).resolve()" in source
    assert "INICIAR_NIKAIDO.bat" in source
