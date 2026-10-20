"""Historial de edición acotado para interfaces de Nikaido.

Mantiene copias profundas de configuraciones pequeñas como el mapa de Nexus.
No conoce Qt ni los motores HID, por lo que se puede probar y reutilizar sin
crear dependencias entre la interfaz y el backend.
"""

from __future__ import annotations

import copy
from typing import Any, Optional


class SnapshotHistory:
    """Historial undo/redo con límite y eliminación de estados duplicados."""

    def __init__(self, limit: int = 60) -> None:
        self.limit = max(2, int(limit))
        self._undo: list[Any] = []
        self._redo: list[Any] = []
        self._current: Optional[Any] = None

    def reset(self, snapshot: Any) -> None:
        self._undo.clear()
        self._redo.clear()
        self._current = copy.deepcopy(snapshot)

    def push(self, snapshot: Any) -> bool:
        candidate = copy.deepcopy(snapshot)
        if self._current == candidate:
            return False
        if self._current is not None:
            self._undo.append(copy.deepcopy(self._current))
            if len(self._undo) > self.limit:
                del self._undo[: len(self._undo) - self.limit]
        self._current = candidate
        self._redo.clear()
        return True

    def undo(self) -> Optional[Any]:
        if not self._undo or self._current is None:
            return None
        self._redo.append(copy.deepcopy(self._current))
        self._current = self._undo.pop()
        return copy.deepcopy(self._current)

    def redo(self) -> Optional[Any]:
        if not self._redo or self._current is None:
            return None
        self._undo.append(copy.deepcopy(self._current))
        self._current = self._redo.pop()
        return copy.deepcopy(self._current)

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def current(self) -> Optional[Any]:
        return copy.deepcopy(self._current)
