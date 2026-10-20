"""Orquestador de alto nivel para el backend simulado."""

from __future__ import annotations

import hashlib
import threading
from typing import Any, Iterable

from .backend import BackendSnapshot, BackendStatus, VirtualControllerBackend
from .model import BUTTON_ORDER, DPad, Stick, coerce_buttons, coerce_dpad
from .simulated import SimulatedDualSenseBackend


class VirtualDualSenseLab:
    """Serializa cambios y asigna secuencias sin depender de la app estable."""

    def __init__(self, backend: VirtualControllerBackend | None = None) -> None:
        self.backend = backend or SimulatedDualSenseBackend()
        self._lock = threading.RLock()
        self._state = self.backend.snapshot().current_state

    def start(self) -> BackendSnapshot:
        with self._lock:
            snapshot = self.backend.start()
            self._state = snapshot.current_state
            return snapshot

    def _submit(self, **changes: Any) -> BackendSnapshot:
        with self._lock:
            if self.backend.status != BackendStatus.RUNNING:
                self.start()
            changes["sequence"] = self._state.sequence + 1
            candidate = self._state.updated(**changes)
            snapshot = self.backend.submit_state(candidate)
            self._state = candidate
            return snapshot

    def set_inputs(
        self,
        *,
        buttons: Iterable[str] | None = None,
        dpad: DPad | str | None = None,
        left_stick: Stick | tuple[float, float] | None = None,
        right_stick: Stick | tuple[float, float] | None = None,
        left_trigger: float | None = None,
        right_trigger: float | None = None,
    ) -> BackendSnapshot:
        changes: dict[str, Any] = {}
        if buttons is not None:
            changes["buttons"] = coerce_buttons(buttons)
        if dpad is not None:
            changes["dpad"] = coerce_dpad(dpad)
        if left_stick is not None:
            changes["left_stick"] = (
                left_stick if isinstance(left_stick, Stick) else Stick(*left_stick)
            )
        if right_stick is not None:
            changes["right_stick"] = (
                right_stick if isinstance(right_stick, Stick) else Stick(*right_stick)
            )
        if left_trigger is not None:
            changes["left_trigger"] = left_trigger
        if right_trigger is not None:
            changes["right_trigger"] = right_trigger
        if not changes:
            raise ValueError("No se indicó ningún control para actualizar")
        return self._submit(**changes)

    def press(self, *buttons: str) -> BackendSnapshot:
        requested = coerce_buttons(buttons)
        return self._submit(buttons=self._state.buttons | requested)

    def release(self, *buttons: str) -> BackendSnapshot:
        requested = coerce_buttons(buttons)
        return self._submit(buttons=self._state.buttons - requested)

    def neutralize(self, *, reason: str = "lab") -> BackendSnapshot:
        with self._lock:
            snapshot = self.backend.neutralize(reason=reason)
            self._state = snapshot.current_state
            return snapshot

    def stop(self) -> BackendSnapshot:
        with self._lock:
            snapshot = self.backend.stop()
            self._state = snapshot.current_state
            return snapshot

    def snapshot(self) -> BackendSnapshot:
        return self.backend.snapshot()

    def __enter__(self) -> "VirtualDualSenseLab":
        self.start()
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.stop()


def run_alpha1_simulation() -> dict[str, Any]:
    """Ejercita todos los controles del alcance y devuelve evidencia portable."""

    backend = SimulatedDualSenseBackend(history_limit=128)
    lab = VirtualDualSenseLab(backend)
    lab.start()
    lab.set_inputs(
        buttons=[button.value for button in BUTTON_ORDER],
        dpad=DPad.UP,
        left_stick=(-1.0, 1.0),
        right_stick=(1.0, -1.0),
        left_trigger=1.0,
        right_trigger=1.0,
    )
    for index, direction in enumerate(DPad):
        ratio = index / max(1, len(DPad) - 1)
        lab.set_inputs(
            dpad=direction,
            left_stick=(-1.0 + 2.0 * ratio, 1.0 - 2.0 * ratio),
            right_stick=(1.0 - 2.0 * ratio, -1.0 + 2.0 * ratio),
            left_trigger=ratio,
            right_trigger=1.0 - ratio,
        )
    lab.set_inputs(buttons=[], dpad=DPad.CENTER, left_trigger=0.0, right_trigger=0.0)
    lab.neutralize(reason="alpha1_demo")
    before_stop = lab.snapshot()
    stopped = lab.stop()
    history = backend.history()
    digest = hashlib.sha256(b"".join(event.report for event in history)).hexdigest()
    return {
        "backend": backend.capabilities.backend_id,
        "simulation_ready": True,
        "reports_to_os": False,
        "dualsense_protocol": False,
        "buttons_exercised": [button.value for button in BUTTON_ORDER],
        "dpad_directions_exercised": [direction.value for direction in DPad],
        "stick_extremes_exercised": True,
        "analog_trigger_range_exercised": [0.0, 1.0],
        "accepted_reports": before_stop.accepted_reports,
        "neutralizations": stopped.neutralizations,
        "final_status": stopped.status.value,
        "final_state_neutral": not stopped.current_state.buttons
        and stopped.current_state.dpad == DPad.CENTER
        and stopped.current_state.left_stick == Stick()
        and stopped.current_state.right_stick == Stick()
        and stopped.current_state.left_trigger == 0.0
        and stopped.current_state.right_trigger == 0.0,
        "history_sha256": digest,
    }
