# Feature 07 — Fault Injection System

> **Project:** AstraLoop — Python Software-in-the-Loop Flight Control & Validation System  
> **Feature:** Fault Injection System  
> **Document path:** `docs/features/07-fault-injection-system.md`  
> **Status:** Implementation specification  
> **Primary goal:** Implement deterministic, configuration-driven fault definitions and lifecycle management that activate on simulation time or explicit supported conditions, modify real sensor/actuator/environment behavior through typed subsystem hooks, and emit structured activation/deactivation events without scattering scenario-specific branches through the simulation.

---

## Scope Boundary

**[Confirmed]** Fault injection is a central AstraLoop portfolio feature and one of the strongest direct signals for simulation, validation, and testing roles.

**[Confirmed]** The selected project direction includes the following core scenarios:

```text
nominal
altimeter_freeze
velocity_bias
sensor_delay
degraded_actuator
```

with an optional:

```text
external_disturbance
```

only after the first five are stable and tested.

**[Confirmed]** Faults must modify real subsystem behavior rather than merely changing a final result label.

**[Confirmed]** Fault logic belongs in the `faults/` subsystem and must not be scattered through the engine with branches such as:

```python
if scenario_name == "altimeter_freeze":
    ...
```

**[Confirmed]** Fault activation should depend on simulation time or an explicit event/condition.

**[Confirmed]** The architecture's tick order places fault activation/deactivation before current-tick sensor sampling:

```text
A. inspect terminal / simulator safety conditions
B. activate or deactivate faults for the current tick
C. sample sensors from current truth
D. apply sensor faults / delay / stale behavior
E. build MeasurementSnapshot
F. update mission state
G. compute controller command
H. update actuator models and actuator faults
I. advance truth state
J. validate invariants
K. record telemetry/events
L. increment tick
```

**[Decision]** Feature 07 owns the **fault-definition and fault-lifecycle orchestration layer**.

It owns:

- fault type definitions;
- fault IDs;
- typed targets;
- typed fault parameters;
- activation/deactivation specifications;
- conversion of time-based fault timing to deterministic simulation ticks;
- pending/active/completed fault lifecycle;
- active-fault registry;
- fault activation/deactivation decisions;
- routing sensor faults to sensor-local hooks;
- routing actuator faults to actuator-local hooks;
- optional environment disturbance routing;
- composition/conflict rules for multiple faults;
- fault activation/deactivation events;
- current active-fault metadata;
- deterministic behavior and tests.

It does **not** own:

- sensor freeze/bias/delay mechanics themselves;
- actuator lag/saturation equations themselves;
- 2D dynamics equations;
- mission state transitions;
- scenario-file discovery/listing;
- full scenario TOML loading/application service;
- CLI commands;
- expected-outcome validation;
- mission PASS/FAIL logic;
- telemetry/event persistence;
- diagnostic plotting;
- campaign/batch execution.

Those remain separate features.

---

# 1. Feature Overview

## Feature name

**Fault Injection System**

---

## One-sentence description

**[Decision]** Implement a deterministic fault manager that activates typed faults at exact simulation ticks or supported explicit conditions, applies them through real subsystem hooks, tracks active fault state, and emits structured lifecycle events for reproducible validation runs.

---

## Detailed description

AstraLoop's fault system should answer four questions cleanly:

```text
WHAT failed?
WHEN did it fail?
HOW did the real subsystem behavior change?
WHEN did the failure end, if ever?
```

The core flow is:

```text
Fault Definition
      |
      v
Fault Manager
      |
      +--> activation/deactivation decision
      |
      +--> Sensor fault hook
      |
      +--> Actuator fault hook
      |
      +--> Environment disturbance hook
      |
      v
Real subsystem behavior changes
      |
      v
Mission/controller/physics respond naturally
```

The fault system must **not** manufacture a final result.

Example:

```text
altimeter_freeze fault activates
        |
        v
altimeter stops updating
        |
        v
measurement age increases
        |
        v
measurement becomes STALE
        |
        v
controller/state machine respond
        |
        v
mission may recover, abort, or fail
```

That causal chain is the portfolio value.

---

## Core MVP fault types

### 1. Sensor freeze

Canonical scenario:

```text
altimeter_freeze
```

Fault type:

```text
sensor_freeze
```

Target:

```text
altimeter
```

Behavior:

- activates the target sensor's freeze primitive;
- preserves the last deliverable sensor value;
- preserves source timestamp;
- value age continues increasing;
- Feature 03 eventually marks it `STALE`;
- deactivation releases the freeze and returns the sensor to normal behavior according to sensor semantics.

The fault manager does not itself hold sensor samples.

---

### 2. Sensor bias

Canonical scenario:

```text
velocity_bias
```

Fault type:

```text
sensor_bias
```

Target:

```text
vertical_velocity
```

or another explicitly supported sensor channel.

Behavior:

```text
effective sensor bias =
    nominal configured bias
    + active fault bias contribution
```

The sensor subsystem owns how bias is applied to samples.

The fault manager owns:

- fault magnitude;
- activation;
- deactivation;
- composition with other active bias faults.

---

### 3. Sensor delay

Canonical scenario:

```text
sensor_delay
```

Fault type:

```text
sensor_delay
```

Target:

```text
one supported sensor channel
```

Behavior:

- changes the target sensor's effective delay;
- existing timestamped samples remain governed by the sensor buffer;
- new effective delay begins on the activation tick;
- deactivation restores nominal/effective non-fault delay according to composition rules.

The fault manager does not reimplement delay-buffer lookup.

---

### 4. Degraded actuator

Canonical scenario:

```text
degraded_actuator
```

Fault type:

```text
actuator_degradation
```

Target:

```text
throttle
```

or:

```text
gimbal
```

depending on the chosen canonical scenario.

**[Decision]** The primary MVP degradation parameter is:

```text
lag_multiplier > 1
```

which increases the target actuator's response time constant.

Optional supported degradation fields:

```text
authority_scale
rate_scale
```

should exist only if Feature 05 retained those hooks and they are tested.

The fault manager changes actuator runtime modifiers.

Feature 05 remains responsible for actual response equations.

---

### 5. Optional external disturbance

Only after the first four non-nominal fault types are stable.

Fault type:

```text
external_disturbance
```

Potential target:

```text
environment
```

Parameters may include bounded:

```text
force_x
force_y
torque
```

Behavior routes into Feature 01/02 environment/disturbance input hooks.

**[Decision]** Keep this optional.

Do not allow it to delay completion of the core sensor/actuator fault set.

---

## Faults are typed domain objects

Do not represent every fault as an unvalidated dictionary passed around at runtime.

Recommended base definition:

```python
@dataclass(frozen=True)
class FaultDefinition:
    id: str
    type: FaultType
    target: FaultTarget
    activation: FaultActivation
    deactivation: FaultDeactivation | None
    parameters: FaultParameters
```

The exact implementation may use discriminated dataclasses by fault type.

Example:

```python
SensorFreezeFaultConfig
SensorBiasFaultConfig
SensorDelayFaultConfig
ActuatorDegradationFaultConfig
ExternalDisturbanceFaultConfig
```

**Decision:** Prefer explicit typed fault configs over one giant class with dozens of optional fields.

This gives Pyright useful structure and makes invalid combinations impossible or easy to reject.

---

## Fault type enum

Recommended:

```python
class FaultType(Enum):
    SENSOR_FREEZE = "sensor_freeze"
    SENSOR_BIAS = "sensor_bias"
    SENSOR_DELAY = "sensor_delay"
    ACTUATOR_DEGRADATION = "actuator_degradation"
    EXTERNAL_DISTURBANCE = "external_disturbance"
```

If optional external disturbance is deferred, the enum may omit it until implemented.

Do not keep unsupported enum values that silently parse but do nothing.

---

## Typed fault targets

Avoid raw arbitrary strings deep in runtime logic.

Recommended target types reuse subsystem enums where possible.

### Sensor targets

Reuse Feature 03:

```text
SensorName.ALTIMETER
SensorName.VERTICAL_VELOCITY
SensorName.HORIZONTAL_POSITION
SensorName.HORIZONTAL_VELOCITY
SensorName.ATTITUDE
SensorName.GYRO
```

### Actuator targets

Recommended enum:

```python
class ActuatorName(Enum):
    THROTTLE = "throttle"
    GIMBAL = "gimbal"
```

### Environment target

Only if optional disturbance is implemented.

---

## Fault lifecycle

Recommended lifecycle enum:

```text
PENDING
ACTIVE
COMPLETED
```

Potential run-final reporting status:

```text
NOT_ACTIVATED
```

does not need to be a live state if the runner/validator can derive it from a `PENDING` fault at termination.

### `PENDING`

Configured but not yet activated.

### `ACTIVE`

Currently modifying subsystem behavior.

### `COMPLETED`

Activated previously and later deactivated.

For a permanent/unbounded-duration fault:

```text
PENDING -> ACTIVE
```

and it remains ACTIVE until run termination.

---

## Fault runtime record

Recommended:

```python
@dataclass
class FaultRuntimeState:
    definition: FaultDefinition
    status: FaultStatus = FaultStatus.PENDING
    activated_tick: int | None = None
    deactivated_tick: int | None = None
```

Mutable lifecycle state belongs to the Fault Manager.

The immutable fault definition remains unchanged.

---

## Activation timing

The architecture uses:

```python
sim_time = tick * dt
```

**[Decision]** Time-based fault activation is resolved into an integer:

```text
activation_tick
```

before the simulation begins.

Example:

```text
activation_time_s = 20.0
dt = 0.02

activation_tick = 1000
```

The fault becomes active when:

```text
current_tick == activation_tick
```

during fault-manager processing at tick-order step B.

---

## Time alignment validation

**[Decision]** For the MVP:

```text
activation_time / dt
```

must be integer-like within a small configuration tolerance.

Otherwise reject the fault configuration.

Do not silently round:

```text
20.013 s
```

to an arbitrary neighboring simulation tick.

