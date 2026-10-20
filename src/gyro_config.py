"""Configuracion y telemetria del sistema de giroscopio de Nikaido."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Tuple


GYRO_MODES = ("disabled", "passthrough_ds4", "mouse", "right_stick")
ACTIVATION_MODES = ("always", "hold_l2", "hold_button", "touchpad", "toggle", "inverted")
RESPONSE_CURVES = ("linear", "exponential", "precision")
STICK_MIX_MODES = ("add", "replace", "prioritize")


@dataclass
class GyroCalibration:
    # v3 identifica calibraciones tomadas desde el reporte HID atómico con el
    # orden correcto del DualSense: gyro primero y acelerómetro después.
    # Las versiones anteriores pueden contener gravedad en lugar de bias.
    version: int = 3
    valid: bool = False
    pitch_bias: float = 0.0
    yaw_bias: float = 0.0
    roll_bias: float = 0.0

    @classmethod
    def from_dict(cls, data: Any) -> "GyroCalibration":
        data = data if isinstance(data, dict) else {}
        return cls(
            version=_int(data.get("version", 1), 1, 3),
            valid=bool(data.get("valid", False)),
            pitch_bias=_float(data.get("pitch_bias", 0.0), -32768.0, 32767.0),
            yaw_bias=_float(data.get("yaw_bias", 0.0), -32768.0, 32767.0),
            roll_bias=_float(data.get("roll_bias", 0.0), -32768.0, 32767.0),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GyroConfig:
    """Configuracion completa y retrocompatible por perfil."""

    enabled: bool = False
    mode: str = "disabled"

    # Gyro aim como mouse
    sensitivity_x: float = 1.25
    sensitivity_y: float = 1.25
    invert_x: bool = False
    invert_y: bool = True
    deadzone: float = 1.25               # grados/segundo
    smoothing: float = 0.20              # 0 = crudo, 0.95 = muy suave
    min_threshold: float = 0.10          # salida minima despues del filtro
    max_speed: float = 1800.0            # pixeles/segundo
    acceleration_enabled: bool = False
    acceleration: float = 0.35
    drift_filter: bool = True
    update_hz: int = 120

    # Activacion
    activation: str = "always"
    activation_button: str = "L2_btn"
    activation_threshold: int = 20

    # Gyro como stick derecho
    stick_sensitivity_x: float = 0.018
    stick_sensitivity_y: float = 0.018
    stick_deadzone: float = 0.04
    stick_anti_deadzone: float = 0.12
    response_curve: str = "linear"
    stick_max_output: float = 1.0
    stick_mix_mode: str = "add"
    stick_mix: float = 1.0

    # Flick Stick. La palanca derecha selecciona un ángulo de giro y el gyro
    # queda libre para la precisión fina. Funciona tanto con salida de mouse
    # como con stick derecho y permanece apagado en perfiles existentes.
    flick_stick_enabled: bool = False
    flick_threshold: float = 0.82
    flick_release_threshold: float = 0.55
    flick_min_angle: float = 5.0
    flick_pixels_per_degree: float = 4.0
    flick_duration_ms: int = 85
    flick_turn_180_ms: int = 240
    flick_invert_x: bool = False

    # Passthrough DS4. Se deja configurable internamente para poder corregir
    # revisiones de hardware sin romper perfiles existentes.
    passthrough_gyro_signs: Tuple[int, int, int] = (1, 1, 1)
    passthrough_accel_signs: Tuple[int, int, int] = (1, 1, 1)
    passthrough_gyro_axes: Tuple[int, int, int] = (0, 1, 2)
    passthrough_accel_axes: Tuple[int, int, int] = (0, 1, 2)
    passthrough_deadzone: float = 6.0

    # Fuente inversa opcional: el movimiento del mouse se convierte en IMU del
    # DS4 virtual. Apagado por defecto y guardado dentro del perfil .Nika.
    mouse_to_gyro_enabled: bool = False
    mouse_to_gyro_sensitivity: float = 0.12  # grados por cuenta de mouse
    mouse_to_gyro_invert_x: bool = False
    mouse_to_gyro_invert_y: bool = False
    mouse_to_gyro_combine_physical: bool = False
    mouse_to_gyro_max_dps: float = 1400.0

    calibration: GyroCalibration = field(default_factory=GyroCalibration)

    @classmethod
    def from_dict(cls, data: Any) -> "GyroConfig":
        data = data if isinstance(data, dict) else {}
        defaults = cls()

        mode = str(data.get("mode", defaults.mode))
        if mode not in GYRO_MODES:
            mode = defaults.mode

        activation = str(data.get("activation", defaults.activation))
        if activation not in ACTIVATION_MODES:
            activation = defaults.activation

        curve = str(data.get("response_curve", defaults.response_curve))
        if curve not in RESPONSE_CURVES:
            curve = defaults.response_curve

        mix_mode = str(data.get("stick_mix_mode", defaults.stick_mix_mode))
        if mix_mode not in STICK_MIX_MODES:
            mix_mode = defaults.stick_mix_mode

        return cls(
            enabled=bool(data.get("enabled", defaults.enabled)),
            mode=mode,
            sensitivity_x=_float(data.get("sensitivity_x", defaults.sensitivity_x), 0.01, 30.0),
            sensitivity_y=_float(data.get("sensitivity_y", defaults.sensitivity_y), 0.01, 30.0),
            invert_x=bool(data.get("invert_x", defaults.invert_x)),
            invert_y=bool(data.get("invert_y", defaults.invert_y)),
            deadzone=_float(data.get("deadzone", defaults.deadzone), 0.0, 50.0),
            smoothing=_float(data.get("smoothing", defaults.smoothing), 0.0, 0.95),
            min_threshold=_float(data.get("min_threshold", defaults.min_threshold), 0.0, 25.0),
            max_speed=_float(data.get("max_speed", defaults.max_speed), 10.0, 10000.0),
            acceleration_enabled=bool(data.get("acceleration_enabled", defaults.acceleration_enabled)),
            acceleration=_float(data.get("acceleration", defaults.acceleration), 0.0, 5.0),
            drift_filter=bool(data.get("drift_filter", defaults.drift_filter)),
            update_hz=_int(data.get("update_hz", defaults.update_hz), 30, 250),
            activation=activation,
            activation_button=str(data.get("activation_button", defaults.activation_button)),
            activation_threshold=_int(data.get("activation_threshold", defaults.activation_threshold), 0, 255),
            stick_sensitivity_x=_float(data.get("stick_sensitivity_x", defaults.stick_sensitivity_x), 0.0001, 0.25),
            stick_sensitivity_y=_float(data.get("stick_sensitivity_y", defaults.stick_sensitivity_y), 0.0001, 0.25),
            stick_deadzone=_float(data.get("stick_deadzone", defaults.stick_deadzone), 0.0, 0.95),
            stick_anti_deadzone=_float(data.get("stick_anti_deadzone", defaults.stick_anti_deadzone), 0.0, 0.95),
            response_curve=curve,
            stick_max_output=_float(data.get("stick_max_output", defaults.stick_max_output), 0.05, 1.0),
            stick_mix_mode=mix_mode,
            stick_mix=_float(data.get("stick_mix", defaults.stick_mix), 0.0, 1.0),
            flick_stick_enabled=bool(data.get("flick_stick_enabled", defaults.flick_stick_enabled)),
            flick_threshold=_float(data.get("flick_threshold", defaults.flick_threshold), 0.45, 0.98),
            flick_release_threshold=_float(data.get("flick_release_threshold", defaults.flick_release_threshold), 0.20, 0.90),
            flick_min_angle=_float(data.get("flick_min_angle", defaults.flick_min_angle), 0.0, 45.0),
            flick_pixels_per_degree=_float(data.get("flick_pixels_per_degree", defaults.flick_pixels_per_degree), 0.1, 30.0),
            flick_duration_ms=_int(data.get("flick_duration_ms", defaults.flick_duration_ms), 10, 500),
            flick_turn_180_ms=_int(data.get("flick_turn_180_ms", defaults.flick_turn_180_ms), 40, 2000),
            flick_invert_x=bool(data.get("flick_invert_x", defaults.flick_invert_x)),
            passthrough_gyro_signs=_sign_tuple(data.get("passthrough_gyro_signs", defaults.passthrough_gyro_signs)),
            passthrough_accel_signs=_sign_tuple(data.get("passthrough_accel_signs", defaults.passthrough_accel_signs)),
            passthrough_gyro_axes=_axis_tuple(data.get("passthrough_gyro_axes", defaults.passthrough_gyro_axes)),
            passthrough_accel_axes=_axis_tuple(data.get("passthrough_accel_axes", defaults.passthrough_accel_axes)),
            passthrough_deadzone=_float(data.get("passthrough_deadzone", defaults.passthrough_deadzone), 0.0, 64.0),
            mouse_to_gyro_enabled=bool(data.get("mouse_to_gyro_enabled", defaults.mouse_to_gyro_enabled)),
            mouse_to_gyro_sensitivity=_float(data.get("mouse_to_gyro_sensitivity", defaults.mouse_to_gyro_sensitivity), 0.005, 2.0),
            mouse_to_gyro_invert_x=bool(data.get("mouse_to_gyro_invert_x", defaults.mouse_to_gyro_invert_x)),
            mouse_to_gyro_invert_y=bool(data.get("mouse_to_gyro_invert_y", defaults.mouse_to_gyro_invert_y)),
            mouse_to_gyro_combine_physical=bool(data.get("mouse_to_gyro_combine_physical", defaults.mouse_to_gyro_combine_physical)),
            mouse_to_gyro_max_dps=_float(data.get("mouse_to_gyro_max_dps", defaults.mouse_to_gyro_max_dps), 100.0, 5000.0),
            calibration=GyroCalibration.from_dict(data.get("calibration", {})),
        )

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["passthrough_gyro_signs"] = list(self.passthrough_gyro_signs)
        data["passthrough_accel_signs"] = list(self.passthrough_accel_signs)
        data["passthrough_gyro_axes"] = list(self.passthrough_gyro_axes)
        data["passthrough_accel_axes"] = list(self.passthrough_accel_axes)
        return data

    def copy(self) -> "GyroConfig":
        return GyroConfig.from_dict(self.to_dict())


@dataclass
class GyroTelemetry:
    pitch: float = 0.0
    yaw: float = 0.0
    roll: float = 0.0
    accel_x: float = 0.0
    accel_y: float = 0.0
    accel_z: float = 0.0
    output_x: float = 0.0
    output_y: float = 0.0
    active: bool = False
    calibrated: bool = False
    calibrating: bool = False
    calibration_progress: float = 0.0
    calibration_error: str = ""
    mouse_to_gyro_active: bool = False
    flick_active: bool = False
    flick_angle: float = 0.0
    flick_pending: float = 0.0
    sample_hz: float = 0.0
    mode: str = "disabled"


def _float(value: Any, minimum: float, maximum: float) -> float:
    try:
        return max(minimum, min(maximum, float(value)))
    except (TypeError, ValueError, OverflowError):
        return minimum


def _int(value: Any, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError, OverflowError):
        return minimum


def _sign_tuple(value: Any) -> Tuple[int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return (1, 1, 1)
    return tuple(-1 if int(item) < 0 else 1 for item in value)  # type: ignore[return-value]


def _axis_tuple(value: Any) -> Tuple[int, int, int]:
    """Acepta solo permutaciones completas de X/Y/Z para no duplicar ejes."""
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return (0, 1, 2)
    try:
        parsed = tuple(int(item) for item in value)
    except (TypeError, ValueError, OverflowError):
        return (0, 1, 2)
    return parsed if sorted(parsed) == [0, 1, 2] else (0, 1, 2)
