"""Teclado y mouse como control virtual para Nikaido.

El motor no crea un segundo dispositivo ni escribe directamente a ViGEm. Usa
``EmulatorManager`` como único propietario del gamepad virtual y solo le entrega
un estado sintético a una frecuencia estable. Así comparte la misma salida
Xbox 360 / DualShock 4, el mismo cierre seguro y las mismas dependencias que la
emulación del DualSense físico.
"""

from __future__ import annotations

import copy
import ctypes
import logging
import math
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from .emulator import EmulationMode, REMAPPABLE_BUTTONS
from .mouse_to_gyro import MouseGyroSource

logger = logging.getLogger(__name__)

KEYBOARD_GAMEPAD_VERSION = 1
POLL_HZ_MIN = 60
POLL_HZ_MAX = 500

# Nombres de bindings que representan ejes digitales.
AXIS_BINDINGS = (
    "left_up",
    "left_down",
    "left_left",
    "left_right",
    "right_up",
    "right_down",
    "right_left",
    "right_right",
)

BUTTON_BINDINGS = tuple(REMAPPABLE_BUTTONS)

DEFAULT_MAPPING: Dict[str, str] = {
    "left_up": "W",
    "left_down": "S",
    "left_left": "A",
    "left_right": "D",
    "right_up": "I",
    "right_down": "K",
    "right_left": "J",
    "right_right": "L",
    "cross": "SPACE",
    "circle": "E",
    "square": "Q",
    "triangle": "R",
    "L1": "1",
    "R1": "3",
    "L2_btn": "MOUSE2",
    "R2_btn": "MOUSE1",
    "L3": "C",
    "R3": "V",
    "options": "ENTER",
    "create": "TAB",
    "ps": "G",
    "touchpad": "F",
    "dpad_up": "UP",
    "dpad_down": "DOWN",
    "dpad_left": "LEFT",
    "dpad_right": "RIGHT",
}

PLATFORMER_MAPPING: Dict[str, str] = {
    **DEFAULT_MAPPING,
    "right_up": "",
    "right_down": "",
    "right_left": "",
    "right_right": "",
    "cross": "Z",
    "circle": "X",
    "square": "A",
    "triangle": "S",
    "L1": "Q",
    "R1": "W",
    "L2_btn": "1",
    "R2_btn": "2",
    "options": "ENTER",
    "create": "BACKSPACE",
}

KEYBOARD_GAMEPAD_PRESETS: Dict[str, Dict[str, Any]] = {
    "shooter": {
        "name": "Shooter",
        "mapping": DEFAULT_MAPPING,
        "mouse_stick_enabled": True,
        "mouse_sensitivity": 0.045,
        "stick_ramp_ms": 55,
        "stick_release_ms": 45,
    },
    "platformer": {
        "name": "Plataformas",
        "mapping": PLATFORMER_MAPPING,
        "mouse_stick_enabled": False,
        "mouse_sensitivity": 0.045,
        "stick_ramp_ms": 35,
        "stick_release_ms": 30,
    },
    "blank": {
        "name": "Vacío",
        "mapping": {key: "" for key in (*AXIS_BINDINGS, *BUTTON_BINDINGS)},
        "mouse_stick_enabled": False,
        "mouse_sensitivity": 0.045,
        "stick_ramp_ms": 60,
        "stick_release_ms": 45,
    },
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "version": KEYBOARD_GAMEPAD_VERSION,
    "enabled": False,
    "mode": "xbox",
    "mapping": copy.deepcopy(DEFAULT_MAPPING),
    "poll_hz": 250,
    "stick_ramp_ms": 55,
    "stick_release_ms": 45,
    "trigger_ramp_ms": 35,
    "mouse_stick_enabled": True,
    "mouse_sensitivity": 0.045,
    "mouse_smoothing": 35,
    "mouse_decay_ms": 55,
    "mouse_invert_x": False,
    "mouse_invert_y": False,
    "normalize_diagonals": True,
    "ignore_when_nikaido_focused": True,
    "pause_hotkey": "F8",
}


