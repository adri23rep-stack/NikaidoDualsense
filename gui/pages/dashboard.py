"""DashboardPage extraídos de la antigua interfaz monolítica."""

from __future__ import annotations

from typing import TYPE_CHECKING


from ..ui_common import (
    logging,
    Any,
    C,
    Dict,
    Optional,
    Path,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QTabBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    Qt,
    button,
    card,
    configure_tabs,
    label,
    os,
    psutil,
)
from ..components import ControllerVisual, LatencyGraph, ScrollPage, load_scaled_pixmap
from ..profile_visuals import fallback_glyph
from ..i18n import tr, translate_widget_tree

if TYPE_CHECKING:
    from ..main_window import NikaidoWindow

logger = logging.getLogger(__name__)


class DashboardPage(ScrollPage):
    FAVORITE_PAGES = (
        ("profiles", "♧"),
        ("automation", "◫"),
        ("monitor", "▣"),
        ("input", "◎"),
        ("gyro", "◉"),
        ("macros", "⌘"),
        ("lights", "☼"),
        ("vibration", "◌"),
        ("triggers", "↯"),
        ("audio", "♬"),
        ("emulation", "◆"),
        ("calibration", "◫"),
        ("tools", "⌁"),
        ("compatibility", "◇"),
        ("settings", "⚙"),
    )

    def __init__(self, window: "NikaidoWindow") -> None:
        super().__init__()
        self.window = window
        self._favorite_destinations = self._load_favorite_destinations()
        self._process = None
        if psutil is not None:
            try:
                self._process = psutil.Process(os.getpid())
                self._process.cpu_percent(None)  # prepara la primera muestra
            except Exception:
                self._process = None
        top = QHBoxLayout()
        top.setSpacing(14)
        top.addWidget(self._controller_card(), 32)
        top.addWidget(self._profile_card(), 31)
        top.addWidget(self._monitor_card(), 37)
        self.layout.addLayout(top)
        self.layout.addWidget(self._workbench(), 1)

    def _controller_card(self) -> QFrame:
        panel = card()
        box = QVBoxLayout(panel)
        box.setContentsMargins(16, 14, 16, 12)
        box.addWidget(label("CONTROLADOR", "eyebrow"))
        self.controller_name = label("DualSense Wireless", "heading")
        box.addWidget(self.controller_name)
        self.connection_label = QLabel("●  Buscando control     ○  USB")
        self.connection_label.setStyleSheet(f"color:{C['muted']};font-size:11px")
        box.addWidget(self.connection_label)
        self.controller = ControllerVisual()
        box.addWidget(self.controller, 1)
        stats = QGridLayout()
        stats.setSpacing(8)
        self.battery_box = self._battery_stat()
        firmware, self.firmware_value = self._tiny_stat("≋", "Firmware", "—", C["text"])
        health, self.health_value = self._tiny_stat(
            "◎", "Estado", "Esperando", C["muted"]
        )
        # La batería ocupa una fila completa; firmware y estado comparten la
        # segunda. Así el texto nunca se encime en ventanas estrechas.
        stats.addWidget(self.battery_box, 0, 0, 1, 2)
        stats.addWidget(firmware, 1, 0)
        stats.addWidget(health, 1, 1)
        stats.setColumnStretch(0, 1)
        stats.setColumnStretch(1, 1)
        box.addLayout(stats)
        details = button("Ver detalles   ›", lambda: self.window.navigate("monitor"))
        details.setFlat(True)
        box.addWidget(details)
        return panel

    @staticmethod
    def _tiny_stat(
        icon: str, title: str, value: str, color: str
    ) -> tuple[QFrame, QLabel]:
        frame = card(sub=True)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 7, 10, 7)
        ico = QLabel(icon)
        ico.setStyleSheet(f"font-size:18px;color:{color}")
        layout.addWidget(ico)
        text = QVBoxLayout()
        text.setSpacing(0)
        text.addWidget(label(title, "muted"))
        value_label = QLabel(value)
        value_label.setStyleSheet(f"font-weight:700;color:{color}")
        text.addWidget(value_label)
        layout.addLayout(text)
        return frame, value_label

    def _battery_stat(self) -> QFrame:
        """Medidor de batería compacto que no se rompe con textos de carga."""
        frame = card(sub=True)
        frame.setMinimumHeight(72)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(11, 8, 11, 8)
        layout.setSpacing(4)

        heading = QHBoxLayout()
        heading.setSpacing(6)
        icon = QLabel("▣")
        icon.setStyleSheet(f"font-size:18px;color:{C['muted']}")
        heading.addWidget(icon)
        heading.addWidget(label("Batería", "muted"))
        heading.addStretch()
        self.battery_value = QLabel("—")
        self.battery_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.battery_value.setStyleSheet(f"font-weight:800;color:{C['muted']}")
        heading.addWidget(self.battery_value)
        layout.addLayout(heading)

        self.battery_bar = QProgressBar()
        self.battery_bar.setRange(0, 100)
        self.battery_bar.setValue(0)
        self.battery_bar.setTextVisible(False)
        self.battery_bar.setFixedHeight(7)
        self.battery_bar.setStyleSheet(
            f"QProgressBar{{background:{C['panel']};border:1px solid {C['border']};border-radius:3px;}}"
            f"QProgressBar::chunk{{background:{C['muted']};border-radius:2px;}}"
        )
        layout.addWidget(self.battery_bar)
        self.battery_detail = QLabel(tr("Esperando lectura", getattr(self.window, "language", "es")))
        self.battery_detail.setStyleSheet(f"color:{C['muted']};font-size:10px")
        self.battery_detail.setWordWrap(False)
        layout.addWidget(self.battery_detail)
        return frame

    def _profile_card(self) -> QFrame:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        panel = card()
        box = QVBoxLayout(panel)
        box.setContentsMargins(15, 14, 15, 14)
        box.addWidget(label("PERFIL ACTIVO", "eyebrow"))
        row = QHBoxLayout()
        self.profile_icon = QLabel("🎮")
        self.profile_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.profile_icon.setFixedSize(96, 96)
        self.profile_icon.setStyleSheet(
            "font-size:42px;background:#18162a;border-radius:9px"
        )
        row.addWidget(self.profile_icon)
        names = QVBoxLayout()
        names.addStretch()
        self.profile_name = label("Sin perfil", "title")
        names.addWidget(self.profile_name)
        self.profile_mode = QLabel("Modo: —")
        self.profile_mode.setStyleSheet(f"color:{C['muted']}")
        names.addWidget(self.profile_mode)
        names.addStretch()
        row.addLayout(names, 1)
        box.addLayout(row)
        actions = QHBoxLayout()
        actions.addWidget(
            button(
                "Cambiar perfil", lambda: self.window.navigate("profiles"), primary=True
            )
        )
        actions.addWidget(
            button("Gatillos L2 / R2", lambda: self.window.navigate("triggers"))
        )
        box.addLayout(actions)
        layout.addWidget(panel)

        quick = card()
        q = QVBoxLayout(quick)
        q.setContentsMargins(15, 12, 15, 12)
        q.addWidget(label("ACCESOS RÁPIDOS", "eyebrow"))
        quick_row = QHBoxLayout()
        quick_row.setSpacing(6)
        for icon, title, action in (
            ("＋", "Nuevo perfil", "profiles"),
            ("⇥", "Importar", "profiles"),
            ("⇤", "Exportar", "profiles"),
            ("⌘", "Compartir", "profiles"),
            ("↶", "Restablecer", "tools"),
        ):
            item = QPushButton(f"{icon}\n{title}")
            item.setFixedHeight(64)
            item.setStyleSheet("padding:5px;font-size:11px")
            item.clicked.connect(
                lambda _=False, dest=action: self.window.navigate(dest)
            )
            quick_row.addWidget(item)
        q.addLayout(quick_row)
        layout.addWidget(quick)
        return wrapper

    def _monitor_card(self) -> QFrame:
        panel = card()
        box = QVBoxLayout(panel)
        box.setContentsMargins(15, 14, 15, 14)
        heading = QHBoxLayout()
        heading.addWidget(label("MONITOR EN TIEMPO REAL", "eyebrow"))
        heading.addStretch()
        heading.addWidget(button("Ver más", lambda: self.window.navigate("monitor")))
        box.addLayout(heading)
        grid = QGridLayout()
        grid.setSpacing(8)
        self.metrics: Dict[str, QLabel] = {}
        for index, (key, title, value) in enumerate(
            (
                ("poll", "HID físico", "— Hz"),
                ("lag", "Ruta p95", "— ms"),
                ("fps", "Control virtual", "— Hz"),
                ("cpu", "CPU de Nikaido", "0%"),
                ("memory", "Memoria", "0 MB"),
                ("lost", "Fallos de lectura", "0"),
            )
        ):
            tile = card(sub=True)
            t = QVBoxLayout(tile)
            t.setContentsMargins(10, 9, 10, 9)
            t.addWidget(label(title, "muted"))
            value_label = label(value, "value")
            t.addWidget(value_label)
            self.metrics[key] = value_label
            grid.addWidget(tile, index // 3, index % 3)
        box.addLayout(grid)
        self.graph = LatencyGraph(
            75, 12.0,
            top_label="12 ms", middle_label="6 ms", bottom_label="0 ms", footer="p95",
        )
        box.addWidget(self.graph, 1)
        return panel

    def _load_favorite_destinations(self) -> list[str]:
        saved = (
            self.window.profile_manager.get_setting("dashboard.favorite_tabs", [])
            if self.window.profile_manager
            else []
        )
        allowed = {destination for destination, _icon in self.FAVORITE_PAGES}
        result: list[str] = []
        for destination in saved if isinstance(saved, list) else []:
            destination = str(destination)
            if destination in allowed and destination not in result:
                result.append(destination)
        return result

    def _workbench(self) -> QFrame:
        panel = card()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 0, 12, 12)

        self.workbench_tabs = configure_tabs(QTabWidget())
        self.workbench_tabs.setTabsClosable(False)

        self.favorite_menu = QMenu(self.workbench_tabs)
        self.favorite_button = QPushButton("✎")
        self.favorite_button.setProperty("iconButton", True)
        self.favorite_button.setFixedSize(34, 30)
        self.favorite_button.setToolTip("Personalizar favoritos")
        self.favorite_button.setAccessibleName("Personalizar favoritos del Dashboard")
        self.favorite_button.setMenu(self.favorite_menu)
        self.workbench_tabs.setCornerWidget(
            self.favorite_button, Qt.Corner.TopRightCorner
        )

        self._append_workbench_tab("mapper", fixed=True)
        for destination in self._favorite_destinations:
            self._append_workbench_tab(destination)
        self._protect_nexus_tab()
        self._rebuild_favorite_menu()

        layout.addWidget(self.workbench_tabs)
        return panel

    def _page_title(self, destination: str) -> str:
        title = self.window.page_meta(destination)[0]
        icon = dict(self.FAVORITE_PAGES).get(destination, "•")
        if destination == "mapper":
            icon = "⌘"
        return f"{icon}  {title}"

    def _append_workbench_tab(self, destination: str, *, fixed: bool = False) -> None:
        page = QWidget()
        page.setProperty("dashboardDestination", destination)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(12, 14, 12, 14)

        if destination == "mapper":
            page_layout.addLayout(self._mapper_overview())
        else:
            page_layout.addWidget(self._favorite_preview(destination))
            page_layout.addStretch()

        translate_widget_tree(page, self.window.language)
        index = self.workbench_tabs.addTab(page, self._page_title(destination))
        if fixed:
            self.workbench_tabs.setTabToolTip(
                index, "Nikaido Nexus siempre permanece en el Dashboard"
            )
        else:
            self.workbench_tabs.setTabToolTip(index, "Favorito del Dashboard")

    def _favorite_preview(self, destination: str) -> QFrame:
        frame = card(sub=True)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title, subtitle = self.window.page_meta(destination)
        heading = QHBoxLayout()
        heading.addWidget(label(self._page_title(destination), "heading"))
        heading.addStretch()
        pill = QLabel("Favorito")
        pill.setStyleSheet(
            f"padding:4px 10px;border-radius:10px;background:{C['brand2']};"
            f"border:1px solid {C['border']};color:{C['muted']};font-size:11px"
        )
        heading.addWidget(pill)
        layout.addLayout(heading)

        if subtitle:
            desc = QLabel(subtitle)
            desc.setWordWrap(True)
            desc.setStyleSheet(f"color:{C['muted']}")
            layout.addWidget(desc)

        quick = self._quick_controls_for(destination)
        if quick is not None:
            layout.addWidget(quick)

        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(
            button(
                "Abrir sección",
                lambda _=False, d=destination: self.window.navigate(d),
                primary=True,
            )
        )
        layout.addLayout(actions)

        hint = QLabel("Usa el lápiz para agregar o quitar favoritos.")
        hint.setProperty("muted", True)
        hint.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(hint)
        return frame

    def _quick_controls_for(self, destination: str) -> Optional[QWidget]:
        builders = {
            "emulation": self._emulation_quick_controls,
            "gyro": self._gyro_quick_controls,
            "settings": self._settings_quick_controls,
            "vibration": self._vibration_quick_controls,
        }
        builder = builders.get(destination)
        return builder() if builder else None

    def _quick_panel(self) -> tuple[QFrame, QVBoxLayout]:
        panel = card(sub=True)
        panel.setStyleSheet(
            f"QFrame[subcard='true']{{background:{C['panel2']};border:1px solid {C['border']};border-radius:16px;}}"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        return panel, layout

    def _toggle_chip(
        self,
        text: str,
        checked: bool,
        callback: Any,
        *,
        tooltip: str = "",
    ) -> QPushButton:
        widget = QPushButton(text)
        widget.setCheckable(True)
        widget.setChecked(bool(checked))
        widget.setCursor(Qt.CursorShape.PointingHandCursor)
        widget.setMinimumHeight(38)
        widget.setMinimumWidth(112)
        widget.setToolTip(tooltip)

        def _apply_style() -> None:
            if widget.isChecked():
                widget.setStyleSheet(
                    f"padding:8px 14px;border-radius:16px;"
                    f"border:1px solid {C['accent2']};"
                    f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {C['accent']}, stop:1 {C['accent2']});"
                    f"color:{C['text']};font-weight:700;"
                )
            else:
                widget.setStyleSheet(
                    f"padding:8px 14px;border-radius:16px;"
                    f"border:1px solid {C['border']};background:{C['panel']};"
                    f"color:{C['muted']};font-weight:600;"
                )

        def _toggled(value: bool) -> None:
            _apply_style()
            callback(bool(value))

        widget.toggled.connect(_toggled)
        _apply_style()
        return widget

    def _simple_action(self, text: str, callback: Any) -> QPushButton:
        action = QPushButton(text)
        action.setCursor(Qt.CursorShape.PointingHandCursor)
        action.setMinimumHeight(36)
        action.setStyleSheet(
            f"padding:8px 12px;border-radius:14px;border:1px solid {C['border']};"
            f"background:{C['panel']};color:{C['text']};font-weight:600;"
        )
        action.clicked.connect(callback)
        return action

    def _setting(self, key: str, default: Any = None) -> Any:
        manager = self.window.profile_manager
        return manager.get_setting(key, default) if manager else default

    def _save_bool(self, key: str, value: bool) -> None:
        self.window.save_setting(key, bool(value))

    def _emulation_quick_controls(self) -> QWidget:
        panel, layout = self._quick_panel()
        layout.addWidget(label("Ajustes rápidos", "eyebrow"))
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(
            self._toggle_chip(
                "Gyro",
                bool(self.window.gyro_engine and self.window.gyro_engine.get_config().enabled),
                self._set_quick_gyro,
                tooltip="Activa o desactiva el giroscopio",
            )
        )
        row.addWidget(
            self._toggle_chip(
                "Touchpad",
                bool(self._setting("touchpad_mouse.enabled", False)),
                self._set_quick_touchpad,
                tooltip="Usar touchpad como mouse",
            )
        )
        row.addWidget(
            self._toggle_chip(
                "Mouse",
                bool(self._setting("keyboard_gamepad.enabled", False)),
                self._set_quick_keybridge,
                tooltip="Activa Nikaido KeyBridge",
            )
        )
        row.addStretch()
        layout.addLayout(row)
        return panel

    def _gyro_quick_controls(self) -> QWidget:
        panel, layout = self._quick_panel()
        layout.addWidget(label("Controles rápidos", "eyebrow"))
        row = QHBoxLayout()
        row.setSpacing(10)
        gyro_enabled = bool(self.window.gyro_engine and self.window.gyro_engine.get_config().enabled)
        mouse_gyro = bool(self.window.gyro_engine and self.window.gyro_engine.get_config().mouse_to_gyro_enabled)
        row.addWidget(self._toggle_chip("Gyro", gyro_enabled, self._set_quick_gyro))
        row.addWidget(
            self._toggle_chip(
                "Mouse → Gyro",
                mouse_gyro,
                self._set_quick_mouse_gyro,
                tooltip="Convierte el mouse global en giroscopio virtual",
            )
        )
        row.addWidget(
            self._simple_action("Calibrar", lambda: self.window.navigate("input"))
        )
        row.addStretch()
        layout.addLayout(row)
        return panel

    def _settings_quick_controls(self) -> QWidget:
        panel, layout = self._quick_panel()
        layout.addWidget(label("Preferencias rápidas", "eyebrow"))
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(
            self._toggle_chip(
                "Windows",
                bool(self._setting("start_with_windows", False)),
                lambda value: self._save_bool("start_with_windows", value),
                tooltip="Iniciar con Windows",
            )
        )
        row.addWidget(
            self._toggle_chip(
                "Bandeja",
                bool(self._setting("minimize_to_tray", True)),
                lambda value: self._save_bool("minimize_to_tray", value),
                tooltip="Minimizar a bandeja",
            )
        )
        row.addWidget(
            self._toggle_chip(
                "Inicio mínimo",
                bool(self._setting("start_minimized", False)),
                lambda value: self._save_bool("start_minimized", value),
                tooltip="Abrir minimizado",
            )
        )
        row.addWidget(
            self._toggle_chip(
                "Low Profile",
                bool(self._setting("low_profile_on_minimize", True)),
                lambda value: self._save_bool("low_profile_on_minimize", value),
                tooltip="Liberar la interfaz al minimizar",
            )
        )
        row.addStretch()
        layout.addLayout(row)
        return panel

    def _vibration_quick_controls(self) -> QWidget:
        panel, layout = self._quick_panel()
        layout.addWidget(label("Ajustes rápidos", "eyebrow"))
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(
            self._toggle_chip(
                "Vibración",
                bool(self._setting("vibration_enabled", True)),
                lambda value: self._save_bool("vibration_enabled", value),
                tooltip="Activa la vibración del DualSense",
            )
        )
        row.addWidget(
            self._toggle_chip(
                "Feedback",
                bool(self._setting("virtual_feedback.enabled", True)),
                lambda value: self._save_bool("virtual_feedback.enabled", value),
                tooltip="Reenviar la vibración del juego al control",
            )
        )
        row.addWidget(
            self._toggle_chip(
                "Swap",
                bool(self._setting("virtual_feedback.swap_motors", False)),
                lambda value: self._save_bool("virtual_feedback.swap_motors", value),
                tooltip="Intercambiar motores grande y pequeño",
            )
        )
        row.addStretch()
        layout.addLayout(row)
        return panel

    def _set_quick_touchpad(self, enabled: bool) -> None:
        page = getattr(self.window, "system_page", None)
        if page and hasattr(page, "set_touchpad_enabled"):
            page.set_touchpad_enabled(bool(enabled))
            return
        self._save_bool("touchpad_mouse.enabled", enabled)

    def _set_quick_gyro(self, enabled: bool) -> None:
        page = getattr(self.window, "system_page", None)
        if page and hasattr(page, "set_gyro_enabled"):
            page.set_gyro_enabled(bool(enabled))
            return
        self._save_bool("dashboard.quick.gyro_enabled", enabled)

    def _set_quick_keybridge(self, enabled: bool) -> None:
        page = getattr(self.window, "system_page", None)
        if page and hasattr(page, "set_keybridge_enabled"):
            page.set_keybridge_enabled(bool(enabled))
            return
        self._save_bool("keyboard_gamepad.enabled", enabled)

    def _set_quick_mouse_gyro(self, enabled: bool) -> None:
        page = getattr(self.window, "system_page", None)
        if page and hasattr(page, "set_mouse_gyro_enabled"):
            page.set_mouse_gyro_enabled(bool(enabled))
            return
        self._save_bool("dashboard.quick.mouse_gyro_enabled", enabled)

    def _protect_nexus_tab(self) -> None:
        if not hasattr(self, "workbench_tabs") or not self.workbench_tabs.count():
            return
        bar = self.workbench_tabs.tabBar()
        bar.setTabButton(0, QTabBar.ButtonPosition.LeftSide, None)
        bar.setTabButton(0, QTabBar.ButtonPosition.RightSide, None)

    def _rebuild_favorite_menu(self) -> None:
        self.favorite_menu.clear()
        self.favorite_menu.addSection(tr("Personalizar favoritos", self.window.language))

        add_menu = self.favorite_menu.addMenu(tr("Añadir favorito", self.window.language))
        available = [
            (destination, icon)
            for destination, icon in self.FAVORITE_PAGES
            if destination not in self._favorite_destinations
        ]
        if not available:
            action = add_menu.addAction(tr("Ya agregaste todas las pestañas", self.window.language))
            action.setEnabled(False)
        else:
            for destination, icon in available:
                title = self.window.page_meta(destination)[0]
                action = add_menu.addAction(f"{icon}  {title}")
                action.triggered.connect(
                    lambda _checked=False, d=destination: self._add_favorite_tab(d)
                )

        remove_menu = self.favorite_menu.addMenu(tr("Eliminar favorito", self.window.language))
        if not self._favorite_destinations:
            action = remove_menu.addAction(tr("Solo está Nikaido Nexus", self.window.language))
            action.setEnabled(False)
        else:
            for destination in self._favorite_destinations:
                title = self.window.page_meta(destination)[0]
                action = remove_menu.addAction(f"{tr('Quitar', self.window.language)} {title}")
                action.triggered.connect(
                    lambda _checked=False, d=destination: self._remove_favorite_destination(d)
                )

    def _persist_favorite_destinations(self) -> None:
        self.window.save_setting(
            "dashboard.favorite_tabs", list(self._favorite_destinations)
        )

    def _add_favorite_tab(self, destination: str) -> None:
        allowed = {item for item, _icon in self.FAVORITE_PAGES}
        if destination not in allowed or destination in self._favorite_destinations:
            return
        self._favorite_destinations.append(destination)
        self._append_workbench_tab(destination)
        self._protect_nexus_tab()
        self._persist_favorite_destinations()
        self._rebuild_favorite_menu()
        self.workbench_tabs.setCurrentIndex(self.workbench_tabs.count() - 1)
        title = self.window.page_meta(destination)[0]
        suffix = {"es": "agregado a favoritos", "en": "added to favorites", "pt_BR": "adicionado aos favoritos"}.get(self.window.language, "agregado a favoritos")
        self.window.toast(f"{title} {suffix}", "success")

    def _remove_favorite_tab(self, index: int) -> None:
        if index <= 0 or index >= self.workbench_tabs.count():
            self._protect_nexus_tab()
            return
        page = self.workbench_tabs.widget(index)
        destination = str(page.property("dashboardDestination") or "")
        self._remove_favorite_destination(destination)

    def _remove_favorite_destination(self, destination: str) -> None:
        destination = str(destination or "")
        if not destination or destination not in self._favorite_destinations:
            self._protect_nexus_tab()
            return
        for index in range(1, self.workbench_tabs.count()):
            page = self.workbench_tabs.widget(index)
            current = str(page.property("dashboardDestination") or "")
            if current == destination:
                self.workbench_tabs.removeTab(index)
                page.deleteLater()
                break
        self._favorite_destinations.remove(destination)
        self._persist_favorite_destinations()
        self._protect_nexus_tab()
        self._rebuild_favorite_menu()
        title = self.window.page_meta(destination)[0]
        suffix = {"es": "quitado de favoritos", "en": "removed from favorites", "pt_BR": "removido dos favoritos"}.get(self.window.language, "quitado de favoritos")
        self.window.toast(f"{title} {suffix}", "info")

    def _mapper_overview(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(14)
        left = card(sub=True)
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(label("NEXUS · BOTONES", "eyebrow"))
        self.map_list = QTableWidget(0, 2)
        self.map_list.setHorizontalHeaderLabels(["Entrada", "Salida"])
        self.map_list.horizontalHeader().setStretchLastSection(True)
        self.map_list.verticalHeader().hide()
        self.map_list.setMaximumWidth(300)
        left_layout.addWidget(self.map_list)
        left_layout.addWidget(button("Abrir Nexus", lambda: self.window.navigate("mapper"), primary=True))
        layout.addWidget(left, 25)
        center = card(sub=True)
        c = QVBoxLayout(center)
        view_label = label("Vista:   Frontal     Superior", "muted")
        view_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c.addWidget(view_label)
        self.map_controller = ControllerVisual(compact=True)
        c.addWidget(self.map_controller, 1)
        c.addWidget(
            button(
                "◉  Probar todos los botones", lambda: self.window.navigate("monitor")
            ),
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        layout.addWidget(center, 45)
        right = card(sub=True)
        r = QVBoxLayout(right)
        r.addWidget(label("ZONAS RÁPIDAS", "eyebrow"))
        for icon, title, sub, dest in (
            ("◎", "Prueba de entrada", "Entrada en tiempo real", "monitor"),
            ("☼", "Calibrar sticks", "Calibración de palancas", "input"),
            ("◌", "Prueba de vibración", "Probar motores", "vibration"),
            ("↯", "Gatillos adaptativos", "Rigidez, efectos y curvas", "triggers"),
        ):
            btn = QPushButton(
                f"{icon}   {title}\n      {sub}                         ›"
            )
            btn.setStyleSheet("text-align:left;padding:10px")
            btn.clicked.connect(lambda _=False, d=dest: self.window.navigate(d))
            r.addWidget(btn)
        r.addStretch()
        layout.addWidget(right, 30)
        return layout

    def refresh_profile(self, profile_id: Optional[str]) -> None:
        engine = self.window.trigger_engine
        profile = engine.get_profile(profile_id) if engine and profile_id else None
        if not profile:
            self.profile_name.setText("Sin perfil")
            self.profile_mode.setText("Modo: —")
            self.profile_icon.clear()
            self.profile_icon.setText("🎮")
            return
        self.profile_name.setText(profile.name)
        self._set_profile_image(profile_id, profile)
        self.profile_mode.setText(f"Modo: {profile.category}")
        self.refresh_mapping()

    def _set_profile_image(self, profile_id: Optional[str], profile: Any) -> None:
        self.profile_icon.clear()
        image_path = Path(
            str(
                getattr(profile, "icon_path", "")
                or getattr(profile, "image_path", "")
                or ""
            )
        )
        if image_path.is_file():
            pixmap = load_scaled_pixmap(str(image_path), 92, 92)
            if not pixmap.isNull():
                self.profile_icon.setPixmap(pixmap)
                return
        fallback = str(getattr(profile, "icon", "") or "").strip()
        if fallback.startswith("theme:") or not fallback:
            fallback = fallback_glyph(str(profile_id or ""), profile)
        self.profile_icon.setText(fallback)

    def refresh_mapping(self) -> None:
        emulator = getattr(self.window.connection_manager, "emulator", None)
        mapping = emulator.get_button_map() if emulator else {}
        rows = (
            ("✕", "cross"),
            ("○", "circle"),
            ("□", "square"),
            ("△", "triangle"),
            ("L1", "L1"),
            ("R1", "R1"),
            ("L2", "L2_btn"),
            ("R2", "R2_btn"),
            ("Share", "create"),
            ("Options", "options"),
            ("L3", "L3"),
            ("R3", "R3"),
            ("PS", "ps"),
            ("Touchpad", "touchpad"),
        )
        self.map_list.setRowCount(len(rows))
        for row, (friendly, source) in enumerate(rows):
            self.map_list.setItem(row, 0, QTableWidgetItem(friendly))
            self.map_list.setItem(row, 1, QTableWidgetItem(mapping.get(source, source)))

    def update_state(self, state: Any) -> None:
        self.controller.set_state(state)
        self.map_controller.set_state(state)
        connected = bool(getattr(state, "connected", False))
        conn = getattr(getattr(state, "connection_type", None), "value", "none").upper()
        self.connection_label.setText(
            f"●  {'Conectado' if connected else 'Buscando control'}     ○  {conn if connected else 'USB'}"
        )
        self.health_value.setText("Conectado" if connected else "Esperando")
        self.health_value.setStyleSheet(
            f"font-weight:700;color:{C['green'] if connected else C['muted']}"
        )

    def clear_battery(self, *, connected: bool = False) -> None:
        self.battery_value.setText("—")
        self.battery_value.setStyleSheet(f"font-weight:800;color:{C['muted']}")
        self.battery_detail.setText(tr("Leyendo batería…" if connected else "Sin control conectado", getattr(self.window, "language", "es")))
        self.battery_bar.setValue(0)
        self.battery_bar.setStyleSheet(
            f"QProgressBar{{background:{C['panel']};border:1px solid {C['border']};border-radius:3px;}}"
            f"QProgressBar::chunk{{background:{C['muted']};border-radius:2px;}}"
        )

    def update_battery(self, level: int, charging_status: Any) -> None:
        level = max(0, min(100, int(level)))
        self.battery_value.setText(f"{level}%")
        color = C["green"] if level >= 50 else C["yellow"] if level >= 20 else C["danger"]
        self.battery_value.setStyleSheet(f"font-weight:800;color:{color}")
        self.battery_bar.setValue(level)
        self.battery_bar.setStyleSheet(
            f"QProgressBar{{background:{C['panel']};border:1px solid {C['border']};border-radius:3px;}}"
            f"QProgressBar::chunk{{background:{color};border-radius:2px;}}"
        )
        status_value = str(getattr(charging_status, "value", "") or "").lower()
        if status_value == "cargando":
            self.battery_detail.setText(tr("⚡ Cargando", getattr(self.window, "language", "es")))
        elif status_value == "cargado completo":
            self.battery_detail.setText(tr("Carga completa", getattr(self.window, "language", "es")))
        else:
            self.battery_detail.setText(tr("En uso", getattr(self.window, "language", "es")))

    def update_system_metrics(self) -> None:
        """Muestra métricas medidas por la ruta HID real, no estimaciones de la UI.

        La versión anterior multiplicaba la frecuencia visual por cuatro,
        calculaba el supuesto lag como ``1000 / FPS`` y siempre mostraba cero
        fallos. Esos números variaban al azar según la carga de Qt y no
        describían al control.
        """
        manager = self.window.connection_manager
        connection: Dict[str, Any] = {}
        emulator: Dict[str, Any] = {}
        if manager is not None:
            try:
                connection = dict(manager.get_diagnostics_snapshot())
            except Exception:
                connection = {}
            virtual = getattr(manager, "emulator", None)
            if virtual is not None:
                try:
                    emulator = dict(virtual.get_diagnostics_snapshot())
                except Exception:
                    emulator = {}

        connected = bool(connection.get("connected", False))
        samples = int(connection.get("total_polls", 0) or 0)
        device_hz = float(connection.get("device_report_hz", 0.0) or 0.0)
        route_p95 = float(connection.get("pipeline_p95_ms", 0.0) or 0.0)
        virtual_hz = float(emulator.get("virtual_hz", 0.0) or 0.0)
        failures = int(connection.get("read_failures", 0) or 0)

        measuring = connected and samples < 8
        self.metrics["poll"].setText(
            "Midiendo…" if measuring or (connected and device_hz <= 0.0)
            else f"{device_hz:.0f} Hz" if connected
            else "— Hz"
        )
        self.metrics["lag"].setText(
            "Midiendo…" if measuring
            else f"{route_p95:.2f} ms" if connected and samples
            else "— ms"
        )
        self.metrics["fps"].setText(
            "Midiendo…" if measuring or (connected and emulator.get("active") and virtual_hz <= 0.0)
            else f"{virtual_hz:.0f} Hz" if emulator.get("active")
            else "Inactivo"
        )
        self.metrics["lost"].setText(str(failures))

        cpu = 0.0
        memory_mb = 0.0
        process = self._process
        if process is not None:
            try:
                cpu = float(process.cpu_percent(None))
                memory_mb = float(process.memory_info().rss) / (1024 * 1024)
            except Exception:
                self._process = None
        self.metrics["cpu"].setText(f"{cpu:.1f}%")
        self.metrics["memory"].setText(f"{memory_mb:.0f} MB")
        self.graph.add_value(route_p95 if connected and samples else 0.0)
