"""InputStudioPage, CalibrationPage, GyroPage extraídos de la antigua interfaz monolítica."""

from __future__ import annotations

from typing import TYPE_CHECKING


from ..ui_common import (
    logging,
    Any,
    C,
    Dict,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
    button,
    card,
    configure_tabs,
    label,
)
from ..components import LatencyGraph, ResponseCurveEditor, ScrollPage, SliderRow, StickScope
from ..i18n import tr

if TYPE_CHECKING:
    from ..main_window import NikaidoWindow

logger = logging.getLogger(__name__)

class InputStudioPage(ScrollPage):
    def __init__(self, window: "NikaidoWindow") -> None:
        super().__init__()
        self.window = window
        self._loading = False
        self.stick = "right"
        self._persist_timer = QTimer(self)
        self._persist_timer.setSingleShot(True)
        self._persist_timer.timeout.connect(self._persist_now)
        bar = QHBoxLayout()
        bar.addWidget(label("Input Studio", "title"))
        bar.addStretch()
        bar.addWidget(label("Perfil", "muted"))
        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self.load)
        bar.addWidget(self.profile_combo)
        self.stick_combo = QComboBox()
        self.stick_combo.addItem("Stick izquierdo", "left")
        self.stick_combo.addItem("Stick derecho", "right")
        self.stick_combo.setCurrentIndex(1)
        self.stick_combo.currentIndexChanged.connect(self._stick_changed)
        bar.addWidget(self.stick_combo)
        self.layout.addLayout(bar)
        self.layout.addWidget(
            label(
                "Ajusta zonas muertas, respuesta y drift por perfil mientras comparas entrada física y salida virtual.",
                "muted",
            )
        )
        autosave = label("Los cambios se aplican al instante y se guardan automáticamente.", "eyebrow")
        autosave.setStyleSheet(f"color:{C['green']}")
        self.layout.addWidget(autosave)
        row = QHBoxLayout()
        row.setSpacing(14)
        controls = card()
        form = QVBoxLayout(controls)
        form.addWidget(label("RESPUESTA DEL STICK", "eyebrow"))
        self.curve = QComboBox()
        self.curve.addItem("Lineal", "linear")
        self.curve.addItem("Exponencial", "exponential")
        self.curve.addItem("Agresiva", "aggressive")
        self.curve.addItem("Personalizada", "custom")
        self.curve.currentIndexChanged.connect(self._curve_selected)
        form.addWidget(QLabel("Curva"))
        form.addWidget(self.curve)
        self.curve_editor = ResponseCurveEditor(editable=True)
        self.curve_editor.changed.connect(self._custom_curve_changed)
        form.addWidget(self.curve_editor)
        self.curve_help = label(
            "Selecciona Personalizada para mover los puntos interiores.", "muted"
        )
        self.curve_help.setWordWrap(True)
        form.addWidget(self.curve_help)
        self.sliders: Dict[str, SliderRow] = {}
        configs = (
            ("inner_deadzone", "Zona muerta interior", 0, 0.95, 0.08),
            ("outer_deadzone", "Zona muerta exterior", 0, 0.90, 0),
            ("anti_deadzone", "Anti-deadzone", 0, 0.95, 0),
            ("sensitivity_x", "Sensibilidad X", 0.1, 3, 1),
            ("sensitivity_y", "Sensibilidad Y", 0.1, 3, 1),
        )
        for key, title, minimum, maximum, value in configs:
            slider = SliderRow(title, minimum, maximum, value, decimals=2)
            slider.changed.connect(lambda _value, k=key: self.save())
            form.addWidget(slider)
            self.sliders[key] = slider
        self.invert_x = QCheckBox("Invertir eje X")
        self.invert_y = QCheckBox("Invertir eje Y")
        self.drift = QCheckBox("Corrección de drift")
        self.invert_x.toggled.connect(self.save)
        self.invert_y.toggled.connect(self.save)
        self.drift.toggled.connect(self.save)
        form.addWidget(self.invert_x)
        form.addWidget(self.invert_y)
        form.addWidget(self.drift)
        actions = QHBoxLayout()
        actions.addWidget(button("Calibrar drift", self.calibrate))
        actions.addWidget(button("Restablecer", self.reset))
        form.addLayout(actions)
        form.addStretch()
        row.addWidget(controls, 45)
        monitor = card()
        m = QVBoxLayout(monitor)
        m.addWidget(label("VISTA EN TIEMPO REAL", "eyebrow"))
        scopes = QHBoxLayout()
        self.left_scope = StickScope("Stick izquierdo")
        self.right_scope = StickScope("Stick derecho")
        scopes.addWidget(self.left_scope)
        scopes.addWidget(self.right_scope)
        m.addLayout(scopes)
        legend = QLabel("● Entrada física     ● Salida virtual")
        legend.setProperty("accentText", True)
        m.addWidget(legend, alignment=Qt.AlignmentFlag.AlignCenter)
        row.addWidget(monitor, 55)
        self.layout.addLayout(row)
        self.refresh_profiles()
        self.load()

    def refresh_profiles(self) -> None:
        engine = self.window.trigger_engine
        previous = self.profile_combo.currentData()
        active = previous or (engine.get_current_profile() if engine else None)
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        if engine:
            for pid, name in engine.get_profile_names():
                self.profile_combo.addItem(name, pid)
        self.profile_combo.setCurrentIndex(max(0, self.profile_combo.findData(active)))
        self.profile_combo.blockSignals(False)

    def _stick_changed(self) -> None:
        self.stick = self.stick_combo.currentData() or "right"
        self.load()

    def load(self) -> None:
        engine = self.window.input_studio
        profile = self.profile_combo.currentData()
        if not engine or not profile:
            return
        self._loading = True
        config = engine.get_config(profile, self.stick)
        idx = self.curve.findData(config["curve"])
        self.curve.blockSignals(True)
        self.curve.setCurrentIndex(max(0, idx))
        self.curve.blockSignals(False)
        self.curve_editor.set_curve(
            str(config.get("curve", "linear")), config.get("custom_curve")
        )
        self._update_curve_help()
        for key, slider in self.sliders.items():
            slider.set_value(float(config[key]))
        for widget, key in (
            (self.invert_x, "invert_x"),
            (self.invert_y, "invert_y"),
            (self.drift, "drift_correction"),
        ):
            widget.blockSignals(True)
            widget.setChecked(bool(config[key]))
            widget.blockSignals(False)
        self._loading = False

    def _curve_selected(self, *_args: Any) -> None:
        if self._loading:
            return
        self.curve_editor.set_curve(
            str(self.curve.currentData() or "linear"),
            self.curve_editor.get_points(),
        )
        self._update_curve_help()
        self.save()

    def _update_curve_help(self) -> None:
        if self.curve.currentData() == "custom":
            text = "Arrastra los puntos interiores. La curva se guarda por perfil y por palanca."
        else:
            text = "Selecciona Personalizada para mover los puntos interiores."
        self.curve_help.setText(tr(text, getattr(self.window, "language", "es")))

    def save(self, *_args: Any) -> None:
        if self._loading or not self.window.input_studio:
            return
        profile = self.profile_combo.currentData()
        changes = {key: slider.spin.value() for key, slider in self.sliders.items()}
        changes.update(
            curve=self.curve.currentData(),
            custom_curve=self.curve_editor.get_points(),
            invert_x=self.invert_x.isChecked(),
            invert_y=self.invert_y.isChecked(),
            drift_correction=self.drift.isChecked(),
        )
        self.window.input_studio.update_config(profile, self.stick, **changes)
        self.persist()

    def _custom_curve_changed(self, _points: Any) -> None:
        if self._loading:
            return
        if self.curve.currentData() != "custom":
            self.curve.setCurrentIndex(max(0, self.curve.findData("custom")))
        self.save()

    def persist(self) -> None:
        self._persist_timer.start(220)

    def _persist_now(self) -> None:
        manager = self.window.profile_manager
        studio = self.window.input_studio
        trigger = self.window.trigger_engine
        if manager and studio:
            profile_id = self.profile_combo.currentData()
            profile = trigger.get_profile(profile_id) if trigger and profile_id else None
            if profile:
                profile.input_studio_config = studio.get_profile_config(profile_id)
            manager.set_setting("profile_input_studio", studio.export_profiles())
            if trigger:
                manager.set_setting("profile_overrides", trigger.export_profile_overrides())
                manager.set_custom_profiles(trigger.export_custom_profiles_to_dict())
            self.window.request_config_save()

    def calibrate(self) -> None:
        engine = self.window.input_studio
        if not engine:
            return
        engine.begin_drift_calibration(
            self.profile_combo.currentData(), self.stick, 120
        )
        self.window.toast(tr("No muevas el stick durante la calibración", self.window.language))

    def reset(self) -> None:
        if self.window.input_studio:
            self.window.input_studio.reset_stick(
                self.profile_combo.currentData(), self.stick
            )
            self.load()
            self.persist()
            self.window.toast(tr("Stick restablecido", self.window.language))

    def update_live(self) -> None:
        engine = self.window.input_studio
        if not engine:
            return
        for stick, scope in (("left", self.left_scope), ("right", self.right_scope)):
            telemetry = engine.get_telemetry(stick)
            scope.set_points(
                (telemetry.get("physical_x", 0), telemetry.get("physical_y", 0)),
                (telemetry.get("output_x", 0), telemetry.get("output_y", 0)),
            )


