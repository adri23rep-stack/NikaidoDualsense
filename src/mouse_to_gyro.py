"""Captura global robusta de mouse para stick derecho y gyro virtual.

La fuente usa Raw Input de Windows como ruta principal porque entrega deltas
reales incluso cuando un juego bloquea o recentra el cursor. Si Windows o algún
programa impiden registrar Raw Input, cae automáticamente a un hook global y,
como último respaldo, a sondeo del cursor.

No escribe directamente a ViGEm: únicamente acumula deltas que consumen
``KeyboardGamepadEngine`` o ``EmulatorManager``.
"""

from __future__ import annotations

import ctypes
import logging
import math
import sys
import threading
import time
from ctypes import wintypes
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class MouseGyroSource:
    """Fuente global de deltas de mouse segura y apagada por defecto."""

    WH_MOUSE_LL = 14
    WM_MOUSEMOVE = 0x0200
    WM_INPUT = 0x00FF
    WM_CLOSE = 0x0010
    WM_DESTROY = 0x0002
    WM_QUIT = 0x0012
    VK_CONTROL = 0x11
    VK_M = 0x4D
    RID_INPUT = 0x10000003
    RIM_TYPEMOUSE = 0
    RIDEV_REMOVE = 0x00000001
    RIDEV_INPUTSINK = 0x00000100
    MOUSE_MOVE_ABSOLUTE = 0x0001
    LLMHF_INJECTED = 0x00000001
    UINT_ERROR = 0xFFFFFFFF

    # Solo aplica al respaldo basado en posición absoluta. Raw Input no necesita
    # este filtro porque ya entrega movimiento relativo del dispositivo.
    MAX_WARP_DELTA = 320
    GYRO_UNITS_PER_DPS = 16.0
    RECENTER_INTERVAL_SECONDS = 0.008
    ESCAPE_POLL_SECONDS = 0.005
    HOTKEY_POLL_SECONDS = 0.02
    DEFAULT_ACTIVATION_DELAY_SECONDS = 5.0
    HOTKEY_DEBOUNCE_SECONDS = 0.20

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._lifecycle_lock = threading.RLock()
        self._dx = 0.0
        self._dy = 0.0
        self._last_position: Optional[Tuple[int, int]] = None
        self._thread: Optional[threading.Thread] = None
        self._watchdog_thread: Optional[threading.Thread] = None
        self._watchdog_stop = threading.Event()
        self._hotkey_thread: Optional[threading.Thread] = None
        self._hotkey_stop = threading.Event()
        self._hotkey_armed = False
        self._activation_thread: Optional[threading.Thread] = None
        self._activation_cancel = threading.Event()
        self._activation_pending = False
        self._activation_deadline = 0.0
        self._activation_delay_seconds = 0.0
        self._thread_id = 0
        self._hook = None
        self._hook_proc = None
        self._window_handle = None
        self._window_proc = None
        self._window_class_name = ""
        self._running = False
        self._ready = threading.Event()
        self._start_ok = False
        self._last_error = ""
        self._backend = "stopped"
        self._packet_count = 0
        self._last_packet_time = 0.0
        self._center_cursor_enabled = True
        self._last_recenter_time = 0.0
        self._recenter_count = 0
        self._last_center: Optional[Tuple[int, int]] = None
        self._center_target: Optional[Tuple[int, int]] = None
        self._original_cursor_position: Optional[Tuple[int, int]] = None
        self._center_refresh_time = 0.0
        self._ignore_next_warp = False
        self._escape_was_down = False
        self._emergency_stop_count = 0
        self._emergency_stop_reason = ""
        self._last_toggle_time = 0.0
        self._last_toggle_action = ""
        self._emergency_callback: Optional[Callable[[], None]] = None

    def is_available(self) -> bool:
        return sys.platform == "win32"

    def is_running(self) -> bool:
        with self._lock:
            thread = self._thread
            return bool(self._running and thread and thread.is_alive())

    @property
    def last_error(self) -> str:
        return self._last_error

    @property
    def backend(self) -> str:
        return self._backend

    def set_emergency_stop_callback(self, callback: Optional[Callable[[], None]]) -> None:
        """Configura el receptor que alterna la captura al usar Ctrl+M.

        El nombre se conserva por compatibilidad con 2.5.3, pero desde 2.5.4
        Ctrl+M es un interruptor real: el propietario decide si debe pausar o
        reactivar la captura de inmediato.
        """
        if callback is not None and not callable(callback):
            raise TypeError("El callback de emergencia debe ser invocable")
        self._emergency_callback = callback

    def arm_hotkey_toggle(self, enabled: bool = True) -> bool:
        """Mantiene Ctrl+M disponible aunque la captura esté temporalmente apagada."""
        with self._lifecycle_lock:
            return self._arm_hotkey_toggle_serialized(enabled)

    def _arm_hotkey_toggle_serialized(self, enabled: bool) -> bool:
        enabled = bool(enabled)
        with self._lock:
            stop_event = self._hotkey_stop
            thread = self._hotkey_thread
        if not enabled:
            with self._lock:
                self._hotkey_armed = False
            stop_event.set()
            if thread and thread.is_alive() and thread is not threading.current_thread():
                thread.join(timeout=0.6)
            with self._lock:
                # No olvidamos un listener bloqueado. Mientras siga vivo, un
                # nuevo armado debe esperar para no registrar Ctrl+M dos veces.
                if self._hotkey_thread is thread and (thread is None or not thread.is_alive()):
                    self._hotkey_thread = None
                self._escape_was_down = False
            return True
        if not self.is_available():
            with self._lock:
                self._hotkey_armed = False
            return False
        if thread and thread.is_alive():
            if stop_event.is_set():
                with self._lock:
                    self._hotkey_armed = False
                    self._last_error = "El atajo Ctrl+M anterior todavía se está cerrando"
                return False
            with self._lock:
                self._hotkey_armed = True
            return True

        stop_event = threading.Event()
        thread = threading.Thread(
            target=self._hotkey_loop,
            args=(stop_event,),
            name="NikaidoMouseHotkey",
            daemon=True,
        )
        with self._lock:
            self._hotkey_stop = stop_event
            self._hotkey_armed = True
            self._escape_was_down = False
            self._hotkey_thread = thread
        try:
            thread.start()
        except Exception:
            with self._lock:
                if self._hotkey_thread is thread:
                    self._hotkey_thread = None
                self._hotkey_armed = False
            raise
        return True

    def note_toggle_action(self, action: str) -> None:
        with self._lock:
            self._last_toggle_action = str(action or "")

    def is_activation_pending(self) -> bool:
        with self._lock:
            return bool(self._activation_pending)

    def set_cursor_centering(self, enabled: bool) -> None:
        self._center_cursor_enabled = bool(enabled)
        if not enabled:
            self._last_center = None
            self._center_target = None
            self._last_recenter_time = 0.0

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            remaining = max(0.0, self._activation_deadline - time.perf_counter())
            return {
                "available": self.is_available(),
                "running": self.is_running(),
                "backend": self._backend,
                "last_error": self._last_error,
                "packets": int(self._packet_count),
                "last_packet_age_ms": (
                    round((time.perf_counter() - self._last_packet_time) * 1000.0, 1)
                    if self._last_packet_time
                    else None
                ),
                "pending_delta": (round(self._dx, 3), round(self._dy, 3)),
                "cursor_centering": bool(self._center_cursor_enabled and self.is_running()),
                "recenter_count": int(self._recenter_count),
                "last_center": self._last_center,
                "escape_hotkey": "CTRL+M",
                "emergency_stop_count": int(self._emergency_stop_count),
                "emergency_stop_reason": self._emergency_stop_reason,
                "hotkey_armed": bool(self._hotkey_armed),
                "hotkey_listener_running": bool(
                    self._hotkey_thread and self._hotkey_thread.is_alive()
                ),
                "hotkey_toggle_count": int(self._emergency_stop_count),
                "last_toggle_action": self._last_toggle_action,
                "activation_pending": bool(self._activation_pending),
                "activation_remaining_seconds": round(remaining, 2),
                "activation_delay_seconds": round(self._activation_delay_seconds, 2),
            }

    def start_delayed(self, delay_seconds: float = DEFAULT_ACTIVATION_DELAY_SECONDS) -> bool:
        """Arma la captura sin secuestrar el cursor hasta terminar la cuenta.

        Es idempotente mientras ya existe una cuenta activa. Esto evita que un
        refresco de perfil o de interfaz vuelva a poner el contador en cinco.
        """
        with self._lifecycle_lock:
            return self._start_delayed_serialized(delay_seconds)

    def _start_delayed_serialized(self, delay_seconds: float) -> bool:
        if self.is_running() or self.is_activation_pending():
            return True
        if not self.is_available():
            self._last_error = "La captura global de mouse requiere Windows"
            return False
        try:
            delay = max(0.0, min(30.0, float(delay_seconds)))
        except (TypeError, ValueError, OverflowError):
            delay = self.DEFAULT_ACTIVATION_DELAY_SECONDS
        if delay <= 0.0:
            return self._start_serialized()

        self._cancel_delayed_start_serialized()
        cancel_event = threading.Event()
        thread = threading.Thread(
            target=self._delayed_start_loop,
            args=(cancel_event,),
            name="NikaidoMouseCountdown",
            daemon=True,
        )
        with self._lock:
            self._activation_pending = True
            self._activation_delay_seconds = delay
            self._activation_deadline = time.perf_counter() + delay
            self._last_error = ""
            self._backend = "countdown"
            self._activation_cancel = cancel_event
            self._activation_thread = thread
        thread.start()
        return True

    def cancel_delayed_start(self) -> None:
        with self._lifecycle_lock:
            self._cancel_delayed_start_serialized()

    def _cancel_delayed_start_serialized(self) -> None:
        with self._lock:
            cancel_event = self._activation_cancel
            thread = self._activation_thread
            self._activation_pending = False
            self._activation_deadline = 0.0
            self._activation_delay_seconds = 0.0
            if self._backend == "countdown":
                self._backend = "stopped"
        cancel_event.set()
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=0.25)
        if thread is not threading.current_thread():
            with self._lock:
                if self._activation_thread is thread:
                    self._activation_thread = None

    def _delayed_start_loop(self, cancel_event: threading.Event) -> None:
        try:
            with self._lock:
                deadline = self._activation_deadline
            remaining = max(0.0, deadline - time.perf_counter())
            if cancel_event.wait(remaining):
                return
            with self._lock:
                if cancel_event is not self._activation_cancel or not self._activation_pending:
                    return
                self._activation_pending = False
                self._activation_deadline = 0.0
                self._activation_delay_seconds = 0.0
            self.start()
        finally:
            with self._lock:
                if self._activation_thread is threading.current_thread():
                    self._activation_thread = None

    def start(self) -> bool:
        with self._lifecycle_lock:
            return self._start_serialized()

    def _start_serialized(self) -> bool:
        if self.is_running():
            return True
        if not self.is_available():
            self._last_error = "La captura global de mouse requiere Windows"
            return False

        # Nunca reutilizamos los eventos de una generación anterior. Si Windows
        # no cerró un hook viejo a tiempo, es más seguro rechazar el reinicio que
        # dejar dos capturas globales compitiendo por el cursor.
        stale_threads = (self._thread, self._watchdog_thread)
        if any(thread and thread.is_alive() for thread in stale_threads):
            self._last_error = "La captura anterior todavía se está cerrando"
            return False

        self._cancel_delayed_start_serialized()
        self.reset()
        self._ready.clear()
        self._start_ok = False
        self._last_error = ""
        self._backend = "starting"
        self._last_recenter_time = 0.0
        self._last_center = None
        self._center_target = None
        self._original_cursor_position = None
        self._center_refresh_time = 0.0
        self._ignore_next_warp = False
        self._watchdog_stop = threading.Event()
        self._running = True
        thread = threading.Thread(
            target=self._capture_loop,
            name="NikaidoMouseCapture",
            daemon=True,
        )
        self._thread = thread
        thread.start()
        self._ready.wait(timeout=2.0)
        if not self._start_ok:
            self._running = False
            self._wake_capture_thread()
            if thread.is_alive() and thread is not threading.current_thread():
                thread.join(timeout=0.5)
            if not thread.is_alive() and self._thread is thread:
                self._thread = None
            return False
        watchdog_stop = self._watchdog_stop
        watchdog = threading.Thread(
            target=self._watchdog_loop,
            args=(watchdog_stop,),
            name="NikaidoMouseSafety",
            daemon=True,
        )
        self._watchdog_thread = watchdog
        watchdog.start()
        return True

    def stop(self) -> None:
        with self._lifecycle_lock:
            self._stop_serialized()

    def _stop_serialized(self) -> None:
        self._cancel_delayed_start_serialized()
        self._running = False
        watchdog_stop = self._watchdog_stop
        watchdog_stop.set()
        self._wake_capture_thread()
        watchdog = self._watchdog_thread
        if watchdog and watchdog.is_alive() and watchdog is not threading.current_thread():
            watchdog.join(timeout=1.0)
        if not watchdog or not watchdog.is_alive():
            if self._watchdog_thread is watchdog:
                self._watchdog_thread = None
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.5)
        if not thread or not thread.is_alive():
            if self._thread is thread:
                self._thread = None
        self._restore_cursor_position()
        self._thread_id = 0
        self._window_handle = None
        self._hook = None
        self._hook_proc = None
        self._window_proc = None
        self._backend = "stopped"
        self._last_center = None
        self._center_target = None
        self._ignore_next_warp = False
        self.reset()

    def _wake_capture_thread(self) -> None:
        if sys.platform != "win32":
            return
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            WPARAM_T = ctypes.c_size_t
            LPARAM_T = ctypes.c_ssize_t
            user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM_T, LPARAM_T]
            user32.PostMessageW.restype = wintypes.BOOL
            user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, WPARAM_T, LPARAM_T]
            user32.PostThreadMessageW.restype = wintypes.BOOL
            hwnd = self._window_handle
            if hwnd:
                user32.PostMessageW(hwnd, self.WM_CLOSE, 0, 0)
            if self._thread_id:
                user32.PostThreadMessageW(self._thread_id, self.WM_QUIT, 0, 0)
        except Exception:
            pass

    def reset(self) -> None:
        with self._lock:
            self._dx = 0.0
            self._dy = 0.0
            self._last_position = None

    def _request_emergency_stop(self) -> None:
        now = time.perf_counter()
        with self._lock:
            if now - self._last_toggle_time < self.HOTKEY_DEBOUNCE_SECONDS:
                return
            self._last_toggle_time = now
            self._emergency_stop_reason = "Ctrl+M"
            self._emergency_stop_count += 1
            self._dx = 0.0
            self._dy = 0.0
        callback = self._emergency_callback
        if callback:
            threading.Thread(
                target=self._run_emergency_callback,
                args=(callback,),
                name="NikaidoMouseEscape",
                daemon=True,
            ).start()

    @staticmethod
    def _run_emergency_callback(callback: Callable[[], None]) -> None:
        try:
            callback()
        except Exception:
            logger.exception("No se pudo aplicar el apagado de emergencia del mouse")

    def _remember_original_cursor(self, user32) -> None:
        if self._original_cursor_position is not None:
            return

        class POINT(ctypes.Structure):
            _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

        try:
            user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
            user32.GetCursorPos.restype = wintypes.BOOL
            point = POINT()
            if user32.GetCursorPos(ctypes.byref(point)):
                self._original_cursor_position = (int(point.x), int(point.y))
        except Exception:
            self._original_cursor_position = None

    def _restore_cursor_position(self) -> None:
        position = self._original_cursor_position
        self._original_cursor_position = None
        if sys.platform != "win32" or position is None:
            return
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
            user32.SetCursorPos.restype = wintypes.BOOL
            user32.SetCursorPos(int(position[0]), int(position[1]))
        except Exception:
            logger.debug("No se pudo restaurar la posición del cursor", exc_info=True)

    def _watchdog_loop(self, stop_event: threading.Event) -> None:
        """Mantiene el cursor centrado fuera del hilo de captura."""
        if sys.platform != "win32":
            return
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
            user32.SetCursorPos.restype = wintypes.BOOL
            self._remember_original_cursor(user32)
            while self._running and not stop_event.is_set():
                # Raw Input entrega deltas relativos aunque el cursor se recoloque.
                # Los respaldos por posición se recentran solo después de aceptar
                # movimiento para no borrar sus propios deltas.
                if self._backend == "raw_input" or self._last_center is None:
                    self._recenter_cursor(user32)
                stop_event.wait(self.ESCAPE_POLL_SECONDS)
        except Exception as exc:
            logger.warning("Vigilante de seguridad del mouse no disponible: %s", exc)
        finally:
            if not self._running:
                self._restore_cursor_position()

    def _hotkey_loop(self, stop_event: threading.Event) -> None:
        """Escucha Ctrl+M aunque el cursor esté libre y la captura detenida."""
        if sys.platform != "win32":
            return
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
            user32.GetAsyncKeyState.restype = ctypes.c_short
            while not stop_event.is_set():
                with self._lock:
                    armed = bool(self._hotkey_armed)
                if not armed:
                    break
                ctrl_down = bool(user32.GetAsyncKeyState(self.VK_CONTROL) & 0x8000)
                m_down = bool(user32.GetAsyncKeyState(self.VK_M) & 0x8000)
                combo_down = ctrl_down and m_down
                if combo_down and not self._escape_was_down:
                    self._request_emergency_stop()
                self._escape_was_down = combo_down
                stop_event.wait(self.HOTKEY_POLL_SECONDS)
        except Exception as exc:
            logger.warning("Atajo global Ctrl+M no disponible: %s", exc)
        finally:
            current = threading.current_thread()
            with self._lock:
                self._escape_was_down = False
                if self._hotkey_thread is current:
                    self._hotkey_thread = None

    def _monitor_center(self, user32) -> Optional[Tuple[int, int]]:
        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        try:
            user32.GetForegroundWindow.argtypes = []
            user32.GetForegroundWindow.restype = wintypes.HWND
            user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
            user32.MonitorFromWindow.restype = wintypes.HANDLE
            user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
            user32.GetMonitorInfoW.restype = wintypes.BOOL
            hwnd = user32.GetForegroundWindow()
            monitor = user32.MonitorFromWindow(hwnd, 2) if hwnd else None
            if monitor:
                info = MONITORINFO()
                info.cbSize = ctypes.sizeof(MONITORINFO)
                if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                    rect = info.rcMonitor
                    return ((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
        except Exception:
            pass
        try:
            user32.GetSystemMetrics.argtypes = [ctypes.c_int]
            user32.GetSystemMetrics.restype = ctypes.c_int
            left = user32.GetSystemMetrics(76)
            top = user32.GetSystemMetrics(77)
            width = user32.GetSystemMetrics(78)
            height = user32.GetSystemMetrics(79)
            if width > 0 and height > 0:
                return (left + width // 2, top + height // 2)
        except Exception:
            pass
        return None

    def _recenter_cursor(self, user32, *, force: bool = False) -> None:
        if not self._center_cursor_enabled or not self._running:
            return
        now = time.perf_counter()
        if not force and now - self._last_recenter_time < self.RECENTER_INTERVAL_SECONDS:
            return
        if self._center_target is None or now >= self._center_refresh_time:
            self._center_target = self._monitor_center(user32)
            self._center_refresh_time = now + 0.5
        center = self._center_target
        if center is None:
            return
        self._last_recenter_time = now
        with self._lock:
            previous_position = self._last_position
            self._last_center = center
            self._last_position = center
            self._ignore_next_warp = True
        if user32.SetCursorPos(int(center[0]), int(center[1])):
            with self._lock:
                self._recenter_count += 1
        else:
            with self._lock:
                self._last_position = previous_position
                self._ignore_next_warp = False

    def feed_delta(self, dx: float, dy: float) -> None:
        """Entrada directa para captura, pruebas y diagnósticos."""
        try:
            dx, dy = float(dx), float(dy)
        except (TypeError, ValueError, OverflowError):
            return
        if not math.isfinite(dx) or not math.isfinite(dy):
            return
        if not dx and not dy:
            return
        with self._lock:
            self._dx = max(-10000.0, min(10000.0, self._dx + dx))
            self._dy = max(-10000.0, min(10000.0, self._dy + dy))
            self._packet_count += 1
            self._last_packet_time = time.perf_counter()

    def _accept_position(self, x: int, y: int, *, injected: bool = False) -> bool:
        if injected:
            return False
        with self._lock:
            current = (int(x), int(y))
            if self._ignore_next_warp and self._last_center:
                if (
                    abs(current[0] - self._last_center[0]) <= 1
                    and abs(current[1] - self._last_center[1]) <= 1
                ):
                    self._ignore_next_warp = False
                    self._last_position = self._last_center
                    return False
            previous = self._last_position
            self._last_position = current
            if previous is None:
                return False
            dx = current[0] - previous[0]
            dy = current[1] - previous[1]
            if abs(dx) > self.MAX_WARP_DELTA or abs(dy) > self.MAX_WARP_DELTA:
                return False
        self.feed_delta(dx, dy)
        return bool(dx or dy)

    def consume_delta(self) -> Tuple[float, float]:
        with self._lock:
            result = (self._dx, self._dy)
            self._dx = 0.0
            self._dy = 0.0
            return result

    def consume_gyro(
        self,
        dt: float,
        *,
        sensitivity: float = 0.12,
        invert_x: bool = False,
        invert_y: bool = False,
        max_dps: float = 1400.0,
    ) -> Tuple[float, float, float]:
        """Devuelve ``(pitch, yaw, roll)`` en unidades crudas de un DS4."""
        dx, dy = self.consume_delta()
        if not dx and not dy:
            return (0.0, 0.0, 0.0)
        dt = max(0.001, min(0.05, float(dt)))
        sensitivity = max(0.005, min(2.0, float(sensitivity)))
        max_dps = max(100.0, min(5000.0, float(max_dps)))

        yaw_dps = (dx * sensitivity / dt) * (-1.0 if invert_x else 1.0)
        pitch_dps = (dy * sensitivity / dt) * (-1.0 if invert_y else 1.0)
        magnitude = math.hypot(yaw_dps, pitch_dps)
        if magnitude > max_dps:
            scale = max_dps / magnitude
            yaw_dps *= scale
            pitch_dps *= scale
        return (
            pitch_dps * self.GYRO_UNITS_PER_DPS,
            yaw_dps * self.GYRO_UNITS_PER_DPS,
            0.0,
        )

    def _capture_loop(self) -> None:
        errors = []
        try:
            try:
                self._raw_input_loop()
                return
            except Exception as exc:
                errors.append(f"Raw Input: {exc}")
                logger.warning("Raw Input de mouse no disponible; usando respaldo: %s", exc)

            if self._running:
                try:
                    self._low_level_hook_loop()
                    return
                except Exception as exc:
                    errors.append(f"Hook: {exc}")
                    logger.warning("Hook global de mouse no disponible; usando sondeo: %s", exc)

            if self._running:
                try:
                    self._cursor_poll_loop()
                    return
                except Exception as exc:
                    errors.append(f"Sondeo: {exc}")
        finally:
            if not self._start_ok:
                self._last_error = " · ".join(errors) or "No se pudo capturar el mouse"
            self._running = False
            self._ready.set()

    def _raw_input_loop(self) -> None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        LRESULT = ctypes.c_ssize_t
        WPARAM_T = ctypes.c_size_t
        LPARAM_T = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, WPARAM_T, LPARAM_T)

        class POINT(ctypes.Structure):
            _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

        class MSG(ctypes.Structure):
            _fields_ = [
                ("hWnd", wintypes.HWND),
                ("message", wintypes.UINT),
                ("wParam", WPARAM_T),
                ("lParam", LPARAM_T),
                ("time", wintypes.DWORD),
                ("pt", POINT),
                ("lPrivate", wintypes.DWORD),
            ]

        class RAWINPUTDEVICE(ctypes.Structure):
            _fields_ = [
                ("usUsagePage", wintypes.USHORT),
                ("usUsage", wintypes.USHORT),
                ("dwFlags", wintypes.DWORD),
                ("hwndTarget", wintypes.HWND),
            ]

        class RAWINPUTHEADER(ctypes.Structure):
            _fields_ = [
                ("dwType", wintypes.DWORD),
                ("dwSize", wintypes.DWORD),
                ("hDevice", wintypes.HANDLE),
                ("wParam", WPARAM_T),
            ]

        class BUTTONS_STRUCT(ctypes.Structure):
            _fields_ = [
                ("usButtonFlags", wintypes.USHORT),
                ("usButtonData", wintypes.USHORT),
            ]

        class BUTTONS_UNION(ctypes.Union):
            _anonymous_ = ("buttons",)
            _fields_ = [
                ("ulButtons", wintypes.ULONG),
                ("buttons", BUTTONS_STRUCT),
            ]

        class RAWMOUSE(ctypes.Structure):
            _anonymous_ = ("button_data",)
            _fields_ = [
                ("usFlags", wintypes.USHORT),
                ("button_data", BUTTONS_UNION),
                ("ulRawButtons", wintypes.ULONG),
                ("lLastX", wintypes.LONG),
                ("lLastY", wintypes.LONG),
                ("ulExtraInformation", wintypes.ULONG),
            ]

        class RAW_UNION(ctypes.Union):
            _fields_ = [("mouse", RAWMOUSE)]

        class RAWINPUT(ctypes.Structure):
            _anonymous_ = ("data",)
            _fields_ = [("header", RAWINPUTHEADER), ("data", RAW_UNION)]

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [
                ("style", wintypes.UINT),
                ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
            ]

        user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
        user32.RegisterClassW.restype = wintypes.ATOM
        user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
        user32.UnregisterClassW.restype = wintypes.BOOL
        user32.CreateWindowExW.argtypes = [
            wintypes.DWORD,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HWND,
            wintypes.HMENU,
            wintypes.HINSTANCE,
            wintypes.LPVOID,
        ]
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.DestroyWindow.argtypes = [wintypes.HWND]
        user32.DestroyWindow.restype = wintypes.BOOL
        user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM_T, LPARAM_T]
        user32.DefWindowProcW.restype = LRESULT
        user32.RegisterRawInputDevices.argtypes = [
            ctypes.POINTER(RAWINPUTDEVICE),
            wintypes.UINT,
            wintypes.UINT,
        ]
        user32.RegisterRawInputDevices.restype = wintypes.BOOL
        user32.GetRawInputData.argtypes = [
            wintypes.HANDLE,
            wintypes.UINT,
            wintypes.LPVOID,
            ctypes.POINTER(wintypes.UINT),
            wintypes.UINT,
        ]
        user32.GetRawInputData.restype = wintypes.UINT
        user32.GetMessageW.argtypes = [
            ctypes.POINTER(MSG),
            wintypes.HWND,
            wintypes.UINT,
            wintypes.UINT,
        ]
        user32.GetMessageW.restype = wintypes.BOOL
        user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
        user32.TranslateMessage.restype = wintypes.BOOL
        user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
        user32.DispatchMessageW.restype = LRESULT
        user32.PostQuitMessage.argtypes = [ctypes.c_int]
        user32.PostQuitMessage.restype = None
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        kernel32.GetCurrentThreadId.argtypes = []
        kernel32.GetCurrentThreadId.restype = wintypes.DWORD

        hinstance = kernel32.GetModuleHandleW(None)
        if not hinstance:
            raise ctypes.WinError(ctypes.get_last_error())

        def read_raw_input(lparam: int) -> None:
            size = wintypes.UINT(0)
            result = user32.GetRawInputData(
                wintypes.HANDLE(lparam),
                self.RID_INPUT,
                None,
                ctypes.byref(size),
                ctypes.sizeof(RAWINPUTHEADER),
            )
            if result == self.UINT_ERROR or not size.value:
                return
            buffer = ctypes.create_string_buffer(size.value)
            copied = user32.GetRawInputData(
                wintypes.HANDLE(lparam),
                self.RID_INPUT,
                buffer,
                ctypes.byref(size),
                ctypes.sizeof(RAWINPUTHEADER),
            )
            if copied == self.UINT_ERROR or copied < ctypes.sizeof(RAWINPUTHEADER):
                return
            raw = ctypes.cast(buffer, ctypes.POINTER(RAWINPUT)).contents
            if raw.header.dwType != self.RIM_TYPEMOUSE:
                return
            mouse = raw.mouse
            # Ratones físicos normales reportan movimiento relativo. Los datos
            # absolutos suelen venir de tabletas o escritorios remotos.
            if mouse.usFlags & self.MOUSE_MOVE_ABSOLUTE:
                return
            self.feed_delta(mouse.lLastX, mouse.lLastY)

        @WNDPROC
        def window_proc(hwnd, message, wparam, lparam):
            try:
                if message == self.WM_INPUT:
                    read_raw_input(int(lparam))
                elif message == self.WM_CLOSE:
                    user32.DestroyWindow(hwnd)
                    return 0
                elif message == self.WM_DESTROY:
                    user32.PostQuitMessage(0)
                    return 0
            except Exception:
                logger.debug("Paquete Raw Input inválido", exc_info=True)
            return user32.DefWindowProcW(hwnd, message, wparam, lparam)

        class_name = f"NikaidoMouseCapture_{id(self):x}"
        wnd_class = WNDCLASSW(
            0,
            window_proc,
            0,
            0,
            hinstance,
            None,
            None,
            None,
            None,
            class_name,
        )
        atom = user32.RegisterClassW(ctypes.byref(wnd_class))
        if not atom:
            raise ctypes.WinError(ctypes.get_last_error())

        hwnd = None
        registered = False
        self._window_proc = window_proc
        self._window_class_name = class_name
        self._thread_id = int(kernel32.GetCurrentThreadId())
        try:
            # Ventana oculta: recibe WM_INPUT sin robar foco ni aparecer en la barra.
            hwnd = user32.CreateWindowExW(
                0,
                class_name,
                "Nikaido Mouse Capture",
                0,
                0,
                0,
                0,
                0,
                None,
                None,
                hinstance,
                None,
            )
            if not hwnd:
                raise ctypes.WinError(ctypes.get_last_error())
            self._window_handle = hwnd

            device = RAWINPUTDEVICE(0x01, 0x02, self.RIDEV_INPUTSINK, hwnd)
            if not user32.RegisterRawInputDevices(
                ctypes.byref(device), 1, ctypes.sizeof(RAWINPUTDEVICE)
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            registered = True

            self._backend = "raw_input"
            self._start_ok = True
            self._last_error = ""
            self._ready.set()

            message = MSG()
            while self._running:
                result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
                if result <= 0:
                    break
                user32.TranslateMessage(ctypes.byref(message))
                user32.DispatchMessageW(ctypes.byref(message))
        finally:
            if registered:
                try:
                    remove = RAWINPUTDEVICE(0x01, 0x02, self.RIDEV_REMOVE, None)
                    user32.RegisterRawInputDevices(
                        ctypes.byref(remove), 1, ctypes.sizeof(RAWINPUTDEVICE)
                    )
                except Exception:
                    pass
            if hwnd:
                try:
                    user32.DestroyWindow(hwnd)
                except Exception:
                    pass
            self._window_handle = None
            try:
                user32.UnregisterClassW(class_name, hinstance)
            except Exception:
                pass
            self._window_proc = None

    def _low_level_hook_loop(self) -> None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        class POINT(ctypes.Structure):
            _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

        class MSLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("pt", POINT),
                ("mouseData", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_void_p),
            ]

        LRESULT = ctypes.c_ssize_t
        WPARAM_T = ctypes.c_size_t
        LPARAM_T = ctypes.c_ssize_t

        class MSG(ctypes.Structure):
            _fields_ = [
                ("hWnd", wintypes.HWND),
                ("message", wintypes.UINT),
                ("wParam", WPARAM_T),
                ("lParam", LPARAM_T),
                ("time", wintypes.DWORD),
                ("pt", POINT),
                ("lPrivate", wintypes.DWORD),
            ]

        HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, WPARAM_T, LPARAM_T)
        user32.SetWindowsHookExW.argtypes = [
            ctypes.c_int,
            HOOKPROC,
            wintypes.HINSTANCE,
            wintypes.DWORD,
        ]
        user32.SetWindowsHookExW.restype = wintypes.HANDLE
        user32.CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int, WPARAM_T, LPARAM_T]
        user32.CallNextHookEx.restype = LRESULT
        user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
        user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        user32.GetMessageW.argtypes = [
            ctypes.POINTER(MSG),
            wintypes.HWND,
            wintypes.UINT,
            wintypes.UINT,
        ]
        user32.GetMessageW.restype = wintypes.BOOL
        user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
        user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        kernel32.GetCurrentThreadId.argtypes = []
        kernel32.GetCurrentThreadId.restype = wintypes.DWORD

        @HOOKPROC
        def hook_proc(code, message, data_ptr):
            try:
                if code >= 0 and message == self.WM_MOUSEMOVE:
                    data = ctypes.cast(data_ptr, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                    accepted = self._accept_position(
                        data.pt.x,
                        data.pt.y,
                        injected=bool(data.flags & self.LLMHF_INJECTED),
                    )
                    if accepted:
                        self._recenter_cursor(user32, force=True)
            except Exception:
                logger.debug("Paquete de hook de mouse inválido", exc_info=True)
            return user32.CallNextHookEx(self._hook, code, message, data_ptr)

        self._hook_proc = hook_proc
        self._thread_id = int(kernel32.GetCurrentThreadId())
        module = kernel32.GetModuleHandleW(None)
        self._hook = user32.SetWindowsHookExW(self.WH_MOUSE_LL, hook_proc, module, 0)
        if not self._hook:
            raise ctypes.WinError(ctypes.get_last_error())

        self._backend = "low_level_hook"
        self._start_ok = True
        self._last_error = ""
        self._ready.set()
        try:
            message = MSG()
            while self._running:
                result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
                if result <= 0:
                    break
                user32.TranslateMessage(ctypes.byref(message))
                user32.DispatchMessageW(ctypes.byref(message))
        finally:
            if self._hook:
                try:
                    user32.UnhookWindowsHookEx(self._hook)
                except Exception:
                    pass
            self._hook = None
            self._hook_proc = None

    def _cursor_poll_loop(self) -> None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)

        class POINT(ctypes.Structure):
            _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

        user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
        user32.GetCursorPos.restype = wintypes.BOOL
        self._backend = "cursor_poll"
        self._start_ok = True
        self._last_error = ""
        self._ready.set()
        while self._running:
            point = POINT()
            if user32.GetCursorPos(ctypes.byref(point)):
                if self._accept_position(point.x, point.y):
                    self._recenter_cursor(user32, force=True)
            time.sleep(0.002)