This keeps activation semantics exact and reviewable.

The same rule applies to explicit time-based deactivation.

---

## Activation tick semantics

If a fault activates at tick `t`:

```text
1. fault manager activates fault at step B of tick t
2. event is generated at time t * dt
3. sensor/actuator/environment subsystem sees active fault on tick t
```

### Sensor example

For a freeze at tick `1000`:

```text
fault activates
before
sensor sampling at tick 1000
```

Therefore the sensor must not publish the newly sampled tick-1000 value if Feature 03 freeze semantics say freeze wins on the activation tick.

It holds the previous deliverable value.

This resolves the open timing question from Feature 03.

---

## Actuator fault timing semantics

Feature 05's actuator update occurs after controller calculation on the same tick.

If degradation activates at tick `t`:

```text
fault manager updates modifier state at step B
...
controller produces desired command at step G
actuator update at step H uses degraded parameters
```

Therefore degradation affects the actuator's tick-`t` response immediately.

---

## Deactivation timing

If a fault deactivates at tick `t`:

```text
deactivation happens at step B of tick t
```

and the target subsystem runs under the restored/effectively recomposed fault state for tick `t`.

This is symmetric with activation.

---

## Activation/deactivation ordering on the same tick

A bad config may attempt:

```text
activation_tick == deactivation_tick
```

**[Decision]** Reject zero-duration time faults in MVP configuration.

Require:

```text
deactivation_tick > activation_tick
```

when both are defined.

This avoids ambiguous "active for no subsystem update" faults.

---

## Permanent faults

If no end time/duration/deactivation trigger is configured:

```text
fault remains ACTIVE until simulation terminates
```

This is valid.

---

## Duration

Human-friendly scenario config may support:

```text
duration_s
```

instead of explicit deactivation time.

Resolve:

```text
deactivation_tick =
    activation_tick
    + duration_ticks
```

with integer tick validation.

**Decision:** A fault config should provide at most one of:

```text
deactivation_time
duration
```

for the same time-based fault.

Reject contradictory timing fields.

---

## Condition/event activation

The master blueprint permits activation based on:

```text
simulation time
or
explicit event/condition
```

**Decision]** Do not build a generic expression language.

Supported MVP activation kinds should be explicit typed cases.

Recommended:

```text
AT_TIME
ON_MISSION_STATE
```

### `AT_TIME`

Primary and required MVP trigger.

Example:

```toml
activation_time = 20.0
```

### `ON_MISSION_STATE`

Optional but useful typed trigger.

Example concept:

```text
activate when MissionState becomes DESCENT
```

This avoids fragile hard-coded time if the scenario logically means "fail during descent."

Activation occurs when the current mission status at the start of fault processing satisfies the trigger based on the last committed mission state.

### Ordering consequence

Fault processing happens before the mission-state update of the current tick.

Therefore:

- a fault cannot react to a mission transition that has not happened yet in the same tick;
- `ON_MISSION_STATE=DESCENT` activates starting on the first later tick where DESCENT is already the current committed state.

This one-tick ordering must be documented and tested.

**[Decision]** Do not add arbitrary measurement predicates in Feature 07 unless there is a concrete scenario need.

A generic rules DSL would be scope creep.

---

## Condition deactivation

MVP should prioritize:

```text
time duration
explicit end time
permanent
```

Condition-based deactivation can be added only if a real scenario requires it.

---

## Fault application architecture

The Fault Manager should not manually mutate subsystem internals.

Preferred architecture:

```text
Fault Manager
    |
    +--> compose SensorFaultEffects
    |
    +--> compose ActuatorFaultEffects
    |
    +--> compose EnvironmentFaultEffects
    |
    v
subsystems consume/apply their typed current effects
```

Two viable patterns:

### Pattern A — setter/hook

```python
sensor_suite.set_fault_effects(...)
actuators.set_runtime_modifiers(...)
```

### Pattern B — fault manager returns an immutable effect snapshot

```python
effects = fault_manager.update(...)
```

Then engine supplies:

```text
effects.sensor_effects
effects.actuator_effects
effects.environment_effects
```

to the target subsystems.

**[Decision]** Prefer **immutable effect snapshots** where practical.

Why:

- easier to test;
- reduces hidden mutation;
- cleanly exposes current active fault effects;
- preserves functional-core style;
- makes tick ordering explicit.

Subsystems may still own state internally.

---

## Fault effect snapshot

Recommended:

```python
@dataclass(frozen=True)
class FaultEffects:
    sensor_effects: SensorFaultEffects
    actuator_effects: ActuatorFaultEffects
    environment_effects: EnvironmentFaultEffects
    active_fault_ids: tuple[str, ...]
```

Do not expose scenario ID.

---

## Sensor fault effects

Possible representation:

```python
@dataclass(frozen=True)
class SensorChannelFaultEffect:
    frozen: bool = False
    additional_bias: float = 0.0
    delay_override_ticks: int | None = None
```

And mapping:

```text
SensorName -> SensorChannelFaultEffect
```

Feature 03 applies the effect.

---

## Actuator fault effects

Possible:

```python
@dataclass(frozen=True)
class ActuatorChannelFaultEffect:
    lag_multiplier: float = 1.0
    authority_scale: float = 1.0
    rate_scale: float = 1.0
```

Feature 05 uses the effect to derive effective actuator parameters.

---

## Environment fault effects

Optional:

```python
@dataclass(frozen=True)
class EnvironmentFaultEffects:
    external_force_x: float = 0.0
    external_force_y: float = 0.0
    external_torque: float = 0.0
```

Only implement if external-disturbance scenario is retained.

---

## Fault composition

The source blueprint requires faults to be composable enough that a future scenario can contain more than one.

Therefore the manager must define deterministic composition rules.

---

## Composition rule — freezes

Multiple freeze faults targeting the same sensor:

```text
effective frozen = any(active freeze targeting sensor)
```

A sensor remains frozen until **all** active freeze faults targeting it are inactive.

This avoids one fault deactivating and accidentally clearing another active freeze.

---

## Composition rule — bias

Multiple sensor-bias faults targeting the same sensor:

```text
effective additional bias =
    sum(active bias magnitudes)
```

Why additive:

- deterministic;
- intuitive;
- order independent.

---

## Composition rule — delay

Multiple active delay faults on one sensor create a conflict because a single channel has one effective delay.

**[Decision]** Compose as:

```text
effective delay =
    maximum requested active fault delay
```

relative to/combined with nominal sensor delay.

Recommended:

```text
effective_delay =
    max(
        nominal_delay,
        all_active_fault_delay_values
    )
```

### Why maximum

- deterministic;
- conservative;
- order independent;
- avoids ambiguous "last fault wins."

If a future fault type represents **additional** delay instead of total delay, name it explicitly and define additive behavior separately.

For MVP `sensor_delay`, treat parameter as:

```text
effective total delay override
```

---

## Composition rule — actuator lag

Multiple lag-degradation faults targeting one actuator:

```text
effective lag multiplier =
    product(active lag multipliers)
```

Example:

```text
1.5 * 2.0 = 3.0x nominal lag
```

This is deterministic and order independent.

---

## Composition rule — actuator authority

Multiple authority scales:

```text
effective authority scale =
    product(active authority scales)
```

For degradation, each scale should normally be:

```text
0 <= scale <= 1
```

---

## Composition rule — actuator rate

Multiple rate scales:

```text
effective rate scale =
    product(active rate scales)
```

---

## Composition rule — external disturbance

If optional disturbance faults overlap:

```text
forces/torques sum
```

unless a future explicitly different disturbance type requires another rule.

---

## Conflicting fault policy

**[Decision]** Avoid "last activated wins."

Composition must be:

- deterministic;
- order independent where practical;
- documented per fault type.

If two fault definitions cannot be safely composed, reject the scenario during configuration validation rather than guessing.

---

## Fault IDs

Every fault definition requires a unique stable ID within a scenario.

Example:

```text
freeze_altimeter_01
velocity_bias_01
```

Requirements:

- non-empty;
- unique;
- suitable for event logs;
- not derived from list position.

Duplicate IDs are a `ConfigError`.

---

## Fault metadata

Each fault should expose immutable metadata sufficient for later run artifacts:

```text
id
type
target
activation spec
deactivation spec
parameters
```

The Fault Manager should not add:

```text
expected mission outcome
```

to runtime fault behavior.

Expected outcome belongs to scenario/validation configuration.

---

## Fault lifecycle events

Required event types:

```text
FAULT_ACTIVATED
FAULT_DEACTIVATED
```

Potential event:

```text
FAULT_NOT_ACTIVATED
```

is better handled in run summary/finalization rather than emitted every run unless needed.

Recommended event:

```python
@dataclass(frozen=True)
class FaultEvent:
    tick: int
    time: float
    event_type: FaultEventType

    fault_id: str
    fault_type: FaultType
    target: str

    message: str
```

Potential structured metadata:

```text
parameters/effective change
```

for later serialization.

---

## Activation event example

```text
20.00s FAULT_ACTIVATED
fault_id=freeze_altimeter_01
type=sensor_freeze
target=altimeter
```

The event is generated at the exact activation tick.

Telemetry/Event Logging later writes it to `events.json`.

---

## Deactivation event example

```text
30.00s FAULT_DEACTIVATED
fault_id=freeze_altimeter_01
type=sensor_freeze
target=altimeter
```

---

## Active fault registry

The simulation engine's imperative shell concept includes:

```text
active faults
```

**[Decision]** The Fault Manager owns this state.

Expose read-only data:

```python
active_fault_ids: tuple[str, ...]
```

and optionally:

```python
active_faults: tuple[ActiveFaultView, ...]
```

Do not expose mutable runtime dicts publicly.

---

## Why fault behavior must be subsystem-real

Bad implementation:

```python
if scenario == "velocity_bias":
    final_result = FAIL
```

Good implementation:

```text
sensor_bias activates
 -> vertical velocity measurement changes
 -> controller responds to biased measurement
 -> applied actuation changes
 -> physics trajectory changes
 -> validator evaluates resulting mission
```

