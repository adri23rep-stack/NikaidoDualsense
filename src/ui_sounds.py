"""Sonidos discretos de la interfaz sin añadir dependencias al runtime."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return base / relative


def play_tip_sound() -> bool:
    """Reproduce el aviso suave del asistente sin bloquear la interfaz."""
    sound = _resource_path("assets/sounds/tip.wav")
    if not sound.is_file():
        return False
    if os.name != "nt":
        return False
    try:
        import winsound

        winsound.PlaySound(
            str(sound),
            winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
        )
        return True
    except Exception as exc:  # pragma: no cover - depende del dispositivo de audio
        logger.debug("No se pudo reproducir el consejo: %s", exc)
        return False


def stop_tip_sound() -> None:
    """Corta el aviso si todavía está sonando (p. ej. al minimizar o cerrar el consejo)."""
    if os.name != "nt":
        return
    try:
        import winsound

        winsound.PlaySound(None, winsound.SND_PURGE)
    except Exception as exc:  # pragma: no cover - depende del dispositivo de audio
        logger.debug("No se pudo detener el aviso: %s", exc)
