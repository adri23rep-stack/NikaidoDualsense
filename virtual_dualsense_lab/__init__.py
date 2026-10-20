"""Nikaido DualSense 3.0.0 Alpha 2.3.0 — Microsoft Signing Readiness."""

from .backend import (
    BackendCapabilities,
    BackendError,
    BackendSnapshot,
    BackendStateError,
    BackendStatus,
    BackendUnavailableError,
    StaleStateError,
)
from .diagnostics import DiagnosticReport, collect_diagnostics
from .hid_report import (
    GENERIC_GAMEPAD_REPORT_DESCRIPTOR,
    REPORT_ID,
    REPORT_SIZE,
    decode_input_report,
    encode_input_report,
)
from .lab import VirtualDualSenseLab, run_alpha1_simulation
from .model import BUTTON_ORDER, Button, ControllerState, DPad, Stick
from .native import NativeHidBackend
from .simulated import SimulatedDualSenseBackend
from .version import LAB_NAME, LAB_RELEASE, LAB_VERSION, PRODUCT_NAME

__all__ = [
    "BUTTON_ORDER",
    "BackendCapabilities",
    "BackendError",
    "BackendSnapshot",
    "BackendStateError",
    "BackendStatus",
    "BackendUnavailableError",
    "Button",
    "ControllerState",
    "DPad",
    "DiagnosticReport",
    "GENERIC_GAMEPAD_REPORT_DESCRIPTOR",
    "LAB_NAME",
    "LAB_RELEASE",
    "LAB_VERSION",
    "NativeHidBackend",
    "PRODUCT_NAME",
    "REPORT_ID",
    "REPORT_SIZE",
    "SimulatedDualSenseBackend",
    "StaleStateError",
    "Stick",
    "VirtualDualSenseLab",
    "collect_diagnostics",
    "decode_input_report",
    "encode_input_report",
    "run_alpha1_simulation",
]
