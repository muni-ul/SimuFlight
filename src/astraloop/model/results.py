"""Structured in-memory results returned by the simulation runtime."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

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


@dataclass(frozen=True, slots=True)
class RunResult:
    scenario_id: str
    config_digest: str
    simulation: SimulationResult
    final_mission_state: str
    telemetry: tuple[Any, ...]
    events: tuple[Any, ...]
    active_fault_ids: tuple[str, ...]
    validation: Any | None = None
    artifact_directory: str | None = None
