"""Strict local TOML scenario loader and unit resolver."""

from difflib import get_close_matches
from math import isclose, isfinite, radians
from pathlib import Path
import re
import tomllib

from astraloop.actuators.models import ActuatorConfig
from astraloop.config.schema import ExpectedOutcome, ResolvedScenarioConfig, ValidationConfig
from astraloop.control.flight_controller import ControlProfile, ControllerConfig
from astraloop.control.pid import PIDConfig
from astraloop.faults.types import (
    ActuatorDegradationFault, ActuatorName, FaultTiming, SensorBiasFault,
    SensorDelayFault, SensorFreezeFault,
)
from astraloop.mission.modes import MissionMode
from astraloop.mission.state_machine import MissionConfig
from astraloop.model.measurements import SensorName
from astraloop.model.state import VehicleState
from astraloop.sensors.models import SensorConfig
from astraloop.simulation.dynamics import (
    VehicleParameters,
    validate_environment,
    validate_parameters,
    validate_state,
)
from astraloop.simulation.engine import SimulationConfig
from astraloop.simulation.environment import EnvironmentForces


class ConfigError(ValueError):
    def __init__(self, source: Path, field: str, message: str) -> None:
        super().__init__(f"{source} [{field}]: {message}")


def _table(raw: dict, key: str, source: Path) -> dict:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ConfigError(source, key, "required TOML table is missing.")
    return value


def _strict(table: dict, allowed: set[str], source: Path, field: str) -> None:
    unknown = set(table) - allowed
    if unknown:
        key = sorted(unknown)[0]
        suggestion = get_close_matches(key, allowed, n=1)
        suffix = f"; did you mean '{suggestion[0]}'?" if suggestion else ""
        raise ConfigError(source, field, f"unknown key '{key}'{suffix}")


def _number(table: dict, key: str, source: Path, field: str) -> float:
    value = table.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(source, f"{field}.{key}", "expected a number.")
    return float(value)


def _boolean(table: dict, key: str, source: Path, field: str) -> bool:
    value = table.get(key)
    if not isinstance(value, bool):
        raise ConfigError(source, f"{field}.{key}", "expected a boolean.")
    return value


def _ticks(seconds: float, dt: float, source: Path, field: str) -> int:
    ratio = seconds / dt
    if not isclose(ratio, round(ratio), rel_tol=1e-10, abs_tol=1e-10):
        raise ConfigError(source, field, "time must align to an integer simulation tick.")
    return round(ratio)


def _validate_cross_fields(config: ResolvedScenarioConfig, source: Path) -> None:
    try:
        validate_parameters(config.vehicle)
        validate_state(config.initial_state, config.vehicle)
        validate_environment(config.environment)
    except ValueError as exc:
        raise ConfigError(source, "resolved", str(exc)) from exc

    sensors = config.sensor_mapping()
    for name, sensor in sensors.items():
        if not isfinite(sensor.sample_interval) or sensor.sample_interval <= 0.0:
            raise ConfigError(source, f"sensors.{name.value}.sample_interval_s", "must be finite and positive.")
        if not isfinite(sensor.delay) or sensor.delay < 0.0:
            raise ConfigError(source, f"sensors.{name.value}.delay_s", "must be finite and nonnegative.")
        if not isfinite(sensor.noise_std) or sensor.noise_std < 0.0:
            raise ConfigError(source, f"sensors.{name.value}.noise_std", "must be finite and nonnegative.")
        if not isfinite(sensor.bias):
            raise ConfigError(source, f"sensors.{name.value}.bias", "must be finite.")
        _ticks(sensor.sample_interval, config.simulation.dt, source, f"sensors.{name.value}.sample_interval_s")
        _ticks(sensor.delay, config.simulation.dt, source, f"sensors.{name.value}.delay_s")

    if not isfinite(config.controller.control_interval) or config.controller.control_interval <= 0.0:
        raise ConfigError(source, "controller.update_interval_s", "must be finite and positive.")
    _ticks(config.controller.control_interval, config.simulation.dt, source, "controller.update_interval_s")
    for fault in config.faults:
        if fault.timing.activation_tick >= config.simulation.max_ticks:
            raise ConfigError(source, f"faults.{fault.id}.activation_time_s", "must occur before max_time.")
        target = getattr(fault, "target", None)
        if isinstance(target, SensorName) and not sensors[target].enabled:
            raise ConfigError(source, f"faults.{fault.id}.target", "cannot target a disabled sensor.")
        if isinstance(fault, SensorDelayFault) and fault.delay <= sensors[fault.target].delay:
            raise ConfigError(source, f"faults.{fault.id}.delay_s", "must exceed the nominal sensor delay.")


def _pid(raw: dict, source: Path, field: str, degrees_output: bool = False) -> PIDConfig:
    allowed = {"kp", "ki", "kd", "output_min", "output_max", "integral_min", "integral_max"}
    _strict(raw, allowed, source, field)
    scale = radians(1.0) if degrees_output else 1.0
    return PIDConfig(
        _number(raw, "kp", source, field), _number(raw, "ki", source, field),
        _number(raw, "kd", source, field), _number(raw, "output_min", source, field) * scale,
        _number(raw, "output_max", source, field) * scale,
        _number(raw, "integral_min", source, field), _number(raw, "integral_max", source, field),
    )


