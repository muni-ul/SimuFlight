"""Explicit environment inputs consumed by the physical model."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EnvironmentForces:
    """Gravity and externally supplied planar force/torque in SI units."""

    gravity: float = 9.80665
    force_x: float = 0.0
    force_y: float = 0.0
    torque: float = 0.0
