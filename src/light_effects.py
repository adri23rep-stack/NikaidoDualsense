"""Motor de efectos RGB para la barra de luz del DualSense.

El hardware del DualSense expone un color RGB global para su barra de luz. Por
eso los efectos se representan como cambios de color y brillo a lo largo del
tiempo, no como zonas independientes. La interfaz puede dibujar una vista previa
más rica, pero el color enviado al control siempre respeta esa limitación real.

El módulo no depende de Qt. Mantiene un solo hilo de animación, permite compartir
la misma función de muestreo con la interfaz y cuenta con medición opcional del
audio de salida de Windows para el efecto reactivo.
"""

from __future__ import annotations

import colorsys
import copy
import logging
import math
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Tuple

logger = logging.getLogger(__name__)

RGB = Tuple[int, int, int]
AudioLevelProvider = Callable[[], float]


@dataclass(frozen=True)
class LightEffectSpec:
    effect_id: str
    name: str
    description: str
    category: str
    animated: bool = True
    supports_direction: bool = True
    audio_reactive: bool = False
    default_speed: float = 1.0


@dataclass(frozen=True)
class LightEffectSample:
    """Resultado completo de un instante de animación.

    ``color`` es lo que se manda al control físico. ``segments`` son colores de
    apoyo para la vista previa visual de la interfaz y nunca implican que el
    hardware tenga zonas RGB independientes.
    """

    color: RGB
    segments: Tuple[RGB, ...]
    progress: float
    level: float
    mix: float
    audio_level: float = 0.0


EFFECT_SPECS: Dict[str, LightEffectSpec] = {
    "static": LightEffectSpec(
        "static",
        "Color fijo",
        "Mantiene el color principal sin animación.",
        "Básicos",
        animated=False,
        supports_direction=False,
    ),
    "breathe": LightEffectSpec(
        "breathe",
        "Respiración",
        "Sube y baja el brillo con una transición suave.",
        "Básicos",
        default_speed=0.7,
    ),
    "pulse": LightEffectSpec(
        "pulse",
        "Pulso",
        "Destello corto con caída progresiva.",
        "Básicos",
        default_speed=1.2,
    ),
    "rainbow": LightEffectSpec(
        "rainbow",
        "RGB arcoíris",
        "Recorre el espectro RGB completo de forma continua.",
        "Animados",
        default_speed=0.45,
    ),
    "wave": LightEffectSpec(
        "wave",
        "Ola neón",
        "Viaja entre el color principal y el secundario.",
        "Animados",
        default_speed=0.8,
    ),
    "comet": LightEffectSpec(
        "comet",
        "Cometa",
        "Un destello brillante aparece, deja una cola y desaparece.",
        "Animados",
        default_speed=0.9,
    ),
    "heartbeat": LightEffectSpec(
        "heartbeat",
        "Latido",
        "Doble pulso inspirado en un latido.",
        "Animados",
        default_speed=0.9,
    ),
    "aurora": LightEffectSpec(
        "aurora",
        "Aurora",
        "Mezcla lenta y orgánica de varios tonos neón.",
        "Animados",
        default_speed=0.35,
    ),
    "plasma": LightEffectSpec(
        "plasma",
        "Plasma",
        "Movimiento energético con cambios de color más intensos.",
        "Animados",
        default_speed=0.75,
    ),
    "fire": LightEffectSpec(
        "fire",
        "Fuego",
        "Parpadeo cálido entre rojo, naranja y amarillo.",
        "Temáticos",
        default_speed=1.25,
    ),
    "ice": LightEffectSpec(
        "ice",
        "Hielo",
        "Brillo frío entre azul, cyan y blanco.",
        "Temáticos",
        default_speed=0.65,
    ),
    "police": LightEffectSpec(
        "police",
        "Alerta roja y azul",
        "Alterna rojo y azul con pausas breves.",
        "Temáticos",
        default_speed=1.0,
    ),
    "audio": LightEffectSpec(
        "audio",
        "Audio reactivo",
        "El brillo y el color reaccionan al nivel de audio de salida de Windows.",
        "Reactivos",
        supports_direction=False,
        audio_reactive=True,
        default_speed=1.0,
    ),
    "custom": LightEffectSpec(
        "custom",
        "Animación personalizada",
        "Recorre una paleta creada por el usuario.",
        "Personalizados",
        default_speed=1.0,
    ),
}

