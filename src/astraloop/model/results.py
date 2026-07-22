"""Structured in-memory results returned by the simulation runtime."""

from dataclasses import dataclass
from enum import StrEnum

from astraloop.model.state import VehicleState


class TerminationReason(StrEnum):
    TERMINAL_CONDITION = "terminal_condition"
    MAX_TIME = "max_time"


@dataclass(frozen=True, slots=True)
class SimulationResult:
    final_tick: int
    final_time: float
    final_state: VehicleState
    termination_reason: TerminationReason