The final outcome must emerge from the real simulation.

---

## Why it matters

The master blueprint identifies fault injection as the strongest direct signal for validation/testing roles.

It lets AstraLoop demonstrate:

- reproducible failures;
- controlled subsystem perturbation;
- real behavioral consequences;
- fault lifecycle events;
- deterministic test cases;
- multiple scenarios using one core engine.

This moves the project from:

```text
"my simulation works"
```

to:

```text
"my software can systematically prove how the system behaves when components stop behaving nominally"
```

---

## Skill it demonstrates

A strong implementation demonstrates:

- validation/test architecture;
- dependency injection;
- typed configuration;
- deterministic event scheduling;
- stateful fault lifecycle;
- composition rules;
- failure modeling;
- subsystem boundary design;
- reusable scenario behavior;
- structured events;
- edge-case handling;
- integration testing;
- reproducibility.

---

## Priority

**P0/P1 — Core portfolio feature**

AstraLoop should not be considered portfolio-complete with only a nominal mission.

The project direction explicitly requires multiple fault scenarios that genuinely alter runtime behavior.

---

## Complexity

**Medium**

The individual faults are simple because the sensor/actuator features already own their mechanics.

The key engineering work is:

- clean fault definitions;
- activation timing;
- lifecycle state;
- routing;
- composition;
- event generation;
- testing.

---

# 2. User / Demo Flow

Feature 08/15 will own the final CLI surface. This feature provides the fault behavior used by those commands.

---

## Happy path

1. Scenario/config layer supplies typed fault definitions.
2. Fault Manager validates/receives resolved definitions.
3. Each time-based activation is already converted to exact ticks.
4. Simulation starts with all faults `PENDING`.
5. At each engine tick, Fault Manager updates before sensor sampling.
6. When a fault trigger becomes true:
   - lifecycle changes `PENDING -> ACTIVE`;
   - activation tick is recorded;
   - activation event is returned;
   - active effect snapshot changes immediately.
7. Sensor/actuator/environment subsystem consumes the current effect.
8. Real behavior changes.
9. If the fault has an end condition/time:
   - lifecycle changes `ACTIVE -> COMPLETED`;
   - deactivation event is returned;
   - composed effect is recalculated.
10. Mission finishes naturally.
11. Later telemetry persists fault events.
12. Later validator checks whether scenario outcome matched expectation.

---

## First-time path

### Stage A — Fault type/target validation

Before engine integration:

- parse/construct one `sensor_freeze` definition;
- validate target;
- validate unique ID;
- validate timing.

### Stage B — Fault lifecycle without subsystem

Use a fake target adapter.

Test:

```text
PENDING -> ACTIVE -> COMPLETED
```

at exact ticks.

### Stage C — Sensor freeze integration

Connect Feature 03.

Activate freeze at known tick.

Verify:

- previous delivered value is held;
- source timestamp stops changing;
- later status becomes stale.

### Stage D — Velocity bias

Activate known bias.

Verify sampled measured velocity changes by configured amount.

### Stage E — Sensor delay

Activate delay override.

Verify the sensor starts delivering older eligible buffered samples.

### Stage F — Actuator degradation

Activate larger lag multiplier.

Verify actual actuator response slows while controller command remains unchanged.

### Stage G — Multiple faults

Use two compatible faults.

Verify composition is order independent.

### Stage H — Lifecycle events

Verify exact activation/deactivation tick/time and metadata.

Only after these pass should Feature 08 scenario runner make them user-facing through TOML scenarios.

---

## Empty state

A nominal scenario contains:

```text
faults = []
```

or no resolved fault definitions.

The Fault Manager should still operate:

```text
active_fault_ids = ()
effects = nominal/no-op
events = ()
```

No special engine branch is needed.

This is important.

The same engine should run nominal and fault missions.

---

## Error path

### Unknown fault type

Reject before simulation.

### Invalid target

Examples:

```text
sensor_freeze target="engine_temperature"
actuator_degradation target="altimeter"
```

Reject.

### Duplicate fault ID

Reject.

### Missing required parameter

Examples:

```text
sensor_bias without bias magnitude
sensor_delay without delay
actuator_degradation without a degradation field
```

Reject.

### Non-finite parameter

Reject.

### Impossible activation time

Examples:

```text
activation_time < 0
activation_time > max_time
```

Recommended behavior:

- negative → invalid config;
- beyond configured max time → invalid config for bundled scenarios because fault can never activate.

This directly addresses the blueprint edge case.

### Non-aligned activation time

Reject if it cannot map exactly to integer simulation tick within tolerance.

### Invalid duration/end time

Reject:

```text
duration <= 0
deactivation <= activation
deactivation > max_time
```

for explicit time-bounded faults unless a later runner deliberately permits end beyond run duration.

### Fault activates after mission ended early

This can still happen even if activation is within `max_time`.

Example:

```text
activation at 40 s
mission reaches LANDED at 30 s
```

**[Decision]** This is not an internal simulation error.

The fault remains `PENDING`.

The scenario runner/validator may later report:

```text
configured fault did not activate
```

and decide whether that violates the expected scenario.

Feature 07 does not artificially continue the mission just to activate the fault.

---

## Demo path for a reviewer

### Demo A — Altimeter freeze

Show:

```text
fault event marker
true altitude continues changing
measured altitude becomes flat
measurement age increases
mission/controller response changes
```

Explain:

> "The fault manager does not fake the result. It activates the sensor's real freeze behavior at an exact simulation tick."

### Demo B — Velocity bias

Show:

```text
true vy
measured vy
```

before and after activation.

Bias step is clearly visible.

### Demo C — Degraded actuator

Show:

```text
requested command
actual actuator output
```

for nominal vs degraded response.

### Demo D — Reproducibility

Run the same scenario/seed twice.

Fault event ticks and resulting deterministic outcomes match.

### Demo E — Architecture

Show the fault folder and no scenario-specific branches in engine.

Reviewer takeaway:

> "Adding a new scenario means composing existing typed fault definitions, not editing the core simulation loop."

---

# 3. UX / UI Requirements

## Screens/pages

**[Decision]** No dedicated GUI.

Fault Injection System is headless.

Later CLI/plotting should make fault behavior visible through:

- activation/deactivation event lines;
- plot vertical markers;
- active fault IDs in telemetry if useful;
- run summary fault metadata.

Feature 07 provides data, not presentation.

---

## Components

Recommended software-facing components:

```text
FaultType
FaultStatus
FaultEventType

FaultDefinition / typed fault configs
FaultActivation
FaultDeactivation

FaultRuntimeState
FaultEvent

FaultEffects
SensorFaultEffects
ActuatorFaultEffects
EnvironmentFaultEffects

FaultManager
```

Optional target enums/types:

```text
SensorName
ActuatorName
```

Reuse existing enums instead of duplicating strings.

---

## Forms/inputs

No GUI form.

Raw scenario fields are loaded in Feature 08, but fault definitions need these conceptual inputs:

```text
id
type
target
activation time/condition
optional duration/end
fault-specific parameters
```

---

## Buttons/actions

None.

---

## Validation messages

Examples:

```text
Invalid fault [freeze_altimeter_01]: unknown target sensor 'barometer_2'.
Invalid fault [velocity_bias_01]: bias must be finite.
Invalid fault [sensor_delay_01]: delay_s must be >= 0.
Invalid fault [degraded_actuator_01]: lag_multiplier must be > 0.
Invalid fault [freeze_altimeter_01]: activation_time_s=20.01 is not aligned to simulation dt=0.02.
Duplicate fault id: 'freeze_altimeter_01'.
Invalid fault timing [fault_02]: deactivation tick must be greater than activation tick.
Fault target/type mismatch: sensor_freeze cannot target actuator 'gimbal'.
```

---

## Empty states

No faults:

```text
FaultManager returns nominal effects and no events.
```

No active faults:

```text
active_fault_ids = ()
```

---

## Loading states

None.

---

## Error states

Use `ConfigError` for invalid fault definitions discovered before simulation.

Use a narrow runtime fault error only for internal invariants such as:

- impossible lifecycle transition;
- missing target adapter that should have existed after setup;
- effect-composition bug.

A mission failing because of an injected fault is **not** a Python exception.

---

## Responsive behavior

Not relevant.

---

# 4. Data Requirements

## Entities involved

### `FaultType`

```python
class FaultType(Enum):
    SENSOR_FREEZE = "sensor_freeze"
    SENSOR_BIAS = "sensor_bias"
    SENSOR_DELAY = "sensor_delay"
    ACTUATOR_DEGRADATION = "actuator_degradation"
    EXTERNAL_DISTURBANCE = "external_disturbance"
```

Omit `EXTERNAL_DISTURBANCE` until implemented if necessary.

---

### `FaultStatus`

```python
class FaultStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
```

---

### `FaultEventType`

```python
class FaultEventType(Enum):
    ACTIVATED = "fault_activated"
    DEACTIVATED = "fault_deactivated"
```

---

### `TimeActivation`

Recommended resolved form:

```python
@dataclass(frozen=True)
class TimeActivation:
    tick: int
```

Human-facing seconds should already have been resolved/validated.

---

### `MissionStateActivation`

Optional:

```python
@dataclass(frozen=True)
class MissionStateActivation:
    state: MissionState
```

---

### `SensorFreezeFault`

```python
@dataclass(frozen=True)
class SensorFreezeFault:
    id: str
    target: SensorName
    activation: FaultActivation
    deactivation: FaultDeactivation | None
```

No magnitude is required.

---

### `SensorBiasFault`

```python
@dataclass(frozen=True)
class SensorBiasFault:
    id: str
    target: SensorName
    bias: float
    activation: FaultActivation
    deactivation: FaultDeactivation | None
```

Bias unit matches target sensor measurement unit.

---

### `SensorDelayFault`

