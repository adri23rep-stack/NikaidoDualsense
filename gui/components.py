"""BackendBridge, BackgroundRoot, AppearancePreview, SidebarNavButton, TitleBar, CommandPalette, ControllerVisual, LatencyGraph, StickScope, ResponseCurveEditor, SliderRow, KeyCaptureButton, MascotPanel, ScrollPage, PageLoadError extraídos de la antigua interfaz monolítica."""

from __future__ import annotations

from typing import TYPE_CHECKING


from .i18n import tr

from .ui_common import (
    logging,
    ACCENT_PALETTES,
    APPEARANCE_PRESETS,
    Any,
    C,
    Callable,
    Dict,
    List,
    Optional,
    Path,
    QColor,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFont,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QImageReader,
    QKeySequence,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMouseEvent,
    QObject,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPoint,
    QPointF,
    QPushButton,
    QRadialGradient,
    QRectF,
    QScrollArea,
    QSize,
    QSlider,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
    button,
    card,
    deque,
    label,
    normalize_appearance,
    resource_path,
)

from .curve_editor import ResponseCurveEditor  # noqa: F401 -- reexport público

if TYPE_CHECKING:
    from .main_window import NikaidoWindow

logger = logging.getLogger(__name__)

def load_scaled_pixmap(path: str, width: int, height: int) -> QPixmap:
    """Carga una miniatura sin decodificar primero la imagen completa."""
    reader = QImageReader(str(path)); reader.setAutoTransform(True)
    source, target = reader.size(), QSize(max(1, int(width)), max(1, int(height)))
    if source.isValid():
        decoded = source.scaled(target, Qt.AspectRatioMode.KeepAspectRatio)
        if decoded.width() < source.width() or decoded.height() < source.height():
            reader.setScaledSize(decoded)
    image = reader.read()
    if image.isNull():
        return QPixmap()
    return QPixmap.fromImage(image).scaled(
        target, Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )

class BackendBridge(QObject):
    connected = Signal(object)
    disconnected = Signal()
    battery = Signal(int, object)
    state = Signal(object)
    profile = Signal(str)
    error = Signal(str)
    show_requested = Signal()
    exit_requested = Signal()
    profile_requested = Signal(str)
    update_checked = Signal(object)
    update_progress = Signal(int)
    update_downloaded = Signal(object, str)


