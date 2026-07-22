from math import cos, exp, log2, sin

import numpy as np
import pytest

from astraloop.simulation.integrator import rk4_step
from tests.numerical.reference import fixed_step

pytestmark = pytest.mark.numerical


def test_rk4_stage_times_and_states_follow_classical_formula():
    calls = []
    def derivative(time, state):
        calls.append((time, state.copy()))
        return state + time
    base = np.array([2.0])
    rk4_step(derivative, base, 1.0, 0.2)
    assert [call[0] for call in calls] == pytest.approx([1.0, 1.1, 1.1, 1.2])
    assert len(calls) == 4
    assert base == pytest.approx([2.0])


@pytest.mark.parametrize(("rate", "initial"), [(-1.0, 2.0), (0.5, 1.0)])
def test_scalar_exponential_matches_exact_solution(rate, initial):
    _, states = fixed_step(lambda _t, y: rate * y, np.array([initial]), 0.0, 1.0, 0.01)
    assert states[-1, 0] == pytest.approx(initial * exp(rate), rel=1e-8)


def test_time_cubic_derivative_uses_correct_stage_times():
    _, states = fixed_step(lambda time, _y: np.array([time**3]), np.array([3.0]), 0.0, 1.0, 0.1)
    assert states[-1, 0] == pytest.approx(3.25, abs=1e-13)


def test_harmonic_oscillator_matches_exact_phase_state():
    _, states = fixed_step(lambda _t, y: np.array([y[1], -y[0]]), np.array([1.0, 0.0]), 0.0, 2.0, 0.01)
    assert states[-1] == pytest.approx([cos(2.0), -sin(2.0)], rel=1e-8, abs=1e-10)


def test_step_refinement_demonstrates_fourth_order_convergence():
    errors = []
    for dt in (0.2, 0.1, 0.05, 0.025):
        _, states = fixed_step(lambda _t, y: -y, np.array([1.0]), 0.0, 1.0, dt)
        errors.append(abs(states[-1, 0] - exp(-1.0)))
    observed = [log2(coarse / fine) for coarse, fine in zip(errors, errors[1:])]
    assert all(3.7 <= order <= 4.3 for order in observed[-2:])
