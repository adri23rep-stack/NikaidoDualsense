"""Pruebas de la separación arquitectónica de Nikaido 2.6."""

from __future__ import annotations

import ast
from pathlib import Path

import build
from nikaido_version import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui"
IMPLEMENTATION_FILES = [
    GUI / "components.py",
    GUI / "curve_editor.py",
    GUI / "main_window.py",
    GUI / "profile_editor.py",
    GUI / "profile_gallery.py",
    GUI / "profile_visuals.py",
    GUI / "ui_common.py",
    *sorted((GUI / "pages").glob("*.py")),
]


def _classes(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [node.name for node in tree.body if isinstance(node, ast.ClassDef)]


def test_modern_app_is_a_small_compatibility_facade():
    path = GUI / "modern_app.py"
    source = path.read_text(encoding="utf-8")
    assert len(source.splitlines()) <= 80
    assert not _classes(path)
    assert "from .main_window import DualSenseGUI, NikaidoWindow" in source
    assert "__all__" in source


def test_window_and_pages_live_outside_the_public_facade():
    assert _classes(GUI / "main_window.py") == ["NikaidoWindow", "DualSenseGUI"]
    expected = {
        "dashboard.py": {"DashboardPage"},
        "profiles.py": {"ProfilesPage"},
        "nexus.py": {"AdvancedBindingDialog", "NexusControllerView", "MapperPage"},
        "input.py": {"InputStudioPage", "CalibrationPage", "GyroPage"},
        "macros.py": {"MacroStickPad", "MacroStepDialog", "MacroComboDialog", "MacroEditorDialog", "MacrosPage"},
        "device.py": {"LightsPage", "VibrationPage", "AudioPage"},
        "triggers.py": {"TriggerCurveEditor", "AdaptiveTriggersPage"},
        "system.py": {"AutoProfilesPage", "CompatibilityPage", "MonitorPage", "ToolsPage"},
        "emulation.py": {"EmulationPage"},
        "settings.py": {"WelcomeWizard", "SettingsPage"},
    }
    for filename, names in expected.items():
        assert names <= set(_classes(GUI / "pages" / filename))
    assert "ProfileEditorDialog" in _classes(GUI / "profile_editor.py")
    assert {"ProfileCoverWidget", "ProfileGalleryCard", "ProfileFeatureRow", "ProfileDetailPanel"} <= set(_classes(GUI / "profile_gallery.py"))


def test_implementation_has_no_duplicate_top_level_classes():
    owners: dict[str, Path] = {}
    for path in IMPLEMENTATION_FILES:
        for name in _classes(path):
            assert name not in owners, f"{name} duplicada en {owners[name]} y {path}"
            owners[name] = path
    assert len(owners) >= 37


def test_modules_stay_within_reviewable_size_limits():
    limits = {
        GUI / "components.py": 1200,
        GUI / "main_window.py": 1500,
        GUI / "curve_editor.py": 320,
    }
    for path in (GUI / "pages").glob("*.py"):
        limits[path] = 2000
    for path, maximum in limits.items():
        assert len(path.read_text(encoding="utf-8").splitlines()) <= maximum


def test_runtime_modules_do_not_import_the_compatibility_facade_back():
    for path in IMPLEMENTATION_FILES:
        source = path.read_text(encoding="utf-8")
        assert "import gui.modern_app" not in source
        assert "from gui.modern_app" not in source
        assert "from .modern_app" not in source
        assert "from ..modern_app" not in source


def test_pyinstaller_explicitly_collects_the_modular_ui():
    expected = {
        "gui.modern_app",
        "gui.main_window",
        "gui.components",
        "gui.curve_editor",
        "gui.i18n",
        "gui.ui_common",
        "gui.design_system",
        "gui.pages.dashboard",
        "gui.pages.profiles",
        "gui.profile_editor",
        "gui.profile_gallery",
        "gui.profile_visuals",
        "gui.pages.nexus",
        "gui.pages.input",
        "gui.pages.macros",
        "gui.pages.device",
        "gui.pages.triggers",
        "gui.pages.system",
        "gui.pages.settings",
    }
    assert expected <= set(build.UI_RUNTIME_MODULES)
    source = Path(build.__file__).read_text(encoding="utf-8")
    assert "*UI_RUNTIME_MODULES" in source


def test_architecture_release_version_is_consistent():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    installer = (ROOT / "installer" / "Nikaido.iss").read_text(encoding="utf-8")
    assert APP_VERSION == "2.9.8.13"
    assert f'version = "{APP_VERSION}"' in pyproject
    assert f'#define MyAppVersion "{APP_VERSION}"' in installer
