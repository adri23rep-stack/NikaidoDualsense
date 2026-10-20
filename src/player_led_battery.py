"""Indicador de batería mediante las luces blancas del jugador.

Este módulo no depende de Qt y mantiene un solo escritor lógico para los
indicadores. Puede mostrar batería, conservar el número de jugador, entregar el
control al juego o apagar las luces.
"""

from __future__ import annotations

import copy
import logging
import threading
from typing import Any, Mapping, Optional

logger = logging.getLogger(__name__)

PLAYER_PATTERNS = {
    0: 0,
    1: 0b00100,
    2: 0b01010,
    3: 0b10101,
    4: 0b11011,
    5: 0b11111,
}

PLAYER_LED_MODES = {
    "battery": "Batería",
    "player": "Número de jugador",
    "game": "Controlado por el juego",
    "off": "Apagado",
}

DEFAULT_PLAYER_LED_CONFIG = {
    "mode": "battery",
    "player_number": 1,
    "charging_animation": True,
    "critical_blink": True,
    "critical_percent": 10,
}


def sanitize_player_led_config(data: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    source = data if isinstance(data, Mapping) else {}
    config = copy.deepcopy(DEFAULT_PLAYER_LED_CONFIG)
    mode = str(source.get("mode", config["mode"]) or "battery").strip().lower()
    config["mode"] = mode if mode in PLAYER_LED_MODES else "battery"
    try:
        config["player_number"] = max(1, min(5, int(source.get("player_number", 1))))
    except (TypeError, ValueError, OverflowError):
        config["player_number"] = 1
    config["charging_animation"] = bool(source.get("charging_animation", True))
    config["critical_blink"] = bool(source.get("critical_blink", True))
    try:
        config["critical_percent"] = max(
            1, min(25, int(source.get("critical_percent", 10)))
        )
    except (TypeError, ValueError, OverflowError):
        config["critical_percent"] = 10
    return config


def battery_segments(level: Any) -> int:
    """Convierte 0-100 % a cuatro niveles visibles."""
    try:
        percent = max(0, min(100, int(level)))
    except (TypeError, ValueError, OverflowError):
        percent = 0
    if percent >= 76:
        return 4
    if percent >= 51:
        return 3
    if percent >= 26:
        return 2
    return 1


class PlayerLedBatteryController:
    """Mantiene el patrón de luces de jugador según batería y preferencias."""

    TICK_SECONDS = 0.55

    def __init__(self, connection_manager=None, config: Optional[Mapping[str, Any]] = None):
        self.connection_manager = connection_manager
        self._config = sanitize_player_led_config(config)
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._connected = bool(
            connection_manager and getattr(connection_manager, "is_connected", False)
        )
        self._battery_level = 0
        self._charging_status: Any = None
        self._battery_known = False
        self._animation_step = 0
        self._blink_on = True
        self._last_pattern: Optional[int] = None
        self._thread = threading.Thread(
            target=self._loop,
            name="DualSensePlayerBattery",
            daemon=True,
        )

        if connection_manager:
            if hasattr(connection_manager, "get_battery_info"):
                try:
                    self._battery_level, self._charging_status = (
                        connection_manager.get_battery_info()
                    )
                    status_value = self._status_value(self._charging_status)
                    self._battery_known = bool(
                        self._battery_level > 0
                        or status_value not in {"", "desconocido", "unknown", "none"}
                    )
                except Exception:
                    pass
            if hasattr(connection_manager, "on_connect"):
                connection_manager.on_connect(self._on_connect)
            if hasattr(connection_manager, "on_disconnect"):
                connection_manager.on_disconnect(self._on_disconnect)
            if hasattr(connection_manager, "on_battery_change"):
                connection_manager.on_battery_change(self._on_battery)

        self._thread.start()
        self.refresh(force=True)

    def get_config(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._config)

    def apply_config(self, data: Optional[Mapping[str, Any]]) -> dict[str, Any]:
        config = sanitize_player_led_config(data)
        with self._lock:
            self._config = config
            self._animation_step = 0
            self._blink_on = True
            self._last_pattern = None
        self._wake_event.set()
        self.refresh(force=True)
        return copy.deepcopy(config)

    def set_mode(self, mode: str) -> None:
        config = self.get_config()
        config["mode"] = mode
        self.apply_config(config)

    def set_player_number(self, player_number: int) -> None:
        config = self.get_config()
        config["player_number"] = player_number
        self.apply_config(config)

    @staticmethod
    def _status_value(status: Any) -> str:
        return str(getattr(status, "value", status) or "").strip().lower()

    def _on_connect(self, _connection: Any) -> None:
        with self._lock:
            self._connected = True
            self._last_pattern = None
        self._wake_event.set()
        self.refresh(force=True)

    def _on_disconnect(self) -> None:
        with self._lock:
            self._connected = False
            self._last_pattern = None
        self._wake_event.set()

    def _on_battery(self, level: int, status: Any) -> None:
        with self._lock:
            self._battery_level = max(0, min(100, int(level)))
            self._charging_status = status
            status_value = self._status_value(status)
            self._battery_known = bool(
                self._battery_level > 0
                or status_value not in {"", "desconocido", "unknown", "none"}
            )
            self._animation_step = 0
            self._blink_on = True
        self._wake_event.set()
        self.refresh(force=True)

    def _target_pattern(self, *, animate: bool) -> Optional[int]:
        with self._lock:
            config = dict(self._config)
            level = self._battery_level
            status = self._status_value(self._charging_status)
            battery_known = self._battery_known

        mode = config["mode"]
        if mode == "game":
            return None
        if mode == "off":
            return PLAYER_PATTERNS[0]
        if mode == "player":
            return PLAYER_PATTERNS.get(config["player_number"], PLAYER_PATTERNS[1])
        if not battery_known:
            # Durante los primeros milisegundos de conexión el estado suele ser
            # 0/desconocido. No lo mostramos como batería crítica.
            return None

        segments = battery_segments(level)
        charged = status in {"cargado completo", "charged", "full"}
        charging = status in {"cargando", "charging"}
        critical = level <= int(config["critical_percent"])

        if charged:
            return PLAYER_PATTERNS[4]
        if charging and config["charging_animation"]:
            if animate:
                with self._lock:
                    self._animation_step = (self._animation_step % 4) + 1
                    step = self._animation_step
            else:
                step = max(1, min(4, self._animation_step or segments))
            return PLAYER_PATTERNS[step]
        if critical and config["critical_blink"]:
            if animate:
                with self._lock:
                    self._blink_on = not self._blink_on
                    visible = self._blink_on
            else:
                visible = self._blink_on
            return PLAYER_PATTERNS[1] if visible else PLAYER_PATTERNS[0]
        return PLAYER_PATTERNS[segments]

    def refresh(self, *, force: bool = False, animate: bool = False) -> bool:
        with self._lock:
            connected = self._connected
            manager = self.connection_manager
        if not connected or manager is None:
            return False
        pattern = self._target_pattern(animate=animate)
        if pattern is None:
            # Modo juego: Nikaido deja de emitir órdenes y no intenta adivinar
            # el estado que el juego quiera mostrar.
            with self._lock:
                self._last_pattern = None
            return False
        with self._lock:
            if not force and pattern == self._last_pattern:
                return True
        setter = getattr(manager, "set_player_led_pattern", None)
        success = bool(setter(pattern)) if callable(setter) else False
        if success:
            with self._lock:
                self._last_pattern = pattern
        return success

    def _needs_animation(self) -> bool:
        with self._lock:
            if not self._connected or self._config["mode"] != "battery":
                return False
            level = self._battery_level
            status = self._status_value(self._charging_status)
            config = dict(self._config)
            battery_known = self._battery_known
        if not battery_known:
            return False
        return bool(
            (status in {"cargando", "charging"} and config["charging_animation"])
            or (level <= config["critical_percent"] and config["critical_blink"])
        )

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            if self._needs_animation():
                self.refresh(animate=True)
                self._stop_event.wait(self.TICK_SECONDS)
            else:
                self._wake_event.wait(2.0)
                self._wake_event.clear()

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        if self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=0.8)
