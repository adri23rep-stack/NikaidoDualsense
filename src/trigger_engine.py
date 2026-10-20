"""
Motor de Gatillos DualSense
Sistema de efectos hapticos en tiempo real para los gatillos L2/R2.
Soporta modos estaticos, animaciones en tiempo real y perfiles de armas.
"""

import copy
import logging
import time
import threading
import math
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, List, Any, Set

from .advanced_mapping import sanitize_config as sanitize_mapping_config
from .audio_manager import sanitize_audio_config
from .gyro_config import GyroConfig
from .input_studio import InputStudioEngine, STICKS
from .light_effects import LightEffectEngine
from .hid_backend import ensure_hidapi_backend
from .profile_catalog import (
    BUILTIN_PROFILE_SPECS,
    RESERVED_PROFILE_IDS,
    canonical_profile_id,
    clone_spec_payload,
)

ensure_hidapi_backend()
try:
    from pydualsense import TriggerModes

    PYDUALSENSE_AVAILABLE = True
except Exception:
    PYDUALSENSE_AVAILABLE = False

    # Definir TriggerModes para modo simulacion
    class TriggerModes:
        Off = 0x00
        Rigid = 0x01
        Pulse = 0x02
        Rigid_A = 0x21
        Rigid_B = 0x05
        Rigid_AB = 0x25
        Pulse_A = 0x22
        Pulse_B = 0x06
        Pulse_AB = 0x26
        Calibration = 0xFC


logger = logging.getLogger(__name__)

MAX_CUSTOM_TRIGGER_PROFILES = 512
MAX_TRIGGER_SECTIONS = 10
MAX_PROFILE_ID_LENGTH = 120


def _bounded_int(value: Any, minimum: int, maximum: int, fallback: int) -> int:
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError, OverflowError):
        return fallback


def _bounded_float(value: Any, minimum: float, maximum: float, fallback: float) -> float:
    try:
        converted = float(value)
        if not math.isfinite(converted):
            return fallback
        return max(minimum, min(maximum, converted))
    except (TypeError, ValueError, OverflowError):
        return fallback


def _sanitize_trigger_params(value: Any) -> Dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    sections = []
    raw_sections = source.get("sections", [])
    if isinstance(raw_sections, (list, tuple)):
        for point in raw_sections[:MAX_TRIGGER_SECTIONS]:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            position = _bounded_int(point[0], 0, 9, 0)
            strength = _bounded_int(point[1], 0, 255, 0)
            sections.append([position, strength])
    return {"sections": sections} if sections else {}


class TriggerEffectType(Enum):
    """Tipos de efectos disponibles para los gatillos."""

    OFF = "off"
    RIGID = "rigid"
    PULSE = "pulse"
    CONTINUOUS_VIBRATION = "continuous_vibration"
    SECTIONS = "sections"
    WEAPON_SINGLE = "weapon_single"
    WEAPON_AUTOMATIC = "weapon_automatic"
    WEAPON_SNIPER = "weapon_sniper"
    WEAPON_BOW = "weapon_bow"
    CUSTOM = "custom"


