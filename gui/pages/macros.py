"""MacroStickPad, MacroStepDialog, MacroComboDialog, MacroEditorDialog, MacrosPage extraídos de la antigua interfaz monolítica."""

from __future__ import annotations

from typing import TYPE_CHECKING


from ..ui_common import (
    logging,
    Any,
    C,
    Dict,
    List,
    Optional,
    Path,
    QCheckBox,
    QColor,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QMouseEvent,
    QPainter,
    QPen,
    QPointF,
    QRectF,
    QSize,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
    button,
    card,
    configure_tabs,
    json,
    label,
    os,
    read_json_file_limited,
    time,
)
from ..components import ScrollPage

if TYPE_CHECKING:
    from ..main_window import NikaidoWindow

logger = logging.getLogger(__name__)

class MacroStickPad(QWidget):
    """Selector visual para una posición de palanca entre -100 % y 100 %."""

    changed = Signal(float, float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._x = 0.0
        self._y = 0.0
        self._dragging = False
        self.setMinimumSize(190, 190)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def sizeHint(self) -> QSize:
        return QSize(210, 210)

    def set_value(self, x: float, y: float, *, emit: bool = False) -> None:
        x = max(-1.0, min(1.0, float(x)))
        y = max(-1.0, min(1.0, float(y)))
        length = (x * x + y * y) ** 0.5
        if length > 1.0:
            x /= length
            y /= length
        if abs(x - self._x) < 0.0001 and abs(y - self._y) < 0.0001:
            return
        self._x, self._y = x, y
        self.update()
        if emit:
            self.changed.emit(self._x, self._y)

    def _set_from_point(self, point: QPointF) -> None:
        side = max(1.0, min(self.width(), self.height()) - 28.0)
        radius = side / 2.0
        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        x = (point.x() - center.x()) / radius
        y = (point.y() - center.y()) / radius
        self.set_value(x, y, emit=True)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._set_from_point(event.position())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            self._set_from_point(event.position())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False

    def paintEvent(self, _event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = max(1.0, min(self.width(), self.height()) - 28.0)
        radius = side / 2.0
        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        outer = QRectF(center.x() - radius, center.y() - radius, side, side)

        painter.setBrush(QColor(C["panel2"]))
        painter.setPen(QPen(QColor(C["border"]), 2))
        painter.drawEllipse(outer)
        painter.setPen(QPen(QColor(C["faint"]), 1))
        painter.drawLine(QPointF(center.x() - radius, center.y()), QPointF(center.x() + radius, center.y()))
        painter.drawLine(QPointF(center.x(), center.y() - radius), QPointF(center.x(), center.y() + radius))
        painter.drawEllipse(QRectF(center.x() - radius * 0.5, center.y() - radius * 0.5, radius, radius))

        dot = QPointF(center.x() + self._x * radius, center.y() + self._y * radius)
        painter.setBrush(QColor(C["accent2"]))
        painter.setPen(QPen(QColor("white"), 2))
        painter.drawEllipse(dot, 9, 9)


class MacroStepDialog(QDialog):
    """Editor visual para un botón, espera, palanca o gatillo de la macro."""

    def __init__(self, parent: QWidget, step: Optional[Any] = None, forced_type: Optional[str] = None) -> None:
        super().__init__(parent)
        from src.macro_engine import BUTTON_LABELS, MacroStep, StepType

        self._MacroStep = MacroStep
        self._StepType = StepType
        self.setWindowTitle("Editar acción" if step else "Añadir acción")
        self.setMinimumWidth(560)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)
        root.addWidget(label("Acción de la macro", "heading"))
        root.addWidget(label("Define qué hace el control y cuánto espera antes de continuar.", "muted"))

        form = QFormLayout()
        form.setSpacing(10)
        root.addLayout(form)
        self.form = form

        self.type_combo = QComboBox()
        for title, value in (
            ("Tocar botón", StepType.TAP.value),
            ("Presionar y mantener", StepType.PRESS.value),
            ("Soltar botón", StepType.RELEASE.value),
            ("Esperar", StepType.WAIT.value),
            ("Mover palanca", StepType.STICK.value),
            ("Mover gatillo analógico", StepType.TRIGGER.value),
        ):
            self.type_combo.addItem(title, value)
        form.addRow("Tipo", self.type_combo)

        self.button_combo = QComboBox()
        for key, title in BUTTON_LABELS.items():
            self.button_combo.addItem(title, key)
        form.addRow("Botón", self.button_combo)

        self.stick_combo = QComboBox()
        self.stick_combo.addItem("Palanca izquierda", "left")
        self.stick_combo.addItem("Palanca derecha", "right")
        form.addRow("Palanca", self.stick_combo)

        self.stick_editor = QWidget()
        stick_row = QHBoxLayout(self.stick_editor)
        stick_row.setContentsMargins(0, 0, 0, 0)
        stick_row.setSpacing(14)
        self.stick_pad = MacroStickPad()
        stick_row.addWidget(self.stick_pad)
        axis_box = QVBoxLayout()
        axis_box.addWidget(label("POSICIÓN", "eyebrow"))
        self.x_spin = QSpinBox()
        self.x_spin.setRange(-100, 100)
        self.x_spin.setSuffix(" %")
        self.y_spin = QSpinBox()
        self.y_spin.setRange(-100, 100)
        self.y_spin.setSuffix(" %")
        axis_form = QFormLayout()
        axis_form.addRow("Horizontal X", self.x_spin)
        axis_form.addRow("Vertical Y", self.y_spin)
        axis_box.addLayout(axis_form)
        quick = QGridLayout()
        for row, col, text, x, y in (
            (0, 1, "↑", 0.0, -1.0),
            (1, 0, "←", -1.0, 0.0),
            (1, 1, "Centro", 0.0, 0.0),
            (1, 2, "→", 1.0, 0.0),
            (2, 1, "↓", 0.0, 1.0),
        ):
            quick.addWidget(
                button(text, lambda _checked=False, _x=x, _y=y: self._set_stick(_x, _y)),
                row,
                col,
            )
        axis_box.addLayout(quick)
        axis_box.addStretch()
        stick_row.addLayout(axis_box, 1)
        form.addRow("Posición", self.stick_editor)

        self.trigger_combo = QComboBox()
        self.trigger_combo.addItem("L2", "left")
        self.trigger_combo.addItem("R2", "right")
        form.addRow("Gatillo", self.trigger_combo)

        self.value_spin = QSpinBox()
        self.value_spin.setRange(0, 100)
        self.value_spin.setSuffix(" %")
        form.addRow("Presión", self.value_spin)

        self.ms_spin = QSpinBox()
        self.ms_spin.setRange(0, 60_000)
        self.ms_spin.setSingleStep(10)
        self.ms_spin.setSuffix(" ms")
        form.addRow("Duración", self.ms_spin)

        self.after_spin = QSpinBox()
        self.after_spin.setRange(0, 60_000)
        self.after_spin.setSingleStep(10)
        self.after_spin.setSuffix(" ms")
        form.addRow("Esperar después", self.after_spin)

        hint = label(
            "Con 0 ms, una palanca o gatillo se mantiene hasta la siguiente acción que lo cambie. "
            "El tiempo “después” controla el espacio exacto entre esta acción y la siguiente.",
            "muted",
        )
        hint.setWordWrap(True)
        root.addWidget(hint)

        actions = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        actions.accepted.connect(self.accept)
        actions.rejected.connect(self.reject)
        root.addWidget(actions)

        if step:
            index = self.type_combo.findData(step.type.value)
            self.type_combo.setCurrentIndex(max(0, index))
            if step.button:
                self.button_combo.setCurrentIndex(max(0, self.button_combo.findData(step.button)))
            if step.stick:
                self.stick_combo.setCurrentIndex(max(0, self.stick_combo.findData(step.stick)))
            self._set_stick(float(step.x), float(step.y))
            if step.trigger:
                self.trigger_combo.setCurrentIndex(max(0, self.trigger_combo.findData(step.trigger)))
            self.value_spin.setValue(round(int(step.value) * 100 / 255))
            self.ms_spin.setValue(int(step.ms))
            self.after_spin.setValue(int(getattr(step, "after_ms", 0)))
        else:
            self.ms_spin.setValue(60)
            self.after_spin.setValue(80)
            self.value_spin.setValue(100)

        if forced_type:
            index = self.type_combo.findData(forced_type)
            if index >= 0:
                self.type_combo.setCurrentIndex(index)
                self.type_combo.setEnabled(False)
                if forced_type == "wait":
                    self.ms_spin.setValue(100)
                    self.after_spin.setValue(0)
                elif forced_type in ("stick", "trigger"):
                    self.ms_spin.setValue(120)
                    self.after_spin.setValue(50)

        self.type_combo.currentIndexChanged.connect(self._update_fields)
        self.x_spin.valueChanged.connect(self._axis_changed)
        self.y_spin.valueChanged.connect(self._axis_changed)
        self.stick_pad.changed.connect(self._pad_changed)
        self._update_fields()

    def _set_stick(self, x: float, y: float) -> None:
        self.x_spin.blockSignals(True)
        self.y_spin.blockSignals(True)
        self.x_spin.setValue(round(x * 100))
        self.y_spin.setValue(round(y * 100))
        self.x_spin.blockSignals(False)
        self.y_spin.blockSignals(False)
        self.stick_pad.set_value(x, y)

    def _axis_changed(self, _value: int) -> None:
        self.stick_pad.set_value(
            self.x_spin.value() / 100.0,
            self.y_spin.value() / 100.0,
            emit=True,
        )

    def _pad_changed(self, x: float, y: float) -> None:
        self.x_spin.blockSignals(True)
        self.y_spin.blockSignals(True)
        self.x_spin.setValue(round(x * 100))
        self.y_spin.setValue(round(y * 100))
        self.x_spin.blockSignals(False)
        self.y_spin.blockSignals(False)

    def _set_row_visible(self, widget: QWidget, visible: bool) -> None:
        widget.setVisible(visible)
        label_widget = self.form.labelForField(widget)
        if label_widget:
            label_widget.setVisible(visible)

    def _update_fields(self) -> None:
        value = self.type_combo.currentData()
        self._set_row_visible(self.button_combo, value in ("tap", "press", "release"))
        self._set_row_visible(self.stick_combo, value == "stick")
        self._set_row_visible(self.stick_editor, value == "stick")
        self._set_row_visible(self.trigger_combo, value == "trigger")
        self._set_row_visible(self.value_spin, value == "trigger")
        self._set_row_visible(self.ms_spin, value in ("tap", "wait", "stick", "trigger"))
        self._set_row_visible(self.after_spin, value != "wait")
        duration_label = self.form.labelForField(self.ms_spin)
        if duration_label:
            duration_label.setText({
                "tap": "Mantener presionado",
                "wait": "Tiempo de espera",
                "stick": "Duración activa",
                "trigger": "Duración activa",
            }.get(value, "Duración"))

    def step(self) -> Any:
        step_type = self._StepType(self.type_combo.currentData())
        after_ms = self.after_spin.value() if step_type != self._StepType.WAIT else 0
        if step_type in (self._StepType.TAP, self._StepType.PRESS, self._StepType.RELEASE):
            return self._MacroStep(
                step_type,
                button=self.button_combo.currentData(),
                ms=self.ms_spin.value() if step_type == self._StepType.TAP else 0,
                after_ms=after_ms,
            )
        if step_type == self._StepType.WAIT:
            return self._MacroStep(step_type, ms=self.ms_spin.value())
        if step_type == self._StepType.STICK:
            return self._MacroStep(
                step_type,
                stick=self.stick_combo.currentData(),
                x=self.x_spin.value() / 100.0,
                y=self.y_spin.value() / 100.0,
                ms=self.ms_spin.value(),
                after_ms=after_ms,
            )
        return self._MacroStep(
            step_type,
            trigger=self.trigger_combo.currentData(),
            value=round(self.value_spin.value() * 255 / 100),
            ms=self.ms_spin.value(),
            after_ms=after_ms,
        )


class MacroComboDialog(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        from src.macro_engine import BUTTON_LABELS

        self.setWindowTitle("Añadir combo de botones")
        self.setMinimumSize(440, 540)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.addWidget(label("Botones del combo", "heading"))
        root.addWidget(label("Se presionan juntos y se sueltan en orden inverso.", "muted"))
        self.buttons = QListWidget()
        for key, title in BUTTON_LABELS.items():
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.buttons.addItem(item)
        root.addWidget(self.buttons, 1)
        form = QFormLayout()
        self.hold = QSpinBox()
        self.hold.setRange(20, 5000)
        self.hold.setValue(100)
        self.hold.setSuffix(" ms")
        form.addRow("Mantener combo", self.hold)
        self.after = QSpinBox()
        self.after.setRange(0, 60_000)
        self.after.setSingleStep(10)
        self.after.setValue(80)
        self.after.setSuffix(" ms")
        form.addRow("Esperar después", self.after)
        root.addLayout(form)
        self.validation = QLabel("")
        self.validation.setStyleSheet(f"color:{C['danger']}")
        self.validation.setWordWrap(True)
        root.addWidget(self.validation)
        actions = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        actions.accepted.connect(self._validate)
        actions.rejected.connect(self.reject)
        root.addWidget(actions)

    def selected_buttons(self) -> List[str]:
        result: List[str] = []
        for row in range(self.buttons.count()):
            item = self.buttons.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                result.append(item.data(Qt.ItemDataRole.UserRole))
        return result

    def _validate(self) -> None:
        if len(self.selected_buttons()) < 2:
            self.validation.setText("Selecciona al menos dos botones.")
            return
        self.accept()


class MacroEditorDialog(QDialog):
    def __init__(
        self,
        page: "MacrosPage",
        macro: Optional[Any] = None,
        auto_record: bool = False,
    ) -> None:
        super().__init__(page)
        from src.macro_engine import (
            BUTTON_LABELS,
            DIRECTION_LABELS,
            Macro,
            MacroStep,
            MacroTrigger,
            StepType,
            TriggerEdge,
            TriggerKind,
        )

        self.page = page
        self.window_ref = page.window
        self.engine = page.window.macro_engine
        self._Macro = Macro
        self._MacroStep = MacroStep
        self._MacroTrigger = MacroTrigger
        self._StepType = StepType
        self._TriggerEdge = TriggerEdge
        self._TriggerKind = TriggerKind
        self.editing_id = macro.id if macro else None
        self.steps = [MacroStep.from_dict(step.to_dict()) for step in (macro.steps if macro else [])]
        self._recording = False
        self._record_started = 0.0
        self._record_base_steps: List[Any] = []
        self._record_preview_count = -1

        self.setWindowTitle("Editar macro" if macro else "Nueva macro")
        self.resize(980, 780)
        self.setMinimumSize(860, 680)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        title_row = QHBoxLayout()
        title_row.addWidget(label("Editor de macros", "title"))
        title_row.addStretch()
        self.enabled = QCheckBox("Macro activa")
        self.enabled.setChecked(bool(macro.enabled) if macro else True)
        title_row.addWidget(self.enabled)
        root.addLayout(title_row)
        root.addWidget(
            label(
                "Crea secuencias de botones, combos, palancas y gatillos. Después decide cómo y en qué perfiles se activan.",
                "muted",
            )
        )

        tabs = configure_tabs(QTabWidget())
        root.addWidget(tabs, 1)

        general = QWidget()
        general_layout = QVBoxLayout(general)
        general_layout.setContentsMargins(14, 14, 14, 14)
        general_layout.setSpacing(12)
        tabs.addTab(general, "General y activador")

        identity = card()
        identity_form = QFormLayout(identity)
        identity_form.setContentsMargins(14, 14, 14, 14)
        self.name = QLineEdit(macro.name if macro else "Nueva macro")
        self.description = QLineEdit(macro.description if macro else "")
        self.description.setPlaceholderText("Ejemplo: combo rápido de construcción")
        self.repeat = QSpinBox()
        self.repeat.setRange(1, 50)
        self.repeat.setValue(int(macro.repeat) if macro else 1)
        self.cooldown = QSpinBox()
        self.cooldown.setRange(0, 10_000)
        self.cooldown.setSingleStep(50)
        self.cooldown.setSuffix(" ms")
        self.cooldown.setValue(int(macro.cooldown_ms) if macro else 250)
        identity_form.addRow("Nombre", self.name)
        identity_form.addRow("Descripción", self.description)
        identity_form.addRow("Repeticiones", self.repeat)
        identity_form.addRow("Protección entre activaciones", self.cooldown)
        general_layout.addWidget(identity)

        activation = card()
        activation_box = QVBoxLayout(activation)
        activation_box.setContentsMargins(14, 14, 14, 14)
        activation_box.addWidget(label("Cómo se activa", "heading"))
        activation_box.addWidget(
            label("Puede ser manual, un botón, varios botones juntos, una palanca o la presión de L2/R2.", "muted")
        )
        activation_form = QFormLayout()
        self.activation_form = activation_form
        activation_box.addLayout(activation_form)
        self.trigger_kind = QComboBox()
        self.trigger_kind.addItem("Solo manual", TriggerKind.MANUAL.value)
        self.trigger_kind.addItem("Un botón", TriggerKind.BUTTON.value)
        self.trigger_kind.addItem("Combo de botones", TriggerKind.COMBO.value)
        self.trigger_kind.addItem("Dirección de palanca", TriggerKind.STICK.value)
        self.trigger_kind.addItem("Presión de L2 o R2", TriggerKind.TRIGGER.value)
        activation_form.addRow("Activador", self.trigger_kind)

        self.trigger_edge = QComboBox()
        self.trigger_edge.addItem("Al presionar o entrar", TriggerEdge.PRESS.value)
        self.trigger_edge.addItem("Al soltar o volver", TriggerEdge.RELEASE.value)
        self.trigger_edge.addItem("Repetir mientras se mantenga", TriggerEdge.WHILE_HELD.value)
        activation_form.addRow("Ejecutar", self.trigger_edge)

        self.trigger_button = QComboBox()
        for key, title in BUTTON_LABELS.items():
            self.trigger_button.addItem(title, key)
        activation_form.addRow("Botón", self.trigger_button)

        self.trigger_combo_list = QListWidget()
        self.trigger_combo_list.setMaximumHeight(170)
        for key, title in BUTTON_LABELS.items():
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.trigger_combo_list.addItem(item)
        activation_form.addRow("Botones del combo", self.trigger_combo_list)

        self.trigger_stick = QComboBox()
        self.trigger_stick.addItem("Palanca izquierda", "left")
        self.trigger_stick.addItem("Palanca derecha", "right")
        activation_form.addRow("Palanca", self.trigger_stick)
        self.trigger_direction = QComboBox()
        for key, title in DIRECTION_LABELS.items():
            self.trigger_direction.addItem(title, key)
        activation_form.addRow("Dirección", self.trigger_direction)
        self.trigger_analog = QComboBox()
        self.trigger_analog.addItem("L2", "left")
        self.trigger_analog.addItem("R2", "right")
        activation_form.addRow("Gatillo", self.trigger_analog)
        self.trigger_threshold = QSpinBox()
        self.trigger_threshold.setRange(10, 95)
        self.trigger_threshold.setValue(65)
        self.trigger_threshold.setSuffix(" %")
        activation_form.addRow("Umbral", self.trigger_threshold)
        general_layout.addWidget(activation)

        profiles_card = card()
        profiles_box = QVBoxLayout(profiles_card)
        profiles_box.setContentsMargins(14, 14, 14, 14)
        profiles_box.addWidget(label("Perfiles donde funciona", "heading"))
        self.profile_mode = QComboBox()
        self.profile_mode.addItem("Todos los perfiles", "all")
        self.profile_mode.addItem("Solo los perfiles seleccionados", "selected")
        profiles_box.addWidget(self.profile_mode)
        self.profile_tools_widget = QWidget()
        profile_tools = QHBoxLayout(self.profile_tools_widget)
        profile_tools.setContentsMargins(0, 0, 0, 0)
        profile_tools.addWidget(button("Perfil actual", self.select_current_profile))
        profile_tools.addWidget(button("Seleccionar todos", self.select_all_profiles))
        profile_tools.addWidget(button("Limpiar", self.clear_profiles))
        profile_tools.addStretch()
        profiles_box.addWidget(self.profile_tools_widget)
        self.profile_list = QListWidget()
        self.profile_list.setMaximumHeight(180)
        profiles = self.window_ref.trigger_engine.get_profile_names() if self.window_ref.trigger_engine else []
        for profile_id, profile_name in profiles:
            item = QListWidgetItem(profile_name)
            item.setData(Qt.ItemDataRole.UserRole, profile_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checked = bool(macro and profile_id in macro.profile_ids)
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            self.profile_list.addItem(item)
        profiles_box.addWidget(self.profile_list)
        general_layout.addWidget(profiles_card)
        general_layout.addStretch()

        sequence = QWidget()
        sequence_layout = QVBoxLayout(sequence)
        sequence_layout.setContentsMargins(14, 14, 14, 14)
        sequence_layout.setSpacing(10)
        tabs.addTab(sequence, "Secuencia")

        record_card = card()
        record_row = QHBoxLayout(record_card)
        record_row.setContentsMargins(14, 12, 14, 12)
        record_info = QVBoxLayout()
        record_info.addWidget(label("Grabar desde el DualSense", "heading"))
        self.record_status = label("Reemplaza la secuencia con lo que hagas en el control.", "muted")
        record_info.addWidget(self.record_status)
        record_row.addLayout(record_info, 1)
        self.record_sticks = QCheckBox("Incluir palancas y gatillos")
        self.record_sticks.setChecked(True)
        record_row.addWidget(self.record_sticks)
        self.record_append = QCheckBox("Añadir al final")
        self.record_append.setChecked(False)
        record_row.addWidget(self.record_append)
        self.record_button = button("● Grabar", self.toggle_recording, danger=True)
        record_row.addWidget(self.record_button)
        sequence_layout.addWidget(record_card)

        toolbar = QHBoxLayout()
        toolbar.addWidget(button("+ Botón", self.add_button_step))
        toolbar.addWidget(button("+ Combo", self.add_combo_steps))
        toolbar.addWidget(button("+ Palanca", self.add_stick_step))
        toolbar.addWidget(button("+ Gatillo", self.add_trigger_step))
        toolbar.addWidget(button("+ Espera", self.add_wait_step))
        toolbar.addStretch()
        toolbar.addWidget(button("Editar", self.edit_step))
        toolbar.addWidget(button("Duplicar", self.duplicate_step))
        toolbar.addWidget(button("Intervalo…", self.set_uniform_delay))
        toolbar.addWidget(button("↑", lambda: self.move_step(-1)))
        toolbar.addWidget(button("↓", lambda: self.move_step(1)))
        toolbar.addWidget(button("Eliminar", self.delete_step, danger=True))
        sequence_layout.addLayout(toolbar)

        self.steps_table = QTableWidget(0, 5)
        self.steps_table.setHorizontalHeaderLabels(["#", "Tipo", "Acción", "Duración", "Después"])
        self.steps_table.setColumnWidth(0, 48)
        self.steps_table.setColumnWidth(1, 130)
        self.steps_table.setColumnWidth(3, 105)
        self.steps_table.setColumnWidth(4, 125)
        self.steps_table.horizontalHeader().setStretchLastSection(False)
        self.steps_table.verticalHeader().setVisible(False)
        self.steps_table.setAlternatingRowColors(True)
        self.steps_table.doubleClicked.connect(self.edit_step)
        sequence_layout.addWidget(self.steps_table, 1)
        self.sequence_summary = label("", "muted")
        sequence_layout.addWidget(self.sequence_summary)

        bottom = QHBoxLayout()
        self.test_button = button("▶ Probar secuencia", self.test_steps)
        bottom.addWidget(self.test_button)
        self.stop_button = button("■ Detener", self.stop_preview)
        bottom.addWidget(self.stop_button)
        bottom.addStretch()
        cancel = button("Cancelar", self.reject)
        save = button("Guardar macro", self.save, primary=True)
        bottom.addWidget(cancel)
        bottom.addWidget(save)
        root.addLayout(bottom)

        trigger = macro.trigger if macro else MacroTrigger()
        self.trigger_kind.setCurrentIndex(max(0, self.trigger_kind.findData(trigger.kind.value)))
        if trigger.buttons:
            self.trigger_button.setCurrentIndex(max(0, self.trigger_button.findData(trigger.buttons[0])))
            for row in range(self.trigger_combo_list.count()):
                item = self.trigger_combo_list.item(row)
                if item.data(Qt.ItemDataRole.UserRole) in trigger.buttons:
                    item.setCheckState(Qt.CheckState.Checked)
        self.trigger_stick.setCurrentIndex(max(0, self.trigger_stick.findData(trigger.stick)))
        self.trigger_direction.setCurrentIndex(max(0, self.trigger_direction.findData(trigger.direction)))
        self.trigger_analog.setCurrentIndex(max(0, self.trigger_analog.findData(trigger.analog_trigger)))
        self.trigger_threshold.setValue(round(trigger.threshold * 100))
        self.trigger_edge.setCurrentIndex(max(0, self.trigger_edge.findData(trigger.edge.value)))
        if macro and macro.profile_ids:
            self.profile_mode.setCurrentIndex(1)

        self.trigger_kind.currentIndexChanged.connect(self._update_trigger_fields)
        self.profile_mode.currentIndexChanged.connect(self._update_profile_fields)
        self.repeat.valueChanged.connect(self.refresh_steps)
        self._update_trigger_fields()
        self._update_profile_fields()
        self.refresh_steps()

        self.record_timer = QTimer(self)
        self.record_timer.setInterval(100)
        self.record_timer.timeout.connect(self._record_tick)
        if auto_record:
            self.auto_record_timer = QTimer(self)
            self.auto_record_timer.setSingleShot(True)
            self.auto_record_timer.timeout.connect(self.toggle_recording)
            self.auto_record_timer.start(150)

    def _set_form_visible(self, form: QFormLayout, widget: QWidget, visible: bool) -> None:
        widget.setVisible(visible)
        label_widget = form.labelForField(widget)
        if label_widget:
            label_widget.setVisible(visible)

    def _update_trigger_fields(self) -> None:
        form = self.activation_form
        kind = self.trigger_kind.currentData()
        self._set_form_visible(form, self.trigger_edge, kind != "manual")
        self._set_form_visible(form, self.trigger_button, kind == "button")
        self._set_form_visible(form, self.trigger_combo_list, kind == "combo")
        self._set_form_visible(form, self.trigger_stick, kind == "stick")
        self._set_form_visible(form, self.trigger_direction, kind == "stick")
        self._set_form_visible(form, self.trigger_analog, kind == "trigger")
        self._set_form_visible(form, self.trigger_threshold, kind in ("stick", "trigger"))

    def _update_profile_fields(self) -> None:
        visible = self.profile_mode.currentData() == "selected"
        self.profile_list.setVisible(visible)
        self.profile_tools_widget.setVisible(visible)

    def _set_profile_checks(self, checked_ids: set[str]) -> None:
        for row in range(self.profile_list.count()):
            item = self.profile_list.item(row)
            item.setCheckState(
                Qt.CheckState.Checked
                if item.data(Qt.ItemDataRole.UserRole) in checked_ids
                else Qt.CheckState.Unchecked
            )

    def select_current_profile(self) -> None:
        profile_id = self.window_ref.trigger_engine.get_current_profile() if self.window_ref.trigger_engine else None
        self.profile_mode.setCurrentIndex(max(0, self.profile_mode.findData("selected")))
        self._set_profile_checks({profile_id} if profile_id else set())

    def select_all_profiles(self) -> None:
        self.profile_mode.setCurrentIndex(max(0, self.profile_mode.findData("selected")))
        ids = {
            self.profile_list.item(row).data(Qt.ItemDataRole.UserRole)
            for row in range(self.profile_list.count())
        }
        self._set_profile_checks(ids)

    def clear_profiles(self) -> None:
        self.profile_mode.setCurrentIndex(max(0, self.profile_mode.findData("selected")))
        self._set_profile_checks(set())

    def selected_profile_ids(self) -> List[str]:
        if self.profile_mode.currentData() == "all":
            return []
        result: List[str] = []
        for row in range(self.profile_list.count()):
            item = self.profile_list.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                result.append(item.data(Qt.ItemDataRole.UserRole))
        return result

    def selected_combo_buttons(self) -> List[str]:
        result: List[str] = []
        for row in range(self.trigger_combo_list.count()):
            item = self.trigger_combo_list.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                result.append(item.data(Qt.ItemDataRole.UserRole))
        return result

    def build_trigger(self) -> Any:
        kind = self._TriggerKind(self.trigger_kind.currentData())
        buttons: List[str] = []
        if kind == self._TriggerKind.BUTTON:
            buttons = [self.trigger_button.currentData()]
        elif kind == self._TriggerKind.COMBO:
            buttons = self.selected_combo_buttons()
        return self._MacroTrigger(
            kind=kind,
            buttons=buttons,
            stick=self.trigger_stick.currentData(),
            direction=self.trigger_direction.currentData(),
            analog_trigger=self.trigger_analog.currentData(),
            threshold=self.trigger_threshold.value() / 100.0,
            edge=self._TriggerEdge(self.trigger_edge.currentData()),
        )

    def refresh_steps(self, *_args: Any) -> None:
        self.steps_table.setRowCount(len(self.steps))
        names = {
            self._StepType.TAP: "Toque",
            self._StepType.PRESS: "Presionar",
            self._StepType.RELEASE: "Soltar",
            self._StepType.WAIT: "Espera",
            self._StepType.STICK: "Palanca",
            self._StepType.TRIGGER: "Gatillo",
        }
        for row, step in enumerate(self.steps):
            values = [
                str(row + 1),
                names.get(step.type, step.type.value),
                step.describe(),
                f"{step.ms} ms" if step.ms else "—",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if column in (0, 3):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.steps_table.setItem(row, column, item)

            delay = QSpinBox()
            delay.setRange(0, 60_000)
            delay.setSingleStep(10)
            delay.setSuffix(" ms")
            delay.setValue(int(getattr(step, "after_ms", 0)))
            delay.setToolTip("Tiempo antes de ejecutar la siguiente acción")
            delay.setEnabled(
                step.type != self._StepType.WAIT and not self._recording
            )
            delay.valueChanged.connect(lambda value, index=row: self._set_step_delay(index, value))
            self.steps_table.setCellWidget(row, 4, delay)

        self.steps_table.resizeColumnToContents(1)
        self.steps_table.setColumnWidth(2, max(330, self.steps_table.viewport().width() - 470))
        total_ms = sum(
            max(0, int(step.ms)) + max(0, int(getattr(step, "after_ms", 0)))
            for step in self.steps
        ) * self.repeat.value()
        analog = sum(step.type in (self._StepType.STICK, self._StepType.TRIGGER) for step in self.steps)
        self.sequence_summary.setText(
            f"{len(self.steps)} acciones · duración aproximada {total_ms / 1000:.2f} s · "
            f"{analog} movimientos analógicos · repetir {self.repeat.value()}×"
        )

    def _set_step_delay(self, row: int, value: int) -> None:
        if 0 <= row < len(self.steps):
            self.steps[row].after_ms = max(0, min(60_000, int(value)))
            total_ms = sum(
                max(0, int(step.ms)) + max(0, int(getattr(step, "after_ms", 0)))
                for step in self.steps
            ) * self.repeat.value()
            analog = sum(step.type in (self._StepType.STICK, self._StepType.TRIGGER) for step in self.steps)
            self.sequence_summary.setText(
                f"{len(self.steps)} acciones · duración aproximada {total_ms / 1000:.2f} s · "
                f"{analog} movimientos analógicos · repetir {self.repeat.value()}×"
            )

    def current_step_row(self) -> int:
        row = self.steps_table.currentRow()
        return row if 0 <= row < len(self.steps) else -1

    def _append_step_dialog(self, forced_type: Optional[str] = None) -> None:
        dialog = MacroStepDialog(self, forced_type=forced_type)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.steps.append(dialog.step())
            self.refresh_steps()
            self.steps_table.selectRow(len(self.steps) - 1)

    def add_button_step(self) -> None:
        self._append_step_dialog()

    def add_wait_step(self) -> None:
        self._append_step_dialog("wait")

    def add_stick_step(self) -> None:
        self._append_step_dialog("stick")

    def add_trigger_step(self) -> None:
        self._append_step_dialog("trigger")

    def add_combo_steps(self) -> None:
        dialog = MacroComboDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        buttons = dialog.selected_buttons()
        self.steps.extend(self._MacroStep(self._StepType.PRESS, button=name) for name in buttons)
        self.steps.append(self._MacroStep(self._StepType.WAIT, ms=dialog.hold.value()))
        releases = [self._MacroStep(self._StepType.RELEASE, button=name) for name in reversed(buttons)]
        if releases:
            releases[-1].after_ms = dialog.after.value()
        self.steps.extend(releases)
        self.refresh_steps()

    def edit_step(self, *_args: Any) -> None:
        row = self.current_step_row()
        if row < 0:
            self.window_ref.toast("Selecciona un paso para editarlo", "info")
            return
        dialog = MacroStepDialog(self, self.steps[row])
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.steps[row] = dialog.step()
            self.refresh_steps()
            self.steps_table.selectRow(row)

    def duplicate_step(self) -> None:
        row = self.current_step_row()
        if row < 0:
            self.window_ref.toast("Selecciona una acción para duplicarla", "info")
            return
        clone = self._MacroStep.from_dict(self.steps[row].to_dict())
        self.steps.insert(row + 1, clone)
        self.refresh_steps()
        self.steps_table.selectRow(row + 1)

    def set_uniform_delay(self) -> None:
        current = self.current_step_row()
        default = int(getattr(self.steps[current], "after_ms", 80)) if current >= 0 else 80
        value, accepted = QInputDialog.getInt(
            self,
            "Tiempo entre acciones",
            "Espera después de cada acción (excepto pasos de espera):",
            default,
            0,
            60_000,
            10,
        )
        if not accepted:
            return
        for step in self.steps:
            if step.type != self._StepType.WAIT:
                step.after_ms = value
        self.refresh_steps()
        if current >= 0:
            self.steps_table.selectRow(current)

    def delete_step(self) -> None:
        row = self.current_step_row()
        if row >= 0:
            self.steps.pop(row)
            self.refresh_steps()
            if self.steps:
                self.steps_table.selectRow(min(row, len(self.steps) - 1))

    def move_step(self, direction: int) -> None:
        row = self.current_step_row()
        target = row + direction
        if row < 0 or target < 0 or target >= len(self.steps):
            return
        self.steps[row], self.steps[target] = self.steps[target], self.steps[row]
        self.refresh_steps()
        self.steps_table.selectRow(target)

    def toggle_recording(self) -> None:
        if not self.engine:
            return
        if self._recording:
            self.finish_recording()
            return
        manager = self.window_ref.connection_manager
        if not manager or not manager.is_connected:
            self.window_ref.alert("Conecta el DualSense para grabar")
            return
        self._record_base_steps = [
            self._MacroStep.from_dict(step.to_dict()) for step in self.steps
        ]
        self._record_preview_count = -1
        self.engine.start_recording(include_sticks=self.record_sticks.isChecked())
        self._recording = True
        self._record_started = time.monotonic()
        self.record_button.setText("■ Detener")
        self.record_sticks.setEnabled(False)
        self.record_append.setEnabled(False)
        self.record_status.setText("Grabando… las acciones aparecerán aquí en tiempo real.")
        if not self.record_append.isChecked():
            self.steps = []
            self.refresh_steps()
        self.record_timer.start()

    def _record_tick(self) -> None:
        if not self._recording:
            return
        elapsed = time.monotonic() - self._record_started
        recorded = self.engine.get_recording_steps()
        count = len(recorded)
        if count != self._record_preview_count:
            self._record_preview_count = count
            preview = (
                self._record_base_steps + recorded
                if self.record_append.isChecked()
                else recorded
            )
            self.steps = [
                self._MacroStep.from_dict(step.to_dict()) for step in preview
            ]
            self.refresh_steps()
            if self.steps:
                self.steps_table.selectRow(len(self.steps) - 1)
                self.steps_table.scrollToBottom()
        self.record_status.setText(
            f"● Grabando… {elapsed:.1f} s · {count} acciones capturadas · "
            f"máximo {self.engine.MAX_RECORD_SECONDS} s"
        )
        if not self.engine.is_recording:
            self.finish_recording()

    def finish_recording(self) -> None:
        if not self._recording:
            return
        self.record_timer.stop()
        recorded = self.engine.stop_recording()
        self._recording = False
        self.record_button.setText("● Grabar")
        self.record_sticks.setEnabled(True)
        self.record_append.setEnabled(True)
        if recorded:
            if self.record_append.isChecked():
                self.steps = self._record_base_steps + recorded
                self.record_status.setText(f"Se añadieron {len(recorded)} pasos al final.")
            else:
                self.steps = recorded
                self.record_status.setText(f"Grabación terminada: {len(recorded)} pasos.")
            self.refresh_steps()
            self.steps_table.selectRow(len(self.steps) - 1)
            self.steps_table.scrollToBottom()
        else:
            self.steps = [
                self._MacroStep.from_dict(step.to_dict())
                for step in self._record_base_steps
            ]
            self.refresh_steps()
            self.record_status.setText("No se detectó ninguna entrada; se conservó la secuencia anterior.")
        self._record_base_steps = []
        self._record_preview_count = -1

    def test_steps(self) -> None:
        if not self.steps:
            self.window_ref.toast("Añade al menos un paso", "info")
            return
        if not self.engine.play_steps(self.steps):
            self.window_ref.alert("No se pudo iniciar la vista previa")

    def stop_preview(self) -> None:
        if self.engine:
            self.engine.stop_macro("__preview__")

    def _conflicting_macro(self, trigger: Any, profile_ids: List[str]) -> Optional[Any]:
        if trigger.kind == self._TriggerKind.MANUAL:
            return None
        signature = trigger.to_dict()
        for macro in self.engine.get_macros():
            if macro.id == self.editing_id or not macro.enabled:
                continue
            if macro.trigger.to_dict() != signature:
                continue
            overlap = not profile_ids or not macro.profile_ids or bool(set(profile_ids) & set(macro.profile_ids))
            if overlap:
                return macro
        return None

    def save(self) -> None:
        if self._recording:
            self.finish_recording()
        name = self.name.text().strip()
        if not name:
            self.window_ref.alert("Escribe un nombre para la macro")
            return
        if not self.steps:
            self.window_ref.alert("Añade o graba al menos un paso")
            return
        trigger = self.build_trigger()
        if trigger.kind == self._TriggerKind.COMBO and len(trigger.buttons) < 2:
            self.window_ref.alert("El activador por combo necesita al menos dos botones")
            return
        profile_ids = self.selected_profile_ids()
        if self.profile_mode.currentData() == "selected" and not profile_ids:
            self.window_ref.alert("Selecciona al menos un perfil o usa “Todos los perfiles”")
            return
        conflict = self._conflicting_macro(trigger, profile_ids)
        if conflict:
            answer = QMessageBox.question(
                self,
                "Activador repetido",
                f'La macro “{conflict.name}” usa el mismo activador en un perfil compatible. '
                "Las dos podrían ejecutarse juntas. ¿Guardar de todos modos?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        macro = self._Macro(
            id=self.editing_id or self.engine.new_macro_id(),
            name=name,
            description=self.description.text().strip(),
            trigger=trigger,
            profile_ids=profile_ids,
            steps=[self._MacroStep.from_dict(step.to_dict()) for step in self.steps],
            repeat=self.repeat.value(),
            enabled=self.enabled.isChecked(),
            cooldown_ms=self.cooldown.value(),
        )
        self.engine.save_macro(macro)
        self.page.persist()
        self.accept()

    def reject(self) -> None:
        if self._recording:
            self.record_timer.stop()
            self.engine.stop_recording()
            self._recording = False
            self.record_sticks.setEnabled(True)
            self.record_append.setEnabled(True)
        self.stop_preview()
        super().reject()


class MacrosPage(ScrollPage):
    def __init__(self, window: "NikaidoWindow") -> None:
        super().__init__()
        self.window = window
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self.refresh)
        self.add_header(
            "Macros avanzadas",
            "Automatiza botones, combos, palancas y gatillos; asígnalos a perfiles y actívalos como tú quieras.",
        )

        top_card = card()
        top = QHBoxLayout(top_card)
        top.setContentsMargins(16, 14, 16, 14)
        status_info = QVBoxLayout()
        status_info.addWidget(label("CONTROL DE MACROS", "eyebrow"))
        self.profile_status = label("Perfil actual: —", "heading")
        status_info.addWidget(self.profile_status)
        self.profile_hint = label("Las macros pueden funcionar en todos los perfiles o solo en los que elijas.", "muted")
        status_info.addWidget(self.profile_hint)
        top.addLayout(status_info, 1)
        self.enabled = QCheckBox("Macros activas en este perfil")
        self.enabled.toggled.connect(self.toggle)
        top.addWidget(self.enabled)
        top.addWidget(button("+ Nueva macro", self.new_macro, primary=True))
        top.addWidget(button("Plantillas", self.new_from_template))
        top.addWidget(button("● Grabar rápido", self.quick_record))
        self.layout.addWidget(top_card)

        summary_row = QHBoxLayout()
        self.total_value = self._summary_card("MACROS", "0", "guardadas")
        self.profile_value = self._summary_card("EN ESTE PERFIL", "0", "disponibles")
        self.combo_value = self._summary_card("ACTIVADORES", "0", "automáticos")
        summary_row.addWidget(self.total_value[0])
        summary_row.addWidget(self.profile_value[0])
        summary_row.addWidget(self.combo_value[0])
        self.layout.addLayout(summary_row)

        tools = QGridLayout()
        tools.setHorizontalSpacing(8)
        tools.setVerticalSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar macro por nombre, activador o perfil…")
        self.search.textChanged.connect(lambda _text: self._search_timer.start(140))
        tools.addWidget(self.search, 0, 0, 1, 4)
        macro_actions = (
            ("Editar", self.edit_selected, False),
            ("Duplicar", self.duplicate_selected, False),
            ("Activar / pausar", self.toggle_selected, False),
            ("▶ Probar", self.play, False),
            ("■ Detener", self.stop_selected, False),
            ("Importar", self.import_macros, False),
            ("Exportar", self.export_selected, False),
            ("Eliminar", self.delete, True),
        )
        for index, (text, callback, danger) in enumerate(macro_actions):
            tools.addWidget(button(text, callback, danger=danger), 1 + index // 4, index % 4)
        self.layout.addLayout(tools)

        content = QHBoxLayout()
        content.setSpacing(14)
        left = card()
        left_box = QVBoxLayout(left)
        left_box.setContentsMargins(12, 12, 12, 12)
        left_box.addWidget(label("Biblioteca", "heading"))
        self.list = QListWidget()
        self.list.setMinimumHeight(420)
        self.list.currentItemChanged.connect(self.show_details)
        self.list.itemDoubleClicked.connect(lambda _item: self.edit_selected())
        left_box.addWidget(self.list, 1)
        content.addWidget(left, 42)

        right = card()
        right_box = QVBoxLayout(right)
        right_box.setContentsMargins(14, 14, 14, 14)
        self.detail_title = label("Selecciona una macro", "heading")
        right_box.addWidget(self.detail_title)
        self.detail_meta = label("Aquí verás el activador, perfiles y secuencia.", "muted")
        self.detail_meta.setWordWrap(True)
        right_box.addWidget(self.detail_meta)
        self.detail_table = QTableWidget(0, 4)
        self.detail_table.setHorizontalHeaderLabels(["#", "Acción", "Duración", "Después"])
        self.detail_table.setColumnWidth(0, 44)
        self.detail_table.setColumnWidth(2, 95)
        self.detail_table.setColumnWidth(3, 95)
        self.detail_table.horizontalHeader().setStretchLastSection(False)
        self.detail_table.verticalHeader().setVisible(False)
        right_box.addWidget(self.detail_table, 1)
        self.detail_footer = label("", "muted")
        right_box.addWidget(self.detail_footer)
        content.addWidget(right, 58)
        self.layout.addLayout(content, 1)
        self.refresh()

    def _summary_card(self, title: str, value: str, caption: str) -> tuple[QFrame, QLabel, QLabel]:
        panel = card(sub=True)
        box = QVBoxLayout(panel)
        box.setContentsMargins(14, 12, 14, 12)
        box.addWidget(label(title, "eyebrow"))
        value_label = label(value, "value")
        box.addWidget(value_label)
        caption_label = label(caption, "muted")
        box.addWidget(caption_label)
        return panel, value_label, caption_label

    def _active_profile(self) -> tuple[Optional[str], Optional[Any]]:
        trigger = self.window.trigger_engine
        profile_id = trigger.get_current_profile() if trigger else None
        if not profile_id and self.window.profile_manager:
            profile_id = self.window.profile_manager.get_active_profile()
        profile = trigger.get_profile(profile_id) if trigger and profile_id else None
        return profile_id, profile

    def refresh(self, *_args: Any) -> None:
        selected = self.selected_id()
        engine = self.window.macro_engine
        profile_id, profile = self._active_profile()
        if engine:
            engine.set_active_profile(profile_id)
        self.enabled.blockSignals(True)
        self.enabled.setChecked(bool(profile.macros_enabled if profile else (engine and engine.is_enabled)))
        self.enabled.blockSignals(False)
        self.profile_status.setText(f"Perfil actual: {profile.name if profile else 'Sin perfil'}")

        macros = engine.get_macros() if engine else []
        query = self.search.text().strip().lower() if hasattr(self, "search") else ""
        visible = []
        for macro in macros:
            profiles_text = self._profiles_text(macro)
            haystack = f"{macro.name} {macro.description} {macro.trigger.describe()} {profiles_text}".lower()
            if query and query not in haystack:
                continue
            visible.append(macro)

        self.list.blockSignals(True)
        self.list.clear()
        selected_row = -1
        for row, macro in enumerate(visible):
            status = "ACTIVA" if macro.enabled else "PAUSADA"
            profiles_text = self._profiles_text(macro)
            analog_count = sum(step.type.value in ("stick", "trigger") for step in macro.steps)
            item = QListWidgetItem(
                f"{macro.name}  ·  {status}\n"
                f"{macro.trigger.describe()}  ·  {profiles_text}\n"
                f"{len(macro.steps)} acciones · {analog_count} analógicas · repetir {macro.repeat}×"
            )
            item.setData(Qt.ItemDataRole.UserRole, macro.id)
            item.setSizeHint(QSize(0, 78))
            if not macro.enabled:
                item.setForeground(QColor(C["muted"]))
            self.list.addItem(item)
            if macro.id == selected:
                selected_row = row
        self.list.blockSignals(False)
        if self.list.count():
            self.list.setCurrentRow(selected_row if selected_row >= 0 else 0)
        else:
            self.show_details()

        available = sum(macro.enabled and macro.is_available_for_profile(profile_id) for macro in macros)
        automatic = sum(macro.enabled and macro.trigger.kind.value != "manual" for macro in macros)
        self.total_value[1].setText(str(len(macros)))
        self.profile_value[1].setText(str(available))
        self.combo_value[1].setText(str(automatic))

    def _profiles_text(self, macro: Any) -> str:
        if not macro.profile_ids:
            return "Todos los perfiles"
        names: List[str] = []
        trigger = self.window.trigger_engine
        for profile_id in macro.profile_ids:
            profile = trigger.get_profile(profile_id) if trigger else None
            names.append(profile.name if profile else profile_id)
        if len(names) <= 2:
            return ", ".join(names)
        return f"{names[0]}, {names[1]} +{len(names) - 2}"

    def show_details(self, *_args: Any) -> None:
        macro_id = self.selected_id()
        macro = self.window.macro_engine.get_macro(macro_id) if self.window.macro_engine and macro_id else None
        if not macro:
            self.detail_title.setText("Selecciona una macro")
            self.detail_meta.setText("Crea una nueva o grábala directamente desde el DualSense.")
            self.detail_table.setRowCount(0)
            self.detail_footer.setText("")
            return
        self.detail_title.setText(macro.name)
        self.detail_meta.setText(
            f"Activador: {macro.trigger.describe()}\n"
            f"Perfiles: {self._profiles_text(macro)}\n"
            f"Estado: {'activa' if macro.enabled else 'pausada'} · protección {macro.cooldown_ms} ms"
        )
        self.detail_table.setRowCount(len(macro.steps))
        for row, step in enumerate(macro.steps):
            for column, value in enumerate((
                str(row + 1),
                step.describe(),
                f"{step.ms} ms" if step.ms else "—",
                f"{getattr(step, 'after_ms', 0)} ms" if getattr(step, "after_ms", 0) else "—",
            )):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if column in (0, 2, 3):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.detail_table.setItem(row, column, item)
        self.detail_table.setColumnWidth(1, max(280, self.detail_table.viewport().width() - 260))
        self.detail_footer.setText(
            f"Duración aproximada: {macro.duration_ms() / 1000:.2f} s · repetir {macro.repeat}×"
        )

    def toggle(self, enabled: bool) -> None:
        if self.window.macro_engine:
            self.window.macro_engine.set_enabled(enabled)
        trigger = self.window.trigger_engine
        profile_id = trigger.get_current_profile() if trigger else None
        profile = trigger.get_profile(profile_id) if trigger and profile_id else None
        if profile:
            profile.macros_enabled = bool(enabled)
        if self.window.profile_manager:
            self.window.profile_manager.set_setting("macros_enabled", enabled)
            if trigger:
                self.window.profile_manager.set_setting("profile_overrides", trigger.export_profile_overrides())
                self.window.profile_manager.set_custom_profiles(trigger.export_custom_profiles_to_dict())
            self.window.request_config_save()
        self.window.toast("Macros activadas" if enabled else "Macros pausadas en este perfil")

    def selected_id(self) -> Optional[str]:
        item = self.list.currentItem() if hasattr(self, "list") else None
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def new_macro(self) -> None:
        self.open_editor()

    def new_from_template(self) -> None:
        engine = self.window.macro_engine
        if not engine:
            self.window.alert("El motor de macros no está disponible.")
            return
        options = [
            "Toque rápido de botón",
            "Combo de dos botones",
            "Flick de palanca derecha",
            "Gatillo analógico progresivo",
            "Fuego rápido mientras mantienes R1",
        ]
        selected, accepted = QInputDialog.getItem(
            self,
            "Plantillas de macros",
            "Elige una base y después personalízala:",
            options,
            0,
            False,
        )
        if not accepted:
            return
        from src.macro_engine import Macro, MacroStep, MacroTrigger, StepType, TriggerEdge, TriggerKind

        macro = Macro(id=engine.new_macro_id(), name=selected)
        if selected == options[0]:
            macro.steps = [MacroStep(StepType.TAP, button="cross", ms=60, after_ms=80)]
        elif selected == options[1]:
            macro.steps = [
                MacroStep(StepType.PRESS, button="L1"),
                MacroStep(StepType.PRESS, button="R1", after_ms=100),
                MacroStep(StepType.RELEASE, button="R1"),
                MacroStep(StepType.RELEASE, button="L1", after_ms=80),
            ]
        elif selected == options[2]:
            macro.steps = [
                MacroStep(StepType.STICK, stick="right", x=1.0, y=0.0, ms=90, after_ms=40),
                MacroStep(StepType.STICK, stick="right", x=0.0, y=0.0),
            ]
        elif selected == options[3]:
            macro.steps = [
                MacroStep(StepType.TRIGGER, trigger="right", value=90, ms=80, after_ms=30),
                MacroStep(StepType.TRIGGER, trigger="right", value=180, ms=80, after_ms=30),
                MacroStep(StepType.TRIGGER, trigger="right", value=255, ms=100, after_ms=50),
                MacroStep(StepType.TRIGGER, trigger="right", value=0),
            ]
        else:
            macro.trigger = MacroTrigger(
                kind=TriggerKind.BUTTON,
                buttons=["R1"],
                edge=TriggerEdge.WHILE_HELD,
            )
            macro.cooldown_ms = 25
            macro.steps = [MacroStep(StepType.TAP, button="cross", ms=35, after_ms=45)]
        dialog = MacroEditorDialog(self, macro)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()
            self.window.toast("Macro creada desde plantilla")

    def quick_record(self) -> None:
        self.open_editor(auto_record=True)

    def open_editor(self, macro_id: Optional[str] = None, auto_record: bool = False) -> None:
        engine = self.window.macro_engine
        if not engine:
            self.window.alert("El motor de macros no está disponible.")
            return
        macro = engine.get_macro(macro_id) if macro_id else None
        dialog = MacroEditorDialog(self, macro, auto_record=auto_record)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()
            self.window.toast("Macro guardada")

    def edit_selected(self) -> None:
        macro_id = self.selected_id()
        if not macro_id:
            self.window.alert("Selecciona una macro")
            return
        self.open_editor(macro_id)

    def duplicate_selected(self) -> None:
        macro_id = self.selected_id()
        if not macro_id or not self.window.macro_engine:
            self.window.alert("Selecciona una macro")
            return
        duplicated = self.window.macro_engine.duplicate_macro(macro_id)
        if duplicated:
            self.persist()
            self.refresh()
            self.window.toast("Macro duplicada; el activador quedó en manual")


    def toggle_selected(self) -> None:
        macro_id = self.selected_id()
        engine = self.window.macro_engine
        macro = engine.get_macro(macro_id) if engine and macro_id else None
        if not macro:
            self.window.alert("Selecciona una macro")
            return
        macro.enabled = not macro.enabled
        if not macro.enabled:
            engine.stop_macro(macro.id)
        engine.save_macro(macro)
        self.persist()
        self.refresh()
        self.window.toast("Macro activada" if macro.enabled else "Macro pausada")

    def export_selected(self) -> None:
        macro_id = self.selected_id()
        engine = self.window.macro_engine
        macro = engine.get_macro(macro_id) if engine and macro_id else None
        if not macro:
            self.window.alert("Selecciona una macro")
            return
        safe_name = "".join(character if character.isalnum() or character in "-_" else "_" for character in macro.name).strip("_") or "macro"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar macro",
            f"{safe_name}.nikaido-macro.json",
            "Macro de Nikaido (*.nikaido-macro.json);;JSON (*.json)",
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".nikaido-macro.json"
        try:
            destination = Path(path)
            temp = destination.with_suffix(destination.suffix + ".tmp")
            payload = {"format": "nikaido-macro", "version": 2, "macro": macro.to_dict()}
            try:
                temp.write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                os.replace(temp, destination)
            finally:
                temp.unlink(missing_ok=True)
            self.window.toast("Macro exportada")
        except Exception as exc:
            self.window.alert(f"No se pudo exportar la macro: {exc}")

    def import_macros(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Importar macro",
            "",
            "Macros de Nikaido (*.nikaido-macro.json *.json);;Todos los archivos (*)",
        )
        if not path:
            return
        try:
            from src.macro_engine import MAX_LOADED_MACROS, Macro

            payload = read_json_file_limited(
                Path(path),
                label="El archivo de macros",
                max_bytes=4 * 1024 * 1024,
                max_depth=24,
                max_nodes=60_000,
                max_collection_items=4_000,
            )
            candidates: List[Dict[str, Any]] = []
            if isinstance(payload, dict) and isinstance(payload.get("macro"), dict):
                candidates = [payload["macro"]]
            elif isinstance(payload, dict) and isinstance(payload.get("macros"), dict):
                candidates = [value for value in payload["macros"].values() if isinstance(value, dict)]
            elif isinstance(payload, dict) and "steps" in payload:
                candidates = [payload]
            elif isinstance(payload, list):
                candidates = [value for value in payload if isinstance(value, dict)]
            if not candidates:
                raise ValueError("El archivo no contiene macros compatibles")
            if len(candidates) > MAX_LOADED_MACROS:
                raise ValueError(
                    f"El archivo supera el límite de {MAX_LOADED_MACROS} macros."
                )
            engine = self.window.macro_engine
            imported = 0
            existing_ids = {macro.id for macro in engine.get_macros()}
            for data in candidates:
                macro = Macro.from_dict(data)
                if macro.id in existing_ids:
                    macro.id = engine.new_macro_id()
                    macro.name = f"{macro.name} importada"
                engine.save_macro(macro)
                existing_ids.add(macro.id)
                imported += 1
            self.persist()
            self.refresh()
            self.window.toast(f"{imported} macro{'s' if imported != 1 else ''} importada{'s' if imported != 1 else ''}")
        except Exception as exc:
            self.window.alert(f"No se pudo importar: {exc}")

    def play(self) -> None:
        macro_id = self.selected_id()
        if not macro_id:
            self.window.alert("Selecciona una macro")
            return
        if not self.window.macro_engine.play_macro(macro_id):
            self.window.alert("No se pudo reproducir. Puede estar pausada, vacía o ya ejecutándose.")
        else:
            self.window.toast("Reproduciendo macro")

    def stop_selected(self) -> None:
        macro_id = self.selected_id()
        if macro_id and self.window.macro_engine:
            if self.window.macro_engine.stop_macro(macro_id):
                self.window.toast("Macro detenida")
            else:
                self.window.macro_engine.stop_all()

    def delete(self) -> None:
        macro_id = self.selected_id()
        engine = self.window.macro_engine
        macro = engine.get_macro(macro_id) if engine and macro_id else None
        if not macro:
            self.window.alert("Selecciona una macro")
            return
        answer = QMessageBox.question(self, "Eliminar macro", f'¿Eliminar “{macro.name}”?')
        if answer != QMessageBox.StandardButton.Yes:
            return
        engine.delete_macro(macro_id)
        self.persist()
        self.refresh()
        self.window.toast("Macro eliminada")

    def persist(self) -> None:
        if self.window.profile_manager and self.window.macro_engine:
            self.window.profile_manager.set_macros(self.window.macro_engine.export_macros())
            self.window.request_config_save()
