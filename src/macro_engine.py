"""Motor avanzado de macros para Nikaido DualSense.

Permite grabar y editar secuencias de botones, palancas y gatillos analógicos.
Las macros pueden activarse manualmente, con un botón, un combo de botones o
una dirección de palanca, y limitarse a perfiles específicos.
"""

from __future__ import annotations

import logging
import math
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

MACRO_BUTTONS = [
    "cross",
    "circle",
    "square",
    "triangle",
    "L1",
    "R1",
    "L2_btn",
    "R2_btn",
    "L3",
    "R3",
    "create",
    "options",
    "ps",
    "touchpad",
    "dpad_up",
    "dpad_down",
    "dpad_left",
    "dpad_right",
]

BUTTON_LABELS = {
    "cross": "Cross (X)",
    "circle": "Circle (O)",
    "square": "Square",
    "triangle": "Triangle",
    "L1": "L1",
    "R1": "R1",
    "L2_btn": "L2 digital",
    "R2_btn": "R2 digital",
    "L3": "L3 (clic palanca izquierda)",
    "R3": "R3 (clic palanca derecha)",
    "create": "Create / Share",
    "options": "Options / Start",
    "ps": "PS / Guide",
    "touchpad": "Clic touchpad",
    "dpad_up": "D-Pad arriba",
    "dpad_down": "D-Pad abajo",
    "dpad_left": "D-Pad izquierda",
    "dpad_right": "D-Pad derecha",
}

STICK_LABELS = {"left": "Palanca izquierda", "right": "Palanca derecha"}
DIRECTION_LABELS = {
    "up": "Arriba",
    "down": "Abajo",
    "left": "Izquierda",
    "right": "Derecha",
    "up_left": "Arriba + izquierda",
    "up_right": "Arriba + derecha",
    "down_left": "Abajo + izquierda",
    "down_right": "Abajo + derecha",
}

MAX_MACRO_STEPS = 600
MAX_LOADED_MACROS = 512
MAX_MACRO_PROFILE_IDS = 128


class StepType(Enum):
    TAP = "tap"
    PRESS = "press"
    RELEASE = "release"
    WAIT = "wait"
    STICK = "stick"
    TRIGGER = "trigger"


class TriggerKind(Enum):
    MANUAL = "manual"
    BUTTON = "button"
    COMBO = "combo"
    STICK = "stick"
    TRIGGER = "trigger"


class TriggerEdge(Enum):
    PRESS = "press"
    RELEASE = "release"
    WHILE_HELD = "while_held"


def _clamp_int(value: Any, minimum: int, maximum: int, fallback: int) -> int:
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError, OverflowError):
        return fallback


def _clamp_float(value: Any, minimum: float, maximum: float, fallback: float) -> float:
    try:
        return max(minimum, min(maximum, float(value)))
    except (TypeError, ValueError, OverflowError):
        return fallback


def _clean_buttons(values: Any) -> List[str]:
    if isinstance(values, str):
        values = values.replace("+", ",").split(",")
    if not isinstance(values, (list, tuple, set)):
        return []
    result: List[str] = []
    for value in values:
        name = str(value).strip()
        if name in MACRO_BUTTONS and name not in result:
            result.append(name)
    return result


