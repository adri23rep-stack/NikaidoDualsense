"""Biblioteca integrada de perfiles de juego de Nikaido DualSense.

Este módulo contiene únicamente datos estables y reglas de migración. No
importa Qt ni controla hardware. TriggerEngine construye los perfiles físicos a
partir de estas especificaciones y Profile Studio consume la presentación.

Los nombres de juegos se usan únicamente para identificar configuraciones no
oficiales creadas por Team Nikaido. No se incluyen logotipos, portadas ni arte
propiedad de terceros.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Tuple


PROFILE_CATALOG_REVISION = 1
DEFAULT_PROFILE_ID = "assault_rifle"

# Se conservan IDs históricos para que reglas, accesos rápidos y perfiles .Nika
# existentes sigan funcionando. El nombre visible y la configuración cambian.
VISIBLE_BUILTIN_PROFILE_IDS: Tuple[str, ...] = (
    "assault_rifle",  # Call of Duty: Warzone
    "racing",        # Forza Horizon 5
    "horror",        # Resident Evil 4
    "lmg",           # Elden Ring
    "pistol",        # EA Sports FC
    "shotgun",       # Street Fighter 6
    "off",           # Minecraft
    "bow",           # Ghost of Tsushima
)

# Perfiles incluidos en versiones anteriores que ya no se muestran. Se aceptan
# como alias para no romper configuraciones antiguas.
LEGACY_PROFILE_ALIASES: Dict[str, str] = {
    "sniper": "assault_rifle",
    "smg": "assault_rifle",
}

RESERVED_PROFILE_IDS = frozenset(VISIBLE_BUILTIN_PROFILE_IDS) | frozenset(LEGACY_PROFILE_ALIASES)


@dataclass(frozen=True)
class ProfilePresentation:
    profile_id: str
    game_name: str
    genre: str
    style: str
    cover_asset: str
    theme_id: str
    short_label: str
    sort_order: int
    disclaimer: str = "Perfil comunitario no oficial"


@dataclass(frozen=True)
class BuiltinProfileSpec:
    profile_id: str
    name: str
    description: str
    category: str
    icon: str
    tags: Tuple[str, ...]
    left_preset: str
    left_changes: Mapping[str, Any]
    right_preset: str
    right_changes: Mapping[str, Any]
    rumble_intensity: int
    macros_enabled: bool
    light_config: Mapping[str, Any]
    input_studio_config: Mapping[str, Mapping[str, Any]]
    presentation: ProfilePresentation


def _stick(
    *,
    inner: float = 0.08,
    outer: float = 0.0,
    anti: float = 0.0,
    curve: str = "linear",
    sensitivity_x: float = 1.0,
    sensitivity_y: float = 1.0,
) -> Dict[str, Any]:
    return {
        "inner_deadzone": inner,
        "outer_deadzone": outer,
        "anti_deadzone": anti,
        "curve": curve,
        "sensitivity_x": sensitivity_x,
        "sensitivity_y": sensitivity_y,
        "invert_x": False,
        "invert_y": False,
        "drift_correction": True,
        "drift_offset_x": 0.0,
        "drift_offset_y": 0.0,
    }


def _lights(
    effect: str,
    color: Tuple[int, int, int],
    secondary: Tuple[int, int, int],
    *,
    speed: float = 1.0,
    brightness: float = 0.82,
    intensity: float = 0.78,
    smoothing: float = 0.18,
) -> Dict[str, Any]:
    return {
        "effect": effect,
        "color": list(color),
        "secondary_color": list(secondary),
        "speed": speed,
        "brightness": brightness,
        "intensity": intensity,
        "direction": 1,
        "smoothing": smoothing,
        "audio_gain": 1.6,
        "audio_floor": 0.03,
        "palette": [],
        "custom_id": "",
    }


BUILTIN_PROFILE_SPECS: Tuple[BuiltinProfileSpec, ...] = (
    BuiltinProfileSpec(
        profile_id="assault_rifle",
        name="Call of Duty: Warzone",
        description=(
            "Respuesta competitiva con apuntado rápido, disparo definido y vibración reducida "
            "para mantener precisión durante sesiones largas."
        ),
        category="FPS / Competitivo",
        icon="theme:warzone",
        tags=("FPS", "Competitivo", "Respuesta rápida"),
        left_preset="soft",
        left_changes={"name": "Apuntado rápido", "start_position": 1, "end_position": 6},
        right_preset="rifle",
        right_changes={
            "name": "Disparo corto",
            "intensity": 165,
            "start_position": 1,
            "end_position": 7,
            "frequency": 38,
            "vibration_enabled": True,
            "vibration_intensity": 75,
            "vibration_frequency": 34,
            "vibration_start_position": 4,
            "vibration_end_position": 8,
        },
        rumble_intensity=58,
        macros_enabled=False,
        light_config=_lights(
            "pulse", (104, 82, 255), (45, 214, 255), speed=1.35, brightness=0.62, intensity=0.72
        ),
        input_studio_config={
            "left": _stick(inner=0.055, anti=0.02, curve="aggressive", sensitivity_x=1.08, sensitivity_y=1.08),
            "right": _stick(inner=0.04, anti=0.025, curve="aggressive", sensitivity_x=1.20, sensitivity_y=1.16),
        },
        presentation=ProfilePresentation(
            "assault_rifle", "Call of Duty: Warzone", "FPS", "Competitivo",
            "assets/profile_library/warzone.png", "warzone", "FPS / Competitivo", 10,
        ),
    ),
    BuiltinProfileSpec(
        profile_id="racing",
        name="Forza Horizon 5",
        description=(
            "Acelerador progresivo, freno firme y vibración de conducción para sentir mejor "
            "la salida de curvas sin volver pesados los controles."
        ),
        category="Carreras / Mundo abierto",
        icon="theme:forza",
        tags=("Carreras", "Conducción", "Progresivo"),
        left_preset="brake",
        left_changes={"name": "Freno progresivo", "intensity": 215},
        right_preset="accelerator",
        right_changes={"name": "Acelerador progresivo"},
        rumble_intensity=148,
        macros_enabled=False,
        light_config=_lights(
            "wave", (40, 176, 255), (255, 72, 94), speed=1.45, brightness=0.84, intensity=0.82
        ),
        input_studio_config={
            "left": _stick(inner=0.04, curve="linear", sensitivity_x=0.98, sensitivity_y=0.98),
            "right": _stick(inner=0.06, curve="exponential", sensitivity_x=0.92, sensitivity_y=0.92),
        },
        presentation=ProfilePresentation(
            "racing", "Forza Horizon 5", "Carreras", "Mundo abierto",
            "assets/profile_library/forza_horizon_5.png", "forza", "Carreras / Mundo abierto", 20,
        ),
    ),
    BuiltinProfileSpec(
        profile_id="horror",
        name="Resident Evil 4",
        description=(
            "Tensión moderada, punto de disparo marcado y luces tipo latido para una experiencia "
            "de horror inmersiva sin cansar las manos."
        ),
        category="Horror / Supervivencia",
        icon="theme:resident",
        tags=("Horror", "Supervivencia", "Inmersivo"),
        left_preset="firm",
        left_changes={"name": "Apuntado estable", "intensity": 135, "start_position": 1, "end_position": 7},
        right_preset="pistol",
        right_changes={
            "name": "Disparo de supervivencia",
            "intensity": 195,
            "vibration_intensity": 135,
            "vibration_frequency": 18,
        },
        rumble_intensity=142,
        macros_enabled=True,
        light_config=_lights(
            "heartbeat", (211, 38, 62), (112, 54, 180), speed=0.78, brightness=0.70, intensity=0.84, smoothing=0.24
        ),
        input_studio_config={
            "left": _stick(inner=0.075, curve="linear", sensitivity_x=1.0, sensitivity_y=1.0),
            "right": _stick(inner=0.055, curve="exponential", sensitivity_x=1.02, sensitivity_y=0.98),
        },
        presentation=ProfilePresentation(
            "horror", "Resident Evil 4", "Horror", "Supervivencia",
            "assets/profile_library/resident_evil_4.png", "resident", "Horror / Supervivencia", 30,
        ),
    ),
    BuiltinProfileSpec(
        profile_id="lmg",
        name="Elden Ring",
        description=(
            "Resistencia equilibrada y vibración contundente para combate cuerpo a cuerpo, "
            "esquivas y ataques cargados en un RPG de acción."
        ),
        category="RPG / Acción",
        icon="theme:elden",
        tags=("RPG", "Acción", "Combate"),
        left_preset="progressive",
        left_changes={"name": "Guardia progresiva", "intensity": 150},
        right_preset="wall",
        right_changes={
            "name": "Ataque cargado",
            "intensity": 205,
            "start_position": 5,
            "end_position": 8,
            "vibration_enabled": True,
            "vibration_intensity": 150,
            "vibration_frequency": 14,
            "vibration_start_position": 7,
            "vibration_end_position": 9,
        },
        rumble_intensity=168,
        macros_enabled=False,
        light_config=_lights(
            "aurora", (178, 118, 42), (133, 73, 206), speed=0.92, brightness=0.78, intensity=0.76
        ),
        input_studio_config={
            "left": _stick(inner=0.07, curve="linear", sensitivity_x=1.03, sensitivity_y=1.03),
            "right": _stick(inner=0.065, curve="exponential", sensitivity_x=0.98, sensitivity_y=0.98),
        },
        presentation=ProfilePresentation(
            "lmg", "Elden Ring", "RPG", "Acción",
            "assets/profile_library/elden_ring.png", "elden", "RPG / Acción", 40,
        ),
    ),
    BuiltinProfileSpec(
        profile_id="pistol",
        name="EA Sports FC",
        description=(
            "Palanca izquierda ágil, gatillos libres y vibración ligera para cambios de dirección, "
            "pases rápidos y partidos competitivos."
        ),
        category="Deportes / Fútbol",
        icon="theme:fc",
        tags=("Deportes", "Fútbol", "Ágil"),
        left_preset="free",
        left_changes={"name": "L2 libre"},
        right_preset="free",
        right_changes={"name": "R2 libre"},
        rumble_intensity=46,
        macros_enabled=False,
        light_config=_lights(
            "static", (39, 211, 113), (55, 190, 255), brightness=0.64, intensity=0.58
        ),
        input_studio_config={
            "left": _stick(inner=0.045, anti=0.02, curve="aggressive", sensitivity_x=1.14, sensitivity_y=1.14),
            "right": _stick(inner=0.08, curve="linear", sensitivity_x=1.0, sensitivity_y=1.0),
        },
        presentation=ProfilePresentation(
            "pistol", "EA Sports FC", "Deportes", "Fútbol",
            "assets/profile_library/ea_sports_fc.png", "fc", "Deportes / Fútbol", 50,
        ),
    ),
    BuiltinProfileSpec(
        profile_id="shotgun",
        name="Street Fighter 6",
        description=(
            "Entrada inmediata, gatillos libres y vibración mínima para que combos y movimientos "
            "dependan únicamente de tu ejecución."
        ),
        category="Peleas / Arcade",
        icon="theme:fighter",
        tags=("Peleas", "Arcade", "Respuesta inmediata"),
        left_preset="free",
        left_changes={"name": "L2 libre"},
        right_preset="free",
        right_changes={"name": "R2 libre"},
        rumble_intensity=28,
        macros_enabled=False,
        light_config=_lights(
            "comet", (239, 57, 194), (42, 213, 255), speed=1.65, brightness=0.72, intensity=0.74
        ),
        input_studio_config={
            "left": _stick(inner=0.035, anti=0.025, curve="aggressive", sensitivity_x=1.18, sensitivity_y=1.18),
            "right": _stick(inner=0.05, curve="aggressive", sensitivity_x=1.10, sensitivity_y=1.10),
        },
        presentation=ProfilePresentation(
            "shotgun", "Street Fighter 6", "Peleas", "Arcade",
            "assets/profile_library/street_fighter_6.png", "fighter", "Peleas / Arcade", 60,
        ),
    ),
    BuiltinProfileSpec(
        profile_id="off",
        name="Minecraft",
        description=(
            "Controles suaves, iluminación tranquila y vibración ligera para explorar, construir y "
            "jugar durante mucho tiempo sin fatiga."
        ),
        category="Sandbox / Exploración",
        icon="theme:minecraft",
        tags=("Sandbox", "Exploración", "Relajado"),
        left_preset="soft",
        left_changes={"name": "L2 suave"},
        right_preset="soft",
        right_changes={"name": "R2 suave"},
        rumble_intensity=52,
        macros_enabled=True,
        light_config=_lights(
            "breathe", (76, 185, 91), (70, 168, 238), speed=0.72, brightness=0.60, intensity=0.60, smoothing=0.24
        ),
        input_studio_config={
            "left": _stick(inner=0.08, curve="linear", sensitivity_x=1.0, sensitivity_y=1.0),
            "right": _stick(inner=0.075, curve="linear", sensitivity_x=0.96, sensitivity_y=0.96),
        },
        presentation=ProfilePresentation(
            "off", "Minecraft", "Sandbox", "Exploración",
            "assets/profile_library/minecraft.png", "minecraft", "Sandbox / Exploración", 70,
        ),
    ),
    BuiltinProfileSpec(
        profile_id="bow",
        name="Ghost of Tsushima",
        description=(
            "Tensión de arco, respuesta cinematográfica y una identidad verde ambiental para combate, "
            "sigilo y exploración de acción."
        ),
        category="Acción / Aventura",
        icon="theme:ghost",
        tags=("Acción", "Aventura", "Arquería"),
        left_preset="firm",
        left_changes={"name": "Apuntado estable", "intensity": 125, "start_position": 1, "end_position": 6},
        right_preset="bow",
        right_changes={"name": "Tensión de arco", "animated": False},
        rumble_intensity=124,
        macros_enabled=True,
        light_config=_lights(
            "aurora", (50, 209, 112), (54, 190, 174), speed=0.88, brightness=0.72, intensity=0.72, smoothing=0.22
        ),
        input_studio_config={
            "left": _stick(inner=0.065, curve="linear", sensitivity_x=1.03, sensitivity_y=1.03),
            "right": _stick(inner=0.055, curve="exponential", sensitivity_x=1.0, sensitivity_y=0.98),
        },
        presentation=ProfilePresentation(
            "bow", "Ghost of Tsushima", "Acción", "Aventura",
            "assets/profile_library/ghost_of_tsushima.png", "ghost", "Acción / Aventura", 80,
        ),
    ),
)


BUILTIN_PROFILE_SPEC_BY_ID: Dict[str, BuiltinProfileSpec] = {
    spec.profile_id: spec for spec in BUILTIN_PROFILE_SPECS
}
PROFILE_PRESENTATION_BY_ID: Dict[str, ProfilePresentation] = {
    spec.profile_id: spec.presentation for spec in BUILTIN_PROFILE_SPECS
}


def canonical_profile_id(profile_id: Any) -> str:
    value = str(profile_id or "").strip()
    return LEGACY_PROFILE_ALIASES.get(value, value)


def is_visible_builtin(profile_id: Any) -> bool:
    return canonical_profile_id(profile_id) in BUILTIN_PROFILE_SPEC_BY_ID


def profile_presentation(profile_id: Any) -> ProfilePresentation | None:
    return PROFILE_PRESENTATION_BY_ID.get(canonical_profile_id(profile_id))


def builtin_profile_spec(profile_id: Any) -> BuiltinProfileSpec | None:
    return BUILTIN_PROFILE_SPEC_BY_ID.get(canonical_profile_id(profile_id))


def ordered_builtin_ids() -> Tuple[str, ...]:
    return tuple(
        item.profile_id
        for item in sorted(BUILTIN_PROFILE_SPECS, key=lambda spec: spec.presentation.sort_order)
    )


def remap_profile_id_list(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    for raw in values:
        mapped = canonical_profile_id(raw)
        if mapped and mapped not in result:
            result.append(mapped)
    return result


def clone_spec_payload(spec: BuiltinProfileSpec) -> Dict[str, Any]:
    """Devuelve una copia mutable para construir WeaponProfile sin fugas."""
    return {
        "profile_id": spec.profile_id,
        "name": spec.name,
        "description": spec.description,
        "category": spec.category,
        "icon": spec.icon,
        "tags": list(spec.tags),
        "left_preset": spec.left_preset,
        "left_changes": copy.deepcopy(dict(spec.left_changes)),
        "right_preset": spec.right_preset,
        "right_changes": copy.deepcopy(dict(spec.right_changes)),
        "rumble_intensity": spec.rumble_intensity,
        "macros_enabled": spec.macros_enabled,
        "light_config": copy.deepcopy(dict(spec.light_config)),
        "input_studio_config": copy.deepcopy(dict(spec.input_studio_config)),
    }
