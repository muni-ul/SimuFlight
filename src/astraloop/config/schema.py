"""Fully resolved immutable runtime scenario configuration."""

from dataclasses import asdict, dataclass
from enum import StrEnum
from hashlib import sha256
import json

from astraloop.actuators.models import ActuatorConfig
from astraloop.control.flight_controller import ControlProfile, ControllerConfig
from astraloop.faults.types import FaultDefinition
from astraloop.mission.modes import MissionMode
from astraloop.mission.state_machine import MissionConfig
from astraloop.model.measurements import SensorName
from astraloop.model.state import VehicleState
from astraloop.sensors.models import SensorConfig
from astraloop.simulation.dynamics import VehicleParameters
from astraloop.simulation.engine import SimulationConfig
from astraloop.simulation.environment import EnvironmentForces


class ExpectedOutcome(StrEnum):
    PASS = "pass"
    CONTROLLED_ABORT = "controlled_abort"
    VALIDATION_FAIL = "validation_fail"


@dataclass(frozen=True, slots=True)
class ValidationConfig:
    expected_outcome: ExpectedOutcome
    max_landing_vertical_speed: float = 2.0
    max_horizontal_error: float = 5.0
    max_pitch_error: float = 0.08726646259971647
    require_valid_transitions: bool = True


@dataclass(frozen=True, slots=True)
class ResolvedScenarioConfig:
    schema_version: int
    id: str
    description: str
    seed: int
    simulation: SimulationConfig
    initial_state: VehicleState
    vehicle: VehicleParameters
    environment: EnvironmentForces
    sensors: tuple[tuple[SensorName, SensorConfig], ...]
    controller: ControllerConfig
    profiles: tuple[tuple[MissionMode, ControlProfile], ...]
    actuators: ActuatorConfig
    mission: MissionConfig
    faults: tuple[FaultDefinition, ...]
    validation: ValidationConfig

    @property
    def digest(self) -> str:
        canonical = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), default=str)
        return sha256(canonical.encode("utf-8")).hexdigest()

    def sensor_mapping(self) -> dict[SensorName, SensorConfig]:
        return dict(self.sensors)

    def profile_mapping(self) -> dict[MissionMode, ControlProfile]:
        return dict(self.profiles)
