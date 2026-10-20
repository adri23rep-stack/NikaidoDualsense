"""
Touchpad como Mouse
Usa el touchpad del DualSense para mover el cursor real de Windows.

Como esta pensado:
  - Mientras el dedo esta apoyado en el touchpad (touchpad_active), cada
    lectura nueva se compara contra la anterior y la diferencia (delta) se
    aplica como movimiento RELATIVO del cursor, multiplicada por la
    sensibilidad. Esto es lo mismo que hace cualquier trackpad de
    notebook: no importa la posicion absoluta, importa cuanto se movio el
    dedo entre una lectura y la siguiente.
  - Cuando el dedo se levanta (touchpad_active pasa a False) se olvida la
    ultima posicion, para que al volver a apoyar el dedo no salte el
    cursor de golpe.
  - El boton fisico del touchpad (click) dispara un click izquierdo.
"""

import logging
import threading
from typing import Optional

try:
    import win32api
    import win32con
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

logger = logging.getLogger(__name__)


class TouchpadMouseController:
    """Traduce el touchpad del DualSense en movimiento real del mouse de
    Windows. Se suscribe a connection_manager.on_state_update."""

    def __init__(self, connection_manager=None):
        self.connection_manager = connection_manager
        self._enabled = False
        self._sensitivity = 2.5  # multiplicador de la sensibilidad del movimiento

        self._last_x: Optional[int] = None
        self._last_y: Optional[int] = None
        self._was_button_down = False
        # Evita saltos enormes cuando cambia el ID del dedo o llega una
        # lectura corrupta. El touchpad mide aproximadamente 1920x943, por
        # lo que 500 unidades entre dos lecturas consecutivas ya es un salto
        # imposible durante un uso normal.
        self._max_raw_delta = 500

        self._lock = threading.Lock()

        if self.connection_manager:
            self.connection_manager.on_state_update(self._on_state_update)

    # ===== Configuracion =====

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._enabled = bool(enabled) and WIN32_AVAILABLE
            if not self._enabled:
                self._last_x = None
                self._last_y = None
                self._release_mouse_button_locked()

    def is_enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def is_available(self) -> bool:
        """False si falta pywin32 -- igual que con psutil, la clase sigue
        existiendo pero no hace nada para no romper el resto de la app."""
        return WIN32_AVAILABLE

    def set_sensitivity(self, value: float) -> None:
        with self._lock:
            try:
                value = float(value)
            except (TypeError, ValueError, OverflowError):
                value = 2.5
            self._sensitivity = max(0.1, min(10.0, value))

    def get_sensitivity(self) -> float:
        with self._lock:
            return self._sensitivity

    # ===== Logica principal =====

    def _on_state_update(self, state) -> None:
        if not self._enabled or not WIN32_AVAILABLE:
            return

        try:
            with self._lock:
                self._handle_movement(state)
                self._handle_click(state)
        except Exception as e:
            logger.debug(f"Error en touchpad mouse: {e}")

    def _handle_movement(self, state) -> None:
        if not state.touchpad_active:
            # Dedo levantado: al volver a tocar no queremos que salte el
            # cursor usando una posicion vieja como referencia.
            self._last_x = None
            self._last_y = None
            return

        x, y = state.touchpad_x, state.touchpad_y

        if self._last_x is None:
            # Primer toque de esta "pasada": todavia no hay delta que calcular.
            self._last_x, self._last_y = x, y
            return

        raw_delta_x = x - self._last_x
        raw_delta_y = y - self._last_y

        self._last_x, self._last_y = x, y

        if abs(raw_delta_x) > self._max_raw_delta or abs(raw_delta_y) > self._max_raw_delta:
            logger.debug("Salto anormal del touchpad ignorado: dx=%s dy=%s", raw_delta_x, raw_delta_y)
            return

        delta_x = raw_delta_x * self._sensitivity
        delta_y = raw_delta_y * self._sensitivity

        if abs(delta_x) < 0.5 and abs(delta_y) < 0.5:
            return

        # mouse_event con MOUSEEVENTF_MOVE usa movimiento relativo. Evita la
        # lectura/escritura absoluta del cursor y se comporta mejor con varios
        # monitores y escalado DPI.
        win32api.mouse_event(
            win32con.MOUSEEVENTF_MOVE,
            int(delta_x),
            int(delta_y),
            0,
            0,
        )

    def _handle_click(self, state) -> None:
        is_down = bool(state.buttons.get('touchpad', False))

        if is_down and not self._was_button_down:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        elif not is_down and self._was_button_down:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

        self._was_button_down = is_down

    def _release_mouse_button_locked(self) -> None:
        """Libera el clic si la funcion se desactiva mientras estaba pulsado."""
        if self._was_button_down and WIN32_AVAILABLE:
            try:
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            except Exception as exc:
                logger.debug("No se pudo liberar el clic del touchpad: %s", exc)
        self._was_button_down = False

    def stop(self) -> None:
        """Deja el mouse en un estado seguro al cerrar la aplicacion."""
        self.set_enabled(False)