class BackgroundRoot(QWidget):
    """Lienzo de fondo con caché estable, ajuste de imagen y viñeta opcional."""

    # Evita decodificar una fotografía 4K completa para una ventana menor.
    IMAGE_DECODE_LIMIT = QSize(2560, 1600)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("root")
        self._appearance = normalize_appearance()
        self._pixmap = QPixmap()
        self._scaled_cache = QPixmap()
        self._cache_key: Optional[tuple[Any, ...]] = None
        self._source_fingerprint: Optional[tuple[str, int, int]] = None

    @staticmethod
    def _fingerprint(path: str) -> Optional[tuple[str, int, int]]:
        if not path:
            return None
        try:
            source = Path(path)
            stat = source.stat()
            return str(source.resolve()), int(stat.st_mtime_ns), int(stat.st_size)
        except OSError:
            return None

    def _load_pixmap(self, path: str) -> QPixmap:
        """Decodifica la imagen cerca del tamaño máximo que realmente usamos."""
        if not path:
            return QPixmap()
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        source_size = reader.size()
        limit = self.IMAGE_DECODE_LIMIT
        if source_size.isValid() and limit.isValid():
            target = source_size.scaled(limit, Qt.AspectRatioMode.KeepAspectRatio)
            if target.width() < source_size.width() or target.height() < source_size.height():
                reader.setScaledSize(target)
        image = reader.read()
        return QPixmap.fromImage(image) if not image.isNull() else QPixmap()

    def release_image_cache(self) -> None:
        """Suelta inmediatamente fondos y escalados de vistas que ya se cerraron."""
        self._pixmap = QPixmap()
        self._scaled_cache = QPixmap()
        self._cache_key = None
        self._source_fingerprint = None
        self.update()

    def set_appearance(self, appearance: Optional[Dict[str, Any]]) -> None:
        previous = self._appearance
        current = normalize_appearance(appearance)
        self._appearance = current

        fingerprint = self._fingerprint(current.get("background_path", ""))
        if fingerprint != self._source_fingerprint:
            self._source_fingerprint = fingerprint
            path = fingerprint[0] if fingerprint else ""
            self._pixmap = self._load_pixmap(path) if path else QPixmap()
            self._scaled_cache = QPixmap()
            self._cache_key = None

        previous_geometry = (
            previous.get("background_zoom"), previous.get("background_fit")
        )
        current_geometry = (
            current.get("background_zoom"), current.get("background_fit")
        )
        if previous_geometry != current_geometry:
            self._scaled_cache = QPixmap()
            self._cache_key = None
        self.update()

    def _scaled_background(self) -> QPixmap:
        if self._pixmap.isNull() or self.width() <= 0 or self.height() <= 0:
            return QPixmap()
        zoom = max(1.0, float(self._appearance.get("background_zoom", 100)) / 100.0)
        target_size = QSize(
            max(1, round(self.width() * zoom)),
            max(1, round(self.height() * zoom)),
        )
        fit = str(self._appearance.get("background_fit", "cover"))
        mode = {
            "contain": Qt.AspectRatioMode.KeepAspectRatio,
            "stretch": Qt.AspectRatioMode.IgnoreAspectRatio,
        }.get(fit, Qt.AspectRatioMode.KeepAspectRatioByExpanding)
        cache_key = (
            target_size.width(), target_size.height(), fit, self._source_fingerprint
        )
        if cache_key != self._cache_key or self._scaled_cache.isNull():
            self._scaled_cache = self._pixmap.scaled(
                target_size, mode, Qt.TransformationMode.SmoothTransformation
            )
            self._cache_key = cache_key
        return self._scaled_cache

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor(C["bg"]))
        enabled = bool(self._appearance.get("background_enabled"))
        if enabled:
            scaled = self._scaled_background()
            if not scaled.isNull():
                x = round((self.width() - scaled.width()) / 2)
                position = str(self._appearance.get("background_position", "center"))
                if position == "top":
                    y = 0
                elif position == "bottom":
                    y = self.height() - scaled.height()
                else:
                    y = round((self.height() - scaled.height()) / 2)
                painter.drawPixmap(x, y, scaled)

                dim = max(0, min(100, int(self._appearance.get("background_dim", 58))))
                painter.fillRect(self.rect(), QColor(4, 7, 15, round(255 * dim / 100)))

                vignette = max(0, min(100, int(self._appearance.get("background_vignette", 18))))
                if vignette:
                    radius = max(self.width(), self.height()) * 0.78
                    gradient = QRadialGradient(
                        QPointF(self.width() / 2.0, self.height() / 2.0), radius
                    )
                    gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
                    gradient.setColorAt(0.62, QColor(0, 0, 0, 0))
                    gradient.setColorAt(1.0, QColor(0, 0, 0, round(210 * vignette / 100)))
                    painter.fillRect(self.rect(), gradient)
        painter.end()


class AppearancePreview(BackgroundRoot):
    """Vista previa ligera que imita tarjetas y botones del tema actual."""

    IMAGE_DECODE_LIMIT = QSize(640, 440)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(320, 190)
        self.setMaximumHeight(220)

    def paintEvent(self, event: Any) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        settings = normalize_appearance(self._appearance)
        palette = ACCENT_PALETTES[settings["accent_style"]]

        panel = QColor(C["panel"])
        panel.setAlpha(round(255 * settings["panel_opacity"] / 100))
        button_color = QColor(C["panel2"])
        button_color.setAlpha(round(255 * settings["button_opacity"] / 100))

        outer = QRectF(18, 18, max(1, self.width() - 36), max(1, self.height() - 36))
        painter.setBrush(panel)
        painter.setPen(QPen(QColor(C["border"]), 1))
        painter.drawRoundedRect(outer, 14, 14)

        accent = QColor(palette["accent"])
        painter.setBrush(accent)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(34, 36, 42, 42), 11, 11)
        font = painter.font()
        logo = QPixmap(str(resource_path("assets/nikaido.svg")))
        if not logo.isNull():
            painter.drawPixmap(QRectF(34, 36, 42, 42).toRect(), logo)
        else:
            painter.setPen(QColor("white"))
            font.setBold(True)
            font.setPointSize(13)
            painter.setFont(font)
            painter.drawText(QRectF(34, 36, 42, 42), Qt.AlignmentFlag.AlignCenter, "N")

        painter.setPen(QColor(C["text"]))
        font.setBold(True)
        font.setPointSize(11)
        painter.setFont(font)
        painter.drawText(QRectF(88, 34, self.width() - 120, 24), Qt.AlignmentFlag.AlignLeft, "Nikaido")
        painter.setPen(QColor(C["muted"]))
        font.setBold(False)
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(QRectF(88, 57, self.width() - 120, 20), Qt.AlignmentFlag.AlignLeft, tr("Vista previa del tema"))

        painter.setBrush(button_color)
        painter.setPen(QPen(QColor(C["border"]), 1))
        painter.drawRoundedRect(QRectF(34, self.height() - 70, 112, 34), 8, 8)
        painter.setPen(QColor(C["text"]))
        font.setBold(True)
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(QRectF(34, self.height() - 70, 112, 34), Qt.AlignmentFlag.AlignCenter, tr("Botón"))

        painter.setBrush(accent)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(156, self.height() - 70, 126, 34), 8, 8)
        painter.setPen(QColor("white"))
        painter.drawText(QRectF(156, self.height() - 70, 126, 34), Qt.AlignmentFlag.AlignCenter, tr("Acción principal"))
        painter.end()