```python
@dataclass(frozen=True)
class SensorDelayFault:
    id: str
    target: SensorName
    delay_ticks: int
    activation: FaultActivation
    deactivation: FaultDeactivation | None
```

`delay_ticks >= 0`.

For a meaningful non-nominal scenario it should normally exceed nominal effective delay.

---

### `ActuatorDegradationFault`

```python
@dataclass(frozen=True)
class ActuatorDegradationFault:
    id: str
    target: ActuatorName

    lag_multiplier: float = 1.0
    authority_scale: float = 1.0
    rate_scale: float = 1.0

    activation: FaultActivation
    deactivation: FaultDeactivation | None
```

At least one degradation field must differ from nominal.

---

### `ExternalDisturbanceFault`

Optional:

```python
@dataclass(frozen=True)
class ExternalDisturbanceFault:
    id: str

    force_x: float = 0.0
    force_y: float = 0.0
    torque: float = 0.0

    activation: FaultActivation
    deactivation: FaultDeactivation | None
```

Require at least one nonzero finite disturbance component.

---

### `FaultRuntimeState`

```python
@dataclass
class FaultRuntimeState:
    definition: FaultDefinition
    status: FaultStatus
    activated_tick: int | None
    deactivated_tick: int | None
```

Private to fault manager where possible.

---

### `FaultEvent`

```python
@dataclass(frozen=True)
class FaultEvent:
    tick: int
    time: float
    event_type: FaultEventType

    fault_id: str
    fault_type: FaultType
    target: str

    message: str
```

---

### `FaultManagerUpdate`

Recommended:

```python
@dataclass(frozen=True)
class FaultManagerUpdate:
    effects: FaultEffects
    active_fault_ids: tuple[str, ...]
    events: tuple[FaultEvent, ...]
```

The engine receives exactly one immutable update snapshot per tick.

---

## Relationships

```text
Resolved fault definitions
          |
          v
      FaultManager
          |
          +--> lifecycle state
          |
          +--> FaultEvents
          |
          +--> compose effects
                    |
          +---------+----------+
          |                    |
          v                    v
      Sensors             Actuators
          |                    |
          +----------+---------+
                     |
                     v
               real behavior
```

Optional:

```text
FaultManager -> Environment effects -> Dynamics
```

---

## Example source-supported fault config

The project blueprint provides this shape:

```toml
[[faults]]
id = "freeze_altimeter_01"
type = "sensor_freeze"
target = "altimeter"
activation_time = 20.0
```

**[Confirmed]** This is the canonical pattern for a time-triggered sensor-freeze fault.

---

## Example velocity-bias shape

The exact source documents do not provide a complete TOML block for this fault.

A reasonable typed structure is:

```toml
[[faults]]
id = "velocity_bias_01"
type = "sensor_bias"
target = "vertical_velocity"
activation_time = 18.0
bias = 1.5
```

**[Decision]** Values are project-development examples only.

Final fault magnitude/timing remains scenario-specific and should be chosen to produce meaningful validation behavior.

---

## Example sensor-delay shape

```toml
[[faults]]
id = "sensor_delay_01"
type = "sensor_delay"
target = "altimeter"
activation_time = 18.0
delay_s = 0.50
```

The config loader resolves `delay_s` to ticks.

---

## Example actuator-degradation shape

```toml
[[faults]]
id = "degraded_gimbal_01"
type = "actuator_degradation"
target = "gimbal"
activation_time = 18.0
lag_multiplier = 3.0
```

**Decision:** Slower response is the preferred canonical degradation.

---

## Local persistence needs

**[Decision]** Fault Manager performs no direct persistence.

It emits:

- current effect snapshot;
- active fault IDs;
- lifecycle events.

Feature 09 persists:

```text
events.json
telemetry.csv
resolved_config.json
summary.json
```

Feature 08/runner ensures resolved fault metadata is included in run artifacts.

---

# 5. Logic Requirements

## Rule 1 — Faults change real subsystem behavior

No cosmetic fault injection.

---

## Rule 2 — Fault Manager owns lifecycle, not subsystem mechanics

Freeze is implemented by sensor feature.

Lag is implemented by actuator feature.

Manager activates those behaviors.

---

## Rule 3 — No scenario-name branching

Core fault behavior depends on typed fault definitions.

---

## Rule 4 — Time uses integer simulation ticks

No wall clock.

---

## Rule 5 — Time activation is exact

Activation occurs at configured resolved tick.

---

## Rule 6 — Fault processing occurs before sensor sampling

This is an architecture contract.

---

## Rule 7 — Actuator degradation active on tick affects same-tick actuator update

Because actuator update happens later in tick order.

---

## Rule 8 — Activation event occurs exactly once

A PENDING fault can activate only once.

---

## Rule 9 — Deactivation event occurs exactly once

An ACTIVE bounded fault can deactivate only once.

---

## Rule 10 — COMPLETED faults cannot reactivate

MVP faults are single-lifecycle instances.

A repeating/intermittent fault should be represented as multiple fault definitions or a future explicit fault type.

---

## Rule 11 — Permanent fault remains ACTIVE

No synthetic deactivation at run end is required.

---

## Rule 12 — Fault ID is unique

Reject duplicates.

---

## Rule 13 — Fault target is validated before run

No late string lookup failures in a nominally valid scenario.

---

## Rule 14 — Fault type and target category must match

Sensor faults cannot target actuators and vice versa.

---

## Rule 15 — Required parameters are fault-type specific

Do not accept irrelevant parameter combinations silently.

---

## Rule 16 — All numerical fault parameters are finite

Reject NaN/Inf.

---

## Rule 17 — Time values cannot be negative

Reject.

---

## Rule 18 — Non-aligned time values are rejected

Do not approximate activation timing silently.

---

## Rule 19 — Explicit deactivation must occur after activation

Reject zero/negative duration.

---

## Rule 20 — Fault Manager updates atomically

All activation/deactivation decisions and composed effects for a tick should be calculated consistently before the engine continues.

---

## Rule 21 — Multiple compatible faults compose deterministically

No input-list-order dependence.

---

## Rule 22 — Freeze composition uses logical OR

Any active freeze keeps target frozen.

---

## Rule 23 — Bias composition is additive

Sum active biases targeting same channel.

---

## Rule 24 — Delay composition uses maximum effective delay

No "last activated wins."

---

## Rule 25 — Lag degradation composition multiplies lag multipliers

Order independent.

---

## Rule 26 — Authority/rate degradation scales multiply

Order independent.

---

## Rule 27 — Optional disturbance vectors add

If implemented.

---

## Rule 28 — Deactivating one fault removes only its contribution

Other active faults continue affecting target.

---

## Rule 29 — Fault Manager does not mutate mission state

Mission responds through changed measurements/status or explicit generic context if later required.

---

## Rule 30 — Fault Manager does not compute controller commands

---

## Rule 31 — Fault Manager does not write expected result

---

## Rule 32 — Fault Manager does not stop simulation

Engine owns termination.

---

## Rule 33 — Fault scheduled after an early terminal mission remains unactivated

Do not continue simulation solely to trigger it.

---

## Rule 34 — Same fault/config stream produces same lifecycle

No RNG in fault timing unless a future explicitly stochastic fault type is introduced.

---

## Rule 35 — Scenario seed does not alter deterministic fault timing

Sensor noise may depend on seed.

Time-triggered fault activation does not.

---

## Rule 36 — Active fault IDs are stable-order

Recommended sort:

```text
fault definition order after validated resolution
```

or lexicographic ID.

Choose one and test it.

Do not depend on mutable set ordering.

---

## Time-activation pseudocode

```python
def should_activate(
    runtime: FaultRuntimeState,
    *,
    tick: int,
    mission_state: MissionState,
) -> bool:

    if runtime.status is not FaultStatus.PENDING:
        return False

    match runtime.definition.activation:
        case TimeActivation(activation_tick):
            return tick == activation_tick

        case MissionStateActivation(required_state):
            return mission_state is required_state

    raise FaultRuntimeError(...)
```

---

## Deactivation pseudocode

```python
def should_deactivate(
    runtime: FaultRuntimeState,
    *,
    tick: int,
) -> bool:

    if runtime.status is not FaultStatus.ACTIVE:
        return False

    if runtime.definition.deactivation is None:
        return False

    match runtime.definition.deactivation:
        case TimeDeactivation(deactivation_tick):
            return tick == deactivation_tick

    raise FaultRuntimeError(...)
```

---

## Fault-manager tick pseudocode

```python
def update(
    *,
    tick: int,
    dt: float,
    mission_state: MissionState,
) -> FaultManagerUpdate:

    events: list[FaultEvent] = []

    for runtime in self._faults:
        if should_deactivate(runtime, tick=tick):
            deactivate(runtime)
            events.append(
                make_deactivation_event(...)
            )

    for runtime in self._faults:
        if should_activate(
            runtime,
            tick=tick,
            mission_state=mission_state,
        ):
            activate(runtime)
            events.append(
                make_activation_event(...)
            )

    effects = compose_effects(
        active_faults=self.active_faults,
    )

    return FaultManagerUpdate(
        effects=effects,
        active_fault_ids=...,
        events=tuple(events),
    )
```

### Same-tick deactivation before activation

**[Decision]** Process deactivations before activations when multiple different faults change on the same tick.

Why:

- old effects are removed first;
- new effects then become active;
- final composed state reflects all faults intended for the current tick;
- event order is deterministic.

This does not permit one fault to activate/deactivate on the same tick because zero-duration faults are invalid.

---

## Effect-composition pseudocode

```python
def compose_sensor_effects(
    active_faults: Iterable[FaultDefinition],
) -> SensorFaultEffects:

    freeze_by_sensor = ...
    bias_by_sensor = ...
    delay_by_sensor = ...

    for fault in active_faults:
        match fault:
            case SensorFreezeFault(...):
                freeze_by_sensor[target] = True

            case SensorBiasFault(...):
                bias_by_sensor[target] += bias

            case SensorDelayFault(...):
                delay_by_sensor[target] = max(
                    delay_by_sensor[target],
                    delay_ticks,
                )

    return ...
```

