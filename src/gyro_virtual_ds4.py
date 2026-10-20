"""Construccion y envio del reporte extendido de un DS4 virtual.

La clase evita acoplar EmulatorManager a detalles privados de vgamepad y
mantiene una ruta de compatibilidad para instalaciones donde
VDS4Gamepad.update_extended_report no esta expuesto directamente.
"""

from __future__ import annotations

import ctypes
import logging
import math
import time
import statistics
from collections import deque
from dataclasses import dataclass
from typing import Any, Optional, Tuple, Type

logger = logging.getLogger(__name__)


class _FallbackDS4Touch(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("bPacketCounter", ctypes.c_ubyte),
        ("bIsUpTrackingNum1", ctypes.c_ubyte),
        ("bTouchData1", ctypes.c_ubyte * 3),
        ("bIsUpTrackingNum2", ctypes.c_ubyte),
        ("bTouchData2", ctypes.c_ubyte * 3),
    ]


class _FallbackDS4SubReportEx(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("bThumbLX", ctypes.c_ubyte),
        ("bThumbLY", ctypes.c_ubyte),
        ("bThumbRX", ctypes.c_ubyte),
        ("bThumbRY", ctypes.c_ubyte),
        ("wButtons", ctypes.c_ushort),
        ("bSpecial", ctypes.c_ubyte),
        ("bTriggerL", ctypes.c_ubyte),
        ("bTriggerR", ctypes.c_ubyte),
        ("wTimestamp", ctypes.c_ushort),
        ("bBatteryLvl", ctypes.c_ubyte),
        ("wGyroX", ctypes.c_short),
        ("wGyroY", ctypes.c_short),
        ("wGyroZ", ctypes.c_short),
        ("wAccelX", ctypes.c_short),
        ("wAccelY", ctypes.c_short),
        ("wAccelZ", ctypes.c_short),
        ("_bUnknown1", ctypes.c_ubyte * 5),
        ("bBatteryLvlSpecial", ctypes.c_ubyte),
        ("_bUnknown2", ctypes.c_ubyte * 2),
        ("bTouchPacketsN", ctypes.c_ubyte),
        ("sCurrentTouch", _FallbackDS4Touch),
        ("sPreviousTouch", _FallbackDS4Touch * 2),
    ]


class _FallbackDS4ReportEx(ctypes.Union):
    _pack_ = 1
    _fields_ = [
        ("Report", _FallbackDS4SubReportEx),
        ("ReportBuffer", ctypes.c_ubyte * 63),
    ]


@dataclass
class DS4MotionPacket:
    gyro: Tuple[int, int, int]
    accel: Tuple[int, int, int]
    timestamp: int
    battery_percent: int
    charging: bool
    touch_active: bool
    touch_x: int
    touch_y: int
    touch_id: int = 0


