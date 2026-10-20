"""Reporte HID genérico de laboratorio.

El descriptor y el codec son deliberadamente neutrales. No contienen VID/PID
de Sony ni pretenden implementar el protocolo USB/Bluetooth de DualSense.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from .model import (
    BUTTON_ORDER,
    DPAD_HAT_CODES,
    HAT_CODE_DPAD,
    ControllerState,
    Stick,
)

REPORT_ID = 1
REPORT_SIZE = 16
_REPORT = struct.Struct("<BHBhhhhHH")

# Generic Desktop / Game Pad, 14 botones, hat switch, dos sticks y dos
# gatillos analógicos. Alpha 2.3.0 lo replica en el driver fuente para revisión,
# pero el paquete todavía no lo publica ante Windows.
GENERIC_GAMEPAD_REPORT_DESCRIPTOR = bytes(
    [
        0x05, 0x01,  # Usage Page (Generic Desktop)
        0x09, 0x05,  # Usage (Game Pad)
        0xA1, 0x01,  # Collection (Application)
        0x85, REPORT_ID,
        0x05, 0x09,  # Usage Page (Button)
        0x19, 0x01,
        0x29, len(BUTTON_ORDER),
        0x15, 0x00,
        0x25, 0x01,
        0x75, 0x01,
        0x95, len(BUTTON_ORDER),
        0x81, 0x02,
        0x75, 0x01,  # Padding to 16 bits
        0x95, 16 - len(BUTTON_ORDER),
        0x81, 0x03,
        0x05, 0x01,
        0x09, 0x39,  # Hat switch
        0x15, 0x00,
        0x25, 0x07,
        0x35, 0x00,
        0x46, 0x3B, 0x01,
        0x65, 0x14,
        0x75, 0x04,
        0x95, 0x01,
        0x81, 0x42,  # Data, Variable, Absolute, Null state
        0x65, 0x00,
        0x75, 0x04,
        0x95, 0x01,
        0x81, 0x03,
        0x09, 0x30,  # X
        0x09, 0x31,  # Y
        0x09, 0x33,  # Rx
        0x09, 0x34,  # Ry
        0x16, 0x00, 0x80,
        0x26, 0xFF, 0x7F,
        0x75, 0x10,
        0x95, 0x04,
        0x81, 0x02,
        0x09, 0x32,  # Z (L2)
        0x09, 0x35,  # Rz (R2)
        0x15, 0x00,
        0x27, 0xFF, 0xFF, 0x00, 0x00,
        0x75, 0x10,
        0x95, 0x02,
        0x81, 0x02,
        0xC0,
    ]
)


def _axis_to_i16(value: float) -> int:
    scale = 32767 if value >= 0 else 32768
    return max(-32768, min(32767, int(round(value * scale))))


def _i16_to_axis(value: int) -> float:
    scale = 32767 if value >= 0 else 32768
    return float(value) / scale


def _trigger_to_u16(value: float) -> int:
    return max(0, min(65535, int(round(value * 65535))))


def _u16_to_trigger(value: int) -> float:
    return float(value) / 65535.0


def encode_input_report(state: ControllerState) -> bytes:
    if not isinstance(state, ControllerState):
        raise TypeError("state debe ser ControllerState")
    buttons = 0
    for bit, button in enumerate(BUTTON_ORDER):
        if button in state.buttons:
            buttons |= 1 << bit
    report = _REPORT.pack(
        REPORT_ID,
        buttons,
        DPAD_HAT_CODES[state.dpad],
        _axis_to_i16(state.left_stick.x),
        _axis_to_i16(state.left_stick.y),
        _axis_to_i16(state.right_stick.x),
        _axis_to_i16(state.right_stick.y),
        _trigger_to_u16(state.left_trigger),
        _trigger_to_u16(state.right_trigger),
    )
    if len(report) != REPORT_SIZE:  # pragma: no cover - contrato estructural
        raise AssertionError("El tamaño del reporte interno cambió")
    return report


def decode_input_report(
    report: bytes | bytearray | memoryview,
    *,
    sequence: int = 0,
) -> ControllerState:
    payload = bytes(report)
    if len(payload) != REPORT_SIZE:
        raise ValueError(f"El reporte debe medir {REPORT_SIZE} bytes")
    (
        report_id,
        button_bits,
        hat,
        left_x,
        left_y,
        right_x,
        right_y,
        left_trigger,
        right_trigger,
    ) = _REPORT.unpack(payload)
    if report_id != REPORT_ID:
        raise ValueError(f"Report ID desconocido: {report_id}")
    if button_bits >> len(BUTTON_ORDER):
        raise ValueError("El reporte contiene bits de botón reservados")
    if hat not in HAT_CODE_DPAD:
        raise ValueError(f"Hat switch inválido: {hat}")
    buttons = frozenset(
        button for bit, button in enumerate(BUTTON_ORDER) if button_bits & (1 << bit)
    )
    return ControllerState(
        buttons=buttons,
        dpad=HAT_CODE_DPAD[hat],
        left_stick=Stick(_i16_to_axis(left_x), _i16_to_axis(left_y)),
        right_stick=Stick(_i16_to_axis(right_x), _i16_to_axis(right_y)),
        left_trigger=_u16_to_trigger(left_trigger),
        right_trigger=_u16_to_trigger(right_trigger),
        sequence=sequence,
    )


@dataclass(frozen=True, slots=True)
class ReportContract:
    report_id: int = REPORT_ID
    input_report_bytes: int = REPORT_SIZE
    button_count: int = len(BUTTON_ORDER)
    dpad_directions: int = 8
    stick_axes: int = 4
    analog_triggers: int = 2
    reports_to_windows: bool = False
    dualsense_protocol: bool = False

    def to_dict(self) -> dict[str, int | bool]:
        return {
            "report_id": self.report_id,
            "input_report_bytes": self.input_report_bytes,
            "button_count": self.button_count,
            "dpad_directions": self.dpad_directions,
            "stick_axes": self.stick_axes,
            "analog_triggers": self.analog_triggers,
            "reports_to_windows": self.reports_to_windows,
            "dualsense_protocol": self.dualsense_protocol,
        }
