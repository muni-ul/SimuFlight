# Architecture

## Data boundary

```text
VehicleState (truth)
  -> SensorSuite
  -> MeasurementSnapshot
  -> MissionStateMachine + FlightController
  -> ControlCommand
  -> ActuatorModel
  -> AppliedActuation
  -> dynamics + RK4
  -> next VehicleState
```

`VehicleState` is owned by the numerical runtime. Flight software receives only `MeasurementSnapshot`. Validation is outside the system under test and may use truth telemetry as its oracle.

## Authoritative clock

The engine stores an integer `tick` and fixed `dt`. Time is always derived as `tick * dt`; it is never repeatedly accumulated or tied to wall time.

## Per-tick ordering

1. Check deterministic termination/safety state.
2. Activate or deactivate typed faults.
3. Apply composed fault effects.
4. Sample sensors from current truth.
5. Build the software-visible measurement snapshot.
6. Update mission state and emit any transition event.
7. Compute or hold the desired control command.
8. Advance physical actuator state once.
9. Hold applied actuation through all four RK4 stages.
10. Validate and commit the next truth state atomically.
11. Commit telemetry and ordered events.
12. Advance the authoritative integer tick.

## Ownership

| Component | Owns |
|---|---|
| Simulation engine | truth state, tick, numerical commit |
| Sensors | RNG, sample cadence, delay buffer, delivered reading |
| Controller | PID history and desired command |
| Actuators | applied state and response dynamics |
| Mission state machine | current mode, guard counters, transition events |
| Fault manager | fault lifecycle and effect composition |
| Telemetry recorder | immutable frames and ordered event envelopes |
| Validator | post-run metrics, outcome, scenario-contract checks |

## Error model

Configuration errors fail before tick zero. Numerical/runtime invariant violations raise simulation errors. A hard landing, validation failure, or controlled abort is a structured domain outcome rather than a Python exception.
