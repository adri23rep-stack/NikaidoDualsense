"""Salida de mouse relativa para Gyro Aim usando SendInput en Windows."""

from __future__ import annotations

import logging
import sys
import threading

logger = logging.getLogger(__name__)

try:
    if sys.platform == "win32":
        import win32api
        import win32con
        WIN32_MOUSE_AVAILABLE = True
    else:
        WIN32_MOUSE_AVAILABLE = False
except ImportError:
    WIN32_MOUSE_AVAILABLE = False


class GyroMouseOutput:
    """Acumula fracciones para evitar saltos cuando cada tick es < 1 pixel."""

    def __init__(self) -> None:
        self._fraction_x = 0.0
        self._fraction_y = 0.0
        self._lock = threading.Lock()
        self._warned = False

    def is_available(self) -> bool:
        return WIN32_MOUSE_AVAILABLE

    def move(self, dx: float, dy: float) -> bool:
        if not WIN32_MOUSE_AVAILABLE:
            if not self._warned:
                logger.warning("Gyro como mouse requiere Windows y pywin32")
                self._warned = True
            return False

        with self._lock:
            total_x = self._fraction_x + float(dx)
            total_y = self._fraction_y + float(dy)
            move_x = int(total_x)
            move_y = int(total_y)
            self._fraction_x = total_x - move_x
            self._fraction_y = total_y - move_y

        if move_x == 0 and move_y == 0:
            return True

        try:
            win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, move_x, move_y, 0, 0)
            return True
        except Exception as exc:
            logger.debug("No se pudo mover el mouse con gyro: %s", exc)
            return False

    def reset(self) -> None:
        with self._lock:
            self._fraction_x = 0.0
            self._fraction_y = 0.0

    def stop(self) -> None:
        self.reset()