@dataclass
class MacroTrigger:
    kind: TriggerKind = TriggerKind.MANUAL
    buttons: List[str] = field(default_factory=list)
    stick: str = "left"
    direction: str = "up"
    analog_trigger: str = "right"
    threshold: float = 0.65
    edge: TriggerEdge = TriggerEdge.PRESS

    def to_dict(self) -> dict:
        return {
            "kind": self.kind.value,
            "buttons": list(self.buttons),
            "stick": self.stick,
            "direction": self.direction,
            "analog_trigger": self.analog_trigger,
            "threshold": round(float(self.threshold), 3),
            "edge": self.edge.value,
        }

    @classmethod
    def from_dict(cls, data: Any, legacy_button: Optional[str] = None) -> "MacroTrigger":
        if not isinstance(data, dict):
            if legacy_button in MACRO_BUTTONS:
                return cls(kind=TriggerKind.BUTTON, buttons=[legacy_button])
            return cls()
        if "kind" not in data and legacy_button in MACRO_BUTTONS:
            return cls(kind=TriggerKind.BUTTON, buttons=[legacy_button])
        try:
            kind = TriggerKind(str(data.get("kind", "manual")))
        except ValueError:
            kind = TriggerKind.MANUAL
        buttons = _clean_buttons(data.get("buttons", []))
        if kind == TriggerKind.BUTTON:
            buttons = buttons[:1]
        if kind in (TriggerKind.BUTTON, TriggerKind.COMBO) and not buttons:
            kind = TriggerKind.MANUAL
        stick = str(data.get("stick", "left"))
        if stick not in STICK_LABELS:
            stick = "left"
        direction = str(data.get("direction", "up"))
        if direction not in DIRECTION_LABELS:
            direction = "up"
        analog_trigger = str(data.get("analog_trigger", data.get("trigger", "right")))
        if analog_trigger not in ("left", "right"):
            analog_trigger = "right"
        try:
            edge = TriggerEdge(str(data.get("edge", "press")))
        except ValueError:
            edge = TriggerEdge.PRESS
        return cls(
            kind=kind,
            buttons=buttons,
            stick=stick,
            direction=direction,
            analog_trigger=analog_trigger,
            threshold=_clamp_float(data.get("threshold", 0.65), 0.10, 0.95, 0.65),
            edge=edge,
        )

    def describe(self) -> str:
        if self.kind == TriggerKind.MANUAL:
            return "Solo manual"
        if self.kind == TriggerKind.BUTTON:
            base = (
                BUTTON_LABELS.get(self.buttons[0], self.buttons[0])
                if self.buttons
                else "Solo manual"
            )
        elif self.kind == TriggerKind.COMBO:
            base = " + ".join(BUTTON_LABELS.get(button, button) for button in self.buttons)
        elif self.kind == TriggerKind.STICK:
            base = f"{STICK_LABELS.get(self.stick, self.stick)} · {DIRECTION_LABELS.get(self.direction, self.direction)}"
        else:
            base = f"{'L2' if self.analog_trigger == 'left' else 'R2'} al {round(self.threshold * 100)}%"
        if self.edge == TriggerEdge.RELEASE:
            return f"{base} · al soltar"
        if self.edge == TriggerEdge.WHILE_HELD:
            return f"{base} · mientras se mantenga"
        return base


@dataclass
class MacroStep:
    type: StepType
    button: Optional[str] = None
    ms: int = 0
    after_ms: int = 0
    stick: Optional[str] = None
    x: float = 0.0
    y: float = 0.0
    trigger: Optional[str] = None
    value: int = 0

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "button": self.button,
            "ms": int(self.ms),
            "after_ms": int(self.after_ms),
            "stick": self.stick,
            "x": round(float(self.x), 4),
            "y": round(float(self.y), 4),
            "trigger": self.trigger,
            "value": int(self.value),
        }

    @staticmethod
    def from_dict(data: Any) -> "MacroStep":
        if not isinstance(data, dict):
            raise ValueError("Paso de macro inválido")
        try:
            step_type = StepType(str(data.get("type", "wait")))
        except ValueError as exc:
            raise ValueError("Tipo de paso desconocido") from exc
        button = str(data.get("button", "") or "") or None
        if button and button not in MACRO_BUTTONS:
            button = None
        stick = str(data.get("stick", "") or "") or None
        if stick not in STICK_LABELS:
            stick = None
        trigger = str(data.get("trigger", "") or "") or None
        if trigger not in ("left", "right"):
            trigger = None
        return MacroStep(
            type=step_type,
            button=button,
            ms=_clamp_int(data.get("ms", 0), 0, 60_000, 0),
            after_ms=_clamp_int(data.get("after_ms", data.get("delay_ms", 0)), 0, 60_000, 0),
            stick=stick,
            x=_clamp_float(data.get("x", 0.0), -1.0, 1.0, 0.0),
            y=_clamp_float(data.get("y", 0.0), -1.0, 1.0, 0.0),
            trigger=trigger,
            value=_clamp_int(data.get("value", 0), 0, 255, 0),
        )

    def describe(self) -> str:
        button = self.button or "Botón"
        label = BUTTON_LABELS.get(button, button)
        if self.type == StepType.TAP:
            return f"Tocar {label} durante {self.ms} ms"
        if self.type == StepType.PRESS:
            return f"Presionar {label}"
        if self.type == StepType.RELEASE:
            return f"Soltar {label}"
        if self.type == StepType.WAIT:
            return f"Esperar {self.ms} ms"
        if self.type == StepType.STICK:
            side = STICK_LABELS.get(self.stick or "", self.stick or "Palanca")
            return f"{side}: X {round(self.x * 100):+d}% · Y {round(self.y * 100):+d}%" + (
                f" durante {self.ms} ms" if self.ms else ""
            )
        side = "L2" if self.trigger == "left" else "R2"
        return f"{side} analógico al {round(self.value * 100 / 255)}%" + (
            f" durante {self.ms} ms" if self.ms else ""
        )


