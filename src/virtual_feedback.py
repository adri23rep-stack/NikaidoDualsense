"""Puente de feedback entre ViGEm y el DualSense físico.

``vgamepad`` entrega las órdenes de vibración del juego desde un callback de
ViGEm. Ese callback nunca escribe directamente al HID: solo publica el último
valor. Un hilo pequeño aplica suavizado, límites y timeout antes de tocar los
motores físicos. Así una ráfaga de notificaciones del juego no compite con el
hilo de lectura de 250 Hz ni deja un motor pegado al cerrar la emulación.
"""

from __future__ import annotations

import copy
import logging
import math
import threading
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)

DEFAULT_FEEDBACK_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "strength": 1.0,
    "large_motor_scale": 1.0,
    "small_motor_scale": 1.0,
    "swap_motors": False,
    "smoothing_ms": 18,
    "idle_timeout_ms": 350,
    "minimum_output": 0,
}


def _number(value: Any, minimum: float, maximum: float, fallback: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        parsed = fallback
    if not math.isfinite(parsed):
        parsed = fallback
    return max(minimum, min(maximum, parsed))


def sanitize_feedback_config(raw: Any) -> Dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    return {
        "enabled": bool(source.get("enabled", DEFAULT_FEEDBACK_CONFIG["enabled"])),
        "strength": _number(source.get("strength"), 0.0, 2.0, 1.0),
        "large_motor_scale": _number(source.get("large_motor_scale"), 0.0, 2.0, 1.0),
        "small_motor_scale": _number(source.get("small_motor_scale"), 0.0, 2.0, 1.0),
        "swap_motors": bool(source.get("swap_motors", False)),
        "smoothing_ms": int(_number(source.get("smoothing_ms"), 0, 250, 18)),
        "idle_timeout_ms": int(_number(source.get("idle_timeout_ms"), 100, 3000, 350)),
        "minimum_output": int(_number(source.get("minimum_output"), 0, 80, 0)),
    }


class VirtualFeedbackBridge:
    """Convierte el rumble del control virtual en motores del DualSense."""

    UPDATE_HZ = 120.0

    def __init__(self, emulator=None, connection_manager=None, config: Any = None) -> None:
        self.emulator = emulator
        self.connection_manager = connection_manager
        self._config = sanitize_feedback_config(config)
        self._lock = threading.RLock()
        self._lifecycle_lock = threading.RLock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._target = (0.0, 0.0)
        self._output = (0, 0)
        self._last_feedback_at = 0.0
        self._last_apply_at = 0.0
        self._received = 0
        self._applied = 0
        self._errors = 0
        self._last_error = ""
        self._registered = False
        self._timed_out = False
        self._manual_override_blocked = False

        if emulator is not None and hasattr(emulator, "on_feedback"):
            emulator.on_feedback(self._on_feedback)
            self._registered = True

    def _register_feedback_callback(self) -> None:
        if self._registered or self.emulator is None:
            return
        registrar = getattr(self.emulator, "on_feedback", None)
        if callable(registrar):
            registrar(self._on_feedback)
            self._registered = True

    def _unregister_feedback_callback(self) -> None:
        if not self._registered or self.emulator is None:
            return
        remover = getattr(self.emulator, "remove_feedback_callback", None)
        if callable(remover):
            try:
                remover(self._on_feedback)
            except (ValueError, KeyError):
                pass
        self._registered = False

    def start(self) -> None:
        # Cada generación tiene sus propios eventos. Limpiar un Event compartido
        # durante un reinicio podía despertar de nuevo al trabajador anterior.
        with self._lifecycle_lock:
            with self._lock:
                if self._thread and self._thread.is_alive():
                    return
                self._register_feedback_callback()
                stop_event = threading.Event()
                wake_event = threading.Event()
                self._stop = stop_event
                self._wake = wake_event
                self._thread = threading.Thread(
                    target=self._worker,
                    args=(stop_event, wake_event),
                    name="VirtualFeedbackBridge",
                    daemon=True,
                )
                thread = self._thread
            thread.start()

    def stop(self) -> None:
        with self._lifecycle_lock:
            with self._lock:
                thread = self._thread
                stop_event = self._stop
                wake_event = self._wake
            stop_event.set()
            wake_event.set()
            if thread and thread is not threading.current_thread() and thread.is_alive():
                thread.join(timeout=1.5)
            with self._lock:
                if self._thread is thread and (thread is None or not thread.is_alive()):
                    self._thread = None
            self._apply_motors(0, 0, force=True)
            self._unregister_feedback_callback()

    def apply_config(self, raw: Any) -> Dict[str, Any]:
        config = sanitize_feedback_config(raw)
        with self._lock:
            self._config = config
            if not config["enabled"]:
                self._target = (0.0, 0.0)
        self._wake.set()
        return copy.deepcopy(config)

    def get_config(self) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._config)

    def set_enabled(self, enabled: bool) -> None:
        config = self.get_config()
        config["enabled"] = bool(enabled)
        self.apply_config(config)

    @staticmethod
    def _motor(value: Any) -> int:
        try:
            return max(0, min(255, int(value)))
        except (TypeError, ValueError, OverflowError):
            return 0

    def _on_feedback(self, feedback: Any) -> None:
        """Callback ligero; acepta el snapshot dict publicado por EmulatorManager."""
        if not isinstance(feedback, dict):
            return
        large = self._motor(feedback.get("large_motor", 0))
        small = self._motor(feedback.get("small_motor", 0))
        now = time.monotonic()
        with self._lock:
            self._received += 1
            self._last_feedback_at = now
            self._target = (float(large), float(small))
            self._timed_out = False
        self._wake.set()

    @staticmethod
    def _scaled_motor(value: float, scale: float, minimum: int) -> int:
        result = max(0, min(255, int(round(value * scale))))
        if 0 < result < minimum:
            result = minimum
        return result

    def _desired_output(self, now: float) -> tuple[float, float, Dict[str, Any]]:
        with self._lock:
            config = dict(self._config)
            large, small = self._target
            last_feedback = self._last_feedback_at
        if not config["enabled"]:
            return 0.0, 0.0, config
        if last_feedback and (now - last_feedback) * 1000.0 > config["idle_timeout_ms"]:
            with self._lock:
                self._target = (0.0, 0.0)
                self._timed_out = True
            large = small = 0.0
        strength = config["strength"]
        left = large * strength * config["large_motor_scale"]
        right = small * strength * config["small_motor_scale"]
        if config["swap_motors"]:
            left, right = right, left
        return left, right, config

    def _worker(
        self,
        stop_event: threading.Event | None = None,
        wake_event: threading.Event | None = None,
    ) -> None:
        stop_event = stop_event or self._stop
        wake_event = wake_event or self._wake
        interval = 1.0 / self.UPDATE_HZ
        current_left = 0.0
        current_right = 0.0
        last_tick = time.monotonic()
        zero_sent_after_idle = False

        while not stop_event.is_set():
            wake_event.wait(interval)
            wake_event.clear()
            now = time.monotonic()
            dt = max(0.001, min(0.1, now - last_tick))
            last_tick = now
            target_left, target_right, config = self._desired_output(now)

            smoothing = config["smoothing_ms"] / 1000.0
            if smoothing <= 0:
                current_left, current_right = target_left, target_right
            else:
                alpha = 1.0 - math.exp(-dt / max(0.001, smoothing))
                current_left += (target_left - current_left) * alpha
                current_right += (target_right - current_right) * alpha
                if abs(current_left - target_left) < 0.35:
                    current_left = target_left
                if abs(current_right - target_right) < 0.35:
                    current_right = target_right

            left = self._scaled_motor(current_left, 1.0, config["minimum_output"])
            right = self._scaled_motor(current_right, 1.0, config["minimum_output"])
            active = bool(left or right or target_left or target_right)
            if active:
                zero_sent_after_idle = False
                self._apply_motors(left, right)
            elif not zero_sent_after_idle:
                self._apply_motors(0, 0)
                zero_sent_after_idle = True

    def _apply_motors(self, left: int, right: int, *, force: bool = False) -> None:
        manager = self.connection_manager
        manual_active = False
        if manager is not None and hasattr(manager, "get_rumble_diagnostics"):
            try:
                manual_active = bool(
                    manager.get_rumble_diagnostics().get("manual_test_active", False)
                )
            except Exception:
                manual_active = False
        with self._lock:
            previous = self._output
            blocked = self._manual_override_blocked
            if manual_active:
                self._manual_override_blocked = True
        values = (self._motor(left), self._motor(right))
        if manual_active and not force:
            return
        if not force and values == previous and not blocked:
            return
        if manager is None or not hasattr(manager, "set_rumble"):
            with self._lock:
                self._output = values
            return
        try:
            try:
                applied = manager.set_rumble(*values, source="game")
            except TypeError as exc:
                # Compatibilidad con backends externos anteriores a 2.9.7.0.
                if "source" not in str(exc):
                    raise
                applied = manager.set_rumble(*values)
            if applied is False:
                # Una prueba manual tiene prioridad. No memorizamos esta salida
                # como aplicada para que el mismo valor se reenvíe al terminar.
                with self._lock:
                    self._manual_override_blocked = True
                return
            with self._lock:
                self._manual_override_blocked = False
                self._output = values
                self._last_apply_at = time.monotonic()
                self._applied += 1
                self._last_error = ""
        except Exception as exc:  # defensive: drivers can disappear during callback
            message = f"{type(exc).__name__}: {exc}"
            with self._lock:
                self._errors += 1
                self._last_error = message
            logger.warning("No se pudo devolver la vibración al DualSense: %s", message)

    def get_diagnostics_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "enabled": bool(self._config["enabled"]),
                "registered": self._registered,
                "running": bool(self._thread and self._thread.is_alive()),
                "target": tuple(round(value, 2) for value in self._target),
                "output": tuple(self._output),
                "received": self._received,
                "applied": self._applied,
                "errors": self._errors,
                "last_error": self._last_error,
                "last_feedback_age_ms": round(
                    (time.monotonic() - self._last_feedback_at) * 1000.0, 1
                )
                if self._last_feedback_at
                else None,
                "timed_out": self._timed_out,
                "manual_override_blocked": self._manual_override_blocked,
            }
