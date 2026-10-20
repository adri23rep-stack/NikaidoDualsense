"""
Gestor de Conexion DualSense
Maneja la deteccion automatica de conexion USB/Bluetooth, monitoreo de bateria y estado del control.
"""

import logging
import sys
import time
import threading
import types
from collections import deque
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Optional, Callable, List

from .hid_backend import ensure_hidapi_backend, get_hid_backend_status

HID_BACKEND_STATUS = ensure_hidapi_backend()
PYDUALSENSE_IMPORT_ERROR = ""
pydualsense = None
try:
    from pydualsense import pydualsense

    try:
        from pydualsense import PlayerID
    except ImportError:
        PlayerID = None
    PYDUALSENSE_AVAILABLE = True
except Exception as exc:
    PYDUALSENSE_AVAILABLE = False
    PlayerID = None
    PYDUALSENSE_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
    logging.warning(
        "No se pudo cargar pydualsense. Backend HID=%s. Error=%s",
        HID_BACKEND_STATUS.name,
        PYDUALSENSE_IMPORT_ERROR,
    )

from .bluetooth_utils import BluetoothManager  # noqa: E402
from .emulator import EmulatorManager, EmulationMode  # noqa: E402

logger = logging.getLogger(__name__)


class ConnectionType(Enum):
    NONE = "none"
    USB = "usb"
    BLUETOOTH = "bluetooth"
    UNKNOWN = "unknown"


class ChargingStatus(Enum):
    DISCHARGING = "descargando"
    CHARGING = "cargando"
    CHARGED = "cargado completo"
    UNKNOWN = "desconocido"


@dataclass
class ControllerState:
    connected: bool = False
    connection_type: ConnectionType = ConnectionType.NONE
    battery_level: int = 0
    # ``False`` hasta recibir el primer informe HID con batería. Un 0 temporal
    # durante la conexión no debe mostrarse como si el control estuviera vacío.
    battery_valid: bool = False
    charging_status: ChargingStatus = ChargingStatus.UNKNOWN
    left_trigger: int = 0
    right_trigger: int = 0
    left_stick_x: int = 128
    left_stick_y: int = 128
    right_stick_x: int = 128
    right_stick_y: int = 128
    # Datos crudos del touchpad (primer dedo). X/Y vienen del sensor tal
    # cual, en una resolucion de ~1920x943 segun el hardware real.
    touchpad_active: bool = False
    touchpad_x: int = 0
    touchpad_y: int = 0
    touchpad_id: int = 0
    # Sensores IMU crudos del DualSense (enteros signed 16-bit).
    gyro_pitch: int = 0
    gyro_yaw: int = 0
    gyro_roll: int = 0
    accel_x: int = 0
    accel_y: int = 0
    accel_z: int = 0
    buttons: dict = field(default_factory=dict)
    # Metadatos del paquete físico. ``sequence`` viene del reporte HID Sony y
    # permite distinguir nuevos informes de sondeos repetidos.
    sequence: int = -1
    source: str = "unknown"
    monotonic_ns: int = 0
    timestamp: float = field(default_factory=time.time)


