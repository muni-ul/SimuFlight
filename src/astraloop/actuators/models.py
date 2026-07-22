"""Bounded first-order throttle and gimbal actuator dynamics."""

from dataclasses import dataclass
from math import exp, isfinite

from astraloop.model.commands import (
    ActuatorState,
    ActuatorUpdate,
    AppliedActuation,
    ControlCommand,
)


@dataclass(frozen=True, slots=True)
class ActuatorConfig:
    min_throttle: float = 0.0
    max_throttle: float = 1.0
    gimbal_limit: float = 0.17453292519943295
    throttle_tau: float = 0.15
    gimbal_tau: float = 0.08
    throttle_max_rate: float | None = None
    gimbal_max_rate: float | None = None

    def __post_init__(self) -> None:
        numeric = (
            self.min_throttle, self.max_throttle, self.gimbal_limit,
            self.throttle_tau, self.gimbal_tau,
        )
        if not all(isfinite(value) for value in numeric):
            raise ValueError("Actuator configuration values must be finite.")
        if not 0.0 <= self.min_throttle <= self.max_throttle <= 1.0:
            raise ValueError("Throttle bounds must satisfy 0 <= min <= max <= 1.")
        if self.gimbal_limit < 0.0 or self.throttle_tau < 0.0 or self.gimbal_tau < 0.0:
            raise ValueError("Gimbal limit and actuator time constants cannot be negative.")
        for name, rate in (("throttle_max_rate", self.throttle_max_rate), ("gimbal_max_rate", self.gimbal_max_rate)):
            if rate is not None and (not isfinite(rate) or rate <= 0.0):
                raise ValueError(f"{name} must be finite and > 0 when enabled.")


@dataclass(frozen=True, slots=True)
class ActuatorDegradation:
    lag_multiplier: float = 1.0
    authority_scale: float = 1.0
    rate_scale: float = 1.0

    def __post_init__(self) -> None:
        if not all(isfinite(v) for v in (self.lag_multiplier, self.authority_scale, self.rate_scale)):
            raise ValueError("Actuator degradation values must be finite.")
        if self.lag_multiplier <= 0.0 or not 0.0 <= self.authority_scale <= 1.0 or self.rate_scale < 0.0:
            raise ValueError("Lag multiplier must be > 0, authority scale in [0,1], and rate scale >= 0.")


def _clamp(value: float, lower: float, upper: float) -> float:
    return min(upper, max(lower, value))


def _lag(current: float, target: float, tau: float, dt: float) -> float:
    if tau == 0.0:
        return target
    return current + (1.0 - exp(-dt / tau)) * (target - current)


def _rate_limit(current: float, candidate: float, rate: float | None, dt: float) -> tuple[float, bool]:
    if rate is None:
        return candidate, False
    max_delta = rate * dt
    delta = candidate - current
    limited = _clamp(delta, -max_delta, max_delta)
    return current + limited, limited != delta


class ActuatorModel:
    def __init__(self, config: ActuatorConfig, state: ActuatorState | None = None) -> None:
        self.config = config
        self.state = state or ActuatorState()
        self.degradation = ActuatorDegradation()
        self._validate_state(self.state)

    def set_degradation(self, degradation: ActuatorDegradation) -> None:
        if self.config.max_throttle * degradation.authority_scale < self.config.min_throttle:
            raise ValueError("Degraded throttle authority cannot fall below min_throttle.")
        self.degradation = degradation

    def update(self, command: ControlCommand, dt: float) -> ActuatorUpdate:
        if not isfinite(dt) or dt <= 0.0:
            raise ValueError("Actuator dt must be finite and > 0.")
        if not isfinite(command.throttle) or not isfinite(command.attitude_command):
            raise ValueError("Actuator command values must be finite.")
        self._validate_state(self.state)
        degradation = self.degradation
        max_throttle = self.config.max_throttle * degradation.authority_scale
        gimbal_limit = self.config.gimbal_limit * degradation.authority_scale
        throttle_target = _clamp(command.throttle, self.config.min_throttle, max_throttle)
        gimbal_target = _clamp(command.attitude_command, -gimbal_limit, gimbal_limit)
        throttle_candidate = _lag(
            self.state.throttle, throttle_target,
            self.config.throttle_tau * degradation.lag_multiplier, dt,
        )
        gimbal_candidate = _lag(
            self.state.gimbal_angle, gimbal_target,
            self.config.gimbal_tau * degradation.lag_multiplier, dt,
        )
        throttle_rate = None if self.config.throttle_max_rate is None else self.config.throttle_max_rate * degradation.rate_scale
        gimbal_rate = None if self.config.gimbal_max_rate is None else self.config.gimbal_max_rate * degradation.rate_scale
        throttle, throttle_limited = _rate_limit(self.state.throttle, throttle_candidate, throttle_rate, dt)
        gimbal, gimbal_limited = _rate_limit(self.state.gimbal_angle, gimbal_candidate, gimbal_rate, dt)
        next_state = ActuatorState(
            _clamp(throttle, self.config.min_throttle, max_throttle),
            _clamp(gimbal, -gimbal_limit, gimbal_limit),
        )
        self._validate_state(next_state)
        self.state = next_state
        return ActuatorUpdate(
            state=next_state,
            throttle_target=throttle_target,
            gimbal_target=gimbal_target,
            throttle_saturated=throttle_target != command.throttle,
            gimbal_saturated=gimbal_target != command.attitude_command,
            throttle_rate_limited=throttle_limited,
            gimbal_rate_limited=gimbal_limited,
            degraded=degradation != ActuatorDegradation(),
        )

    def applied(self) -> AppliedActuation:
        return AppliedActuation(self.state.throttle, self.state.gimbal_angle)

    @staticmethod
    def _validate_state(state: ActuatorState) -> None:
        if not isfinite(state.throttle) or not isfinite(state.gimbal_angle):
            raise ValueError("Actuator state must be finite.")