Equivalent typed logic applies to actuator effects.

---

## Edge cases

### Fault activation tick is zero

Valid.

The fault is active before the first sensor sample/actuator update.

This is useful for tests.

---

### Fault activation time equals max time

If max-time semantics mean the engine never executes that tick's subsystem processing, the fault may never activate.

**Decision]** Configuration validation must use Feature 02's exact max-tick semantics.

Do not validate against seconds loosely.

---

### Two freeze faults on same sensor

Allowed.

Sensor remains frozen until both have ended.

---

### Freeze + bias on same sensor

Allowed.

While frozen, the externally visible frozen value does not change.

The bias fault may become active internally/effectively, but it only influences future samples when sampling resumes according to Feature 03 semantics.

This is acceptable and deterministic.

---

### Freeze + delay on same sensor

Allowed.

Freeze dominates external value updates while active.

After release, current effective delay controls which buffered sample is deliverable.

---

### Two bias faults on same sensor

Add.

---

### Two delay faults on same sensor

Use max delay.

---

### Two degradation faults on same actuator

Compose multipliers/scales as documented.

---

### Invalid target sensor

Config error.

---

### Fault parameter omitted

Config error.

---

### Activation after mission already ended

Fault remains PENDING.

No fake activation event.

---

### Fault deactivation after mission already ended

Run ends with fault ACTIVE.

No deactivation event because that simulation tick never occurred.

---

### Mission-state activation trigger

Because fault update occurs before current-tick mission update, trigger observes the state committed from the previous tick.

Document this explicitly.

---

### Fault activated while target already disabled by nominal config

**Decision]** Allow only if behavior is well-defined, but configuration validation should normally reject meaningless bundled scenarios.

Example:

```text
sensor_freeze targeting a disabled sensor
```

does not demonstrate a real additional effect.

Prefer cross-field validation in Feature 08.

---

### Actuator lag multiplier with nominal tau zero

Multiplying zero by any finite multiplier remains zero, so a "sluggish" fault would have no effect.

**Decision]** Cross-field validation must reject/flag this combination for a degraded-lag fault.

The fault itself must genuinely alter runtime behavior.

---

### Delay fault equal to nominal delay

Technically valid but behaviorally cosmetic.

**Decision]** Bundled non-nominal scenario validation should reject/flag fault definitions that produce no effective change.

---

### Bias magnitude zero

Reject for `sensor_bias`.

A non-nominal fault must change behavior.

---

### Authority scale one with no other degradation field changed

Reject as no-op actuator degradation.

---

### External disturbance all zeros

Reject.

---

### Fault target disappears

Subsystem topology is fixed for run.

A missing resolved target after startup is an internal runtime/configuration bug.

---

### Fault manager called twice for same tick

This could duplicate lifecycle effects/events.

**Decision]** Track last processed tick and reject non-monotonic or duplicate tick processing.

This protects deterministic lifecycle semantics.

---

### Tick skips forward

The engine should call fault manager every tick.

If manager receives:

```text
last_tick = 100
current_tick = 102
```

and a fault was scheduled at 101, silently missing it would be dangerous.

**Decision]** Reject skipped/non-sequential tick processing in normal runtime, unless the manager is explicitly designed for initialization at tick 0 only.

---

# 6. Acceptance Criteria

## AC-01 — Fault Manager supports empty nominal fault set

**Given** no configured faults  
**When** fault manager updates  
**Then** no events are produced, no faults are active, and all effect snapshots are nominal/no-op.

---

## AC-02 — Fault IDs must be unique

**Given** two definitions with the same fault ID  
**When** configuration is validated  
**Then** setup fails with `ConfigError`.

---

## AC-03 — Unknown fault type is rejected

**Given** a raw/resolved definition with unsupported type  
**When** config validation runs  
**Then** simulation does not begin.

---

## AC-04 — Sensor fault requires valid sensor target

**Given** a sensor fault targeting an unknown sensor  
**When** validation runs  
**Then** setup fails.

---

## AC-05 — Actuator fault requires valid actuator target

**Given** an actuator degradation targeting an unknown actuator  
**When** validation runs  
**Then** setup fails.

---

## AC-06 — Target-category mismatch is rejected

**Given** `sensor_freeze` targeting `gimbal`  
**When** validation runs  
**Then** setup fails.

---

## AC-07 — Negative activation time is rejected

**Given** `activation_time < 0`  
**When** timing is resolved  
**Then** setup fails.

---

## AC-08 — Non-finite activation time is rejected

**Given** NaN/Inf activation time  
**When** validation runs  
**Then** setup fails.

---

## AC-09 — Non-tick-aligned activation time is rejected

**Given** activation time cannot map to integer simulation tick within tolerance  
**When** config is resolved  
**Then** setup fails rather than silently rounding.

---

## AC-10 — Exact time activation maps to expected tick

**Given** `dt=0.02` and `activation_time=20.0`  
**When** timing is resolved  
**Then** activation tick is `1000`.

---

## AC-11 — Fault does not activate early

**Given** time-triggered activation tick `1000`  
**When** manager processes tick `999`  
**Then** fault remains PENDING.

---

## AC-12 — Fault activates exactly on configured tick

**Given** activation tick `1000` and pending fault  
**When** manager processes tick `1000`  
**Then** status becomes ACTIVE.

---

## AC-13 — Activation event uses exact tick/time

**Given** activation at tick `1000`, `dt=0.02`  
**When** event is produced  
**Then** event tick is `1000` and time is `20.0`.

---

## AC-14 — Activation event occurs only once

**Given** a fault already ACTIVE  
**When** later ticks process  
**Then** no duplicate activation event is emitted.

---

## AC-15 — Permanent fault remains active

**Given** no deactivation specification  
**When** ticks advance after activation  
**Then** fault remains ACTIVE until run termination.

---

## AC-16 — Invalid zero/negative duration is rejected

**Given** duration `<= 0`  
**When** config validation runs  
**Then** setup fails.

---

## AC-17 — Deactivation must follow activation

**Given** deactivation tick `<=` activation tick  
**When** validation runs  
**Then** setup fails.

---

## AC-18 — Bounded fault deactivates exactly on configured tick

**Given** ACTIVE fault with deactivation tick `d`  
**When** manager processes tick `d`  
**Then** status becomes COMPLETED before subsystem processing for that tick.

---

## AC-19 — Deactivation event occurs once

**Given** bounded fault deactivates  
**When** later ticks execute  
**Then** no duplicate deactivation event occurs.

---

## AC-20 — Completed fault cannot reactivate

**Given** status COMPLETED  
**When** its activation condition is true again  
**Then** it remains COMPLETED.

---

## AC-21 — Fault scheduled after early mission termination does not fake activation

**Given** mission terminates before a pending fault's activation tick  
**When** run ends  
**Then** the fault remains unactivated and no activation event exists.

---

## AC-22 — Sensor freeze changes real sensor behavior

**Given** active `sensor_freeze` targeting altimeter  
**When** sensor suite processes ticks  
**Then** altimeter externally visible value obeys Feature 03 freeze semantics rather than normal sampling.

---

## AC-23 — Sensor freeze activation applies on activation tick

**Given** freeze activates at a tick that is also an altimeter sample tick  
**When** current tick sensor update occurs  
**Then** freeze is already active and the newly sampled value is not published under the documented freeze semantics.

---

## AC-24 — Frozen sensor source timestamp stops updating

**Given** active sensor freeze after a valid reading  
**When** ticks advance  
**Then** delivered source tick remains unchanged.

---

## AC-25 — Frozen sensor may become stale naturally

**Given** active freeze and Feature 03 stale logic  
**When** measurement age exceeds threshold  
**Then** sensor status becomes STALE without Fault Manager directly setting the status.

---

## AC-26 — Freeze deactivation restores sensor behavior

**Given** a bounded freeze fault deactivates  
**When** sensor runs afterward  
**Then** sensor resumes normal behavior according to Feature 03 release semantics.

---

## AC-27 — Sensor bias modifies real sampled measurement

**Given** active sensor bias `b` and zero other fault bias  
**When** target sensor generates a new sample  
**Then** effective additional bias contribution equals `b`.

---

## AC-28 — Zero bias magnitude is rejected as no-op fault

**Given** `sensor_bias` magnitude `0`  
**When** non-nominal fault config is validated  
**Then** setup rejects it or explicitly flags it invalid for the supported fault definition.

---

## AC-29 — Multiple sensor biases compose additively

**Given** two active bias faults `b1`, `b2` targeting same sensor  
**When** effects are composed  
**Then** effective additional bias is `b1 + b2`.

---

## AC-30 — Sensor delay changes real delivery behavior

**Given** active sensor-delay fault  
**When** target sensor determines deliverable sample  
**Then** it uses the effective fault-modified delay.

---

## AC-31 — Multiple sensor delay faults use maximum delay

**Given** active delay faults requesting `d1` and `d2`  
**When** effects compose  
**Then** effective fault delay is `max(d1,d2)` under MVP semantics.

---

## AC-32 — Delay fault equal to nominal effective delay is rejected/flagged as no-op for bundled non-nominal scenario

**Given** fault would not change effective delay  
**When** cross-field fault config is validated  
**Then** it is not accepted as a meaningful non-nominal fault scenario.

---

## AC-33 — Actuator degradation changes real actuator response

**Given** active lag multiplier greater than one  
**When** target actuator updates  
**Then** actual actuator response is slower than nominal for identical command/input state.

---

## AC-34 — Actuator fault does not modify requested command

**Given** active degradation  
**When** controller output is inspected  
**Then** `ControlCommand` is unchanged by Fault Manager.

---

## AC-35 — Lag multiplier must be positive

**Given** actuator degradation lag multiplier `<= 0`  
**When** validation runs  
**Then** setup fails.

---

## AC-36 — No-op actuator degradation is rejected

