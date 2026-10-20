"""Ciclo de vida ligero para crear, destruir y reconstruir la interfaz Qt."""

from __future__ import annotations

import gc
import logging
import sys
from typing import Any, Callable, Dict, List, Optional, Type

from .ui_common import QApplication, QObject, QPixmapCache, QTimer, Signal

logger = logging.getLogger(__name__)


class GuiLifecycleBridge(QObject):
    """Puente persistente para acciones que llegan desde el hilo de pystray."""

    show_requested = Signal()
    exit_requested = Signal()
    profile_requested = Signal(str)
    low_profile_requested = Signal()


class LowProfileGuiRuntime(QObject):
    """Mantiene motores vivos mientras la ventana completa deja de existir."""

    def __init__(
        self,
        window_factory: Type[Any],
        backends: Dict[str, Any],
    ) -> None:
        app = QApplication.instance() or QApplication(sys.argv)
        super().__init__()
        self.app = app
        self.app.setApplicationName("Nikaido")
        self.app.setOrganizationName("Team Nikaido")
        self.app.setQuitOnLastWindowClosed(False)
        self._window_factory = window_factory
        self._backends = dict(backends)
        self._close_callbacks: List[Callable[[], None]] = []
        self._stopped = False
        self._low_profile_active = False
        self.window: Optional[Any] = None
        self.root: Optional[Any] = None
        self._lifecycle = GuiLifecycleBridge(self)
        self._lifecycle.show_requested.connect(self._show_or_rebuild)
        self._lifecycle.exit_requested.connect(self._exit_from_qt)
        self._lifecycle.profile_requested.connect(self._select_profile_from_qt)
        self._lifecycle.low_profile_requested.connect(self._schedule_low_profile)
        self._create_window()

    def _create_window(self) -> Any:
        if self.window is not None:
            return self.window
        backends = dict(self._backends)
        backends["low_profile_handler"] = self.enter_low_profile
        window = self._window_factory(**backends)
        for callback in self._close_callbacks:
            window.on_close(callback)
        self.window = window
        self.root = window
        self._low_profile_active = False
        tray = self._backends.get("tray_manager")
        if tray is not None:
            setter = getattr(tray, "set_low_profile", None)
            if callable(setter):
                setter(False)
        return window

    def run(self) -> None:
        self._create_window().show()
        self.app.exec()

    def start(self) -> None:
        self.run()

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        window, self.window = self.window, None
        self.root = None
        if window is not None:
            window.stop()
        self.app.quit()

    def _schedule_low_profile(self) -> None:
        if self._stopped or self._low_profile_active:
            return
        QTimer.singleShot(0, self._enter_low_profile_now)

    def enter_low_profile(self) -> None:
        """Solicitud segura desde Qt o desde el hilo del icono de bandeja."""
        self._lifecycle.low_profile_requested.emit()

    def _enter_low_profile_now(self) -> None:
        if self._stopped or self._low_profile_active:
            return
        tray = self._backends.get("tray_manager")
        if tray is None or not getattr(tray, "is_visible", lambda: False)():
            if self.window is not None:
                self.window.showMinimized()
            return

        old_window, self.window = self.window, None
        self.root = None
        if old_window is None:
            return
        old_window.stop()
        self._low_profile_active = True
        setter = getattr(tray, "set_low_profile", None)
        if callable(setter):
            setter(True)
        notifier = getattr(tray, "notify_low_profile", None)
        if callable(notifier):
            notifier()
        QTimer.singleShot(150, self._release_ui_memory)

    def _release_ui_memory(self) -> None:
        if not self._low_profile_active or self.window is not None:
            return
        QPixmapCache.clear()
        gc.collect()

    def hide_window(self) -> None:
        pm = self._backends.get("profile_manager")
        tray = self._backends.get("tray_manager")
        low_profile = bool(
            pm and pm.get_setting("low_profile_on_minimize", True)
            and tray and getattr(tray, "is_visible", lambda: False)()
        )
        if low_profile:
            self.enter_low_profile()
        elif self.window is not None:
            self.window.hide_window()

    def show_window(self) -> None:
        self._lifecycle.show_requested.emit()

    def _show_or_rebuild(self) -> None:
        if self._stopped:
            return
        self._create_window().show_window()

    def exit_app(self) -> None:
        self._lifecycle.exit_requested.emit()

    def _exit_from_qt(self) -> None:
        if self._stopped:
            return
        if self.window is not None:
            self.window.exit_app()
            return
        for callback in list(self._close_callbacks):
            try:
                callback()
            except Exception:
                logger.exception("Error cerrando Nikaido desde Low Profile")
        if not self._stopped:
            self.stop()

    def select_profile(self, profile_id: str) -> None:
        self._lifecycle.profile_requested.emit(str(profile_id))

    def _select_profile_from_qt(self, profile_id: str) -> None:
        if self.window is not None:
            self.window.apply_profile(str(profile_id))
            return
        trigger_engine = self._backends.get("trigger_engine")
        apply_profile = getattr(trigger_engine, "apply_profile", None)
        if not callable(apply_profile):
            return
        success = bool(apply_profile(str(profile_id)))
        profile_manager = self._backends.get("profile_manager")
        if success and profile_manager is not None:
            profile_manager.set_active_profile(str(profile_id))
            profile_manager.save_config()

    def on_close(self, callback: Callable[[], None]) -> None:
        if callback not in self._close_callbacks:
            self._close_callbacks.append(callback)
        if self.window is not None:
            self.window.on_close(callback)

    def call_later(self, ms: int, callback: Callable[[], None]) -> None:
        if self.window is not None:
            self.window.call_later(ms, callback)
        else:
            QTimer.singleShot(max(0, int(ms)), callback)
