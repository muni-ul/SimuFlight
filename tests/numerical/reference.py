"""Independent numerical-reference helpers used only by verification tests."""

from collections.abc import Callable

import numpy as np
from scipy.integrate import solve_ivp

from astraloop.simulation.integrator import rk4_step


def fixed_step(derivative: Callable, initial: np.ndarray, start: float, end: float, dt: float):
    count = round((end - start) / dt)
    if not np.isclose(start + count * dt, end):
        raise ValueError("Verification interval must contain an integer number of steps.")
    times = start + np.arange(count + 1) * dt
    states = [np.asarray(initial, dtype=float)]
    for time in times[:-1]:
        states.append(rk4_step(derivative, states[-1], float(time), dt))
    return times, np.asarray(states)


def scipy_reference(derivative: Callable, initial: np.ndarray, times: np.ndarray):
    solution = solve_ivp(
        derivative,
        (float(times[0]), float(times[-1])),
        initial,
        method="DOP853",
        t_eval=times,
        rtol=1e-12,
        atol=1e-14,
    )
    if not solution.success:
        raise RuntimeError(solution.message)
    return solution.y.T
