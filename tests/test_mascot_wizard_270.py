"""Regresiones de la mascota y el wizard de Nikaido 2.7.0."""

from __future__ import annotations

import ast
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "gui" / "components.py"
SETTINGS = ROOT / "gui" / "pages" / "settings.py"
DESIGN = ROOT / "gui" / "design_system.py"
MASCOT = ROOT / "assets" / "mascot"


def _class_source(path: Path, name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(
        item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == name
    )
    return ast.get_source_segment(source, node) or ""


def test_mascot_panel_is_reusable_and_has_full_and_compact_poses():
    source = _class_source(COMPONENTS, "MascotPanel")
    assert '"greeting": "assets/mascot/poses_a/greeting.png"' in source
    assert '"compact_error_critical"' in source
    assert "def set_scene" in source
    assert "SmoothTransformation" in source


def test_wizard_uses_a_persistent_mascot_panel_and_mandatory_language_scene():
    source = _class_source(SETTINGS, "WelcomeWizard")
    assert "MASCOT_SCENES = (" in source
    assert "self.mascot_panel = MascotPanel()" in source
    assert "self._update_mascot_scene()" in source
    assert '"celebrating"' in source
    version_source = (ROOT / "nikaido_version.py").read_text(encoding="utf-8")
    assert "ONBOARDING_VERSION = 6" in version_source
    assert "from nikaido_version import ONBOARDING_VERSION" in SETTINGS.read_text(encoding="utf-8")


def test_connection_step_has_live_status_and_manual_search():
    source = _class_source(SETTINGS, "WelcomeWizard")
    assert 'setObjectName("wizardConnectionStatus")' in source
    assert 'button("Buscar ahora", self._request_connection' in source
    assert "manager.request_connect()" in source
    assert '"✓ DualSense conectado"' in source
    assert "battery_level" in source


def test_mascot_styles_are_part_of_the_shared_theme():
    source = DESIGN.read_text(encoding="utf-8")
    assert "QFrame#mascotPanel" in source
    assert "QFrame#mascotBubble" in source
    assert "QLabel#mascotMessage" in source


def test_all_mascot_assets_are_real_transparent_pngs():
    sprites = sorted(MASCOT.glob("poses_*/*.png"))
    assert len(sprites) == 20
    for path in sprites:
        with Image.open(path) as image:
            assert image.mode == "RGBA", path
            alpha = image.getchannel("A")
            minimum, maximum = alpha.getextrema()
            assert minimum == 0 and maximum == 255, path
            assert image.width <= 720 and image.height <= 900, path
