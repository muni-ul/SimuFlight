# Feature 03 — Simulated Sensor System

> **Project:** AstraLoop — Python Software-in-the-Loop Flight Control & Validation System  
> **Feature:** Simulated Sensor System  
> **Document path:** `docs/features/03-simulated-sensor-system.md`  
> **Status:** Implementation specification  
> **Primary goal:** Build the deterministic truth-to-measurement boundary for AstraLoop so flight software receives realistic, timestamped, imperfect sensor data instead of direct access to perfect simulator truth.

---

## Scope Boundary

**[Confirmed]** AstraLoop's central architecture rule is that the controller must not use perfect `VehicleState` as its normal input. The simulation engine owns truth state; sensors sample that truth; flight-software components consume software-visible measurements.

**[Confirmed]** The selected sensor suite includes:

- altimeter → altitude;
- vertical velocity sensor;
- horizontal position sensor;
- horizontal velocity sensor;
- attitude sensor → pitch;
- gyro → angular rate.

**[Confirmed]** Sensor behavior must support selected imperfections including:

- configurable noise;
- constant bias;
- latency/delay;
- freeze behavior;
- stale-reading behavior.

**[Confirmed]** Noise must use injected seeded random-number generators, delay must use simulation-time buffers rather than `sleep()`, and simulation time must remain independent of computer speed.

**[Decision]** Feature 03 owns the **sensor models and measurement-production pipeline**.

It owns:

- the sensor channel definitions;
- truth-to-measurement mapping;
- per-sensor configuration;
- sample cadence;
- deterministic per-sensor RNG state;
- additive Gaussian noise;
- static/configured bias;
- simulation-time delay buffers;
- last-value hold behavior between sample events;
- measurement timestamps and age;
- unavailable/missing measurement behavior;
- stale-reading detection;
- disabled-sensor behavior;
- a sensor-suite coordinator;
- construction of `MeasurementSnapshot`;
- sensor-level primitives/hooks needed later for freeze/bias/delay faults;
- unit and engine-integration tests for sensing behavior.

It does **not** own:

- closed-loop controller equations;
- PID state;
- mission-state transitions;
- actuator modeling;
- general fault scheduling/activation;
- fault scenario definitions;
- telemetry file persistence;
- mission PASS/FAIL evaluation;
- plotting;
- CLI commands;
- scenario campaign execution;
- state estimation/Kalman filtering.

The later **Fault Injection System** may activate or modify sensor impairment primitives, but Feature 03 defines how the sensor itself behaves once an impairment is applied.

---

# 1. Feature Overview

## Feature name

**Simulated Sensor System**

---

## One-sentence description

**[Decision]** Implement a deterministic sensor suite that samples AstraLoop's perfect 2D truth state on explicit simulation-time cadences and exposes timestamped measurements with configurable bias, noise, delay, missing/stale behavior, and future fault hooks.

---

## Detailed description

AstraLoop has two fundamentally different views of the vehicle:

```text
TRUE SIMULATION STATE
        |
        v
 SIMULATED SENSORS
        |
        v
SOFTWARE-VISIBLE MEASUREMENTS
```

The simulation engine can know the exact:

```text
x
y
vx
vy
theta
omega
mass
```

because it owns the numerical model.

The flight software must **not** receive that same object.

Instead, each sensor samples only the truth quantity it represents, applies its configured imperfections, stores timestamped samples, and publishes the measurement currently available to the software.

The result is a `MeasurementSnapshot` that becomes the normal input boundary for later:

```text
Mission State Machine
Closed-Loop Flight Controllers
```

This is what makes AstraLoop a meaningful software-in-the-loop project rather than a controller acting on perfect internal state.

---

## Sensor suite

### 1. Altimeter

Truth source:

```text
VehicleState.y
```

Measurement:

```text
measured altitude [m]
```

Primary later use:

- descent/landing logic;
- throttle controller;
- state-transition guards.

---

### 2. Vertical velocity sensor

Truth source:

```text
VehicleState.vy
```

Measurement:

```text
measured vertical velocity [m/s]
```

Primary later use:

- descent-rate control;
- landing validation logic through software-visible state where appropriate.

---

### 3. Horizontal position sensor

Truth source:

```text
VehicleState.x
```

Measurement:

```text
measured horizontal position [m]
```

Primary later use:

- horizontal-position control;
- landing-target error.

---

### 4. Horizontal velocity sensor

Truth source:

```text
VehicleState.vx
```

Measurement:

```text
measured horizontal velocity [m/s]
```

Primary later use:

- horizontal damping/control.

---

### 5. Attitude sensor

Truth source:

```text
VehicleState.theta
```

Measurement:

```text
measured pitch [rad]
```

**[Decision]** Internal measurement units remain radians.

Human-facing plots/config may convert to degrees later.

---

### 6. Gyro

Truth source:

```text
VehicleState.omega
```

Measurement:

```text
measured angular rate [rad/s]
```

---

## Why mass is not a normal flight-software measurement

**[Decision]** `VehicleState.mass` is not included in the MVP `MeasurementSnapshot` unless a later controller demonstrates a concrete need.

**Justification:** The source blueprint's measurement object contains:

```text
x
y
vx
vy
theta
omega
```

and the project's main truth-separation signal is clearer if only required measurements are exposed.

If fuel/mass estimation becomes necessary later, it should be introduced as an explicit measured/estimated software input rather than quietly exposing perfect truth mass.

---

## Measurement pipeline

For a nominal sensor sample:

```text
TRUE VALUE AT SAMPLE TIME
        |
        v
 nominal sensor transform
        |
        v
 configured constant bias
        |
        v
 seeded random noise
        |
        v
 timestamped raw sensor sample
        |
        v
 simulation-time delay buffer
        |
        v
 currently deliverable sample
        |
        v
 freeze/override primitive if active
        |
        v
 age + validity/staleness evaluation
        |
        v
 SENSOR READING
```

The sensor suite then combines channel readings into:

```text
MeasurementSnapshot
```

---

## Truth-to-measurement formula

For scalar channels in the MVP:

```text
nominal_value = selected truth field
```

Configured static bias:

```text
biased_value = nominal_value + bias
```

Noise:

```text
noise ~ Normal(0, noise_std)
```

Final newly sampled value:

```text
sample_value = nominal_value + bias + noise
```

**[Decision]** Noise is additive Gaussian noise for the MVP.

**Justification:**

- simple;
- testable;
- understandable;
- sufficient to prove deterministic stochastic modeling;
- no need for high-fidelity sensor electronics.

**[Open Question]** Final nominal `noise_std` values for each bundled scenario are not fixed by the planning documents and should be calibrated with the controller later.

---

## Sample cadence

Each sensor has an explicit sampling interval.

Example:

```text
simulation dt = 0.02 s
altimeter sample interval = 0.10 s
```

This means:

```text
sample every 5 simulation ticks
```

**[Decision]** Resolve sensor sample periods to integer simulation ticks during setup.

Recommended validation:

```text
sample_interval > 0

sample_interval / simulation_dt
must be integer-like within a small configuration tolerance
```

Then:

```python
sample_every_ticks = round(sample_interval / dt)
```

### Why integer-tick cadence

The Numerical Simulation Engine already establishes the deterministic clock:

```python
sim_time = tick * dt
```

Using integer tick cadence means the sensor never depends on approximate floating-point conditions such as:

```python
if sim_time >= next_sample_time:
```

It also makes later tests straightforward:

```text
sensor samples on ticks:
0, 5, 10, 15, ...
```

---

## First sample

**[Decision]** An enabled nominal sensor samples at tick `0` unless its configuration explicitly requires otherwise.

This gives immediate software-visible data for zero-delay sensors.

For a delayed sensor, the sample may exist internally at tick `0` but may not yet be deliverable.

---

## Last-value hold

A physical/discrete sensor does not need to generate a new random sample on every simulation tick.

Between sampling instants:

**[Decision]** The sensor continues exposing its most recently deliverable value.

Example:

```text
sample every 5 ticks

tick 0: new sample
tick 1: hold tick-0 sample
tick 2: hold tick-0 sample
tick 3: hold tick-0 sample
tick 4: hold tick-0 sample
tick 5: new sample
```

The reading's source timestamp remains the timestamp of the actual sample.

This lets software reason about measurement age.

---

## Delay model

Sensor delay must be simulation-time delay, not real-time delay.

**[Decision]** Store timestamped generated samples in a per-sensor buffer.

