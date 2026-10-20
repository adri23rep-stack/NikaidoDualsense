"""
Motor de Emulacion de Controles.
Traduce el DualSense fisico a Xbox 360 o DS4 virtual mediante vgamepad.
El mismo hilo que lee el control es el unico que escribe a ViGEm.
"""

import logging
import math
import threading
import time
from collections import deque
from enum import Enum

try:
    import vgamepad as vg
    VGAMEPAD_AVAILABLE = True
except ImportError:
    vg = None
    VGAMEPAD_AVAILABLE = False
    logging.warning("Libreria vgamepad no encontrada. La emulacion estara desactivada.")

from .gyro_virtual_ds4 import DS4ExtendedReportAdapter
from .mouse_to_gyro import MouseGyroSource

logger = logging.getLogger(__name__)


class EmulationMode(Enum):
    NONE = "none"
    XBOX = "xbox"
    PS4 = "ps4"


REMAPPABLE_BUTTONS = [
    'cross', 'circle', 'square', 'triangle',
    'L1', 'R1', 'L2_btn', 'R2_btn', 'L3', 'R3',
    'options', 'create', 'ps', 'touchpad',
    'dpad_up', 'dpad_down', 'dpad_left', 'dpad_right',
]

BUTTON_FRIENDLY_NAMES = {
    'cross': 'Cruz (X)', 'circle': 'Circulo', 'square': 'Cuadrado',
    'triangle': 'Triangulo', 'L1': 'L1', 'R1': 'R1',
    'L2_btn': 'L2 digital', 'R2_btn': 'R2 digital',
    'L3': 'L3 (click palanca izquierda)', 'R3': 'R3 (click palanca derecha)',
    'options': 'Options / Start', 'create': 'Create / Share',
    'ps': 'PS / Guide', 'touchpad': 'Click touchpad',
    'dpad_up': 'Dpad Arriba', 'dpad_down': 'Dpad Abajo',
    'dpad_left': 'Dpad Izquierda', 'dpad_right': 'Dpad Derecha',
}


