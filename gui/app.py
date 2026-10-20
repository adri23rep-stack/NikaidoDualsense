"""Compatibilidad para integraciones que todavía importan ``gui.app``.

La interfaz oficial de Nikaido 2.0 es la implementación Qt de
:mod:`gui.modern_app`. Este módulo evita romper imports antiguos sin mantener
dos interfaces activas en paralelo.
"""

from .modern_app import DualSenseGUI, NikaidoWindow

__all__ = ["DualSenseGUI", "NikaidoWindow"]
