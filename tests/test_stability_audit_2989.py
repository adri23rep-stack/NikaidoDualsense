"""Regresiones de la auditoría de estabilidad 2.9.8.9."""

from __future__ import annotations

import gc
import importlib
import os
import sys
import weakref
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _qt():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

    return QApplication, QCoreApplication, QEvent, QLabel, QPushButton, QWidget


def test_all_main_runtime_modules_import() -> None:
    modules = {"main", "nikaido_version"}
    for package in ("src", "gui"):
        for path in (ROOT / package).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            relative = path.relative_to(ROOT).with_suffix("")
            parts = list(relative.parts)
            if parts[-1] == "__init__":
                parts.pop()
            modules.add(".".join(parts))

    failures = {}
    for module_name in sorted(modules):
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - solo aparece en regresión
            failures[module_name] = f"{type(exc).__name__}: {exc}"
    assert not failures


def test_callback_subscriptions_are_idempotently_releasable() -> None:
    from src.connection_manager import ConnectionManager
    from src.system_tray import TrayManager
    from src.trigger_engine import TriggerEngine

    manager = ConnectionManager()
    engine = TriggerEngine(manager)
    tray = TrayManager()
    initial_state_callbacks = len(manager._on_state_update)

    disconnect = manager.on_disconnect(lambda: None)
    profile = engine.on_profile_change(lambda _profile_id: None)
    show = tray.on_show_window(lambda: None)
    assert len(manager._on_disconnect) == 1
    assert len(engine._on_profile_change) == 1
    assert len(tray._on_show_window) == 1

    for unsubscribe in (disconnect, profile, show):
        unsubscribe()
        unsubscribe()
    assert manager._on_disconnect == []
    assert engine._on_profile_change == []
    assert tray._on_show_window == []

    engine.stop()
    assert len(manager._on_state_update) == initial_state_callbacks - 1
    manager.stop()


def test_three_real_qt_window_cycles_release_callbacks_and_widgets(tmp_path) -> None:
    QApplication, QCoreApplication, QEvent, _QLabel, _QPushButton, _QWidget = _qt()
    from gui.main_window import NikaidoWindow
    from src.connection_manager import ConnectionManager
    from src.profile_manager import ProfileManager
    from src.trigger_engine import TriggerEngine

    app = QApplication.instance() or QApplication([])
    profile_manager = ProfileManager(config_dir=str(tmp_path / "config"))
    profile_manager.set_setting("onboarding.completed", True)
    profile_manager.set_setting("onboarding.version", 6)
    manager = ConnectionManager()
    engine = TriggerEngine(manager)
    baseline_callbacks = (
        len(manager._on_connect),
        len(manager._on_disconnect),
        len(manager._on_battery_change),
        len(manager._on_state_update),
        len(manager._on_error),
        len(engine._on_profile_change),
    )
    baseline_top_levels = len(app.topLevelWidgets())
    references = []

    try:
        for _cycle in range(3):
            window = NikaidoWindow(
                connection_manager=manager,
                trigger_engine=engine,
                profile_manager=profile_manager,
            )
            window.navigate("profiles")
            assert window.profiles_page is not None
            app.processEvents()
            references.append(weakref.ref(window))

            window.stop()
            # Limitar el envío al receptor de esta prueba evita procesar
            # deleteLater pendientes que pertenecen a otros tests Qt.
            QCoreApplication.sendPostedEvents(
                window, QEvent.Type.DeferredDelete
            )
            window = None
            for _ in range(4):
                app.processEvents()
                gc.collect()

            current_callbacks = (
                len(manager._on_connect),
                len(manager._on_disconnect),
                len(manager._on_battery_change),
                len(manager._on_state_update),
                len(manager._on_error),
                len(engine._on_profile_change),
            )
            assert current_callbacks == baseline_callbacks
            assert len(app.topLevelWidgets()) == baseline_top_levels
            assert all(reference() is None for reference in references)
    finally:
        engine.stop()
        manager.stop()


def test_profile_studio_reports_button_exceptions(monkeypatch) -> None:
    QApplication, _QCoreApplication, _QEvent, _QLabel, QPushButton, QWidget = _qt()
    from tests.test_hotfix_2986_profile_editor_actions import _fake_window
    import gui.pages.profiles as profiles_module

    app = QApplication.instance() or QApplication([])
    window = _fake_window(QWidget)
    page = profiles_module.ProfilesPage(window)

    class BrokenEditor:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("editor-test")

    monkeypatch.setattr(profiles_module, "ProfileEditorDialog", BrokenEditor)
    new_button = next(
        button
        for button in page.findChildren(QPushButton)
        if "Nuevo perfil" in button.text()
    )
    new_button.click()
    app.processEvents()
    assert any(
        kind == "alert" and "No se pudo crear el perfil" in message
        for kind, message in window.messages
    )
    page.deleteLater()
    app.processEvents()


