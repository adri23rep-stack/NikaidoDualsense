"""Backend simulado, determinista y seguro de Alpha 1."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Iterable, Optional

from .backend import (
    BackendCapabilities,
    BackendError,
    BackendEvent,
    BackendSnapshot,
    BackendStateError,
    BackendStatus,
    BackendSubscriber,
    StaleStateError,
    Unsubscribe,
    VirtualControllerBackend,
)
from .hid_report import encode_input_report
from .model import ControllerState


class SimulatedDualSenseBackend(VirtualControllerBackend):
    """Implementa el ciclo completo sin publicar ningún dispositivo en Windows."""

    def __init__(
        self,
        *,
        history_limit: int = 512,
        fail_after_reports: Optional[int] = None,
    ) -> None:
        if isinstance(history_limit, bool) or not isinstance(history_limit, int):
            raise TypeError("history_limit debe ser un entero")
        if not 16 <= history_limit <= 10_000:
            raise ValueError("history_limit debe estar entre 16 y 10000")
        if fail_after_reports is not None:
            if isinstance(fail_after_reports, bool) or not isinstance(fail_after_reports, int):
                raise TypeError("fail_after_reports debe ser un entero o None")
            if fail_after_reports < 0:
                raise ValueError("fail_after_reports no puede ser negativo")

        self._lock = threading.RLock()
        self._status = BackendStatus.STOPPED
        self._capabilities = BackendCapabilities(
            backend_id="simulated-dualsense-alpha1",
            native=False,
            reports_to_os=False,
        )
        self._history = deque(maxlen=history_limit)
        self._subscribers: list[BackendSubscriber] = []
        self._fail_after_reports = fail_after_reports
        self._session_id = 0
        self._event_index = 0
        self._current_state = ControllerState.neutral()
        self._current_report = encode_input_report(self._current_state)
        self._accepted_reports = 0
        self._rejected_reports = 0
        self._neutralizations = 0
        self._errors = 0
        self._callback_errors = 0
        self._started_ns = 0
        self._last_error = ""

    @property
    def capabilities(self) -> BackendCapabilities:
        return self._capabilities

    @property
    def status(self) -> BackendStatus:
        with self._lock:
            return self._status

    def _snapshot_locked(self) -> BackendSnapshot:
        uptime_ms = 0.0
        if self._started_ns:
            uptime_ms = max(0.0, (time.monotonic_ns() - self._started_ns) / 1_000_000.0)
        return BackendSnapshot(
            status=self._status,
            capabilities=self._capabilities,
            session_id=self._session_id,
            current_state=self._current_state,
            current_report=self._current_report,
            accepted_reports=self._accepted_reports,
            rejected_reports=self._rejected_reports,
            neutralizations=self._neutralizations,
            errors=self._errors,
            callback_errors=self._callback_errors,
            history_size=len(self._history),
            subscriber_count=len(self._subscribers),
            uptime_ms=round(uptime_ms, 3),
            last_error=self._last_error,
        )

    def snapshot(self) -> BackendSnapshot:
        with self._lock:
            return self._snapshot_locked()

    def _record_locked(
        self,
        kind: str,
        *,
        state: ControllerState | None = None,
        report: bytes | None = None,
        reason: str = "",
    ) -> BackendEvent:
        self._event_index += 1
        event = BackendEvent(
            index=self._event_index,
            kind=str(kind),
            at_ns=time.monotonic_ns(),
            state=state or self._current_state,
            report=bytes(report if report is not None else self._current_report),
            reason=str(reason or ""),
        )
        self._history.append(event)
        return event

    def _notify(self, events: Iterable[BackendEvent]) -> None:
        for event in tuple(events):
            with self._lock:
                callbacks = tuple(self._subscribers)
            failed = []
            for callback in callbacks:
                try:
                    callback(event)
                except Exception:
                    failed.append(callback)
            if failed:
                with self._lock:
                    self._callback_errors += len(failed)
                    self._subscribers[:] = [
                        callback for callback in self._subscribers if callback not in failed
                    ]

    def start(self) -> BackendSnapshot:
        with self._lock:
            if self._status == BackendStatus.RUNNING:
                return self._snapshot_locked()
            if self._status == BackendStatus.FAULTED:
                raise BackendStateError("Detén el backend fallido antes de reiniciarlo")
            self._session_id += 1
            self._event_index = 0
            self._history.clear()
            self._accepted_reports = 0
            self._rejected_reports = 0
            self._neutralizations = 0
            self._errors = 0
            self._callback_errors = 0
            self._last_error = ""
            self._current_state = ControllerState.neutral(sequence=0)
            self._current_report = encode_input_report(self._current_state)
            self._started_ns = time.monotonic_ns()
            self._status = BackendStatus.RUNNING
            event = self._record_locked("started", reason="simulation")
            snapshot = self._snapshot_locked()
        self._notify((event,))
        return snapshot

    def submit_state(self, state: ControllerState) -> BackendSnapshot:
        if not isinstance(state, ControllerState):
            raise TypeError("state debe ser ControllerState")
        failure: BackendError | None = None
        with self._lock:
            if self._status != BackendStatus.RUNNING:
                self._rejected_reports += 1
                raise BackendStateError("El backend simulado no está activo")
            if state.sequence <= self._current_state.sequence:
                self._rejected_reports += 1
                raise StaleStateError(
                    f"Secuencia {state.sequence} no supera {self._current_state.sequence}"
                )
            if (
                self._fail_after_reports is not None
                and self._accepted_reports >= self._fail_after_reports
            ):
                self._errors += 1
                self._last_error = "Fallo simulado solicitado por la prueba"
                self._status = BackendStatus.FAULTED
                neutral = ControllerState.neutral(sequence=state.sequence)
                self._current_state = neutral
                self._current_report = encode_input_report(neutral)
                event = self._record_locked("faulted", reason=self._last_error)
                snapshot = self._snapshot_locked()
                failure = BackendError(self._last_error)
            else:
                report = encode_input_report(state)
                self._current_state = state
                self._current_report = report
                self._accepted_reports += 1
                event = self._record_locked("state", state=state, report=report)
                snapshot = self._snapshot_locked()
        self._notify((event,))
        if failure is not None:
            raise failure
        return snapshot

    def neutralize(self, *, reason: str = "manual") -> BackendSnapshot:
        with self._lock:
            if self._status == BackendStatus.STOPPED:
                return self._snapshot_locked()
            next_sequence = self._current_state.sequence + 1
            neutral = ControllerState.neutral(sequence=next_sequence)
            report = encode_input_report(neutral)
            self._current_state = neutral
            self._current_report = report
            self._neutralizations += 1
            event = self._record_locked(
                "neutralized",
                state=neutral,
                report=report,
                reason=reason,
            )
            snapshot = self._snapshot_locked()
        self._notify((event,))
        return snapshot

    def stop(self) -> BackendSnapshot:
        events = []
        with self._lock:
            if self._status == BackendStatus.STOPPED:
                return self._snapshot_locked()
            next_sequence = self._current_state.sequence + 1
            neutral = ControllerState.neutral(sequence=next_sequence)
            self._current_state = neutral
            self._current_report = encode_input_report(neutral)
            self._neutralizations += 1
            events.append(
                self._record_locked(
                    "neutralized",
                    state=neutral,
                    report=self._current_report,
                    reason="stop",
                )
            )
            self._status = BackendStatus.STOPPED
            events.append(self._record_locked("stopped", reason="clean_shutdown"))
            self._started_ns = 0
            snapshot = self._snapshot_locked()
        self._notify(events)
        return snapshot

    def subscribe(self, callback: BackendSubscriber) -> Unsubscribe:
        if not callable(callback):
            raise TypeError("El callback debe ser invocable")
        with self._lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)
        unsubscribed = False
        unsubscribe_lock = threading.Lock()

        def unsubscribe() -> None:
            nonlocal unsubscribed
            with unsubscribe_lock:
                if unsubscribed:
                    return
                unsubscribed = True
            with self._lock:
                self._subscribers[:] = [item for item in self._subscribers if item != callback]

        return unsubscribe

    def history(self) -> tuple[BackendEvent, ...]:
        with self._lock:
            return tuple(self._history)

    def __enter__(self) -> "SimulatedDualSenseBackend":
        self.start()
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.stop()

