"""Mission-profiled throttle and attitude feedback using measurements only."""

from collections.abc import Mapping
from dataclasses import dataclass
from math import isclose, isfinite, pi

from astraloop.control.pid import PID, PIDConfig
from astraloop.mission.modes import MissionMode
from astraloop.model.commands import (
    ControlCommand,
    ControllerStatus,
    ControllerUpdate,
)
from astraloop.model.measurements import (
    MeasurementSnapshot,
    MeasurementStatus,
    SensorName,
)


@dataclass(frozen=True, slots=True)
class ControlProfile:
    target_vertical_velocity: float = 0.0
    target_pitch: float = 0.0
    base_throttle: float = 0.0
    throttle_enabled: bool = False
    attitude_enabled: bool = False


@dataclass(frozen=True, slots=True)
class ControllerConfig:
    throttle_pid: PIDConfig
    attitude_pid: PIDConfig
    control_interval: float


def wrap_angle(angle: float) -> float:
    return (angle + pi) % (2.0 * pi) - pi


class FlightController:
    """Computes desired commands without importing or accepting truth state."""

    def __init__(
        self,
        config: ControllerConfig,
        profiles: Mapping[MissionMode, ControlProfile],
        simulation_dt: float,
    ) -> None:
        ratio = config.control_interval / simulation_dt
        if not isfinite(ratio) or ratio <= 0.0 or not isclose(ratio, round(ratio), abs_tol=1e-10):
            raise ValueError("Controller interval must be a positive integer multiple of simulation dt.")
        missing = set(MissionMode) - set(profiles)
        if missing:
            raise ValueError(f"Missing control profiles for: {sorted(missing)}")
        self.config = config
        self.profiles = dict(profiles)
        self.update_every_ticks = round(ratio)
        self.throttle_pid = PID(config.throttle_pid)
        self.attitude_pid = PID(config.attitude_pid)
        self.last_mode: MissionMode | None = None
        self.last_command = ControlCommand(0.0, 0.0)

    def reset(self) -> None:
        self.throttle_pid.reset()
        self.attitude_pid.reset()
        self.last_command = ControlCommand(0.0, 0.0)

    def update(
        self, measurement: MeasurementSnapshot, mission_mode: MissionMode
    ) -> ControllerUpdate:
        mode_changed = mission_mode != self.last_mode
        if mode_changed:
            self.reset()
            self.last_mode = mission_mode
        profile = self.profiles[mission_mode]
        if not profile.throttle_enabled and not profile.attitude_enabled:
            self.reset()
            return ControllerUpdate(self.last_command, ControllerStatus.INACTIVE)
        if not mode_changed and measurement.tick % self.update_every_ticks != 0:
            return ControllerUpdate(self.last_command, ControllerStatus.HELD)

        required = []
        if profile.throttle_enabled:
            required.append((SensorName.VERTICAL_VELOCITY, measurement.vy))
        if profile.attitude_enabled:
            required.extend(
                [(SensorName.ATTITUDE, measurement.theta), (SensorName.GYRO, measurement.omega)]
            )
        for name, value in required:
            metadata = measurement.metadata[name]
            if value is None or not isfinite(value) or metadata.status is not MeasurementStatus.VALID:
                return ControllerUpdate(
                    self.last_command,
                    ControllerStatus.INVALID_INPUT,
                    f"Required {name.value} measurement is {metadata.status.value}.",
                )

        throttle = 0.0
        if profile.throttle_enabled:
            throttle = self.throttle_pid.update(
                profile.target_vertical_velocity - measurement.vy,
                self.config.control_interval,
                feed_forward=profile.base_throttle,
            ).output
        attitude = 0.0
        if profile.attitude_enabled:
            attitude = self.attitude_pid.update(
                wrap_angle(profile.target_pitch - measurement.theta),
                self.config.control_interval,
                derivative_value=-measurement.omega,
            ).output
        self.last_command = ControlCommand(throttle, attitude)
        return ControllerUpdate(self.last_command, ControllerStatus.OK)