A configured delay represents the minimum age required before a sample becomes deliverable.

Conceptually, at current tick:

```text
delivery_cutoff_tick = current_tick - delay_ticks
```

The sensor returns the newest buffered sample whose:

```text
sample_tick <= delivery_cutoff_tick
```

### Delay configuration

Recommended:

```text
delay_s >= 0
```

Resolve to:

```text
delay_ticks
```

and validate:

```text
delay_s / dt
```

is integer-like.

### Example

```text
dt = 0.02 s
sample interval = 0.10 s = 5 ticks
delay = 0.20 s = 10 ticks
```

Samples are generated at:

```text
0, 5, 10, 15, 20 ...
```

At current tick `10`, the newest sample satisfying:

```text
sample_tick <= 0
```

is the tick-0 sample.

At current tick `15`, the newest deliverable sample is tick 5.

This produces deterministic latency without `sleep()`.

---

## Delay-buffer data

Each raw sample should retain:

```text
value
sample_tick
sample_time
```

**[Decision]** Store the source time with the sample rather than replacing it with delivery time.

This makes it possible to calculate:

```text
measurement_age = current_time - sample_time
```

and makes sensor delay visible to later telemetry/debugging.

---

## Delay buffer size

A sensor does not need to store its entire mission history.

**[Decision]** Keep only enough buffered samples to satisfy the configured delay plus a small safety margin/current sample.

Implementation may use:

```python
collections.deque
```

as selected by the architecture.

Do not build a database or large history store inside the sensor.

Telemetry will later record delivered measurements separately.

---

## Measurement age

For any delivered reading:

```text
age_ticks = current_tick - source_tick
age_seconds = age_ticks * dt
```

**[Decision]** Derive age from ticks where practical rather than subtracting repeatedly accumulated floating-point timestamps.

The current snapshot still exposes human-friendly time in seconds.

---

## Fresh vs stale behavior

The sources call for stale-reading behavior but do not prescribe an exact threshold.

**[Decision]** Define stale status relative to the sensor's expected nominal delivery age.

A reading is nominally expected to be no older than approximately:

```text
delay_ticks + sample_every_ticks
```

Therefore a practical deterministic rule is:

```text
stale if:
age_ticks > delay_ticks + sample_every_ticks
```

This means:

- normal zero-delay sample-and-hold between expected samples is not immediately considered stale;
- normal delayed readings are not considered stale merely because their source timestamp is older;
- a frozen or otherwise non-updating sensor eventually becomes stale.

**[Open Question]** If controller tuning later needs stricter or looser stale semantics, add an explicit `stale_after_ticks` configuration. Do not add it until there is a demonstrated need.

---

## Freeze behavior

Freeze is one of the sensor behaviors required by the project.

The **general fault system** will later decide:

```text
when a freeze activates
which sensor is targeted
when/if it deactivates
what event is logged
```

Feature 03 defines the sensor's response while frozen.

**[Decision]** When freeze becomes active:

- the sensor stops producing new externally visible readings;
- the last deliverable valid reading remains held;
- its source timestamp remains unchanged;
- its age therefore continues increasing;
- it eventually becomes `STALE` under the stale rule.

If freeze activates before the sensor has any deliverable reading:

```text
value = None
status = UNAVAILABLE
```

until freeze is released or another explicitly defined behavior is supplied later.

### Important distinction

Freeze does **not** mean:

```text
keep sampling truth internally and simply hide it
```

for the normal fault behavior.

**Decision:** Once frozen, the channel should stop updating its delivered sensor state so telemetry clearly shows a flat value and growing age.

The internal implementation may choose whether raw sample generation also pauses, but the externally observable behavior must be deterministic and tested.

---

## Bias behavior

Configured nominal bias is applied to each generated sample:

```text
sample = truth + configured_bias + noise
```

The later Fault Injection System may need to apply a runtime velocity bias.

**[Decision]** Feature 03 may expose a small sensor-specific runtime-bias hook, such as:

```python
set_additional_bias(...)
```

or an equivalent injected modifier.

This hook must not know:

- scenario names;
- activation times;
- expected mission outcomes.

General fault orchestration remains outside this feature.

---

## Runtime delay override hook

The later sensor-delay fault may need to increase delay dynamically.

**[Decision]** The sensor/buffer design must make delay a replaceable sensor parameter at runtime, but Feature 03 does not implement fault scheduling.

A runtime delay change must have deterministic semantics.

Recommended:

```text
new delay applies beginning on the fault activation tick
```

Existing timestamped samples remain in the buffer and become eligible according to the new delay.

---

## Disabled sensors

Per-sensor configuration includes:

```text
enabled = true/false
```

For a disabled sensor:

```text
value = None
status = DISABLED
```

It should not consume random draws or create samples.

**Justification:** Disabled components should not perturb RNG streams or create confusing hidden state.

---

## Measurement snapshot

The source architecture proposes a software-visible measurement object equivalent to:

```python
@dataclass(frozen=True)
class MeasurementSnapshot:
    timestamp: float
    x: float | None
    y: float | None
    vx: float | None
    vy: float | None
    theta: float | None
    omega: float | None
```

**[Decision]** Preserve these convenient flat values for controller/state-machine consumption.

Also expose enough metadata to debug imperfect measurements.

Recommended additional structured metadata:

```python
@dataclass(frozen=True)
class MeasurementMetadata:
    source_tick: int | None
    source_time: float | None
    age_ticks: int | None
    age_seconds: float | None
    status: MeasurementStatus
```

And:

```python
@dataclass(frozen=True)
class MeasurementSnapshot:
    tick: int
    timestamp: float

    x: float | None
    y: float | None
    vx: float | None
    vy: float | None
    theta: float | None
    omega: float | None

    metadata: Mapping[SensorName, MeasurementMetadata]
```

**Decision:** If an immutable mapping becomes awkward, use a dedicated metadata dataclass with named sensor fields. Do not choose a mutable global dictionary.

---

## Measurement status

Recommended enum:

```text
VALID
STALE
UNAVAILABLE
DISABLED
```

### `VALID`

A usable reading exists and is within expected age.

### `STALE`

A value exists but has not updated within its expected age window.

### `UNAVAILABLE`

No deliverable measurement exists yet.

Common example:

```text
delay buffer has not filled
```

### `DISABLED`

Sensor is intentionally disabled by configuration.

**Decision:** Do not represent all four states with only `None`.

The flat measurement value may be `None`, but metadata should retain the reason.

---

## Deterministic random-number generation

**[Confirmed]** The architecture forbids hidden global NumPy RNG state and requires seeded sensor RNG objects.

**[Decision]** Every stochastic sensor owns its own injected:

```python
numpy.random.Generator
```

Do not use:

```python
np.random.normal(...)
```

through global state.

### Scenario seed

A run begins with one configured scenario seed.

Example:

```text
seed = 42
```

From that seed, the setup layer derives independent streams for:

```text
altimeter
vertical_velocity
horizontal_position
horizontal_velocity
attitude
gyro
```

### Stable derivation

**[Decision]** Derive streams in a canonical, fixed sensor order using `numpy.random.SeedSequence`, or an equivalent explicit deterministic method.

Do not depend on:

- Python's process-randomized `hash()`;
- unordered mapping iteration;
- one shared RNG consumed by every sensor.

### Why separate RNGs matter

If all sensors share one RNG:

```text
adding one extra altimeter draw
```

can silently change:

```text
gyro noise
horizontal sensor noise
every later stochastic value
```

With independent sensor RNGs, local implementation changes remain local.

This is a strong reproducibility design choice.

---

## Noise draw timing

**[Decision]** Draw random noise only when the sensor creates a new sample.

Do not generate a new random value merely because the engine tick advanced while the sensor is holding its previous sample.

This preserves:

- correct sample cadence;
- deterministic random draw count;
- sensible last-value-hold behavior.

---

## Sensor ownership/state

Unlike the pure flight-dynamics function, simulated sensors are stateful.

Each sensor owns only its own state:

```text
RNG
sample cadence bookkeeping
delay buffer
last deliverable reading
freeze state / impairment primitive
runtime bias/delay modifier if enabled
```

The Simulation Engine owns:

```text
truth state
simulation tick/time
```

The sensor suite must not mutate the truth state.

---

## Why it matters

This feature is one of AstraLoop's strongest differentiators.

Without it, a later controller could simply read:

```python
state.y
state.vy
state.theta
```

and behave like a perfect-information demonstration.

