"""Generic tick-scheduled scalar sensor channel."""

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from math import isclose, isfinite

import numpy as np
from numpy.random import Generator

from astraloop.model.measurements import (
    MeasurementMetadata,
    MeasurementStatus,
    SensorName,
)
from astraloop.model.state import VehicleState

TruthReader = Callable[[VehicleState], float]


class SensorError(ValueError):
    """Raised for invalid configuration, truth, or tick ordering."""


@dataclass(frozen=True, slots=True)
class SensorConfig:
    enabled: bool = True
    sample_interval: float = 0.02
    noise_std: float = 0.0
    bias: float = 0.0
    delay: float = 0.0


@dataclass(frozen=True, slots=True)
class SensorSample:
    value: float
    tick: int


@dataclass(frozen=True, slots=True)
class SensorReading:
    value: float | None
    metadata: MeasurementMetadata


def _ticks_for_duration(name: str, duration: float, dt: float, *, allow_zero: bool) -> int:
    if not isfinite(duration) or duration < 0.0 or (not allow_zero and duration == 0.0):
        relation = ">= 0" if allow_zero else "> 0"
        raise SensorError(f"{name} must be finite and {relation} seconds.")
    ratio = duration / dt
    rounded = round(ratio)
    if not isclose(ratio, rounded, rel_tol=1e-10, abs_tol=1e-10):
        raise SensorError(f"{name} must align to an integer number of simulation ticks.")
    return rounded


class ScalarSensor:
    """Stateful scalar sensor with sample/hold, noise, delay, and freeze hooks."""

    def __init__(
        self,
        name: SensorName,
        truth_reader: TruthReader,
        config: SensorConfig,
        dt: float,
        rng: Generator,
    ) -> None:
        if not isfinite(dt) or dt <= 0.0:
            raise SensorError("Sensor dt must be finite and > 0 seconds.")
        if not isfinite(config.noise_std) or config.noise_std < 0.0:
            raise SensorError("Sensor noise_std must be finite and >= 0.")
        if not isfinite(config.bias):
            raise SensorError("Sensor bias must be finite.")
        self.name = name
        self.truth_reader = truth_reader
        self.config = config
        self.dt = dt
        self.rng = rng
        self.sample_every_ticks = _ticks_for_duration(
            "sample_interval", config.sample_interval, dt, allow_zero=False
        )
        self.delay_ticks = _ticks_for_duration("delay", config.delay, dt, allow_zero=True)
        self.additional_bias = 0.0
        self.frozen = False
        self._buffer: deque[SensorSample] = deque()
        self._delivered: SensorSample | None = None
        self._last_tick = -1

    def set_frozen(self, frozen: bool) -> None:
        self.frozen = bool(frozen)

    def set_additional_bias(self, bias: float) -> None:
        if not isfinite(bias):
            raise SensorError("Runtime sensor bias must be finite.")
        self.additional_bias = bias

    def set_delay(self, delay: float) -> None:
        self.delay_ticks = _ticks_for_duration("runtime delay", delay, self.dt, allow_zero=True)

    def update(self, truth: VehicleState, tick: int) -> SensorReading:
        if tick < 0 or tick < self._last_tick:
            raise SensorError("Sensor ticks must be nonnegative and monotonic.")
        self._last_tick = tick
        if not self.config.enabled:
            return self._empty_reading(MeasurementStatus.DISABLED)
        if self.frozen:
            return self._reading_at(tick)

        if tick % self.sample_every_ticks == 0:
            truth_value = self.truth_reader(truth)
            if not isfinite(truth_value):
                raise SensorError(f"{self.name} truth input must be finite.")
            noise = float(self.rng.normal(0.0, self.config.noise_std)) if self.config.noise_std else 0.0
            self._buffer.append(
                SensorSample(truth_value + self.config.bias + self.additional_bias + noise, tick)
            )

        cutoff = tick - self.delay_ticks
        eligible = None
        for sample in self._buffer:
            if sample.tick <= cutoff:
                eligible = sample
            else:
                break
        if eligible is not None:
            self._delivered = eligible
        self._prune_buffer()
        return self._reading_at(tick)

    def _prune_buffer(self) -> None:
        if self._delivered is None:
            return
        while len(self._buffer) > 1 and self._buffer[1].tick <= self._delivered.tick:
            self._buffer.popleft()

    def _reading_at(self, tick: int) -> SensorReading:
        if self._delivered is None:
            return self._empty_reading(MeasurementStatus.UNAVAILABLE)
        age = tick - self._delivered.tick
        stale = age > self.delay_ticks + self.sample_every_ticks
        metadata = MeasurementMetadata(
            source_tick=self._delivered.tick,
            source_time=self._delivered.tick * self.dt,
            age_ticks=age,
            age_seconds=age * self.dt,
            status=MeasurementStatus.STALE if stale else MeasurementStatus.VALID,
        )
        return SensorReading(self._delivered.value, metadata)

    @staticmethod
    def _empty_reading(status: MeasurementStatus) -> SensorReading:
        return SensorReading(None, MeasurementMetadata(None, None, None, None, status))
