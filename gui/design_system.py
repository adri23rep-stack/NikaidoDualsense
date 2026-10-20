"""Sistema visual compartido de Nikaido.

Centraliza colores, estilos y componentes pequeños para que las pantallas no
repitan CSS ni construyan botones de forma distinta. No contiene lógica del
DualSense ni conoce los motores de ``src``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Optional

from .i18n import mark_text_source, tr

from src.appearance import (
    ACCENT_PALETTES,
    APPEARANCE_PRESETS,
    DEFAULT_APPEARANCE,
    appearance_background_signature,
    appearance_style_signature,
    normalize_appearance,
)

__all__ = (
    "ACCENT_PALETTES",
    "APPEARANCE_PRESETS",
    "DEFAULT_APPEARANCE",
    "appearance_background_signature",
    "appearance_style_signature",
    "normalize_appearance",
)


from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


C = {
    "bg": "#070b17",
    "sidebar": "#0a1020",
    "panel": "#0d1324",
    "panel2": "#11182a",
    "hover": "#151d32",
    "border": "#1d2740",
    "brand": "#0e1630",
    "brand2": "#121d3a",
    "accent": "#7b3ff2",
    "accent2": "#c63ff4",
    "cyan": "#43d7ef",
    "green": "#54d67b",
    "yellow": "#f1c84d",
    "danger": "#ff5e74",
    "text": "#f4f6ff",
    "muted": "#8992aa",
    "faint": "#566078",
}

# BASE_APP_QSS is rendered once at import time. Keep immutable source colors
# so switching accent palettes repeatedly never depends on the previously
# selected palette. C is updated at runtime for custom-painted widgets.
_BASE_ACCENT = {
    "accent": "#7b3ff2",
    "accent2": "#c63ff4",
    "cyan": "#43d7ef",
    "hover": "#8c51f6",
}

BASE_APP_QSS = f"""
* {{ font-family: 'Segoe UI'; font-size: 13px; color: {C['text']}; }}
QMainWindow, QDialog, QWidget#root {{ background: {C['bg']}; }}
QFrame#sidebar {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #091228, stop:1 #070d1b);
    border-right: 1px solid {C['border']};
}}
QFrame#topbar {{ background: {C['bg']}; border-bottom: 1px solid {C['border']}; }}
QFrame#statusbar {{ background: {C['sidebar']}; border-top: 1px solid {C['border']}; }}
QFrame#brandCard {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {C['brand']}, stop:1 {C['brand2']});
    border: 1px solid #243456;
    border-radius: 16px;
}}
QFrame[card="true"] {{ background: {C['panel']}; border: 1px solid {C['border']}; border-radius: 14px; }}
QFrame[subcard="true"] {{ background: {C['panel2']}; border: 1px solid {C['border']}; border-radius: 10px; }}
QLabel[muted="true"] {{ color: {C['muted']}; }}
QLabel[eyebrow="true"] {{ color: #95a2c0; font-size: 10px; font-weight: 700; letter-spacing: 0.8px; }}
QLabel#brandCaption {{ color: {C['muted']}; font-size: 11px; }}
QLabel#versionBadge {{
    color: #f7f7ff;
    background: rgba(198, 63, 244, 0.18);
    border: 1px solid rgba(198, 63, 244, 0.45);
    border-radius: 10px;
    padding: 4px 8px;
    font-size: 10px;
    font-weight: 700;
}}
QLabel[title="true"] {{ font-size: 20px; font-weight: 700; }}
QLabel[heading="true"] {{ font-size: 16px; font-weight: 700; }}
QLabel[value="true"] {{ font-size: 20px; font-weight: 700; }}
QLabel[accentText="true"] {{ color: {C['cyan']}; }}
QLabel[accentIcon="true"] {{ color: {C['accent2']}; }}
QLabel[accentBadge="true"] {{
    background: rgba(123,63,242,0.22);
    color: white;
    border: 1px solid {C['accent']};
    border-radius: 9px;
    padding: 7px 10px;
    font-weight: 700;
}}
QPushButton {{ background: {C['panel2']}; border: 1px solid {C['border']}; border-radius: 7px; padding: 8px 14px; font-weight: 600; }}
QPushButton[homeButton="true"] {{
    background: rgba(123,63,242,0.16);
    border: 1px solid rgba(198,63,244,0.42);
    border-radius: 12px;
    color: {C['accent2']};
    padding: 0;
    font-size: 24px;
}}
QPushButton[homeButton="true"]:hover {{
    background: rgba(123,63,242,0.28);
    border-color: {C['accent2']};
}}
QPushButton:hover {{ background: {C['hover']}; border-color: #394467; }}
QPushButton:focus {{ border-color: {C['accent2']}; }}
QPushButton:pressed {{ background: #1b2440; }}
QPushButton:disabled {{ color: {C['faint']}; background: #0d1320; border-color: #182036; }}
QPushButton[primary="true"] {{ background: {C['accent']}; border-color: {C['accent']}; }}
QPushButton[primary="true"]:hover {{ background: #8c51f6; }}
QPushButton[danger="true"] {{ color: {C['danger']}; }}
QPushButton[danger="true"]:hover {{ background: #321722; border-color: #6f2a3a; }}
QPushButton[iconButton="true"] {{ padding: 0; font-size: 17px; min-width: 36px; min-height: 36px; }}
QPushButton[windowClose="true"]:hover {{ background: #b3263e; border-color: #d1445c; color: white; }}
QPushButton[nav="true"] {{
    text-align: left;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 14px;
    padding: 0;
    color: #b8c0d4;
    font-weight: 600;
}}
QPushButton[nav="true"][hasSubtitle="true"] {{ min-height: 62px; }}
QPushButton[nav="true"]:hover {{
    background: rgba(25, 36, 62, 0.94);
    border-color: #233150;
    color: white;
}}
QPushButton[nav="true"]:checked {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 rgba(123,63,242,0.30), stop:1 rgba(198,63,244,0.18));
    border: 1px solid rgba(163, 103, 255, 0.62);
    color: white;
}}
QPushButton[nav="true"] QLabel#navIcon {{
    color: #a8b2c9;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 10px;
    font-size: 16px;
    font-weight: 700;
}}
QPushButton[nav="true"] QLabel#navTitle {{
    color: #edf1ff;
    font-size: 14px;
    font-weight: 700;
}}
QPushButton[nav="true"] QLabel#navSubtitle {{
    color: {C['muted']};
    font-size: 11px;
    padding-top: 1px;
}}
QPushButton[nav="true"] QLabel#navArrow {{
    color: #6d7893;
    font-size: 18px;
    font-weight: 700;
}}
QPushButton[nav="true"]:hover QLabel#navIcon {{
    color: white;
    background: rgba(123,63,242,0.15);
    border-color: rgba(123,63,242,0.35);
}}
QPushButton[nav="true"]:hover QLabel#navSubtitle,
QPushButton[nav="true"]:hover QLabel#navArrow {{ color: #c9d2e6; }}
QPushButton[nav="true"]:checked QLabel#navIcon {{
    color: white;
    background: rgba(255,255,255,0.10);
    border-color: rgba(255,255,255,0.14);
}}
QPushButton[nav="true"]:checked QLabel#navSubtitle,
QPushButton[nav="true"]:checked QLabel#navArrow {{ color: #e1ddff; }}
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {{ background: {C['panel2']}; border: 1px solid {C['border']}; border-radius: 6px; padding: 7px 10px; min-height: 19px; }}
QComboBox:hover, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {C['accent']}; }}
QComboBox::drop-down {{ border: 0; width: 24px; }}
QComboBox QAbstractItemView {{ background: {C['panel2']}; border: 1px solid {C['border']}; selection-background-color: {C['accent']}; }}
QScrollArea {{ background: transparent; border: 0; }}
QScrollArea#navScroll,
QScrollArea#navScroll > QWidget > QWidget,
QWidget#navBody {{ background: transparent; border: 0; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #2a3552; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QProgressBar {{ background: #18213a; border: 0; border-radius: 3px; min-height: 7px; text-align: center; color: {C['muted']}; }}
QProgressBar::chunk {{ background: {C['green']}; border-radius: 3px; }}
QSlider::groove:horizontal {{ background: #252e49; height: 4px; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {C['accent']}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: white; border: 2px solid {C['accent']}; width: 14px; margin: -6px 0; border-radius: 8px; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 30px; height: 16px; border-radius: 8px; background: #28314a; }}
QCheckBox::indicator:checked {{ background: {C['accent']}; }}
QTableWidget, QListWidget {{ background: transparent; alternate-background-color: {C['panel2']}; border: 1px solid {C['border']}; border-radius: 8px; gridline-color: {C['border']}; }}
QHeaderView::section {{ background: {C['panel2']}; color: {C['muted']}; border: 0; border-bottom: 1px solid {C['border']}; padding: 8px; }}
QTabWidget::pane {{
    border: 1px solid {C['border']};
    border-radius: 10px;
    top: 0;
    margin-top: 7px;
    background: {C['panel']};
}}
QTabWidget::tab-bar {{ left: 0; }}
QTabBar {{ background: transparent; qproperty-drawBase: 0; }}
QTabBar::tab {{
    background: {C['panel2']};
    color: #aab2c7;
    border: 1px solid {C['border']};
    border-radius: 10px;
    padding: 10px 16px;
    margin-right: 8px;
    min-height: 22px;
    font-weight: 700;
}}
QTabBar::tab:hover:!selected {{ background: {C['hover']}; color: white; border-color: #394467; }}
QTabBar::tab:selected {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 rgba(123,63,242,0.38), stop:1 rgba(198,63,244,0.18));
    color: white;
    border-color: rgba(163, 103, 255, 0.62);
}}
QTabBar QToolButton {{
    background: {C['panel2']};
    border: 1px solid {C['border']};
    border-radius: 7px;
    min-width: 28px;
    margin: 1px 2px;
}}
QTabBar QToolButton:hover {{ background: {C['hover']}; border-color: {C['accent']}; }}
QToolTip {{ background: #151d32; color: white; border: 1px solid {C['border']}; padding: 7px 9px; border-radius: 6px; }}
QFrame#toast {{ background: #11192c; border: 1px solid #31405f; border-radius: 10px; }}
QFrame#toast[level="success"] {{ border-color: #2f7d4b; }}
QFrame#toast[level="warning"] {{ border-color: #8b742b; }}
QFrame#toast[level="error"] {{ border-color: #8f3042; }}
QLabel#toastIcon {{ font-size: 18px; font-weight: 800; }}
QLabel#toastMessage {{ font-size: 12px; }}
QDialog#welcomeWizard {{ background: {C['bg']}; }}
QFrame#wizardHeader {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0c1429, stop:1 #101735);
    border-bottom: 1px solid {C['border']};
}}
QFrame#wizardRail {{
    background: rgba(8, 14, 30, 0.96);
    border-right: 1px solid {C['border']};
}}
QLabel#wizardBrand {{ font-size: 21px; font-weight: 800; letter-spacing: 1px; }}
QLabel#wizardTitle {{ font-size: 28px; font-weight: 800; }}
QLabel#wizardHero {{ font-size: 24px; font-weight: 800; line-height: 1.2; }}
QLabel[languageBadge="true"] {{
    color: #d8ccff;
    background: rgba(123,63,242,0.20);
    border: 1px solid rgba(198,63,244,0.40);
    border-radius: 10px;
    padding: 7px 11px;
    font-weight: 700;
}}
QPushButton[languageChoice="true"] {{
    text-align: left;
    padding: 18px 20px;
    border-radius: 15px;
    font-size: 15px;
    font-weight: 700;
    background: rgba(18,25,52,0.92);
    border: 1px solid {C['border']};
}}
QPushButton[languageChoice="true"]:hover {{
    background: rgba(123,63,242,0.18);
    border-color: rgba(198,63,244,0.58);
}}
QPushButton[languageChoice="true"]:checked {{
    background: rgba(123,63,242,0.30);
    border: 2px solid {C['accent2']};
    color: white;
}}
QLabel#wizardFeatureIcon {{
    color: white;
    background: rgba(123,63,242,0.24);
    border: 1px solid rgba(198,63,244,0.52);
    border-radius: 11px;
    font-size: 14px;
    font-weight: 800;
}}
QLabel[wizardStep="true"] {{
    color: {C['muted']};
    background: transparent;
    border: 1px solid transparent;
    border-radius: 11px;
    padding: 8px 10px;
    font-size: 11px;
}}
QLabel[wizardStep="true"][done="true"] {{ color: #b8c3dd; }}
QLabel[wizardStep="true"][active="true"] {{
    color: white;
    background: rgba(123,63,242,0.22);
    border-color: rgba(198,63,244,0.48);
    font-weight: 700;
}}
QPushButton[wizardDestination="true"] {{
    text-align: left;
    padding: 13px 16px;
    border-radius: 12px;
}}
QPushButton[wizardDestination="true"]:hover {{
    background: rgba(123,63,242,0.22);
    border-color: {C['accent2']};
}}
QFrame#mascotPanel {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(18,25,52,0.98), stop:1 rgba(9,14,31,0.98));
    border: 1px solid rgba(145,91,255,0.48);
    border-radius: 18px;
}}
QLabel#mascotBadge {{
    color: white;
    background: rgba(123,63,242,0.34);
    border: 1px solid rgba(198,63,244,0.55);
    border-radius: 9px;
    padding: 4px 9px;
    font-size: 10px;
    font-weight: 800;
}}
QLabel#mascotName {{
    color: #d8ccff;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1px;
}}
QLabel#mascotSprite {{
    background: transparent;
    border: none;
}}
QFrame#mascotBubble {{
    background: rgba(8,13,29,0.92);
    border: 1px solid rgba(99,116,170,0.38);
    border-radius: 14px;
}}
QLabel#mascotTitle {{
    color: white;
    font-size: 14px;
    font-weight: 800;
}}
QLabel#mascotMessage {{
    color: #aeb8d2;
    font-size: 11px;
    line-height: 1.35;
}}
QFrame#assistantTipCard {{
    background: rgba(13, 19, 36, 0.97);
    border: 1px solid rgba(145,91,255,0.72);
    border-radius: 18px;
}}
QLabel#assistantTipSprite {{
    background: transparent;
    border: none;
}}
QFrame#wizardConnectionStatus {{
    background: rgba(13,20,43,0.92);
    border: 1px solid rgba(67,215,239,0.32);
    border-radius: 13px;
}}
QLabel#wizardConnectionValue {{
    font-size: 17px;
    font-weight: 800;
}}
"""


def _rgba(hex_color: str, opacity_percent: int) -> str:
    value = str(hex_color).lstrip("#")
    if len(value) != 6:
        return hex_color
    r, g, b = int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    alpha = max(0.0, min(1.0, opacity_percent / 100.0))
    return f"rgba({r}, {g}, {b}, {alpha:.3f})"


def _rgb_tuple(hex_color: str) -> tuple[int, int, int]:
    value = str(hex_color).lstrip("#")
    if len(value) != 6:
        return 0, 0, 0
    return int(value[:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def build_app_qss(appearance: Optional[dict] = None) -> str:
    """Genera el tema con transparencias y acento sin tocar la lógica Qt."""
    settings = normalize_appearance(appearance)
    panel_alpha = settings["panel_opacity"]
    sidebar_alpha = settings["sidebar_opacity"]
    button_alpha = settings["button_opacity"]
    palette = ACCENT_PALETTES[settings["accent_style"]]
    qss = BASE_APP_QSS

    # La plantilla usa los colores base. Sustituirlos aquí permite cambiar el
    # acento sin duplicar una hoja QSS de cientos de líneas.
    qss = qss.replace(_BASE_ACCENT["accent2"], palette["accent2"])
    qss = qss.replace(_BASE_ACCENT["accent"], palette["accent"])
    qss = qss.replace(_BASE_ACCENT["cyan"], palette["cyan"])
    qss = qss.replace(_BASE_ACCENT["hover"], palette["hover"])
    old_rgb = {
        (123, 63, 242): _rgb_tuple(palette["accent"]),
        (198, 63, 244): _rgb_tuple(palette["accent2"]),
        (163, 103, 255): _rgb_tuple(palette["accent2"]),
    }
    for old, new in old_rgb.items():
        for spaced in (True, False):
            old_text = f"rgba({old[0]}{', ' if spaced else ','}{old[1]}{', ' if spaced else ','}{old[2]},"
            new_text = f"rgba({new[0]}{', ' if spaced else ','}{new[1]}{', ' if spaced else ','}{new[2]},"
            qss = qss.replace(old_text, new_text)

    qss = qss.replace(
        f"QMainWindow, QDialog, QWidget#root {{ background: {C['bg']}; }}",
        f"QMainWindow, QWidget#root {{ background: transparent; }}\nQDialog {{ background: {C['bg']}; }}",
    )
    qss = qss.replace(
        "stop:0 #091228, stop:1 #070d1b",
        f"stop:0 {_rgba('#091228', sidebar_alpha)}, stop:1 {_rgba('#070d1b', sidebar_alpha)}",
    )
    qss = qss.replace(
        f"QFrame#topbar {{ background: {C['bg']};",
        f"QFrame#topbar {{ background: {_rgba(C['bg'], sidebar_alpha)};",
    )
    qss = qss.replace(
        f"QFrame#statusbar {{ background: {C['sidebar']};",
        f"QFrame#statusbar {{ background: {_rgba(C['sidebar'], sidebar_alpha)};",
    )
    qss = qss.replace(
        f"stop:0 {C['brand']}, stop:1 {C['brand2']}",
        f"stop:0 {_rgba(C['brand'], sidebar_alpha)}, stop:1 {_rgba(C['brand2'], sidebar_alpha)}",
    )
    qss = qss.replace(f"background: {C['panel']};", f"background: {_rgba(C['panel'], panel_alpha)};")
    qss = qss.replace(f"background: {C['panel2']};", f"background: {_rgba(C['panel2'], button_alpha)};")
    qss = qss.replace(f"alternate-background-color: {C['panel2']};", f"alternate-background-color: {_rgba(C['panel2'], panel_alpha)};")
    qss = qss.replace(f"background: {C['hover']};", f"background: {_rgba(C['hover'], min(100, button_alpha + 5))};")
    qss = qss.replace("background: rgba(25, 36, 62, 0.94);", f"background: {_rgba('#19243e', button_alpha)};")

    if settings["ui_density"] == "compact":
        qss = qss.replace("font-size: 13px", "font-size: 12px", 1)
        qss = qss.replace("padding: 8px 14px", "padding: 6px 11px")
        qss = qss.replace("padding: 10px 16px", "padding: 8px 13px")
        qss = qss.replace("min-height: 62px", "min-height: 54px")

    # Los menús flotantes deben mantenerse opacos aunque las tarjetas sean
    # transparentes; de otro modo el texto queda ilegible sobre el fondo.
    qss += f"""
