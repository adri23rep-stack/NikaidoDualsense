"""Configuración visual portable de Nikaido.

No importa Qt. Mantener la normalización separada permite validar preferencias,
migrar configuraciones viejas y probar presets incluso en el compilador o en
entornos donde PySide6 todavía no está instalado.
"""

from __future__ import annotations

from typing import Optional


ACCENT_PALETTES = {
    "violet": {
        "name": "Violeta Nikaido",
        "accent": "#7b3ff2",
        "accent2": "#c63ff4",
        "cyan": "#43d7ef",
        "hover": "#8c51f6",
    },
    "cyan": {
        "name": "Cian eléctrico",
        "accent": "#168fda",
        "accent2": "#43d7ef",
        "cyan": "#76f0ff",
        "hover": "#29a8ee",
    },
    "pink": {
        "name": "Rosa neón",
        "accent": "#b43fe0",
        "accent2": "#ff4fa3",
        "cyan": "#72dfff",
        "hover": "#c958e8",
    },
    "green": {
        "name": "Verde aurora",
        "accent": "#168d68",
        "accent2": "#54d67b",
        "cyan": "#55e8c3",
        "hover": "#24a879",
    },
    "orange": {
        "name": "Ámbar",
        "accent": "#c76824",
        "accent2": "#ff9b42",
        "cyan": "#ffd36e",
        "hover": "#dc7b30",
    },
}

DEFAULT_APPEARANCE = {
    "background_enabled": False,
    "background_path": "",
    "background_dim": 58,
    "background_zoom": 100,
    "background_fit": "cover",
    "background_position": "center",
    "background_vignette": 18,
    "panel_opacity": 88,
    "sidebar_opacity": 94,
    "button_opacity": 92,
    "accent_style": "violet",
    "ui_density": "comfortable",
    "reduce_motion": False,
    "sidebar_collapsed": False,
}

APPEARANCE_PRESETS = {
    "nikaido": {
        "name": "Nikaido",
        "panel_opacity": 88,
        "sidebar_opacity": 94,
        "button_opacity": 92,
        "background_dim": 58,
        "background_vignette": 18,
        "ui_density": "comfortable",
    },
    "glass": {
        "name": "Cristal",
        "panel_opacity": 68,
        "sidebar_opacity": 78,
        "button_opacity": 76,
        "background_dim": 48,
        "background_vignette": 28,
        "ui_density": "comfortable",
    },
    "focus": {
        "name": "Enfoque",
        "panel_opacity": 96,
        "sidebar_opacity": 98,
        "button_opacity": 96,
        "background_dim": 76,
        "background_vignette": 36,
        "ui_density": "comfortable",
    },
    "amoled": {
        "name": "AMOLED",
        "panel_opacity": 100,
        "sidebar_opacity": 100,
        "button_opacity": 100,
        "background_dim": 88,
        "background_vignette": 48,
        "ui_density": "compact",
    },
    "minimal": {
        "name": "Minimal",
        "panel_opacity": 82,
        "sidebar_opacity": 90,
        "button_opacity": 84,
        "background_dim": 66,
        "background_vignette": 10,
        "ui_density": "compact",
    },
}

STYLE_APPEARANCE_KEYS = (
    "panel_opacity",
    "sidebar_opacity",
    "button_opacity",
    "accent_style",
    "ui_density",
)
BACKGROUND_APPEARANCE_KEYS = (
    "background_enabled",
    "background_path",
    "background_dim",
    "background_zoom",
    "background_fit",
    "background_position",
    "background_vignette",
)


def _clamp_percent(value: object, fallback: int) -> int:
    try:
        return max(0, min(100, int(float(value))))
    except (TypeError, ValueError, OverflowError):
        return fallback


def normalize_appearance(raw: Optional[dict] = None) -> dict:
    source = raw if isinstance(raw, dict) else {}
    clean = dict(DEFAULT_APPEARANCE)
    clean["background_enabled"] = bool(
        source.get("background_enabled", clean["background_enabled"])
    )
    clean["background_path"] = str(
        source.get("background_path", clean["background_path"]) or ""
    )
    clean["reduce_motion"] = bool(source.get("reduce_motion", clean["reduce_motion"]))
    clean["sidebar_collapsed"] = bool(
        source.get("sidebar_collapsed", clean["sidebar_collapsed"])
    )
    for key in (
        "background_dim",
        "background_vignette",
        "panel_opacity",
        "sidebar_opacity",
        "button_opacity",
    ):
        clean[key] = _clamp_percent(source.get(key, clean[key]), clean[key])
    try:
        zoom = int(float(source.get("background_zoom", clean["background_zoom"])))
    except (TypeError, ValueError, OverflowError):
        zoom = int(clean["background_zoom"])
    clean["background_zoom"] = max(100, min(180, zoom))
    fit = str(source.get("background_fit", clean["background_fit"])).lower().strip()
    clean["background_fit"] = fit if fit in {"cover", "contain", "stretch"} else "cover"
    position = str(
        source.get("background_position", clean["background_position"])
    ).lower().strip()
    clean["background_position"] = (
        position if position in {"top", "center", "bottom"} else "center"
    )
    accent = str(source.get("accent_style", clean["accent_style"])).lower().strip()
    clean["accent_style"] = accent if accent in ACCENT_PALETTES else "violet"
    density = str(source.get("ui_density", clean["ui_density"])).lower().strip()
    clean["ui_density"] = density if density in {"comfortable", "compact"} else "comfortable"
    return clean


def appearance_style_signature(appearance: Optional[dict]) -> tuple[object, ...]:
    settings = normalize_appearance(appearance)
    return tuple(settings[key] for key in STYLE_APPEARANCE_KEYS)


def appearance_background_signature(appearance: Optional[dict]) -> tuple[object, ...]:
    settings = normalize_appearance(appearance)
    return tuple(settings[key] for key in BACKGROUND_APPEARANCE_KEYS)