**Given** lag multiplier `1`, authority scale `1`, and rate scale `1`  
**When** degradation config is validated  
**Then** the fault is rejected as behaviorally empty.

---

## AC-37 — Multiple lag degradations multiply

**Given** active lag multipliers `a` and `b` targeting same actuator  
**When** effects compose  
**Then** effective lag multiplier is `a * b`.

---

## AC-38 — Authority scales compose multiplicatively

**Given** multiple active authority scales on same actuator  
**When** effects compose  
**Then** effective authority scale is their product.

---

## AC-39 — Rate scales compose multiplicatively

**Given** multiple active rate scales  
**When** effects compose  
**Then** effective rate scale is their product.

---

## AC-40 — Deactivating one overlapping fault preserves others

**Given** two active compatible faults target same subsystem  
**When** one deactivates  
**Then** the remaining fault contribution is still present.

---

## AC-41 — Multiple freeze faults use logical OR

**Given** two active freeze faults target same sensor  
**When** one deactivates  
**Then** sensor remains effectively frozen while the other is ACTIVE.

---

## AC-42 — Composition is independent of fault-list order

**Given** same active compatible fault set in different definition order  
**When** effects are composed  
**Then** resulting effective behavior values match.

---

## AC-43 — Fault activation precedes sensor sampling

**Given** architecture tick processing  
**When** a sensor fault activates at tick `t`  
**Then** the tick-`t` sensor update sees the fault as active.

---

## AC-44 — Actuator degradation affects same-tick actuator update

**Given** actuator fault activates at tick `t`  
**When** controller and actuator execute later that tick  
**Then** the actuator update uses degraded effective parameters.

---

## AC-45 — Fault Manager does not run inside RK4 stages

**Given** one simulation tick with four RK4 derivative evaluations  
**When** fault manager is inspected/instrumented  
**Then** lifecycle update occurs once for the tick, not four times.

---

## AC-46 — Fault Manager processes each simulation tick once

**Given** normal engine integration  
**When** tick `t` is processed  
**Then** the manager accepts it once.

---

## AC-47 — Duplicate tick processing is rejected

**Given** manager already processed tick `t`  
**When** it is called again for tick `t`  
**Then** runtime invariant error is raised rather than duplicating lifecycle events.

---

## AC-48 — Skipped tick processing is rejected

**Given** previous processed tick `t`  
**When** next call is `t+2`  
**Then** manager raises an invariant error because a scheduled activation could have been missed.

---

## AC-49 — Fault manager active IDs match ACTIVE lifecycle state

**Given** a set of pending/active/completed faults  
**When** active IDs are requested  
**Then** only ACTIVE fault IDs are returned.

---

## AC-50 — Active fault ID ordering is deterministic

**Given** identical definitions/lifecycle  
**When** active IDs are returned across runs  
**Then** order is stable.

---

## AC-51 — Fault effects snapshot is immutable/read-only

**Given** an update result  
**When** downstream subsystems consume it  
**Then** they cannot mutate Fault Manager's internal lifecycle state through the returned object.

---

## AC-52 — Activation event identifies fault ID/type/target

**Given** activation  
**When** event is inspected  
**Then** ID, type, and target are present and correct.

---

## AC-53 — Deactivation event identifies same fault

**Given** deactivation  
**When** event is inspected  
**Then** metadata identifies the same configured fault ID/type/target.

---

## AC-54 — Fault Manager performs no event persistence

**Given** fault updates  
**When** events are produced  
**Then** no JSON/CSV files are written directly by Feature 07.

---

## AC-55 — Fault Manager contains no scenario-name branches

**Given** fault/engine source  
**When** inspected  
**Then** behavior does not branch on scenario IDs like `altimeter_freeze`.

---

## AC-56 — New supported fault instances do not require engine-loop edits

**Given** a new scenario uses an already-supported fault type/target  
**When** it is configured  
**Then** core simulation-loop source does not need modification.

---

## AC-57 — Fault Manager does not calculate expected outcome

**Given** a faulted run  
**When** fault code executes  
**Then** it does not decide PASS/FAIL/controlled-abort expectation.

---

## AC-58 — Fault Manager does not modify MissionState directly

**Given** active fault  
**When** behavior changes  
**Then** mission state may respond through normal mission inputs, but Fault Manager does not directly transition it.

---

## AC-59 — Fault Manager does not compute control command

**Given** active fault  
**When** controller executes  
**Then** command remains owned by Feature 04.

---

## AC-60 — Fault Manager does not reimplement sensor fault mechanics

**Given** freeze/bias/delay fault  
**When** fault activates  
**Then** it routes/composes effects and Feature 03 owns actual sensor behavior.

---

## AC-61 — Fault Manager does not reimplement actuator lag physics

**Given** actuator degradation fault  
**When** active  
**Then** Feature 05 remains responsible for actual lag state update.

---

## AC-62 — Time-triggered faults are deterministic independent of wall-clock speed

**Given** identical config and tick progression  
**When** simulation runs under different machine load  
**Then** activation/deactivation ticks are unchanged.

---

## AC-63 — Scenario seed does not alter deterministic fault timing

**Given** same time-triggered fault config but different RNG seed  
**When** runs execute  
**Then** fault lifecycle ticks remain the same.

---

## AC-64 — Same resolved config reproduces same fault lifecycle

**Given** identical resolved fault definitions and mission-state stream for condition triggers  
**When** two managers execute  
**Then** lifecycle states/events/effects match.

---

## AC-65 — Optional mission-state activation is deterministic

**Given** a mission-state-triggered fault waiting for DESCENT  
**When** current committed mission state first equals DESCENT at fault-processing time  
**Then** the fault activates exactly once.

---

## AC-66 — Mission-state trigger does not see later same-tick state transition

**Given** fault processing occurs before mission update  
**When** state changes into DESCENT later on tick `t`  
**Then** an `ON_MISSION_STATE=DESCENT` fault does not activate until the next fault-manager update where DESCENT is already current.

---

## AC-67 — Invalid fault configuration fails before normal simulation

**Given** unknown type/target/missing parameter/impossible timing  
**When** scenario configuration is resolved  
**Then** simulation does not start.

---

## AC-68 — Mission failure caused by fault is a domain result

**Given** injected fault causes poor landing or controlled abort  
**When** run completes  
**Then** Feature 07 does not throw merely because mission outcome is unsuccessful.

---

## AC-69 — At least four non-nominal fault scenarios can alter runtime behavior

**Given** the supported core fault set  
**When** altimeter freeze, velocity bias, sensor delay, and degraded actuator scenarios are configured  
**Then** each causes a genuine subsystem behavior change.

This is a cross-feature portfolio gate completed with Feature 08/10 scenario tests.

---

## AC-70 — Fault lifecycle metadata can be handed to later telemetry

**Given** current tick fault update  
**When** engine constructs telemetry/event inputs  
**Then** active fault IDs and lifecycle events are available without telemetry importing Fault Manager internals.

---

# 7. Test Plan

## Unit tests

Primary files:

```text
tests/unit/test_fault_manager.py
tests/unit/test_fault_effects.py
tests/unit/test_fault_validation.py
```

They may be consolidated if simpler.

---

## Fault-definition/config tests

```text
test_duplicate_fault_id_rejected
test_unknown_fault_type_rejected
test_invalid_sensor_target_rejected
test_invalid_actuator_target_rejected
test_target_type_mismatch_rejected
test_negative_activation_time_rejected
test_non_finite_activation_time_rejected
test_non_aligned_activation_time_rejected
test_zero_duration_rejected
test_deactivation_before_activation_rejected
test_missing_bias_parameter_rejected
test_zero_bias_rejected
test_missing_delay_parameter_rejected
test_negative_delay_rejected
test_invalid_lag_multiplier_rejected
test_noop_actuator_degradation_rejected
```

---

## Lifecycle tests

```text
test_initial_status_pending
test_fault_does_not_activate_before_tick
test_fault_activates_exact_tick
test_activation_event_once
test_permanent_fault_remains_active
test_bounded_fault_deactivates_exact_tick
test_deactivation_event_once
test_completed_fault_does_not_reactivate
test_pending_fault_can_remain_unactivated_at_run_end
```

---

## Tick-order/invariant tests

```text
test_tick_zero_fault_activation
test_duplicate_tick_rejected
test_skipped_tick_rejected
test_activation_event_time_tick_times_dt
test_deactivation_processed_before_new_activation_same_tick
```

---

## Sensor-effect composition tests

```text
test_single_freeze_effect
test_multiple_freezes_logical_or
test_deactivating_one_freeze_preserves_other
test_single_bias_effect
test_multiple_biases_add
test_single_delay_effect
test_multiple_delays_use_max
test_freeze_bias_composition_order_independent
test_freeze_delay_composition_order_independent
```

---

## Actuator-effect composition tests

```text
test_single_lag_multiplier
test_multiple_lag_multipliers_product
test_authority_scales_product
test_rate_scales_product
test_deactivating_one_degradation_preserves_other
test_actuator_composition_order_independent
```

---

## Optional disturbance-effect tests

If implemented:

```text
test_disturbance_force_x
test_disturbance_force_y
test_disturbance_torque
test_multiple_disturbances_add
test_zero_disturbance_rejected
```

---

## Event tests

```text
test_activation_event_fault_id
test_activation_event_fault_type
test_activation_event_target
test_activation_event_tick
test_deactivation_event_metadata
test_no_duplicate_lifecycle_events
```

---

## Integration tests with Feature 03 Sensors

Recommended:

```text
tests/integration/test_fault_sensor.py
```

### Altimeter freeze

At exact known tick:

- activate fault;
- verify freeze is visible same tick;
- verify no new external sample;
- verify source tick stops;
- verify age increases;
- verify stale status eventually occurs.

### Velocity bias

- zero noise preferred for direct test;
- compare measured velocity immediately before/after activation;
- verify additional bias magnitude.

### Sensor delay

- activate delay;
- verify target sensor returns older eligible sample;
- deactivate;
- verify nominal delay resumes according to Feature 03 semantics.

