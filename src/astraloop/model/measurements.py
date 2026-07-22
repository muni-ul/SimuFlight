"""Controller-facing software-visible measurement types."""

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


class SensorName(StrEnum):
    HORIZONTAL_POSITION = "horizontal_position"
    ALTITUDE = "altimeter"
    HORIZONTAL_VELOCITY = "horizontal_velocity"
    VERTICAL_VELOCITY = "vertical_velocity"
    ATTITUDE = "attitude"
    GYRO = "gyro"


class MeasurementStatus(StrEnum):
    VALID = "valid"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class MeasurementMetadata:
    source_tick: int | None
    source_time: float | None
    age_ticks: int | None
    age_seconds: float | None
    status: MeasurementStatus


@dataclass(frozen=True, slots=True)
class MeasurementSnapshot:
    """Imperfect state visible to flight software; never contains truth state."""

    tick: int
    timestamp: float
    x: float | None
    y: float | None
    vx: float | None
    vy: float | None
    theta: float | None
    omega: float | None
    metadata: Mapping[SensorName, MeasurementMetadata]

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
