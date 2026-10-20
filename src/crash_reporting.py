"""Reporte local de errores inesperados sin enviar datos por internet."""

from __future__ import annotations

import logging
import os
import platform
import sys
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import Callable, Optional, Type

from .security_utils import harden_private_file, redact_private_text

logger = logging.getLogger(__name__)

def show_fatal_error(message: str, *, title: str = "Nikaido DualSense") -> bool:
    """Muestra un error visible incluso en el EXE compilado sin consola."""
    text = str(message or "Nikaido encontró un error inesperado.")
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, text, str(title), 0x00000010)
            return True
        except Exception:
            pass
    try:
        stream = sys.stderr or sys.__stderr__
        if stream is not None:
            stream.write(f"{title}: {text}\n")
            stream.flush()
            return True
    except Exception:
        pass
    return False


def install_exception_hook(
    directory: Path,
    *,
    app_version: str,
    keep: int = 5,
) -> Callable[[Type[BaseException], BaseException, Optional[TracebackType]], None]:
    """Captura errores del hilo principal y workers sin enviar datos fuera."""
    reporting_available = True
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        reporting_available = False
        logger.warning(
            "La carpeta de reportes no está disponible; el hook seguirá activo: %s",
            exc,
        )
    original = sys.excepthook
    original_thread = getattr(threading, "excepthook", None)

    def write_report(
        exc_type: Type[BaseException],
        exc_value: BaseException,
        exc_tb: Optional[TracebackType],
        *,
        thread_name: str = "main",
    ) -> Optional[Path]:
        if not reporting_available:
            return None
        timestamp = datetime.now(timezone.utc)
        report = directory / f"crash_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.txt"
        content = [
            "Nikaido DualSense — reporte local de error",
            f"Version: {app_version}",
            f"UTC: {timestamp.isoformat()}",
            f"Python: {platform.python_version()}",
            f"Windows: {platform.platform()}",
            f"Proceso: {os.getpid()}",
            f"Hilo: {thread_name}",
            "",
            redact_private_text(
                "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            ),
        ]
        try:
            report.write_text("\n".join(content), encoding="utf-8")
            harden_private_file(report)
            reports = sorted(directory.glob("crash_*.txt"), reverse=True)
            for old in reports[max(1, int(keep)):]:
                old.unlink(missing_ok=True)
            return report
        except OSError:
            return None

    def hook(
        exc_type: Type[BaseException],
        exc_value: BaseException,
        exc_tb: Optional[TracebackType],
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            original(exc_type, exc_value, exc_tb)
            return
        report = write_report(exc_type, exc_value, exc_tb)
        logger.critical(
            "Error no controlado. Reporte: %s",
            report or "no disponible",
            exc_info=(exc_type, exc_value, exc_tb),
        )

    def thread_hook(args) -> None:
        if issubclass(args.exc_type, KeyboardInterrupt):
            if original_thread:
                original_thread(args)
            return
        thread_name = getattr(getattr(args, "thread", None), "name", "worker")
        report = write_report(
            args.exc_type,
            args.exc_value,
            args.exc_traceback,
            thread_name=thread_name,
        )
        logger.critical(
            "Error no controlado en %s. Reporte: %s",
            thread_name,
            report or "no disponible",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = hook
    if hasattr(threading, "excepthook"):
        threading.excepthook = thread_hook
    return hook