### Overlapping sensor faults

Use compatible overlap and verify composition.

---

## Integration tests with Feature 05 Actuators

Recommended:

```text
tests/integration/test_fault_actuator.py
```

### Sluggish actuator

Same command sequence:

```text
nominal
vs
lag_multiplier > 1
```

Verify degraded actual response is slower.

### Activation tick

Verify degradation begins on exact activation tick's actuator update.

### Deactivation

Verify nominal parameters resume without actuator state teleportation.

---

## Integration tests with Feature 06 Mission State Machine

Recommended:

```text
tests/integration/test_fault_mission.py
```

### Altimeter freeze to stale to ABORT

Test causal chain:

```text
fault activates
-> sensor freezes
-> sensor becomes stale
-> mission critical-input invalid count increases
-> mission enters ABORT
```

The exact expected final behavior depends on configured mission policy.

Fault Manager must not call state transition directly.

---

## Integration tests with Feature 02 Engine

Recommended:

```text
tests/integration/test_fault_engine_order.py
```

Instrument ordering:

```text
fault manager
before
sensor update
before
mission/controller
before
actuator/dynamics
```

Verify manager called once per tick and never inside RK4.

---

## Scenario tests deferred to Feature 08/10

Later files:

```text
tests/scenarios/test_nominal.py
tests/scenarios/test_fault_scenarios.py
```

Required bundled cases:

```text
altimeter_freeze
velocity_bias
sensor_delay
degraded_actuator
```

Assertions include:

- expected fault activated;
- runtime behavior genuinely changed;
- same config/seed reproduces outcome;
- validator's expected outcome matches.

Feature 07 only provides fault machinery.

---

## Telemetry tests deferred to Feature 09

Later assert:

- activation event serialized;
- deactivation event serialized;
- active fault IDs available in telemetry/summary if included;
- plot marker corresponds to event time.

---

## Manual QA checklist

- [ ] Fault type enum exists.
- [ ] Fault IDs are unique.
- [ ] Targets reuse typed subsystem names.
- [ ] Unknown types/targets fail before run.
- [ ] Activation timing resolves to ticks.
- [ ] No wall-clock fault timing exists.
- [ ] Non-aligned activation times are rejected.
- [ ] Fault activation occurs before sensor sampling.
- [ ] Actuator degradation affects same-tick actuator update.
- [ ] Fault Manager updates once per engine tick.
- [ ] Duplicate/skipped tick processing is guarded.
- [ ] PENDING/ACTIVE/COMPLETED lifecycle is explicit.
- [ ] Activation event occurs once.
- [ ] Deactivation event occurs once.
- [ ] Permanent faults remain active.
- [ ] Freeze routes to sensor freeze behavior.
- [ ] Bias routes to sensor bias behavior.
- [ ] Delay routes to sensor buffer behavior.
- [ ] Degradation routes to actuator runtime modifiers.
- [ ] Fault manager does not reimplement sensor/actuator internals.
- [ ] Multiple freeze faults compose safely.
- [ ] Multiple bias faults compose additively.
- [ ] Multiple delays use documented rule.
- [ ] Multiple degradation modifiers compose deterministically.
- [ ] Deactivation removes only that fault's contribution.
- [ ] No "last fault wins" hidden behavior.
- [ ] No scenario-name branches exist in engine/subsystems.
- [ ] Mission state is not directly mutated.
- [ ] Controller command is not directly modified by actuator fault.
- [ ] PASS/FAIL is not decided by fault manager.
- [ ] Events are returned, not written to disk.
- [ ] All fault unit/integration tests pass.

---

## Demo verification checklist

- [ ] `altimeter_freeze` visibly changes measured altitude behavior.
- [ ] Freeze activation is marked at exact simulation time.
- [ ] Frozen measurement age/staleness is visible.
- [ ] `velocity_bias` visibly offsets measured velocity.
- [ ] `sensor_delay` visibly trails truth/current samples.
- [ ] `degraded_actuator` visibly separates requested vs actual response.
- [ ] Same resolved fault config reproduces same activation ticks.
- [ ] Faulted behavior emerges through actual subsystems.
- [ ] Core engine contains no scenario-specific fault branch.
- [ ] Multiple compatible faults can coexist.
- [ ] Fault event data is ready for Feature 09 serialization.

---

# 8. Portfolio Value

## How this feature helps the project stand out

The master blueprint explicitly identifies reproducible fault injection as the strongest direct signal for validation/testing roles.

The strongest story is not:

> "I made a scenario fail."

It is:

> "I built typed faults that activate at deterministic simulation ticks and modify the actual sensor or actuator subsystem. The flight software then reacts naturally to the changed behavior, and the resulting mission is automatically validated."

That demonstrates:

- systems thinking;
- test architecture;
- dependency boundaries;
- event timing;
- deterministic failure reproduction;
- validation engineering.

---

## What to mention in README

Recommended wording:

> **Reproducible fault injection:** AstraLoop injects typed sensor and actuator failures at deterministic simulation ticks or supported mission conditions. Faults modify real subsystem behavior—such as freezing an altimeter, biasing a velocity measurement, increasing sensor delay, or slowing an actuator—without scenario-specific branches in the core engine.

Useful bullets:

- `sensor_freeze`;
- `sensor_bias`;
- `sensor_delay`;
- `actuator_degradation`;
- exact tick activation;
- optional bounded duration/deactivation;
- composable overlapping faults;
- structured activation/deactivation events;
- real subsystem effects;
- no cosmetic result-label faults.

---

## What to mention in interviews

### How are faults injected without duplicating scenarios in code?

> "Scenarios resolve into typed fault definitions. A central Fault Manager activates them using simulation ticks and composes current subsystem effects. The engine never checks the scenario name."

### What happens when an altimeter freeze activates?

> "Fault activation happens before sensor sampling on that tick. The manager enables the altimeter's freeze effect, so the sensor holds its previous deliverable reading and source timestamp. As simulation time advances, the measurement eventually becomes stale and the flight software responds through its normal health logic."

### How do you guarantee exact fault timing?

> "Human-facing activation times are resolved to integer simulation ticks. Non-aligned times are rejected rather than silently rounded. The fault manager runs once per tick before sensor sampling."

### What if two faults target the same sensor?

> "I defined deterministic composition rules instead of using last-write-wins. Freeze is logical OR, bias is additive, and delay uses the maximum active delay. Deactivating one fault removes only its contribution."

### How is degraded actuation modeled?

> "The fault manager changes target-local runtime modifiers, such as the actuator lag multiplier. The actuator module still owns the actual first-order response equation."

### Does the fault manager know whether the mission should pass?

> "No. That's deliberately separate. Faults modify behavior; mission validation decides whether the resulting outcome matched the scenario expectation."

### Why not use arbitrary fault-condition expressions?

> "The MVP uses explicit typed triggers like simulation time and, if needed, mission-state activation. A generic expression DSL would add complexity without strengthening the core portfolio signal."

### How do faults affect reproducibility?

> "Fault timing is deterministic and tick-based. Stochastic sensors still use their seeded subsystem RNGs, so the same resolved configuration and seed reproduce the same failure behavior and outcome."

---

# 9. Implementation Notes for Codex

## Likely files/folders

Primary:

```text
src/astraloop/faults/
├── __init__.py
├── base.py
├── manager.py
├── sensor_faults.py
├── actuator_faults.py
└── disturbances.py          # optional/defer if external disturbance omitted
```

Shared model/events:

```text
src/astraloop/model/events.py
src/astraloop/model/results.py   # only if active-fault view/result type belongs there
```

Config touchpoints:

```text
src/astraloop/config/schema.py
src/astraloop/config/validation.py
```

Tests:

```text
tests/unit/test_fault_manager.py
tests/unit/test_fault_effects.py
tests/unit/test_fault_validation.py

tests/integration/test_fault_sensor.py
tests/integration/test_fault_actuator.py
tests/integration/test_fault_engine_order.py
tests/integration/test_fault_mission.py
```

---

## Suggested responsibilities

### `faults/base.py`

Own shared fault-domain types:

```text
FaultType
FaultStatus
FaultEventType
FaultActivation
FaultDeactivation
FaultRuntimeState
FaultEffects
```

Keep this file focused.

---

### `faults/sensor_faults.py`

Own typed configs/effect composition helpers for:

```text
sensor_freeze
sensor_bias
sensor_delay
```

Do not implement SensorChannel mechanics here.

---

### `faults/actuator_faults.py`

Own typed config/effect composition for:

```text
actuator_degradation
```

Do not implement first-order actuator equations here.

---

### `faults/disturbances.py`

Only if optional external disturbance is implemented.

Own typed disturbance fault definitions/effect combination.

Do not rewrite dynamics.

---

### `faults/manager.py`

Own:

- runtime lifecycle state;
- tick-order validation;
- trigger evaluation;
- activation/deactivation;
- active registry;
- effect composition orchestration;
- event generation.

Do not load scenario files.

---

## Build order

### Step 1 — Lock supported MVP fault types

Start with exactly:

```text
sensor_freeze
sensor_bias
sensor_delay
actuator_degradation
```

Do not add external disturbance until these work end to end.

---

### Step 2 — Define typed targets and fault configs

Reuse:

```text
SensorName
```

and add/confirm:

```text
ActuatorName
```

Reject mismatched types early.

---

### Step 3 — Implement tick-based activation type

Resolve human time in config layer.

Fault Manager should receive integer ticks.

---

### Step 4 — Implement lifecycle engine with no real subsystem

Test:

```text
PENDING
-> ACTIVE
-> COMPLETED
```

and lifecycle events.

---

### Step 5 — Add sequential-tick invariant

Protect against duplicate/skipped update calls.

---

### Step 6 — Implement no-op effect snapshot

Nominal/no active faults must require no special engine path.

---

### Step 7 — Implement sensor-freeze effect

Integrate with Feature 03.

Lock activation-on-sample-tick semantics.

---

