"""Immutable records representing perfect simulator truth and its derivative."""

from dataclasses import dataclass, fields
from math import isfinite


@dataclass(frozen=True, slots=True)
class VehicleState:
    """Planar vehicle truth state in SI units.

    Coordinates use +x right and +y up. ``theta=0`` is upright, and positive
    theta/omega rotate clockwise toward +x. Angles are always radians.
    Simulation time intentionally belongs to the engine, not this record.
    """

    x: float
    y: float
    vx: float
    vy: float
    theta: float
    omega: float
    mass: float

    def is_finite(self) -> bool:
        return all(isfinite(getattr(self, field.name)) for field in fields(self))


@dataclass(frozen=True, slots=True)
class VehicleStateDerivative:
    """Instantaneous derivative of every field in :class:`VehicleState`."""

    dx: float
    dy: float
    dvx: float
    dvy: float
    dtheta: float
    domega: float
    dmass: float
