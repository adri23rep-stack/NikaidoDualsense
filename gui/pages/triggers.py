"""Editor visual y biblioteca de efectos para los gatillos adaptativos."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..ui_common import (
    Any,
    C,
    Dict,
    List,
    Optional,
    QCheckBox,
    QColor,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPointF,
    QProgressBar,
    QRectF,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
    button,
    card,
    label,
)
from ..components import ScrollPage, SliderRow

if TYPE_CHECKING:
    from ..main_window import NikaidoWindow


class TriggerCurveEditor(QWidget):
    """Editor visual de cuatro tramos reales de resistencia (zonas 0-9)."""

    changed = Signal(object)
    DEFAULT_POINTS = [(0, 40), (3, 120), (6, 180), (9, 220)]

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(270)
        self.setMinimumWidth(520)
        self.setMouseTracking(True)
        self.points: List[tuple[int, int]] = list(self.DEFAULT_POINTS)
        self._dragging: Optional[int] = None
        self._margin_left = 45
        self._margin_right = 22
        self._margin_top = 20
        self._margin_bottom = 35

    @staticmethod
    def _sanitize(points: Any) -> List[tuple[int, int]]:
        parsed: List[tuple[int, int]] = []
        if isinstance(points, (list, tuple)):
            for item in points:
                try:
                    pos, force = item
                    parsed.append(
                        (
                            max(0, min(9, int(round(float(pos))))),
                            max(0, min(255, int(round(float(force))))),
                        )
                    )
                except (TypeError, ValueError, OverflowError):
                    continue
        unique: Dict[int, int] = {}
        for pos, force in parsed:
            unique[pos] = force
        result = sorted(unique.items())
        return result if len(result) == 4 else list(TriggerCurveEditor.DEFAULT_POINTS)

    def set_points(self, points: Any) -> None:
        self.points = self._sanitize(points)
        self._dragging = None
        self.update()

    def get_points(self) -> List[tuple[int, int]]:
        return list(self.points)

    def _bounds(self) -> tuple[float, float, float, float]:
        return (
            float(self._margin_left),
            float(self._margin_top),
            float(max(self._margin_left + 1, self.width() - self._margin_right)),
            float(max(self._margin_top + 1, self.height() - self._margin_bottom)),
        )

    def _to_canvas(self, position: float, force: float) -> QPointF:
        left, top, right, bottom = self._bounds()
        x = left + (position / 9.0) * (right - left)
        y = bottom - (force / 255.0) * (bottom - top)
        return QPointF(x, y)

    def _from_canvas(self, point: QPointF) -> tuple[int, int]:
        left, top, right, bottom = self._bounds()
        position = round(((point.x() - left) / max(1.0, right - left)) * 9.0)
        force = round(((bottom - point.y()) / max(1.0, bottom - top)) * 255.0)
        return max(0, min(9, position)), max(0, min(255, force))

    def paintEvent(self, _event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(C["panel2"]))
        left, top, right, bottom = self._bounds()

        grid_pen = QPen(QColor(C["border"]))
        grid_pen.setWidth(1)
        painter.setPen(grid_pen)
        for position in range(10):
            point = self._to_canvas(position, 0)
            painter.drawLine(QPointF(point.x(), top), QPointF(point.x(), bottom))
        for force in (0, 64, 128, 192, 255):
            point = self._to_canvas(0, force)
            painter.drawLine(QPointF(left, point.y()), QPointF(right, point.y()))
            painter.setPen(QColor(C["muted"]))
            painter.drawText(
                QRectF(2, point.y() - 9, left - 8, 18), Qt.AlignmentFlag.AlignRight, str(force)
            )
            painter.setPen(grid_pen)

        points = sorted(self.points, key=lambda item: item[0])
        path = QPainterPath()
        if points:
            first_pos, first_force = points[0]
            if first_pos > 0:
                start = self._to_canvas(0, 0)
                at_first_zero = self._to_canvas(first_pos, 0)
                at_first_force = self._to_canvas(first_pos, first_force)
                path.moveTo(start)
                path.lineTo(at_first_zero)
                path.lineTo(at_first_force)
            else:
                path.moveTo(self._to_canvas(first_pos, first_force))
            for index, (position, force) in enumerate(points):
                next_position = points[index + 1][0] if index + 1 < len(points) else 9
                path.lineTo(self._to_canvas(next_position, force))
                if index + 1 < len(points):
                    path.lineTo(self._to_canvas(next_position, points[index + 1][1]))
        curve_pen = QPen(QColor(C["accent2"]))
        curve_pen.setWidth(3)
        painter.setPen(curve_pen)
        painter.drawPath(path)

        painter.setBrush(QColor(C["accent"]))
        point_pen = QPen(QColor(C["text"]))
        point_pen.setWidth(2)
        painter.setPen(point_pen)
        for position, force in self.points:
            point = self._to_canvas(position, force)
            painter.drawEllipse(point, 8, 8)

        painter.setPen(QColor(C["muted"]))
        painter.drawText(
            QRectF(left, bottom + 6, 90, 22),
            Qt.AlignmentFlag.AlignLeft,
            "Suelto",
        )
        painter.drawText(
            QRectF(right - 90, bottom + 6, 90, 22),
            Qt.AlignmentFlag.AlignRight,
            "Fondo",
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        cursor = event.position()
        closest: Optional[int] = None
        distance = float("inf")
        for index, (position, force) in enumerate(self.points):
            point = self._to_canvas(position, force)
            current = ((point.x() - cursor.x()) ** 2 + (point.y() - cursor.y()) ** 2) ** 0.5
            if current < distance:
                closest, distance = index, current
        if closest is not None and distance <= 18:
            self._dragging = closest

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging is None or not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        position, force = self._from_canvas(event.position())
        index = self._dragging
        minimum = self.points[index - 1][0] + 1 if index > 0 else 0
        maximum = self.points[index + 1][0] - 1 if index < len(self.points) - 1 else 9
        position = max(minimum, min(maximum, position))
        self.points[index] = (position, force)
        self.update()
        self.changed.emit(self.get_points())

    def mouseReleaseEvent(self, _event: QMouseEvent) -> None:
        if self._dragging is not None:
            self._dragging = None
            self.changed.emit(self.get_points())


class AdaptiveTriggersPage(ScrollPage):
    PRESET_CATEGORIES = ("Todos", "Básicos", "Armas", "Vehículos", "Mecánicos")
    EFFECTS = (
        ("Libre / apagado", "off"),
        ("Rigidez", "rigid"),
        ("Pulso", "pulse"),
        ("Vibración continua", "continuous_vibration"),
        ("Secciones", "sections"),
        ("Arma semiautomática", "weapon_single"),
        ("Arma automática", "weapon_automatic"),
        ("Francotirador", "weapon_sniper"),
        ("Arco", "weapon_bow"),
        ("Personalizado", "custom"),
    )

    def __init__(self, window: "NikaidoWindow") -> None:
        super().__init__()
        self.window = window
        self._loading = False
        self.controls: Dict[str, Dict[str, Any]] = {}
        self._reapply_timer = QTimer(self)
        self._reapply_timer.setSingleShot(True)
        self._reapply_timer.timeout.connect(self._reapply_active)
        self._persist_timer = QTimer(self)
        self._persist_timer.setSingleShot(True)
        self._persist_timer.timeout.connect(self._persist_now)
        self._live_timer = QTimer(self)
        self._live_timer.setInterval(50)
        self._live_timer.timeout.connect(self._update_live_positions)
        bar = QHBoxLayout()
        bar.addWidget(label("Gatillos adaptativos", "title"))
        bar.addStretch()
        self.profile = QComboBox()
        self.profile.currentIndexChanged.connect(self.load)
        bar.addWidget(label("Perfil", "muted"))
        bar.addWidget(self.profile)
        self.link_triggers = QCheckBox("Vincular L2 y R2")
        self.link_triggers.toggled.connect(self._toggle_link)
        bar.addWidget(self.link_triggers)
        bar.addWidget(button("Abrir vibración", self.open_vibration))
        bar.addWidget(button("Probar efecto real", lambda: self.test("both"), primary=True))
        self.layout.addLayout(bar)
        intro = label(
            "Elige un preset o construye el efecto por zonas. El monitor muestra el recorrido físico de cada gatillo y todo se guarda dentro del perfil.",
            "muted",
        )
        intro.setWordWrap(True)
        self.layout.addWidget(intro)
        self.layout.addWidget(self._build_preset_studio())
        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(self._trigger_panel("left", "L2 · GATILLO IZQUIERDO"))
        row.addWidget(self._trigger_panel("right", "R2 · GATILLO DERECHO"))
        self.layout.addLayout(row)

        curve_card = card()
        curve_box = QVBoxLayout(curve_card)
        curve_header = QHBoxLayout()
        curve_header.addWidget(label("CURVA VISUAL DE RIGIDEZ", "eyebrow"))
        curve_header.addStretch()
        self.curve_trigger = QComboBox()
        self.curve_trigger.addItem("L2", "left")
        self.curve_trigger.addItem("R2", "right")
        self.curve_trigger.setCurrentIndex(1)
        self.curve_trigger.currentIndexChanged.connect(self._load_curve)
        curve_header.addWidget(self.curve_trigger)
        curve_header.addWidget(button("Restablecer curva", self._reset_curve))
        curve_box.addLayout(curve_header)
        curve_help = label(
            "Arrastra los cuatro puntos. Cada punto inicia un tramo real de resistencia que se manda al DualSense.",
            "muted",
        )
        curve_help.setWordWrap(True)
        curve_box.addWidget(curve_help)
        self.curve_editor = TriggerCurveEditor()
        self.curve_editor.changed.connect(self._curve_changed)
        curve_box.addWidget(self.curve_editor)
        self.curve_zones = label("", "muted")
        self.curve_zones.setWordWrap(True)
        curve_box.addWidget(self.curve_zones)
        self.layout.addWidget(curve_card)

        linked = bool(
            self.window.profile_manager.get_setting("trigger_linked", False)
            if self.window.profile_manager else False
        )
        self.link_triggers.blockSignals(True)
        self.link_triggers.setChecked(linked)
        self.link_triggers.blockSignals(False)
        self._toggle_link(linked)

        self.refresh_profiles()
        self._refresh_preset_list()
        self.load()
        self._live_timer.start()

    def _build_preset_studio(self) -> QFrame:
        preset_card = card()
        box = QVBoxLayout(preset_card)
        box.addWidget(label("BIBLIOTECA DE SENSACIONES", "eyebrow"))
        row = QHBoxLayout()
        self.preset_category = QComboBox()
        for category in self.PRESET_CATEGORIES:
            self.preset_category.addItem(category, category)
        self.preset_category.currentIndexChanged.connect(self._refresh_preset_list)
        row.addWidget(self.preset_category)
        self.preset = QComboBox()
        self.preset.currentIndexChanged.connect(self._preset_changed)
        row.addWidget(self.preset, 1)
        self.preset_target = QComboBox()
        self.preset_target.addItem("Aplicar a L2", "left")
        self.preset_target.addItem("Aplicar a R2", "right")
        self.preset_target.addItem("Aplicar a ambos", "both")
        row.addWidget(self.preset_target)
        row.addWidget(button("Aplicar preset", self._apply_preset, primary=True))
        box.addLayout(row)
        self.preset_description = label("", "muted")
        self.preset_description.setWordWrap(True)
        box.addWidget(self.preset_description)
        return preset_card

    def _trigger_panel(self, trigger: str, title: str) -> QFrame:
        panel = card()
        box = QVBoxLayout(panel)
        header = QHBoxLayout()
        header.addWidget(label(title, "eyebrow"))
        header.addStretch()
        other = "right" if trigger == "left" else "left"
        header.addWidget(
            button(
                "Copiar a R2" if trigger == "left" else "Copiar a L2",
                lambda _checked=False, source=trigger, target=other: self._copy_trigger(source, target),
            )
        )
        header.addWidget(
            button(
                "Limpiar",
                lambda _checked=False, side=trigger: self._clear_trigger(side),
                danger=True,
            )
        )
        box.addLayout(header)

        position = QProgressBar()
        position.setRange(0, 255)
        position.setValue(0)
        position.setFormat("Recorrido físico: %v / 255")
        box.addWidget(position)
        summary = label("Gatillo libre", "muted")
        summary.setWordWrap(True)
        box.addWidget(summary)

        effect = QComboBox()
        for text, value in self.EFFECTS:
            effect.addItem(text, value)
        effect.currentIndexChanged.connect(
            lambda _index, side=trigger: self._effect_controls_changed(side)
        )
        box.addWidget(QLabel("Efecto base"))
        box.addWidget(effect)

        intensity = SliderRow("Rigidez / intensidad", 0, 255, 140, decimals=0)
        start = SliderRow("Zona inicial", 0, 9, 1, decimals=0)
        end = SliderRow("Zona final", 0, 9, 9, decimals=0)
        frequency = SliderRow("Frecuencia", 0, 255, 25, decimals=0, suffix=" Hz")
        for control in (intensity, start, end, frequency):
            control.changed.connect(lambda _v: self.save())
            box.addWidget(control)

        animated = QCheckBox("Animar resistencia")
        animated.toggled.connect(
            lambda _checked, side=trigger: self._effect_controls_changed(side)
        )
        box.addWidget(animated)
        curve = QComboBox()
        for text, value in (
            ("Lineal", "linear"),
            ("Entrada suave", "ease_in"),
            ("Salida suave", "ease_out"),
            ("Suave completa", "ease_in_out"),
            ("Seno", "sine"),
            ("Rebote", "bounce"),
        ):
            curve.addItem(text, value)
        curve.currentIndexChanged.connect(self.save)
        box.addWidget(QLabel("Curva de animación"))
        box.addWidget(curve)
        animation_speed = SliderRow("Velocidad de curva", 0.1, 8.0, 1.0, decimals=1, suffix="×")
        animation_speed.changed.connect(lambda _v: self.save())
        box.addWidget(animation_speed)

        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet(f"background:{C['border']}")
        box.addWidget(separator)
        box.addWidget(label("VIBRACIÓN DEL GATILLO", "eyebrow"))
        vibration_enabled = QCheckBox("Activar vibración dentro de este gatillo")
        vibration_enabled.toggled.connect(
            lambda _checked, side=trigger: self._effect_controls_changed(side)
        )
        box.addWidget(vibration_enabled)
        vibration_intensity = SliderRow("Intensidad", 0, 255, 150, decimals=0)
        vibration_frequency = SliderRow("Frecuencia", 1, 255, 25, decimals=0, suffix=" Hz")
        vibration_start = SliderRow("Zona de inicio", 0, 9, 2, decimals=0)
        vibration_end = SliderRow("Zona final", 0, 9, 9, decimals=0)
        for control in (
            vibration_intensity,
            vibration_frequency,
            vibration_start,
            vibration_end,
        ):
            control.changed.connect(lambda _v: self.save())
            box.addWidget(control)
        box.addWidget(button("Probar L2" if trigger == "left" else "Probar R2", lambda: self.test(trigger), primary=True))
        box.addStretch()
        self.controls[trigger] = {
            "panel": panel,
            "position": position,
            "summary": summary,
            "effect": effect,
            "intensity": intensity,
            "start": start,
            "end": end,
            "frequency": frequency,
            "animated": animated,
            "curve": curve,
            "animation_speed": animation_speed,
            "vibration_enabled": vibration_enabled,
            "vibration_intensity": vibration_intensity,
            "vibration_frequency": vibration_frequency,
            "vibration_start": vibration_start,
            "vibration_end": vibration_end,
        }
        return panel

    def _refresh_preset_list(self, *_args: Any) -> None:
        from src.trigger_engine import get_trigger_presets

        category = str(self.preset_category.currentData() or "Todos")
        current = self.preset.currentData()
        self.preset.blockSignals(True)
        self.preset.clear()
        for preset in get_trigger_presets(category):
            self.preset.addItem(preset.name, preset.preset_id)
        index = self.preset.findData(current)
        self.preset.setCurrentIndex(max(0, index))
        self.preset.blockSignals(False)
        self._preset_changed()

    def _preset_changed(self, *_args: Any) -> None:
        from src.trigger_engine import TRIGGER_PRESETS

        preset = TRIGGER_PRESETS.get(str(self.preset.currentData() or ""))
        self.preset_description.setText(
            f"{preset.category} · {preset.description}" if preset else "Selecciona una sensación."
        )

    def _apply_preset(self) -> None:
        from src.trigger_engine import effect_from_preset

        engine = self.window.trigger_engine
        profile_id = self.profile.currentData()
        profile = engine.get_profile(profile_id) if engine and profile_id else None
        preset_id = str(self.preset.currentData() or "")
        if not profile or not preset_id:
            return
        target = str(self.preset_target.currentData() or "right")
        targets = (
            ("left", "right")
            if self.link_triggers.isChecked() or target == "both"
            else (target,)
        )
        try:
            for side in targets:
                effect = effect_from_preset(preset_id)
                if side == "left":
                    profile.left_trigger = effect
                else:
                    profile.right_trigger = effect
        except KeyError as exc:
            self.window.alert(str(exc))
            return
        self.load()
        self._persist()
        if engine.get_current_profile() == profile_id:
            self._reapply_timer.start(60)
        self.window.toast("Preset de gatillo aplicado")

    def _effect_controls_changed(self, trigger: str) -> None:
        self._update_effect_controls(trigger)
        self.save()

    def _update_effect_controls(self, trigger: str) -> None:
        controls = self.controls.get(trigger)
        if not controls:
            return
        effect_type = str(controls["effect"].currentData() or "off")
        active = effect_type != "off"
        frequency_modes = {"pulse", "continuous_vibration", "weapon_automatic"}
        for key in ("intensity", "start", "end"):
            controls[key].setEnabled(active)
        controls["frequency"].setEnabled(effect_type in frequency_modes)
        controls["animated"].setEnabled(active)
        animated = active and controls["animated"].isChecked()
        controls["curve"].setEnabled(animated)
        controls["animation_speed"].setEnabled(animated)
        vibration = active and controls["vibration_enabled"].isChecked()
        for key in (
            "vibration_intensity", "vibration_frequency", "vibration_start", "vibration_end"
        ):
            controls[key].setEnabled(vibration)
        controls["summary"].setText(self._effect_summary(trigger))

    def _effect_summary(self, trigger: str) -> str:
        controls = self.controls.get(trigger)
        if not controls:
            return ""
        title = controls["effect"].currentText() or "Libre"
        if str(controls["effect"].currentData() or "off") == "off":
            return "Gatillo libre, sin resistencia."
        start = int(controls["start"].spin.value())
        end = int(controls["end"].spin.value())
        intensity = int(controls["intensity"].spin.value())
        extra = " · vibración activa" if controls["vibration_enabled"].isChecked() else ""
        return f"{title} · fuerza {intensity}/255 · zonas {start}–{end}{extra}"

    def _copy_trigger(self, source: str, target: str, *, notify: bool = True) -> None:
        from src.trigger_engine import TriggerEffect

        engine = self.window.trigger_engine
        profile_id = self.profile.currentData()
        profile = engine.get_profile(profile_id) if engine and profile_id else None
        if not profile:
            return
        source_effect = profile.left_trigger if source == "left" else profile.right_trigger
        cloned = TriggerEffect.from_dict(source_effect.to_dict())
        if target == "left":
            profile.left_trigger = cloned
        else:
            profile.right_trigger = cloned
        self.load()
        self._persist()
        if engine.get_current_profile() == profile_id:
            self._reapply_timer.start(60)
        if notify:
            self.window.toast(f"{source.upper()} copiado a {target.upper()}")

    def _clear_trigger(self, trigger: str) -> None:
        from src.trigger_engine import TriggerEffect, TriggerEffectType

        engine = self.window.trigger_engine
        profile_id = self.profile.currentData()
        profile = engine.get_profile(profile_id) if engine and profile_id else None
        if not profile:
            return
        effect = TriggerEffect("Libre", TriggerEffectType.OFF)
        if self.link_triggers.isChecked():
            profile.left_trigger = TriggerEffect.from_dict(effect.to_dict())
            profile.right_trigger = TriggerEffect.from_dict(effect.to_dict())
        elif trigger == "left":
            profile.left_trigger = effect
        else:
            profile.right_trigger = effect
        self.load()
        self._persist()
        if engine.get_current_profile() == profile_id:
            self._reapply_timer.start(60)

    def _toggle_link(self, checked: bool) -> None:
        right_panel = self.controls.get("right", {}).get("panel")
        if right_panel is not None:
            right_panel.setEnabled(not checked)
        if hasattr(self, "preset_target"):
            self.preset_target.setEnabled(not checked)
            if checked:
                self.preset_target.setCurrentIndex(
                    max(0, self.preset_target.findData("both"))
                )
        if hasattr(self, "curve_trigger"):
            self.curve_trigger.setEnabled(not checked)
            if checked:
                self.curve_trigger.setCurrentIndex(
                    max(0, self.curve_trigger.findData("left"))
                )
        if checked and self.controls:
            self._copy_trigger("left", "right", notify=False)
        manager = self.window.profile_manager
        if manager:
            manager.set_setting("trigger_linked", bool(checked))
            self.window.request_config_save()

    def _update_live_positions(self) -> None:
        state = getattr(self.window, "_latest_state", None) or getattr(
            self.window, "_pending_state", None
        )
        left = int(getattr(state, "left_trigger", 0) or 0) if state else 0
        right = int(getattr(state, "right_trigger", 0) or 0) if state else 0
        if "left" in self.controls:
            self.controls["left"]["position"].setValue(max(0, min(255, left)))
        if "right" in self.controls:
            self.controls["right"]["position"].setValue(max(0, min(255, right)))

    def open_vibration(self) -> None:
        profile_id = self.profile.currentData()
        page = self.window.ensure_page("vibration")
        self.window.navigate("vibration")
        if profile_id and page is not None:
            page.select_profile(str(profile_id))

    def refresh_profiles(self) -> None:
        engine = self.window.trigger_engine
        current_data = self.profile.currentData()
        current = current_data or (engine.get_current_profile() if engine else None)
        self.profile.blockSignals(True)
        self.profile.clear()
        if engine:
            for pid, name in engine.get_profile_names():
                self.profile.addItem(name, pid)
        self.profile.setCurrentIndex(max(0, self.profile.findData(current)))
        self.profile.blockSignals(False)

    def select_profile(self, profile_id: str) -> None:
        self.profile.setCurrentIndex(max(0, self.profile.findData(profile_id)))
        self.load()

    def load(self) -> None:
        engine = self.window.trigger_engine
        profile_id = self.profile.currentData()
        profile = engine.get_profile(profile_id) if engine and profile_id else None
        if not profile:
            return
        if self.link_triggers.isChecked():
            from src.trigger_engine import TriggerEffect

            if profile.right_trigger.to_dict() != profile.left_trigger.to_dict():
                profile.right_trigger = TriggerEffect.from_dict(profile.left_trigger.to_dict())
                self._persist()
        self._loading = True
        for trigger in ("left", "right"):
            effect_data = profile.left_trigger if trigger == "left" else profile.right_trigger
            controls = self.controls[trigger]
            controls["effect"].setCurrentIndex(
                max(0, controls["effect"].findData(effect_data.effect_type.value))
            )
            controls["intensity"].set_value(effect_data.intensity)
            controls["start"].set_value(effect_data.start_position)
            controls["end"].set_value(effect_data.end_position)
            controls["frequency"].set_value(effect_data.frequency)
            controls["animated"].setChecked(effect_data.animated)
            controls["curve"].setCurrentIndex(
                max(0, controls["curve"].findData(effect_data.animation_curve))
            )
            controls["animation_speed"].set_value(effect_data.animation_speed)
            controls["vibration_enabled"].setChecked(effect_data.vibration_enabled)
            controls["vibration_intensity"].set_value(effect_data.vibration_intensity)
            controls["vibration_frequency"].set_value(effect_data.vibration_frequency)
            controls["vibration_start"].set_value(effect_data.vibration_start_position)
            controls["vibration_end"].set_value(effect_data.vibration_end_position)
            self._update_effect_controls(trigger)
        self._loading = False
        self._load_curve()

    def _curve_side(self) -> str:
        return str(self.curve_trigger.currentData() or "right")

    def _load_curve(self, *_args: Any) -> None:
        engine = self.window.trigger_engine
        profile_id = self.profile.currentData()
        profile = engine.get_profile(profile_id) if engine and profile_id else None
        if not profile:
            return
        side = self._curve_side()
        effect = profile.left_trigger if side == "left" else profile.right_trigger
        points = (
            effect.custom_params.get("sections") if isinstance(effect.custom_params, dict) else None
        )
        self.curve_editor.set_points(points or TriggerCurveEditor.DEFAULT_POINTS)
        self._update_curve_zones()

    def _update_curve_zones(self) -> None:
        engine = self.window.trigger_engine
        if not engine:
            return
        strengths = engine.get_section_zone_strengths(self.curve_editor.get_points())
        self.curve_zones.setText(
            "Fuerza real por zona 0–9 (escala interna 0–8): "
            + " · ".join(str(value) for value in strengths)
        )

    def _curve_changed(self, points: Any) -> None:
        if self._loading:
            return
        from src.trigger_engine import TriggerEffectType

        engine = self.window.trigger_engine
        profile_id = self.profile.currentData()
        profile = engine.get_profile(profile_id) if engine and profile_id else None
        if not profile:
            return
        side = self._curve_side()
        effect = profile.left_trigger if side == "left" else profile.right_trigger
        effect.name = "Curva personalizada"
        effect.effect_type = TriggerEffectType.SECTIONS
        effect.custom_params = dict(effect.custom_params or {})
        effect.custom_params["sections"] = [list(point) for point in points]
        if self.link_triggers.isChecked():
            from src.trigger_engine import TriggerEffect

            profile.left_trigger = TriggerEffect.from_dict(effect.to_dict())
            profile.right_trigger = TriggerEffect.from_dict(effect.to_dict())
        self._loading = True
        controls = self.controls[side]
        controls["effect"].setCurrentIndex(
            max(0, controls["effect"].findData(TriggerEffectType.SECTIONS.value))
        )
        self._loading = False
        self._update_curve_zones()
        self._persist()
        if engine.get_current_profile() == profile_id:
            self._reapply_timer.start(80)

    def _reset_curve(self) -> None:
        self.curve_editor.set_points(TriggerCurveEditor.DEFAULT_POINTS)
        self._curve_changed(self.curve_editor.get_points())
        self.window.toast("Curva de gatillo restablecida")

    def save(self, *_args: Any) -> None:
        if self._loading or not self.window.trigger_engine:
            return
        from src.trigger_engine import TriggerEffectType

        profile_id = self.profile.currentData()
        profile = self.window.trigger_engine.get_profile(profile_id)
        if not profile:
            return
        for trigger, controls in self.controls.items():
            effect = profile.left_trigger if trigger == "left" else profile.right_trigger
            effect.effect_type = TriggerEffectType(controls["effect"].currentData())
            effect.intensity = int(controls["intensity"].spin.value())
            effect.start_position = int(controls["start"].spin.value())
            effect.end_position = max(effect.start_position, int(controls["end"].spin.value()))
            controls["end"].set_value(effect.end_position)
            effect.frequency = int(controls["frequency"].spin.value())
            effect.animated = controls["animated"].isChecked()
            effect.animation_curve = controls["curve"].currentData()
            effect.animation_speed = float(controls["animation_speed"].spin.value())
            effect.vibration_enabled = controls["vibration_enabled"].isChecked()
            effect.vibration_intensity = int(controls["vibration_intensity"].spin.value())
            effect.vibration_frequency = int(controls["vibration_frequency"].spin.value())
            effect.vibration_start_position = int(controls["vibration_start"].spin.value())
            effect.vibration_end_position = max(
                effect.vibration_start_position,
                int(controls["vibration_end"].spin.value()),
            )
            controls["vibration_end"].set_value(effect.vibration_end_position)
            self._update_effect_controls(trigger)
        if self.link_triggers.isChecked():
            from src.trigger_engine import TriggerEffect
            profile.right_trigger = TriggerEffect.from_dict(profile.left_trigger.to_dict())
        self._persist()
        if self.window.trigger_engine.get_current_profile() == profile_id:
            self._reapply_timer.start(120)

    def _persist(self) -> None:
        self._persist_timer.start(220)

    def _persist_now(self) -> None:
        manager = self.window.profile_manager
        engine = self.window.trigger_engine
        if manager and engine:
            manager.set_setting("profile_trigger_vibration", engine.export_vibration_overrides())
            manager.set_setting("profile_overrides", engine.export_profile_overrides())
            manager.set_custom_profiles(engine.export_custom_profiles_to_dict())
            self.window.request_config_save()

    def _reapply_active(self) -> None:
        profile_id = self.profile.currentData()
        if profile_id and self.window.trigger_engine.get_current_profile() == profile_id:
            self.window.apply_profile(profile_id, force=True)

    def test(self, trigger: str) -> None:
        engine = self.window.trigger_engine
        if engine and not engine.test_effect(trigger, duration=1.4):
            self.window.alert("Conecta el DualSense para probar el efecto")
