"""Sistema visual compartido por Profile Studio y Dashboard.

Los perfiles pueden usar una imagen propia o un tema vectorial. Los temas no
requieren assets externos, escalan sin perder calidad y aceptan un único reloj
de animación administrado por la página de perfiles.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .components import load_scaled_pixmap
from .ui_common import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRectF,
    QWidget,
    Qt,
)


@dataclass(frozen=True)
class ProfileVisual:
    glyph: str
    accent_a: str
    accent_b: str
    chip: str
    theme_id: str


THEME_PRESETS: dict[str, ProfileVisual] = {
    "assault": ProfileVisual("AR", "#3DDC97", "#43D7EF", "EQUILIBRADO", "assault"),
    "precision": ProfileVisual("SN", "#6EE7FF", "#6B7CFF", "PRECISIÓN", "precision"),
    "bow": ProfileVisual("BW", "#8B5CFF", "#43D7EF", "TENSIÓN", "bow"),
    "sidearm": ProfileVisual("PI", "#FF9F43", "#FF5A5F", "RESPUESTA", "sidearm"),
    "impact": ProfileVisual("SG", "#FF7A18", "#FF3F6C", "IMPACTO", "impact"),
    "rapid": ProfileVisual("SM", "#E056FD", "#43D7EF", "CADENCIA", "rapid"),
    "heavy": ProfileVisual("LM", "#FFB347", "#F6416C", "POTENCIA", "heavy"),
    "neutral": ProfileVisual("OFF", "#6B7280", "#9CA3AF", "LIBRE", "neutral"),
    "racing": ProfileVisual("GT", "#43D7EF", "#3DDC97", "CONDUCCIÓN", "racing"),
    "horror": ProfileVisual("HX", "#FF3F6C", "#8B5CFF", "INMERSIÓN", "horror"),
    "rpg": ProfileVisual("RPG", "#A855F7", "#F59E0B", "AVENTURA", "rpg"),
    "stealth": ProfileVisual("ST", "#64748B", "#43D7EF", "SIGILO", "stealth"),
    "sports": ProfileVisual("SP", "#22C55E", "#FACC15", "DEPORTES", "sports"),
    "arcade": ProfileVisual("AC", "#FF4DD6", "#43D7EF", "ARCADE", "arcade"),
    "custom": ProfileVisual("MY", "#C63FF4", "#43D7EF", "CUSTOM", "custom"),
    "warzone": ProfileVisual("WZ", "#6852FF", "#2DD6FF", "FPS", "warzone"),
    "forza": ProfileVisual("FH", "#28B0FF", "#FF485E", "CARRERAS", "forza"),
    "resident": ProfileVisual("RE", "#D3263E", "#7036B4", "HORROR", "resident"),
    "elden": ProfileVisual("ER", "#D8A33D", "#8549CE", "RPG", "elden"),
    "fc": ProfileVisual("FC", "#27D371", "#37BEFF", "DEPORTES", "fc"),
    "fighter": ProfileVisual("SF", "#EF39C2", "#2AD5FF", "PELEAS", "fighter"),
    "minecraft": ProfileVisual("MC", "#4CB95B", "#46A8EE", "SANDBOX", "minecraft"),
    "ghost": ProfileVisual("GT", "#32D170", "#36BEAE", "AVENTURA", "ghost"),
}


ICON_THEME_CHOICES: tuple[tuple[str, str], ...] = (
    ("Call of Duty: Warzone", "theme:warzone"),
    ("Forza Horizon 5", "theme:forza"),
    ("Resident Evil 4", "theme:resident"),
    ("Elden Ring", "theme:elden"),
    ("EA Sports FC", "theme:fc"),
    ("Street Fighter 6", "theme:fighter"),
    ("Minecraft", "theme:minecraft"),
    ("Ghost of Tsushima", "theme:ghost"),
    ("Shooter genérico", "theme:assault"),
    ("Precisión", "theme:precision"),
    ("Arquería", "theme:bow"),
    ("Conducción", "theme:racing"),
    ("Horror / inmersión", "theme:horror"),
    ("RPG / aventura", "theme:rpg"),
    ("Sigilo", "theme:stealth"),
    ("Deportes", "theme:sports"),
    ("Arcade", "theme:arcade"),
    ("Personalizado", "theme:custom"),
    ("Neutro / libre", "theme:neutral"),
)


PROFILE_THEME_IDS: dict[str, str] = {
    "assault_rifle": "warzone",
    "racing": "forza",
    "horror": "resident",
    "lmg": "elden",
    "pistol": "fc",
    "shotgun": "fighter",
    "off": "minecraft",
    "bow": "ghost",
    # aliases de lectura para instalaciones anteriores
    "sniper": "warzone",
    "smg": "warzone",
}


CATEGORY_THEME_IDS: dict[str, str] = {
    "automaticas": "assault",
    "automáticas": "assault",
    "shooter": "assault",
    "precision": "precision",
    "precisión": "precision",
    "pistolas": "sidearm",
    "acción": "sidearm",
    "pesadas": "heavy",
    "conducción": "racing",
    "vehículos": "racing",
    "inmersión": "horror",
    "horror": "horror",
    "aventura": "rpg",
    "rpg": "rpg",
    "sigilo": "stealth",
    "deportes": "sports",
    "arcade": "arcade",
    "general": "neutral",
    "personal": "custom",
}


def _initials(text: str) -> str:
    words = [chunk for chunk in str(text).replace("_", " ").replace("-", " ").split() if chunk]
    if not words:
        return "PF"
    if len(words) == 1:
        cleaned = words[0][:3].upper()
        return cleaned or "PF"
    return (words[0][0] + words[1][0]).upper()


def _copy_with_glyph(visual: ProfileVisual, glyph: str) -> ProfileVisual:
    return ProfileVisual(
        glyph=glyph,
        accent_a=visual.accent_a,
        accent_b=visual.accent_b,
        chip=visual.chip,
        theme_id=visual.theme_id,
    )


def visual_for_profile(profile_id: str, profile: Any) -> ProfileVisual:
    key = str(profile_id or "").strip().lower()
    icon = str(getattr(profile, "icon", "") or "").strip()
    if icon.startswith("theme:"):
        requested = icon.split(":", 1)[1].strip().lower()
        if requested in THEME_PRESETS:
            return THEME_PRESETS[requested]

    theme_id = PROFILE_THEME_IDS.get(key)
    if theme_id:
        return THEME_PRESETS[theme_id]

    category = str(getattr(profile, "category", "") or "").strip().lower()
    theme_id = CATEGORY_THEME_IDS.get(category)
    if theme_id:
        return _copy_with_glyph(
            THEME_PRESETS[theme_id],
            _initials(getattr(profile, "name", key) or key),
        )

    if icon and not icon.startswith("theme:") and len(icon) <= 3:
        return _copy_with_glyph(THEME_PRESETS["custom"], icon)
    return _copy_with_glyph(
        THEME_PRESETS["custom"],
        _initials(getattr(profile, "name", key) or key),
    )


def fallback_glyph(profile_id: str, profile: Any) -> str:
    return visual_for_profile(profile_id, profile).glyph


def normalize_icon_theme(value: Any, *, fallback: str = "theme:custom") -> str:
    token = str(value or "").strip().lower()
    if token.startswith("theme:") and token.split(":", 1)[1] in THEME_PRESETS:
        return token
    return fallback


class ProfileAvatarWidget(QWidget):
    """Avatar vectorial animado con soporte para imagen personalizada."""

    def __init__(
        self,
        profile_id: str,
        profile: Any,
        *,
        size: int = 62,
        active: bool = False,
        selected: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.profile_id = str(profile_id or "")
        self.profile = profile
        self.visual = visual_for_profile(self.profile_id, profile)
        self.active = bool(active)
        self.selected = bool(selected)
        self.hovered = False
        self.progress = 0.0
        self._pixmap = QPixmap()
        self.setFixedSize(max(36, int(size)), max(36, int(size)))
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._load_image()

    def _load_image(self) -> None:
        self._pixmap = QPixmap()
        image_path = Path(
            str(
                getattr(self.profile, "icon_path", "")
                or getattr(self.profile, "image_path", "")
                or ""
            )
        )
        if image_path.is_file():
            self._pixmap = load_scaled_pixmap(
                str(image_path),
                max(64, self.width() * 2),
                max(64, self.height() * 2),
            )

    def has_custom_image(self) -> bool:
        return not self._pixmap.isNull()

    def set_preview_pixmap(self, pixmap: QPixmap) -> None:
        self._pixmap = QPixmap(pixmap) if not pixmap.isNull() else QPixmap()
        self.update()

    def clear_preview_pixmap(self) -> None:
        self._pixmap = QPixmap()
        self.update()

    def set_profile_visual(self, profile_id: str, profile: Any) -> None:
        self.profile_id = str(profile_id or "")
        self.profile = profile
        self.visual = visual_for_profile(self.profile_id, profile)
        self._load_image()
        self.update()

    def set_frame(
        self,
        progress: float,
        *,
        active: Optional[bool] = None,
        selected: Optional[bool] = None,
        hovered: Optional[bool] = None,
    ) -> None:
        self.progress = float(progress) % 1.0
        if active is not None:
            self.active = bool(active)
        if selected is not None:
            self.selected = bool(selected)
        if hovered is not None:
            self.hovered = bool(hovered)
        self.update()

    @staticmethod
    def _alpha(color: QColor, alpha: int) -> QColor:
        return QColor(color.red(), color.green(), color.blue(), max(0, min(255, int(alpha))))

    def paintEvent(self, _event: Any) -> None:  # pragma: no cover - render Qt
        """Render plano y barato; no usa halos, arcos ni animación continua."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(self.rect()).adjusted(2.5, 2.5, -2.5, -2.5)
        radius = max(9.0, rect.width() * 0.22)
        accent_a = QColor(self.visual.accent_a)
        accent_b = QColor(self.visual.accent_b)

        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)
        painter.save()
        painter.setClipPath(clip)
        painter.fillPath(clip, QColor("#171927"))

        if not self._pixmap.isNull():
            source = QRectF(self._pixmap.rect())
            source_ratio = source.width() / max(1.0, source.height())
            target_ratio = rect.width() / max(1.0, rect.height())
            if source_ratio > target_ratio:
                new_width = source.height() * target_ratio
                source.setLeft(source.center().x() - new_width / 2)
                source.setWidth(new_width)
            else:
                new_height = source.width() / target_ratio
                source.setTop(source.center().y() - new_height / 2)
                source.setHeight(new_height)
            painter.drawPixmap(rect, self._pixmap, source)
        else:
            band_height = max(5.0, rect.height() * 0.12)
            gradient = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.top())
            gradient.setColorAt(0.0, accent_a)
            gradient.setColorAt(1.0, accent_b)
            painter.fillRect(
                QRectF(rect.left(), rect.top(), rect.width(), band_height),
                QBrush(gradient),
            )
            font = QFont(self.font())
            font.setBold(True)
            glyph_len = len(self.visual.glyph)
            font.setPointSizeF(max(8.0, rect.width() * (0.22 if glyph_len <= 2 else 0.17)))
            painter.setFont(font)
            painter.setPen(QColor("#F4F6FC"))
            painter.drawText(rect.adjusted(0, band_height * 0.25, 0, 0), Qt.AlignmentFlag.AlignCenter, self.visual.glyph)
        painter.restore()

        border_color = accent_a if self.active or self.selected else QColor("#353849")
        border_width = 2.0 if self.active else (1.6 if self.selected else 1.0)
        painter.setPen(QPen(border_color, border_width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, radius, radius)