def load_scenario(path: str | Path) -> ResolvedScenarioConfig:
    source = Path(path).resolve()
    if source.suffix.lower() != ".toml" or not source.is_file():
        raise ConfigError(source, "file", "expected an existing .toml scenario file.")
    try:
        with source.open("rb") as stream:
            raw = tomllib.load(stream)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(source, "file", f"invalid TOML: {exc}") from exc
    top = {"schema_version", "id", "description", "seed", "dt", "max_time", "initial_state", "vehicle", "environment", "sensors", "controller", "actuators", "mission", "validation", "faults"}
    _strict(raw, top, source, "root")
    if raw.get("schema_version") != 1:
        raise ConfigError(source, "schema_version", "only schema version 1 is supported.")
    scenario_id = raw.get("id")
    if not isinstance(scenario_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", scenario_id):
        raise ConfigError(source, "id", "expected a lowercase scenario slug.")
    if source.parent.name == "scenarios" and source.stem != scenario_id:
        raise ConfigError(source, "id", "bundled file stem must match scenario id.")
    description = raw.get("description")
    seed = raw.get("seed")
    if not isinstance(description, str) or not description.strip():
        raise ConfigError(source, "description", "must be a non-empty string.")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2**64 - 1:
        raise ConfigError(source, "seed", "must be an unsigned 64-bit integer.")
    dt = _number(raw, "dt", source, "root")
    max_time = _number(raw, "max_time", source, "root")
    simulation = SimulationConfig(dt, max_time)

    state_raw = _table(raw, "initial_state", source)
    state_keys = {"x_m", "y_m", "vx_m_s", "vy_m_s", "theta_deg", "omega_deg_s", "mass_kg"}
    _strict(state_raw, state_keys, source, "initial_state")
    initial_state = VehicleState(*[_number(state_raw, key, source, "initial_state") for key in ("x_m", "y_m", "vx_m_s", "vy_m_s")], radians(_number(state_raw, "theta_deg", source, "initial_state")), radians(_number(state_raw, "omega_deg_s", source, "initial_state")), _number(state_raw, "mass_kg", source, "initial_state"))

    vehicle_raw = _table(raw, "vehicle", source)
    vehicle_order = ("dry_mass_kg", "max_thrust_n", "max_mass_flow_rate_kg_s", "moment_of_inertia_kg_m2", "thrust_lever_arm_m")
    _strict(vehicle_raw, set(vehicle_order), source, "vehicle")
    vehicle = VehicleParameters(*[_number(vehicle_raw, key, source, "vehicle") for key in vehicle_order])
    environment_raw = _table(raw, "environment", source)
    _strict(environment_raw, {"gravity_m_s2"}, source, "environment")
    environment = EnvironmentForces(_number(environment_raw, "gravity_m_s2", source, "environment"))

    sensors_raw = _table(raw, "sensors", source)
    if set(sensors_raw) != {name.value for name in SensorName}:
        raise ConfigError(source, "sensors", "all six exact sensor tables are required.")
    sensor_items = []
    for name in SensorName:
        item = sensors_raw[name.value]
        _strict(item, {"enabled", "sample_interval_s", "noise_std", "bias", "delay_s"}, source, f"sensors.{name.value}")
        enabled = _boolean(item, "enabled", source, f"sensors.{name.value}")
        sensor_items.append((name, SensorConfig(enabled, _number(item, "sample_interval_s", source, f"sensors.{name.value}"), _number(item, "noise_std", source, f"sensors.{name.value}"), _number(item, "bias", source, f"sensors.{name.value}"), _number(item, "delay_s", source, f"sensors.{name.value}"))))

    controller_raw = _table(raw, "controller", source)
    _strict(controller_raw, {"update_interval_s", "throttle_pid", "attitude_pid", "profiles"}, source, "controller")
    controller = ControllerConfig(_pid(_table(controller_raw, "throttle_pid", source), source, "controller.throttle_pid"), _pid(_table(controller_raw, "attitude_pid", source), source, "controller.attitude_pid", True), _number(controller_raw, "update_interval_s", source, "controller"))
    profiles_raw = _table(controller_raw, "profiles", source)
    if set(profiles_raw) != {mode.value for mode in MissionMode}:
        raise ConfigError(source, "controller.profiles", "profiles for every mission mode are required.")
    profiles = []
    for mode in MissionMode:
        item = profiles_raw[mode.value]
        keys = {"target_vertical_velocity_m_s", "target_pitch_deg", "base_throttle", "throttle_enabled", "attitude_enabled"}
        _strict(item, keys, source, f"controller.profiles.{mode.value}")
        profiles.append((mode, ControlProfile(_number(item, "target_vertical_velocity_m_s", source, mode.value), radians(_number(item, "target_pitch_deg", source, mode.value)), _number(item, "base_throttle", source, mode.value), _boolean(item, "throttle_enabled", source, f"controller.profiles.{mode.value}"), _boolean(item, "attitude_enabled", source, f"controller.profiles.{mode.value}"))))

    actuator_raw = _table(raw, "actuators", source)
    _strict(actuator_raw, {"min_throttle", "max_throttle", "gimbal_limit_deg", "throttle_tau_s", "gimbal_tau_s", "throttle_max_rate", "gimbal_max_rate_deg_s"}, source, "actuators")
    actuators = ActuatorConfig(_number(actuator_raw, "min_throttle", source, "actuators"), _number(actuator_raw, "max_throttle", source, "actuators"), radians(_number(actuator_raw, "gimbal_limit_deg", source, "actuators")), _number(actuator_raw, "throttle_tau_s", source, "actuators"), _number(actuator_raw, "gimbal_tau_s", source, "actuators"), actuator_raw.get("throttle_max_rate"), radians(float(actuator_raw["gimbal_max_rate_deg_s"])) if actuator_raw.get("gimbal_max_rate_deg_s") is not None else None)

    mission_raw = _table(raw, "mission", source)
    mission_keys = {"prelaunch_hold_s", "ascent_cutoff_altitude_m", "descent_entry_velocity_m_s", "landing_entry_altitude_m", "landed_altitude_threshold_m", "transition_confirmation_ticks", "abort_invalid_confirm_ticks"}
    _strict(mission_raw, mission_keys, source, "mission")
    mission = MissionConfig(_ticks(_number(mission_raw, "prelaunch_hold_s", source, "mission"), dt, source, "mission.prelaunch_hold_s"), _number(mission_raw, "ascent_cutoff_altitude_m", source, "mission"), _number(mission_raw, "descent_entry_velocity_m_s", source, "mission"), _number(mission_raw, "landing_entry_altitude_m", source, "mission"), _number(mission_raw, "landed_altitude_threshold_m", source, "mission"), int(mission_raw["transition_confirmation_ticks"]), int(mission_raw["abort_invalid_confirm_ticks"]))

    faults = []
    for index, item in enumerate(raw.get("faults", [])):
        base = f"faults.{index}"
        fault_type = item.get("type")
        activation = _ticks(_number(item, "activation_time_s", source, base), dt, source, f"{base}.activation_time_s")
        end = item.get("deactivation_time_s")
        timing = FaultTiming(activation, _ticks(float(end), dt, source, f"{base}.deactivation_time_s") if end is not None else None)
        common = {"id", "type", "target", "activation_time_s", "deactivation_time_s"}
        try:
            if fault_type == "sensor_freeze":
                _strict(item, common, source, base); faults.append(SensorFreezeFault(item["id"], SensorName(item["target"]), timing))
            elif fault_type == "sensor_bias":
                _strict(item, common | {"bias"}, source, base); faults.append(SensorBiasFault(item["id"], SensorName(item["target"]), timing, _number(item, "bias", source, base)))
            elif fault_type == "sensor_delay":
                _strict(item, common | {"delay_s"}, source, base); faults.append(SensorDelayFault(item["id"], SensorName(item["target"]), timing, _number(item, "delay_s", source, base)))
            elif fault_type == "actuator_degradation":
                _strict(item, common | {"lag_multiplier", "authority_scale", "rate_scale"}, source, base); faults.append(ActuatorDegradationFault(item["id"], ActuatorName(item["target"]), timing, float(item.get("lag_multiplier", 1.0)), float(item.get("authority_scale", 1.0)), float(item.get("rate_scale", 1.0))))
            else:
                raise ConfigError(source, f"{base}.type", f"unsupported fault type {fault_type!r}.")
        except (KeyError, ValueError) as exc:
            if isinstance(exc, ConfigError): raise
            raise ConfigError(source, base, str(exc)) from exc

    validation_raw = _table(raw, "validation", source)
    val_keys = {"expected_outcome", "max_landing_vertical_speed_m_s", "max_horizontal_error_m", "max_pitch_error_deg", "require_valid_transitions"}
    _strict(validation_raw, val_keys, source, "validation")
    try:
        expected = ExpectedOutcome(validation_raw["expected_outcome"])
    except (KeyError, ValueError) as exc:
        raise ConfigError(source, "validation.expected_outcome", "unsupported expected outcome.") from exc
    try:
        validation = ValidationConfig(expected, _number(validation_raw, "max_landing_vertical_speed_m_s", source, "validation"), _number(validation_raw, "max_horizontal_error_m", source, "validation"), radians(_number(validation_raw, "max_pitch_error_deg", source, "validation")), _boolean(validation_raw, "require_valid_transitions", source, "validation"))
    except ValueError as exc:
        raise ConfigError(source, "validation", str(exc)) from exc
    config = ResolvedScenarioConfig(1, scenario_id, description.strip(), seed, simulation, initial_state, vehicle, environment, tuple(sensor_items), controller, tuple(profiles), actuators, mission, tuple(faults), validation)
    _validate_cross_fields(config, source)
    return config
