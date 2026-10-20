"""Vista vectorial reutilizable del control y su iluminación RGB."""

from __future__ import annotations

from typing import Any, List, Optional

from .ui_common import (
    QColor, QBrush, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
    QPointF, QRadialGradient, QRectF, QWidget, Qt,
)

class ControllerVisual(QWidget):
    """Dibujo vectorial escalable del DualSense con vista previa RGB animada.

    Las demás pantallas siguen usando el modo normal basado en conexión. La
    pestaña de luces activa explícitamente ``preview_enabled`` para mostrar el
    efecto aunque no exista un control físico conectado.
    """

    def __init__(self, compact: bool = False) -> None:
        super().__init__()
        self.compact = compact
        self.connected = False
        self.left = (0.0, 0.0)
        self.right = (0.0, 0.0)
        self.preview_enabled = False
        self.light_primary = QColor(67, 215, 239)
        self.light_secondary = QColor(198, 63, 244)
        self.light_effect = "static"
        self.light_segments: List[QColor] = [
            QColor(198, 63, 244), QColor(255, 77, 214), QColor(67, 215, 239)
        ]
        self.light_progress = 0.0
        self.light_level = 1.0
        self.audio_level = 0.0
        self.emulation_mode = "none"
        self.keybridge_active = False
        self.setMinimumSize(250, 150 if compact else 215)

    def set_state(self, state: Any) -> None:
        self.connected = bool(getattr(state, "connected", False))
        self.left = (
            (getattr(state, "left_stick_x", 128) - 128) / 128,
            (getattr(state, "left_stick_y", 128) - 128) / 128,
        )
        self.right = (
            (getattr(state, "right_stick_x", 128) - 128) / 128,
            (getattr(state, "right_stick_y", 128) - 128) / 128,
        )
        self.update()

    def set_light_preview(
        self,
        primary: Optional[QColor],
        secondary: Optional[QColor] = None,
        effect: str = "static",
    ) -> None:
        self.preview_enabled = True
        self.light_primary = QColor(primary) if primary is not None else QColor(67, 215, 239)
        self.light_secondary = QColor(secondary) if secondary is not None else QColor(198, 63, 244)
        self.light_effect = str(effect or "static")
        self.light_segments = [QColor(self.light_secondary), QColor(self.light_primary), QColor(self.light_secondary)]
        self.update()

    def set_light_frame(self, sample: Any, effect: Optional[str] = None) -> None:
        """Actualiza un cuadro generado por ``src.light_effects.sample_light_effect``."""
        self.preview_enabled = True
        if effect is not None:
            self.light_effect = str(effect or "static")
        try:
            color = getattr(sample, "color")
            self.light_primary = QColor(int(color[0]), int(color[1]), int(color[2]))
        except Exception:
            pass
        try:
            raw_segments = list(getattr(sample, "segments"))
            parsed = [QColor(int(color[0]), int(color[1]), int(color[2])) for color in raw_segments]
            if parsed:
                self.light_segments = parsed
                self.light_secondary = QColor(parsed[-1])
        except Exception:
            pass
        try:
            self.light_progress = max(0.0, min(1.0, float(getattr(sample, "progress"))))
        except Exception:
            self.light_progress = 0.0
        try:
            self.light_level = max(0.0, min(1.0, float(getattr(sample, "level"))))
        except Exception:
            self.light_level = 1.0
        try:
            self.audio_level = max(0.0, min(1.0, float(getattr(sample, "audio_level"))))
        except Exception:
            self.audio_level = 0.0
        self.update()

    def clear_light_preview(self) -> None:
        self.preview_enabled = False
        self.light_progress = 0.0
        self.light_level = 1.0
        self.update()

    def set_emulation_mode(self, mode: str, *, keybridge: bool = False) -> None:
        """Cambia la identidad visual sin alterar el motor de emulación."""
        normalized = str(mode or "none").lower()
        if normalized not in {"none", "ps4", "xbox"}:
            normalized = "none"
        self.emulation_mode = normalized
        self.keybridge_active = bool(keybridge)
        if self.keybridge_active:
            self.set_light_preview(QColor("#a855f7"), QColor("#7c3aed"), "static")
        elif normalized == "xbox":
            self.set_light_preview(QColor("#52e36f"), QColor("#159947"), "static")
        elif normalized == "ps4":
            self.set_light_preview(QColor("#2f8cff"), QColor("#0b4edb"), "static")
        else:
            self.set_light_preview(QColor("#43d7ef"), QColor("#7b3ff2"), "static")
        self.update()

    def _active_light(self) -> bool:
        return self.preview_enabled or self.connected

    def _light_gradient(self, start_x: float = 92.0, end_x: float = 268.0) -> QLinearGradient:
        gradient = QLinearGradient(start_x, 70, end_x, 70)
        colors = self.light_segments if self.light_segments else [self.light_secondary, self.light_primary]
        if len(colors) == 1:
            gradient.setColorAt(0.0, colors[0])
            gradient.setColorAt(1.0, colors[0])
            return gradient
        for index, color in enumerate(colors):
            gradient.setColorAt(index / max(1, len(colors) - 1), color)
        return gradient

    def _draw_light_path(self, painter: QPainter, path: QPainterPath, gradient: QLinearGradient) -> None:
        level = max(0.08, self.light_level) if self._active_light() else 0.22
        glow_alpha = int(88 * level)
        glow_color = QColor(self.light_primary)
        glow_color.setAlpha(glow_alpha)
        glow_pen = QPen(glow_color, 13, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(glow_pen)
        painter.drawPath(path)
        core_pen = QPen(QBrush(gradient), 5.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(core_pen)
        painter.drawPath(path)
        shine = QColor(255, 255, 255, int(105 + 90 * level))
        shine_pen = QPen(shine, 1.25, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(shine_pen)
        painter.drawPath(path)

    def paintEvent(self, _event: Any) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        scale = min(w / 360.0, h / 215.0)
        p.translate((w - 360 * scale) / 2, (h - 215 * scale) / 2)
        p.scale(scale, scale)

        active = self._active_light()
        gradient = self._light_gradient()

        # Halo trasero para dar profundidad sin depender de imágenes raster.
        halo = QRadialGradient(QPointF(180, 94), 142)
        halo_color = QColor(self.light_primary if active else QColor("#26314b"))
        halo_color.setAlpha(int((70 if active else 24) * max(0.12, self.light_level)))
        halo.setColorAt(0.0, halo_color)
        halo.setColorAt(0.56, QColor(halo_color.red(), halo_color.green(), halo_color.blue(), halo_color.alpha() // 3))
        halo.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(halo))
        p.drawEllipse(QPointF(180, 96), 150, 108)

        body = QPainterPath()
        body.moveTo(112, 39)
        body.cubicTo(72, 38, 52, 57, 42, 92)
        body.cubicTo(32, 125, 10, 178, 37, 195)
        body.cubicTo(59, 209, 80, 159, 96, 145)
        body.cubicTo(118, 126, 242, 126, 264, 145)
        body.cubicTo(280, 159, 301, 209, 323, 195)
        body.cubicTo(350, 178, 328, 125, 318, 92)
        body.cubicTo(308, 57, 288, 38, 248, 39)
        body.cubicTo(223, 42, 211, 55, 180, 55)
        body.cubicTo(149, 55, 137, 42, 112, 39)
        body.closeSubpath()
        p.setPen(QPen(QColor("#b9c6df"), 2))
        p.setBrush(QColor("#eef2f9"))
        p.drawPath(body)

        center = QPainterPath()
        center.moveTo(126, 43)
        center.lineTo(234, 43)
        center.lineTo(222, 115)
        center.cubicTo(205, 128, 155, 128, 138, 115)
        center.closeSubpath()
        p.setPen(QPen(QColor("#263047"), 2))
        p.setBrush(QColor("#111827"))
        p.drawPath(center)

        # Touchpad.
        touchpad = QRectF(139, 48, 82, 51)
        p.setPen(QPen(QColor("#303b54"), 1.5))
        p.setBrush(QColor("#202a40"))
        p.drawRoundedRect(touchpad, 8, 8)
        p.setPen(QPen(QColor(255, 255, 255, 18), 1))
        for y in range(55, 94, 7):
            p.drawLine(QPointF(147, y), QPointF(213, y))

        # Identidad dinámica del modo: nativo, DS4, Xbox o KeyBridge.
        if self.keybridge_active:
            emblem, emblem_color, emblem_size = "⌨", QColor("#d8b4fe"), 20
        elif self.emulation_mode == "xbox":
            emblem, emblem_color, emblem_size = "X", QColor("#72f08b"), 22
        elif self.emulation_mode == "ps4":
            emblem, emblem_color, emblem_size = "PS\n4", QColor("#72b8ff"), 13
        else:
            emblem, emblem_color, emblem_size = "SONY\n5", QColor("#dce7ff"), 11
        p.setPen(emblem_color)
        p.setFont(QFont("Segoe UI", emblem_size, QFont.Weight.Bold))
        p.drawText(touchpad.adjusted(4, 3, -4, -3), Qt.AlignmentFlag.AlignCenter, emblem)

        # Barra RGB rodeando el touchpad, como en el concepto de RGB Studio.
        light_path = QPainterPath()
        light_path.moveTo(131, 51)
        light_path.cubicTo(130, 69, 131, 91, 141, 104)
        light_path.cubicTo(153, 117, 207, 117, 219, 104)
        light_path.cubicTo(229, 91, 230, 69, 229, 51)
        if active:
            self._draw_light_path(p, light_path, gradient)
        else:
            p.setPen(QPen(QColor("#33415f"), 4.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawPath(light_path)

        # Barra superior compacta para que se aprecie bien el movimiento.
        top_bar = QRectF(139, 43, 82, 7)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 24))
        p.drawRoundedRect(top_bar.adjusted(-1, -1, 1, 1), 4, 4)
        p.setBrush(QBrush(gradient if active else QColor("#33415f")))
        p.drawRoundedRect(top_bar, 3.5, 3.5)

        p.setPen(QPen(QColor("#5b6680"), 2))
        p.setBrush(QColor("#202a40"))
        for cx, cy, offset in ((126, 131, self.left), (234, 131, self.right)):
            p.drawEllipse(QPointF(cx, cy), 20, 20)
            p.setBrush(QColor("#111728"))
            p.drawEllipse(QPointF(cx + offset[0] * 5, cy + offset[1] * 5), 13, 13)
            p.setBrush(QColor("#202a40"))

        # D-pad.
        p.setBrush(QColor("#2b3449"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(76, 77, 14, 44), 4, 4)
        p.drawRoundedRect(QRectF(61, 92, 44, 14), 4, 4)

        # Botones frontales adaptados al dispositivo virtual elegido.
        if self.emulation_mode == "xbox" or self.keybridge_active and self.emulation_mode == "xbox":
            face_buttons = (
                (281, 83, "Y", "#f4d44d"),
                (300, 102, "B", "#ff6678"),
                (281, 121, "A", "#65e37e"),
                (262, 102, "X", "#55b8ff"),
            )
        else:
            face_buttons = (
                (281, 83, "△", "#79d8b1"),
                (300, 102, "○", "#ed8fba"),
                (281, 121, "×", "#8cc9f0"),
                (262, 102, "□", "#c99ee9"),
            )
        p.setPen(QPen(QColor("#59657f"), 2))
        p.setBrush(QColor("#f7f9ff"))
        for x, y, mark, color in face_buttons:
            p.drawEllipse(QPointF(x, y), 9, 9)
            p.setPen(QColor(color))
            p.setFont(QFont("Segoe UI Symbol", 7, QFont.Weight.Bold))
            p.drawText(QRectF(x - 8, y - 8, 16, 16), Qt.AlignmentFlag.AlignCenter, mark)
            p.setPen(QPen(QColor("#59657f"), 2))

        # Indicadores del jugador.
        led_y = 163
        colors = self.light_segments or [self.light_primary]
        for index, led_x in enumerate((155, 170, 190, 205)):
            p.setBrush(QColor(255, 255, 255, 18))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(led_x, led_y, 10, 4), 2, 2)
            if active:
                current = colors[index % len(colors)]
                p.setBrush(QColor(current.red(), current.green(), current.blue(), 225))
                p.drawRoundedRect(QRectF(led_x, led_y, 10, 4), 2, 2)

        p.end()

