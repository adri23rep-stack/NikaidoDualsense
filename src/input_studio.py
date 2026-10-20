"""Nikaido Input Studio: procesamiento de palancas por perfil.

Este modulo no modifica el estado que llega del DualSense.  Conserva una
separacion deliberada entre la lectura fisica y la salida que se enviara al
gamepad virtual, de modo que la UI pueda mostrar ambas sin falsear el valor
original ni afectar a otros subsistemas (macros, gyro o diagnosticos).
"""

from __future__ import annotations

import copy
import math
import threading
from typing import Any, Dict, List, Mapping, Optional, Tuple


STICKS = ("left", "right")
CURVES = ("linear", "exponential", "aggressive", "custom")
MAX_CUSTOM_CURVE_POINTS = 32
MAX_INPUT_PROFILES = 512
MAX_PROFILE_ID_LENGTH = 120

DEFAULT_CUSTOM_CURVE = (
    (0.0, 0.0),
    (0.25, 0.16),
    (0.50, 0.42),
    (0.75, 0.78),
    (1.0, 1.0),
)

DEFAULT_STICK_CONFIG: Dict[str, Any] = {
    "inner_deadzone": 0.08,
    "outer_deadzone": 0.00,
    "anti_deadzone": 0.00,
    "curve": "linear",
    "custom_curve": [list(point) for point in DEFAULT_CUSTOM_CURVE],
    "sensitivity_x": 1.00,
    "sensitivity_y": 1.00,
    "invert_x": False,
    "invert_y": False,
    "drift_correction": True,
    "drift_offset_x": 0.0,
    "drift_offset_y": 0.0,
}


def _clamp(value: Any, minimum: float, maximum: float, fallback: float) -> float:
    """Convierte y limita un numero aun si vino de un JSON antiguo/corrupto."""
    try:
        return max(minimum, min(maximum, float(value)))
    except (TypeError, ValueError, OverflowError):
        return fallback


def normalize_axis(value: Any) -> float:
    """Pasa un eje 0..255 a -1..1 conservando ambos extremos exactos."""
    raw = _clamp(value, 0.0, 255.0, 128.0)
    if raw >= 128.0:
        return (raw - 128.0) / 127.0
    return (raw - 128.0) / 128.0


def _clamp_vector(x: float, y: float) -> Tuple[float, float]:
    magnitude = math.hypot(x, y)
    if magnitude <= 1.0 or magnitude == 0.0:
        return x, y
    return x / magnitude, y / magnitude


