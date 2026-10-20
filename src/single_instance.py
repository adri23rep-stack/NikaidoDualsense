"""Protección contra dos instancias de Nikaido usando el mismo DualSense."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional


class SingleInstance:
    def __init__(self, name: str = "NikaidoDualSense", lock_dir: Optional[str] = None) -> None:
        safe = "".join(ch for ch in str(name) if ch.isalnum() or ch in "_-.") or "Nikaido"
        self.name = safe
        self.lock_dir = Path(lock_dir or tempfile.gettempdir())
        self._handle = None
        self._file = None
        self.acquired = False

    def acquire(self) -> bool:
        if self.acquired:
            return True
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32
            create_mutex = kernel32.CreateMutexW
            create_mutex.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
            create_mutex.restype = wintypes.HANDLE
            close_handle = kernel32.CloseHandle
            close_handle.argtypes = [wintypes.HANDLE]
            close_handle.restype = wintypes.BOOL

            handle = create_mutex(None, False, f"Local\\{self.name}")
            if not handle:
                return False
            already_exists = kernel32.GetLastError() == 183
            if already_exists:
                close_handle(handle)
                return False
            self._handle = handle
            self.acquired = True
            return True

        self.lock_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.lock_dir / f"{self.name}.lock"
        stream = open(lock_path, "a+", encoding="utf-8")
        try:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (ImportError, OSError):
            stream.close()
            return False
        stream.seek(0)
        stream.truncate()
        stream.write(str(os.getpid()))
        stream.flush()
        self._file = stream
        self.acquired = True
        return True

    def release(self) -> None:
        if not self.acquired:
            return
        if os.name == "nt" and self._handle:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32
            release_mutex = kernel32.ReleaseMutex
            release_mutex.argtypes = [wintypes.HANDLE]
            release_mutex.restype = wintypes.BOOL
            close_handle = kernel32.CloseHandle
            close_handle.argtypes = [wintypes.HANDLE]
            close_handle.restype = wintypes.BOOL
            release_mutex(self._handle)
            close_handle(self._handle)
            self._handle = None
        elif self._file is not None:
            try:
                import fcntl

                fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
            except (ImportError, OSError):
                pass
            self._file.close()
            self._file = None
        self.acquired = False

    def __enter__(self) -> "SingleInstance":
        if not self.acquire():
            raise RuntimeError("Nikaido ya está en ejecución")
        return self

    def __exit__(self, *_args: object) -> None:
        self.release()


def notify_already_running() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            None,
            "Nikaido DualSense ya está abierto. Revisa la bandeja del sistema.",
            "Nikaido DualSense",
            0x00000040,
        )
    except Exception:
        pass
