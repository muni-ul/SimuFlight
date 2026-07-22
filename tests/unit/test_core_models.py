from math import pi

import numpy as np
import pytest

from astraloop.actuators.models import ActuatorConfig, ActuatorModel
from astraloop.control.pid import PID, PIDConfig
from astraloop.model.commands import ControlCommand, AppliedActuation
from astraloop.model.state import VehicleState
from astraloop.simulation.dynamics import VehicleParameters, compute_derivatives
from astraloop.simulation.environment import EnvironmentForces
from astraloop.simulation.integrator import rk4_step, state_to_vector, vector_to_state


def state(**overrides):
    values = dict(x=0.0, y=100.0, vx=0.0, vy=0.0, theta=0.0, omega=0.0, mass=1000.0)
    values.update(overrides)
    return VehicleState(**values)


def parameters():
    return VehicleParameters(900.0, 15000.0, 5.0, 4000.0, 2.0)


def test_zero_throttle_produces_gravity_only():
    derivative = compute_derivatives(state(), parameters(), AppliedActuation(0.0, 0.0), EnvironmentForces())
    assert derivative.dvx == pytest.approx(0.0)
    assert derivative.dvy == pytest.approx(-9.80665)
    assert derivative.dmass == 0.0


def test_positive_pitch_creates_positive_horizontal_acceleration():
    derivative = compute_derivatives(state(theta=pi / 12), parameters(), AppliedActuation(1.0, 0.0))
    assert derivative.dvx > 0.0


def test_state_vector_round_trip():
    original = state(vx=3.0, omega=-0.2)
    assert vector_to_state(state_to_vector(original)) == original


def test_rk4_constant_derivative_is_exact():
    result = rk4_step(lambda _time, value: np.full_like(value, 3.0), np.array([1.0]), 0.0, 0.2)
    assert result == pytest.approx([1.6])


def test_pid_conditional_anti_windup_holds_integral_at_upper_saturation():
    pid = PID(PIDConfig(2.0, 1.0, 0.0, 0.0, 1.0, -10.0, 10.0))
    pid.update(10.0, 1.0)
    assert pid.integral == 0.0


def test_actuator_lag_separates_requested_from_applied():
    model = ActuatorModel(ActuatorConfig(throttle_tau=0.2, gimbal_tau=0.1))
    update = model.update(ControlCommand(1.0, 0.0), 0.02)
    assert 0.0 < update.state.throttle < 1.0
