import numpy as np

from astraloop.actuators.models import ActuatorConfig, ActuatorModel
from astraloop.faults.manager import FaultManager
from astraloop.faults.types import FaultTiming, SensorFreezeFault
from astraloop.mission.modes import MissionMode
from astraloop.mission.state_machine import MissionConfig, MissionContext, MissionStateMachine
from astraloop.model.measurements import MeasurementStatus, SensorName
from astraloop.model.state import VehicleState
from astraloop.sensors.models import ScalarSensor, SensorConfig
from astraloop.sensors.suite import SensorSuite


def truth(y=10.0):
    return VehicleState(0.0, y, 0.0, 1.0, 0.0, 0.0, 1000.0)


def configs():
    return {name: SensorConfig(sample_interval=0.02) for name in SensorName}


def test_sensor_freeze_holds_last_deliverable_value():
    sensor = ScalarSensor(SensorName.ALTITUDE, lambda state: state.y, SensorConfig(), 0.02, np.random.default_rng(1))
    first = sensor.update(truth(10.0), 0)
    sensor.set_frozen(True)
    frozen = sensor.update(truth(20.0), 1)
    assert frozen.value == first.value
    assert frozen.metadata.source_tick == 0


def test_fault_activation_precedes_sensor_sample_effect():
    suite = SensorSuite.from_config(configs(), 0.02, 42)
    manager = FaultManager([SensorFreezeFault("freeze", SensorName.ALTITUDE, FaultTiming(0))], 0.02)
    effects, events = manager.update(0)
    manager.apply(effects, suite, ActuatorModel(ActuatorConfig()))
    reading = suite.sample(truth(), 0)
    assert len(events) == 1
    assert reading.metadata[SensorName.ALTITUDE].status is MeasurementStatus.UNAVAILABLE


def test_explicit_abort_has_priority():
    suite = SensorSuite.from_config(configs(), 0.02, 42)
    snapshot = suite.sample(truth(), 0)
    machine = MissionStateMachine(MissionConfig(prelaunch_hold_ticks=0))
    update = machine.update(snapshot, MissionContext(0, 0.02, abort_requested=True))
    assert update.current_state is MissionMode.ABORT