@dataclass
class Macro:
    id: str
    name: str
    steps: List[MacroStep] = field(default_factory=list)
    repeat: int = 1
    trigger: MacroTrigger = field(default_factory=MacroTrigger)
    profile_ids: List[str] = field(default_factory=list)
    enabled: bool = True
    cooldown_ms: int = 250
    description: str = ""

    @property
    def trigger_button(self) -> Optional[str]:
        """Compatibilidad con la interfaz y JSON anteriores."""
        if self.trigger.kind == TriggerKind.BUTTON and self.trigger.buttons:
            return self.trigger.buttons[0]
        return None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "trigger": self.trigger.to_dict(),
            "trigger_button": self.trigger_button,
            "profile_ids": list(dict.fromkeys(str(pid) for pid in self.profile_ids if str(pid))),
            "steps": [step.to_dict() for step in self.steps],
            "repeat": _clamp_int(self.repeat, 1, 50, 1),
            "enabled": bool(self.enabled),
            "cooldown_ms": _clamp_int(self.cooldown_ms, 0, 10_000, 250),
        }

    @staticmethod
    def from_dict(data: Any) -> "Macro":
        if not isinstance(data, dict):
            raise ValueError("Macro inválida")
        macro_id = str(data.get("id", "")).strip()[:120]
        if not macro_id:
            macro_id = f"macro_{uuid.uuid4().hex[:8]}"
        profiles_raw = data.get("profile_ids", data.get("profiles", []))
        if isinstance(profiles_raw, str):
            profiles_raw = [profiles_raw]
        profile_ids = []
        if isinstance(profiles_raw, (list, tuple, set)):
            profile_ids = list(
                dict.fromkeys(
                    str(value).strip()[:120] for value in profiles_raw if str(value).strip()
                )
            )[:MAX_MACRO_PROFILE_IDS]
        steps_raw = data.get("steps", [])
        if not isinstance(steps_raw, (list, tuple)):
            steps_raw = []
        steps: List[MacroStep] = []
        invalid_steps = 0
        first_invalid_reason = ""
        for step in steps_raw[:MAX_MACRO_STEPS]:
            if not isinstance(step, dict):
                invalid_steps += 1
                if not first_invalid_reason:
                    first_invalid_reason = "estructura no válida"
                continue
            try:
                steps.append(MacroStep.from_dict(step))
            except ValueError as exc:
                invalid_steps += 1
                if not first_invalid_reason:
                    first_invalid_reason = str(exc)
        if invalid_steps:
            # Un archivo manipulado puede contener cientos de pasos dañados. Un
            # solo resumen conserva el diagnóstico sin bloquear la interfaz ni
            # llenar el archivo de log con una línea por paso.
            logger.warning(
                "Macro %s: %s paso(s) inválido(s) ignorado(s); primer motivo: %s",
                macro_id,
                invalid_steps,
                first_invalid_reason,
            )

        return Macro(
            id=macro_id,
            name=(str(data.get("name", "Macro")).strip() or "Macro")[:120],
            description=str(data.get("description", "") or "")[:2_000],
            trigger=MacroTrigger.from_dict(data.get("trigger"), data.get("trigger_button")),
            profile_ids=profile_ids,
            steps=steps,
            repeat=_clamp_int(data.get("repeat", 1), 1, 50, 1),
            enabled=bool(data.get("enabled", True)),
            cooldown_ms=_clamp_int(data.get("cooldown_ms", 250), 0, 10_000, 250),
        )

    def is_available_for_profile(self, profile_id: Optional[str]) -> bool:
        return not self.profile_ids or bool(profile_id and profile_id in self.profile_ids)

    def duration_ms(self) -> int:
        one_pass = sum(max(0, int(step.ms)) + max(0, int(step.after_ms)) for step in self.steps)
        return one_pass * max(1, self.repeat)


