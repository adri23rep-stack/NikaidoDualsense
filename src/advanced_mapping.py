"""Remapeo avanzado de botones para Nikaido.

Mantiene separada la lectura fisica del DualSense, las acciones de Windows y
la salida ViGEm. El motor se ejecuta antes de cada envio al gamepad virtual y
solo publica dos cosas al emulador: botones virtuales adicionales y botones
fisicos que deben bloquearse. Asi un binding de teclado, macro o perfil no
necesita escribir directamente sobre ViGEm ni competir con sus otros motores.
"""

from __future__ import annotations

import copy
import logging
import sys
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

from .emulator import REMAPPABLE_BUTTONS

logger = logging.getLogger(__name__)


ACTION_TYPES = (
    "controller", "keyboard", "mouse_button", "mouse_move", "macro",
    "profile", "layer", "gyro", "disabled", "passthrough",
)
ACTIVATIONS = ("hold", "toggle", "press", "release", "short", "long", "double")
MAX_LAYERS = 32
MAX_BINDINGS_PER_SOURCE = 16
MAX_REQUIRED_BUTTONS = 8
MAX_ACTION_VALUE_LENGTH = 256

DEFAULT_CONFIG: Dict[str, Any] = {
    "version": 2,
    "enabled": True,
    "default_layer": "base",
    "layers": {"base": {}},
}


try:
    if sys.platform == "win32":
        import win32api
        import win32con
        WIN32_INPUT_AVAILABLE = True
    else:
        WIN32_INPUT_AVAILABLE = False
except ImportError:
    WIN32_INPUT_AVAILABLE = False


def _clamp_int(value: Any, minimum: int, maximum: int, fallback: int) -> int:
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError, OverflowError):
        return fallback


def _parse_required(value: Any) -> List[str]:
    if isinstance(value, str):
        value = value.replace("+", ",").split(",")
    if not isinstance(value, (list, tuple, set)):
        return []
    clean: List[str] = []
    for button in value:
        name = str(button).strip()
        if name in REMAPPABLE_BUTTONS and name not in clean:
            clean.append(name)
        if len(clean) >= MAX_REQUIRED_BUTTONS:
            break
    return clean


def sanitize_binding(raw: Any) -> Dict[str, Any]:
    """Normaliza un binding de JSON y deja valores seguros para el tick HID."""
    source = raw if isinstance(raw, Mapping) else {}
    action_type = str(source.get("action_type", "controller")).lower().strip()
    if action_type not in ACTION_TYPES:
        action_type = "controller"
    activation = str(source.get("activation", "hold")).lower().strip()
    if activation not in ACTIVATIONS:
        activation = "hold"
    default_block = action_type not in ("passthrough",)
    return {
        "action_type": action_type,
        "value": str(source.get("value", "")).strip()[:MAX_ACTION_VALUE_LENGTH],
        "activation": activation,
        "enabled": bool(source.get("enabled", True)),
        "block_original": bool(source.get("block_original", default_block)),
        "requires": _parse_required(source.get("requires", [])),
        "turbo": bool(source.get("turbo", False)),
        "turbo_hz": _clamp_int(source.get("turbo_hz", 12), 2, 30, 12),
        "long_press_ms": _clamp_int(source.get("long_press_ms", 450), 150, 2000, 450),
        "double_tap_ms": _clamp_int(source.get("double_tap_ms", 280), 120, 800, 280),
        "pulse_ms": _clamp_int(source.get("pulse_ms", 45), 20, 300, 45),
        "label": str(source.get("label", "")).strip()[:80],
        "exclusive_double": bool(source.get("exclusive_double", False)),
    }