With the sensor boundary:

```text
truth
 -> sample cadence
 -> noise
 -> bias
 -> delay
 -> missing/stale behavior
 -> measurements
 -> flight software
```

the project has to deal with:

- imperfect inputs;
- timing;
- state ownership;
- deterministic randomness;
- failure behavior;
- missing data;
- interface design.

That is much closer to the systems/simulation/validation software signal the project is intended to demonstrate.

---

## Skill it demonstrates

A strong implementation demonstrates:

- interface design;
- truth-state isolation;
- deterministic stochastic modeling;
- NumPy RNG discipline;
- simulation-time scheduling;
- buffering;
- data freshness/age semantics;
- immutable typed measurement records;
- stateful component ownership;
- reproducibility;
- fault-ready subsystem design;
- unit testing;
- integration testing;
- software architecture restraint.

---

## Priority

**P0/P1 — Core closed-loop prerequisite**

The project cannot honestly implement closed-loop flight controllers until this feature exists.

The correct dependency order is:

```text
2D Flight Dynamics
      |
      v
Numerical Simulation Engine
      |
      v
Simulated Sensor System
      |
      v
Closed-Loop Flight Controllers
```

---

## Complexity

**High**

Most code can remain small, but timing and state semantics are subtle.

Common bug sources include:

- off-by-one sampling ticks;
- delay-buffer selection errors;
- RNG streams changing unexpectedly;
- noise being redrawn while holding a sample;
- source timestamp being replaced by delivery time;
- stale logic incorrectly marking normal delayed samples;
- freeze before first valid reading;
- truth accidentally leaking into controller APIs.

---

# 2. User / Demo Flow

The direct runtime consumer is the later flight software, but a reviewer should be able to understand sensor behavior through deterministic tests and later diagnostic plots.

---

## Happy path

1. The Simulation Engine owns current truth:

```text
tick
sim_time
VehicleState
```

2. The engine calls the sensor suite for the current tick.
3. Each enabled sensor checks whether this is one of its sampling ticks.
4. Sensors due to sample read only their relevant truth field.
5. Static bias is applied.
6. Seeded noise is drawn and applied.
7. A timestamped sample is added to the sensor's buffer.
8. Each sensor determines the newest sample eligible under its configured delay.
9. Freeze/impairment state is applied if active.
10. Measurement age/status is calculated.
11. The suite creates one immutable `MeasurementSnapshot`.
12. The later mission logic/controller receives the snapshot, not `VehicleState`.

---

## First-time path

Recommended implementation/proving sequence:

### Step A — Zero-imperfection identity sensor

Configure:

```text
noise_std = 0
bias = 0
delay = 0
sample interval = dt
```

Verify:

```text
measurement == corresponding truth field
```

for all six channels.

### Step B — Sample cadence

Configure one sensor to sample every 5 engine ticks.

Verify:

- new samples only on ticks `0, 5, 10, ...`;
- held value remains unchanged on intermediate ticks;
- source timestamp remains the timestamp of the last sample.

### Step C — Static bias

Set:

```text
bias = +2.0
noise = 0
```

Verify every new sample is exactly:

```text
truth + 2.0
```

### Step D — Seeded noise

Run the same configured sample sequence twice with the same seed.

Verify the sequences match.

Then use a different seed and verify at least one stochastic sample changes.

### Step E — Delay

Configure a known sample period and delay.

Verify the exact sample tick delivered on every engine tick.

### Step F — Missing startup measurement

Use delay > 0.

Verify `UNAVAILABLE` until a sample becomes eligible.

### Step G — Freeze primitive

Freeze a channel after a valid reading.

Verify:

- value remains fixed;
- source timestamp remains fixed;
- age grows;
- status eventually becomes stale.

Only after these tests pass should Feature 04 Closed-Loop Flight Controllers consume the suite.

---

## Empty state

### No sensors enabled

The suite may still construct a snapshot:

```text
all values = None
all statuses = DISABLED
```

This is valid infrastructure behavior, although a later controller may reject the snapshot as unusable.

### Delay buffer not yet populated

Return:

```text
value = None
status = UNAVAILABLE
```

Do not fabricate:

- zero;
- current truth;
- future sample;
- first sample early.

---

## Error path

### Invalid sensor configuration

Examples:

```text
sample_interval <= 0
noise_std < 0
delay < 0
non-finite bias
non-finite noise_std
sample period not aligned to dt
delay not aligned to dt
```

Expected:

- fail during configuration/setup;
- identify sensor name and field.

### Invalid truth input

If the truth field a sensor needs is NaN/Inf:

**[Decision]** The sensor should fail clearly rather than turn it into a normal noisy reading.

The Simulation Engine should normally catch invalid truth state earlier, but the sensor boundary should remain defensive.

### RNG missing for stochastic sensor

If:

```text
noise_std > 0
```

and no RNG is injected:

- fail setup/programming validation.

Do not silently fall back to global randomness.

### Buffer inconsistency

If timestamps/ticks become non-monotonic:

- raise a sensor invariant error.

### Invalid runtime delay/bias modifier

Reject non-finite or negative values according to the modifier type.

---

## Demo path for a reviewer

### Demo A — Truth vs measured altitude

Later diagnostic plot shows:

```text
true altitude
measured altitude
```

with small seeded noise.

Explain:

> "The controller sees the measured line, not the truth line."

### Demo B — Delay

Use a deterministic sensor-delay scenario.

Show that the measurement curve trails truth and that metadata records an older source timestamp.

Explain:

> "Latency is modeled with simulation-time buffers. The program does not sleep."

### Demo C — Freeze

Freeze altimeter output during descent.

Show:

- flat measured altitude;
- changing true altitude;
- increasing measurement age;
- stale status;
- deterministic activation handled later by the fault system.

### Demo D — Reproducibility

Run the same seed twice.

Show identical sensor noise sequence.

Then change the seed.

Show changed noise sequence without changing physical/config logic.

### Demo E — API boundary

Show controller function signature later:

```python
controller.update(
    measurement: MeasurementSnapshot,
    ...
)
```

and point out that it does not receive `VehicleState`.

Reviewer takeaway:

> "Imperfect sensing is a real software boundary, not just noise added to a plot after the fact."

---

# 3. UX / UI Requirements

## Screens/pages

**[Decision]** No dedicated sensor UI/page is required.

The feature is headless.

Later visualization should make sensor behavior inspectable through:

- truth-vs-measurement plots;
- fault markers;
- timestamps/age if useful;
- terminal summary only when a sensor issue is relevant.

Sensor implementation must not import Matplotlib or Rich.

---

## Components

Recommended software components:

```text
SensorName
MeasurementStatus
SensorConfig
SensorSample
SensorReading
MeasurementMetadata
MeasurementSnapshot
SensorChannel
DelayBuffer
SensorSuite
RNG factory/setup helper
```

Avoid an inheritance hierarchy unless multiple concrete implementations truly need one.

---

## Forms/inputs

No GUI form.

Per-sensor configuration should support:

```text
enabled
sample_interval_s
noise_std
bias
delay_s
```

Potential later runtime modifiers:

```text
additional_bias
freeze
delay_override
```

but the general fault configuration/scheduling belongs to Feature 07 Fault Injection System.

---

## Buttons/actions

None.

---

## Validation messages

Examples:

```text
Invalid sensor config [altimeter]: sample_interval_s must be > 0; received 0.0.
Invalid sensor config [gyro]: noise_std must be finite and >= 0; received -0.02.
Invalid sensor config [vertical_velocity]: delay_s=0.07 is not aligned to simulation dt=0.02.
Sensor [attitude] requires a seeded RNG because noise_std > 0.
Sensor invariant failed [altimeter] at tick 125: sample ticks are not monotonic.
Sensor [horizontal_position] received non-finite truth value x=nan.
```

Messages should include:

- sensor name;
- invalid field;
- value;
- expected rule.

---

## Empty states

### Disabled

Metadata:

```text
DISABLED
```

Value:

```text
None
```

### Not yet deliverable

Metadata:

```text
UNAVAILABLE
```

Value:

```text
None
```

### Frozen before first valid reading

Metadata:

```text
UNAVAILABLE
```

until a valid deliverable value exists after release.

---

## Loading states

None.

Sampling and buffering are in-process operations.

No wall-clock waiting.

---

## Error states

Use a small domain-specific set, for example:

```text
SensorConfigError
SensorRuntimeError
```

