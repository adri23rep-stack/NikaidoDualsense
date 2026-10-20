# ruff: noqa: F401
"""Dependencias visuales compartidas por la interfaz Qt de Nikaido.
Este módulo centraliza imports y utilidades sin contener pantallas. Mantenerlo
pequeño evita duplicar el bloque de PySide6 en cada página extraída.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from nikaido_version import APP_VERSION
from src.edit_history import SnapshotHistory
from src.security_utils import read_json_file_limited
from .design_system import (
    ACCENT_PALETTES, APPEARANCE_PRESETS, C, DEFAULT_APPEARANCE,
    MouseCaptureOverlay, ToastOverlay, appearance_background_signature, appearance_style_signature,
    apply_runtime_palette, build_app_qss, button, card, clear_layout, configure_tabs, label,
    normalize_appearance, resource_path,
)

from PySide6.QtCore import (
    QEasingCurve, QObject, QPoint, QPointF, QPropertyAnimation, QRectF, QSize,
    Qt, QTimer, QVariantAnimation, Signal,
)
from PySide6.QtGui import (
    QColor, QCloseEvent, QFont, QIcon, QImageReader, QMouseEvent, QPainter, QPixmap,
    QPixmapCache, QPainterPath, QPen, QKeySequence, QRadialGradient, QLinearGradient, QBrush, QShortcut,
)
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QCheckBox, QColorDialog, QComboBox,
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame,
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QLabel, QInputDialog,
    QLayout, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu,
    QMessageBox, QPushButton, QProgressBar, QPlainTextEdit, QScrollArea, QSizeGrip, QSlider,
    QSpinBox, QDoubleSpinBox, QStackedWidget, QTabBar, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

try:
    import psutil
except ImportError:  # pragma: no cover - dependencia normal del proyecto
    psutil = None
