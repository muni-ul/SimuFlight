"""Deterministic 2D planar rigid-body flight dynamics.

Coordinate convention: +x is right, +y is up, theta=0 is upright, and
positive theta is clockwise/rightward. All angles are radians. This module
calculates derivatives only; numerical integration belongs to the engine.
"""

from dataclasses import dataclass, fields, replace
from math import cos, isfinite, sin

from astraloop.model.commands import AppliedActuation
from astraloop.model.state import VehicleState, VehicleStateDerivative
from astraloop.simulation.environment import EnvironmentForces

_MASS_TOLERANCE_KG = 1e-9


class DynamicsInputError(ValueError):
    """Raised when parameters or physical inputs violate their contract."""


class DynamicsInvariantError(ValueError):
    """Raised when vehicle truth violates a physical invariant."""


@dataclass(frozen=True, slots=True)
class VehicleParameters:
    """Immutable physical properties of the simplified vehicle, in SI units."""

    dry_mass: float
    max_thrust: float
    max_mass_flow_rate: float
    moment_of_inertia: float
    thrust_lever_arm: float


def _require_finite(name: str, value: float) -> None:
    if not isfinite(value):
        raise DynamicsInputError(f"Invalid {name}: expected a finite value, received {value!r}.")


def validate_parameters(parameters: VehicleParameters) -> None:
    for field in fields(parameters):
        _require_finite(f"vehicle parameter {field.name}", getattr(parameters, field.name))
    if parameters.dry_mass <= 0.0:
        raise DynamicsInputError("Invalid vehicle parameter: dry_mass must be > 0 kg.")
    if parameters.max_thrust < 0.0:
        raise DynamicsInputError("Invalid vehicle parameter: max_thrust must be >= 0 N.")
    if parameters.max_mass_flow_rate < 0.0:
        raise DynamicsInputError(
            "Invalid vehicle parameter: max_mass_flow_rate must be >= 0 kg/s."
        )
    if parameters.moment_of_inertia <= 0.0:
        raise DynamicsInputError(
            "Invalid vehicle parameter: moment_of_inertia must be > 0 kg*m^2."
        )
    if parameters.thrust_lever_arm < 0.0:
        raise DynamicsInputError(
            "Invalid vehicle parameter: thrust_lever_arm must be >= 0 m."
        )


def validate_state(state: VehicleState, parameters: VehicleParameters) -> None:
    if not state.is_finite():
        for field in fields(state):
            value = getattr(state, field.name)
            if not isfinite(value):
                raise DynamicsInvariantError(
                    f"Invalid state: {field.name} must be finite, received {value!r}."
                )
    if state.mass <= 0.0:
        raise DynamicsInvariantError("Invalid state: mass must be > 0 kg.")
    if state.mass < parameters.dry_mass - _MASS_TOLERANCE_KG:
        raise DynamicsInvariantError(
            f"Invalid state: mass={state.mass} kg is below "
            f"dry_mass={parameters.dry_mass} kg."
        )


def validate_actuation(actuation: AppliedActuation) -> None:
    _require_finite("applied throttle", actuation.throttle)
    _require_finite("applied gimbal angle", actuation.gimbal_angle)
    if not 0.0 <= actuation.throttle <= 1.0:
        raise DynamicsInputError(
            "Invalid applied throttle: expected value in [0.0, 1.0], "
            f"received {actuation.throttle}."
        )


def validate_environment(environment: EnvironmentForces) -> None:
    for field in fields(environment):
        _require_finite(f"environment input {field.name}", getattr(environment, field.name))
    if environment.gravity < 0.0:
        raise DynamicsInputError("Invalid environment input: gravity must be >= 0 m/s^2.")


def compute_derivatives(
    state: VehicleState,
    parameters: VehicleParameters,
    actuation: AppliedActuation,
    environment: EnvironmentForces | None = None,
) -> VehicleStateDerivative:
    """Return the instantaneous state derivative without mutating any input."""

    environment = environment or EnvironmentForces()
    validate_parameters(parameters)
    validate_state(state, parameters)
    validate_actuation(actuation)
    validate_environment(environment)

    has_fuel = state.mass > parameters.dry_mass + _MASS_TOLERANCE_KG
    throttle = actuation.throttle if has_fuel else 0.0
    thrust = throttle * parameters.max_thrust
    alpha = state.theta + actuation.gimbal_angle

    thrust_x = thrust * sin(alpha)
    thrust_y = thrust * cos(alpha)
    gimbal_torque = (
        parameters.thrust_lever_arm * thrust * sin(actuation.gimbal_angle)
    )

    return VehicleStateDerivative(
        dx=state.vx,
        dy=state.vy,
        dvx=(thrust_x + environment.force_x) / state.mass,
        dvy=(thrust_y + environment.force_y) / state.mass - environment.gravity,
        dtheta=state.omega,
        domega=(gimbal_torque + environment.torque) / parameters.moment_of_inertia,
        dmass=-throttle * parameters.max_mass_flow_rate,
    )


def enforce_physical_bounds(
    state: VehicleState, parameters: VehicleParameters
) -> VehicleState:
    """Clamp only a tiny integration overshoot at the dry-mass boundary.

    Material invariant violations remain errors so numerical bugs are visible.
    """

    validate_parameters(parameters)
    if not state.is_finite():
        validate_state(state, parameters)
    if state.mass < parameters.dry_mass - _MASS_TOLERANCE_KG:
        raise DynamicsInvariantError(
            f"Post-step mass={state.mass} kg materially crossed "
            f"dry_mass={parameters.dry_mass} kg."
        )
    if state.mass < parameters.dry_mass:
        return replace(state, mass=parameters.dry_mass)
    validate_state(state, parameters)
    return state