Do not create dozens of subclasses.

Configuration errors should normally happen before simulation begins.

Runtime errors should be reserved for corrupted or impossible state.

---

## Responsive behavior

Not relevant.

---

# 4. Data Requirements

## Entities involved

### `SensorName`

Recommended enum:

```python
class SensorName(Enum):
    ALTIMETER = "altimeter"
    VERTICAL_VELOCITY = "vertical_velocity"
    HORIZONTAL_POSITION = "horizontal_position"
    HORIZONTAL_VELOCITY = "horizontal_velocity"
    ATTITUDE = "attitude"
    GYRO = "gyro"
```

**Decision:** Use stable explicit string values.

These names later become valid fault targets and telemetry labels.

---

### `SensorConfig`

Recommended:

```python
@dataclass(frozen=True)
class SensorConfig:
    enabled: bool
    sample_interval: float
    noise_std: float
    bias: float
    delay: float
```

Resolved runtime values may include:

```text
sample_every_ticks
delay_ticks
```

These may live in a separate resolved config rather than mixing human units and runtime tick values.

---

### `ResolvedSensorConfig`

Recommended if it improves clarity:

```python
@dataclass(frozen=True)
class ResolvedSensorConfig:
    enabled: bool
    sample_every_ticks: int
    noise_std: float
    bias: float
    delay_ticks: int
```

**Decision:** Do not expose both independently mutable second-based and tick-based values at runtime.

---

### `SensorSample`

Represents a generated measurement at the time truth was sampled.

```python
@dataclass(frozen=True)
class SensorSample:
    value: float
    sample_tick: int
```

Human-readable sample time is:

```python
sample_tick * dt
```

It does not need to be separately stored unless that improves serialization clarity.

---

### `MeasurementStatus`

```text
VALID
STALE
UNAVAILABLE
DISABLED
```

---

### `SensorReading`

Recommended:

```python
@dataclass(frozen=True)
class SensorReading:
    sensor: SensorName
    value: float | None
    source_tick: int | None
    current_tick: int
    status: MeasurementStatus
```

Convenience properties can derive:

```text
source_time
current_time
age_ticks
age_seconds
```

using `dt`.

---

### `MeasurementMetadata`

If flat values are retained in `MeasurementSnapshot`:

```python
@dataclass(frozen=True)
class MeasurementMetadata:
    source_tick: int | None
    age_ticks: int | None
    status: MeasurementStatus
```

---

### `MeasurementSnapshot`

Recommended controller-facing contract:

```python
@dataclass(frozen=True)
class MeasurementSnapshot:
    tick: int
    timestamp: float

    x: float | None
    y: float | None
    vx: float | None
    vy: float | None
    theta: float | None
    omega: float | None

    metadata: ...
```

The snapshot is immutable.

---

### `SensorChannel`

Owns one sensor's runtime state.

Responsibilities:

```text
truth-field extraction
sampling schedule
bias/noise
delay buffer
last delivered sample
freeze primitive
runtime sensor modifiers if needed
```

---

### `SensorSuite`

Owns the six sensor channels.

Responsibilities:

- invoke each sensor deterministically for the current tick;
- build the complete snapshot;
- provide lookup by `SensorName` for later fault targeting;
- avoid leaking `VehicleState` downstream.

---

## Fields and units

| Measurement | Truth field | Unit |
|---|---|---|
| horizontal position | `x` | m |
| altitude | `y` | m |
| horizontal velocity | `vx` | m/s |
| vertical velocity | `vy` | m/s |
| pitch | `theta` | rad |
| angular rate | `omega` | rad/s |

Configuration fields:

| Field | Unit | Constraint |
|---|---|---|
| `sample_interval` | s | finite, `> 0` |
| `noise_std` | measurement unit | finite, `>= 0` |
| `bias` | measurement unit | finite |
| `delay` | s | finite, `>= 0` |
| `sample_every_ticks` | ticks | integer, `>= 1` |
| `delay_ticks` | ticks | integer, `>= 0` |

---

## Relationships

```text
VehicleState (truth)
        |
        v
    SensorSuite
        |
        +--> Altimeter
        +--> Vertical Velocity
        +--> Horizontal Position
        +--> Horizontal Velocity
        +--> Attitude
        +--> Gyro
        |
        v
MeasurementSnapshot
        |
        +--> Mission State Machine
        |
        +--> Closed-Loop Controllers
```

Per channel:

```text
truth field
   |
sample cadence
   |
bias
   |
seeded noise
   |
timestamped sample
   |
delay buffer
   |
freeze/runtime impairment
   |
age/status
   |
SensorReading
```

---

## Example seed data

These are development examples, not real aerospace sensor specifications.

```toml
[sensors.altimeter]
enabled = true
sample_interval_s = 0.10
noise_std = 0.50
bias = 0.0
delay_s = 0.00

[sensors.vertical_velocity]
enabled = true
sample_interval_s = 0.10
noise_std = 0.10
bias = 0.0
delay_s = 0.00

[sensors.horizontal_position]
enabled = true
sample_interval_s = 0.10
noise_std = 0.25
bias = 0.0
delay_s = 0.00

[sensors.horizontal_velocity]
enabled = true
sample_interval_s = 0.10
noise_std = 0.10
bias = 0.0
delay_s = 0.00

[sensors.attitude]
enabled = true
sample_interval_s = 0.04
noise_std = 0.002
bias = 0.0
delay_s = 0.00

[sensors.gyro]
enabled = true
sample_interval_s = 0.04
noise_std = 0.002
bias = 0.0
delay_s = 0.00
```

**[Open Question]** Final sensor noise magnitudes and sample rates must be calibrated with the nominal controller and should be described as project-defined simulation parameters rather than real hardware specifications.

---

## Local persistence needs

**[Decision]** None inside this feature.

Sensors maintain only in-memory runtime state.

They do not:

- write CSV;
- write JSON;
- create run directories;
- save RNG state files;
- generate plots.

Later Telemetry & Event Logging records the sensor outputs.

---

# 5. Logic Requirements

## Rule 1 — Controller-facing code never receives `VehicleState` through this feature

The sensor suite accepts truth.

The output is a new measurement object.

Do not implement:

```python
snapshot.truth = vehicle_state
```

Do not attach hidden truth references for convenience.

---

## Rule 2 — Sensor sampling is deterministic by tick

Use:

```text
current_tick % sample_every_ticks == 0
```

or an equivalent explicit next-sample-tick mechanism.

Do not schedule using wall-clock time.

---

## Rule 3 — Tick zero is a sample tick for enabled sensors

Unless a future specific requirement changes it.

This must be tested.

---

## Rule 4 — Noise is drawn only on sample events

No new random noise on held ticks.

---

## Rule 5 — Noise uses injected per-sensor RNG

No global `np.random` state.

---

## Rule 6 — Bias is deterministic

For zero noise:

```text
measurement - truth == bias
```

on each new sample.

---

## Rule 7 — Delay acts on timestamped generated samples

Do not delay by sleeping.

Do not rewrite the sample source timestamp at delivery.

---

## Rule 8 — Delay selection chooses the newest eligible sample

At current tick:

```text
sample_tick <= current_tick - delay_ticks
```

Choose the largest eligible `sample_tick`.

---

## Rule 9 — Before the first delayed sample is eligible, output is unavailable

Do not expose future information.

---

## Rule 10 — Held values preserve their source timestamp

This is required for accurate age/stale logic.

---

## Rule 11 — Normal hold is not automatically stale

Stale status begins only after the expected delivery age has been exceeded.

Recommended default:

```text
age_ticks > delay_ticks + sample_every_ticks
```

---

## Rule 12 — Frozen value preserves value and source timestamp

Therefore:

```text
age increases
```

while frozen.

---

## Rule 13 — Freeze before first valid reading produces `UNAVAILABLE`

Do not invent a frozen value.

---

## Rule 14 — Disabled sensor does not sample

It should:

- not consume RNG;
- not add buffer entries;
- return `DISABLED`.

---

## Rule 15 — A sensor only reads its own truth quantity

Examples:

- altimeter does not read velocity;
- gyro does not read position.

This keeps interfaces easy to test and explain.

---

## Rule 16 — Sensor outputs use the same units as the corresponding internal state

No hidden degree/radian conversions in core sensor calculations.

---

## Rule 17 — All generated/delivered numerical values must be finite

If truth + bias + noise becomes non-finite:

- fail loudly.

---

## Rule 18 — Random streams are independent by sensor

