"""Editor modal de perfiles, separado de la galería principal."""

from __future__ import annotations

import logging
import math
import time
from typing import TYPE_CHECKING, Any

from .ui_common import (
    C,
    QCheckBox,
    QColor,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPixmap,
    QPlainTextEdit,
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
from .light_studio import NeonEffectIcon, SHOWCASE_EFFECTS
from .i18n import translate_widget_tree
from .profile_gallery import ProfileCoverWidget
from .profile_visuals import (
    ICON_THEME_CHOICES,
    ProfileAvatarWidget,
    normalize_icon_theme,
)

if TYPE_CHECKING:
    from .main_window import NikaidoWindow

logger = logging.getLogger(__name__)


def profile_image_widget(profile_id: str, profile: Any, size: int = 54) -> ProfileAvatarWidget:
    return ProfileAvatarWidget(profile_id, profile, size=size)


class ProfileEditorDialog(QDialog):
    """Editor completo de un perfil sin tocar el hardware hasta guardar."""

    EFFECT_LABELS = {
        "off": "Libre / apagado",
        "rigid": "Rigidez",
        "pulse": "Pulso",
        "continuous_vibration": "Vibración continua",
        "sections": "Rigidez por secciones",
        "weapon_single": "Arma semiautomática",
        "weapon_automatic": "Arma automática",
        "weapon_sniper": "Francotirador",
        "weapon_bow": "Arco",
        "custom": "Personalizado",
    }

    def __init__(
        self,
        window: "NikaidoWindow",
        profile_id: str,
        profile: Any,
        *,
        creating: bool = False,
    ) -> None:
        super().__init__(window)
        import copy

        self.window = window
        self.profile_id = profile_id
        self.profile = copy.deepcopy(profile)
        self.creating = creating
        legacy_image = str(getattr(profile, "image_path", "") or "")
        self.icon_source = str(getattr(profile, "icon_path", "") or legacy_image)
        self.banner_source = str(getattr(profile, "banner_path", "") or legacy_image)
        self.icon_changed = False
        self.banner_changed = False
        # Alias públicos para extensiones y pruebas de versiones anteriores.
        self.image_source = self.icon_source
        self.image_changed = False
        self.primary_color = QColor(0, 100, 255)
        self.secondary_color = QColor(198, 63, 244)
        self.setWindowTitle("Crear perfil" if creating else f"Editar {profile.name}")
        self.resize(760, 690)

        root = QVBoxLayout(self)
        tabs = configure_tabs(QTabWidget())
        root.addWidget(tabs, 1)
        tabs.addTab(self._general_tab(), "General")
        tabs.addTab(self._trigger_tab("left"), "L2")
        tabs.addTab(self._trigger_tab("right"), "R2")
        tabs.addTab(self._profile_features_tab(), "Perfil completo")

        self._preview_origin = time.monotonic()
        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(250)
        self._preview_timer.timeout.connect(self._advance_preview)
        reduce_motion = bool(
            self.window.profile_manager.get_setting("appearance.reduce_motion", False)
            if self.window.profile_manager
            else False
        )
        if not reduce_motion:
            self._preview_timer.start()
        self._sync_light_preview()

        self.validation = QLabel("")
        self.validation.setWordWrap(True)
        self.validation.setStyleSheet(f"color:{C['danger']};font-weight:700")
        self.validation.hide()
        root.addWidget(self.validation)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_changes)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        translate_widget_tree(self, getattr(self.window, "language", "es"))

    def done(self, result: int) -> None:  # pragma: no cover - ciclo de vida Qt
        """Detiene el preview antes de cerrar para no dejar timers huérfanos."""
        self._preview_timer.stop()
        super().done(result)

    def _general_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)

        self.name_edit = QLineEdit(self.profile.name)
        self.name_edit.setMaxLength(80)
        self.name_edit.setPlaceholderText("Ej. Horror inmersivo")
        self.name_edit.textChanged.connect(self._update_icon_preview)

        self.category_edit = QComboBox()
        self.category_edit.setEditable(True)
        self.category_edit.addItems(
            [
                "Shooter",
                "Precisión",
                "Acción",
                "Conducción",
                "Aventura",
                "Inmersión",
                "Sigilo",
                "Deportes",
                "Arcade",
                "General",
                "Personal",
            ]
        )
        current_category = str(self.profile.category or "Personal")
        category_index = self.category_edit.findText(current_category)
        if category_index < 0:
            self.category_edit.addItem(current_category)
            category_index = self.category_edit.count() - 1
        self.category_edit.setCurrentIndex(category_index)
        self.category_edit.currentTextChanged.connect(self._update_icon_preview)

        self.description_edit = QPlainTextEdit()
        self.description_edit.setPlainText(self.profile.description)
        self.description_edit.setPlaceholderText(
            "Explica cómo se sentirá el perfil y para qué tipo de juego sirve."
        )
        self.description_edit.setFixedHeight(84)

        self.tags_edit = QLineEdit(", ".join(getattr(self.profile, "tags", []) or []))
        self.tags_edit.setPlaceholderText("Ej. FPS, Competitivo, Respuesta rápida")
        self.tags_edit.setMaxLength(320)

        form.addRow("Nombre", self.name_edit)
        form.addRow("Categoría", self.category_edit)
        form.addRow("Descripción", self.description_edit)
        form.addRow("Etiquetas", self.tags_edit)

        media_card = card(sub=True)
        media_layout = QVBoxLayout(media_card)
        media_layout.setContentsMargins(14, 14, 14, 14)
        media_layout.setSpacing(12)

        banner_heading = QLabel("Banner del perfil")
        banner_heading.setStyleSheet("font-weight:700")
        media_layout.addWidget(banner_heading)
        self.banner_preview = ProfileCoverWidget(
            self.profile_id, self.profile, detail=False
        )
        self.banner_preview.setMinimumHeight(138)
        self.banner_preview.setMaximumHeight(154)
        media_layout.addWidget(self.banner_preview)
        banner_actions = QHBoxLayout()
        banner_actions.addWidget(
            button("Elegir banner", self.choose_banner, primary=True)
        )
        banner_actions.addWidget(
            button("Restaurar predeterminado", self.clear_banner)
        )
        banner_actions.addStretch()
        media_layout.addLayout(banner_actions)
        banner_hint = QLabel(
            "Recomendado: imagen horizontal 16:9 o 3:1. Nikaido la recorta sin deformarla."
        )
        banner_hint.setWordWrap(True)
        banner_hint.setProperty("muted", True)
        media_layout.addWidget(banner_hint)

        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet(f"background:{C['border']}")
        media_layout.addWidget(separator)

        icon_heading = QLabel("Icono del perfil")
        icon_heading.setStyleSheet("font-weight:700")
        media_layout.addWidget(icon_heading)
        icon_row = QHBoxLayout()
        self.image_preview = profile_image_widget(self.profile_id, self.profile, 84)
        icon_row.addWidget(self.image_preview)
        icon_actions = QVBoxLayout()
        icon_actions.addWidget(button("Elegir icono", self.choose_icon, primary=True))
        icon_actions.addWidget(button("Usar icono predeterminado", self.clear_icon))
        icon_actions.addStretch()
        icon_row.addLayout(icon_actions)
        icon_row.addStretch()
        media_layout.addLayout(icon_row)

        self.icon_theme = QComboBox()
        for title, token in ICON_THEME_CHOICES:
            self.icon_theme.addItem(title, token)
        current_theme = normalize_icon_theme(
            getattr(self.profile, "icon", ""),
            fallback="theme:custom",
        )
        self.icon_theme.setCurrentIndex(max(0, self.icon_theme.findData(current_theme)))
        self.icon_theme.currentIndexChanged.connect(self._update_icon_preview)
        media_layout.addWidget(QLabel("Diseño usado cuando no hay icono personalizado"))
        media_layout.addWidget(self.icon_theme)
        form.addRow("Identidad visual", media_card)

        self.rumble = QSpinBox()
        self.rumble.setRange(0, 255)
        self.rumble.setValue(int(self.profile.rumble_intensity))
        self.rumble.setSuffix(" / 255")
        form.addRow("Intensidad de vibración", self.rumble)

        hint = QLabel(
            "Icono y banner se guardan por separado. Al restaurarlos, los perfiles incluidos vuelven a usar el arte de Nikaido."
        )
        hint.setWordWrap(True)
        hint.setProperty("muted", True)
        form.addRow(hint)
        return page

    def _trigger_tab(self, side: str) -> QWidget:
        from src.trigger_engine import TriggerEffectType, get_trigger_presets

        effect = self.profile.left_trigger if side == "left" else self.profile.right_trigger
        page = QWidget()
        box = QVBoxLayout(page)
        box.setSpacing(12)

        preset_card = card(sub=True)
        preset_layout = QVBoxLayout(preset_card)
        preset_layout.setContentsMargins(12, 12, 12, 12)
        preset_layout.setSpacing(8)
        preset_title = QLabel("Biblioteca de sensaciones")
        preset_title.setStyleSheet("font-weight:700")
        preset_layout.addWidget(preset_title)
        preset_row = QHBoxLayout()
        preset_combo = QComboBox()
        presets = get_trigger_presets()
        for preset_item in presets:
            preset_combo.addItem(
                f"{preset_item.category} · {preset_item.name}",
                preset_item.preset_id,
            )
        preset_row.addWidget(preset_combo, 1)
        preset_row.addWidget(
            button(
                "Cargar preset",
                lambda: self._load_trigger_preset(side),
                primary=True,
            )
        )
        preset_layout.addLayout(preset_row)
        preset_description = QLabel(presets[0].description if presets else "")
        preset_description.setWordWrap(True)
        preset_description.setProperty("muted", True)
        preset_layout.addWidget(preset_description)
        box.addWidget(preset_card)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(9)
        effect_type = QComboBox()
        for value in TriggerEffectType:
            effect_type.addItem(self.EFFECT_LABELS.get(value.value, value.value), value.value)
        effect_type.setCurrentIndex(max(0, effect_type.findData(effect.effect_type.value)))
        intensity = QSpinBox()
        intensity.setRange(0, 255)
        intensity.setValue(int(effect.intensity))
        start = QSpinBox()
        start.setRange(0, 9)
        start.setValue(int(effect.start_position))
        end = QSpinBox()
        end.setRange(0, 9)
        end.setValue(int(effect.end_position))
        frequency = QSpinBox()
        frequency.setRange(0, 255)
        frequency.setValue(int(effect.frequency))
        frequency.setSuffix(" Hz")
        animated = QCheckBox("Animar la resistencia")
        animated.setChecked(bool(effect.animated))
        animation_speed = QDoubleSpinBox()
        animation_speed.setRange(0.1, 8.0)
        animation_speed.setSingleStep(0.1)
        animation_speed.setValue(float(effect.animation_speed))
        animation_speed.setSuffix("×")
        curve = QComboBox()
        for title, value in (
            ("Lineal", "linear"),
            ("Entrada suave", "ease_in"),
            ("Salida suave", "ease_out"),
            ("Suave completa", "ease_in_out"),
            ("Seno", "sine"),
            ("Rebote", "bounce"),
        ):
            curve.addItem(title, value)
        curve.setCurrentIndex(max(0, curve.findData(effect.animation_curve)))
        form.addRow("Tipo de efecto", effect_type)
        form.addRow("Rigidez / intensidad", intensity)
        form.addRow("Zona inicial", start)
        form.addRow("Zona final", end)
        form.addRow("Frecuencia", frequency)
        form.addRow(animated)
        form.addRow("Velocidad", animation_speed)
        form.addRow("Curva de animación", curve)
        box.addLayout(form)

        vibration_card = card(sub=True)
        vibration_form = QFormLayout(vibration_card)
        vibration_enabled = QCheckBox("Vibración adicional al presionar")
        vibration_enabled.setChecked(bool(effect.vibration_enabled))
        vibration_intensity = QSpinBox()
        vibration_intensity.setRange(0, 255)
        vibration_intensity.setValue(int(effect.vibration_intensity))
        vibration_frequency = QSpinBox()
        vibration_frequency.setRange(1, 255)
        vibration_frequency.setValue(int(effect.vibration_frequency))
        vibration_frequency.setSuffix(" Hz")
        vibration_start = QSpinBox()
        vibration_start.setRange(0, 9)
        vibration_start.setValue(int(effect.vibration_start_position))
        vibration_end = QSpinBox()
        vibration_end.setRange(0, 9)
        vibration_end.setValue(int(effect.vibration_end_position))
        vibration_form.addRow(vibration_enabled)
        vibration_form.addRow("Intensidad", vibration_intensity)
        vibration_form.addRow("Frecuencia", vibration_frequency)
        vibration_form.addRow("Inicio", vibration_start)
        vibration_form.addRow("Final", vibration_end)
        box.addWidget(vibration_card)

        quick_actions = QHBoxLayout()
        quick_actions.addWidget(
            button(
                "Copiar a R2" if side == "left" else "Copiar a L2",
                lambda: self._copy_trigger_to_other(side),
            )
        )
        quick_actions.addWidget(
            button(
                "Dejar libre",
                lambda: self._set_trigger_free(side),
            )
        )
        quick_actions.addStretch()
        box.addLayout(quick_actions)
        box.addStretch()

        self.__dict__[f"{side}_controls"] = {
            "effect_type": effect_type,
            "intensity": intensity,
            "start": start,
            "end": end,
            "frequency": frequency,
            "animated": animated,
            "animation_speed": animation_speed,
            "curve": curve,
            "vibration_enabled": vibration_enabled,
            "vibration_intensity": vibration_intensity,
            "vibration_frequency": vibration_frequency,
            "vibration_start": vibration_start,
            "vibration_end": vibration_end,
            "preset": preset_combo,
            "preset_description": preset_description,
        }
        preset_combo.currentIndexChanged.connect(
            lambda _index, current_side=side: self._update_trigger_preset_description(current_side)
        )
        return page

    def _profile_features_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.macros_enabled = QCheckBox("Activar macros al usar este perfil")
        self.macros_enabled.setChecked(bool(self.profile.macros_enabled))
        form.addRow(self.macros_enabled)

        config = dict(getattr(self.profile, "light_config", {}) or {})
        self.light_effect = QComboBox()
        engine = getattr(self.window, "light_effect_engine", None)
        effects = engine.available_effects() if engine else [
            ("static", "Color fijo"),
            ("breathe", "Respiración"),
            ("pulse", "Pulso"),
            ("rainbow", "RGB arcoíris"),
            ("wave", "Ola neón"),
            ("comet", "Cometa"),
            ("heartbeat", "Latido"),
            ("aurora", "Aurora"),
            ("plasma", "Plasma"),
            ("fire", "Fuego"),
            ("ice", "Hielo"),
            ("police", "Alerta roja y azul"),
            ("audio", "Audio reactivo"),
            ("custom", "Animación personalizada"),
        ]
        for effect_id, title in effects:
            self.light_effect.addItem(title, effect_id)
        selected_effect = str(config.get("effect", "static"))
        if selected_effect == "custom" and config.get("custom_id"):
            selected_effect = f"custom:{config['custom_id']}"
        self.light_effect.setCurrentIndex(max(0, self.light_effect.findData(selected_effect)))
        self.light_effect.currentIndexChanged.connect(self._sync_light_preview)

        preview_card = card(sub=True)
        preview_layout = QHBoxLayout(preview_card)
        preview_layout.setContentsMargins(12, 10, 12, 10)
        self.light_preview_icon = NeonEffectIcon(
            selected_effect.split(":", 1)[0] if selected_effect else "static",
            size=68,
        )
        preview_layout.addWidget(self.light_preview_icon)
        preview_text = QVBoxLayout()
        preview_text.addWidget(label("Vista previa del efecto", "heading"))
        preview_note = QLabel(
            "La vista previa no aplica nada al control hasta guardar."
        )
        preview_note.setWordWrap(True)
        preview_note.setProperty("muted", True)
        preview_text.addWidget(preview_note)
        preview_layout.addLayout(preview_text, 1)
        form.addRow("Preview", preview_card)

        primary = config.get("color", [0, 100, 255])
        secondary = config.get("secondary_color", [198, 63, 244])
        self.primary_color = QColor(*primary[:3]) if len(primary) >= 3 else QColor(0, 100, 255)
        self.secondary_color = QColor(*secondary[:3]) if len(secondary) >= 3 else QColor(198, 63, 244)
        self.primary_button = button("Elegir color principal", lambda: self._choose_color("primary"))
        self.secondary_button = button("Elegir color secundario", lambda: self._choose_color("secondary"))
        self._update_color_buttons()
        self.light_speed = QDoubleSpinBox()
        self.light_speed.setRange(0.1, 8.0)
        self.light_speed.setSingleStep(0.1)
        self.light_speed.setValue(float(config.get("speed", 1.0)))
        self.light_brightness = QSpinBox()
        self.light_brightness.setRange(2, 100)
        self.light_brightness.setValue(int(float(config.get("brightness", 1.0)) * 100))
        self.light_brightness.setSuffix("%")
        self.light_intensity = QSpinBox()
        self.light_intensity.setRange(0, 100)
        self.light_intensity.setValue(int(float(config.get("intensity", 1.0)) * 100))
        self.light_intensity.setSuffix("%")
        self.light_smoothing = QSpinBox()
        self.light_smoothing.setRange(0, 95)
        self.light_smoothing.setValue(int(float(config.get("smoothing", 0.18)) * 100))
        self.light_smoothing.setSuffix("%")
        self.light_direction = QComboBox()
        self.light_direction.addItem("Izquierda → derecha", 1)
        self.light_direction.addItem("Derecha → izquierda", -1)
        self.light_direction.setCurrentIndex(
            max(0, self.light_direction.findData(int(config.get("direction", 1))))
        )
        self.light_audio_gain = QDoubleSpinBox()
        self.light_audio_gain.setRange(0.25, 5.0)
        self.light_audio_gain.setSingleStep(0.05)
        self.light_audio_gain.setDecimals(2)
        self.light_audio_gain.setValue(float(config.get("audio_gain", 1.6)))
        self.light_audio_gain.setSuffix("×")
        palette_text = ", ".join(
            "#{:02X}{:02X}{:02X}".format(*color[:3])
            for color in config.get("palette", [])
            if isinstance(color, (list, tuple)) and len(color) >= 3
        )
        self.palette = QLineEdit(palette_text)
        self.palette.setPlaceholderText("#FF006E, #7B3FF2, #43D7EF")
        form.addRow("Efecto de luces", self.light_effect)
        form.addRow("Color principal", self.primary_button)
        form.addRow("Color secundario", self.secondary_button)
        form.addRow("Velocidad", self.light_speed)
        form.addRow("Brillo", self.light_brightness)
        form.addRow("Intensidad", self.light_intensity)
        form.addRow("Suavizado", self.light_smoothing)
        form.addRow("Dirección", self.light_direction)
        form.addRow("Sensibilidad de audio", self.light_audio_gain)
        form.addRow("Paleta personalizada", self.palette)
        note = QLabel(
            "Input Studio, curvas de sticks y drift también quedan ligados al ID del perfil. "
            "Al crear uno nuevo se copia la configuración del perfil activo."
        )
        note.setWordWrap(True)
        note.setProperty("muted", True)
        form.addRow(note)
        return page

    def _update_trigger_preset_description(self, side: str) -> None:
        from src.trigger_engine import TRIGGER_PRESETS

        controls = self.__dict__.get(f"{side}_controls", {})
        combo = controls.get("preset")
        description = controls.get("preset_description")
        if combo is None or description is None:
            return
        preset = TRIGGER_PRESETS.get(str(combo.currentData() or ""))
        description.setText(preset.description if preset else "Preset no disponible")

    def _fill_trigger_controls(self, side: str, effect: Any) -> None:
        import copy

        controls = self.__dict__.get(f"{side}_controls")
        if not controls:
            return
        restored = copy.deepcopy(effect)
        if side == "left":
            self.profile.left_trigger = restored
        else:
            self.profile.right_trigger = restored
        controls["effect_type"].setCurrentIndex(
            max(0, controls["effect_type"].findData(restored.effect_type.value))
        )
        controls["intensity"].setValue(int(restored.intensity))
        controls["start"].setValue(int(restored.start_position))
        controls["end"].setValue(int(restored.end_position))
        controls["frequency"].setValue(int(restored.frequency))
        controls["animated"].setChecked(bool(restored.animated))
        controls["animation_speed"].setValue(float(restored.animation_speed))
        controls["curve"].setCurrentIndex(
            max(0, controls["curve"].findData(restored.animation_curve))
        )
        controls["vibration_enabled"].setChecked(bool(restored.vibration_enabled))
        controls["vibration_intensity"].setValue(int(restored.vibration_intensity))
        controls["vibration_frequency"].setValue(int(restored.vibration_frequency))
        controls["vibration_start"].setValue(int(restored.vibration_start_position))
        controls["vibration_end"].setValue(int(restored.vibration_end_position))

    def _load_trigger_preset(self, side: str) -> None:
        from src.trigger_engine import effect_from_preset

        controls = self.__dict__.get(f"{side}_controls", {})
        combo = controls.get("preset")
        if combo is None:
            return
        try:
            effect = effect_from_preset(str(combo.currentData() or "free"))
        except KeyError:
            self.window.alert("Ese preset de gatillo ya no está disponible")
            return
        self._fill_trigger_controls(side, effect)

    def _copy_trigger_to_other(self, side: str) -> None:
        import copy

        self._write_trigger(side)
        source = self.profile.left_trigger if side == "left" else self.profile.right_trigger
        target = "right" if side == "left" else "left"
        self._fill_trigger_controls(target, copy.deepcopy(source))

    def _set_trigger_free(self, side: str) -> None:
        from src.trigger_engine import effect_from_preset

        self._fill_trigger_controls(side, effect_from_preset("free"))

    def _sync_light_preview(self, *_args: Any) -> None:
        if not hasattr(self, "light_preview_icon") or not hasattr(self, "light_effect"):
            return
        selected = str(self.light_effect.currentData() or "static")
        effect_id = selected.split(":", 1)[0]
        if effect_id == "custom":
            effect_id = "rainbow"
        self.light_preview_icon.set_effect(
            effect_id if effect_id in SHOWCASE_EFFECTS else "static"
        )

    def _advance_preview(self) -> None:
        reduced = bool(
            self.window.profile_manager
            and self.window.profile_manager.get_setting("appearance.reduce_motion", False)
        )
        elapsed = time.monotonic() - self._preview_origin
        progress = 0.18 if reduced else (elapsed % 4.0) / 4.0
        level = 0.82 if reduced else 0.76 + 0.24 * (0.5 + 0.5 * math.sin(progress * math.tau))
        engine = getattr(self.window, "light_effect_engine", None)
        audio_level = float(engine.get_audio_level()) if engine else 0.0
        if hasattr(self, "light_preview_icon"):
            self.light_preview_icon.set_frame(
                progress,
                level=level,
                audio_level=audio_level,
                selected=True,
            )
        self._preview_timer.setInterval(320 if reduced else 180)

    def _choose_visual_file(self, title: str, *, preview_size: tuple[int, int]) -> tuple[str, QPixmap]:
        path, _ = QFileDialog.getOpenFileName(
            self, title, "", "Imágenes (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if not path:
            return "", QPixmap()
        manager = self.window.profile_manager
        if not manager or not manager.validate_profile_image(path):
            self.window.alert("La imagen no es válida o es demasiado grande.")
            return "", QPixmap()
        try:
            from PIL import Image, ImageOps
            from PIL.ImageQt import ImageQt

            with Image.open(path) as source:
                preview = ImageOps.exif_transpose(source).convert("RGBA")
                preview.thumbnail(preview_size, Image.Resampling.LANCZOS)
                qimage = ImageQt(preview)
                pixmap = QPixmap.fromImage(qimage.copy())
        except Exception as exc:
            logger.warning("No se pudo crear la vista previa segura: %s", exc)
            self.window.alert("No se pudo leer la imagen seleccionada.")
            return "", QPixmap()
        return path, pixmap

    def choose_icon(self) -> None:
        path, pixmap = self._choose_visual_file(
            "Elegir icono del perfil", preview_size=(512, 512)
        )
        if not path:
            return
        self.icon_source = path
        self.icon_changed = True
        self.image_source = path
        self.image_changed = True
        if not pixmap.isNull():
            self.image_preview.set_preview_pixmap(
                pixmap.scaled(
                    168,
                    168,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

    def choose_banner(self) -> None:
        path, pixmap = self._choose_visual_file(
            "Elegir banner del perfil", preview_size=(1600, 900)
        )
        if not path:
            return
        self.banner_source = path
        self.banner_changed = True
        if not pixmap.isNull():
            self.banner_preview.set_preview_pixmap(pixmap)

    def choose_image(self) -> None:
        """Alias de compatibilidad: las imágenes antiguas ahora son iconos.

        ``choose_icon`` pasa por ``validate_profile_image`` y crea la vista
        segura mediante Pillow + ``ImageQt``; evita la decodificación directa de Qt.
        """
        self.choose_icon()

    def clear_icon(self) -> None:
        self.icon_source = ""
        self.icon_changed = True
        self.image_source = ""
        self.image_changed = True
        self.profile.image_path = ""
        self.profile.icon_path = ""
        self.image_preview.clear_preview_pixmap()
        self._update_icon_preview()

    def clear_banner(self) -> None:
        self.banner_source = ""
        self.banner_changed = True
        self.profile.banner_path = ""
        self.banner_preview.clear_preview_pixmap()

    def clear_image(self) -> None:
        """Alias de compatibilidad."""
        self.clear_icon()

    def _update_icon_preview(self, *_args: Any) -> None:
        if not hasattr(self, "image_preview"):
            return
        if hasattr(self, "name_edit"):
            self.profile.name = self.name_edit.text().strip() or self.profile.name
        if hasattr(self, "category_edit"):
            self.profile.category = self.category_edit.currentText().strip() or "Personal"
        if hasattr(self, "icon_theme"):
            self.profile.icon = str(self.icon_theme.currentData() or "theme:custom")
        if self.icon_source and self.image_preview.has_custom_image():
            return
        self.image_preview.set_profile_visual(self.profile_id, self.profile)

    def _choose_color(self, which: str) -> None:
        current = self.primary_color if which == "primary" else self.secondary_color
        chosen = QColorDialog.getColor(current, self, "Color de la luz")
        if not chosen.isValid():
            return
        if which == "primary":
            self.primary_color = chosen
        else:
            self.secondary_color = chosen
        self._update_color_buttons()

    def _update_color_buttons(self) -> None:
        self.primary_button.setText(self.primary_color.name().upper())
        self.secondary_button.setText(self.secondary_color.name().upper())
        self.primary_button.setStyleSheet(
            f"background:{self.primary_color.name()};color:white;font-weight:700"
        )
        self.secondary_button.setStyleSheet(
            f"background:{self.secondary_color.name()};color:white;font-weight:700"
        )

    def _write_trigger(self, side: str) -> None:
        from src.trigger_engine import TriggerEffectType

        controls = self.__dict__[f"{side}_controls"]
        effect = self.profile.left_trigger if side == "left" else self.profile.right_trigger
        effect.effect_type = TriggerEffectType(controls["effect_type"].currentData())
        if effect.effect_type not in {TriggerEffectType.SECTIONS, TriggerEffectType.CUSTOM}:
            effect.custom_params = {}
        effect.intensity = controls["intensity"].value()
        effect.start_position = controls["start"].value()
        effect.end_position = max(effect.start_position, controls["end"].value())
        effect.frequency = controls["frequency"].value()
        effect.animated = controls["animated"].isChecked()
        effect.animation_speed = controls["animation_speed"].value()
        effect.animation_curve = controls["curve"].currentData()
        effect.vibration_enabled = controls["vibration_enabled"].isChecked()
        effect.vibration_intensity = controls["vibration_intensity"].value()
        effect.vibration_frequency = controls["vibration_frequency"].value()
        effect.vibration_start_position = controls["vibration_start"].value()
        effect.vibration_end_position = max(
            effect.vibration_start_position, controls["vibration_end"].value()
        )

    def _accept_changes(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            self.window.alert("Escribe un nombre para el perfil")
            return
        self.profile.name = name
        self.profile.category = self.category_edit.currentText().strip()[:80] or "Personal"
        self.profile.description = self.description_edit.toPlainText().strip()[:2000]
        tags = []
        for raw in self.tags_edit.text().split(","):
            tag = raw.strip()[:40]
            if tag and tag.lower() not in {item.lower() for item in tags}:
                tags.append(tag)
            if len(tags) >= 8:
                break
        self.profile.tags = tags
        self.profile.icon = str(self.icon_theme.currentData() or "theme:custom")[:16]
        self.profile.rumble_intensity = self.rumble.value()
        self.profile.macros_enabled = self.macros_enabled.isChecked()
        self._write_trigger("left")
        self._write_trigger("right")
        raw_light = {
            "effect": self.light_effect.currentData() or "static",
            "color": [self.primary_color.red(), self.primary_color.green(), self.primary_color.blue()],
            "secondary_color": [
                self.secondary_color.red(),
                self.secondary_color.green(),
                self.secondary_color.blue(),
            ],
            "speed": self.light_speed.value(),
            "brightness": self.light_brightness.value() / 100.0,
            "intensity": self.light_intensity.value() / 100.0,
            "smoothing": self.light_smoothing.value() / 100.0,
            "direction": self.light_direction.currentData() or 1,
            "audio_gain": self.light_audio_gain.value(),
            "audio_floor": float((getattr(self.profile, "light_config", {}) or {}).get("audio_floor", 0.03)),
            "palette": self.palette.text(),
        }
        engine = getattr(self.window, "light_effect_engine", None)
        if engine:
            self.profile.light_config = engine.sanitize_config(raw_light)
            selected = str(raw_light["effect"])
            if selected.startswith("custom:"):
                self.profile.light_config["effect"] = "custom"
                self.profile.light_config["custom_id"] = selected.split(":", 1)[1]
        else:
            self.profile.light_config = raw_light
        self.accept()
