"""Contrato de backends para Virtual DualSense Lab."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from .model import ControllerState


class BackendStatus(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    FAULTED = "faulted"


class BackendError(RuntimeError):
    """Error base controlado del laboratorio."""


class BackendUnavailableError(BackendError):
    """El backend solicitado no puede usarse con seguridad."""


class BackendStateError(BackendError):
    """Una operación no es válida en el estado actual."""


class StaleStateError(BackendStateError):
    """Se rechazó un estado fuera de orden."""


@dataclass(frozen=True, slots=True)
class BackendCapabilities:
    backend_id: str
    native: bool
    reports_to_os: bool
    buttons: bool = True
    dpad: bool = True
    sticks: bool = True
    analog_triggers: bool = True
    output_reports: bool = False
    feature_reports: bool = False
    motion: bool = False
    touch_contacts: bool = False
    adaptive_triggers: bool = False
    audio: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_id": self.backend_id,
            "native": self.native,
            "reports_to_os": self.reports_to_os,
            "buttons": self.buttons,
            "dpad": self.dpad,
            "sticks": self.sticks,
            "analog_triggers": self.analog_triggers,
            "output_reports": self.output_reports,
            "feature_reports": self.feature_reports,
            "motion": self.motion,
            "touch_contacts": self.touch_contacts,
            "adaptive_triggers": self.adaptive_triggers,
            "audio": self.audio,
        }


@dataclass(frozen=True, slots=True)
class BackendEvent:
    index: int
    kind: str
    at_ns: int
    state: ControllerState
    report: bytes
    reason: str = ""

    def to_dict(self, *, include_report: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "index": self.index,
            "kind": self.kind,
            "at_ns": self.at_ns,
            "state": self.state.to_dict(),
            "reason": self.reason,
        }
        if include_report:
            result["report_hex"] = self.report.hex()
        return result


@dataclass(frozen=True, slots=True)
class BackendSnapshot:
    status: BackendStatus
    capabilities: BackendCapabilities
    session_id: int
    current_state: ControllerState
    current_report: bytes
    accepted_reports: int
    rejected_reports: int
    neutralizations: int
    errors: int
    callback_errors: int
    history_size: int
    subscriber_count: int
    uptime_ms: float
    last_error: str = ""

    def to_dict(self, *, include_report: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": self.status.value,
            "capabilities": self.capabilities.to_dict(),
            "session_id": self.session_id,
            "current_state": self.current_state.to_dict(),
            "accepted_reports": self.accepted_reports,
            "rejected_reports": self.rejected_reports,
            "neutralizations": self.neutralizations,
            "errors": self.errors,
            "callback_errors": self.callback_errors,
            "history_size": self.history_size,
            "subscriber_count": self.subscriber_count,
            "uptime_ms": self.uptime_ms,
            "last_error": self.last_error,
        }
        if include_report:
            result["current_report_hex"] = self.current_report.hex()
        return result


BackendSubscriber = Callable[[BackendEvent], None]
Unsubscribe = Callable[[], None]


class VirtualControllerBackend(ABC):
    """Superficie mínima que no depende de Qt ni de la emulación estable."""

    @property
    @abstractmethod
    def capabilities(self) -> BackendCapabilities:
        raise NotImplementedError

    @property
    @abstractmethod
    def status(self) -> BackendStatus:
        raise NotImplementedError

    @abstractmethod
    def start(self) -> BackendSnapshot:
        raise NotImplementedError

    @abstractmethod
    def submit_state(self, state: ControllerState) -> BackendSnapshot:
        raise NotImplementedError

    @abstractmethod
    def neutralize(self, *, reason: str = "manual") -> BackendSnapshot:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> BackendSnapshot:
        raise NotImplementedError

    @abstractmethod
    def snapshot(self) -> BackendSnapshot:
        raise NotImplementedError

    @abstractmethod
    def subscribe(self, callback: BackendSubscriber) -> Unsubscribe:
        raise NotImplementedError