Adding or disabling one sensor must not silently change another sensor's RNG sequence, assuming the same canonical RNG derivation and seed.

---

## Rule 19 — Runtime bias/freeze/delay hooks contain no scenario logic

Allowed:

```python
sensor.set_frozen(True)
```

Not allowed:

```python
if scenario_name == "altimeter_freeze":
    ...
```

The general fault system owns activation decisions.

---

## Rule 20 — Sensor suite output ordering is stable

If iterating sensor channels, use canonical `SensorName` order rather than arbitrary dictionary order for any behavior that can affect RNG/setup/testing.

---

## Rule 21 — No state estimator in MVP

Do not fuse measurements into a Kalman filter or estimated full state.

The project deliberately starts with direct simulated measurements.

---

## Rule 22 — No physical hardware interface

No serial, CAN, USB, ROS device, or external sensor requirement.

---

## Sensor sampling pseudocode

```python
def update(
    truth: VehicleState,
    tick: int,
) -> SensorReading:

    if not config.enabled:
        return disabled_reading(...)

    if is_sampling_tick(tick):
        truth_value = extract_truth(truth)

        sample_value = (
            truth_value
            + effective_bias()
            + draw_noise_if_enabled()
        )

        buffer.append(
            SensorSample(
                value=sample_value,
                sample_tick=tick,
            )
        )

    deliverable = buffer.newest_at_or_before(
        tick - effective_delay_ticks()
    )

    if frozen:
        deliverable = frozen_sample

    if deliverable is None:
        return unavailable_reading(...)

    age_ticks = tick - deliverable.sample_tick
    status = classify_age(age_ticks)

    return SensorReading(
        value=deliverable.value,
        source_tick=deliverable.sample_tick,
        current_tick=tick,
        status=status,
    )
```

Actual implementation may arrange freeze before/after buffer selection differently as long as externally visible semantics match this document.

---

## Sensor suite pseudocode

```python
def sample(
    truth: VehicleState,
    tick: int,
    dt: float,
) -> MeasurementSnapshot:

    x_reading = horizontal_position.update(truth, tick)
    y_reading = altimeter.update(truth, tick)
    vx_reading = horizontal_velocity.update(truth, tick)
    vy_reading = vertical_velocity.update(truth, tick)
    theta_reading = attitude.update(truth, tick)
    omega_reading = gyro.update(truth, tick)

    return MeasurementSnapshot(
        tick=tick,
        timestamp=tick * dt,
        x=x_reading.value,
        y=y_reading.value,
        vx=vx_reading.value,
        vy=vy_reading.value,
        theta=theta_reading.value,
        omega=omega_reading.value,
        metadata=...,
    )
```

---

## Simulation-engine integration order

Feature 02 defines the future ordering:

```text
current truth state
      |
      v
fault activation for tick
      |
      v
sensor suite samples truth
      |
      v
sensor impairments applied
      |
      v
MeasurementSnapshot
      |
      v
mission/controller
```

For Feature 03 before the Fault Injection System exists:

```text
current truth state
      |
      v
sensor suite
      |
      v
MeasurementSnapshot
```

The sensor snapshot should correspond to the truth state at the **current tick before physics advances to the next tick**.

This timing relationship must be tested.

---

## Edge cases

### Sensor sample period equals `dt`

New sample every engine tick.

---

### Sensor sample period greater than `dt`

Hold last deliverable sample between sensor updates.

---

### Sample interval not divisible by `dt`

Reject configuration for MVP.

Do not implement fractional event scheduling.

---

### Delay equals zero

Newest generated sample is immediately eligible.

---

### Delay shorter than sample interval

Works normally.

Delivered sample age will depend on the most recent available sample.

---

### Delay longer than sample interval

Buffer holds multiple generated samples.

Return newest eligible sample.

---

### Delay buffer initially empty

`UNAVAILABLE`.

---

### Noise standard deviation equals zero

Do not need to draw from RNG.

**Decision:** Avoid consuming a random draw when `noise_std == 0`.

This preserves reproducibility if a sensor's nominal noise is disabled.

---

### Large bias

Mathematically allowed if finite.

Do not silently clip measurement unless a later explicit sensor-range feature is added.

---

### Sensor range limits

**[Decision]** Do not add saturation/range clipping to sensor measurements in the MVP unless a concrete scenario requires it.

The planning documents require noise, bias, delay, freeze, and stale behavior—not a high-fidelity hardware range model.

---

### Negative altitude truth

If the Simulation Engine provides a finite negative altitude due to a physical boundary issue, the altimeter should report the value according to its model rather than secretly fixing physics.

Physical ground handling belongs to dynamics/engine/mission logic.

---

### Angle wrapping

**[Decision]** The attitude sensor reports the internal finite pitch value without automatic wrap unless the project later standardizes an angle range.

Do not introduce discontinuities unnecessarily.

---

### Freeze activates exactly on a sample tick

Recommended semantics:

1. general Fault Injection System activates freeze for the tick;
2. sensor sees frozen state;
3. it does not publish a newly sampled value on that activation tick;
4. it holds the previously deliverable sample.

**[Open Question]** The exact activation ordering must remain consistent with the Simulation Engine's final fault-before-sensor contract. Once Feature 07 is specified, lock this behavior with integration tests.

---

### Freeze releases

On the release tick, sensor returns to normal sampling/delay behavior.

If the release tick is a scheduled sample tick, a new sample may be produced.

General fault deactivation is outside Feature 03.

---

### Runtime delay increases

Older sample becomes the deliverable sample under the new delay rule.

---

### Runtime delay decreases

A newer buffered sample may become immediately deliverable.

---

### Sensor disabled while running

Baseline MVP configuration is resolved before run.

Dynamic enable/disable does not need to be supported unless a fault scenario later requires it.

---

# 6. Acceptance Criteria

## AC-01 — Controller measurement type is separate from truth type

**Given** the public sensing API  
**When** a sensor snapshot is produced  
**Then** the output is a `MeasurementSnapshot` and does not expose or embed the mutable/perfect `VehicleState` object.

---

## AC-02 — Zero-imperfection altimeter matches truth

**Given** an enabled altimeter with zero noise, zero bias, zero delay, and sampling every tick  
**When** it samples truth altitude `y`  
**Then** delivered altitude equals `y`.

---

## AC-03 — Zero-imperfection vertical velocity matches truth

**Given** an equivalent vertical-velocity configuration  
**When** the sensor samples `vy`  
**Then** the delivered value equals `vy`.

---

## AC-04 — Horizontal position maps only from `x`

**Given** a truth state with distinct field values  
**When** the horizontal position sensor samples  
**Then** its nominal value equals `x` and is unaffected by other truth fields.

---

## AC-05 — Horizontal velocity maps only from `vx`

**Given** a truth state with distinct field values  
**When** the horizontal velocity sensor samples  
**Then** its nominal value equals `vx`.

---

## AC-06 — Attitude sensor maps pitch

**Given** a finite `theta`  
**When** the attitude sensor samples with zero imperfections  
**Then** it returns `theta` in radians.

---

## AC-07 — Gyro maps angular rate

**Given** a finite `omega`  
**When** the gyro samples with zero imperfections  
**Then** it returns `omega` in rad/s.

---

## AC-08 — Bias changes a measurement by configured amount

**Given** zero noise and bias `b`  
**When** a new sample is produced  
**Then** `measurement == truth + b` within floating-point tolerance.

---

## AC-09 — Zero noise consumes no stochastic variation

**Given** `noise_std = 0`  
**When** repeated samples are created  
**Then** no noise term changes the deterministic biased value.

---

## AC-10 — Same seed reproduces the same noise sequence

**Given** identical sensor configuration, truth sequence, tick sequence, and scenario seed  
**When** two sensor suites run independently  
**Then** their stochastic measurement sequences match.

---

## AC-11 — Different seeds can change stochastic measurements

**Given** nonzero noise and identical inputs except for the scenario seed  
**When** two sufficiently long sensor sequences are generated  
**Then** at least one stochastic value differs.

---

## AC-12 — Sensors use independent RNG streams

**Given** two stochastic sensors and a fixed scenario seed  
**When** one sensor is disabled or its sampling behavior changes  
**Then** the other sensor's pre-defined RNG sequence remains unchanged under the canonical RNG derivation.

---

## AC-13 — Sampling occurs only on scheduled ticks

