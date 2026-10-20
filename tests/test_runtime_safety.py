import sys
from pathlib import Path

from src.crash_reporting import install_exception_hook, show_fatal_error
from src.single_instance import SingleInstance


def test_single_instance_blocks_second_lock(tmp_path):
    first = SingleInstance("NikaidoTest", str(tmp_path))
    second = SingleInstance("NikaidoTest", str(tmp_path))
    assert first.acquire() is True
    assert second.acquire() is False
    first.release()
    assert second.acquire() is True
    second.release()


def test_crash_hook_writes_bounded_local_report(tmp_path):
    original = sys.excepthook
    try:
        hook = install_exception_hook(tmp_path, app_version="test", keep=2)
        try:
            raise RuntimeError("boom")
        except RuntimeError as exc:
            hook(type(exc), exc, exc.__traceback__)
        reports = list(tmp_path.glob("crash_*.txt"))
        assert len(reports) == 1
        content = reports[0].read_text(encoding="utf-8")
        assert "Version: test" in content
        assert "RuntimeError: boom" in content
    finally:
        sys.excepthook = original


def test_crash_hook_also_captures_worker_exceptions(tmp_path):
    import threading
    from types import SimpleNamespace

    original_sys = sys.excepthook
    original_thread = threading.excepthook
    try:
        install_exception_hook(tmp_path, app_version="worker-test", keep=3)
        try:
            raise ValueError("worker boom")
        except ValueError as exc:
            args = SimpleNamespace(
                exc_type=type(exc),
                exc_value=exc,
                exc_traceback=exc.__traceback__,
                thread=SimpleNamespace(name="InputWorker"),
            )
            threading.excepthook(args)
        reports = list(tmp_path.glob("crash_*.txt"))
        assert len(reports) == 1
        content = reports[0].read_text(encoding="utf-8")
        assert "Hilo: InputWorker" in content
        assert "ValueError: worker boom" in content
    finally:
        sys.excepthook = original_sys
        threading.excepthook = original_thread


def test_windows_mutex_declares_handle_width_explicitly():
    source = (Path(__file__).resolve().parents[1] / "src" / "single_instance.py").read_text(encoding="utf-8")
    assert "create_mutex.restype = wintypes.HANDLE" in source
    assert "close_handle.argtypes = [wintypes.HANDLE]" in source
    assert "release_mutex.argtypes = [wintypes.HANDLE]" in source


def test_fatal_error_has_console_fallback(monkeypatch):
    import io
    import src.crash_reporting as crash_reporting

    stream = io.StringIO()
    monkeypatch.setattr(crash_reporting.os, "name", "posix")
    monkeypatch.setattr(crash_reporting.sys, "stderr", stream)
    assert show_fatal_error("fatal-test", title="Nikaido Test") is True
    assert "Nikaido Test: fatal-test" in stream.getvalue()
