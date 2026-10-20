"""WelcomeWizard, SettingsPage extraídos de la antigua interfaz monolítica."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nikaido_version import ONBOARDING_VERSION
from nikaido_version import APP_VERSION, RELEASE_STAGE


from ..ui_common import (
    logging,
    ACCENT_PALETTES,
    APPEARANCE_PRESETS,
    Any,
    DEFAULT_APPEARANCE,
    Dict,
    List,
    Optional,
    Path,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QIcon,
    QLabel,
    QMessageBox,
    QProgressBar,
    QScrollArea,
    QStackedWidget,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
    button,
    card,
    label,
    normalize_appearance,
    os,
    resource_path,
    sys,
)
from ..components import AppearancePreview, MascotPanel, ScrollPage, SliderRow
from ..wallpaper_gallery import WallpaperGallery
from src.wallpapers import find_wallpaper
from ..i18n import LANGUAGE_OPTIONS, normalize_language, tr, translate_widget_tree

if TYPE_CHECKING:
    from ..main_window import NikaidoWindow

logger = logging.getLogger(__name__)


class AssistantChoiceDialog(QDialog):
    """Pregunta final del wizard para activar o rechazar a Nikaido."""

    def __init__(self, window: "NikaidoWindow") -> None:
        super().__init__(window)
        self.window = window
        self.choice: Optional[bool] = None
        self.setObjectName("assistantChoiceDialog")
        self.setWindowTitle("Nikaido como asistente")
        self.setModal(True)
        self.setMinimumSize(760, 520)
        self.resize(820, 560)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)
        self.mascot = MascotPanel()
        self.mascot.setMaximumWidth(760)
        self.mascot.set_scene(
            "neutral",
            "¿Quieres a Nikaido como tu asistente?",
            "Puedo mostrarte consejos ocasionales, funciones poco visibles y accesos rápidos. No interrumpiré tus juegos y podrás desactivarme después.",
            badge="ASISTENTE",
        )
        root.addWidget(self.mascot, 1, Qt.AlignmentFlag.AlignCenter)

        self.actions = QWidget()
        actions = QHBoxLayout(self.actions)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.addStretch()
        no_button = button("No, gracias", lambda: self._choose(False))
        yes_button = button("Sí, acompáñame", lambda: self._choose(True), primary=True)
        actions.addWidget(no_button)
        actions.addWidget(yes_button)
        actions.addStretch()
        root.addWidget(self.actions)
        self.finished.connect(lambda _result: self.mascot.clear_resources())
        self._accept_timer = QTimer(self)
        self._accept_timer.setSingleShot(True)
        self._accept_timer.timeout.connect(self.accept)
        translate_widget_tree(self, getattr(window, "language", "es"))

    def _choose(self, enabled: bool) -> None:
        if self.choice is not None:
            return
        self.choice = bool(enabled)
        pm = self.window.profile_manager
        if pm:
            pm.set_setting("assistant.enabled", self.choice)
            pm.set_setting("assistant.choice_made", True)
            pm.set_setting("assistant.tips_enabled", self.choice)
            self.window.request_config_save(0)
            self.window.flush_config_save()
        self.actions.setEnabled(False)
        self.actions.hide()
        if self.choice:
            self.mascot.set_scene(
                "happy",
                tr("¡Sí! Prometo no ser castrosa", self.window.language),
                tr("Te mostraré consejos útiles de vez en cuando. Puedes cerrarlos, cambiar su frecuencia o desactivarme desde Ajustes.", self.window.language),
                badge=tr("ACTIVADA", self.window.language),
            )
        else:
            self.mascot.set_scene(
                "worried",
                tr("¿Por qué? 😭", self.window.language),
                tr("Está bien... abriré Nikaido sin asistente. Si después cambias de opinión, podrás activarme desde Ajustes.", self.window.language),
                badge=tr("DESACTIVADA", self.window.language),
            )
        self._accept_timer.start(1350)

    def reject(self) -> None:
        if self.choice is None:
            self._choose(False)
            return
        super().reject()


class WelcomeWizard(QDialog):
    """Asistente inicial de Nikaido con ajustes rápidos y accesos guiados."""

    LANGUAGE_STEP = 0
    CONNECTION_STEP = 2
    APPEARANCE_STEP = 5

    STEPS = (
        ("Idioma / Language / Idioma", "Elige cómo quieres ver Nikaido"),
        ("Bienvenida", "Descubre la idea general de Nikaido"),
        ("Conexión", "Control, ventana y bandeja"),
        ("Perfiles y Nexus", "Capas, acciones y perfiles .Nika"),
        ("Gyro, KeyBridge y macros", "Movimiento, teclado virtual y automatizaciones"),
        ("Apariencia", "Fondo, acento y densidad"),
        ("Listo", "Elige por dónde comenzar"),
    )

    MASCOT_SCENES = (
        (
            "neutral",
            "Primero, elige tu idioma",
            "Esta decisión configura todo Nikaido. Podrás cambiarla después desde Ajustes.",
            "IDIOMA",
        ),
        (
            "greeting",
            "¡Hola! Soy Nikaido",
            "Te acompañaré durante este recorrido para que dejes tu DualSense listo sin perderte entre ajustes.",
            "BIENVENIDA",
        ),
        (
            "present_left",
            "Primero, conectemos tu control",
            "USB ofrece la ruta más directa. Bluetooth también funciona y Nikaido te mostrará el estado en tiempo real.",
            "CONEXIÓN",
        ),
        (
            "point_left",
            "Aquí empieza la magia",
            "Los perfiles .Nika guardan tus ajustes y Nexus te deja cambiar botones, capas, gestos y acciones.",
            "PERFILES",
        ),
        (
            "thinking",
            "Elige solo lo que necesites",
            "Gyro, KeyBridge y macros son herramientas potentes. Puedes configurarlas después sin activar nada a la fuerza.",
            "HERRAMIENTAS",
        ),
        (
            "happy",
            "Haz que Nikaido se sienta tuyo",
            "Prueba colores, densidad y fondos. La vista previa se aplica al instante y puedes regresar sin guardar.",
            "APARIENCIA",
        ),
        (
            "celebrating",
            "¡Todo listo!",
            "Tus ajustes quedarán guardados. Elige una sección y yo te llevaré directamente ahí.",
            "COMPLETADO",
        ),
    )

    def __init__(self, window: "NikaidoWindow", *, forced: bool = False) -> None:
        super().__init__(window)
        self.window = window
        self.forced = bool(forced)
        self._language = normalize_language(
            window.profile_manager.get_setting("language", "es")
            if window.profile_manager else getattr(window, "language", "es")
        )
        self._index = 0
        pm = window.profile_manager
        self._requires_language_choice = not bool(
            pm and pm.get_setting("onboarding.completed", False)
        )
        self._language_confirmed = not self._requires_language_choice
        self._finishing = False
        self._original_appearance = normalize_appearance(
            window.profile_manager.get_setting("appearance", {})
            if window.profile_manager else {}
        )
        self._appearance = dict(self._original_appearance)
        self._destination: Optional[str] = None

        self.setObjectName("welcomeWizard")
        self.setWindowTitle("Bienvenido a Nikaido")
        self.setModal(True)
        self.setMinimumSize(1120, 700)
        self.resize(1240, 760)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        # QDialog.accept() normalmente solo oculta el widget. El wizard contiene
        # varias páginas, un fondo y sprites, así que debe destruirse al cerrar.
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.finished.connect(self._release_resources)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setObjectName("wizardHeader")
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(24, 18, 20, 18)
        header_row.setSpacing(12)
        logo = QLabel()
        logo.setFixedSize(46, 46)
        pixmap = QIcon(str(resource_path("assets/nikaido.svg"))).pixmap(46, 46)
        if not pixmap.isNull():
            logo.setPixmap(pixmap)
        else:
            logo.setText("N")
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_row.addWidget(logo)
        heading = QVBoxLayout()
        heading.setSpacing(1)
        brand = QLabel("NIKAIDO")
        brand.setObjectName("wizardBrand")
        heading.addWidget(brand)
        tagline = label("Configura lo esencial y conoce las herramientas principales.", "muted")
        heading.addWidget(tagline)
        header_row.addLayout(heading, 1)
        self.header_language = QLabel(dict(LANGUAGE_OPTIONS).get(self._language, "Español"))
        self.header_language.setProperty("languageBadge", True)
        self.header_language.setProperty("i18nSkipText", True)
        header_row.addWidget(self.header_language)
        self.skip_button = button("Omitir por ahora", self.skip)
        self.skip_button.setToolTip("Marca el asistente como completado sin cambiar tus ajustes")
        header_row.addWidget(self.skip_button)
        root.addWidget(header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        rail = QFrame()
        rail.setObjectName("wizardRail")
        rail.setFixedWidth(248)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(16, 22, 16, 18)
        rail_layout.setSpacing(8)
        rail_layout.addWidget(label("RECORRIDO", "eyebrow"))
        self.step_labels: List[QLabel] = []
        for number, (title, subtitle) in enumerate(self.STEPS, start=1):
            item = QLabel(f"{number:02d}   {title}\n       {subtitle}")
            item.setProperty("wizardStep", True)
            item.setWordWrap(True)
            item.setMinimumHeight(58)
            self.step_labels.append(item)
            rail_layout.addWidget(item)
        rail_layout.addStretch()
        hint = label("Puedes abrir este recorrido otra vez desde Ajustes.", "muted")
        hint.setWordWrap(True)
        rail_layout.addWidget(hint)
        body.addWidget(rail)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(28, 24, 28, 20)
        content_layout.setSpacing(16)
        self.page_title = QLabel()
        self.page_title.setObjectName("wizardTitle")
        content_layout.addWidget(self.page_title)
        self.page_subtitle = label("", "muted")
        self.page_subtitle.setWordWrap(True)
        content_layout.addWidget(self.page_subtitle)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_language_page())
        self.stack.addWidget(self._build_welcome_page())
        self.stack.addWidget(self._build_connection_page())
        self.stack.addWidget(self._build_nexus_page())
        self.stack.addWidget(self._build_gyro_page())
        self.stack.addWidget(self._build_appearance_page())
        self.stack.addWidget(self._build_finish_page())

        workspace = QHBoxLayout()
        workspace.setSpacing(16)
        workspace.addWidget(self.stack, 1)
        self.mascot_panel = MascotPanel()
        workspace.addWidget(self.mascot_panel)
        content_layout.addLayout(workspace, 1)

        footer = QHBoxLayout()
        footer.setSpacing(10)
        self.back_button = button("‹  Atrás", self.previous)
        footer.addWidget(self.back_button)
        self.progress = QProgressBar()
        self.progress.setRange(1, len(self.STEPS))
        self.progress.setTextVisible(False)
        self.progress.setMaximumWidth(230)
        footer.addWidget(self.progress)
        self.progress_text = label("", "muted")
        footer.addWidget(self.progress_text)
        footer.addStretch()
        self.next_button = button("Siguiente  ›", self.next, primary=True)
        self.next_button.setMinimumWidth(150)
        footer.addWidget(self.next_button)
        content_layout.addLayout(footer)
        body.addWidget(content, 1)
        root.addLayout(body, 1)

        self.connection_timer = QTimer(self)
        self.connection_timer.setInterval(700)
        self.connection_timer.timeout.connect(self._refresh_connection_status)
        translate_widget_tree(self, self._language)
        self._update_page()

    def _build_language_page(self) -> QWidget:
        area, layout = self._scroll_page()
        hero = card()
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(26, 24, 26, 24)
        hero_layout.setSpacing(8)
        eyebrow = QLabel("LANGUAGE · IDIOMA")
        eyebrow.setProperty("role", "eyebrow")
        hero_layout.addWidget(eyebrow)
        title = QLabel("Choose your language · Elige tu idioma · Escolha seu idioma")
        title.setObjectName("wizardHero")
        title.setWordWrap(True)
        hero_layout.addWidget(title)
        detail = QLabel("This first choice cannot be skipped. Esta primera elección no se puede omitir. Esta primeira escolha não pode ser ignorada.")
        detail.setProperty("muted", True)
        detail.setWordWrap(True)
        hero_layout.addWidget(detail)
        layout.addWidget(hero)

        choices = QGridLayout()
        choices.setSpacing(14)
        self.language_choice_buttons: Dict[str, Any] = {}
        descriptions = {
            "es": "Español\nInterfaz y consejos en español",
            "en": "English\nInterface and tips in English",
            "pt_BR": "Português (Brasil)\nInterface e dicas em português",
        }
        for column, (code, _native_name) in enumerate(LANGUAGE_OPTIONS):
            choice = button(
                descriptions[code],
                lambda _checked=False, language=code: self._select_wizard_language(language),
            )
            choice.setCheckable(True)
            choice.setProperty("languageChoice", True)
            choice.setProperty("i18nSkipText", True)
            choice.setMinimumHeight(112)
            choice.setAccessibleName(descriptions[code].split("\n", 1)[0])
            self.language_choice_buttons[code] = choice
            choices.addWidget(choice, 0, column)
        layout.addLayout(choices)

        note = self._feature_card(
            "✓",
            "Tu elección se guarda para todo Nikaido",
            "También podrás cambiar el idioma al instante desde Ajustes, sin reiniciar el programa.",
        )
        layout.addWidget(note)
        layout.addStretch()
        if self._language_confirmed:
            self._mark_language_choice(self._language)
        return area

    def _mark_language_choice(self, code: str) -> None:
        for language, choice in getattr(self, "language_choice_buttons", {}).items():
            choice.setChecked(language == code)

    def _select_wizard_language(self, code: str) -> None:
        code = normalize_language(code)
        self._language_confirmed = True
        self._language = self.window.set_language(code, persist=True)
        pm = self.window.profile_manager
        if pm:
            pm.set_setting("onboarding.language_confirmed", True)
            self.window.request_config_save()
        self._mark_language_choice(code)
        self.header_language.setText(dict(LANGUAGE_OPTIONS).get(code, code))
        translate_widget_tree(self, self._language)
        self._refresh_step_labels()
        self._update_page()

    def _refresh_step_labels(self) -> None:
        for index, item in enumerate(self.step_labels):
            title, subtitle = self.STEPS[index]
            item.setText(
                f"{index + 1:02d}   {tr(title, self._language)}\n"
                f"       {tr(subtitle, self._language)}"
            )

    def _feature_card(self, icon: str, title: str, description: str) -> QFrame:
        panel = card(sub=True)
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(14, 13, 14, 13)
        layout.setSpacing(12)
        badge = QLabel(icon)
        badge.setObjectName("wizardFeatureIcon")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(38, 38)
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        copy_layout = QVBoxLayout()
        copy_layout.setSpacing(2)
        copy_layout.addWidget(label(title, "heading"))
        detail = label(description, "muted")
        detail.setWordWrap(True)
        copy_layout.addWidget(detail)
        layout.addLayout(copy_layout, 1)
        return panel

    def _scroll_page(self) -> tuple[QScrollArea, QVBoxLayout]:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 2, 8, 4)
        layout.setSpacing(12)
        area.setWidget(body)
        return area, layout

    def _build_welcome_page(self) -> QWidget:
        area, layout = self._scroll_page()
        hero = card()
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(22, 20, 22, 20)
        hero_layout.setSpacing(10)
        eyebrow = label("TU DUALSENSE, A TU MANERA", "eyebrow")
        hero_layout.addWidget(eyebrow)
        title = QLabel("Nikaido reúne perfiles, gyro, macros, luces y emulación en un solo lugar.")
        title.setObjectName("wizardHero")
        title.setWordWrap(True)
        hero_layout.addWidget(title)
        detail = label(
            "Este recorrido tarda menos de dos minutos. Puedes dejar todo como está o ajustar lo esencial antes de comenzar.",
            "muted",
        )
        detail.setWordWrap(True)
        hero_layout.addWidget(detail)
        layout.addWidget(hero)
        grid = QGridLayout()
        grid.setSpacing(10)
        features = (
            ("◇", "Perfiles .Nika", "Guarda configuración, macros, gyro, RGB y más en un solo archivo."),
            ("◉", "Gyro preciso", "Passthrough DS4, Mouse → Gyro y Flick Stick por perfil."),
            ("⌘", "Nikaido Nexus", "Capas, gestos, combinaciones y acciones visuales."),
            ("✦", "Apariencia Studio", "Fondos, transparencias, densidad y colores de acento."),
        )
        for index, values in enumerate(features):
            grid.addWidget(self._feature_card(*values), index // 2, index % 2)
        layout.addLayout(grid)
        layout.addWidget(
            self._feature_card(
                "N",
                "Una guía que sí ayuda",
                "Nikaido cambia de pose y explicación según el paso. Más adelante también podrá mostrar avisos y consejos dentro del programa.",
            )
        )
        layout.addStretch()
        return area

    def _build_connection_page(self) -> QWidget:
        area, layout = self._scroll_page()
        intro = self._feature_card(
            "USB",
            "Conexión y comportamiento de ventana",
            "Nikaido detecta USB o Bluetooth y mantiene la ruta de entrada activa solo cuando corresponde.",
        )
        layout.addWidget(intro)

        status = QFrame()
        status.setObjectName("wizardConnectionStatus")
        status_row = QHBoxLayout(status)
        status_row.setContentsMargins(16, 13, 16, 13)
        status_copy = QVBoxLayout()
        status_copy.setSpacing(2)
        self.wizard_connection_value = QLabel("Buscando DualSense…")
        self.wizard_connection_value.setObjectName("wizardConnectionValue")
        status_copy.addWidget(self.wizard_connection_value)
        self.wizard_connection_detail = label(
            "Conecta el control por USB o Bluetooth para verificarlo.", "muted"
        )
        self.wizard_connection_detail.setWordWrap(True)
        status_copy.addWidget(self.wizard_connection_detail)
        status_row.addLayout(status_copy, 1)
        status_row.addWidget(button("Buscar ahora", self._request_connection, primary=True))
        layout.addWidget(status)

        settings = card()
        form = QVBoxLayout(settings)
        form.setContentsMargins(18, 16, 18, 16)
        form.setSpacing(11)
        form.addWidget(label("AJUSTES RÁPIDOS", "eyebrow"))
        pm = self.window.profile_manager
        self.wizard_auto_connect = QCheckBox("Conectar automáticamente al abrir Nikaido")
        self.wizard_auto_connect.setChecked(bool(pm and pm.get_setting("auto_connect", True)))
        self.wizard_start_minimized = QCheckBox("Iniciar Nikaido minimizado")
        self.wizard_start_minimized.setChecked(bool(pm and pm.get_setting("start_minimized", False)))
        self.wizard_minimize_to_tray = QCheckBox("El botón minimizar (−) envía Nikaido a la bandeja")
        self.wizard_minimize_to_tray.setChecked(bool(pm and pm.get_setting("minimize_to_tray", True)))
        self.wizard_low_profile = QCheckBox("Liberar la interfaz al minimizar (Low Profile)")
        self.wizard_low_profile.setChecked(bool(pm and pm.get_setting("low_profile_on_minimize", True)))
        for widget in (
            self.wizard_auto_connect,
            self.wizard_start_minimized,
            self.wizard_minimize_to_tray,
            self.wizard_low_profile,
        ):
            form.addWidget(widget)
        notice = label(
            "Low Profile libera la ventana al minimizar; el control, la emulación y tus ajustes siguen activos en la bandeja.",
            "muted",
        )
        notice.setWordWrap(True)
        form.addWidget(notice)
        layout.addWidget(settings)
        layout.addWidget(
            self._feature_card(
                "●",
                "Estado visible",
                "La barra inferior muestra conexión, batería y guardado. Diagnóstico mide latencia y genera reportes.",
            )
        )
        layout.addStretch()
        return area

    def _build_nexus_page(self) -> QWidget:
        area, layout = self._scroll_page()
        layout.addWidget(
            self._feature_card(
                "⌘",
                "Nikaido Nexus",
                "Selecciona una entrada del DualSense y asigna botones, teclado, mouse, macros, capas o acciones de gyro.",
            )
        )
        grid = QGridLayout()
        grid.setSpacing(10)
        cards = (
            ("01", "Gestos", "Pulsación, doble toque, mantener, soltar, pulsación larga y turbo."),
            ("02", "Capas", "Cambia el comportamiento completo del control mientras juegas."),
            ("03", "Perfiles", "Cada juego puede cargar su propio perfil automáticamente."),
            ("04", "Compatibilidad", "Todo se guarda en .Nika sin duplicar la lógica del mapper."),
        )
        for index, values in enumerate(cards):
            grid.addWidget(self._feature_card(*values), index // 2, index % 2)
        layout.addLayout(grid)
        pm = self.window.profile_manager
        self.wizard_game_profiles = QCheckBox("Cambiar perfil automáticamente según el juego")
        self.wizard_game_profiles.setChecked(bool(pm and pm.get_setting("game_profiles_enabled", True)))
        layout.addWidget(self.wizard_game_profiles)
        action_row = QHBoxLayout()
        action_row.addWidget(button("Abrir Nexus al terminar", lambda: self._choose_destination("mapper")))
        action_row.addWidget(button("Abrir Perfiles al terminar", lambda: self._choose_destination("profiles")))
        action_row.addStretch()
        layout.addLayout(action_row)
        layout.addStretch()
        return area

    def _build_gyro_page(self) -> QWidget:
        area, layout = self._scroll_page()
        grid = QGridLayout()
        grid.setSpacing(10)
        cards = (
            ("◉", "Gyro Studio", "Sensibilidad, activación, suavizado, zonas muertas y presets por perfil."),
            ("↻", "Flick Stick", "Giros rápidos con la palanca y precisión fina mediante movimiento."),
            ("⌘", "Macros visuales", "Timeline, grabación en vivo, sticks, gatillos, grupos y biblioteca."),
            ("⌨", "Nikaido KeyBridge", "Convierte teclado y mouse en un Xbox 360 o DualShock 4 virtual."),
            ("▣", "Diagnóstico", "Comprueba HID, ViGEm, botones, sensores y rendimiento sin adivinar."),
        )
        for index, values in enumerate(cards):
            grid.addWidget(self._feature_card(*values), index // 2, index % 2)
        layout.addLayout(grid)
        pm = self.window.profile_manager
        self.wizard_vibration = QCheckBox("Mantener la vibración general activada")
        self.wizard_vibration.setChecked(bool(pm and pm.get_setting("vibration_enabled", True)))
        layout.addWidget(self.wizard_vibration)
        note = label(
            "El Gyro Aim no se activa automáticamente desde este asistente. Primero calibra el control y elige el modo que prefieras en Gyro Studio.",
            "muted",
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        action_row = QHBoxLayout()
        action_row.addWidget(button("Abrir Gyro Studio al terminar", lambda: self._choose_destination("gyro")))
        action_row.addWidget(button("Abrir KeyBridge al terminar", lambda: self._choose_destination("emulation")))
        action_row.addWidget(button("Abrir Macros al terminar", lambda: self._choose_destination("macros")))
        action_row.addStretch()
        layout.addLayout(action_row)
        layout.addStretch()
        return area

    def _build_appearance_page(self) -> QWidget:
        area, layout = self._scroll_page()
        preview_row = QHBoxLayout()
        preview_row.setSpacing(12)
        preview_panel = card(sub=True)
        preview_layout = QVBoxLayout(preview_panel)
        self.wizard_appearance_preview = AppearancePreview()
        # El fondo solo se decodifica al entrar en este paso. Así el wizard no
        # duplica una fotografía grande mientras el usuario ve otras páginas.
        preview_appearance = dict(self._appearance)
        preview_appearance["background_enabled"] = False
        preview_appearance["background_path"] = ""
        self.wizard_appearance_preview.set_appearance(preview_appearance)
        preview_layout.addWidget(self.wizard_appearance_preview)
        self.wizard_background_name = label("Fondo predeterminado", "muted")
        self.wizard_background_name.setWordWrap(True)
        preview_layout.addWidget(self.wizard_background_name)
        choose_row = QHBoxLayout()
        choose_row.addWidget(button("Elegir fondo", self.choose_wizard_background, primary=True))
        choose_row.addWidget(button("Sin fondo", self.clear_wizard_background))
        preview_layout.addLayout(choose_row)
        self.wizard_wallpaper_gallery = WallpaperGallery(columns=3)
        if not self.wizard_wallpaper_gallery.is_empty:
            preview_layout.addWidget(label("Fondos incluidos (libres, CC0)", "muted"))
            preview_layout.addWidget(self.wizard_wallpaper_gallery)
            self.wizard_wallpaper_gallery.selected.connect(self.choose_wizard_bundled_background)
        else:
            self.wizard_wallpaper_gallery.hide()
        preview_row.addWidget(preview_panel, 52)

        controls = card(sub=True)
        form = QFormLayout(controls)
        form.setContentsMargins(16, 15, 16, 15)
        form.setSpacing(10)
        self.wizard_accent = QComboBox()
        for key, palette in ACCENT_PALETTES.items():
            self.wizard_accent.addItem(palette["name"], key)
        self.wizard_accent.setCurrentIndex(max(0, self.wizard_accent.findData(self._appearance["accent_style"])))
        form.addRow("Color", self.wizard_accent)
        self.wizard_density = QComboBox()
        self.wizard_density.addItem("Cómoda", "comfortable")
        self.wizard_density.addItem("Compacta", "compact")
        self.wizard_density.setCurrentIndex(max(0, self.wizard_density.findData(self._appearance["ui_density"])))
        form.addRow("Densidad", self.wizard_density)
        self.wizard_reduce_motion = QCheckBox("Reducir animaciones")
        self.wizard_reduce_motion.setChecked(bool(self._appearance["reduce_motion"]))
        form.addRow("", self.wizard_reduce_motion)
        self.wizard_sidebar_collapsed = QCheckBox("Iniciar con menú lateral compacto")
        self.wizard_sidebar_collapsed.setChecked(bool(self._appearance["sidebar_collapsed"]))
        form.addRow("", self.wizard_sidebar_collapsed)
        preview_row.addWidget(controls, 48)
        layout.addLayout(preview_row)

        for widget in (self.wizard_accent, self.wizard_density):
            widget.currentIndexChanged.connect(self._preview_wizard_appearance)
        self.wizard_reduce_motion.toggled.connect(self._preview_wizard_appearance)
        self.wizard_sidebar_collapsed.toggled.connect(self._preview_wizard_appearance)
        detail = label(
            "El asistente aplica una vista previa al instante. Los controles avanzados de transparencia, zoom y viñeta siguen disponibles en Ajustes.",
            "muted",
        )
        detail.setWordWrap(True)
        layout.addWidget(detail)
        layout.addWidget(button("Abrir Apariencia Studio al terminar", lambda: self._choose_destination("settings")))
        layout.addStretch()
        self._refresh_wizard_background_name()
        return area

    def _build_finish_page(self) -> QWidget:
        area, layout = self._scroll_page()
        hero = card()
        box = QVBoxLayout(hero)
        box.setContentsMargins(22, 22, 22, 22)
        complete = QLabel("Todo listo para usar Nikaido")
        complete.setObjectName("wizardHero")
        complete.setWordWrap(True)
        box.addWidget(complete)
        summary = label(
            "Tus ajustes se guardarán al finalizar. Puedes modificar cualquier opción después y volver a abrir este asistente desde Ajustes.",
            "muted",
        )
        summary.setWordWrap(True)
        box.addWidget(summary)
        layout.addWidget(hero)
        layout.addWidget(label("¿POR DÓNDE QUIERES COMENZAR?", "eyebrow"))
        grid = QGridLayout()
        grid.setSpacing(10)
        destinations = (
            ("dashboard", "⌂", "Dashboard", "Estado del control y accesos rápidos"),
            ("mapper", "⌘", "Nikaido Nexus", "Configura capas, botones y gestos"),
            ("gyro", "◉", "Gyro Studio", "Calibra y ajusta el apuntado"),
            ("settings", "✦", "Apariencia Studio", "Personaliza el programa"),
        )
        for index, (page, icon, title, description) in enumerate(destinations):
            action = button(
                f"{icon}   {title}\n{description}",
                lambda _checked=False, p=page: self.finish(p),
            )
            action.setMinimumHeight(72)
            action.setProperty("wizardDestination", True)
            grid.addWidget(action, index // 2, index % 2)
        layout.addLayout(grid)
        layout.addStretch()
        return area

    def _choose_destination(self, page: str) -> None:
        self._destination = str(page)
        prefix = {"es": "Al finalizar se abrirá", "en": "When finished, Nikaido will open", "pt_BR": "Ao finalizar, o Nikaido abrirá"}.get(self._language, "Al finalizar se abrirá")
        self.window.toast(f"{prefix} {self.window.page_meta(page)[0]}")

    def _preview_wizard_appearance(self, *_args: Any) -> None:
        if not hasattr(self, "wizard_accent"):
            return
        values = dict(self._appearance)
        values.update(
            accent_style=str(self.wizard_accent.currentData() or "violet"),
            ui_density=str(self.wizard_density.currentData() or "comfortable"),
            reduce_motion=self.wizard_reduce_motion.isChecked(),
            sidebar_collapsed=self.wizard_sidebar_collapsed.isChecked(),
        )
        self._appearance = normalize_appearance(values)
        self.wizard_appearance_preview.set_appearance(self._appearance)
        self.window.apply_appearance(self._appearance)

    def choose_wizard_background(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Elegir fondo de Nikaido",
            "",
            "Imágenes (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        pm = self.window.profile_manager
        if not path or not pm:
            return
        stored = pm.store_ui_background(path)
        if not stored:
            self.window.alert(tr("La imagen no es válida o es demasiado grande.", self._language))
            return
        self._apply_wizard_background(stored)

    def choose_wizard_bundled_background(self, key: str) -> None:
        pm = self.window.profile_manager
        if not pm:
            return
        stored = pm.store_bundled_wallpaper(key)
        if not stored:
            self.window.alert(tr("La imagen no es válida o es demasiado grande.", self._language))
            return
        self._apply_wizard_background(stored)

    def _apply_wizard_background(self, stored: str) -> None:
        self._appearance["background_path"] = stored
        self._appearance["background_enabled"] = True
        self._appearance = normalize_appearance(self._appearance)
        pm = self.window.profile_manager
        self.wizard_wallpaper_gallery.set_current(pm.current_wallpaper_key() if pm else "")
        self.wizard_appearance_preview.set_appearance(self._appearance)
        self.window.apply_appearance(self._appearance)
        self._refresh_wizard_background_name()

    def clear_wizard_background(self) -> None:
        if self.window.profile_manager:
            self.window.profile_manager.set_setting("ui_wallpaper_key", "")
        if hasattr(self, "wizard_wallpaper_gallery"):
            self.wizard_wallpaper_gallery.set_current("")
        self._appearance["background_enabled"] = False
        self._appearance["background_path"] = ""
        self._appearance = normalize_appearance(self._appearance)
        self.wizard_appearance_preview.set_appearance(self._appearance)
        self.window.apply_appearance(self._appearance)
        self._refresh_wizard_background_name()

    def _refresh_wizard_background_name(self) -> None:
        if not hasattr(self, "wizard_background_name"):
            return
        path = str(self._appearance.get("background_path", "") or "")
        pm = self.window.profile_manager
        wallpaper = find_wallpaper(pm.current_wallpaper_key()) if pm else None
        if path and wallpaper:
            self.wizard_background_name.setText(wallpaper.name)
        else:
            self.wizard_background_name.setText(Path(path).name if path else "Fondo predeterminado")

    def _update_page(self) -> None:
        self.stack.setCurrentIndex(self._index)
        title, subtitle = self.STEPS[self._index]
        self.page_title.setText(tr(title, self._language))
        self.page_subtitle.setText(tr(subtitle, self._language))
        self.progress.setValue(self._index + 1)
        if self._language == "en":
            progress_text = f"{self._index + 1} of {len(self.STEPS)}"
        else:
            progress_text = f"{self._index + 1} de {len(self.STEPS)}"
        self.progress_text.setText(progress_text)
        self.back_button.setEnabled(self._index > 0)
        self.skip_button.setVisible(self._index > self.LANGUAGE_STEP)
        self.header_language.setVisible(self._index > self.LANGUAGE_STEP)
        next_text = "Entrar a Nikaido" if self._index == len(self.STEPS) - 1 else "Siguiente  ›"
        self.next_button.setText(tr(next_text, self._language))
        language_ready = self._index != self.LANGUAGE_STEP or self._language_confirmed
        self.next_button.setEnabled(language_ready)
        self.next_button.setToolTip("" if language_ready else tr("Elige un idioma para continuar", self._language))
        self._update_mascot_scene()
        if self._index == self.CONNECTION_STEP:
            if not self.connection_timer.isActive():
                self.connection_timer.start()
            self._refresh_connection_status()
        else:
            self.connection_timer.stop()
        if self._index == self.APPEARANCE_STEP:
            self.wizard_appearance_preview.set_appearance(self._appearance)
        else:
            # La vista de apariencia puede contener una copia reducida del
            # fondo. Se suelta al cambiar de paso y se recarga al volver.
            self.wizard_appearance_preview.release_image_cache()
        for index, item in enumerate(self.step_labels):
            item.setProperty("active", index == self._index)
            item.setProperty("done", index < self._index)
            item.style().unpolish(item)
            item.style().polish(item)

    def _update_mascot_scene(self) -> None:
        pose, title, message, badge = self.MASCOT_SCENES[self._index]
        self.mascot_panel.set_scene(
            pose,
            tr(title, self._language),
            tr(message, self._language),
            badge=tr(badge, self._language),
        )

    def _request_connection(self) -> None:
        manager = self.window.connection_manager
        if manager:
            manager.request_connect()
            self.window.toast(tr("Buscando tu DualSense…", self._language), "info")
        self._refresh_connection_status()

    def _refresh_connection_status(self) -> None:
        if not hasattr(self, "wizard_connection_value"):
            return
        manager = self.window.connection_manager
        try:
            state = manager.state if manager else None
        except Exception:
            state = None
        connected = bool(state and getattr(state, "connected", False))
        if connected:
            connection = getattr(getattr(state, "connection_type", None), "value", "USB")
            battery_valid = bool(getattr(state, "battery_valid", False))
            battery = int(getattr(state, "battery_level", 0) or 0)
            battery_text = f"{battery}%" if battery_valid else tr("Leyendo…", self._language)
            self.wizard_connection_value.setText(tr("✓ DualSense conectado", self._language))
            self.wizard_connection_value.setStyleSheet("color:#54d67b")
            if self._language == "en":
                detail = f"Connection {str(connection).upper()} · Battery {battery_text} · Ready to continue."
            elif self._language == "pt_BR":
                detail = f"Conexão {str(connection).upper()} · Bateria {battery_text} · Pronto para continuar."
            else:
                detail = f"Conexión {str(connection).upper()} · Batería {battery_text} · Listo para continuar."
            self.wizard_connection_detail.setText(detail)
            if self._index == self.CONNECTION_STEP:
                self.mascot_panel.set_scene(
                    "happy",
                    tr("¡Ya lo encontré!", self._language),
                    tr("Tu DualSense está conectado. Puedes continuar y cambiar estos ajustes después cuando quieras.", self._language),
                    badge=tr("CONECTADO", self._language),
                )
            return
        self.wizard_connection_value.setText(tr("Buscando DualSense…", self._language))
        self.wizard_connection_value.setStyleSheet("color:#43d7ef")
        self.wizard_connection_detail.setText(
            tr("Conecta el control por USB o Bluetooth. Puedes seguir aunque todavía no esté disponible.", self._language)
        )
        if self._index == self.CONNECTION_STEP:
            pose, title, message, badge = self.MASCOT_SCENES[self.CONNECTION_STEP]
            self.mascot_panel.set_scene(
                pose, tr(title, self._language), tr(message, self._language),
                badge=tr(badge, self._language)
            )

    def previous(self) -> None:
        if self._index <= 0:
            return
        self._index -= 1
        self._update_page()

    def next(self) -> None:
        if self._index == self.LANGUAGE_STEP and not self._language_confirmed:
            self.window.toast("Elige un idioma para continuar · Choose a language · Escolha um idioma", "info")
            return
        if self._index >= len(self.STEPS) - 1:
            self.finish(self._destination or "dashboard")
            return
        self._index += 1
        self._update_page()

    def _sync_settings_appearance(self, values: Dict[str, Any]) -> None:
        settings_page = getattr(self.window, "settings_page", None)
        if settings_page is None:
            return
        settings_page._load_appearance_controls(values)
        settings_page.refresh_appearance_preview()

    def _save_settings(self, *, completed: bool = True) -> None:
        pm = self.window.profile_manager
        if not pm:
            return
        pm.set_setting("auto_connect", self.wizard_auto_connect.isChecked())
        pm.set_setting("start_minimized", self.wizard_start_minimized.isChecked())
        pm.set_setting("minimize_to_tray", self.wizard_minimize_to_tray.isChecked())
        pm.set_setting("low_profile_on_minimize", self.wizard_low_profile.isChecked())
        pm.set_setting("game_profiles_enabled", self.wizard_game_profiles.isChecked())
        pm.set_setting("vibration_enabled", self.wizard_vibration.isChecked())
        pm.set_setting("language", self._language)
        pm.set_setting("onboarding.language_confirmed", True)
        pm.set_setting("appearance", normalize_appearance(self._appearance))
        if completed:
            pm.set_setting("onboarding.completed", True)
            pm.set_setting("onboarding.version", ONBOARDING_VERSION)
        self.window.request_config_save()
        self.window.flush_config_save()

        if self.window.game_profile_watcher:
            self.window.game_profile_watcher.set_enabled(self.wizard_game_profiles.isChecked())
        if self.window.connection_manager:
            if self.wizard_auto_connect.isChecked():
                self.window.connection_manager.request_connect()
            else:
                self.window.connection_manager.disconnect()
        self.window.apply_appearance(self._appearance)
        self._sync_settings_appearance(self._appearance)

    def _release_resources(self, *_args: Any) -> None:
        """Suelta imágenes y temporizadores antes de destruir el diálogo."""
        self.connection_timer.stop()
        if hasattr(self, "mascot_panel"):
            self.mascot_panel.clear_resources()
        if hasattr(self, "wizard_appearance_preview"):
            self.wizard_appearance_preview.release_image_cache()

    def _ask_assistant_choice(self) -> bool:
        dialog = AssistantChoiceDialog(self.window)
        dialog.exec()
        enabled = bool(dialog.choice)
        self.window.set_assistant_enabled(enabled, persist=False)
        return enabled

    def finish(self, destination: str = "dashboard") -> None:
        if self._finishing:
            return
        self._finishing = True
        self.connection_timer.stop()
        self._save_settings(completed=True)
        enabled = self._ask_assistant_choice()
        window = self.window
        self.accept()
        window.toast(
            tr("Bienvenida completada. Nikaido te acompañará." if enabled
            else "Bienvenida completada. Asistente desactivada.", window.language),
            "success" if enabled else "info",
        )
        window.call_later(0, lambda w=window, page=destination: w.navigate(page))

    def skip(self) -> None:
        if self._index == self.LANGUAGE_STEP and not self._language_confirmed:
            self.window.toast("Primero elige un idioma · First choose a language · Primeiro escolha um idioma", "info")
            return
        pm = self.window.profile_manager
        if pm:
            pm.set_setting("onboarding.completed", True)
            pm.set_setting("onboarding.version", ONBOARDING_VERSION)
            self.window.request_config_save()
            self.window.flush_config_save()
        # Omitir no debe dejar una vista previa sin guardar activa.
        self.connection_timer.stop()
        self.window.apply_appearance(self._original_appearance)
        self._sync_settings_appearance(self._original_appearance)
        self._finishing = True
        self._ask_assistant_choice()
        self.accept()

    def reject(self) -> None:
        if self._requires_language_choice and not self._language_confirmed:
            self.window.toast(tr("Elige un idioma antes de cerrar el recorrido", self._language), "info")
            return
        self.connection_timer.stop()
        if not self._finishing:
            self.window.apply_appearance(self._original_appearance)
            self._sync_settings_appearance(self._original_appearance)
        super().reject()


class SettingsPage(ScrollPage):
    def __init__(self, window: "NikaidoWindow") -> None:
        super().__init__()
        self.window = window
        self._appearance_loading = True
        self._appearance_apply_timer = QTimer(self)
        self._appearance_apply_timer.setSingleShot(True)
        self._appearance_apply_timer.timeout.connect(self._apply_appearance_now)
        self.add_header("Ajustes", "Preferencias generales de Nikaido.")

        language_panel = card()
        language_root = QVBoxLayout(language_panel)
        language_root.setContentsMargins(16, 15, 16, 15)
        language_root.setSpacing(8)
        language_root.addWidget(label("IDIOMA / LANGUAGE", "eyebrow"))
        language_copy = label(
            "Cambia el idioma del programa al instante. No necesitas reiniciar Nikaido.",
            "muted",
        )
        language_copy.setWordWrap(True)
        language_root.addWidget(language_copy)
        self.language_combo = QComboBox()
        self.language_combo.setProperty("i18nSkipItems", True)
        for code, native_name in LANGUAGE_OPTIONS:
            self.language_combo.addItem(native_name, code)
        current_language = normalize_language(
            self.window.profile_manager.get_setting("language", getattr(self.window, "language", "es"))
            if self.window.profile_manager else getattr(self.window, "language", "es")
        )
        self.language_combo.setCurrentIndex(
            max(0, self.language_combo.findData(current_language))
        )
        self.language_combo.currentIndexChanged.connect(self._language_setting_changed)
        language_root.addWidget(self.language_combo)
        self.layout.addWidget(language_panel)

        assistant_panel = card()
        assistant_root = QVBoxLayout(assistant_panel)
        assistant_root.setContentsMargins(16, 15, 16, 15)
        assistant_root.setSpacing(9)
        assistant_root.addWidget(label("ASISTENTE NIKAIDO", "eyebrow"))
        assistant_copy = label(
            "Consejos ocasionales sobre funciones poco visibles y accesos directos. Puedes apagarla cuando quieras.",
            "muted",
        )
        assistant_copy.setWordWrap(True)
        assistant_root.addWidget(assistant_copy)
        pm = self.window.profile_manager
        self.assistant_enabled = QCheckBox("Usar a Nikaido como asistente")
        self.assistant_enabled.setChecked(bool(pm and pm.get_setting("assistant.enabled", False)))
        self.assistant_tips = QCheckBox("Mostrar consejos ocasionales")
        self.assistant_tips.setChecked(bool(pm and pm.get_setting("assistant.tips_enabled", True)))
        self.assistant_tip_sounds = QCheckBox("Reproducir un sonido suave al mostrar un consejo")
        self.assistant_tip_sounds.setChecked(
            bool(pm and pm.get_setting("assistant.tip_sounds_enabled", True))
        )
        self.assistant_tips.setEnabled(self.assistant_enabled.isChecked())
        self.assistant_tip_sounds.setEnabled(
            self.assistant_enabled.isChecked() and self.assistant_tips.isChecked()
        )
        self.assistant_enabled.toggled.connect(self._assistant_enabled_changed)
        self.assistant_tips.toggled.connect(self._assistant_tips_changed)
        self.assistant_tip_sounds.toggled.connect(self._assistant_tip_sounds_changed)
        assistant_root.addWidget(self.assistant_enabled)
        assistant_root.addWidget(self.assistant_tips)
        assistant_root.addWidget(self.assistant_tip_sounds)
        assistant_actions = QHBoxLayout()
        assistant_actions.addWidget(button("Mostrar un consejo ahora", self._show_tip_now))
        assistant_actions.addStretch()
        assistant_root.addLayout(assistant_actions)
        self.layout.addWidget(assistant_panel)

        updates_panel = card()
        updates_root = QVBoxLayout(updates_panel)
        updates_root.setContentsMargins(16, 15, 16, 15)
        updates_root.setSpacing(9)
        updates_header = QHBoxLayout()
        updates_header.addWidget(label("ACTUALIZACIONES", "eyebrow"))
        updates_header.addStretch()
        updates_header.addWidget(label(f"v{APP_VERSION} · {RELEASE_STAGE}", "muted"))
        updates_root.addLayout(updates_header)
        updates_copy = label(
            "Instala versiones nuevas sobre la actual sin borrar perfiles, macros, imágenes ni ajustes.",
            "muted",
        )
        updates_copy.setWordWrap(True)
        updates_root.addWidget(updates_copy)
        self.update_status = label("Listo para buscar actualizaciones", "muted")
        self.update_status.setWordWrap(True)
        updates_root.addWidget(self.update_status)
        updates_options = QHBoxLayout()
        self.update_startup = QCheckBox("Buscar al iniciar")
        self.update_startup.setChecked(bool(pm and pm.get_setting("updates.check_on_startup", True)))
        self.update_startup.toggled.connect(self._update_startup_changed)
        updates_options.addWidget(self.update_startup)
        updates_options.addSpacing(18)
        updates_options.addWidget(label("Canal", "muted"))
        self.update_channel = QComboBox()
        self.update_channel.addItem("Estable", "stable")
        self.update_channel.addItem("Beta", "beta")
        channel = str(pm.get_setting("updates.channel", "beta") if pm else "beta")
        self.update_channel.setCurrentIndex(max(0, self.update_channel.findData(channel)))
        self.update_channel.currentIndexChanged.connect(self._update_channel_changed)
        updates_options.addWidget(self.update_channel)
        updates_options.addStretch()
        updates_root.addLayout(updates_options)
        self.update_progress = QProgressBar()
        self.update_progress.setRange(0, 100)
        self.update_progress.setValue(0)
        self.update_progress.setVisible(False)
        updates_root.addWidget(self.update_progress)
        updates_actions = QHBoxLayout()
        self.update_check_button = button("Buscar actualización", self._check_updates, primary=True)
        self.update_install_button = button(
            "Descargar e instalar", self.window.download_available_update, primary=True
        )
        self.update_skip_button = button("Omitir esta versión", self.window.skip_available_update)
        self.update_restore_button = button(
            "Volver a mostrar", self.window.restore_skipped_update
        )
        self.update_install_button.setVisible(False)
        self.update_skip_button.setVisible(False)
        self.update_restore_button.setVisible(False)
        updates_actions.addWidget(self.update_check_button)
        updates_actions.addWidget(self.update_install_button)
        updates_actions.addWidget(self.update_skip_button)
        updates_actions.addWidget(self.update_restore_button)
        updates_actions.addStretch()
        updates_root.addLayout(updates_actions)
        manager = getattr(self.window, "update_manager", None)
        if manager is None:
            self.update_status.setText("El motor de actualizaciones no está disponible")
            self.update_check_button.setEnabled(False)
        elif not manager.manifest_url():
            self.update_status.setText(
                "El actualizador está listo; falta publicar el servidor oficial de versiones."
            )
        self.layout.addWidget(updates_panel)

        appearance = normalize_appearance(
            self.window.profile_manager.get_setting("appearance", {})
            if self.window.profile_manager else {}
        )
        visual = card()
        visual_root = QVBoxLayout(visual)
        visual_root.setContentsMargins(16, 15, 16, 15)
        visual_root.setSpacing(12)
        visual_header = QHBoxLayout()
        visual_titles = QVBoxLayout()
        visual_titles.addWidget(label("APARIENCIA STUDIO", "eyebrow"))
        visual_titles.addWidget(
            label("Fondo, color de acento, densidad y transparencias con vista previa en vivo.", "muted")
        )
        visual_header.addLayout(visual_titles, 1)
        self.appearance_preset = QComboBox()
        for key, preset in APPEARANCE_PRESETS.items():
            self.appearance_preset.addItem(preset["name"], key)
        visual_header.addWidget(self.appearance_preset)
        visual_header.addWidget(button("Aplicar preset", self.apply_appearance_preset))
        visual_header.addWidget(button("Restablecer", self.reset_appearance))
        visual_root.addLayout(visual_header)

        visual_body = QHBoxLayout()
        visual_body.setSpacing(14)
        preview_card = card(sub=True)
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        self.background_preview = AppearancePreview()
        preview_layout.addWidget(self.background_preview)
        self.background_name = label("Fondo predeterminado", "muted")
        self.background_name.setWordWrap(True)
        preview_layout.addWidget(self.background_name)
        preview_actions = QHBoxLayout()
        preview_actions.addWidget(button("Elegir imagen", self.choose_background, primary=True))
        preview_actions.addWidget(button("Quitar", self.remove_background, danger=True))
        preview_layout.addLayout(preview_actions)
        self.wallpaper_gallery = WallpaperGallery(columns=3)
        if self.window.profile_manager:
            self.wallpaper_gallery.set_current(self.window.profile_manager.current_wallpaper_key())
        if not self.wallpaper_gallery.is_empty:
            preview_layout.addWidget(label("Fondos incluidos (libres, CC0)", "muted"))
            preview_layout.addWidget(self.wallpaper_gallery)
            self.wallpaper_gallery.selected.connect(self.choose_bundled_background)
        else:
            self.wallpaper_gallery.hide()
        visual_body.addWidget(preview_card, 42)

        controls_card = card(sub=True)
        controls = QVBoxLayout(controls_card)
        controls.setContentsMargins(14, 12, 14, 12)
        controls.setSpacing(8)
        self.appearance_enabled = QCheckBox("Usar imagen de fondo")
        self.appearance_enabled.setChecked(bool(appearance["background_enabled"]))
        controls.addWidget(self.appearance_enabled)

        selectors = QFormLayout()
        selectors.setSpacing(8)
        self.appearance_accent = QComboBox()
        for key, palette in ACCENT_PALETTES.items():
            self.appearance_accent.addItem(palette["name"], key)
        self.appearance_accent.setCurrentIndex(max(0, self.appearance_accent.findData(appearance["accent_style"])))
        selectors.addRow("Color de acento", self.appearance_accent)

        self.background_fit = QComboBox()
        self.background_fit.addItem("Llenar ventana", "cover")
        self.background_fit.addItem("Mostrar completa", "contain")
        self.background_fit.addItem("Estirar", "stretch")
        self.background_fit.setCurrentIndex(max(0, self.background_fit.findData(appearance["background_fit"])))
        selectors.addRow("Ajuste del fondo", self.background_fit)

        self.background_position = QComboBox()
        self.background_position.addItem("Arriba", "top")
        self.background_position.addItem("Centro", "center")
        self.background_position.addItem("Abajo", "bottom")
        self.background_position.setCurrentIndex(max(0, self.background_position.findData(appearance["background_position"])))
        selectors.addRow("Posición", self.background_position)

        self.ui_density = QComboBox()
        self.ui_density.addItem("Cómoda", "comfortable")
        self.ui_density.addItem("Compacta", "compact")
        self.ui_density.setCurrentIndex(max(0, self.ui_density.findData(appearance["ui_density"])))
        selectors.addRow("Densidad", self.ui_density)
        controls.addLayout(selectors)

        self.appearance_sliders: Dict[str, SliderRow] = {
            "background_dim": SliderRow("Oscurecer fondo", 0, 90, appearance["background_dim"], decimals=0, suffix=" %"),
            "background_zoom": SliderRow("Zoom del fondo", 100, 180, appearance["background_zoom"], decimals=0, suffix=" %"),
            "background_vignette": SliderRow("Viñeta", 0, 80, appearance["background_vignette"], decimals=0, suffix=" %"),
            "panel_opacity": SliderRow("Opacidad de paneles", 30, 100, appearance["panel_opacity"], decimals=0, suffix=" %"),
            "sidebar_opacity": SliderRow("Opacidad del menú", 30, 100, appearance["sidebar_opacity"], decimals=0, suffix=" %"),
            "button_opacity": SliderRow("Opacidad de controles", 30, 100, appearance["button_opacity"], decimals=0, suffix=" %"),
        }
        for key, slider in self.appearance_sliders.items():
            slider.changed.connect(lambda _value, k=key: self._appearance_changed(k))
            controls.addWidget(slider)

        self.reduce_motion = QCheckBox("Reducir animaciones")
        self.reduce_motion.setChecked(bool(appearance["reduce_motion"]))
        controls.addWidget(self.reduce_motion)
        for selector in (
            self.appearance_accent, self.background_fit, self.background_position, self.ui_density
        ):
            selector.currentIndexChanged.connect(lambda _index: self._appearance_changed("selector"))
        self.appearance_enabled.toggled.connect(lambda _value: self._appearance_changed("background_enabled"))
        self.reduce_motion.toggled.connect(lambda _value: self._appearance_changed("reduce_motion"))
        note = label(
            "Los fondos se validan, orientan y optimizan para evitar consumo excesivo de RAM.",
            "muted",
        )
        note.setWordWrap(True)
        controls.addWidget(note)
        visual_body.addWidget(controls_card, 58)
        visual_root.addLayout(visual_body)
        self.layout.addWidget(visual)
        self._appearance_loading = False
        self.refresh_appearance_preview()

        general = card()
        form = QVBoxLayout(general)
        form.addWidget(label("INICIO Y VENTANA", "eyebrow"))
        self.start_min = self.setting("Iniciar minimizado", "start_minimized", False)
        self.tray = self.setting(
            "Enviar a la bandeja al minimizar", "minimize_to_tray", True
        )
        self.low_profile = self.setting(
            "Activar Low Profile al minimizar", "low_profile_on_minimize", True
        )
        self.auto = self.setting("Conectar automáticamente", "auto_connect", True)
        self.windows = self.setting("Iniciar con Windows", "start_with_windows", False)
        form.addWidget(self.start_min)
        form.addWidget(self.tray)
        form.addWidget(self.low_profile)
        form.addWidget(self.auto)
        form.addWidget(self.windows)
        close_note = label(
            "Low Profile destruye la interfaz al minimizar, pero conserva el control, la emulación, macros y perfiles activos. Cerrar (×) termina Nikaido.",
            "muted",
        )
        close_note.setWordWrap(True)
        form.addWidget(close_note)
        self.layout.addWidget(general)
        control = card()
        c = QVBoxLayout(control)
        c.addWidget(label("CONTROLADOR", "eyebrow"))
        self.vibration = self.setting("Vibración general", "vibration_enabled", True)
        self.games = self.setting(
            "Cambiar perfil según el juego", "game_profiles_enabled", True
        )
        c.addWidget(self.vibration)
        c.addWidget(self.games)
        self.layout.addWidget(control)
        data = card()
        d = QVBoxLayout(data)
        d.addWidget(label("DATOS", "eyebrow"))
        d.addWidget(button("Abrir carpeta de configuración", self.open_config))
        d.addWidget(button("Volver a iniciar el asistente de bienvenida", self.restart_wizard))
        d.addWidget(
            button("Restablecer toda la configuración", self.reset_all, danger=True)
        )
        self.layout.addWidget(data)
        self.layout.addStretch()

    def _appearance_values(self) -> Dict[str, Any]:
        pm = self.window.profile_manager
        existing = normalize_appearance(pm.get_setting("appearance", {}) if pm else {})
        existing.update(
            background_enabled=self.appearance_enabled.isChecked(),
            background_fit=str(self.background_fit.currentData() or "cover"),
            background_position=str(self.background_position.currentData() or "center"),
            accent_style=str(self.appearance_accent.currentData() or "violet"),
            ui_density=str(self.ui_density.currentData() or "comfortable"),
            reduce_motion=self.reduce_motion.isChecked(),
        )
        for key, slider in self.appearance_sliders.items():
            existing[key] = round(slider.spin.value())
        return normalize_appearance(existing)

    def _load_appearance_controls(self, values: Dict[str, Any]) -> None:
        values = normalize_appearance(values)
        self._appearance_loading = True
        try:
            self.appearance_enabled.setChecked(bool(values["background_enabled"]))
            self.reduce_motion.setChecked(bool(values["reduce_motion"]))
            for widget, key in (
                (self.appearance_accent, "accent_style"),
                (self.background_fit, "background_fit"),
                (self.background_position, "background_position"),
                (self.ui_density, "ui_density"),
            ):
                widget.setCurrentIndex(max(0, widget.findData(values[key])))
            for key, slider in self.appearance_sliders.items():
                slider.set_value(float(values[key]))
        finally:
            self._appearance_loading = False

    def _appearance_changed(self, _key: str = "") -> None:
        if self._appearance_loading:
            return
        values = self._appearance_values()
        pm = self.window.profile_manager
        if pm:
            pm.set_setting("appearance", values)
            self.window.request_config_save()
        # Regenerar una hoja QSS completa es costoso. Agrupar cambios rápidos
        # mantiene los sliders suaves incluso con fondos y cientos de widgets.
        self._appearance_apply_timer.start(90)
        self.background_preview.set_appearance(values)

    def _apply_appearance_now(self) -> None:
        values = self._appearance_values()
        self.window.apply_appearance(values)
        self.refresh_appearance_preview()

    def apply_appearance_preset(self) -> None:
        preset = APPEARANCE_PRESETS.get(str(self.appearance_preset.currentData() or ""))
        if not preset:
            return
        values = self._appearance_values()
        values.update({key: value for key, value in preset.items() if key != "name"})
        values = normalize_appearance(values)
        self._load_appearance_controls(values)
        if self.window.profile_manager:
            self.window.profile_manager.set_setting("appearance", values)
            self.window.request_config_save()
        self.window.apply_appearance(values)
        self.refresh_appearance_preview()
        suffix = {"es": "aplicado", "en": "applied", "pt_BR": "aplicado"}.get(self.window.language, "aplicado")
        self.window.toast(f"Preset {preset['name']} {suffix}", "success")

    def choose_background(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Elegir fondo de Nikaido",
            "",
            "Imágenes (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not path or not self.window.profile_manager:
            return
        stored = self.window.profile_manager.store_ui_background(path)
        if not stored:
            self.window.alert(
                tr("La imagen no es válida o es demasiado grande. Usa PNG, JPG, WEBP o BMP de menos de 20 MB.", self.window.language)
            )
            return
        self._apply_background(stored)

    def choose_bundled_background(self, key: str) -> None:
        if not self.window.profile_manager:
            return
        stored = self.window.profile_manager.store_bundled_wallpaper(key)
        if not stored:
            self.window.alert(tr("La imagen no es válida o es demasiado grande.", self.window.language))
            return
        self._apply_background(stored)

    def _apply_background(self, stored: str) -> None:
        values = self._appearance_values()
        values["background_path"] = stored
        values["background_enabled"] = True
        self.wallpaper_gallery.set_current(self.window.profile_manager.current_wallpaper_key())
        self._load_appearance_controls(values)
        self.window.profile_manager.set_setting("appearance", values)
        self.window.request_config_save()
        self.window.apply_appearance(values)
        self.refresh_appearance_preview()
        self.window.toast(tr("Fondo optimizado y aplicado", self.window.language), "success")

    def remove_background(self) -> None:
        pm = self.window.profile_manager
        if not pm:
            return
        pm.remove_ui_background()
        self.wallpaper_gallery.set_current("")
        values = self._appearance_values()
        values["background_path"] = ""
        values["background_enabled"] = False
        self._load_appearance_controls(values)
        pm.set_setting("appearance", values)
        self.window.request_config_save()
        self.window.apply_appearance(values)
        self.refresh_appearance_preview()
        self.window.toast(tr("Fondo eliminado", self.window.language))

    def reset_appearance(self) -> None:
        pm = self.window.profile_manager
        values = normalize_appearance(DEFAULT_APPEARANCE)
        current_path = pm.get_setting("appearance.background_path", "") if pm else ""
        values["background_path"] = current_path
        self._load_appearance_controls(values)
        if pm:
            pm.set_setting("appearance", values)
            self.window.request_config_save()
        self.window.apply_appearance(values)
        self.refresh_appearance_preview()
        self.window.toast(tr("Apariencia restablecida", self.window.language), "success")

    def _language_setting_changed(self, *_args: Any) -> None:
        code = normalize_language(self.language_combo.currentData())
        self.window.set_language(code, persist=True)
        translate_widget_tree(self, code)
        self.window.toast(
            {"es": "Idioma actualizado", "en": "Language updated", "pt_BR": "Idioma atualizado"}[code],
            "success",
        )

    def _assistant_enabled_changed(self, enabled: bool) -> None:
        self.assistant_tips.setEnabled(bool(enabled))
        self.assistant_tip_sounds.setEnabled(bool(enabled) and self.assistant_tips.isChecked())
        self.window.set_assistant_enabled(bool(enabled))
        self.window.toast(
            tr("Nikaido asistente activada" if enabled else "Nikaido asistente desactivada", self.window.language),
            "success" if enabled else "info",
        )

    def _assistant_tips_changed(self, enabled: bool) -> None:
        self.window.save_setting("assistant.tips_enabled", bool(enabled))
        self.assistant_tip_sounds.setEnabled(bool(enabled) and self.assistant_enabled.isChecked())
        if not enabled:
            self.window.hide_assistant_tip()
        elif self.assistant_enabled.isChecked() and hasattr(self.window, "assistant_timer"):
            self.window.assistant_timer.start(20_000)

    def _assistant_tip_sounds_changed(self, enabled: bool) -> None:
        self.window.save_setting("assistant.tip_sounds_enabled", bool(enabled))

    def _show_tip_now(self) -> None:
        if not self.assistant_enabled.isChecked():
            self.assistant_enabled.setChecked(True)
        if not self.assistant_tips.isChecked():
            self.assistant_tips.setChecked(True)
        self.window.show_next_assistant_tip()

    def _update_startup_changed(self, enabled: bool) -> None:
        self.window.save_setting("updates.check_on_startup", bool(enabled))

    def _update_channel_changed(self, *_args: Any) -> None:
        channel = str(self.update_channel.currentData() or "stable")
        self.window.save_setting("updates.channel", channel)

    def _check_updates(self) -> None:
        self.window.check_for_updates(manual=True)

    def set_update_checking(self) -> None:
        self.update_status.setText("Buscando una versión nueva…")
        self.update_check_button.setEnabled(False)
        self.update_install_button.setVisible(False)
        self.update_skip_button.setVisible(False)
        self.update_restore_button.setVisible(False)
        self.update_progress.setVisible(False)

    def set_update_result(self, result: Any) -> None:
        self.update_check_button.setEnabled(True)
        status = str(getattr(result, "status", "error") or "error")
        update = getattr(result, "update", None)
        if status == "available" and update is not None:
            version = str(getattr(update, "version", "nueva"))
            title = str(getattr(update, "title", "Actualización disponible"))
            self.update_status.setText(f"{title} · versión {version}")
            self.update_install_button.setVisible(True)
            self.update_skip_button.setVisible(True)
            self.update_restore_button.setVisible(False)
            self.update_install_button.setEnabled(True)
            return
        if status == "skipped":
            version = str(getattr(update, "version", "") or "")
            self.update_status.setText(
                f"La versión {version or 'encontrada'} está omitida."
            )
            self.update_install_button.setVisible(False)
            self.update_skip_button.setVisible(False)
            self.update_restore_button.setVisible(True)
            return
        messages = {
            "current": "Tienes la versión más reciente.",
            "skipped": "La versión encontrada está omitida.",
            "unconfigured": "Servidor de actualizaciones aún no configurado.",
            "managed_externally": "Steam administra las actualizaciones de esta edición.",
        }
        self.update_status.setText(
            messages.get(status) or str(getattr(result, "message", "No se pudo buscar la actualización"))
        )
        self.update_install_button.setVisible(False)
        self.update_skip_button.setVisible(False)
        self.update_restore_button.setVisible(False)

    def set_update_skipped(self, version: str) -> None:
        self.update_status.setText(f"Versión {version} omitida. Puedes buscar otra vez cuando quieras.")
        self.update_install_button.setVisible(False)
        self.update_skip_button.setVisible(False)
        self.update_restore_button.setVisible(True)
        self.update_check_button.setEnabled(True)

    def set_update_downloading(self) -> None:
        self.update_status.setText("Descargando y verificando el instalador…")
        self.update_check_button.setEnabled(False)
        self.update_install_button.setEnabled(False)
        self.update_skip_button.setEnabled(False)
        self.update_restore_button.setVisible(False)
        self.update_progress.setValue(0)
        self.update_progress.setVisible(True)

    def set_update_progress(self, value: int) -> None:
        self.update_progress.setVisible(True)
        self.update_progress.setValue(max(0, min(100, int(value))))

    def set_update_error(self, message: str) -> None:
        self.update_status.setText(f"No se pudo actualizar: {message}")
        self.update_check_button.setEnabled(True)
        self.update_install_button.setEnabled(True)
        self.update_skip_button.setEnabled(True)

    def refresh_appearance_preview(self) -> None:
        values = self._appearance_values()
        self.background_preview.set_appearance(values)
        path = str(values.get("background_path", "") or "")
        if path and Path(path).is_file():
            pm = self.window.profile_manager
            wallpaper = find_wallpaper(pm.current_wallpaper_key()) if pm else None
            shown = wallpaper.name if wallpaper else Path(path).name
            self.background_name.setText(
                f"{shown} · {values['background_fit']} · {values['background_position']}"
            )
        else:
            self.background_name.setText("Fondo predeterminado de Nikaido")

    def setting(self, text: str, key: str, default: bool) -> QCheckBox:
        widget = QCheckBox(text)
        widget.setChecked(
            bool(
                self.window.profile_manager
                and self.window.profile_manager.get_setting(key, default)
            )
        )
        widget.toggled.connect(lambda value, k=key: self.save(k, value))
        return widget

    def save(self, key: str, value: Any) -> None:
        pm = self.window.profile_manager
        if pm:
            pm.set_setting(key, value)
            self.window.request_config_save()
        if key == "start_with_windows":
            self.configure_startup(bool(value))
        if key == "auto_connect" and self.window.connection_manager:
            if value:
                self.window.connection_manager.request_connect()
            else:
                self.window.connection_manager.disconnect()
        if key == "game_profiles_enabled" and self.window.game_profile_watcher:
            self.window.game_profile_watcher.set_enabled(bool(value))

    def configure_startup(self, enabled: bool) -> None:
        if sys.platform != "win32":
            return
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            )
            if enabled:
                if getattr(sys, "frozen", False):
                    command = f'"{sys.executable}" --minimized'
                else:
                    command = f'"{sys.executable}" "{Path(__file__).resolve().parents[1] / "main.py"}" --minimized'
                winreg.SetValueEx(key, "Nikaido", 0, winreg.REG_SZ, command)
            else:
                try:
                    winreg.DeleteValue(key, "Nikaido")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except OSError as exc:
            self.window.alert(
                f"Windows no permitió cambiar el inicio automático: {exc}"
            )


    def restart_wizard(self) -> None:
        self.window.show_welcome_wizard(force=True)

    def open_config(self) -> None:
        path = (
            self.window.profile_manager.get_config_dir()
            if self.window.profile_manager
            else ""
        )
        if path and sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif path:
            self.window.toast(path)

    def reset_all(self) -> None:
        if (
            QMessageBox.warning(
                self,
                "Restablecer ajustes",
                "Se perderán perfiles y ajustes personalizados. ¿Continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        if self.window.profile_manager:
            self.window.profile_manager.reset_to_defaults(purge_assets=True)
            self.window.toast(tr("Configuración restablecida. Reinicia Nikaido.", self.window.language))
