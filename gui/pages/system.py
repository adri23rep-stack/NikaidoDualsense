"""AutoProfilesPage, CompatibilityPage, MonitorPage, EmulationPage, ToolsPage extraídos de la antigua interfaz monolítica."""

from __future__ import annotations

from typing import TYPE_CHECKING


from ..ui_common import (
    logging,
    Any,
    C,
    Callable,
    Dict,
    Path,
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
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
    copy,
    label,
    os,
    threading,
    time,
)
from ..components import ControllerVisual, KeyCaptureButton, LatencyGraph, ScrollPage, SliderRow

if TYPE_CHECKING:
    from ..main_window import NikaidoWindow

logger = logging.getLogger(__name__)

class AutoProfilesPage(ScrollPage):
    """Editor de perfiles automáticos por ventana, proceso y prioridad."""

    def __init__(self, window: "NikaidoWindow") -> None:
        super().__init__()
        self.window = window
        self._editing_rule_id = ""
        self._loading = False

        top = QHBoxLayout()
        top.addWidget(label("Perfiles automáticos", "title"))
        top.addStretch()
        self.enabled = QCheckBox("Activar cambios automáticos")
        self.enabled.toggled.connect(self.set_enabled)
        top.addWidget(self.enabled)
        top.addWidget(button("Revisar ahora", self.refresh_status))
        self.layout.addLayout(top)
        intro = label(
            "Nikaido puede detectar el juego que está al frente, aplicar su perfil y restaurar el perfil anterior al cerrarlo o cambiar de ventana.",
            "muted",
        )
        intro.setWordWrap(True)
        self.layout.addWidget(intro)

        editor = card()
        editor_box = QVBoxLayout(editor)
        editor_box.setContentsMargins(18, 16, 18, 18)
        editor_box.addWidget(label("NUEVA REGLA / EDITAR REGLA", "eyebrow"))
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.rule_name = QLineEdit()
        self.rule_name.setPlaceholderText("Ejemplo: Cyberpunk 2077")
        form.addRow("Nombre", self.rule_name)

        executable_row = QHBoxLayout()
        self.executable = QLineEdit()
        self.executable.setPlaceholderText("juego.exe")
        executable_row.addWidget(self.executable, 1)
        executable_row.addWidget(button("Buscar .exe", self.browse_executable))
        form.addRow("Ejecutable", executable_row)

        self.window_title = QLineEdit()
        self.window_title.setPlaceholderText("Opcional: texto dentro del título de la ventana")
        form.addRow("Título de ventana", self.window_title)

        self.profile = QComboBox()
        form.addRow("Perfil", self.profile)

        options = QHBoxLayout()
        self.priority = QSpinBox()
        self.priority.setRange(-100, 999)
        self.priority.setValue(0)
        self.priority.setToolTip("Las reglas con número mayor ganan cuando coinciden varias")
        options.addWidget(label("Prioridad", "muted"))
        options.addWidget(self.priority)
        self.foreground_only = QCheckBox("Solo cuando el juego esté al frente")
        self.foreground_only.setChecked(True)
        options.addWidget(self.foreground_only)
        options.addStretch()
        form.addRow("Comportamiento", options)

        delays = QHBoxLayout()
        self.enter_delay = QSpinBox()
        self.enter_delay.setRange(0, 10000)
        self.enter_delay.setValue(250)
        self.enter_delay.setSuffix(" ms")
        self.exit_delay = QSpinBox()
        self.exit_delay.setRange(0, 10000)
        self.exit_delay.setValue(500)
        self.exit_delay.setSuffix(" ms")
        delays.addWidget(label("Al entrar", "muted"))
        delays.addWidget(self.enter_delay)
        delays.addSpacing(16)
        delays.addWidget(label("Al salir", "muted"))
        delays.addWidget(self.exit_delay)
        delays.addStretch()
        form.addRow("Estabilidad", delays)
        editor_box.addLayout(form)

        editor_actions = QHBoxLayout()
        self.save_button = button("Guardar regla", self.save_rule, primary=True)
        editor_actions.addWidget(self.save_button)
        editor_actions.addWidget(button("Limpiar", self.clear_form))
        editor_actions.addStretch()
        editor_box.addLayout(editor_actions)
        self.layout.addWidget(editor)

        rules_panel = card()
        rules_box = QVBoxLayout(rules_panel)
        rules_box.setContentsMargins(18, 16, 18, 18)
        rules_header = QHBoxLayout()
        rules_header.addWidget(label("REGLAS GUARDADAS", "eyebrow"))
        rules_header.addStretch()
        rules_header.addWidget(button("Editar seleccionada", self.edit_selected))
        rules_header.addWidget(button("Eliminar", self.remove_selected, danger=True))
        rules_box.addLayout(rules_header)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(("Juego", "Ejecutable", "Perfil", "Prioridad", "Modo"))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.doubleClicked.connect(lambda _index: self.edit_selected())
        rules_box.addWidget(self.table)
        self.layout.addWidget(rules_panel)

        live = card()
        live_box = QVBoxLayout(live)
        live_box.setContentsMargins(18, 16, 18, 18)
        live_box.addWidget(label("ESTADO EN VIVO", "eyebrow"))
        self.live_status = label("Esperando información…", "muted")
        self.live_status.setWordWrap(True)
        live_box.addWidget(self.live_status)
        self.live_history = label("Sin cambios automáticos recientes", "muted")
        self.live_history.setWordWrap(True)
        live_box.addWidget(self.live_history)
        self.layout.addWidget(live)
        self.layout.addStretch()
        self.refresh()

    def _watcher(self):
        return self.window.game_profile_watcher

    def refresh_profiles(self) -> None:
        current = self.profile.currentData()
        self.profile.blockSignals(True)
        self.profile.clear()
        engine = self.window.trigger_engine
        if engine:
            for profile_id, name in engine.get_profile_names():
                self.profile.addItem(name, profile_id)
        if current:
            self.profile.setCurrentIndex(max(0, self.profile.findData(current)))
        self.profile.blockSignals(False)

    def browse_executable(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar juego", "", "Aplicaciones (*.exe);;Todos los archivos (*)"
        )
        if path:
            self.executable.setText(path)
            if not self.rule_name.text().strip():
                self.rule_name.setText(Path(path).stem)

    def set_enabled(self, enabled: bool) -> None:
        if self._loading:
            return
        watcher = self._watcher()
        if watcher:
            watcher.set_enabled(enabled)
        if self.window.profile_manager:
            self.window.profile_manager.set_setting("game_profiles_enabled", bool(enabled))
            self.window.request_config_save()
        self.refresh_status()

    def _persist_rules(self) -> None:
        watcher = self._watcher()
        if watcher and self.window.profile_manager:
            self.window.profile_manager.set_setting("game_profile_rules", watcher.get_rules())
            self.window.request_config_save()

    def save_rule(self) -> None:
        watcher = self._watcher()
        executable_text = self.executable.text().strip()
        profile_id = str(self.profile.currentData() or "")
        if not watcher or not executable_text or not profile_id:
            self.window.alert("Selecciona un ejecutable y un perfil")
            return
        payload = {
            "name": self.rule_name.text().strip() or Path(executable_text).stem,
            "executable": executable_text,
            "path": executable_text if ("\\" in executable_text or "/" in executable_text) else "",
            "window_title": self.window_title.text().strip(),
            "profile_id": profile_id,
            "priority": self.priority.value(),
            "foreground_only": self.foreground_only.isChecked(),
            "enter_delay_ms": self.enter_delay.value(),
            "exit_delay_ms": self.exit_delay.value(),
        }
        if self._editing_rule_id:
            payload["id"] = self._editing_rule_id
        try:
            watcher.add_rule(payload)
        except Exception as exc:
            self.window.alert(f"No se pudo guardar la regla: {exc}")
            return
        self._persist_rules()
        self.window.toast("Regla automática guardada")
        self.clear_form()
        self.refresh_rules()

    def selected_rule_id(self) -> str:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return ""
        item = self.table.item(rows[0].row(), 0)
        return str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""

    def edit_selected(self) -> None:
        rule_id = self.selected_rule_id()
        watcher = self._watcher()
        if not rule_id or not watcher:
            self.window.alert("Selecciona una regla")
            return
        rule = next((item for item in watcher.get_rules() if item.get("id") == rule_id), None)
        if not rule:
            return
        self._editing_rule_id = rule_id
        self.rule_name.setText(str(rule.get("name") or ""))
        self.executable.setText(str(rule.get("path") or rule.get("executable") or ""))
        self.window_title.setText(str(rule.get("window_title") or ""))
        self.profile.setCurrentIndex(max(0, self.profile.findData(rule.get("profile_id"))))
        self.priority.setValue(int(rule.get("priority", 0)))
        self.foreground_only.setChecked(bool(rule.get("foreground_only", True)))
        self.enter_delay.setValue(int(rule.get("enter_delay_ms", 250)))
        self.exit_delay.setValue(int(rule.get("exit_delay_ms", 500)))
        self.save_button.setText("Actualizar regla")
        self.verticalScrollBar().setValue(0)

    def remove_selected(self) -> None:
        rule_id = self.selected_rule_id()
        watcher = self._watcher()
        if not rule_id or not watcher:
            self.window.alert("Selecciona una regla")
            return
        answer = QMessageBox.question(
            self, "Eliminar regla", "¿Eliminar la regla automática seleccionada?"
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        watcher.remove_rule(rule_id)
        self._persist_rules()
        self.clear_form()
        self.refresh_rules()
        self.window.toast("Regla eliminada", "info")

    def clear_form(self) -> None:
        self._editing_rule_id = ""
        self.rule_name.clear()
        self.executable.clear()
        self.window_title.clear()
        self.priority.setValue(0)
        self.foreground_only.setChecked(True)
        self.enter_delay.setValue(250)
        self.exit_delay.setValue(500)
        self.save_button.setText("Guardar regla")

    def refresh_rules(self) -> None:
        watcher = self._watcher()
        rules = watcher.get_rules() if watcher else []
        profile_names = dict(self.window.trigger_engine.get_profile_names()) if self.window.trigger_engine else {}
        self.table.setRowCount(len(rules))
        for row, rule in enumerate(rules):
            values = (
                str(rule.get("name") or rule.get("executable") or "—"),
                str(rule.get("executable") or "—"),
                profile_names.get(str(rule.get("profile_id") or ""), str(rule.get("profile_id") or "—")),
                str(rule.get("priority", 0)),
                "Al frente" if rule.get("foreground_only") else "Mientras esté abierto",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, str(rule.get("id") or ""))
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()

    def refresh_status(self) -> None:
        watcher = self._watcher()
        if not watcher:
            self.live_status.setText("El motor de perfiles automáticos no está disponible")
            return
        snap = watcher.get_diagnostics_snapshot()
        game = snap.get("current_game")
        profile_id = snap.get("current_profile")
        foreground = snap.get("foreground") or {}
        foreground_name = foreground.get("executable") or "ninguna"
        if game:
            self.live_status.setText(
                f"Activo: {game} → {profile_id}. Ventana al frente: {foreground_name}. Perfil de regreso: {snap.get('base_profile') or '—'}."
            )
        else:
            self.live_status.setText(
                f"Sin regla activa. Ventana al frente: {foreground_name}. Perfil base: {snap.get('base_profile') or '—'}."
            )
        history = snap.get("history") or []
        if history:
            last = history[-1]
            self.live_history.setText(
                f"Último evento: {last.get('reason', 'cambio')} · {last.get('executable') or 'sin juego'} · {last.get('profile_id') or 'sin perfil'}"
            )
        else:
            self.live_history.setText("Sin cambios automáticos recientes")

    def refresh(self) -> None:
        self._loading = True
        self.refresh_profiles()
        watcher = self._watcher()
        self.enabled.setChecked(bool(watcher.is_enabled()) if watcher else False)
        self._loading = False
        self.refresh_rules()
        self.refresh_status()


class CompatibilityPage(ScrollPage):
    """Centro de HidHide y prevención de doble entrada."""

    scan_ready = Signal(object)
    action_ready = Signal(bool, str)

    def __init__(self, window: "NikaidoWindow") -> None:
        super().__init__()
        self.window = window
        self._busy = False
        self._snapshot: Dict[str, Any] = {}
        self.scan_ready.connect(self._apply_scan)
        self.action_ready.connect(self._apply_action)

        top = QHBoxLayout()
        top.addWidget(label("Compatibilidad y doble entrada", "title"))
        top.addStretch()
        self.scan_button = button("Analizar", self.refresh, primary=True)
        top.addWidget(self.scan_button)
        self.layout.addLayout(top)
        intro = label(
            "HidHide evita que un juego vea al mismo tiempo el DualSense físico y el control virtual. Nikaido solo usa las herramientas oficiales y nunca oculta un dispositivo sin que tú lo elijas.",
            "muted",
        )
        intro.setWordWrap(True)
        self.layout.addWidget(intro)

        status_panel = card()
        status_box = QVBoxLayout(status_panel)
        status_box.setContentsMargins(18, 16, 18, 18)
        status_box.addWidget(label("ESTADO", "eyebrow"))
        self.state_title = label("Analizando…", "heading")
        status_box.addWidget(self.state_title)
        self.state_detail = label("", "muted")
        self.state_detail.setWordWrap(True)
        status_box.addWidget(self.state_detail)
        self.issues = label("", "muted")
        self.issues.setWordWrap(True)
        status_box.addWidget(self.issues)
        self.layout.addWidget(status_panel)

        actions_panel = card()
        actions_box = QVBoxLayout(actions_panel)
        actions_box.setContentsMargins(18, 16, 18, 18)
        actions_box.addWidget(label("ACCIONES SEGURAS", "eyebrow"))
        actions = QHBoxLayout()
        actions.addWidget(button("Instalar HidHide", self.install_hidhide))
        actions.addWidget(button("Abrir cliente oficial", self.open_client))
        actions.addWidget(button("Permitir Nikaido", self.whitelist_nikaido))
        self.cloak_button = button("Activar ocultamiento", self.toggle_cloak, primary=True)
        actions.addWidget(self.cloak_button)
        actions.addStretch()
        actions_box.addLayout(actions)
        self.layout.addWidget(actions_panel)

        devices_panel = card()
        devices_box = QVBoxLayout(devices_panel)
        devices_box.setContentsMargins(18, 16, 18, 18)
        devices_box.addWidget(label("DUALSENSE DETECTADOS", "eyebrow"))
        device_help = label(
            "Selecciona el ID exacto del DualSense. Ocultarlo afecta únicamente cómo lo ven los juegos; Nikaido seguirá leyéndolo si está permitido en HidHide.",
            "muted",
        )
        device_help.setWordWrap(True)
        devices_box.addWidget(device_help)
        row = QHBoxLayout()
        self.devices = QComboBox()
        self.devices.setMinimumWidth(420)
        row.addWidget(self.devices, 1)
        row.addWidget(button("Ocultar seleccionado", lambda: self.set_hidden(True), primary=True))
        row.addWidget(button("Volver a mostrar", lambda: self.set_hidden(False)))
        devices_box.addLayout(row)
        self.layout.addWidget(devices_panel)
        self.layout.addStretch()
        self.window.call_later(80, self.refresh)

    def _manager(self):
        return self.window.hidhide_manager

    def _emulator_active(self) -> bool:
        emulator = getattr(self.window.connection_manager, "emulator", None)
        if emulator and hasattr(emulator, "get_diagnostics_snapshot"):
            try:
                return bool(emulator.get_diagnostics_snapshot().get("active"))
            except Exception:
                return False
        return False

    def refresh(self) -> None:
        manager = self._manager()
        if not manager or self._busy:
            return
        self._busy = True
        self.scan_button.setEnabled(False)
        self.state_title.setText("Analizando HidHide…")

        def work() -> None:
            try:
                snapshot = manager.scan(force=True, emulator_active=self._emulator_active())
            except Exception as exc:
                snapshot = {"supported": os.name == "nt", "installed": False, "issues": [str(exc)], "error": str(exc)}
            self.scan_ready.emit(snapshot)

        threading.Thread(target=work, name="NikaidoHidHideScan", daemon=True).start()

    def _apply_scan(self, snapshot: object) -> None:
        self._busy = False
        self.scan_button.setEnabled(True)
        self._snapshot = dict(snapshot) if isinstance(snapshot, dict) else {}
        data = self._snapshot
        if not data.get("supported"):
            self.state_title.setText("Disponible únicamente en Windows")
            self.state_detail.setText("HidHide es un controlador de Windows. El resto de Nikaido puede seguir funcionando sin esta sección.")
        elif not data.get("installed"):
            self.state_title.setText("HidHide no está instalado")
            self.state_detail.setText("La emulación funciona, pero algunos juegos podrían registrar dos controles.")
        elif data.get("ready"):
            self.state_title.setText("✓ Protección contra doble entrada lista")
            self.state_detail.setText(f"HidHide {data.get('version') or ''} está activo, Nikaido está permitido y el DualSense está oculto.")
        else:
            self.state_title.setText("HidHide necesita ajustes")
            self.state_detail.setText(
                f"Ocultamiento: {'activo' if data.get('cloak_enabled') else 'apagado'} · Nikaido permitido: {'sí' if data.get('nikaido_whitelisted') else 'no'} · DualSense oculto: {'sí' if data.get('dualsense_hidden') else 'no'}"
            )
        issues = data.get("issues") or []
        self.issues.setText("\n".join(f"• {item}" for item in issues) if issues else "Sin problemas detectados")
        self.cloak_button.setText("Desactivar ocultamiento" if data.get("cloak_enabled") else "Activar ocultamiento")
        current = self.devices.currentData()
        self.devices.clear()
        for device in data.get("dualsense_devices") or []:
            text = str(device)
            hidden = text in (data.get("dualsense_hidden") or [])
            self.devices.addItem(("Oculto · " if hidden else "Visible · ") + text, text)
        if current:
            self.devices.setCurrentIndex(max(0, self.devices.findData(current)))
        if not self.devices.count():
            self.devices.addItem("No se detectó un DualSense en la lista de HidHide", "")

    def _run_action(self, callback: Callable[[], Any], success_message: str) -> None:
        if self._busy:
            return
        self._busy = True
        self.scan_button.setEnabled(False)

        def work() -> None:
            try:
                result = callback()
                if result is False:
                    raise RuntimeError("La acción no está disponible en este equipo")
                self.action_ready.emit(True, success_message)
            except Exception as exc:
                self.action_ready.emit(False, str(exc))

        threading.Thread(target=work, name="NikaidoHidHideAction", daemon=True).start()

    def _apply_action(self, ok: bool, message: str) -> None:
        self._busy = False
        self.scan_button.setEnabled(True)
        if ok:
            self.window.toast(message)
            self.window.call_later(250, self.refresh)
        else:
            self.window.alert(f"HidHide: {message}")

    def install_hidhide(self) -> None:
        manager = self._manager()
        if manager:
            self._run_action(manager.launch_installer, "Página oficial de HidHide abierta")

    def open_client(self) -> None:
        manager = self._manager()
        if manager:
            self._run_action(manager.open_client, "Cliente oficial de HidHide abierto")

    def whitelist_nikaido(self) -> None:
        manager = self._manager()
        if manager:
            self._run_action(manager.whitelist_nikaido, "Nikaido.exe agregado a aplicaciones permitidas")

    def toggle_cloak(self) -> None:
        manager = self._manager()
        if not manager:
            return
        enabled = not bool(self._snapshot.get("cloak_enabled"))
        if not enabled:
            answer = QMessageBox.question(
                self, "Desactivar HidHide", "Esto puede causar doble entrada mientras uses emulación. ¿Continuar?"
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._run_action(lambda: manager.set_cloak_enabled(enabled), "Ocultamiento actualizado")

    def set_hidden(self, hidden: bool) -> None:
        manager = self._manager()
        device = str(self.devices.currentData() or "")
        if not manager or not device:
            self.window.alert("Selecciona un DualSense válido")
            return
        action = "ocultar" if hidden else "volver a mostrar"
        answer = QMessageBox.question(
            self, "Confirmar dispositivo", f"¿{action.capitalize()} este dispositivo?\n\n{device}"
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._run_action(
            lambda: manager.set_device_hidden(device, hidden),
            "Dispositivo actualizado en HidHide",
        )


class MonitorPage(ScrollPage):
    """Centro de diagnóstico sin trabajo pesado en la ruta HID."""

    HEALTH_TEXT = {
        "excellent": ("Excelente", C["green"], "La entrada física y virtual trabajan dentro de valores normales."),
        "warning": ("Revisar", C["yellow"], "Nikaido detectó algo que podría afectar la experiencia."),
        "problem": ("Problema", C["danger"], "Hay uno o más fallos que conviene corregir."),
    }

    def __init__(self, window: "NikaidoWindow") -> None:
        super().__init__()
        self.window = window
        self.packet_count = 0
        self.last_time = time.perf_counter()
        self._capture_was_active = False

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(label("Centro de diagnóstico", "title"))
        sub = label(
            "Mide la ruta HID → Nikaido → control virtual y crea reportes seguros para soporte.",
            "muted",
        )
        sub.setWordWrap(True)
        titles.addWidget(sub)
        header.addLayout(titles, 1)
        header.addWidget(button("Reiniciar métricas", self.reset_metrics))
        header.addWidget(button("Copiar diagnóstico", self.copy_diagnostic))
        header.addWidget(button("Generar reporte", self.export_report, primary=True))
        self.layout.addLayout(header)

        health_card = card()
        health = QHBoxLayout(health_card)
        health.setContentsMargins(18, 14, 18, 14)
        self.health_icon = QLabel("●")
        self.health_icon.setStyleSheet(f"font-size:30px;color:{C['muted']}")
        health.addWidget(self.health_icon)
        health_text = QVBoxLayout()
        self.health_title = label("Esperando datos", "heading")
        self.health_detail = QLabel("Conecta un DualSense para comenzar el análisis.")
        self.health_detail.setWordWrap(True)
        self.health_detail.setProperty("muted", True)
        health_text.addWidget(self.health_title)
        health_text.addWidget(self.health_detail)
        health.addLayout(health_text, 1)
        self.profile_value = QLabel("Perfil: —")
        self.profile_value.setStyleSheet(f"color:{C['muted']}")
        health.addWidget(self.profile_value)
        self.layout.addWidget(health_card)

        top = QHBoxLayout()
        top.setSpacing(14)
        controller_card = card()
        c = QVBoxLayout(controller_card)
        c.addWidget(label("ENTRADA FÍSICA", "eyebrow"))
        self.controller = ControllerVisual(compact=True)
        c.addWidget(self.controller)
        self.connection = label("Desconectado", "heading")
        self.connection.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c.addWidget(self.connection)
        self.buttons = QLabel("Botones: ninguno")
        self.buttons.setWordWrap(True)
        self.buttons.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.buttons.setProperty("muted", True)
        c.addWidget(self.buttons)
        top.addWidget(controller_card, 34)

        metrics_card = card()
        m = QVBoxLayout(metrics_card)
        m.addWidget(label("RUTA DE BAJA LATENCIA", "eyebrow"))
        grid = QGridLayout()
        self.metrics: Dict[str, QLabel] = {}
        metric_help = {
            "HID físico": "Frecuencia estimada con el avance real del contador Sony.",
            "Procesamiento": "Ticks por segundo que Nikaido procesa en su ruta rápida.",
            "Estados nuevos": "Copias nuevas vistas por Nikaido; no es la frecuencia física.",
            "Control virtual": "Actualizaciones por segundo enviadas a ViGEm.",
            "Ruta promedio": "Tiempo interno completo de lectura a salida virtual.",
            "Ruta p95": "El 95 % de los ticks termina por debajo de este tiempo.",
            "Botón p95": "Tiempo de la ruta solo en pulsaciones o liberaciones.",
            "ViGEm promedio": "Tiempo empleado por la escritura del control virtual.",
            "Lecturas fallidas": "Fallos consecutivos reales al leer el DualSense.",
            "Intermedios": "Informes reemplazados por el más reciente; no son paquetes perdidos.",
            "Gyro procesado": "Secuencias nuevas de sensor procesadas por Gyro Engine.",
            "Reinicios secuencia": "Saltos grandes o reinicios del contador HID.",
            "RAM": "Memoria usada por Nikaido.",
            "CPU": "Uso actual de CPU del proceso.",
            "Hilos": "Hilos activos del proceso.",
            "Fuente": "Ruta usada para obtener el estado físico.",
        }
        metric_names = tuple(metric_help)
        for index, key in enumerate(metric_names):
            tile = card(sub=True)
            tile.setToolTip(metric_help[key])
            box = QVBoxLayout(tile)
            box.setContentsMargins(10, 8, 10, 8)
            title_widget = label(key, "muted")
            title_widget.setToolTip(metric_help[key])
            box.addWidget(title_widget)
            value = label("—", "value")
            value.setStyleSheet("font-size:18px")
            value.setToolTip(metric_help[key])
            box.addWidget(value)
            self.metrics[key] = value
            grid.addWidget(tile, index // 4, index % 4)
        m.addLayout(grid)
        top.addWidget(metrics_card, 66)
        self.layout.addLayout(top)

        live_card = card()
        live = QVBoxLayout(live_card)
        live.addWidget(label("ENTRADA CRUDA", "eyebrow"))
        values_grid = QGridLayout()
        self.values: Dict[str, QLabel] = {}
        for index, key in enumerate((
            "L2", "R2", "LS X", "LS Y", "RS X", "RS Y",
            "Gyro X", "Gyro Y", "Gyro Z", "Batería", "Secuencia", "Fuente",
        )):
            tile = card(sub=True)
            box = QVBoxLayout(tile)
            box.setContentsMargins(9, 7, 9, 7)
            box.addWidget(label(key, "muted"))
            value = label("0", "heading")
            box.addWidget(value)
            self.values[key] = value
            values_grid.addWidget(tile, index // 6, index % 6)
        live.addLayout(values_grid)
        self.graph = LatencyGraph(120, 12.0, top_label="12 ms", middle_label="6 ms", bottom_label="0 ms", footer="p95")
        live.addWidget(self.graph)
        self.layout.addWidget(live_card)

        lower = QHBoxLayout()
        lower.setSpacing(14)
        capture_card = card()
        capture = QVBoxLayout(capture_card)
        capture.addWidget(label("CAPTURA PARA SOPORTE", "eyebrow"))
        capture.addWidget(label("Graba una muestra corta sin datos personales", "heading"))
        capture_info = QLabel(
            "Incluye tiempos, botones, sticks y sensores. No incluye macros, nombres de usuario ni rutas privadas."
        )
        capture_info.setWordWrap(True)
        capture_info.setProperty("muted", True)
        capture.addWidget(capture_info)
        capture_row = QHBoxLayout()
        self.capture_duration = QComboBox()
        self.capture_duration.addItem("10 segundos", 10)
        self.capture_duration.addItem("20 segundos", 20)
        self.capture_duration.addItem("30 segundos", 30)
        capture_row.addWidget(self.capture_duration)
        self.capture_button = button("Iniciar captura", self.toggle_capture, primary=True)
        capture_row.addWidget(self.capture_button)
        capture.addLayout(capture_row)
        self.capture_progress = QProgressBar()
        self.capture_progress.setRange(0, 100)
        self.capture_progress.setValue(0)
        capture.addWidget(self.capture_progress)
        self.capture_status = label("Sin captura · el reporte usará los últimos 10 segundos", "muted")
        capture.addWidget(self.capture_status)
        lower.addWidget(capture_card, 48)

        conflicts_card = card()
        conflicts = QVBoxLayout(conflicts_card)
        conflicts.addWidget(label("CONFLICTOS Y AVISOS", "eyebrow"))
        self.conflicts = QListWidget()
        self.conflicts.setMinimumHeight(130)
        conflicts.addWidget(self.conflicts)
        self.conflict_hint = label("La revisión se actualiza cada pocos segundos.", "muted")
        conflicts.addWidget(self.conflict_hint)
        lower.addWidget(conflicts_card, 52)
        self.layout.addLayout(lower)

    def update_state(self, state: Any) -> None:
        self.controller.set_state(state)
        self.packet_count += 1
        connected = bool(getattr(state, "connected", False))
        conn = getattr(getattr(state, "connection_type", None), "value", "none")
        self.connection.setText(f"{'Conectado' if connected else 'Desconectado'} · {conn.upper()}")
        self.connection.setStyleSheet(
            f"color:{C['green'] if connected else C['muted']};font-weight:700"
        )
        data = {
            "L2": getattr(state, "left_trigger", 0),
            "R2": getattr(state, "right_trigger", 0),
            "LS X": getattr(state, "left_stick_x", 128),
            "LS Y": getattr(state, "left_stick_y", 128),
            "RS X": getattr(state, "right_stick_x", 128),
            "RS Y": getattr(state, "right_stick_y", 128),
            "Gyro X": getattr(state, "gyro_pitch", 0),
            "Gyro Y": getattr(state, "gyro_yaw", 0),
            "Gyro Z": getattr(state, "gyro_roll", 0),
            "Secuencia": getattr(state, "sequence", -1),
            "Fuente": getattr(state, "source", "unknown"),
        }
        for key, value in data.items():
            self.values[key].setText(str(value))
        pressed = [key for key, value in getattr(state, "buttons", {}).items() if value]
        self.buttons.setText("Botones: " + (", ".join(pressed) if pressed else "ninguno"))

    def update_battery(self, level_value: int) -> None:
        self.values["Batería"].setText(f"{level_value}%")

    def update_system_metrics(self) -> None:
        engine = self.window.diagnostic_engine
        if not engine:
            self.health_title.setText("Diagnóstico no disponible")
            return
        snapshot = engine.snapshot()
        connection = snapshot.get("connection", {})
        emulator = snapshot.get("emulator", {})
        gyro = snapshot.get("gyro", {})
        process = snapshot.get("process", {})
        health = snapshot.get("health", "warning")
        title, color, default_detail = self.HEALTH_TEXT.get(health, self.HEALTH_TEXT["warning"])
        issues = snapshot.get("issues", [])
        self.health_icon.setStyleSheet(f"font-size:30px;color:{color}")
        self.health_title.setText(title)
        self.health_title.setStyleSheet(f"color:{color};font-weight:800")
        self.health_detail.setText(" · ".join(issues) if issues else default_detail)
        self.profile_value.setText(f"Perfil: {snapshot.get('profile') or '—'}")

        values = {
            "HID físico": f"{connection.get('device_report_hz', 0):.0f} Hz",
            "Procesamiento": f"{connection.get('processing_hz', connection.get('poll_hz', 0)):.0f} Hz",
            "Estados nuevos": f"{connection.get('fresh_snapshot_hz', connection.get('unique_hid_hz', 0)):.0f} Hz",
            "Control virtual": f"{emulator.get('virtual_hz', 0):.0f} Hz",
            "Ruta promedio": f"{connection.get('pipeline_avg_ms', 0):.2f} ms",
            "Ruta p95": f"{connection.get('pipeline_p95_ms', 0):.2f} ms",
            "Botón p95": f"{connection.get('button_edge_p95_ms', 0):.2f} ms",
            "ViGEm promedio": f"{emulator.get('update_avg_ms', 0):.2f} ms",
            "Lecturas fallidas": str(connection.get("read_failures", 0)),
            "Intermedios": f"{connection.get('coalesced_percent', 0):.1f}%",
            "Gyro procesado": f"{gyro.get('processed_sample_hz', gyro.get('sample_hz', 0)):.0f} Hz",
            "Reinicios secuencia": str(connection.get("sequence_discontinuities", 0)),
            "RAM": f"{process.get('ram_mb', 0):.0f} MB",
            "CPU": f"{process.get('cpu_percent', 0):.1f}%",
            "Hilos": str(process.get("threads", 0)),
            "Fuente": str(connection.get("source", "unknown")),
        }
        for key, value in values.items():
            self.metrics[key].setText(value)
        self.graph.add_value(float(connection.get("pipeline_p95_ms", 0.0) or 0.0))

        self.conflicts.clear()
        conflicts = snapshot.get("conflicts", [])
        if conflicts:
            for name in conflicts:
                if str(name).startswith("Steam ("):
                    item = QListWidgetItem("ℹ Steam detectado · revisa Steam Input para este juego")
                    item.setToolTip(
                        "Steam por sí solo no es un error. Puede duplicar entradas si Steam Input "
                        "también está emulando el mismo control."
                    )
                else:
                    item = QListWidgetItem(f"⚠ {name} podría duplicar entradas")
                    item.setToolTip(
                        "Cierra este programa o desactiva su remapeo mientras usas Nikaido."
                    )
                self.conflicts.addItem(item)
        for issue in issues:
            if not any(issue in self.conflicts.item(i).text() for i in range(self.conflicts.count())):
                self.conflicts.addItem(QListWidgetItem(f"• {issue}"))
        for advisory in snapshot.get("advisories", []):
            if not any(advisory in self.conflicts.item(i).text() for i in range(self.conflicts.count())):
                item = QListWidgetItem(f"ℹ {advisory}")
                item.setToolTip("Aviso informativo: no reduce la salud del sistema.")
                self.conflicts.addItem(item)
        if self.conflicts.count() == 0:
            self.conflicts.addItem(QListWidgetItem("✓ No se detectaron conflictos"))

        capture = snapshot.get("capture", {})
        active = bool(capture.get("active"))
        progress = int(float(capture.get("progress", 0)) * 100)
        self.capture_progress.setValue(progress)
        self.capture_button.setText("Detener captura" if active else "Iniciar captura")
        self.capture_duration.setEnabled(not active)
        samples = int(capture.get("samples", 0))
        if active:
            self.capture_status.setText(
                f"Capturando · {capture.get('elapsed', 0):.1f}/{capture.get('duration', 0):.0f} s · {samples} muestras"
            )
        elif samples:
            self.capture_status.setText(f"Captura lista · {samples} muestras")
        else:
            self.capture_status.setText("Sin captura · el reporte usará los últimos 10 segundos")
        if self._capture_was_active and not active:
            self.window.toast("Captura de diagnóstico terminada", "success")
        self._capture_was_active = active

    def toggle_capture(self) -> None:
        engine = self.window.diagnostic_engine
        if not engine:
            return
        status = engine.capture_status()
        if status.get("active"):
            engine.stop_capture()
            self.window.toast("Captura detenida")
        else:
            engine.start_capture(float(self.capture_duration.currentData() or 10))
            self.window.toast("Captura iniciada")
        self.update_system_metrics()

    def reset_metrics(self) -> None:
        manager = self.window.connection_manager
        emulator = getattr(manager, "emulator", None)
        if manager and hasattr(manager, "reset_diagnostics"):
            manager.reset_diagnostics()
        if emulator and hasattr(emulator, "reset_diagnostics"):
            emulator.reset_diagnostics()
        if self.window.diagnostic_engine:
            self.window.diagnostic_engine.clear_capture()
        self.graph.values.clear()
        self.window.toast("Métricas reiniciadas")
        self.update_system_metrics()

    def copy_diagnostic(self) -> None:
        engine = self.window.diagnostic_engine
        if not engine or not hasattr(engine, "generate_summary_text"):
            self.window.toast("Diagnóstico no disponible", "error")
            return
        try:
            QApplication.clipboard().setText(engine.generate_summary_text())
        except Exception as exc:
            self.window.alert(f"No se pudo copiar el diagnóstico: {exc}")
            return
        self.window.toast("Diagnóstico seguro copiado", "success")

    def export_report(self) -> None:
        engine = self.window.diagnostic_engine
        if not engine:
            self.window.toast("Diagnóstico no disponible", "error")
            return
        default_name = f"Nikaido-Diagnostico-{time.strftime('%Y%m%d-%H%M')}.zip"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar reporte de diagnóstico",
            default_name,
            "Reporte Nikaido (*.zip)",
        )
        if not path:
            return
        try:
            output = engine.generate_report(path)
        except Exception as exc:
            self.window.alert(f"No se pudo generar el reporte: {exc}")
            return
        self.window.toast(f"Reporte guardado: {Path(output).name}", "success")


from .emulation import EmulationPage



class ToolsPage(ScrollPage):
    def __init__(self, window: "NikaidoWindow") -> None:
        super().__init__()
        self.window = window
        self.add_header(
            "Herramientas", "Pruebas, conexión, calibración y recuperación."
        )
        self.grid = QGridLayout()
        self.grid.setSpacing(12)
        self.layout.addLayout(self.grid)
        tools = (
            (
                "⌁",
                "Conectar control",
                "Activa la búsqueda USB/Bluetooth.",
                self.connect,
            ),
            ("×", "Desconectar", "Pausa la reconexión automática.", self.disconnect),
            (
                "↻",
                "Reiniciar Bluetooth",
                "Reinicia el servicio de Windows.",
                self.reset_bt,
            ),
            (
                "◌",
                "Restablecer gatillos",
                "Elimina resistencia y vibración activa.",
                self.reset_triggers,
            ),
            (
                "◎",
                "Calibrar sticks",
                "Mide el centro de ambas palancas.",
                self.calibrate_sticks,
            ),
            (
                "◉",
                "Calibrar giroscopio",
                "Calcula el bias del sensor IMU.",
                self.calibrate_gyro,
            ),
        )
        for index, (icon, title, desc, action) in enumerate(tools):
            panel = card()
            box = QVBoxLayout(panel)
            ico = QLabel(icon)
            ico.setProperty("accentIcon", True)
            ico.setStyleSheet("font-size:30px")
            box.addWidget(ico)
            box.addWidget(label(title, "heading"))
            description = QLabel(desc)
            description.setWordWrap(True)
            description.setProperty("muted", True)
            box.addWidget(description)
            box.addStretch()
            box.addWidget(button("Ejecutar", action, primary=index in (0, 4, 5)))
            self.grid.addWidget(panel, index // 3, index % 3)

    def connect(self) -> None:
        if self.window.connection_manager:
            self.window.connection_manager.request_connect()
            self.window.toast("Buscando DualSense")

    def disconnect(self) -> None:
        if self.window.connection_manager:
            self.window.connection_manager.disconnect()

    def reset_bt(self) -> None:
        manager = self.window.connection_manager
        if not manager:
            return
        self.window.toast("Reiniciando Bluetooth…")

        def worker() -> None:
            if not manager.perform_bluetooth_reset():
                self.window.bridge.error.emit("No se pudo reiniciar Bluetooth")

        threading.Thread(target=worker, daemon=True).start()

    def reset_triggers(self) -> None:
        if self.window.trigger_engine:
            self.window.trigger_engine.reset_triggers()
            self.window.toast("Gatillos restablecidos")

    def calibrate_sticks(self) -> None:
        if self.window.input_studio:
            profile = (
                self.window.trigger_engine.get_current_profile()
                if self.window.trigger_engine
                else None
            )
            self.window.input_studio.begin_drift_calibration(profile, "left", 120)
            self.window.input_studio.begin_drift_calibration(profile, "right", 120)
            self.window.toast("No muevas las palancas")

    def calibrate_gyro(self) -> None:
        if self.window.gyro_engine:
            self.window.gyro_engine.begin_calibration()
            self.window.toast("Deja quieto el control")
