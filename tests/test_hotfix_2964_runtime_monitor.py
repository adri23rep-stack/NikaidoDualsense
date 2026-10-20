"""Regresiones para rutas largas de PySide6 y métricas reales del Dashboard."""

from pathlib import Path

from src.runtime_bootstrap import choose_local_runtime, short_venv_python


ROOT = Path(__file__).resolve().parents[1]


def test_windows_prefers_short_runtime_over_nested_project_venv(tmp_path):
    local_app_data = tmp_path / "Local"
    short_python = local_app_data / "NKB" / "rt" / "Scripts" / "python.exe"
    short_python.parent.mkdir(parents=True)
    short_python.write_bytes(b"python")

    nested = tmp_path / "Downloads" / ("Nikaido-" + "x" * 90)
    old_python = nested / ".venv" / "Scripts" / "python.exe"
    old_python.parent.mkdir(parents=True)
    old_python.write_bytes(b"old")

    selected = choose_local_runtime(
        nested,
        platform_name="win32",
        executable=r"C:\Python310\python.exe",
        frozen=False,
        environ={"LOCALAPPDATA": str(local_app_data)},
    )
    assert selected == short_python


def test_explicit_runtime_directory_is_respected(tmp_path):
    runtime = tmp_path / "custom-runtime"
    python = runtime / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.write_bytes(b"python")
    environment = {"NIKAIDO_VENV_DIR": str(runtime)}

    assert short_venv_python(platform_name="win32", environ=environment) == python
    assert choose_local_runtime(
        tmp_path,
        platform_name="win32",
        executable=r"C:\Python310\python.exe",
        frozen=False,
        environ=environment,
    ) == python


def test_runtime_scripts_do_not_install_pyside_inside_downloads():
    install = (ROOT / "install.bat").read_text(encoding="utf-8")
    helper = (ROOT / "NIKAIDO_RUNTIME.bat").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements-runtime.txt").read_text(encoding="utf-8")

    assert 'python -m venv "%VENV_DIR%"' in install
    assert "python -m venv .venv" not in install
    assert "%LOCALAPPDATA%\\NKB" in helper
    assert 'set "TEMP=%NIKAIDO_SHORT_TEMP%"' in helper
    assert "PySide6>=6.8.3,<6.9" in requirements


def test_dashboard_uses_backend_metrics_instead_of_fake_ui_math():
    source = (ROOT / "gui" / "pages" / "dashboard.py").read_text(encoding="utf-8")

    assert 'connection.get("device_report_hz"' in source
    assert 'connection.get("pipeline_p95_ms"' in source
    assert 'emulator.get("virtual_hz"' in source
    assert 'connection.get("read_failures"' in source
    assert "self.graph.add_value(route_p95" in source
    assert "fps * 4" not in source
    assert "1000 / max(fps" not in source
    assert "self.graph.push(" not in source


def test_dashboard_metric_refresh_renders_measured_backend_values():
    from types import SimpleNamespace

    import pytest

    pytest.importorskip("PySide6")
    from gui.pages.dashboard import DashboardPage

    class TextSink:
        def __init__(self):
            self.text = ""

        def setText(self, value):
            self.text = str(value)

    class GraphSink:
        def __init__(self):
            self.values = []

        def add_value(self, value):
            self.values.append(float(value))

    class Process:
        def cpu_percent(self, _interval):
            return 3.25

        def memory_info(self):
            return SimpleNamespace(rss=150 * 1024 * 1024)

    emulator = SimpleNamespace(
        get_diagnostics_snapshot=lambda: {
            "active": True,
            "virtual_hz": 248.6,
        }
    )
    manager = SimpleNamespace(
        emulator=emulator,
        get_diagnostics_snapshot=lambda: {
            "connected": True,
            "total_polls": 200,
            "device_report_hz": 249.2,
            "pipeline_p95_ms": 1.234,
            "read_failures": 2,
        },
    )
    page = SimpleNamespace(
        window=SimpleNamespace(connection_manager=manager),
        metrics={key: TextSink() for key in ("poll", "lag", "fps", "cpu", "memory", "lost")},
        graph=GraphSink(),
        _process=Process(),
    )

    DashboardPage.update_system_metrics(page)

    assert page.metrics["poll"].text == "249 Hz"
    assert page.metrics["lag"].text == "1.23 ms"
    assert page.metrics["fps"].text == "249 Hz"
    assert page.metrics["cpu"].text == "3.2%"
    assert page.metrics["memory"].text == "150 MB"
    assert page.metrics["lost"].text == "2"
    assert page.graph.values == [1.234]
