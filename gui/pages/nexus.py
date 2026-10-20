"""AdvancedBindingDialog, NexusControllerView, MapperPage extraídos de la antigua interfaz monolítica."""

from __future__ import annotations

from typing import TYPE_CHECKING


from ..ui_common import (
    logging,
    Any,
    C,
    Dict,
    List,
    Optional,
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QColor,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QIcon,
    QInputDialog,
    QKeySequence,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPointF,
    QRectF,
    QScrollArea,
    QShortcut,
    QSize,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
    SnapshotHistory,
    button,
    card,
    clear_layout,
    configure_tabs,
    copy,
    label,
    resource_path,
)
from ..components import ScrollPage

if TYPE_CHECKING:
    from ..main_window import NikaidoWindow

logger = logging.getLogger(__name__)

class AdvancedBindingDialog(QDialog):
    """Editor compacto para una acción avanzada de botón."""

    ACTIONS = (
        ("Botón virtual", "controller"),
        ("Teclado", "keyboard"),
        ("Botón del mouse", "mouse_button"),
        ("Movimiento del mouse", "mouse_move"),
        ("Macro", "macro"),
        ("Cambiar perfil", "profile"),
        ("Cambiar capa", "layer"),
        ("Giroscopio", "gyro"),
        ("Desactivar botón", "disabled"),
        ("Dejar pasar original", "passthrough"),
    )
    ACTIVATIONS = (
        ("Mientras se mantiene", "hold"),
        ("Al presionar", "press"),
        ("Al soltar", "release"),
        ("Pulsación corta", "short"),
        ("Pulsación larga", "long"),
        ("Doble pulsación", "double"),
        ("Alternar encendido/apagado", "toggle"),
    )

    def __init__(
        self,
        window: "NikaidoWindow",
        layer_names: List[str],
        source: str = "cross",
        binding: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(window)
        from src.emulator import BUTTON_FRIENDLY_NAMES, REMAPPABLE_BUTTONS

        self.window = window
        self.layer_names = list(layer_names)
        self._buttons = list(REMAPPABLE_BUTTONS)
        self._friendly = dict(BUTTON_FRIENDLY_NAMES)
        self.setWindowTitle("Acción avanzada")
        self.setMinimumWidth(720)
        self.setModal(True)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.addWidget(label("Acción avanzada", "title"))
        help_text = label(
            "Combina gestos, capas y condiciones sin perder la entrada original.",
            "muted",
        )
        help_text.setWordWrap(True)
        title_box.addWidget(help_text)
        header.addLayout(title_box, 1)
        root.addLayout(header)

        main = QHBoxLayout()
        main.setSpacing(12)
        action_card = card()
        form = QFormLayout(action_card)
        form.setContentsMargins(16, 14, 16, 14)
        form.setSpacing(10)

        self.source = QComboBox()
        for item in self._buttons:
            self.source.addItem(self._friendly.get(item, item), item)
        self.source.setCurrentIndex(max(0, self.source.findData(source)))
        self.source.currentIndexChanged.connect(self._refresh_requires)
        form.addRow("Botón físico", self.source)

        self.action_type = QComboBox()
        for title, value in self.ACTIONS:
            self.action_type.addItem(title, value)
        self.action_type.currentIndexChanged.connect(self._refresh_value_choices)
        self.action_type.currentIndexChanged.connect(self._refresh_timing)
        form.addRow("Acción", self.action_type)

        self.value = QComboBox()
        self.value.setEditable(True)
        self.value.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        form.addRow("Salida / destino", self.value)

        self.activation = QComboBox()
        for title, value in self.ACTIVATIONS:
            self.activation.addItem(title, value)
        self.activation.currentIndexChanged.connect(self._refresh_timing)
        form.addRow("Gesto", self.activation)

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Opcional, por ejemplo: Capa de francotirador")
        form.addRow("Nombre", self.label_edit)

        self.enabled = QCheckBox("Acción activa")
        self.enabled.setChecked(True)
        self.block_original = QCheckBox("Bloquear el botón físico original")
        self.block_original.setChecked(True)
        self.turbo = QCheckBox("Turbo mientras se mantiene")
        self.turbo.toggled.connect(self._refresh_timing)
        self.exclusive_double = QCheckBox("Reservar la doble pulsación")
        form.addRow(self.enabled)
        form.addRow(self.block_original)
        form.addRow(self.turbo)
        form.addRow(self.exclusive_double)
        main.addWidget(action_card, 55)

        condition_card = card()
        conditions = QVBoxLayout(condition_card)
        conditions.setContentsMargins(16, 14, 16, 14)
        conditions.addWidget(label("CONDICIONES", "eyebrow"))
        info = QLabel("La acción solo se ejecuta cuando estos botones también están presionados.")
        info.setWordWrap(True)
        info.setProperty("muted", True)
        conditions.addWidget(info)
        self.requires = QListWidget()
        self.requires.setAlternatingRowColors(True)
        conditions.addWidget(self.requires, 1)
        main.addWidget(condition_card, 45)
        root.addLayout(main)

        timing_card = card()
        timing = QGridLayout(timing_card)
        timing.setContentsMargins(16, 12, 16, 12)
        timing.addWidget(label("TIEMPOS", "eyebrow"), 0, 0, 1, 4)
        self.long_ms = QSpinBox()
        self.long_ms.setRange(150, 2000)
        self.long_ms.setValue(450)
        self.long_ms.setSuffix(" ms")
        self.double_ms = QSpinBox()
        self.double_ms.setRange(120, 800)
        self.double_ms.setValue(280)
        self.double_ms.setSuffix(" ms")
        self.pulse_ms = QSpinBox()
        self.pulse_ms.setRange(20, 300)
        self.pulse_ms.setValue(45)
        self.pulse_ms.setSuffix(" ms")
        self.turbo_hz = QSpinBox()
        self.turbo_hz.setRange(2, 30)
        self.turbo_hz.setValue(12)
        self.turbo_hz.setSuffix(" Hz")
        for col, (title, widget) in enumerate((
            ("Pulsación larga", self.long_ms),
            ("Doble pulsación", self.double_ms),
            ("Pulso de salida", self.pulse_ms),
            ("Velocidad turbo", self.turbo_hz),
        )):
            timing.addWidget(label(title, "muted"), 1, col)
            timing.addWidget(widget, 2, col)
        self.timing_hint = label("Los tiempos se pueden preparar aunque el gesto actual todavía no los use.", "muted")
        self.timing_hint.setWordWrap(True)
        root.addWidget(timing_card)
        root.addWidget(self.timing_hint)

        self.validation = QLabel("")
        self.validation.setWordWrap(True)
        self.validation.setStyleSheet(f"color:{C['danger']};font-weight:700")
        self.validation.hide()
        root.addWidget(self.validation)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Guardar acción")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        data = dict(binding or {})
        self.action_type.setCurrentIndex(
            max(0, self.action_type.findData(data.get("action_type", "controller")))
        )
        self.activation.setCurrentIndex(
            max(0, self.activation.findData(data.get("activation", "hold")))
        )
        self.label_edit.setText(str(data.get("label", "")))
        self.enabled.setChecked(bool(data.get("enabled", True)))
        self.block_original.setChecked(bool(data.get("block_original", True)))
        self.turbo.setChecked(bool(data.get("turbo", False)))
        self.exclusive_double.setChecked(bool(data.get("exclusive_double", False)))
        self.long_ms.setValue(int(data.get("long_press_ms", 450)))
        self.double_ms.setValue(int(data.get("double_tap_ms", 280)))
        self.pulse_ms.setValue(int(data.get("pulse_ms", 45)))
        self.turbo_hz.setValue(int(data.get("turbo_hz", 12)))
        self._refresh_value_choices()
        current_value = str(data.get("value", ""))
        index = self.value.findData(current_value)
        if index >= 0:
            self.value.setCurrentIndex(index)
        else:
            self.value.setEditText(current_value)
        self._refresh_requires()
        selected = set(data.get("requires", []))
        for row in range(self.requires.count()):
            item = self.requires.item(row)
            item.setCheckState(
                Qt.CheckState.Checked
                if item.data(Qt.ItemDataRole.UserRole) in selected
                else Qt.CheckState.Unchecked
            )
        self._refresh_timing()

    def _refresh_value_choices(self) -> None:
        from src.emulator import BUTTON_FRIENDLY_NAMES, REMAPPABLE_BUTTONS

        current = self.value.currentData() or self.value.currentText()
        action = self.action_type.currentData()
        self.value.blockSignals(True)
        self.value.clear()
        self.value.setEditable(action in ("keyboard", "mouse_move"))
        choices: List[tuple[str, str]] = []
        if action == "controller":
            choices = [(BUTTON_FRIENDLY_NAMES.get(x, x), x) for x in REMAPPABLE_BUTTONS]
        elif action == "keyboard":
            choices = [(x, x) for x in ("SPACE", "ENTER", "ESC", "TAB", "CTRL", "SHIFT", "ALT", "CTRL+F", "F1")]
        elif action == "mouse_button":
            choices = [("Clic izquierdo", "left"), ("Clic derecho", "right"), ("Clic central", "middle"), ("Botón lateral 1", "x1"), ("Botón lateral 2", "x2")]
        elif action == "mouse_move":
            choices = [("Derecha 20 px", "20,0"), ("Izquierda 20 px", "-20,0"), ("Arriba 20 px", "0,-20"), ("Abajo 20 px", "0,20")]
        elif action == "macro":
            engine = self.window.macro_engine
            macros = engine.get_macros() if engine and hasattr(engine, "get_macros") else []
            choices = [(getattr(item, "name", getattr(item, "id", "Macro")), getattr(item, "id", "")) for item in macros]
        elif action == "profile":
            trigger = self.window.trigger_engine
            choices = list(trigger.get_profile_names()) if trigger else []
            choices = [(name, pid) for pid, name in choices]
        elif action == "layer":
            choices = [(name.replace("_", " ").title(), name) for name in self.layer_names]
        elif action == "gyro":
            choices = [("Recentrar", "recenter"), ("Alternar", "toggle"), ("Activar", "enable"), ("Desactivar", "disable")]
        elif action == "disabled":
            choices = [("Sin salida", "")]
        elif action == "passthrough":
            choices = [("Botón original", "")]
        for title, value in choices:
            self.value.addItem(title, value)
        idx = self.value.findData(current)
        if idx >= 0:
            self.value.setCurrentIndex(idx)
        elif self.value.isEditable() and current:
            self.value.setEditText(str(current))
        self.value.setEnabled(action not in ("disabled", "passthrough"))
        self.value.blockSignals(False)
        if action == "passthrough":
            self.block_original.setChecked(False)
        elif action == "disabled":
            self.block_original.setChecked(True)

    def _refresh_requires(self) -> None:
        current = {
            self.requires.item(row).data(Qt.ItemDataRole.UserRole)
            for row in range(self.requires.count())
            if self.requires.item(row).checkState() == Qt.CheckState.Checked
        }
        source = self.source.currentData()
        self.requires.clear()
        for item in self._buttons:
            if item == source:
                continue
            row = QListWidgetItem(self._friendly.get(item, item))
            row.setData(Qt.ItemDataRole.UserRole, item)
            row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            row.setCheckState(Qt.CheckState.Checked if item in current else Qt.CheckState.Unchecked)
            self.requires.addItem(row)

    def _refresh_timing(self) -> None:
        activation = str(self.activation.currentData() or "hold")
        action = str(self.action_type.currentData() or "controller")
        turbo_supported = action in ("controller", "keyboard", "mouse_button", "mouse_move")
        self.turbo.setEnabled(activation == "hold" and turbo_supported)
        if not self.turbo.isEnabled():
            self.turbo.setChecked(False)

        # Los valores permanecen editables siempre. Así el usuario puede preparar
        # los tiempos antes de cambiar de gesto y al editar no parece que Nexus
        # haya perdido o bloqueado la configuración guardada.
        for widget in (self.long_ms, self.double_ms, self.pulse_ms, self.turbo_hz):
            widget.setEnabled(True)

        used_by_gesture = {
            "hold": "Este gesto usa la velocidad turbo cuando Turbo está activo.",
            "press": "Este gesto usa el pulso de salida.",
            "release": "Este gesto usa el pulso de salida.",
            "short": "Este gesto usa pulsación larga como límite y el pulso de salida.",
            "long": "Este gesto usa el umbral de pulsación larga.",
            "double": "Este gesto usa la ventana de doble pulsación y el pulso de salida.",
            "toggle": "Este gesto conserva los tiempos para cuando cambies de modo.",
        }
        if hasattr(self, "timing_hint"):
            self.timing_hint.setText(used_by_gesture.get(activation, "Los tiempos quedan guardados con la acción."))

        self.exclusive_double.setEnabled(activation == "double")
        if activation != "double":
            self.exclusive_double.setChecked(False)

    def accept(self) -> None:
        from src.advanced_mapping import KeyboardMouseOutput

        action = str(self.action_type.currentData())
        value = self.value.currentText().strip()
        error = ""
        if action not in ("disabled", "passthrough") and not value:
            error = "Elige una salida o destino para esta acción."
        elif action == "keyboard" and not KeyboardMouseOutput._key_codes(value):
            error = "Escribe una tecla o atajo válido, por ejemplo F, SPACE o CTRL+F."
        elif action == "mouse_move":
            try:
                x_text, y_text = value.replace(";", ",").split(",", 1)
                float(x_text.strip())
                float(y_text.strip())
            except (TypeError, ValueError, OverflowError):
                error = "El movimiento debe tener formato X,Y; por ejemplo 20,-10."
        if error:
            self.validation.setText(error)
            self.validation.show()
            return
        self.validation.hide()
        super().accept()

    def result_data(self) -> tuple[str, Dict[str, Any]]:
        requires = []
        for row in range(self.requires.count()):
            item = self.requires.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                requires.append(str(item.data(Qt.ItemDataRole.UserRole)))
        value = self.value.currentData()
        if value is None or self.value.isEditable():
            value = self.value.currentText().strip()
        return str(self.source.currentData()), {
            "action_type": str(self.action_type.currentData()),
            "value": str(value or ""),
            "activation": str(self.activation.currentData()),
            "enabled": self.enabled.isChecked(),
            "block_original": self.block_original.isChecked(),
            "requires": requires,
            "turbo": self.turbo.isChecked(),
            "turbo_hz": self.turbo_hz.value(),
            "long_press_ms": self.long_ms.value(),
            "double_tap_ms": self.double_ms.value(),
            "pulse_ms": self.pulse_ms.value(),
            "label": self.label_edit.text().strip(),
            "exclusive_double": self.exclusive_double.isChecked(),
        }


class NexusControllerView(QWidget):
    """Mapa visual original de Nikaido para elegir entradas del DualSense."""

    selected = Signal(str)

    HOTSPOTS = {
        "L2_btn": (0.18, 0.12), "R2_btn": (0.82, 0.12),
        "L1": (0.22, 0.22), "R1": (0.78, 0.22),
        "create": (0.41, 0.37), "options": (0.59, 0.37),
        "touchpad": (0.50, 0.31), "ps": (0.50, 0.60),
        "dpad_up": (0.25, 0.42), "dpad_left": (0.20, 0.49),
        "dpad_right": (0.30, 0.49), "dpad_down": (0.25, 0.56),
        "triangle": (0.75, 0.42), "square": (0.70, 0.49),
        "circle": (0.80, 0.49), "cross": (0.75, 0.56),
        "L3": (0.39, 0.67), "R3": (0.61, 0.67),
    }

    SYMBOLS = {
        "cross": "×", "circle": "○", "square": "□", "triangle": "△",
        "L1": "L1", "R1": "R1", "L2_btn": "L2", "R2_btn": "R2",
        "L3": "L3", "R3": "R3", "options": "≡", "create": "···",
        "ps": "PS", "touchpad": "TOUCH", "dpad_up": "↑",
        "dpad_down": "↓", "dpad_left": "←", "dpad_right": "→",
    }

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._selected = "cross"
        self._counts: Dict[str, int] = {}
        self._pressed: set[str] = set()
        self._hovered = ""
        self.setMinimumSize(420, 320)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Control visual de Nikaido Nexus")
        self.setAccessibleDescription(
            "Usa el mouse o las flechas para elegir una entrada; Enter abre su inspector."
        )

    def sizeHint(self) -> QSize:
        return QSize(620, 410)

    def set_selected(self, source: str) -> None:
        if source in self.HOTSPOTS:
            self._selected = source
            self.update()

    def set_counts(self, counts: Dict[str, int]) -> None:
        self._counts = {str(key): int(value) for key, value in counts.items() if value}
        self.update()

    def set_pressed(self, sources: Any) -> None:
        pressed = {str(item) for item in (sources or []) if str(item) in self.HOTSPOTS}
        if pressed != self._pressed:
            self._pressed = pressed
            self.update()

    def _point(self, source: str) -> QPointF:
        x, y = self.HOTSPOTS[source]
        return QPointF(x * self.width(), y * self.height())

    def _hit(self, point: QPointF) -> str:
        best, distance = "", 10_000.0
        for source in self.HOTSPOTS:
            center = self._point(source)
            current = ((center.x() - point.x()) ** 2 + (center.y() - point.y()) ** 2) ** 0.5
            radius = 34 if source == "touchpad" else 25
            if current <= radius and current < distance:
                best, distance = source, current
        return best

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        hovered = self._hit(event.position())
        if hovered != self._hovered:
            self._hovered = hovered
            self.setCursor(Qt.CursorShape.PointingHandCursor if hovered else Qt.CursorShape.ArrowCursor)
            self.update()

    def leaveEvent(self, event: Any) -> None:
        self._hovered = ""
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        source = self._hit(event.position())
        if source:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self._selected = source
            self.selected.emit(source)
            self.update()

    def _move_keyboard_selection(self, dx: float, dy: float) -> None:
        current = self.HOTSPOTS.get(self._selected, (0.5, 0.5))
        candidates: List[tuple[float, str]] = []
        for source, point in self.HOTSPOTS.items():
            if source == self._selected:
                continue
            vx, vy = point[0] - current[0], point[1] - current[1]
            forward = vx * dx + vy * dy
            if forward <= 0:
                continue
            sideways = abs(vx * dy - vy * dx)
            distance = (vx * vx + vy * vy) ** 0.5
            # Prioriza la dirección pedida y después la entrada más cercana.
            candidates.append((sideways * 3.0 + distance - forward * 0.35, source))
        if not candidates:
            return
        self._selected = min(candidates)[1]
        self.selected.emit(self._selected)
        self.update()

    def keyPressEvent(self, event: Any) -> None:
        directions = {
            Qt.Key.Key_Left: (-1.0, 0.0),
            Qt.Key.Key_Right: (1.0, 0.0),
            Qt.Key.Key_Up: (0.0, -1.0),
            Qt.Key.Key_Down: (0.0, 1.0),
        }
        direction = directions.get(event.key())
        if direction is not None:
            self._move_keyboard_selection(*direction)
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.selected.emit(self._selected)
            event.accept()
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event: Any) -> None:
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event: Any) -> None:
        self.update()
        super().focusOutEvent(event)

    def paintEvent(self, _event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(8, 13, 27, 90))

        w, h = float(self.width()), float(self.height())
        body = QPainterPath()
        body.moveTo(w * 0.28, h * 0.25)
        body.cubicTo(w * 0.17, h * 0.20, w * 0.10, h * 0.31, w * 0.10, h * 0.57)
        body.cubicTo(w * 0.10, h * 0.78, w * 0.16, h * 0.87, w * 0.24, h * 0.72)
        body.cubicTo(w * 0.30, h * 0.61, w * 0.34, h * 0.58, w * 0.39, h * 0.60)
        body.cubicTo(w * 0.45, h * 0.63, w * 0.55, h * 0.63, w * 0.61, h * 0.60)
        body.cubicTo(w * 0.66, h * 0.58, w * 0.70, h * 0.61, w * 0.76, h * 0.72)
        body.cubicTo(w * 0.84, h * 0.87, w * 0.90, h * 0.78, w * 0.90, h * 0.57)
        body.cubicTo(w * 0.90, h * 0.31, w * 0.83, h * 0.20, w * 0.72, h * 0.25)
        body.cubicTo(w * 0.63, h * 0.29, w * 0.59, h * 0.22, w * 0.50, h * 0.22)
        body.cubicTo(w * 0.41, h * 0.22, w * 0.37, h * 0.29, w * 0.28, h * 0.25)
        body.closeSubpath()
        painter.setBrush(QColor(19, 28, 49, 225))
        painter.setPen(QPen(QColor(48, 64, 98, 230), 2))
        painter.drawPath(body)

        center_panel = QRectF(w * 0.37, h * 0.24, w * 0.26, h * 0.23)
        painter.setBrush(QColor(7, 12, 25, 220))
        painter.setPen(QPen(QColor(C["border"]), 1))
        painter.drawRoundedRect(center_panel, 14, 14)

        for source in self.HOTSPOTS:
            center = self._point(source)
            selected = source == self._selected
            hovered = source == self._hovered
            pressed = source in self._pressed
            count = self._counts.get(source, 0)
            radius = 25 if source != "touchpad" else 31
            if pressed:
                fill = QColor(C["green"])
                fill.setAlpha(190)
            else:
                fill = QColor(C["accent"] if selected else C["hover"] if hovered else C["panel2"])
            painter.setBrush(fill)
            border = QColor(
                C["green"] if pressed else C["accent2"] if selected else C["cyan"] if count else C["border"]
            )
            painter.setPen(QPen(border, 3 if pressed else 2 if selected or count else 1))
            painter.drawEllipse(center, radius, radius)
            if selected and self.hasFocus():
                focus_color = QColor(C["cyan"])
                focus_color.setAlpha(210)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(focus_color, 2, Qt.PenStyle.DashLine))
                painter.drawEllipse(center, radius + 5, radius + 5)
                painter.setBrush(fill)
            painter.setPen(QColor("white") if selected else QColor(C["text"]))
            font = painter.font()
            font.setBold(True)
            font.setPointSize(8 if source == "touchpad" else 10)
            painter.setFont(font)
            painter.drawText(
                QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2),
                Qt.AlignmentFlag.AlignCenter,
                self.SYMBOLS.get(source, source),
            )
            if count:
                badge = QPointF(center.x() + radius * 0.72, center.y() - radius * 0.72)
                painter.setBrush(QColor(C["accent2"]))
                painter.setPen(QPen(QColor("white"), 1))
                painter.drawEllipse(badge, 9, 9)
                font.setPointSize(7)
                painter.setFont(font)
                painter.drawText(QRectF(badge.x() - 9, badge.y() - 9, 18, 18), Qt.AlignmentFlag.AlignCenter, str(min(9, count)))

        painter.setPen(QColor(C["muted"]))
        font = painter.font()
        font.setPointSize(9)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(
            QRectF(0, h - 32, w, 24),
            Qt.AlignmentFlag.AlignCenter,
            "Selecciona una entrada · también puedes usar flechas y Enter",
        )