**Given** `sample_every_ticks = 5`  
**When** ticks `0` through `10` are processed  
**Then** new samples are generated only on ticks `0`, `5`, and `10`.

---

## AC-14 — Held reading preserves value between samples

**Given** a valid sample at tick `0` and next sample scheduled at tick `5`  
**When** ticks `1` through `4` are processed  
**Then** the delivered value remains the tick-0 sample unless delay/freeze semantics make it unavailable.

---

## AC-15 — Held reading preserves source tick

**Given** the same setup as AC-14  
**When** tick `4` is processed  
**Then** the reading source tick remains `0`, not `4`.

---

## AC-16 — Delay returns newest eligible older sample

**Given** buffered samples and configured `delay_ticks = d`  
**When** a reading is requested at tick `t`  
**Then** the sensor returns the sample with the greatest sample tick satisfying `sample_tick <= t - d`.

---

## AC-17 — Delay buffer never exposes a future sample

**Given** a sample whose tick is newer than `current_tick - delay_ticks`  
**When** the reading is requested  
**Then** that sample is not delivered yet.

---

## AC-18 — Startup delay produces unavailable state

**Given** delay > 0 and no buffered sample is old enough  
**When** a reading is requested  
**Then** value is `None` and status is `UNAVAILABLE`.

---

## AC-19 — Delay uses simulation time, not wall-clock sleep

**Given** a delayed sensor  
**When** the simulation runs as fast as possible  
**Then** delivered sample timing depends only on engine ticks and configured delay, with no `sleep()` requirement.

---

## AC-20 — Measurement age derives from source tick

**Given** a delivered sample from tick `s` at current tick `t`  
**When** metadata is constructed  
**Then** `age_ticks == t - s` and `age_seconds == (t - s) * dt`.

---

## AC-21 — Normal sample-and-hold remains valid within expected age

**Given** a healthy sensor holding its latest normal delayed sample  
**When** age does not exceed `delay_ticks + sample_every_ticks`  
**Then** status remains `VALID`.

---

## AC-22 — Over-aged reading becomes stale

**Given** a reading whose source age exceeds the expected nominal age window  
**When** status is evaluated  
**Then** status is `STALE`.

---

## AC-23 — Freeze holds the last deliverable value

**Given** a valid delivered reading and freeze activated  
**When** later ticks are processed  
**Then** the externally visible sensor value remains equal to the frozen reading.

---

## AC-24 — Freeze preserves original source timestamp

**Given** a sensor frozen on a previously delivered sample  
**When** time advances  
**Then** source tick/time remain unchanged.

---

## AC-25 — Frozen reading eventually becomes stale

**Given** a frozen reading and advancing simulation ticks  
**When** its age exceeds the stale threshold  
**Then** status changes to `STALE` while the frozen value remains available.

---

## AC-26 — Freeze before any valid sample is unavailable

**Given** a delayed sensor with no deliverable sample yet  
**When** freeze becomes active  
**Then** value remains `None` and status remains `UNAVAILABLE`.

---

## AC-27 — Disabled sensor reports disabled state

**Given** `enabled = false`  
**When** the suite is sampled  
**Then** that channel returns `None` with status `DISABLED`.

---

## AC-28 — Disabled sensor does not consume noise RNG

**Given** a disabled stochastic-configured sensor  
**When** engine ticks advance  
**Then** it does not generate samples or consume sensor noise draws.

---

## AC-29 — Invalid negative noise is rejected

**Given** `noise_std < 0`  
**When** configuration is validated  
**Then** setup fails with a sensor-specific configuration error.

---

## AC-30 — Invalid delay is rejected

**Given** negative/non-finite delay  
**When** configuration is validated  
**Then** setup fails.

---

## AC-31 — Non-aligned sample interval is rejected

**Given** a sample interval that cannot be represented as an integer number of simulation ticks within configuration tolerance  
**When** sensor configuration is resolved  
**Then** setup fails rather than using approximate wall-time scheduling.

---

## AC-32 — Non-aligned delay is rejected

**Given** a delay that cannot be represented as an integer number of simulation ticks within tolerance  
**When** configuration is resolved  
**Then** setup fails.

---

## AC-33 — Non-finite truth value fails safely

**Given** the truth field required by a sensor is NaN or Inf  
**When** sampling is attempted  
**Then** a sensor/runtime error is raised rather than emitting a normal measurement.

---

## AC-34 — Sensor suite snapshot timestamp matches current engine tick

**Given** engine tick `t` and timestep `dt`  
**When** the suite builds a snapshot  
**Then** `snapshot.timestamp == t * dt`.

---

## AC-35 — Sensor snapshot is deterministic for deterministic inputs

**Given** the same truth states, ticks, configs, RNG seeds, and runtime modifiers  
**When** two suites execute  
**Then** their snapshots and status metadata match.

---

## AC-36 — Sensor suite does not mutate truth

**Given** a `VehicleState`  
**When** the suite samples it  
**Then** the truth object remains unchanged.

---

## AC-37 — Sensor modules perform no persistence

**Given** sensor unit tests  
**When** readings/snapshots are produced  
**Then** no CSV, JSON, database, or plot output is required or created by the sensor layer.

---

## AC-38 — Sensor module contains no controller logic

**Given** the sensor package  
**When** dependencies and implementation are inspected  
**Then** it does not compute throttle, attitude commands, PID values, or mission transitions.

---

## AC-39 — Sensor module contains no scenario-name branching

**Given** sensor code  
**When** it is inspected  
**Then** there is no behavior such as `if scenario_name == "altimeter_freeze"`.

---

## AC-40 — Runtime fault hooks remain target-local

**Given** a later fault manager applies freeze/bias/delay to a sensor  
**When** the sensor changes behavior  
**Then** the sensor does not need to know fault schedule, scenario expected outcome, or mission validation rules.

---

# 7. Test Plan

## Unit tests

Primary files:

```text
tests/unit/test_sensors.py
tests/unit/test_sensor_buffers.py
tests/unit/test_sensor_rng.py
```

They may be combined if the codebase remains clearer with one file.

---

## Mapping tests

Required:

```text
test_altimeter_reads_y
test_vertical_velocity_reads_vy
test_horizontal_position_reads_x
test_horizontal_velocity_reads_vx
test_attitude_reads_theta
test_gyro_reads_omega
```

Use distinct truth values so mapping mistakes cannot accidentally pass.

---

## Bias/noise tests

```text
test_static_bias_added_exactly_with_zero_noise
test_zero_noise_is_deterministic
test_same_seed_repeats_noise_sequence
test_different_seed_changes_noise_sequence
test_noise_draws_only_on_sample_ticks
test_disabled_sensor_does_not_draw_noise
test_independent_sensor_rng_streams
test_negative_noise_std_rejected
```

Do not test Gaussian randomness by demanding an exact statistical distribution from a tiny sample.

For the unit contract, reproducibility and correct use of `noise_std` are the priority.

Optional broader statistical sanity test:

- generate a large deterministic sample set;
- assert approximate mean near configured bias;
- assert approximate standard deviation near `noise_std`;

Use loose, non-flaky tolerances.

---

## Sampling-cadence tests

```text
test_samples_at_tick_zero
test_samples_on_integer_tick_period
test_holds_between_sample_ticks
test_hold_preserves_source_tick
test_invalid_non_aligned_sample_period_rejected
```

---

## Delay-buffer tests

```text
test_zero_delay_delivers_current_sample
test_positive_delay_hides_new_sample
test_delay_returns_newest_eligible_sample
test_delay_never_returns_future_sample
test_delay_startup_is_unavailable
test_long_delay_keeps_multiple_samples
test_invalid_delay_rejected
test_non_aligned_delay_rejected
```

---

## Age/stale tests

```text
test_age_ticks_from_current_minus_source
test_age_seconds_from_ticks
test_normal_hold_not_stale_too_early
test_old_reading_becomes_stale
test_delayed_normal_reading_not_marked_stale_immediately
```

---

## Freeze tests

```text
test_freeze_holds_last_value
test_freeze_holds_source_tick
test_freeze_age_increases
test_frozen_reading_becomes_stale
test_freeze_before_valid_reading_is_unavailable
test_release_returns_to_normal_sampling
```

The release test may remain low-level until the Fault Injection System defines activation semantics.

---

## Disabled/missing tests

```text
test_disabled_sensor_returns_none
test_disabled_sensor_status
test_unavailable_differs_from_disabled
```

---

## Validation/error tests

