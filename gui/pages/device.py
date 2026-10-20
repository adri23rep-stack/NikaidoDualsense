"""Páginas de luces, vibración y audio extraídas de la interfaz monolítica."""

from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING


from ..ui_common import (
    logging,
    Any,
    C,
    Dict,
    Optional,
    QCheckBox,
    QColor,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
    button,
    card,
    label,
    os,
    sys,
)
from ..components import ControllerVisual, ScrollPage, SliderRow
from ..i18n import tr
from ..light_studio import (
    EffectTile,
    LightTimelinePreview,
    NeonEffectIcon,
    SHOWCASE_CATEGORIES,
    SHOWCASE_EFFECTS,
)
from src.audio_manager import DEFAULT_TARGET_MODE, sanitize_audio_config
from src.light_effects import EFFECT_SPECS, LIGHT_CONTROL_MODES, sample_light_effect
from src.player_led_battery import PLAYER_LED_MODES

if TYPE_CHECKING:
    from ..main_window import NikaidoWindow

logger = logging.getLogger(__name__)


PALETTE_PRESETS: Dict[str, Dict[str, Any]] = {
    "Nikaido": {
        "primary": [67, 215, 239],
        "secondary": [198, 63, 244],
        "palette": [[123, 63, 242], [255, 77, 214], [67, 215, 239], [59, 130, 246]],
    },
    "Vaporwave": {
        "primary": [255, 77, 214],
        "secondary": [94, 234, 212],
        "palette": [[255, 77, 214], [168, 85, 247], [94, 234, 212], [59, 130, 246]],
    },
    "Océano": {
        "primary": [34, 211, 238],
        "secondary": [37, 99, 235],
        "palette": [[8, 47, 73], [14, 116, 144], [34, 211, 238], [96, 165, 250]],
    },
    "Fuego": {
        "primary": [255, 72, 0],
        "secondary": [255, 190, 40],
        "palette": [[110, 0, 0], [255, 32, 0], [255, 112, 0], [255, 220, 70]],
    },
    "Hielo": {
        "primary": [67, 215, 239],
        "secondary": [96, 165, 250],
        "palette": [[20, 80, 255], [40, 210, 255], [210, 250, 255], [110, 160, 255]],
    },
}