class SidebarNavButton(QPushButton):
    """Botón de navegación con icono, título y subtítulo en un formato más limpio."""

    def __init__(self, icon: str, title: str, subtitle: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("nav", True)
        self.setProperty("hasSubtitle", bool(subtitle))
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(64 if subtitle else 50)
        self.setToolTip(f"{title} · {subtitle}" if subtitle else title)
        self.setAccessibleName(f"{title} {subtitle}".strip())
        self.setText("")

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(10)

        self.icon_label = QLabel(icon)
        self.icon_label.setObjectName("navIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(28, 28)
        row.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("navTitle")
        text_col.addWidget(self.title_label)
        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setObjectName("navSubtitle")
            self.subtitle_label.setWordWrap(True)
            text_col.addWidget(self.subtitle_label)
        else:
            self.subtitle_label = None
        row.addLayout(text_col, 1)

        self.arrow_label = QLabel("›")
        self.arrow_label.setObjectName("navArrow")
        self.arrow_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.arrow_label.setFixedWidth(16)
        row.addWidget(self.arrow_label, 0, Qt.AlignmentFlag.AlignVCenter)
        self._row_layout = row
        self._has_subtitle = bool(subtitle)

    def set_compact(self, compact: bool) -> None:
        compact = bool(compact)
        self.title_label.setVisible(not compact)
        if self.subtitle_label is not None:
            self.subtitle_label.setVisible(not compact)
        self.arrow_label.setVisible(not compact)
        self._row_layout.setContentsMargins(12 if not compact else 10, 10, 12 if not compact else 10, 10)
        self._row_layout.setSpacing(10 if not compact else 0)
        self.setMinimumHeight(64 if self._has_subtitle and not compact else 50)
        self.setAccessibleDescription(self.toolTip())


class TitleBar(QFrame):
    def __init__(self, window: "NikaidoWindow") -> None:
        super().__init__()
        self.window = window
        self._drag_pos: Optional[QPoint] = None
        self.setObjectName("topbar")
        self.setFixedHeight(82)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 10, 16, 10)

        home = QPushButton("⌂")
        home.setProperty("homeButton", True)
        home.setAccessibleName("Ir al Dashboard")
        home.setToolTip("Ir al Dashboard")
        home.setCursor(Qt.CursorShape.PointingHandCursor)
        home.setFixedSize(44, 44)
        home.clicked.connect(lambda: window.navigate("dashboard"))
        layout.addWidget(home)

        titles = QVBoxLayout()
        titles.setSpacing(1)
        self.title = label("Dashboard", "title")
        self.subtitle = label(
            "Resumen general de tu controlador y perfil activo", "muted"
        )
        titles.addWidget(self.title)
        titles.addWidget(self.subtitle)
        layout.addLayout(titles)
        layout.addStretch()

        profile_box = QVBoxLayout()
        profile_box.setSpacing(0)
        profile_box.addWidget(label("Perfil activo", "muted"))
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(190)
        self.profile_combo.currentIndexChanged.connect(self._profile_changed)
        profile_box.addWidget(self.profile_combo)
        layout.addLayout(profile_box)

        for text, tooltip, slot in (
            ("⌕", "Buscar en Nikaido · Ctrl+K", window.show_command_palette),
            ("⚙", "Abrir ajustes", lambda: window.navigate("settings")),
            ("−", "Minimizar", window.request_minimize),
            ("□", "Maximizar o restaurar", window.toggle_maximize),
            ("×", "Cerrar", window.request_close),
        ):
            btn = QPushButton(text)
            btn.setProperty("iconButton", True)
            btn.setProperty("windowClose", text == "×")
            btn.setAccessibleName(tooltip)
            btn.setToolTip(tooltip)
            btn.setFixedSize(38, 38)
            btn.clicked.connect(slot)
            layout.addWidget(btn)

    def _profile_changed(self, index: int) -> None:
        profile_id = self.profile_combo.itemData(index)
        if profile_id and self.window.trigger_engine:
            self.window.apply_profile(str(profile_id))

    def set_profiles(
        self, profiles: List[tuple[str, str]], active: Optional[str]
    ) -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        active_index = 0
        for index, (profile_id, name) in enumerate(profiles):
            self.profile_combo.addItem(name, profile_id)
            if profile_id == active:
                active_index = index
        self.profile_combo.setCurrentIndex(active_index)
        self.profile_combo.blockSignals(False)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self._drag_pos is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and not self.window.isMaximized()
        ):
            self.window.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, _event: QMouseEvent) -> None:
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.window.toggle_maximize()


