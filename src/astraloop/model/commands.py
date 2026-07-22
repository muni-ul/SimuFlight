"""Physical input records at subsystem boundaries."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppliedActuation:
    """Actuator output physically applied to the vehicle.

    ``throttle`` is normalized to [0, 1]; ``gimbal_angle`` is in radians.
    Saturation, lag, and slew behavior belong to the actuator subsystem.
    """

    throttle: float
    gimbal_angle: float
