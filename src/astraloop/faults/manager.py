"""Tick-exact fault lifecycle and order-independent effect composition."""

from dataclasses import dataclass

from astraloop.actuators.models import ActuatorDegradation, ActuatorModel
from astraloop.faults.types import (
    ActuatorDegradationFault,
    ActuatorFaultEffect,
    FaultDefinition,
    FaultEffects,
    FaultStatus,
    SensorBiasFault,
    SensorDelayFault,
    SensorFaultEffect,
    SensorFreezeFault,
)
from astraloop.model.events import FaultEventType, FaultLifecycleEvent
from astraloop.model.measurements import SensorName
from astraloop.sensors.suite import SensorSuite


@dataclass(slots=True)
class FaultRuntime:
    definition: FaultDefinition
    status: FaultStatus = FaultStatus.PENDING


class FaultManager:
    def __init__(self, definitions: list[FaultDefinition], dt: float) -> None:
        ids = [definition.id for definition in definitions]
        if len(ids) != len(set(ids)):
            raise ValueError("Fault ids must be unique within a scenario.")
        if dt <= 0.0:
            raise ValueError("Fault manager dt must be > 0.")
        self.runtimes = [FaultRuntime(definition) for definition in definitions]
        self.dt = dt
        self._last_tick = -1

    def update(self, tick: int) -> tuple[FaultEffects, tuple[FaultLifecycleEvent, ...]]:
        if tick != self._last_tick + 1:
            raise RuntimeError(f"Fault manager expected tick {self._last_tick + 1}, received {tick}.")
        self._last_tick = tick
        events: list[FaultLifecycleEvent] = []
        for runtime in self.runtimes:
            definition = runtime.definition
            if runtime.status is FaultStatus.PENDING and tick == definition.timing.activation_tick:
                runtime.status = FaultStatus.ACTIVE
                events.append(self._event(definition, tick, FaultEventType.ACTIVATED))
            if runtime.status is FaultStatus.ACTIVE and definition.timing.deactivation_tick == tick:
                runtime.status = FaultStatus.COMPLETED
                events.append(self._event(definition, tick, FaultEventType.DEACTIVATED))
        return self._compose(), tuple(events)

    def apply(
        self,
        effects: FaultEffects,
        sensors: SensorSuite,
        actuators: ActuatorModel,
    ) -> None:
        for name, sensor in sensors.sensors.items():
            effect = effects.sensors.get(name, SensorFaultEffect())
            sensor.set_frozen(effect.frozen)
            sensor.set_additional_bias(effect.additional_bias)
            sensor.set_delay(sensor.config.delay if effect.delay_override is None else effect.delay_override)
        actuators.set_degradation(
            ActuatorDegradation(
                effects.actuator.lag_multiplier,
                effects.actuator.authority_scale,
                effects.actuator.rate_scale,
            )
        )

    def _compose(self) -> FaultEffects:
        sensors: dict[SensorName, SensorFaultEffect] = {}
        lag = authority = rate = 1.0
        active = sorted(
            (runtime.definition for runtime in self.runtimes if runtime.status is FaultStatus.ACTIVE),
            key=lambda definition: definition.id,
        )
        for definition in active:
            if isinstance(definition, (SensorFreezeFault, SensorBiasFault, SensorDelayFault)):
                current = sensors.get(definition.target, SensorFaultEffect())
                sensors[definition.target] = SensorFaultEffect(
                    frozen=current.frozen or isinstance(definition, SensorFreezeFault),
                    additional_bias=current.additional_bias + (definition.bias if isinstance(definition, SensorBiasFault) else 0.0),
                    delay_override=max(
                        value for value in (current.delay_override, definition.delay if isinstance(definition, SensorDelayFault) else None) if value is not None
                    ) if current.delay_override is not None or isinstance(definition, SensorDelayFault) else None,
                )
            elif isinstance(definition, ActuatorDegradationFault):
                lag *= definition.lag_multiplier
                authority *= definition.authority_scale
                rate *= definition.rate_scale
        return FaultEffects(
            sensors,
            ActuatorFaultEffect(lag, authority, rate),
            tuple(definition.id for definition in active),
        )

    def _event(self, definition: FaultDefinition, tick: int, kind: FaultEventType) -> FaultLifecycleEvent:
        return FaultLifecycleEvent(
            tick, tick * self.dt, definition.id, definition.type.value,
            definition.target.value, kind,
        )