class CommandPalette(QDialog):
    """Buscador global para navegar y ejecutar acciones frecuentes."""

    def __init__(self, window: "NikaidoWindow") -> None:
        super().__init__(window)
        self.window = window
        self.setWindowTitle("Buscar en Nikaido")
        self.setModal(True)
        self.setMinimumSize(560, 430)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)
        root.addWidget(label("BÚSQUEDA RÁPIDA", "eyebrow"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Escribe una sección o acción…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        self.search.returnPressed.connect(self.activate_current)
        root.addWidget(self.search)
        self.results = QListWidget()
        self.results.itemDoubleClicked.connect(lambda _item: self.activate_current())
        root.addWidget(self.results, 1)
        hint = label("Enter para abrir · Esc para cerrar · Ctrl+K desde cualquier pantalla", "muted")
        root.addWidget(hint)
        self._entries: List[tuple[str, str, str, Callable[[], None]]] = []
        self._build_entries()
        self.refresh()

    def _build_entries(self) -> None:
        self._entries.clear()
        icons = {
            "dashboard": "⌂", "profiles": "♧", "monitor": "▣", "mapper": "⌘",
            "input": "◎", "gyro": "◉", "macros": "⌁", "lights": "☼",
            "vibration": "◌", "triggers": "↯", "audio": "♬", "emulation": "◆",
            "calibration": "◫", "tools": "⌁", "settings": "⚙",
        }
        for key in self.window.PAGE_META:
            title, subtitle = self.window.page_meta(key)
            self._entries.append(
                (f"{icons.get(key, '•')}  {title}", subtitle, f"{title} {subtitle} {key}", lambda page=key: self.window.navigate(page))
            )

        trigger = self.window.trigger_engine
        if trigger:
            for profile_id, profile_name in trigger.get_profile_names():
                self._entries.append(
                    (
                        f"♧  {tr('Aplicar', self.window.language)} {profile_name}",
                        tr("Cambiar el perfil activo", self.window.language),
                        f"perfil profile {profile_name} {profile_id}",
                        lambda pid=profile_id: self.window.apply_profile(str(pid)),
                    )
                )

        manager = self.window.connection_manager
        if manager:
            self._entries.extend(
                [
                    (tr("●  Buscar DualSense", self.window.language), tr("Inicia la conexión automática", self.window.language), "conectar control buscar usb bluetooth", manager.request_connect),
                    (tr("○  Desconectar DualSense", self.window.language), tr("Pausa la conexión automática", self.window.language), "desconectar control", manager.disconnect),
                ]
            )
        if self.window.gyro_engine:
            self._entries.append(
                (tr("◎  Recentrar giroscopio", self.window.language), tr("Limpia la orientación acumulada", self.window.language), "gyro giroscopio recentrar", self.window.gyro_engine.recenter)
            )
        for preset_id, preset in APPEARANCE_PRESETS.items():
            self._entries.append(
                (
                    f"✦  {tr('Apariencia', self.window.language)} {preset['name']}",
                    tr("Aplicar preset visual", self.window.language),
                    f"tema apariencia preset {preset['name']} {preset_id}",
                    lambda key=preset_id: self.window.apply_appearance_preset(key),
                )
            )
        self._entries.append(
            ("✓  Guardar configuración", "Escribe los cambios pendientes ahora", "guardar salvar configuración", self.window.flush_config_save)
        )

    def refresh(self, *_args: Any) -> None:
        query = self.search.text().strip().lower()
        words = [word for word in query.split() if word]
        self.results.clear()
        for index, (title, subtitle, keywords, _callback) in enumerate(self._entries):
            haystack = f"{title} {subtitle} {keywords}".lower()
            if words and not all(word in haystack for word in words):
                continue
            item = QListWidgetItem(f"{title}\n{subtitle}")
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.results.addItem(item)
        if self.results.count():
            self.results.setCurrentRow(0)

    def activate_current(self) -> None:
        item = self.results.currentItem()
        if not item:
            return
        try:
            index = int(item.data(Qt.ItemDataRole.UserRole))
            callback = self._entries[index][3]
        except (TypeError, ValueError, IndexError):
            return
        self.accept()
        self.window.call_later(0, callback)

    def show_palette(self) -> None:
        self._build_entries()
        self.search.clear()
        self.refresh()
        self.search.setFocus()
        self.show()
        self.raise_()
        self.activateWindow()


from .controller_visual import ControllerVisual  # noqa: E402,F401 -- reexport público

class LatencyGraph(QWidget):
    def __init__(
        self,
        capacity: int = 75,
        maximum: float = 3.0,
        *,
        top_label: str = "3 ms",
        middle_label: str = "1.5 ms",
        bottom_label: str = "0 ms",
        footer: str = "60s",
    ) -> None:
        super().__init__()
        self.maximum = max(0.0001, float(maximum))
        self.top_label = top_label
        self.middle_label = middle_label
        self.bottom_label = bottom_label
        self.footer = footer
        self.values: deque[float] = deque([0.0] * capacity, maxlen=capacity)
        self.setMinimumHeight(115)

    def add_value(self, value: float) -> None:
        self.values.append(max(0.0, min(self.maximum, float(value))))
        self.update()

    def paintEvent(self, _event: Any) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(48, 8, -10, -20)
        p.setPen(QPen(QColor("#1d2944"), 1))
        for i in range(4):
            y = rect.top() + i * rect.height() / 3
            p.drawLine(rect.left(), int(y), rect.right(), int(y))
        p.setPen(QColor(C["faint"]))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(2, rect.top() + 4, self.top_label)
        p.drawText(2, rect.center().y() + 4, self.middle_label)
        p.drawText(2, rect.bottom() + 4, self.bottom_label)
        if len(self.values) > 1:
            path = QPainterPath()
            for i, value in enumerate(self.values):
                x = rect.left() + i * rect.width() / (len(self.values) - 1)
                y = rect.bottom() - min(value / self.maximum, 1.0) * rect.height()
                path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
            p.setPen(QPen(QColor(C["accent2"]), 1.5))
            p.drawPath(path)
        p.setPen(QColor(C["faint"]))
        p.drawText(rect.right() - 28, self.height() - 3, self.footer)


class StickScope(QWidget):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.title_source = title
        self.physical = (0.0, 0.0)
        self.output = (0.0, 0.0)
        self.setMinimumSize(210, 200)

    def set_points(
        self, physical: tuple[float, float], output: tuple[float, float]
    ) -> None:
        self.physical, self.output = physical, output
        self.update()

    def paintEvent(self, _event: Any) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        size = min(self.width() - 28, self.height() - 48)
        rect = QRectF((self.width() - size) / 2, 30, size, size)
        p.setPen(QColor(C["muted"]))
        p.drawText(8, 16, tr(self.title_source))
        p.setPen(QPen(QColor(C["border"]), 1))
        p.setBrush(QColor(C["panel2"]))
        p.drawEllipse(rect)
        p.drawLine(rect.center().x(), rect.top(), rect.center().x(), rect.bottom())
        p.drawLine(rect.left(), rect.center().y(), rect.right(), rect.center().y())
        radius = size / 2 - 6
        for point, color, r in (
            (self.physical, C["cyan"], 5),
            (self.output, C["accent2"], 4),
        ):
            x = rect.center().x() + point[0] * radius
            y = rect.center().y() + point[1] * radius
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color))
            p.drawEllipse(QPointF(x, y), r, r)


