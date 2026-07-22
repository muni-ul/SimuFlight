"""Deterministic measurement-driven flight-software mission state machine."""

from dataclasses import dataclass
from math import isfinite

from astraloop.mission.modes import LEGAL_TRANSITIONS, TERMINAL_MODES, MissionMode
from astraloop.model.events import MissionTransitionEvent
from astraloop.model.measurements import MeasurementSnapshot, MeasurementStatus, SensorName


class MissionTransitionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MissionConfig:
    prelaunch_hold_ticks: int = 10
    ascent_cutoff_altitude: float = 100.0
    descent_entry_velocity: float = -0.25
    landing_entry_altitude: float = 30.0
    landed_altitude: float = 0.25
    transition_confirmation_ticks: int = 3
    critical_invalid_ticks: int = 10

    def __post_init__(self) -> None:
        if self.prelaunch_hold_ticks < 0 or self.transition_confirmation_ticks <= 0 or self.critical_invalid_ticks <= 0:
            raise ValueError("Mission tick thresholds must be nonnegative/positive as appropriate.")
        thresholds = (
            self.ascent_cutoff_altitude, self.descent_entry_velocity,
            self.landing_entry_altitude, self.landed_altitude,
        )
        if not all(isfinite(value) for value in thresholds):
            raise ValueError("Mission thresholds must be finite.")
        if self.descent_entry_velocity >= 0.0:
            raise ValueError("descent_entry_velocity must be negative.")
        if not 0.0 <= self.landed_altitude < self.landing_entry_altitude < self.ascent_cutoff_altitude:
            raise ValueError("Mission altitude thresholds must be strictly ordered.")


@dataclass(frozen=True, slots=True)
class MissionContext:
    tick: int
    dt: float
    abort_requested: bool = False
    abort_reason: str | None = None


@dataclass(frozen=True, slots=True)
class MissionUpdate:
    previous_state: MissionMode
    current_state: MissionMode
    changed: bool
    reason: str | None = None
    event: MissionTransitionEvent | None = None

    @property
    def is_terminal(self) -> bool:
        return self.current_state in TERMINAL_MODES


CRITICAL_SENSORS = (
    SensorName.ALTITUDE,
    SensorName.VERTICAL_VELOCITY,
    SensorName.ATTITUDE,
    SensorName.GYRO,
)


class MissionStateMachine:
    def __init__(
        self,
        config: MissionConfig,
        initial_state: MissionMode = MissionMode.PRELAUNCH,
        entered_tick: int = 0,
    ) -> None:
        if entered_tick < 0:
            raise ValueError("Mission entered_tick must be nonnegative.")
        self.config = config
        self.state = initial_state
        self.entered_tick = entered_tick
        self._guard_count = 0
        self._critical_invalid_count = 0

    def update(self, measurement: MeasurementSnapshot, context: MissionContext) -> MissionUpdate:
        if context.tick < 0 or not isfinite(context.dt) or context.dt <= 0.0:
            raise ValueError("Mission context requires nonnegative tick and positive finite dt.")
        previous = self.state
        if previous in TERMINAL_MODES:
            return MissionUpdate(previous, previous, False)
        if context.abort_requested:
            return self._transition(
                MissionMode.ABORT, context, "abort_requested",
                context.abort_reason or "External abort requested.",
            )
        if previous is not MissionMode.PRELAUNCH and self._critical_inputs_invalid(measurement):
            self._critical_invalid_count += 1
        else:
            self._critical_invalid_count = 0
        if self._critical_invalid_count >= self.config.critical_invalid_ticks:
            return self._transition(
                MissionMode.ABORT, context, "critical_measurement_invalid",
                "Critical measurements remained invalid.",
            )

        target, reason, message, guard = self._nominal_guard(measurement, context)
        if target is None:
            self._guard_count = 0
            return MissionUpdate(previous, previous, False)
        self._guard_count = self._guard_count + 1 if guard else 0
        required = 1 if previous is MissionMode.PRELAUNCH else self.config.transition_confirmation_ticks
        if self._guard_count < required:
            return MissionUpdate(previous, previous, False)
        return self._transition(target, context, reason, message)

    def transition(self, target: MissionMode, context: MissionContext, reason: str) -> MissionUpdate:
        return self._transition(target, context, reason, reason.replace("_", " ").capitalize())

    def _nominal_guard(self, m: MeasurementSnapshot, c: MissionContext):
        if self.state is MissionMode.PRELAUNCH:
            ready = not self._critical_inputs_invalid(m)
            return MissionMode.ASCENT, "prelaunch_complete", "Prelaunch hold and sensor readiness complete.", ready and c.tick - self.entered_tick >= self.config.prelaunch_hold_ticks
        if self._critical_inputs_invalid(m):
            return None, None, None, False
        if self.state is MissionMode.ASCENT:
            return MissionMode.COAST, "ascent_altitude_reached", "Measured ascent objective reached.", m.y >= self.config.ascent_cutoff_altitude and m.vy > 0.0
        if self.state is MissionMode.COAST:
            return MissionMode.DESCENT, "descent_confirmed", "Measured descent confirmed after apex.", m.vy <= self.config.descent_entry_velocity
        if self.state is MissionMode.DESCENT:
            return MissionMode.LANDING, "landing_phase_altitude_reached", "Measured altitude entered landing phase.", m.y <= self.config.landing_entry_altitude and m.vy < 0.0
        if self.state is MissionMode.LANDING:
            return MissionMode.LANDED, "landing_contact_confirmed", "Measured near-ground contact confirmed.", m.y <= self.config.landed_altitude and m.vy <= 0.25
        return None, None, None, False

    def _critical_inputs_invalid(self, measurement: MeasurementSnapshot) -> bool:
        values = {
            SensorName.ALTITUDE: measurement.y,
            SensorName.VERTICAL_VELOCITY: measurement.vy,
            SensorName.ATTITUDE: measurement.theta,
            SensorName.GYRO: measurement.omega,
        }
        return any(
            values[name] is None
            or not isfinite(values[name])
            or measurement.metadata[name].status is not MeasurementStatus.VALID
            for name in CRITICAL_SENSORS
        )

    def _transition(
        self, target: MissionMode, context: MissionContext, reason: str, message: str
    ) -> MissionUpdate:
        previous = self.state
        if target not in LEGAL_TRANSITIONS[previous]:
            raise MissionTransitionError(f"Illegal mission transition: {previous} -> {target}.")
        event = MissionTransitionEvent(
            context.tick, context.tick * context.dt, previous, target, reason, message
        )
        self.state = target
        self.entered_tick = context.tick
        self._guard_count = 0
        self._critical_invalid_count = 0
        return MissionUpdate(previous, target, True, reason, event)