```text
test_non_finite_bias_rejected
test_non_finite_noise_std_rejected
test_non_finite_truth_rejected
test_missing_rng_rejected_for_noisy_sensor
test_buffer_tick_order_violation_rejected
```

---

## Integration tests with Numerical Simulation Engine

Recommended file:

```text
tests/integration/test_sensor_engine.py
```

### Snapshot timing

Run engine over known truth trajectory.

Assert:

```text
snapshot tick corresponds to truth state at same pre-integration tick
```

according to the engine ordering contract.

### Sample cadence under engine

Verify a sensor configured every N ticks updates exactly when expected.

### Delay under engine

Verify delivery timing is independent of wall-clock execution speed.

### Reproducibility

Run same deterministic truth trajectory and same seed twice.

Compare snapshots.

### Truth isolation

Pass the generated `MeasurementSnapshot` to a fake controller interface and prove the controller does not receive a `VehicleState`.

---

## Integration tests intentionally deferred

### Closed-loop behavior

Belongs primarily to Feature 04.

### General fault activation timing

Belongs to Feature 07 Fault Injection System.

### Telemetry serialization

Belongs to Feature 09 Telemetry & Event Logging.

### Mission outcome changes

Belongs to Mission Validation / scenario tests.

---

## Manual QA checklist

- [ ] Six required sensor channels exist.
- [ ] Each channel maps to the correct truth field.
- [ ] `VehicleState.mass` is not silently exposed as a perfect measurement.
- [ ] Sensor snapshot is a separate type from truth state.
- [ ] Every sensor has explicit units.
- [ ] Sampling uses engine ticks.
- [ ] No sensor uses wall-clock time.
- [ ] No `sleep()` models delay.
- [ ] Sample intervals resolve to integer ticks.
- [ ] Delay resolves to integer ticks.
- [ ] Noise uses injected `numpy.random.Generator`.
- [ ] Global `np.random` is not used.
- [ ] RNG stream derivation is stable and canonical.
- [ ] Random noise is drawn only on actual sample events.
- [ ] Zero-noise sensors do not unnecessarily consume random draws.
- [ ] Bias is applied deterministically.
- [ ] Delay buffer preserves source tick.
- [ ] Held readings preserve source tick.
- [ ] Measurement age is correct.
- [ ] Unavailable and disabled states are distinguishable.
- [ ] Freeze holds value and timestamp.
- [ ] Frozen readings become stale.
- [ ] Sensors do not mutate truth.
- [ ] Sensors do not compute control commands.
- [ ] Sensors do not write telemetry files.
- [ ] Sensor code contains no scenario-name branches.
- [ ] All sensor tests pass.

---

## Demo verification checklist

- [ ] Reviewer can see true vs measured altitude.
- [ ] Reviewer can see a noisy measurement sequence that repeats with the same seed.
- [ ] Changing seed changes stochastic noise.
- [ ] Reviewer can see configured bias offset.
- [ ] Reviewer can see delayed measurement trailing truth.
- [ ] Delay uses simulation timestamps, not wall-clock waiting.
- [ ] Reviewer can see frozen measurement remain flat while truth changes.
- [ ] Frozen measurement age grows and becomes stale.
- [ ] Controller-facing API accepts `MeasurementSnapshot`, not `VehicleState`.
- [ ] Sensor suite works entirely locally/headlessly.

---

# 8. Portfolio Value

## How this feature helps the project stand out

This feature supports one of AstraLoop's strongest interview claims:

> "The controller cannot cheat by reading the simulator's perfect state."

That is more meaningful than simply adding random noise to plotted data.

The architecture forces a real boundary:

```text
physics truth
  |
  v
sensor subsystem
  |
  v
software-visible measurements
  |
  v
flight software
```

The feature also demonstrates several software-engineering ideas employers can discuss deeply:

- deterministic random streams;
- stateful components;
- buffering;
- discrete sampling;
- timestamp semantics;
- missing/stale data;
- runtime subsystem isolation;
- configuration validation;
- reproducible failure behavior.

---

## What to mention in README

Recommended wording:

> **Imperfect simulated sensors:** Flight software never receives AstraLoop's perfect `VehicleState`. A sensor suite samples altitude, velocity, position, pitch, and angular rate on deterministic simulation-time cadences, with seeded noise, bias, delay buffers, and stale/freeze behavior.

Useful design bullets:

- controller sees `MeasurementSnapshot`, not truth;
- per-sensor seeded RNGs;
- delay modeled with tick-based buffers;
- source timestamps preserved;
- stale/missing states explicit;
- freeze behavior holds the actual last sensor output;
- no wall-clock sleeps.

Do not claim:

- real avionics sensor fidelity;
- certified hardware models;
- hardware-in-the-loop sensing;
- real sensor noise distributions.

---

## What to mention in interviews

### How did you stop the controller from cheating?

> "The sensor suite is a hard type/interface boundary. The controller receives `MeasurementSnapshot`, which contains only software-visible measurements and metadata. `VehicleState` stays owned by the simulation engine."

### How is sensor delay modeled?

> "Every generated sample has a simulation tick. A delay buffer only releases samples old enough under the configured delay. No sleeping or wall-clock timing is involved."

### How is randomness reproducible?

> "The scenario has one seed, but I derive a dedicated NumPy generator for each sensor. That prevents unrelated sensor changes from shifting every other sensor's random sequence."

### Why preserve source timestamps?

> "The value may be delivered later than it was sampled. Preserving the source tick lets the controller, telemetry, and tests know how old the data actually is."

### What happens between sensor samples?

> "The sensor holds the last deliverable reading. It does not redraw noise every simulation tick. The source timestamp stays unchanged so age is explicit."

### How does freeze differ from delay?

> "Delay still delivers a progression of older samples. Freeze stops the externally visible reading from updating at all, so the value and source timestamp remain fixed and the reading eventually becomes stale."

### Why no Kalman filter?

> "The MVP is about clean software-in-the-loop boundaries and deterministic validation. I deliberately avoided adding estimation complexity before raw sensor/control behavior was stable."

---

# 9. Implementation Notes for Codex

## Likely files/folders

Primary:

```text
src/astraloop/model/measurements.py

src/astraloop/sensors/
├── __init__.py
├── base.py
├── models.py
├── buffers.py
└── suite.py

src/astraloop/config/
├── schema.py
└── validation.py

tests/unit/
├── test_sensors.py
└── test_sensor_buffers.py

tests/integration/
└── test_sensor_engine.py
```

Potential RNG helper:

```text
src/astraloop/sensors/rng.py
```

Only add it if setup logic is substantial enough to justify a separate file.

---

## Suggested responsibilities

### `model/measurements.py`

Own:

```text
SensorName
MeasurementStatus
MeasurementMetadata
MeasurementSnapshot
```

Potentially `SensorReading` if it is used outside sensor internals.

---

### `sensors/base.py`

Use only if a shared sensor interface is actually useful.

Possible lightweight protocol:

```python
class Sensor(Protocol):
    def update(
        self,
        truth: VehicleState,
        tick: int,
    ) -> SensorReading:
        ...
```

**Decision:** Do not build an abstract-class hierarchy merely because there are six sensor channels.

If all channels share one generic scalar sensor implementation with different truth extractors, prefer that.

---

### `sensors/models.py`

Likely contains generic scalar sensor/channel implementation and truth-field extractors.

Potential design:

```python
ScalarSensor(
    name=SensorName.ALTI...
    truth_reader=lambda state: state.y,
    ...
)
```

Be careful not to make debugging opaque with excessive lambdas/factories.

Named small functions may be clearer.

---

### `sensors/buffers.py`

Own:

- timestamped/sample-tick buffer;
- newest-eligible lookup;
- bounded buffer cleanup.

Use `collections.deque`.

---

### `sensors/suite.py`

Own:

- six sensor instances;
- stable update order;
- snapshot construction;
- sensor lookup by name for later fault targeting.

Do not implement controller logic here.

---

## Build order

### Step 1 — Define measurement types

Implement:

```text
SensorName
MeasurementStatus
MeasurementMetadata
MeasurementSnapshot
```

Lock the controller-facing contract early.

---

### Step 2 — Implement zero-imperfection scalar sensor

Before RNG or delay, prove:

```text
truth field -> measurement
```

with sampling every tick.

---

### Step 3 — Add integer-tick sample cadence

Resolve:

```text
sample_interval -> sample_every_ticks
```

and test tick `0` plus periodic updates.

---

### Step 4 — Add static bias

