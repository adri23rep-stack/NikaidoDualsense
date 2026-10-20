"""Componentes visuales del RGB Studio.

Toda la animación usa un único reloj administrado por ``LightsPage``. Ninguna
tarjeta crea su propio ``QTimer``; así la galería completa permanece ligera y
todos los iconos avanzan exactamente en el mismo cuadro.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Mapping, Optional

from src.light_effects import EFFECT_SPECS, LightEffectSample, sample_light_effect

from .ui_common import (
    C,
    QColor,
    QFrame,
    QLabel,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPointF,
    QRadialGradient,
    QRectF,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)


SHOWCASE_EFFECTS = [effect_id for effect_id in EFFECT_SPECS if effect_id != "custom"]
SHOWCASE_CATEGORIES = ["Todos", "Básicos", "Animados", "Temáticos", "Reactivos"]

PURPLE = QColor("#A855F7")
PINK = QColor("#FF4DD6")
CYAN = QColor("#43D7EF")
BLUE = QColor("#3B82F6")
ORANGE = QColor("#FF7A18")
RED = QColor("#FF2038")
WHITE = QColor("#F8FBFF")


def _with_alpha(color: QColor, alpha: int) -> QColor:
    return QColor(color.red(), color.green(), color.blue(), max(0, min(255, alpha)))


class NeonEffectIcon(QWidget):
    """Icono vectorial animado, inspirado en el paquete neón entregado."""

    def __init__(
        self,
        effect_id: str,
        *,
        size: int = 48,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.effect_id = str(effect_id or "static")
        self.progress = 0.0
        self.level = 1.0
        self.audio_level = 0.0
        self.selected = False
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_effect(self, effect_id: str) -> None:
        effect_id = str(effect_id or "static")
        if effect_id != self.effect_id:
            self.effect_id = effect_id
            self.update()

    def set_frame(
        self,
        progress: float,
        *,
        level: float = 1.0,
        audio_level: float = 0.0,
        selected: Optional[bool] = None,
    ) -> None:
        self.progress = float(progress) % 1.0
        self.level = max(0.0, min(1.0, float(level)))
        self.audio_level = max(0.0, min(1.0, float(audio_level)))
        if selected is not None:
            self.selected = bool(selected)
        self.update()

    @staticmethod
    def _path(points: list[QPointF], *, closed: bool = False) -> QPainterPath:
        path = QPainterPath()
        if not points:
            return path
        path.moveTo(points[0])
        for point in points[1:]:
            path.lineTo(point)
        if closed:
            path.closeSubpath()
        return path

    def _stroke(
        self,
        painter: QPainter,
        path: QPainterPath,
        color: QColor,
        *,
        width: float = 3.0,
        strength: float = 1.0,
    ) -> None:
        strength = max(0.08, min(1.0, strength))
        glow = QPen(_with_alpha(color, int(78 * strength)), width + 5.5)
        glow.setCapStyle(Qt.PenCapStyle.RoundCap)
        glow.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(glow)
        painter.drawPath(path)
        core = QPen(_with_alpha(color, int(170 + 85 * strength)), width)
        core.setCapStyle(Qt.PenCapStyle.RoundCap)
        core.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(core)
        painter.drawPath(path)
        shine = QPen(_with_alpha(WHITE, int(75 + 105 * strength)), max(0.7, width * 0.32))
        shine.setCapStyle(Qt.PenCapStyle.RoundCap)
        shine.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(shine)
        painter.drawPath(path)

    def _arc(
        self,
        painter: QPainter,
        rect: QRectF,
        start_degrees: float,
        span_degrees: float,
        color: QColor,
        *,
        width: float = 3.0,
        strength: float = 1.0,
    ) -> None:
        path = QPainterPath()
        path.arcMoveTo(rect, start_degrees)
        path.arcTo(rect, start_degrees, span_degrees)
        self._stroke(painter, path, color, width=width, strength=strength)

    def _circle_glow(
        self,
        painter: QPainter,
        center: QPointF,
        radius: float,
        color: QColor,
        strength: float,
    ) -> None:
        gradient = QRadialGradient(center, radius * 2.3)
        gradient.setColorAt(0.0, _with_alpha(WHITE, int(230 * strength)))
        gradient.setColorAt(0.20, _with_alpha(color, int(210 * strength)))
        gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(center, radius * 2.3, radius * 2.3)
        painter.setBrush(_with_alpha(WHITE, int(220 * strength)))
        painter.drawEllipse(center, radius, radius)

    def paintEvent(self, _event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(5, 5, -5, -5)
        cx, cy = rect.center().x(), rect.center().y()
        progress = self.progress
        level = max(0.10, self.level)
        effect = self.effect_id

        # Un halo seleccionado muy tenue evita que el icono parezca una imagen
        # pegada encima de la tarjeta.
        if self.selected:
            halo = QRadialGradient(rect.center(), rect.width() * 0.65)
            halo.setColorAt(0.0, QColor(67, 215, 239, 38))
            halo.setColorAt(1.0, QColor(67, 215, 239, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(halo)
            painter.drawEllipse(rect.adjusted(-3, -3, 3, 3))

        if effect == "static":
            path = self._path([QPointF(rect.left() + 3, cy), QPointF(rect.right() - 3, cy)])
            self._stroke(painter, path, PINK, width=3.6, strength=0.82 + 0.18 * level)
            overlay = self._path([QPointF(cx, cy), QPointF(rect.right() - 3, cy)])
            self._stroke(painter, overlay, CYAN, width=3.6, strength=0.82 + 0.18 * level)
            return

        if effect == "breathe":
            pulse = 0.25 + 0.75 * level
            ring = rect.adjusted(6, 6, -6, -6)
            self._arc(painter, ring, 135, 205, PINK, width=3.1, strength=pulse)
            self._arc(painter, ring, -20, 155, CYAN, width=3.1, strength=pulse)
            return

        if effect == "pulse":
            pts = [
                QPointF(rect.left() + 1, cy + 5),
                QPointF(rect.left() + 10, cy + 5),
                QPointF(rect.left() + 16, cy - 2),
                QPointF(cx - 4, rect.bottom() - 5),
                QPointF(cx + 7, rect.top() + 3),
                QPointF(cx + 17, cy + 7),
                QPointF(rect.right() - 1, cy + 5),
            ]
            self._stroke(painter, self._path(pts[:4]), PURPLE, width=3.0, strength=level)
            self._stroke(painter, self._path(pts[3:6]), PINK, width=3.0, strength=level)
            self._stroke(painter, self._path(pts[5:]), CYAN, width=3.0, strength=level)
            return

        if effect == "rainbow":
            base = rect.adjusted(2, 11, -2, -2)
            colors = [PURPLE, PINK, QColor("#FF7AC8"), CYAN, BLUE]
            for index, color in enumerate(colors):
                offset = index * 3.3
                arc_rect = QRectF(
                    base.left() + offset,
                    base.top() + offset,
                    base.width() - 2 * offset,
                    base.height() - offset,
                )
                shift = progress * 360.0
                self._arc(painter, arc_rect, shift, 180, color, width=2.1, strength=0.88)
            return

        if effect == "wave":
            samples = 22
            points: list[QPointF] = []
            for index in range(samples):
                x = rect.left() + index / (samples - 1) * rect.width()
                phase = (index / (samples - 1) + progress) * math.tau
                y = cy + math.sin(phase) * rect.height() * 0.25
                points.append(QPointF(x, y))
            split = samples // 2
            self._stroke(painter, self._path(points[: split + 1]), PINK, width=3.0, strength=0.9)
            self._stroke(painter, self._path(points[split:]), CYAN, width=3.0, strength=0.9)
            return

        if effect == "comet":
            start = QPointF(rect.left() + 6, rect.bottom() - 7)
            end = QPointF(rect.right() - 5, rect.top() + 5)
            head_t = progress
            head = QPointF(
                start.x() + (end.x() - start.x()) * head_t,
                start.y() + (end.y() - start.y()) * head_t,
            )
            trail_t = max(0.0, head_t - 0.43)
            trail = QPointF(
                start.x() + (end.x() - start.x()) * trail_t,
                start.y() + (end.y() - start.y()) * trail_t,
            )
            self._stroke(painter, self._path([trail, head]), CYAN, width=3.4, strength=level)
            for offset, color in ((5.0, BLUE), (-5.0, PINK)):
                shifted = QPointF(trail.x(), trail.y() + offset)
                self._stroke(painter, self._path([shifted, QPointF(head.x() - 3, head.y() + offset * 0.3)]), color, width=1.8, strength=level * 0.72)
            self._circle_glow(painter, head, 3.4, PINK if progress < 0.5 else CYAN, level)
            return

        if effect == "heartbeat":
            heart = QPainterPath()
            heart.moveTo(cx, rect.bottom() - 4)
            heart.cubicTo(rect.left() + 2, cy + 4, rect.left() + 4, rect.top() + 6, cx, rect.top() + 13)
            heart.cubicTo(rect.right() - 4, rect.top() + 6, rect.right() - 2, cy + 4, cx, rect.bottom() - 4)
            self._stroke(painter, heart, PINK if progress < 0.5 else CYAN, width=3.0, strength=level)
            return

        if effect == "audio":
            bars = 9
            reactive = max(self.audio_level, level * 0.55)
            for index in range(bars):
                x = rect.left() + (index + 0.5) * rect.width() / bars
                oscillation = 0.55 + 0.45 * math.sin(progress * math.tau * (1.2 + index * 0.09) + index * 0.75)
                height = rect.height() * max(0.14, min(1.0, reactive * (0.62 + oscillation * 0.62)))
                color = [PURPLE, PINK, CYAN, BLUE][min(3, index * 4 // bars)]
                self._stroke(
                    painter,
                    self._path([QPointF(x, cy - height / 2), QPointF(x, cy + height / 2)]),
                    color,
                    width=2.2,
                    strength=max(0.25, reactive),
                )
            return

        if effect == "aurora":
            colors = [PURPLE, PINK, CYAN]
            for index, color in enumerate(colors):
                points = []
                for step in range(16):
                    x = rect.left() + step / 15 * rect.width()
                    phase = progress * math.tau + step * 0.48 + index * 1.2
                    y = cy + math.sin(phase) * (5 + index * 2.5) + (index - 1) * 5
                    points.append(QPointF(x, y))
                self._stroke(painter, self._path(points), color, width=2.4, strength=0.62 + level * 0.38)
            return

        if effect == "plasma":
            radius = rect.width() * 0.28
            for index, color in enumerate((PURPLE, PINK, CYAN, BLUE)):
                angle = progress * math.tau * (1.0 + index * 0.12) + index * math.tau / 4
                point = QPointF(cx + math.cos(angle) * radius, cy + math.sin(angle) * radius)
                self._circle_glow(painter, point, 2.2 + index * 0.25, color, 0.55 + level * 0.45)
            self._arc(painter, rect.adjusted(8, 8, -8, -8), progress * 360, 250, CYAN, width=2.0, strength=0.55)
            return

        if effect == "fire":
            flame = QPainterPath()
            flame.moveTo(cx, rect.bottom() - 2)
            flame.cubicTo(rect.left() + 7, cy + 6, cx - 5, rect.top() + 12, cx - 1, rect.top() + 3)
            flame.cubicTo(cx + 2, rect.top() + 13, rect.right() - 4, cy + 3, cx, rect.bottom() - 2)
            self._stroke(painter, flame, ORANGE, width=3.0, strength=0.62 + level * 0.38)
            inner = QPainterPath()
            inner.moveTo(cx, rect.bottom() - 8)
            inner.cubicTo(cx - 7, cy + 5, cx + 1, cy - 6, cx + 2, rect.top() + 14)
            inner.cubicTo(cx + 8, cy + 6, cx + 6, rect.bottom() - 9, cx, rect.bottom() - 8)
            self._stroke(painter, inner, PINK, width=2.0, strength=level)
            return

        if effect == "ice":
            center = QPointF(cx, cy)
            for angle_index in range(6):
                angle = angle_index * math.tau / 6
                end = QPointF(cx + math.cos(angle) * rect.width() * 0.39, cy + math.sin(angle) * rect.height() * 0.39)
                self._stroke(painter, self._path([center, end]), CYAN if angle_index % 2 else BLUE, width=2.2, strength=0.58 + level * 0.42)
                branch = QPointF(cx + math.cos(angle) * rect.width() * 0.24, cy + math.sin(angle) * rect.height() * 0.24)
                for side in (-1, 1):
                    branch_angle = angle + side * 0.62
                    twig = QPointF(branch.x() + math.cos(branch_angle) * 6, branch.y() + math.sin(branch_angle) * 6)
                    self._stroke(painter, self._path([branch, twig]), WHITE, width=1.35, strength=0.7)
            return

        if effect == "police":
            left_strength = 1.0 if progress < 0.5 else 0.25
            right_strength = 1.0 if progress >= 0.5 else 0.25
            left = QRectF(rect.left() + 2, cy - 5, rect.width() * 0.44, 10)
            right = QRectF(cx + 2, cy - 5, rect.width() * 0.44, 10)
            self._stroke(painter, rounded_line(left), RED, width=5.0, strength=left_strength)
            self._stroke(painter, rounded_line(right), BLUE, width=5.0, strength=right_strength)
            return

        # Personalizado o identificador desconocido: una onda de paleta neutra.
        points = [
            QPointF(rect.left() + 2, cy + 7),
            QPointF(cx - 7, rect.top() + 8),
            QPointF(cx + 5, rect.bottom() - 8),
            QPointF(rect.right() - 2, cy - 5),
        ]
        self._stroke(painter, self._path(points[:3]), PINK, width=3.0, strength=level)
        self._stroke(painter, self._path(points[2:]), CYAN, width=3.0, strength=level)


class EffectTile(QFrame):
    clicked = Signal(str)

    def __init__(
        self,
        effect_id: str,
        title: str,
        category: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.effect_id = effect_id
        self._selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(132)
        self.setProperty("card", True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 11, 12, 11)
        layout.setSpacing(5)
        self.icon = NeonEffectIcon(effect_id, size=54)
        layout.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignCenter)
        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-weight:700;")
        self.category_label = QLabel(category)
        self.category_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.category_label.setStyleSheet(f"color:{C['muted']};font-size:10px;")
        layout.addWidget(self.title_label)
        layout.addWidget(self.category_label)
        self._refresh_style()

    def set_selected(self, selected: bool) -> None:
        selected = bool(selected)
        if selected != self._selected:
            self._selected = selected
            self.icon.selected = selected
            self._refresh_style()

    def set_frame(self, sample: LightEffectSample) -> None:
        self.icon.set_frame(
            sample.progress,
            level=sample.level,
            audio_level=sample.audio_level,
            selected=self._selected,
        )

    def _refresh_style(self) -> None:
        if self._selected:
            self.setStyleSheet(
                "QFrame {background: rgba(67,215,239,0.14);"
                "border:1px solid rgba(67,215,239,0.72);border-radius:16px;}"
            )
        else:
            self.setStyleSheet(
                "QFrame {background: rgba(255,255,255,0.025);"
                "border:1px solid rgba(255,255,255,0.06);border-radius:16px;}"
                "QFrame:hover {background: rgba(123,63,242,0.14);"
                "border:1px solid rgba(198,63,244,0.50);}"
            )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.effect_id)
        super().mousePressEvent(event)


class LightTimelinePreview(QWidget):
    """Línea de tiempo compacta con curva de brillo, color y playhead."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config: Dict[str, Any] = {"effect": "static"}
        self._custom_effects: Dict[str, Dict[str, Any]] = {}
        self._progress = 0.0
        self._audio_level = 0.0
        self._samples: list[LightEffectSample] = []
        self._cache_key: Optional[tuple[Any, ...]] = None
        self.setMinimumHeight(142)

    def set_config(
        self,
        config: Mapping[str, Any],
        custom_effects: Optional[Mapping[str, Mapping[str, Any]]] = None,
    ) -> None:
        self._config = dict(config)
        self._custom_effects = {
            str(key): dict(value) for key, value in (custom_effects or {}).items()
        }
        self._cache_key = None
        self.update()

    def set_frame(self, progress: float, audio_level: float = 0.0) -> None:
        self._progress = float(progress) % 1.0
        self._audio_level = max(0.0, min(1.0, float(audio_level)))
        if str(self._config.get("effect", "")) == "audio":
            self._cache_key = None
        self.update()

    def _signature(self) -> tuple[Any, ...]:
        palette = tuple(tuple(color[:3]) for color in self._config.get("palette", []) if isinstance(color, (list, tuple)))
        return (
            str(self._config.get("effect", "static")),
            tuple(self._config.get("color", [0, 100, 255])[:3]),
            tuple(self._config.get("secondary_color", [198, 63, 244])[:3]),
            round(float(self._config.get("brightness", 1.0)), 3),
            round(float(self._config.get("intensity", 1.0)), 3),
            int(self._config.get("direction", 1)),
            palette,
            str(self._config.get("custom_id", "")),
            round(self._audio_level, 2) if str(self._config.get("effect")) == "audio" else 0.0,
        )

    def _ensure_samples(self) -> None:
        key = self._signature()
        if key == self._cache_key and self._samples:
            return
        count = 80
        speed = max(0.1, float(self._config.get("speed", 1.0)))
        self._samples = [
            sample_light_effect(
                self._config,
                (index / (count - 1)) / speed,
                custom_effects=self._custom_effects,
                audio_level=(
                    self._audio_level * (0.60 + 0.40 * math.sin(index / (count - 1) * math.tau * 3.0) ** 2)
                    if str(self._config.get("effect")) == "audio"
                    else 0.0
                ),
                segment_count=7,
            )
            for index in range(count)
        ]
        self._cache_key = key

    def paintEvent(self, _event: Any) -> None:
        self._ensure_samples()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.setPen(QPen(QColor(C["border"]), 1))
        painter.setBrush(QColor(C["panel2"]))
        painter.drawRoundedRect(outer, 14, 14)

        color_rect = QRectF(16, 18, max(10, self.width() - 32), 30)
        gradient = QLinearGradient(color_rect.left(), color_rect.top(), color_rect.right(), color_rect.top())
        for index, sample in enumerate(self._samples):
            color = QColor(*sample.color)
            gradient.setColorAt(index / max(1, len(self._samples) - 1), color)
        painter.setPen(QPen(QColor(255, 255, 255, 28), 1))
        painter.setBrush(gradient)
        painter.drawRoundedRect(color_rect, 9, 9)

        graph = QRectF(16, 64, max(10, self.width() - 32), 52)
        painter.setPen(QPen(QColor(C["border"]), 1))
        for row in range(3):
            y = graph.top() + row * graph.height() / 2
            painter.drawLine(QPointF(graph.left(), y), QPointF(graph.right(), y))
        path = QPainterPath()
        for index, sample in enumerate(self._samples):
            x = graph.left() + index / max(1, len(self._samples) - 1) * graph.width()
            y = graph.bottom() - sample.level * graph.height()
            path.moveTo(x, y) if index == 0 else path.lineTo(x, y)
        painter.setPen(QPen(CYAN, 2.1))
        painter.drawPath(path)

        x = graph.left() + self._progress * graph.width()
        painter.setPen(QPen(WHITE, 1.4))
        painter.drawLine(QPointF(x, color_rect.top() - 3), QPointF(x, graph.bottom() + 3))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(PINK)
        painter.drawEllipse(QPointF(x, color_rect.top() - 3), 4, 4)

        painter.setPen(QColor(C["muted"]))
        painter.drawText(QRectF(16, 119, 80, 18), Qt.AlignmentFlag.AlignLeft, "0%")
        painter.drawText(QRectF(self.width() / 2 - 40, 119, 80, 18), Qt.AlignmentFlag.AlignCenter, "50%")
        painter.drawText(QRectF(self.width() - 96, 119, 80, 18), Qt.AlignmentFlag.AlignRight, "100%")


def rounded_line(rect: QRectF) -> QPainterPath:
    path = QPainterPath()
    path.moveTo(rect.left(), rect.center().y())
    path.lineTo(rect.right(), rect.center().y())
    return path