class DS4ExtendedReportAdapter:
    """Copia el reporte base del gamepad y agrega sensores/touchpad."""

    # El timestamp del DS4 avanza en unidades aproximadas de 5.33 us.
    TIMESTAMP_UNIT_SECONDS = 0.00000533
    STARTUP_SAMPLE_COUNT = 32
    # El centrado automático solo acepta un bias pequeño. Una rotación real
    # sostenida puede ser estable, así que no basta con mirar la varianza.
    MAX_AUTO_BIAS = 24.0
    MAX_STARTUP_RANGE = 18.0
    MAX_STARTUP_MAD = 4.0

    def __init__(self, vg_module: Any = None) -> None:
        # Siempre construimos el wire report con nuestra estructura pack=1.
        # Algunas versiones de vgamepad declaran DS4_TOUCH.bTouchData2 como
        # c_ushort * 3, aunque ViGEmClient lo define como BYTE[3]. Eso cambia
        # offsets y tamaño. Conservamos el tipo nativo solo como envoltorio
        # para satisfacer los argtypes de ctypes.
        self._native_report_cls: Optional[Type[Any]] = None
        self._vcom = None
        self._vcli = None
        self._last_time = time.perf_counter()
        self._timestamp = 0
        self._touch_counter = 0
        self._last_touch_active = False
        self._available = False
        self._last_error_log = 0.0
        # La IMU se procesa como un vector atómico X/Y/Z. Nunca se calibra un
        # eje por separado ni se "aprende" mientras el usuario juega: ambas
        # cosas podían convertir pitch en yaw o dejar un giro opuesto.
        self._gyro_bias = (0.0, 0.0, 0.0)
        self._gyro_bias_trusted = False
        self._auto_gyro_bias = (0.0, 0.0, 0.0)
        self._startup_gyro_samples = deque(maxlen=self.STARTUP_SAMPLE_COUNT)
        self._startup_accel_samples = deque(maxlen=self.STARTUP_SAMPLE_COUNT)
        self._startup_complete = False
        self._startup_aborted = False
        self._auto_center_deadline = time.perf_counter() + 1.5
        self._gyro_axes = (0, 1, 2)
        self._accel_axes = (0, 1, 2)
        self._deadzone = 6.0
        self._vg_module = vg_module
        self._discover_vgamepad_api()

    @property
    def is_supported(self) -> bool:
        return self.is_available()

    @property
    def support_description(self) -> str:
        if self._available and self._vcli is not None:
            return "update_extended_report / binding ViGEm DS4_EX disponible"
        return "se comprobara update_extended_report al crear el DS4 virtual"

    def _discover_vgamepad_api(self) -> None:
        try:
            import vgamepad.win.vigem_commons as vcom
            self._vcom = vcom
            if hasattr(vcom, "DS4_REPORT_EX"):
                self._native_report_cls = vcom.DS4_REPORT_EX
            try:
                import vgamepad.win.vigem_client as vcli
                self._vcli = vcli
            except Exception:
                self._vcli = None
            self._available = True
        except Exception:
            # Linux no tiene la ruta win; el resto de la app puede seguir.
            self._available = False

    def is_available(self, gamepad: Any = None) -> bool:
        if gamepad is not None and callable(getattr(gamepad, "update_extended_report", None)):
            return True
        return bool(self._available and self._vcli is not None)

    def reset(self) -> None:
        self._last_time = time.perf_counter()
        self._timestamp = 0
        self._touch_counter = 0
        self._last_touch_active = False
        self._auto_gyro_bias = (0.0, 0.0, 0.0)
        self._startup_gyro_samples.clear()
        self._startup_accel_samples.clear()
        self._startup_complete = bool(self._gyro_bias_trusted)
        self._startup_aborted = False
        self._auto_center_deadline = time.perf_counter() + 1.5

    @staticmethod
    def _parse_bias(bias) -> Tuple[float, float, float]:
        try:
            parsed = tuple(float(value) for value in tuple(bias)[:3])
        except (TypeError, ValueError, OverflowError):
            return (0.0, 0.0, 0.0)
        return parsed if len(parsed) == 3 else (0.0, 0.0, 0.0)

    @staticmethod
    def _parse_axes(axes) -> Tuple[int, int, int]:
        try:
            parsed = tuple(int(value) for value in tuple(axes)[:3])
        except (TypeError, ValueError, OverflowError):
            return (0, 1, 2)
        return parsed if len(parsed) == 3 and sorted(parsed) == [0, 1, 2] else (0, 1, 2)

    def set_gyro_bias(self, bias=(0.0, 0.0, 0.0), *, trusted: Optional[bool] = None) -> None:
        """Aplica una calibración completa tomada desde un reporte coherente.

        ``trusted=False`` migra perfiles 2.0.3 o anteriores: sus valores se
        conservan en el archivo, pero el passthrough hace un centro nuevo porque
        esas versiones podían capturar tres ejes de paquetes distintos.
        """
        parsed = self._parse_bias(bias)
        if trusted is None:
            trusted = any(abs(value) >= 0.5 for value in parsed)
        trusted = bool(trusted and all(abs(value) <= 512.0 for value in parsed))
        changed = parsed != self._gyro_bias or trusted != self._gyro_bias_trusted
        self._gyro_bias = parsed
        self._gyro_bias_trusted = trusted
        if changed:
            self.reset()

    def set_motion_transform(
        self,
        *,
        gyro_axes=(0, 1, 2),
        accel_axes=(0, 1, 2),
        deadzone: float = 6.0,
    ) -> None:
        self._gyro_axes = self._parse_axes(gyro_axes)
        self._accel_axes = self._parse_axes(accel_axes)
        try:
            self._deadzone = max(0.0, min(64.0, float(deadzone)))
        except (TypeError, ValueError, OverflowError):
            self._deadzone = 6.0

    @staticmethod
    def _accel_window_is_stationary(samples: Tuple[Tuple[float, float, float], ...]) -> bool:
        if not samples:
            return True
        magnitudes = [math.sqrt(sum(value * value for value in sample)) for sample in samples]
        # Pruebas/simuladores pueden no proporcionar acelerómetro.
        if max(magnitudes) < 256.0:
            return True
        ranges = [
            max(sample[index] for sample in samples) - min(sample[index] for sample in samples)
            for index in range(3)
        ]
        return max(ranges) <= 120.0 and (max(magnitudes) - min(magnitudes)) <= 160.0

    @staticmethod
    def _gyro_window_center(samples: Tuple[Tuple[float, float, float], ...]):
        """Devuelve la mediana solo cuando los tres ejes están quietos."""
        if not samples:
            return None
        centers = tuple(statistics.median(sample[index] for sample in samples) for index in range(3))
        ranges = tuple(
            max(sample[index] for sample in samples) - min(sample[index] for sample in samples)
            for index in range(3)
        )
        deviations = tuple(
            statistics.median(abs(sample[index] - centers[index]) for sample in samples)
            for index in range(3)
        )
        if (
            max(ranges) > DS4ExtendedReportAdapter.MAX_STARTUP_RANGE
            or max(deviations) > DS4ExtendedReportAdapter.MAX_STARTUP_MAD
            or math.sqrt(sum(value * value for value in centers)) > DS4ExtendedReportAdapter.MAX_AUTO_BIAS
        ):
            return None
        return centers

    def _try_startup_center(self) -> None:
        if self._startup_complete or self._startup_aborted or self._gyro_bias_trusted:
            return
        if len(self._startup_gyro_samples) < self._startup_gyro_samples.maxlen:
            return
        gyro_samples = tuple(self._startup_gyro_samples)
        accel_samples = tuple(self._startup_accel_samples)
        center = self._gyro_window_center(gyro_samples)
        if center is not None and self._accel_window_is_stationary(accel_samples):
            self._auto_gyro_bias = center
            self._startup_complete = True
            return
        # La primera ventana contenía movimiento. No inventamos un centro ni
        # retenemos la salida por más tiempo; el usuario puede calibrar después.
        self._startup_aborted = True

    def _correct_gyro(
        self,
        raw: Tuple[float, float, float],
        accel: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> Tuple[float, float, float]:
        now = time.perf_counter()
        manual = self._gyro_bias if self._gyro_bias_trusted else (0.0, 0.0, 0.0)
        residual = tuple(raw[index] - manual[index] for index in range(3))

        if not self._gyro_bias_trusted and not self._startup_complete and not self._startup_aborted:
            magnitude = math.sqrt(sum(value * value for value in residual))
            # Una rotación real también puede verse perfectamente estable. Solo
            # usamos auto-centro dentro del rango razonable de bias del sensor;
            # fuera de él dejamos pasar el movimiento sin aprenderlo.
            if magnitude > self.MAX_AUTO_BIAS:
                self._startup_aborted = True
                self._startup_gyro_samples.clear()
                self._startup_accel_samples.clear()
            elif now <= self._auto_center_deadline:
                self._startup_gyro_samples.append(residual)
                self._startup_accel_samples.append(accel)
                self._try_startup_center()
                if not self._startup_complete and not self._startup_aborted:
                    return (0.0, 0.0, 0.0)
            else:
                self._startup_aborted = True

        corrected = tuple(residual[index] - self._auto_gyro_bias[index] for index in range(3))
        # El passthrough no debe escalar ni mezclar ejes. La zona muerta es una
        # puerta radial: bajo el ruido queda neutral; sobre ella pasa el vector
        # físico exacto al DS4 virtual.
        if math.sqrt(sum(value * value for value in corrected)) <= self._deadzone:
            return (0.0, 0.0, 0.0)
        return corrected

    @staticmethod
    def _transform(
        values: Tuple[float, float, float],
        axes: Tuple[int, int, int],
        signs,
    ) -> Tuple[float, float, float]:
        parsed_signs = tuple(-1 if int(value) < 0 else 1 for value in tuple(signs)[:3])
        if len(parsed_signs) != 3:
            parsed_signs = (1, 1, 1)
        return tuple(values[axes[index]] * parsed_signs[index] for index in range(3))

    @staticmethod
    def _short(value: Any) -> int:
        try:
            return max(-32768, min(32767, int(round(float(value)))))
        except (TypeError, ValueError, OverflowError):
            return 0

    @staticmethod
    def _byte(value: Any) -> int:
        try:
            return max(0, min(255, int(round(float(value)))))
        except (TypeError, ValueError, OverflowError):
            return 0

    @staticmethod
    def _report_byte(value: Any) -> int:
        """Recupera el byte real de campos c_byte de vgamepad.

        vgamepad 0.1.0 declara sticks/gatillos DS4 con ``c_byte`` firmado.
        Por eso 255 se observa desde Python como -1. Solo para copiar el
        reporte base debemos reinterpretar esos negativos como 0..255.
        """
        try:
            integer = int(value)
            if -128 <= integer < 0:
                return integer & 0xFF
            return max(0, min(255, integer))
        except (TypeError, ValueError, OverflowError):
            return 0

    def _next_timestamp(self) -> int:
        now = time.perf_counter()
        dt = max(0.0, min(0.1, now - self._last_time))
        self._last_time = now
        increment = max(1, int(round(dt / self.TIMESTAMP_UNIT_SECONDS)))
        self._timestamp = (self._timestamp + increment) & 0xFFFF
        return self._timestamp

    def make_packet(
        self,
        state: Any,
        gyro_signs=(1, 1, 1),
        accel_signs=(1, 1, 1),
        *,
        synthetic_gyro=(0.0, 0.0, 0.0),
        replace_physical: bool = False,
    ) -> DS4MotionPacket:
        charging_status = getattr(getattr(state, "charging_status", None), "value", "")
        charging = charging_status in ("cargando", "cargado completo")
        raw_gyro = (
            float(getattr(state, "gyro_pitch", 0) or 0),
            float(getattr(state, "gyro_yaw", 0) or 0),
            float(getattr(state, "gyro_roll", 0) or 0),
        )
        raw_accel = (
            float(getattr(state, "accel_x", 0) or 0),
            float(getattr(state, "accel_y", 0) or 0),
            float(getattr(state, "accel_z", 0) or 0),
        )
        corrected = self._correct_gyro(raw_gyro, raw_accel)
        physical_gyro = self._transform(corrected, self._gyro_axes, gyro_signs)
        physical_accel = self._transform(raw_accel, self._accel_axes, accel_signs)
        try:
            synthetic = tuple(float(value) for value in tuple(synthetic_gyro)[:3])
        except (TypeError, ValueError, OverflowError):
            synthetic = (0.0, 0.0, 0.0)
        if len(synthetic) != 3:
            synthetic = (0.0, 0.0, 0.0)
        output_gyro = synthetic if replace_physical else tuple(
            physical_gyro[index] + synthetic[index] for index in range(3)
        )
        return DS4MotionPacket(
            gyro=tuple(self._short(value) for value in output_gyro),
            accel=tuple(self._short(value) for value in physical_accel),
            timestamp=self._next_timestamp(),
            battery_percent=max(0, min(100, int(getattr(state, "battery_level", 0)))),
            charging=charging,
            touch_active=bool(getattr(state, "touchpad_active", False)),
            touch_x=max(0, min(1919, int(getattr(state, "touchpad_x", 0)))),
            touch_y=max(0, min(942, int(getattr(state, "touchpad_y", 0)))),
            touch_id=max(0, min(127, int(getattr(state, "touchpad_id", 0)))),
        )

    def build_report(self, base_report: Any, packet: DS4MotionPacket) -> Any:
        # Se rellena primero una representacion garantizada de 63 bytes con
        # los offsets exactos del DS4_REPORT_EX de ViGEmClient.
        wire = _FallbackDS4ReportEx()
        report = wire.Report

        # Estado tradicional. Esta copia es la garantia de que el reporte
        # extendido no borra botones, sticks ni gatillos.
        report.bThumbLX = self._report_byte(getattr(base_report, "bThumbLX", 128))
        report.bThumbLY = self._report_byte(getattr(base_report, "bThumbLY", 128))
        report.bThumbRX = self._report_byte(getattr(base_report, "bThumbRX", 128))
        report.bThumbRY = self._report_byte(getattr(base_report, "bThumbRY", 128))
        report.wButtons = int(getattr(base_report, "wButtons", 0)) & 0xFFFF
        report.bSpecial = self._report_byte(getattr(base_report, "bSpecial", 0))
        report.bTriggerL = self._report_byte(getattr(base_report, "bTriggerL", 0))
        report.bTriggerR = self._report_byte(getattr(base_report, "bTriggerR", 0))

        report.wTimestamp = packet.timestamp
        report.bBatteryLvl = self._byte(round(packet.battery_percent * 255 / 100))
        report.wGyroX, report.wGyroY, report.wGyroZ = packet.gyro
        report.wAccelX, report.wAccelY, report.wAccelZ = packet.accel

        # Byte nativo de bateria DS4: nibble bajo 0-10; bit 4 cargando.
        battery_steps = max(0, min(10, int(round(packet.battery_percent / 10))))
        report.bBatteryLvlSpecial = battery_steps | (0x10 if packet.charging else 0)

        self._fill_touch(report, packet)

        if self._native_report_cls is None:
            return wire

        # update_extended_report() termina llamando a una funcion ctypes cuyo
        # argtype es POINTER(vgamepad.DS4_REPORT_EX). Entregamos ese tipo, pero
        # copiamos nuestro buffer empaquetado para no heredar sus offsets
        # incorrectos en versiones afectadas.
        native = self._native_report_cls()
        ctypes.memmove(ctypes.addressof(native), ctypes.addressof(wire), 63)
        return native

    def _fill_touch(self, report: Any, packet: DS4MotionPacket) -> None:
        if packet.touch_active and not self._last_touch_active:
            self._touch_counter = (self._touch_counter + 1) & 0x7F
        self._last_touch_active = packet.touch_active

        report.bTouchPacketsN = 1
        touch = report.sCurrentTouch
        touch.bPacketCounter = self._touch_counter & 0xFF
        tracking_id = packet.touch_id if packet.touch_active else self._touch_counter
        touch.bIsUpTrackingNum1 = (tracking_id & 0x7F) | (0x00 if packet.touch_active else 0x80)
        self._encode_touch_xyz(touch.bTouchData1, packet.touch_x, packet.touch_y)
        touch.bIsUpTrackingNum2 = 0x80
        self._zero_three(touch.bTouchData2)

        # Historial coherente pero neutro; algunas herramientas esperan las
        # dos estructuras aunque solo haya un paquete actual.
        for previous in report.sPreviousTouch:
            previous.bPacketCounter = touch.bPacketCounter
            previous.bIsUpTrackingNum1 = touch.bIsUpTrackingNum1
            self._copy_three(previous.bTouchData1, touch.bTouchData1)
            previous.bIsUpTrackingNum2 = 0x80
            self._zero_three(previous.bTouchData2)

    @staticmethod
    def _encode_touch_xyz(target: Any, x: int, y: int) -> None:
        values = (x & 0xFF, ((x >> 8) & 0x0F) | ((y & 0x0F) << 4), (y >> 4) & 0xFF)
        for index, value in enumerate(values):
            target[index] = value

    @staticmethod
    def _zero_three(target: Any) -> None:
        for index in range(3):
            target[index] = 0

    @staticmethod
    def _copy_three(target: Any, source: Any) -> None:
        for index in range(3):
            target[index] = source[index]

    def update(
        self,
        gamepad: Any,
        state: Any,
        gyro_signs=(1, 1, 1),
        accel_signs=(1, 1, 1),
        *,
        synthetic_gyro=(0.0, 0.0, 0.0),
        replace_physical: bool = False,
    ) -> bool:
        if gamepad is None or not hasattr(gamepad, "report"):
            return False

        try:
            packet = self.make_packet(
                state,
                gyro_signs=gyro_signs,
                accel_signs=accel_signs,
                synthetic_gyro=synthetic_gyro,
                replace_physical=replace_physical,
            )
            extended = self.build_report(gamepad.report, packet)

            direct = getattr(gamepad, "update_extended_report", None)
            if callable(direct):
                direct(extended)
                return True

            # Compatibilidad con versiones/forks que exponen solo el binding.
            if self._vcli is not None and hasattr(self._vcli, "vigem_target_ds4_update_ex_ptr"):
                func = self._vcli.vigem_target_ds4_update_ex_ptr
                busp = getattr(gamepad, "_busp", None)
                devicep = getattr(gamepad, "_devicep", None)
                if busp is None or devicep is None:
                    return False

                if self._vcom is not None and hasattr(self._vcom, "DS4_REPORT_EX"):
                    pointer = ctypes.cast(ctypes.byref(extended), ctypes.POINTER(self._vcom.DS4_REPORT_EX))
                else:
                    pointer = ctypes.byref(extended)
                result = func(busp, devicep, pointer)
                # ViGEm devuelve 0x20000000 cuando todo salio bien.
                return int(result) == 0x20000000

            return False
        except Exception as exc:
            now = time.monotonic()
            if now - self._last_error_log > 5.0:
                logger.warning("Fallo enviando reporte DS4 extendido: %s", exc)
                self._last_error_log = now
            return False