# Virtual-key codes aceptados por GetAsyncKeyState. Los alias se mantienen
# independientes de Qt para que el motor también funcione en modo consola.
KEY_ALIASES: Dict[str, int] = {
    "MOUSE1": 0x01,
    "MOUSE2": 0x02,
    "MOUSE3": 0x04,
    "MOUSE4": 0x05,
    "MOUSE5": 0x06,
    "BACKSPACE": 0x08,
    "TAB": 0x09,
    "ENTER": 0x0D,
    "SHIFT": 0x10,
    "CTRL": 0x11,
    "CONTROL": 0x11,
    "ALT": 0x12,
    "PAUSE": 0x13,
    "CAPSLOCK": 0x14,
    "ESC": 0x1B,
    "ESCAPE": 0x1B,
    "SPACE": 0x20,
    "PAGEUP": 0x21,
    "PAGEDOWN": 0x22,
    "END": 0x23,
    "HOME": 0x24,
    "LEFT": 0x25,
    "UP": 0x26,
    "RIGHT": 0x27,
    "DOWN": 0x28,
    "INSERT": 0x2D,
    "DELETE": 0x2E,
    "WIN": 0x5B,
    "WINDOWS": 0x5B,
    "NUM0": 0x60,
    "NUM1": 0x61,
    "NUM2": 0x62,
    "NUM3": 0x63,
    "NUM4": 0x64,
    "NUM5": 0x65,
    "NUM6": 0x66,
    "NUM7": 0x67,
    "NUM8": 0x68,
    "NUM9": 0x69,
    "MULTIPLY": 0x6A,
    "ADD": 0x6B,
    "SUBTRACT": 0x6D,
    "DECIMAL": 0x6E,
    "DIVIDE": 0x6F,
    ";": 0xBA,
    "=": 0xBB,
    ",": 0xBC,
    "-": 0xBD,
    ".": 0xBE,
    "/": 0xBF,
    "`": 0xC0,
    "[": 0xDB,
    "\\": 0xDC,
    "]": 0xDD,
    "'": 0xDE,
}
for _index in range(1, 25):
    KEY_ALIASES[f"F{_index}"] = 0x6F + _index


def _clamp_float(value: Any, minimum: float, maximum: float, fallback: float) -> float:
    try:
        return max(minimum, min(maximum, float(value)))
    except (TypeError, ValueError, OverflowError):
        return fallback


def _clamp_int(value: Any, minimum: int, maximum: int, fallback: int) -> int:
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError, OverflowError):
        return fallback


def normalize_key_name(value: Any) -> str:
    """Normaliza una tecla o combinación a un formato estable y corto."""
    raw = str(value or "").upper().strip().replace(" ", "")
    if not raw:
        return ""
    aliases = {
        "LMB": "MOUSE1",
        "LEFTMOUSE": "MOUSE1",
        "RMB": "MOUSE2",
        "RIGHTMOUSE": "MOUSE2",
        "MMB": "MOUSE3",
        "MIDDLEMOUSE": "MOUSE3",
        "XBUTTON1": "MOUSE4",
        "XBUTTON2": "MOUSE5",
        "RETURN": "ENTER",
        "DEL": "DELETE",
        "INS": "INSERT",
        "PGUP": "PAGEUP",
        "PGDN": "PAGEDOWN",
    }
    parts = []
    for token in raw.split("+"):
        token = aliases.get(token, token)
        if token and token not in parts:
            parts.append(token)
    return "+".join(parts[:4])


def key_to_vk(value: str) -> Tuple[int, ...]:
    codes = []
    for token in normalize_key_name(value).split("+"):
        if not token:
            continue
        code = KEY_ALIASES.get(token)
        if code is None and len(token) == 1 and ("A" <= token <= "Z" or "0" <= token <= "9"):
            code = ord(token)
        if code is not None and code not in codes:
            codes.append(code)
    return tuple(codes)


