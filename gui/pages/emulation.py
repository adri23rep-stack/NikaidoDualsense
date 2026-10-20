"""Centro visual de Emulación e Integración de Nikaido."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..ui_common import (
    Any, C, Dict, QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QPushButton, QTabWidget, QTimer, QVBoxLayout, QWidget, Qt, button, card,
    configure_tabs, copy, label,
)
from ..components import ControllerVisual, KeyCaptureButton, ScrollPage, SliderRow

if TYPE_CHECKING:
    from ..main_window import NikaidoWindow

class EmulationPage(ScrollPage):
    MODE_INFO = (
        ("xbox", "⌘", "Xbox 360", "Máxima compatibilidad con juegos de Windows."),
        ("ps4", "◇", "DualShock 4", "Salida PlayStation con soporte de movimiento."),
        ("none", "○", "Sin emulación", "Usa solamente las funciones directas del DualSense."),
    )

    KEY_LABELS = {
        "left_up": "Stick izquierdo · arriba",
        "left_down": "Stick izquierdo · abajo",
        "left_left": "Stick izquierdo · izquierda",
        "left_right": "Stick izquierdo · derecha",
        "right_up": "Stick derecho · arriba",
        "right_down": "Stick derecho · abajo",
        "right_left": "Stick derecho · izquierda",
        "right_right": "Stick derecho · derecha",
        "cross": "Cruz / A",
        "circle": "Círculo / B",
        "square": "Cuadrado / X",
        "triangle": "Triángulo / Y",
        "L1": "L1 / LB",
        "R1": "R1 / RB",
        "L2_btn": "L2 / LT",
        "R2_btn": "R2 / RT",
        "L3": "L3",
        "R3": "R3",
        "options": "Options / Start",
        "create": "Create / Back",
        "ps": "PS / Guide",
        "touchpad": "Click touchpad",
        "dpad_up": "D-pad arriba",
        "dpad_down": "D-pad abajo",
        "dpad_left": "D-pad izquierda",
        "dpad_right": "D-pad derecha",
    }

    def __init__(self, window: "NikaidoWindow") -> None:
        super().__init__()
        from src.keyboard_gamepad import (
            KEYBOARD_GAMEPAD_PRESETS,
            sanitize_keyboard_gamepad_config,
        )

        self.window = window
        self._loading = False
        self._last_keybridge_mouse_escape_count = 0
        self._last_gyro_mouse_escape_count = 0
        self._keyboard_presets = KEYBOARD_GAMEPAD_PRESETS
        self._last_virtual_mode = "xbox"
        self._preview_override = ""
        pm = self.window.profile_manager
        engine = getattr(self.window, "keyboard_gamepad", None)
        stored = pm.get_setting("keyboard_gamepad", {}) if pm else {}
        self._keyboard_config = (
            engine.get_config() if engine else sanitize_keyboard_gamepad_config(stored)
        )
        self._mapping_buttons: Dict[str, KeyCaptureButton] = {}

        self.add_header(
            "Emulación e Integración",
            "Transforma tu DualSense, usa KeyBridge y controla toda la salida virtual desde un solo lugar.",
        )

        # El editor completo se conserva, pero queda plegado para que la página
        # principal sea limpia. Al abrirlo no se crea otro motor ni otra copia.
        self.keybridge_editor = self._build_keybridge_card()
        self.keybridge_editor.setVisible(False)

        workspace = QGridLayout()
        workspace.setSpacing(12)
        workspace.addWidget(self._build_mode_selector(), 0, 0)
        workspace.addWidget(self._build_controller_preview(), 0, 1)
        workspace.addWidget(self._build_current_options(), 0, 2)
        workspace.setColumnStretch(0, 25)
        workspace.setColumnStretch(1, 48)
        workspace.setColumnStretch(2, 31)
        self.layout.addLayout(workspace)

        self.layout.addWidget(self.keybridge_editor)
        self.layout.addWidget(self._build_status_strip())
        self.layout.addWidget(self._build_quick_tools())
        self.layout.addStretch()

        self.keybridge_timer = QTimer(self)
        self.keybridge_timer.setInterval(650)
        self.keybridge_timer.timeout.connect(self._refresh_runtime_status)
        self.keybridge_timer.start()
        self.refresh()

    def _build_mode_selector(self) -> QFrame:
        panel = card()
        panel.setMinimumWidth(232)
        root = QVBoxLayout(panel)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(9)
        root.addWidget(label("MODO DE SALIDA", "eyebrow"))
        help_text = label("Elige cómo te verá el juego.", "muted")
        help_text.setWordWrap(True)
        root.addWidget(help_text)

        self.mode_buttons: Dict[str, QPushButton] = {}
        modes = (
            ("none", "5", "DualSense nativo", "Sin control virtual; conserva las funciones directas."),
            ("ps4", "4", "DualShock 4", "Salida PlayStation con movimiento y touchpad virtual."),
            ("xbox", "X", "Xbox 360", "Compatibilidad máxima con juegos de Windows."),
        )
        for mode, icon, title, description in modes:
            control = QPushButton(f"{icon}    {title}\n      {description}")
            control.setCheckable(True)
            control.setCursor(Qt.CursorShape.PointingHandCursor)
            control.setMinimumHeight(82)
            control.setProperty("emulationModeCard", True)
            control.setStyleSheet(
                "QPushButton{padding:12px;text-align:left;border-radius:12px;"
                f"border:1px solid {C['border']};background:{C['panel2']};color:{C['text']};font-weight:650;}}"
                f"QPushButton:hover{{border-color:{C['cyan']};background:{C['hover']};}}"
                f"QPushButton:checked{{border:2px solid {C['green']};background:#10251b;color:#eaffef;}}"
                "QPushButton:disabled{color:#667089;background:#0b1020;}"
            )
            control.clicked.connect(lambda _=False, selected=mode: self.set_emulation(selected))
            self.mode_buttons[mode] = control
            root.addWidget(control)

        self.keybridge_mode_button = QPushButton(
            "⌨    KeyBridge\n      Convierte teclado y mouse en un control virtual."
        )
        self.keybridge_mode_button.setCheckable(True)
        self.keybridge_mode_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.keybridge_mode_button.setMinimumHeight(82)
        self.keybridge_mode_button.setStyleSheet(
            "QPushButton{padding:12px;text-align:left;border-radius:12px;"
            f"border:1px solid #5d2b87;background:{C['panel2']};color:{C['text']};font-weight:650;}}"
            "QPushButton:hover{border-color:#c084fc;background:#1d1230;}"
            "QPushButton:checked{border:2px solid #c084fc;background:#25133a;color:#f3e8ff;}"
        )
        self.keybridge_mode_button.clicked.connect(self._activate_keybridge_from_card)
        root.addWidget(self.keybridge_mode_button)
        root.addStretch()
        return panel

    def _build_controller_preview(self) -> QFrame:
        panel = card()
        panel.setMinimumHeight(430)
        root = QVBoxLayout(panel)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(8)

        heading = QHBoxLayout()
        self.preview_title = label("Vista previa — DualSense nativo", "heading")
        heading.addWidget(self.preview_title)
        heading.addStretch()
        self.preview_badge = QLabel("●  Nativo")
        self.preview_badge.setStyleSheet(
            f"padding:6px 10px;border-radius:12px;background:{C['panel2']};"
            f"border:1px solid {C['border']};color:{C['muted']};font-weight:700;"
        )
        heading.addWidget(self.preview_badge)
        root.addLayout(heading)

        self.controller_preview = ControllerVisual()
        self.controller_preview.setMinimumHeight(300)
        root.addWidget(self.controller_preview, 1)

        self.mode_status = QLabel("Modo actual: Sin emulación")
        self.mode_status.setWordWrap(True)
        self.mode_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mode_status.setStyleSheet(
            f"padding:9px 12px;border-radius:10px;background:{C['panel2']};"
            f"border:1px solid {C['border']};color:{C['muted']};"
        )
        root.addWidget(self.mode_status)
        return panel

    def _build_current_options(self) -> QFrame:
        column = QFrame()
        column.setStyleSheet("background:transparent;border:none;")
        root = QVBoxLayout(column)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        panel = card()
        box = QVBoxLayout(panel)
        box.setContentsMargins(15, 14, 15, 14)
        box.setSpacing(9)
        box.addWidget(label("OPCIONES DEL MODO ACTUAL", "eyebrow"))

        self.emulation_enabled_toggle = QCheckBox("Activar emulación")
        self.emulation_enabled_toggle.toggled.connect(self._toggle_emulation)
        box.addWidget(self.emulation_enabled_toggle)

        reconnect_row = QHBoxLayout()
        reconnect_row.addWidget(label("Reconectar control", "muted"))
        reconnect_row.addStretch()
        reconnect_row.addWidget(button("Reconectar", self._reconnect_controller))
        box.addLayout(reconnect_row)

        hidhide_row = QHBoxLayout()
        hidhide_text = label("Ocultar control físico", "muted")
        hidhide_text.setToolTip("Abre Compatibilidad para configurar HidHide de forma segura")
        hidhide_row.addWidget(hidhide_text)
        hidhide_row.addStretch()
        hidhide_row.addWidget(button("Configurar", lambda: self.window.navigate("compatibility")))
        box.addLayout(hidhide_row)

        self.low_latency_toggle = QCheckBox("Modo baja latencia")
        self.low_latency_toggle.setChecked(True)
        self.low_latency_toggle.setEnabled(False)
        self.low_latency_toggle.setToolTip("La bomba HID de baja latencia se administra automáticamente")
        box.addWidget(self.low_latency_toggle)

        self.feedback_strength = SliderRow("Vibración", 0.0, 1.5, 1.0, decimals=2)
        self.feedback_strength.changed.connect(self._set_feedback_strength)
        box.addWidget(self.feedback_strength)

        self.touchpad_toggle = QCheckBox("Usar touchpad como mouse")
        self.touchpad_toggle.toggled.connect(self.set_touchpad_enabled)
        box.addWidget(self.touchpad_toggle)
        self.touch_sensitivity = SliderRow("Sensibilidad", 0.5, 8.0, 2.5, decimals=1)
        self.touch_sensitivity.changed.connect(self.set_touchpad_sensitivity)
        box.addWidget(self.touch_sensitivity)
        self.touch_status = label("Disponible en Windows", "muted")
        box.addWidget(self.touch_status)

        self.gyro_toggle = QCheckBox("Activar giroscopio")
        self.gyro_toggle.toggled.connect(self.set_gyro_enabled)
        box.addWidget(self.gyro_toggle)
        self.mouse_gyro_toggle = QCheckBox("Mouse → giroscopio virtual")
        self.mouse_gyro_toggle.toggled.connect(self.set_mouse_gyro_enabled)
        box.addWidget(self.mouse_gyro_toggle)
        self.gyro_status = label("Giroscopio desactivado", "muted")
        self.gyro_status.setWordWrap(True)
        box.addWidget(self.gyro_status)
        root.addWidget(panel)

        summary = card()
        summary_box = QVBoxLayout(summary)
        summary_box.setContentsMargins(15, 13, 15, 13)
        summary_box.setSpacing(8)
        title_row = QHBoxLayout()
        key_title = QLabel("KeyBridge")
        key_title.setStyleSheet("font-size:15px;font-weight:750;color:#d8b4fe")
        title_row.addWidget(key_title)
        title_row.addStretch()
        self.keybridge_quick_toggle = QCheckBox("Activo")
        self.keybridge_quick_toggle.toggled.connect(self.set_keybridge_enabled)
        title_row.addWidget(self.keybridge_quick_toggle)
        summary_box.addLayout(title_row)
        self.keybridge_summary_status = label("Desactivado", "muted")
        self.keybridge_summary_status.setWordWrap(True)
        summary_box.addWidget(self.keybridge_summary_status)
        self.keybridge_summary_details = QLabel("Perfil: —   ·   Mouse: —")
        self.keybridge_summary_details.setStyleSheet(f"color:{C['muted']};font-size:11px")
        self.keybridge_summary_details.setWordWrap(True)
        summary_box.addWidget(self.keybridge_summary_details)
        summary_box.addWidget(button("Abrir editor de KeyBridge", self._toggle_keybridge_editor, primary=True))
        root.addWidget(summary)
        root.addStretch()
        return column

    def _build_status_strip(self) -> QFrame:
        panel = card()
        root = QVBoxLayout(panel)
        root.setContentsMargins(14, 12, 14, 14)
        root.setSpacing(9)
        root.addWidget(label("ESTADO", "eyebrow"))
        grid = QGridLayout()
        grid.setSpacing(8)
        self.status_physical = self._status_tile(grid, 0, "Control físico", "Buscando…")
        self.status_output = self._status_tile(grid, 1, "Modo actual", "Nativo")
        self.status_virtual = self._status_tile(grid, 2, "Dispositivo virtual", "Inactivo")
        self.status_latency = self._status_tile(grid, 3, "Latencia interna", "—")
        self.status_connection = self._status_tile(grid, 4, "Conexión", "—")
        self.status_profile = self._status_tile(grid, 5, "Perfil activo", "—")
        self.status_battery = self._status_tile(grid, 6, "Batería", "—")
        for index in range(7):
            grid.setColumnStretch(index, 1)
        root.addLayout(grid)
        return panel

    @staticmethod
    def _status_tile(layout: QGridLayout, column: int, title: str, value: str) -> QLabel:
        tile = card(sub=True)
        box = QVBoxLayout(tile)
        box.setContentsMargins(10, 8, 10, 8)
        box.setSpacing(2)
        box.addWidget(label(title, "muted"))
        value_label = QLabel(value)
        value_label.setWordWrap(True)
        value_label.setStyleSheet("font-weight:750;font-size:12px")
        box.addWidget(value_label)
        layout.addWidget(tile, 0, column)
        return value_label

    def _build_quick_tools(self) -> QFrame:
        panel = card()
        root = QVBoxLayout(panel)
        root.setContentsMargins(14, 12, 14, 14)
        root.setSpacing(9)
        root.addWidget(label("HERRAMIENTAS RÁPIDAS", "eyebrow"))
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(button("Probar entrada", self._test_input))
        row.addWidget(button("Probar vibración", self._test_vibration))
        row.addWidget(button("Reset virtual", self._reset_virtual))
        row.addStretch()
        row.addWidget(button("Modo pánico", self._panic_mode, danger=True))
        root.addLayout(row)
        return panel

    def _toggle_keybridge_editor(self) -> None:
        visible = not self.keybridge_editor.isVisible()
        self.keybridge_editor.setVisible(visible)
        self.window.toast(
            "Editor de KeyBridge abierto" if visible else "Editor de KeyBridge plegado"
        )

    def _activate_keybridge_from_card(self) -> None:
        self._preview_override = "keybridge"
        if not self._keybridge_running():
            self.keybridge_toggle.setChecked(True)
        else:
            self._toggle_keybridge_editor()
        self._refresh_hub_visuals()

    def _toggle_emulation(self, enabled: bool) -> None:
        if self._loading:
            return
        if enabled:
            target = self._last_virtual_mode if self._last_virtual_mode in ("xbox", "ps4") else "xbox"
            self.set_emulation(target)
        else:
            self.set_emulation("none")

    def _reconnect_controller(self) -> None:
        manager = self.window.connection_manager
        if not manager:
            self.window.toast("El gestor del control no está disponible", "error")
            return
        manager.disconnect()
        QTimer.singleShot(350, manager.request_connect)
        self.window.toast("Reconectando DualSense…")

    def _set_feedback_strength(self, value: float) -> None:
        if self._loading:
            return
        bridge = self.window.virtual_feedback_bridge
        pm = self.window.profile_manager
        config = bridge.get_config() if bridge else (pm.get_setting("virtual_feedback", {}) if pm else {})
        config = dict(config or {})
        config["strength"] = max(0.0, min(1.5, float(value)))
        if bridge:
            config = bridge.apply_config(config)
        if pm:
            pm.set_setting("virtual_feedback", config)
            self.window.request_config_save()

    def _test_input(self) -> None:
        self._preview_override = self._preview_override or self._current_mode()
        self.controller_preview.set_light_preview("#43d7ef", "#7b3ff2", "pulse")
        self.window.toast("Mueve sticks y botones: la vista previa está escuchando", "success")
        QTimer.singleShot(1400, self._refresh_hub_visuals)

    def _test_vibration(self) -> None:
        manager = self.window.connection_manager
        ok = bool(manager and manager.start_rumble_test(145, 205, duration_ms=850))
        self.window.toast(
            "Prueba de vibración iniciada" if ok else "No se pudo probar la vibración",
            "success" if ok else "error",
        )

    def _reset_virtual(self) -> None:
        engine = self._keybridge_engine()
        if engine and engine.is_running():
            config = engine.get_config()
            engine.stop()
            QTimer.singleShot(320, lambda saved=config: self._restore_keybridge_after_reset(saved))
            self.window.toast("Reiniciando salida virtual de KeyBridge…")
            return
        mode = self._current_mode()
        if mode == "none":
            self.window.toast("No hay un dispositivo virtual activo")
            return
        self.set_emulation("none")
        QTimer.singleShot(320, lambda selected=mode: self.set_emulation(selected))
        self.window.toast("Reiniciando dispositivo virtual…")

    def _restore_keybridge_after_reset(self, config: Dict[str, Any]) -> None:
        engine = self._keybridge_engine()
        if not engine:
            return
        engine.apply_config(config, restart=False)
        engine.set_enabled(True)
        self._keyboard_config = engine.get_config()
        self.refresh()

    def _panic_mode(self) -> None:
        from src.emulator import EmulationMode

        engine = self._keybridge_engine()
        if engine:
            engine.stop()
        manager = self.window.connection_manager
        if manager:
            manager.stop_rumble_test()
            manager.set_emulation_mode(EmulationMode.NONE)
        if self.window.touchpad_mouse:
            self.window.touchpad_mouse.set_enabled(False)
        if self.window.gyro_engine:
            self.window.gyro_engine.update_config(
                enabled=False, mode="disabled", mouse_to_gyro_enabled=False
            )
        pm = self.window.profile_manager
        if pm:
            pm.set_setting("touchpad_mouse.enabled", False)
            config = dict(self._keyboard_config)
            config["enabled"] = False
            pm.set_setting("keyboard_gamepad", config)
            self.window.request_config_save()
        self.window.toast("Modo pánico: salidas virtuales y movimiento desactivados", "error", 4200)
        self.refresh()

    def _refresh_runtime_status(self) -> None:
        if not self.isVisible():
            return
        self.refresh_keybridge_status()
        self._refresh_hub_visuals()

    def _refresh_hub_visuals(self) -> None:
        manager = self.window.connection_manager
        state = manager.state if manager else None
        mode = self._current_mode()
        keybridge_running = self._keybridge_running()
        if mode in ("xbox", "ps4") and not keybridge_running:
            self._last_virtual_mode = mode
        display_mode = str(self._keyboard_config.get("mode", "xbox")) if keybridge_running else mode
        names = {"xbox": "Xbox 360", "ps4": "DualShock 4", "none": "DualSense nativo"}
        title = "KeyBridge" if keybridge_running else names.get(display_mode, display_mode)

        old_loading = self._loading
        self._loading = True
        try:
            self.controller_preview.set_state(state)
            self.controller_preview.set_emulation_mode(display_mode, keybridge=keybridge_running)
            self.preview_title.setText(f"Vista previa — {title}")
            active = keybridge_running or mode != "none"
            self.preview_badge.setText("●  Emulación activa" if active else "●  DualSense nativo")
            badge_color = "#72f08b" if active else C["muted"]
            self.preview_badge.setStyleSheet(
                f"padding:6px 10px;border-radius:12px;background:{C['panel2']};"
                f"border:1px solid {C['border']};color:{badge_color};font-weight:700;"
            )
            self.emulation_enabled_toggle.setChecked(mode != "none" and not keybridge_running)
            self.keybridge_quick_toggle.setChecked(keybridge_running)
            self.keybridge_mode_button.setChecked(keybridge_running)

            bridge = self.window.virtual_feedback_bridge
            feedback = bridge.get_config() if bridge else (
                self.window.profile_manager.get_setting("virtual_feedback", {})
                if self.window.profile_manager else {}
            )
            self.feedback_strength.set_value(float((feedback or {}).get("strength", 1.0)))
        finally:
            self._loading = old_loading

        connected = bool(state and state.connected)
        connection = getattr(getattr(state, "connection_type", None), "value", "—") if state else "—"
        battery_valid = bool(state and getattr(state, "battery_valid", False))
        battery = f"{int(state.battery_level)}%" if battery_valid else "—"
        diagnostics = manager.get_diagnostics_snapshot() if manager else {}
        latency = diagnostics.get("snapshot_to_virtual_avg_ms")
        latency_text = f"{float(latency):.2f} ms" if isinstance(latency, (int, float)) and latency >= 0 else "—"
        profile_id = self.window.profile_manager.get_active_profile() if self.window.profile_manager else "—"
        profile_names = dict(self.window.trigger_engine.get_profile_names()) if self.window.trigger_engine else {}
        profile_name = profile_names.get(profile_id, profile_id)

        self.status_physical.setText("DualSense conectado" if connected else "Sin conexión")
        self.status_physical.setStyleSheet(f"font-weight:750;color:{C['green'] if connected else C['muted']}")
        self.status_output.setText(title)
        self.status_virtual.setText("Activo" if keybridge_running or mode != "none" else "Inactivo")
        self.status_latency.setText(latency_text)
        self.status_connection.setText(str(connection).upper())
        self.status_profile.setText(str(profile_name or "—"))
        self.status_battery.setText(battery)

        kb_mapping = self._keyboard_config.get("mapping", {})
        mapped_count = sum(1 for value in kb_mapping.values() if str(value or "").strip()) if isinstance(kb_mapping, dict) else 0
        mouse_state = "Activado" if self._keyboard_config.get("mouse_stick_enabled") else "Desactivado"
        self.keybridge_summary_status.setText(
            f"●  {'Activo' if keybridge_running else 'Desactivado'} · salida {names.get(str(self._keyboard_config.get('mode', 'xbox')), 'Xbox 360')}"
        )
        self.keybridge_summary_status.setStyleSheet(
            f"color:{'#c084fc' if keybridge_running else C['muted']};font-weight:700"
        )
        self.keybridge_summary_details.setText(
            f"Perfil: {profile_name or '—'}   ·   Teclas mapeadas: {mapped_count}   ·   Mouse: {mouse_state}"
        )

    def _build_keybridge_card(self) -> QFrame:
        panel = card()
        root = QVBoxLayout(panel)
        root.setContentsMargins(16, 15, 16, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(label("NIKAIDO KEYBRIDGE", "eyebrow"))
        titles.addWidget(label("Teclado y mouse → control virtual", "heading"))
        description = label(
            "Juega como si tu teclado fuera un Xbox 360 o DualShock 4. No necesita un DualSense conectado.",
            "muted",
        )
        description.setWordWrap(True)
        titles.addWidget(description)
        header.addLayout(titles, 1)
        self.keybridge_toggle = QCheckBox("Activar KeyBridge")
        self.keybridge_toggle.setChecked(bool(self._keyboard_config["enabled"]))
        self.keybridge_toggle.toggled.connect(self.set_keybridge_enabled)
        header.addWidget(self.keybridge_toggle, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        toolbar.addWidget(label("Salida", "muted"))
        self.keybridge_mode = QComboBox()
        self.keybridge_mode.addItem("Xbox 360 virtual", "xbox")
        self.keybridge_mode.addItem("DualShock 4 virtual", "ps4")
        self.keybridge_mode.setCurrentIndex(
            max(0, self.keybridge_mode.findData(self._keyboard_config["mode"]))
        )
        self.keybridge_mode.currentIndexChanged.connect(self.set_keybridge_mode)
        toolbar.addWidget(self.keybridge_mode)
        toolbar.addSpacing(8)
        toolbar.addWidget(label("Preset", "muted"))
        self.keybridge_preset = QComboBox()
        for preset_id, preset in self._keyboard_presets.items():
            self.keybridge_preset.addItem(preset["name"], preset_id)
        toolbar.addWidget(self.keybridge_preset)
        toolbar.addWidget(button("Aplicar", self.apply_keybridge_preset))
        toolbar.addStretch()
        self.keybridge_pause = button("Pausar · F8", self.toggle_keybridge_pause)
        toolbar.addWidget(self.keybridge_pause)
        root.addLayout(toolbar)

        self.keybridge_status = QLabel("KeyBridge desactivado")
        self.keybridge_status.setWordWrap(True)
        self.keybridge_status.setProperty("muted", True)
        root.addWidget(self.keybridge_status)

        tabs = QTabWidget()
        configure_tabs(tabs)
        tabs.addTab(self._build_keybridge_movement_tab(), "Movimiento")
        tabs.addTab(self._build_keybridge_buttons_tab(), "Botones")
        tabs.addTab(self._build_keybridge_mouse_tab(), "Mouse y respuesta")
        root.addWidget(tabs)

        note = label(
            "Al activarlo por primera vez tendrás 5 segundos para abrir tu juego. Después Ctrl + M libera o reactiva el mouse al instante sin apagar KeyBridge; F8 pausa o reanuda toda la salida. Mientras Nikaido tiene el foco, las teclas se ignoran para que puedas editar.",
            "muted",
        )
        note.setWordWrap(True)
        root.addWidget(note)
        return panel

    def _mapping_control(self, key: str) -> KeyCaptureButton:
        control = KeyCaptureButton(self._keyboard_config["mapping"].get(key, ""))
        control.setAccessibleName(self.KEY_LABELS.get(key, key))
        control.binding_changed.connect(
            lambda value, mapping_key=key: self.set_keybridge_mapping(mapping_key, value)
        )
        self._mapping_buttons[key] = control
        return control

    def _add_mapping_row(
        self,
        layout: QGridLayout,
        row: int,
        key: str,
        *,
        column: int = 0,
    ) -> None:
        text = QLabel(self.KEY_LABELS.get(key, key))
        text.setWordWrap(True)
        layout.addWidget(text, row, column * 2)
        layout.addWidget(self._mapping_control(key), row, column * 2 + 1)

    def _build_keybridge_movement_tab(self) -> QWidget:
        body = QWidget()
        root = QHBoxLayout(body)
        root.setContentsMargins(8, 10, 8, 8)
        root.setSpacing(12)
        groups = (
            ("STICK IZQUIERDO", ("left_up", "left_down", "left_left", "left_right")),
            ("STICK DERECHO", ("right_up", "right_down", "right_left", "right_right")),
            ("D-PAD", ("dpad_up", "dpad_down", "dpad_left", "dpad_right")),
        )
        for title, keys in groups:
            group = card(sub=True)
            box = QVBoxLayout(group)
            box.setContentsMargins(12, 11, 12, 11)
            box.addWidget(label(title, "eyebrow"))
            grid = QGridLayout()
            grid.setSpacing(8)
            for row, key in enumerate(keys):
                self._add_mapping_row(grid, row, key)
            grid.setColumnStretch(0, 1)
            box.addLayout(grid)
            box.addStretch()
            root.addWidget(group, 1)
        return body

    def _build_keybridge_buttons_tab(self) -> QWidget:
        body = QWidget()
        grid = QGridLayout(body)
        grid.setContentsMargins(8, 10, 8, 8)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)
        keys = (
            "cross", "circle", "square", "triangle",
            "L1", "R1", "L2_btn", "R2_btn",
            "L3", "R3", "options", "create",
            "ps", "touchpad",
        )
        half = (len(keys) + 1) // 2
        for index, key in enumerate(keys):
            column = 0 if index < half else 1
            row = index if column == 0 else index - half
            self._add_mapping_row(grid, row, key, column=column)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(2, 1)
        return body

    def _build_keybridge_mouse_tab(self) -> QWidget:
        body = QWidget()
        root = QGridLayout(body)
        root.setContentsMargins(8, 10, 8, 8)
        root.setSpacing(12)

        mouse = card(sub=True)
        mouse_box = QVBoxLayout(mouse)
        mouse_box.addWidget(label("MOUSE → STICK DERECHO", "eyebrow"))
        self.keybridge_mouse = QCheckBox("Usar movimiento del mouse para apuntar")
        self.keybridge_mouse.setChecked(bool(self._keyboard_config["mouse_stick_enabled"]))
        self.keybridge_mouse.toggled.connect(self._keybridge_option_changed)
        mouse_box.addWidget(self.keybridge_mouse)
        self.keybridge_mouse_sens = SliderRow(
            "Sensibilidad", 0.002, 0.30,
            float(self._keyboard_config["mouse_sensitivity"]), decimals=3,
        )
        self.keybridge_mouse_sens.changed.connect(self._keybridge_option_changed)
        mouse_box.addWidget(self.keybridge_mouse_sens)
        self.keybridge_smoothing = SliderRow(
            "Suavizado", 0, 90,
            float(self._keyboard_config["mouse_smoothing"]), decimals=0, suffix=" %",
        )
        self.keybridge_smoothing.changed.connect(self._keybridge_option_changed)
        mouse_box.addWidget(self.keybridge_smoothing)
        self.keybridge_decay = SliderRow(
            "Retorno al centro", 10, 300,
            float(self._keyboard_config["mouse_decay_ms"]), decimals=0, suffix=" ms",
        )
        self.keybridge_decay.changed.connect(self._keybridge_option_changed)
        mouse_box.addWidget(self.keybridge_decay)
        self.keybridge_invert_x = QCheckBox("Invertir mouse horizontal")
        self.keybridge_invert_y = QCheckBox("Invertir mouse vertical")
        self.keybridge_invert_x.setChecked(bool(self._keyboard_config["mouse_invert_x"]))
        self.keybridge_invert_y.setChecked(bool(self._keyboard_config["mouse_invert_y"]))
        self.keybridge_invert_x.toggled.connect(self._keybridge_option_changed)
        self.keybridge_invert_y.toggled.connect(self._keybridge_option_changed)
        mouse_box.addWidget(self.keybridge_invert_x)
        mouse_box.addWidget(self.keybridge_invert_y)
        mouse_escape = label(
            "La primera activación muestra una cuenta de 5 segundos. Después el cursor se centra automáticamente. Ctrl + M lo libera o lo reactiva al instante.",
            "muted",
        )
        mouse_escape.setWordWrap(True)
        mouse_box.addWidget(mouse_escape)
        root.addWidget(mouse, 0, 0)

        response = card(sub=True)
        response_box = QVBoxLayout(response)
        response_box.addWidget(label("RESPUESTA DIGITAL", "eyebrow"))
        self.keybridge_ramp = SliderRow(
            "Entrada de sticks", 0, 500,
            float(self._keyboard_config["stick_ramp_ms"]), decimals=0, suffix=" ms",
        )
        self.keybridge_release = SliderRow(
            "Retorno de sticks", 0, 500,
            float(self._keyboard_config["stick_release_ms"]), decimals=0, suffix=" ms",
        )
        self.keybridge_trigger_ramp = SliderRow(
            "Entrada de gatillos", 0, 500,
            float(self._keyboard_config["trigger_ramp_ms"]), decimals=0, suffix=" ms",
        )
        for slider in (self.keybridge_ramp, self.keybridge_release, self.keybridge_trigger_ramp):
            slider.changed.connect(self._keybridge_option_changed)
            response_box.addWidget(slider)
        self.keybridge_diagonals = QCheckBox("Normalizar diagonales para evitar más de 100 %")
        self.keybridge_diagonals.setChecked(bool(self._keyboard_config["normalize_diagonals"]))
        self.keybridge_diagonals.toggled.connect(self._keybridge_option_changed)
        response_box.addWidget(self.keybridge_diagonals)
        self.keybridge_ignore_focus = QCheckBox("Ignorar teclas y clics con Nikaido al frente (el movimiento sigue activo)")
        self.keybridge_ignore_focus.setChecked(bool(self._keyboard_config["ignore_when_nikaido_focused"]))
        self.keybridge_ignore_focus.toggled.connect(self._keybridge_option_changed)
        response_box.addWidget(self.keybridge_ignore_focus)
        root.addWidget(response, 0, 1)
        root.setColumnStretch(0, 1)
        root.setColumnStretch(1, 1)
        return body

    def _current_mode(self) -> str:
        manager = self.window.connection_manager
        emulator = getattr(manager, "emulator", None) if manager else None
        value = getattr(getattr(emulator, "mode", None), "value", "none")
        return str(value or "none")

    def _keybridge_engine(self):
        return getattr(self.window, "keyboard_gamepad", None)

    def _keybridge_running(self) -> bool:
        engine = self._keybridge_engine()
        return bool(engine and engine.is_running())

    def _save_keyboard_config(self, *, apply_engine: bool = True) -> bool:
        from src.keyboard_gamepad import sanitize_keyboard_gamepad_config

        self._keyboard_config = sanitize_keyboard_gamepad_config(self._keyboard_config)
        engine = self._keybridge_engine()
        ok = True
        if apply_engine and engine:
            ok = bool(engine.apply_config(self._keyboard_config))
            self._keyboard_config = engine.get_config()
        pm = self.window.profile_manager
        if pm:
            pm.set_setting("keyboard_gamepad", self._keyboard_config)
            self.window.request_config_save()
        return ok

    def refresh(self) -> None:
        self._loading = True
        try:
            mode = self._current_mode()
            keybridge_running = self._keybridge_running()
            names = {"xbox": "Xbox 360", "ps4": "DualShock 4", "none": "Sin emulación"}
            if keybridge_running:
                self.mode_status.setText(
                    f"Salida reservada por KeyBridge · {names.get(mode, mode)}"
                )
            else:
                self.mode_status.setText(f"Modo actual: {names.get(mode, mode)}")
            for key, widget in self.mode_buttons.items():
                widget.setChecked(not keybridge_running and key == mode)
                widget.setEnabled(not keybridge_running)

            pm = self.window.profile_manager
            touch_enabled = bool(pm and pm.get_setting("touchpad_mouse.enabled", False))
            sensitivity = float(pm.get_setting("touchpad_mouse.sensitivity", 2.5)) if pm else 2.5
            self.touchpad_toggle.setChecked(touch_enabled)
            self.touch_sensitivity.set_value(sensitivity)
            available = bool(
                self.window.touchpad_mouse
                and self.window.touchpad_mouse.is_available()
            )
            self.touch_status.setText(
                "Listo para usarse" if available else "Requiere Windows y pywin32"
            )
            self.touchpad_toggle.setEnabled(available)

            config = self.window.gyro_engine.get_config() if self.window.gyro_engine else None
            enabled = bool(config and config.enabled and config.mode != "disabled")
            self.gyro_toggle.setChecked(enabled)
            mouse_gyro = bool(config and config.mouse_to_gyro_enabled)
            self.mouse_gyro_toggle.setChecked(mouse_gyro)
            emulator = getattr(self.window.connection_manager, "emulator", None)
            mouse_capture = (
                getattr(emulator, "get_mouse_to_gyro_status", lambda: {})()
                if emulator else {}
            )
            mouse_available = bool(
                emulator
                and getattr(emulator, "supports_mouse_to_gyro", lambda: False)()
                and not keybridge_running
            )
            self.mouse_gyro_toggle.setEnabled(mouse_available)
            if mouse_capture.get("activation_pending"):
                remaining = max(
                    1,
                    int(float(mouse_capture.get("activation_remaining_seconds", 0.0) or 0.0) + 0.999),
                )
                suffix = f" · Mouse → gyro en {remaining} s"
            elif mouse_capture.get("running"):
                suffix = " · Mouse → gyro activo"
            elif mouse_capture.get("hotkey_paused"):
                suffix = " · Mouse liberado · Ctrl + M para activar"
            else:
                suffix = " · Mouse → gyro armado" if mouse_gyro else ""
            self.gyro_status.setText(
                f"Activo · modo {config.mode}{suffix}" if enabled else "Giroscopio desactivado"
            )

            engine = self._keybridge_engine()
            if engine:
                self._keyboard_config = engine.get_config()
            self.keybridge_toggle.setChecked(bool(self._keyboard_config["enabled"] and keybridge_running))
            self.keybridge_mode.setCurrentIndex(
                max(0, self.keybridge_mode.findData(self._keyboard_config["mode"]))
            )
            for key, widget in self._mapping_buttons.items():
                widget.set_binding(self._keyboard_config["mapping"].get(key, ""))
            self.keybridge_mouse.setChecked(bool(self._keyboard_config["mouse_stick_enabled"]))
            self.keybridge_mouse_sens.set_value(float(self._keyboard_config["mouse_sensitivity"]))
            self.keybridge_smoothing.set_value(float(self._keyboard_config["mouse_smoothing"]))
            self.keybridge_decay.set_value(float(self._keyboard_config["mouse_decay_ms"]))
            self.keybridge_invert_x.setChecked(bool(self._keyboard_config["mouse_invert_x"]))
            self.keybridge_invert_y.setChecked(bool(self._keyboard_config["mouse_invert_y"]))
            self.keybridge_ramp.set_value(float(self._keyboard_config["stick_ramp_ms"]))
            self.keybridge_release.set_value(float(self._keyboard_config["stick_release_ms"]))
            self.keybridge_trigger_ramp.set_value(float(self._keyboard_config["trigger_ramp_ms"]))
            self.keybridge_diagonals.setChecked(bool(self._keyboard_config["normalize_diagonals"]))
            self.keybridge_ignore_focus.setChecked(bool(self._keyboard_config["ignore_when_nikaido_focused"]))
        finally:
            self._loading = False
        self.refresh_keybridge_status()
        self._refresh_hub_visuals()

    def refresh_keybridge_status(self) -> None:
        engine = self._keybridge_engine()
        if not engine:
            self.keybridge_status.setText("KeyBridge no está disponible en esta instalación")
            self.keybridge_pause.setEnabled(False)
            return
        status = engine.get_diagnostics_snapshot()
        engine_config = engine.get_config()
        if bool(engine_config.get("mouse_stick_enabled")) != bool(self._keyboard_config.get("mouse_stick_enabled")):
            self._keyboard_config = engine_config
            self._loading = True
            self.keybridge_mouse.setChecked(bool(engine_config.get("mouse_stick_enabled")))
            self._loading = False
            self._save_keyboard_config(apply_engine=False)
        keybridge_escape_count = int(status.get("mouse_emergency_stop_count", 0))
        if keybridge_escape_count > self._last_keybridge_mouse_escape_count:
            self._last_keybridge_mouse_escape_count = keybridge_escape_count
            action = str(status.get("mouse_last_toggle_action") or "")
            if action in ("arming", "enabled"):
                self.window.toast("Mouse → Stick activado al instante · Ctrl + M para liberarlo", "success")
            else:
                self.window.toast("Mouse → Stick apagado temporalmente · Ctrl + M para activarlo", "info")

        emulator = getattr(self.window.connection_manager, "emulator", None)
        gyro_capture = (
            getattr(emulator, "get_mouse_to_gyro_status", lambda: {})()
            if emulator else {}
        )
        gyro_escape_count = int(gyro_capture.get("emergency_stop_count", 0))
        if gyro_escape_count > self._last_gyro_mouse_escape_count:
            self._last_gyro_mouse_escape_count = gyro_escape_count
            if self.window.gyro_engine:
                config = self.window.gyro_engine.get_config()
                self._loading = True
                self.mouse_gyro_toggle.setChecked(bool(config.mouse_to_gyro_enabled))
                self._loading = False
            action = str(gyro_capture.get("last_toggle_action") or "")
            if action in ("arming", "enabled"):
                self.window.toast("Mouse → Gyro activado al instante · Ctrl + M para liberarlo", "success")
            else:
                self.window.toast("Mouse → Gyro apagado temporalmente · Ctrl + M para activarlo", "info")

        self.keybridge_pause.setEnabled(bool(status["running"]))
        self.keybridge_pause.setText(
            "Reanudar · F8" if status["suspended"] else "Pausar · F8"
        )
        if status["running"]:
            output = "Xbox 360" if status["mode"] == "xbox" else "DualShock 4"
            active = "Pausado" if status["suspended"] else "Activo"
            backend_names = {
                "raw_input": "Raw Input",
                "low_level_hook": "hook global",
                "cursor_poll": "sondeo",
            }
            mouse_pending = bool(status.get("mouse_activation_pending"))
            mouse_paused = bool(status.get("mouse_hotkey_paused"))
            mouse_failed = bool(
                status.get("mouse_enabled")
                and not status["mouse_running"]
                and not mouse_pending
                and not mouse_paused
            )
            if mouse_pending:
                remaining = max(1, int(float(status.get("mouse_activation_remaining_seconds", 0.0) or 0.0) + 0.999))
                mouse = f" · mouse → stick en {remaining} s"
            elif status["mouse_running"]:
                backend = backend_names.get(status.get("mouse_backend"), status.get("mouse_backend", "captura"))
                mouse = f" · mouse → stick ({backend})"
            elif mouse_paused:
                mouse = " · mouse liberado · Ctrl + M para activar"
            elif mouse_failed:
                mouse = f" · mouse sin captura: {status.get('mouse_error') or 'error desconocido'}"
            else:
                mouse = ""
            self.keybridge_status.setText(
                f"●  {active} · {output} · {status['poll_hz']} Hz{mouse}"
            )
            status_color = (
                C['red']
                if mouse_failed
                else C['yellow']
                if mouse_pending or mouse_paused or status['suspended']
                else C['green']
            )
            self.keybridge_status.setStyleSheet(f"color:{status_color}")
        elif not status["available"]:
            self.keybridge_status.setText("Disponible únicamente en Windows")
            self.keybridge_status.setStyleSheet(f"color:{C['muted']}")
        elif status["last_error"]:
            self.keybridge_status.setText(f"No se pudo iniciar: {status['last_error']}")
            self.keybridge_status.setStyleSheet(f"color:{C['red']}")
        else:
            self.keybridge_status.setText("KeyBridge desactivado · el DualSense conserva la salida virtual")
            self.keybridge_status.setStyleSheet(f"color:{C['muted']}")

    def set_emulation(self, mode: str) -> None:
        from src.emulator import EmulationMode

        engine = self._keybridge_engine()
        if engine and engine.is_running():
            engine.stop()
            self._keyboard_config = engine.get_config()
            self._keyboard_config["enabled"] = False
            self._save_keyboard_config(apply_engine=False)
            self.window.toast("KeyBridge desactivado para usar el DualSense físico")

        value = {
            "xbox": EmulationMode.XBOX,
            "ps4": EmulationMode.PS4,
            "none": EmulationMode.NONE,
        }[mode]
        manager = self.window.connection_manager
        if manager and hasattr(manager.emulator, "set_input_source"):
            manager.emulator.set_input_source("dualsense")
        ok = bool(manager and manager.set_emulation_mode(value))
        if mode == "none":
            message = "Emulación desactivada" if ok else "No se pudo desactivar"
        else:
            message = f"Emulación {mode.upper()} {'activa' if ok else 'no disponible'}"
        self.window.toast(message)
        self.refresh()

    def set_keybridge_enabled(self, enabled: bool) -> None:
        if self._loading:
            return
        engine = self._keybridge_engine()
        if not engine:
            self._loading = True
            self.keybridge_toggle.setChecked(False)
            self._loading = False
            self.window.alert("Nikaido KeyBridge no está disponible en esta instalación.")
            return
        self._keyboard_config["enabled"] = bool(enabled)
        self._keyboard_config["mode"] = str(self.keybridge_mode.currentData() or "xbox")
        engine.apply_config(self._keyboard_config, restart=False)
        ok = engine.set_enabled(bool(enabled))
        self._keyboard_config = engine.get_config()
        if enabled and not ok:
            self._keyboard_config["enabled"] = False
            self._loading = True
            self.keybridge_toggle.setChecked(False)
            self._loading = False
            self.window.alert(
                "No se pudo crear el control virtual de KeyBridge. "
                f"{engine.last_error or 'Comprueba ViGEm y vgamepad.'}"
            )
        else:
            self.window.toast(
                "Nikaido KeyBridge activo" if enabled else "Nikaido KeyBridge desactivado",
                "success" if enabled else "info",
            )
        self._save_keyboard_config(apply_engine=False)
        self.refresh()

    def set_keybridge_mode(self, _index: int = 0) -> None:
        if self._loading:
            return
        self._keyboard_config["mode"] = str(self.keybridge_mode.currentData() or "xbox")
        if not self._save_keyboard_config():
            self.window.toast("No se pudo cambiar la salida virtual", "error")
        self.refresh()

    def set_keybridge_mapping(self, key: str, value: str) -> None:
        if self._loading:
            return
        self._keyboard_config.setdefault("mapping", {})[key] = value
        self._save_keyboard_config()

    def _keybridge_option_changed(self, _value: Any = None) -> None:
        if self._loading:
            return
        self._keyboard_config.update(
            mouse_stick_enabled=self.keybridge_mouse.isChecked(),
            mouse_sensitivity=float(self.keybridge_mouse_sens.spin.value()),
            mouse_smoothing=round(self.keybridge_smoothing.spin.value()),
            mouse_decay_ms=round(self.keybridge_decay.spin.value()),
            mouse_invert_x=self.keybridge_invert_x.isChecked(),
            mouse_invert_y=self.keybridge_invert_y.isChecked(),
            stick_ramp_ms=round(self.keybridge_ramp.spin.value()),
            stick_release_ms=round(self.keybridge_release.spin.value()),
            trigger_ramp_ms=round(self.keybridge_trigger_ramp.spin.value()),
            normalize_diagonals=self.keybridge_diagonals.isChecked(),
            ignore_when_nikaido_focused=self.keybridge_ignore_focus.isChecked(),
        )
        self._save_keyboard_config()
        self.refresh_keybridge_status()

    def apply_keybridge_preset(self) -> None:
        preset_id = str(self.keybridge_preset.currentData() or "shooter")
        preset = self._keyboard_presets.get(preset_id)
        if not preset:
            return
        self._keyboard_config["mapping"] = copy.deepcopy(preset["mapping"])
        for key in (
            "mouse_stick_enabled", "mouse_sensitivity",
            "stick_ramp_ms", "stick_release_ms",
        ):
            if key in preset:
                self._keyboard_config[key] = preset[key]
        self._save_keyboard_config()
        self.refresh()
        self.window.toast(f"Preset {preset['name']} aplicado a KeyBridge", "success")

    def toggle_keybridge_pause(self) -> None:
        engine = self._keybridge_engine()
        if not engine or not engine.is_running():
            return
        suspended = engine.toggle_suspended()
        self.window.toast("KeyBridge pausado" if suspended else "KeyBridge reanudado")
        self.refresh_keybridge_status()

    def _save(self, key: str, value: Any) -> None:
        pm = self.window.profile_manager
        if pm:
            pm.set_setting(key, value)
            self.window.request_config_save()

    def set_touchpad_enabled(self, enabled: bool) -> None:
        if self._loading:
            return
        self._save("touchpad_mouse.enabled", bool(enabled))
        controller = self.window.touchpad_mouse
        if controller:
            controller.set_enabled(bool(enabled))
            actual = controller.is_enabled()
            if actual != bool(enabled):
                self._loading = True
                self.touchpad_toggle.setChecked(actual)
                self._loading = False
                self.window.alert("El touchpad como mouse requiere Windows y pywin32.")
                return
        self.window.toast(
            "Touchpad como mouse activado" if enabled else "Touchpad como mouse desactivado"
        )

    def set_touchpad_sensitivity(self, value: float) -> None:
        if self._loading:
            return
        self._save("touchpad_mouse.sensitivity", float(value))
        if self.window.touchpad_mouse:
            self.window.touchpad_mouse.set_sensitivity(value)

    def set_gyro_enabled(self, enabled: bool) -> None:
        if self._loading or not self.window.gyro_engine:
            return
        config = self.window.gyro_engine.get_config()
        changes: Dict[str, Any] = {"enabled": bool(enabled)}
        if enabled and config.mode == "disabled":
            changes["mode"] = "mouse"
        self.window.gyro_engine.update_config(**changes)
        self._persist_gyro()
        self.window.toast(
            "Giroscopio activado" if enabled else "Giroscopio desactivado"
        )
        self.refresh()

    def _persist_gyro(self) -> None:
        manager = self.window.profile_manager
        trigger = self.window.trigger_engine
        if manager and trigger:
            manager.set_setting("profile_gyro", trigger.export_gyro_overrides())
            manager.set_setting("profile_overrides", trigger.export_profile_overrides())
            manager.set_custom_profiles(trigger.export_custom_profiles_to_dict())
            self.window.request_config_save()

    def set_mouse_gyro_enabled(self, enabled: bool) -> None:
        if self._loading or not self.window.gyro_engine:
            return
        if enabled and self._keybridge_running():
            self._loading = True
            self.mouse_gyro_toggle.setChecked(False)
            self._loading = False
            self.window.alert(
                "Mouse → giroscopio y KeyBridge usan el movimiento global del mouse. "
                "Desactiva KeyBridge antes de activar esta función."
            )
            return
        if enabled:
            from src.emulator import EmulationMode

            manager = self.window.connection_manager
            needs_ps4 = self._current_mode() != "ps4"
            if not manager or (needs_ps4 and not manager.set_emulation_mode(EmulationMode.PS4)):
                self._loading = True
                self.mouse_gyro_toggle.setChecked(False)
                self._loading = False
                self.window.toast("No se pudo activar el DualShock 4 virtual", "error")
                return
            self.window.gyro_engine.update_config(
                enabled=True,
                mode="passthrough_ds4",
                mouse_to_gyro_enabled=True,
            )
            self.window.toast(
                "Mouse → giroscopio armado · se activa en 5 segundos · Ctrl + M alterna el mouse",
                "success",
                5200,
            )
        else:
            self.window.gyro_engine.update_config(mouse_to_gyro_enabled=False)
            self.window.toast("Mouse → giroscopio virtual desactivado")
        self._persist_gyro()
        gyro_page = getattr(self.window, "gyro_page", None)
        if gyro_page:
            gyro_page.load()
        self.refresh()
