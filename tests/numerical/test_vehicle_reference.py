import numpy as np
import pytest

from astraloop.model.commands import AppliedActuation
from astraloop.model.state import VehicleState
from astraloop.simulation.dynamics import VehicleParameters, compute_derivatives
from astraloop.simulation.environment import EnvironmentForces
from astraloop.simulation.integrator import derivative_to_vector, state_to_vector, vector_to_state
from tests.numerical.reference import fixed_step, scipy_reference

pytestmark = pytest.mark.numerical


def rhs(parameters, actuation, environment):
    def derivative(_time, vector):
        return derivative_to_vector(compute_derivatives(vector_to_state(vector), parameters, actuation, environment))
    return derivative


def test_gravity_only_vehicle_matches_analytical_solution():
    initial = VehicleState(2.0, 100.0, 3.0, 4.0, 0.1, 0.2, 1200.0)
    parameters = VehicleParameters(900.0, 18000.0, 0.0, 4500.0, 2.0)
    times, states = fixed_step(rhs(parameters, AppliedActuation(0.0, 0.0), EnvironmentForces()), state_to_vector(initial), 0.0, 1.0, 0.02)
    expected = np.array([5.0, 100.0 + 4.0 - 0.5 * 9.80665, 3.0, 4.0 - 9.80665, 0.3, 0.2, 1200.0])
    assert states[-1] == pytest.approx(expected, rel=1e-11, abs=1e-11)


def test_fixed_gimbal_vehicle_matches_high_accuracy_scipy_reference():
    initial = VehicleState(0.0, 500.0, 0.0, 0.0, 0.0, 0.0, 1200.0)
    parameters = VehicleParameters(900.0, 18000.0, 2.0, 4500.0, 2.0)
    derivative = rhs(parameters, AppliedActuation(0.65, 0.025), EnvironmentForces())
    times, custom = fixed_step(derivative, state_to_vector(initial), 0.0, 3.0, 0.02)
    reference = scipy_reference(derivative, state_to_vector(initial), times)
    tolerances = np.array([2e-5, 2e-5, 2e-5, 2e-5, 2e-6, 2e-6, 1e-9])
    errors = np.max(np.abs(custom - reference), axis=0)
    assert np.all(errors <= tolerances), f"component errors={errors}, tolerances={tolerances}"


def test_production_timestep_refines_toward_reference():
    initial = VehicleState(0.0, 500.0, 0.0, 0.0, 0.0, 0.0, 1200.0)
    parameters = VehicleParameters(900.0, 18000.0, 2.0, 4500.0, 2.0)
    derivative = rhs(parameters, AppliedActuation(0.65, 0.02), EnvironmentForces())
    errors = []
    for dt in (0.02, 0.01, 0.005):
        times, custom = fixed_step(derivative, state_to_vector(initial), 0.0, 2.0, dt)
        reference = scipy_reference(derivative, state_to_vector(initial), times)
        errors.append(float(np.max(np.abs(custom[-1] - reference[-1]))))
    assert errors[2] < errors[1] < errors[0]
