"""Bandeja del sistema de Nikaido.

Mantiene Nikaido accesible junto al reloj de Windows y convierte el icono en
un indicador útil del DualSense: conexión, batería, carga y perfil activo.
La bandeja vive en su propio hilo; nunca toca Qt directamente.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Dict, List, Optional, Tuple

try:
    from PIL import Image, ImageDraw

    PIL_AVAILABLE = True
except ImportError:  # pragma: no cover - Pillow es dependencia normal
    Image = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]
    PIL_AVAILABLE = False

try:
    import pystray

    PYSTRAY_AVAILABLE = True
    PYSTRAY_IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - la bandeja es un componente opcional
    pystray = None  # type: ignore[assignment]
    PYSTRAY_AVAILABLE = False
    PYSTRAY_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

logger = logging.getLogger(__name__)


class TrayManager:
    """Gestiona el icono, tooltip y menú de la bandeja de Windows."""

    _ICON_SIZE = 64

    def __init__(self, app_name: str = "Nikaido DualSense") -> None:
        self.app_name = app_name
        self.icon: Optional["pystray.Icon"] = None
        self._thread: Optional[threading.Thread] = None
        self._visible = False
        self._lock = threading.RLock()
        self._lifecycle_lock = threading.RLock()

        self._status_text = "Desconectado"
        self._connected = False
        self._battery_level: Optional[int] = None
        self._charging = False
        self._battery_text = "Batería no disponible"
        self._profile_text = ""
        self._last_icon_key: Optional[Tuple[bool, Optional[int], bool]] = None
        self._image_cache: Dict[Tuple[bool, Optional[int], bool, int, int], "Image.Image"] = {}
        self._minimize_notice_shown = False
        self._low_profile_notice_shown = False
        self._low_profile_active = False

        self._on_show_window: List[Callable[[], None]] = []
        self._on_exit: List[Callable[[], None]] = []
        self._on_profile_select: List[Callable[[str], None]] = []
        self._on_low_profile: List[Callable[[], None]] = []

        self._profiles: List[tuple[str, str]] = []
        self._current_profile: Optional[str] = None

    # ===== Callbacks =====

    def _add_callback(self, bucket: list, callback: Callable[..., None]) -> Callable[[], None]:
        if not callable(callback):
            raise TypeError("El callback debe ser invocable")
        with self._lock:
            if callback not in bucket:
                bucket.append(callback)

        def unsubscribe() -> None:
            with self._lock:
                bucket[:] = [item for item in bucket if item != callback]

        return unsubscribe

    def _notify_callbacks(self, bucket: list, *args) -> None:
        with self._lock:
            callbacks = list(bucket)
        failed: list[Callable[..., None]] = []
        for callback in callbacks:
            try:
                callback(*args)
            except Exception:
                logger.exception("Callback de bandeja desactivado tras fallar")
                failed.append(callback)
        if failed:
            with self._lock:
                bucket[:] = [callback for callback in bucket if callback not in failed]

    def on_show_window(self, callback: Callable[[], None]) -> Callable[[], None]:
        return self._add_callback(self._on_show_window, callback)

    def on_exit(self, callback: Callable[[], None]) -> Callable[[], None]:
        return self._add_callback(self._on_exit, callback)

    def on_profile_select(
        self, callback: Callable[[str], None]
    ) -> Callable[[], None]:
        return self._add_callback(self._on_profile_select, callback)

    def on_low_profile(self, callback: Callable[[], None]) -> Callable[[], None]:
        return self._add_callback(self._on_low_profile, callback)

    # ===== Estado =====

    def set_status(self, text: str) -> None:
        """Actualiza conexión, tooltip, menú e icono visual."""
        clean = str(text or "Desconectado").strip()
        lowered = clean.casefold()
        with self._lock:
            self._status_text = clean
            self._connected = lowered.startswith("conectado") and not lowered.startswith(
                "desconectado"
            )
            if not self._connected:
                self._battery_level = None
                self._charging = False
                self._battery_text = "Batería no disponible"
        self._refresh_visuals(rebuild_menu=True)

    def set_battery(self, level: int, charging: bool = False) -> None:
        """Actualiza el indicador de batería mostrado en icono, menú y tooltip."""
        try:
            normalized = max(0, min(100, int(level)))
        except (TypeError, ValueError, OverflowError):
            normalized = 0
        with self._lock:
            self._battery_level = normalized
            self._charging = bool(charging)
            self._battery_text = (
                f"Cargando · {normalized}%" if self._charging else f"Batería · {normalized}%"
            )
        self._refresh_visuals(rebuild_menu=True)

    def set_current_profile(self, profile_id: Optional[str]) -> None:
        with self._lock:
            self._current_profile = profile_id
            self._profile_text = next(
                (name for pid, name in self._profiles if pid == profile_id), ""
            )
        self._refresh_visuals(rebuild_menu=True, update_icon=False)

    def set_low_profile(self, active: bool) -> None:
        with self._lock:
            self._low_profile_active = bool(active)
        self._refresh_visuals(rebuild_menu=True, update_icon=False)

    def set_profiles(self, profiles: List[tuple[str, str]]) -> None:
        with self._lock:
            self._profiles = list(profiles)
            self._profile_text = next(
                (name for pid, name in self._profiles if pid == self._current_profile),
                "",
            )
        self._refresh_visuals(rebuild_menu=True, update_icon=False)

    # ===== Render del icono =====

    @staticmethod
    def _battery_color(
        level: Optional[int], charging: bool, connected: bool
    ) -> tuple[int, int, int, int]:
        if not connected or level is None:
            return (104, 115, 140, 255)
        if charging:
            return (67, 215, 239, 255)
        if level <= 20:
            return (255, 94, 116, 255)
        if level <= 45:
            return (241, 200, 77, 255)
        return (84, 214, 123, 255)

    def _create_icon_image(
        self,
        width: int = 64,
        height: int = 64,
        *,
        battery_level: Optional[int] = None,
        charging: bool = False,
        connected: bool = True,
    ) -> "Image.Image":
        """Crea el logo Nikaido con un medidor de batería legible en 16 px."""
        if not PIL_AVAILABLE:
            raise RuntimeError("Pillow no está disponible para crear el icono")

        key = (bool(connected), battery_level, bool(charging), int(width), int(height))
        cached = self._image_cache.get(key)
        if cached is not None:
            return cached.copy()

        scale_x = width / 64.0
        scale_y = height / 64.0

        def point(x: float, y: float) -> tuple[int, int]:
            return (round(x * scale_x), round(y * scale_y))

        def box(x1: float, y1: float, x2: float, y2: float) -> list[int]:
            return [
                round(x1 * scale_x),
                round(y1 * scale_y),
                round(x2 * scale_x),
                round(y2 * scale_y),
            ]

        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        color = self._battery_color(battery_level, charging, connected)

        # Base Nikaido. El borde se convierte en un indicador rápido del estado.
        draw.rounded_rectangle(
            box(1, 1, 62, 62),
            radius=max(4, round(14 * min(scale_x, scale_y))),
            fill=(12, 18, 35, 255),
            outline=color,
            width=max(1, round(3 * min(scale_x, scale_y))),
        )

        opacity = 255 if connected else 115
        draw.polygon(
            [point(12, 47), point(12, 14), point(24, 22), point(24, 35)],
            fill=(72, 217, 239, opacity),
        )
        draw.polygon(
            [point(25, 22), point(38, 40), point(38, 48), point(25, 35)],
            fill=(123, 63, 242, opacity),
        )
        draw.polygon(
            [point(39, 40), point(39, 14), point(50, 9), point(50, 48)],
            fill=(211, 64, 244, opacity),
        )

        # Badge de batería. La forma y el relleno siguen siendo reconocibles
        # incluso cuando Windows reduce el icono a 16×16.
        battery_outer = box(31, 40, 58, 59)
        draw.rounded_rectangle(
            battery_outer,
            radius=max(2, round(4 * min(scale_x, scale_y))),
            fill=(8, 12, 24, 245),
            outline=(240, 244, 255, 245),
            width=max(1, round(2 * min(scale_x, scale_y))),
        )
        draw.rectangle(box(58, 46, 61, 53), fill=(240, 244, 255, 245))

        if connected and battery_level is not None:
            ratio = max(0.0, min(1.0, battery_level / 100.0))
            fill_left, fill_top, fill_right, fill_bottom = box(34, 43, 55, 56)
            available = max(0, fill_right - fill_left)
            filled = round(available * ratio)
            if filled > 0:
                draw.rounded_rectangle(
                    [fill_left, fill_top, fill_left + filled, fill_bottom],
                    radius=max(1, round(2 * min(scale_x, scale_y))),
                    fill=color,
                )
            if charging:
                draw.polygon(
                    [
                        point(45, 42),
                        point(39, 50),
                        point(44, 50),
                        point(41, 57),
                        point(51, 47),
                        point(46, 47),
                    ],
                    fill=(255, 255, 255, 255),
                )
        elif connected:
            # El control acaba de conectar pero aún no llegó el primer informe
            # de batería. Dejamos el medidor vacío en vez de marcar un error.
            draw.ellipse(box(43, 48, 47, 52), fill=(160, 170, 194, 255))
        else:
            draw.line(
                [point(35, 44), point(54, 56)],
                fill=(255, 94, 116, 255),
                width=max(2, round(3 * min(scale_x, scale_y))),
            )

        self._image_cache[key] = image.copy()
        # El número de combinaciones reales es pequeño, pero evitamos que una
        # fuente de batería defectuosa haga crecer la caché indefinidamente.
        if len(self._image_cache) > 64:
            oldest = next(iter(self._image_cache))
            self._image_cache.pop(oldest, None)
        return image

    def _current_icon_image(self) -> Optional["Image.Image"]:
        if not PIL_AVAILABLE:
            return None
        with self._lock:
            level = self._battery_level
            charging = self._charging
            connected = self._connected
        return self._create_icon_image(
            self._ICON_SIZE,
            self._ICON_SIZE,
            battery_level=level,
            charging=charging,
            connected=connected,
        )

    def _update_icon_image(self, *, force: bool = False) -> None:
        with self._lock:
            icon = self.icon
            key = (self._connected, self._battery_level, self._charging)
            if not force and key == self._last_icon_key:
                return
            self._last_icon_key = key
        if icon is None:
            return
        try:
            image = self._current_icon_image()
            if image is not None:
                icon.icon = image
        except Exception as exc:
            logger.debug("No se pudo actualizar el icono de batería: %s", exc)

    # ===== Tooltip y menú =====

    def _tooltip_text(self) -> str:
        with self._lock:
            parts = [self.app_name, self._status_text]
            if self._connected and self._battery_level is not None:
                parts.append(self._battery_text)
            if self._profile_text:
                parts.append(f"Perfil · {self._profile_text}")
        # Windows limita el tooltip del área de notificación.
        return "\n".join(parts)[:127]

    def _update_tooltip(self) -> None:
        with self._lock:
            icon = self.icon
        if icon is not None:
            try:
                icon.title = self._tooltip_text()
            except Exception as exc:
                logger.debug("No se pudo actualizar el tooltip: %s", exc)

    @staticmethod
    def _separator():
        return pystray.MenuItem("", lambda *_args: None, enabled=False)

    def _build_menu(self) -> "pystray.Menu":
        with self._lock:
            status_text = self._status_text
            battery_text = self._battery_text
            battery_level = self._battery_level if self._connected else None
            profiles = list(self._profiles)
            current_profile = self._current_profile
            profile_text = self._profile_text
            low_profile_active = self._low_profile_active

        items = [
            pystray.MenuItem(self.app_name, lambda *_args: None, enabled=False),
            pystray.MenuItem(f"Estado · {status_text}", lambda *_args: None, enabled=False),
        ]
        if battery_level is not None:
            items.append(pystray.MenuItem(battery_text, lambda *_args: None, enabled=False))
        if profile_text:
            items.append(
                pystray.MenuItem(f"Perfil · {profile_text}", lambda *_args: None, enabled=False)
            )
        if low_profile_active:
            items.append(
                pystray.MenuItem("Modo · Low Profile activo", lambda *_args: None, enabled=False)
            )

        items.extend(
            [
                self._separator(),
                # En Windows, el elemento default se ejecuta con clic izquierdo
                # o doble clic sobre el icono.
                pystray.MenuItem("Abrir Nikaido", self._show_window, default=True),
            ]
        )

        if not low_profile_active:
            items.append(pystray.MenuItem("Activar Low Profile", self._activate_low_profile))

        if profiles:
            profile_items = []
            for profile_id, profile_name in profiles:
                is_current = profile_id == current_profile
                label = f"{'✓ ' if is_current else ''}{profile_name}"
                profile_items.append(
                    pystray.MenuItem(
                        label,
                        lambda *_args, pid=profile_id: self._select_profile(pid),
                    )
                )
            items.append(pystray.MenuItem("Cambiar perfil", pystray.Menu(*profile_items)))

        items.extend(
            [
                self._separator(),
                pystray.MenuItem("Salir de Nikaido", self._exit_app),
            ]
        )
        return pystray.Menu(*items)

    def _rebuild_menu(self) -> None:
        with self._lock:
            icon = self.icon
        if icon is None:
            return
        try:
            icon.menu = self._build_menu()
            if hasattr(icon, "update_menu"):
                icon.update_menu()
        except Exception as exc:
            logger.debug("No se pudo reconstruir el menú de bandeja: %s", exc)

    def _refresh_visuals(
        self,
        *,
        rebuild_menu: bool = False,
        update_icon: bool = True,
    ) -> None:
        if update_icon:
            self._update_icon_image()
        self._update_tooltip()
        if rebuild_menu:
            self._rebuild_menu()

    # ===== Acciones =====

    def _show_window(self, *_args) -> None:
        self._notify_callbacks(self._on_show_window)

    def _exit_app(self, *_args) -> None:
        # Detener primero evita que Windows vuelva a disparar la acción del
        # icono mientras Qt está liberando los motores.
        self.stop()
        self._notify_callbacks(self._on_exit)

    def _select_profile(self, profile_id: str) -> None:
        self._notify_callbacks(self._on_profile_select, profile_id)

    def _activate_low_profile(self, *_args) -> None:
        self._notify_callbacks(self._on_low_profile)

    # ===== Notificaciones =====

    def notify(self, message: str, title: Optional[str] = None) -> bool:
        """Muestra una notificación nativa sin fallar si Windows la bloquea."""
        with self._lock:
            icon = self.icon
        if icon is None or not self._visible:
            return False
        try:
            icon.notify(str(message), str(title or self.app_name))
            return True
        except Exception as exc:
            logger.debug("No se pudo mostrar notificación de bandeja: %s", exc)
            return False

    def notify_minimized(self) -> None:
        """Explica una vez por sesión dónde quedó Nikaido al minimizar."""
        with self._lock:
            if self._minimize_notice_shown:
                return
        shown = self.notify(
            "Nikaido sigue activo. Clic en el icono para volver; clic derecho para perfiles y salida.",
            "Nikaido está en la bandeja",
        )
        if shown:
            with self._lock:
                self._minimize_notice_shown = True

    def notify_low_profile(self) -> None:
        """Avisa una vez que la interfaz se liberó y solo quedan los motores."""
        with self._lock:
            if self._low_profile_notice_shown:
                return
        shown = self.notify(
            "Interfaz liberada. El control, la emulación y tu perfil siguen activos.",
            "Low Profile activado",
        )
        if shown:
            with self._lock:
                self._low_profile_notice_shown = True

    # ===== Ciclo de vida =====

    def _run_icon(self, icon: "pystray.Icon") -> None:
        """Ejecuta pystray y corrige el estado si el backend termina solo."""
        try:
            icon.run()
        except Exception as exc:
            logger.error("El hilo de bandeja terminó con error: %s", exc)
        finally:
            with self._lock:
                if self.icon is icon:
                    self.icon = None
                    self._thread = None
                    self._visible = False
                    self._last_icon_key = None

    def start(self) -> None:
        with self._lifecycle_lock:
            self._start_serialized()

    def _start_serialized(self) -> None:
        if not PYSTRAY_AVAILABLE or not PIL_AVAILABLE:
            detail = f" ({PYSTRAY_IMPORT_ERROR})" if PYSTRAY_IMPORT_ERROR else ""
            logger.warning(
                "pystray o Pillow no disponible. Modo bandeja desactivado.%s", detail
            )
            return

        with self._lock:
            if self._visible:
                return
            if self._thread and self._thread.is_alive():
                logger.warning("La bandeja anterior todavía se está cerrando")
                return
            self.icon = None
            self._thread = None
        try:
            icon_image = self._current_icon_image()
            icon = pystray.Icon(
                "nikaido_dualsense",
                icon_image,
                title=self._tooltip_text(),
                menu=self._build_menu(),
            )
            thread = threading.Thread(
                target=self._run_icon,
                args=(icon,),
                name="NikaidoSystemTray",
                daemon=True,
            )
            with self._lock:
                self.icon = icon
                self._thread = thread
                self._visible = True
                self._last_icon_key = (
                    self._connected,
                    self._battery_level,
                    self._charging,
                )
            # El candado de ciclo de vida evita que stop() detenga el icono antes
            # de que su hilo haya arrancado y luego start() lo reviva por accidente.
            thread.start()
            logger.info("Icono de bandeja con batería iniciado")
        except Exception as exc:
            with self._lock:
                self.icon = None
                self._thread = None
                self._visible = False
            logger.error("Error iniciando bandeja del sistema: %s", exc)

    def stop(self) -> None:
        with self._lifecycle_lock:
            self._stop_serialized()

    def _stop_serialized(self) -> None:
        with self._lock:
            icon = self.icon
            thread = self._thread
            self._visible = False
            self._last_icon_key = None
        if icon is not None:
            try:
                icon.stop()
            except Exception as exc:
                logger.debug("No se pudo detener limpiamente el icono: %s", exc)
        if thread and thread is not threading.current_thread() and thread.is_alive():
            thread.join(timeout=1.5)
        with self._lock:
            if thread is None or not thread.is_alive():
                if self._thread is thread:
                    self._thread = None
                if self.icon is icon:
                    self.icon = None
        logger.info("Icono de bandeja detenido")

    def is_visible(self) -> bool:
        with self._lock:
            return self._visible

    def update(self) -> None:
        self._refresh_visuals(rebuild_menu=True)
