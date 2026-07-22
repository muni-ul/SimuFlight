"""Deterministic tick-driven simulation lifecycle and RK4 orchestration."""

from collections.abc import Callable
from dataclasses import dataclass
from math import ceil, isclose, isfinite

from astraloop.model.commands import AppliedActuation
from astraloop.model.results import SimulationResult, TerminationReason
from astraloop.model.state import VehicleState
from astraloop.simulation.dynamics import (
    VehicleParameters,
    compute_derivatives,
    enforce_physical_bounds,
    validate_parameters,
    validate_state,
)
from astraloop.simulation.environment import EnvironmentForces
from astraloop.simulation.integrator import (
    IntegrationError,
    derivative_to_vector,
    rk4_step,
    state_to_vector,
    vector_to_state,
)

InputProvider = Callable[[int, float, VehicleState], tuple[AppliedActuation, EnvironmentForces]]
TerminalPredicate = Callable[[int, float, VehicleState], bool]
StepObserver = Callable[[int, float, VehicleState], None]


class SimulationConfigError(ValueError):
    """Raised when numerical runtime configuration is invalid."""


class SimulationError(RuntimeError):
    """Raised when a simulation cannot safely complete its next step."""


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    dt: float
    max_time: float

    def __post_init__(self) -> None:
        if not isfinite(self.dt) or self.dt <= 0.0:
            raise SimulationConfigError("Simulation dt must be finite and > 0 seconds.")
        if not isfinite(self.max_time) or self.max_time <= 0.0:
            raise SimulationConfigError("Simulation max_time must be finite and > 0 seconds.")
        ticks = self.max_time / self.dt
        if not isclose(ticks, round(ticks), rel_tol=1e-12, abs_tol=1e-12):
            raise SimulationConfigError("max_time must be an integer multiple of dt.")

    @property
    def max_ticks(self) -> int:
        return ceil(self.max_time / self.dt)


@dataclass(slots=True)
class SimulationEngine:
    """Owns committed truth state and its authoritative integer simulation tick.

    Future per-tick ordering is: safety, faults, sensors, measurements, mission,
    controller, actuators, integration, invariants, observers, then tick commit.
    Discrete dependencies run once per tick; their physical output is held across
    all four RK4 stages.
    """

    config: SimulationConfig
    parameters: VehicleParameters
    state: VehicleState
    tick: int = 0

    def __post_init__(self) -> None:
        validate_parameters(self.parameters)
        validate_state(self.state, self.parameters)
        if self.tick < 0:
            raise SimulationConfigError("Initial tick must be nonnegative.")

    @property
    def sim_time(self) -> float:
        return self.tick * self.config.dt

    def step(
        self, actuation: AppliedActuation, environment: EnvironmentForces | None = None
    ) -> VehicleState:
        """Atomically advance one tick, committing only a fully valid state."""

        if self.tick >= self.config.max_ticks:
            raise SimulationError("Cannot step beyond configured maximum simulation time.")
        environment = environment or EnvironmentForces()
        committed_state = self.state
        committed_tick = self.tick
        vector = state_to_vector(committed_state)

        def derivative(_time: float, stage_vector):
            stage_state = vector_to_state(stage_vector)
            return derivative_to_vector(
                compute_derivatives(stage_state, self.parameters, actuation, environment)
            )

        try:
            next_vector = rk4_step(derivative, vector, self.sim_time, self.config.dt)
            next_state = enforce_physical_bounds(
                vector_to_state(next_vector), self.parameters
            )
            validate_state(next_state, self.parameters)
        except Exception as exc:
            self.state = committed_state
            self.tick = committed_tick
            if isinstance(exc, SimulationError):
                raise
            raise SimulationError(
                f"Simulation step failed at tick {committed_tick}: {exc}"
            ) from exc

        self.state = next_state
        self.tick = committed_tick + 1
        return self.state

    def run(
        self,
        input_provider: InputProvider,
        terminal: TerminalPredicate | None = None,
        observer: StepObserver | None = None,
    ) -> SimulationResult:
        """Run until a supplied terminal condition or deterministic tick limit."""

        terminal = terminal or (lambda _tick, _time, _state: False)
        while self.tick < self.config.max_ticks:
            if terminal(self.tick, self.sim_time, self.state):
                return self._result(TerminationReason.TERMINAL_CONDITION)
            actuation, environment = input_provider(self.tick, self.sim_time, self.state)
            self.step(actuation, environment)
            if observer is not None:
                observer(self.tick, self.sim_time, self.state)

        return self._result(TerminationReason.MAX_TIME)

    def _result(self, reason: TerminationReason) -> SimulationResult:
        return SimulationResult(
            final_tick=self.tick,
            final_time=self.sim_time,
            final_state=self.state,
            termination_reason=reason,
        )