def sanitize_keyboard_gamepad_config(raw: Any) -> Dict[str, Any]:
    source = raw if isinstance(raw, Mapping) else {}
    mapping_source = source.get("mapping", {})
    if not isinstance(mapping_source, Mapping):
        mapping_source = {}
    mapping: Dict[str, str] = {}
    for key in (*AXIS_BINDINGS, *BUTTON_BINDINGS):
        value = mapping_source.get(key, DEFAULT_MAPPING.get(key, ""))
        normalized = normalize_key_name(value)
        # Una asignación inválida se conserva vacía en vez de bloquear el motor.
        mapping[key] = normalized if not normalized or key_to_vk(normalized) else ""
    mode = str(source.get("mode", "xbox")).strip().lower()
    if mode not in ("xbox", "ps4"):
        mode = "xbox"
    return {
        "version": KEYBOARD_GAMEPAD_VERSION,
        "enabled": bool(source.get("enabled", False)),
        "mode": mode,
        "mapping": mapping,
        "poll_hz": _clamp_int(source.get("poll_hz", 250), POLL_HZ_MIN, POLL_HZ_MAX, 250),
        "stick_ramp_ms": _clamp_int(source.get("stick_ramp_ms", 55), 0, 500, 55),
        "stick_release_ms": _clamp_int(source.get("stick_release_ms", 45), 0, 500, 45),
        "trigger_ramp_ms": _clamp_int(source.get("trigger_ramp_ms", 35), 0, 500, 35),
        "mouse_stick_enabled": bool(source.get("mouse_stick_enabled", True)),
        "mouse_sensitivity": _clamp_float(
            source.get("mouse_sensitivity", 0.045), 0.002, 0.30, 0.045
        ),
        "mouse_smoothing": _clamp_int(source.get("mouse_smoothing", 35), 0, 90, 35),
        "mouse_decay_ms": _clamp_int(source.get("mouse_decay_ms", 55), 10, 300, 55),
        "mouse_invert_x": bool(source.get("mouse_invert_x", False)),
        "mouse_invert_y": bool(source.get("mouse_invert_y", False)),
        "normalize_diagonals": bool(source.get("normalize_diagonals", True)),
        "ignore_when_nikaido_focused": bool(source.get("ignore_when_nikaido_focused", True)),
        "pause_hotkey": normalize_key_name(source.get("pause_hotkey", "F8")) or "F8",
    }


@dataclass
class KeyboardGamepadState:
    connected: bool = True
    left_trigger: int = 0
    right_trigger: int = 0
    left_stick_x: int = 128
    left_stick_y: int = 128
    right_stick_x: int = 128
    right_stick_y: int = 128
    buttons: Dict[str, bool] = field(default_factory=dict)
    gyro_pitch: int = 0
    gyro_yaw: int = 0
    gyro_roll: int = 0
    accel_x: int = 0
    accel_y: int = 0
    accel_z: int = 0
    sequence: int = 0
    source: str = "keyboard_gamepad"
    monotonic_ns: int = 0
    timestamp: float = 0.0