class EmulatorManager:
    def __init__(self):
        self.mode = EmulationMode.NONE
        self.gamepad = None
        self.is_active = False
        self._macro_overrides = set()
        # Cada hilo de macro conserva la propiedad de sus entradas. Antes, dos
        # macros sosteniendo el mismo botón/palanca/gatillo se podían liberar
        # entre sí cuando una terminaba primero.
        self._macro_button_owners = {}
        self._macro_stick_overrides = {}
        self._macro_trigger_overrides = {}
        self._macro_override_sequence = 0
        self._macro_lock = threading.Lock()
        self._state_lock = threading.RLock()
        self._mode_lock = threading.RLock()
        # Solo una fuente puede alimentar ViGEm a la vez. El DualSense físico
        # sigue siendo la fuente predeterminada; Nikaido KeyBridge toma el
        # control temporalmente cuando teclado/mouse emulan un gamepad.
        self._input_source = 'dualsense'
        self._button_map = {}
        self._advanced_buttons = set()
        self._advanced_blocked_sources = set()
        self._effective_buttons = {}
        self._right_stick_override = None
        # El procesador es opcional para que la emulacion siga funcionando si
        # Input Studio no esta inicializado (o en instalaciones antiguas).
        self._input_processor = None
        self._last_virtual_sticks = {'left': (0.0, 0.0), 'right': (0.0, 0.0)}
        self._last_virtual_output = {
            'active': False, 'mode': 'none', 'sequence': -1, 'source': 'none',
            'buttons': [], 'left_stick': (0.0, 0.0), 'right_stick': (0.0, 0.0),
            'left_trigger': 0, 'right_trigger': 0, 'updated_ns': 0,
        }
        self._ds4_motion_passthrough = False
        self._gyro_signs = (1, 1, 1)
        self._accel_signs = (1, 1, 1)
        self._gyro_bias = (0.0, 0.0, 0.0)
        self._gyro_bias_trusted = False
        self._gyro_axes = (0, 1, 2)
        self._accel_axes = (0, 1, 2)
        self._gyro_deadzone = 6.0
        self._mouse_to_gyro = MouseGyroSource()
        self._mouse_to_gyro.set_emergency_stop_callback(
            self._handle_mouse_to_gyro_emergency_stop
        )
        self._mouse_to_gyro_escape_callbacks = []
        self._mouse_to_gyro_enabled = False
        self._mouse_to_gyro_hotkey_paused = False
        self._mouse_to_gyro_sensitivity = 0.12
        self._mouse_to_gyro_invert_x = False
        self._mouse_to_gyro_invert_y = False
        self._mouse_to_gyro_combine = False
        self._mouse_to_gyro_max_dps = 1400.0
        self._last_motion_tick = time.perf_counter()
        self._ds4_report_adapter = DS4ExtendedReportAdapter(vg_module=vg)
        self._last_update_error = None
        # Feedback enviado por el juego al dispositivo virtual. El callback de
        # vgamepad se conserva como atributo porque internamente usa ctypes.
        self._feedback_callbacks = []
        self._feedback_callback_ref = None
        self._feedback_registered = False
        self._feedback_supported = False
        self._feedback_count = 0
        self._feedback_errors = 0
        self._last_feedback = {
            'large_motor': 0, 'small_motor': 0, 'led_number': 0,
            'mode': 'none', 'received_ns': 0,
        }
        self._diag_virtual_times = deque(maxlen=1200)
        self._diag_update_ms = deque(maxlen=600)
        self._diag_total_updates = 0
        self._diag_errors = 0
        self._diag_started = time.perf_counter()

    def on_mouse_to_gyro_emergency_stop(self, callback) -> None:
        """Avisa cuando Ctrl+M libera el cursor de mouse → gyro."""
        if not callable(callback):
            raise TypeError("El callback debe ser invocable")
        with self._state_lock:
            if callback not in self._mouse_to_gyro_escape_callbacks:
                self._mouse_to_gyro_escape_callbacks.append(callback)

    def _handle_mouse_to_gyro_emergency_stop(self) -> None:
        with self._state_lock:
            if not self._mouse_to_gyro_enabled:
                return
            capture_active = bool(
                self._mouse_to_gyro.is_running()
                or self._mouse_to_gyro_pending()
            )
            self._mouse_to_gyro_hotkey_paused = capture_active
            callbacks = tuple(self._mouse_to_gyro_escape_callbacks)
        if capture_active:
            self._mouse_to_gyro.stop()
            self._note_mouse_to_gyro_toggle("disabled")
        else:
            # La espera de cinco segundos solo se usa al habilitar la opción
            # desde la interfaz. Ctrl+M debe reanudar el gyro de inmediato.
            self._note_mouse_to_gyro_toggle("enabling")
            started = self._start_mouse_to_gyro_immediate()
            self._note_mouse_to_gyro_toggle("enabled" if started else "failed")
        for callback in callbacks:
            try:
                callback()
            except Exception:
                logger.exception("Callback de liberación mouse → gyro falló")

    def _arm_mouse_to_gyro_hotkey(self, enabled: bool) -> bool:
        arm = getattr(self._mouse_to_gyro, "arm_hotkey_toggle", None)
        return bool(arm(bool(enabled))) if callable(arm) else True

    def _mouse_to_gyro_pending(self) -> bool:
        pending = getattr(self._mouse_to_gyro, "is_activation_pending", None)
        if callable(pending):
            return bool(pending())
        status = getattr(self._mouse_to_gyro, "get_status", lambda: {})()
        return bool(status.get("activation_pending", False))

    def _start_mouse_to_gyro_delayed(self) -> bool:
        with self._state_lock:
            allowed = bool(
                self._mouse_to_gyro_enabled
                and self.mode == EmulationMode.PS4
                and self.is_active
                and self._input_source == "dualsense"
            )
            if allowed:
                self._mouse_to_gyro_hotkey_paused = False
        if not allowed:
            return False
        self._arm_mouse_to_gyro_hotkey(True)
        starter = getattr(self._mouse_to_gyro, "start_delayed", None)
        if callable(starter):
            return bool(starter(MouseGyroSource.DEFAULT_ACTIVATION_DELAY_SECONDS))
        return bool(self._mouse_to_gyro.start())

    def _start_mouse_to_gyro_immediate(self) -> bool:
        """Reactiva Mouse → Gyro al instante desde Ctrl+M."""
        with self._state_lock:
            allowed = bool(
                self._mouse_to_gyro_enabled
                and self.mode == EmulationMode.PS4
                and self.is_active
                and self._input_source == "dualsense"
            )
            if allowed:
                self._mouse_to_gyro_hotkey_paused = False
        if not allowed:
            return False
        self._arm_mouse_to_gyro_hotkey(True)
        started = bool(self._mouse_to_gyro.start())
        if not started:
            with self._state_lock:
                self._mouse_to_gyro_hotkey_paused = True
        return started

    def _note_mouse_to_gyro_toggle(self, action: str) -> None:
        note = getattr(self._mouse_to_gyro, "note_toggle_action", None)
        if callable(note):
            note(action)

    def on_feedback(self, callback) -> None:
        """Suscribe un receptor ligero al rumble/LED recibido desde ViGEm."""
        if not callable(callback):
            raise TypeError("El callback debe ser invocable")
        with self._state_lock:
            if callback not in self._feedback_callbacks:
                self._feedback_callbacks.append(callback)

    def remove_feedback_callback(self, callback) -> None:
        with self._state_lock:
            self._feedback_callbacks[:] = [item for item in self._feedback_callbacks if item != callback]

    @staticmethod
    def _feedback_byte(value) -> int:
        try:
            return max(0, min(255, int(value)))
        except (TypeError, ValueError, OverflowError):
            return 0

    def _publish_feedback(self, large_motor, small_motor, led_number=0) -> None:
        snapshot = {
            'large_motor': self._feedback_byte(large_motor),
            'small_motor': self._feedback_byte(small_motor),
            'led_number': self._feedback_byte(led_number),
            'mode': self.mode.value,
            'received_ns': time.perf_counter_ns(),
        }
        with self._state_lock:
            self._last_feedback = snapshot
            self._feedback_count += 1
            callbacks = tuple(self._feedback_callbacks)
        failed = []
        for callback in callbacks:
            try:
                callback(dict(snapshot))
            except Exception:
                logger.exception("Callback de feedback virtual desactivado tras fallar")
                failed.append(callback)
        if failed:
            with self._state_lock:
                self._feedback_callbacks[:] = [
                    item for item in self._feedback_callbacks if item not in failed
                ]

    def _register_feedback_notification(self, gamepad) -> bool:
        register = getattr(gamepad, 'register_notification', None)
        self._feedback_supported = callable(register)
        self._feedback_registered = False
        self._feedback_callback_ref = None
        if not callable(register):
            return False

        def feedback_callback(_client, _target, large_motor, small_motor, led_number, _user_data):
            try:
                self._publish_feedback(large_motor, small_motor, led_number)
            except Exception as exc:
                with self._state_lock:
                    self._feedback_errors += 1
                logger.debug("Callback de feedback ViGEm falló: %s", exc)

        self._feedback_callback_ref = feedback_callback
        try:
            try:
                register(callback_function=feedback_callback)
            except TypeError:
                register(feedback_callback)
            self._feedback_registered = True
            return True
        except Exception as exc:
            with self._state_lock:
                self._feedback_errors += 1
            logger.warning("ViGEm no permitió registrar feedback: %s", exc)
            self._feedback_callback_ref = None
            return False

    def _unregister_feedback_notification(self, gamepad) -> None:
        unregister = getattr(gamepad, 'unregister_notification', None)
        if callable(unregister) and self._feedback_registered:
            try:
                unregister()
            except Exception as exc:
                logger.debug("No se pudo retirar el callback de feedback: %s", exc)
        self._feedback_registered = False
        self._feedback_callback_ref = None

    def get_feedback_snapshot(self) -> dict:
        with self._state_lock:
            return dict(self._last_feedback)

    def set_button_map(self, mapping: dict) -> None:
        with self._state_lock:
            self._button_map = {k: v for k, v in (mapping or {}).items() if v}

    def get_button_map(self) -> dict:
        with self._state_lock:
            return dict(self._button_map)

    def set_advanced_button_state(self, buttons, blocked_sources=()) -> None:
        """Recibe la salida del remapeador avanzado para el siguiente tick.

        Los botones en ``buttons`` se suman a la salida virtual; los de
        ``blocked_sources`` no pasan por el remapeo basico. Es la unica puerta
        de entrada para que teclado, macros, capas y gestos afecten ViGEm.
        """
        with self._state_lock:
            self._advanced_buttons = {
                button for button in (buttons or ()) if button in REMAPPABLE_BUTTONS
            }
            self._advanced_blocked_sources = {
                button for button in (blocked_sources or ()) if button in REMAPPABLE_BUTTONS
            }

    def get_advanced_button_state(self) -> dict:
        """Estado inmutable util para diagnostico y pruebas."""
        with self._state_lock:
            return {
                'buttons': set(self._advanced_buttons),
                'blocked_sources': set(self._advanced_blocked_sources),
            }

    def _remap_buttons(self, physical_buttons: dict) -> dict:
        effective = {}
        for physical, pressed in (physical_buttons or {}).items():
            if not pressed:
                continue
            if physical in self._advanced_blocked_sources:
                continue
            target = self._button_map.get(physical, physical)
            if target and target != 'none':
                effective[target] = True
        for target in self._advanced_buttons:
            effective[target] = True
        return effective

    @staticmethod
    def _macro_owner() -> int:
        return threading.get_ident()

    def _clear_macro_overrides_locked(self) -> None:
        self._macro_overrides.clear()
        self._macro_button_owners.clear()
        self._macro_stick_overrides.clear()
        self._macro_trigger_overrides.clear()

    def _next_macro_override_sequence_locked(self) -> int:
        self._macro_override_sequence += 1
        return self._macro_override_sequence

    def macro_press(self, button_name: str) -> None:
        if button_name not in REMAPPABLE_BUTTONS:
            return
        owner = self._macro_owner()
        with self._macro_lock:
            self._macro_button_owners.setdefault(button_name, set()).add(owner)
            self._macro_overrides.add(button_name)

    def macro_release(self, button_name: str) -> None:
        owner = self._macro_owner()
        with self._macro_lock:
            owners = self._macro_button_owners.get(button_name)
            if owners is None:
                # Compatibilidad con integraciones antiguas que escribieran
                # directamente al conjunto antes de usar macro_release().
                self._macro_overrides.discard(button_name)
                return
            owners.discard(owner)
            if not owners:
                self._macro_button_owners.pop(button_name, None)
                self._macro_overrides.discard(button_name)

    def macro_clear(self) -> None:
        with self._macro_lock:
            self._clear_macro_overrides_locked()

    def macro_set_stick(self, stick: str, x: float, y: float) -> None:
        if stick not in ('left', 'right'):
            return
        owner = self._macro_owner()
        try:
            safe_x = float(x)
        except (TypeError, ValueError, OverflowError):
            safe_x = 0.0
        try:
            safe_y = float(y)
        except (TypeError, ValueError, OverflowError):
            safe_y = 0.0
        if not math.isfinite(safe_x):
            safe_x = 0.0
        if not math.isfinite(safe_y):
            safe_y = 0.0
        value = (
            max(-1.0, min(1.0, safe_x)),
            max(-1.0, min(1.0, safe_y)),
        )
        with self._macro_lock:
            sequence = self._next_macro_override_sequence_locked()
            self._macro_stick_overrides.setdefault(stick, {})[owner] = (sequence, value)

    def macro_clear_stick(self, stick: str) -> None:
        owner = self._macro_owner()
        with self._macro_lock:
            owners = self._macro_stick_overrides.get(stick)
            if not owners:
                return
            owners.pop(owner, None)
            if not owners:
                self._macro_stick_overrides.pop(stick, None)

    def macro_clear_sticks(self) -> None:
        with self._macro_lock:
            self._macro_stick_overrides.clear()

    def macro_set_trigger(self, trigger: str, value: int) -> None:
        if trigger not in ('left', 'right'):
            return
        owner = self._macro_owner()
        try:
            numeric = float(value)
            clamped = 0 if not math.isfinite(numeric) else max(0, min(255, int(numeric)))
        except (TypeError, ValueError, OverflowError):
            clamped = 0
        with self._macro_lock:
            sequence = self._next_macro_override_sequence_locked()
            self._macro_trigger_overrides.setdefault(trigger, {})[owner] = (sequence, clamped)

    def macro_clear_trigger(self, trigger: str) -> None:
        owner = self._macro_owner()
        with self._macro_lock:
            owners = self._macro_trigger_overrides.get(trigger)
            if not owners:
                return
            owners.pop(owner, None)
            if not owners:
                self._macro_trigger_overrides.pop(trigger, None)

    def macro_clear_triggers(self) -> None:
        with self._macro_lock:
            self._macro_trigger_overrides.clear()

    def _macro_stick(self, stick: str):
        with self._macro_lock:
            owners = self._macro_stick_overrides.get(stick)
            if not owners:
                return None
            return max(owners.values(), key=lambda item: item[0])[1]

    def _macro_trigger(self, trigger: str, fallback: int) -> int:
        with self._macro_lock:
            owners = self._macro_trigger_overrides.get(trigger)
            if not owners:
                return int(fallback)
            return int(max(owners.values(), key=lambda item: item[0])[1])

    def _is_down(self, _state, button_name: str) -> bool:
        with self._macro_lock:
            if button_name in self._macro_overrides:
                return True
        return bool(self._effective_buttons.get(button_name))

    def set_right_stick_override(self, x: float, y: float) -> None:
        with self._state_lock:
            self._right_stick_override = (
                max(-1.0, min(1.0, float(x))),
                max(-1.0, min(1.0, float(y))),
            )

    def clear_right_stick_override(self) -> None:
        with self._state_lock:
            self._right_stick_override = None

    def set_input_processor(self, processor) -> None:
        """Conecta Input Studio al unico escritor de ViGEm.

        El procesador recibe valores HID fisicos y devuelve valores
        normalizados. Mantener esta transformacion aqui garantiza que Xbox y
        DS4 ven exactamente la misma salida y evita otro hilo escribiendo al
        gamepad virtual.
        """
        with self._state_lock:
            self._input_processor = processor

    def get_virtual_stick_output(self, stick: str) -> tuple:
        """Ultima salida efectiva que se envio (o se previsualizo) a ViGEm."""
        if stick not in ('left', 'right'):
            raise ValueError(f"Palanca desconocida: {stick}")
        with self._state_lock:
            return tuple(self._last_virtual_sticks[stick])

    @staticmethod
    def _parse_motion_axes(value) -> tuple:
        try:
            parsed = tuple(int(item) for item in tuple(value)[:3])
        except (TypeError, ValueError, OverflowError):
            return (0, 1, 2)
        return parsed if len(parsed) == 3 and sorted(parsed) == [0, 1, 2] else (0, 1, 2)

    def set_ds4_motion_passthrough(
        self,
        enabled: bool,
        gyro_signs=(1, 1, 1),
        accel_signs=(1, 1, 1),
        gyro_bias=(0.0, 0.0, 0.0),
        *,
        gyro_bias_trusted: bool = False,
        gyro_axes=(0, 1, 2),
        accel_axes=(0, 1, 2),
        deadzone: float = 6.0,
        mouse_to_gyro_enabled: bool = False,
        mouse_to_gyro_sensitivity: float = 0.12,
        mouse_to_gyro_invert_x: bool = False,
        mouse_to_gyro_invert_y: bool = False,
        mouse_to_gyro_combine: bool = False,
        mouse_to_gyro_max_dps: float = 1400.0,
    ) -> None:
        with self._state_lock:
            enabled = bool(enabled)
            try:
                parsed_bias = tuple(float(v) for v in tuple(gyro_bias)[:3])
            except (TypeError, ValueError, OverflowError):
                parsed_bias = (0.0, 0.0, 0.0)
            if len(parsed_bias) != 3:
                parsed_bias = (0.0, 0.0, 0.0)
            trusted = bool(gyro_bias_trusted)
            should_reset = enabled and (
                not self._ds4_motion_passthrough
                or parsed_bias != self._gyro_bias
                or trusted != self._gyro_bias_trusted
            )
            self._ds4_motion_passthrough = enabled
            self._gyro_signs = tuple(-1 if int(v) < 0 else 1 for v in tuple(gyro_signs)[:3])
            self._accel_signs = tuple(-1 if int(v) < 0 else 1 for v in tuple(accel_signs)[:3])
            self._gyro_bias = parsed_bias
            self._gyro_bias_trusted = trusted
            self._gyro_axes = self._parse_motion_axes(gyro_axes)
            self._accel_axes = self._parse_motion_axes(accel_axes)
            try:
                self._gyro_deadzone = max(0.0, min(64.0, float(deadzone)))
            except (TypeError, ValueError, OverflowError):
                self._gyro_deadzone = 6.0
            self._mouse_to_gyro_enabled = bool(enabled and mouse_to_gyro_enabled)
            if not self._mouse_to_gyro_enabled:
                self._mouse_to_gyro_hotkey_paused = False
            self._mouse_to_gyro_sensitivity = float(mouse_to_gyro_sensitivity)
            self._mouse_to_gyro_invert_x = bool(mouse_to_gyro_invert_x)
            self._mouse_to_gyro_invert_y = bool(mouse_to_gyro_invert_y)
            self._mouse_to_gyro_combine = bool(mouse_to_gyro_combine)
            self._mouse_to_gyro_max_dps = float(mouse_to_gyro_max_dps)
            self._ds4_report_adapter.set_motion_transform(
                gyro_axes=self._gyro_axes,
                accel_axes=self._accel_axes,
                deadzone=self._gyro_deadzone,
            )
            self._ds4_report_adapter.set_gyro_bias(parsed_bias, trusted=trusted)
            if should_reset:
                self._ds4_report_adapter.reset()
            should_run_mouse = bool(
                self._mouse_to_gyro_enabled
                and self.mode == EmulationMode.PS4
                and self.is_active
                and self._input_source == "dualsense"
            )
            self._last_motion_tick = time.perf_counter()

        # Instalar/quitar el hook fuera del lock que protege el reporte ViGEm.
        if should_run_mouse:
            self._arm_mouse_to_gyro_hotkey(True)
            if not self._mouse_to_gyro_hotkey_paused:
                self._start_mouse_to_gyro_delayed()
        else:
            self._mouse_to_gyro.stop()
            self._arm_mouse_to_gyro_hotkey(False)

    def recenter_ds4_motion(self) -> None:
        """Descarta deltas pendientes y reinicia solo el centro temporal IMU."""
        with self._state_lock:
            self._ds4_report_adapter.reset()
            self._last_motion_tick = time.perf_counter()
        self._mouse_to_gyro.reset()

    def supports_mouse_to_gyro(self) -> bool:
        return self._mouse_to_gyro.is_available()

    def is_mouse_to_gyro_running(self) -> bool:
        return self._mouse_to_gyro.is_running()

    def get_mouse_to_gyro_status(self) -> dict:
        """Estado real del capturador para UI y diagnóstico."""
        status = self._mouse_to_gyro.get_status()
        with self._state_lock:
            status.update(
                configured=bool(self._mouse_to_gyro_enabled),
                hotkey_paused=bool(self._mouse_to_gyro_hotkey_paused),
            )
        return status

    def supports_ds4_motion(self) -> bool:
        return self._ds4_report_adapter.is_supported

    def release_all_inputs(self) -> None:
        """Neutraliza el mando virtual tras una desconexion fisica.

        El lock evita competir con el tick normal. Se usa el reporte basico
        neutral porque funciona tanto en Xbox como en DS4, incluso si el
        ultimo envio habia sido DS4_REPORT_EX.
        """
        with self._state_lock:
            self._right_stick_override = None
            self._advanced_buttons.clear()
            self._advanced_blocked_sources.clear()
            self._effective_buttons = {}
            self._last_virtual_sticks = {'left': (0.0, 0.0), 'right': (0.0, 0.0)}
            self._last_virtual_output = {
                'active': False, 'mode': self.mode.value, 'sequence': -1, 'source': 'release',
                'buttons': [], 'left_stick': (0.0, 0.0), 'right_stick': (0.0, 0.0),
                'left_trigger': 0, 'right_trigger': 0, 'updated_ns': time.perf_counter_ns(),
            }
            self._mouse_to_gyro.reset()
            with self._macro_lock:
                self._clear_macro_overrides_locked()
            gamepad = self.gamepad
            if not self.is_active or gamepad is None:
                return
            try:
                gamepad.reset()
                gamepad.update()
            except Exception as exc:
                logger.debug("No se pudo neutralizar el control virtual: %s", exc)

    def set_mode(self, mode: EmulationMode) -> bool:
        # Evita que dos cambios de modo creen y publiquen dispositivos ViGEm
        # fuera de orden. El tick normal solo verá el dispositivo ya publicado.
        with self._mode_lock:
            return self._set_mode_serialized(mode)

    def _set_mode_serialized(self, mode: EmulationMode) -> bool:
        if mode != EmulationMode.NONE and not VGAMEPAD_AVAILABLE:
            logger.error("No se puede emular: vgamepad no esta instalado.")
            return False
        with self._state_lock:
            old_gamepad = self.gamepad
            # Despublicar primero impide que un tick escriba al mando viejo
            # mientras se está retirando o creando el nuevo.
            self.gamepad = None
            self.is_active = False
            self.mode = mode
            self._right_stick_override = None
            self._last_virtual_output = {
                'active': False, 'mode': mode.value, 'sequence': -1, 'source': 'mode_change',
                'buttons': [], 'left_stick': (0.0, 0.0), 'right_stick': (0.0, 0.0),
                'left_trigger': 0, 'right_trigger': 0, 'updated_ns': time.perf_counter_ns(),
            }
            with self._macro_lock:
                self._clear_macro_overrides_locked()
            self._ds4_report_adapter.reset()
        if old_gamepad is not None:
            self._unregister_feedback_notification(old_gamepad)
        # El hook no debe seguir acumulando movimiento al cambiar de dispositivo.
        self._mouse_to_gyro.stop()
        self._arm_mouse_to_gyro_hotkey(False)
        with self._state_lock:
            self._mouse_to_gyro_hotkey_paused = False
        if old_gamepad:
            try:
                old_gamepad.reset()
                old_gamepad.update()
            except Exception as exc:
                logger.debug("No se pudo retirar el control virtual anterior: %s", exc)
        self._publish_feedback(0, 0, 0)
        if mode == EmulationMode.NONE:
            return True
        try:
            gamepad = vg.VX360Gamepad() if mode == EmulationMode.XBOX else vg.VDS4Gamepad()
            self._register_feedback_notification(gamepad)
            with self._state_lock:
                self.gamepad = gamepad
                self.is_active = True
            if mode == EmulationMode.PS4 and self._ds4_motion_passthrough:
                logger.info("DS4 extendido: %s", self._ds4_report_adapter.support_description)
                if self._mouse_to_gyro_enabled and self._input_source == "dualsense":
                    self._arm_mouse_to_gyro_hotkey(True)
                    self._start_mouse_to_gyro_delayed()
            self._last_motion_tick = time.perf_counter()
            return True
        except Exception as exc:
            logger.error("Error creando control virtual: %s", exc)
            with self._state_lock:
                self.mode = EmulationMode.NONE
            return False

    def set_input_source(self, source: str) -> None:
        """Selecciona quién alimenta el gamepad virtual.

        ``dualsense`` conserva la ruta física histórica y ``keyboard`` reserva
        ViGEm para Nikaido KeyBridge. Cambiar de dueño neutraliza cualquier
        entrada retenida para que no queden botones o sticks pegados.
        """
        normalized = str(source or 'dualsense').strip().lower()
        if normalized not in ('dualsense', 'keyboard'):
            raise ValueError(f"Fuente virtual desconocida: {source}")
        with self._state_lock:
            if normalized == self._input_source:
                return
        self.release_all_inputs()
        with self._state_lock:
            self._input_source = normalized
            should_resume_mouse = bool(
                normalized == "dualsense"
                and self._mouse_to_gyro_enabled
                and self.mode == EmulationMode.PS4
                and self.is_active
            )
            if normalized == "keyboard":
                self._mouse_to_gyro_hotkey_paused = False
        if should_resume_mouse:
            self._arm_mouse_to_gyro_hotkey(True)
            self._start_mouse_to_gyro_delayed()
        else:
            self._mouse_to_gyro.stop()
            self._arm_mouse_to_gyro_hotkey(False)

    def get_input_source(self) -> str:
        with self._state_lock:
            return self._input_source

    def update_from_dualsense(self, state) -> None:
        with self._state_lock:
            if self._input_source != 'dualsense':
                return
        self._update_from_state(state, remap_buttons=True, allow_motion=True)

    def update_from_keyboard(self, state) -> None:
        """Recibe un estado sintético de KeyBridge sin remapearlo otra vez."""
        with self._state_lock:
            if self._input_source != 'keyboard':
                return
        self._update_from_state(state, remap_buttons=False, allow_motion=False)

    def _update_from_state(self, state, *, remap_buttons: bool, allow_motion: bool) -> None:
        started = time.perf_counter()
        sent = False
        with self._state_lock:
            processed_sticks = self._processed_sticks(state)
            left_output = self._macro_stick('left') or processed_sticks['left']
            right_output = self._macro_stick('right') or self._right_stick_override or processed_sticks['right']
            self._last_virtual_sticks = {
                'left': left_output,
                'right': right_output,
            }
            if not self.is_active or not self.gamepad:
                self._last_virtual_output = {
                    'active': False, 'mode': self.mode.value,
                    'sequence': int(getattr(state, 'sequence', -1)),
                    'source': str(getattr(state, 'source', 'unknown')),
                    'buttons': [],
                    'left_stick': tuple(round(value, 4) for value in left_output),
                    'right_stick': tuple(round(value, 4) for value in right_output),
                    'left_trigger': 0, 'right_trigger': 0, 'updated_ns': 0,
                }
                return
            physical_buttons = getattr(state, 'buttons', {})
            if remap_buttons:
                self._effective_buttons = self._remap_buttons(physical_buttons)
            else:
                self._effective_buttons = {
                    name: True for name, pressed in (physical_buttons or {}).items()
                    if pressed and name in REMAPPABLE_BUTTONS
                }
            with self._macro_lock:
                output_buttons = set(self._effective_buttons) | set(self._macro_overrides)
            effective_left_trigger = self._macro_trigger(
                'left', max(0, min(255, int(getattr(state, 'left_trigger', 0))))
            )
            effective_right_trigger = self._macro_trigger(
                'right', max(0, min(255, int(getattr(state, 'right_trigger', 0))))
            )
            pending_output = {
                'active': True, 'mode': self.mode.value,
                'sequence': int(getattr(state, 'sequence', -1)),
                'source': str(getattr(state, 'source', 'unknown')),
                'buttons': sorted(output_buttons),
                'left_stick': tuple(round(value, 4) for value in left_output),
                'right_stick': tuple(round(value, 4) for value in right_output),
                'left_trigger': effective_left_trigger,
                'right_trigger': effective_right_trigger,
                'updated_ns': 0,
            }
            try:
                if self.mode == EmulationMode.XBOX:
                    self._update_xbox(state, processed_sticks)
                elif self.mode == EmulationMode.PS4:
                    self._update_ps4(state, processed_sticks, allow_motion=allow_motion)
                self._last_update_error = None
                sent = True
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                self._diag_errors += 1
                if message != self._last_update_error:
                    logger.warning("Fallo actualizando control virtual: %s", message)
                    self._last_update_error = message
            finally:
                if sent:
                    now = time.perf_counter()
                    pending_output['updated_ns'] = time.perf_counter_ns()
                    self._last_virtual_output = pending_output
                    self._diag_total_updates += 1
                    self._diag_virtual_times.append(now)
                    self._diag_update_ms.append((now - started) * 1000.0)

    def get_output_state_snapshot(self) -> dict:
        """Último estado efectivo enviado a ViGEm, listo para reportes."""
        with self._state_lock:
            result = dict(self._last_virtual_output)
            result['buttons'] = list(result.get('buttons', []))
            result['left_stick'] = tuple(result.get('left_stick', (0.0, 0.0)))
            result['right_stick'] = tuple(result.get('right_stick', (0.0, 0.0)))
            return result

    @staticmethod
    def _diagnostic_rate(values) -> float:
        values = tuple(values)
        if len(values) < 2:
            return 0.0
        span = values[-1] - values[0]
        return (len(values) - 1) / span if span > 0 else 0.0

    @staticmethod
    def _diagnostic_p95(values) -> float:
        values = sorted(float(value) for value in values)
        if not values:
            return 0.0
        return values[int(round((len(values) - 1) * 0.95))]

    def get_diagnostics_snapshot(self) -> dict:
        with self._state_lock:
            durations = tuple(self._diag_update_ms)
            return {
                'mode': self.mode.value,
                'input_source': self._input_source,
                'active': bool(self.is_active and self.gamepad),
                'virtual_hz': round(self._diagnostic_rate(self._diag_virtual_times), 2),
                'total_updates': self._diag_total_updates,
                'update_avg_ms': round(sum(durations) / len(durations), 3) if durations else 0.0,
                'update_p95_ms': round(self._diagnostic_p95(durations), 3),
                'update_max_ms': round(max(durations), 3) if durations else 0.0,
                'errors': self._diag_errors,
                'last_error': self._last_update_error or '',
                'effective_buttons': sorted(self._effective_buttons),
                'advanced_buttons': sorted(self._advanced_buttons),
                'blocked_buttons': sorted(self._advanced_blocked_sources),
                'left_stick': tuple(round(value, 4) for value in self._last_virtual_sticks['left']),
                'right_stick': tuple(round(value, 4) for value in self._last_virtual_sticks['right']),
                'motion_passthrough': bool(self._ds4_motion_passthrough),
                'mouse_to_gyro': bool(self._mouse_to_gyro_enabled and self._mouse_to_gyro.is_running()),
                'feedback_supported': bool(self._feedback_supported),
                'feedback_registered': bool(self._feedback_registered),
                'feedback_count': self._feedback_count,
                'feedback_errors': self._feedback_errors,
                'feedback_large_motor': int(self._last_feedback.get('large_motor', 0)),
                'feedback_small_motor': int(self._last_feedback.get('small_motor', 0)),
                'feedback_led_number': int(self._last_feedback.get('led_number', 0)),
                'feedback_age_ms': round(
                    (time.perf_counter_ns() - int(self._last_feedback.get('received_ns', 0))) / 1_000_000.0,
                    1,
                ) if self._last_feedback.get('received_ns') else None,
                'uptime_seconds': round(time.perf_counter() - self._diag_started, 1),
            }

    def reset_diagnostics(self) -> None:
        with self._state_lock:
            self._diag_virtual_times.clear()
            self._diag_update_ms.clear()
            self._diag_total_updates = 0
            self._diag_errors = 0
            self._diag_started = time.perf_counter()

    @staticmethod
    def _normalize_axis(value) -> float:
        try:
            raw = max(0.0, min(255.0, float(value)))
        except (TypeError, ValueError, OverflowError):
            raw = 128.0
        return (raw - 128.0) / (127.0 if raw >= 128.0 else 128.0)

    def _processed_sticks(self, state) -> dict:
        """Obtiene la salida de Input Studio o una previsualizacion neutral."""
        fallback = {
            'left': (self._normalize_axis(getattr(state, 'left_stick_x', 128)),
                     self._normalize_axis(getattr(state, 'left_stick_y', 128))),
            'right': (self._normalize_axis(getattr(state, 'right_stick_x', 128)),
                      self._normalize_axis(getattr(state, 'right_stick_y', 128))),
        }
        processor = self._input_processor
        if processor is None:
            return fallback
        try:
            return {
                'left': processor.process_stick(
                    'left', getattr(state, 'left_stick_x', 128), getattr(state, 'left_stick_y', 128)),
                'right': processor.process_stick(
                    'right', getattr(state, 'right_stick_x', 128), getattr(state, 'right_stick_y', 128)),
            }
        except Exception as exc:
            logger.warning("Input Studio no pudo procesar la palanca: %s", exc)
            return fallback

    @staticmethod
    def _ps4_axis(value: float) -> int:
        return max(0, min(255, int(round(128 + value * (127 if value >= 0 else 128)))))

    @staticmethod
    def _xbox_axis(value: float, *, invert: bool = False) -> int:
        signed = -value if invert else value
        scaled = int(round(signed * (32767 if signed >= 0 else 32768)))
        return max(-32768, min(32767, scaled))

    def _stick_values(self, stick: str, processed_sticks, xbox: bool):
        macro_override = self._macro_stick(stick)
        if macro_override is not None:
            x, y = macro_override
        elif stick == 'right' and self._right_stick_override is not None:
            x, y = self._right_stick_override
        else:
            x, y = processed_sticks[stick]
        if xbox:
            return self._xbox_axis(x), self._xbox_axis(y, invert=True)
        return self._ps4_axis(x), self._ps4_axis(y)

    def _update_xbox(self, state, processed_sticks):
        gp = self.gamepad
        mapping = (
            ('cross', vg.XUSB_BUTTON.XUSB_GAMEPAD_A), ('circle', vg.XUSB_BUTTON.XUSB_GAMEPAD_B),
            ('square', vg.XUSB_BUTTON.XUSB_GAMEPAD_X), ('triangle', vg.XUSB_BUTTON.XUSB_GAMEPAD_Y),
            ('L1', vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER), ('R1', vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER),
            ('L3', vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB), ('R3', vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB),
            ('options', vg.XUSB_BUTTON.XUSB_GAMEPAD_START), ('create', vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK),
            ('dpad_up', vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP), ('dpad_down', vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN),
            ('dpad_left', vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT), ('dpad_right', vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT),
        )
        for name, button in mapping:
            (gp.press_button if self._is_down(state, name) else gp.release_button)(button=button)
        gp.left_trigger(value=self._macro_trigger('left', max(0, min(255, int(state.left_trigger)))))
        gp.right_trigger(value=self._macro_trigger('right', max(0, min(255, int(state.right_trigger)))))
        lx, ly = self._stick_values('left', processed_sticks, xbox=True)
        rx, ry = self._stick_values('right', processed_sticks, xbox=True)
        gp.left_joystick(x_value=lx, y_value=ly)
        gp.right_joystick(x_value=rx, y_value=ry)
        gp.update()

    def _update_ps4(self, state, processed_sticks, *, allow_motion: bool = True):
        gp = self.gamepad
        mapping = (
            ('cross', vg.DS4_BUTTONS.DS4_BUTTON_CROSS), ('circle', vg.DS4_BUTTONS.DS4_BUTTON_CIRCLE),
            ('square', vg.DS4_BUTTONS.DS4_BUTTON_SQUARE), ('triangle', vg.DS4_BUTTONS.DS4_BUTTON_TRIANGLE),
            ('L1', vg.DS4_BUTTONS.DS4_BUTTON_SHOULDER_LEFT), ('R1', vg.DS4_BUTTONS.DS4_BUTTON_SHOULDER_RIGHT),
            ('L2_btn', vg.DS4_BUTTONS.DS4_BUTTON_TRIGGER_LEFT), ('R2_btn', vg.DS4_BUTTONS.DS4_BUTTON_TRIGGER_RIGHT),
            ('L3', vg.DS4_BUTTONS.DS4_BUTTON_THUMB_LEFT), ('R3', vg.DS4_BUTTONS.DS4_BUTTON_THUMB_RIGHT),
            ('options', vg.DS4_BUTTONS.DS4_BUTTON_OPTIONS), ('create', vg.DS4_BUTTONS.DS4_BUTTON_SHARE),
        )
        for name, button in mapping:
            (gp.press_button if self._is_down(state, name) else gp.release_button)(button=button)
        # PS y click de touchpad viven en el byte especial de DS4.
        special_map = (
            ('ps', getattr(vg.DS4_SPECIAL_BUTTONS, 'DS4_SPECIAL_BUTTON_PS', None)),
            ('touchpad', getattr(vg.DS4_SPECIAL_BUTTONS, 'DS4_SPECIAL_BUTTON_TOUCHPAD', None)),
        )
        for name, button in special_map:
            if button is not None:
                (gp.press_special_button if self._is_down(state, name) else gp.release_special_button)(special_button=button)

        up, down = self._is_down(state, 'dpad_up'), self._is_down(state, 'dpad_down')
        left, right = self._is_down(state, 'dpad_left'), self._is_down(state, 'dpad_right')
        if up and right: direction = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTHEAST
        elif up and left: direction = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTHWEST
        elif down and right: direction = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTHEAST
        elif down and left: direction = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTHWEST
        elif up: direction = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTH
        elif down: direction = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTH
        elif right: direction = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_EAST
        elif left: direction = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_WEST
        else: direction = vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NONE
        gp.directional_pad(direction=direction)
        gp.left_trigger(value=self._macro_trigger('left', max(0, min(255, int(state.left_trigger)))))
        gp.right_trigger(value=self._macro_trigger('right', max(0, min(255, int(state.right_trigger)))))
        lx, ly = self._stick_values('left', processed_sticks, xbox=False)
        gp.left_joystick(x_value=lx, y_value=ly)
        rx, ry = self._stick_values('right', processed_sticks, xbox=False)
        gp.right_joystick(x_value=rx, y_value=ry)

        if allow_motion and self._ds4_motion_passthrough:
            now = time.perf_counter()
            dt = max(0.001, min(0.05, now - self._last_motion_tick))
            self._last_motion_tick = now
            synthetic = (0.0, 0.0, 0.0)
            mouse_running = self._mouse_to_gyro_enabled and self._mouse_to_gyro.is_running()
            if mouse_running:
                synthetic = self._mouse_to_gyro.consume_gyro(
                    dt,
                    sensitivity=self._mouse_to_gyro_sensitivity,
                    invert_x=self._mouse_to_gyro_invert_x,
                    invert_y=self._mouse_to_gyro_invert_y,
                    max_dps=self._mouse_to_gyro_max_dps,
                )
            if self._ds4_report_adapter.update(
                gp,
                state,
                self._gyro_signs,
                self._accel_signs,
                synthetic_gyro=synthetic,
                replace_physical=bool(mouse_running and not self._mouse_to_gyro_combine),
            ):
                return
        gp.update()
