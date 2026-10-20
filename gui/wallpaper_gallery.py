"""Galería de fondos incluidos, compartida por el asistente y Ajustes."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QButtonGroup, QGridLayout, QSizePolicy, QToolButton, QWidget

from src.wallpapers import available_wallpapers, thumbnail_path

from .i18n import tr


class WallpaperGallery(QWidget):
    """Cuadrícula de miniaturas. Emite la clave del fondo elegido."""

    selected = Signal(str)

    def __init__(self, columns: int = 3, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._buttons: dict[str, QToolButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(False)
        self.setStyleSheet(
            "QToolButton{border:1px solid rgba(255,255,255,0.12);border-radius:10px;"
            "padding:5px;background:transparent;}"
            "QToolButton:hover{border-color:palette(highlight);}"
            "QToolButton:checked{border:2px solid palette(highlight);}"
        )
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        for index, item in enumerate(available_wallpapers()):
            button = QToolButton()
            button.setCheckable(True)
            button.setText(item.short_name)
            button.setToolTip(f"{item.name} — {item.description}")
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setIconSize(QSize(100, 56))
            button.setMinimumWidth(96)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            thumb = QPixmap(str(thumbnail_path(item)))
            if not thumb.isNull():
                button.setIcon(QIcon(thumb))
            button.setAccessibleName(f"{tr('Usar fondo')} {item.name}")
            button.clicked.connect(lambda _checked=False, key=item.key: self._pick(key))
            self._group.addButton(button)
            self._buttons[item.key] = button
            grid.addWidget(button, index // columns, index % columns)
        for column in range(columns):
            grid.setColumnStretch(column, 1)

    @property
    def is_empty(self) -> bool:
        return not self._buttons

    def set_current(self, key: str) -> None:
        for item_key, button in self._buttons.items():
            button.setChecked(item_key == key)

    def _pick(self, key: str) -> None:
        self.set_current(key)
        self.selected.emit(key)