def test_all_eight_builtin_profiles_apply_without_hardware() -> None:
    from src.profile_catalog import ordered_builtin_ids
    from src.trigger_engine import TriggerEngine

    engine = TriggerEngine()
    profile_ids = ordered_builtin_ids()
    assert len(profile_ids) == 8
    for profile_id in profile_ids:
        assert engine.get_profile(profile_id) is not None
        assert engine.apply_profile(profile_id) is True
        assert engine.get_current_profile() == profile_id
    engine.stop()


def test_dashboard_falls_back_for_corrupt_image(tmp_path) -> None:
    QApplication, _QCoreApplication, _QEvent, QLabel, _QPushButton, _QWidget = _qt()
    from gui.pages.dashboard import DashboardPage
    from gui.profile_visuals import fallback_glyph

    app = QApplication.instance() or QApplication([])
    corrupt = tmp_path / "corrupt.png"
    corrupt.write_bytes(b"not-a-real-image")
    profile = SimpleNamespace(
        name="Perfil con imagen dañada",
        category="Personal",
        icon="theme:custom",
        icon_path=str(corrupt),
        image_path=str(corrupt),
    )
    holder = SimpleNamespace(profile_icon=QLabel())
    DashboardPage._set_profile_image(holder, "custom_corrupt", profile)
    assert holder.profile_icon.text() == fallback_glyph("custom_corrupt", profile)
    assert holder.profile_icon.pixmap().isNull()
    holder.profile_icon.deleteLater()
    app.processEvents()


def test_shutdown_persists_remaining_state_after_one_export_fails() -> None:
    from main import DualSenseApp

    class ProfileManager:
        def __init__(self):
            self.settings = {}
            self.custom_profiles = None
            self.saved = 0

        def set_macros(self, _value):
            raise AssertionError("el exportador roto no debe llegar aquí")

        def set_setting(self, key, value):
            self.settings[key] = value

        def set_custom_profiles(self, value):
            self.custom_profiles = value

        def save_config(self):
            self.saved += 1
            return True

    class BrokenMacros:
        def export_macros(self):
            raise RuntimeError("macro-export-test")

        def stop(self):
            return None

    class Trigger:
        def export_vibration_overrides(self):
            return {"vibration": True}

        def export_gyro_overrides(self):
            return {"gyro": True}

        def export_profile_overrides(self):
            return {"builtin": True}

        def export_custom_profiles_to_dict(self):
            return {"custom": {"name": "Custom"}}

        def stop(self):
            return None

    app = DualSenseApp(SimpleNamespace())
    app.profile_manager = ProfileManager()
    app.macro_engine = BrokenMacros()
    app.trigger_engine = Trigger()
    app.shutdown()

    assert app.profile_manager.saved == 1
    assert app.profile_manager.custom_profiles == {"custom": {"name": "Custom"}}
    assert app.profile_manager.settings["profile_overrides"] == {"builtin": True}
    assert app.profile_manager.settings["profile_gyro"] == {"gyro": True}


def test_noninteractive_gui_startup_failure_is_rethrown(monkeypatch) -> None:
    from main import DualSenseApp
    import gui.modern_app as modern_app
    import main as main_module

    class BrokenGUI:
        def __init__(self, **_backends):
            raise RuntimeError("qt-start-test")

    monkeypatch.setattr(modern_app, "DualSenseGUI", BrokenGUI)
    monkeypatch.setattr(
        main_module.sys,
        "stdin",
        SimpleNamespace(isatty=lambda: False),
    )
    app = DualSenseApp(SimpleNamespace(minimized=False))
    with pytest.raises(RuntimeError, match="interfaz gráfica"):
        app._run_gui_mode()
    assert app._shutdown_started is True


def test_crash_hook_survives_an_unwritable_report_directory(monkeypatch, tmp_path) -> None:
    import threading
    import src.crash_reporting as crash_reporting

    original_sys = sys.excepthook
    original_thread = threading.excepthook

    def denied(*_args, **_kwargs):
        raise PermissionError("read-only-test")

    monkeypatch.setattr(crash_reporting.Path, "mkdir", denied)
    try:
        hook = crash_reporting.install_exception_hook(
            tmp_path / "blocked", app_version="test"
        )
        assert callable(hook)
    finally:
        sys.excepthook = original_sys
        threading.excepthook = original_thread


def test_launchers_separate_dependencies_from_project_imports() -> None:
    checker = (ROOT / "tools" / "check_runtime_dependencies.py").read_text(
        encoding="utf-8"
    )
    assert "from gui" not in checker
    assert "from src" not in checker

    for filename in ("INICIAR_NIKAIDO.bat", "install.bat", "REPARAR_GUI_Y_AUDIO.bat"):
        source = (ROOT / filename).read_text(encoding="utf-8")
        dependency_check = source.index("check_runtime_dependencies.py")
        project_check = source.index("from gui.modern_app import DualSenseGUI")
        assert dependency_check < project_check
        assert ":dependency_error" in source
        assert ":source_error" in source
