"""Modelo portable de entrada para el laboratorio virtual.

No representa el protocolo propietario de un DualSense físico. Es un contrato
interno, estricto e inmutable que puede usar el simulador y, en una fase futura,
un backend nativo revisado y firmado.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, FrozenSet, Iterable


class Button(str, Enum):
    CROSS = "cross"
    CIRCLE = "circle"
    SQUARE = "square"
    TRIANGLE = "triangle"
    L1 = "l1"
    R1 = "r1"
    L2_BUTTON = "l2_button"
    R2_BUTTON = "r2_button"
    L3 = "l3"
    R3 = "r3"
    OPTIONS = "options"
    CREATE = "create"
    PS = "ps"
    TOUCHPAD = "touchpad"


BUTTON_ORDER = tuple(Button)


class DPad(str, Enum):
    UP = "up"
    UP_RIGHT = "up_right"
    RIGHT = "right"
    DOWN_RIGHT = "down_right"
    DOWN = "down"
    DOWN_LEFT = "down_left"
    LEFT = "left"
    UP_LEFT = "up_left"
    CENTER = "center"


DPAD_HAT_CODES = {
    DPad.UP: 0,
    DPad.UP_RIGHT: 1,
    DPad.RIGHT: 2,
    DPad.DOWN_RIGHT: 3,
    DPad.DOWN: 4,
    DPad.DOWN_LEFT: 5,
    DPad.LEFT: 6,
    DPad.UP_LEFT: 7,
    DPad.CENTER: 8,
}
HAT_CODE_DPAD = {value: key for key, value in DPAD_HAT_CODES.items()}


def _finite_float(value: Any, *, name: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} debe ser numérico, no booleano")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{name} debe ser numérico") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} debe ser finito")
    if number < minimum or number > maximum:
        raise ValueError(f"{name} debe estar entre {minimum} y {maximum}")
    return number


def coerce_button(value: Button | str) -> Button:
    if isinstance(value, Button):
        return value
    normalized = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "touchpad_click": "touchpad",
        "touch_click": "touchpad",
        "share": "create",
        "start": "options",
        "home": "ps",
        "l2": "l2_button",
        "r2": "r2_button",
    }
    normalized = aliases.get(normalized, normalized)
    try:
        return Button(normalized)
    except ValueError as exc:
        raise ValueError(f"Botón desconocido: {value!r}") from exc


def coerce_buttons(values: Iterable[Button | str] | None) -> FrozenSet[Button]:
    if values is None:
        return frozenset()
    if isinstance(values, (str, bytes)):
        raise TypeError("buttons debe ser una colección de botones")
    return frozenset(coerce_button(value) for value in values)


def coerce_dpad(value: DPad | str) -> DPad:
    if isinstance(value, DPad):
        return value
    normalized = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "neutral": "center",
        "none": "center",
        "centro": "center",
        "arriba": "up",
        "abajo": "down",
        "izquierda": "left",
        "derecha": "right",
    }
    normalized = aliases.get(normalized, normalized)
    try:
        return DPad(normalized)
    except ValueError as exc:
        raise ValueError(f"Dirección D-pad desconocida: {value!r}") from exc


@dataclass(frozen=True, slots=True)
class Stick:
    x: float = 0.0
    y: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "x",
            _finite_float(self.x, name="stick.x", minimum=-1.0, maximum=1.0),
        )
        object.__setattr__(
            self,
            "y",
            _finite_float(self.y, name="stick.y", minimum=-1.0, maximum=1.0),
        )


def _coerce_stick(value: Stick | Iterable[Any], *, name: str) -> Stick:
    if isinstance(value, Stick):
        return value
    if isinstance(value, (str, bytes)):
        raise TypeError(f"{name} debe contener dos ejes")
    try:
        axes = tuple(value)
    except TypeError as exc:
        raise TypeError(f"{name} debe contener dos ejes") from exc
    if len(axes) != 2:
        raise TypeError(f"{name} debe contener dos ejes")
    return Stick(*axes)


@dataclass(frozen=True, slots=True)
class ControllerState:
    """Estado completo y validado de los controles cubiertos por Alpha 1."""

    buttons: FrozenSet[Button] = field(default_factory=frozenset)
    dpad: DPad = DPad.CENTER
    left_stick: Stick = field(default_factory=Stick)
    right_stick: Stick = field(default_factory=Stick)
    left_trigger: float = 0.0
    right_trigger: float = 0.0
    sequence: int = 0
    timestamp_ns: int = field(default_factory=time.monotonic_ns)

    def __post_init__(self) -> None:
        object.__setattr__(self, "buttons", coerce_buttons(self.buttons))
        object.__setattr__(self, "dpad", coerce_dpad(self.dpad))
        object.__setattr__(
            self,
            "left_stick",
            _coerce_stick(self.left_stick, name="left_stick"),
        )
        object.__setattr__(
            self,
            "right_stick",
            _coerce_stick(self.right_stick, name="right_stick"),
        )
        object.__setattr__(
            self,
            "left_trigger",
            _finite_float(
                self.left_trigger,
                name="left_trigger",
                minimum=0.0,
                maximum=1.0,
            ),
        )
        object.__setattr__(
            self,
            "right_trigger",
            _finite_float(
                self.right_trigger,
                name="right_trigger",
                minimum=0.0,
                maximum=1.0,
            ),
        )
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise TypeError("sequence debe ser un entero")
        if self.sequence < 0:
            raise ValueError("sequence no puede ser negativa")
        if isinstance(self.timestamp_ns, bool) or not isinstance(self.timestamp_ns, int):
            raise TypeError("timestamp_ns debe ser un entero")
        if self.timestamp_ns <= 0:
            raise ValueError("timestamp_ns debe ser positivo")

    @classmethod
    def neutral(cls, *, sequence: int = 0) -> "ControllerState":
        return cls(sequence=sequence)

    def updated(self, **changes: Any) -> "ControllerState":
        changes.setdefault("timestamp_ns", time.monotonic_ns())
        return replace(self, **changes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "buttons": [button.value for button in BUTTON_ORDER if button in self.buttons],
            "dpad": self.dpad.value,
            "left_stick": {"x": self.left_stick.x, "y": self.left_stick.y},
            "right_stick": {"x": self.right_stick.x, "y": self.right_stick.y},
            "left_trigger": self.left_trigger,
            "right_trigger": self.right_trigger,
            "sequence": self.sequence,
            "timestamp_ns": self.timestamp_ns,
        }
