"""Fondos de pantalla incluidos con Nikaido.

Todos son imágenes satelitales de Landsat (dominio público) recopiladas por
Leonardo Uieda y publicadas bajo CC0. Ver ``assets/wallpapers/CREDITS.txt``.
Este módulo no depende de Qt para poder probarse sin interfaz.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BundledWallpaper:
    key: str
    name: str
    short_name: str
    description: str
    filename: str


BUNDLED_WALLPAPERS: tuple[BundledWallpaper, ...] = (
    BundledWallpaper("roraima", "Monte Roraima", "Roraima", "Tepuy en la frontera Venezuela-Brasil-Guyana", "roraima.jpg"),
    BundledWallpaper("amazon-delta", "Delta del Amazonas", "Amazonas", "Desembocadura del río Amazonas", "amazon-delta.jpg"),
    BundledWallpaper("vale-do-pati", "Valle del Pati", "Pati", "Chapada Diamantina, Brasil", "vale-do-pati.jpg"),
    BundledWallpaper("villarrica", "Volcán Villarrica", "Villarrica", "Los Andes, Chile", "villarrica.jpg"),
    BundledWallpaper("lencois", "Lençóis Maranhenses", "Lençóis", "Dunas y lagunas del norte de Brasil", "lencois.jpg"),
    BundledWallpaper("neuquen", "Neuquén", "Neuquén", "Patagonia argentina", "neuquen.jpg"),
)


def wallpapers_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return base / "assets" / "wallpapers"


def image_path(wallpaper: BundledWallpaper) -> Path:
    return wallpapers_dir() / wallpaper.filename


def thumbnail_path(wallpaper: BundledWallpaper) -> Path:
    return wallpapers_dir() / "thumbs" / wallpaper.filename


def available_wallpapers() -> list[BundledWallpaper]:
    """Solo los fondos cuyo archivo existe, para no mostrar botones rotos."""
    return [item for item in BUNDLED_WALLPAPERS if image_path(item).is_file()]


def find_wallpaper(key: str) -> BundledWallpaper | None:
    for item in BUNDLED_WALLPAPERS:
        if item.key == key:
            return item
    return None
