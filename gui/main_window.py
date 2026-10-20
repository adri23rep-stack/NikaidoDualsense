"""NikaidoWindow, DualSenseGUI extraídos de la antigua interfaz monolítica."""

from __future__ import annotations

import gc
import importlib

from nikaido_version import ONBOARDING_VERSION

from .ui_common import (
    logging,
    APPEARANCE_PRESETS,
    APP_VERSION,
    Any,
    C,
    Callable,
    Dict,
    List,
    MouseCaptureOverlay,
    Optional,
    QApplication,
    QCloseEvent,
    QEasingCurve,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QIcon,
    QKeySequence,
    QLabel,
    QMainWindow,
    QPixmapCache,
    QPropertyAnimation,
    QPushButton,
    QScrollArea,
    QShortcut,
    QSizeGrip,
    QStackedWidget,
    QTimer,
    QVBoxLayout,
    QVariantAnimation,
    QWidget,
    Qt,
    ToastOverlay,
    appearance_background_signature,
    appearance_style_signature,
    apply_runtime_palette,
    build_app_qss,
    card,
    label,
    normalize_appearance,
    resource_path,
    sys,
)
from .assistant import AssistantTipCard, window_is_in_front
from .assistant_tips import ASSISTANT_TIPS as ASSISTANT_TIP_LIBRARY, take_assistant_tip
from .update_mixin import UpdateWindowMixin
from src.ui_sounds import play_tip_sound, stop_tip_sound
from PySide6.QtCore import QEvent
from .i18n import normalize_language, set_current_language, tr, translate_widget_tree
from .components import BackendBridge, BackgroundRoot, CommandPalette, PageLoadError, SidebarNavButton, TitleBar
from .pages.dashboard import DashboardPage
from .low_profile_runtime import LowProfileGuiRuntime

logger = logging.getLogger(__name__)

