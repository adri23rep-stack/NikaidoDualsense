"""Regresiones del arranque del Dashboard con iconos de perfil de respaldo."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_SOURCE = (ROOT / "gui" / "pages" / "dashboard.py").read_text(encoding="utf-8")


def test_dashboard_imports_the_profile_fallback_from_its_owner_module():
    assert "from ..profile_visuals import fallback_glyph" in DASHBOARD_SOURCE
    assert "fallback_glyph(str(profile_id or \"\"), profile)" in DASHBOARD_SOURCE


def _qt_modules():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QLabel

    return QApplication, QLabel


class _Profile:
    name = "Perfil sin imagen"
    category = "Shooter"
    icon = "theme:fps"
    icon_path = ""
    image_path = ""


def test_dashboard_fallback_renders_repeatedly_without_a_custom_icon():
    QApplication, QLabel = _qt_modules()
    app = QApplication.instance() or QApplication([])

    from gui.pages.dashboard import DashboardPage
    from gui.profile_visuals import fallback_glyph

    class Holder:
        profile_icon = QLabel()

    holder = Holder()
    profile = _Profile()
    expected = fallback_glyph("assault_rifle", profile)

    # Dos llamadas consecutivas reproducen el escenario del segundo arranque:
    # la vista se reconstruye sin una imagen personalizada disponible.
    DashboardPage._set_profile_image(holder, "assault_rifle", profile)
    assert holder.profile_icon.text() == expected
    DashboardPage._set_profile_image(holder, "assault_rifle", profile)
    assert holder.profile_icon.text() == expected
    assert holder.profile_icon.pixmap().isNull()
    holder.profile_icon.deleteLater()
    app.processEvents()


def test_dashboard_fallback_survives_a_missing_icon_file(tmp_path):
    QApplication, QLabel = _qt_modules()
    app = QApplication.instance() or QApplication([])

    from gui.pages.dashboard import DashboardPage
    from gui.profile_visuals import fallback_glyph

    class Holder:
        profile_icon = QLabel()

    profile = _Profile()
    profile.icon_path = str(tmp_path / "no_existe.png")
    profile.image_path = profile.icon_path
    holder = Holder()

    DashboardPage._set_profile_image(holder, "custom_profile", profile)
    assert holder.profile_icon.text() == fallback_glyph("custom_profile", profile)
    holder.profile_icon.deleteLater()
    app.processEvents()
