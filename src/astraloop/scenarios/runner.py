"""Fresh deterministic subsystem construction and per-tick orchestration."""

from pathlib import Path
from dataclasses import asdict

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
from astraloop.telemetry.recorder import TelemetryFrame, TelemetryFrameKind, TelemetryRecorder
from astraloop.telemetry.serialization import ArtifactWriter
from astraloop.validation.validator import validate_run


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
    recorder = TelemetryRecorder(config.simulation.dt)
    recorder.record_simulation_event(0, "simulation_started", "Simulation started.", {"scenario_id": config.id, "seed": config.seed, "config_digest": config.digest})
    active_faults: tuple[str, ...] = ()
    measurement = control_update = actuator_update = None

    while engine.tick < config.simulation.max_ticks:
        effects, fault_events = faults.update(engine.tick)
        faults.apply(effects, sensors, actuators)
        for event in fault_events:
            recorder.record_domain_event(event)
        active_faults = effects.active_fault_ids
        measurement = sensors.sample(engine.state, engine.tick)
        mission_update = mission.update(
            measurement,
            MissionContext(engine.tick, config.simulation.dt),
        )
        if mission_update.event is not None:
            recorder.record_domain_event(mission_update.event)
        control_update = controller.update(measurement, mission.state)
        actuator_update = actuators.update(control_update.command, config.simulation.dt)
        if mission.state in TERMINAL_MODES:
            simulation = SimulationResult(
                engine.tick, engine.sim_time, engine.state,
                TerminationReason.TERMINAL_CONDITION,
            )
            break
        frame = TelemetryFrame(
            1, TelemetryFrameKind.CONTROL, engine.tick, engine.sim_time,
            mission.state.value, engine.state, measurement, control_update,
            actuator_update, active_faults,
        )
        engine.step(actuators.applied(), config.environment)
        recorder.record_frame(frame)
    else:
        simulation = SimulationResult(
            engine.tick, engine.sim_time, engine.state, TerminationReason.MAX_TIME
        )

    terminal = TelemetryFrame(
        1, TelemetryFrameKind.TERMINAL, engine.tick, engine.sim_time,
        mission.state.value, engine.state, measurement, control_update,
        actuator_update, active_faults, simulation.termination_reason.value,
    )
    recorder.record_frame(terminal)
    recorder.record_simulation_event(
        engine.tick, "simulation_terminated", "Simulation terminated.",
        {"reason": simulation.termination_reason.value, "final_mission_state": mission.state.value},
    )
    completed = recorder.finalize()
    validation = validate_run(config, completed)
    artifact_directory = None
    if artifact_root is not None:
        artifacts = ArtifactWriter(artifact_root).write(
            config,
            completed,
            {
                "scenario_id": config.id,
                "config_digest": config.digest,
                "final_tick": simulation.final_tick,
                "final_time_s": simulation.final_time,
                "final_mission_state": mission.state.value,
                "termination_reason": simulation.termination_reason.value,
                "validation": asdict(validation),
            },
        )
        artifact_directory = str(artifacts.directory)

    return RunResult(
        scenario_id=config.id,
        config_digest=config.digest,
        simulation=simulation,
        final_mission_state=mission.state.value,
        telemetry=completed.frames,
        events=completed.events,
        active_fault_ids=active_faults,
        validation=validation,
        artifact_directory=artifact_directory,
    )


def run_scenario_file(path: str | Path, *, artifact_root: Path | None = None) -> RunResult:
    return run_scenario(load_scenario(path), artifact_root=artifact_root)
