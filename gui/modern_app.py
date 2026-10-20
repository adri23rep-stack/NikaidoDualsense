# ruff: noqa: F401
"""Compatibilidad pública de la interfaz moderna de Nikaido.
La implementación fue dividida en componentes, páginas y una ventana
coordinadora. Este módulo conserva las importaciones históricas para plugins,
``main.py`` y código externo.
"""

from .components import (
    AppearancePreview, BackendBridge, BackgroundRoot, CommandPalette,
    ControllerVisual, KeyCaptureButton, LatencyGraph, PageLoadError,
    ResponseCurveEditor, ScrollPage, SidebarNavButton, SliderRow, StickScope,
    TitleBar,
)
from .main_window import DualSenseGUI, NikaidoWindow
from .pages.dashboard import DashboardPage
from .pages.device import AudioPage, LightsPage, VibrationPage
from .pages.triggers import AdaptiveTriggersPage, TriggerCurveEditor
from .pages.input import CalibrationPage, GyroPage, InputStudioPage
from .pages.macros import (
    MacroComboDialog, MacroEditorDialog, MacroStepDialog, MacroStickPad,
    MacrosPage,
)
from .pages.nexus import AdvancedBindingDialog, MapperPage, NexusControllerView
from .profile_editor import ProfileEditorDialog, profile_image_widget
from .pages.profiles import ProfilesPage
from .pages.settings import SettingsPage, WelcomeWizard
from .pages.system import (
    AutoProfilesPage, CompatibilityPage, EmulationPage, MonitorPage, ToolsPage,
)

__all__ = [name for name in globals() if not name.startswith("_")]