def sanitize_config(raw: Any) -> Dict[str, Any]:
    """Migra configuraciones antiguas sin descartar el mapa basico legado."""
    data = raw if isinstance(raw, Mapping) else {}
    layers_raw = data.get("layers", {})
    layers: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    if isinstance(layers_raw, Mapping):
        for layer_name, layer_map in layers_raw.items():
            if len(layers) >= MAX_LAYERS:
                break
            layer_id = str(layer_name).strip().lower().replace(" ", "_")[:40]
            layer_id = "".join(ch for ch in layer_id if ch.isalnum() or ch == "_")
            if not layer_id or layer_id in layers or not isinstance(layer_map, Mapping):
                continue
            clean_map: Dict[str, List[Dict[str, Any]]] = {}
            for source, bindings in layer_map.items():
                if source not in REMAPPABLE_BUTTONS:
                    continue
                if isinstance(bindings, Mapping):
                    bindings = [bindings]
                if not isinstance(bindings, (list, tuple)):
                    continue
                clean = [sanitize_binding(binding) for binding in bindings[:MAX_BINDINGS_PER_SOURCE]]
                if clean:
                    clean_map[source] = clean
            layers[layer_id] = clean_map
    if "base" not in layers:
        # Reserva siempre una de las 32 capas para la base obligatoria.
        # Sin esto un archivo externo podía terminar con 33 capas sanitizadas.
        if len(layers) >= MAX_LAYERS:
            layers.pop(next(reversed(layers)))
        layers["base"] = {}
    default_layer = str(data.get("default_layer", "base")).strip().lower().replace(" ", "_")
    if default_layer not in layers:
        default_layer = "base"
    return {
        "version": 2,
        "enabled": bool(data.get("enabled", True)),
        "default_layer": default_layer,
        "layers": layers,
    }


class KeyboardMouseOutput:
    """Salida Windows de teclado y raton con conteo de referencias seguro."""

    KEY_ALIASES = {
        "CTRL": 0x11, "CONTROL": 0x11, "SHIFT": 0x10, "ALT": 0x12,
        "WIN": 0x5B, "WINDOWS": 0x5B, "TAB": 0x09, "ENTER": 0x0D,
        "ESC": 0x1B, "ESCAPE": 0x1B, "SPACE": 0x20, "BACKSPACE": 0x08,
        "DELETE": 0x2E, "INSERT": 0x2D, "HOME": 0x24, "END": 0x23,
        "PAGEUP": 0x21, "PAGEDOWN": 0x22, "UP": 0x26, "DOWN": 0x28,
        "LEFT": 0x25, "RIGHT": 0x27,
    }
    MOUSE_BUTTONS = {"left", "right", "middle", "x1", "x2"}

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._key_refs: Dict[int, int] = {}
        self._mouse_refs: Dict[str, int] = {}
        self._warned = False

    def is_available(self) -> bool:
        return WIN32_INPUT_AVAILABLE

    @classmethod
    def _key_codes(cls, value: str) -> Tuple[int, ...]:
        codes: List[int] = []
        for token in str(value).upper().replace(" ", "").split("+"):
            if not token:
                continue
            if token in cls.KEY_ALIASES:
                codes.append(cls.KEY_ALIASES[token])
            elif len(token) == 1 and ("A" <= token <= "Z" or "0" <= token <= "9"):
                codes.append(ord(token))
            elif token.startswith("F") and token[1:].isdigit() and 1 <= int(token[1:]) <= 24:
                codes.append(0x6F + int(token[1:]))
        return tuple(codes)

    def _warn_unavailable(self) -> None:
        if not self._warned:
            logger.warning("Remapeo de teclado/raton requiere Windows y pywin32")
            self._warned = True

    def press_keyboard(self, value: str) -> None:
        codes = self._key_codes(value)
        if not codes:
            return
        if not WIN32_INPUT_AVAILABLE:
            self._warn_unavailable()
            return
        with self._lock:
            for code in codes:
                count = self._key_refs.get(code, 0)
                self._key_refs[code] = count + 1
                if count == 0:
                    win32api.keybd_event(code, 0, 0, 0)

    def release_keyboard(self, value: str) -> None:
        codes = self._key_codes(value)
        if not codes or not WIN32_INPUT_AVAILABLE:
            return
        with self._lock:
            for code in reversed(codes):
                count = self._key_refs.get(code, 0)
                if count <= 1:
                    self._key_refs.pop(code, None)
                    win32api.keybd_event(code, 0, win32con.KEYEVENTF_KEYUP, 0)
                else:
                    self._key_refs[code] = count - 1

    @staticmethod
    def _mouse_flags(button: str) -> Tuple[int, int]:
        button = str(button).lower()
        flags = {
            "left": (win32con.MOUSEEVENTF_LEFTDOWN, win32con.MOUSEEVENTF_LEFTUP),
            "right": (win32con.MOUSEEVENTF_RIGHTDOWN, win32con.MOUSEEVENTF_RIGHTUP),
            "middle": (win32con.MOUSEEVENTF_MIDDLEDOWN, win32con.MOUSEEVENTF_MIDDLEUP),
            "x1": (win32con.MOUSEEVENTF_XDOWN, win32con.MOUSEEVENTF_XUP),
            "x2": (win32con.MOUSEEVENTF_XDOWN, win32con.MOUSEEVENTF_XUP),
        }
        return flags.get(button, (0, 0))

    def press_mouse(self, button: str) -> None:
        button = str(button).lower()
        if button not in self.MOUSE_BUTTONS:
            return
        if not WIN32_INPUT_AVAILABLE:
            self._warn_unavailable()
            return
        with self._lock:
            count = self._mouse_refs.get(button, 0)
            self._mouse_refs[button] = count + 1
            if count == 0:
                down, _ = self._mouse_flags(button)
                data = 1 if button == "x1" else 2 if button == "x2" else 0
                win32api.mouse_event(down, 0, 0, data, 0)

    def release_mouse(self, button: str) -> None:
        button = str(button).lower()
        if button not in self.MOUSE_BUTTONS or not WIN32_INPUT_AVAILABLE:
            return
        with self._lock:
            count = self._mouse_refs.get(button, 0)
            if count <= 1:
                self._mouse_refs.pop(button, None)
                _, up = self._mouse_flags(button)
                data = 1 if button == "x1" else 2 if button == "x2" else 0
                win32api.mouse_event(up, 0, 0, data, 0)
            else:
                self._mouse_refs[button] = count - 1

    def move_mouse(self, value: str) -> None:
        try:
            x_text, y_text = str(value).replace(";", ",").split(",", 1)
            dx, dy = int(float(x_text.strip())), int(float(y_text.strip()))
        except (TypeError, ValueError, OverflowError):
            return
        if not WIN32_INPUT_AVAILABLE:
            self._warn_unavailable()
            return
        win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, dx, dy, 0, 0)

    def release_all(self) -> None:
        if not WIN32_INPUT_AVAILABLE:
            self._key_refs.clear()
            self._mouse_refs.clear()
            return
        with self._lock:
            keys = list(self._key_refs)
            mice = list(self._mouse_refs)
            self._key_refs.clear()
            self._mouse_refs.clear()
            for code in reversed(keys):
                try:
                    win32api.keybd_event(code, 0, win32con.KEYEVENTF_KEYUP, 0)
                except Exception:
                    pass
            for button in mice:
                try:
                    _, up = self._mouse_flags(button)
                    data = 1 if button == "x1" else 2 if button == "x2" else 0
                    win32api.mouse_event(up, 0, 0, data, 0)
                except Exception:
                    pass