QComboBox QAbstractItemView, QMenu {{
    background: {C['panel2']};
    border: 1px solid {C['border']};
    padding: 5px;
}}
QMenu::item {{ padding: 7px 18px; border-radius: 5px; }}
QMenu::item:selected {{ background: {palette['accent']}; color: white; }}
"""
    return qss


def apply_runtime_palette(appearance: Optional[dict] = None) -> dict:
    """Sincroniza colores usados por widgets dibujados con QPainter.

    La hoja QSS cambia controles normales. Algunos gráficos (sticks, curvas,
    Nexus) se pintan a mano y leen C en cada repintado; mantener C sincronizado
    evita que conserven el violeta después de elegir otro acento.
    """
    settings = normalize_appearance(appearance)
    palette = ACCENT_PALETTES[settings["accent_style"]]
    C["accent"] = palette["accent"]
    C["accent2"] = palette["accent2"]
    C["cyan"] = palette["cyan"]
    return palette


APP_QSS = build_app_qss()


def configure_tabs(widget: QTabWidget) -> QTabWidget:
    """Aplica el comportamiento moderno y evita texto recortado en pestañas."""
    widget.setDocumentMode(True)
    bar = widget.tabBar()
    bar.setDrawBase(False)
    bar.setExpanding(False)
    bar.setUsesScrollButtons(True)
    bar.setElideMode(Qt.TextElideMode.ElideNone)
    bar.setMovable(False)
    return widget

def clear_layout(layout: QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.deleteLater()
        elif item.layout():
            clear_layout(item.layout())


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return base / relative


def card(parent: Optional[QWidget] = None, *, sub: bool = False) -> QFrame:
    frame = QFrame(parent)
    frame.setProperty("subcard" if sub else "card", True)
    return frame


def label(text: str, kind: str = "") -> QLabel:
    widget = QLabel(tr(text))
    mark_text_source(widget, text)
    if kind:
        widget.setProperty(kind, True)
    return widget


def button(
    text: str,
    callback: Callable[[], None],
    *,
    primary: bool = False,
    danger: bool = False,
    tooltip: str = "",
) -> QPushButton:
    widget = QPushButton(tr(text))
    mark_text_source(widget, text, tooltip=tooltip or None)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.setProperty("primary", primary)
    widget.setProperty("danger", danger)
    widget.setAutoDefault(False)
    if tooltip:
        widget.setToolTip(tr(tooltip))
        widget.setAccessibleDescription(tr(tooltip))
    widget.clicked.connect(callback)
    return widget


class ToastOverlay(QFrame):
    """Aviso no modal reutilizable para no interrumpir el flujo de trabajo."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("toast")
        self.setProperty("level", "info")
        self.setMinimumWidth(280)
        self.setMaximumWidth(460)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 10, 10)
        layout.setSpacing(9)
        self.icon = QLabel("●")
        self.icon.setObjectName("toastIcon")
        layout.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)
        self.message = QLabel()
        self.message.setObjectName("toastMessage")
        self.message.setWordWrap(True)
        layout.addWidget(self.message, 1)
        close = QPushButton("×")
        close.setProperty("iconButton", True)
        close.setFixedSize(28, 28)
        close.setToolTip("Cerrar aviso")
        close.clicked.connect(self.hide_animated)
        layout.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)

        self.opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity)
        self.animation = QPropertyAnimation(self.opacity, b"opacity", self)
        self.animation.setDuration(150)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide_animated)
        self.hide()

    def show_message(self, message: str, level: str = "info", duration: int = 3500) -> None:
        if not message:
            return
        level = level if level in {"info", "success", "warning", "error"} else "info"
        self.setProperty("level", level)
        self.style().unpolish(self)
        self.style().polish(self)
        self.icon.setText({"success": "✓", "warning": "!", "error": "×"}.get(level, "●"))
        icon_color = {"success": C["green"], "warning": C["yellow"], "error": C["danger"]}.get(level, C["cyan"])
        self.icon.setStyleSheet(f"color:{icon_color}")
        self.message.setText(str(message))
        self.adjustSize()
        self.resize(min(460, max(300, self.sizeHint().width())), self.sizeHint().height())
        self.reposition()
        self.show()
        self.raise_()
        self.animation.stop()
        # Una animación de salida conecta ``finished`` con ``hide``. Esa
        # conexión debe retirarse antes de reutilizar el mismo objeto para
        # evitar que el toast nuevo desaparezca al terminar su fade-in.
        try:
            self.animation.finished.disconnect(self.hide)
        except (RuntimeError, TypeError):
            pass
        self.animation.setStartValue(float(self.opacity.opacity()))
        self.animation.setEndValue(1.0)
        self.animation.start()
        self.hide_timer.start(max(1200, int(duration)))

    def hide_animated(self) -> None:
        if not self.isVisible():
            return
        self.hide_timer.stop()
        self.animation.stop()
        self.animation.setStartValue(float(self.opacity.opacity()))
        self.animation.setEndValue(0.0)
        try:
            self.animation.finished.disconnect(self.hide)
        except (RuntimeError, TypeError):
            pass
        self.animation.finished.connect(self.hide)
        self.animation.start()

    def reposition(self) -> None:
        parent = self.parentWidget()
        if parent:
            self.move(max(18, parent.width() - self.width() - 24), 96)


