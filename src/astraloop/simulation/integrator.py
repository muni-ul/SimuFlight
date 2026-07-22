"""Project-owned fixed-step classical Runge-Kutta integrator."""

from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray

from astraloop.model.state import VehicleState, VehicleStateDerivative

FloatVector = NDArray[np.float64]
DerivativeFunction = Callable[[float, FloatVector], FloatVector]

STATE_VECTOR_SIZE = 7
STATE_VECTOR_ORDER = ("x", "y", "vx", "vy", "theta", "omega", "mass")


class IntegrationError(RuntimeError):
    """Raised when a derivative stage or integrated state is invalid."""


def state_to_vector(state: VehicleState) -> FloatVector:
    return np.asarray([getattr(state, name) for name in STATE_VECTOR_ORDER], dtype=float)


def vector_to_state(vector: FloatVector) -> VehicleState:
    values = np.asarray(vector, dtype=float)
    if values.shape != (STATE_VECTOR_SIZE,):
        raise IntegrationError(
            f"State vector must have shape ({STATE_VECTOR_SIZE},), received {values.shape}."
        )
    if not np.all(np.isfinite(values)):
        raise IntegrationError("State vector contains a non-finite value.")
    return VehicleState(**dict(zip(STATE_VECTOR_ORDER, values.tolist(), strict=True)))


def derivative_to_vector(derivative: VehicleStateDerivative) -> FloatVector:
    return np.asarray(
        [
            derivative.dx,
            derivative.dy,
            derivative.dvx,
            derivative.dvy,
            derivative.dtheta,
            derivative.domega,
            derivative.dmass,
        ],
        dtype=float,
    )


def _evaluate_stage(
    derivative: DerivativeFunction, time: float, state: FloatVector, stage: str
) -> FloatVector:
    value = np.asarray(derivative(time, state.copy()), dtype=float)
    if value.shape != state.shape:
        raise IntegrationError(
            f"RK4 {stage} derivative shape {value.shape} does not match state {state.shape}."
        )
    if not np.all(np.isfinite(value)):
        raise IntegrationError(f"RK4 {stage} derivative contains a non-finite value.")
    return value


def rk4_step(
    derivative: DerivativeFunction, state: FloatVector, time: float, dt: float
) -> FloatVector:
    """Advance one fixed RK4 interval without mutating the supplied state."""

    base = np.asarray(state, dtype=float).copy()
    if base.ndim != 1 or not np.all(np.isfinite(base)):
        raise IntegrationError("RK4 state must be a finite one-dimensional vector.")
    if not np.isfinite(time):
        raise IntegrationError("RK4 time must be finite.")
    if not np.isfinite(dt) or dt <= 0.0:
        raise IntegrationError("RK4 dt must be finite and > 0.")

    k1 = _evaluate_stage(derivative, time, base, "k1")
    k2 = _evaluate_stage(derivative, time + dt / 2.0, base + dt * k1 / 2.0, "k2")
    k3 = _evaluate_stage(derivative, time + dt / 2.0, base + dt * k2 / 2.0, "k3")
    k4 = _evaluate_stage(derivative, time + dt, base + dt * k3, "k4")
    result = base + dt * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
    if not np.all(np.isfinite(result)):
        raise IntegrationError("RK4 result contains a non-finite value.")
    return result