class ConnectionManager:
    CONNECTION_POLL_INTERVAL = 1.0
    # 250 Hz reduce el tiempo máximo entre un paquete HID y ViGEm a ~4 ms.
    # La interfaz se actualiza por separado y no reconstruye widgets a esta tasa.
    STATE_POLL_INTERVAL = 1.0 / 250.0
    # Al emular, revisar el contador del paquete cada 1 ms reduce la espera
    # hasta detectar el estado físico más reciente. La ruta pesada solo corre
    # cuando llega un informe nuevo o vence el heartbeat de 250 Hz.
    LOW_LATENCY_SCAN_INTERVAL = 1.0 / 1000.0
    LOW_LATENCY_SPIN_THRESHOLD = 0.00010
    WINDOWS_TIMER_PERIOD_MS = 1
    # pydualsense escribe un reporte físico después de CADA lectura HID. Esa
    # mezcla puede crear una cola de entrada atrasada si la escritura USB/BT
    # tarda. Nikaido publica cada entrada de inmediato y limita únicamente las
    # salidas físicas (luces, rumble y gatillos) a 60 Hz.
    PHYSICAL_OUTPUT_INTERVAL = 1.0 / 60.0
    PHYSICAL_OUTPUT_KEEPALIVE = 0.25
    OBSERVER_POLL_INTERVAL = 1.0 / 60.0
    # Si pasa mas de este tiempo sin una lectura buena del control, asumimos
    # que se desconecto de verdad (se durmio, se fue del rango del
    # Bluetooth, se desenchufo el USB) aunque el objeto pydualsense siga
    # "vivo" en memoria.
    STALE_TIMEOUT = 1.5
    # Bluetooth puede tardar unos segundos en publicar el primer paquete crudo
    # aun cuando ``controller.state`` ya existe. Durante esta ventana aceptamos
    # el estado compatible; después exigimos actividad HID si la librería anunció
    # que dispone de ``states``. Así evitamos tanto reconexiones falsas al iniciar
    # como una conexión fantasma que permanezca viva para siempre.
    RAW_REPORT_STARTUP_GRACE = 5.0
    MAX_READ_FAILURES = 15

    def __init__(self):
        self.dualsense: Any = None
        self.bluetooth_manager = BluetoothManager()
        self.emulator = EmulatorManager()
        self._state = ControllerState()
        self._connected = False
        self._connection_type = ConnectionType.NONE
        self._running = False
        self._connection_enabled = True
        now = time.monotonic()
        self._last_successful_read = now
        # Una llamada a pydualsense puede seguir devolviendo el último estado
        # incluso después de desconectar físicamente el control. Solo un cambio
        # real en el contador del reporte HID confirma que siguen llegando datos.
        self._last_fresh_report = now
        self._last_raw_sequence: Optional[int] = None
        self._raw_report_wait_started = now
        # ``pydualsense`` crea ``states`` antes de recibir el primer informe.
        # Solo activamos la vigilancia estricta cuando ya vimos una captura HID
        # válida; antes de eso el objeto ``state`` es un fallback legítimo.
        self._raw_report_seen = False
        self._backend_error_notified = False
        self._last_connect_error = ""
        self._read_failures = 0
        self._last_observer_notification = 0.0
        self._timer_resolution_active = False
        self._timer_resolution_api = None
        self._state_thread_priority_boosted = False
        self._connection_generation = 0

        # Métricas ligeras para el Centro de diagnóstico. Solo se guardan
        # ventanas pequeñas y números agregados; nada de esto toca la UI.
        self._diag_poll_times = deque(maxlen=1200)
        self._diag_unique_times = deque(maxlen=1200)
        # Progreso acumulado del contador HID. El delta entre dos puntos
        # permite estimar la frecuencia REAL del dispositivo aunque Nikaido
        # solo alcance a observar el estado más reciente de varios informes.
        self._diag_device_progress = deque(maxlen=1200)
        self._diag_pipeline_ms = deque(maxlen=600)
        self._diag_realtime_ms = deque(maxlen=600)
        self._diag_emulator_ms = deque(maxlen=600)
        self._diag_snapshot_to_virtual_ms = deque(maxlen=600)
        self._diag_button_edge_ms = deque(maxlen=300)
        self._diag_total_polls = 0
        self._diag_unique_reports = 0
        self._diag_duplicate_reports = 0
        self._diag_coalesced_reports = 0
        self._diag_sequence_discontinuities = 0
        self._diag_sequence_progress = 0
        self._diag_sequence_advance_total = 0
        self._diag_raw_reports = 0
        self._diag_fallback_reports = 0
        self._diag_last_sequence = None
        self._diag_last_buttons = None
        self._diag_last_tick = {}
        self._diag_started = time.perf_counter()

        self._on_connect: List[Callable[[ConnectionType], None]] = []
        self._on_disconnect: List[Callable[[], None]] = []
        self._on_realtime_state_update: List[Callable[[ControllerState], None]] = []
        self._on_state_update: List[Callable[[ControllerState], None]] = []
        self._on_battery_change: List[Callable[[int, ChargingStatus], None]] = []
        self._on_error: List[Callable[[str], None]] = []

        self._connection_thread: Optional[threading.Thread] = None
        self._state_thread: Optional[threading.Thread] = None
        self._lifecycle_lock = threading.RLock()
        self._stop_event = threading.Event()
        self._stopping = False
        self._lock = threading.RLock()
        # Serializa lecturas HID y cierre del dispositivo. Sin este candado, el
        # hilo de conexión y el hilo de estado podían cerrar/procesar el mismo
        # controlador al mismo tiempo y volver a enviar una entrada ya liberada.
        self._io_lock = threading.RLock()
        # Entrada virtual y salidas físicas usan candados distintos. Una
        # escritura RGB/rumble lenta no debe frenar el snapshot que va a ViGEm.
        # Este candado ordena el pipeline virtual frente a una desconexión.
        self._virtual_pipeline_lock = threading.RLock()
        # Las pruebas manuales tienen prioridad sobre el feedback del control
        # virtual. En builds congeladas el hilo de salida de pydualsense puede
        # tardar unas vueltas en publicar el nuevo reporte, por eso la prueba
        # se reafirma durante su ventana en lugar de escribir una sola vez.
        self._rumble_test_generation = 0
        self._rumble_test_until = 0.0
        self._rumble_test_output = (0, 0)
        self._rumble_last_output = (0, 0)
        self._rumble_last_source = ""
        self._rumble_write_count = 0
        self._rumble_errors = 0
        self._rumble_last_error = ""

    def _add_callback(self, bucket: list, callback: Callable[..., None]) -> bool:
        if not callable(callback):
            raise TypeError("El callback debe ser invocable")
        with self._lock:
            if callback in bucket:
                return False
            bucket.append(callback)
            return True

    def _remove_callback(self, bucket: list, callback: Callable[..., None]) -> bool:
        """Retira un suscriptor sin fallar si ya fue eliminado durante un aviso."""
        with self._lock:
            if callback not in bucket:
                return False
            bucket[:] = [item for item in bucket if item != callback]
            return True

    def _unsubscribe(self, bucket: list, callback: Callable[..., None]) -> Callable[[], None]:
        """Crea una baja idempotente para ventanas y motores de vida más corta."""
        return lambda: self._remove_callback(bucket, callback)

    def _replay_callback(self, bucket: list, callback: Callable[..., None], *args: Any) -> None:
        """Entrega el estado actual a un suscriptor que llegó después del evento.

        El ejecutable empaquetado inicia el lector HID muy rápido. La interfaz
        puede registrarse después de que ya ocurrió ``on_connect`` o del primer
        cambio de batería. Reproducir la instantánea evita que la UI se quede
        mostrando "Buscando" hasta la siguiente reconexión.
        """
        try:
            callback(*args)
        except Exception:
            logger.exception("Callback desactivado tras fallar durante la sincronización inicial")
            with self._lock:
                bucket[:] = [item for item in bucket if item is not callback]

    def on_connect(self, callback: Callable[[ConnectionType], None]) -> Callable[[], None]:
        added = self._add_callback(self._on_connect, callback)
        if added:
            with self._lock:
                connected = self._connected
                connection_type = self._connection_type
            if connected:
                self._replay_callback(self._on_connect, callback, connection_type)
        return self._unsubscribe(self._on_connect, callback)

    def on_disconnect(self, callback: Callable[[], None]) -> Callable[[], None]:
        self._add_callback(self._on_disconnect, callback)
        return self._unsubscribe(self._on_disconnect, callback)

    def on_realtime_state_update(
        self, callback: Callable[[ControllerState], None]
    ) -> Callable[[], None]:
        """Registra procesamiento que debe terminar antes de escribir a ViGEm.

        Se reserva para gyro, macros y remapeo. La interfaz y tareas de
        diagnóstico deben seguir usando ``on_state_update`` para no retrasar
        la salida del control virtual.
        """
        self._add_callback(self._on_realtime_state_update, callback)
        return self._unsubscribe(self._on_realtime_state_update, callback)

    def on_state_update(self, callback: Callable[[ControllerState], None]) -> Callable[[], None]:
        self._add_callback(self._on_state_update, callback)
        return self._unsubscribe(self._on_state_update, callback)

    def on_battery_change(
        self, callback: Callable[[int, ChargingStatus], None]
    ) -> Callable[[], None]:
        added = self._add_callback(self._on_battery_change, callback)
        if added:
            with self._lock:
                connected = self._connected
                level = self._state.battery_level
                battery_valid = self._state.battery_valid
                status = self._state.charging_status
            # Compatibilidad: algunas integraciones antiguas establecen nivel/estado
            # manualmente sin conocer ``battery_valid``. Un valor distinto de cero o
            # un estado de carga conocido también confirma que existe una lectura.
            known_snapshot = battery_valid or level > 0 or status is not ChargingStatus.UNKNOWN
            if connected and known_snapshot:
                self._replay_callback(self._on_battery_change, callback, level, status)
        return self._unsubscribe(self._on_battery_change, callback)

    def on_error(self, callback: Callable[[str], None]) -> Callable[[], None]:
        self._add_callback(self._on_error, callback)
        return self._unsubscribe(self._on_error, callback)

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    @property
    def connection_type(self) -> ConnectionType:
        with self._lock:
            return self._connection_type

    @property
    def state(self) -> ControllerState:
        with self._lock:
            return ControllerState(
                connected=self._state.connected,
                connection_type=self._state.connection_type,
                battery_level=self._state.battery_level,
                battery_valid=self._state.battery_valid,
                charging_status=self._state.charging_status,
                left_trigger=self._state.left_trigger,
                right_trigger=self._state.right_trigger,
                left_stick_x=self._state.left_stick_x,
                left_stick_y=self._state.left_stick_y,
                right_stick_x=self._state.right_stick_x,
                right_stick_y=self._state.right_stick_y,
                touchpad_active=self._state.touchpad_active,
                touchpad_x=self._state.touchpad_x,
                touchpad_y=self._state.touchpad_y,
                touchpad_id=self._state.touchpad_id,
                gyro_pitch=self._state.gyro_pitch,
                gyro_yaw=self._state.gyro_yaw,
                gyro_roll=self._state.gyro_roll,
                accel_x=self._state.accel_x,
                accel_y=self._state.accel_y,
                accel_z=self._state.accel_z,
                buttons=dict(self._state.buttons),
                sequence=self._state.sequence,
                source=self._state.source,
                monotonic_ns=self._state.monotonic_ns,
                timestamp=self._state.timestamp,
            )

    @property
    def dualsense_instance(self) -> Optional[Any]:
        return self.dualsense

    def set_emulation_mode(self, mode: EmulationMode) -> bool:
        return self.emulator.set_mode(mode)

    def request_connect(self) -> bool:
        """Habilita la búsqueda automática del control."""
        self._connection_enabled = True
        if not self._running:
            self.start()
        return True

    def disconnect(self) -> None:
        """Desconecta y pausa la reconexión hasta request_connect()."""
        self._connection_enabled = False
        self._disconnect()

    def _enable_low_latency_timer(self) -> None:
        """Solicita resolución de 1 ms en Windows y la revierte al detenerse."""
        if sys.platform != "win32" or self._timer_resolution_active:
            return
        try:
            import ctypes

            api = ctypes.WinDLL("winmm")
            api.timeBeginPeriod.argtypes = [ctypes.c_uint]
            api.timeBeginPeriod.restype = ctypes.c_uint
            api.timeEndPeriod.argtypes = [ctypes.c_uint]
            api.timeEndPeriod.restype = ctypes.c_uint
            if int(api.timeBeginPeriod(self.WINDOWS_TIMER_PERIOD_MS)) == 0:
                self._timer_resolution_api = api
                self._timer_resolution_active = True
        except Exception as exc:
            logger.debug("Windows no permitió resolución de temporizador de 1 ms: %s", exc)

    def _disable_low_latency_timer(self) -> None:
        if not self._timer_resolution_active:
            return
        api = self._timer_resolution_api
        self._timer_resolution_active = False
        self._timer_resolution_api = None
        if api is None:
            return
        try:
            api.timeEndPeriod(self.WINDOWS_TIMER_PERIOD_MS)
        except Exception as exc:
            logger.debug("No se pudo restaurar la resolución del temporizador: %s", exc)

    def _boost_state_thread_priority(self) -> None:
        """Da prioridad moderada al lector sin usar prioridad de tiempo real."""
        self._state_thread_priority_boosted = False
        if sys.platform != "win32":
            return
        try:
            import ctypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetCurrentThread.argtypes = []
            kernel32.GetCurrentThread.restype = ctypes.c_void_p
            kernel32.SetThreadPriority.argtypes = [ctypes.c_void_p, ctypes.c_int]
            kernel32.SetThreadPriority.restype = ctypes.c_int
            current_thread = kernel32.GetCurrentThread()
            # THREAD_PRIORITY_ABOVE_NORMAL = 1. Evitamos TIME_CRITICAL para no
            # quitarle tiempo a audio, red o a la propia interfaz.
            self._state_thread_priority_boosted = bool(
                kernel32.SetThreadPriority(current_thread, 1)
            )
        except Exception as exc:
            logger.debug("No se pudo elevar la prioridad del lector HID: %s", exc)

    def _wait_until_state_deadline(self, deadline: float) -> None:
        """Espera precisa; solo gira activamente durante el último tramo corto."""
        while self._running and not self._stop_event.is_set():
            remaining = float(deadline) - time.perf_counter()
            if remaining <= 0.0:
                return
            if remaining > self.LOW_LATENCY_SPIN_THRESHOLD:
                if self._stop_event.wait(remaining - self.LOW_LATENCY_SPIN_THRESHOLD):
                    return
                continue
            while (
                self._running
                and not self._stop_event.is_set()
                and time.perf_counter() < deadline
            ):
                pass
            return

    def _peek_raw_sequence(self) -> Optional[int]:
        """Consulta el contador Sony sin esperar escrituras RGB/rumble."""
        with self._lock:
            controller = self.dualsense
        raw = getattr(controller, "states", None) if controller is not None else None
        if not isinstance(raw, (list, tuple)) or len(raw) <= 7:
            return None
        try:
            return int(raw[7]) & 0xFF
        except (TypeError, ValueError, OverflowError):
            return None

    def _low_latency_scan_enabled(self) -> bool:
        emulator = self.emulator
        return bool(
            emulator
            and getattr(emulator, "is_active", False)
            and getattr(emulator, "gamepad", None) is not None
        )

    def start(self) -> None:
        with self._lifecycle_lock:
            if self._running or self._stopping:
                return
            # Un cierre puede agotar su tiempo de espera si el backend HID queda
            # bloqueado dentro de una lectura nativa. No iniciamos otra pareja
            # encima de esos trabajadores: ambos compartirían el dispositivo,
            # callbacks y la bandera ``_running``.
            lingering = [
                thread
                for thread in (self._connection_thread, self._state_thread)
                if thread is not None and thread.is_alive()
            ]
            if lingering:
                logger.warning(
                    "ConnectionManager no se reinició: todavía se cierran %s hilo(s)",
                    len(lingering),
                )
                return
            self._connection_thread = None
            self._state_thread = None
            self._stop_event.clear()
            self._running = True
            self._enable_low_latency_timer()
            self._connection_thread = threading.Thread(
                target=self._connection_loop, name="ConnectionMonitor", daemon=True
            )
            self._state_thread = threading.Thread(
                target=self._state_loop, name="StateMonitor", daemon=True
            )
            self._connection_thread.start()
            self._state_thread.start()
        logger.info("ConnectionManager iniciado")

    def stop(self) -> None:
        with self._lifecycle_lock:
            if self._stopping:
                return
            self._stopping = True
            self._running = False
            self._stop_event.set()
            connection_thread = self._connection_thread
            state_thread = self._state_thread
        current = threading.current_thread()
        try:
            for thread in (connection_thread, state_thread):
                if thread and thread is not current and thread.is_alive():
                    thread.join(timeout=3)
            self.emulator.set_mode(EmulationMode.NONE)
            self._disconnect()
        finally:
            with self._lifecycle_lock:
                if self._connection_thread is connection_thread and (
                    connection_thread is None or not connection_thread.is_alive()
                ):
                    self._connection_thread = None
                if self._state_thread is state_thread and (
                    state_thread is None or not state_thread.is_alive()
                ):
                    self._state_thread = None
                still_alive = [
                    thread
                    for thread in (self._connection_thread, self._state_thread)
                    if thread is not None and thread.is_alive()
                ]
                self._stopping = False
            self._disable_low_latency_timer()
            if still_alive:
                logger.warning(
                    "ConnectionManager detenido con %s hilo(s) HID aún cerrándose",
                    len(still_alive),
                )
        logger.info("ConnectionManager detenido")

    def _connection_loop(self) -> None:
        while self._running:
            try:
                if not self._connected:
                    if self._connection_enabled:
                        self._try_connect()
                else:
                    if not self._verify_connection():
                        self._disconnect()
                self._stop_event.wait(self.CONNECTION_POLL_INTERVAL)
            except Exception as e:
                logger.error(f"Error en bucle de conexion: {e}")
                self._stop_event.wait(self.CONNECTION_POLL_INTERVAL * 2)

    def _install_low_latency_input_pump(self, controller: Any) -> bool:
        """Reemplaza el bucle read->decode->write de pydualsense.

        La implementación original ejecuta ``readInput`` (eventos + deepcopy) y
        ``writeReport`` después de cada informe físico. Cuando la escritura HID
        tarda, el siguiente ``read`` recoge un paquete que ya estaba esperando
        en la cola del sistema y el control virtual se siente arrastrado.

        Esta bomba publica el reporte crudo de entrada tan pronto como llega.
        Las salidas físicas se preparan a 60 Hz, solo se escriben cuando cambian
        o cada breve keepalive, y nunca se anteponen a la siguiente lectura.
        """
        original = getattr(controller, "sendReport", None)
        if not callable(original):
            return False

        manager = self

        def low_latency_send_report(ds) -> None:
            input_event = threading.Event()
            output_stop = threading.Event()
            ds._nikaido_input_event = input_event
            ds._nikaido_low_latency_pump = True
            ds._nikaido_pump_active = True
            ds._nikaido_output_thread_active = False
            ds._nikaido_input_reports = 0
            ds._nikaido_output_writes = 0
            ds._nikaido_output_skips = 0
            ds._nikaido_pump_error = ""
            ds._nikaido_last_input_ns = 0

            def physical_output_loop() -> None:
                """Envía RGB/rumble/gatillos sin detener la lectura HID."""
                last_output: Optional[bytes] = None
                last_output_write = 0.0
                ds._nikaido_output_thread_active = True
                try:
                    while bool(getattr(ds, "ds_thread", False)) and not output_stop.is_set():
                        cycle_started = time.perf_counter()
                        try:
                            output = bytes(ds.prepareReport())
                            changed = output != last_output
                            keepalive_due = (
                                last_output_write <= 0.0
                                or cycle_started - last_output_write
                                >= manager.PHYSICAL_OUTPUT_KEEPALIVE
                            )
                            if changed or keepalive_due:
                                ds.writeReport(output)
                                last_output = output
                                last_output_write = time.perf_counter()
                                ds._nikaido_output_writes += 1
                            else:
                                ds._nikaido_output_skips += 1
                        except (IOError, OSError, AttributeError) as exc:
                            ds._nikaido_pump_error = f"{type(exc).__name__}: {exc}"
                            ds.connected = False
                            break
                        except Exception as exc:
                            ds._nikaido_pump_error = f"{type(exc).__name__}: {exc}"
                            logger.exception(
                                "La salida física de la bomba HID se detuvo"
                            )
                            ds.connected = False
                            break

                        elapsed = time.perf_counter() - cycle_started
                        output_stop.wait(
                            max(0.0, manager.PHYSICAL_OUTPUT_INTERVAL - elapsed)
                        )
                finally:
                    ds._nikaido_output_thread_active = False

            output_thread = threading.Thread(
                target=physical_output_loop,
                name="NikaidoPhysicalOutput",
                daemon=True,
            )
            ds._nikaido_output_thread = output_thread
            ds._nikaido_output_stop = output_stop
            output_thread.start()

            try:
                while bool(getattr(ds, "ds_thread", False)):
                    try:
                        packet = ds.device.read(int(ds.input_report_length))
                        if not packet:
                            continue

                        values = tuple(int(value) & 0xFF for value in packet)
                        connection_name = str(
                            getattr(getattr(ds, "conType", None), "name", "")
                        ).upper()
                        is_bluetooth = len(values) == 78 or connection_name in {
                            "BT", "BLUETOOTH"
                        }
                        normalized = values[1:] if is_bluetooth else values

                        # Una asignación de referencia es atómica en CPython. El
                        # hilo de Nikaido recibe un paquete completo, no campos
                        # mutables actualizados uno por uno por pydualsense.
                        ds.states = normalized
                        ds._nikaido_input_reports += 1
                        ds._nikaido_last_input_ns = time.perf_counter_ns()
                        input_event.set()
                    except (IOError, OSError, AttributeError) as exc:
                        ds._nikaido_pump_error = f"{type(exc).__name__}: {exc}"
                        ds.connected = False
                        break
                    except Exception as exc:
                        ds._nikaido_pump_error = f"{type(exc).__name__}: {exc}"
                        logger.exception("La bomba HID de baja latencia se detuvo")
                        ds.connected = False
                        break
            finally:
                output_stop.set()
                if output_thread.is_alive():
                    output_thread.join(timeout=0.25)
                ds._nikaido_pump_active = False
                input_event.set()

        controller._nikaido_original_send_report = original
        controller.sendReport = types.MethodType(low_latency_send_report, controller)
        return True

    def _try_connect(self) -> bool:
        if not PYDUALSENSE_AVAILABLE:
            if not self._backend_error_notified:
                status = get_hid_backend_status()
                detail = PYDUALSENSE_IMPORT_ERROR or status.error or "backend HID no disponible"
                self._last_connect_error = detail
                self._backend_error_notified = True
                self._notify_error(
                    f"No se pudo iniciar el lector DualSense. Backend HID: {status.name}. {detail}"
                )
            return False
        try:
            factory: Any = pydualsense
            if factory is None:
                return False
            controller = factory()
            self._install_low_latency_input_pump(controller)
            self.dualsense = controller
            controller.init()
            conn_type = self._detect_connection_type()
            with self._lock:
                self._connected = True
                self._connection_type = conn_type
                self._state.connected = True
                self._state.connection_type = conn_type
                now = time.monotonic()
                self._last_successful_read = now
                self._last_fresh_report = now
                self._last_raw_sequence = None
                self._raw_report_wait_started = now
                self._raw_report_seen = False
                self._read_failures = 0
                self._connection_generation += 1
            self._backend_error_notified = False
            self._last_connect_error = ""
            logger.info(f"DualSense conectado via {conn_type.value.upper()}")
            self._notify_connect(conn_type)
            return True
        except Exception as e:
            self._last_connect_error = f"{type(e).__name__}: {e}"
            logger.debug("No se pudo abrir el DualSense: %s", self._last_connect_error)
            if self.dualsense:
                try:
                    self.dualsense.close()
                except Exception:
                    pass
                self.dualsense = None
            return False

    def _detect_connection_type(self) -> ConnectionType:
        if not self.dualsense:
            return ConnectionType.UNKNOWN
        try:
            device = self.dualsense.device
            if device:
                try:
                    device_info = (
                        device.get_manufacturer_string()
                        if hasattr(device, "get_manufacturer_string")
                        else ""
                    )
                    product_info = (
                        device.get_product_string() if hasattr(device, "get_product_string") else ""
                    )
                    info_str = f"{device_info} {product_info}".lower()
                    if "bluetooth" in info_str or "bt" in info_str:
                        return ConnectionType.BLUETOOTH
                    elif "usb" in info_str:
                        return ConnectionType.USB
                except Exception:
                    pass
                try:
                    raw_path = getattr(device, "path", "")
                    path = (
                        raw_path.decode("utf-8") if isinstance(raw_path, bytes) else str(raw_path)
                    )
                    if "bluetooth" in path.lower() or "{00001124" in path:
                        return ConnectionType.BLUETOOTH
                    elif "usb" in path.lower() or "hid" in path.lower():
                        return ConnectionType.USB
                except Exception:
                    pass
            return ConnectionType.USB
        except Exception:
            return ConnectionType.UNKNOWN

    def _verify_connection(self) -> bool:
        if not self.dualsense:
            return False
        # ``dualsense.state`` y ``dualsense.states`` pueden quedarse con la
        # última fotografía válida después de retirar el USB o perder BT. La
        # conexión solo está viva si el contador HID avanzó recientemente.
        return (time.monotonic() - self._last_fresh_report) < self.STALE_TIMEOUT

    def _register_report_freshness(
        self, raw_decoded: Optional[dict], *, raw_source_available: bool
    ) -> bool:
        """Registra únicamente informes HID realmente nuevos.

        Nikaido consulta más rápido que la tasa del dispositivo, por lo que es
        normal observar varias veces la misma secuencia durante unos milisegundos.
        Lo anormal es que permanezca idéntica durante ``STALE_TIMEOUT``.

        ``pydualsense`` puede exponer el atributo ``states`` con valor ``None``
        durante el arranque. La presencia del atributo no prueba que la captura
        cruda ya esté operativa, por eso existe una gracia breve antes de activar
        el modo estricto. Si la versión usada ni siquiera expone ``states``, el
        estado compatible sigue siendo válido indefinidamente.
        """
        now = time.monotonic()
        if raw_decoded is None:
            if self._raw_report_seen:
                # Después de usar informes crudos, perder esa fuente no puede
                # maquillarse refrescando la fotografía mutable de ``state``.
                return False
            if raw_source_available:
                waiting = now - self._raw_report_wait_started
                if waiting >= self.RAW_REPORT_STARTUP_GRACE:
                    # La librería anunció captura cruda pero nunca entregó un
                    # paquete. Dejamos de renovar la vida para que el watchdog
                    # desconecte el objeto congelado tras STALE_TIMEOUT.
                    return False
            # Compatibilidad durante el arranque y para versiones antiguas que
            # no publican ``states`` en absoluto.
            self._last_fresh_report = now
            return True

        self._raw_report_seen = True
        sequence = int(raw_decoded.get("sequence", -1))
        if self._last_raw_sequence is None or sequence != self._last_raw_sequence:
            self._last_raw_sequence = sequence
            self._last_fresh_report = now
            return True
        return False

    def _disconnect(self) -> None:
        # Separa primero el objeto físico y neutraliza el estado interno. El
        # reset virtual se coordina después, sin sostener el candado de salidas
        # HID, para evitar interbloqueos con macros, luces o vibración.
        with self._io_lock:
            with self._lock:
                controller = self.dualsense
                self.dualsense = None
                was_connected = self._connected
                self._connected = False
                self._connection_type = ConnectionType.NONE
                self._connection_generation += 1
                self._state = ControllerState()
                self._last_raw_sequence = None
                self._raw_report_seen = False
                disconnected_snapshot = self.state
                self._rumble_test_generation += 1
                self._rumble_test_until = 0.0
                self._rumble_test_output = (0, 0)
                self._rumble_last_output = (0, 0)

            if controller is not None:
                self._reset_controller_state(controller)
                try:
                    controller.close()
                except Exception:
                    logger.debug("El handle DualSense ya estaba cerrado", exc_info=True)

        if was_connected:
            logger.info("DualSense desconectado")
            self._notify_disconnect()
            self._notify_state_update(disconnected_snapshot)
            self._notify_battery_change(0, ChargingStatus.UNKNOWN)
            # Si un tick ya estaba escribiendo ViGEm termina primero. Este reset
            # queda como la última escritura y no puede ser pisado por estado viejo.
            with self._virtual_pipeline_lock:
                self.emulator.release_all_inputs()

    def _reset_controller_state(self, controller=None) -> None:
        target = controller if controller is not None else self.dualsense
        if target is None:
            return
        try:
            from pydualsense import TriggerModes

            target.triggerL.setMode(TriggerModes.Off)
            target.triggerR.setMode(TriggerModes.Off)
            target.light.setColorI(0, 0, 0)
            target.setLeftMotor(0)
            target.setRightMotor(0)
        except Exception:
            # El cierre debe continuar aunque una salida física ya no responda.
            logger.debug("No se pudo neutralizar por completo el DualSense", exc_info=True)

    @staticmethod
    def _signed_short(report, offset: int) -> int:
        """Lee un entero little-endian firmado de un reporte HID ya copiado."""
        try:
            low = int(report[offset]) & 0xFF
            high = int(report[offset + 1]) & 0xFF
        except (IndexError, TypeError, ValueError):
            return 0
        value = low | (high << 8)
        return value - 0x10000 if value & 0x8000 else value

    @staticmethod
    def _decode_dpad(value: int) -> dict:
        """Convierte el nibble Sony (0..7, 8 neutral) a cuatro botones."""
        value = int(value) & 0x0F
        return {
            "dpad_up": value in (0, 1, 7),
            "dpad_right": value in (1, 2, 3),
            "dpad_down": value in (3, 4, 5),
            "dpad_left": value in (5, 6, 7),
        }

    def _raw_report_snapshot(self, controller=None):
        """Obtiene un paquete completo sin leer ``dualsense.state`` a medias.

        pydualsense reemplaza ``states`` con una lista nueva al recibir cada
        informe. Copiar esa referencia a una tupla es atómico en CPython y
        evita mezclar palancas del paquete N con botones o IMU del N-1.
        ``states`` ya viene normalizado: la cabecera extra de Bluetooth fue
        retirada por la propia librería.
        """
        target = controller if controller is not None else self.dualsense
        if target is None:
            return None
        raw = getattr(target, "states", None)
        if not isinstance(raw, (list, tuple)) or len(raw) < 54:
            return None
        try:
            return tuple(int(value) & 0xFF for value in raw)
        except (TypeError, ValueError, OverflowError):
            return None

    @classmethod
    def _decode_raw_report(cls, report):
        """Decodifica controles, touch e IMU desde una sola captura HID."""
        if report is None or len(report) < 54:
            return None
        face = report[8]
        misc = report[9]
        misc2 = report[10]
        buttons = {
            "cross": bool(face & 0x20),
            "circle": bool(face & 0x40),
            "square": bool(face & 0x10),
            "triangle": bool(face & 0x80),
            "L1": bool(misc & 0x01),
            "R1": bool(misc & 0x02),
            "L2_btn": bool(misc & 0x04),
            "R2_btn": bool(misc & 0x08),
            "create": bool(misc & 0x10),
            "options": bool(misc & 0x20),
            "L3": bool(misc & 0x40),
            "R3": bool(misc & 0x80),
            "ps": bool(misc2 & 0x01),
            "touchpad": bool(misc2 & 0x02),
            "mute": bool(misc2 & 0x04),
        }
        buttons.update(cls._decode_dpad(face))

        touch_byte = report[33]
        touch_x = ((report[35] & 0x0F) << 8) | report[34]
        touch_y = (report[36] << 4) | ((report[35] & 0xF0) >> 4)
        battery = report[53]
        battery_state = (battery >> 4) & 0x0F
        charging = {
            0: ChargingStatus.DISCHARGING,
            1: ChargingStatus.CHARGING,
            2: ChargingStatus.CHARGED,
        }.get(battery_state, ChargingStatus.UNKNOWN)

        return {
            "sequence": int(report[7]),
            "left_stick_x": int(report[1]),
            "left_stick_y": int(report[2]),
            "right_stick_x": int(report[3]),
            "right_stick_y": int(report[4]),
            "left_trigger": int(report[5]),
            "right_trigger": int(report[6]),
            "buttons": buttons,
            "touchpad_active": (touch_byte & 0x80) == 0,
            "touchpad_id": touch_byte & 0x7F,
            "touchpad_x": touch_x,
            "touchpad_y": touch_y,
            # El reporte DualSense coloca PRIMERO giroscopio (16..21) y
            # DESPUÉS acelerómetro (22..27). pydualsense 0.7.x los etiqueta
            # al revés; leer el paquete aquí evita enviar gravedad como gyro.
            "gyro_pitch": cls._signed_short(report, 16),
            "gyro_yaw": cls._signed_short(report, 18),
            "gyro_roll": cls._signed_short(report, 20),
            "accel_x": cls._signed_short(report, 22),
            "accel_y": cls._signed_short(report, 24),
            "accel_z": cls._signed_short(report, 26),
            "battery_level": min((battery & 0x0F) * 10 + 5, 100),
            "charging_status": charging,
        }

    def _state_loop(self) -> None:
        self._boost_state_thread_priority()
        next_scan = time.perf_counter()
        next_process = next_scan
        last_raw_sequence: Optional[int] = None
        while self._running:
            try:
                if self._connected and self.dualsense:
                    low_latency = self._low_latency_scan_enabled()
                    controller = self.dualsense
                    input_event = getattr(controller, "_nikaido_input_event", None)
                    event_driven = bool(
                        low_latency
                        and input_event is not None
                        and callable(getattr(input_event, "wait", None))
                        and callable(getattr(input_event, "clear", None))
                    )

                    if event_driven:
                        # Limpiar antes de mirar la secuencia evita perder una
                        # señal que llegue entre la comprobación y el wait.
                        input_event.clear()
                        peeked_sequence = self._peek_raw_sequence()
                        fresh_report = bool(
                            peeked_sequence is not None
                            and peeked_sequence != last_raw_sequence
                        )
                        heartbeat_due = time.perf_counter() >= next_process
                        if not fresh_report and not heartbeat_due:
                            input_event.wait(self.STATE_POLL_INTERVAL)
                            peeked_sequence = self._peek_raw_sequence()
                            fresh_report = bool(
                                peeked_sequence is not None
                                and peeked_sequence != last_raw_sequence
                            )
                            heartbeat_due = time.perf_counter() >= next_process

                        if fresh_report or heartbeat_due:
                            self._read_controller_state()
                            with self._lock:
                                actual_sequence = int(self._state.sequence)
                                actual_source = str(self._state.source)
                            if actual_source == "raw_hid" and actual_sequence >= 0:
                                last_raw_sequence = actual_sequence
                            else:
                                last_raw_sequence = None
                            next_process = time.perf_counter() + self.STATE_POLL_INTERVAL
                        next_scan = time.perf_counter()
                        continue

                    scan_interval = (
                        self.LOW_LATENCY_SCAN_INTERVAL
                        if low_latency
                        else self.STATE_POLL_INTERVAL
                    )
                    now = time.perf_counter()
                    peeked_sequence = self._peek_raw_sequence() if low_latency else None
                    fresh_report = bool(
                        peeked_sequence is not None
                        and peeked_sequence != last_raw_sequence
                    )
                    heartbeat_due = now >= next_process

                    if not low_latency or fresh_report or heartbeat_due:
                        self._read_controller_state()
                        with self._lock:
                            actual_sequence = int(self._state.sequence)
                            actual_source = str(self._state.source)
                        if actual_source == "raw_hid" and actual_sequence >= 0:
                            last_raw_sequence = actual_sequence
                        else:
                            last_raw_sequence = None
                        next_process = time.perf_counter() + self.STATE_POLL_INTERVAL

                    next_scan += scan_interval
                    current = time.perf_counter()
                    if next_scan < current - scan_interval:
                        next_scan = current
                    self._wait_until_state_deadline(next_scan)
                else:
                    last_raw_sequence = None
                    next_scan = time.perf_counter()
                    next_process = next_scan
                    self._stop_event.wait(self.CONNECTION_POLL_INTERVAL)
            except Exception:
                last_raw_sequence = None
                next_scan = time.perf_counter()
                next_process = next_scan
                logger.debug("Fallo temporal en el programador de entrada", exc_info=True)
                self._stop_event.wait(0.05)

    def _read_controller_state(self) -> None:
        self._read_controller_state_serialized()

    def _read_controller_state_serialized(self) -> None:
        try:
            tick_started = time.perf_counter()
            with self._lock:
                controller = self.dualsense
                session_generation = self._connection_generation
            if controller is None:
                return

            # ``states`` y ``state`` son fotografías en memoria actualizadas por
            # pydualsense; leerlas no requiere esperar escrituras físicas HID.
            raw_source_available = hasattr(controller, "states")
            raw_decoded = self._decode_raw_report(self._raw_report_snapshot(controller))
            ds_state = controller.state
            if ds_state is None and raw_decoded is None:
                raise RuntimeError("No hay estado ni reporte HID disponible")

            with self._lock:
                if (
                    controller is not self.dualsense
                    or not self._connected
                    or session_generation != self._connection_generation
                ):
                    return
                report_is_fresh = self._register_report_freshness(
                    raw_decoded, raw_source_available=raw_source_available
                )
                raw_watchdog_active = self._raw_report_seen or (
                    raw_source_available
                    and time.monotonic() - self._raw_report_wait_started
                    >= self.RAW_REPORT_STARTUP_GRACE
                )
                if (
                    raw_watchdog_active
                    and not report_is_fresh
                    and time.monotonic() - self._last_fresh_report >= self.STALE_TIMEOUT
                ):
                    raise RuntimeError("El reporte HID quedó congelado o nunca inició")

                old_battery = self._state.battery_level
                old_battery_valid = self._state.battery_valid
                old_charging = self._state.charging_status

                if raw_decoded is not None:
                    for key in (
                        "left_trigger",
                        "right_trigger",
                        "left_stick_x",
                        "left_stick_y",
                        "right_stick_x",
                        "right_stick_y",
                        "touchpad_active",
                        "touchpad_x",
                        "touchpad_y",
                        "touchpad_id",
                        "gyro_pitch",
                        "gyro_yaw",
                        "gyro_roll",
                        "accel_x",
                        "accel_y",
                        "accel_z",
                        "battery_level",
                        "charging_status",
                    ):
                        setattr(self._state, key, raw_decoded[key])
                    self._state.battery_valid = True
                    self._state.buttons = dict(raw_decoded["buttons"])
                    self._state.sequence = int(raw_decoded.get("sequence", -1))
                    self._state.source = "raw_hid"
                else:
                    # Compatibilidad con dobles de prueba y versiones antiguas
                    # de pydualsense que no publican ``states``.
                    lt_raw = getattr(ds_state, "L2_value", getattr(ds_state, "L2", 0))
                    rt_raw = getattr(ds_state, "R2_value", getattr(ds_state, "R2", 0))
                    self._state.left_trigger = (
                        255 if isinstance(lt_raw, bool) and lt_raw else int(lt_raw or 0)
                    )
                    self._state.right_trigger = (
                        255 if isinstance(rt_raw, bool) and rt_raw else int(rt_raw or 0)
                    )

                    def scale_stick(value):
                        try:
                            return int(max(0, min(255, float(value) + 128)))
                        except (TypeError, ValueError, OverflowError):
                            return 128

                    self._state.left_stick_x = scale_stick(getattr(ds_state, "LX", 0))
                    self._state.left_stick_y = scale_stick(getattr(ds_state, "LY", 0))
                    self._state.right_stick_x = scale_stick(getattr(ds_state, "RX", 0))
                    self._state.right_stick_y = scale_stick(getattr(ds_state, "RY", 0))

                    touch0 = getattr(ds_state, "trackPadTouch0", None)
                    if touch0 is not None:
                        self._state.touchpad_active = bool(getattr(touch0, "isActive", False))
                        self._state.touchpad_x = int(getattr(touch0, "X", 0))
                        self._state.touchpad_y = int(getattr(touch0, "Y", 0))
                        self._state.touchpad_id = int(getattr(touch0, "ID", 0)) & 0x7F
                    else:
                        self._state.touchpad_active = False
                        self._state.touchpad_id = 0

                    gyro = getattr(ds_state, "gyro", None)
                    accel = getattr(ds_state, "accelerometer", None)
                    self._state.gyro_pitch = int(getattr(gyro, "Pitch", 0) or 0)
                    self._state.gyro_yaw = int(getattr(gyro, "Yaw", 0) or 0)
                    self._state.gyro_roll = int(getattr(gyro, "Roll", 0) or 0)
                    self._state.accel_x = int(getattr(accel, "X", 0) or 0)
                    self._state.accel_y = int(getattr(accel, "Y", 0) or 0)
                    self._state.accel_z = int(getattr(accel, "Z", 0) or 0)
                    self._state.buttons = {
                        "cross": bool(getattr(ds_state, "cross", False)),
                        "circle": bool(getattr(ds_state, "circle", False)),
                        "square": bool(getattr(ds_state, "square", False)),
                        "triangle": bool(getattr(ds_state, "triangle", False)),
                        "L1": bool(getattr(ds_state, "L1", False)),
                        "R1": bool(getattr(ds_state, "R1", False)),
                        "L2_btn": bool(
                            getattr(
                                ds_state,
                                "L2Btn",
                                getattr(ds_state, "l2_btn", getattr(ds_state, "L2", False)),
                            )
                        ),
                        "R2_btn": bool(
                            getattr(
                                ds_state,
                                "R2Btn",
                                getattr(ds_state, "r2_btn", getattr(ds_state, "R2", False)),
                            )
                        ),
                        "L3": bool(getattr(ds_state, "L3", getattr(ds_state, "l3", False))),
                        "R3": bool(getattr(ds_state, "R3", getattr(ds_state, "r3", False))),
                        "create": bool(
                            getattr(ds_state, "create", getattr(ds_state, "share", False))
                        ),
                        "options": bool(
                            getattr(ds_state, "options", getattr(ds_state, "start", False))
                        ),
                        "ps": bool(getattr(ds_state, "PS", getattr(ds_state, "ps", False))),
                        "touchpad": bool(
                            getattr(ds_state, "touchBtn", getattr(ds_state, "touchpad", False))
                        ),
                        "mute": bool(getattr(ds_state, "micBtn", getattr(ds_state, "mute", False))),
                        "dpad_up": bool(
                            getattr(ds_state, "DpadUp", getattr(ds_state, "dpad_up", False))
                        ),
                        "dpad_down": bool(
                            getattr(ds_state, "DpadDown", getattr(ds_state, "dpad_down", False))
                        ),
                        "dpad_left": bool(
                            getattr(ds_state, "DpadLeft", getattr(ds_state, "dpad_left", False))
                        ),
                        "dpad_right": bool(
                            getattr(ds_state, "DpadRight", getattr(ds_state, "dpad_right", False))
                        ),
                    }
                    self._state.sequence = (self._state.sequence + 1) & 0xFF
                    self._state.source = "pydualsense_fallback"

                    try:
                        battery = getattr(controller, "battery", None)
                        level = getattr(battery, "Level", None)
                        if level is not None:
                            self._state.battery_level = max(0, min(100, int(level)))
                            self._state.battery_valid = True
                        state_value = getattr(battery, "State", None)
                        if state_value is not None:
                            self._state.charging_status = {
                                0: ChargingStatus.DISCHARGING,
                                1: ChargingStatus.CHARGING,
                                2: ChargingStatus.CHARGED,
                            }.get(int(state_value), ChargingStatus.UNKNOWN)
                    except Exception:
                        pass

                self._state.monotonic_ns = time.perf_counter_ns()
                self._state.timestamp = time.time()
                battery_changed = self._state.battery_valid and (
                    not old_battery_valid
                    or old_battery != self._state.battery_level
                    or old_charging != self._state.charging_status
                )
                battery_snapshot = (self._state.battery_level, self._state.charging_status)

            snapshot = self.state
            # Este candado solo coordina macros/gyro/ViGEm con la neutralización
            # de desconexión; RGB, rumble y gatillos físicos quedan fuera.
            with self._virtual_pipeline_lock:
                with self._lock:
                    session_is_current = bool(
                        self._connected
                        and controller is self.dualsense
                        and session_generation == self._connection_generation
                    )
                if not session_is_current:
                    return

                realtime_started = time.perf_counter()
                self._notify_realtime_state_update(snapshot)
                realtime_finished = time.perf_counter()

                # Un callback puede desconectar el control; validar de nuevo
                # evita enviar un snapshot viejo después de neutralizar ViGEm.
                with self._lock:
                    session_is_current = bool(
                        self._connected
                        and controller is self.dualsense
                        and session_generation == self._connection_generation
                    )
                if not session_is_current:
                    return

                self.emulator.update_from_dualsense(snapshot)
                emulator_finished = time.perf_counter()
                self._record_diagnostics(
                    snapshot,
                    raw_decoded is not None,
                    tick_started,
                    realtime_finished - realtime_started,
                    emulator_finished - realtime_finished,
                    emulator_finished - tick_started,
                )

            self._read_failures = 0
            self._last_successful_read = time.monotonic()
            if battery_changed:
                self._notify_battery_change(*battery_snapshot)

            # Monitor, touchpad y efectos físicos no necesitan 250 eventos por
            # segundo. Limitar esta rama evita que trabajo secundario robe tiempo
            # al siguiente informe, sin afectar macros/remapeo/ViGEm.
            now = time.perf_counter()
            if now - self._last_observer_notification >= self.OBSERVER_POLL_INTERVAL:
                self._last_observer_notification = now
                self._notify_state_update(snapshot)

        except Exception as exc:
            self._read_failures += 1
            stale_for = time.monotonic() - self._last_fresh_report
            logger.debug(
                "Fallo leyendo estado del DualSense (intento %s): %s", self._read_failures, exc
            )
            if self._read_failures >= self.MAX_READ_FAILURES or stale_for > self.STALE_TIMEOUT:
                logger.warning("Se perdio la señal del DualSense, reconectando...")
                self._disconnect()

    @staticmethod
    def _diag_rate(values) -> float:
        values = tuple(values)
        if len(values) < 2:
            return 0.0
        span = values[-1] - values[0]
        return (len(values) - 1) / span if span > 0 else 0.0

    @staticmethod
    def _diag_percentile(values, percentile: float) -> float:
        values = sorted(float(value) for value in values)
        if not values:
            return 0.0
        index = max(0, min(len(values) - 1, int(round((len(values) - 1) * percentile))))
        return values[index]

    @staticmethod
    def _diag_progress_rate(values) -> float:
        """Calcula eventos/segundo usando (tiempo, contador acumulado)."""
        values = tuple(values)
        if len(values) < 2:
            return 0.0
        span = float(values[-1][0]) - float(values[0][0])
        advance = int(values[-1][1]) - int(values[0][1])
        return advance / span if span > 0 and advance >= 0 else 0.0

    def _record_diagnostics(
        self,
        state: ControllerState,
        raw_report: bool,
        tick_started: float,
        realtime_seconds: float,
        emulator_seconds: float,
        pipeline_seconds: float,
    ) -> None:
        now = time.perf_counter()
        virtual_ns = time.perf_counter_ns()
        pipeline_ms = pipeline_seconds * 1000.0
        snapshot_to_virtual_ms = 0.0
        captured_ns = int(getattr(state, "monotonic_ns", 0) or 0)
        if captured_ns > 0 and virtual_ns >= captured_ns:
            snapshot_to_virtual_ms = (virtual_ns - captured_ns) / 1_000_000.0

        with self._lock:
            self._diag_total_polls += 1
            self._diag_poll_times.append(now)
            self._diag_pipeline_ms.append(pipeline_ms)
            self._diag_realtime_ms.append(realtime_seconds * 1000.0)
            self._diag_emulator_ms.append(emulator_seconds * 1000.0)
            if snapshot_to_virtual_ms >= 0.0:
                self._diag_snapshot_to_virtual_ms.append(snapshot_to_virtual_ms)
            if raw_report:
                self._diag_raw_reports += 1
            else:
                self._diag_fallback_reports += 1

            current_buttons = dict(getattr(state, "buttons", {}) or {})
            button_edge = False
            if self._diag_last_buttons is not None and current_buttons != self._diag_last_buttons:
                button_edge = True
                self._diag_button_edge_ms.append(pipeline_ms)
            self._diag_last_buttons = current_buttons

            sequence = int(getattr(state, "sequence", -1))
            if sequence < 0 or not raw_report:
                self._diag_unique_reports += 1
                self._diag_unique_times.append(now)
            elif self._diag_last_sequence is None:
                self._diag_last_sequence = sequence
                self._diag_unique_reports += 1
                self._diag_unique_times.append(now)
                self._diag_device_progress.append((now, self._diag_sequence_progress))
            else:
                delta = (sequence - int(self._diag_last_sequence)) & 0xFF
                if delta == 0:
                    # No es un paquete HID duplicado: Nikaido volvió a consultar
                    # antes de que pydualsense publicara el siguiente informe.
                    self._diag_duplicate_reports += 1
                elif delta <= 32:
                    self._diag_unique_reports += 1
                    self._diag_unique_times.append(now)
                    self._diag_sequence_progress += delta
                    self._diag_sequence_advance_total += delta
                    self._diag_device_progress.append((now, self._diag_sequence_progress))
                    # Informes intermedios reemplazados por el estado más nuevo.
                    # Son coalescidos, no pérdidas del bus USB/Bluetooth.
                    if delta > 1:
                        self._diag_coalesced_reports += delta - 1
                    self._diag_last_sequence = sequence
                else:
                    # Un salto enorme suele ser reinicio/reconexión del contador.
                    # No lo convertimos en miles de paquetes "perdidos".
                    self._diag_sequence_discontinuities += 1
                    self._diag_last_sequence = sequence
                    self._diag_sequence_progress = 0
                    self._diag_device_progress.clear()
                    self._diag_device_progress.append((now, 0))
                    self._diag_unique_reports += 1
                    self._diag_unique_times.append(now)

            self._diag_last_tick = {
                "sequence": sequence,
                "source": str(getattr(state, "source", "unknown")),
                "captured_ns": captured_ns,
                "virtual_ns": virtual_ns,
                "pipeline_ms": round(pipeline_ms, 4),
                "realtime_ms": round(realtime_seconds * 1000.0, 4),
                "emulator_ms": round(emulator_seconds * 1000.0, 4),
                "snapshot_to_virtual_ms": round(snapshot_to_virtual_ms, 4),
                "button_edge": button_edge,
            }

    def reset_diagnostics(self) -> None:
        with self._lock:
            self._diag_poll_times.clear()
            self._diag_unique_times.clear()
            self._diag_device_progress.clear()
            self._diag_pipeline_ms.clear()
            self._diag_realtime_ms.clear()
            self._diag_emulator_ms.clear()
            self._diag_snapshot_to_virtual_ms.clear()
            self._diag_button_edge_ms.clear()
            self._diag_total_polls = 0
            self._diag_unique_reports = 0
            self._diag_duplicate_reports = 0
            self._diag_coalesced_reports = 0
            self._diag_sequence_discontinuities = 0
            self._diag_sequence_progress = 0
            self._diag_sequence_advance_total = 0
            self._diag_raw_reports = 0
            self._diag_fallback_reports = 0
            self._diag_last_sequence = None
            self._diag_last_buttons = None
            self._diag_last_tick = {}
            self._diag_started = time.perf_counter()

    def get_last_pipeline_sample(self) -> dict:
        """Último desglose temporal del tick que terminó en ViGEm."""
        with self._lock:
            return dict(self._diag_last_tick)

    def get_diagnostics_snapshot(self) -> dict:
        with self._lock:
            pipeline = tuple(self._diag_pipeline_ms)
            realtime = tuple(self._diag_realtime_ms)
            emulator = tuple(self._diag_emulator_ms)
            snapshot_to_virtual = tuple(self._diag_snapshot_to_virtual_ms)
            button_edges = tuple(self._diag_button_edge_ms)
            total = self._diag_total_polls
            reused = self._diag_duplicate_reports
            device_hz = self._diag_progress_rate(self._diag_device_progress)
            fresh_hz = self._diag_rate(self._diag_unique_times)
            processing_hz = self._diag_rate(self._diag_poll_times)
            advanced = max(0, self._diag_sequence_advance_total)
            coalesced = self._diag_coalesced_reports
            controller = self.dualsense
            hid_pump = {
                "installed": bool(getattr(controller, "_nikaido_low_latency_pump", False)),
                "active": bool(getattr(controller, "_nikaido_pump_active", False)),
                "output_thread_active": bool(
                    getattr(controller, "_nikaido_output_thread_active", False)
                ),
                "input_reports": int(getattr(controller, "_nikaido_input_reports", 0) or 0),
                "physical_output_writes": int(
                    getattr(controller, "_nikaido_output_writes", 0) or 0
                ),
                "physical_output_skips": int(
                    getattr(controller, "_nikaido_output_skips", 0) or 0
                ),
                "physical_output_limit_hz": round(
                    1.0 / self.PHYSICAL_OUTPUT_INTERVAL, 2
                ),
                "error": str(getattr(controller, "_nikaido_pump_error", "") or ""),
            }
            return {
                "connected": self._connected,
                "connection_type": self._connection_type.value,
                "device_report_hz": round(device_hz, 2),
                "processing_hz": round(processing_hz, 2),
                "low_latency_scan_active": self._low_latency_scan_enabled(),
                "low_latency_scan_hz": round(1.0 / self.LOW_LATENCY_SCAN_INTERVAL, 2),
                "timer_resolution_ms": (
                    self.WINDOWS_TIMER_PERIOD_MS if self._timer_resolution_active else None
                ),
                "state_thread_priority_boosted": self._state_thread_priority_boosted,
                "hid_input_pump": hid_pump,
                "fresh_snapshot_hz": round(fresh_hz, 2),
                # Alias antiguos para que plugins/reportes 2.1.0 no fallen.
                "poll_hz": round(processing_hz, 2),
                "unique_hid_hz": round(fresh_hz, 2),
                "total_polls": total,
                "unique_reports": self._diag_unique_reports,
                "reused_snapshots": reused,
                "reused_snapshot_percent": round(reused * 100.0 / total, 2) if total else 0.0,
                "duplicate_reports": reused,
                "duplicate_percent": round(reused * 100.0 / total, 2) if total else 0.0,
                "coalesced_reports": coalesced,
                "coalesced_percent": round(coalesced * 100.0 / advanced, 2) if advanced else 0.0,
                "sequence_discontinuities": self._diag_sequence_discontinuities,
                "confirmed_lost_reports": 0,
                "loss_detection_supported": False,
                "lost_reports": 0,
                "raw_reports": self._diag_raw_reports,
                "fallback_reports": self._diag_fallback_reports,
                "read_failures": self._read_failures,
                "rumble": {
                    "manual_test_active": time.monotonic() < self._rumble_test_until,
                    "last_output": tuple(self._rumble_last_output),
                    "last_source": self._rumble_last_source,
                    "writes": self._rumble_write_count,
                    "errors": self._rumble_errors,
                    "last_error": self._rumble_last_error,
                },
                "pipeline_avg_ms": round(sum(pipeline) / len(pipeline), 3) if pipeline else 0.0,
                "pipeline_p95_ms": round(self._diag_percentile(pipeline, 0.95), 3),
                "pipeline_max_ms": round(max(pipeline), 3) if pipeline else 0.0,
                "snapshot_to_virtual_avg_ms": round(
                    sum(snapshot_to_virtual) / len(snapshot_to_virtual), 3
                )
                if snapshot_to_virtual
                else 0.0,
                "snapshot_to_virtual_p95_ms": round(
                    self._diag_percentile(snapshot_to_virtual, 0.95), 3
                ),
                "button_edge_count": len(button_edges),
                "button_edge_avg_ms": round(sum(button_edges) / len(button_edges), 3)
                if button_edges
                else 0.0,
                "button_edge_p95_ms": round(self._diag_percentile(button_edges, 0.95), 3),
                "button_edge_max_ms": round(max(button_edges), 3) if button_edges else 0.0,
                "realtime_avg_ms": round(sum(realtime) / len(realtime), 3) if realtime else 0.0,
                "emulator_avg_ms": round(sum(emulator) / len(emulator), 3) if emulator else 0.0,
                "uptime_seconds": round(time.perf_counter() - self._diag_started, 1),
                "sequence": self._state.sequence,
                "source": self._state.source,
                "hid_backend": get_hid_backend_status().name,
                "hid_backend_fallback": get_hid_backend_status().fallback,
                "hid_backend_available": get_hid_backend_status().available,
                "hid_backend_error": get_hid_backend_status().error,
                "pydualsense_available": PYDUALSENSE_AVAILABLE,
                "pydualsense_import_error": PYDUALSENSE_IMPORT_ERROR,
                "last_connect_error": self._last_connect_error,
            }

    def _notify_callbacks(self, callbacks: list, *args: Any) -> None:
        with self._lock:
            listeners = tuple(callbacks)
        failed = []
        for callback in listeners:
            try:
                callback(*args)
            except Exception:
                # Los callbacks críticos pueden notificarse a 250 Hz. Mantener uno
                # roto produciría una tormenta de excepciones y degradaría la
                # interfaz, así que se registra una vez y se retira.
                logger.exception("Callback desactivado tras fallar en ConnectionManager")
                failed.append(callback)
        if failed:
            with self._lock:
                callbacks[:] = [callback for callback in callbacks if callback not in failed]

    def _notify_connect(self, conn_type: ConnectionType) -> None:
        self._notify_callbacks(self._on_connect, conn_type)

    def _notify_disconnect(self) -> None:
        self._notify_callbacks(self._on_disconnect)

    def _notify_realtime_state_update(self, state: ControllerState) -> None:
        self._notify_callbacks(self._on_realtime_state_update, state)

    def _notify_state_update(self, state: ControllerState) -> None:
        self._notify_callbacks(self._on_state_update, state)

    def _notify_battery_change(self, level: int, status: ChargingStatus) -> None:
        self._notify_callbacks(self._on_battery_change, level, status)

    def _notify_error(self, message: str) -> None:
        self._notify_callbacks(self._on_error, message)

    def get_battery_info(self) -> tuple[int, ChargingStatus]:
        with self._lock:
            return self._state.battery_level, self._state.charging_status

    def perform_bluetooth_reset(self) -> bool:
        return self.bluetooth_manager.full_bluetooth_reset()

    def set_led_color(self, r: int, g: int, b: int) -> bool:
        """Escribe la barra RGB dentro del candado HID compartido.

        Luces, micrófono, vibración y gatillos terminan en el mismo reporte de
        salida del DualSense. Serializar la escritura evita que dos servicios
        internos construyan reportes cruzados durante una reconexión.
        """
        try:
            red = max(0, min(255, int(r)))
            green = max(0, min(255, int(g)))
            blue = max(0, min(255, int(b)))
        except (TypeError, ValueError, OverflowError):
            return False
        with self._io_lock:
            controller = self.dualsense
            if controller is None:
                return False
            try:
                controller.light.setColorI(red, green, blue)
                return True
            except Exception as exc:
                logger.debug("No se pudo cambiar la barra RGB: %s", exc)
                return False

    def set_microphone_state(self, muted: bool, *, mute_audio: bool = True) -> bool:
        """Sincroniza el estado/LED naranja del micrófono del DualSense.

        ``pydualsense`` conserva estos campos dentro del reporte de salida, por
        lo que luces, vibración y gatillos pueden seguir actualizándose sin
        borrar el mute. El candado HID evita cruzarlo con una desconexión.
        """
        with self._io_lock:
            controller = self.dualsense
            if controller is None:
                return False
            audio = getattr(controller, "audio", None)
            if audio is None:
                return False
            if mute_audio:
                setter = getattr(audio, "setMicrophoneState", None)
                if callable(setter):
                    try:
                        setter(bool(muted))
                        return True
                    except Exception as exc:
                        logger.debug(
                            "setMicrophoneState falló; se intentará solo el LED MIC: %s",
                            exc,
                        )
            led_setter = getattr(audio, "setMicrophoneLED", None)
            if callable(led_setter):
                try:
                    led_setter(bool(muted))
                    return True
                except Exception as exc:
                    logger.debug("No se pudo cambiar el LED MIC del DualSense: %s", exc)
        return False

    def set_player_led_pattern(self, pattern: int) -> bool:
        """Configura el patrón crudo de los indicadores blancos (5 bits).

        ``pydualsense.PlayerID`` es un ``IntFlag``. Aceptar el patrón permite
        apagar los indicadores y reutilizar los cuatro estados oficiales como
        una barra de batería sin tocar la barra RGB del touchpad.
        """
        if PlayerID is None:
            return False
        try:
            mask = max(0, min(31, int(pattern)))
        except (TypeError, ValueError, OverflowError):
            return False
        with self._io_lock:
            controller = self.dualsense
            if controller is None:
                return False
            try:
                try:
                    value = PlayerID(mask)
                except TypeError:
                    # Compatibilidad con dobles de prueba y versiones antiguas
                    # que exponen constantes, pero no el constructor IntFlag.
                    known = {
                        4: PlayerID.PLAYER_1,
                        10: PlayerID.PLAYER_2,
                        21: PlayerID.PLAYER_3,
                        27: PlayerID.PLAYER_4,
                        31: PlayerID.ALL,
                    }
                    value = known.get(mask)
                    if value is None:
                        return False
                controller.light.setPlayerID(value)
                return True
            except Exception as exc:
                logger.debug("No se pudo cambiar el patrón de jugador: %s", exc)
                return False

    def set_player_led(self, player: int) -> bool:
        """Configura uno de los cuatro estados oficiales o todas las luces."""
        if PlayerID is None:
            return False
        try:
            choices = {
                1: PlayerID.PLAYER_1,
                2: PlayerID.PLAYER_2,
                3: PlayerID.PLAYER_3,
                4: PlayerID.PLAYER_4,
                5: PlayerID.ALL,
            }
            value = choices.get(int(player), PlayerID.PLAYER_1)
        except Exception:
            return False
        with self._io_lock:
            controller = self.dualsense
            if controller is None:
                return False
            try:
                controller.light.setPlayerID(value)
                return True
            except Exception as exc:
                logger.debug("No se pudo cambiar el indicador de jugador: %s", exc)
                return False

    @staticmethod
    def _motor_value(value: Any) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError, OverflowError):
            parsed = 0
        return max(0, min(255, parsed))

    def _write_rumble(self, left_motor: int, right_motor: int, *, source: str) -> bool:
        left = self._motor_value(left_motor)
        right = self._motor_value(right_motor)
        with self._io_lock:
            controller = self.dualsense
            if controller is None:
                with self._lock:
                    self._rumble_last_error = "DualSense no conectado"
                return False
            try:
                left_setter = getattr(controller, "setLeftMotor", None)
                right_setter = getattr(controller, "setRightMotor", None)
                if callable(left_setter) and callable(right_setter):
                    left_setter(left)
                    right_setter(right)
                else:
                    # Compatibilidad defensiva con forks de pydualsense que
                    # exponen los campos del reporte pero no los dos helpers.
                    setattr(controller, "leftMotor", left)
                    setattr(controller, "rightMotor", right)
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                with self._lock:
                    self._rumble_errors += 1
                    self._rumble_last_error = message
                logger.warning("No se pudo escribir la vibración del DualSense: %s", message)
                return False

        with self._lock:
            self._rumble_last_output = (left, right)
            self._rumble_last_source = str(source or "direct")
            self._rumble_write_count += 1
            self._rumble_last_error = ""
        return True

    def set_rumble(
        self,
        left_motor: int,
        right_motor: int,
        *,
        source: str = "direct",
        force: bool = False,
    ) -> bool:
        """Escribe ambos motores por una única ruta segura.

        El feedback del juego no puede apagar una prueba iniciada desde la UI.
        Al terminar la prueba, el puente vuelve a enviar su estado normalmente.
        """
        now = time.monotonic()
        with self._lock:
            manual_active = now < self._rumble_test_until
        if source == "game" and manual_active and not force:
            return False
        return self._write_rumble(left_motor, right_motor, source=source)

    def start_rumble_test(
        self,
        left_motor: int,
        right_motor: int,
        *,
        duration_ms: int = 900,
    ) -> bool:
        """Inicia una prueba fiable incluso dentro del EXE compilado.

        Reafirmar el valor por unos milisegundos evita que un tick simultáneo de
        ViGEm o el arranque del hilo de salida borre la única escritura manual.
        """
        left = self._motor_value(left_motor)
        right = self._motor_value(right_motor)
        duration = max(100, min(5000, int(duration_ms))) / 1000.0
        with self._lock:
            self._rumble_test_generation += 1
            generation = self._rumble_test_generation
            self._rumble_test_until = time.monotonic() + duration
            self._rumble_test_output = (left, right)

        if not self._write_rumble(left, right, source="manual_test"):
            with self._lock:
                if generation == self._rumble_test_generation:
                    self._rumble_test_until = 0.0
                    self._rumble_test_output = (0, 0)
            return False

        def replay() -> None:
            interval = 0.045
            while True:
                with self._lock:
                    if generation != self._rumble_test_generation:
                        return
                    remaining = self._rumble_test_until - time.monotonic()
                    output = self._rumble_test_output
                if remaining <= 0:
                    break
                time.sleep(min(interval, max(0.005, remaining)))
                with self._lock:
                    if generation != self._rumble_test_generation:
                        return
                self._write_rumble(*output, source="manual_test")

            with self._lock:
                if generation != self._rumble_test_generation:
                    return
                self._rumble_test_until = 0.0
                self._rumble_test_output = (0, 0)
            self._write_rumble(0, 0, source="manual_test")

        threading.Thread(
            target=replay,
            name="DualSenseRumbleTest",
            daemon=True,
        ).start()
        return True

    def stop_rumble_test(self) -> bool:
        with self._lock:
            self._rumble_test_generation += 1
            self._rumble_test_until = 0.0
            self._rumble_test_output = (0, 0)
        return self._write_rumble(0, 0, source="manual_test")

    def get_rumble_diagnostics(self) -> dict:
        with self._lock:
            return {
                "manual_test_active": time.monotonic() < self._rumble_test_until,
                "last_output": tuple(self._rumble_last_output),
                "last_source": self._rumble_last_source,
                "writes": self._rumble_write_count,
                "errors": self._rumble_errors,
                "last_error": self._rumble_last_error,
            }