class MapperPage(ScrollPage):
    """Remapeo directo y editor completo de capas/gestos."""

    def __init__(self, window: "NikaidoWindow") -> None:
        super().__init__()
        self.window = window
        self.combos: Dict[str, QComboBox] = {}
        self._advanced_config: Dict[str, Any] = {}
        self._loading = False
        self._nexus_source = "cross"
        self._nexus_loading = False
        self._nexus_clipboard: Optional[Dict[str, Any]] = None
        self._history = SnapshotHistory(limit=60)
        self._history_profile = ""

        bar = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(label("Nikaido Nexus", "title"))
        sub = label("Diseña botones, gestos, condiciones y capas desde un espacio visual conectado al mapper avanzado.", "muted")
        sub.setWordWrap(True)
        titles.addWidget(sub)
        bar.addLayout(titles, 1)
        self.layer_badge = QLabel("Capa activa: base")
        self.layer_badge.setProperty("accentBadge", True)
        bar.addWidget(self.layer_badge)
        self.enabled = QCheckBox("Remapeo avanzado")
        self.enabled.toggled.connect(self.toggle_advanced)
        bar.addWidget(self.enabled)
        bar.addWidget(button("Guardar configuración", self.save, primary=True))
        self.layout.addLayout(bar)

        self.tabs = configure_tabs(QTabWidget())
        self.tabs.addTab(self._build_nexus_tab(), "Nikaido Nexus")
        self.tabs.addTab(self._build_direct_tab(), "Remapeo directo")
        self.tabs.addTab(self._build_advanced_tab(), "Capas y gestos")
        self.layout.addWidget(self.tabs)
        self._install_nexus_shortcuts()
        self.refresh()

    def _build_nexus_tab(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        hero = card(sub=True)
        hero_row = QHBoxLayout(hero)
        hero_row.setContentsMargins(16, 13, 16, 13)
        hero_row.setSpacing(12)
        mark = QLabel()
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(38, 38)
        mark_icon = QIcon(str(resource_path("assets/nikaido.svg"))).pixmap(38, 38)
        if not mark_icon.isNull():
            mark.setPixmap(mark_icon)
        else:
            mark.setText("N")
            mark.setProperty("accentBadge", True)
        hero_row.addWidget(mark)
        hero_text = QVBoxLayout()
        hero_text.setSpacing(1)
        hero_text.addWidget(label("Nikaido Nexus", "heading"))
        description = label(
            "Diseña cada entrada visualmente y conecta botones, gestos, capas, macros, teclado, mouse y gyro.",
            "muted",
        )
        description.setWordWrap(True)
        hero_text.addWidget(description)
        hero_row.addLayout(hero_text, 1)
        self.nexus_runtime_badge = QLabel("Capa activa: base")
        self.nexus_runtime_badge.setProperty("accentBadge", True)
        hero_row.addWidget(self.nexus_runtime_badge)
        root.addWidget(hero)

        toolbar_group = QVBoxLayout()
        toolbar_group.setSpacing(7)
        layer_row = QHBoxLayout()
        layer_row.addWidget(label("Editar capa", "muted"))
        self.nexus_layer_combo = QComboBox()
        self.nexus_layer_combo.setMinimumWidth(190)
        self.nexus_layer_combo.currentIndexChanged.connect(self._nexus_layer_changed)
        layer_row.addWidget(self.nexus_layer_combo)
        layer_row.addWidget(button("+ Capa", self.add_layer))
        layer_row.addWidget(button("Duplicar", self.duplicate_layer))
        layer_row.addWidget(button("Marcar inicial", lambda: self._set_default_layer(True), tooltip="Usar esta capa al activar el perfil"))
        layer_row.addStretch()
        self.nexus_summary = label("0 entradas · 0 acciones", "muted")
        layer_row.addWidget(self.nexus_summary)
        toolbar_group.addLayout(layer_row)

        edit_row = QHBoxLayout()
        edit_row.addWidget(button("Renombrar capa", self.rename_layer))
        edit_row.addWidget(button("Eliminar capa", self.delete_layer, danger=True))
        edit_row.addWidget(button("Validar mapa", self.validate_nexus, tooltip="Buscar acciones incompletas o destinos faltantes"))
        edit_row.addStretch()
        self.nexus_undo_button = button("↶", self.undo_advanced, tooltip="Deshacer · Ctrl+Z")
        self.nexus_undo_button.setFixedWidth(38)
        self.nexus_redo_button = button("↷", self.redo_advanced, tooltip="Rehacer · Ctrl+Y")
        self.nexus_redo_button.setFixedWidth(38)
        edit_row.addWidget(self.nexus_undo_button)
        edit_row.addWidget(self.nexus_redo_button)
        toolbar_group.addLayout(edit_row)
        root.addLayout(toolbar_group)

        workspace = QHBoxLayout()
        workspace.setSpacing(12)
        controller_card = card()
        controller_layout = QVBoxLayout(controller_card)
        controller_layout.setContentsMargins(14, 14, 14, 14)
        controller_layout.addWidget(label("CONTROL VISUAL", "eyebrow"))
        self.nexus_controller = NexusControllerView()
        self.nexus_controller.selected.connect(self._nexus_select_source)
        controller_layout.addWidget(self.nexus_controller, 1)
        workspace.addWidget(controller_card, 64)

        inspector = card()
        inspector_layout = QVBoxLayout(inspector)
        inspector_layout.setContentsMargins(15, 14, 15, 14)
        inspector_layout.setSpacing(10)
        inspector_layout.addWidget(label("INSPECTOR", "eyebrow"))
        self.nexus_source_title = label("Cruz (X)", "title")
        inspector_layout.addWidget(self.nexus_source_title)
        self.nexus_source_hint = label("Sin acciones en esta capa. La entrada conserva su comportamiento original.", "muted")
        self.nexus_source_hint.setWordWrap(True)
        inspector_layout.addWidget(self.nexus_source_hint)
        self.nexus_search = QLineEdit()
        self.nexus_search.setPlaceholderText("Buscar acción o destino…  Ctrl+F")
        self.nexus_search.setClearButtonEnabled(True)
        self.nexus_search.textChanged.connect(self._refresh_nexus_inspector)
        inspector_layout.addWidget(self.nexus_search)
        self.nexus_actions = QListWidget()
        self.nexus_actions.setAlternatingRowColors(True)
        self.nexus_actions.itemDoubleClicked.connect(lambda _item: self._nexus_edit_binding())
        inspector_layout.addWidget(self.nexus_actions, 1)

        actions = QGridLayout()
        actions.addWidget(button("+ Nueva acción", self._nexus_add_binding, primary=True), 0, 0, 1, 3)
        actions.addWidget(button("Editar", self._nexus_edit_binding), 1, 0)
        actions.addWidget(button("Copiar", self._nexus_copy_binding), 1, 1)
        actions.addWidget(button("Pegar", self._nexus_paste_binding), 1, 2)
        actions.addWidget(button("Subir", lambda: self._nexus_move_binding(-1)), 2, 0)
        actions.addWidget(button("Bajar", lambda: self._nexus_move_binding(1)), 2, 1)
        actions.addWidget(button("Eliminar", self._nexus_remove_binding, danger=True), 2, 2)
        inspector_layout.addLayout(actions)

        inspector_layout.addWidget(label("ATAJOS DE CREACIÓN", "eyebrow"))
        quick = QGridLayout()
        quick.addWidget(button("Tecla", lambda: self._nexus_quick_action("keyboard")), 0, 0)
        quick.addWidget(button("Macro", lambda: self._nexus_quick_action("macro")), 0, 1)
        quick.addWidget(button("Cambiar capa", lambda: self._nexus_quick_action("layer")), 1, 0)
        quick.addWidget(button("Gyro", lambda: self._nexus_quick_action("gyro")), 1, 1)
        quick.addWidget(button("Desactivar", lambda: self._nexus_quick_action("disabled")), 2, 0)
        quick.addWidget(button("Dejar original", lambda: self._nexus_quick_action("passthrough")), 2, 1)
        inspector_layout.addLayout(quick)
        workspace.addWidget(inspector, 36)
        root.addLayout(workspace, 1)

        flow = card(sub=True)
        flow_layout = QVBoxLayout(flow)
        flow_layout.setContentsMargins(14, 12, 14, 12)
        flow_layout.addWidget(label("NEXUS FLOW · CAPAS DEL PERFIL", "eyebrow"))
        flow_scroll = QScrollArea()
        flow_scroll.setWidgetResizable(True)
        flow_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        flow_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        flow_scroll.setFrameShape(QFrame.Shape.NoFrame)
        flow_body = QWidget()
        self.nexus_layers_body = QHBoxLayout(flow_body)
        self.nexus_layers_body.setContentsMargins(0, 0, 0, 2)
        self.nexus_layers_body.setSpacing(8)
        flow_scroll.setWidget(flow_body)
        flow_layout.addWidget(flow_scroll)
        root.addWidget(flow)
        return page

    def _install_nexus_shortcuts(self) -> None:
        self._nexus_shortcuts: List[QShortcut] = []
        for sequence, callback in (
            ("Ctrl+Z", self.undo_advanced),
            ("Ctrl+Y", self.redo_advanced),
            ("Ctrl+Shift+Z", self.redo_advanced),
            ("Ctrl+C", self._nexus_copy_shortcut),
            ("Ctrl+V", self._nexus_paste_shortcut),
            ("Ctrl+D", lambda: self._nexus_duplicate_binding() if self._nexus_is_active() else None),
            ("Delete", self._nexus_delete_shortcut),
            ("Ctrl+F", self._focus_nexus_search),
        ):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)
            self._nexus_shortcuts.append(shortcut)

    def _nexus_is_active(self) -> bool:
        return hasattr(self, "tabs") and self.tabs.currentIndex() == 0

    def _focus_nexus_search(self) -> None:
        if self._nexus_is_active() and hasattr(self, "nexus_search"):
            self.nexus_search.setFocus()
            self.nexus_search.selectAll()

    def _update_history_buttons(self) -> None:
        if hasattr(self, "nexus_undo_button"):
            self.nexus_undo_button.setEnabled(self._history.can_undo)
            self.nexus_redo_button.setEnabled(self._history.can_redo)

    def undo_advanced(self) -> None:
        if not self._nexus_is_active() and self.tabs.currentIndex() != 2:
            return
        snapshot = self._history.undo()
        if snapshot is None:
            self.window.toast("No hay cambios para deshacer", "info")
            return
        self._advanced_config = snapshot
        self._apply_advanced("Cambio deshecho", record_history=False)

    def redo_advanced(self) -> None:
        if not self._nexus_is_active() and self.tabs.currentIndex() != 2:
            return
        snapshot = self._history.redo()
        if snapshot is None:
            self.window.toast("No hay cambios para rehacer", "info")
            return
        self._advanced_config = snapshot
        self._apply_advanced("Cambio rehecho", record_history=False)

    @staticmethod
    def _focused_line_edit() -> Optional[QLineEdit]:
        focus = QApplication.focusWidget()
        return focus if isinstance(focus, QLineEdit) else None

    def _nexus_copy_shortcut(self) -> None:
        editor = self._focused_line_edit()
        if editor is not None:
            editor.copy()
            return
        self._nexus_copy_binding()

    def _nexus_paste_shortcut(self) -> None:
        editor = self._focused_line_edit()
        if editor is not None:
            editor.paste()
            return
        self._nexus_paste_binding()

    def _nexus_delete_shortcut(self) -> None:
        editor = self._focused_line_edit()
        if editor is not None:
            editor.del_()
            return
        if self._nexus_is_active():
            self._nexus_remove_binding()

    def _nexus_copy_binding(self) -> None:
        if not self._nexus_is_active():
            return
        index = self._nexus_selected_index()
        bindings = self._nexus_bindings()
        if not 0 <= index < len(bindings):
            self.window.toast("Selecciona una acción para copiar", "warning")
            return
        self._nexus_clipboard = copy.deepcopy(bindings[index])
        self.window.toast("Acción copiada", "info")

    def _nexus_paste_binding(self) -> None:
        if not self._nexus_is_active():
            return
        if not self._nexus_clipboard:
            self.window.toast("No hay una acción copiada", "warning")
            return
        duplicate = copy.deepcopy(self._nexus_clipboard)
        label_text = str(duplicate.get("label", "")).strip()
        duplicate["label"] = f"{label_text} copia".strip() if label_text else "Acción pegada"
        self._advanced_config["layers"][self._current_layer()].setdefault(
            self._nexus_source, []
        ).append(duplicate)
        self._apply_advanced("Acción pegada")

    def _nexus_move_binding(self, direction: int) -> None:
        index = self._nexus_selected_index()
        bindings = self._advanced_config.get("layers", {}).get(
            self._current_layer(), {}
        ).get(self._nexus_source, [])
        target = index + int(direction)
        if not 0 <= index < len(bindings) or not 0 <= target < len(bindings):
            return
        bindings[index], bindings[target] = bindings[target], bindings[index]
        self._apply_advanced("Orden de acciones actualizado")
        for row in range(self.nexus_actions.count()):
            item = self.nexus_actions.item(row)
            if item and item.data(Qt.ItemDataRole.UserRole) == target:
                self.nexus_actions.setCurrentRow(row)
                break

    def _binding_issue(self, binding_data: Dict[str, Any]) -> str:
        action_type = str(binding_data.get("action_type", ""))
        value = str(binding_data.get("value", "") or "")
        if not binding_data.get("enabled", True):
            return "Acción pausada"
        if action_type == "layer" and value not in self._advanced_config.get("layers", {}):
            return "La capa de destino ya no existe"
        if action_type == "macro":
            engine = self.window.macro_engine
            if not value or not engine or not engine.get_macro(value):
                return "La macro de destino no existe"
        if action_type == "profile":
            engine = self.window.trigger_engine
            if not value or not engine or not engine.get_profile(value):
                return "El perfil de destino no existe"
        if action_type in {"keyboard", "mouse_button", "mouse_move", "controller"} and not value:
            return "Falta elegir un destino"
        if action_type == "gyro" and value not in {"toggle", "enable", "disable", "recenter"}:
            return "Acción de giroscopio desconocida"
        return ""

    def validate_nexus(self) -> None:
        issues: List[tuple[str, str, int, str]] = []
        for layer_name, layer_map in self._advanced_config.get("layers", {}).items():
            for source, bindings in layer_map.items():
                for index, binding_data in enumerate(bindings):
                    issue = self._binding_issue(binding_data)
                    if issue and issue != "Acción pausada":
                        issues.append((layer_name, source, index, issue))
        if not issues:
            self.window.toast("Nexus validado: no hay destinos rotos", "success")
            return
        layer_name, source, binding_index, issue = issues[0]
        self._select_nexus_layer(layer_name)
        self._nexus_select_source(source)
        for row in range(self.nexus_actions.count()):
            item = self.nexus_actions.item(row)
            if item and item.data(Qt.ItemDataRole.UserRole) == binding_index:
                self.nexus_actions.setCurrentRow(row)
                self.nexus_actions.scrollToItem(item)
                break
        self.window.toast(
            f"Nexus encontró {len(issues)} acción{'es' if len(issues) != 1 else ''} por revisar · {issue}",
            "warning",
            5200,
        )

    def _nexus_layer_changed(self, *_args: Any) -> None:
        if self._nexus_loading:
            return
        layer = self.nexus_layer_combo.currentData()
        if layer is None:
            return
        self._loading = True
        self.layer_combo.setCurrentIndex(max(0, self.layer_combo.findData(layer)))
        self._loading = False
        self._refresh_advanced_table()
        self._refresh_nexus()

    def _nexus_select_source(self, source: str) -> None:
        self._nexus_source = source
        self.nexus_controller.set_selected(source)
        self._refresh_nexus_inspector()

    def _nexus_bindings(self) -> List[Dict[str, Any]]:
        layer = self._advanced_config.get("layers", {}).get(self._current_layer(), {})
        return list(layer.get(self._nexus_source, []))

    def _nexus_selected_index(self) -> int:
        item = self.nexus_actions.currentItem()
        if not item:
            return -1
        try:
            return int(item.data(Qt.ItemDataRole.UserRole))
        except (TypeError, ValueError, OverflowError):
            return -1

    def _refresh_nexus_inspector(self) -> None:
        from src.emulator import BUTTON_FRIENDLY_NAMES

        source = self._nexus_source
        bindings = self._nexus_bindings()
        self.nexus_source_title.setText(BUTTON_FRIENDLY_NAMES.get(source, source))
        issues = sum(1 for binding_data in bindings if self._binding_issue(binding_data))
        if bindings:
            issue_text = f" · {issues} por revisar" if issues else ""
            self.nexus_source_hint.setText(
                f"{len(bindings)} acción{'es' if len(bindings) != 1 else ''} en la capa "
                f"{self._current_layer().replace('_', ' ')}{issue_text}."
            )
            self.nexus_source_hint.setStyleSheet(
                f"color:{C['yellow'] if issues else C['muted']}"
            )
        else:
            self.nexus_source_hint.setText(
                "Sin acciones en esta capa. La entrada conserva su comportamiento original."
            )
            self.nexus_source_hint.setStyleSheet(f"color:{C['muted']}")

        selected_index = self._nexus_selected_index()
        query = self.nexus_search.text().strip().lower() if hasattr(self, "nexus_search") else ""
        self.nexus_actions.clear()
        action_names = dict((value, title) for title, value in AdvancedBindingDialog.ACTIONS)
        activation_names = dict((value, title) for title, value in AdvancedBindingDialog.ACTIVATIONS)
        visible_row = -1
        for index, binding_data in enumerate(bindings):
            title = binding_data.get("label") or action_names.get(binding_data.get("action_type"), "Acción")
            destination = binding_data.get("value") or "Sin destino"
            gesture = activation_names.get(binding_data.get("activation"), binding_data.get("activation", ""))
            issue = self._binding_issue(binding_data)
            haystack = f"{title} {destination} {gesture} {issue}".lower()
            if query and query not in haystack:
                continue
            status = f"\n⚠ {issue}" if issue else ""
            item = QListWidgetItem(f"{title}\n{gesture}  ·  {destination}{status}")
            item.setData(Qt.ItemDataRole.UserRole, index)
            item.setToolTip(issue or "Doble clic para editar")
            if issue:
                item.setForeground(QColor(C["yellow"]))
            self.nexus_actions.addItem(item)
            if index == selected_index:
                visible_row = self.nexus_actions.count() - 1
        if visible_row >= 0:
            self.nexus_actions.setCurrentRow(visible_row)
        self._update_history_buttons()

    def _refresh_nexus_layers(self) -> None:
        clear_layout(self.nexus_layers_body)
        default = self._advanced_config.get("default_layer", "base")
        for layer_name, layer_map in self._advanced_config.get("layers", {}).items():
            count = sum(len(items) for items in layer_map.values())
            title = layer_name.replace("_", " ").title()
            if layer_name == default:
                title += "  · inicial"
            layer_button = button(
                f"{title}\n{count} acción{'es' if count != 1 else ''}",
                lambda _=False, name=layer_name: self._select_nexus_layer(name),
            )
            layer_button.setMinimumHeight(54)
            layer_button.setProperty("primary", layer_name == self._current_layer())
            self.nexus_layers_body.addWidget(layer_button)
        self.nexus_layers_body.addStretch()

    def _select_nexus_layer(self, layer_name: str) -> None:
        index = self.nexus_layer_combo.findData(layer_name)
        if index >= 0:
            self.nexus_layer_combo.setCurrentIndex(index)

    def _refresh_nexus(self) -> None:
        if not hasattr(self, "nexus_layer_combo"):
            return
        layer = self._current_layer()
        self._nexus_loading = True
        self.nexus_layer_combo.clear()
        for layer_name in self._advanced_config.get("layers", {}):
            self.nexus_layer_combo.addItem(layer_name.replace("_", " ").title(), layer_name)
        self.nexus_layer_combo.setCurrentIndex(max(0, self.nexus_layer_combo.findData(layer)))
        self._nexus_loading = False
        layer_map = self._advanced_config.get("layers", {}).get(layer, {})
        counts = {source: len(bindings) for source, bindings in layer_map.items()}
        self.nexus_controller.set_counts(counts)
        self.nexus_controller.set_selected(self._nexus_source)
        total = sum(counts.values())
        issue_count = 0
        for bindings in layer_map.values():
            for binding_data in bindings:
                issue = self._binding_issue(binding_data)
                if issue and issue != "Acción pausada":
                    issue_count += 1
        warning = f" · {issue_count} por revisar" if issue_count else ""
        self.nexus_summary.setText(
            f"{len(counts)} entrada{'s' if len(counts) != 1 else ''} · {total} acción{'es' if total != 1 else ''}{warning}"
        )
        self.nexus_summary.setStyleSheet(f"color:{C['yellow'] if issue_count else C['muted']}")
        self._refresh_nexus_inspector()
        self._refresh_nexus_layers()

    def _nexus_add_binding(self) -> None:
        dialog = AdvancedBindingDialog(
            self.window, list(self._advanced_config.get("layers", {})), self._nexus_source
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        source, binding_data = dialog.result_data()
        layer = self._advanced_config["layers"][self._current_layer()]
        layer.setdefault(source, []).append(binding_data)
        self._nexus_source = source
        self._apply_advanced("Acción añadida desde Nexus")

    def _nexus_edit_binding(self) -> None:
        index = self._nexus_selected_index()
        bindings = self._nexus_bindings()
        if not 0 <= index < len(bindings):
            self.window.toast("Selecciona una acción de Nexus", "warning")
            return
        dialog = AdvancedBindingDialog(
            self.window,
            list(self._advanced_config.get("layers", {})),
            self._nexus_source,
            dict(bindings[index]),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        new_source, new_binding = dialog.result_data()
        layer = self._advanced_config["layers"][self._current_layer()]
        layer[self._nexus_source].pop(index)
        if not layer[self._nexus_source]:
            layer.pop(self._nexus_source, None)
        layer.setdefault(new_source, []).append(new_binding)
        self._nexus_source = new_source
        self._apply_advanced("Acción de Nexus actualizada")

    def _nexus_duplicate_binding(self) -> None:
        import copy
        index = self._nexus_selected_index()
        bindings = self._nexus_bindings()
        if not 0 <= index < len(bindings):
            self.window.toast("Selecciona una acción de Nexus", "warning")
            return
        duplicate = copy.deepcopy(bindings[index])
        label_text = str(duplicate.get("label", "")).strip()
        duplicate["label"] = f"{label_text} copia".strip() if label_text else "Copia"
        self._advanced_config["layers"][self._current_layer()].setdefault(self._nexus_source, []).append(duplicate)
        self._apply_advanced("Acción duplicada")

    def _nexus_remove_binding(self) -> None:
        index = self._nexus_selected_index()
        bindings = self._nexus_bindings()
        if not 0 <= index < len(bindings):
            self.window.toast("Selecciona una acción de Nexus", "warning")
            return
        layer = self._advanced_config["layers"][self._current_layer()]
        layer[self._nexus_source].pop(index)
        if not layer[self._nexus_source]:
            layer.pop(self._nexus_source, None)
        self._apply_advanced("Acción eliminada")

    def _nexus_quick_action(self, action_type: str) -> None:
        defaults = {
            "keyboard": {"action_type": "keyboard", "value": "SPACE", "label": "Tecla"},
            "macro": {"action_type": "macro", "value": "", "label": "Macro"},
            "layer": {"action_type": "layer", "value": "base", "label": "Cambiar capa"},
            "gyro": {"action_type": "gyro", "value": "toggle", "label": "Alternar gyro"},
            "disabled": {"action_type": "disabled", "value": "", "label": "Desactivado"},
            "passthrough": {"action_type": "passthrough", "value": "", "label": "Original", "block_original": False},
        }
        binding_data = defaults.get(action_type, {"action_type": action_type})
        dialog = AdvancedBindingDialog(
            self.window, list(self._advanced_config.get("layers", {})), self._nexus_source, binding_data
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        source, result = dialog.result_data()
        self._advanced_config["layers"][self._current_layer()].setdefault(source, []).append(result)
        self._nexus_source = source
        self._apply_advanced("Acción rápida creada")

    def _build_direct_tab(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(14, 14, 14, 14)
        info = QLabel("Cambia un botón por otro sin crear reglas. Es la ruta más simple y rápida.")
        info.setWordWrap(True)
        info.setProperty("muted", True)
        root.addWidget(info)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Botón físico", "Salida virtual", "Estado"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        root.addWidget(self.table)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(button("Restablecer directo", self.reset_direct))
        root.addLayout(row)
        return page

    def _build_advanced_tab(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        toolbar = QHBoxLayout()
        toolbar.addWidget(label("Capa", "muted"))
        self.layer_combo = QComboBox()
        self.layer_combo.setMinimumWidth(190)
        self.layer_combo.currentIndexChanged.connect(self._layer_changed)
        toolbar.addWidget(self.layer_combo)
        self.default_layer = QCheckBox("Capa inicial")
        self.default_layer.toggled.connect(self._set_default_layer)
        toolbar.addWidget(self.default_layer)
        toolbar.addWidget(button("+ Nueva capa", self.add_layer))
        toolbar.addWidget(button("Duplicar capa", self.duplicate_layer))
        toolbar.addWidget(button("Renombrar", self.rename_layer))
        self.delete_layer_button = button("Eliminar", self.delete_layer, danger=True)
        toolbar.addWidget(self.delete_layer_button)
        toolbar.addStretch()
        toolbar.addWidget(button("↶ Deshacer", self.undo_advanced, tooltip="Ctrl+Z"))
        toolbar.addWidget(button("↷ Rehacer", self.redo_advanced, tooltip="Ctrl+Y"))
        root.addLayout(toolbar)

        helper = card(sub=True)
        h = QHBoxLayout(helper)
        h.addWidget(QLabel("⌘"))
        text = QVBoxLayout()
        text.addWidget(label("Una entrada puede hacer varias cosas", "heading"))
        tip = QLabel(
            "Ejemplo: tocar Touchpad abre el mapa, mantenerlo activa otra capa y doble toque recentra el gyro."
        )
        tip.setWordWrap(True)
        tip.setProperty("muted", True)
        text.addWidget(tip)
        h.addLayout(text, 1)
        root.addWidget(helper)

        self.advanced_table = QTableWidget(0, 6)
        self.advanced_table.setHorizontalHeaderLabels(
            ["Botón", "Gesto", "Acción", "Destino", "Condiciones", "Estado"]
        )
        self.advanced_table.horizontalHeader().setStretchLastSection(True)
        self.advanced_table.verticalHeader().hide()
        self.advanced_table.setAlternatingRowColors(True)
        self.advanced_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.advanced_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.advanced_table.doubleClicked.connect(self.edit_binding)
        root.addWidget(self.advanced_table)

        actions = QHBoxLayout()
        actions.addWidget(button("+ Añadir acción", self.add_binding, primary=True))
        actions.addWidget(button("Editar", self.edit_binding))
        actions.addWidget(button("Duplicar", self.duplicate_binding))
        actions.addWidget(button("Eliminar", self.remove_binding, danger=True))
        actions.addStretch()
        self.binding_count = label("0 acciones", "muted")
        actions.addWidget(self.binding_count)
        root.addLayout(actions)
        return page

    def refresh(self) -> None:
        from src.advanced_mapping import sanitize_config
        from src.emulator import BUTTON_FRIENDLY_NAMES, REMAPPABLE_BUTTONS

        emulator = getattr(self.window.connection_manager, "emulator", None)
        mapping = emulator.get_button_map() if emulator else {}
        self.table.setRowCount(len(REMAPPABLE_BUTTONS))
        self.combos.clear()
        choices = [("Sin cambio", ""), ("Desactivado", "none")] + [
            (BUTTON_FRIENDLY_NAMES.get(item, item), item) for item in REMAPPABLE_BUTTONS
        ]
        for row, source in enumerate(REMAPPABLE_BUTTONS):
            self.table.setItem(row, 0, QTableWidgetItem(BUTTON_FRIENDLY_NAMES.get(source, source)))
            combo = QComboBox()
            for title, value in choices:
                combo.addItem(title, value)
            current = mapping.get(source, "")
            combo.setCurrentIndex(max(0, combo.findData(current)))
            self.table.setCellWidget(row, 1, combo)
            self.combos[source] = combo
            self.table.setItem(row, 2, QTableWidgetItem("Personalizado" if current else "Original"))

        # La interfaz muestra el mapa del perfil activo, aunque el motor esté
        # esperando la liberación de un botón para instalarlo de forma segura.
        # Leer solo el runtime podía enseñar durante ese instante el perfil
        # anterior y después quedarse visualmente desfasado.
        trigger = self.window.trigger_engine
        profile_id = trigger.get_current_profile() if trigger else None
        profile = trigger.get_profile(profile_id) if trigger and profile_id else None
        if profile is not None and profile.advanced_mapping_config:
            config = profile.advanced_mapping_config
        elif self.window.profile_manager:
            config = self.window.profile_manager.get_advanced_mapping()
        else:
            mapper = self.window.advanced_mapper
            config = mapper.get_config() if mapper else {}
        self._advanced_config = sanitize_config(config)
        history_profile = str(profile_id or "__global__")
        if self._history_profile != history_profile or self._history.current != self._advanced_config:
            self._history_profile = history_profile
            self._history.reset(self._advanced_config)
        self._update_history_buttons()
        self._loading = True
        self.enabled.setChecked(bool(self._advanced_config.get("enabled", True)))
        current_layer = self.layer_combo.currentData() or self._advanced_config.get("default_layer", "base")
        self.layer_combo.clear()
        for layer_name in self._advanced_config["layers"]:
            self.layer_combo.addItem(layer_name.replace("_", " ").title(), layer_name)
        index = self.layer_combo.findData(current_layer)
        if index < 0:
            index = self.layer_combo.findData(self._advanced_config.get("default_layer", "base"))
        self.layer_combo.setCurrentIndex(max(0, index))
        self._loading = False
        self._refresh_advanced_table()
        self._refresh_nexus()
        self.update_live()

    def _current_layer(self) -> str:
        return str(self.layer_combo.currentData() or "base")

    def _iter_layer_bindings(self) -> List[tuple[str, int, Dict[str, Any]]]:
        layer_map = self._advanced_config.get("layers", {}).get(self._current_layer(), {})
        result: List[tuple[str, int, Dict[str, Any]]] = []
        for source, bindings in layer_map.items():
            for index, binding_data in enumerate(bindings):
                result.append((source, index, binding_data))
        return result

    def _refresh_advanced_table(self) -> None:
        from src.emulator import BUTTON_FRIENDLY_NAMES

        activation_names = dict((value, title) for title, value in AdvancedBindingDialog.ACTIVATIONS)
        action_names = dict((value, title) for title, value in AdvancedBindingDialog.ACTIONS)
        rows = self._iter_layer_bindings()
        self.advanced_table.setRowCount(len(rows))
        issue_count = 0
        for row, (source, index, binding_data) in enumerate(rows):
            issue = self._binding_issue(binding_data)
            if issue:
                issue_count += 1
            values = (
                BUTTON_FRIENDLY_NAMES.get(source, source),
                activation_names.get(binding_data.get("activation"), binding_data.get("activation", "")),
                binding_data.get("label") or action_names.get(binding_data.get("action_type"), binding_data.get("action_type", "")),
                binding_data.get("value") or "—",
                " + ".join(BUTTON_FRIENDLY_NAMES.get(x, x) for x in binding_data.get("requires", [])) or "Ninguna",
                f"Revisar · {issue}" if issue else "Activa",
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, (source, index))
                if issue:
                    item.setForeground(QColor(C["yellow"]))
                    item.setToolTip(issue)
                self.advanced_table.setItem(row, col, item)
        issue_text = f" · {issue_count} por revisar" if issue_count else ""
        self.binding_count.setText(
            f"{len(rows)} acción{'es' if len(rows) != 1 else ''}{issue_text}"
        )
        layer = self._current_layer()
        self._loading = True
        self.default_layer.setChecked(layer == self._advanced_config.get("default_layer"))
        self._loading = False
        self.delete_layer_button.setEnabled(layer != "base")

    def _selected_binding(self) -> Optional[tuple[str, int, Dict[str, Any]]]:
        row = self.advanced_table.currentRow()
        if row < 0:
            return None
        item = self.advanced_table.item(row, 0)
        if not item:
            return None
        source, index = item.data(Qt.ItemDataRole.UserRole)
        bindings = self._advanced_config["layers"][self._current_layer()].get(source, [])
        if not 0 <= index < len(bindings):
            return None
        return source, index, dict(bindings[index])

    def add_binding(self) -> None:
        dialog = AdvancedBindingDialog(
            self.window,
            list(self._advanced_config.get("layers", {})),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        source, binding_data = dialog.result_data()
        layer = self._advanced_config["layers"][self._current_layer()]
        layer.setdefault(source, []).append(binding_data)
        self._apply_advanced("Acción añadida")

    def edit_binding(self, *_args: Any) -> None:
        selected = self._selected_binding()
        if not selected:
            self.window.toast("Selecciona una acción para editar", "warning")
            return
        source, index, binding_data = selected
        dialog = AdvancedBindingDialog(
            self.window,
            list(self._advanced_config.get("layers", {})),
            source,
            binding_data,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        new_source, new_binding = dialog.result_data()
        layer = self._advanced_config["layers"][self._current_layer()]
        layer[source].pop(index)
        if not layer[source]:
            layer.pop(source, None)
        layer.setdefault(new_source, []).append(new_binding)
        self._apply_advanced("Acción actualizada")

    def duplicate_binding(self) -> None:
        import copy

        selected = self._selected_binding()
        if not selected:
            self.window.toast("Selecciona una acción para duplicar", "warning")
            return
        source, _index, binding_data = selected
        duplicate = copy.deepcopy(binding_data)
        label_text = str(duplicate.get("label", "")).strip()
        duplicate["label"] = f"{label_text} copia".strip() if label_text else "Copia"
        self._advanced_config["layers"][self._current_layer()].setdefault(source, []).append(duplicate)
        self._apply_advanced("Acción duplicada")

    def remove_binding(self) -> None:
        selected = self._selected_binding()
        if not selected:
            self.window.toast("Selecciona una acción para eliminar", "warning")
            return
        source, index, _binding_data = selected
        layer = self._advanced_config["layers"][self._current_layer()]
        layer[source].pop(index)
        if not layer[source]:
            layer.pop(source, None)
        self._apply_advanced("Acción eliminada")

    @staticmethod
    def _layer_id(text: str) -> str:
        clean = "_".join(str(text).strip().lower().split())
        return "".join(ch for ch in clean if ch.isalnum() or ch == "_")[:40]

    def add_layer(self) -> None:
        name, ok = QInputDialog.getText(self, "Nueva capa", "Nombre de la capa")
        layer_id = self._layer_id(name)
        if not ok or not layer_id:
            return
        if layer_id in self._advanced_config["layers"]:
            self.window.toast("Ya existe una capa con ese nombre", "warning")
            return
        self._advanced_config["layers"][layer_id] = {}
        self._apply_advanced("Capa creada", selected_layer=layer_id)

    def duplicate_layer(self) -> None:
        source = self._current_layer()
        name, ok = QInputDialog.getText(
            self,
            "Duplicar capa",
            "Nombre de la nueva capa",
            text=f"{source.replace('_', ' ')} copia",
        )
        layer_id = self._layer_id(name)
        if not ok or not layer_id:
            return
        if layer_id in self._advanced_config["layers"]:
            self.window.toast("Ya existe una capa con ese nombre", "warning")
            return
        self._advanced_config["layers"][layer_id] = copy.deepcopy(
            self._advanced_config["layers"].get(source, {})
        )
        self._apply_advanced("Capa duplicada", selected_layer=layer_id)

    def rename_layer(self) -> None:
        old = self._current_layer()
        if old == "base":
            self.window.toast("La capa base no se puede renombrar", "warning")
            return
        name, ok = QInputDialog.getText(self, "Renombrar capa", "Nuevo nombre", text=old.replace("_", " "))
        new = self._layer_id(name)
        if not ok or not new or new == old:
            return
        if new in self._advanced_config["layers"]:
            self.window.toast("Ya existe una capa con ese nombre", "warning")
            return
        layers = self._advanced_config["layers"]
        layers[new] = layers.pop(old)
        if self._advanced_config.get("default_layer") == old:
            self._advanced_config["default_layer"] = new
        for layer_map in layers.values():
            for bindings in layer_map.values():
                for binding_data in bindings:
                    if binding_data.get("action_type") == "layer" and binding_data.get("value") == old:
                        binding_data["value"] = new
        self._apply_advanced("Capa renombrada", selected_layer=new)

    def delete_layer(self) -> None:
        layer = self._current_layer()
        if layer == "base":
            return
        if QMessageBox.question(
            self,
            "Eliminar capa",
            f"¿Eliminar la capa “{layer.replace('_', ' ')}” y todas sus acciones?",
        ) != QMessageBox.StandardButton.Yes:
            return
        self._advanced_config["layers"].pop(layer, None)
        if self._advanced_config.get("default_layer") == layer:
            self._advanced_config["default_layer"] = "base"
        for layer_map in self._advanced_config["layers"].values():
            for bindings in layer_map.values():
                for binding_data in bindings:
                    if binding_data.get("action_type") == "layer" and binding_data.get("value") == layer:
                        binding_data["enabled"] = False
        self._apply_advanced("Capa eliminada", selected_layer="base")

    def _layer_changed(self, *_args: Any) -> None:
        if not self._loading:
            self._refresh_advanced_table()
            self._refresh_nexus()

    def _set_default_layer(self, checked: bool) -> None:
        if self._loading or not checked:
            return
        self._advanced_config["default_layer"] = self._current_layer()
        self._apply_advanced("Capa inicial actualizada", selected_layer=self._current_layer())

    def _apply_advanced(
        self,
        message: str = "",
        selected_layer: Optional[str] = None,
        *,
        record_history: bool = True,
    ) -> None:
        from src.advanced_mapping import sanitize_config

        selected = selected_layer or self._current_layer()
        self._advanced_config = sanitize_config(self._advanced_config)
        if record_history:
            self._history.push(self._advanced_config)
        self._update_history_buttons()
        mapper = self.window.advanced_mapper
        if mapper:
            mapper.set_config(self._advanced_config)
        trigger = self.window.trigger_engine
        profile_id = trigger.get_current_profile() if trigger else None
        profile = trigger.get_profile(profile_id) if trigger and profile_id else None
        if profile is not None:
            profile.advanced_mapping_config = copy.deepcopy(self._advanced_config)
            trigger.update_profile(profile_id, profile)
        if self.window.profile_manager:
            # El mapa global de 2.0 queda intacto como fallback de migración.
            # A partir de 2.1 cada perfil guarda su propio editor avanzado.
            if trigger:
                self.window.profile_manager.set_setting(
                    "profile_overrides", trigger.export_profile_overrides()
                )
                self.window.profile_manager.set_custom_profiles(
                    trigger.export_custom_profiles_to_dict()
                )
            self.window.request_config_save()
        self._loading = True
        self.layer_combo.clear()
        for layer_name in self._advanced_config["layers"]:
            self.layer_combo.addItem(layer_name.replace("_", " ").title(), layer_name)
        self.layer_combo.setCurrentIndex(max(0, self.layer_combo.findData(selected)))
        self._loading = False
        self._refresh_advanced_table()
        self._refresh_nexus()
        self.update_live()
        if message:
            self.window.toast(message, "success")

    def save(self) -> None:
        mapping = {
            source: combo.currentData()
            for source, combo in self.combos.items()
            if combo.currentData()
        }
        emulator = getattr(self.window.connection_manager, "emulator", None)
        if emulator:
            emulator.set_button_map(mapping)
        if self.window.profile_manager:
            self.window.profile_manager.set_button_map(mapping)
        self._advanced_config["enabled"] = self.enabled.isChecked()
        self._apply_advanced()
        if self.window.profile_manager:
            self.window.request_config_save()
        self.window.dashboard.refresh_mapping()
        self.refresh()
        self.window.toast("Mapper guardado", "success")

    def reset_direct(self) -> None:
        for combo in self.combos.values():
            combo.setCurrentIndex(0)
        emulator = getattr(self.window.connection_manager, "emulator", None)
        if emulator:
            emulator.set_button_map({})
        if self.window.profile_manager:
            self.window.profile_manager.set_button_map({})
            self.window.request_config_save()
        self.refresh()
        self.window.toast("Remapeo directo restablecido")

    def toggle_advanced(self, enabled: bool) -> None:
        if self._loading:
            return
        self._advanced_config["enabled"] = bool(enabled)
        self._apply_advanced()
        self.window.toast("Remapeo avanzado activado" if enabled else "Remapeo avanzado pausado")

    def update_live(self) -> None:
        mapper = self.window.advanced_mapper
        if not mapper:
            self.layer_badge.setText("Capa activa: no disponible")
            if hasattr(self, "nexus_controller"):
                self.nexus_controller.set_pressed(set())
            return
        active = mapper.get_active_layer()
        title = active.replace('_', ' ').title()
        self.layer_badge.setText(f"Capa activa: {title}")
        if hasattr(self, "nexus_runtime_badge"):
            diagnostics = mapper.get_diagnostics_snapshot()
            pressed = diagnostics.get("pressed_sources", [])
            self.nexus_controller.set_pressed(pressed)
            suffix = f" · {len(pressed)} entrada{'s' if len(pressed) != 1 else ''}" if pressed else ""
            self.nexus_runtime_badge.setText(f"Capa activa: {title}{suffix}")