EFFECT_NAMES = {effect_id: spec.name for effect_id, spec in EFFECT_SPECS.items()}

LIGHT_CONTROL_MODES: Dict[str, str] = {
    "nikaido": "Prioridad Nikaido",
    "balanced": "Equilibrio",
    "game": "Prioridad del juego",
}

LIGHT_KEEPALIVE_SECONDS = 0.75


DEFAULT_LIGHT_CONFIG: Dict[str, Any] = {
    "effect": "static",
    "color": [0, 100, 255],
    "secondary_color": [198, 63, 244],
    "speed": 1.0,
    "brightness": 1.0,
    "intensity": 1.0,
    "direction": 1,
    "smoothing": 0.18,
    "audio_gain": 1.6,
    "audio_floor": 0.03,
    "palette": [],
    "custom_id": "",
}

_HEX_COLOR = re.compile(r"^#?([0-9a-fA-F]{6})$")
MAX_CUSTOM_LIGHT_EFFECTS = 256


def _clamp_number(value: Any, minimum: float, maximum: float, fallback: float) -> float:
    try:
        number = float(value)
        if not math.isfinite(number):
            return fallback
        return max(minimum, min(maximum, number))
    except (TypeError, ValueError, OverflowError):
        return fallback


def _sanitize_color(value: Any, fallback: Iterable[int]) -> list[int]:
    if isinstance(value, str):
        match = _HEX_COLOR.match(value.strip())
        if match:
            raw = match.group(1)
            return [int(raw[i : i + 2], 16) for i in (0, 2, 4)]
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            return [max(0, min(255, int(value[index]))) for index in range(3)]
        except (TypeError, ValueError, OverflowError):
            pass
    return [max(0, min(255, int(channel))) for channel in fallback]


def parse_palette(value: Any) -> list[list[int]]:
    """Acepta una lista RGB o texto ``#ff0000, #00ff00``."""
    source: list[Any]
    if isinstance(value, str):
        source = [part.strip() for part in value.split(",") if part.strip()]
    elif isinstance(value, (list, tuple)):
        source = list(value)
    else:
        source = []
    colors: list[list[int]] = []
    for item in source:
        color: Optional[list[int]] = None
        if isinstance(item, str):
            match = _HEX_COLOR.match(item.strip())
            if match:
                raw = match.group(1)
                color = [int(raw[i : i + 2], 16) for i in (0, 2, 4)]
        elif isinstance(item, (list, tuple)) and len(item) >= 3:
            try:
                color = [max(0, min(255, int(item[index]))) for index in range(3)]
            except (TypeError, ValueError, OverflowError):
                color = None
        if color is not None and color not in colors:
            colors.append(color)
    return colors[:24]


def color_to_hex(color: Iterable[int]) -> str:
    rgb = _sanitize_color(list(color), (0, 0, 0))
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _mix(a: Iterable[int], b: Iterable[int], amount: float) -> RGB:
    amount = max(0.0, min(1.0, float(amount)))
    left = list(a)
    right = list(b)
    mixed = [
        int(round(left[index] + (right[index] - left[index]) * amount))
        for index in range(3)
    ]
    return mixed[0], mixed[1], mixed[2]


def _scale(color: Iterable[int], amount: float) -> RGB:
    amount = max(0.0, min(1.0, float(amount)))
    scaled = [max(0, min(255, int(round(channel * amount)))) for channel in color]
    return scaled[0], scaled[1], scaled[2]


def _palette_color(palette: list[list[int]], progress: float) -> RGB:
    if not palette:
        return 0, 100, 255
    if len(palette) == 1:
        return palette[0][0], palette[0][1], palette[0][2]
    progress %= 1.0
    scaled = progress * len(palette)
    index = int(scaled) % len(palette)
    nxt = (index + 1) % len(palette)
    return _mix(palette[index], palette[nxt], scaled - int(scaled))


def _gaussian(value: float, center: float, width: float) -> float:
    distance = (value - center) / max(0.0001, width)
    return math.exp(-(distance * distance) * 0.5)


def _noise(progress: float) -> float:
    """Ruido determinista suave, sin estado global ni generador aleatorio."""
    value = (
        math.sin(progress * math.tau * 3.0)
        + 0.55 * math.sin(progress * math.tau * 7.0 + 1.37)
        + 0.28 * math.sin(progress * math.tau * 13.0 + 0.42)
    )
    return max(0.0, min(1.0, 0.5 + value / 3.66))


