"""Componentes ligeros de la galería de perfiles.

La galería es deliberadamente estática: no crea temporizadores por tarjeta ni
repinta en segundo plano. Las portadas integradas se cargan una sola vez y el
panel de detalle solo se reconstruye al cambiar la selección.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from src.profile_catalog import profile_presentation

from .profile_visuals import visual_for_profile
from .ui_common import (
    C,
    QBrush,
    QColor,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QImageReader,
    QLabel,
    QLinearGradient,
    QMenu,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPushButton,
    QRectF,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
    button,
    card,
    clear_layout,
    label,
    resource_path,
)

if TYPE_CHECKING:
    from .main_window import NikaidoWindow


LIGHT_EFFECT_LABELS = {
    "static": "Estático",
    "breathe": "Respirar",
    "pulse": "Pulso",
    "rainbow": "Arco iris",
    "wave": "Ola",
    "comet": "Cometa",
    "heartbeat": "Latido",
    "aurora": "Aurora",
    "plasma": "Plasma",
    "fire": "Fuego",
    "ice": "Hielo",
    "police": "Alerta",
    "audio": "Audio reactivo",
    "custom": "Personalizado",
}

TRIGGER_TYPE_LABELS = {
    "off": "Libre",
    "rigid": "Rigidez",
    "pulse": "Pulso",
    "continuous_vibration": "Vibración",
    "sections": "Progresivo",
    "weapon_single": "Punto de disparo",
    "weapon_automatic": "Automático",
    "weapon_sniper": "Precisión",
    "weapon_bow": "Arco",
    "custom": "Personalizado",
}


def _safe_rgb(value: Any, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    try:
        values = list(value)[:3]
        if len(values) != 3:
            raise ValueError
        return tuple(max(0, min(255, int(item))) for item in values)  # type: ignore[return-value]
    except Exception:
        return fallback


def _timestamp_label(profile: Any, *, builtin: bool) -> str:
    if builtin:
        return "Incluido con Nikaido"
    raw = str(getattr(profile, "updated_at", "") or getattr(profile, "created_at", "") or "")
    if not raw:
        return "Perfil personalizado"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return f"Actualizado: {parsed.strftime('%d/%m/%Y')}"
    except ValueError:
        return "Perfil personalizado"


def vibration_label(value: Any) -> str:
    try:
        amount = max(0, min(255, int(value)))
    except Exception:
        amount = 0
    if amount <= 0:
        return "Desactivada"
    if amount < 80:
        return "Ligera"
    if amount < 170:
        return "Media"
    return "Fuerte"


def input_studio_ready(profile: Any) -> bool:
    config = getattr(profile, "input_studio_config", {}) or {}
    if not isinstance(config, dict):
        return False
    for stick in config.values():
        if not isinstance(stick, dict):
            continue
        if (
            abs(float(stick.get("inner_deadzone", 0.08)) - 0.08) > 0.002
            or str(stick.get("curve", "linear")) != "linear"
            or abs(float(stick.get("sensitivity_x", 1.0)) - 1.0) > 0.002
            or abs(float(stick.get("sensitivity_y", 1.0)) - 1.0) > 0.002
        ):
            return True
    return False


class ProfileCoverWidget(QWidget):
    """Portada recortada con avatar y estado, sin animación continua."""

    _pixmap_cache: dict[tuple[str, int, int], QPixmap] = {}

    def __init__(
        self,
        profile_id: str,
        profile: Any,
        *,
        active: bool = False,
        selected: bool = False,
        detail: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.profile_id = str(profile_id)
        self.profile = profile
        self.active = bool(active)
        self.selected = bool(selected)
        self.detail = bool(detail)
        self._pixmap = QPixmap()
        self._preview_override = QPixmap()
        self.setMinimumHeight(168 if detail else 118)
        self.setMaximumHeight(214 if detail else 132)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._load_source()

    def _source_path(self) -> Path | None:
        banner_value = getattr(self.profile, "banner_path", None)
        custom = Path(
            str(
                (getattr(self.profile, "image_path", "") if banner_value is None else banner_value)
                or ""
            )
        )
        if custom.is_file():
            return custom
        presentation = profile_presentation(self.profile_id)
        if presentation:
            bundled = resource_path(presentation.cover_asset)
            if bundled.is_file():
                return bundled
        return None

    def _load_source(self) -> None:
        self._pixmap = QPixmap()
        if not self._preview_override.isNull():
            self._pixmap = QPixmap(self._preview_override)
            self.update()
            return
        source = self._source_path()
        if not source:
            return
        try:
            stamp = int(source.stat().st_mtime_ns)
        except OSError:
            stamp = 0
        target_w = 1180 if self.detail else 720
        target_h = 440 if self.detail else 300
        key = (str(source), stamp, target_w)
        cached = self._pixmap_cache.get(key)
        if cached is not None and not cached.isNull():
            self._pixmap = QPixmap(cached)
            return
        reader = QImageReader(str(source))
        reader.setAutoTransform(True)
        size = reader.size()
        if size.isValid():
            scaled = size.scaled(
                target_w,
                target_h,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            )
            reader.setScaledSize(scaled)
        image = reader.read()
        if image.isNull():
            return
        self._pixmap = QPixmap.fromImage(image)
        self._pixmap_cache[key] = QPixmap(self._pixmap)
        if len(self._pixmap_cache) > 48:
            oldest = next(iter(self._pixmap_cache))
            self._pixmap_cache.pop(oldest, None)

    def set_preview_pixmap(self, pixmap: QPixmap) -> None:
        self._preview_override = QPixmap(pixmap) if not pixmap.isNull() else QPixmap()
        self._load_source()

    def clear_preview_pixmap(self) -> None:
        self._preview_override = QPixmap()
        self._load_source()

    def set_profile_media(self, profile_id: str, profile: Any) -> None:
        self.profile_id = str(profile_id)
        self.profile = profile
        self._preview_override = QPixmap()
        self._load_source()

    def set_states(self, *, active: bool, selected: bool) -> None:
        self.active = bool(active)
        self.selected = bool(selected)
        self.update()

    @staticmethod
    def _cover_source_rect(pixmap: QPixmap, target: QRectF) -> QRectF:
        source = QRectF(pixmap.rect())
        source_ratio = source.width() / max(1.0, source.height())
        target_ratio = target.width() / max(1.0, target.height())
        if source_ratio > target_ratio:
            width = source.height() * target_ratio
            source.setLeft(source.center().x() - width / 2)
            source.setWidth(width)
        else:
            height = source.width() / target_ratio
            source.setTop(source.center().y() - height / 2)
            source.setHeight(height)
        return source

    def paintEvent(self, _event: Any) -> None:  # pragma: no cover - render Qt
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        radius = 14.0
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.save()
        painter.setClipPath(path)

        visual = visual_for_profile(self.profile_id, self.profile)
        primary = QColor(visual.accent_a)
        secondary = QColor(visual.accent_b)
        if self._pixmap.isNull():
            gradient = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
            gradient.setColorAt(0.0, primary.darker(190))
            gradient.setColorAt(1.0, secondary.darker(250))
            painter.fillPath(path, QBrush(gradient))
        else:
            painter.drawPixmap(rect, self._pixmap, self._cover_source_rect(self._pixmap, rect))

        # Oscurece la parte inferior para conservar legibilidad y unifica arte
        # personal con las portadas incluidas.
        shade = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
        shade.setColorAt(0.0, QColor(4, 7, 16, 5))
        shade.setColorAt(0.55, QColor(4, 7, 16, 20))
        shade.setColorAt(1.0, QColor(4, 7, 16, 205))
        painter.fillPath(path, QBrush(shade))
        painter.restore()

        # Estilo A: la selección no cambia el borde. Se distingue mediante
        # sombreado en la tarjeta y una iluminación interna muy tenue.
        if self.selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 10))
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius - 1, radius - 1)
        painter.setPen(QPen(QColor(C["border"]), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, radius, radius)

        if self.active:
            badge = QRectF(12, 10, 68, 25)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(31, 126, 73, 230))
            painter.drawRoundedRect(badge, 12, 12)
            painter.setPen(QColor("#F4FFF7"))
            font = painter.font()
            font.setBold(True)
            font.setPointSize(9)
            painter.setFont(font)
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, "ACTIVO")

        avatar_size = 78 if self.detail else 58
        avatar_rect = QRectF(
            18,
            rect.bottom() - avatar_size - (18 if self.detail else 12),
            avatar_size,
            avatar_size,
        )
        painter.setPen(QPen(primary, 3))
        painter.setBrush(QColor(8, 12, 23, 235))
        painter.drawEllipse(avatar_rect)
        painter.setPen(QColor("#F5F7FF"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(15 if self.detail else 11)
        painter.setFont(font)
        painter.drawText(avatar_rect, Qt.AlignmentFlag.AlignCenter, visual.glyph)


class ProfileGalleryCard(QWidget):
    """Tarjeta de galería que solo repinta al cambiar estado."""

    selected = Signal(str)

    def __init__(
        self,
        page: Any,
        profile_id: str,
        profile: Any,
        *,
        active: bool,
        favorite: bool,
        selected: bool,
        custom: bool,
        display_mode: str = "grid",
    ) -> None:
        super().__init__()
        self.page = page
        self.profile_id = str(profile_id)
        self.profile = profile
        self.active = bool(active)
        self.favorite = bool(favorite)
        self.is_selected = bool(selected)
        self.custom = bool(custom)
        self.display_mode = "list" if display_mode == "list" else "grid"
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build()
        self._apply_style()

    def _build(self) -> None:
        self.root = card(self)
        self._hovered = False
        self._shadow = QGraphicsDropShadowEffect(self.root)
        self.root.setGraphicsEffect(self._shadow)
        outer = QVBoxLayout(self)
        # Espacio reservado para que la sombra no quede recortada.
        outer.setContentsMargins(7, 7, 7, 9)
        outer.addWidget(self.root)

        if self.display_mode == "list":
            layout = QHBoxLayout(self.root)
            layout.setContentsMargins(0, 0, 10, 0)
            layout.setSpacing(12)
            self.cover = ProfileCoverWidget(
                self.profile_id,
                self.profile,
                active=self.active,
                selected=self.is_selected,
            )
            self.cover.setFixedSize(190, 102)
            layout.addWidget(self.cover)
            content = QVBoxLayout()
            content.setSpacing(4)
            content.setContentsMargins(0, 10, 0, 9)
            title_row = QHBoxLayout()
            title = QLabel(str(self.profile.name))
            title.setStyleSheet(f"color:{C['text']};font-size:14px;font-weight:700")
            title_row.addWidget(title, 1)
            more = QPushButton("⋯")
            more.setProperty("iconButton", True)
            more.setFixedSize(30, 30)
            more.clicked.connect(self._show_menu)
            title_row.addWidget(more)
            content.addLayout(title_row)
            category = QLabel(str(self.profile.category or "General"))
            category.setStyleSheet(f"color:{C['muted']};font-size:10px")
            content.addWidget(category)
            description = QLabel(str(self.profile.description or "Sin descripción"))
            description.setStyleSheet(f"color:{C['muted']};font-size:9px;")
            description.setWordWrap(True)
            description.setMaximumHeight(30)
            content.addWidget(description)
            content.addStretch()
            meta = QLabel(_timestamp_label(self.profile, builtin=not self.custom))
            meta.setStyleSheet(f"color:{C['muted']};font-size:8px")
            content.addWidget(meta)
            layout.addLayout(content, 1)
            self.root.setMinimumHeight(104)
            return

        layout = QVBoxLayout(self.root)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.setSpacing(7)
        self.cover = ProfileCoverWidget(
            self.profile_id,
            self.profile,
            active=self.active,
            selected=self.is_selected,
        )
        layout.addWidget(self.cover)

        identity = QHBoxLayout()
        identity.setContentsMargins(13, 0, 10, 0)
        names = QVBoxLayout()
        names.setSpacing(2)
        title = QLabel(str(self.profile.name))
        title.setStyleSheet(f"color:{C['text']};font-size:14px;font-weight:700")
        title.setWordWrap(True)
        names.addWidget(title)
        category = QLabel(str(self.profile.category or "General"))
        category.setStyleSheet(f"color:{C['muted']};font-size:10px")
        category.setWordWrap(True)
        names.addWidget(category)
        identity.addLayout(names, 1)

        more = QPushButton("⋯")
        more.setProperty("iconButton", True)
        more.setFixedSize(30, 30)
        more.setCursor(Qt.CursorShape.PointingHandCursor)
        more.clicked.connect(self._show_menu)
        identity.addWidget(more, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(identity)

        meta = QLabel(_timestamp_label(self.profile, builtin=not self.custom))
        meta.setStyleSheet(f"color:{C['muted']};font-size:9px;")
        meta.setContentsMargins(13, 0, 10, 0)
        layout.addWidget(meta)
        self.root.setMinimumHeight(220)

    def _show_menu(self) -> None:  # pragma: no cover - interacción UI
        menu = QMenu(self)
        apply_action = menu.addAction("Aplicar perfil")
        edit_action = menu.addAction("Editar")
        duplicate_action = menu.addAction("Duplicar")
        export_action = menu.addAction("Exportar")
        favorite_action = menu.addAction(
            "Quitar de favoritos" if self.favorite else "Agregar a favoritos"
        )
        reset_action = None
        delete_action = None
        if self.custom:
            menu.addSeparator()
            delete_action = menu.addAction("Eliminar")
        else:
            menu.addSeparator()
            reset_action = menu.addAction("Restaurar perfil incluido")
        chosen = menu.exec(self.mapToGlobal(self.rect().bottomRight()))
        if chosen is apply_action:
            self.page.apply_profile(self.profile_id)
        elif chosen is edit_action:
            self.page.edit_profile(self.profile_id)
        elif chosen is duplicate_action:
            self.page.duplicate_profile(self.profile_id)
        elif chosen is export_action:
            self.page.export_profile(self.profile_id)
        elif chosen is favorite_action:
            self.page.toggle_favorite(self.profile_id)
        elif delete_action is not None and chosen is delete_action:
            self.page.delete_profile(self.profile_id)
        elif reset_action is not None and chosen is reset_action:
            self.page.reset_builtin_profile(self.profile_id)

    def set_selected_state(self, selected: bool) -> None:
        self.is_selected = bool(selected)
        self.cover.set_states(active=self.active, selected=self.is_selected)
        self._apply_style()

    def set_active_state(self, active: bool) -> None:
        self.active = bool(active)
        self.cover.set_states(active=self.active, selected=self.is_selected)
        self._apply_style()

    def _apply_style(self) -> None:
        # Estilo A · Sobrio premium. El borde permanece estable; selección y
        # hover se comunican con fondo, elevación y sombra estática.
        if self.is_selected:
            background = C["panel2"]
            blur, offset_y, alpha = 26.0, 6.0, 105
        elif self._hovered:
            background = C["panel2"]
            blur, offset_y, alpha = 18.0, 4.0, 78
        else:
            background = C["panel"]
            blur, offset_y, alpha = 0.0, 0.0, 0

        # El perfil activo conserva únicamente su badge. No usa borde verde.
        self.root.setStyleSheet(
            f"QFrame {{ border:1px solid {C['border']};"
            f"background:{background};border-radius:15px; }}"
        )
        shadow_visible = self.is_selected or self._hovered
        self._shadow.setEnabled(shadow_visible)
        if shadow_visible:
            self._shadow.setBlurRadius(blur)
            self._shadow.setOffset(0.0, offset_y)
            self._shadow.setColor(QColor(0, 0, 0, alpha))
        self.cover.set_states(active=self.active, selected=self.is_selected)

    def enterEvent(self, event: Any) -> None:  # pragma: no cover - interacción UI
        self._hovered = True
        self._apply_style()
        super().enterEvent(event)

    def leaveEvent(self, event: Any) -> None:  # pragma: no cover - interacción UI
        self._hovered = False
        self._apply_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # pragma: no cover
        target = self.childAt(event.position().toPoint())
        while target is not None:
            if isinstance(target, QPushButton):
                return super().mousePressEvent(event)
            target = target.parentWidget()
        self.selected.emit(self.profile_id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # pragma: no cover
        self.page.apply_profile(self.profile_id)
        super().mouseDoubleClickEvent(event)


class ProfileFeatureRow(QPushButton):
    """Fila clicable del panel de detalle."""

    def __init__(
        self,
        icon: str,
        title: str,
        description: str,
        status: str,
        *,
        accent: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoDefault(False)
        self.setStyleSheet(
            f"QPushButton {{ text-align:left;background:{C['panel2']};border:1px solid {C['border']};"
            "border-radius:12px;padding:0; }"
            f"QPushButton:hover {{ border-color:{accent};background:rgba(255,255,255,9); }}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)
        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedSize(30, 30)
        icon_label.setStyleSheet(
            f"background:rgba(255,255,255,0.04);border-radius:9px;color:{accent};font-size:16px;font-weight:700;"
        )
        layout.addWidget(icon_label)
        text = QVBoxLayout()
        text.setSpacing(1)
        heading = QLabel(title)
        heading.setStyleSheet(f"color:{C['text']};font-size:12px;font-weight:700;")
        text.addWidget(heading)
        helper = QLabel(description)
        helper.setStyleSheet(f"color:{C['muted']};font-size:9px;")
        helper.setWordWrap(True)
        text.addWidget(helper)
        layout.addLayout(text, 1)
        status_label = QLabel(status)
        status_label.setStyleSheet(f"color:{accent};font-size:10px;font-weight:700;")
        status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(status_label)
        chevron = QLabel("›")
        chevron.setStyleSheet(f"color:{C['muted']};font-size:20px;")
        layout.addWidget(chevron)
        for child in (icon_label, heading, helper, status_label, chevron):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setMinimumHeight(58)


class ProfileDetailPanel(QWidget):
    """Vista previa y accesos de configuración del perfil seleccionado."""

    apply_requested = Signal(str)
    edit_requested = Signal(str)
    duplicate_requested = Signal(str)
    export_requested = Signal(str)
    favorite_requested = Signal(str)
    delete_requested = Signal(str)
    reset_requested = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self, window: "NikaidoWindow", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.window = window
        self.profile_id = ""
        self.profile: Any = None
        self.active = False
        self.custom = False
        self.favorite = False
        self.root = card(self)
        shell = QVBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.addWidget(self.root)
        self.layout = QVBoxLayout(self.root)
        self.layout.setContentsMargins(14, 14, 14, 14)
        self.layout.setSpacing(9)
        self.setMinimumWidth(340)
        self.setMaximumWidth(430)
        self.show_empty()

    def show_empty(self) -> None:
        clear_layout(self.layout)
        title = label("Vista previa", "heading")
        self.layout.addWidget(title)
        helper = QLabel("Selecciona un perfil para revisar y modificar su configuración.")
        helper.setProperty("muted", True)
        helper.setWordWrap(True)
        self.layout.addWidget(helper)
        self.layout.addStretch()

    def set_profile(
        self,
        profile_id: str,
        profile: Any,
        *,
        active: bool,
        custom: bool,
        favorite: bool,
        macro_count: int,
    ) -> None:
        self.profile_id = str(profile_id)
        self.profile = profile
        self.active = bool(active)
        self.custom = bool(custom)
        self.favorite = bool(favorite)
        clear_layout(self.layout)

        top = QHBoxLayout()
        eyebrow = QLabel("VISTA PREVIA")
        eyebrow.setStyleSheet(f"color:{C['muted']};font-size:9px;font-weight:700")
        top.addWidget(eyebrow)
        top.addStretch()
        if not active:
            top.addWidget(
                button(
                    "Aplicar",
                    lambda: self.apply_requested.emit(self.profile_id),
                    primary=True,
                )
            )
        favorite_button = button(
            "★" if favorite else "☆",
            lambda: self.favorite_requested.emit(self.profile_id),
            tooltip="Quitar de favoritos" if favorite else "Agregar a favoritos",
        )
        favorite_button.setProperty("iconButton", True)
        favorite_button.setFixedSize(34, 34)
        top.addWidget(favorite_button)
        self.layout.addLayout(top)

        cover = ProfileCoverWidget(
            profile_id,
            profile,
            active=active,
            selected=True,
            detail=True,
        )
        self.layout.addWidget(cover)

        identity = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        name = QLabel(str(profile.name))
        name.setStyleSheet(f"color:{C['text']};font-size:18px;font-weight:700")
        name.setWordWrap(True)
        title_box.addWidget(name)
        category = QLabel(str(profile.category or "General"))
        category.setStyleSheet(f"color:{C['muted']};font-size:10px")
        category.setWordWrap(True)
        title_box.addWidget(category)
        identity.addLayout(title_box, 1)
        if active:
            active_badge = QLabel("ACTIVO")
            active_badge.setStyleSheet(
                f"background:rgba(39,190,101,0.14);color:{C['green']};padding:5px 9px;"
                "border-radius:10px;font-size:9px;font-weight:700"
            )
            identity.addWidget(active_badge)
        self.layout.addLayout(identity)

        description = QLabel(str(profile.description or "Sin descripción"))
        description.setWordWrap(True)
        description.setStyleSheet(f"color:{C['muted']};font-size:10px")
        self.layout.addWidget(description)

        visual = visual_for_profile(profile_id, profile)
        light = getattr(profile, "light_config", {}) or {}
        effect = LIGHT_EFFECT_LABELS.get(str(light.get("effect", "static")), "Personalizado")
        left = TRIGGER_TYPE_LABELS.get(profile.left_trigger.effect_type.value, "Personalizado")
        right = TRIGGER_TYPE_LABELS.get(profile.right_trigger.effect_type.value, "Personalizado")

        rows = (
            (
                "◉", "RGB Studio", "Iluminación y animaciones del control.", effect,
                visual.accent_a, "lights",
            ),
            (
                "LT", "Gatillos adaptativos", "Resistencia y puntos de activación.",
                f"L2 {left} · R2 {right}", visual.accent_b, "triggers",
            ),
            (
                "≈", "Vibración", "Intensidad y respuesta háptica.",
                vibration_label(getattr(profile, "rumble_intensity", 0)), C["cyan"], "vibration",
            ),
            (
                "M", "Macros", "Secuencias y accesos asignados.",
                f"{macro_count} asignada{'s' if macro_count != 1 else ''}" if macro_count else "Sin asignar",
                C.get("accent2", C["accent"]), "macros",
            ),
            (
                "◇", "Input Studio", "Curvas, zonas muertas y sensibilidad.",
                "Personalizado" if input_studio_ready(profile) else "Base",
                C["cyan"], "input",
            ),
        )
        for icon, title, helper, status, accent, destination in rows:
            row = ProfileFeatureRow(icon, title, helper, status, accent=accent)
            row.clicked.connect(
                lambda _checked=False, target=destination: self.navigate_requested.emit(target)
            )
            self.layout.addWidget(row)

        actions = QHBoxLayout()
        actions.addWidget(
            button(
                "Editar perfil",
                lambda: self.edit_requested.emit(self.profile_id),
                primary=True,
            ),
            1,
        )
        actions.addWidget(
            button(
                "Duplicar",
                lambda: self.duplicate_requested.emit(self.profile_id),
            )
        )
        actions.addWidget(
            button(
                "Exportar",
                lambda: self.export_requested.emit(self.profile_id),
            )
        )
        self.layout.addLayout(actions)

        final_actions = QHBoxLayout()
        if custom:
            final_actions.addWidget(
                button(
                    "Eliminar",
                    lambda: self.delete_requested.emit(self.profile_id),
                    danger=True,
                )
            )
        else:
            final_actions.addWidget(
                button(
                    "Restaurar incluido",
                    lambda: self.reset_requested.emit(self.profile_id),
                )
            )
        final_actions.addStretch()
        self.layout.addLayout(final_actions)

        note = QLabel(
            "Configuración no oficial creada por Team Nikaido. No existe afiliación con el juego o su publisher."
            if not custom
            else _timestamp_label(profile, builtin=False)
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{C['muted']};font-size:8px")
        self.layout.addWidget(note)
        self.layout.addStretch()