class LightsPage(ScrollPage):
    """RGB Studio completo, integrado en la pestaña de luces existente."""

    PREVIEW_INTERVAL_MS = 33

    def __init__(self, window: "NikaidoWindow") -> None:
        super().__init__()
        self.window = window
        self._loading = False
        self._persist_timer = QTimer(self)
        self._persist_timer.setSingleShot(True)
        self._persist_timer.timeout.connect(self._persist_now)
        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(self.PREVIEW_INTERVAL_MS)
        self._preview_timer.timeout.connect(self._advance_preview)
        self._preview_origin = time.monotonic()
        self._paused_elapsed = 0.0
        self._preview_paused = False
        self._frame_counter = 0
        self._current_sample = None
        self.primary_color = QColor(67, 215, 239)
        self.secondary_color = QColor(198, 63, 244)
        self.effect_cards: Dict[str, EffectTile] = {}
        self.category_buttons: Dict[str, QPushButton] = {}
        self._active_category = "Todos"

        self.add_header(
            "Luces RGB y efectos",
            "RGB Studio ahora incluye vista previa animada, efectos reales, paletas rápidas, controles avanzados y audio reactivo dentro de la misma pestaña.",
        )

        self._build_main_studio()
        self._build_effect_gallery()
        self._build_timeline()
        self.refresh()
        self._preview_timer.start()

    # ------------------------------------------------------------------ UI
    def _build_main_studio(self) -> None:
        main_row = QHBoxLayout()
        main_row.setSpacing(14)

        controls = card()
        controls.setMinimumWidth(265)
        controls_box = QVBoxLayout(controls)
        controls_box.setContentsMargins(17, 16, 17, 18)
        controls_box.setSpacing(10)
        controls_box.addWidget(label("PALETA Y LUCES", "eyebrow"))
        controls_box.addWidget(label("Colores del perfil", "heading"))
        color_help = label(
            "El principal domina el efecto y el secundario crea transiciones, olas y destellos.",
            "muted",
        )
        color_help.setWordWrap(True)
        controls_box.addWidget(color_help)

        color_buttons = QHBoxLayout()
        self.primary_button = button("Principal", lambda: self.choose_color("primary"), primary=True)
        self.secondary_button = button("Secundario", lambda: self.choose_color("secondary"))
        color_buttons.addWidget(self.primary_button)
        color_buttons.addWidget(self.secondary_button)
        controls_box.addLayout(color_buttons)

        self.swatch = QFrame()
        self.swatch.setFixedHeight(42)
        controls_box.addWidget(self.swatch)

        controls_box.addWidget(label("PALETAS RÁPIDAS", "eyebrow"))
        palette_grid = QGridLayout()
        palette_grid.setHorizontalSpacing(7)
        palette_grid.setVerticalSpacing(7)
        for index, preset_name in enumerate(PALETTE_PRESETS):
            preset_button = button(preset_name, lambda _checked=False, name=preset_name: self.apply_palette_preset(name))
            preset_button.setMinimumHeight(34)
            palette_grid.addWidget(preset_button, index // 2, index % 2)
        controls_box.addLayout(palette_grid)

        controls_box.addWidget(QLabel("Paleta personalizada"))
        self.palette = QLineEdit()
        self.palette.setPlaceholderText("#FF006E, #7B3FF2, #43D7EF")
        self.palette.editingFinished.connect(self.apply)
        controls_box.addWidget(self.palette)

        controls_box.addWidget(label("QUIÉN CONTROLA EL RGB", "eyebrow"))
        self.light_control_mode = QComboBox()
        for mode_id, mode_name in LIGHT_CONTROL_MODES.items():
            self.light_control_mode.addItem(mode_name, mode_id)
        self.light_control_mode.currentIndexChanged.connect(self.apply_light_control_mode)
        controls_box.addWidget(self.light_control_mode)
        self.light_mode_help = label("", "muted")
        self.light_mode_help.setWordWrap(True)
        controls_box.addWidget(self.light_mode_help)

        controls_box.addWidget(label("LUCES BLANCAS DEL JUGADOR", "eyebrow"))
        self.player_led_mode = QComboBox()
        for mode_id, mode_name in PLAYER_LED_MODES.items():
            self.player_led_mode.addItem(mode_name, mode_id)
        self.player_led_mode.currentIndexChanged.connect(self.apply_player_settings)
        controls_box.addWidget(self.player_led_mode)

        self.player = QComboBox()
        for number, title in enumerate(
            ("Jugador 1", "Jugador 2", "Jugador 3", "Jugador 4", "Todas las luces"),
            start=1,
        ):
            self.player.addItem(title, number)
        self.player.currentIndexChanged.connect(self.apply_player_settings)
        controls_box.addWidget(self.player)

        self.charging_animation = QCheckBox("Animar mientras carga")
        self.charging_animation.toggled.connect(self.apply_player_settings)
        controls_box.addWidget(self.charging_animation)
        self.critical_blink = QCheckBox("Parpadear con batería crítica")
        self.critical_blink.toggled.connect(self.apply_player_settings)
        controls_box.addWidget(self.critical_blink)
        self.player_led_help = label(
            "100–76 %: cuatro luces · 75–51 %: tres · 50–26 %: dos · 25–0 %: una.",
            "muted",
        )
        self.player_led_help.setWordWrap(True)
        controls_box.addWidget(self.player_led_help)

        custom_actions = QHBoxLayout()
        custom_actions.addWidget(button("Guardar animación", self.save_custom, primary=True))
        custom_actions.addWidget(button("Eliminar", self.delete_custom, danger=True))
        controls_box.addLayout(custom_actions)
        controls_box.addStretch()
        main_row.addWidget(controls, 27)

        preview = card()
        preview_box = QVBoxLayout(preview)
        preview_box.setContentsMargins(18, 16, 18, 16)
        preview_box.setSpacing(8)
        preview_top = QHBoxLayout()
        preview_top.addWidget(label("VISTA PREVIA EN TIEMPO REAL", "eyebrow"))
        preview_top.addStretch()
        self.active_profile = label("Perfil: —", "muted")
        preview_top.addWidget(self.active_profile)
        preview_box.addLayout(preview_top)

        self.controller = ControllerVisual()
        self.controller.setMinimumHeight(285)
        preview_box.addWidget(self.controller, 1)

        preview_status = QHBoxLayout()
        self.preview_play = button("Pausar", self.toggle_preview)
        self.preview_restart = button("Reiniciar", self.restart_preview)
        preview_status.addWidget(self.preview_play)
        preview_status.addWidget(self.preview_restart)
        preview_status.addStretch()
        self.live_color = QFrame()
        self.live_color.setFixedSize(26, 26)
        preview_status.addWidget(self.live_color)
        self.preview_badge = QLabel("Efecto actual: Color fijo")
        self.preview_badge.setStyleSheet("font-weight:700;")
        preview_status.addWidget(self.preview_badge)
        preview_box.addLayout(preview_status)

        hardware_note = label(
            "Vista visual enriquecida. El DualSense físico recibe un color RGB global que cambia con la animación.",
            "muted",
        )
        hardware_note.setWordWrap(True)
        hardware_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_box.addWidget(hardware_note)
        main_row.addWidget(preview, 43)

        details = card()
        details.setMinimumWidth(292)
        details_box = QVBoxLayout(details)
        details_box.setContentsMargins(17, 16, 17, 18)
        details_box.setSpacing(9)
        details_box.addWidget(label("EFECTO ACTIVO", "eyebrow"))
        effect_header = QHBoxLayout()
        self.effect_detail_icon = NeonEffectIcon("static", size=76)
        effect_header.addWidget(self.effect_detail_icon)
        effect_header_text = QVBoxLayout()
        self.effect_title = label("Color fijo", "heading")
        self.effect_description = label(EFFECT_SPECS["static"].description, "muted")
        self.effect_description.setWordWrap(True)
        effect_header_text.addWidget(self.effect_title)
        effect_header_text.addWidget(self.effect_description)
        effect_header.addLayout(effect_header_text, 1)
        details_box.addLayout(effect_header)

        self.effect = QComboBox()
        self.effect.currentIndexChanged.connect(self._on_effect_selection_changed)
        details_box.addWidget(self.effect)

        self.speed = SliderRow("Velocidad", 0.1, 8.0, 1.0, decimals=1, suffix="×")
        self.brightness = SliderRow("Brillo", 0.02, 1.0, 1.0, decimals=2)
        self.intensity = SliderRow("Intensidad del efecto", 0.0, 1.0, 1.0, decimals=2)
        self.smoothing = SliderRow("Suavizado", 0.0, 0.95, 0.18, decimals=2)
        for control in (self.speed, self.brightness, self.intensity, self.smoothing):
            control.changed.connect(lambda _value: self.apply())
            details_box.addWidget(control)

        direction_row = QHBoxLayout()
        direction_row.addWidget(QLabel("Dirección"))
        self.direction = QComboBox()
        self.direction.addItem("Izquierda → derecha", 1)
        self.direction.addItem("Derecha → izquierda", -1)
        self.direction.currentIndexChanged.connect(self.apply)
        direction_row.addWidget(self.direction, 1)
        details_box.addLayout(direction_row)

        self.audio_gain = SliderRow("Sensibilidad de audio", 0.25, 5.0, 1.6, decimals=2, suffix="×")
        self.audio_gain.changed.connect(lambda _value: self.apply())
        details_box.addWidget(self.audio_gain)
        self.audio_meter = QProgressBar()
        self.audio_meter.setRange(0, 100)
        self.audio_meter.setValue(0)
        self.audio_meter.setTextVisible(True)
        self.audio_meter.setFormat("Nivel de audio: %p%")
        details_box.addWidget(self.audio_meter)
        self.audio_status = label("Audio reactivo inactivo", "muted")
        self.audio_status.setWordWrap(True)
        details_box.addWidget(self.audio_status)
        details_box.addStretch()
        main_row.addWidget(details, 30)

        self.layout.addLayout(main_row)

    def _build_effect_gallery(self) -> None:
        gallery = card()
        gallery_box = QVBoxLayout(gallery)
        gallery_box.setContentsMargins(18, 16, 18, 18)
        gallery_box.setSpacing(11)
        top = QHBoxLayout()
        top.addWidget(label("GALERÍA DE EFECTOS", "eyebrow"))
        top.addStretch()
        top.addWidget(label("Todos usan el mismo motor que el control físico", "muted"))
        gallery_box.addLayout(top)
        gallery_box.addWidget(label("Efectos animados completos", "heading"))

        filters = QHBoxLayout()
        for category in SHOWCASE_CATEGORIES:
            filter_button = QPushButton(category)
            filter_button.setCheckable(True)
            filter_button.setChecked(category == "Todos")
            filter_button.setCursor(Qt.CursorShape.PointingHandCursor)
            filter_button.clicked.connect(
                lambda _checked=False, selected=category: self.filter_effects(selected)
            )
            self.category_buttons[category] = filter_button
            filters.addWidget(filter_button)
        filters.addStretch()
        gallery_box.addLayout(filters)

        self.effect_grid = QGridLayout()
        self.effect_grid.setHorizontalSpacing(10)
        self.effect_grid.setVerticalSpacing(10)
        for index, effect_id in enumerate(SHOWCASE_EFFECTS):
            spec = EFFECT_SPECS[effect_id]
            tile = EffectTile(effect_id, spec.name, spec.category)
            tile.setToolTip(spec.description)
            tile.clicked.connect(self.select_effect_card)
            self.effect_cards[effect_id] = tile
            self.effect_grid.addWidget(tile, index // 5, index % 5)
        gallery_box.addLayout(self.effect_grid)
        self.layout.addWidget(gallery)

    def _build_timeline(self) -> None:
        timeline_card = card()
        box = QVBoxLayout(timeline_card)
        box.setContentsMargins(18, 16, 18, 18)
        box.setSpacing(8)
        top = QHBoxLayout()
        top.addWidget(label("VISTA DEL CICLO", "eyebrow"))
        top.addStretch()
        self.cycle_label = label("Ciclo: 1.00 s", "muted")
        top.addWidget(self.cycle_label)
        box.addLayout(top)
        help_text = label(
            "La franja superior muestra el color durante un ciclo; la curva inferior muestra el brillo real que recibe el control.",
            "muted",
        )
        help_text.setWordWrap(True)
        box.addWidget(help_text)
        self.timeline = LightTimelinePreview()
        box.addWidget(self.timeline)
        self.layout.addWidget(timeline_card)

    # ------------------------------------------------------------- data/model
    def _ordered_effects(self) -> list[tuple[str, str]]:
        engine = getattr(self.window, "light_effect_engine", None)
        effects = (
            engine.available_effects()
            if engine
            else [(effect_id, spec.name) for effect_id, spec in EFFECT_SPECS.items()]
        )
        order = {effect_id: index for index, effect_id in enumerate(EFFECT_SPECS)}

        def sort_key(item: tuple[str, str]) -> tuple[int, str]:
            effect_id, title = item
            if effect_id.startswith("custom:"):
                return 1000, title.lower()
            return order.get(effect_id, 900), title.lower()

        return sorted(effects, key=sort_key)

    def _fill_effects(self, selected: str = "static") -> None:
        self.effect.blockSignals(True)
        self.effect.clear()
        for effect_id, title in self._ordered_effects():
            self.effect.addItem(title, effect_id)
        index = self.effect.findData(selected)
        if index < 0 and selected.startswith("custom:"):
            index = self.effect.findData("custom")
        self.effect.setCurrentIndex(max(0, index))
        self.effect.blockSignals(False)

    def refresh(self) -> None:
        trigger = self.window.trigger_engine
        profile_id = trigger.get_current_profile() if trigger else None
        profile = trigger.get_profile(profile_id) if trigger and profile_id else None
        engine = getattr(self.window, "light_effect_engine", None)
        config = (
            engine.sanitize_config(profile.light_config)
            if engine and profile
            else {
                "effect": "static",
                "color": [67, 215, 239],
                "secondary_color": [198, 63, 244],
                "speed": 1.0,
                "brightness": 1.0,
                "intensity": 1.0,
                "direction": 1,
                "smoothing": 0.18,
                "audio_gain": 1.6,
                "audio_floor": 0.03,
                "palette": [],
                "custom_id": "",
            }
        )
        if profile:
            profile.light_config = dict(config)
        self._loading = True
        selected = str(config.get("effect", "static"))
        if selected == "custom" and config.get("custom_id"):
            selected = f"custom:{config['custom_id']}"
        self._fill_effects(selected)
        primary = config.get("color", [67, 215, 239])
        secondary = config.get("secondary_color", [198, 63, 244])
        self.primary_color = QColor(*primary[:3])
        self.secondary_color = QColor(*secondary[:3])
        self.speed.set_value(float(config.get("speed", 1.0)))
        self.brightness.set_value(float(config.get("brightness", 1.0)))
        self.intensity.set_value(float(config.get("intensity", 1.0)))
        self.smoothing.set_value(float(config.get("smoothing", 0.18)))
        self.audio_gain.set_value(float(config.get("audio_gain", 1.6)))
        self.direction.setCurrentIndex(max(0, self.direction.findData(int(config.get("direction", 1)))))
        self.palette.setText(
            ", ".join(
                "#{:02X}{:02X}{:02X}".format(*color[:3])
                for color in config.get("palette", [])
                if isinstance(color, (list, tuple)) and len(color) >= 3
            )
        )
        self.active_profile.setText(f"Perfil: {profile.name if profile else '—'}")
        light_mode = engine.get_control_mode() if engine else "nikaido"
        self.light_control_mode.setCurrentIndex(
            max(0, self.light_control_mode.findData(light_mode))
        )
        player_controller = getattr(self.window, "player_led_controller", None)
        player_config = player_controller.get_config() if player_controller else {
            "mode": "battery", "player_number": 1,
            "charging_animation": True, "critical_blink": True,
        }
        self.player_led_mode.setCurrentIndex(
            max(0, self.player_led_mode.findData(player_config.get("mode", "battery")))
        )
        self.player.setCurrentIndex(
            max(0, self.player.findData(int(player_config.get("player_number", 1))))
        )
        self.charging_animation.setChecked(bool(player_config.get("charging_animation", True)))
        self.critical_blink.setChecked(bool(player_config.get("critical_blink", True)))
        self._loading = False
        self._update_output_help()
        self._update_player_controls()
        self.update_swatch()
        self._sync_effect_ui()
        self.restart_preview()

    def current_config(self) -> Dict[str, Any]:
        return {
            "effect": self.effect.currentData() or "static",
            "color": [
                self.primary_color.red(),
                self.primary_color.green(),
                self.primary_color.blue(),
            ],
            "secondary_color": [
                self.secondary_color.red(),
                self.secondary_color.green(),
                self.secondary_color.blue(),
            ],
            "speed": self.speed.spin.value(),
            "brightness": self.brightness.spin.value(),
            "intensity": self.intensity.spin.value(),
            "direction": self.direction.currentData() or 1,
            "smoothing": self.smoothing.spin.value(),
            "audio_gain": self.audio_gain.spin.value(),
            "audio_floor": 0.03,
            "palette": self.palette.text(),
        }

    def _selected_effect_id(self) -> str:
        value = str(self.effect.currentData() or "static")
        return "custom" if value.startswith("custom:") else value

    def _custom_effects(self) -> Dict[str, Dict[str, Any]]:
        engine = getattr(self.window, "light_effect_engine", None)
        return engine.get_custom_effects() if engine else {}

    # -------------------------------------------------------------- interaction
    def _on_effect_selection_changed(self, *_args: Any) -> None:
        if self._loading:
            return
        self._sync_effect_ui()
        self.restart_preview()
        self.apply()

    def _sync_effect_ui(self) -> None:
        raw_value = str(self.effect.currentData() or "static")
        effect_id = self._selected_effect_id()
        spec = EFFECT_SPECS.get(effect_id, EFFECT_SPECS["custom"])
        title = self.effect.currentText() or spec.name
        self.effect_title.setText(title)
        self.effect_description.setText(spec.description)
        self.effect_detail_icon.set_effect(effect_id)
        self.preview_badge.setText(f"Efecto actual: {title}")
        for key, tile in self.effect_cards.items():
            tile.set_selected(key == effect_id)
        direction_enabled = bool(spec.supports_direction)
        self.direction.setEnabled(direction_enabled)
        audio_enabled = bool(spec.audio_reactive)
        self.audio_gain.setEnabled(audio_enabled)
        self.audio_meter.setVisible(audio_enabled)
        self.audio_status.setVisible(audio_enabled)
        speed = max(0.1, self.speed.spin.value())
        self.cycle_label.setText(f"Ciclo aproximado: {1.0 / speed:.2f} s")
        config = self.current_config()
        if raw_value.startswith("custom:"):
            config["effect"] = "custom"
            config["custom_id"] = raw_value.split(":", 1)[1]
        self.timeline.set_config(config, self._custom_effects())

    def filter_effects(self, category: str) -> None:
        self._active_category = category if category in SHOWCASE_CATEGORIES else "Todos"
        for name, control in self.category_buttons.items():
            control.blockSignals(True)
            control.setChecked(name == self._active_category)
            control.blockSignals(False)
        for effect_id, tile in self.effect_cards.items():
            visible = self._active_category == "Todos" or EFFECT_SPECS[effect_id].category == self._active_category
            tile.setVisible(visible)

    def select_effect_card(self, effect_id: str) -> None:
        index = self.effect.findData(effect_id)
        if index >= 0:
            self.effect.setCurrentIndex(index)

    def choose_color(self, which: str) -> None:
        current = self.primary_color if which == "primary" else self.secondary_color
        chosen = QColorDialog.getColor(current, self, "Color del DualSense")
        if not chosen.isValid():
            return
        if which == "primary":
            self.primary_color = chosen
        else:
            self.secondary_color = chosen
        self.update_swatch()
        self.restart_preview()
        self.apply()

    def apply_palette_preset(self, name: str) -> None:
        preset = PALETTE_PRESETS.get(name)
        if not preset:
            return
        self.primary_color = QColor(*preset["primary"])
        self.secondary_color = QColor(*preset["secondary"])
        self.palette.setText(
            ", ".join("#{:02X}{:02X}{:02X}".format(*color) for color in preset["palette"])
        )
        target_effect = {"Fuego": "fire", "Hielo": "ice"}.get(name)
        if target_effect:
            index = self.effect.findData(target_effect)
            if index >= 0:
                self.effect.setCurrentIndex(index)
        self.update_swatch()
        self.restart_preview()
        self.apply()

    def apply(self, *_args: Any) -> None:
        if self._loading:
            return
        lights = getattr(self.window, "light_effect_engine", None)
        trigger = self.window.trigger_engine
        profile_id = trigger.get_current_profile() if trigger else None
        profile = trigger.get_profile(profile_id) if trigger and profile_id else None
        self.update_swatch()
        self._sync_effect_ui()
        if not lights or not profile:
            return
        raw = self.current_config()
        selected = str(raw["effect"])
        config = lights.apply_config(raw)
        if selected.startswith("custom:"):
            config["effect"] = "custom"
            config["custom_id"] = selected.split(":", 1)[1]
            lights.apply_config(config)
        profile.light_config = config
        self._persist()

    # --------------------------------------------------------------- animation
    def _preview_elapsed(self) -> float:
        if self._preview_paused:
            return self._paused_elapsed
        return self._paused_elapsed + max(0.0, time.monotonic() - self._preview_origin)

    def restart_preview(self) -> None:
        self._paused_elapsed = 0.0
        self._preview_origin = time.monotonic()
        if self._preview_paused:
            self._preview_paused = False
            self.preview_play.setText("Pausar")
        self._advance_preview()

    def toggle_preview(self) -> None:
        if self._preview_paused:
            self._preview_origin = time.monotonic()
            self._preview_paused = False
            self.preview_play.setText("Pausar")
        else:
            self._paused_elapsed = self._preview_elapsed()
            self._preview_paused = True
            self.preview_play.setText("Reanudar")

    def _display_audio_level(self, elapsed: float, effect_id: str) -> tuple[float, bool, str]:
        if effect_id != "audio":
            return 0.0, False, ""
        engine = getattr(self.window, "light_effect_engine", None)
        status = engine.get_audio_status() if engine else {"available": False, "level": 0.0, "error": ""}
        real_level = max(0.0, min(1.0, float(status.get("level", 0.0))))
        available = bool(status.get("available"))
        if available:
            return real_level, True, "Audio de Windows detectado"
        simulated = 0.18 + 0.42 * (0.5 - 0.5 * math.cos(elapsed * math.tau * 1.7))
        message = "Vista previa simulada; el control usará audio real en Windows"
        error = str(status.get("error", "") or "").strip()
        if error and os.name == "nt":
            message = f"Vista previa simulada: {error[:120]}"
        return simulated, False, message

    def _advance_preview(self) -> None:
        if self._loading:
            return
        elapsed = self._preview_elapsed()
        raw_value = str(self.effect.currentData() or "static")
        effect_id = self._selected_effect_id()
        config = self.current_config()
        if raw_value.startswith("custom:"):
            config["effect"] = "custom"
            config["custom_id"] = raw_value.split(":", 1)[1]
        audio_level, audio_real, audio_message = self._display_audio_level(elapsed, effect_id)
        sample = sample_light_effect(
            config,
            elapsed,
            custom_effects=self._custom_effects(),
            audio_level=audio_level,
            segment_count=9,
        )
        self._current_sample = sample
        self.controller.set_light_frame(sample, effect_id)
        self.effect_detail_icon.set_frame(
            sample.progress,
            level=sample.level,
            audio_level=audio_level,
            selected=True,
        )
        self.timeline.set_frame(sample.progress, audio_level)
        color = QColor(*sample.color)
        self.live_color.setStyleSheet(
            f"background:{color.name()};border:1px solid rgba(255,255,255,0.35);border-radius:13px;"
        )
        self.audio_meter.setValue(round(audio_level * 100))
        if effect_id == "audio":
            self.audio_status.setText(audio_message)
            self.audio_status.setStyleSheet(
                f"color:{C['green'] if audio_real else C['yellow']};"
            )

        # La galería se anima a 15 FPS para no gastar de más dibujando trece
        # iconos mientras el control central conserva 30 FPS.
        self._frame_counter += 1
        if self._frame_counter % 2 == 0:
            base = self.current_config()
            custom_effects = self._custom_effects()
            for tile_effect, tile in self.effect_cards.items():
                tile_config = dict(base)
                tile_config["effect"] = tile_effect
                tile_audio = audio_level if tile_effect == "audio" else 0.0
                tile_sample = sample_light_effect(
                    tile_config,
                    elapsed,
                    custom_effects=custom_effects,
                    audio_level=tile_audio,
                    segment_count=7,
                )
                tile.set_frame(tile_sample)

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        if not self._preview_timer.isActive():
            self._preview_origin = time.monotonic()
            self._preview_timer.start()

    def hideEvent(self, event: Any) -> None:
        if self._preview_timer.isActive():
            self._paused_elapsed = self._preview_elapsed()
            self._preview_timer.stop()
        super().hideEvent(event)

    # --------------------------------------------------------------- persistence
    def save_custom(self) -> None:
        engine = getattr(self.window, "light_effect_engine", None)
        if not engine:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Guardar animación de luces")
        form = QFormLayout(dialog)
        name = QLineEdit("Mi animación")
        palette = QLineEdit(self.palette.text())
        palette.setPlaceholderText("#FF006E, #7B3FF2, #43D7EF")
        speed = QDoubleSpinBox()
        speed.setRange(0.1, 8.0)
        speed.setValue(self.speed.spin.value())
        form.addRow("Nombre", name)
        form.addRow("Colores", palette)
        form.addRow("Velocidad", speed)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            effect_id = engine.register_custom_effect(name.text(), palette.text(), speed.value())
        except ValueError as exc:
            self.window.alert(str(exc))
            return
        self._persist_custom_effects()
        self._fill_effects(f"custom:{effect_id}")
        self._sync_effect_ui()
        self.apply()
        self.window.toast("Animación de luces guardada")

    def delete_custom(self) -> None:
        value = str(self.effect.currentData() or "")
        if not value.startswith("custom:"):
            self.window.alert("Selecciona una animación personalizada")
            return
        engine = getattr(self.window, "light_effect_engine", None)
        if engine and engine.remove_custom_effect(value.split(":", 1)[1]):
            self._persist_custom_effects()
            self._fill_effects("static")
            self._sync_effect_ui()
            self.apply()

    def _persist_custom_effects(self) -> None:
        manager = self.window.profile_manager
        engine = getattr(self.window, "light_effect_engine", None)
        if manager and engine:
            manager.set_setting("custom_light_effects", engine.export_custom_effects())
            self.window.request_config_save()

    def _persist(self) -> None:
        self._persist_timer.start(220)

    def _persist_now(self) -> None:
        manager = self.window.profile_manager
        trigger = self.window.trigger_engine
        if manager and trigger:
            manager.set_setting("profile_overrides", trigger.export_profile_overrides())
            manager.set_custom_profiles(trigger.export_custom_profiles_to_dict())
            self.window.request_config_save()

    def update_swatch(self) -> None:
        self.primary_button.setText(self.primary_color.name().upper())
        self.secondary_button.setText(self.secondary_color.name().upper())
        self.primary_button.setStyleSheet(
            f"background:{self.primary_color.name()};color:white;font-weight:700"
        )
        self.secondary_button.setStyleSheet(
            f"background:{self.secondary_color.name()};color:white;font-weight:700"
        )
        self.swatch.setStyleSheet(
            "border-radius:12px;"
            f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {self.primary_color.name()},stop:0.50 #FF4DD6,stop:1 {self.secondary_color.name()});"
            "border:1px solid rgba(255,255,255,0.12);"
        )

    def _update_output_help(self) -> None:
        mode = str(self.light_control_mode.currentData() or "nikaido")
        descriptions = {
            "nikaido": "Nikaido recupera el color si un juego intenta reemplazarlo.",
            "balanced": "Los efectos animados siguen activos; un color fijo se manda una sola vez.",
            "game": "Nikaido deja de escribir RGB para que el juego tenga control completo.",
        }
        self.light_mode_help.setText(descriptions.get(mode, descriptions["nikaido"]))

    def apply_light_control_mode(self, *_args: Any) -> None:
        if self._loading:
            return
        mode = str(self.light_control_mode.currentData() or "nikaido")
        engine = getattr(self.window, "light_effect_engine", None)
        if engine:
            mode = engine.set_control_mode(mode)
        manager = self.window.profile_manager
        if manager:
            manager.set_setting("light_control_mode", mode)
            self.window.request_config_save()
        self._update_output_help()

    def _update_player_controls(self) -> None:
        mode = str(self.player_led_mode.currentData() or "battery")
        self.player.setEnabled(mode == "player")
        self.charging_animation.setEnabled(mode == "battery")
        self.critical_blink.setEnabled(mode == "battery")

    def apply_player_settings(self, *_args: Any) -> None:
        if self._loading:
            return
        config = {
            "mode": str(self.player_led_mode.currentData() or "battery"),
            "player_number": int(self.player.currentData() or 1),
            "charging_animation": self.charging_animation.isChecked(),
            "critical_blink": self.critical_blink.isChecked(),
            "critical_percent": 10,
        }
        controller = getattr(self.window, "player_led_controller", None)
        if controller:
            config = controller.apply_config(config)
        manager = self.window.profile_manager
        if manager:
            manager.set_setting("player_led", config)
            manager.set_setting("player_number", config["player_number"])
            self.window.request_config_save()
        self._update_player_controls()




class VibrationPage(ScrollPage):
    """Controles de los motores de vibracion, separados de L2/R2."""

    def __init__(self, window: "NikaidoWindow") -> None:
        super().__init__()
        self.window = window
        self._loading = False
        self._test_timer = QTimer(self)
        self._test_timer.setSingleShot(True)
        self._test_timer.timeout.connect(self.stop_test)
        self._persist_timer = QTimer(self)
        self._persist_timer.setSingleShot(True)
        self._persist_timer.timeout.connect(self._persist_now)

        bar = QHBoxLayout()
        bar.addWidget(label("Vibración", "title"))
        bar.addStretch()
        self.profile = QComboBox()
        self.profile.currentIndexChanged.connect(self.load)
        bar.addWidget(label("Perfil", "muted"))
        bar.addWidget(self.profile)
        self.layout.addLayout(bar)

        discover = card()
        discover_box = QHBoxLayout(discover)
        discover_box.setContentsMargins(16, 14, 16, 14)
        discover_icon = QLabel("↯")
        discover_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        discover_icon.setFixedSize(48, 48)
        discover_icon.setProperty("accentIcon", True)
        discover_icon.setStyleSheet("font-size:28px;background:#18162a;border-radius:12px")
        discover_box.addWidget(discover_icon)
        discover_text = QVBoxLayout()
        discover_text.setSpacing(2)
        discover_text.addWidget(label("¿Buscas la rigidez de L2 y R2?", "heading"))
        hint = label(
            "Los efectos, zonas, frecuencia y curvas ahora tienen su propia sección: Gatillos adaptativos.",
            "muted",
        )
        hint.setWordWrap(True)
        discover_text.addWidget(hint)
        discover_box.addLayout(discover_text, 1)
        discover_box.addWidget(
            button(
                "Abrir gatillos adaptativos  →",
                self.open_triggers,
                primary=True,
            )
        )
        self.layout.addWidget(discover)

        panel = card()
        box = QVBoxLayout(panel)
        box.setContentsMargins(18, 16, 18, 18)
        box.addWidget(label("MOTORES DE VIBRACIÓN", "eyebrow"))
        description = label(
            "Ajusta la fuerza general de vibración que se guarda dentro del perfil seleccionado.",
            "muted",
        )
        description.setWordWrap(True)
        box.addWidget(description)
        self.intensity = SliderRow("Intensidad general", 0, 255, 128, decimals=0)
        self.intensity.changed.connect(lambda _value: self.save())
        box.addWidget(self.intensity)

        presets = QHBoxLayout()
        presets.addWidget(label("Ajustes rápidos", "muted"))
        presets.addWidget(button("Suave", lambda: self.set_preset(70)))
        presets.addWidget(button("Equilibrada", lambda: self.set_preset(140)))
        presets.addWidget(button("Fuerte", lambda: self.set_preset(220)))
        presets.addStretch()
        box.addLayout(presets)
        self.layout.addWidget(panel)

        test_panel = card()
        test_box = QVBoxLayout(test_panel)
        test_box.setContentsMargins(18, 16, 18, 18)
        test_box.addWidget(label("PRUEBA DE MOTORES", "eyebrow"))
        test_help = label(
            "Prueba cada motor por separado o ambos al mismo tiempo. La prueba se detiene automáticamente.",
            "muted",
        )
        test_help.setWordWrap(True)
        test_box.addWidget(test_help)
        test_actions = QHBoxLayout()
        test_actions.addWidget(button("Motor izquierdo", lambda: self.test(True, False)))
        test_actions.addWidget(button("Ambos motores", lambda: self.test(True, True), primary=True))
        test_actions.addWidget(button("Motor derecho", lambda: self.test(False, True)))
        test_box.addLayout(test_actions)
        self.test_status = label("Listo para probar", "muted")
        self.test_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        test_box.addWidget(self.test_status)
        self.layout.addWidget(test_panel)

        feedback_panel = card()
        feedback_box = QVBoxLayout(feedback_panel)
        feedback_box.setContentsMargins(18, 16, 18, 18)
        feedback_top = QHBoxLayout()
        feedback_top.addWidget(label("VIBRACIÓN DEL JUEGO", "eyebrow"))
        feedback_top.addStretch()
        self.feedback_enabled = QCheckBox("Devolver vibración al DualSense")
        self.feedback_enabled.toggled.connect(self.save_feedback)
        feedback_top.addWidget(self.feedback_enabled)
        feedback_box.addLayout(feedback_top)
        feedback_help = label(
            "Recibe la vibración que el juego manda al control virtual Xbox/DS4 y la reproduce en los motores físicos del DualSense.",
            "muted",
        )
        feedback_help.setWordWrap(True)
        feedback_box.addWidget(feedback_help)
        self.feedback_strength = SliderRow("Fuerza global", 0.0, 2.0, 1.0, decimals=2, suffix="×")
        self.feedback_large = SliderRow(
            "Motor izquierdo / golpes", 0.0, 2.0, 1.0, decimals=2, suffix="×"
        )
        self.feedback_small = SliderRow(
            "Motor derecho / vibración fina", 0.0, 2.0, 1.0, decimals=2, suffix="×"
        )
        self.feedback_smoothing = SliderRow("Suavizado", 0, 120, 18, decimals=0, suffix=" ms")
        self.feedback_timeout = SliderRow(
            "Apagado de seguridad", 100, 1500, 350, decimals=0, suffix=" ms"
        )
        for control in (
            self.feedback_strength,
            self.feedback_large,
            self.feedback_small,
            self.feedback_smoothing,
            self.feedback_timeout,
        ):
            control.changed.connect(lambda _value: self.save_feedback())
            feedback_box.addWidget(control)
        self.feedback_swap = QCheckBox("Intercambiar motores")
        self.feedback_swap.toggled.connect(self.save_feedback)
        feedback_box.addWidget(self.feedback_swap)
        self.feedback_status = label("Esperando feedback del juego…", "muted")
        self.feedback_status.setWordWrap(True)
        feedback_box.addWidget(self.feedback_status)
        self.layout.addWidget(feedback_panel)
        self.layout.addStretch()

        self.refresh_profiles()
        self.load()
        self.refresh_feedback()

    def open_triggers(self) -> None:
        profile_id = self.profile.currentData()
        page = self.window.ensure_page("triggers")
        self.window.navigate("triggers")
        if profile_id and page is not None:
            page.select_profile(str(profile_id))

    def refresh_profiles(self) -> None:
        engine = self.window.trigger_engine
        current_data = self.profile.currentData()
        current = current_data or (engine.get_current_profile() if engine else None)
        self.profile.blockSignals(True)
        self.profile.clear()
        if engine:
            for profile_id, name in engine.get_profile_names():
                self.profile.addItem(name, profile_id)
        self.profile.setCurrentIndex(max(0, self.profile.findData(current)))
        self.profile.blockSignals(False)

    def select_profile(self, profile_id: str) -> None:
        self.profile.setCurrentIndex(max(0, self.profile.findData(profile_id)))
        self.load()

    def load(self, *_args: Any) -> None:
        engine = self.window.trigger_engine
        profile_id = self.profile.currentData()
        profile = engine.get_profile(profile_id) if engine and profile_id else None
        if not profile:
            return
        self._loading = True
        self.intensity.set_value(max(0, min(255, int(profile.rumble_intensity))))
        self._loading = False
        self.refresh_feedback_status()

    def refresh_feedback(self) -> None:
        bridge = self.window.virtual_feedback_bridge
        config = (
            bridge.get_config()
            if bridge
            else (
                self.window.profile_manager.get_setting("virtual_feedback", {})
                if self.window.profile_manager
                else {}
            )
        )
        self._loading = True
        self.feedback_enabled.setChecked(bool(config.get("enabled", True)))
        self.feedback_strength.set_value(float(config.get("strength", 1.0)))
        self.feedback_large.set_value(float(config.get("large_motor_scale", 1.0)))
        self.feedback_small.set_value(float(config.get("small_motor_scale", 1.0)))
        self.feedback_smoothing.set_value(float(config.get("smoothing_ms", 18)))
        self.feedback_timeout.set_value(float(config.get("idle_timeout_ms", 350)))
        self.feedback_swap.setChecked(bool(config.get("swap_motors", False)))
        self._loading = False
        self.refresh_feedback_status()

    def save_feedback(self, *_args: Any) -> None:
        if self._loading:
            return
        config = {
            "enabled": self.feedback_enabled.isChecked(),
            "strength": float(self.feedback_strength.spin.value()),
            "large_motor_scale": float(self.feedback_large.spin.value()),
            "small_motor_scale": float(self.feedback_small.spin.value()),
            "swap_motors": self.feedback_swap.isChecked(),
            "smoothing_ms": int(self.feedback_smoothing.spin.value()),
            "idle_timeout_ms": int(self.feedback_timeout.spin.value()),
            "minimum_output": 0,
        }
        bridge = self.window.virtual_feedback_bridge
        if bridge:
            config = bridge.apply_config(config)
        if self.window.profile_manager:
            self.window.profile_manager.set_setting("virtual_feedback", config)
            self.window.request_config_save()
        self.refresh_feedback_status()

    def refresh_feedback_status(self) -> None:
        bridge = self.window.virtual_feedback_bridge
        if not bridge:
            self.feedback_status.setText("El puente de vibración no está disponible")
            return
        snap = bridge.get_diagnostics_snapshot()
        emulator = getattr(self.window.connection_manager, "emulator", None)
        emulator_snap = (
            emulator.get_diagnostics_snapshot()
            if emulator and hasattr(emulator, "get_diagnostics_snapshot")
            else {}
        )
        if not snap.get("enabled"):
            text = "Desactivada. Las pruebas manuales de motores siguen disponibles."
        elif not emulator_snap.get("active"):
            text = "Lista. Activa la emulación Xbox 360 o DS4 para recibir vibración de los juegos."
        elif not emulator_snap.get("feedback_registered"):
            text = "El control virtual está activo, pero el driver no expuso feedback. Revisa ViGEm en Diagnóstico."
        elif snap.get("received"):
            output = snap.get("output") or (0, 0)
            text = f"Funcionando · {snap.get('received', 0)} eventos · salida L {output[0]} / R {output[1]}"
        else:
            text = "Control virtual listo; esperando que el juego mande vibración."
        if snap.get("last_error"):
            text += f" · Error: {snap.get('last_error')}"
        self.feedback_status.setText(text)

    def set_preset(self, value: int) -> None:
        self.intensity.set_value(value)
        self.save()

    def save(self, *_args: Any) -> None:
        if self._loading:
            return
        engine = self.window.trigger_engine
        profile_id = self.profile.currentData()
        profile = engine.get_profile(profile_id) if engine and profile_id else None
        if not profile:
            return
        profile.rumble_intensity = max(0, min(255, int(self.intensity.spin.value())))
        self._persist()

    def _persist(self) -> None:
        self._persist_timer.start(220)

    def _persist_now(self) -> None:
        manager = self.window.profile_manager
        engine = self.window.trigger_engine
        if manager and engine:
            manager.set_setting("profile_overrides", engine.export_profile_overrides())
            manager.set_custom_profiles(engine.export_custom_profiles_to_dict())
            self.window.request_config_save()

    def test(self, left: bool, right: bool) -> None:
        self.save()
        manager = self.window.connection_manager
        intensity = max(0, min(255, int(self.intensity.spin.value())))
        names = (
            "ambos motores" if left and right else ("motor izquierdo" if left else "motor derecho")
        )
        if manager is None or not hasattr(manager, "start_rumble_test"):
            self.test_status.setText("No se pudo iniciar: motor de vibración no disponible")
            self.window.toast("La prueba de vibración no está disponible", "error")
            return
        started = manager.start_rumble_test(
            intensity if left else 0,
            intensity if right else 0,
            duration_ms=900,
        )
        if not started:
            detail = ""
            if hasattr(manager, "get_rumble_diagnostics"):
                detail = str(manager.get_rumble_diagnostics().get("last_error") or "")
            self.test_status.setText("No se pudo enviar vibración al control")
            self.window.toast(detail or "Conecta el DualSense e inténtalo otra vez", "error")
            return
        self.test_status.setText(f"Probando {names} al {intensity} / 255…")
        self._test_timer.start(950)

    def stop_test(self) -> None:
        manager = self.window.connection_manager
        if manager and hasattr(manager, "stop_rumble_test"):
            manager.stop_rumble_test()
        elif manager:
            manager.set_rumble(0, 0)
        self.test_status.setText("Prueba terminada")




class AudioPage(ScrollPage):
    """Micrófono de Windows, botón MIC y LED naranja sincronizados."""

    def __init__(self, window: "NikaidoWindow") -> None:
        super().__init__()
        self.window = window
        self._loading = False
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._persist_now)
        self._volume_timer = QTimer(self)
        self._volume_timer.setSingleShot(True)
        self._volume_timer.timeout.connect(self._apply_volume_now)
        self._last_device_signature: tuple = ()
        self._last_live_signature: tuple = ()

        self.add_header(
            "Audio y micrófono",
            "Usa el botón MIC del DualSense para silenciar uno o todos los micrófonos de Windows.",
        )

        toolbar = card()
        toolbar_box = QHBoxLayout(toolbar)
        toolbar_box.addWidget(label("PERFIL", "eyebrow"))
        self.profile = QComboBox()
        self.profile.currentIndexChanged.connect(self.load)
        toolbar_box.addWidget(self.profile, 1)
        toolbar_box.addWidget(button("Actualizar dispositivos", self.refresh_devices, primary=True))
        toolbar_box.addWidget(button("Sonido de Windows", self.open_windows_sound))
        self.layout.addWidget(toolbar)

        row = QHBoxLayout()
        row.setSpacing(14)

        status_card = card()
        status = QVBoxLayout(status_card)
        status.setSpacing(12)
        status.addWidget(label("ESTADO EN VIVO", "eyebrow"))
        self.mic_icon = QLabel("●")
        self.mic_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mic_icon.setStyleSheet(f"font-size:74px;color:{C['muted']}")
        status.addWidget(self.mic_icon)
        self.state_title = label("Esperando a Windows…", "title")
        self.state_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status.addWidget(self.state_title)
        self.state_device = label("Micrófono: —", "muted")
        self.state_device.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_device.setWordWrap(True)
        status.addWidget(self.state_device)
        self.state_volume = label("Volumen: —", "muted")
        self.state_volume.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status.addWidget(self.state_volume)
        self.mute_button = button("Silenciar micrófono", self.toggle_mute, primary=True)
        status.addWidget(self.mute_button)
        self.runtime_error = QLabel("")
        self.runtime_error.setWordWrap(True)
        self.runtime_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.runtime_error.setProperty("muted", True)
        status.addWidget(self.runtime_error)
        status.addStretch()
        row.addWidget(status_card, 42)

        settings_card = card()
        settings = QVBoxLayout(settings_card)
        settings.setSpacing(10)
        settings.addWidget(label("CONTROL DEL MICRÓFONO", "eyebrow"))

        settings.addWidget(QLabel("Qué silencia el botón MIC"))
        self.target_mode = QComboBox()
        self.target_mode.addItem("Todos los micrófonos activos", "all")
        self.target_mode.addItem(
            "Todos excepto el micrófono del DualSense", "all_except_dualsense"
        )
        self.target_mode.addItem("Un micrófono específico", "selected")
        self.target_mode.currentIndexChanged.connect(self.save)
        settings.addWidget(self.target_mode)
        settings.addWidget(
            button("Usar esta opción en todos los perfiles", self.apply_target_to_all_profiles)
        )

        self.device_label = QLabel("Micrófono que controlará el botón")
        settings.addWidget(self.device_label)
        self.device = QComboBox()
        self.device.currentIndexChanged.connect(self.save)
        settings.addWidget(self.device)

        self.enabled = QCheckBox("Activar control de audio en este perfil")
        self.enabled.toggled.connect(self.save)
        settings.addWidget(self.enabled)

        self.button_enabled = QCheckBox("El botón MIC alterna activar / silenciar")
        self.button_enabled.toggled.connect(self.save)
        settings.addWidget(self.button_enabled)

        self.led_sync = QCheckBox("Sincronizar el LED naranja del DualSense")
        self.led_sync.toggled.connect(self.save)
        settings.addWidget(self.led_sync)

        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet(f"background:{C['border']}")
        settings.addWidget(separator)
        settings.addWidget(label("VOLUMEN Y ESTADO DEL PERFIL", "eyebrow"))

        self.apply_volume = QCheckBox("Aplicar este volumen al cambiar de perfil")
        self.apply_volume.toggled.connect(self.save)
        settings.addWidget(self.apply_volume)
        self.volume = SliderRow("Volumen del micrófono", 0, 100, 100, decimals=0, suffix="%")
        self.volume.changed.connect(self._volume_changed)
        settings.addWidget(self.volume)

        settings.addWidget(QLabel("Al aplicar el perfil"))
        self.mute_mode = QComboBox()
        self.mute_mode.addItem("Conservar el estado actual", "keep")
        self.mute_mode.addItem("Silenciar el micrófono", "muted")
        self.mute_mode.addItem("Activar el micrófono", "unmuted")
        self.mute_mode.currentIndexChanged.connect(self.save)
        settings.addWidget(self.mute_mode)

        explanation = label(
            "En “Todos los micrófonos”, el botón MIC también envía a Windows la misma orden que una tecla física de silencio del micrófono. Nikaido refuerza el cambio en todos los dispositivos y conserva el LED naranja sincronizado.",
            "muted",
        )
        explanation.setWordWrap(True)
        settings.addWidget(explanation)
        settings.addStretch()
        row.addWidget(settings_card, 58)
        self.layout.addLayout(row)

        self.refresh_profiles()
        self.load()
        manager = getattr(self.window, "audio_manager", None)
        if manager:
            manager.refresh_devices()
            self.window.call_later(350, self._load_devices_from_cache)
        self.refresh_live()

    def _translated(self, source: str) -> str:
        return tr(source, getattr(self.window, "language", "es"))

    def _set_runtime_text(self, widget: QWidget, source: str) -> None:
        # Los textos de estado cambian cada segundo. Guardar también la fuente
        # española permite que el selector de idioma traduzca el estado actual,
        # no la etiqueta inicial que tenía la página al construirse.
        widget.setProperty("_nikaido_i18n_text_source", str(source))
        widget.setText(self._translated(source))

    def refresh_profiles(self) -> None:
        engine = self.window.trigger_engine
        selected = self.profile.currentData()
        current = selected or (engine.get_current_profile() if engine else None)
        self.profile.blockSignals(True)
        self.profile.clear()
        if engine:
            for profile_id, name in engine.get_profile_names():
                self.profile.addItem(name, profile_id)
        self.profile.setCurrentIndex(max(0, self.profile.findData(current)))
        self.profile.blockSignals(False)

    def select_profile(self, profile_id: str) -> None:
        self.profile.setCurrentIndex(max(0, self.profile.findData(profile_id)))
        self.load()

    def _load_devices_from_cache(self, selected: Optional[str] = None) -> None:
        manager = getattr(self.window, "audio_manager", None)
        devices = manager.get_devices() if manager else []
        selected_id = str(selected or self.device.currentData() or "default")
        signature = tuple(
            (str(item.get("id", "")), str(item.get("name", "")), bool(item.get("is_default")))
            for item in devices
            if isinstance(item, dict)
        )
        selected_present = selected_id in ("", "default") or self.device.findData(selected_id) >= 0
        if signature == self._last_device_signature and self.device.count() and selected_present:
            return
        self._last_device_signature = signature
        self.device.blockSignals(True)
        self.device.clear()
        source_items = ["Predeterminado de Windows (cambia automáticamente)"]
        self.device.addItem(self._translated(source_items[0]), "default")
        for item in devices:
            if not isinstance(item, dict):
                continue
            device_id = str(item.get("id", "") or "")
            if not device_id:
                continue
            name = str(item.get("name", "Micrófono") or "Micrófono")
            if item.get("is_default"):
                name += " · predeterminado ahora"
            source_items.append(name)
            self.device.addItem(self._translated(name), device_id)
        index = self.device.findData(selected_id)
        if index < 0 and selected_id not in ("", "default"):
            missing = "Dispositivo guardado · actualmente desconectado"
            source_items.append(missing)
            self.device.addItem(self._translated(missing), selected_id)
            index = self.device.count() - 1
        # Evita que un cambio English -> Español tome el texto inglés mostrado
        # como si fuera la fuente original del combo dinámico.
        self.device.setProperty("_nikaido_i18n_combo_sources", source_items)
        self.device.setCurrentIndex(max(0, index))
        self.device.blockSignals(False)

    def refresh_devices(self) -> None:
        manager = getattr(self.window, "audio_manager", None)
        if not manager:
            self.window.toast(self._translated("El motor de audio no está disponible"), "error")
            return
        selected = str(self.device.currentData() or "default")
        manager.refresh_devices()
        self.window.toast(self._translated("Buscando micrófonos de Windows…"))
        self.window.call_later(
            400, lambda: self._load_devices_from_cache(selected)
        )

    def load(self, *_args: Any) -> None:
        from src.audio_manager import sanitize_audio_config

        engine = self.window.trigger_engine
        profile_id = self.profile.currentData()
        profile = engine.get_profile(profile_id) if engine and profile_id else None
        config = sanitize_audio_config(profile.audio_config if profile else {})
        self._loading = True
        self._load_devices_from_cache(config["device_id"])
        self.device.setCurrentIndex(max(0, self.device.findData(config["device_id"])))
        self.target_mode.setCurrentIndex(
            max(0, self.target_mode.findData(config["target_mode"]))
        )
        self.enabled.setChecked(config["enabled"])
        self.button_enabled.setChecked(config["button_enabled"])
        self.led_sync.setChecked(config["led_sync"])
        self.apply_volume.setChecked(config["apply_volume"])
        self.volume.set_value(config["volume"])
        self.mute_mode.setCurrentIndex(max(0, self.mute_mode.findData(config["profile_mute_mode"])))
        self._loading = False
        self._update_enabled_state()
        self.refresh_live()

    def current_config(self) -> Dict[str, Any]:
        from src.audio_manager import sanitize_audio_config

        return sanitize_audio_config(
            {
                "enabled": self.enabled.isChecked(),
                "button_enabled": self.button_enabled.isChecked(),
                "target_mode": self.target_mode.currentData() or DEFAULT_TARGET_MODE,
                "device_id": self.device.currentData() or "default",
                "led_sync": self.led_sync.isChecked(),
                "apply_volume": self.apply_volume.isChecked(),
                "volume": int(self.volume.spin.value()),
                "profile_mute_mode": self.mute_mode.currentData() or "keep",
            }
        )

    def save(self, *_args: Any) -> None:
        if self._loading:
            return
        engine = self.window.trigger_engine
        profile_id = self.profile.currentData()
        profile = engine.get_profile(profile_id) if engine and profile_id else None
        if not profile:
            return
        profile.audio_config = self.current_config()
        self._update_enabled_state()
        self._save_timer.start(220)
        if engine.get_current_profile() == profile_id:
            manager = getattr(self.window, "audio_manager", None)
            if manager:
                manager.apply_config(
                    profile.audio_config,
                    str(profile_id),
                    apply_profile_state=False,
                )

    def apply_target_to_all_profiles(self) -> None:
        """Copia solo «qué silencia el botón MIC» a todos los perfiles.

        El micrófono concreto, el volumen y el resto siguen siendo de cada perfil.
        """
        engine = self.window.trigger_engine
        if not engine:
            return
        mode = self.target_mode.currentData() or DEFAULT_TARGET_MODE
        changed = 0
        for profile in engine.get_all_profiles().values():
            config = sanitize_audio_config(profile.audio_config)
            if config["target_mode"] != mode:
                config["target_mode"] = mode
                profile.audio_config = config
                changed += 1
        current_id = engine.get_current_profile()
        current = engine.get_profile(current_id) if current_id else None
        manager = getattr(self.window, "audio_manager", None)
        if manager and current:
            manager.apply_config(
                current.audio_config, str(current_id), apply_profile_state=False
            )
        self._persist_now()
        self.window.toast(
            tr("Aplicado a todos los perfiles", self.window.language)
            if changed
            else tr("Todos los perfiles ya usaban esta opción", self.window.language),
            "success",
        )

    def _persist_now(self) -> None:
        manager = self.window.profile_manager
        engine = self.window.trigger_engine
        if manager and engine:
            manager.set_setting("profile_overrides", engine.export_profile_overrides())
            manager.set_custom_profiles(engine.export_custom_profiles_to_dict())
            self.window.request_config_save()

    def _update_enabled_state(self) -> None:
        enabled = self.enabled.isChecked()
        selected_mode = (self.target_mode.currentData() or DEFAULT_TARGET_MODE) == "selected"
        for widget in (
            self.button_enabled,
            self.led_sync,
            self.mute_mode,
            self.target_mode,
        ):
            widget.setEnabled(enabled)
        self.device_label.setEnabled(enabled and selected_mode)
        self.device.setEnabled(enabled and selected_mode)
        self.apply_volume.setEnabled(enabled and selected_mode)
        self.volume.setEnabled(enabled and selected_mode)

    def _volume_changed(self, _value: float) -> None:
        self.save()
        if self._loading:
            return
        profile_id = self.profile.currentData()
        engine = self.window.trigger_engine
        is_active = bool(engine and engine.get_current_profile() == profile_id)
        if is_active:
            self._volume_timer.start(160)

    def _apply_volume_now(self) -> None:
        manager = getattr(self.window, "audio_manager", None)
        selected_mode = (self.target_mode.currentData() or DEFAULT_TARGET_MODE) == "selected"
        if manager and self.enabled.isChecked() and selected_mode:
            manager.set_volume(int(self.volume.spin.value()))

    def toggle_mute(self) -> None:
        manager = getattr(self.window, "audio_manager", None)
        if not manager:
            self.window.toast(self._translated("El motor de audio no está disponible"), "error")
            return
        snapshot = manager.get_snapshot()
        if not snapshot.get("available"):
            manager.refresh_devices()
            self.window.toast(self._translated("Reintentando el acceso al micrófono…"))
            return
        manager.set_muted(not bool(snapshot.get("muted", False)))

    def refresh_live(self) -> None:
        manager = getattr(self.window, "audio_manager", None)
        if not manager:
            self._set_runtime_text(self.state_title, "Audio no disponible")
            self._set_runtime_text(self.runtime_error, "Nikaido no recibió AudioManager.")
            return
        snapshot = manager.get_snapshot()
        self._load_devices_from_cache()
        signature = (
            bool(snapshot.get("running")),
            bool(snapshot.get("available")),
            bool(snapshot.get("muted")),
            int(snapshot.get("volume", 0) or 0),
            str(snapshot.get("device_name", "")),
            str(snapshot.get("error", "")),
            bool(snapshot.get("enabled", True)),
            bool(snapshot.get("using_fallback", False)),
            str(snapshot.get("target_mode", DEFAULT_TARGET_MODE)),
            bool(snapshot.get("partially_muted", False)),
            int(snapshot.get("target_count", 0) or 0),
            int(snapshot.get("muted_count", 0) or 0),
            bool(snapshot.get("restore_pending", False)),
        )
        if signature == self._last_live_signature:
            return
        self._last_live_signature = signature
        available = bool(snapshot.get("available"))
        muted = bool(snapshot.get("muted"))
        enabled = bool(snapshot.get("enabled", True))
        target_mode = str(snapshot.get("target_mode", DEFAULT_TARGET_MODE) or DEFAULT_TARGET_MODE)
        is_group = target_mode in {"all", "all_except_dualsense"}
        target_count = int(snapshot.get("target_count", 0) or 0)
        muted_count = int(snapshot.get("muted_count", 0) or 0)
        partially_muted = bool(snapshot.get("partially_muted", False))
        if not enabled:
            self.mic_icon.setText("○")
            self.mic_icon.setStyleSheet(f"font-size:74px;color:{C['muted']}")
            self._set_runtime_text(self.state_title, "Control desactivado en este perfil")
            self._set_runtime_text(self.mute_button, "Control desactivado")
        elif available and muted:
            self.mic_icon.setText("●")
            self.mic_icon.setStyleSheet(f"font-size:74px;color:{C['yellow']}")
            if is_group:
                self._set_runtime_text(self.state_title, "Todos los micrófonos silenciados")
                self._set_runtime_text(self.mute_button, "Restaurar micrófonos")
            else:
                self._set_runtime_text(self.state_title, "Micrófono silenciado")
                self._set_runtime_text(self.mute_button, "Activar micrófono")
        elif available:
            if is_group and partially_muted:
                self.mic_icon.setText("◐")
                self.mic_icon.setStyleSheet(f"font-size:74px;color:{C['yellow']}")
                self._set_runtime_text(
                    self.state_title,
                    f"{muted_count} de {target_count} micrófonos silenciados",
                )
                self._set_runtime_text(self.mute_button, "Silenciar todos")
            else:
                self.mic_icon.setText("◉")
                self.mic_icon.setStyleSheet(f"font-size:74px;color:{C['green']}")
                self._set_runtime_text(
                    self.state_title,
                    "Micrófonos activos" if is_group else "Micrófono activo",
                )
                self._set_runtime_text(
                    self.mute_button,
                    "Silenciar todos" if is_group else "Silenciar micrófono",
                )
        else:
            self.mic_icon.setText("○")
            self.mic_icon.setStyleSheet(f"font-size:74px;color:{C['muted']}")
            self._set_runtime_text(self.state_title, "Audio no disponible")
            self._set_runtime_text(self.mute_button, "Reintentar")
        self.mute_button.setEnabled(bool(snapshot.get("running")) and enabled)
        if is_group:
            self._set_runtime_text(
                self.state_device, f"Alcance: {snapshot.get('device_name') or '—'}"
            )
            self._set_runtime_text(
                self.state_volume,
                f"Silenciados: {muted_count}/{target_count}" if target_count else "Silenciados: —",
            )
        else:
            self._set_runtime_text(
                self.state_device, f"Micrófono: {snapshot.get('device_name') or '—'}"
            )
            self._set_runtime_text(
                self.state_volume, f"Volumen: {int(snapshot.get('volume', 0) or 0)}%"
            )
        error = str(snapshot.get("error", "") or "")
        if error and "únicamente en Windows" in error:
            self._set_runtime_text(self.runtime_error, "Esta función se activa dentro de Windows.")
        elif not error and snapshot.get("using_fallback"):
            self._set_runtime_text(
                self.runtime_error,
                "El micrófono guardado está desconectado; usando el predeterminado de Windows.",
            )
        else:
            # Errores de pycaw/COM se muestran tal como llegaron. No son cadenas
            # de la interfaz y traducir palabras sueltas podría ocultar la causa.
            self.runtime_error.setProperty("_nikaido_i18n_text_source", error)
            self.runtime_error.setText(error)

    def open_windows_sound(self) -> None:
        if sys.platform == "win32":
            os.startfile("ms-settings:sound")  # type: ignore[attr-defined]
        else:
            self.window.toast(self._translated("Disponible en Windows"))
