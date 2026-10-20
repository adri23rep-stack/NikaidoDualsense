"""Puerta sellada para el backend nativo aún no compilado ni firmado.

Alpha 2.3.0 incluye código fuente KMDF/VHF por separado, pero este módulo no carga,
instala ni controla drivers. Impide presentar código no compilado y no validado
como una emulación real.
"""

from __future__ import annotations

from .backend import (
    BackendCapabilities,
    BackendSnapshot,
    BackendStatus,
    BackendSubscriber,
    BackendUnavailableError,
    Unsubscribe,
    VirtualControllerBackend,
)
from .diagnostics import DiagnosticReport, collect_diagnostics
from .hid_report import encode_input_report
from .model import ControllerState


class NativeHidBackend(VirtualControllerBackend):
    def __init__(self, report: DiagnosticReport | None = None) -> None:
        self._report = report or collect_diagnostics()
        self._state = ControllerState.neutral()
        self._capabilities = BackendCapabilities(
            backend_id="native-vhf-alpha2-source-gated",
            native=True,
            reports_to_os=False,
        )
        self._last_error = "; ".join(self._report.native_blockers)

    @property
    def capabilities(self) -> BackendCapabilities:
        return self._capabilities

    @property
    def status(self) -> BackendStatus:
        return BackendStatus.STOPPED

    def _blocked(self) -> BackendUnavailableError:
        return BackendUnavailableError(
            self._last_error or "El backend nativo está bloqueado en Alpha 2.3.0"
        )

    def start(self) -> BackendSnapshot:
        raise self._blocked()

    def submit_state(self, state: ControllerState) -> BackendSnapshot:
        if not isinstance(state, ControllerState):
            raise TypeError("state debe ser ControllerState")
        raise self._blocked()

    def neutralize(self, *, reason: str = "manual") -> BackendSnapshot:
        del reason
        return self.snapshot()

    def stop(self) -> BackendSnapshot:
        return self.snapshot()

    def snapshot(self) -> BackendSnapshot:
        return BackendSnapshot(
            status=BackendStatus.STOPPED,
            capabilities=self._capabilities,
            session_id=0,
            current_state=self._state,
            current_report=encode_input_report(self._state),
            accepted_reports=0,
            rejected_reports=0,
            neutralizations=0,
            errors=0,
            callback_errors=0,
            history_size=0,
            subscriber_count=0,
            uptime_ms=0.0,
            last_error=self._last_error,
        )

    def subscribe(self, callback: BackendSubscriber) -> Unsubscribe:
        if not callable(callback):
            raise TypeError("El callback debe ser invocable")

        def unsubscribe() -> None:
            return None

        return unsubscribe