class MouseCaptureOverlay(QFrame):
    """Cuenta regresiva grande que no roba el foco al juego ni bloquea clics."""

    def __init__(self, owner: Optional[QWidget] = None) -> None:
        flags = (
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        transparent_input = getattr(Qt.WindowType, "WindowTransparentForInput", None)
        if transparent_input is not None:
            flags |= transparent_input
        super().__init__(owner, flags)
        self.setObjectName("mouseCaptureOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMinimumSize(560, 270)
        self.setMaximumWidth(680)
        self._mode = ""
        self._kind = ""
        self._last_second = -1

        self.setStyleSheet(
            f"""
            QFrame#mouseCaptureOverlay {{
                background: rgba(7, 11, 23, 242);
                border: 2px solid {C['accent2']};
                border-radius: 24px;
            }}
            QLabel#mouseCaptureTitle {{
                color: {C['text']};
                font-size: 24px;
                font-weight: 800;
                letter-spacing: 1px;
            }}
            QLabel#mouseCaptureCount {{
                color: {C['cyan']};
                font-size: 76px;
                font-weight: 900;
            }}
            QLabel#mouseCaptureDetail {{
                color: {C['muted']};
                font-size: 16px;
            }}
            QLabel#mouseCaptureHotkey {{
                color: {C['text']};
                background: rgba(123, 63, 242, 75);
                border: 1px solid rgba(198, 63, 244, 155);
                border-radius: 12px;
                padding: 10px 16px;
                font-size: 20px;
                font-weight: 800;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(9)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title = QLabel()
        self.title.setObjectName("mouseCaptureTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)

        self.count = QLabel()
        self.count.setObjectName("mouseCaptureCount")
        self.count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.count)

        self.detail = QLabel()
        self.detail.setObjectName("mouseCaptureDetail")
        self.detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)

        self.hotkey = QLabel("CTRL + M  ·  ACTIVAR / DESACTIVAR EL MOUSE")
        self.hotkey.setObjectName("mouseCaptureHotkey")
        self.hotkey.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hotkey)

        # También se marca cada hijo como transparente: evita que una QLabel
        # capture el clic aunque el contenedor ya sea click-through.
        for widget in (self.title, self.count, self.detail, self.hotkey):
            widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)
        self.hide()

    def show_countdown(self, kind: str, remaining_seconds: float) -> None:
        import math

        second = max(1, int(math.ceil(float(remaining_seconds or 0.0))))
        normalized_kind = str(kind or "Mouse")
        if (
            self._mode == "countdown"
            and self._kind == normalized_kind
            and self._last_second == second
            and self.isVisible()
        ):
            return
        self._mode = "countdown"
        self._kind = normalized_kind
        self._last_second = second
        self.hide_timer.stop()
        self.title.setText(f"{normalized_kind.upper()} SE ACTIVA EN")
        self.count.setText(str(second))
        self.detail.setText("Abre tu juego o aplicación ahora. El cursor sigue libre durante la cuenta.")
        self._show_without_focus()

    def show_state(self, kind: str, active: bool) -> None:
        normalized_kind = str(kind or "Mouse")
        self._mode = "state"
        self._kind = normalized_kind
        self._last_second = -1
        self.title.setText("MOUSE ACTIVADO" if active else "MOUSE LIBERADO")
        self.count.setText("ON" if active else "OFF")
        self.detail.setText(
            f"{normalized_kind} está listo para jugar."
            if active
            else f"{normalized_kind} está apagado temporalmente y el cursor vuelve a ser normal."
        )
        self._show_without_focus()
        self.hide_timer.start(3200)

    def cancel_countdown(self) -> None:
        if self._mode == "countdown":
            self.hide_timer.stop()
            self.hide()
            self._mode = ""
            self._kind = ""
            self._last_second = -1

    def _show_without_focus(self) -> None:
        self.adjustSize()
        self.resize(max(560, self.sizeHint().width()), max(270, self.sizeHint().height()))
        self._reposition_to_active_screen()
        self.show()
        self._apply_native_click_through()
        self.raise_()

    def _apply_native_click_through(self) -> None:
        """Refuerza el click-through a nivel de ventana en Windows."""
        if sys.platform != "win32":
            return
        try:
            import ctypes

            user32 = ctypes.WinDLL("user32", use_last_error=True)
            pointer_bits = ctypes.sizeof(ctypes.c_void_p) * 8
            get_style = getattr(
                user32,
                "GetWindowLongPtrW" if pointer_bits == 64 else "GetWindowLongW",
            )
            set_style = getattr(
                user32,
                "SetWindowLongPtrW" if pointer_bits == 64 else "SetWindowLongW",
            )
            long_type = ctypes.c_ssize_t if pointer_bits == 64 else ctypes.c_long
            get_style.argtypes = [ctypes.c_void_p, ctypes.c_int]
            get_style.restype = long_type
            set_style.argtypes = [ctypes.c_void_p, ctypes.c_int, long_type]
            set_style.restype = long_type

            hwnd = ctypes.c_void_p(int(self.winId()))
            GWL_EXSTYLE = -20
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_LAYERED = 0x00080000
            WS_EX_NOACTIVATE = 0x08000000
            current = int(get_style(hwnd, GWL_EXSTYLE))
            wanted = current | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE
            if wanted != current:
                set_style(hwnd, GWL_EXSTYLE, long_type(wanted))
        except Exception:
            # Los atributos Qt siguen ofreciendo click-through en otros backends.
            pass

    def nativeEvent(self, event_type, message):
        """Devuelve HTTRANSPARENT para que Windows entregue el clic al juego."""
        if sys.platform == "win32":
            try:
                from ctypes import wintypes

                WM_NCHITTEST = 0x0084
                HTTRANSPARENT = -1
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_NCHITTEST:
                    return True, HTTRANSPARENT
            except Exception:
                pass
        return super().nativeEvent(event_type, message)

    def _reposition_to_active_screen(self) -> None:
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        x = area.x() + (area.width() - self.width()) // 2
        y = area.y() + max(36, int(area.height() * 0.12))
        self.move(x, y)
