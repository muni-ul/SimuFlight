"""Fresh deterministic subsystem construction and per-tick orchestration."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astraloop.actuators.models import ActuatorModel
from astraloop.config.loader import load_scenario
from astraloop.config.schema import ResolvedScenarioConfig
from astraloop.control.flight_controller import FlightController
from astraloop.faults.manager import FaultManager
from astraloop.mission.modes import TERMINAL_MODES
from astraloop.mission.state_machine import MissionContext, MissionStateMachine
from astraloop.model.results import RunResult, SimulationResult, TerminationReason
from astraloop.sensors.suite import SensorSuite
from astraloop.simulation.engine import SimulationEngine


@dataclass(frozen=True, slots=True)
class RuntimeFrame:
    tick: int
    time: float
    truth: Any
    measurements: Any
    mission_state: str
    controller_update: Any
    actuator_update: Any
    active_fault_ids: tuple[str, ...]


def run_scenario(
    config: ResolvedScenarioConfig,
    *,
    artifact_root: Path | None = None,
) -> RunResult:
    sensors = SensorSuite.from_config(config.sensor_mapping(), config.simulation.dt, config.seed)
    controller = FlightController(config.controller, config.profile_mapping(), config.simulation.dt)
    actuators = ActuatorModel(config.actuators)
    mission = MissionStateMachine(config.mission)
    faults = FaultManager(list(config.faults), config.simulation.dt)
    engine = SimulationEngine(config.simulation, config.vehicle, config.initial_state)
    frames: list[RuntimeFrame] = []
    events: list[Any] = []
    active_faults: tuple[str, ...] = ()

    while engine.tick < config.simulation.max_ticks:
        effects, fault_events = faults.update(engine.tick)
        faults.apply(effects, sensors, actuators)
        events.extend(fault_events)
        active_faults = effects.active_fault_ids
        measurement = sensors.sample(engine.state, engine.tick)
        mission_update = mission.update(
            measurement,
            MissionContext(engine.tick, config.simulation.dt),
        )
        if mission_update.event is not None:
            events.append(mission_update.event)
        control_update = controller.update(measurement, mission.state)
        actuator_update = actuators.update(control_update.command, config.simulation.dt)
        frames.append(
            RuntimeFrame(
                engine.tick, engine.sim_time, engine.state, measurement,
                mission.state.value, control_update, actuator_update, active_faults,
            )
        )
        if mission.state in TERMINAL_MODES:
            simulation = SimulationResult(
                engine.tick, engine.sim_time, engine.state,
                TerminationReason.TERMINAL_CONDITION,
            )
            break
        engine.step(actuators.applied(), config.environment)
    else:
        simulation = SimulationResult(
            engine.tick, engine.sim_time, engine.state, TerminationReason.MAX_TIME
        )

    return RunResult(
        config.id,
        config.digest,
        simulation,
        mission.state.value,
        tuple(frames),
        tuple(events),
        active_faults,
        str(artifact_root.resolve()) if artifact_root is not None else None,
    )


def run_scenario_file(path: str | Path, *, artifact_root: Path | None = None) -> RunResult:
    return run_scenario(load_scenario(path), artifact_root=artifact_root)