class NikaidoWindow(UpdateWindowMixin, QMainWindow):
    PAGE_META = {
        "dashboard": ("Dashboard", "Resumen general de tu controlador y perfil activo"),
        "profiles": ("Perfiles", "Configuraciones por juego y estilo de uso"),
        "automation": ("Perfiles automáticos", "Detección de juegos, prioridades y restauración"),
        "mapper": ("Nikaido Nexus", "Control visual, capas y salidas virtuales"),
        "input": ("Input Studio", "Palancas, zonas muertas y curvas"),
        "gyro": ("Gyro Studio", "Apunta y controla con movimiento"),
        "macros": ("Macros", "Botones, combos, palancas y automatizaciones por perfil"),
        "lights": ("Luces", "RGB e indicador del jugador"),
        "vibration": ("Vibración", "Motores hápticos y fuerza general"),
        "triggers": ("Gatillos adaptativos", "Rigidez, efectos, zonas y curvas de L2/R2"),
        "audio": ("Audio", "Botón MIC, volumen y LED"),
        "monitor": ("Centro de diagnóstico", "Latencia, paquetes, conflictos y reportes de soporte"),
        "emulation": ("Emulación", "DualSense o teclado como Xbox 360 / DualShock 4"),
        "calibration": ("Calibración", "Drift, giroscopio, gatillos y ajustes guiados"),
        "tools": ("Herramientas", "Pruebas y conexión"),
        "compatibility": ("Compatibilidad", "HidHide y prevención de doble entrada"),
        "settings": ("Ajustes", "Preferencias generales de Nikaido"),
    }

    def __init__(self, **backends: Any) -> None:
        super().__init__()
        backend_names = (
            "connection_manager", "trigger_engine", "profile_manager",
            "macro_engine", "light_effect_engine", "player_led_controller", "audio_manager", "game_profile_watcher",
            "touchpad_mouse", "advanced_mapper", "keyboard_gamepad", "gyro_engine", "input_studio",
            "diagnostic_engine", "virtual_feedback_bridge", "hidhide_manager", "update_manager",
        )
        for name in backend_names:
            setattr(self, name, backends.get(name))
        for name, value in backends.items():
            setattr(self, name, value)

        self.language = set_current_language(
            self.profile_manager.get_setting("language", "es")
            if self.profile_manager else "es"
        )
        self.bridge = BackendBridge(self)
        self._on_close: List[Callable[[], None]] = []
        self._backend_unsubscriptions: List[Callable[[], None]] = []
        self._deferred_timers: List[QTimer] = []
        self._stopping = False
        self._cleanup_started = False
        self._pending_state: Any = None
        self._latest_state: Any = None
        self._last_battery: Optional[int] = None
        self._last_charging_status: Any = None
        self._current_page = ""
        self._page_animation: Optional[QPropertyAnimation] = None
        self._animated_page: Optional[QWidget] = None
        self._profile_apply_in_progress = False
        self._profile_apply_scheduled = False
        self._pending_profile_id: Optional[str] = None
        self._welcome_wizard: Optional[QWidget] = None
        self._welcome_prompted = False
        self._assistant_tip_index = 0
        self._assistant_tip_visible = False
        self._available_update: Any = None
        self._update_manual_request = False

        self.config_save_timer = QTimer(self)
        self.config_save_timer.setSingleShot(True)
        self.config_save_timer.timeout.connect(self.flush_config_save)
        self.geometry_save_timer = QTimer(self)
        self.geometry_save_timer.setSingleShot(True)
        self.geometry_save_timer.timeout.connect(self._save_geometry)
        self.status_reset_timer = QTimer(self)
        self.status_reset_timer.setSingleShot(True)
        self.status_reset_timer.timeout.connect(lambda: self.ready.setText(tr("●  Listo.", self.language)))

        self.setObjectName("root")
        self.setWindowTitle(f"Nikaido DualSense {APP_VERSION}")
        self.setMinimumSize(1080, 700)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        geometry = self.profile_manager.get_window_geometry() if self.profile_manager else {}
        self.resize(
            max(1080, int(geometry.get("width") or 1536)),
            max(700, int(geometry.get("height") or 1000)),
        )
        if geometry.get("x") is not None and geometry.get("y") is not None:
            self.move(int(geometry["x"]), int(geometry["y"]))
        icon_path = resource_path("assets/nikaido.svg")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self._appearance = normalize_appearance(
            self.profile_manager.get_setting("appearance", {})
            if self.profile_manager else {}
        )
        self._appearance_style_sig = appearance_style_signature(self._appearance)
        self._appearance_background_sig = appearance_background_signature(self._appearance)
        self.setStyleSheet(build_app_qss(self._appearance))
        apply_runtime_palette(self._appearance)
        # Qt guarda automáticamente pixmaps cargados desde disco. Ocho MB son
        # suficientes para iconos y miniaturas sin retener varias poses grandes.
        QPixmapCache.setCacheLimit(8192)

        self._build()
        translate_widget_tree(self, self.language)
        self._sidebar_collapsed = False
        self._sidebar_animation: Optional[QVariantAnimation] = None
        self.set_sidebar_collapsed(bool(self._appearance.get("sidebar_collapsed", False)), persist=False, animate=False)
        self.background_root.set_appearance(self._appearance)
        self.command_palette = CommandPalette(self)
        self.command_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        self.command_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.command_shortcut.activated.connect(self.show_command_palette)
        self.toast_overlay = ToastOverlay(self.centralWidget())
        self.assistant_card = AssistantTipCard(
            self.centralWidget(),
            on_close=self.hide_assistant_tip,
            on_open=self._open_assistant_destination,
        )
        self.assistant_timer = QTimer(self)
        self.assistant_timer.setSingleShot(True)
        self.assistant_timer.timeout.connect(self.show_next_assistant_tip)
        if self.is_assistant_enabled():
            self.assistant_timer.start(90_000)
        # Ventana independiente para que la cuenta siga visible aunque Nikaido
        # quede detrás del juego o se minimice durante los cinco segundos.
        self.mouse_capture_overlay = MouseCaptureOverlay(self)
        self._mouse_capture_overlay_state = ("", "off")
        self._connect_backend()
        self.refresh_profiles()
        self.navigate("dashboard")

        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self._ui_tick)
        self.ui_timer.start(80)
        self.system_timer = QTimer(self)
        self.system_timer.timeout.connect(self._system_tick)
        self.system_timer.start(1000)
        self.call_later(900, self.maybe_show_welcome_wizard)
        self.call_later(5_000, self._auto_check_updates)

    def page_meta(self, page: str) -> tuple[str, str]:
        title, subtitle = self.PAGE_META.get(page, (str(page).title(), ""))
        return tr(title, self.language), tr(subtitle, self.language)

    def set_language(self, language: Any, *, persist: bool = True) -> str:
        """Cambia el idioma sin reconstruir motores ni perder el estado actual."""
        code = normalize_language(language)
        self.language = set_current_language(code)
        if persist and self.profile_manager:
            self.profile_manager.set_setting("language", code)
            self.request_config_save()
        translate_widget_tree(self, code)
        for page_widget in getattr(self, "pages", {}).values():
            if page_widget is not None:
                translate_widget_tree(page_widget, code)
        if getattr(self, "_current_page", ""):
            title, subtitle = self.page_meta(self._current_page)
            self.titlebar.title.setText(title)
            self.titlebar.subtitle.setText(subtitle)
        palette = getattr(self, "command_palette", None)
        if palette is not None:
            palette._build_entries()
            translate_widget_tree(palette, code)
            palette.refresh()
        self.setWindowTitle(f"Nikaido DualSense {APP_VERSION}")
        return code

    def apply_appearance(self, appearance: Optional[Dict[str, Any]] = None) -> None:
        if appearance is None:
            appearance = (
                self.profile_manager.get_setting("appearance", {})
                if self.profile_manager else {}
            )
        normalized = normalize_appearance(appearance)
        style_sig = appearance_style_signature(normalized)
        background_sig = appearance_background_signature(normalized)
        self._appearance = normalized

        # Oscurecimiento, zoom y posición solo necesitan repintar el fondo.
        # Evitar repolish de toda la aplicación hace los sliders mucho más suaves.
        if style_sig != getattr(self, "_appearance_style_sig", None):
            self.setStyleSheet(build_app_qss(normalized))
            apply_runtime_palette(normalized)
            self._appearance_style_sig = style_sig
            # Gráficos y el control visual usan QPainter, por lo que necesitan
            # un repintado explícito después de cambiar el acento.
            for widget in self.findChildren(QWidget):
                widget.update()
        root = getattr(self, "background_root", None)
        if root is not None and background_sig != getattr(self, "_appearance_background_sig", None):
            root.set_appearance(normalized)
            self._appearance_background_sig = background_sig
        collapsed = bool(normalized.get("sidebar_collapsed", False))
        if collapsed != getattr(self, "_sidebar_collapsed", False):
            self.set_sidebar_collapsed(collapsed, persist=False, animate=True)
        self.update()

    def _build(self) -> None:
        root = BackgroundRoot()
        self.background_root = root
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.sidebar = self._build_sidebar()
        body.addWidget(self.sidebar)
        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)
        self.titlebar = TitleBar(self)
        content.addWidget(self.titlebar)
        self.stack = QStackedWidget()
        content.addWidget(self.stack, 1)
        body.addLayout(content, 1)
        outer.addLayout(body, 1)
        outer.addWidget(self._build_statusbar())
        self.setCentralWidget(root)
        self.size_grip = QSizeGrip(root)
        self.size_grip.setFixedSize(20, 20)
        self.dashboard = DashboardPage(self)
        self.pages: Dict[str, QWidget] = {"dashboard": self.dashboard}
        # Guardamos rutas, no clases. Así Python no importa las seis pantallas
        # grandes hasta que el usuario realmente abre una de ellas.
        self._page_factories: Dict[str, tuple[str, str, str]] = {
            "profiles": ("profiles_page", "gui.pages.profiles", "ProfilesPage"),
            "automation": ("automation_page", "gui.pages.system", "AutoProfilesPage"),
            "mapper": ("mapper_page", "gui.pages.nexus", "MapperPage"),
            "input": ("input_page", "gui.pages.input", "InputStudioPage"),
            "gyro": ("gyro_page", "gui.pages.input", "GyroPage"),
            "macros": ("macros_page", "gui.pages.macros", "MacrosPage"),
            "lights": ("lights_page", "gui.pages.device", "LightsPage"),
            "vibration": ("vibration_page", "gui.pages.device", "VibrationPage"),
            "triggers": ("triggers_page", "gui.pages.triggers", "AdaptiveTriggersPage"),
            "audio": ("audio_page", "gui.pages.device", "AudioPage"),
            "monitor": ("monitor_page", "gui.pages.system", "MonitorPage"),
            "emulation": ("emulation_page", "gui.pages.system", "EmulationPage"),
            "calibration": ("calibration_page", "gui.pages.input", "CalibrationPage"),
            "tools": ("tools_page", "gui.pages.system", "ToolsPage"),
            "compatibility": ("compatibility_page", "gui.pages.system", "CompatibilityPage"),
            "settings": ("settings_page", "gui.pages.settings", "SettingsPage"),
        }
        self.stack.addWidget(self.dashboard)

    def ensure_page(self, page: str) -> Optional[QWidget]:
        """Crea pantallas pesadas bajo demanda y aísla fallos de construcción."""
        existing = self.pages.get(page)
        if existing is not None:
            return existing
        factory_data = self._page_factories.get(page)
        if not factory_data:
            return None
        attribute, module_name, class_name = factory_data
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        previous_status = self.ready.text() if hasattr(self, "ready") else ""
        if hasattr(self, "ready"):
            self.ready.setText(tr(f"●  Cargando {self.page_meta(page)[0]}…", self.language))
            QApplication.processEvents()
        try:
            module = importlib.import_module(module_name)
            factory = getattr(module, class_name)
            widget = factory(self)
            translate_widget_tree(widget, self.language)
            setattr(self, attribute, widget)
        except Exception as exc:
            logger.exception("No se pudo construir la pantalla %s", page)
            widget = PageLoadError(self, page, exc)
        finally:
            QApplication.restoreOverrideCursor()
            if hasattr(self, "ready"):
                self.ready.setText(previous_status or tr("●  Listo.", self.language))
        self.pages[page] = widget
        self.stack.addWidget(widget)
        return widget

    def retry_page(self, page: str) -> None:
        current = self.pages.pop(page, None)
        if current is not None and current is not self.dashboard:
            self.stack.removeWidget(current)
            current.deleteLater()
        factory_data = self._page_factories.get(page)
        if factory_data:
            attribute, _module_name, _class_name = factory_data
            if hasattr(self, attribute):
                delattr(self, attribute)
        target = self.ensure_page(page)
        if target is not None:
            self._current_page = ""
            self.navigate(page)

    def _build_sidebar(self) -> QFrame:
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(320)
        layout = QVBoxLayout(side)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(10)

        brand_card = QFrame()
        brand_card.setObjectName("brandCard")
        self.brand_card = brand_card
        brand_layout = QHBoxLayout(brand_card)
        self.brand_layout = brand_layout
        brand_layout.setContentsMargins(14, 14, 14, 14)
        brand_layout.setSpacing(12)

        logo = QLabel()
        self.brand_logo = logo
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedSize(48, 48)
        icon = QIcon(str(resource_path("assets/nikaido.svg")))
        pixmap = icon.pixmap(48, 48)
        if not pixmap.isNull():
            logo.setPixmap(pixmap)
        else:
            logo.setText("N")
            logo.setStyleSheet(
                f"font-size:27px;font-weight:800;color:white;background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {C['cyan']},stop:.5 {C['accent']},stop:1 {C['accent2']});border-radius:12px"
            )
        brand_layout.addWidget(logo)

        brand_text = QVBoxLayout()
        brand_text.setContentsMargins(0, 0, 0, 0)
        brand_text.setSpacing(2)
        name = label("NIKAIDO", "title")
        self.brand_name = name
        name.setStyleSheet("font-size:22px;font-weight:800;letter-spacing:0.5px")
        brand_text.addWidget(name)
        caption = QLabel("DualSense Control Center")
        self.brand_caption = caption
        caption.setObjectName("brandCaption")
        brand_text.addWidget(caption)
        brand_layout.addLayout(brand_text, 1)

        version = QLabel(f"v{APP_VERSION}")
        self.version_badge = version
        version.setObjectName("versionBadge")
        brand_layout.addWidget(version, 0, Qt.AlignmentFlag.AlignTop)
        self.sidebar_toggle = QPushButton("‹")
        self.sidebar_toggle.setProperty("iconButton", True)
        self.sidebar_toggle.setFixedSize(26, 26)
        self.sidebar_toggle.setToolTip("Contraer barra lateral")
        self.sidebar_toggle.setAccessibleName("Contraer o expandir barra lateral")
        self.sidebar_toggle.clicked.connect(self.toggle_sidebar)
        brand_layout.addWidget(self.sidebar_toggle, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(brand_card)

        self.nav_scroll = QScrollArea()
        self.nav_scroll.setObjectName("navScroll")
        self.nav_scroll.setWidgetResizable(True)
        self.nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.nav_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.nav_scroll.setAutoFillBackground(False)
        self.nav_scroll.viewport().setAutoFillBackground(False)
        nav_body = QWidget()
        nav_body.setObjectName("navBody")
        nav_body.setAutoFillBackground(False)
        nav_layout = QVBoxLayout(nav_body)
        nav_layout.setContentsMargins(0, 6, 0, 6)
        nav_layout.setSpacing(4)
        self.nav_buttons: Dict[str, QPushButton] = {}
        self.nav_headings: List[QLabel] = []

        sections = (
            ("GENERAL", (
                ("dashboard", "⌂", "Dashboard", "Vista general y accesos rápidos"),
                ("profiles", "♧", "Perfiles", "Juegos, favoritos y configuración"),
                ("automation", "◫", "Perfiles automáticos", "Detecta juegos y restaura el perfil"),
                ("monitor", "▣", "Diagnóstico", "Latencia, paquetes y reportes"),
            )),
            ("ENTRADA", (
                ("mapper", "⌘", "Nikaido Nexus", "Control visual, capas y acciones"),
                ("input", "◎", "Input Studio", "Sticks, zonas muertas y curvas"),
                ("gyro", "◉", "Gyro Studio", "Apuntar con movimiento"),
                ("macros", "⌘", "Macros", "Combos, palancas y automatización"),
            )),
            ("DUALSENSE", (
                ("lights", "☼", "Luces", "RGB, efectos y presets"),
                ("vibration", "◌", "Vibración", "Motores hápticos y fuerza"),
                ("triggers", "↯", "Gatillos adaptativos", "Rigidez, efectos y curvas"),
                ("audio", "♬", "Audio", "Botón MIC, volumen y LED"),
            )),
            ("SISTEMA", (
                ("emulation", "◆", "Emulación", "DualSense, teclado y mouse"),
                ("calibration", "◫", "Calibración", "Drift, gyro y gatillos"),
                ("tools", "⌁", "Herramientas", "Pruebas, conexión y soporte"),
                ("compatibility", "◇", "Compatibilidad", "HidHide y doble entrada"),
                ("settings", "⚙", "Ajustes", "Preferencias generales"),
            )),
        )
        for index, (section, items) in enumerate(sections):
            heading = label(section, "eyebrow")
            heading.setContentsMargins(8, 12 if index else 6, 0, 4)
            self.nav_headings.append(heading)
            nav_layout.addWidget(heading)
            for key, icon_char, title, subtitle in items:
                btn = SidebarNavButton(icon_char, title, subtitle)
                btn.clicked.connect(lambda _=False, page=key: self.navigate(page))
                nav_layout.addWidget(btn)
                self.nav_buttons[key] = btn
        nav_layout.addStretch()
        self.nav_scroll.setWidget(nav_body)
        layout.addWidget(self.nav_scroll, 1)

        controller = card(sub=True)
        status = QHBoxLayout(controller)
        status.setContentsMargins(12, 10, 12, 10)
        status.setSpacing(10)
        mini = QLabel()
        mini_icon = icon.pixmap(26, 26)
        if not mini_icon.isNull():
            mini.setPixmap(mini_icon)
        else:
            mini.setText("🎮")
            mini.setStyleSheet("font-size:22px")
        status.addWidget(mini, 0, Qt.AlignmentFlag.AlignTop)
        info = QVBoxLayout()
        info.setSpacing(1)
        self.controller_title = QLabel("DualSense")
        info.addWidget(self.controller_title)
        self.side_connection = QLabel("● Buscando")
        self.side_connection.setStyleSheet(f"color:{C['muted']};font-size:11px")
        info.addWidget(self.side_connection)
        self.side_battery = QLabel("▣ —")
        self.side_battery.setStyleSheet(f"color:{C['muted']};font-size:11px")
        info.addWidget(self.side_battery)
        status.addLayout(info, 1)
        layout.addWidget(controller)
        return side

    def _set_sidebar_content_visible(self, expanded: bool) -> None:
        self.brand_name.setVisible(expanded)
        self.brand_caption.setVisible(expanded)
        self.version_badge.setVisible(expanded)
        for heading in self.nav_headings:
            heading.setVisible(expanded)
        for nav_button in self.nav_buttons.values():
            if isinstance(nav_button, SidebarNavButton):
                nav_button.set_compact(not expanded)
        self.controller_title.setVisible(expanded)
        self.side_connection.setVisible(expanded)
        self.side_battery.setVisible(expanded)
        logo_size = 48 if expanded else 34
        self.brand_logo.setFixedSize(logo_size, logo_size)
        self.sidebar_toggle.setFixedSize(26 if expanded else 22, 26 if expanded else 22)
        icon = QIcon(str(resource_path("assets/nikaido.svg")))
        pixmap = icon.pixmap(logo_size, logo_size)
        if not pixmap.isNull():
            self.brand_logo.setPixmap(pixmap)
        self.brand_layout.setContentsMargins(*( (14, 14, 14, 14) if expanded else (6, 6, 6, 6) ))
        self.brand_layout.setSpacing(12 if expanded else 2)
        self.sidebar_toggle.setText("‹" if expanded else "›")
        self.sidebar_toggle.setToolTip(tr("Contraer barra lateral" if expanded else "Expandir barra lateral", self.language))

    def set_sidebar_collapsed(
        self,
        collapsed: bool,
        *,
        persist: bool = True,
        animate: bool = True,
    ) -> None:
        collapsed = bool(collapsed)
        target_width = 104 if collapsed else 320
        current_width = self.sidebar.width()
        self._sidebar_collapsed = collapsed

        if self._sidebar_animation is not None:
            self._sidebar_animation.stop()
            self._sidebar_animation.deleteLater()
            self._sidebar_animation = None

        reduce_motion = bool(self._appearance.get("reduce_motion", False))
        should_animate = animate and not reduce_motion and current_width != target_width
        if collapsed:
            self._set_sidebar_content_visible(False)
        elif not should_animate:
            self._set_sidebar_content_visible(True)

        if should_animate:
            animation = QVariantAnimation(self)
            animation.setDuration(180)
            animation.setStartValue(current_width)
            animation.setEndValue(target_width)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation.valueChanged.connect(lambda value: self.sidebar.setFixedWidth(int(value)))

            def finish() -> None:
                self.sidebar.setFixedWidth(target_width)
                if not collapsed:
                    self._set_sidebar_content_visible(True)
                self._sidebar_animation = None

            animation.finished.connect(finish)
            self._sidebar_animation = animation
            animation.start()
        else:
            self.sidebar.setFixedWidth(target_width)

        if persist:
            values = normalize_appearance(self._appearance)
            values["sidebar_collapsed"] = collapsed
            self._appearance = values
            if self.profile_manager:
                self.profile_manager.set_setting("appearance", values)
                self.request_config_save()

    def toggle_sidebar(self) -> None:
        self.set_sidebar_collapsed(not self._sidebar_collapsed)

    def _build_statusbar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("statusbar")
        frame.setFixedHeight(42)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(18, 3, 18, 3)
        layout.setSpacing(12)
        brand_wrap = QHBoxLayout()
        brand_wrap.setSpacing(8)
        brand_icon = QLabel()
        brand_icon.setFixedSize(18, 18)
        icon = QIcon(str(resource_path("assets/nikaido.svg")))
        pixmap = icon.pixmap(18, 18)
        if not pixmap.isNull():
            brand_icon.setPixmap(pixmap)
        else:
            brand_icon.setText("N")
            brand_icon.setStyleSheet("font-weight:800")
        brand_wrap.addWidget(brand_icon)
        brand = QLabel("NIKAIDO")
        brand.setStyleSheet("font-weight:800;letter-spacing:0.4px")
        brand_wrap.addWidget(brand)
        layout.addLayout(brand_wrap)
        self.ready = QLabel("●  Listo.")
        self.ready.setStyleSheet(f"color:{C['green']}")
        layout.addWidget(self.ready)
        self.save_status = QLabel("✓ Guardado")
        self.save_status.setStyleSheet(f"color:{C['muted']};font-size:11px")
        layout.addWidget(self.save_status)
        layout.addStretch()
        self.game_status = label("♜  No se está ejecutando ningún juego", "muted")
        layout.addWidget(self.game_status)
        return frame

    def _connect_backend(self) -> None:
        self.bridge.connected.connect(self._connected)
        self.bridge.disconnected.connect(self._disconnected)
        self.bridge.battery.connect(self._battery)
        self.bridge.profile.connect(self._queue_profile_applied)
        self.bridge.error.connect(self._error)
        self.bridge.show_requested.connect(self.show_window)
        self.bridge.exit_requested.connect(self.exit_app)
        self.bridge.profile_requested.connect(self.apply_profile)
        self.bridge.update_checked.connect(self._update_checked)
        self.bridge.update_progress.connect(self._update_progress)
        self.bridge.update_downloaded.connect(self._update_downloaded)
        manager = self.connection_manager
        if manager:
            self._track_backend_subscription(
                manager.on_connect(
                    lambda connection: self.bridge.connected.emit(connection)
                )
            )
            self._track_backend_subscription(
                manager.on_disconnect(lambda: self.bridge.disconnected.emit())
            )
            self._track_backend_subscription(
                manager.on_battery_change(
                    lambda level_value, status: self.bridge.battery.emit(
                        level_value, status
                    )
                )
            )
            self._track_backend_subscription(
                manager.on_state_update(
                    lambda state: setattr(self, "_pending_state", state)
                )
            )
            self._track_backend_subscription(
                manager.on_error(lambda message: self.bridge.error.emit(message))
            )
            self.call_later(450, self._check_input_backend)
        if self.trigger_engine:
            self._track_backend_subscription(
                self.trigger_engine.on_profile_change(
                    lambda pid: self.bridge.profile.emit(pid)
                )
            )

    def _track_backend_subscription(self, unsubscribe: Any) -> None:
        """Guarda bajas opcionales sin exigirlas a backends antiguos o de terceros."""
        if callable(unsubscribe):
            self._backend_unsubscriptions.append(unsubscribe)

    def _detach_backend_callbacks(self) -> None:
        callbacks, self._backend_unsubscriptions = self._backend_unsubscriptions, []
        for unsubscribe in callbacks:
            try:
                unsubscribe()
            except Exception:
                logger.exception("No se pudo retirar un callback de la interfaz")

    def _check_input_backend(self) -> None:
        manager = self.connection_manager
        if not manager or not hasattr(manager, "get_diagnostics_snapshot"):
            return
        try:
            status = manager.get_diagnostics_snapshot()
        except Exception:
            return
        if status.get("hid_backend_available") and status.get("pydualsense_available"):
            return
        backend = str(status.get("hid_backend") or "no disponible")
        detail = str(
            status.get("pydualsense_import_error")
            or status.get("hid_backend_error")
            or "El lector HID no pudo iniciar"
        )
        self.toast(
            f"El ejecutable no pudo cargar el lector DualSense ({backend}). {detail}",
            "error",
            9000,
        )

    def _ui_tick(self) -> None:
        self._sync_mouse_capture_overlay()
        state = self._pending_state
        if state is not None and state is not self._latest_state:
            self._latest_state = state
            self._sync_controller_summary(state)
            if self._current_page == "dashboard":
                self.dashboard.update_state(state)
            elif self._current_page == "monitor":
                self.monitor_page.update_state(state)
            elif self._current_page == "lights":
                self.lights_page.controller.set_state(state)
        if self._current_page == "input":
            self.input_page.update_live()
        elif self._current_page == "gyro":
            self.gyro_page.update_live()
        elif self._current_page == "mapper":
            self.mapper_page.update_live()
        elif self._current_page == "calibration":
            self.calibration_page.update_live(state)

    def _sync_mouse_capture_overlay(self) -> None:
        """Presenta la cuenta de 5 s y los cambios de Ctrl+M sobre cualquier juego."""
        overlay = getattr(self, "mouse_capture_overlay", None)
        if overlay is None:
            return

        candidates = []
        keybridge = getattr(self, "keyboard_gamepad", None)
        if keybridge is not None:
            try:
                status = keybridge.get_diagnostics_snapshot()
            except Exception:
                status = {}
            configured = bool(status.get("running") and status.get("mouse_enabled"))
            if configured:
                if status.get("mouse_activation_pending"):
                    phase = "countdown"
                elif status.get("mouse_running"):
                    phase = "active"
                elif status.get("mouse_hotkey_paused"):
                    phase = "paused"
                else:
                    phase = "off"
                if phase != "off":
                    candidates.append(
                        (
                            0,
                            "keybridge",
                            "Mouse → Stick",
                            phase,
                            float(status.get("mouse_activation_remaining_seconds", 0.0) or 0.0),
                        )
                    )

        manager = getattr(self, "connection_manager", None)
        emulator = getattr(manager, "emulator", None) if manager else None
        if emulator is not None:
            try:
                status = emulator.get_mouse_to_gyro_status()
            except Exception:
                status = {}
            configured = bool(status.get("configured"))
            if configured:
                if status.get("activation_pending"):
                    phase = "countdown"
                elif status.get("running"):
                    phase = "active"
                elif status.get("hotkey_paused"):
                    phase = "paused"
                else:
                    phase = "off"
                if phase != "off":
                    candidates.append(
                        (
                            1,
                            "gyro",
                            "Mouse → Gyro",
                            phase,
                            float(status.get("activation_remaining_seconds", 0.0) or 0.0),
                        )
                    )

        if not candidates:
            previous_source, previous_phase = self._mouse_capture_overlay_state
            if previous_phase == "countdown":
                overlay.cancel_countdown()
            self._mouse_capture_overlay_state = ("", "off")
            return

        phase_priority = {"countdown": 0, "active": 1, "paused": 2}
        _, source, kind, phase, remaining = min(
            candidates,
            key=lambda item: (phase_priority.get(item[3], 9), item[0]),
        )
        previous = self._mouse_capture_overlay_state
        current = (source, phase)
        if phase == "countdown":
            overlay.show_countdown(kind, remaining)
        elif current != previous:
            overlay.show_state(kind, phase == "active")
        self._mouse_capture_overlay_state = current

    def _system_tick(self) -> None:
        if self._current_page == "dashboard":
            self.dashboard.update_system_metrics()
        elif self._current_page == "monitor":
            self.monitor_page.update_system_metrics()
        elif self._current_page == "automation":
            self.automation_page.refresh_status()
        elif self._current_page == "vibration":
            self.vibration_page.refresh_feedback_status()
        elif self._current_page == "audio":
            self.audio_page.refresh_live()

    def navigate(self, page: str) -> None:
        if page not in self.PAGE_META:
            return
        target = self.ensure_page(page)
        if target is None:
            return
        changed = page != self._current_page
        self._current_page = page
        self.stack.setCurrentWidget(target)
        if hasattr(self, "ui_timer"):
            live_pages = {"monitor", "mapper", "input", "gyro", "lights", "calibration"}
            self.ui_timer.setInterval(33 if page in live_pages else 80)
        title, subtitle = self.page_meta(page)
        self.titlebar.title.setText(title)
        self.titlebar.subtitle.setText(subtitle)
        for key, btn in self.nav_buttons.items():
            btn.setChecked(key == page)
        active_button = self.nav_buttons.get(page)
        if active_button:
            self.nav_scroll.ensureWidgetVisible(active_button, 0, 24)

        if isinstance(target, PageLoadError):
            if changed:
                self._animate_page(target)
            return

        if page == "profiles":
            self.profiles_page.refresh()
        elif page == "automation":
            self.automation_page.refresh()
        elif page == "mapper":
            self.mapper_page.refresh()
            self.mapper_page.update_live()
        elif page == "input":
            self.input_page.refresh_profiles()
            self.input_page.load()
        elif page == "gyro":
            self.gyro_page.load()
            self.gyro_page.update_live()
        elif page == "macros":
            self.macros_page.refresh()
        elif page == "lights":
            self.lights_page.refresh()
            if self._latest_state is not None:
                self.lights_page.controller.set_state(self._latest_state)
        elif page == "vibration":
            self.vibration_page.refresh_profiles()
            self.vibration_page.load()
        elif page == "triggers":
            self.triggers_page.refresh_profiles()
            self.triggers_page.load()
        elif page == "emulation":
            self.emulation_page.refresh()
        elif page == "dashboard" and self._latest_state is not None:
            self.dashboard.update_state(self._latest_state)
        elif page == "monitor":
            if self._latest_state is not None:
                self.monitor_page.update_state(self._latest_state)
            self.monitor_page.update_system_metrics()
        elif page == "calibration":
            self.calibration_page.update_live(self._latest_state)
        elif page == "compatibility":
            self.compatibility_page.refresh()

        if changed:
            self._animate_page(target)

    def _animate_page(self, page: QWidget) -> None:
        if bool(self._appearance.get("reduce_motion", False)):
            if self._page_animation is not None:
                self._page_animation.stop()
            if self._animated_page is not None:
                self._animated_page.setGraphicsEffect(None)
            self._page_animation = None
            self._animated_page = None
            return
        if self._page_animation is not None:
            self._page_animation.stop()
        if self._animated_page is not None:
            self._animated_page.setGraphicsEffect(None)

        effect = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(130)
        animation.setStartValue(0.72)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        def finish() -> None:
            if self._animated_page is page:
                page.setGraphicsEffect(None)
                self._animated_page = None
                self._page_animation = None

        animation.finished.connect(finish)
        self._animated_page = page
        self._page_animation = animation
        animation.start()

    def refresh_profiles(self) -> None:
        engine = self.trigger_engine
        profiles = engine.get_profile_names() if engine else []
        active = engine.get_current_profile() if engine else None
        if not active and self.profile_manager:
            active = self.profile_manager.get_active_profile()
        self.titlebar.set_profiles(profiles, active)
        tray = getattr(self, "tray_manager", None)
        if tray:
            tray.set_profiles(profiles)
            tray.set_current_profile(active)
        self.dashboard.refresh_profile(active)
        if hasattr(self, "mapper_page"):
            self.mapper_page.refresh()
        if hasattr(self, "input_page"):
            self.input_page.refresh_profiles()
        if hasattr(self, "gyro_page"):
            self.gyro_page.load()
        if hasattr(self, "vibration_page"):
            self.vibration_page.refresh_profiles()
        if hasattr(self, "triggers_page"):
            self.triggers_page.refresh_profiles()
        if hasattr(self, "audio_page"):
            self.audio_page.refresh_profiles()

    def apply_profile(self, profile_id: str, force: bool = False) -> None:
        """Aplica una sola vez y difiere la reconstrucción visual al siguiente tick."""
        if not self.trigger_engine or not profile_id or self._profile_apply_in_progress:
            return
        if not force and self.trigger_engine.get_current_profile() == profile_id:
            self._queue_profile_applied(profile_id)
            return
        self._profile_apply_in_progress = True
        try:
            success = self.trigger_engine.apply_profile(profile_id)
            if success and self.profile_manager:
                self.profile_manager.set_active_profile(profile_id)
                self.request_config_save()
            if success:
                self._queue_profile_applied(profile_id)
        finally:
            self._profile_apply_in_progress = False

    def _queue_profile_applied(self, profile_id: str) -> None:
        if not profile_id:
            return
        self._pending_profile_id = profile_id
        if self._profile_apply_scheduled:
            return
        self._profile_apply_scheduled = True
        self.call_later(0, self._flush_profile_applied)

    def _flush_profile_applied(self) -> None:
        self._profile_apply_scheduled = False
        profile_id = self._pending_profile_id
        self._pending_profile_id = None
        if profile_id:
            self._profile_applied(profile_id)

    def _profile_applied(self, profile_id: str) -> None:
        if not profile_id:
            return
        self.titlebar.profile_combo.blockSignals(True)
        index = self.titlebar.profile_combo.findData(profile_id)
        self.titlebar.profile_combo.setCurrentIndex(max(0, index))
        self.titlebar.profile_combo.blockSignals(False)
        self.dashboard.refresh_profile(profile_id)
        if hasattr(self, "profiles_page"):
            self.profiles_page.refresh()
        if hasattr(self, "input_page"):
            self.input_page.refresh_profiles()
        if hasattr(self, "vibration_page"):
            self.vibration_page.refresh_profiles()
            self.vibration_page.select_profile(profile_id)
        if hasattr(self, "triggers_page"):
            self.triggers_page.refresh_profiles()
            self.triggers_page.select_profile(profile_id)
        if hasattr(self, "lights_page"):
            self.lights_page.refresh()
        if hasattr(self, "audio_page"):
            self.audio_page.refresh_profiles()
            self.audio_page.select_profile(profile_id)
        if hasattr(self, "macros_page"):
            self.macros_page.refresh()

    def _sync_controller_summary(self, state: Any) -> None:
        """Mantiene la tarjeta lateral correcta aunque un evento inicial se pierda."""
        connected = bool(getattr(state, "connected", False))
        connection = getattr(state, "connection_type", None)
        value = getattr(connection, "value", str(connection or "unknown")).upper()
        if connected:
            expected = f"● {tr('Conectado', self.language)} · {value}"
            if self.side_connection.text() != expected:
                self.side_connection.setText(expected)
                self.side_connection.setStyleSheet(f"color:{C['green']};font-size:11px")
            battery_valid = bool(getattr(state, "battery_valid", False))
            charging_status = getattr(state, "charging_status", None)
            if battery_valid:
                level_value = max(0, min(100, int(getattr(state, "battery_level", 0) or 0)))
                if (
                    level_value != self._last_battery
                    or charging_status != self._last_charging_status
                ):
                    self._battery(level_value, charging_status)
            elif self._last_battery is not None or self.side_battery.text() != "▣ —":
                self._last_battery = None
                self._last_charging_status = None
                self.side_battery.setText("▣ —")
                if hasattr(self, "dashboard"):
                    self.dashboard.clear_battery(connected=True)
        elif self.side_connection.text() != tr("● Buscando", self.language):
            self.side_connection.setText(tr("● Buscando", self.language))
            self.side_connection.setStyleSheet(f"color:{C['muted']};font-size:11px")

    def _connected(self, connection: Any) -> None:
        value = getattr(connection, "value", str(connection)).upper()
        self.side_connection.setText(f"● {tr('Conectado', self.language)} · {value}")
        self.side_connection.setStyleSheet(f"color:{C['green']};font-size:11px")
        self.ready.setText(tr("●  Control conectado", self.language))
        self.toast({"es": f"DualSense conectado por {value}", "en": f"DualSense connected through {value}", "pt_BR": f"DualSense conectado por {value}"}.get(self.language, f"DualSense conectado por {value}"))

    def _disconnected(self) -> None:
        self.side_connection.setText(tr("● Buscando", self.language))
        self.side_connection.setStyleSheet(f"color:{C['muted']};font-size:11px")
        self.side_battery.setText("▣ —")
        self._last_battery = None
        self._last_charging_status = None
        if hasattr(self, "dashboard"):
            self.dashboard.clear_battery(connected=False)
        self.ready.setText(tr("●  Esperando control", self.language))

    def _battery(self, level_value: int, status: Any) -> None:
        self._last_battery = level_value
        self._last_charging_status = status
        if not self.connection_manager or not self.connection_manager.is_connected:
            self.side_battery.setText("▣ —")
            if hasattr(self, "dashboard"):
                self.dashboard.clear_battery(connected=False)
            return
        self.side_battery.setText(f"▣ {level_value}%")
        self.dashboard.update_battery(level_value, status)
        if hasattr(self, "monitor_page"):
            self.monitor_page.update_battery(level_value)

    def _error(self, message: str) -> None:
        if message:
            self.ready.setText(tr("●  Error", self.language))
            self.alert(message)

    def save_setting(self, key: str, value: Any) -> None:
        if self.profile_manager:
            self.profile_manager.set_setting(key, value)
            self.request_config_save()
        if key == "start_with_windows" and hasattr(self, "settings_page"):
            self.settings_page.configure_startup(bool(value))

    def request_config_save(self, delay: int = 280) -> None:
        if not self.profile_manager or self._stopping:
            return
        if hasattr(self, "save_status"):
            self.save_status.setText(tr("● Cambios pendientes", self.language))
            self.save_status.setStyleSheet(f"color:{C['yellow']};font-size:11px")
        self.config_save_timer.start(max(0, int(delay)))

    def flush_config_save(self) -> None:
        if not self.profile_manager:
            return
        self.config_save_timer.stop()
        saved = bool(self.profile_manager.save_config())
        if hasattr(self, "save_status"):
            self.save_status.setText(tr("✓ Guardado" if saved else "! Error al guardar", self.language))
            self.save_status.setStyleSheet(
                f"color:{C['muted'] if saved else C['danger']};font-size:11px"
            )
        if not saved and not self._stopping:
            self.toast(tr("No se pudo guardar la configuración. Revisa el diagnóstico.", self.language), "error", 5200)

    def _schedule_geometry_save(self) -> None:
        if not self._stopping and not self.isMaximized() and not self.isMinimized():
            self.geometry_save_timer.start(450)

    def _save_geometry(self) -> None:
        if not self.profile_manager or self.isMaximized() or self.isMinimized():
            return
        self.profile_manager.save_window_geometry(
            self.width(), self.height(), self.x(), self.y()
        )
        self.request_config_save()

    def toast(self, message: str, level: str = "success", duration: int = 3500) -> None:
        self.ready.setText(f"●  {message}")
        self.status_reset_timer.start(max(1200, int(duration)))
        if hasattr(self, "toast_overlay"):
            self.toast_overlay.show_message(message, level, duration)

    def alert(self, message: str) -> None:
        self.toast(message, "error", 5200)

    def apply_appearance_preset(self, preset_id: str) -> None:
        preset = APPEARANCE_PRESETS.get(str(preset_id))
        if not preset:
            return
        values = normalize_appearance(
            self.profile_manager.get_setting("appearance", {})
            if self.profile_manager else self._appearance
        )
        values.update({key: value for key, value in preset.items() if key != "name"})
        values = normalize_appearance(values)
        if self.profile_manager:
            self.profile_manager.set_setting("appearance", values)
            self.request_config_save()
        self.apply_appearance(values)
        settings_page = getattr(self, "settings_page", None)
        if settings_page is not None:
            settings_page._load_appearance_controls(values)
            settings_page.refresh_appearance_preview()
        self.toast(f"Apariencia {preset['name']} aplicada", "success")

    def show_command_palette(self) -> None:
        if hasattr(self, "command_palette"):
            self.command_palette.show_palette()

    def toggle_dim(self) -> None:
        self.toast("Tema oscuro Nikaido activo", "info")

    def toggle_maximize(self) -> None:
        self.showNormal() if self.isMaximized() else self.showMaximized()

    def call_later(self, ms: int, callback: Callable[[], None]) -> None:
        """Programa trabajo Qt ligado a la vida de esta ventana.
        ``QTimer.singleShot`` con un método Python conserva la ventana aunque
        esta ya se haya cerrado. Un timer hijo permite cancelarlo de forma
        determinista y contiene cualquier excepción de un callback diferido.
        """
        if self._stopping or not callable(callback):
            return
        timer = QTimer(self)
        timer.setSingleShot(True)
        self._deferred_timers.append(timer)

        def run() -> None:
            try:
                if not self._stopping:
                    callback()
            except Exception:
                logger.exception("Error en una acción diferida de la interfaz")
                if not self._stopping:
                    self.alert("Una acción de la interfaz no pudo completarse")
            finally:
                if timer in self._deferred_timers:
                    self._deferred_timers.remove(timer)
                timer.deleteLater()

        timer.timeout.connect(run)
        timer.start(max(0, int(ms)))

    def request_minimize(self) -> None:
        """Minimiza o libera por completo la interfaz conservando los motores."""
        tray = getattr(self, "tray_manager", None)
        use_tray = bool(
            not self._stopping
            and self.profile_manager
            and self.profile_manager.get_setting("minimize_to_tray", True)
            and tray
            and getattr(tray, "is_visible", lambda: False)()
        )
        if not use_tray:
            self.showMinimized()
            return

        low_profile = bool(
            self.profile_manager.get_setting("low_profile_on_minimize", True)
        )
        low_profile_handler = getattr(self, "low_profile_handler", None)
        if low_profile and callable(low_profile_handler):
            self.ready.setText(tr("●  Activando Low Profile…", self.language))
            # La destrucción se agenda fuera de la señal del botón para evitar
            # eliminar widgets mientras Qt todavía recorre su callback.
            low_profile_handler()
            return

        self.ready.setText(tr("●  Nikaido sigue activo en la bandeja", self.language))
        self.hide()
        notify = getattr(tray, "notify_minimized", None)
        if callable(notify):
            notify()

    def request_close(self) -> None:
        """El botón cerrar siempre termina Nikaido y libera sus procesos."""
        self.exit_app()

    def _persist_before_close(self) -> List[Exception]:
        errors: List[Exception] = []
        for label_name, callback in (
            ("geometría", self._save_geometry),
            ("configuración", self.flush_config_save),
        ):
            try:
                callback()
            except Exception as exc:
                logger.exception("No se pudo guardar %s al cerrar", label_name)
                errors.append(exc)
        return errors

    def exit_app(self) -> None:
        if self._stopping:
            return
        if hasattr(self, "mouse_capture_overlay"):
            self.mouse_capture_overlay.hide()
        errors = self._persist_before_close()
        self._stopping = True
        callbacks, self._on_close = list(self._on_close), []
        for callback in callbacks:
            try:
                callback()
            except Exception as exc:
                logger.exception("Error durante el cierre de Nikaido")
                errors.append(exc)
        app = QApplication.instance()
        if app is not None:
            app.quit()
        if errors and not self._cleanup_started:
            self.ready.setText(tr("●  Cierre completado con avisos", self.language))
        if not self._cleanup_started:
            self.stop()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._stopping:
            event.accept()
        else:
            event.ignore()
            self.request_close()

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        if hasattr(self, "size_grip"):
            self.size_grip.move(
                self.centralWidget().width() - 20, self.centralWidget().height() - 20
            )
        if hasattr(self, "toast_overlay"):
            self.toast_overlay.reposition()
        if getattr(self, "_assistant_tip_visible", False):
            self._position_assistant_card()
        if hasattr(self, "profiles_page"):
            self.profiles_page.schedule_responsive_refresh()
        self._schedule_geometry_save()

    def moveEvent(self, event: Any) -> None:
        super().moveEvent(event)
        self._schedule_geometry_save()

    def changeEvent(self, event: Any) -> None:
        super().changeEvent(event)
        minimized = event.type() == QEvent.Type.WindowStateChange and self.windowState() & Qt.WindowState.WindowMinimized
        if minimized and getattr(self, "_assistant_tip_visible", False):
            self.hide_assistant_tip()
        elif minimized:
            stop_tip_sound()

    def hideEvent(self, event: Any) -> None:
        super().hideEvent(event)
        stop_tip_sound()

    def hide_window(self) -> None:
        self.hide()

    def show_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self.call_later(350, self.maybe_show_welcome_wizard)

    ASSISTANT_TIPS = ASSISTANT_TIP_LIBRARY

    def is_assistant_enabled(self) -> bool:
        pm = self.profile_manager
        return bool(pm and pm.get_setting("assistant.enabled", False))

    def set_assistant_enabled(self, enabled: bool, *, persist: bool = True) -> None:
        enabled = bool(enabled)
        if persist and self.profile_manager:
            self.profile_manager.set_setting("assistant.enabled", enabled)
            self.profile_manager.set_setting("assistant.choice_made", True)
            self.profile_manager.set_setting("assistant.tips_enabled", enabled)
            self.request_config_save()
        if not hasattr(self, "assistant_timer"):
            return
        if enabled:
            self.assistant_timer.start(45_000)
        else:
            self.assistant_timer.stop()
            self.hide_assistant_tip(clear=True)

    def _take_assistant_tip(self) -> tuple[str, str, str, str, str, str]:
        """Toma un consejo de una bolsa mezclada sin repetir hasta agotarla."""
        if not self.profile_manager:
            tip = self.ASSISTANT_TIPS[self._assistant_tip_index % len(self.ASSISTANT_TIPS)]
            self._assistant_tip_index += 1
            return tip

        last_id = str(self.profile_manager.get_setting("assistant.last_tip_id", "") or "")
        raw_remaining = self.profile_manager.get_setting("assistant.tip_remaining", [])
        tip, remaining = take_assistant_tip(raw_remaining, last_id)
        self.profile_manager.set_setting("assistant.tip_remaining", remaining)
        self.profile_manager.set_setting("assistant.last_tip_id", tip[0])
        self.request_config_save()
        return tip

    def show_next_assistant_tip(self) -> None:
        if (
            self._stopping
            or not self.is_assistant_enabled()
            or not self.isVisible()
            or self.isMinimized()
            or self._welcome_wizard is not None
        ):
            if self.is_assistant_enabled() and not self._stopping:
                self.assistant_timer.start(120_000)
            return
        tips_enabled = bool(
            self.profile_manager
            and self.profile_manager.get_setting("assistant.tips_enabled", True)
        )
        if not tips_enabled:
            return
        tip_id, pose, title, message, destination, action = self._take_assistant_tip()
        self.assistant_card.set_tip(
            pose,
            tr(title, self.language),
            tr(message, self.language),
            destination,
            tr(action, self.language),
        )
        self._position_assistant_card()
        self.assistant_card.show()
        self.assistant_card.raise_()
        self._assistant_tip_visible = True
        if (
            self.profile_manager
            and self.profile_manager.get_setting("assistant.tip_sounds_enabled", True)
            and window_is_in_front(self)
        ):
            play_tip_sound()
        self.call_later(22_000, self._hide_assistant_tip_if_same_session)

    def _hide_assistant_tip_if_same_session(self) -> None:
        if self._assistant_tip_visible:
            self.hide_assistant_tip()

    def hide_assistant_tip(self, *, clear: bool = False) -> None:
        stop_tip_sound()
        if hasattr(self, "assistant_card"):
            self.assistant_card.hide()
            if clear:
                self.assistant_card.clear_resources()
        self._assistant_tip_visible = False
        if (
            hasattr(self, "assistant_timer")
            and self.is_assistant_enabled()
            and not self._stopping
        ):
            minutes = int(
                self.profile_manager.get_setting("assistant.tip_interval_minutes", 12)
                if self.profile_manager else 12
            )
            self.assistant_timer.start(max(5, min(minutes, 60)) * 60_000)

    def _open_assistant_destination(self, destination: str) -> None:
        self.hide_assistant_tip()
        if destination == "dashboard":
            self.navigate("dashboard")
        else:
            self.navigate(destination)

    def _position_assistant_card(self) -> None:
        if not hasattr(self, "assistant_card"):
            return
        card = self.assistant_card
        card.adjustSize()
        parent = self.centralWidget()
        margin = 22
        x = max(margin, parent.width() - card.width() - margin)
        y = max(margin, parent.height() - card.height() - 46)
        card.move(x, y)

    def maybe_show_welcome_wizard(self) -> None:
        if self._stopping or not self.isVisible() or self._welcome_prompted:
            return
        pm = self.profile_manager
        completed = bool(pm and pm.get_setting("onboarding.completed", False))
        version = int(pm.get_setting("onboarding.version", 0) if pm else 0)
        if completed and version >= ONBOARDING_VERSION:
            self._welcome_prompted = True
            return
        self.show_welcome_wizard(force=False)

    def show_welcome_wizard(self, *, force: bool = False) -> None:
        if self._stopping:
            return
        existing = self._welcome_wizard
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return
        self._welcome_prompted = True
        # Importar el wizard solo cuando realmente se mostrará evita cargar la
        # pantalla completa de Ajustes en cada inicio normal.
        from .pages.settings import WelcomeWizard

        wizard = WelcomeWizard(self, forced=force)
        self._welcome_wizard = wizard
        wizard.finished.connect(self._welcome_wizard_finished)
        wizard.destroyed.connect(self._welcome_wizard_destroyed)
        wizard.show()
        wizard.raise_()
        wizard.activateWindow()

    def _welcome_wizard_finished(self, _result: int) -> None:
        self._welcome_wizard = None

    def _welcome_wizard_destroyed(self, *_args: Any) -> None:
        self._welcome_wizard = None
        # El diálogo ya soltó los buffers Qt; esta pasada elimina ciclos Python
        # sin mantener el proceso detenido durante la navegación normal.
        self.call_later(0, gc.collect)

    def on_close(self, callback: Callable[[], None]) -> None:
        self._on_close.append(callback)

    def stop(self) -> None:
        if self._cleanup_started:
            return
        self._cleanup_started = True
        if not self._stopping:
            self._persist_before_close()
        self._stopping = True
        self._detach_backend_callbacks()
        self._on_close.clear()

        for timer in list(self.findChildren(QTimer)):
            try:
                timer.stop()
            except RuntimeError:
                pass
        for timer in self._deferred_timers:
            try:
                timer.deleteLater()
            except RuntimeError:
                pass
        self._deferred_timers.clear()

        for animation_name in ("_page_animation", "_sidebar_animation"):
            animation = getattr(self, animation_name, None)
            if animation is not None:
                try:
                    animation.stop()
                except RuntimeError:
                    pass
                setattr(self, animation_name, None)
        if self._animated_page is not None:
            try:
                self._animated_page.setGraphicsEffect(None)
            except RuntimeError:
                pass
            self._animated_page = None

        if hasattr(self, "assistant_card"):
            try:
                self.assistant_card.clear_resources()
                self.assistant_card.hide()
            except RuntimeError:
                pass
        for widget_name in ("mouse_capture_overlay", "_welcome_wizard", "command_palette"):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                try:
                    widget.close()
                    widget.deleteLater()
                except RuntimeError:
                    pass
            if widget_name == "_welcome_wizard":
                self._welcome_wizard = None
        self.close()
        self.deleteLater()


class DualSenseGUI(LowProfileGuiRuntime):
    """Adaptador estable con Low Profile y reconstrucción de interfaz."""

    def __init__(self, **backends: Any) -> None:
        super().__init__(NikaidoWindow, backends)