class SliderRow(QWidget):
    changed = Signal(float)

    def __init__(
        self,
        title: str,
        minimum: float,
        maximum: float,
        value: float,
        *,
        decimals: int = 2,
        suffix: str = "",
    ) -> None:
        super().__init__()
        self.factor = 10**decimals
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        title_label = QLabel(title)
        layout.addWidget(title_label, 0, 0)
        self.spin = QDoubleSpinBox()
        self.spin.setAccessibleName(title)
        self.spin.setKeyboardTracking(False)
        self.spin.setDecimals(decimals)
        self.spin.setRange(minimum, maximum)
        self.spin.setSuffix(suffix)
        self.spin.setValue(value)
        self.spin.setFixedWidth(92)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setAccessibleName(title)
        self.slider.setToolTip(f"{title}: {minimum:g} a {maximum:g}{suffix}")
        self.slider.setRange(round(minimum * self.factor), round(maximum * self.factor))
        self.slider.setValue(round(value * self.factor))
        layout.addWidget(self.spin, 0, 2)
        layout.addWidget(self.slider, 1, 0, 1, 3)
        self.spin.valueChanged.connect(self._from_spin)
        self.slider.valueChanged.connect(self._from_slider)

    def _from_spin(self, value: float) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(round(value * self.factor))
        self.slider.blockSignals(False)
        self.changed.emit(value)

    def _from_slider(self, value: int) -> None:
        real = value / self.factor
        self.spin.blockSignals(True)
        self.spin.setValue(real)
        self.spin.blockSignals(False)
        self.changed.emit(real)

    def set_value(self, value: float) -> None:
        self.spin.blockSignals(True)
        self.slider.blockSignals(True)
        self.spin.setValue(value)
        self.slider.setValue(round(value * self.factor))
        self.spin.blockSignals(False)
        self.slider.blockSignals(False)


