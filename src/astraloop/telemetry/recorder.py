"""Immutable tick-aligned telemetry and ordered event recording."""

from dataclasses import dataclass
from enum import StrEnum
from math import isclose, isfinite
from typing import Any


class TelemetryFrameKind(StrEnum):
    CONTROL = "control"
    TERMINAL = "terminal"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class TelemetryFrame:
    schema_version: int
    kind: TelemetryFrameKind
    tick: int
    time: float
    mission_state: str
    truth: Any
    measurement: Any | None
    controller: Any | None
    actuator: Any | None
    active_fault_ids: tuple[str, ...]
    termination_reason: str | None = None
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class RecordedEvent:
    sequence: int
    tick: int
    time: float
    source: str
    event_type: str
    code: str
    message: str
    data: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CompletedTelemetry:
    schema_version: int
    event_schema_version: int
    frames: tuple[TelemetryFrame, ...]
    events: tuple[RecordedEvent, ...]


class TelemetryRecorder:
    def __init__(self, dt: float) -> None:
        if not isfinite(dt) or dt <= 0.0:
            raise ValueError("Telemetry dt must be finite and > 0.")
        self.dt = dt
        self._frames: list[TelemetryFrame] = []
        self._events: list[RecordedEvent] = []
        self._finalized: CompletedTelemetry | None = None

    def record_frame(self, frame: TelemetryFrame) -> None:
        if self._finalized is not None:
            raise RuntimeError("Cannot record telemetry after finalization.")
        expected = len(self._frames)
        if frame.tick != expected:
            raise ValueError(f"Expected telemetry tick {expected}, received {frame.tick}.")
        if not isclose(frame.time, frame.tick * self.dt, abs_tol=1e-12):
            raise ValueError("Telemetry frame time must equal tick * dt.")
        if not frame.truth.is_finite():
            raise ValueError("Telemetry truth state must be finite.")
        self._frames.append(frame)

    def record_domain_event(self, event: Any) -> None:
        source = "mission" if hasattr(event, "from_state") else "fault"
        if source == "mission":
            event_type = "mission_transition"
            code = event.reason_code
            message = event.message
            data = {"from_state": event.from_state.value, "to_state": event.to_state.value}
        else:
            event_type = f"fault_{event.event_type.value}"
            code = event_type
            message = f"Fault {event.fault_id} {event.event_type.value}."
            data = {"fault_id": event.fault_id, "fault_type": event.fault_type, "target": event.target}
        self._events.append(RecordedEvent(len(self._events), event.tick, event.time, source, event_type, code, message, data))

    def record_simulation_event(self, tick: int, event_type: str, message: str, data: dict[str, Any] | None = None) -> None:
        self._events.append(RecordedEvent(len(self._events), tick, tick * self.dt, "simulation", event_type, event_type, message, data or {}))

    def finalize(self) -> CompletedTelemetry:
        if self._finalized is None:
            if not self._frames or self._frames[-1].kind not in (TelemetryFrameKind.TERMINAL, TelemetryFrameKind.ERROR):
                raise RuntimeError("Telemetry requires a final terminal or error frame.")
            self._finalized = CompletedTelemetry(1, 1, tuple(self._frames), tuple(self._events))
        return self._finalized
