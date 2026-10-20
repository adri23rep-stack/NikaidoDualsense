"""Coordinación de actualizaciones para la ventana principal.

El motor de red vive en ``src.update_manager``; este mixin solo conecta sus
callbacks con señales Qt y mensajes de la interfaz.
"""

from __future__ import annotations

from typing import Any

class UpdateWindowMixin:
    def _auto_check_updates(self) -> None:
        manager = getattr(self, "update_manager", None)
        if manager and manager.should_auto_check():
            self.check_for_updates(manual=False)

    def check_for_updates(self, *, manual: bool = True) -> None:
        manager = getattr(self, "update_manager", None)
        if manager is None:
            if manual:
                self.toast("El sistema de actualizaciones no está disponible", "error")
            return
        self._update_manual_request = bool(manual)
        page = getattr(self, "settings_page", None)
        if page is not None and hasattr(page, "set_update_checking"):
            page.set_update_checking()
        manager.check_async(lambda result: self.bridge.update_checked.emit(result))

    def _update_checked(self, result: Any) -> None:
        manual = self._update_manual_request
        self._update_manual_request = False
        status = str(getattr(result, "status", "error") or "error")
        self._available_update = getattr(result, "update", None) if status == "available" else None
        page = getattr(self, "settings_page", None)
        if page is not None and hasattr(page, "set_update_result"):
            page.set_update_result(result)
        if status == "available" and self._available_update is not None:
            version = getattr(self._available_update, "version", "nueva")
            self.toast(f"Nikaido {version} está disponible", "info", 6500)
        elif manual:
            messages = {
                "current": "Nikaido ya está actualizado",
                "skipped": "Esa versión está omitida",
                "unconfigured": "Servidor de actualizaciones aún no configurado",
                "managed_externally": "Steam administra las actualizaciones de esta edición",
            }
            message = messages.get(status) or str(getattr(result, "message", "No se pudo buscar la actualización"))
            self.toast(message, "error" if status == "error" else "info", 5500)

    def skip_available_update(self) -> None:
        info = self._available_update
        if info is None or self.profile_manager is None:
            return
        version = str(getattr(info, "version", "") or "")
        if not version:
            return
        self.profile_manager.set_setting("updates.skipped_version", version)
        self.request_config_save()
        self._available_update = None
        page = getattr(self, "settings_page", None)
        if page is not None and hasattr(page, "set_update_skipped"):
            page.set_update_skipped(version)
        self.toast(f"Versión {version} omitida", "info")

    def restore_skipped_update(self) -> None:
        if self.profile_manager is None:
            return
        self.profile_manager.set_setting("updates.skipped_version", "")
        self.request_config_save()
        self.check_for_updates(manual=True)

    def download_available_update(self) -> None:
        manager = getattr(self, "update_manager", None)
        info = self._available_update
        if manager is None or info is None:
            self.toast("Primero busca una actualización disponible", "info")
            return
        page = getattr(self, "settings_page", None)
        if page is not None and hasattr(page, "set_update_downloading"):
            page.set_update_downloading()
        manager.download_async(
            info,
            lambda path, error: self.bridge.update_downloaded.emit(path, error),
            progress=lambda value: self.bridge.update_progress.emit(int(value)),
        )

    def _update_progress(self, value: int) -> None:
        page = getattr(self, "settings_page", None)
        if page is not None and hasattr(page, "set_update_progress"):
            page.set_update_progress(value)

    def _update_downloaded(self, path: Any, error: str) -> None:
        page = getattr(self, "settings_page", None)
        if error or path is None:
            if page is not None and hasattr(page, "set_update_error"):
                page.set_update_error(error or "No se completó la descarga")
            self.toast(error or "No se completó la descarga", "error", 7000)
            return
        manager = getattr(self, "update_manager", None)
        try:
            manager.launch_installer(path, self._available_update)
        except Exception as exc:
            if page is not None and hasattr(page, "set_update_error"):
                page.set_update_error(str(exc))
            self.toast(f"No se pudo abrir el instalador: {exc}", "error", 7000)
            return
        self.toast("Instalador verificado. Nikaido se cerrará para actualizar.", "success", 5000)
        self.call_later(1200, self.exit_app)
