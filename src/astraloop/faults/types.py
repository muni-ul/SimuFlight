"""Immutable typed fault definitions and composed effect snapshots."""

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from types import MappingProxyType
from typing import Mapping, TypeAlias

from astraloop.model.measurements import SensorName


class FaultType(StrEnum):
    SENSOR_FREEZE = "sensor_freeze"
    SENSOR_BIAS = "sensor_bias"
    SENSOR_DELAY = "sensor_delay"
    ACTUATOR_DEGRADATION = "actuator_degradation"


class FaultStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"


class ActuatorName(StrEnum):
    THROTTLE = "throttle"
    GIMBAL = "gimbal"
    ALL = "all"


@dataclass(frozen=True, slots=True)
class FaultTiming:
    activation_tick: int
    deactivation_tick: int | None = None

    def __post_init__(self) -> None:
        if self.activation_tick < 0:
            raise ValueError("Fault activation tick must be nonnegative.")
        if self.deactivation_tick is not None and self.deactivation_tick <= self.activation_tick:
            raise ValueError("Fault deactivation tick must follow activation tick.")


def _validate_id(fault_id: str) -> None:
    if not fault_id.strip():
        raise ValueError("Fault id cannot be empty.")


@dataclass(frozen=True, slots=True)
class SensorFreezeFault:
    id: str
    target: SensorName
    timing: FaultTiming
    type: FaultType = field(default=FaultType.SENSOR_FREEZE, init=False)

    def __post_init__(self) -> None:
        _validate_id(self.id)


@dataclass(frozen=True, slots=True)
class SensorBiasFault:
    id: str
    target: SensorName
    timing: FaultTiming
    bias: float
    type: FaultType = field(default=FaultType.SENSOR_BIAS, init=False)

    def __post_init__(self) -> None:
        _validate_id(self.id)
        if not isfinite(self.bias) or self.bias == 0.0:
            raise ValueError("Sensor fault bias must be finite and nonzero.")


@dataclass(frozen=True, slots=True)
class SensorDelayFault:
    id: str
    target: SensorName
    timing: FaultTiming
    delay: float
    type: FaultType = field(default=FaultType.SENSOR_DELAY, init=False)

    def __post_init__(self) -> None:
        _validate_id(self.id)
        if not isfinite(self.delay) or self.delay <= 0.0:
            raise ValueError("Sensor fault delay must be finite and > 0.")


@dataclass(frozen=True, slots=True)
class ActuatorDegradationFault:
    id: str
    target: ActuatorName
    timing: FaultTiming
    lag_multiplier: float = 1.0
    authority_scale: float = 1.0
    rate_scale: float = 1.0
    type: FaultType = field(default=FaultType.ACTUATOR_DEGRADATION, init=False)

    def __post_init__(self) -> None:
        _validate_id(self.id)
        values = (self.lag_multiplier, self.authority_scale, self.rate_scale)
        if not all(isfinite(value) for value in values):
            raise ValueError("Actuator fault values must be finite.")
        if self.lag_multiplier < 1.0 or not 0.0 <= self.authority_scale <= 1.0 or not 0.0 <= self.rate_scale <= 1.0:
            raise ValueError("Invalid actuator degradation parameters.")
        if values == (1.0, 1.0, 1.0):
            raise ValueError("Actuator degradation must change at least one parameter.")


FaultDefinition: TypeAlias = SensorFreezeFault | SensorBiasFault | SensorDelayFault | ActuatorDegradationFault


@dataclass(frozen=True, slots=True)
class SensorFaultEffect:
    frozen: bool = False
    additional_bias: float = 0.0
    delay_override: float | None = None


@dataclass(frozen=True, slots=True)
class ActuatorFaultEffect:
    lag_multiplier: float = 1.0
    authority_scale: float = 1.0
    rate_scale: float = 1.0


@dataclass(frozen=True, slots=True)
class FaultEffects:
    sensors: Mapping[SensorName, SensorFaultEffect]
    actuator: ActuatorFaultEffect
    active_fault_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "sensors", MappingProxyType(dict(self.sensors)))
