"""Stable six-channel sensor-suite construction and snapshot production."""

from collections.abc import Mapping

import numpy as np

from astraloop.model.measurements import MeasurementSnapshot, SensorName
from astraloop.model.state import VehicleState
from astraloop.sensors.models import ScalarSensor, SensorConfig

SENSOR_ORDER = tuple(SensorName)
TRUTH_FIELDS = {
    SensorName.HORIZONTAL_POSITION: "x",
    SensorName.ALTITUDE: "y",
    SensorName.HORIZONTAL_VELOCITY: "vx",
    SensorName.VERTICAL_VELOCITY: "vy",
    SensorName.ATTITUDE: "theta",
    SensorName.GYRO: "omega",
}
SNAPSHOT_FIELDS = {
    SensorName.HORIZONTAL_POSITION: "x",
    SensorName.ALTITUDE: "y",
    SensorName.HORIZONTAL_VELOCITY: "vx",
    SensorName.VERTICAL_VELOCITY: "vy",
    SensorName.ATTITUDE: "theta",
    SensorName.GYRO: "omega",
}


class SensorSuite:
    def __init__(
        self,
        sensors: Mapping[SensorName, ScalarSensor],
        dt: float,
    ) -> None:
        missing = set(SENSOR_ORDER) - set(sensors)
        if missing:
            raise ValueError(f"Sensor suite is missing channels: {sorted(missing)}")
        self.sensors = {name: sensors[name] for name in SENSOR_ORDER}
        self.dt = dt

    @classmethod
    def from_config(
        cls,
        configs: Mapping[SensorName, SensorConfig],
        dt: float,
        seed: int,
    ) -> "SensorSuite":
        seed_sequences = np.random.SeedSequence(seed).spawn(len(SENSOR_ORDER))
        sensors: dict[SensorName, ScalarSensor] = {}
        for name, sequence in zip(SENSOR_ORDER, seed_sequences, strict=True):
            field = TRUTH_FIELDS[name]
            sensors[name] = ScalarSensor(
                name,
                lambda state, field=field: getattr(state, field),
                configs[name],
                dt,
                np.random.default_rng(sequence),
            )
        return cls(sensors, dt)

    def sample(self, truth: VehicleState, tick: int) -> MeasurementSnapshot:
        readings = {name: self.sensors[name].update(truth, tick) for name in SENSOR_ORDER}
        values = {
            SNAPSHOT_FIELDS[name]: reading.value for name, reading in readings.items()
        }
        return MeasurementSnapshot(
            tick=tick,
            timestamp=tick * self.dt,
            metadata={name: reading.metadata for name, reading in readings.items()},
            **values,
        )

    def __getitem__(self, name: SensorName) -> ScalarSensor:
        return self.sensors[name]