class KeyboardGamepadEngine:
    """Convierte estado global de teclado/mouse en un gamepad ViGEm."""

    def __init__(self, emulator, config: Optional[Mapping[str, Any]] = None) -> None:
        self.emulator = emulator
        self._config = sanitize_keyboard_gamepad_config(config)
        self._lock = threading.RLock()
        self._lifecycle_lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._suspended = False
        self._last_error = ""
        self._last_state = KeyboardGamepadState()
        self._sequence = 0
        self._axis = {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0}
        self._trigger = {"left": 0.0, "right": 0.0}
        self._mouse_axis = [0.0, 0.0]
        self._mouse = MouseGyroSource()
        self._mouse.set_emergency_stop_callback(self._handle_mouse_emergency_stop)
        self._mouse_hotkey_paused = False
        self._hotkey_was_down = False
        self._callbacks: list[Callable[[Dict[str, Any]], None]] = []
        self._diag_started = time.perf_counter()
        self._diag_ticks = 0
        self._diag_max_tick_ms = 0.0
        self._diag_last_tick_ms = 0.0

        self._user32 = None
        if sys.platform == "win32":
            try:
                self._user32 = ctypes.windll.user32
                self._user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
                self._user32.GetAsyncKeyState.restype = ctypes.c_short
            except Exception as exc:  # pragma: no cover - solo Windows
                self._last_error = str(exc)
                self._user32 = None

    def is_available(self) -> bool:
        return bool(sys.platform == "win32" and self._user32 is not None)

    def is_running(self) -> bool:
        with self._lock:
            thread = self._thread
            return bool(self._running and thread and thread.is_alive())

    def is_suspended(self) -> bool:
        with self._lock:
            return bool(self._suspended)

    @property
    def last_error(self) -> str:
        with self._lock:
            return self._last_error

    def on_status_change(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def _notify_status(self) -> None:
        snapshot = self.get_diagnostics_snapshot()
        for callback in list(self._callbacks):
            try:
                callback(snapshot)
            except Exception:
                logger.debug("Callback de KeyBridge falló", exc_info=True)

    def get_config(self) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._config)

    def apply_config(self, config: Mapping[str, Any], *, restart: bool = True) -> bool:
        normalized = sanitize_keyboard_gamepad_config(config)
        with self._lock:
            was_running = self.is_running()
            old_mode = self._config.get("mode")
            old_mouse = bool(self._config.get("mouse_stick_enabled"))
            self._config = normalized
        if (
            was_running
            and restart
            and (old_mode != normalized["mode"] or old_mouse != normalized["mouse_stick_enabled"])
        ):
            return self.restart()
        if was_running:
            if normalized["mouse_stick_enabled"] and not self._mouse.is_running():
                self._arm_mouse_hotkey(True)
                if not self._mouse_hotkey_paused and not self._mouse_pending():
                    self._start_mouse_capture_delayed()
            elif not normalized["mouse_stick_enabled"]:
                self._mouse_hotkey_paused = False
                self._mouse.stop()
                self._arm_mouse_hotkey(False)
        self._notify_status()
        return True

    def set_enabled(self, enabled: bool) -> bool:
        with self._lock:
            self._config["enabled"] = bool(enabled)
        return self.start() if enabled else self.stop()

    def start(self) -> bool:
        with self._lifecycle_lock:
            return self._start_serialized()

    def _start_serialized(self) -> bool:
        with self._lock:
            existing_thread = self._thread
            running = self._running
        if existing_thread and existing_thread.is_alive():
            if running:
                return True
            with self._lock:
                self._last_error = "El KeyBridge anterior todavía se está cerrando"
            self._notify_status()
            return False
        with self._lock:
            if self._thread is existing_thread:
                self._thread = None
        if not self.is_available():
            with self._lock:
                self._last_error = "Nikaido KeyBridge requiere Windows"
                self._config["enabled"] = False
            self._notify_status()
            return False

        with self._lock:
            config = copy.deepcopy(self._config)
            config["enabled"] = True
            self._config = config
            self._last_error = ""
            self._suspended = False
            self._hotkey_was_down = False
            self._reset_runtime_locked()

        try:
            set_source = getattr(self.emulator, "set_input_source", None)
            if callable(set_source):
                set_source("keyboard")
            mode = EmulationMode.XBOX if config["mode"] == "xbox" else EmulationMode.PS4
            if not self.emulator.set_mode(mode):
                raise RuntimeError("No se pudo crear el control virtual. Revisa ViGEm/vgamepad.")
            if config["mouse_stick_enabled"]:
                self._mouse_hotkey_paused = False
                self._arm_mouse_hotkey(True)
                if not self._start_mouse_capture_delayed():
                    logger.warning(
                        "KeyBridge inició sin captura de mouse: %s", self._mouse.last_error
                    )
            with self._lock:
                self._running = True
                self._thread = threading.Thread(
                    target=self._loop,
                    name="NikaidoKeyBridge",
                    daemon=True,
                )
                thread = self._thread
            thread.start()
            self._notify_status()
            logger.info("Nikaido KeyBridge activo como %s", config["mode"])
            return True
        except Exception as exc:
            with self._lock:
                self._last_error = f"{type(exc).__name__}: {exc}"
                self._config["enabled"] = False
                self._running = False
            self._mouse.stop()
            self._arm_mouse_hotkey(False)
            try:
                self.emulator.release_all_inputs()
                self.emulator.set_mode(EmulationMode.NONE)
                set_source = getattr(self.emulator, "set_input_source", None)
                if callable(set_source):
                    set_source("dualsense")
            except Exception:
                pass
            self._notify_status()
            logger.error("No se pudo iniciar Nikaido KeyBridge: %s", exc)
            return False

    def restart(self) -> bool:
        with self._lifecycle_lock:
            self._stop_serialized(preserve_enabled=True)
            return self._start_serialized()

    def stop(self, *, preserve_enabled: bool = False) -> bool:
        with self._lifecycle_lock:
            return self._stop_serialized(preserve_enabled=preserve_enabled)

    def _stop_serialized(self, *, preserve_enabled: bool = False) -> bool:
        with self._lock:
            if not preserve_enabled:
                self._config["enabled"] = False
            self._running = False
            thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.5)
        with self._lock:
            if self._thread is thread and (thread is None or not thread.is_alive()):
                self._thread = None
        self._mouse.stop()
        self._arm_mouse_hotkey(False)
        try:
            self.emulator.release_all_inputs()
            self.emulator.set_mode(EmulationMode.NONE)
        except Exception:
            logger.debug("No se pudo neutralizar KeyBridge", exc_info=True)
        finally:
            set_source = getattr(self.emulator, "set_input_source", None)
            if callable(set_source):
                set_source("dualsense")
        with self._lock:
            self._suspended = False
            self._mouse_hotkey_paused = False
            self._reset_runtime_locked()
        self._notify_status()
        return True

    def _handle_mouse_emergency_stop(self) -> None:
        """Ctrl+M alterna mouse → stick sin borrar la configuración."""
        with self._lock:
            if not self._running or not self._config.get("mouse_stick_enabled"):
                return
            capture_active = bool(self._mouse.is_running() or self._mouse_pending())
            self._mouse_hotkey_paused = capture_active
            self._mouse_axis = [0.0, 0.0]
            self._axis["rx"] = 0.0
            self._axis["ry"] = 0.0
        if capture_active:
            self._mouse.stop()
            self._note_mouse_toggle("disabled")
        else:
            # La cuenta de cinco segundos solo pertenece a la activación manual.
            # Ctrl+M es un interruptor de juego y debe devolver el mouse al stick
            # de inmediato, sin hacer esperar al jugador otra vez.
            self._note_mouse_toggle("enabling")
            started = self._start_mouse_capture_immediate()
            self._note_mouse_toggle("enabled" if started else "failed")
        self._notify_status()

    def _arm_mouse_hotkey(self, enabled: bool) -> bool:
        arm = getattr(self._mouse, "arm_hotkey_toggle", None)
        return bool(arm(bool(enabled))) if callable(arm) else True

    def _mouse_pending(self) -> bool:
        pending = getattr(self._mouse, "is_activation_pending", None)
        if callable(pending):
            return bool(pending())
        status = getattr(self._mouse, "get_status", lambda: {})()
        return bool(status.get("activation_pending", False))

    def _start_mouse_capture_delayed(self) -> bool:
        self._mouse_hotkey_paused = False
        starter = getattr(self._mouse, "start_delayed", None)
        if callable(starter):
            return bool(starter(MouseGyroSource.DEFAULT_ACTIVATION_DELAY_SECONDS))
        return bool(self._mouse.start())

    def _start_mouse_capture_immediate(self) -> bool:
        """Reactiva Mouse → Stick al instante desde Ctrl+M."""
        self._mouse_hotkey_paused = False
        self._arm_mouse_hotkey(True)
        started = bool(self._mouse.start())
        if not started:
            self._mouse_hotkey_paused = True
        return started

    def _note_mouse_toggle(self, action: str) -> None:
        note = getattr(self._mouse, "note_toggle_action", None)
        if callable(note):
            note(action)

    def toggle_suspended(self) -> bool:
        with self._lock:
            self._suspended = not self._suspended
            suspended = self._suspended
            self._reset_runtime_locked()
        if suspended:
            try:
                self.emulator.release_all_inputs()
            except Exception:
                pass
        self._notify_status()
        return suspended

    def _reset_runtime_locked(self) -> None:
        self._axis = {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0}
        self._trigger = {"left": 0.0, "right": 0.0}
        self._mouse_axis = [0.0, 0.0]
        self._last_state = KeyboardGamepadState()
        self._mouse.reset()

    def _is_vk_down(self, code: int) -> bool:
        user32 = self._user32
        if user32 is None:
            return False
        try:
            return bool(user32.GetAsyncKeyState(int(code)) & 0x8000)
        except Exception:
            return False

    def _is_binding_down(self, value: str) -> bool:
        codes = key_to_vk(value)
        return bool(codes and all(self._is_vk_down(code) for code in codes))

    def _nikaido_has_focus(self) -> bool:
        with self._lock:
            enabled = bool(self._config.get("ignore_when_nikaido_focused", True))
        if not enabled or self._user32 is None:
            return False
        try:
            hwnd = self._user32.GetForegroundWindow()
            if not hwnd:
                return False
            pid = ctypes.c_ulong()
            self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            return int(pid.value) == os.getpid()
        except Exception:
            return False

    @staticmethod
    def _approach(current: float, target: float, dt: float, milliseconds: int) -> float:
        if milliseconds <= 0:
            return target
        step = max(0.0, min(1.0, dt / (milliseconds / 1000.0)))
        result = current + (target - current) * step
        return target if abs(result - target) < 0.001 else result

    @staticmethod
    def _axis_target(negative: bool, positive: bool) -> float:
        return float(int(bool(positive)) - int(bool(negative)))

    @staticmethod
    def _raw_axis(value: float) -> int:
        value = max(-1.0, min(1.0, float(value)))
        return max(0, min(255, round(128 + value * (127 if value >= 0 else 128))))

    def _update_mouse_axis(self, dt: float, config: Mapping[str, Any]) -> Tuple[float, float]:
        if not config["mouse_stick_enabled"]:
            self._mouse_axis = [0.0, 0.0]
            return (0.0, 0.0)
        dx, dy = self._mouse.consume_delta()
        sensitivity = float(config["mouse_sensitivity"])
        raw_x = max(-1.0, min(1.0, dx * sensitivity))
        raw_y = max(-1.0, min(1.0, dy * sensitivity))
        if config["mouse_invert_x"]:
            raw_x *= -1.0
        if config["mouse_invert_y"]:
            raw_y *= -1.0
        smoothing = max(0.0, min(0.90, float(config["mouse_smoothing"]) / 100.0))
        if dx or dy:
            self._mouse_axis[0] = self._mouse_axis[0] * smoothing + raw_x * (1.0 - smoothing)
            self._mouse_axis[1] = self._mouse_axis[1] * smoothing + raw_y * (1.0 - smoothing)
        else:
            decay = max(0.010, float(config["mouse_decay_ms"]) / 1000.0)
            factor = math.exp(-dt / decay)
            self._mouse_axis[0] *= factor
            self._mouse_axis[1] *= factor
            if abs(self._mouse_axis[0]) < 0.001:
                self._mouse_axis[0] = 0.0
            if abs(self._mouse_axis[1]) < 0.001:
                self._mouse_axis[1] = 0.0
        return (float(self._mouse_axis[0]), float(self._mouse_axis[1]))

    def _neutral_state(self) -> KeyboardGamepadState:
        self._sequence = (self._sequence + 1) & 0x7FFFFFFF
        return KeyboardGamepadState(
            sequence=self._sequence,
            monotonic_ns=time.perf_counter_ns(),
            timestamp=time.time(),
        )

    def _build_state(self, dt: float, config: Mapping[str, Any]) -> KeyboardGamepadState:
        mapping = config["mapping"]
        left_x_target = self._axis_target(
            self._is_binding_down(mapping["left_left"]),
            self._is_binding_down(mapping["left_right"]),
        )
        left_y_target = self._axis_target(
            self._is_binding_down(mapping["left_up"]),
            self._is_binding_down(mapping["left_down"]),
        )
        right_x_target = self._axis_target(
            self._is_binding_down(mapping["right_left"]),
            self._is_binding_down(mapping["right_right"]),
        )
        right_y_target = self._axis_target(
            self._is_binding_down(mapping["right_up"]),
            self._is_binding_down(mapping["right_down"]),
        )
        mouse_x, mouse_y = self._update_mouse_axis(dt, config)
        right_x_target = max(-1.0, min(1.0, right_x_target + mouse_x))
        right_y_target = max(-1.0, min(1.0, right_y_target + mouse_y))

        if config["normalize_diagonals"]:
            for pair in (
                ("left", left_x_target, left_y_target),
                ("right", right_x_target, right_y_target),
            ):
                name, x_value, y_value = pair
                magnitude = math.hypot(x_value, y_value)
                if magnitude > 1.0:
                    if name == "left":
                        left_x_target, left_y_target = x_value / magnitude, y_value / magnitude
                    else:
                        right_x_target, right_y_target = x_value / magnitude, y_value / magnitude

        targets = {
            "lx": left_x_target,
            "ly": left_y_target,
            "rx": right_x_target,
            "ry": right_y_target,
        }
        for key, target in targets.items():
            ramp = config["stick_ramp_ms"] if target else config["stick_release_ms"]
            self._axis[key] = self._approach(self._axis[key], target, dt, int(ramp))

        buttons: Dict[str, bool] = {}
        for name in BUTTON_BINDINGS:
            value = mapping.get(name, "")
            buttons[name] = self._is_binding_down(value)

        left_target = 1.0 if buttons.get("L2_btn") else 0.0
        right_target = 1.0 if buttons.get("R2_btn") else 0.0
        trigger_ms = int(config["trigger_ramp_ms"])
        self._trigger["left"] = self._approach(self._trigger["left"], left_target, dt, trigger_ms)
        self._trigger["right"] = self._approach(
            self._trigger["right"], right_target, dt, trigger_ms
        )

        self._sequence = (self._sequence + 1) & 0x7FFFFFFF
        return KeyboardGamepadState(
            left_trigger=round(self._trigger["left"] * 255),
            right_trigger=round(self._trigger["right"] * 255),
            left_stick_x=self._raw_axis(self._axis["lx"]),
            left_stick_y=self._raw_axis(self._axis["ly"]),
            right_stick_x=self._raw_axis(self._axis["rx"]),
            right_stick_y=self._raw_axis(self._axis["ry"]),
            buttons=buttons,
            sequence=self._sequence,
            monotonic_ns=time.perf_counter_ns(),
            timestamp=time.time(),
        )

    def _handle_pause_hotkey(self, config: Mapping[str, Any]) -> None:
        down = self._is_binding_down(config["pause_hotkey"])
        if down and not self._hotkey_was_down:
            self.toggle_suspended()
        self._hotkey_was_down = down

    def _loop(self) -> None:
        last = time.perf_counter()
        next_tick = last
        try:
            while self._running:
                started = time.perf_counter()
                with self._lock:
                    config = copy.deepcopy(self._config)
                    suspended = self._suspended
                interval = 1.0 / max(POLL_HZ_MIN, min(POLL_HZ_MAX, int(config["poll_hz"])))
                now = started
                dt = max(0.0005, min(0.05, now - last))
                last = now
                self._handle_pause_hotkey(config)
                with self._lock:
                    suspended = self._suspended
                focused = self._nikaido_has_focus()
                if suspended:
                    # Pausa real: neutraliza absolutamente todo y descarta deltas.
                    with self._lock:
                        self._axis = {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0}
                        self._trigger = {"left": 0.0, "right": 0.0}
                        self._mouse_axis = [0.0, 0.0]
                    self._mouse.reset()
                    state = self._neutral_state()
                elif focused:
                    # La opción de foco promete ignorar teclas/clics, no matar el
                    # movimiento. Mantener el mouse permite probar el stick desde
                    # Nikaido y evita que parezca desconectado.
                    mouse_only = copy.deepcopy(config)
                    mouse_only["mapping"] = {key: "" for key in (*AXIS_BINDINGS, *BUTTON_BINDINGS)}
                    state = self._build_state(dt, mouse_only)
                else:
                    state = self._build_state(dt, config)
                self._last_state = state
                try:
                    self.emulator.update_from_keyboard(state)
                    with self._lock:
                        self._last_error = ""
                except Exception as exc:
                    message = f"{type(exc).__name__}: {exc}"
                    with self._lock:
                        if message != self._last_error:
                            logger.warning("KeyBridge no pudo actualizar ViGEm: %s", message)
                        self._last_error = message
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                self._diag_ticks += 1
                self._diag_last_tick_ms = elapsed_ms
                self._diag_max_tick_ms = max(self._diag_max_tick_ms, elapsed_ms)
                next_tick += interval
                delay = next_tick - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
                else:
                    next_tick = time.perf_counter()
        finally:
            try:
                self.emulator.release_all_inputs()
            except Exception:
                pass

    def get_diagnostics_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            state = self._last_state
            config = copy.deepcopy(self._config)
            mouse_status = self._mouse.get_status()
            return {
                "available": self.is_available(),
                "running": self.is_running(),
                "enabled": bool(config["enabled"]),
                "suspended": bool(self._suspended),
                "mode": config["mode"],
                "poll_hz": config["poll_hz"],
                "pause_hotkey": config["pause_hotkey"],
                "mouse_enabled": bool(config["mouse_stick_enabled"]),
                "mouse_running": self._mouse.is_running(),
                "mouse_backend": self._mouse.backend,
                "mouse_error": self._mouse.last_error,
                "mouse_packets": mouse_status.get("packets", 0),
                "mouse_cursor_centering": bool(mouse_status.get("cursor_centering", False)),
                "mouse_escape_hotkey": mouse_status.get("escape_hotkey", "CTRL+M"),
                "mouse_emergency_stop_count": int(mouse_status.get("emergency_stop_count", 0)),
                "mouse_emergency_stop_reason": mouse_status.get("emergency_stop_reason", ""),
                "mouse_hotkey_armed": bool(mouse_status.get("hotkey_armed", False)),
                "mouse_hotkey_paused": bool(self._mouse_hotkey_paused),
                "mouse_activation_pending": bool(mouse_status.get("activation_pending", False)),
                "mouse_activation_remaining_seconds": float(
                    mouse_status.get("activation_remaining_seconds", 0.0) or 0.0
                ),
                "mouse_last_toggle_action": mouse_status.get("last_toggle_action", ""),
                "last_error": self._last_error,
                "buttons": sorted(name for name, pressed in state.buttons.items() if pressed),
                "left_stick": (state.left_stick_x, state.left_stick_y),
                "right_stick": (state.right_stick_x, state.right_stick_y),
                "left_trigger": state.left_trigger,
                "right_trigger": state.right_trigger,
                "ticks": self._diag_ticks,
                "tick_last_ms": round(self._diag_last_tick_ms, 3),
                "tick_max_ms": round(self._diag_max_tick_ms, 3),
                "uptime_seconds": round(time.perf_counter() - self._diag_started, 1),
            }
