"""Editor visual de curvas de respuesta para Input Studio."""

from __future__ import annotations

from typing import Any, List, Optional

from .i18n import tr
from .ui_common import (
    C, QColor, QMouseEvent, QPainter, QPainterPath, QPen, QPointF, QRectF,
    Qt, Signal, QWidget,
)

class ResponseCurveEditor(QWidget):
    """Vista y editor normalizado 0..1 para la respuesta de los sticks."""

    changed = Signal(object)
    DEFAULT_POINTS = [
        (0.0, 0.0), (0.25, 0.16), (0.5, 0.42),
        (0.75, 0.78), (1.0, 1.0),
    ]
    CURVES = {"linear", "exponential", "aggressive", "custom"}

    def __init__(self, editable: bool = True) -> None:
        super().__init__()
        self.allow_editing = bool(editable)
        self.editable = bool(editable)
        self.curve_mode = "custom"
        self.points = list(self.DEFAULT_POINTS)
        self._dragging: Optional[int] = None
        self.setMinimumHeight(230)
        self.setMouseTracking(True)

    def set_points(self, points: Any) -> None:
        parsed = []
        if isinstance(points, (list, tuple)):
            for item in points:
                try:
                    x, y = item
                    parsed.append(
                        (
                            max(0.0, min(1.0, float(x))),
                            max(0.0, min(1.0, float(y))),
                        )
                    )
                except (TypeError, ValueError, OverflowError):
                    pass
        self.points = sorted(parsed) if len(parsed) >= 2 else list(self.DEFAULT_POINTS)
        self.points[0] = (0.0, 0.0)
        self.points[-1] = (1.0, 1.0)
        self.update()

    def set_curve(self, curve: str, custom_points: Any = None) -> None:
        """Actualiza la curva visible y permite arrastrar solo la personalizada."""
        if custom_points is not None:
            self.set_points(custom_points)
        self.curve_mode = str(curve or "linear")
        if self.curve_mode not in self.CURVES:
            self.curve_mode = "linear"
        self.editable = self.allow_editing and self.curve_mode == "custom"
        self.setCursor(
            Qt.CursorShape.CrossCursor if self.editable
            else Qt.CursorShape.ArrowCursor
        )
        self._dragging = None
        self.update()

    def set_editable(self, editable: bool) -> None:
        self.allow_editing = bool(editable)
        self.editable = self.allow_editing and self.curve_mode == "custom"
        self.setCursor(
            Qt.CursorShape.CrossCursor if self.editable
            else Qt.CursorShape.ArrowCursor
        )
        self.update()

    def get_points(self) -> List[List[float]]:
        return [[round(x, 4), round(y, 4)] for x, y in self.points]

    def _rect(self) -> QRectF:
        return QRectF(40, 18, max(1, self.width() - 58), max(1, self.height() - 52))

    def _canvas(self, point: tuple[float, float]) -> QPointF:
        rect = self._rect()
        return QPointF(
            rect.left() + point[0] * rect.width(),
            rect.bottom() - point[1] * rect.height(),
        )

    def _display_points(self) -> list[tuple[float, float]]:
        if self.curve_mode == "custom":
            return list(self.points)
        values = [index / 48 for index in range(49)]
        if self.curve_mode == "exponential":
            return [(value, value * value) for value in values]
        if self.curve_mode == "aggressive":
            return [(value, value ** 0.5) for value in values]
        return [(value, value) for value in values]

    def paintEvent(self, _event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(C["panel2"]))
        rect = self._rect()
        painter.setPen(QPen(QColor(C["border"]), 1))
        for index in range(5):
            x = rect.left() + index * rect.width() / 4
            y = rect.top() + index * rect.height() / 4
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))

        # Referencia lineal para comparar rápidamente presets y curva custom.
        reference = QPen(QColor(C["faint"]), 1)
        reference.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(reference)
        painter.drawLine(self._canvas((0.0, 0.0)), self._canvas((1.0, 1.0)))

        path = QPainterPath()
        for index, point in enumerate(self._display_points()):
            canvas_point = self._canvas(point)
            if index == 0:
                path.moveTo(canvas_point)
            else:
                path.lineTo(canvas_point)
        painter.setPen(QPen(QColor(C["accent2"]), 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        if self.curve_mode == "custom":
            for index, point in enumerate(self.points):
                canvas_point = self._canvas(point)
                color = C["cyan"] if index not in (0, len(self.points) - 1) else C["muted"]
                painter.setBrush(QColor(color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(canvas_point, 6, 6)

        painter.setPen(QColor(C["muted"]))
        painter.drawText(4, 16, tr("Salida"))
        painter.drawText(int(rect.right() - 42), self.height() - 8, tr("Entrada"))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self.editable:
            return
        best = None
        distance = 999.0
        for index, point in enumerate(self.points[1:-1], 1):
            candidate = (self._canvas(point) - event.position()).manhattanLength()
            if candidate < distance:
                best, distance = index, candidate
        if best is not None and distance < 22:
            self._dragging = best
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging is None or not self.editable:
            return
        rect = self._rect()
        index = self._dragging
        x = max(
            self.points[index - 1][0] + 0.02,
            min(
                self.points[index + 1][0] - 0.02,
                (event.position().x() - rect.left()) / rect.width(),
            ),
        )
        y = max(0.0, min(1.0, (rect.bottom() - event.position().y()) / rect.height()))
        self.points[index] = (x, y)
        self.update()
        self.changed.emit(self.get_points())
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._dragging = None
        event.accept()