class MacroEngine:
    """Graba, reproduce y detecta activadores de macros."""

    MIN_WAIT_MS = 10
    MAX_WAIT_MS = 5000
    MAX_STEPS = MAX_MACRO_STEPS
    MAX_RECORD_SECONDS = 30
    ANALOG_SAMPLE_SECONDS = 0.075
    ANALOG_CHANGE_THRESHOLD = 0.16

    def __init__(self, connection_manager, emulator_manager):
        self.connection_manager = connection_manager
        self.emulator = emulator_manager
        self.macros: Dict[str, Macro] = {}
        self._enabled = True
        self._active_profile_id: Optional[str] = None

        self._recording = False
        self._record_analog = False
        self._record_start = 0.0
        self._record_last_ts = 0.0
        self._record_last_analog_ts = 0.0
        self._record_steps: List[MacroStep] = []
        self._record_pressed: set[str] = set()
        self._record_sticks = {"left": (0.0, 0.0), "right": (0.0, 0.0)}
        self._record_triggers = {"left": 0, "right": 0}

        self._playing: set[str] = set()
        self._cancel_events: Dict[str, threading.Event] = {}
        self._prev_buttons: Dict[str, bool] = {}
        self._trigger_active: Dict[str, bool] = {}
        self._last_fired_at: Dict[str, float] = {}

        self._on_macro_fired: List[Callable[[str], None]] = []
        self._on_recording_tick: List[Callable[[int, float], None]] = []
        self._lock = threading.RLock()

        if self.connection_manager:
            subscribe = getattr(
                self.connection_manager,
                "on_realtime_state_update",
                getattr(self.connection_manager, "on_state_update", None),
            )
            if subscribe:
                subscribe(self._on_state_update)

    # ===== Persistencia y consulta =====

    def load_macros(self, data: Dict[str, dict]) -> None:
        # Una recarga no debe dejar hilos ejecutando definiciones antiguas.
        with self._lock:
            has_running_macros = bool(self._cancel_events)
        if has_running_macros:
            self.stop_all()
        with self._lock:
            self.macros = {}
            items = list((data or {}).items())[:MAX_LOADED_MACROS]
            for macro_id, payload in items:
                try:
                    content = dict(payload) if isinstance(payload, dict) else {}
                    content.setdefault("id", macro_id)
                    macro = Macro.from_dict(content)
                    self.macros[macro.id] = macro
                except Exception as exc:
                    logger.warning("Macro inválida ignorada (%s): %s", macro_id, exc)

    def export_macros(self) -> Dict[str, dict]:
        with self._lock:
            return {macro_id: macro.to_dict() for macro_id, macro in self.macros.items()}

    def save_macro(self, macro: Macro) -> None:
        if not isinstance(macro, Macro):
            raise TypeError("save_macro requiere Macro")
        with self._lock:
            self.macros[macro.id] = Macro.from_dict(macro.to_dict())

    def delete_macro(self, macro_id: str) -> None:
        self.stop_macro(macro_id)
        with self._lock:
            self.macros.pop(macro_id, None)
            self._trigger_active.pop(macro_id, None)
            self._last_fired_at.pop(macro_id, None)

    def get_macros(self) -> List[Macro]:
        with self._lock:
            return sorted(
                (Macro.from_dict(macro.to_dict()) for macro in self.macros.values()),
                key=lambda item: item.name.lower(),
            )

    def get_macro(self, macro_id: str) -> Optional[Macro]:
        with self._lock:
            macro = self.macros.get(macro_id)
            return Macro.from_dict(macro.to_dict()) if macro else None

    def duplicate_macro(self, macro_id: str) -> Optional[Macro]:
        source = self.get_macro(macro_id)
        if not source:
            return None
        source.id = self.new_macro_id()
        source.name = f"{source.name} copia"
        source.trigger = MacroTrigger()
        self.save_macro(source)
        return source

    def new_macro_id(self) -> str:
        return f"macro_{uuid.uuid4().hex[:8]}"

    def set_enabled(self, enabled: bool) -> None:
        normalized = bool(enabled)
        with self._lock:
            self._enabled = normalized
        if not normalized:
            self.stop_all()

    @property
    def is_enabled(self) -> bool:
        with self._lock:
            return bool(self._enabled)

    def set_active_profile(self, profile_id: Optional[str]) -> None:
        normalized = str(profile_id) if profile_id else None
        with self._lock:
            changed = normalized != self._active_profile_id
            has_running_macros = bool(self._cancel_events)
            self._active_profile_id = normalized
            self._trigger_active.clear()
        # Una macro perteneciente al perfil anterior no debe seguir inyectando
        # entradas después del cambio de perfil.
        if changed and has_running_macros:
            self.stop_all()

    @property
    def active_profile_id(self) -> Optional[str]:
        with self._lock:
            return self._active_profile_id

    def is_playing(self, macro_id: Optional[str] = None) -> bool:
        with self._lock:
            return bool(self._playing) if macro_id is None else macro_id in self._playing

    # ===== Grabación =====

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._recording

    def start_recording(self, include_sticks: bool = False) -> None:
        with self._lock:
            self._recording = True
            self._record_analog = bool(include_sticks)
            self._record_start = time.monotonic()
            self._record_last_ts = self._record_start
            self._record_last_analog_ts = self._record_start
            self._record_steps = []
            self._record_pressed = set()
            self._record_sticks = {"left": (0.0, 0.0), "right": (0.0, 0.0)}
            self._record_triggers = {"left": 0, "right": 0}

    def stop_recording(self) -> List[MacroStep]:
        with self._lock:
            self._recording = False
            for button_name in list(self._record_pressed):
                self._record_steps.append(MacroStep(StepType.RELEASE, button=button_name))
            self._record_pressed.clear()
            if self._record_analog:
                for stick, position in self._record_sticks.items():
                    if math.hypot(*position) > 0.05:
                        self._record_steps.append(
                            MacroStep(StepType.STICK, stick=stick, x=0.0, y=0.0)
                        )
                for side, value in self._record_triggers.items():
                    if value > 0:
                        self._record_steps.append(
                            MacroStep(StepType.TRIGGER, trigger=side, value=0)
                        )
            steps = [MacroStep.from_dict(step.to_dict()) for step in self._record_steps]
            self._record_steps = []
            self._record_analog = False
            return steps

    def get_recording_steps(self) -> List[MacroStep]:
        """Devuelve una copia segura de lo capturado hasta este instante.

        La UI puede mostrar la secuencia mientras se graba sin tocar la lista
        interna ni detener la grabación.
        """
        with self._lock:
            return [MacroStep.from_dict(step.to_dict()) for step in self._record_steps]

    def on_recording_tick(self, callback: Callable[[int, float], None]) -> None:
        self._on_recording_tick.append(callback)

    # ===== Reproducción =====

    def play_macro(self, macro_id: str) -> bool:
        with self._lock:
            macro = self.macros.get(macro_id)
            if not macro or macro_id in self._playing or not macro.steps or not macro.enabled:
                return False
            macro_copy = Macro.from_dict(macro.to_dict())
            cancel = threading.Event()
            self._playing.add(macro_id)
            self._cancel_events[macro_id] = cancel
        threading.Thread(
            target=self._run_macro, args=(macro_copy, cancel), daemon=True, name=f"Macro-{macro_id}"
        ).start()
        return True

    def play_steps(self, steps: List[MacroStep]) -> bool:
        if not steps:
            return False
        preview_id = "__preview__"
        with self._lock:
            if preview_id in self._playing:
                return False
            self._playing.add(preview_id)
            cancel = threading.Event()
            self._cancel_events[preview_id] = cancel
        temp = Macro(
            id=preview_id,
            name="Vista previa",
            steps=[MacroStep.from_dict(step.to_dict()) for step in steps],
        )
        threading.Thread(
            target=self._run_macro, args=(temp, cancel), daemon=True, name="Macro-preview"
        ).start()
        return True

    def stop_macro(self, macro_id: str) -> bool:
        with self._lock:
            event = self._cancel_events.get(macro_id)
            if event:
                event.set()
                return True
        return False

    def stop(self) -> None:
        """Detiene grabación y reproducción antes de cerrar la aplicación."""
        with self._lock:
            self._enabled = False
            self._recording = False
            self._record_pressed.clear()
        self.stop_all()

    def stop_all(self) -> None:
        with self._lock:
            events = list(self._cancel_events.values())
        for event in events:
            event.set()
        try:
            self.emulator.macro_clear()
            if hasattr(self.emulator, "macro_clear_sticks"):
                self.emulator.macro_clear_sticks()
            if hasattr(self.emulator, "macro_clear_triggers"):
                self.emulator.macro_clear_triggers()
        except Exception:
            pass

    @staticmethod
    def _sleep(cancel: threading.Event, milliseconds: int) -> bool:
        return not cancel.wait(max(0, milliseconds) / 1000.0)

    def _run_macro(self, macro: Macro, cancel: threading.Event) -> None:
        pressed: set[str] = set()
        touched_sticks: set[str] = set()
        touched_triggers: set[str] = set()
        try:
            for _ in range(max(1, macro.repeat)):
                for step in macro.steps:
                    if cancel.is_set():
                        return
                    if step.type == StepType.TAP and step.button:
                        self.emulator.macro_press(step.button)
                        pressed.add(step.button)
                        if step.ms and not self._sleep(cancel, step.ms):
                            return
                        self.emulator.macro_release(step.button)
                        pressed.discard(step.button)
                    elif step.type == StepType.PRESS and step.button:
                        self.emulator.macro_press(step.button)
                        pressed.add(step.button)
                    elif step.type == StepType.RELEASE and step.button:
                        self.emulator.macro_release(step.button)
                        pressed.discard(step.button)
                    elif step.type == StepType.WAIT:
                        if not self._sleep(cancel, step.ms):
                            return
                    elif step.type == StepType.STICK and step.stick:
                        if hasattr(self.emulator, "macro_set_stick"):
                            self.emulator.macro_set_stick(step.stick, step.x, step.y)
                            touched_sticks.add(step.stick)
                        if step.ms:
                            if not self._sleep(cancel, step.ms):
                                return
                            if hasattr(self.emulator, "macro_clear_stick"):
                                self.emulator.macro_clear_stick(step.stick)
                            touched_sticks.discard(step.stick)
                    elif step.type == StepType.TRIGGER and step.trigger:
                        if hasattr(self.emulator, "macro_set_trigger"):
                            self.emulator.macro_set_trigger(step.trigger, step.value)
                            touched_triggers.add(step.trigger)
                        if step.ms:
                            if not self._sleep(cancel, step.ms):
                                return
                            if hasattr(self.emulator, "macro_clear_trigger"):
                                self.emulator.macro_clear_trigger(step.trigger)
                            touched_triggers.discard(step.trigger)
                    if step.after_ms and not self._sleep(cancel, step.after_ms):
                        return
        except Exception as exc:
            logger.error("Error reproduciendo macro '%s': %s", macro.name, exc)
        finally:
            for button_name in pressed:
                try:
                    self.emulator.macro_release(button_name)
                except Exception:
                    pass
            for stick in touched_sticks:
                try:
                    self.emulator.macro_clear_stick(stick)
                except Exception:
                    pass
            for trigger in touched_triggers:
                try:
                    self.emulator.macro_clear_trigger(trigger)
                except Exception:
                    pass
            with self._lock:
                self._playing.discard(macro.id)
                self._cancel_events.pop(macro.id, None)
            self._notify_fired(macro.id)

    def on_macro_fired(self, callback: Callable[[str], None]) -> None:
        self._on_macro_fired.append(callback)

    def _notify_fired(self, macro_id: str) -> None:
        for callback in self._on_macro_fired:
            try:
                callback(macro_id)
            except Exception:
                pass

    # ===== Activadores físicos =====

    @staticmethod
    def _normalize_axis(value: Any) -> float:
        try:
            raw = max(0.0, min(255.0, float(value)))
        except (TypeError, ValueError, OverflowError):
            raw = 128.0
        return (raw - 128.0) / (127.0 if raw >= 128.0 else 128.0)

    def _stick_xy(self, state, stick: str) -> tuple[float, float]:
        prefix = "left" if stick == "left" else "right"
        return (
            self._normalize_axis(getattr(state, f"{prefix}_stick_x", 128)),
            self._normalize_axis(getattr(state, f"{prefix}_stick_y", 128)),
        )

    @staticmethod
    def _direction_active(x: float, y: float, direction: str, threshold: float) -> bool:
        # En el reporte físico, Y negativo es arriba después de normalizar.
        horizontal = abs(x) >= threshold
        vertical = abs(y) >= threshold
        if direction == "up":
            return y <= -threshold and abs(y) >= abs(x) * 0.75
        if direction == "down":
            return y >= threshold and abs(y) >= abs(x) * 0.75
        if direction == "left":
            return x <= -threshold and abs(x) >= abs(y) * 0.75
        if direction == "right":
            return x >= threshold and abs(x) >= abs(y) * 0.75
        if direction == "up_left":
            return horizontal and vertical and x < 0 and y < 0
        if direction == "up_right":
            return horizontal and vertical and x > 0 and y < 0
        if direction == "down_left":
            return horizontal and vertical and x < 0 and y > 0
        if direction == "down_right":
            return horizontal and vertical and x > 0 and y > 0
        return False

    def _trigger_is_active(self, macro: Macro, state, buttons: Dict[str, bool]) -> bool:
        trigger = macro.trigger
        if trigger.kind == TriggerKind.MANUAL:
            return False
        if trigger.kind == TriggerKind.BUTTON:
            return bool(trigger.buttons and buttons.get(trigger.buttons[0]))
        if trigger.kind == TriggerKind.COMBO:
            return bool(
                trigger.buttons and all(bool(buttons.get(name)) for name in trigger.buttons)
            )
        if trigger.kind == TriggerKind.TRIGGER:
            raw = getattr(
                state, f"{'left' if trigger.analog_trigger == 'left' else 'right'}_trigger", 0
            )
            try:
                value = max(0.0, min(255.0, float(raw))) / 255.0
            except (TypeError, ValueError, OverflowError):
                value = 0.0
            return value >= trigger.threshold
        x, y = self._stick_xy(state, trigger.stick)
        return self._direction_active(x, y, trigger.direction, trigger.threshold)

    def _on_state_update(self, state) -> None:
        buttons = dict(getattr(state, "buttons", {}) or {})
        if self._recording:
            self._record_tick(state, buttons)

        if self._enabled and not self._recording:
            now = time.monotonic()
            # Los objetos almacenados nunca se editan en sitio: save_macro y
            # load_macros siempre guardan copias nuevas. Tomar solo las
            # referencias bajo el lock evita serializar y reconstruir todas
            # las macros cientos de veces por segundo dentro de la ruta HID.
            with self._lock:
                macros_snapshot = tuple(self.macros.values())
            for macro in macros_snapshot:
                active = self._trigger_is_active(macro, state, buttons)
                was_active = bool(self._trigger_active.get(macro.id))
                self._trigger_active[macro.id] = active
                if not macro.enabled:
                    continue
                edge = macro.trigger.edge
                should_fire = (
                    (edge == TriggerEdge.PRESS and active and not was_active)
                    or (edge == TriggerEdge.RELEASE and not active and was_active)
                    or (edge == TriggerEdge.WHILE_HELD and active and not self.is_playing(macro.id))
                )
                if not should_fire:
                    continue
                if not macro.is_available_for_profile(self._active_profile_id):
                    continue
                last = self._last_fired_at.get(macro.id, 0.0)
                if (now - last) * 1000 < macro.cooldown_ms:
                    continue
                if self.play_macro(macro.id):
                    self._last_fired_at[macro.id] = now

        self._prev_buttons = dict(buttons)

    def _append_record_wait(self, now: float) -> None:
        """Guarda el tiempo hasta la siguiente entrada en el paso anterior.

        Así la grabación queda compacta y el usuario puede editar directamente
        el tiempo entre cada botón o movimiento sin navegar entre filas de espera.
        """
        elapsed_ms = int((now - self._record_last_ts) * 1000)
        if elapsed_ms >= self.MIN_WAIT_MS and self._record_steps:
            delay = min(elapsed_ms, self.MAX_WAIT_MS)
            previous = self._record_steps[-1]
            if previous.type == StepType.WAIT:
                previous.ms = min(60_000, previous.ms + delay)
            else:
                previous.after_ms = min(60_000, previous.after_ms + delay)
        self._record_last_ts = now

    def _record_tick(self, state, buttons: Dict[str, bool]) -> None:
        # El reloj monotónico no salta si Windows sincroniza la hora mientras
        # se está grabando una macro.
        now = time.monotonic()
        with self._lock:
            if now - self._record_start > self.MAX_RECORD_SECONDS:
                self._recording = False
                return

            for button_name in MACRO_BUTTONS:
                is_down = bool(buttons.get(button_name))
                was_down = button_name in self._record_pressed
                if is_down == was_down:
                    continue
                self._append_record_wait(now)
                if is_down:
                    self._record_steps.append(MacroStep(StepType.PRESS, button=button_name))
                    self._record_pressed.add(button_name)
                else:
                    self._record_steps.append(MacroStep(StepType.RELEASE, button=button_name))
                    self._record_pressed.discard(button_name)

            if (
                self._record_analog
                and now - self._record_last_analog_ts >= self.ANALOG_SAMPLE_SECONDS
            ):
                self._record_last_analog_ts = now
                for stick in ("left", "right"):
                    current = self._stick_xy(state, stick)
                    previous = self._record_sticks[stick]
                    moved = math.hypot(current[0] - previous[0], current[1] - previous[1])
                    neutral_transition = math.hypot(*current) < 0.08 <= math.hypot(*previous)
                    if moved >= self.ANALOG_CHANGE_THRESHOLD or neutral_transition:
                        self._append_record_wait(now)
                        x = 0.0 if abs(current[0]) < 0.08 else current[0]
                        y = 0.0 if abs(current[1]) < 0.08 else current[1]
                        self._record_steps.append(MacroStep(StepType.STICK, stick=stick, x=x, y=y))
                        self._record_sticks[stick] = (x, y)

                for side in ("left", "right"):
                    try:
                        current_value = max(0, min(255, int(getattr(state, f"{side}_trigger", 0))))
                    except (TypeError, ValueError, OverflowError):
                        current_value = 0
                    previous_value = self._record_triggers[side]
                    changed = abs(current_value - previous_value) >= 20
                    released = current_value <= 5 < previous_value
                    if changed or released:
                        self._append_record_wait(now)
                        current_value = 0 if current_value <= 5 else current_value
                        self._record_steps.append(
                            MacroStep(StepType.TRIGGER, trigger=side, value=current_value)
                        )
                        self._record_triggers[side] = current_value

            if len(self._record_steps) >= self.MAX_STEPS:
                self._recording = False

            step_count = len(self._record_steps)
            elapsed_total = now - self._record_start

        for callback in self._on_recording_tick:
            try:
                callback(step_count, elapsed_total)
            except Exception:
                pass