### Step 8 — Implement sensor bias

Use additive composition.

---

### Step 9 — Implement sensor delay

Use max-delay composition.

---

### Step 10 — Implement actuator degradation

Start with lag multiplier only.

Add authority/rate modifiers only if already supported and useful.

---

### Step 11 — Implement overlapping-fault composition tests

Do not wait until scenario tests to define conflicts.

---

### Step 12 — Integrate Fault Manager into engine tick order

Exact location:

```text
after simulator terminal/safety check
before sensor sampling
```

---

### Step 13 — Integrate Mission State Machine causally

Do not directly transition mission state.

Test fault -> subsystem -> measurement health -> mission response.

---

### Step 14 — Expose fault events/active IDs to engine

Feature 09 can persist later.

---

### Step 15 — Add optional mission-state trigger only if needed

Time activation is enough for the canonical source example.

Do not overbuild condition logic.

---

### Step 16 — Defer scenario-runner behavior

Feature 08 will own:

- loading `scenarios/*.toml`;
- listing scenarios;
- complete scenario cross-field validation;
- constructing engine and fault manager;
- run application service.

Feature 07 should not absorb that work.

---

## Risks

### Risk 1 — Cosmetic fault injection

The worst implementation is one where fault config changes only a label.

**Mitigation:** every supported fault has an integration test proving a real subsystem behavior difference.

---

### Risk 2 — Scenario-name branching spreads through code

**Mitigation:** typed fault configs + central manager + subsystem hooks.

---

### Risk 3 — Timing off by one tick

This can completely change failure behavior.

**Mitigation:** architecture fixes manager before sensor sampling; exact tick tests.

---

### Risk 4 — Time converted with silent rounding

**Mitigation:** require tick alignment.

---

### Risk 5 — Multiple faults overwrite each other

**Mitigation:** explicit composition rules.

---

### Risk 6 — Deactivating one fault clears another

**Mitigation:** recompute effect from the complete ACTIVE fault set every tick rather than maintaining fragile incremental flags.

This is a key implementation recommendation.

---

### Risk 7 — Fault Manager owns too much subsystem logic

**Mitigation:** manager produces effects; sensor/actuator modules implement mechanics.

---

### Risk 8 — Generic condition DSL scope creep

Avoid:

- arbitrary expressions;
- eval;
- AST rule engines;
- scripting callbacks from TOML.

Use typed supported triggers.

---

### Risk 9 — Fault scheduled after terminal mission never activates

This is a valid possible run outcome.

**Mitigation:** leave fault pending; later validator can identify expected fault not activated.

---

### Risk 10 — No-op fault looks like validation coverage

Examples:

```text
bias = 0
delay equals nominal
lag multiplier = 1
```

**Mitigation:** cross-field/no-op validation.

---

### Risk 11 — Fault manager changes requested controller command

For actuator fault this breaks architecture.

**Mitigation:** change actuator physical modifier only.

---

### Risk 12 — Fault manager directly forces ABORT

This can make the failure story artificial.

**Mitigation:** prefer real subsystem consequence -> measurement/status -> mission logic. A generic explicit abort request may exist only for a deliberately modeled safety behavior, not as the default outcome of every fault.

---

### Risk 13 — Fault manager uses RNG unnecessarily

Core canonical faults are deterministic.

**Mitigation:** no RNG in fault manager for MVP.

If stochastic fault activation is added later, it must use an injected dedicated RNG and explicit seed derivation.

---

## What not to change

While implementing Feature 07, Codex should **not**:

- change 2D dynamics equations;
- change RK4;
- change simulation tick/time semantics;
- reimplement sensor freeze;
- reimplement sensor bias;
- reimplement sensor delay buffering;
- change PID/controller equations;
- reimplement actuator lag equations;
- change mission transition graph merely to make a fault pass;
- directly set final PASS/FAIL from a fault;
- directly set expected scenario outcome;
- write telemetry CSV;
- write events JSON;
- implement diagnostic plots;
- implement CLI commands;
- implement full scenario-file runner;
- create campaign/batch command behavior;
- add arbitrary condition-expression DSLs;
- add scenario-name branches;
- add database/cloud/SaaS infrastructure;
- add physical hardware integration.

---

# Feature-Specific Definition of Done

Feature 07 is complete when:

- [ ] Typed fault definitions exist.
- [ ] Core supported types include sensor freeze, sensor bias, sensor delay, and actuator degradation.
- [ ] Every fault has a unique stable ID.
- [ ] Fault targets are typed/validated.
- [ ] Unknown/mismatched targets fail before run.
- [ ] Time activation resolves to integer simulation tick.
- [ ] Non-aligned activation time is rejected.
- [ ] PENDING/ACTIVE/COMPLETED lifecycle is implemented.
- [ ] Activation occurs exactly once.
- [ ] Deactivation occurs exactly once when configured.
- [ ] Permanent faults remain active.
- [ ] Fault Manager runs once per simulation tick.
- [ ] Duplicate/skipped tick calls are guarded.
- [ ] Fault processing occurs before sensor sampling.
- [ ] Sensor freeze affects same-tick sensor behavior.
- [ ] Sensor bias affects actual sampled values.
- [ ] Sensor delay affects actual buffer delivery behavior.
- [ ] Actuator degradation affects same-tick actuator response.
- [ ] Fault Manager does not mutate controller command for actuator faults.
- [ ] Fault Manager does not directly change MissionState.
- [ ] Fault Manager does not calculate PASS/FAIL.
- [ ] Activation/deactivation events are generated.
- [ ] Events include tick/time/id/type/target.
- [ ] Events are returned rather than persisted by Feature 07.
- [ ] Active fault IDs are exposed in deterministic order.
- [ ] Multiple freeze faults compose correctly.
- [ ] Multiple bias faults compose additively.
- [ ] Multiple delay faults use documented max rule.
- [ ] Multiple actuator modifiers compose deterministically.
- [ ] Deactivating one overlapping fault preserves others.
- [ ] No-op fault configs are rejected/flagged.
- [ ] No scenario-name branches exist in core logic.
- [ ] Nominal empty-fault path needs no special engine branch.
- [ ] Fault effects are deterministic.
- [ ] Core fault manager uses no RNG.
- [ ] Unit tests cover lifecycle, timing, validation, and composition.
- [ ] Sensor-fault integration tests pass.
- [ ] Actuator-fault integration tests pass.
- [ ] Engine-order integration tests pass.
- [ ] Fault-to-mission causal integration test passes.
- [ ] At least four non-nominal fault definitions can genuinely alter runtime behavior.
- [ ] Feature remains independent of full scenario runner, telemetry persistence, and validation.

---

# Open Questions

1. **[Open Question] Which exact sensor should the canonical `sensor_delay` scenario target?**  
   The source confirms the scenario but does not specify the target.

2. **[Open Question] Should canonical `velocity_bias` target vertical velocity or another velocity channel?**  
   Vertical velocity is the strongest fit because Feature 04 throttle control directly consumes it.

3. **[Open Question] Should canonical `degraded_actuator` target throttle or gimbal?**  
   A gimbal lag fault gives a clear requested-vs-actual attitude-control demonstration; throttle lag may more directly affect landing descent. Choose after nominal controller tuning.

4. **[Open Question] What exact bias magnitude should the bundled `velocity_bias` scenario use?**

5. **[Open Question] What exact delay should the bundled `sensor_delay` scenario use?**

6. **[Open Question] What exact lag multiplier should the bundled `degraded_actuator` scenario use?**

7. **[Open Question] What activation times should the four canonical fault scenarios use?**  
   The blueprint gives `20.0 s` as an example for altimeter freeze, not a required universal value.

8. **[Open Question] Should canonical faults be permanent after activation or deactivate after a duration?**  
   Permanent faults are simpler and stronger for initial validation; bounded faults are still useful to prove lifecycle support.

9. **[Open Question] Should `ON_MISSION_STATE` activation be included in MVP or deferred until a scenario needs it?**  
   Time activation is source-proven and sufficient for the initial bundled cases.

10. **[Open Question] Should optional `external_disturbance` be implemented after the core four faults?**  
    Only after the first five total scenarios (`nominal` + four faults) are stable, matching the master blueprint.

11. **[Open Question] Should actuator degradation support only `lag_multiplier` initially?**  
    Recommended yes. Add authority/rate degradation only if they strengthen a tested scenario.

12. **[Open Question] Should a pending fault at run termination appear as a dedicated final `NOT_ACTIVATED` lifecycle status or remain `PENDING` with runner-level interpretation?**  
    Recommended: keep runtime lifecycle simple (`PENDING/ACTIVE/COMPLETED`) and let run result report "not activated."

13. **[Open Question] Should fault definitions allow condition-based deactivation?**  
    Recommended defer until a concrete scenario needs it.

14. **[Open Question] Should a fault ever directly request MissionState.ABORT?**  
    Recommended baseline: no. Prefer genuine subsystem effects that naturally cause the mission logic to react. Add a generic explicit abort fault only if a specific safety test requires it.

---

# Move On When

- [ ] Every supported fault type has clear Given/When/Then acceptance criteria.
- [ ] Exact tick activation/deactivation is tested.
- [ ] Faults alter actual sensor/actuator behavior.
- [ ] Fault activation events are structured and deterministic.
- [ ] Multiple compatible faults compose safely.
- [ ] No scenario-name branching exists in engine/subsystems.
- [ ] A reviewer can clearly demonstrate altimeter freeze, velocity bias, sensor delay, and degraded actuator behavior.
- [ ] Fault timing and active-effect behavior are reproducible.
- [ ] Feature clearly proves validation/test architecture skill.
- [ ] Scenario loading/CLI/campaign logic remains outside this feature.
- [ ] Telemetry persistence remains outside this feature.
- [ ] Mission validation/expected-outcome checking remains outside this feature.
- [ ] Optional external disturbance has not distracted from completing the required core fault set.
- [ ] The scope remains finishable and ready for Feature 08 — Config-Driven Scenario Runner.