class InputStudioEngine:
    """Transforma ambas palancas con configuracion independiente por perfil.

    El motor es seguro para el hilo de lectura HID y para el hilo de Tk. Las
    configuraciones devueltas siempre son copias, asi una pantalla no puede
    mutar accidentalmente el perfil activo desde fuera del lock.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._active_profile = "assault_rifle"
        self._profiles: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._telemetry: Dict[str, Dict[str, float]] = {
            stick: {"physical_x": 0.0, "physical_y": 0.0, "output_x": 0.0, "output_y": 0.0}
            for stick in STICKS
        }
        # Calibrar durante varios reportes evita guardar un micro-movimiento o
        # una lectura ruidosa como si fuera drift permanente.
        self._drift_calibrations: Dict[str, Dict[str, Any]] = {}
        self._calibration_revision = 0

    @staticmethod
    def _default_profile() -> Dict[str, Dict[str, Any]]:
        return {stick: copy.deepcopy(DEFAULT_STICK_CONFIG) for stick in STICKS}

    @classmethod
    def _sanitize_curve(cls, value: Any) -> List[List[float]]:
        """Normaliza puntos, ordena X y garantiza extremos para interpolar."""
        points: List[Tuple[float, float]] = []
        if isinstance(value, (list, tuple)):
            for point in value[:MAX_CUSTOM_CURVE_POINTS]:
                if not isinstance(point, (list, tuple)) or len(point) != 2:
                    continue
                try:
                    points.append((_clamp(point[0], 0.0, 1.0, 0.0), _clamp(point[1], 0.0, 1.0, 0.0)))
                except (TypeError, ValueError, OverflowError):
                    continue
        if len(points) < 2:
            return [list(point) for point in DEFAULT_CUSTOM_CURVE]

        points.sort(key=lambda point: point[0])
        # Una sola coordenada X debe tener un unico valor. Conservamos el
        # ultimo porque normalmente es el punto que acaba de arrastrar el UI.
        deduplicated: List[Tuple[float, float]] = []
        for point in points:
            if deduplicated and abs(deduplicated[-1][0] - point[0]) < 0.0001:
                deduplicated[-1] = point
            else:
                deduplicated.append(point)
        if deduplicated[0][0] > 0.0:
            deduplicated.insert(0, (0.0, 0.0))
        else:
            deduplicated[0] = (0.0, 0.0)
        if deduplicated[-1][0] < 1.0:
            deduplicated.append((1.0, 1.0))
        else:
            deduplicated[-1] = (1.0, 1.0)
        if len(deduplicated) > MAX_CUSTOM_CURVE_POINTS:
            deduplicated = deduplicated[: MAX_CUSTOM_CURVE_POINTS - 1] + [deduplicated[-1]]
        return [[round(x, 5), round(y, 5)] for x, y in deduplicated]

    @classmethod
    def sanitize_config(cls, data: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
        """Migra datos incompletos y elimina valores que harian inestable el filtro."""
        source = data if isinstance(data, Mapping) else {}
        config = copy.deepcopy(DEFAULT_STICK_CONFIG)
        config["inner_deadzone"] = _clamp(source.get("inner_deadzone"), 0.0, 0.95, config["inner_deadzone"])
        # Reservamos una fraccion para que inner + outer nunca divida entre 0.
        max_outer = max(0.0, 0.98 - config["inner_deadzone"])
        config["outer_deadzone"] = _clamp(source.get("outer_deadzone"), 0.0, max_outer, config["outer_deadzone"])
        config["anti_deadzone"] = _clamp(source.get("anti_deadzone"), 0.0, 0.95, config["anti_deadzone"])
        curve = str(source.get("curve", config["curve"])).lower()
        config["curve"] = curve if curve in CURVES else "linear"
        config["custom_curve"] = cls._sanitize_curve(source.get("custom_curve", config["custom_curve"]))
        config["sensitivity_x"] = _clamp(source.get("sensitivity_x"), 0.10, 3.00, config["sensitivity_x"])
        config["sensitivity_y"] = _clamp(source.get("sensitivity_y"), 0.10, 3.00, config["sensitivity_y"])
        config["invert_x"] = bool(source.get("invert_x", config["invert_x"]))
        config["invert_y"] = bool(source.get("invert_y", config["invert_y"]))
        config["drift_correction"] = bool(source.get("drift_correction", config["drift_correction"]))
        # El offset esta limitado: una calibracion defectuosa no debe poder
        # invertir por completo una palanca funcional.
        config["drift_offset_x"] = _clamp(source.get("drift_offset_x"), -0.35, 0.35, 0.0)
        config["drift_offset_y"] = _clamp(source.get("drift_offset_y"), -0.35, 0.35, 0.0)
        return config

    def load_profiles(self, data: Optional[Mapping[str, Any]]) -> None:
        """Carga sin asumir que todos los perfiles o ambas palancas existen."""
        if not isinstance(data, Mapping):
            return
        parsed: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for profile_id, profile_data in data.items():
            if len(parsed) >= MAX_INPUT_PROFILES:
                break
            if not isinstance(profile_id, str) or not isinstance(profile_data, Mapping):
                continue
            clean_id = profile_id.strip()[:MAX_PROFILE_ID_LENGTH]
            if not clean_id:
                continue
            parsed[clean_id] = {
                stick: self.sanitize_config(profile_data.get(stick)) for stick in STICKS
            }
        with self._lock:
            self._profiles = parsed

    def export_profiles(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        with self._lock:
            return copy.deepcopy(self._profiles)

    def get_profile_config(self, profile_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """Devuelve ambas palancas de un perfil como una copia segura."""
        with self._lock:
            target = str(profile_id or self._active_profile)[:MAX_PROFILE_ID_LENGTH] or "assault_rifle"
            profile = self._profiles.setdefault(target, self._default_profile())
            return copy.deepcopy(profile)

    def set_profile_config(self, profile_id: str, data: Optional[Mapping[str, Any]]) -> None:
        """Reemplaza de forma segura la configuración completa de un perfil."""
        source = data if isinstance(data, Mapping) else {}
        parsed = {stick: self.sanitize_config(source.get(stick)) for stick in STICKS}
        target = str(profile_id).strip()[:MAX_PROFILE_ID_LENGTH]
        if not target:
            raise ValueError("El ID del perfil no puede estar vacío")
        with self._lock:
            if target not in self._profiles and len(self._profiles) >= MAX_INPUT_PROFILES:
                raise ValueError(f"Input Studio admite hasta {MAX_INPUT_PROFILES} perfiles")
            self._profiles[target] = parsed

    def copy_profile(self, source_profile: str, target_profile: str) -> None:
        """Clona curvas, zonas muertas y drift al crear otro perfil."""
        self.set_profile_config(target_profile, self.get_profile_config(source_profile))

    def remove_profile(self, profile_id: str) -> bool:
        """Elimina los ajustes de Input Studio asociados a un perfil borrado."""
        with self._lock:
            if profile_id not in self._profiles:
                return False
            del self._profiles[profile_id]
            if self._active_profile == profile_id:
                self._active_profile = "assault_rifle"
            for stick, state in list(self._drift_calibrations.items()):
                if state.get("profile") == profile_id:
                    self._drift_calibrations.pop(stick, None)
            return True

    def apply_profile(self, profile_id: Optional[str]) -> None:
        with self._lock:
            target = str(profile_id or "assault_rifle")[:MAX_PROFILE_ID_LENGTH] or "assault_rifle"
            if target != self._active_profile:
                self._drift_calibrations.clear()
            self._active_profile = target
            self._profiles.setdefault(self._active_profile, self._default_profile())

    def get_active_profile(self) -> str:
        with self._lock:
            return self._active_profile

    def get_config(self, profile_id: Optional[str] = None, stick: str = "right") -> Dict[str, Any]:
        if stick not in STICKS:
            raise ValueError(f"Palanca desconocida: {stick}")
        with self._lock:
            target = str(profile_id or self._active_profile)[:MAX_PROFILE_ID_LENGTH] or "assault_rifle"
            profile = self._profiles.setdefault(target, self._default_profile())
            return copy.deepcopy(profile[stick])

    def update_config(self, profile_id: Optional[str], stick: str, **changes: Any) -> Dict[str, Any]:
        """Aplica una actualizacion atomica y devuelve la configuracion validada."""
        if stick not in STICKS:
            raise ValueError(f"Palanca desconocida: {stick}")
        with self._lock:
            target = str(profile_id or self._active_profile)[:MAX_PROFILE_ID_LENGTH] or "assault_rifle"
            profile = self._profiles.setdefault(target, self._default_profile())
            merged = dict(profile[stick])
            merged.update(changes)
            profile[stick] = self.sanitize_config(merged)
            return copy.deepcopy(profile[stick])

    def reset_stick(self, profile_id: Optional[str], stick: str) -> Dict[str, Any]:
        if stick not in STICKS:
            raise ValueError(f"Palanca desconocida: {stick}")
        with self._lock:
            target = str(profile_id or self._active_profile)[:MAX_PROFILE_ID_LENGTH] or "assault_rifle"
            profile = self._profiles.setdefault(target, self._default_profile())
            profile[stick] = copy.deepcopy(DEFAULT_STICK_CONFIG)
            self._drift_calibrations.pop(stick, None)
            return copy.deepcopy(profile[stick])

    def calibrate_drift(self, profile_id: Optional[str], stick: str, raw_x: Any, raw_y: Any) -> Dict[str, Any]:
        """Guarda el punto de reposo actual como offset de drift para una palanca."""
        return self.update_config(
            profile_id,
            stick,
            drift_offset_x=normalize_axis(raw_x),
            drift_offset_y=normalize_axis(raw_y),
        )

    def begin_drift_calibration(self, profile_id: Optional[str], stick: str, samples: int = 120) -> None:
        """Inicia una calibracion de reposo promediada en el hilo HID.

        ``process_stick`` recolecta las muestras, por lo cual no se bloquea la
        UI ni se crean hilos extra.  A 120 Hz, el valor por defecto tarda un
        segundo aproximadamente.
        """
        if stick not in STICKS:
            raise ValueError(f"Palanca desconocida: {stick}")
        target = str(profile_id or self.get_active_profile())
        count = max(12, min(600, int(samples)))
        with self._lock:
            self._drift_calibrations[stick] = {
                "profile": target,
                "samples": [],
                "target_samples": count,
                "completed": False,
                "revision": self._calibration_revision,
            }

    def get_drift_calibration(self, stick: str) -> Dict[str, Any]:
        """Estado inmutable de calibracion para dibujar progreso en la UI."""
        if stick not in STICKS:
            raise ValueError(f"Palanca desconocida: {stick}")
        with self._lock:
            state = self._drift_calibrations.get(stick)
            if not state:
                return {"active": False, "completed": False, "progress": 0.0, "revision": self._calibration_revision}
            target = max(1, int(state["target_samples"]))
            return {
                "active": not bool(state["completed"]),
                "completed": bool(state["completed"]),
                "progress": min(1.0, len(state["samples"]) / target),
                "revision": int(state["revision"]),
            }

    def _collect_drift_sample(self, stick: str, physical_x: float, physical_y: float) -> None:
        state = self._drift_calibrations.get(stick)
        if not state or state["completed"] or state["profile"] != self._active_profile:
            return
        samples = state["samples"]
        samples.append((physical_x, physical_y))
        if len(samples) < state["target_samples"]:
            return
        average_x = sum(point[0] for point in samples) / len(samples)
        average_y = sum(point[1] for point in samples) / len(samples)
        profile = self._profiles.setdefault(self._active_profile, self._default_profile())
        merged = dict(profile[stick])
        merged.update({"drift_offset_x": average_x, "drift_offset_y": average_y, "drift_correction": True})
        profile[stick] = self.sanitize_config(merged)
        self._calibration_revision += 1
        state["completed"] = True
        state["revision"] = self._calibration_revision

    @staticmethod
    def _curve_value(value: float, config: Mapping[str, Any]) -> float:
        curve = config.get("curve", "linear")
        if curve == "exponential":
            return value * value
        if curve == "aggressive":
            # Llega antes al maximo sin crear un salto en el centro.
            return math.sqrt(value)
        if curve != "custom":
            return value

        points = config.get("custom_curve", DEFAULT_CUSTOM_CURVE)
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            if value <= x1:
                if x1 <= x0:
                    return float(y1)
                factor = (value - x0) / (x1 - x0)
                return float(y0 + (y1 - y0) * factor)
        return 1.0

    @classmethod
    def transform(cls, x: float, y: float, config: Mapping[str, Any]) -> Tuple[float, float]:
        """Procesa una configuración externa, validándola antes de usarla."""
        return cls._transform_sanitized(x, y, cls.sanitize_config(config))

    @classmethod
    def _transform_sanitized(cls, x: float, y: float, cfg: Mapping[str, Any]) -> Tuple[float, float]:
        """Ruta rápida para perfiles que ya fueron saneados al cargar/editar."""
        x = _clamp(x, -1.0, 1.0, 0.0)
        y = _clamp(y, -1.0, 1.0, 0.0)
        if cfg["drift_correction"]:
            x -= cfg["drift_offset_x"]
            y -= cfg["drift_offset_y"]
        x, y = _clamp_vector(x, y)
        magnitude = math.hypot(x, y)
        if magnitude <= cfg["inner_deadzone"]:
            return 0.0, 0.0

        usable_range = max(0.02, 1.0 - cfg["inner_deadzone"] - cfg["outer_deadzone"])
        scaled = min(1.0, (magnitude - cfg["inner_deadzone"]) / usable_range)
        curved = cls._curve_value(scaled, cfg)
        curved = cfg["anti_deadzone"] + curved * (1.0 - cfg["anti_deadzone"])
        factor = min(1.0, curved) / magnitude
        output_x = x * factor * cfg["sensitivity_x"]
        output_y = y * factor * cfg["sensitivity_y"]
        if cfg["invert_x"]:
            output_x = -output_x
        if cfg["invert_y"]:
            output_y = -output_y
        output_x, output_y = _clamp_vector(output_x, output_y)
        # Evita que una calibracion perfecta deje residuos de coma flotante
        # (por ejemplo 6e-18) que se verian como movimiento en la UI o en un
        # juego que compara el centro de la palanca de forma exacta.
        if abs(output_x) < 1e-12:
            output_x = 0.0
        if abs(output_y) < 1e-12:
            output_y = 0.0
        return output_x, output_y

    def process_stick(self, stick: str, raw_x: Any, raw_y: Any) -> Tuple[float, float]:
        """Procesa y conserva telemetria de una lectura HID; se llama a 120 Hz."""
        if stick not in STICKS:
            raise ValueError(f"Palanca desconocida: {stick}")
        physical_x, physical_y = normalize_axis(raw_x), normalize_axis(raw_y)
        with self._lock:
            profile = self._profiles.get(self._active_profile)
            if profile is None:
                profile = self._default_profile()
                self._profiles[self._active_profile] = profile
            self._collect_drift_sample(stick, physical_x, physical_y)
            output_x, output_y = self._transform_sanitized(
                physical_x, physical_y, profile[stick]
            )
            self._telemetry[stick] = {
                "physical_x": physical_x,
                "physical_y": physical_y,
                "output_x": output_x,
                "output_y": output_y,
            }
            return output_x, output_y

    def get_telemetry(self, stick: str) -> Dict[str, float]:
        if stick not in STICKS:
            raise ValueError(f"Palanca desconocida: {stick}")
        with self._lock:
            return dict(self._telemetry[stick])