@dataclass
class TriggerEffect:
    """Configuracion de un efecto de gatillo."""

    name: str
    effect_type: TriggerEffectType
    # Parametros generales
    intensity: int = 255  # 0-255
    start_position: int = 0  # 0-9 (zona donde inicia el efecto)
    end_position: int = 9  # 0-9 (zona donde termina el efecto)
    frequency: int = 0  # Para efectos pulsados/vibracion

    # Vibracion adicional del propio gatillo. Esta configuracion puede
    # convivir con un efecto base de resistencia: la resistencia se mantiene
    # hasta alcanzar la zona de activacion y entonces se cambia temporalmente
    # al efecto oficial de vibracion del DualSense (0x26).
    vibration_enabled: bool = False
    vibration_intensity: int = 0  # 0-255 en UI; hardware usa 0-8
    vibration_frequency: int = 25  # Hz, byte 1-255
    vibration_start_position: int = 2  # zona 0-9
    vibration_end_position: int = 9  # zona 0-9

    # Parametros especificos por tipo
    custom_params: Dict[str, Any] = field(default_factory=dict)

    # Animacion
    animated: bool = False
    animation_speed: float = 1.0  # Multiplicador de velocidad
    animation_curve: str = "linear"  # linear, ease_in, ease_out, sine

    def to_dict(self) -> dict:
        """Serializa el efecto a diccionario."""
        return {
            "name": self.name,
            "effect_type": self.effect_type.value,
            "intensity": self.intensity,
            "start_position": self.start_position,
            "end_position": self.end_position,
            "frequency": self.frequency,
            "vibration_enabled": self.vibration_enabled,
            "vibration_intensity": self.vibration_intensity,
            "vibration_frequency": self.vibration_frequency,
            "vibration_start_position": self.vibration_start_position,
            "vibration_end_position": self.vibration_end_position,
            "custom_params": self.custom_params,
            "animated": self.animated,
            "animation_speed": self.animation_speed,
            "animation_curve": self.animation_curve,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TriggerEffect":
        """Deserializa un efecto y limita todo lo que llega al hardware."""
        source = data if isinstance(data, dict) else {}
        try:
            effect_type = TriggerEffectType(str(source.get("effect_type", "off")))
        except ValueError:
            effect_type = TriggerEffectType.OFF
        curve = str(source.get("animation_curve", "linear")).strip().lower()
        if curve not in {"linear", "ease_in", "ease_out", "ease_in_out", "sine", "bounce"}:
            curve = "linear"
        start_position = _bounded_int(source.get("start_position", 0), 0, 9, 0)
        end_position = _bounded_int(source.get("end_position", 9), start_position, 9, 9)
        return cls(
            name=str(source.get("name", "Unknown"))[:120],
            effect_type=effect_type,
            intensity=_bounded_int(source.get("intensity", 255), 0, 255, 255),
            start_position=start_position,
            end_position=end_position,
            frequency=_bounded_int(source.get("frequency", 0), 0, 255, 0),
            vibration_enabled=bool(source.get("vibration_enabled", False)),
            vibration_intensity=_bounded_int(source.get("vibration_intensity", 0), 0, 255, 0),
            vibration_frequency=_bounded_int(source.get("vibration_frequency", 25), 1, 255, 25),
            vibration_start_position=_bounded_int(
                source.get("vibration_start_position", 2), 0, 9, 2
            ),
            vibration_end_position=_bounded_int(source.get("vibration_end_position", 9), 0, 9, 9),
            custom_params=_sanitize_trigger_params(source.get("custom_params")),
            animated=bool(source.get("animated", False)),
            animation_speed=_bounded_float(source.get("animation_speed", 1.0), 0.05, 10.0, 1.0),
            animation_curve=curve,
        )


@dataclass(frozen=True)
class TriggerPreset:
    preset_id: str
    name: str
    category: str
    description: str
    effect: Dict[str, Any]


TRIGGER_PRESETS: Dict[str, TriggerPreset] = {
    "free": TriggerPreset("free", "Libre", "Básicos", "Sin resistencia ni vibración.", {"name": "Libre", "effect_type": "off"}),
    "soft": TriggerPreset("soft", "Resistencia suave", "Básicos", "Entrada ligera y cómoda para sesiones largas.", {"name": "Resistencia suave", "effect_type": "sections", "custom_params": {"sections": [[0, 18], [3, 42], [6, 70], [8, 95]]}}),
    "firm": TriggerPreset("firm", "Resistencia firme", "Básicos", "Resistencia estable desde el inicio.", {"name": "Resistencia firme", "effect_type": "rigid", "intensity": 155, "start_position": 1, "end_position": 9}),
    "progressive": TriggerPreset("progressive", "Progresiva", "Básicos", "La fuerza aumenta conforme aprietas.", {"name": "Resistencia progresiva", "effect_type": "sections", "custom_params": {"sections": [[0, 15], [2, 55], [4, 105], [6, 170], [8, 235]]}}),
    "wall": TriggerPreset("wall", "Pared final", "Básicos", "Recorrido libre y bloqueo fuerte cerca del fondo.", {"name": "Pared final", "effect_type": "weapon_single", "intensity": 225, "start_position": 6, "end_position": 8}),
    "pistol": TriggerPreset("pistol", "Pistola", "Armas", "Punto de disparo definido con golpe corto.", {"name": "Pistola", "effect_type": "weapon_single", "intensity": 205, "start_position": 3, "end_position": 7, "vibration_enabled": True, "vibration_intensity": 170, "vibration_frequency": 22, "vibration_start_position": 5, "vibration_end_position": 8}),
    "rifle": TriggerPreset("rifle", "Rifle automático", "Armas", "Cadencia rápida con resistencia media.", {"name": "Rifle automático", "effect_type": "weapon_automatic", "intensity": 185, "start_position": 2, "end_position": 9, "frequency": 34}),
    "shotgun": TriggerPreset("shotgun", "Escopeta", "Armas", "Disparo pesado y retroceso marcado.", {"name": "Escopeta", "effect_type": "weapon_single", "intensity": 255, "start_position": 4, "end_position": 9, "vibration_enabled": True, "vibration_intensity": 255, "vibration_frequency": 16, "vibration_start_position": 6, "vibration_end_position": 9}),
    "sniper": TriggerPreset("sniper", "Francotirador", "Armas", "Recorrido pesado con quiebre al final.", {"name": "Francotirador", "effect_type": "weapon_sniper", "intensity": 255, "start_position": 5, "end_position": 9}),
    "bow": TriggerPreset("bow", "Arco", "Armas", "Tensión elástica que crece hasta el fondo.", {"name": "Arco", "effect_type": "sections", "custom_params": {"sections": [[0, 25], [2, 70], [4, 125], [6, 190], [8, 255]]}}),
    "accelerator": TriggerPreset("accelerator", "Acelerador", "Vehículos", "Presión progresiva y suave.", {"name": "Acelerador", "effect_type": "sections", "custom_params": {"sections": [[0, 12], [3, 45], [6, 95], [8, 145]]}}),
    "brake": TriggerPreset("brake", "Freno", "Vehículos", "Fuerza creciente para simular presión hidráulica.", {"name": "Freno", "effect_type": "sections", "custom_params": {"sections": [[0, 25], [2, 65], [4, 125], [6, 190], [8, 245]]}}),
    "abs": TriggerPreset("abs", "Freno ABS", "Vehículos", "Vibración concentrada en la segunda mitad.", {"name": "ABS", "effect_type": "continuous_vibration", "intensity": 185, "start_position": 4, "end_position": 9, "frequency": 24}),
    "engine": TriggerPreset("engine", "Motor", "Vehículos", "Vibración baja y constante.", {"name": "Motor", "effect_type": "continuous_vibration", "intensity": 85, "start_position": 0, "end_position": 9, "frequency": 12}),
    "click": TriggerPreset("click", "Click mecánico", "Mecánicos", "Punto duro y corto cerca del final.", {"name": "Click mecánico", "effect_type": "weapon_single", "intensity": 235, "start_position": 7, "end_position": 8}),
    "spring": TriggerPreset("spring", "Resorte", "Mecánicos", "Resistencia escalonada con retorno elástico.", {"name": "Resorte", "effect_type": "sections", "animated": True, "animation_speed": 1.25, "animation_curve": "sine", "custom_params": {"sections": [[0, 35], [2, 90], [5, 155], [8, 220]]}}),
    "machine": TriggerPreset("machine", "Máquina", "Mecánicos", "Golpeteo rápido tipo herramienta.", {"name": "Máquina", "effect_type": "pulse", "intensity": 175, "start_position": 2, "end_position": 9, "frequency": 42}),
    "gallop": TriggerPreset("gallop", "Galope", "Mecánicos", "Pulso lento y marcado.", {"name": "Galope", "effect_type": "pulse", "intensity": 210, "start_position": 3, "end_position": 9, "frequency": 8, "animated": True, "animation_speed": 1.4, "animation_curve": "bounce"}),
}


def get_trigger_presets(category: str = "") -> list[TriggerPreset]:
    requested = str(category or "").strip().lower()
    presets = list(TRIGGER_PRESETS.values())
    if requested and requested not in {"todos", "all"}:
        presets = [preset for preset in presets if preset.category.lower() == requested]
    return presets


def effect_from_preset(preset_id: str) -> TriggerEffect:
    preset = TRIGGER_PRESETS.get(str(preset_id))
    if preset is None:
        raise KeyError(f"Preset de gatillo desconocido: {preset_id}")
    return TriggerEffect.from_dict(copy.deepcopy(preset.effect))


@dataclass
class WeaponProfile:
    """Perfil completo de configuracion de armas."""

    name: str
    description: str
    left_trigger: TriggerEffect
    right_trigger: TriggerEffect
    rumble_intensity: int = 128
    icon: str = "🔫"
    # ``image_path`` se conserva como alias legado del icono para perfiles
    # creados antes de 2.9.8.7. La galería moderna usa rutas separadas.
    image_path: str = ""
    icon_path: str = ""
    banner_path: str = ""
    category: str = "General"
    tags: List[str] = field(default_factory=list)
    origin: str = "user"
    created_at: str = ""
    updated_at: str = ""
    gyro_config: GyroConfig = field(default_factory=GyroConfig)
    light_config: Dict[str, Any] = field(
        default_factory=lambda: {
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
    )
    macros_enabled: bool = True
    input_studio_config: Dict[str, Any] = field(default_factory=dict)
    advanced_mapping_config: Dict[str, Any] = field(default_factory=dict)
    audio_config: Dict[str, Any] = field(default_factory=lambda: sanitize_audio_config({}))

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "left_trigger": self.left_trigger.to_dict(),
            "right_trigger": self.right_trigger.to_dict(),
            "rumble_intensity": self.rumble_intensity,
            "icon": self.icon,
            # Las versiones viejas leen image_path; mantenerlo apuntando al
            # icono permite abrir el perfil sin perder su imagen cuadrada.
            "image_path": self.icon_path or self.image_path,
            "icon_path": self.icon_path or self.image_path,
            "banner_path": self.banner_path,
            "category": self.category,
            "tags": list(self.tags),
            "origin": self.origin,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "gyro": self.gyro_config.to_dict(),
            "light_config": dict(self.light_config),
            "macros_enabled": bool(self.macros_enabled),
            "input_studio": dict(self.input_studio_config),
            "advanced_mapping": copy.deepcopy(self.advanced_mapping_config),
            "audio_config": sanitize_audio_config(self.audio_config),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WeaponProfile":
        source = data if isinstance(data, dict) else {}
        input_studio = source.get("input_studio", source.get("input_studio_config", {}))
        if not isinstance(input_studio, dict):
            input_studio = {}
        return cls(
            name=str(source.get("name", "Default"))[:120],
            description=str(source.get("description", ""))[:2_000],
            left_trigger=TriggerEffect.from_dict(source.get("left_trigger", {})),
            right_trigger=TriggerEffect.from_dict(source.get("right_trigger", {})),
            rumble_intensity=_bounded_int(source.get("rumble_intensity", 128), 0, 255, 128),
            icon=str(source.get("icon", "🔫"))[:64],
            image_path=str(
                source.get("image_path", source.get("icon_path", "")) or ""
            )[:2_048],
            icon_path=str(
                source.get("icon_path", source.get("image_path", "")) or ""
            )[:2_048],
            # En la primera galería image_path también se usó como portada.
            # Usarlo como fallback preserva visualmente esos perfiles hasta
            # que la persona elija un banner independiente.
            banner_path=str(
                source.get("banner_path", source.get("image_path", "")) or ""
            )[:2_048],
            category=str(source.get("category", "General"))[:80],
            tags=[
                str(item).strip()[:40]
                for item in (source.get("tags", []) if isinstance(source.get("tags", []), (list, tuple)) else [])[:12]
                if str(item).strip()
            ],
            origin=(
                str(source.get("origin", "user")).strip().lower()
                if str(source.get("origin", "user")).strip().lower() in {"builtin", "user", "imported"}
                else "user"
            ),
            created_at=str(source.get("created_at", "") or "")[:64],
            updated_at=str(source.get("updated_at", "") or "")[:64],
            gyro_config=GyroConfig.from_dict(source.get("gyro", source.get("gyro_config", {}))),
            light_config=LightEffectEngine.sanitize_config(source.get("light_config", {})),
            macros_enabled=bool(source.get("macros_enabled", True)),
            input_studio_config={
                stick: InputStudioEngine.sanitize_config(input_studio.get(stick))
                for stick in STICKS
            },
            advanced_mapping_config=sanitize_mapping_config(
                source.get("advanced_mapping", source.get("advanced_mapping_config", {}))
            ),
            audio_config=sanitize_audio_config(source.get("audio_config", source.get("audio", {}))),
        )


class TriggerEngine:
    """
    Motor de efectos de gatillo para DualSense.
    Gestiona efectos estaticos, animaciones en tiempo real y perfiles.
    """

    # Mapeo de curvas de animacion
    CURVES = {
        "linear": lambda t: t,
        "ease_in": lambda t: t * t,
        "ease_out": lambda t: 1 - (1 - t) * (1 - t),
        "ease_in_out": lambda t: 0.5 - 0.5 * math.cos(t * math.pi),
        "sine": lambda t: 0.5 + 0.5 * math.sin(t * 2 * math.pi - math.pi / 2),
        "bounce": lambda t: abs(math.sin(t * math.pi * 3)) * (1 - t) + t,
    }

    def __init__(self, connection_manager=None):
        self.connection_manager = connection_manager
        self.dualsense = None

        # Estado actual
        self._current_left_effect: Optional[TriggerEffect] = None
        self._current_right_effect: Optional[TriggerEffect] = None
        self._animation_running = False
        self._animation_thread: Optional[threading.Thread] = None
        self._animation_stop_event = threading.Event()
        self._animation_time = 0.0
        self._lock = threading.RLock()

        # Estado de vibracion adicional por perfil. Se activa al cruzar la
        # zona configurada y vuelve al efecto base al soltar el gatillo.
        self._profile_vibration_active = {"left": False, "right": False}
        self._profile_vibration_last_change = {"left": 0.0, "right": 0.0}
        self._test_active = False
        self._test_targets: set[str] = set()
        self._test_timer: Optional[threading.Timer] = None

        # Perfiles predefinidos
        self._profiles: Dict[str, WeaponProfile] = {}
        self._current_profile: Optional[str] = None
        self._init_default_profiles()
        # Se conserva una copia inmutable de los perfiles integrados para que
        # la opción Restaurar no dependa de datos guardados por el usuario.
        self._builtin_defaults = copy.deepcopy(self._profiles)
        self._builtin_profile_ids = set(RESERVED_PROFILE_IDS)
        self._custom_profile_ids: Set[str] = set()

        # Callbacks
        self._on_effect_change: List[Callable[[str, TriggerEffect], None]] = []
        self._on_profile_change: List[Callable[[str], None]] = []
        self._connection_unsubscribe: Optional[Callable[[], None]] = None

        if self.connection_manager and hasattr(self.connection_manager, "on_state_update"):
            unsubscribe = self.connection_manager.on_state_update(
                self._on_controller_state_update
            )
            if callable(unsubscribe):
                self._connection_unsubscribe = unsubscribe

    def set_connection_manager(self, connection_manager) -> None:
        """Establece el gestor de conexion y escucha la posicion de gatillos."""
        if self._connection_unsubscribe is not None:
            self._connection_unsubscribe()
            self._connection_unsubscribe = None
        self.connection_manager = connection_manager
        if connection_manager and hasattr(connection_manager, "on_state_update"):
            unsubscribe = connection_manager.on_state_update(
                self._on_controller_state_update
            )
            if callable(unsubscribe):
                self._connection_unsubscribe = unsubscribe

    def _add_callback(self, bucket: list, callback: Callable[..., None]) -> Callable[[], None]:
        if not callable(callback):
            raise TypeError("El callback debe ser invocable")
        with self._lock:
            if callback not in bucket:
                bucket.append(callback)

        def unsubscribe() -> None:
            with self._lock:
                bucket[:] = [item for item in bucket if item != callback]

        return unsubscribe

    def _notify_callbacks(self, bucket: list, *args: Any) -> None:
        """Avisa sobre una instantánea y retira suscriptores que ya no son válidos."""
        with self._lock:
            callbacks = list(bucket)
        failed: list[Callable[..., None]] = []
        for callback in callbacks:
            try:
                callback(*args)
            except Exception:
                logger.exception("Callback de TriggerEngine desactivado tras fallar")
                failed.append(callback)
        if failed:
            with self._lock:
                bucket[:] = [callback for callback in bucket if callback not in failed]

    def on_effect_change(
        self, callback: Callable[[str, TriggerEffect], None]
    ) -> Callable[[], None]:
        """Registra callback para cambios de efecto."""
        return self._add_callback(self._on_effect_change, callback)

    def on_profile_change(self, callback: Callable[[str], None]) -> Callable[[], None]:
        """Registra callback para cambios de perfil."""
        return self._add_callback(self._on_profile_change, callback)

    # ===== Inicialización de Perfiles =====

    def _init_default_profiles(self) -> None:
        """Construye la biblioteca oficial de ocho perfiles comunitarios.

        Los parámetros vienen de :mod:`src.profile_catalog` y los efectos usan
        los mismos presets validados que Trigger Studio. Así la interfaz, los
        perfiles y el motor de hardware comparten una sola fuente de verdad.
        """

        self._profiles.clear()
        for catalog_spec in BUILTIN_PROFILE_SPECS:
            payload = clone_spec_payload(catalog_spec)
            left = effect_from_preset(payload["left_preset"])
            right = effect_from_preset(payload["right_preset"])
            for key, value in payload["left_changes"].items():
                if hasattr(left, key):
                    setattr(left, key, copy.deepcopy(value))
            for key, value in payload["right_changes"].items():
                if hasattr(right, key):
                    setattr(right, key, copy.deepcopy(value))

            self._profiles[payload["profile_id"]] = WeaponProfile(
                name=payload["name"],
                description=payload["description"],
                left_trigger=left,
                right_trigger=right,
                rumble_intensity=payload["rumble_intensity"],
                icon=payload["icon"],
                category=payload["category"],
                tags=list(payload["tags"]),
                origin="builtin",
                light_config=LightEffectEngine.sanitize_config(payload["light_config"]),
                macros_enabled=bool(payload["macros_enabled"]),
                input_studio_config={
                    stick: InputStudioEngine.sanitize_config(
                        payload["input_studio_config"].get(stick)
                    )
                    for stick in STICKS
                },
            )

        logger.info(
            "Inicializados %s perfiles comunitarios integrados",
            len(self._profiles),
        )

    @staticmethod
    def canonical_profile_id(profile_id: Any) -> str:
        """Resuelve IDs retirados sin exponer perfiles duplicados en la UI."""
        return canonical_profile_id(profile_id)

    def reset_builtin_profile(self, profile_id: str) -> bool:
        """Restaura un perfil de fábrica a su definición del catálogo."""
        resolved = self.canonical_profile_id(profile_id)
        default = self._builtin_defaults.get(resolved)
        if default is None:
            return False
        with self._lock:
            self._profiles[resolved] = copy.deepcopy(default)
        return True

    def get_all_profiles(self) -> Dict[str, WeaponProfile]:
        """Devuelve todos los perfiles disponibles."""
        return dict(self._profiles)

    def get_profile(self, profile_id: str) -> Optional[WeaponProfile]:
        """Obtiene un perfil y resuelve aliases de versiones anteriores."""
        return self._profiles.get(self.canonical_profile_id(profile_id))

    def get_profile_names(self) -> List[tuple[str, str]]:
        """Devuelve lista de (id, nombre) de perfiles."""
        return [(k, v.name) for k, v in self._profiles.items()]

    def add_custom_profile(self, profile_id: str, profile: WeaponProfile) -> bool:
        """Agrega o actualiza un perfil creado por la persona usuaria.

        Los IDs de fabrica son reservados para que una importacion o una UI
        defectuosa no pueda sobrescribir los comportamientos incluidos.
        """
        clean_id = (
            str(profile_id).strip()[:MAX_PROFILE_ID_LENGTH] if isinstance(profile_id, str) else ""
        )
        if (
            not clean_id
            or clean_id in self._builtin_profile_ids
            or self.canonical_profile_id(clean_id) in self._builtin_profile_ids
        ):
            logger.warning(f"ID de perfil personalizado invalido o reservado: {profile_id!r}")
            return False
        if not isinstance(profile, WeaponProfile):
            logger.warning("Se intento agregar un perfil que no es WeaponProfile")
            return False
        with self._lock:
            if (
                clean_id not in self._custom_profile_ids
                and len(self._custom_profile_ids) >= MAX_CUSTOM_TRIGGER_PROFILES
            ):
                logger.warning("Se alcanzó el límite de perfiles personalizados")
                return False
            if profile.origin == "builtin":
                profile.origin = "user"
            self._profiles[clean_id] = profile
            self._custom_profile_ids.add(clean_id)
        logger.info(f"Perfil personalizado agregado: {clean_id}")
        return True

    def update_profile(self, profile_id: str, profile: WeaponProfile) -> bool:
        """Actualiza un perfil existente sin cambiar si es integrado o personalizado."""
        if not isinstance(profile, WeaponProfile):
            return False
        resolved = self.canonical_profile_id(profile_id)
        with self._lock:
            if resolved not in self._profiles:
                return False
            self._profiles[resolved] = profile
        return True

    def export_profile_overrides(self) -> Dict[str, Dict[str, Any]]:
        """Guarda partes editables también para perfiles integrados."""
        with self._lock:
            return {
                profile_id: {
                    "name": profile.name,
                    "description": profile.description,
                    "category": profile.category,
                    "tags": list(profile.tags),
                    "origin": profile.origin,
                    "created_at": profile.created_at,
                    "updated_at": profile.updated_at,
                    "icon": profile.icon,
                    "image_path": profile.icon_path or profile.image_path,
                    "icon_path": profile.icon_path or profile.image_path,
                    "banner_path": profile.banner_path,
                    "rumble_intensity": profile.rumble_intensity,
                    "left_trigger": profile.left_trigger.to_dict(),
                    "right_trigger": profile.right_trigger.to_dict(),
                    "light_config": dict(profile.light_config),
                    "macros_enabled": bool(profile.macros_enabled),
                    "input_studio": dict(profile.input_studio_config),
                    "advanced_mapping": copy.deepcopy(profile.advanced_mapping_config),
                    "audio_config": sanitize_audio_config(profile.audio_config),
                }
                for profile_id, profile in self._profiles.items()
            }

    def load_profile_overrides(self, data: Dict[str, Any]) -> None:
        """Restaura cambios hechos desde la nueva interfaz sin romper JSON antiguos."""
        if not isinstance(data, dict):
            return
        with self._lock:
            for profile_id, payload in data.items():
                resolved = self.canonical_profile_id(profile_id)
                profile = self._profiles.get(resolved)
                if not profile or not isinstance(payload, dict):
                    continue
                profile.name = str(payload.get("name", profile.name) or profile.name).strip()[:120]
                profile.description = str(
                    payload.get("description", profile.description) or ""
                )[:2_000]
                profile.category = str(
                    payload.get("category", profile.category) or "General"
                ).strip()[:80]
                if isinstance(payload.get("tags"), (list, tuple)):
                    cleaned_tags: List[str] = []
                    for item in payload["tags"][:12]:
                        tag = str(item).strip()[:40]
                        if tag and tag not in cleaned_tags:
                            cleaned_tags.append(tag)
                    profile.tags = cleaned_tags
                requested_origin = str(payload.get("origin", profile.origin) or profile.origin)
                profile.origin = requested_origin if requested_origin in {"builtin", "user", "imported"} else profile.origin
                profile.created_at = str(payload.get("created_at", profile.created_at) or "")[:64]
                profile.updated_at = str(payload.get("updated_at", profile.updated_at) or "")[:64]
                profile.icon = str(payload.get("icon", profile.icon) or profile.icon)[:64]
                legacy_image = str(
                    payload.get("image_path", profile.image_path) or ""
                )[:2_048]
                profile.image_path = legacy_image
                profile.icon_path = str(
                    payload.get("icon_path", legacy_image or profile.icon_path) or ""
                )[:2_048]
                profile.banner_path = str(
                    payload.get("banner_path", legacy_image or profile.banner_path) or ""
                )[:2_048]
                try:
                    profile.rumble_intensity = max(
                        0, min(255, int(payload.get("rumble_intensity", profile.rumble_intensity)))
                    )
                except (TypeError, ValueError, OverflowError):
                    pass
                if isinstance(payload.get("left_trigger"), dict):
                    profile.left_trigger = TriggerEffect.from_dict(payload["left_trigger"])
                if isinstance(payload.get("right_trigger"), dict):
                    profile.right_trigger = TriggerEffect.from_dict(payload["right_trigger"])
                if isinstance(payload.get("light_config"), dict):
                    profile.light_config = LightEffectEngine.sanitize_config(
                        payload["light_config"]
                    )
                profile.macros_enabled = bool(payload.get("macros_enabled", profile.macros_enabled))
                if isinstance(payload.get("input_studio"), dict):
                    profile.input_studio_config = {
                        stick: InputStudioEngine.sanitize_config(
                            payload["input_studio"].get(stick)
                        )
                        for stick in STICKS
                    }
                if isinstance(payload.get("advanced_mapping"), dict):
                    profile.advanced_mapping_config = sanitize_mapping_config(
                        payload["advanced_mapping"]
                    )
                if "audio_config" in payload or "audio" in payload:
                    profile.audio_config = sanitize_audio_config(
                        payload.get("audio_config", payload.get("audio", {}))
                    )

    def is_custom_profile(self, profile_id: str) -> bool:
        """Indica si un perfil puede editarse/eliminarse desde la coleccion."""
        resolved = self.canonical_profile_id(profile_id)
        with self._lock:
            return resolved in self._custom_profile_ids

    def export_custom_profiles_to_dict(self) -> Dict[str, dict]:
        """Exporta solo los perfiles creados por el usuario para persistirlos."""
        with self._lock:
            return {
                profile_id: self._profiles[profile_id].to_dict()
                for profile_id in sorted(self._custom_profile_ids)
                if profile_id in self._profiles
            }

    def remove_profile(self, profile_id: str) -> bool:
        """Elimina exclusivamente un perfil personalizado.

        Los perfiles incluidos se reconstruyen al iniciar la aplicacion; por
        eso eliminarlos en memoria daba una experiencia confusa y podia dejar
        configuraciones apuntando a un ID que reaparecia al reiniciar.
        """
        resolved = self.canonical_profile_id(profile_id)
        with self._lock:
            if resolved not in self._custom_profile_ids or resolved not in self._profiles:
                return False
            del self._profiles[resolved]
            self._custom_profile_ids.discard(resolved)
            if self._current_profile == resolved:
                self._current_profile = None
        logger.info(f"Perfil personalizado eliminado: {resolved}")
        return True

    # ===== Aplicación de Efectos =====

    def apply_effect(self, trigger: str, effect: TriggerEffect) -> bool:
        """
        Aplica un efecto a un gatillo.
        trigger: 'left' o 'right'
        """
        if not self._can_send_commands():
            return False

        try:
            ds = self.connection_manager.dualsense_instance
            if not ds:
                return False

            with self._lock:
                if trigger == "left":
                    self._current_left_effect = effect
                    self._send_trigger_command(ds, "left", effect)
                elif trigger == "right":
                    self._current_right_effect = effect
                    self._send_trigger_command(ds, "right", effect)
                else:
                    logger.warning(f"Gatillo desconocido: {trigger}")
                    return False

            # Notificar cambio
            self._notify_effect_change(trigger, effect)

            # Manejar animacion
            if effect.animated:
                self._start_animation()

            return True

        except Exception as e:
            logger.error(f"Error aplicando efecto: {e}")
            return False

    def apply_profile(self, profile_id: str) -> bool:
        """Aplica un perfil completo y normaliza IDs retirados."""
        resolved = self.canonical_profile_id(profile_id)
        profile = self._profiles.get(resolved)
        if not profile:
            logger.warning(f"Perfil no encontrado: {profile_id}")
            return False

        try:
            # Un cambio de perfil cancela cualquier prueba temporal y reinicia
            # el estado de las vibraciones superpuestas.
            self.stop_trigger_vibration_test(restore=False)
            self._profile_vibration_active = {"left": False, "right": False}

            # Aplicar efecto al gatillo izquierdo
            self.apply_effect("left", profile.left_trigger)

            # Aplicar efecto al gatillo derecho
            self.apply_effect("right", profile.right_trigger)

            # Apagar motores al cambiar de perfil para evitar vibracion infinita
            if self.connection_manager:
                self.connection_manager.set_rumble(0, 0)

            self._current_profile = resolved

            # Notificar siempre con el ID canónico para que macros, Input
            # Studio y reglas por juego converjan en una sola configuración.
            self._notify_callbacks(self._on_profile_change, resolved)

            logger.info("Perfil aplicado: %s (%s)", profile.name, resolved)
            return True

        except Exception as e:
            logger.error(f"Error aplicando perfil: {e}")
            return False

    def get_profile_gyro_config(self, profile_id: str) -> GyroConfig:
        """Devuelve una copia segura de la configuracion IMU del perfil."""
        resolved = self.canonical_profile_id(profile_id)
        with self._lock:
            profile = self._profiles.get(resolved)
            return profile.gyro_config.copy() if profile else GyroConfig()

    def update_profile_gyro_config(self, profile_id: str, config: Any) -> bool:
        """Actualiza gyro sin reemplazar gatillos, icono ni otros datos."""
        parsed = config.copy() if isinstance(config, GyroConfig) else GyroConfig.from_dict(config)
        resolved = self.canonical_profile_id(profile_id)
        with self._lock:
            profile = self._profiles.get(resolved)
            if not profile:
                return False
            profile.gyro_config = parsed
            return True

    def export_gyro_overrides(self) -> Dict[str, Dict[str, Any]]:
        """Persiste gyro tambien para perfiles predefinidos."""
        with self._lock:
            return {
                profile_id: profile.gyro_config.to_dict()
                for profile_id, profile in self._profiles.items()
            }

    def load_gyro_overrides(self, data: Dict[str, Any]) -> None:
        """Carga datos nuevos sin romper configuraciones antiguas."""
        if not isinstance(data, dict):
            return
        with self._lock:
            for profile_id, config in data.items():
                profile = self._profiles.get(self.canonical_profile_id(profile_id))
                if profile and isinstance(config, dict):
                    profile.gyro_config = GyroConfig.from_dict(config)

    @staticmethod
    def _effect_vibration_dict(effect: TriggerEffect) -> Dict[str, Any]:
        """Extrae la configuracion editable de vibracion de un efecto."""
        return {
            "enabled": bool(effect.vibration_enabled),
            "intensity": max(0, min(255, int(effect.vibration_intensity))),
            "frequency": max(1, min(255, int(effect.vibration_frequency))),
            "start_position": max(0, min(9, int(effect.vibration_start_position))),
            "end_position": max(0, min(9, int(effect.vibration_end_position))),
        }

    def get_profile_vibration_settings(
        self, profile_id: str
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """Devuelve la vibracion adicional de L2/R2 para editarla en la UI."""
        resolved = self.canonical_profile_id(profile_id)
        profile = self._profiles.get(resolved)
        if not profile:
            return None
        return {
            "left": self._effect_vibration_dict(profile.left_trigger),
            "right": self._effect_vibration_dict(profile.right_trigger),
        }

    def update_profile_vibration(
        self,
        profile_id: str,
        trigger: str,
        *,
        enabled: bool,
        intensity: int,
        frequency: int,
        start_position: int,
        end_position: int,
        reapply: bool = True,
    ) -> bool:
        """Actualiza la vibracion adicional de un gatillo dentro de un perfil."""
        resolved = self.canonical_profile_id(profile_id)
        profile = self._profiles.get(resolved)
        if not profile or trigger not in ("left", "right"):
            return False

        effect = profile.left_trigger if trigger == "left" else profile.right_trigger
        start = max(0, min(9, int(start_position)))
        end = max(start, min(9, int(end_position)))
        effect.vibration_enabled = bool(enabled)
        effect.vibration_intensity = max(0, min(255, int(intensity)))
        effect.vibration_frequency = max(1, min(255, int(frequency)))
        effect.vibration_start_position = start
        effect.vibration_end_position = end

        if reapply and self._current_profile == resolved and self._can_send_commands():
            self.apply_profile(resolved)
        return True

    def export_vibration_overrides(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Exporta solo la parte de vibracion para persistir incluso perfiles base."""
        return {
            profile_id: {
                "left": self._effect_vibration_dict(profile.left_trigger),
                "right": self._effect_vibration_dict(profile.right_trigger),
            }
            for profile_id, profile in self._profiles.items()
        }

    def load_vibration_overrides(self, data: Dict[str, Any]) -> None:
        """Aplica configuraciones guardadas sin reemplazar el resto del perfil."""
        if not isinstance(data, dict):
            return
        for profile_id, triggers in data.items():
            if not isinstance(triggers, dict):
                continue
            for trigger in ("left", "right"):
                cfg = triggers.get(trigger)
                if not isinstance(cfg, dict):
                    continue
                self.update_profile_vibration(
                    profile_id,
                    trigger,
                    enabled=cfg.get("enabled", False),
                    intensity=cfg.get("intensity", 0),
                    frequency=cfg.get("frequency", 25),
                    start_position=cfg.get("start_position", 2),
                    end_position=cfg.get("end_position", 9),
                    reapply=False,
                )

    def _build_profile_vibration_effect(self, effect: TriggerEffect) -> TriggerEffect:
        return TriggerEffect(
            name=f"Vibracion de {effect.name}",
            effect_type=TriggerEffectType.CONTINUOUS_VIBRATION,
            intensity=effect.vibration_intensity,
            start_position=effect.vibration_start_position,
            end_position=effect.vibration_end_position,
            frequency=effect.vibration_frequency,
        )

    @staticmethod
    def _zone_to_input_value(zone: int) -> int:
        return int(max(0, min(9, zone)) * 255 / 9)

    def _on_controller_state_update(self, state) -> None:
        """Activa la vibracion del perfil al llegar a la zona elegida.

        El hardware solo admite un modo de gatillo a la vez. Por eso se conserva
        la resistencia base mientras se presiona, se cambia a vibracion al cruzar
        el umbral y se restaura la resistencia al soltar.
        """
        if self._test_active or not self._can_send_commands():
            return

        now = time.monotonic()
        ds = self.connection_manager.dualsense_instance
        if not ds:
            return

        for trigger, value, effect in (
            ("left", int(getattr(state, "left_trigger", 0)), self._current_left_effect),
            ("right", int(getattr(state, "right_trigger", 0)), self._current_right_effect),
        ):
            active = self._profile_vibration_active[trigger]
            usable = bool(
                effect
                and effect.vibration_enabled
                and effect.vibration_intensity > 0
                and effect.vibration_frequency > 0
            )

            if not usable:
                if active and effect:
                    with self._lock:
                        self._send_trigger_command(ds, trigger, effect)
                        self._profile_vibration_active[trigger] = False
                continue

            threshold = self._zone_to_input_value(effect.vibration_start_position)
            release_threshold = max(0, threshold - 14)
            last_change = self._profile_vibration_last_change[trigger]

            if not active and value >= threshold and (now - last_change) >= 0.04:
                with self._lock:
                    self._send_trigger_command(
                        ds, trigger, self._build_profile_vibration_effect(effect)
                    )
                    self._profile_vibration_active[trigger] = True
                    self._profile_vibration_last_change[trigger] = now
            elif active and value <= release_threshold and (now - last_change) >= 0.04:
                with self._lock:
                    self._send_trigger_command(ds, trigger, effect)
                    self._profile_vibration_active[trigger] = False
                    self._profile_vibration_last_change[trigger] = now

    def test_effect(self, target: str = "both", duration: float = 1.4) -> bool:
        """Prueba el efecto base actual y restaura el perfil automáticamente."""
        if not self._can_send_commands():
            return False
        targets = {"left", "right"} if target == "both" else {str(target)}
        targets &= {"left", "right"}
        if not targets:
            return False
        with self._lock:
            self.stop_trigger_vibration_test(restore=True)
            ds = self.connection_manager.dualsense_instance
            if not ds:
                return False
            effects = {
                "left": self._current_left_effect,
                "right": self._current_right_effect,
            }
            self._test_active = True
            self._test_targets = set(targets)
            for trigger in targets:
                effect = effects.get(trigger)
                if effect is not None:
                    self._send_trigger_command(ds, trigger, effect)
            self._test_timer = threading.Timer(
                max(0.2, min(10.0, float(duration))),
                self.stop_trigger_vibration_test,
            )
            self._test_timer.daemon = True
            self._test_timer.start()
        return True

    def test_trigger_vibration(
        self,
        target: str = "both",
        intensity: int = 220,
        frequency: int = 30,
        start_position: int = 1,
        end_position: int = 9,
        duration: float = 2.0,
    ) -> bool:
        """Prueba la vibracion oficial 0x26 y luego restaura los efectos previos."""
        if not self._can_send_commands():
            return False

        targets = {"left", "right"} if target == "both" else {target}
        targets &= {"left", "right"}
        if not targets:
            return False

        effect = TriggerEffect(
            name="Prueba de vibracion",
            effect_type=TriggerEffectType.CONTINUOUS_VIBRATION,
            intensity=max(0, min(255, int(intensity))),
            frequency=max(1, min(255, int(frequency))),
            start_position=max(0, min(9, int(start_position))),
            end_position=max(0, min(9, int(end_position))),
        )
        if effect.end_position < effect.start_position:
            effect.end_position = effect.start_position

        with self._lock:
            self.stop_trigger_vibration_test(restore=True)
            ds = self.connection_manager.dualsense_instance
            if not ds:
                return False
            self._test_active = True
            self._test_targets = targets
            for trigger in targets:
                self._send_trigger_command(ds, trigger, effect)

            self._test_timer = threading.Timer(
                max(0.2, min(10.0, float(duration))),
                self.stop_trigger_vibration_test,
            )
            self._test_timer.daemon = True
            self._test_timer.start()
        return True

    def stop_trigger_vibration_test(self, restore: bool = True) -> None:
        """Detiene una prueba y recupera la resistencia/perfil anterior."""
        with self._lock:
            timer = self._test_timer
            self._test_timer = None
            if timer and timer is not threading.current_thread():
                timer.cancel()

            targets = set(self._test_targets)
            was_active = self._test_active
            self._test_active = False
            self._test_targets.clear()

            if not restore or not was_active or not self._can_send_commands():
                return
            ds = self.connection_manager.dualsense_instance
            if not ds:
                return
            for trigger in targets:
                base = (
                    self._current_left_effect if trigger == "left" else self._current_right_effect
                )
                if base:
                    self._send_trigger_command(ds, trigger, base)
                self._profile_vibration_active[trigger] = False

    def get_current_profile(self) -> Optional[str]:
        """Devuelve el ID del perfil actual."""
        return self._current_profile

    def reset_triggers(self) -> None:
        """Apaga los efectos de ambos gatillos."""
        self.stop_trigger_vibration_test(restore=False)
        self._profile_vibration_active = {"left": False, "right": False}
        off_effect = TriggerEffect("Off", TriggerEffectType.OFF)
        self.apply_effect("left", off_effect)
        self.apply_effect("right", off_effect)
        self._stop_animation()

    # ===== Comandos de Bajo Nivel =====

    def _send_trigger_command(self, ds, trigger: str, effect: TriggerEffect) -> None:
        """Envia el comando de efecto al control usando la API real."""
        if not PYDUALSENSE_AVAILABLE:
            return

        try:
            # 1. Apuntar al objeto correcto del gatillo
            t_obj = ds.triggerL if trigger == "left" else ds.triggerR

            # 2. Establecer el modo
            mode = self._map_effect_to_mode(effect)
            t_obj.setMode(mode)

            # 3. Aplicar la fuerza. OJO: setForce(forceID, force) de pydualsense
            # solo acepta UN par (indice, valor) por llamada -- nunca 3 o 4
            # argumentos juntos. Para efectos con varios parametros (Pulse,
            # secciones, automatica, francotirador, etc.) hay que llamarlo una
            # vez por cada posicion del array interno de fuerzas (0-6), tal
            # como lo hace el propio ejemplo oficial de la libreria.
            # Limpiar los siete slots primero. Sin esto, al pasar de una curva
            # multizona a un efecto corto podían sobrevivir bytes del efecto
            # anterior, una especie de fantasma háptico bastante poco elegante.
            for force_id in range(7):
                t_obj.setForce(force_id, 0)

            params = self._calculate_force_params(effect)
            for force_id, value in enumerate(params[:7]):
                t_obj.setForce(force_id, max(0, min(255, int(value))))

        except Exception as e:
            # Antes esto se tragaba en silencio y ocultaba fallos reales
            # (como el de arriba). Con debug queda visible sin inundar la
            # consola en uso normal.
            logger.debug(f"Error enviando comando de gatillo ({trigger}): {e}")

    def _map_effect_to_mode(self, effect: TriggerEffect) -> int:
        """Mapea un TriggerEffectType al modo correspondiente del DualSense."""
        # El modo Feedback oficial (0x21 / Rigid_A en pydualsense) permite
        # activar hasta 10 zonas independientes con fuerza propia. El editor
        # visual usa ese formato cuando recibe una curva por secciones.
        if effect.effect_type == TriggerEffectType.SECTIONS:
            return TriggerModes.Rigid_A
        if effect.effect_type == TriggerEffectType.CUSTOM and effect.custom_params.get("sections"):
            return TriggerModes.Rigid_A

        mode_map = {
            TriggerEffectType.OFF: TriggerModes.Off,
            TriggerEffectType.RIGID: TriggerModes.Rigid,
            # 0x26 es el modo oficial Vibration. Pulse_A (0x22) corresponde
            # al efecto Bow/snap-back y por eso la implementacion anterior
            # no producia una vibracion continua real.
            TriggerEffectType.PULSE: TriggerModes.Pulse_AB,
            TriggerEffectType.CONTINUOUS_VIBRATION: TriggerModes.Pulse_AB,
            TriggerEffectType.WEAPON_SINGLE: TriggerModes.Rigid_AB,
            TriggerEffectType.WEAPON_AUTOMATIC: TriggerModes.Pulse_AB,
            TriggerEffectType.WEAPON_SNIPER: TriggerModes.Rigid_AB,
            TriggerEffectType.WEAPON_BOW: TriggerModes.Rigid_AB,
            TriggerEffectType.CUSTOM: TriggerModes.Rigid_AB,
        }
        return mode_map.get(effect.effect_type, TriggerModes.Off)

    @staticmethod
    def _force_255_to_zone_strength(force: int) -> int:
        """Convierte fuerza 0-255 a la escala real del hardware 0-8."""
        force = max(0, min(255, int(force)))
        if force == 0:
            return 0
        return max(1, min(8, round((force / 255) * 8)))

    def _sections_to_zone_strengths(self, sections: List[Any]) -> List[int]:
        """Convierte puntos (posicion, fuerza) en 10 zonas reales.

        Cada punto inicia un tramo de resistencia que se mantiene hasta el
        siguiente punto. Por ejemplo, puntos en 0, 3, 6 y 9 producen cuatro
        zonas independientes: 0-2, 3-5, 6-8 y 9. Esto coincide con la forma
        escalonada del editor y evita volver a reducir toda la curva a una
        sola fuerza maxima.
        """
        clean: Dict[int, int] = {}
        for item in sections or []:
            try:
                position, force = item
                position = max(0, min(9, int(round(float(position)))))
                force = max(0, min(255, int(round(float(force)))))
            except (TypeError, ValueError, OverflowError):
                continue
            # Si dos puntos terminan en la misma posicion, el ultimo editado
            # gana. La UI evita esto, pero los perfiles importados pueden traerlo.
            clean[position] = force

        if not clean:
            return [0] * 10

        points = sorted(clean.items())
        zones = [0] * 10

        for index, (start, force) in enumerate(points):
            end = points[index + 1][0] - 1 if index + 1 < len(points) else 9
            strength = self._force_255_to_zone_strength(force)
            for zone in range(start, max(start, end) + 1):
                zones[zone] = strength

        return zones

    def get_section_zone_strengths(self, sections: List[Any]) -> List[int]:
        """Devuelve las 10 fuerzas reales (0-8) para previsualizacion/UI."""
        return self._sections_to_zone_strengths(sections)

    @staticmethod
    def _pack_feedback_zones(zone_strengths: List[int]) -> List[int]:
        """Empaqueta 10 fuerzas en el layout real del efecto Feedback.

        Parametros 0-1: bitmask de zonas activas (10 bits).
        Parametros 2-5: diez valores de fuerza de 3 bits (fuerza-1).
        Parametro 6: reservado, se mantiene en cero.
        """
        strengths = list(zone_strengths[:10]) + [0] * max(0, 10 - len(zone_strengths))
        active_zones = 0
        packed_strengths = 0

        for zone, strength in enumerate(strengths[:10]):
            strength = max(0, min(8, int(strength)))
            if strength <= 0:
                continue
            active_zones |= 1 << zone
            packed_strengths |= ((strength - 1) & 0x07) << (zone * 3)

        return [
            active_zones & 0xFF,
            (active_zones >> 8) & 0xFF,
            packed_strengths & 0xFF,
            (packed_strengths >> 8) & 0xFF,
            (packed_strengths >> 16) & 0xFF,
            (packed_strengths >> 24) & 0xFF,
            0,
        ]

    @staticmethod
    def _vibration_amplitude_255_to_8(intensity: int) -> int:
        intensity = max(0, min(255, int(intensity)))
        if intensity == 0:
            return 0
        return max(1, min(8, round((intensity / 255) * 8)))

    def _pack_vibration_zones(
        self, start_position: int, end_position: int, intensity: int, frequency: int
    ) -> List[int]:
        """Empaqueta el modo oficial Vibration (0x26) para pydualsense.

        pydualsense expone siete ``forces``: los primeros seis corresponden a
        máscara + amplitudes empaquetadas y el séptimo se escribe en el byte de
        frecuencia del reporte HID (los dos bytes intermedios son reservados).
        """
        start = max(0, min(9, int(start_position)))
        end = max(start, min(9, int(end_position)))
        amplitude = self._vibration_amplitude_255_to_8(intensity)
        hz = max(1, min(255, int(frequency)))

        zones = [0] * 10
        for zone in range(start, end + 1):
            zones[zone] = amplitude

        active_zones = 0
        packed_amplitudes = 0
        for zone, strength in enumerate(zones):
            if strength <= 0:
                continue
            active_zones |= 1 << zone
            packed_amplitudes |= ((strength - 1) & 0x07) << (zone * 3)

        return [
            active_zones & 0xFF,
            (active_zones >> 8) & 0xFF,
            packed_amplitudes & 0xFF,
            (packed_amplitudes >> 8) & 0xFF,
            (packed_amplitudes >> 16) & 0xFF,
            (packed_amplitudes >> 24) & 0xFF,
            hz,
        ]

    def _calculate_force_params(self, effect: TriggerEffect) -> List[int]:
        """Calcula los parametros de fuerza segun el tipo de efecto."""
        params = []

        if effect.effect_type == TriggerEffectType.OFF:
            params = [0]

        elif effect.effect_type == TriggerEffectType.RIGID:
            # Rigid simple (mode=1): forceID 1 = fuerza, escala 0-255. Es
            # el patron EXACTO del ejemplo oficial de pydualsense
            # (setForce(1, 255)), asi que es el mas confiable de todos.
            params = [0, effect.intensity]

        elif effect.effect_type in (
            TriggerEffectType.PULSE,
            TriggerEffectType.CONTINUOUS_VIBRATION,
            TriggerEffectType.WEAPON_AUTOMATIC,
        ):
            params = self._pack_vibration_zones(
                effect.start_position,
                effect.end_position,
                effect.intensity,
                max(1, effect.frequency),
            )

        elif effect.effect_type == TriggerEffectType.SECTIONS or (
            effect.effect_type == TriggerEffectType.CUSTOM and effect.custom_params.get("sections")
        ):
            sections = effect.custom_params.get("sections", [])
            if sections:
                params = self._pack_feedback_zones(self._sections_to_zone_strengths(sections))
            else:
                start = max(0, min(9, effect.start_position))
                end = max(start, min(9, effect.end_position))
                strength = self._force_255_to_zone_strength(effect.intensity)
                zones = [0] * 10
                for zone in range(start, end + 1):
                    zones[zone] = strength
                params = self._pack_feedback_zones(zones)

        elif effect.effect_type in (
            TriggerEffectType.WEAPON_BOW,
            TriggerEffectType.WEAPON_SINGLE,
            TriggerEffectType.WEAPON_SNIPER,
        ):
            # Modo Weapon (Rigid_AB). Esta escala SI esta confirmada por
            # documentacion de terceros sobre el SDK real de Sony:
            # startPosition y endPosition van de 0 a 9, resistiveStrength
            # va de 0 a 8 -- NO son bytes 0-255 como el resto de los
            # modos. Antes se mandaba todo en escala 0-255 aca, lo cual
            # esta mal para este modo especifico y probablemente sea la
            # razon de que se sintiera debil o directamente nada.
            start = max(0, min(9, effect.start_position))
            end = max(start + 1, min(9, effect.end_position))
            strength = max(0, min(8, round((effect.intensity / 255) * 8)))
            params = [start, end, strength]

        else:
            params = [0, effect.intensity]

        return params

    # ===== Animación en Tiempo Real =====

    def _start_animation(self) -> None:
        """Inicia un único hilo de animación, incluso con cambios simultáneos."""
        with self._lock:
            if self._animation_running or (
                self._animation_thread and self._animation_thread.is_alive()
            ):
                return
            stop_event = threading.Event()
            self._animation_stop_event = stop_event
            self._animation_running = True
            self._animation_time = 0.0
            thread = threading.Thread(
                target=self._animation_loop,
                args=(stop_event,),
                name="TriggerAnimation",
                daemon=True,
            )
            self._animation_thread = thread
        thread.start()
        logger.debug("Animacion de gatillos iniciada")

    def _stop_animation(self) -> None:
        """Detiene el hilo de animación sin intentar unirse consigo mismo."""
        with self._lock:
            self._animation_running = False
            stop_event = self._animation_stop_event
            thread = self._animation_thread
            stop_event.set()
        if thread and thread is not threading.current_thread() and thread.is_alive():
            thread.join(timeout=0.5)
        with self._lock:
            if self._animation_thread is thread and (thread is None or not thread.is_alive()):
                self._animation_thread = None

    def _animation_loop(self, stop_event: Optional[threading.Event] = None) -> None:
        """Bucle de animación con reloj monotónico y delta acotado."""
        stop_event = stop_event or self._animation_stop_event
        last_time = time.perf_counter()

        while not stop_event.is_set():
            try:
                current_time = time.perf_counter()
                # Suspender/reanudar Windows no debe saltar varios ciclos de
                # golpe ni una corrección de reloj producir tiempo negativo.
                dt = max(0.0, min(0.25, current_time - last_time))
                last_time = current_time

                with self._lock:
                    if not self._animation_running or stop_event is not self._animation_stop_event:
                        return
                    self._animation_time += dt

                    # Actualizar efectos animados
                    if (
                        self._current_left_effect
                        and self._current_left_effect.animated
                        and not self._profile_vibration_active["left"]
                        and "left" not in self._test_targets
                    ):
                        self._update_animated_effect("left", self._current_left_effect, dt)

                    if (
                        self._current_right_effect
                        and self._current_right_effect.animated
                        and not self._profile_vibration_active["right"]
                        and "right" not in self._test_targets
                    ):
                        self._update_animated_effect("right", self._current_right_effect, dt)

                stop_event.wait(1 / 60)

            except Exception as e:
                logger.error("Error en animacion: %s", e)
                stop_event.wait(0.1)

    def _update_animated_effect(self, trigger: str, effect: TriggerEffect, dt: float) -> None:
        """Actualiza un efecto animado basado en el tiempo."""
        if not self.connection_manager:
            return

        ds = self.connection_manager.dualsense_instance
        if not ds:
            return

        # Calcular progreso de la animacion (0-1 ciclico)
        cycle_duration = 2.0 / effect.animation_speed
        progress = (self._animation_time % cycle_duration) / cycle_duration

        # Aplicar curva
        curve_func = self.CURVES.get(effect.animation_curve, self.CURVES["linear"])
        curved_progress = curve_func(progress)

        # Crear efecto modificado
        modified_effect = TriggerEffect(
            name=effect.name,
            effect_type=effect.effect_type,
            intensity=int(effect.intensity * (0.3 + 0.7 * curved_progress)),
            start_position=effect.start_position,
            end_position=effect.end_position,
            frequency=int(effect.frequency * (0.5 + curved_progress))
            if effect.frequency > 0
            else 0,
            vibration_enabled=effect.vibration_enabled,
            vibration_intensity=effect.vibration_intensity,
            vibration_frequency=effect.vibration_frequency,
            vibration_start_position=effect.vibration_start_position,
            vibration_end_position=effect.vibration_end_position,
            custom_params=effect.custom_params,
        )

        # Enviar comando actualizado (throttle para no saturar Bluetooth)
        self._send_trigger_command(ds, trigger, modified_effect)

    # ===== Lectura de Posición de Gatillos =====

    def get_trigger_position(self, trigger: str) -> int:
        """
        Obtiene la posicion actual de un gatillo (0-255).
        """
        if not self.connection_manager:
            return 0

        state = self.connection_manager.state
        if trigger == "left":
            return state.left_trigger
        elif trigger == "right":
            return state.right_trigger
        return 0

    def is_trigger_pressed(self, trigger: str, threshold: int = 20) -> bool:
        """Verifica si un gatillo esta presionado mas del umbral."""
        return self.get_trigger_position(trigger) > threshold

    # ===== Utilidades =====

    def _can_send_commands(self) -> bool:
        """Verifica si se pueden enviar comandos al control."""
        return (
            self.connection_manager is not None
            and self.connection_manager.is_connected
            and self.connection_manager.dualsense_instance is not None
        )

    def _notify_effect_change(self, trigger: str, effect: TriggerEffect) -> None:
        """Notifica cambio de efecto."""
        self._notify_callbacks(self._on_effect_change, trigger, effect)

    def get_current_effects(self) -> Dict[str, Optional[TriggerEffect]]:
        """Devuelve los efectos actuales aplicados."""
        with self._lock:
            return {
                "left": self._current_left_effect,
                "right": self._current_right_effect,
            }

    def load_profiles_from_dict(self, profiles_data: Dict[str, dict]) -> None:
        """Carga perfiles desde un diccionario (para importar configuraciones)."""
        for index, (profile_id, data) in enumerate(profiles_data.items()):
            if index >= MAX_CUSTOM_TRIGGER_PROFILES:
                logger.warning("Se ignoraron perfiles adicionales por límite de seguridad")
                break
            try:
                if profile_id in self._builtin_profile_ids:
                    logger.warning(f"Se ignoro perfil personalizado con ID reservado: {profile_id}")
                    continue
                profile = WeaponProfile.from_dict(data)
                self.add_custom_profile(profile_id, profile)
            except Exception as e:
                logger.warning(f"Error cargando perfil {profile_id}: {e}")

    def export_profiles_to_dict(self) -> Dict[str, dict]:
        """Exporta todos los perfiles a diccionario (para guardar configuraciones)."""
        result = {}
        for profile_id, profile in self._profiles.items():
            result[profile_id] = profile.to_dict()
        return result

    def stop(self) -> None:
        """Detiene el motor de gatillos y limpia recursos."""
        self.stop_trigger_vibration_test(restore=False)
        self._stop_animation()
        self.reset_triggers()
        if self._connection_unsubscribe is not None:
            self._connection_unsubscribe()
            self._connection_unsubscribe = None
        logger.info("TriggerEngine detenido")
