"""Motor central de giroscopio, Gyro Aim y mezcla con control virtual."""

from __future__ import annotations

import logging
import math
import threading
import time
import statistics
from collections import deque
from typing import Any, Callable, List, Optional, Tuple

from .gyro_config import GyroCalibration, GyroConfig, GyroTelemetry
from .gyro_mouse import GyroMouseOutput

logger = logging.getLogger(__name__)


class GyroEngine:
    """Procesa sensores en el mismo flujo de estado que la emulacion.

    No crea un segundo escritor de ViGEm. El mouse se envia directamente y la
    salida de stick se entrega a EmulatorManager para que el unico update del
    gamepad virtual siga ocurriendo en ConnectionManager.
    """

    GYRO_UNITS_PER_DPS = 16.0

    def __init__(self, connection_manager=None, emulator=None) -> None:
        self.connection_manager = connection_manager
        self.emulator = emulator if emulator is not None else getattr(connection_manager, "emulator", None)
        self.mouse = GyroMouseOutput()

        self._config = GyroConfig()
        self._profile_id: Optional[str] = None
        self._running = False
        self._lock = threading.RLock()
        self._telemetry = GyroTelemetry()
        self._on_config_change: List[Callable[[Optional[str], GyroConfig], None]] = []

        self._last_sample_time: Optional[float] = None
        # La frecuencia visible se basa en secuencias HID nuevas, no en la
        # distancia entre callbacks. Los callbacks pueden llegar agrupados y
        # hacían aparecer valores imposibles de 500+ Hz.
        self._sample_times = deque(maxlen=600)
        self._last_rate_sequence: Optional[int] = None
        self._last_rate_source = ""
        self._sample_rate_ema = 0.0
        self._smooth_x = 0.0
        self._smooth_y = 0.0
        self._orientation_pitch = 0.0
        self._orientation_yaw = 0.0
        self._orientation_roll = 0.0
        self._dynamic_bias = [0.0, 0.0, 0.0]

        self._toggle_active = False
        self._last_activation_pressed = False
        self._test_active_until = 0.0

        # Estado de Flick Stick. Los giros se acumulan en grados para poder
        # repartirlos suavemente sin bloquear el hilo HID.
        self._flick_engaged = False
        self._flick_last_angle: Optional[float] = None
        self._flick_mouse_pending = 0.0
        self._flick_mouse_time = 0.0
        self._flick_stick_degrees = 0.0

        self._calibration_target = 0
        self._calibration_count = 0
        self._calibration_sum = [0.0, 0.0, 0.0]
        self._calibration_samples = []
        self._calibration_accel_samples = []

        if connection_manager:
            subscribe = getattr(
                connection_manager,
                "on_realtime_state_update",
                getattr(connection_manager, "on_state_update", None),
            )
            if subscribe:
                subscribe(self._on_state_update)
        if connection_manager and hasattr(connection_manager, "on_connect"):
            connection_manager.on_connect(self._on_connect)
        if connection_manager and hasattr(connection_manager, "on_disconnect"):
            connection_manager.on_disconnect(self._on_disconnect)
        if self.emulator and hasattr(self.emulator, "on_mouse_to_gyro_emergency_stop"):
            self.emulator.on_mouse_to_gyro_emergency_stop(
                self._handle_mouse_to_gyro_emergency_stop
            )

    def _handle_mouse_to_gyro_emergency_stop(self) -> None:
        """Ctrl+M es una pausa de sesión; no destruye el ajuste del perfil."""
        # EmulatorManager mantiene el estado temporal y vuelve a armar la
        # captura con otra pulsación. Conservar ``mouse_to_gyro_enabled`` evita
        # que el checkbox se desmarque y que el perfil pierda su preferencia.
        logger.info("Mouse → gyro alternado con Ctrl+M")

    # ===== Ciclo de vida =====

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._last_sample_time = None
            self._sample_times.clear()
            self._last_rate_sequence = None
            self._last_rate_source = ""
            self._sample_rate_ema = 0.0
        logger.info("GyroEngine iniciado")

    def stop(self) -> None:
        with self._lock:
            self._running = False
            self._test_active_until = 0.0
            self._calibration_target = 0
            self._clear_outputs_locked()
        self.mouse.stop()
        logger.info("GyroEngine detenido")

    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def is_mouse_available(self) -> bool:
        return self.mouse.is_available()

    # ===== Configuracion =====

    def apply_config(self, config: Any, profile_id: Optional[str] = None) -> None:
        parsed = config if isinstance(config, GyroConfig) else GyroConfig.from_dict(config)
        with self._lock:
            self._config = parsed.copy()
            self._profile_id = profile_id
            self._reset_filters_locked()
            self._sync_emulator_mode_locked()
            if not self._config.enabled or self._config.mode == "disabled":
                self._clear_outputs_locked()
        logger.info("Gyro config aplicada: perfil=%s modo=%s activo=%s", profile_id, parsed.mode, parsed.enabled)

    def update_config(self, **changes: Any) -> GyroConfig:
        with self._lock:
            previous = self._config
            data = previous.to_dict()
            data.update(changes)
            self._config = GyroConfig.from_dict(data)
            if any((
                previous.enabled != self._config.enabled,
                previous.mode != self._config.mode,
                previous.activation != self._config.activation,
                previous.activation_button != self._config.activation_button,
                previous.flick_stick_enabled != self._config.flick_stick_enabled,
                previous.flick_threshold != self._config.flick_threshold,
            )):
                self._reset_filters_locked()
            self._sync_emulator_mode_locked()
            if not self._config.enabled or self._config.mode == "disabled":
                self._clear_outputs_locked()
            snapshot = self._config.copy()
            profile_id = self._profile_id
        self._notify_config_change(profile_id, snapshot)
        return snapshot

    def get_config(self) -> GyroConfig:
        with self._lock:
            return self._config.copy()

    def get_profile_id(self) -> Optional[str]:
        with self._lock:
            return self._profile_id

    def on_config_change(
        self, callback: Callable[[Optional[str], GyroConfig], None]
    ) -> Callable[[], None]:
        if not callable(callback):
            raise TypeError("El callback debe ser invocable")
        with self._lock:
            if callback not in self._on_config_change:
                self._on_config_change.append(callback)

        def unsubscribe() -> None:
            with self._lock:
                self._on_config_change[:] = [
                    item for item in self._on_config_change if item != callback
                ]

        return unsubscribe

    def _notify_config_change(self, profile_id: Optional[str], config: GyroConfig) -> None:
        with self._lock:
            callbacks = list(self._on_config_change)
        failed = []
        for callback in callbacks:
            try:
                callback(profile_id, config.copy())
            except Exception:
                logger.exception("Callback de gyro config desactivado tras fallar")
                failed.append(callback)
        if failed:
            with self._lock:
                self._on_config_change[:] = [
                    callback
                    for callback in self._on_config_change
                    if callback not in failed
                ]

    def _sync_emulator_mode_locked(self) -> None:
        # Libera inmediatamente la salida del modo anterior. Esperar al
        # siguiente paquete dejaba el stick inclinado al pasar a passthrough.
        if self._config.mode != "mouse":
            self.mouse.reset()
        if not self.emulator:
            return
        enabled = bool(self._config.enabled and self._config.mode == "passthrough_ds4")
        try:
            calibration = self._config.calibration
            self.emulator.set_ds4_motion_passthrough(
                enabled,
                gyro_signs=self._config.passthrough_gyro_signs,
                accel_signs=self._config.passthrough_accel_signs,
                gyro_bias=(
                    calibration.pitch_bias,
                    calibration.yaw_bias,
                    calibration.roll_bias,
                ),
                gyro_bias_trusted=bool(calibration.valid and calibration.version >= 3),
                gyro_axes=self._config.passthrough_gyro_axes,
                accel_axes=self._config.passthrough_accel_axes,
                deadzone=self._config.passthrough_deadzone,
                mouse_to_gyro_enabled=self._config.mouse_to_gyro_enabled,
                mouse_to_gyro_sensitivity=self._config.mouse_to_gyro_sensitivity,
                mouse_to_gyro_invert_x=self._config.mouse_to_gyro_invert_x,
                mouse_to_gyro_invert_y=self._config.mouse_to_gyro_invert_y,
                mouse_to_gyro_combine=self._config.mouse_to_gyro_combine_physical,
                mouse_to_gyro_max_dps=self._config.mouse_to_gyro_max_dps,
            )
            if self._config.mode != "right_stick":
                self.emulator.clear_right_stick_override()
        except Exception as exc:
            logger.debug("No se pudo sincronizar passthrough DS4: %s", exc)

    # ===== Calibracion / recentrado =====

    def begin_calibration(self, sample_count: int = 90) -> None:
        with self._lock:
            self._calibration_target = max(30, min(500, int(sample_count)))
            self._calibration_count = 0
            self._calibration_sum = [0.0, 0.0, 0.0]
            self._calibration_samples = []
            self._calibration_accel_samples = []
            self._dynamic_bias = [0.0, 0.0, 0.0]
            self._telemetry.calibrating = True
            self._telemetry.calibration_progress = 0.0
            self._telemetry.calibration_error = ""
        logger.info("Calibracion de gyro iniciada (%s muestras)", self._calibration_target)

    def cancel_calibration(self) -> None:
        with self._lock:
            self._calibration_target = 0
            self._telemetry.calibrating = False
            self._telemetry.calibration_progress = 0.0
            self._telemetry.calibration_error = ""

    def recenter(self) -> None:
        with self._lock:
            self._orientation_pitch = 0.0
            self._orientation_yaw = 0.0
            self._orientation_roll = 0.0
            self._smooth_x = 0.0
            self._smooth_y = 0.0
            self.mouse.reset()
            if self.emulator:
                try:
                    self.emulator.recenter_ds4_motion()
                except Exception:
                    pass
        logger.info("Gyro recentrado")

    def test_output(self, duration: float = 2.0) -> None:
        with self._lock:
            self._test_active_until = time.monotonic() + max(0.25, min(10.0, float(duration)))

    # ===== Telemetria =====

    def get_telemetry(self) -> GyroTelemetry:
        with self._lock:
            return GyroTelemetry(**vars(self._telemetry))

    def get_orientation(self) -> Tuple[float, float, float]:
        with self._lock:
            return self._orientation_pitch, self._orientation_yaw, self._orientation_roll

    # ===== Procesamiento =====

    def _on_connect(self, _connection_type: Any = None) -> None:
        # Al reconectar, ConnectionManager conserva el modo virtual. Rearmamos
        # el passthrough que se desactivo durante la desconexion para no dejar
        # el DS4 virtual sin sensores hasta tocar otra vez la interfaz.
        with self._lock:
            if self._running:
                self._last_sample_time = None
                self._sample_times.clear()
                self._last_rate_sequence = None
                self._last_rate_source = ""
                self._sample_rate_ema = 0.0
                self._sync_emulator_mode_locked()

    def _on_disconnect(self) -> None:
        with self._lock:
            self._last_sample_time = None
            self._sample_times.clear()
            self._last_rate_sequence = None
            self._last_rate_source = ""
            self._sample_rate_ema = 0.0
            self._last_activation_pressed = False
            self._toggle_active = False
            self._clear_outputs_locked()

    def _on_state_update(self, state: Any) -> None:
        with self._lock:
            if not self._running:
                return

            now = time.perf_counter()
            if self._last_sample_time is None:
                dt = 1.0 / max(30, self._config.update_hz)
            else:
                dt = max(0.001, min(0.05, now - self._last_sample_time))
            self._last_sample_time = now

            source = str(getattr(state, "source", "unknown"))
            try:
                sequence = int(getattr(state, "sequence", -1))
            except (TypeError, ValueError, OverflowError):
                sequence = -1
            fresh_sample = True
            if source == "raw_hid" and sequence >= 0:
                fresh_sample = not (
                    self._last_rate_source == source
                    and self._last_rate_sequence == sequence
                )
                self._last_rate_source = source
                self._last_rate_sequence = sequence
            if fresh_sample:
                self._sample_times.append(now)
                if len(self._sample_times) >= 2:
                    span = self._sample_times[-1] - self._sample_times[0]
                    self._sample_rate_ema = (len(self._sample_times) - 1) / span if span > 0 else 0.0
                else:
                    self._sample_rate_ema = 0.0

            raw = (
                float(getattr(state, "gyro_pitch", 0.0)),
                float(getattr(state, "gyro_yaw", 0.0)),
                float(getattr(state, "gyro_roll", 0.0)),
            )
            accel = (
                float(getattr(state, "accel_x", 0.0)),
                float(getattr(state, "accel_y", 0.0)),
                float(getattr(state, "accel_z", 0.0)),
            )

            if self._calibration_target and fresh_sample:
                # Un mismo snapshot HID puede ser consultado varias veces por el
                # loop de 250 Hz. Contarlo repetido falseaba la calibración.
                self._consume_calibration_sample_locked(raw, accel)

            cal = self._config.calibration
            trusted_calibration = bool(cal.valid and cal.version >= 3)
            base_bias = (
                (cal.pitch_bias, cal.yaw_bias, cal.roll_bias)
                if trusted_calibration
                else (0.0, 0.0, 0.0)
            )
            corrected_raw = [
                raw[0] - base_bias[0] - self._dynamic_bias[0],
                raw[1] - base_bias[1] - self._dynamic_bias[1],
                raw[2] - base_bias[2] - self._dynamic_bias[2],
            ]
            dps = [value / self.GYRO_UNITS_PER_DPS for value in corrected_raw]

            activation_active = self._activation_is_active_locked(state)
            aim_mode = self._config.mode in ("mouse", "right_stick")
            active = bool(
                self._config.enabled
                and (
                    self._config.mode == "passthrough_ds4"
                    or (aim_mode and activation_active)
                )
            )
            if self._config.drift_filter and aim_mode and self._config.enabled and not self._calibration_target:
                quiet_limit = max(0.25, min(1.0, self._config.deadzone * 0.5))
                if fresh_sample and (
                    not active or math.sqrt(sum(value * value for value in dps)) <= quiet_limit
                ):
                    # El filtro adaptativo aprende a la tasa real del sensor, no
                    # a la tasa de sondeo de Nikaido. Así no sobrecorrige drift.
                    self._update_dynamic_bias_locked(raw, cal, dps)

            if active and aim_mode and self._config.flick_stick_enabled:
                self._update_flick_locked(state)
            else:
                self._reset_flick_locked()

            self._orientation_pitch += dps[0] * dt
            self._orientation_yaw += dps[1] * dt
            self._orientation_roll += dps[2] * dt

            self._telemetry.pitch = dps[0]
            self._telemetry.yaw = dps[1]
            self._telemetry.roll = dps[2]
            self._telemetry.accel_x, self._telemetry.accel_y, self._telemetry.accel_z = accel
            self._telemetry.sample_hz = self._sample_rate_ema
            self._telemetry.mode = self._config.mode
            self._telemetry.active = active
            self._telemetry.calibrated = trusted_calibration
            self._telemetry.flick_active = bool(
                self._flick_engaged
                or abs(self._flick_mouse_pending) > 0.01
                or abs(self._flick_stick_degrees) > 0.01
            )
            self._telemetry.flick_pending = (
                self._flick_mouse_pending
                if self._config.mode == "mouse"
                else self._flick_stick_degrees
            )
            self._telemetry.mouse_to_gyro_active = bool(
                self._config.enabled
                and self._config.mode == "passthrough_ds4"
                and self._config.mouse_to_gyro_enabled
                and self.emulator
                and getattr(self.emulator, "is_mouse_to_gyro_running", lambda: False)()
            )

            if not self._config.enabled or self._config.mode in ("disabled", "passthrough_ds4"):
                self._telemetry.output_x = 0.0
                self._telemetry.output_y = 0.0
                if self._config.mode != "passthrough_ds4":
                    self._clear_outputs_locked()
                return

            if not active:
                self._smooth_x *= self._config.smoothing
                self._smooth_y *= self._config.smoothing
                self._telemetry.output_x = 0.0
                self._telemetry.output_y = 0.0
                self._release_mode_output_locked()
                return

            aim_x, aim_y = self._prepare_aim_axes_locked(dps[1], dps[0])
            if self._config.mode == "mouse":
                self._process_mouse_locked(aim_x, aim_y, dt)
            elif self._config.mode == "right_stick":
                self._process_stick_locked(state, aim_x, aim_y, dt)

    def _consume_calibration_sample_locked(
        self,
        raw: Tuple[float, float, float],
        accel: Tuple[float, float, float],
    ) -> None:
        self._calibration_samples.append(tuple(raw))
        self._calibration_accel_samples.append(tuple(accel))
        self._calibration_count += 1
        self._telemetry.calibration_progress = self._calibration_count / self._calibration_target

        if self._calibration_count < self._calibration_target:
            return

        samples = tuple(self._calibration_samples)
        accel_samples = tuple(self._calibration_accel_samples)
        centers = tuple(
            statistics.median(sample[index] for sample in samples)
            for index in range(3)
        )
        ranges = tuple(
            max(sample[index] for sample in samples) - min(sample[index] for sample in samples)
            for index in range(3)
        )
        deviations = tuple(
            statistics.median(abs(sample[index] - centers[index]) for sample in samples)
            for index in range(3)
        )
        accel_ranges = tuple(
            max(sample[index] for sample in accel_samples) - min(sample[index] for sample in accel_samples)
            for index in range(3)
        ) if accel_samples else (0.0, 0.0, 0.0)
        accel_magnitudes = [math.sqrt(sum(value * value for value in sample)) for sample in accel_samples]
        accel_has_data = bool(accel_magnitudes and max(accel_magnitudes) >= 256.0)
        accel_stable = (
            not accel_has_data
            or (
                max(accel_ranges) <= 140.0
                and max(accel_magnitudes) - min(accel_magnitudes) <= 180.0
            )
        )
        gyro_stable = max(ranges) <= 24.0 and max(deviations) <= 5.0
        plausible = max(abs(value) for value in centers) <= 512.0

        self._calibration_target = 0
        self._calibration_count = 0
        self._calibration_sum = [0.0, 0.0, 0.0]
        self._calibration_samples = []
        self._calibration_accel_samples = []
        self._telemetry.calibrating = False

        if not (gyro_stable and accel_stable and plausible):
            self._telemetry.calibration_progress = 0.0
            self._telemetry.calibration_error = (
                "Se detectó movimiento. Coloca el control en una superficie y repite."
            )
            logger.info(
                "Calibracion de gyro rechazada: ranges=%s mad=%s accel=%s",
                ranges,
                deviations,
                accel_ranges,
            )
            return

        self._config.calibration = GyroCalibration(
            version=3,
            valid=True,
            pitch_bias=centers[0],
            yaw_bias=centers[1],
            roll_bias=centers[2],
        )
        self._telemetry.calibration_progress = 1.0
        self._telemetry.calibration_error = ""
        self._telemetry.calibrated = True
        self._sync_emulator_mode_locked()
        config = self._config.copy()
        profile_id = self._profile_id
        threading.Thread(
            target=self._notify_config_change,
            args=(profile_id, config),
            name="GyroCalibrationSave",
            daemon=True,
        ).start()
        logger.info("Calibracion de gyro completada: %s", config.calibration.to_dict())

    def _update_dynamic_bias_locked(self, raw: Tuple[float, float, float], cal: GyroCalibration, dps: list[float]) -> None:
        if math.sqrt(sum(value * value for value in dps)) > 2.0:
            return
        base = (
            (cal.pitch_bias, cal.yaw_bias, cal.roll_bias)
            if cal.valid and cal.version >= 3
            else (0.0, 0.0, 0.0)
        )
        alpha = 0.002
        for index in range(3):
            residual = raw[index] - base[index]
            self._dynamic_bias[index] = (1.0 - alpha) * self._dynamic_bias[index] + alpha * residual

    def _activation_is_active_locked(self, state: Any) -> bool:
        config = self._config
        buttons = getattr(state, "buttons", {}) or {}
        selected = config.activation_button
        pressed = bool(buttons.get(selected, False))
        if selected in ("L2", "L2_btn"):
            pressed = pressed or int(getattr(state, "left_trigger", 0)) >= config.activation_threshold
        elif selected in ("R2", "R2_btn"):
            pressed = pressed or int(getattr(state, "right_trigger", 0)) >= config.activation_threshold

        if config.activation == "always":
            active = True
        elif config.activation == "hold_l2":
            active = int(getattr(state, "left_trigger", 0)) >= config.activation_threshold
        elif config.activation == "hold_button":
            active = pressed
        elif config.activation == "touchpad":
            active = bool(getattr(state, "touchpad_active", False))
        elif config.activation == "toggle":
            if pressed and not self._last_activation_pressed:
                self._toggle_active = not self._toggle_active
            active = self._toggle_active
        elif config.activation == "inverted":
            active = not pressed
        else:
            active = False

        self._last_activation_pressed = pressed
        if time.monotonic() < self._test_active_until:
            active = True
        return active

    def _prepare_aim_axes_locked(self, yaw_dps: float, pitch_dps: float) -> Tuple[float, float]:
        x = -yaw_dps if self._config.invert_x else yaw_dps
        y = -pitch_dps if self._config.invert_y else pitch_dps

        magnitude = math.hypot(x, y)
        if magnitude <= self._config.deadzone:
            x = y = 0.0
        elif magnitude > 0 and self._config.deadzone > 0:
            scale = (magnitude - self._config.deadzone) / magnitude
            x *= scale
            y *= scale

        smoothing = self._config.smoothing
        self._smooth_x = smoothing * self._smooth_x + (1.0 - smoothing) * x
        self._smooth_y = smoothing * self._smooth_y + (1.0 - smoothing) * y

        if abs(self._smooth_x) < self._config.min_threshold:
            self._smooth_x = 0.0
        if abs(self._smooth_y) < self._config.min_threshold:
            self._smooth_y = 0.0
        return self._smooth_x, self._smooth_y

    @staticmethod
    def _normalize_stick_axis(value: Any) -> float:
        try:
            raw = max(0.0, min(255.0, float(value)))
        except (TypeError, ValueError, OverflowError):
            raw = 128.0
        return (raw - 128.0) / (127.0 if raw >= 128.0 else 128.0)

    @staticmethod
    def _shortest_angle_delta(current: float, previous: float) -> float:
        return (current - previous + 180.0) % 360.0 - 180.0

    def _update_flick_locked(self, state: Any) -> None:
        x = self._normalize_stick_axis(getattr(state, "right_stick_x", 128))
        y = self._normalize_stick_axis(getattr(state, "right_stick_y", 128))
        magnitude = math.hypot(x, y)
        release = min(self._config.flick_threshold - 0.02, self._config.flick_release_threshold)

        if magnitude < max(0.05, release):
            self._flick_engaged = False
            self._flick_last_angle = None
            self._telemetry.flick_angle = 0.0
            return
        if magnitude < self._config.flick_threshold and not self._flick_engaged:
            return

        # Arriba es 0°, derecha +90°, izquierda -90° y abajo 180°.
        angle = math.degrees(math.atan2(x, -y))
        self._telemetry.flick_angle = angle
        if not self._flick_engaged:
            self._flick_engaged = True
            self._flick_last_angle = angle
            if abs(angle) >= self._config.flick_min_angle:
                self._queue_flick_locked(angle)
            return

        previous = self._flick_last_angle
        self._flick_last_angle = angle
        if previous is None:
            return
        delta = self._shortest_angle_delta(angle, previous)
        # Ignora ruido angular microscópico del stick, pero conserva giros
        # circulares lentos y continuos.
        if abs(delta) >= 0.35:
            self._queue_flick_locked(delta)

    def _queue_flick_locked(self, angle: float) -> None:
        if self._config.flick_invert_x:
            angle = -angle
        if self._config.mode == "mouse":
            self._flick_mouse_pending += angle * self._config.flick_pixels_per_degree
            duration = self._config.flick_duration_ms / 1000.0
            self._flick_mouse_time = max(self._flick_mouse_time, duration)
        elif self._config.mode == "right_stick":
            self._flick_stick_degrees += angle

    def _consume_flick_mouse_locked(self, dt: float) -> float:
        pending = self._flick_mouse_pending
        if abs(pending) < 0.01:
            self._flick_mouse_pending = 0.0
            self._flick_mouse_time = 0.0
            return 0.0
        remaining = max(dt, self._flick_mouse_time)
        fraction = min(1.0, dt / remaining)
        step = pending * fraction
        self._flick_mouse_pending -= step
        self._flick_mouse_time = max(0.0, self._flick_mouse_time - dt)
        return step

    def _consume_flick_stick_locked(self, dt: float) -> float:
        pending = self._flick_stick_degrees
        if abs(pending) < 0.01:
            self._flick_stick_degrees = 0.0
            return 0.0
        degrees_per_second = 180.0 / max(0.04, self._config.flick_turn_180_ms / 1000.0)
        consumed = min(abs(pending), degrees_per_second * dt)
        self._flick_stick_degrees -= math.copysign(consumed, pending)
        return math.copysign(self._config.stick_max_output, pending)

    def _reset_flick_locked(self) -> None:
        self._flick_engaged = False
        self._flick_last_angle = None
        self._flick_mouse_pending = 0.0
        self._flick_mouse_time = 0.0
        self._flick_stick_degrees = 0.0
        self._telemetry.flick_active = False
        self._telemetry.flick_angle = 0.0
        self._telemetry.flick_pending = 0.0

    def _process_mouse_locked(self, x_dps: float, y_dps: float, dt: float) -> None:
        speed = math.hypot(x_dps, y_dps)
        accel_mult = 1.0
        if self._config.acceleration_enabled:
            accel_mult += self._config.acceleration * min(3.0, speed / 180.0)

        velocity_x = x_dps * self._config.sensitivity_x * accel_mult
        velocity_y = y_dps * self._config.sensitivity_y * accel_mult
        velocity_mag = math.hypot(velocity_x, velocity_y)
        if velocity_mag > self._config.max_speed and velocity_mag > 0:
            scale = self._config.max_speed / velocity_mag
            velocity_x *= scale
            velocity_y *= scale

        flick_dx = self._consume_flick_mouse_locked(dt) if self._config.flick_stick_enabled else 0.0
        dx = velocity_x * dt + flick_dx
        dy = velocity_y * dt
        self.mouse.move(dx, dy)
        self._telemetry.output_x = velocity_x + (flick_dx / dt if dt > 0 else 0.0)
        self._telemetry.output_y = velocity_y
        if self.emulator:
            if self._config.flick_stick_enabled:
                # Flick Stick reutiliza la palanca derecha; neutralizarla evita
                # que el juego reciba a la vez la palanca normal y el giro.
                self.emulator.set_right_stick_override(0.0, 0.0)
            else:
                self.emulator.clear_right_stick_override()

    def _process_stick_locked(self, state: Any, x_dps: float, y_dps: float, dt: float) -> None:
        gx = x_dps * self._config.stick_sensitivity_x
        gy = y_dps * self._config.stick_sensitivity_y
        gx, gy = self._apply_response_curve(gx, gy, self._config.response_curve)
        gx, gy = self._apply_radial_deadzone(gx, gy, self._config.stick_deadzone, self._config.stick_anti_deadzone)

        magnitude = math.hypot(gx, gy)
        max_output = self._config.stick_max_output
        if magnitude > max_output and magnitude > 0:
            scale = max_output / magnitude
            gx *= scale
            gy *= scale

        if self._config.flick_stick_enabled:
            px = py = 0.0
            flick_x = self._consume_flick_stick_locked(dt)
        else:
            px = max(-1.0, min(1.0, (float(getattr(state, "right_stick_x", 128)) - 128.0) / 127.0))
            py = max(-1.0, min(1.0, (float(getattr(state, "right_stick_y", 128)) - 128.0) / 127.0))
            flick_x = 0.0
        mix = self._config.stick_mix

        if self._config.stick_mix_mode == "replace":
            out_x, out_y = gx, gy
        elif self._config.stick_mix_mode == "prioritize":
            if math.hypot(gx, gy) > 0.001:
                out_x = gx * mix + px * (1.0 - mix)
                out_y = gy * mix + py * (1.0 - mix)
            else:
                out_x, out_y = px, py
        else:  # add
            out_x = px + gx * mix
            out_y = py + gy * mix

        out_x += flick_x
        out_x, out_y = self._clamp_unit_circle(out_x, out_y)
        self._telemetry.output_x = out_x
        self._telemetry.output_y = out_y
        if self.emulator:
            self.emulator.set_right_stick_override(out_x, out_y)

    @staticmethod
    def _apply_response_curve(x: float, y: float, curve: str) -> Tuple[float, float]:
        def transform(value: float) -> float:
            sign = -1.0 if value < 0 else 1.0
            amount = abs(value)
            if curve == "exponential":
                amount = amount ** 1.5
            elif curve == "precision":
                amount = amount ** 2.0
            return sign * amount
        return transform(x), transform(y)

    @staticmethod
    def _apply_radial_deadzone(x: float, y: float, deadzone: float, anti_deadzone: float) -> Tuple[float, float]:
        magnitude = math.hypot(x, y)
        if magnitude <= deadzone or magnitude <= 0:
            return 0.0, 0.0
        normalized = min(1.0, (magnitude - deadzone) / max(0.0001, 1.0 - deadzone))
        output_mag = anti_deadzone + normalized * (1.0 - anti_deadzone)
        scale = output_mag / magnitude
        return x * scale, y * scale

    @staticmethod
    def _clamp_unit_circle(x: float, y: float) -> Tuple[float, float]:
        magnitude = math.hypot(x, y)
        if magnitude > 1.0:
            return x / magnitude, y / magnitude
        return max(-1.0, min(1.0, x)), max(-1.0, min(1.0, y))

    def _release_mode_output_locked(self) -> None:
        if self.emulator:
            self.emulator.clear_right_stick_override()
        self.mouse.reset()

    def _clear_outputs_locked(self) -> None:
        self._smooth_x = 0.0
        self._smooth_y = 0.0
        self._telemetry.output_x = 0.0
        self._telemetry.output_y = 0.0
        self._telemetry.active = False
        self._telemetry.mouse_to_gyro_active = False
        self._reset_flick_locked()
        self._release_mode_output_locked()
        if self.emulator:
            try:
                self.emulator.set_ds4_motion_passthrough(False)
            except Exception:
                pass

    def _reset_filters_locked(self) -> None:
        self._smooth_x = 0.0
        self._smooth_y = 0.0
        self._dynamic_bias = [0.0, 0.0, 0.0]
        self._last_sample_time = None
        self._last_activation_pressed = False
        self._toggle_active = False
        self._reset_flick_locked()
        self.mouse.reset()
