"""Physical input records at subsystem boundaries."""

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class AppliedActuation:
    """Actuator output physically applied to the vehicle.

    ``throttle`` is normalized to [0, 1]; ``gimbal_angle`` is in radians.
    Saturation, lag, and slew behavior belong to the actuator subsystem.
    """

    throttle: float
    gimbal_angle: float


@dataclass(frozen=True, slots=True)
class ControlCommand:
    """Desired software command before actuator physics."""

    throttle: float
    attitude_command: float


class ControllerStatus(StrEnum):
    OK = "ok"
    HELD = "held"
    INVALID_INPUT = "invalid_input"
    INACTIVE = "inactive"


@dataclass(frozen=True, slots=True)
class ControllerUpdate:
    command: ControlCommand
    status: ControllerStatus
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ActuatorState:
    throttle: float = 0.0
    gimbal_angle: float = 0.0


@dataclass(frozen=True, slots=True)
class ActuatorUpdate:
    state: ActuatorState
    throttle_target: float
    gimbal_target: float
    throttle_saturated: bool
    gimbal_saturated: bool
    throttle_rate_limited: bool
    gimbal_rate_limited: bool
    degraded: bool