class CalibrationPage(ScrollPage):
    """Asistente centralizado para drift, gyro y recorrido de gatillos."""

    def __init__(self, window: "NikaidoWindow") -> None:
        super().__init__()
        self.window = window
        self.status: Dict[str, QLabel] = {}
        self.progress: Dict[str, QProgressBar] = {}
        self.action_buttons: Dict[str, QPushButton] = {}
        self._saved_stick_revisions: Dict[str, int] = {}
        self._trigger_min = [255, 255]
        self._trigger_max = [0, 0]

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(label("Calibración guiada", "title"))
        titles.addWidget(
            label(
                "Completa los pasos en orden. Nikaido valida las muestras y guarda el perfil activo automáticamente.",
                "muted",
            )
        )
        header.addLayout(titles, 1)
        restore = button("Restaurar valores", self.restore_defaults)
        restore.setToolTip("Elimina los offsets de drift y giroscopio del perfil activo")
        header.addWidget(restore, 0, Qt.AlignmentFlag.AlignVCenter)
        self.overall = QProgressBar()
        self.overall.setRange(0, 4)
        self.overall.setValue(0)
        self.overall.setFixedWidth(170)
        self.overall.setFormat("%v de 4 pasos")
        self.overall.setTextVisible(True)
        header.addWidget(self.overall, 0, Qt.AlignmentFlag.AlignVCenter)
        self.layout.addLayout(header)

        grid = QGridLayout()
        grid.setSpacing(14)
        cards = (
            ("left", "1", "Stick izquierdo", "Déjalo completamente quieto hasta que termine la captura.", lambda: self.calibrate_stick("left")),
            ("right", "2", "Stick derecho", "Déjalo completamente quieto hasta que termine la captura.", lambda: self.calibrate_stick("right")),
            ("gyro", "3", "Giroscopio", "Coloca el control en una superficie plana y no lo muevas.", self.calibrate_gyro),
            ("triggers", "4", "L2 y R2", "Suelta ambos y después presiónalos lentamente hasta el fondo.", self.check_triggers),
        )
        for index, (key, number, title, description, callback) in enumerate(cards):
            panel = card()
            panel.setMinimumHeight(190)
            box = QVBoxLayout(panel)
            box.setContentsMargins(16, 15, 16, 15)
            box.setSpacing(9)
            top = QHBoxLayout()
            badge = QLabel(number)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedSize(28, 28)
            badge.setStyleSheet(
                f"background:#28184b;color:{C['accent2']};border:1px solid #53328a;border-radius:14px;font-weight:800"
            )
            top.addWidget(badge)
            top.addWidget(label(title, "heading"))
            top.addStretch()
            box.addLayout(top)
            description_label = label(description, "muted")
            description_label.setWordWrap(True)
            box.addWidget(description_label)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setTextVisible(False)
            self.progress[key] = bar
            box.addWidget(bar)
            status = QLabel("Pendiente")
            status.setStyleSheet(f"color:{C['yellow']}")
            self.status[key] = status
            box.addWidget(status)
            action = button("Iniciar paso", callback, primary=True)
            self.action_buttons[key] = action
            box.addWidget(action)
            grid.addWidget(panel, index // 2, index % 2)
        self.layout.addLayout(grid)

        live = card()
        live_box = QVBoxLayout(live)
        live_box.addWidget(label("VALIDACIÓN EN TIEMPO REAL", "eyebrow"))
        self.trigger_readout = label("L2 0 %   ·   R2 0 %", "heading")
        live_box.addWidget(self.trigger_readout)
        live_box.addWidget(
            label(
                "Para validar los gatillos, Nikaido debe detectar el punto de reposo y al menos 94 % de recorrido en ambos.",
                "muted",
            )
        )
        shortcuts = QHBoxLayout()
        shortcuts.addWidget(button("Abrir Input Studio", lambda: self.window.navigate("input")))
        shortcuts.addWidget(button("Abrir Gyro Studio", lambda: self.window.navigate("gyro")))
        shortcuts.addWidget(button("Abrir diagnóstico", lambda: self.window.navigate("monitor")))
        shortcuts.addStretch()
        live_box.addLayout(shortcuts)
        self.layout.addWidget(live)
        self.layout.addStretch()

    def restore_defaults(self) -> None:
        answer = QMessageBox.question(
            self,
            "Restaurar calibración",
            "Se eliminarán los offsets de drift y giroscopio del perfil activo. ¿Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        trigger = self.window.trigger_engine
        manager = self.window.profile_manager
        studio = self.window.input_studio
        gyro = self.window.gyro_engine
        profile_id = trigger.get_current_profile() if trigger else None
        if not profile_id and manager:
            profile_id = manager.get_active_profile()

        if studio:
            for stick in ("left", "right"):
                studio.reset_stick(profile_id, stick)
            profile = trigger.get_profile(profile_id) if trigger and profile_id else None
            if profile:
                profile.input_studio_config = studio.get_profile_config(profile_id)

        if gyro:
            gyro.cancel_calibration()
            gyro.update_config(
                calibration={"pitch_bias": 0.0, "yaw_bias": 0.0, "roll_bias": 0.0}
            )
            gyro.recenter()

        if manager:
            if studio:
                manager.set_setting("profile_input_studio", studio.export_profiles())
            if trigger:
                manager.set_setting("profile_gyro", trigger.export_gyro_overrides())
                manager.set_setting("profile_overrides", trigger.export_profile_overrides())
                manager.set_custom_profiles(trigger.export_custom_profiles_to_dict())
            self.window.request_config_save(0)

        self._saved_stick_revisions.clear()
        self._trigger_min = [255, 255]
        self._trigger_max = [0, 0]
        self.trigger_readout.setText("L2 0 %   ·   R2 0 %")
        for key, bar in self.progress.items():
            bar.setValue(0)
            self.action_buttons[key].setEnabled(True)
            self.action_buttons[key].setText("Iniciar paso")
            self._set_status(key, "Pendiente")
        self._refresh_overall()

        if hasattr(self.window, "input_page"):
            self.window.input_page.load()
        if hasattr(self.window, "gyro_page"):
            self.window.gyro_page.load()
        self.window.toast(tr("Calibración restaurada", self.window.language), "success")

    def _set_status(self, key: str, text: str, level: str = "warning") -> None:
        colors = {"success": C["green"], "error": C["danger"], "info": C["cyan"], "warning": C["yellow"]}
        self.status[key].setText(text)
        self.status[key].setStyleSheet(f"color:{colors.get(level, C['muted'])}")

    def _refresh_overall(self) -> None:
        completed = sum(bar.value() >= 100 for bar in self.progress.values())
        self.overall.setValue(completed)

    def calibrate_stick(self, stick: str) -> None:
        engine = self.window.input_studio
        if not engine:
            self.window.alert(tr("Input Studio no está disponible", self.window.language))
            return
        profile = self.window.trigger_engine.get_current_profile() if self.window.trigger_engine else None
        engine.begin_drift_calibration(profile,stick,120)
        self.progress[stick].setValue(0)
        self.action_buttons[stick].setEnabled(False)
        self._set_status(stick, "Capturando muestras… no muevas la palanca", "info")
        self.window.call_later(1500, lambda s=stick: self._finish_stick(s))

    def _finish_stick(self, stick: str) -> None:
        state = self.window.input_studio.get_drift_calibration(stick) if self.window.input_studio else {}
        if state.get("completed"):
            self.progress[stick].setValue(100)
            self.action_buttons[stick].setEnabled(True)
            self.action_buttons[stick].setText("Calibrar otra vez")
            self._set_status(stick, "Validado y guardado", "success")
            revision = int(state.get("revision", 0))
            if self._saved_stick_revisions.get(stick) != revision:
                self._saved_stick_revisions[stick] = revision
                if hasattr(self.window, "input_page"):
                    self.window.input_page.persist()
                else:
                    manager = self.window.profile_manager
                    trigger = self.window.trigger_engine
                    if manager and self.window.input_studio:
                        manager.set_setting(
                            "profile_input_studio", self.window.input_studio.export_profiles()
                        )
                        if trigger:
                            manager.set_setting(
                                "profile_overrides", trigger.export_profile_overrides()
                            )
                        self.window.request_config_save()
        else:
            self.action_buttons[stick].setEnabled(True)
            self._set_status(stick, "Aún faltan muestras; mantén la palanca quieta", "warning")
        self._refresh_overall()

    def calibrate_gyro(self) -> None:
        if not self.window.gyro_engine:
            self.window.alert(tr("Gyro Studio no está disponible", self.window.language))
            return
        self.window.gyro_engine.begin_calibration()
        self.progress["gyro"].setValue(0)
        self.action_buttons["gyro"].setEnabled(False)
        self._set_status("gyro", "Capturando movimiento base… control quieto", "info")
        self.window.call_later(2200, self._finish_gyro)

    def _finish_gyro(self) -> None:
        data = self.window.gyro_engine.get_telemetry() if self.window.gyro_engine else None
        done = bool(data and data.calibrated and not data.calibrating)
        self.progress["gyro"].setValue(100 if done else int(getattr(data, "calibration_progress", 0.0) * 100) if data else 0)
        self.action_buttons["gyro"].setEnabled(True)
        self.action_buttons["gyro"].setText("Calibrar otra vez" if done else "Reintentar")
        self._set_status("gyro", "Validado y guardado" if done else "La calibración sigue en proceso", "success" if done else "warning")
        if done:
            if hasattr(self.window, "gyro_page"):
                self.window.gyro_page.persist()
            else:
                manager = self.window.profile_manager
                trigger = self.window.trigger_engine
                if manager and trigger:
                    manager.set_setting("profile_gyro", trigger.export_gyro_overrides())
                    manager.set_setting("profile_overrides", trigger.export_profile_overrides())
                    self.window.request_config_save()
        self._refresh_overall()

    def check_triggers(self) -> None:
        self._trigger_min = [255, 255]
        self._trigger_max = [0, 0]
        self.progress["triggers"].setValue(0)
        self._set_status("triggers", "Suelta L2/R2 y presiónalos lentamente hasta el fondo", "info")
        self.window.toast(tr("Revisión de gatillos iniciada", self.window.language), "info")

    def update_live(self, state: Any = None) -> None:
        studio = self.window.input_studio
        if studio:
            for stick in ("left", "right"):
                calibration = studio.get_drift_calibration(stick)
                value = int(float(calibration.get("progress", 0.0)) * 100)
                if calibration.get("completed"):
                    value = 100
                if calibration.get("active") or calibration.get("completed"):
                    self.progress[stick].setValue(value)
                if calibration.get("completed"):
                    self._finish_stick(stick)

        gyro = self.window.gyro_engine.get_telemetry() if self.window.gyro_engine else None
        if gyro and gyro.calibrating:
            self.progress["gyro"].setValue(int(max(0.0, min(1.0, gyro.calibration_progress)) * 100))
        elif gyro and gyro.calibrated and self.progress["gyro"].value() < 100:
            self._finish_gyro()

        if state is not None:
            left = max(0, min(255, int(getattr(state, "left_trigger", 0))))
            right = max(0, min(255, int(getattr(state, "right_trigger", 0))))
            self._trigger_min[0] = min(self._trigger_min[0], left)
            self._trigger_min[1] = min(self._trigger_min[1], right)
            self._trigger_max[0] = max(self._trigger_max[0], left)
            self._trigger_max[1] = max(self._trigger_max[1], right)
            left_percent = round(left / 255 * 100)
            right_percent = round(right / 255 * 100)
            self.trigger_readout.setText(f"L2 {left_percent} %   ·   R2 {right_percent} %")
            reach = min(self._trigger_max) / 255.0
            self.progress["triggers"].setValue(min(100, round(reach * 100)))
            valid = max(self._trigger_min) <= 8 and min(self._trigger_max) >= 240
            if valid:
                self.progress["triggers"].setValue(100)
                self.action_buttons["triggers"].setText("Revisar otra vez")
                self._set_status("triggers", "Recorrido completo validado", "success")
            elif max(self._trigger_max) > 0:
                self._set_status(
                    "triggers",
                    f"Máximo detectado: L2 {round(self._trigger_max[0] / 255 * 100)} % · R2 {round(self._trigger_max[1] / 255 * 100)} %",
                    "info",
                )
        self._refresh_overall()


class GyroPage(ScrollPage):
    """Configuración profesional de gyro aim y Flick Stick por perfil."""

    PRESETS = {
        "suave": {
            "sensitivity_x": 0.85, "sensitivity_y": 0.85, "deadzone": 1.8,
            "smoothing": 0.38, "acceleration": 0.15, "min_threshold": 0.15,
        },
        "equilibrado": {
            "sensitivity_x": 1.25, "sensitivity_y": 1.25, "deadzone": 1.25,
            "smoothing": 0.20, "acceleration": 0.35, "min_threshold": 0.10,
        },
        "competitivo": {
            "sensitivity_x": 1.65, "sensitivity_y": 1.55, "deadzone": 0.55,
            "smoothing": 0.07, "acceleration": 0.10, "min_threshold": 0.04,
        },
        "stick": {
            "stick_sensitivity_x": 0.018, "stick_sensitivity_y": 0.018,
            "stick_deadzone": 0.04, "stick_anti_deadzone": 0.12,
            "stick_mix_mode": "replace", "response_curve": "precision",
        },
    }

    def __init__(self, window: "NikaidoWindow") -> None:
        super().__init__()
        self.window = window
        self._loading = False
        self._persist_timer = QTimer(self)
        self._persist_timer.setSingleShot(True)
        self._persist_timer.timeout.connect(self._persist_now)
        self._was_calibrating = False

        bar = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(label("Gyro Studio", "title"))
        subtitle = label(
            "Apuntado por movimiento, activadores, respuesta profesional y Flick Stick.",
            "muted",
        )
        subtitle.setWordWrap(True)
        titles.addWidget(subtitle)
        bar.addLayout(titles, 1)
        self.preset = QComboBox()
        self.preset.addItem("Preset…", "")
        self.preset.addItem("Suave", "suave")
        self.preset.addItem("Equilibrado", "equilibrado")
        self.preset.addItem("Competitivo", "competitivo")
        self.preset.addItem("Gyro como stick", "stick")
        bar.addWidget(self.preset)
        bar.addWidget(button("Aplicar preset", self.apply_preset))
        self.enabled = QCheckBox("Giroscopio activo")
        self.enabled.toggled.connect(self.save)
        bar.addWidget(self.enabled)
        bar.addWidget(button("Recentrar", self.recenter))
        bar.addWidget(button("Calibrar", self.calibrate, primary=True))
        self.layout.addLayout(bar)

        upper = QHBoxLayout()
        upper.setSpacing(14)
        self.tabs = configure_tabs(QTabWidget())
        self.tabs.addTab(self._build_general_tab(), "General")
        self.tabs.addTab(self._build_response_tab(), "Respuesta avanzada")
        self.tabs.addTab(self._build_flick_tab(), "Flick Stick")
        self.tabs.addTab(self._build_mouse_to_gyro_tab(), "Mouse → Gyro")
        upper.addWidget(self.tabs, 60)
        upper.addWidget(self._build_telemetry_card(), 40)
        self.layout.addLayout(upper)
        self.load()

    def _build_general_tab(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)
        mode_row = QHBoxLayout()
        mode_col = QVBoxLayout()
        mode_col.addWidget(label("Modo de salida", "muted"))
        self.mode = QComboBox()
        self.mode.addItem("Desactivado", "disabled")
        self.mode.addItem("Mouse", "mouse")
        self.mode.addItem("Stick derecho", "right_stick")
        self.mode.addItem("Passthrough DS4", "passthrough_ds4")
        self.mode.currentIndexChanged.connect(self.save)
        mode_col.addWidget(self.mode)
        mode_row.addLayout(mode_col)
        activation_col = QVBoxLayout()
        activation_col.addWidget(label("Activación", "muted"))
        self.activation = QComboBox()
        for title, value in (
            ("Siempre", "always"),
            ("Mantener L2", "hold_l2"),
            ("Mantener botón", "hold_button"),
            ("Touchpad", "touchpad"),
            ("Alternar", "toggle"),
            ("Activo al soltar botón", "inverted"),
        ):
            self.activation.addItem(title, value)
        self.activation.currentIndexChanged.connect(self.save)
        activation_col.addWidget(self.activation)
        mode_row.addLayout(activation_col)
        button_col = QVBoxLayout()
        button_col.addWidget(label("Botón activador", "muted"))
        self.activation_button = QComboBox()
        from src.emulator import BUTTON_FRIENDLY_NAMES, REMAPPABLE_BUTTONS
        for item in REMAPPABLE_BUTTONS:
            self.activation_button.addItem(BUTTON_FRIENDLY_NAMES.get(item, item), item)
        self.activation_button.currentIndexChanged.connect(self.save)
        button_col.addWidget(self.activation_button)
        mode_row.addLayout(button_col)
        root.addLayout(mode_row)

        self.activation_threshold = SliderRow("Umbral de gatillo", 0, 255, 20, decimals=0)
        self.activation_threshold.changed.connect(lambda _v: self.save())
        root.addWidget(self.activation_threshold)

        self.sliders: Dict[str, SliderRow] = {}
        for key, title, minimum, maximum, default in (
            ("sensitivity_x", "Sensibilidad horizontal", 0.01, 10, 1.25),
            ("sensitivity_y", "Sensibilidad vertical", 0.01, 10, 1.25),
            ("deadzone", "Zona muerta del sensor", 0, 20, 1.25),
            ("smoothing", "Suavizado", 0, 0.95, 0.2),
            ("acceleration", "Aceleración", 0, 5, 0.35),
        ):
            slider = SliderRow(title, minimum, maximum, default, decimals=2)
            slider.changed.connect(lambda _v, k=key: self.save())
            self.sliders[key] = slider
            root.addWidget(slider)

        options = QHBoxLayout()
        self.invert_x = QCheckBox("Invertir horizontal")
        self.invert_y = QCheckBox("Invertir vertical")
        self.accel = QCheckBox("Aceleración dinámica")
        self.drift = QCheckBox("Filtro de drift")
        for widget in (self.invert_x, self.invert_y, self.accel, self.drift):
            widget.toggled.connect(self.save)
            options.addWidget(widget)
        options.addStretch()
        root.addLayout(options)
        root.addStretch()
        return page

    def _build_response_tab(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)
        intro = QLabel(
            "Ajustes finos. Los valores normales ya son rápidos; cambia esto solo para adaptar la sensación a cada juego."
        )
        intro.setWordWrap(True)
        intro.setProperty("muted", True)
        root.addWidget(intro)

        self.advanced_sliders: Dict[str, SliderRow] = {}
        for key, title, minimum, maximum, default, decimals in (
            ("min_threshold", "Salida mínima", 0, 5, 0.10, 2),
            ("max_speed", "Velocidad máxima del mouse", 100, 10000, 1800, 0),
            ("stick_sensitivity_x", "Stick · sensibilidad X", 0.0001, 0.08, 0.018, 4),
            ("stick_sensitivity_y", "Stick · sensibilidad Y", 0.0001, 0.08, 0.018, 4),
            ("stick_deadzone", "Stick · zona muerta", 0, 0.50, 0.04, 2),
            ("stick_anti_deadzone", "Stick · anti-zona muerta", 0, 0.50, 0.12, 2),
            ("stick_max_output", "Stick · salida máxima", 0.05, 1.0, 1.0, 2),
            ("stick_mix", "Mezcla con palanca física", 0, 1.0, 1.0, 2),
        ):
            slider = SliderRow(title, minimum, maximum, default, decimals=decimals)
            slider.changed.connect(lambda _v, k=key: self.save())
            self.advanced_sliders[key] = slider
            root.addWidget(slider)

        selectors = QHBoxLayout()
        curve_box = QVBoxLayout()
        curve_box.addWidget(label("Curva", "muted"))
        self.response_curve = QComboBox()
        self.response_curve.addItem("Lineal", "linear")
        self.response_curve.addItem("Exponencial", "exponential")
        self.response_curve.addItem("Precisión", "precision")
        self.response_curve.currentIndexChanged.connect(self.save)
        curve_box.addWidget(self.response_curve)
        selectors.addLayout(curve_box)
        mix_box = QVBoxLayout()
        mix_box.addWidget(label("Modo de mezcla", "muted"))
        self.stick_mix_mode = QComboBox()
        self.stick_mix_mode.addItem("Sumar al stick", "add")
        self.stick_mix_mode.addItem("Reemplazar stick", "replace")
        self.stick_mix_mode.addItem("Priorizar gyro", "prioritize")
        self.stick_mix_mode.currentIndexChanged.connect(self.save)
        mix_box.addWidget(self.stick_mix_mode)
        selectors.addLayout(mix_box)
        hz_box = QVBoxLayout()
        hz_box.addWidget(label("Frecuencia de referencia", "muted"))
        self.update_hz = QSpinBox()
        self.update_hz.setRange(30, 250)
        self.update_hz.setValue(120)
        self.update_hz.setSuffix(" Hz")
        self.update_hz.setToolTip(
            "Estabiliza el primer cálculo al conectar. Durante el juego, Nikaido sigue la frecuencia HID real del DualSense."
        )
        self.update_hz.valueChanged.connect(self.save)
        hz_box.addWidget(self.update_hz)
        selectors.addLayout(hz_box)
        root.addLayout(selectors)
        root.addStretch()
        return page

    def _build_flick_tab(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)
        hero = card(sub=True)
        box = QHBoxLayout(hero)
        icon = QLabel("↻")
        icon.setProperty("accentText", True)
        icon.setStyleSheet("font-size:34px")
        box.addWidget(icon)
        text = QVBoxLayout()
        text.addWidget(label("Giro instantáneo con la palanca derecha", "heading"))
        help_text = QLabel(
            "Empuja la palanca hacia una dirección para girar a ese ángulo; usa el gyro para la precisión fina."
        )
        help_text.setWordWrap(True)
        help_text.setProperty("muted", True)
        text.addWidget(help_text)
        box.addLayout(text, 1)
        self.flick_enabled = QCheckBox("Flick Stick")
        self.flick_enabled.toggled.connect(self.save)
        box.addWidget(self.flick_enabled)
        root.addWidget(hero)

        self.flick_sliders: Dict[str, SliderRow] = {}
        for key, title, minimum, maximum, default, decimals, suffix in (
            ("flick_threshold", "Umbral de entrada", 0.45, 0.98, 0.82, 2, ""),
            ("flick_release_threshold", "Umbral para volver a activar", 0.20, 0.90, 0.55, 2, ""),
            ("flick_min_angle", "Ángulo mínimo", 0, 45, 5, 1, "°"),
            ("flick_pixels_per_degree", "Mouse · píxeles por grado", 0.1, 30, 4, 1, ""),
            ("flick_duration_ms", "Mouse · duración del giro", 10, 500, 85, 0, " ms"),
            ("flick_turn_180_ms", "Stick · tiempo para 180°", 40, 2000, 240, 0, " ms"),
        ):
            slider = SliderRow(title, minimum, maximum, default, decimals=decimals, suffix=suffix)
            slider.changed.connect(lambda _v, k=key: self.save())
            self.flick_sliders[key] = slider
            root.addWidget(slider)
        self.flick_invert = QCheckBox("Invertir dirección horizontal del Flick Stick")
        self.flick_invert.toggled.connect(self.save)
        root.addWidget(self.flick_invert)
        self.flick_status = label("Flick Stick apagado", "muted")
        root.addWidget(self.flick_status)
        root.addStretch()
        return page

    def _build_mouse_to_gyro_tab(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)
        help_text = QLabel(
            "Convierte el movimiento del mouse en datos de giroscopio del DS4 virtual. Solo se usa con Passthrough DS4. El cursor se centra mientras está activo; Ctrl + M lo libera y apaga esta opción."
        )
        help_text.setWordWrap(True)
        help_text.setProperty("muted", True)
        root.addWidget(help_text)
        self.mouse_gyro_toggle = QCheckBox("Usar mouse como giroscopio del DS4")
        self.mouse_gyro_toggle.toggled.connect(self.save)
        root.addWidget(self.mouse_gyro_toggle)
        self.mouse_gyro_sensitivity = SliderRow(
            "Sensibilidad del mouse", 0.01, 0.50, 0.12, decimals=2
        )
        self.mouse_gyro_sensitivity.changed.connect(lambda _v: self.save())
        root.addWidget(self.mouse_gyro_sensitivity)
        self.mouse_gyro_max = SliderRow(
            "Velocidad máxima virtual", 100, 5000, 1400, decimals=0, suffix=" dps"
        )
        self.mouse_gyro_max.changed.connect(lambda _v: self.save())
        root.addWidget(self.mouse_gyro_max)
        self.mouse_gyro_invert_x = QCheckBox("Invertir horizontal")
        self.mouse_gyro_invert_y = QCheckBox("Invertir vertical")
        self.mouse_gyro_combine = QCheckBox("Combinar con movimiento físico")
        for widget in (
            self.mouse_gyro_invert_x,
            self.mouse_gyro_invert_y,
            self.mouse_gyro_combine,
        ):
            widget.toggled.connect(self.save)
            root.addWidget(widget)
        self.mouse_gyro_status = label(
            "Selecciona Passthrough DS4 para usar esta opción.", "muted"
        )
        root.addWidget(self.mouse_gyro_status)
        root.addStretch()
        return page

    def _build_telemetry_card(self) -> QFrame:
        telemetry = card()
        t = QVBoxLayout(telemetry)
        t.addWidget(label("TELEMETRÍA IMU", "eyebrow"))
        self.gyro_graph = LatencyGraph(75, 1.0, top_label="Alta", middle_label="Media", bottom_label="0", footer="Ahora")
        t.addWidget(self.gyro_graph)
        grid = QGridLayout()
        self.values: Dict[str, QLabel] = {}
        for index, key in enumerate(
            ("Pitch", "Yaw", "Roll", "Salida X", "Salida Y", "Muestreo")
        ):
            tile = card(sub=True)
            v = QVBoxLayout(tile)
            v.addWidget(label(key, "muted"))
            val = label("0.00", "value")
            v.addWidget(val)
            self.values[key] = val
            grid.addWidget(tile, index // 2, index % 2)
        t.addLayout(grid)
        self.calibration = QLabel("Estado: esperando datos")
        self.calibration.setWordWrap(True)
        self.calibration.setProperty("muted", True)
        t.addWidget(self.calibration)
        t.addWidget(button("Probar salida durante 2 segundos", self.test))
        t.addStretch()
        return telemetry

    def load(self) -> None:
        engine = self.window.gyro_engine
        if not engine:
            return
        config = engine.get_config()
        self._loading = True
        self.enabled.setChecked(config.enabled)
        self.mode.setCurrentIndex(max(0, self.mode.findData(config.mode)))
        self.activation.setCurrentIndex(max(0, self.activation.findData(config.activation)))
        self.activation_button.setCurrentIndex(
            max(0, self.activation_button.findData(config.activation_button))
        )
        self.activation_threshold.set_value(config.activation_threshold)
        for key, slider in self.sliders.items():
            slider.set_value(float(getattr(config, key)))
        for key, slider in self.advanced_sliders.items():
            slider.set_value(float(getattr(config, key)))
        for key, slider in self.flick_sliders.items():
            slider.set_value(float(getattr(config, key)))
        self.update_hz.setValue(config.update_hz)
        self.response_curve.setCurrentIndex(max(0, self.response_curve.findData(config.response_curve)))
        self.stick_mix_mode.setCurrentIndex(max(0, self.stick_mix_mode.findData(config.stick_mix_mode)))
        for widget, key in (
            (self.invert_x, "invert_x"),
            (self.invert_y, "invert_y"),
            (self.accel, "acceleration_enabled"),
            (self.drift, "drift_filter"),
            (self.flick_enabled, "flick_stick_enabled"),
            (self.flick_invert, "flick_invert_x"),
            (self.mouse_gyro_toggle, "mouse_to_gyro_enabled"),
            (self.mouse_gyro_invert_x, "mouse_to_gyro_invert_x"),
            (self.mouse_gyro_invert_y, "mouse_to_gyro_invert_y"),
            (self.mouse_gyro_combine, "mouse_to_gyro_combine_physical"),
        ):
            widget.setChecked(bool(getattr(config, key)))
        self.mouse_gyro_sensitivity.set_value(config.mouse_to_gyro_sensitivity)
        self.mouse_gyro_max.set_value(config.mouse_to_gyro_max_dps)
        self._loading = False
        self._refresh_mode_controls()

    def save(self, *_args: Any) -> None:
        if self._loading or not self.window.gyro_engine:
            return
        changes = {key: slider.spin.value() for key, slider in self.sliders.items()}
        changes.update({key: slider.spin.value() for key, slider in self.advanced_sliders.items()})
        changes.update({key: slider.spin.value() for key, slider in self.flick_sliders.items()})
        changes.update(
            enabled=self.enabled.isChecked(),
            mode=self.mode.currentData(),
            activation=self.activation.currentData(),
            activation_button=self.activation_button.currentData(),
            activation_threshold=round(self.activation_threshold.spin.value()),
            invert_x=self.invert_x.isChecked(),
            invert_y=self.invert_y.isChecked(),
            acceleration_enabled=self.accel.isChecked(),
            drift_filter=self.drift.isChecked(),
            update_hz=self.update_hz.value(),
            response_curve=self.response_curve.currentData(),
            stick_mix_mode=self.stick_mix_mode.currentData(),
            flick_stick_enabled=self.flick_enabled.isChecked(),
            flick_invert_x=self.flick_invert.isChecked(),
            mouse_to_gyro_enabled=self.mouse_gyro_toggle.isChecked(),
            mouse_to_gyro_sensitivity=self.mouse_gyro_sensitivity.spin.value(),
            mouse_to_gyro_max_dps=self.mouse_gyro_max.spin.value(),
            mouse_to_gyro_invert_x=self.mouse_gyro_invert_x.isChecked(),
            mouse_to_gyro_invert_y=self.mouse_gyro_invert_y.isChecked(),
            mouse_to_gyro_combine_physical=self.mouse_gyro_combine.isChecked(),
        )
        self.window.gyro_engine.update_config(**changes)
        self._refresh_mode_controls()
        self.persist()

    def apply_preset(self) -> None:
        key = self.preset.currentData()
        values = self.PRESETS.get(key)
        if not values or not self.window.gyro_engine:
            self.window.toast(tr("Selecciona un preset", self.window.language), "warning")
            return
        self.window.gyro_engine.update_config(**values)
        self.load()
        self.persist()
        self.window.toast(tr("Preset de giroscopio aplicado", self.window.language), "success")

    def _refresh_mode_controls(self) -> None:
        engine_config = self.window.gyro_engine.get_config() if self.window.gyro_engine else None
        if engine_config is not None:
            expected = bool(engine_config.mouse_to_gyro_enabled)
            if self.mouse_gyro_toggle.isChecked() != expected:
                self._loading = True
                self.mouse_gyro_toggle.setChecked(expected)
                self._loading = False
        mode = self.mode.currentData()
        passthrough = mode == "passthrough_ds4"
        button_mode = self.activation.currentData() in ("hold_button", "toggle", "inverted")
        self.activation_button.setEnabled(button_mode)
        self.activation_threshold.setEnabled(
            self.activation.currentData() == "hold_l2"
            or (button_mode and self.activation_button.currentData() in ("L2_btn", "R2_btn"))
        )
        for widget in (
            self.mouse_gyro_toggle,
            self.mouse_gyro_sensitivity,
            self.mouse_gyro_max,
            self.mouse_gyro_invert_x,
            self.mouse_gyro_invert_y,
            self.mouse_gyro_combine,
        ):
            widget.setEnabled(passthrough)
        for widget in (self.flick_enabled, *self.flick_sliders.values(), self.flick_invert):
            widget.setEnabled(mode in ("mouse", "right_stick"))
        emulator = getattr(self.window.connection_manager, "emulator", None)
        available = bool(
            emulator and getattr(emulator, "supports_mouse_to_gyro", lambda: False)()
        )
        capture = (
            getattr(emulator, "get_mouse_to_gyro_status", lambda: {})()
            if emulator else {}
        )
        backend_names = {
            "raw_input": "Raw Input",
            "low_level_hook": "hook global",
            "cursor_poll": "sondeo de cursor",
        }
        if not passthrough:
            text = "Selecciona Passthrough DS4 para usar esta opción."
        elif not available:
            text = "Mouse → gyro requiere Windows."
        elif self.mouse_gyro_toggle.isChecked() and capture.get("activation_pending"):
            remaining = max(
                1,
                int(float(capture.get("activation_remaining_seconds", 0.0) or 0.0) + 0.999),
            )
            text = (
                f"Mouse → gyro se activa en {remaining} s. Abre tu juego ahora. "
                "Ctrl + M activa o desactiva el mouse."
            )
        elif self.mouse_gyro_toggle.isChecked() and capture.get("running"):
            backend = backend_names.get(capture.get("backend"), capture.get("backend", "captura global"))
            text = (
                f"Captura activa con {backend}. Mueve el mouse para alimentar el DS4 virtual. "
                "Ctrl + M activa o desactiva el mouse."
            )
        elif self.mouse_gyro_toggle.isChecked() and capture.get("hotkey_paused"):
            text = "Mouse liberado temporalmente. Presiona Ctrl + M para reactivarlo al instante."
        elif self.mouse_gyro_toggle.isChecked() and capture.get("last_error"):
            text = f"No se pudo capturar el mouse: {capture['last_error']}"
        elif self.mouse_gyro_toggle.isChecked():
            text = "Preparando la captura global del mouse…"
        elif capture.get("emergency_stop_reason"):
            text = "Cursor liberado con Ctrl + M. Vuelve a presionarlo para reactivar el mouse al instante."
        else:
            text = "Apagado. El movimiento físico del control sigue funcionando."
        self.mouse_gyro_status.setText(text)

    def persist(self) -> None:
        self._persist_timer.start(220)

    def _persist_now(self) -> None:
        manager = self.window.profile_manager
        trigger = self.window.trigger_engine
        if manager and trigger:
            manager.set_setting("profile_gyro", trigger.export_gyro_overrides())
            manager.set_setting("profile_overrides", trigger.export_profile_overrides())
            manager.set_custom_profiles(trigger.export_custom_profiles_to_dict())
            self.window.request_config_save()

    def calibrate(self) -> None:
        if self.window.gyro_engine:
            self._was_calibrating = True
            self.window.gyro_engine.begin_calibration()
            self.window.toast(tr("Deja el control quieto mientras se calibra", self.window.language))

    def recenter(self) -> None:
        if self.window.gyro_engine:
            self.window.gyro_engine.recenter()
            self.window.toast(tr("Orientación recentrada", self.window.language))

    def test(self) -> None:
        if self.window.gyro_engine:
            self.window.gyro_engine.test_output(2.0)

    def update_live(self) -> None:
        if not self.window.gyro_engine:
            return
        data = self.window.gyro_engine.get_telemetry()
        if data.calibrating:
            self._was_calibrating = True
        elif self._was_calibrating:
            self._was_calibrating = False
            if data.calibrated:
                self.persist()
                self.window.toast(tr("Calibración de giroscopio guardada", self.window.language), "success")
        vals = {
            "Pitch": data.pitch,
            "Yaw": data.yaw,
            "Roll": data.roll,
            "Salida X": data.output_x,
            "Salida Y": data.output_y,
            "Muestreo": data.sample_hz,
        }
        for key, value in vals.items():
            self.values[key].setText(f"{value:.1f}{' Hz' if key == 'Muestreo' else ''}")
        self.gyro_graph.add_value(min(3.0, (abs(data.output_x) + abs(data.output_y)) / 600.0))
        if data.calibration_error:
            status = data.calibration_error
        elif data.calibrating:
            status = f"calibrando {round(data.calibration_progress * 100)}%"
        elif data.mouse_to_gyro_active:
            status = "mouse → gyro activo"
        else:
            status = "activo" if data.active else "en espera"
        self.calibration.setText(f"Estado: {status} · {data.mode}")
        if getattr(data, "flick_active", False):
            self.flick_status.setText(
                f"Flick activo · {getattr(data, 'flick_angle', 0.0):.0f}° · pendiente {getattr(data, 'flick_pending', 0.0):.1f}"
            )
            self.flick_status.setStyleSheet(f"color:{C['cyan']};font-weight:700")
        elif self.flick_enabled.isChecked():
            self.flick_status.setText("Flick Stick listo · mueve la palanca desde el centro")
            self.flick_status.setStyleSheet(f"color:{C['green']}")
        else:
            self.flick_status.setText("Flick Stick apagado")
            self.flick_status.setStyleSheet(f"color:{C['muted']}")
        self._refresh_mode_controls()