def sanitize_light_config(data: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    source = data if isinstance(data, Mapping) else {}
    config = copy.deepcopy(DEFAULT_LIGHT_CONFIG)
    effect = str(source.get("effect", config["effect"]) or "static").lower()
    config["effect"] = effect if effect in EFFECT_SPECS else "static"
    config["color"] = _sanitize_color(source.get("color"), config["color"])
    config["secondary_color"] = _sanitize_color(
        source.get("secondary_color"), config["secondary_color"]
    )
    config["speed"] = _clamp_number(source.get("speed"), 0.1, 8.0, 1.0)
    config["brightness"] = _clamp_number(source.get("brightness"), 0.02, 1.0, 1.0)
    config["intensity"] = _clamp_number(source.get("intensity"), 0.0, 1.0, 1.0)
    try:
        config["direction"] = -1 if int(float(source.get("direction", 1))) < 0 else 1
    except (TypeError, ValueError, OverflowError):
        config["direction"] = 1
    config["smoothing"] = _clamp_number(source.get("smoothing"), 0.0, 0.95, 0.18)
    config["audio_gain"] = _clamp_number(source.get("audio_gain"), 0.25, 5.0, 1.6)
    config["audio_floor"] = _clamp_number(source.get("audio_floor"), 0.0, 0.35, 0.03)
    config["palette"] = parse_palette(source.get("palette"))
    config["custom_id"] = str(source.get("custom_id", "") or "")[:120]
    return config


def sample_light_effect(
    data: Optional[Mapping[str, Any]],
    elapsed: float,
    *,
    custom_effects: Optional[Mapping[str, Mapping[str, Any]]] = None,
    audio_level: float = 0.0,
    segment_count: int = 7,
) -> LightEffectSample:
    """Muestrea cualquier efecto sin tocar hardware.

    Esta función es la fuente única para el motor físico y la vista previa Qt.
    Así no existen dos implementaciones visuales que se comporten distinto.
    """

    config = sanitize_light_config(data)
    effect = str(config["effect"])
    speed = float(config["speed"])
    brightness = float(config["brightness"])
    intensity = float(config["intensity"])
    direction = int(config["direction"])
    primary = config["color"]
    secondary = config["secondary_color"]
    palette = parse_palette(config.get("palette"))
    progress = (max(0.0, float(elapsed)) * speed) % 1.0
    if direction < 0 and EFFECT_SPECS.get(effect, EFFECT_SPECS["static"]).supports_direction:
        progress = (1.0 - progress) % 1.0

    level = 1.0
    mix = 0.0
    raw_color: RGB = tuple(primary[:3])  # type: ignore[assignment]
    requested_segments = max(3, min(15, int(segment_count)))

    if effect == "rainbow":
        r, g, b = colorsys.hsv_to_rgb(progress, 1.0, 1.0)
        raw_color = int(r * 255), int(g * 255), int(b * 255)
        segments = tuple(
            tuple(int(channel * 255) for channel in colorsys.hsv_to_rgb((progress + index / requested_segments) % 1.0, 1.0, 1.0))
            for index in range(requested_segments)
        )
    elif effect == "wave":
        # Seno en lugar de coseno: invertir la dirección también cambia el
        # color global en ese instante, no solo el orden visual de segmentos.
        mix = 0.5 + 0.5 * math.sin(progress * math.tau)
        raw_color = _mix(primary, secondary, mix)
        segments = tuple(
            _mix(
                primary,
                secondary,
                0.5 + 0.5 * math.sin(
                    (progress + index / max(1, requested_segments - 1)) * math.tau
                ),
            )
            for index in range(requested_segments)
        )
    elif effect == "breathe":
        level = 0.10 + 0.90 * (0.5 - 0.5 * math.cos(progress * math.tau))
        raw_color = tuple(primary[:3])  # type: ignore[assignment]
        segments = tuple(_mix(primary, secondary, index / max(1, requested_segments - 1) * 0.18) for index in range(requested_segments))
    elif effect == "pulse":
        level = 0.08 + 0.92 * math.exp(-progress * 5.4)
        mix = min(1.0, progress * 1.5)
        raw_color = _mix(primary, secondary, mix * 0.55)
        segments = tuple(_mix(primary, secondary, max(0.0, 1.0 - index / requested_segments - progress) * 0.8) for index in range(requested_segments))
    elif effect == "comet":
        head = progress * (requested_segments + 2) - 1.0
        segment_values: list[RGB] = []
        head_level = 0.0
        for index in range(requested_segments):
            distance = head - index
            trail = 1.0 if -0.35 <= distance <= 0.35 else max(0.0, 1.0 - abs(distance) / 3.2)
            trail *= 1.0 if distance >= -0.35 else 0.22
            if trail > head_level:
                head_level = trail
            segment_values.append(_scale(_mix(primary, secondary, index / max(1, requested_segments - 1)), 0.20 + 0.80 * trail))
        level = max(0.12, head_level)
        mix = progress
        raw_color = _mix(primary, secondary, progress)
        segments = tuple(segment_values)
    elif effect == "heartbeat":
        first = _gaussian(progress, 0.10, 0.035)
        second = _gaussian(progress, 0.27, 0.052)
        level = max(0.10, min(1.0, 0.10 + 0.95 * first + 0.72 * second))
        mix = min(1.0, second * 0.5)
        raw_color = _mix(primary, secondary, mix)
        segments = tuple(_scale(_mix(primary, secondary, index / max(1, requested_segments - 1) * 0.35), level) for index in range(requested_segments))
    elif effect == "aurora":
        aurora_palette = palette or [secondary, [43, 215, 239], primary, [255, 77, 214]]
        color_progress = (progress + 0.08 * math.sin(progress * math.tau * 2.0)) % 1.0
        raw_color = _palette_color(aurora_palette, color_progress)
        level = 0.55 + 0.45 * (0.5 - 0.5 * math.cos(progress * math.tau * 1.5))
        mix = color_progress
        segments = tuple(_palette_color(aurora_palette, (color_progress + index / requested_segments * 0.42) % 1.0) for index in range(requested_segments))
    elif effect == "plasma":
        plasma = 0.5 + 0.25 * math.sin(progress * math.tau * 2.0) + 0.25 * math.sin(progress * math.tau * 5.0 + 1.2)
        plasma %= 1.0
        if palette:
            raw_color = _palette_color(palette, plasma)
        else:
            hue = (0.72 + plasma * 0.42) % 1.0
            rgb = colorsys.hsv_to_rgb(hue, 0.88, 1.0)
            raw_color = tuple(int(channel * 255) for channel in rgb)  # type: ignore[assignment]
        level = 0.55 + 0.45 * _noise(progress)
        mix = plasma
        segments = tuple(_mix(raw_color, _mix(primary, secondary, index / max(1, requested_segments - 1)), 0.38) for index in range(requested_segments))
    elif effect == "fire":
        fire_palette = palette or [[120, 0, 0], [255, 40, 0], [255, 130, 0], [255, 220, 70]]
        flicker = _noise(progress)
        level = 0.38 + 0.62 * flicker
        mix = flicker
        raw_color = _palette_color(fire_palette, 0.18 + flicker * 0.75)
        segments = tuple(_palette_color(fire_palette, (flicker + index * 0.11 + _noise(progress + index * 0.07) * 0.16) % 1.0) for index in range(requested_segments))
    elif effect == "ice":
        ice_palette = palette or [[20, 80, 255], [40, 210, 255], [210, 250, 255], [110, 160, 255]]
        shimmer = 0.5 - 0.5 * math.cos(progress * math.tau * 2.0)
        sparkle = _gaussian(progress, 0.18, 0.045) + _gaussian(progress, 0.63, 0.035)
        level = min(1.0, 0.48 + 0.32 * shimmer + 0.38 * sparkle)
        mix = shimmer
        raw_color = _palette_color(ice_palette, (progress * 0.65 + shimmer * 0.25) % 1.0)
        segments = tuple(_palette_color(ice_palette, (progress + index / requested_segments * 0.45) % 1.0) for index in range(requested_segments))
    elif effect == "police":
        phase = progress * 8.0
        slot = int(phase) % 8
        flash = phase - int(phase)
        red = (255, 16, 32)
        blue = (20, 80, 255)
        if slot in {0, 1}:
            raw_color = red
            level = 1.0 if flash < 0.62 else 0.12
            mix = 0.0
        elif slot in {4, 5}:
            raw_color = blue
            level = 1.0 if flash < 0.62 else 0.12
            mix = 1.0
        else:
            raw_color = _mix(red, blue, 0.5)
            level = 0.08
            mix = 0.5
        segments = tuple(red if index < requested_segments / 2 else blue for index in range(requested_segments))
    elif effect == "audio":
        measured = max(0.0, min(1.0, float(audio_level)))
        gain = float(config.get("audio_gain", 1.6))
        floor = float(config.get("audio_floor", 0.03))
        reactive = max(floor, min(1.0, measured * gain))
        level = max(0.04, reactive)
        mix = max(0.0, min(1.0, reactive))
        raw_color = _mix(primary, secondary, mix)
        bars = []
        for index in range(requested_segments):
            pseudo = 0.58 + 0.42 * math.sin(progress * math.tau * (1.2 + index * 0.17) + index * 0.81)
            bar_level = max(0.12, min(1.0, reactive * (0.70 + 0.55 * pseudo)))
            bars.append(_scale(_mix(primary, secondary, index / max(1, requested_segments - 1)), bar_level))
        segments = tuple(bars)
    elif effect == "custom":
        source = custom_effects if isinstance(custom_effects, Mapping) else {}
        custom = source.get(str(config.get("custom_id", "")), {})
        custom_palette = parse_palette(custom.get("palette")) or palette or [primary, secondary]
        custom_speed = _clamp_number(custom.get("speed"), 0.1, 8.0, speed)
        custom_progress = (max(0.0, float(elapsed)) * custom_speed) % 1.0
        if direction < 0:
            custom_progress = (1.0 - custom_progress) % 1.0
        raw_color = _palette_color(custom_palette, custom_progress)
        mix = custom_progress
        segments = tuple(_palette_color(custom_palette, (custom_progress + index / requested_segments) % 1.0) for index in range(requested_segments))
    else:
        segments = tuple(tuple(primary[:3]) for _ in range(requested_segments))  # type: ignore[arg-type]

    modulation = (1.0 - intensity) + intensity * max(0.0, min(1.0, level))
    output_color = _scale(raw_color, brightness * modulation)
    scaled_segments = tuple(_scale(color, brightness * ((1.0 - intensity) + intensity * 1.0)) for color in segments)
    return LightEffectSample(
        color=output_color,
        segments=scaled_segments,
        progress=progress,
        level=max(0.0, min(1.0, modulation)),
        mix=max(0.0, min(1.0, mix)),
        audio_level=max(0.0, min(1.0, float(audio_level))),
    )


class WindowsAudioLevelMeter:
    """Medidor opcional de la salida predeterminada de Windows mediante pycaw.

    Se inicializa y se destruye en el mismo hilo que lo usa. Cualquier fallo se
    vuelve estado de disponibilidad y nunca tumba la animación ni el programa.
    """

    RETRY_SECONDS = 5.0

    def __init__(self) -> None:
        self._meter: Any = None
        self._comtypes: Any = None
        self._initialized = False
        self._next_retry = 0.0
        self._error = ""

    @property
    def available(self) -> bool:
        return self._meter is not None

    @property
    def error(self) -> str:
        return self._error

    def _initialize(self) -> None:
        if os.name != "nt":
            self._error = "El audio reactivo real solo está disponible en Windows"
            self._next_retry = time.monotonic() + 60.0
            return
        try:
            import comtypes
            from comtypes import CLSCTX_ALL, POINTER, cast
            from pycaw.pycaw import AudioUtilities, IAudioMeterInformation

            comtypes.CoInitialize()
            self._comtypes = comtypes
            device = AudioUtilities.GetSpeakers()
            meter = None
            try:
                meter = getattr(device, "AudioMeterInformation", None)
            except Exception:
                meter = None
            if meter is None:
                raw_device = getattr(device, "_dev", device)
                interface = raw_device.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None)
                meter = cast(interface, POINTER(IAudioMeterInformation))
            if meter is None or not callable(getattr(meter, "GetPeakValue", None)):
                raise RuntimeError("Windows no devolvió un medidor de nivel compatible")
            self._meter = meter
            self._initialized = True
            self._error = ""
        except Exception as exc:
            self._error = str(exc) or exc.__class__.__name__
            self._next_retry = time.monotonic() + self.RETRY_SECONDS
            self.shutdown()

    def read(self) -> float:
        if self._meter is None and time.monotonic() >= self._next_retry:
            self._initialize()
        if self._meter is None:
            return 0.0
        try:
            value = float(self._meter.GetPeakValue())
            if not math.isfinite(value):
                return 0.0
            return max(0.0, min(1.0, value))
        except Exception as exc:
            self._error = str(exc) or exc.__class__.__name__
            self._next_retry = time.monotonic() + self.RETRY_SECONDS
            self.shutdown()
            return 0.0

    def shutdown(self) -> None:
        self._meter = None
        comtypes_module = self._comtypes
        self._comtypes = None
        if comtypes_module is not None:
            try:
                comtypes_module.CoUninitialize()
            except Exception:
                pass
        self._initialized = False