class AdvancedMapper:
    """Ejecuta bindings por capas con gestos, turbo y bloqueo selectivo."""

    def __init__(
        self, connection_manager=None, emulator=None, macro_engine=None, gyro_engine=None,
        profile_getter: Optional[Callable[[], Optional[str]]] = None,
        profile_applier: Optional[Callable[[str], Any]] = None,
        output: Optional[KeyboardMouseOutput] = None,
    ) -> None:
        self.connection_manager = connection_manager
        self.emulator = emulator or getattr(connection_manager, "emulator", None)
        self.macro_engine = macro_engine
        self.gyro_engine = gyro_engine
        self.profile_getter = profile_getter or (lambda: None)
        self.profile_applier = profile_applier or (lambda _profile: False)
        self.output = output or KeyboardMouseOutput()
        self._lock = threading.RLock()
        self._config = sanitize_config(DEFAULT_CONFIG)
        self._bound_sources: set[str] = set()
        self._layer_base = "base"
        self._current_layer = "base"
        self._presses: Dict[str, Dict[str, Any]] = {}
        self._last_taps: Dict[str, float] = {}
        self._active_actions: Dict[str, Dict[str, Any]] = {}
        self._pulses: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        self._pending_actions: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        self._turbo: Dict[str, Tuple[Dict[str, Any], float]] = {}
        # Las capas activas se apilan por orden, no por "capa anterior".
        # Esto permite soltar modificadores en cualquier orden sin terminar
        # en una capa equivocada. El override más reciente siempre gana.
        self._temporary_layers: Dict[str, Tuple[int, str]] = {}
        self._toggle_layers: Dict[str, Tuple[int, str]] = {}
        self._layer_order = 0
        self._temporary_profiles: Dict[str, Optional[str]] = {}
        self._toggle_profiles: Dict[str, Optional[str]] = {}
        self._last_snapshot = {"buttons": set(), "blocked": set(), "layer": "base"}
        self._pending_profile_config: Optional[Dict[str, Any]] = None
        self._stopped = False
        if connection_manager:
            subscribe = getattr(
                connection_manager,
                "on_realtime_state_update",
                getattr(connection_manager, "on_state_update", None),
            )
            if subscribe:
                subscribe(self._on_state_update)
            connection_manager.on_disconnect(self.reset)

    def get_config(self) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._config)

    def set_config(self, config: Any) -> Dict[str, Any]:
        with self._lock:
            self._pending_profile_config = None
            self._install_config_locked(sanitize_config(config))
            return copy.deepcopy(self._config)

    def queue_profile_config(self, config: Any) -> Dict[str, Any]:
        """Cambia el mapa al terminar el gesto físico actual.

        Un binding puede cambiar de perfil mientras su botón sigue presionado.
        Reemplazar el mapa en ese mismo callback perdería la liberación y podría
        dejar una tecla o capa pegada. La última solicitud gana y se instala
        cuando ya no hay gestos/perfiles temporales activos.
        """
        clean = sanitize_config(config)
        with self._lock:
            if self._presses or self._temporary_profiles or self._toggle_profiles:
                self._pending_profile_config = clean
            else:
                self._install_config_locked(clean)
            return copy.deepcopy(clean)

    def _install_config_locked(self, clean: Dict[str, Any]) -> None:
        self._release_all_locked()
        self._config = clean
        self._bound_sources = {
            source
            for layer in self._config["layers"].values()
            for source in layer
        }
        self._layer_base = self._config["default_layer"]
        self._current_layer = self._layer_base
        self._layer_order = 0
        self._stopped = False

    def _apply_pending_profile_config_locked(self) -> None:
        if (
            self._pending_profile_config is None
            or self._presses
            or self._temporary_profiles
            or self._toggle_profiles
        ):
            return
        clean = self._pending_profile_config
        self._pending_profile_config = None
        self._install_config_locked(clean)

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._config["enabled"] = bool(enabled)
            if not enabled:
                self._release_all_locked()

    def get_active_layer(self) -> str:
        with self._lock:
            return self._current_layer

    def set_active_layer(self, layer: str) -> bool:
        with self._lock:
            if layer in self._config["layers"]:
                self._layer_base = layer
                self._recompute_layer_locked()
                return True
            return False

    def _push_layer_override_locked(self, store: Dict[str, Tuple[int, str]], key: str, target: str) -> None:
        self._layer_order += 1
        store[key] = (self._layer_order, target)
        self._recompute_layer_locked()

    def _recompute_layer_locked(self) -> None:
        candidates = list(self._temporary_layers.values()) + list(self._toggle_layers.values())
        if candidates:
            _order, target = max(candidates, key=lambda item: item[0])
            if target in self._config["layers"]:
                self._current_layer = target
                return
        self._current_layer = (
            self._layer_base
            if self._layer_base in self._config["layers"]
            else self._config["default_layer"]
        )

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "buttons": sorted(self._last_snapshot["buttons"]),
                "blocked": sorted(self._last_snapshot["blocked"]),
                "layer": self._last_snapshot["layer"],
            }

    def _on_state_update(self, state) -> None:
        self.process_state(state)

    def process_state(self, state, now: Optional[float] = None) -> Dict[str, Any]:
        """Procesa un estado; es publico para pruebas y diagnostico sin HID."""
        timestamp = time.monotonic() if now is None else float(now)
        buttons = dict(getattr(state, "buttons", {}) or {})
        with self._lock:
            if self._stopped or not self._config["enabled"]:
                self._publish_locked(set(), set())
                return self.get_snapshot()

            blocked: set[str] = set()
            # Los botones sin bindings pasan directo al emulador. Recorrerlos
            # todos en cada paquete HID añadía trabajo a la ruta de baja
            # latencia aunque el usuario no hubiera configurado el mapper.
            sources = self._bound_sources | set(self._presses)
            # Los cambios de capa se resuelven antes que el resto del mismo
            # paquete. Así L1 + X usa la capa nueva desde el primer frame, sin
            # depender del orden interno de un set de Python.
            ordered_sources = sorted(
                sources,
                key=lambda item: (self._source_priority(item, buttons), item),
            )
            for source in ordered_sources:
                is_down = bool(buttons.get(source))
                press = self._presses.get(source)
                if is_down and press is None:
                    bindings = self._matching_bindings(source, buttons)
                    press = {"started": timestamp, "bindings": bindings, "long": set()}
                    self._presses[source] = press
                    self._on_press(source, press, timestamp)
                elif is_down and press is not None:
                    self._on_hold(source, press, timestamp)
                elif not is_down and press is not None:
                    self._on_release(source, press, timestamp)
                    self._presses.pop(source, None)

                active_press = self._presses.get(source)
                bindings = active_press["bindings"] if active_press else self._matching_bindings(source, buttons)
                if any(binding["block_original"] for _index, binding in bindings):
                    blocked.add(source)

            self._update_turbo(timestamp)
            self._expire_pending_actions(timestamp)
            self._expire_pulses(timestamp)
            virtual_buttons = {
                action["value"] for action in self._active_actions.values()
                if action["action_type"] == "controller" and action["value"] in REMAPPABLE_BUTTONS
            }
            self._publish_locked(virtual_buttons, blocked)
            self._apply_pending_profile_config_locked()
            return self.get_snapshot()

    def _source_priority(self, source: str, buttons: Mapping[str, Any]) -> int:
        if source in self._presses:
            bindings = self._presses[source].get("bindings", [])
        else:
            bindings = self._matching_bindings(source, buttons)
        if any(
            binding.get("action_type") == "layer"
            and binding.get("activation") in ("hold", "press", "toggle")
            for _index, binding in bindings
        ):
            return 0
        return 1

    def _matching_bindings(self, source: str, buttons: Mapping[str, Any]) -> List[Tuple[int, Dict[str, Any]]]:
        layers = self._config["layers"]
        layer_map = layers.get(self._current_layer, {})
        bindings = layer_map.get(source)
        if bindings is None and self._current_layer != "base":
            bindings = layers.get("base", {}).get(source, [])
        result = []
        for index, binding in enumerate(bindings or []):
            if binding["enabled"] and all(bool(buttons.get(required)) for required in binding["requires"]):
                result.append((index, binding))
        return result

    @staticmethod
    def _key(source: str, index: int, binding: Optional[Dict[str, Any]] = None) -> str:
        # El índice solo es único dentro de una capa. Dos reglas cross:0 en
        # capas distintas podían compartir estado de toggle/turbo y apagar la
        # acción equivocada. Cada dict sanitizado vive durante toda la
        # configuración, así que su identidad separa las reglas sin añadir IDs
        # al formato JSON existente.
        token = f"{id(binding):x}" if binding is not None else str(index)
        return f"{source}:{token}"

    def _on_press(self, source: str, press: Dict[str, Any], now: float) -> None:
        bindings = press["bindings"]
        exclusive_doubles = [
            (index, binding)
            for index, binding in bindings
            if binding["activation"] == "double" and binding.get("exclusive_double")
        ]
        exclusive_window_ms = max(
            (binding["double_tap_ms"] for _index, binding in exclusive_doubles),
            default=0,
        )
        press["exclusive_window_ms"] = exclusive_window_ms
        press["double_fired"] = False

        # Primero se resuelven las dobles pulsaciones. Así, cuando la segunda
        # llega, se cancelan las acciones simples pendientes antes de emitir
        # cualquier salida del mismo botón.
        for index, binding in bindings:
            if binding["activation"] != "double":
                continue
            key = self._key(source, index, binding)
            previous = self._last_taps.get(key)
            if previous is not None and (now - previous) * 1000 <= binding["double_tap_ms"]:
                self._last_taps.pop(key, None)
                press["double_fired"] = True
                if binding.get("exclusive_double"):
                    self._cancel_pending_for_source(source)
                self._activate(key, binding, now, held=False)
            else:
                self._last_taps[key] = now

        for index, binding in bindings:
            key = self._key(source, index, binding)
            activation = binding["activation"]
            if activation == "double":
                continue
            if activation == "hold":
                if binding["turbo"] and binding["action_type"] in ("controller", "keyboard", "mouse_button", "mouse_move"):
                    self._turbo[key] = (binding, now)
                else:
                    self._activate(key, binding, now, held=True)
            elif activation == "toggle":
                self._toggle(key, binding, now)
            elif activation == "press":
                if exclusive_window_ms and not press["double_fired"]:
                    self._pending_actions[key] = (
                        now + exclusive_window_ms / 1000.0,
                        binding,
                    )
                elif not press["double_fired"]:
                    self._activate(key, binding, now, held=False)

    def _on_hold(self, source: str, press: Dict[str, Any], now: float) -> None:
        elapsed_ms = (now - press["started"]) * 1000
        for index, binding in press["bindings"]:
            if binding["activation"] != "long" or index in press["long"]:
                continue
            if elapsed_ms >= binding["long_press_ms"]:
                press["long"].add(index)
                self._activate(self._key(source, index, binding), binding, now, held=True)

    def _on_release(self, source: str, press: Dict[str, Any], now: float) -> None:
        elapsed_ms = (now - press["started"]) * 1000
        for index, binding in press["bindings"]:
            key = self._key(source, index, binding)
            activation = binding["activation"]
            if activation == "hold":
                self._turbo.pop(key, None)
                self._deactivate(key)
            elif activation == "long" and index in press["long"]:
                self._deactivate(key)
            elif activation == "release":
                self._activate(key, binding, now, held=False)
            elif activation == "short" and elapsed_ms < binding["long_press_ms"]:
                window_ms = int(press.get("exclusive_window_ms", 0) or 0)
                if window_ms and not press.get("double_fired", False):
                    first_press = float(press.get("started", now))
                    self._pending_actions[key] = (
                        max(now, first_press + window_ms / 1000.0),
                        binding,
                    )
                elif not press.get("double_fired", False):
                    self._activate(key, binding, now, held=False)

    def _activate(self, key: str, binding: Dict[str, Any], now: float, *, held: bool, toggle: bool = False) -> None:
        action_type = binding["action_type"]
        if action_type == "macro":
            if self.macro_engine and binding["value"]:
                self.macro_engine.play_macro(binding["value"])
            return
        if action_type == "layer":
            target = binding["value"]
            if target not in self._config["layers"]:
                return
            if held:
                self._push_layer_override_locked(self._temporary_layers, key, target)
            else:
                self._layer_base = target
                self._recompute_layer_locked()
            return
        if action_type == "profile":
            target = binding["value"]
            if not target:
                return
            previous = self.profile_getter()
            if held:
                self._temporary_profiles[key] = previous
                self.profile_applier(target)
            else:
                self.profile_applier(target)
            return
        if action_type == "gyro":
            self._run_gyro_action(binding["value"])
            return
        if action_type in ("disabled", "passthrough"):
            return
        self._set_direct_active(key, binding, True)
        if not held:
            self._pulses[key] = (now + binding["pulse_ms"] / 1000.0, binding)

    def _run_gyro_action(self, value: str) -> None:
        engine = self.gyro_engine
        if not engine:
            return
        action = str(value).strip().lower()
        try:
            if action == "recenter":
                engine.recenter()
            elif action == "toggle":
                config = engine.get_config()
                engine.update_config(enabled=not bool(config.enabled))
            elif action == "enable":
                engine.update_config(enabled=True)
            elif action == "disable":
                engine.update_config(enabled=False)
        except Exception as exc:
            logger.debug("Acción de giroscopio falló: %s", exc)

    def get_diagnostics_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "enabled": bool(self._config.get("enabled", True)),
                "active_layer": self._current_layer,
                "layers": len(self._config.get("layers", {})),
                "layer_overrides": len(self._temporary_layers) + len(self._toggle_layers),
                "bound_sources": len(self._bound_sources),
                "pressed_sources": sorted(self._presses),
                "active_actions": len(self._active_actions),
                "turbo_actions": len(self._turbo),
                "pending_actions": len(self._pending_actions),
                "profile_config_pending": self._pending_profile_config is not None,
                "virtual_buttons": sorted(self._last_snapshot["buttons"]),
                "blocked_buttons": sorted(self._last_snapshot["blocked"]),
            }

    def _toggle(self, key: str, binding: Dict[str, Any], now: float) -> None:
        """Alterna una salida persistente, una capa o un perfil sin pegarlos."""
        action_type = binding["action_type"]
        if action_type == "layer":
            target = binding["value"]
            if target not in self._config["layers"]:
                return
            if key in self._toggle_layers:
                self._toggle_layers.pop(key, None)
                self._recompute_layer_locked()
            else:
                self._push_layer_override_locked(self._toggle_layers, key, target)
            return
        if action_type == "profile":
            target = binding["value"]
            if not target:
                return
            if key in self._toggle_profiles:
                previous = self._toggle_profiles.pop(key)
                if previous:
                    self.profile_applier(previous)
            else:
                self._toggle_profiles[key] = self.profile_getter()
                self.profile_applier(target)
            return
        if key in self._active_actions:
            self._deactivate(key)
        else:
            self._activate(key, binding, now, held=True)

    def _deactivate(self, key: str) -> None:
        if key in self._temporary_layers:
            self._temporary_layers.pop(key, None)
            self._recompute_layer_locked()
        if key in self._temporary_profiles:
            previous = self._temporary_profiles.pop(key)
            if previous:
                self.profile_applier(previous)
        self._turbo.pop(key, None)
        self._pulses.pop(key, None)
        self._set_direct_active(key, None, False)

    def _set_direct_active(self, key: str, binding: Optional[Dict[str, Any]], active: bool) -> None:
        existing = self._active_actions.get(key)
        if active:
            if existing:
                return
            if not binding:
                return
            self._active_actions[key] = binding
            action_type, value = binding["action_type"], binding["value"]
            if action_type == "keyboard":
                self.output.press_keyboard(value)
            elif action_type == "mouse_button":
                self.output.press_mouse(value)
            elif action_type == "mouse_move":
                self.output.move_mouse(value)
        elif existing:
            self._active_actions.pop(key, None)
            action_type, value = existing["action_type"], existing["value"]
            if action_type == "keyboard":
                self.output.release_keyboard(value)
            elif action_type == "mouse_button":
                self.output.release_mouse(value)

    def _update_turbo(self, now: float) -> None:
        for key, (binding, started) in list(self._turbo.items()):
            phase = int((now - started) * binding["turbo_hz"] * 2) % 2 == 0
            self._set_direct_active(key, binding, phase)

    def _cancel_pending_for_source(self, source: str) -> None:
        prefix = f"{source}:"
        for key in [item for item in self._pending_actions if item.startswith(prefix)]:
            self._pending_actions.pop(key, None)

    def _expire_pending_actions(self, now: float) -> None:
        for key, (deadline, binding) in list(self._pending_actions.items()):
            if now >= deadline:
                self._pending_actions.pop(key, None)
                self._activate(key, binding, now, held=False)

    def _expire_pulses(self, now: float) -> None:
        for key, (expiry, _binding) in list(self._pulses.items()):
            if now >= expiry:
                self._pulses.pop(key, None)
                self._set_direct_active(key, None, False)

    def _publish_locked(self, buttons: Iterable[str], blocked: Iterable[str]) -> None:
        button_set, blocked_set = set(buttons), set(blocked)
        self._last_snapshot = {"buttons": button_set, "blocked": blocked_set, "layer": self._current_layer}
        if self.emulator and hasattr(self.emulator, "set_advanced_button_state"):
            self.emulator.set_advanced_button_state(button_set, blocked_set)

    def _release_all_locked(self) -> None:
        for key in list(self._active_actions):
            self._set_direct_active(key, None, False)
        self._presses.clear()
        self._last_taps.clear()
        self._pulses.clear()
        self._pending_actions.clear()
        self._turbo.clear()
        self._temporary_layers.clear()
        self._toggle_layers.clear()
        self._recompute_layer_locked()
        restore_profiles = list(self._temporary_profiles.values()) + list(self._toggle_profiles.values())
        self._temporary_profiles.clear()
        self._toggle_profiles.clear()
        for previous in restore_profiles:
            if previous:
                try:
                    self.profile_applier(previous)
                except Exception:
                    pass
        self.output.release_all()
        self._publish_locked(set(), set())

    def reset(self) -> None:
        with self._lock:
            self._release_all_locked()
            self._layer_base = self._config["default_layer"]
            self._current_layer = self._layer_base

    def stop(self) -> None:
        with self._lock:
            self._pending_profile_config = None
            self._release_all_locked()
            self._stopped = True
