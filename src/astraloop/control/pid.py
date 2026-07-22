"""Reusable deterministic PID with conditional anti-windup."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class PIDConfig:
    kp: float
    ki: float
    kd: float
    output_min: float
    output_max: float
    integral_min: float
    integral_max: float

    def __post_init__(self) -> None:
        values = (
            self.kp, self.ki, self.kd, self.output_min, self.output_max,
            self.integral_min, self.integral_max,
        )
        if not all(isfinite(value) for value in values):
            raise ValueError("PID configuration values must be finite.")
        if self.output_min > self.output_max:
            raise ValueError("PID output_min cannot exceed output_max.")
        if self.integral_min > self.integral_max:
            raise ValueError("PID integral_min cannot exceed integral_max.")


@dataclass(frozen=True, slots=True)
class PIDResult:
    output: float
    proportional: float
    integral: float
    derivative: float
    saturated: bool


class PID:
    def __init__(self, config: PIDConfig) -> None:
        self.config = config
        self.integral = 0.0
        self.previous_error: float | None = None

    def reset(self) -> None:
        self.integral = 0.0
        self.previous_error = None

    def update(
        self,
        error: float,
        dt: float,
        *,
        derivative_value: float | None = None,
        feed_forward: float = 0.0,
    ) -> PIDResult:
        if not isfinite(error) or not isfinite(dt) or dt <= 0.0 or not isfinite(feed_forward):
            raise ValueError("PID error/feed-forward must be finite and dt must be > 0.")
        if derivative_value is not None and not isfinite(derivative_value):
            raise ValueError("PID derivative input must be finite.")
        candidate = min(
            self.config.integral_max,
            max(self.config.integral_min, self.integral + error * dt),
        )
        derivative = derivative_value if derivative_value is not None else (
            0.0 if self.previous_error is None else (error - self.previous_error) / dt
        )
        p_term = self.config.kp * error
        d_term = self.config.kd * derivative
        raw = feed_forward + p_term + self.config.ki * candidate + d_term
        saturated_high = raw > self.config.output_max
        saturated_low = raw < self.config.output_min
        if not ((saturated_high and error > 0.0) or (saturated_low and error < 0.0)):
            self.integral = candidate
        raw = feed_forward + p_term + self.config.ki * self.integral + d_term
        output = min(self.config.output_max, max(self.config.output_min, raw))
        self.previous_error = error
        return PIDResult(output, p_term, self.config.ki * self.integral, d_term, output != raw)