class LightEffectEngine:
    """Genera colores animados y los manda al ``ConnectionManager``."""

    def __init__(
        self,
        connection_manager=None,
        fps: int = 30,
        audio_level_provider: Optional[AudioLevelProvider] = None,
    ) -> None:
        self.connection_manager = connection_manager
        self.fps = max(10, min(60, int(fps)))
        self._external_audio_level_provider = audio_level_provider
        self._lock = threading.RLock()
        self._lifecycle_lock = threading.RLock()
        self._stop_event = threading.Event()
        self._config = copy.deepcopy(DEFAULT_LIGHT_CONFIG)
        self._custom_effects: Dict[str, Dict[str, Any]] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._started_at = time.monotonic()
        self._last_color: Optional[RGB] = None
        self._last_send_at = 0.0
        self._control_mode = "nikaido"
        self._smoothed_color: Optional[Tuple[float, float, float]] = None
        self._last_audio_level = 0.0
        self._audio_available = False
        self._audio_error = ""

    @classmethod
    def sanitize_config(cls, data: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
        return sanitize_light_config(data)

    def set_connection_manager(self, connection_manager) -> None:
        with self._lock:
            self.connection_manager = connection_manager

    def set_audio_level_provider(self, provider: Optional[AudioLevelProvider]) -> None:
        with self._lock:
            self._external_audio_level_provider = provider
            self._last_audio_level = 0.0
            self._audio_available = bool(provider)
            self._audio_error = ""

    @staticmethod
    def sanitize_control_mode(value: Any) -> str:
        mode = str(value or "nikaido").strip().lower()
        return mode if mode in LIGHT_CONTROL_MODES else "nikaido"

    def get_control_mode(self) -> str:
        with self._lock:
            return self._control_mode

    def set_control_mode(self, mode: Any) -> str:
        """Define quién tiene prioridad sobre la barra RGB.

        ``nikaido`` mantiene la salida incluso para colores fijos; ``balanced``
        conserva el comportamiento de una sola escritura para colores fijos; y
        ``game`` detiene por completo las órdenes RGB de Nikaido.
        """
        parsed = self.sanitize_control_mode(mode)
        with self._lock:
            changed = parsed != self._control_mode
            self._control_mode = parsed
            self._last_color = None
            self._last_send_at = 0.0
            config = copy.deepcopy(self._config)
        if changed:
            self.apply_config(config)
        return parsed

    @staticmethod
    def sanitize_custom_effects(
        data: Optional[Mapping[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        parsed: Dict[str, Dict[str, Any]] = {}
        if isinstance(data, Mapping):
            for effect_id, payload in data.items():
                if len(parsed) >= MAX_CUSTOM_LIGHT_EFFECTS:
                    break
                if not isinstance(effect_id, str) or not isinstance(payload, Mapping):
                    continue
                effect_id = effect_id.strip()[:120]
                if not effect_id:
                    continue
                palette = parse_palette(payload.get("palette"))
                if len(palette) < 2:
                    continue
                parsed[effect_id] = {
                    "name": str(payload.get("name", "Animación personalizada"))[:60],
                    "palette": palette,
                    "speed": _clamp_number(payload.get("speed"), 0.1, 8.0, 1.0),
                }
        return parsed

    def load_custom_effects(self, data: Optional[Mapping[str, Any]]) -> None:
        parsed = self.sanitize_custom_effects(data)
        with self._lock:
            self._custom_effects = parsed

    def export_custom_effects(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self._custom_effects)

    def get_custom_effects(self) -> Dict[str, Dict[str, Any]]:
        return self.export_custom_effects()

    def register_custom_effect(
        self, name: str, palette: Any, speed: float = 1.0, effect_id: str = ""
    ) -> str:
        colors = parse_palette(palette)
        if len(colors) < 2:
            raise ValueError("La animación necesita por lo menos dos colores")
        key = effect_id.strip()[:120] or f"custom_{uuid.uuid4().hex[:8]}"
        with self._lock:
            if key not in self._custom_effects and len(self._custom_effects) >= MAX_CUSTOM_LIGHT_EFFECTS:
                raise ValueError(f"Solo se permiten {MAX_CUSTOM_LIGHT_EFFECTS} animaciones personalizadas")
            self._custom_effects[key] = {
                "name": (name.strip() or "Animación personalizada")[:60],
                "palette": colors,
                "speed": _clamp_number(speed, 0.1, 8.0, 1.0),
            }
        return key

    def remove_custom_effect(self, effect_id: str) -> bool:
        with self._lock:
            if effect_id not in self._custom_effects:
                return False
            del self._custom_effects[effect_id]
            if self._config.get("custom_id") == effect_id:
                self._config["custom_id"] = ""
            return True

    def available_effects(self) -> list[tuple[str, str]]:
        with self._lock:
            result = [(effect_id, spec.name) for effect_id, spec in EFFECT_SPECS.items()]
            result.extend(
                (f"custom:{effect_id}", payload["name"])
                for effect_id, payload in sorted(
                    self._custom_effects.items(), key=lambda item: item[1]["name"].lower()
                )
            )
            return result

    def get_config(self) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._config)

    def get_audio_level(self) -> float:
        with self._lock:
            return float(self._last_audio_level)

    def get_audio_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "available": bool(self._audio_available),
                "level": float(self._last_audio_level),
                "error": str(self._audio_error or ""),
            }

    def preview_sample(
        self,
        data: Optional[Mapping[str, Any]],
        elapsed: float,
        *,
        audio_level: Optional[float] = None,
        segment_count: int = 7,
    ) -> LightEffectSample:
        with self._lock:
            custom_effects = copy.deepcopy(self._custom_effects)
            current_audio = self._last_audio_level
        return sample_light_effect(
            data,
            elapsed,
            custom_effects=custom_effects,
            audio_level=current_audio if audio_level is None else audio_level,
            segment_count=segment_count,
        )

    def apply_config(self, data: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
        config = self.sanitize_config(data)
        effect = (
            str((data or {}).get("effect", config["effect"]))
            if isinstance(data, Mapping)
            else config["effect"]
        )
        if effect.startswith("custom:"):
            config["effect"] = "custom"
            config["custom_id"] = effect.split(":", 1)[1]
        with self._lock:
            self._config = config
            self._started_at = time.monotonic()
            self._last_color = None
            self._last_send_at = 0.0
            self._smoothed_color = None
            control_mode = self._control_mode
            animated = bool(EFFECT_SPECS.get(config["effect"], EFFECT_SPECS["static"]).animated)
        if control_mode == "game":
            self.stop(join=True)
        elif animated or control_mode == "nikaido":
            # En prioridad Nikaido también se mantiene vivo un color fijo para
            # recuperarlo si un juego escribe azul/rojo en el mismo control.
            self.start()
            if not animated:
                sample = sample_light_effect(config, 0.0)
                self._send_color(sample.color, force=True)
        else:
            self.stop(join=True)
            sample = sample_light_effect(config, 0.0)
            self._send_color(sample.color, force=True)
        return copy.deepcopy(config)

    def preview_config(self, data: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
        return self.apply_config(data)

    def start(self) -> None:
        with self._lifecycle_lock:
            with self._lock:
                if self._running or (self._thread and self._thread.is_alive()):
                    return
                stop_event = threading.Event()
                self._stop_event = stop_event
                self._running = True
                self._thread = threading.Thread(
                    target=self._loop,
                    args=(stop_event,),
                    name="DualSenseLightEffects",
                    daemon=True,
                )
                thread = self._thread
            thread.start()

    def stop(self, join: bool = True) -> None:
        with self._lifecycle_lock:
            with self._lock:
                self._running = False
                stop_event = self._stop_event
                stop_event.set()
                thread = self._thread
            if join and thread and thread is not threading.current_thread() and thread.is_alive():
                thread.join(timeout=0.55)
            with self._lock:
                if self._thread is thread and (thread is None or not thread.is_alive()):
                    self._thread = None

    def _read_audio_level(self, meter: WindowsAudioLevelMeter) -> float:
        with self._lock:
            provider = self._external_audio_level_provider
            previous = self._last_audio_level
        if provider is not None:
            try:
                target = max(0.0, min(1.0, float(provider())))
                available = True
                error = ""
            except Exception as exc:
                target = 0.0
                available = False
                error = str(exc) or exc.__class__.__name__
        else:
            target = meter.read()
            available = meter.available
            error = meter.error
        coefficient = 0.62 if target >= previous else 0.18
        smoothed = previous + (target - previous) * coefficient
        with self._lock:
            self._last_audio_level = smoothed
            self._audio_available = available
            self._audio_error = error
        return smoothed

    def _loop(self, stop_event: Optional[threading.Event] = None) -> None:
        normal_interval = 1.0 / self.fps
        stop_event = stop_event or self._stop_event
        meter = WindowsAudioLevelMeter()
        try:
            while not stop_event.is_set():
                with self._lock:
                    if not self._running or stop_event is not self._stop_event:
                        return
                    config = copy.deepcopy(self._config)
                    custom_effects = copy.deepcopy(self._custom_effects)
                    started_at = self._started_at
                    control_mode = self._control_mode
                if control_mode == "game":
                    return
                spec = EFFECT_SPECS.get(config["effect"], EFFECT_SPECS["static"])
                interval = normal_interval if spec.animated else LIGHT_KEEPALIVE_SECONDS
                try:
                    if config["effect"] == "audio":
                        audio_level = self._read_audio_level(meter)
                    else:
                        audio_level = 0.0
                        if meter.available:
                            meter.shutdown()
                        with self._lock:
                            self._last_audio_level = 0.0
                            self._audio_available = bool(self._external_audio_level_provider)
                            self._audio_error = ""
                    elapsed = time.monotonic() - started_at
                    sample = sample_light_effect(
                        config,
                        elapsed,
                        custom_effects=custom_effects,
                        audio_level=audio_level,
                    )
                    self._send_color(
                        self._smooth_color(sample.color, float(config["smoothing"])),
                        force=not spec.animated and control_mode == "nikaido",
                    )
                except Exception as exc:  # pragma: no cover - protección para hardware
                    logger.debug("Fallo animando luces: %s", exc)
                stop_event.wait(interval)
        finally:
            meter.shutdown()
            with self._lock:
                self._audio_available = bool(self._external_audio_level_provider)
                if not self._audio_available:
                    self._last_audio_level = 0.0

    def _smooth_color(self, color: RGB, smoothing: float) -> RGB:
        smoothing = max(0.0, min(0.95, smoothing))
        with self._lock:
            previous = self._smoothed_color
            if previous is None or smoothing <= 0.001:
                current = float(color[0]), float(color[1]), float(color[2])
            else:
                responsiveness = max(0.05, 1.0 - smoothing)
                current = tuple(
                    previous[index] + (float(color[index]) - previous[index]) * responsiveness
                    for index in range(3)
                )
            self._smoothed_color = current
        return tuple(max(0, min(255, int(round(channel)))) for channel in current)  # type: ignore[return-value]

    @staticmethod
    def _mix(a: Iterable[int], b: Iterable[int], amount: float) -> RGB:
        return _mix(a, b, amount)

    @staticmethod
    def _scale(color: Iterable[int], amount: float) -> RGB:
        return _scale(color, amount)

    def _palette_color(self, palette: list[list[int]], progress: float) -> RGB:
        return _palette_color(palette, progress)

    def _color_at(
        self,
        config: Mapping[str, Any],
        custom_effects: Mapping[str, Mapping[str, Any]],
        elapsed: float,
    ) -> RGB:
        """Compatibilidad con pruebas y código previo."""
        return sample_light_effect(config, elapsed, custom_effects=custom_effects).color

    def _send_color(self, color: RGB, *, force: bool = False) -> None:
        normalized = _sanitize_color(color, (0, 0, 0))
        safe_color: RGB = normalized[0], normalized[1], normalized[2]
        now = time.monotonic()
        with self._lock:
            if self._control_mode == "game":
                return
            if (
                not force
                and safe_color == self._last_color
                and (now - self._last_send_at) < LIGHT_KEEPALIVE_SECONDS
            ):
                return
            manager = self.connection_manager
        if manager:
            result = manager.set_led_color(*safe_color)
            # Gestores antiguos no devolvían valor; solo ``False`` significa
            # fallo explícito. Así una desconexión temporal sí se vuelve a intentar.
            if result is not False:
                with self._lock:
                    self._last_color = safe_color
                    self._last_send_at = now

    def shutdown(self) -> None:
        self.stop(join=True)