Keep zero noise.

Test exact offset.

---

### Step 5 — Add per-sensor RNG and noise

Use injected `numpy.random.Generator`.

Test reproducibility before adding buffers.

---

### Step 6 — Implement `SensorSample` and delay buffer

Test buffer independently.

Do not use wall-clock time.

---

### Step 7 — Add source age and measurement status

Implement:

```text
VALID
STALE
UNAVAILABLE
DISABLED
```

---

### Step 8 — Add freeze primitive

Test hold + age + stale behavior.

Do not implement fault timing/activation manager.

---

### Step 9 — Add runtime bias/delay hook only as needed

Keep interfaces small and target-local so Feature 07 can use them later.

Do not build general fault infrastructure.

---

### Step 10 — Build `SensorSuite`

Construct all six readings into `MeasurementSnapshot`.

---

### Step 11 — Integrate with Simulation Engine

Place sensor sampling at the documented pre-control/pre-physics point for the current tick.

---

### Step 12 — Prove truth isolation

Before Feature 04 begins, ensure the normal flight-controller API can be written entirely against `MeasurementSnapshot`.

---

## Risks

### Risk 1 — Truth leaks through convenience APIs

Example:

```python
MeasurementSnapshot(..., truth=state)
```

or passing both truth and measurements to controller.

**Mitigation:** hard type boundary and tests.

---

### Risk 2 — RNG coupling

One shared RNG can make unrelated code changes alter all sensor results.

**Mitigation:** dedicated deterministic per-sensor generators.

---

### Risk 3 — Delay off-by-one

A sample can be delivered one tick too soon or one tick late.

**Mitigation:** table-driven tests with exact sample/delay ticks.

---

### Risk 4 — Noise drawn on every engine tick

This makes held values randomly jump even though the sensor did not sample.

**Mitigation:** draw noise only on sample ticks.

---

### Risk 5 — Delivery time replaces sample time

Then delayed data looks fresh.

**Mitigation:** preserve source tick.

---

### Risk 6 — Normal delay is incorrectly labeled stale

A delayed reading is naturally older.

**Mitigation:** stale rule accounts for configured delay and sampling cadence.

---

### Risk 7 — Freeze implementation continues updating hidden delivered sample

Then releasing freeze can produce confusing behavior or telemetry.

**Mitigation:** explicitly document freeze/release semantics and test.

---

### Risk 8 — Feature becomes high-fidelity avionics simulation

Avoid:

- sensor hardware transfer functions;
- ADC quantization;
- bus packets;
- temperature drift;
- calibration matrices;
- redundant voting;
- sensor fusion;
- real IMU models.

Unless a later concrete portfolio need justifies one.

---

### Risk 9 — Fault system gets implemented here accidentally

The sensor needs impairment behavior, but not scenario scheduling.

**Mitigation:** expose small hooks; Feature 07 decides activation.

---

## What not to change

While implementing Feature 03, Codex should **not**:

- change 2D dynamics equations;
- change RK4 implementation;
- change simulation clock semantics;
- give the controller direct access to `VehicleState`;
- implement PID controllers;
- tune landing control;
- implement actuator lag/saturation;
- implement mission states;
- build the general fault manager;
- hard-code `altimeter_freeze` scenario logic;
- hard-code `velocity_bias` scenario logic;
- hard-code `sensor_delay` scenario logic;
- write telemetry CSV/JSON;
- generate Matplotlib plots;
- implement mission validation;
- implement CLI commands;
- add a Kalman filter;
- add sensor fusion;
- add 3D/6-DOF sensors;
- add real hardware interfaces;
- add ROS;
- add CAN/serial;
- add a database;
- add a web UI;
- add cloud services.

If Feature 07 will later need a sensor impairment capability, implement only the smallest sensor-local hook required.

---

# Feature-Specific Definition of Done

Feature 03 is complete when:

- [ ] The six required software-visible sensor channels exist.
- [ ] Each channel reads only its intended truth quantity.
- [ ] `MeasurementSnapshot` is separate from `VehicleState`.
- [ ] Controller-facing measurement values are `x`, `y`, `vx`, `vy`, `theta`, and `omega`.
- [ ] Internal pitch/rate units remain radians/rad/s.
- [ ] Every enabled sensor has explicit sampling cadence.
- [ ] Sampling cadence resolves to integer simulation ticks.
- [ ] Sensors sample at tick `0`.
- [ ] Values hold between sample events.
- [ ] Held values preserve source tick.
- [ ] Static bias works.
- [ ] Gaussian noise works.
- [ ] Noise is drawn only when a new sample is created.
- [ ] Every stochastic sensor uses an injected dedicated RNG.
- [ ] Same seed reproduces the same sensor sequence.
- [ ] Sensor RNG streams are independent.
- [ ] Delay uses timestamped simulation-time buffers.
- [ ] No `sleep()` models sensor latency.
- [ ] Delay cannot reveal future samples.
- [ ] Startup delay returns `UNAVAILABLE`.
- [ ] Measurement age is explicit.
- [ ] Normal delayed/sample-held values remain valid within expected age.
- [ ] Old readings become `STALE`.
- [ ] Disabled sensors return `DISABLED`.
- [ ] Freeze holds the last valid delivered value.
- [ ] Freeze preserves the source timestamp.
- [ ] Frozen readings eventually become stale.
- [ ] Freeze before first valid delivery remains unavailable.
- [ ] Sensor-local future fault hooks contain no scenario scheduling logic.
- [ ] Non-finite truth/config values fail clearly.
- [ ] Sensor suite does not mutate truth state.
- [ ] Sensor modules do not write persistence artifacts.
- [ ] Sensor modules contain no controller/mission logic.
- [ ] Sensor modules contain no scenario-name branches.
- [ ] Unit tests cover mapping, cadence, RNG, bias, delay, age, status, freeze, disabled behavior, and errors.
- [ ] Simulation-engine integration tests confirm snapshot timing and reproducibility.
- [ ] `pytest` passes for all sensor tests.

---

# Open Questions

1. **[Open Question] What exact sample intervals should the nominal bundled sensors use?**  
   The source docs require configurable sample intervals but do not fix final values.

2. **[Open Question] What exact `noise_std` and baseline bias values should each nominal sensor use?**  
   These should be project-defined simulation parameters tuned for useful but controllable behavior.

3. **[Open Question] Should every baseline nominal sensor have zero delay, or should one have a small normal delay?**  
   Recommended initial decision: zero nominal delay for all sensors, then demonstrate delay through the dedicated fault scenario. This makes the nominal controller easier to stabilize.

4. **[Open Question] Should `MeasurementSnapshot` metadata be a mapping keyed by `SensorName` or a named immutable metadata record?**  
   Choose whichever produces the clearest typed API under Pyright.

5. **[Open Question] Should the stale threshold remain the derived `delay + sample period` rule or become explicitly configurable?**  
   Recommended: use the derived rule for MVP; add configuration only if controller/mission behavior needs it.

6. **[Open Question] What exact semantics should apply when freeze activates on the same tick a sensor is scheduled to sample?**  
   The architecture indicates fault activation precedes sensor sampling. Recommended behavior: freeze wins on that tick and holds the previous deliverable reading. Lock this once Feature 07 is specified.

7. **[Open Question] Should a sensor continue generating hidden raw samples while its output is frozen?**  
   Recommended MVP behavior: no externally meaningful update while frozen; implementation should favor the simplest semantics that produce deterministic release behavior.

8. **[Open Question] How should runtime delay reduction after a fault ends choose from buffered samples?**  
   Recommended: immediately return the newest sample eligible under the restored delay.

---

# Move On When

- [ ] Every sensor has clear Given/When/Then acceptance criteria.
- [ ] Zero-imperfection sensors correctly mirror only their intended truth fields.
- [ ] Sampling cadence and delay are deterministic by simulation tick.
- [ ] Seeded noise is reproducible and sensor-local.
- [ ] Measurement age/missing/stale semantics are tested.
- [ ] Freeze behavior has a reviewer-visible demo path.
- [ ] `MeasurementSnapshot` is a hard boundary protecting truth state.
- [ ] The sensor feature clearly demonstrates imperfect-data and systems-software skill.
- [ ] Fault activation scheduling remains outside this feature.
- [ ] No unnecessary SaaS, hardware, estimator, GUI, database, or cloud systems have been added.
- [ ] The scope still feels finishable before starting Closed-Loop Flight Controllers.