class KeyCaptureButton(QPushButton):
    """Botón compacto que aprende una tecla, combinación o botón del mouse."""

    binding_changed = Signal(str)

    SPECIAL_KEYS = {
        Qt.Key.Key_Space: "SPACE",
        Qt.Key.Key_Return: "ENTER",
        Qt.Key.Key_Enter: "ENTER",
        Qt.Key.Key_Tab: "TAB",
        Qt.Key.Key_Backtab: "TAB",
        Qt.Key.Key_Backspace: "BACKSPACE",
        Qt.Key.Key_Delete: "DELETE",
        Qt.Key.Key_Insert: "INSERT",
        Qt.Key.Key_Home: "HOME",
        Qt.Key.Key_End: "END",
        Qt.Key.Key_PageUp: "PAGEUP",
        Qt.Key.Key_PageDown: "PAGEDOWN",
        Qt.Key.Key_Up: "UP",
        Qt.Key.Key_Down: "DOWN",
        Qt.Key.Key_Left: "LEFT",
        Qt.Key.Key_Right: "RIGHT",
        Qt.Key.Key_Shift: "SHIFT",
        Qt.Key.Key_Control: "CTRL",
        Qt.Key.Key_Alt: "ALT",
        Qt.Key.Key_Meta: "WIN",
    }

    def __init__(self, value: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._value = ""
        self._capturing = False
        self._ignore_next_clicked = False
        self.setCheckable(True)
        self.setMinimumWidth(116)
        self.setMaximumWidth(170)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.clicked.connect(self.begin_capture)
        self.set_binding(value)

    def binding(self) -> str:
        return self._value

    def set_binding(self, value: str, *, emit: bool = False) -> None:
        from src.keyboard_gamepad import normalize_key_name

        self._value = normalize_key_name(value)
        self._capturing = False
        self.setChecked(False)
        self.setText(self._value or "Sin asignar")
        self.setToolTip(
            "Haz clic y pulsa una tecla. Backspace elimina la asignación. "
            "También acepta botones del mouse."
        )
        if emit:
            self.binding_changed.emit(self._value)

    def begin_capture(self) -> None:
        if self._ignore_next_clicked:
            self._ignore_next_clicked = False
            return
        if self._capturing:
            return
        self._capturing = True
        self.setChecked(True)
        self.setText("Pulsa una tecla…")
        self.setFocus(Qt.FocusReason.MouseFocusReason)

    @staticmethod
    def _modifier_names(modifiers: Qt.KeyboardModifier) -> List[str]:
        names: List[str] = []
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            names.append("CTRL")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            names.append("ALT")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            names.append("SHIFT")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            names.append("WIN")
        return names

    def keyPressEvent(self, event: Any) -> None:
        if not self._capturing:
            super().keyPressEvent(event)
            return
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.set_binding(self._value)
            return
        if key == Qt.Key.Key_Backspace:
            self.set_binding("", emit=True)
            return
        name = self.SPECIAL_KEYS.get(key, "")
        if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24:
            name = f"F{key - Qt.Key.Key_F1 + 1}"
        if not name:
            text = str(event.text() or "").upper().strip()
            if len(text) == 1 and (text.isalnum() or text in "`-=[]\\;',./"):
                name = text
        if not name:
            sequence = QKeySequence(key).toString(QKeySequence.SequenceFormat.PortableText)
            name = sequence.upper().replace(" ", "")
        if not name:
            return
        modifiers = self._modifier_names(event.modifiers())
        if name not in ("CTRL", "ALT", "SHIFT", "WIN"):
            parts = [item for item in modifiers if item != name]
            parts.append(name)
            name = "+".join(parts)
        self.set_binding(name, emit=True)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._capturing:
            mouse_name = {
                Qt.MouseButton.LeftButton: "MOUSE1",
                Qt.MouseButton.RightButton: "MOUSE2",
                Qt.MouseButton.MiddleButton: "MOUSE3",
                Qt.MouseButton.BackButton: "MOUSE4",
                Qt.MouseButton.ForwardButton: "MOUSE5",
            }.get(event.button())
            if mouse_name:
                self._ignore_next_clicked = True
                self.set_binding(mouse_name, emit=True)
                event.accept()
                return
        super().mousePressEvent(event)

    def focusOutEvent(self, event: Any) -> None:
        if self._capturing:
            self.set_binding(self._value)
        super().focusOutEvent(event)


class MascotPanel(QFrame):
    """Panel reutilizable para mostrar a Nikaido con pose y diálogo contextual."""

    POSES = {
        "greeting": "assets/mascot/poses_a/greeting.png",
        "neutral": "assets/mascot/poses_a/neutral.png",
        "happy": "assets/mascot/poses_a/happy.png",
        "celebrating": "assets/mascot/poses_a/celebrating.png",
        "thinking": "assets/mascot/poses_a/thinking.png",
        "worried": "assets/mascot/poses_a/worried.png",
        "point_left": "assets/mascot/poses_a/point_left.png",
        "point_right": "assets/mascot/poses_a/point_right.png",
        "present_left": "assets/mascot/poses_a/present_left.png",
        "sleeping": "assets/mascot/poses_a/sleeping.png",
        "compact_neutral": "assets/mascot/poses_b/neutral.png",
        "compact_happy": "assets/mascot/poses_b/happy.png",
        "compact_thinking": "assets/mascot/poses_b/thinking.png",
        "compact_explaining": "assets/mascot/poses_b/explaining.png",
        "compact_connecting": "assets/mascot/poses_b/connecting.png",
        "compact_battery_low": "assets/mascot/poses_b/battery_low.png",
        "compact_error_mild": "assets/mascot/poses_b/error_mild.png",
        "compact_error_critical": "assets/mascot/poses_b/error_critical.png",
        "compact_update": "assets/mascot/poses_b/update.png",
        "compact_idle": "assets/mascot/poses_b/idle.png",
    }

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("mascotPanel")
        self.setMinimumWidth(270)
        self.setMaximumWidth(310)
        self._source = QPixmap()
        self._scaled = QPixmap()
        self._pose = ""
        self._scaled_key: Optional[tuple[int, int]] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        self.badge = QLabel("GUÍA")
        self.badge.setObjectName("mascotBadge")
        header.addWidget(self.badge)
        header.addStretch()
        self.name_label = QLabel("NIKAIDO")
        self.name_label.setObjectName("mascotName")
        header.addWidget(self.name_label)
        root.addLayout(header)

        self.sprite = QLabel()
        self.sprite.setObjectName("mascotSprite")
        self.sprite.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom)
        self.sprite.setMinimumHeight(300)
        root.addWidget(self.sprite, 1)

        bubble = QFrame()
        bubble.setObjectName("mascotBubble")
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(14, 12, 14, 12)
        bubble_layout.setSpacing(5)
        self.title_label = QLabel("Hola, soy Nikaido")
        self.title_label.setObjectName("mascotTitle")
        self.title_label.setWordWrap(True)
        bubble_layout.addWidget(self.title_label)
        self.message_label = QLabel()
        self.message_label.setObjectName("mascotMessage")
        self.message_label.setWordWrap(True)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        bubble_layout.addWidget(self.message_label)
        root.addWidget(bubble)

    @classmethod
    def asset_path(cls, pose: str) -> Path:
        relative = cls.POSES.get(str(pose), cls.POSES["neutral"])
        return resource_path(relative)

    def _load_pose(self, pose: str) -> QPixmap:
        path = str(self.asset_path(pose))
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        source_size = reader.size()
        limit = QSize(440, 560) if not pose.startswith("compact_") else QSize(420, 420)
        if source_size.isValid():
            target = source_size.scaled(limit, Qt.AspectRatioMode.KeepAspectRatio)
            if target.width() < source_size.width() or target.height() < source_size.height():
                reader.setScaledSize(target)
        image = reader.read()
        return QPixmap.fromImage(image) if not image.isNull() else QPixmap()

    def set_scene(
        self,
        pose: str,
        title: str,
        message: str,
        *,
        badge: str = "GUÍA",
    ) -> None:
        self.badge.setText(str(badge).upper())
        self.title_label.setText(str(title))
        self.message_label.setText(str(message))
        normalized_pose = str(pose) if str(pose) in self.POSES else "neutral"
        # La conexión se actualiza varias veces; la misma pose no se recarga.
        if normalized_pose != self._pose or self._source.isNull():
            self._pose = normalized_pose
            self._source = self._load_pose(normalized_pose)
            self._scaled = QPixmap()
            self._scaled_key = None
        self._refresh_sprite()

    def clear_resources(self) -> None:
        """Libera los buffers nativos cuando el wizard o aviso desaparece."""
        self._source = QPixmap()
        self._scaled = QPixmap()
        self._scaled_key = None
        self._pose = ""
        self.sprite.clear()

    def _refresh_sprite(self) -> None:
        if self._source.isNull():
            self.sprite.setPixmap(QPixmap())
            self.sprite.setText("N")
            return
        width = max(180, self.sprite.width() - 4)
        height = max(260, self.sprite.height() - 4)
        key = (width, height)
        if key != self._scaled_key or self._scaled.isNull():
            self._scaled = self._source.scaled(
                width,
                height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._scaled_key = key
        self.sprite.setText("")
        self.sprite.setPixmap(self._scaled)

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        self._refresh_sprite()



class ScrollPage(QScrollArea):
    def __init__(self) -> None:
        super().__init__()
        self.setWidgetResizable(True)
        self.viewport().setObjectName("scrollViewport")
        self.viewport().setStyleSheet("QWidget#scrollViewport { background: transparent; }")
        self.body = QWidget()
        self.body.setObjectName("scrollBody")
        self.body.setStyleSheet("QWidget#scrollBody { background: transparent; }")
        self.layout = QVBoxLayout(self.body)
        self.layout.setContentsMargins(18, 18, 18, 18)
        self.layout.setSpacing(14)
        self.setWidget(self.body)

    def add_header(self, title: str, subtitle: str) -> None:
        self.layout.addWidget(label(title, "title"))
        subtitle_label = label(subtitle, "muted")
        subtitle_label.setWordWrap(True)
        self.layout.addWidget(subtitle_label)


class PageLoadError(ScrollPage):
    """Mantiene el resto de Nikaido usable si una pantalla opcional falla."""

    def __init__(self, window: "NikaidoWindow", page: str, error: Exception) -> None:
        super().__init__()
        self.window = window
        self.page = page
        panel = card()
        panel.setMaximumWidth(760)
        box = QVBoxLayout(panel)
        box.setContentsMargins(22, 22, 22, 22)
        box.setSpacing(12)
        box.addWidget(label("No se pudo abrir esta sección", "title"))
        description = label(
            "Nikaido aisló el fallo para que el control y las demás pantallas sigan funcionando.",
            "muted",
        )
        description.setWordWrap(True)
        box.addWidget(description)
        detail = QLabel(str(error) or error.__class__.__name__)
        detail.setWordWrap(True)
        detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        detail.setStyleSheet(
            f"background:{C['panel2']};border:1px solid {C['border']};border-radius:8px;padding:12px;color:{C['yellow']}"
        )
        box.addWidget(detail)
        actions = QHBoxLayout()
        actions.addWidget(button("Reintentar", lambda: window.retry_page(page), primary=True))
        actions.addWidget(button("Abrir diagnóstico", lambda: window.navigate("monitor")))
        actions.addStretch()
        box.addLayout(actions)
        self.layout.addWidget(panel, 0, Qt.AlignmentFlag.AlignHCenter)
        self.layout.addStretch()
