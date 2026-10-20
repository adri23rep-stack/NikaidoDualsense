"""Asistente contextual de Nikaido dentro de la ventana principal."""

from __future__ import annotations

from .ui_common import (
    Callable, QApplication, QLabel, QFrame, QHBoxLayout, QPixmap, QPushButton,
    QVBoxLayout, QWidget, Qt,
)
from .components import MascotPanel, load_scaled_pixmap


def window_is_in_front(window: QWidget) -> bool:
    """True solo si la ventana está realmente a la vista y en uso.

    ``isVisible()`` sigue siendo True con la ventana minimizada, y en Windows el
    estado de minimizado puede llegar tarde. Por eso se exige también que la
    ventana esté activa: minimizada, en la bandeja, detrás de un juego o con otra
    app al frente no debe sonar nada.
    """
    if getattr(window, "_stopping", False) or not window.isVisible() or window.isMinimized():
        return False
    if window.windowState() & Qt.WindowState.WindowMinimized:
        return False
    app = QApplication.instance()
    if app is None or app.applicationState() != Qt.ApplicationState.ApplicationActive:
        return False
    return bool(window.isActiveWindow())


class AssistantTipCard(QFrame):
    """Aviso compacto y reutilizable de Nikaido dentro de la ventana principal."""

    def __init__(
        self,
        parent: QWidget,
        *,
        on_close: Callable[[], None],
        on_open: Callable[[str], None],
    ) -> None:
        super().__init__(parent)
        self.setObjectName("assistantTipCard")
        self.setMinimumWidth(430)
        self.setMaximumWidth(470)
        self._on_close = on_close
        self._on_open = on_open
        self._destination = ""
        self._source = QPixmap()
        self._pose = ""

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        self.sprite = QLabel()
        self.sprite.setObjectName("assistantTipSprite")
        self.sprite.setFixedSize(122, 142)
        self.sprite.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom)
        root.addWidget(self.sprite, 0, Qt.AlignmentFlag.AlignBottom)

        content = QVBoxLayout()
        content.setSpacing(5)
        header = QHBoxLayout()
        self.badge = QLabel("CONSEJO")
        self.badge.setObjectName("mascotBadge")
        header.addWidget(self.badge)
        header.addStretch()
        close = QPushButton("×")
        close.setProperty("iconButton", True)
        close.setFixedSize(27, 27)
        close.setToolTip("Cerrar consejo")
        close.clicked.connect(self._on_close)
        header.addWidget(close)
        content.addLayout(header)

        self.title = QLabel("Consejo de Nikaido")
        self.title.setObjectName("mascotTitle")
        self.title.setWordWrap(True)
        content.addWidget(self.title)
        self.message = QLabel()
        self.message.setObjectName("mascotMessage")
        self.message.setWordWrap(True)
        content.addWidget(self.message)
        content.addStretch()

        actions = QHBoxLayout()
        actions.addStretch()
        self.open_button = QPushButton("Abrir")
        self.open_button.setProperty("primary", True)
        self.open_button.clicked.connect(self._open_destination)
        actions.addWidget(self.open_button)
        content.addLayout(actions)
        root.addLayout(content, 1)
        self.hide()

    def set_tip(
        self, pose: str, title: str, message: str, destination: str = "",
        action_label: str = "Abrir", badge: str = "CONSEJO",
    ) -> None:
        self.badge.setText(str(badge).upper())
        self.title.setText(str(title))
        self.message.setText(str(message))
        self._destination = str(destination or "")
        self.open_button.setText(str(action_label or "Abrir"))
        self.open_button.setVisible(bool(self._destination))
        normalized = str(pose) if str(pose) in MascotPanel.POSES else "compact_explaining"
        if normalized != self._pose or self._source.isNull():
            self._pose = normalized
            path = MascotPanel.asset_path(normalized)
            self._source = load_scaled_pixmap(str(path), 122, 142)
        self.sprite.setPixmap(self._source)
        self.sprite.setText("" if not self._source.isNull() else "N")

    def clear_resources(self) -> None:
        self._source = QPixmap()
        self._pose = ""
        self.sprite.clear()

    def _open_destination(self) -> None:
        if self._destination:
            self._on_open(self._destination)


