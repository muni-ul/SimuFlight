# Feature 04 — Closed-Loop Flight Controllers

> **Project:** AstraLoop — Python Software-in-the-Loop Flight Control & Validation System  
> **Feature:** Closed-Loop Flight Controllers  
> **Document path:** `docs/features/04-closed-loop-flight-controllers.md`  
> **Status:** Implementation specification  
> **Primary goal:** Build deterministic, testable throttle and pitch/attitude controllers that operate only on software-visible sensor measurements, maintain explicit controller state, respect configured command limits, and integrate cleanly with mission modes and the later actuator layer.

---

## Scope Boundary

**[Confirmed]** AstraLoop requires closed-loop control through simulated measurements rather than perfect simulator truth.

**[Confirmed]** The selected architecture requires:

- a reusable PID component;
- a throttle controller;
- a pitch/attitude controller;
- controller-owned internal memory;
- a controller API that receives a measurement object, mission mode, and timestep;
- explicit output limits;
- integral-windup protection / safe integral behavior;
- controller memory that resets or transitions safely across mission-mode changes.

**[Confirmed]** The normal controller path must not import or receive `VehicleState`.

**[Confirmed]** The actuator layer is separate and owns:

- physical command saturation;
- actuator response lag;
- actual applied actuator state.

**[Decision]** Feature 04 owns the **flight-software control-law layer**.

It owns:

- reusable PID logic;
- controller configuration;
- mission-mode-specific controller targets/profiles;
- vertical-velocity/throttle feedback control;
- pitch/attitude feedback control;
- measured angular-rate damping;
- controller command limits;
- anti-windup behavior;
- controller internal state;
- controller reset behavior;
- mode-change behavior;
- handling of unavailable/stale required measurements;
- deterministic command generation;
- a structured controller update result;
- unit and closed-loop integration tests.

It does **not** own:

- 2D vehicle physics;
- RK4 integration;
- sensor sampling/noise/delay/freeze implementation;
- mission-state transition rules;
- actuator lag/slew/physical response;
- fault scheduling;
- scenario expected outcomes;
- telemetry persistence;
- mission PASS/FAIL evaluation;
- plotting;
- CLI behavior;
- advanced guidance optimization;
- Kalman filtering/state estimation;
- machine learning control.

---

# 1. Feature Overview

## Feature name

**Closed-Loop Flight Controllers**

---

## One-sentence description

**[Decision]** Implement deterministic measurement-driven throttle and attitude feedback controllers that convert `MeasurementSnapshot` data and mission-mode targets into bounded desired commands without accessing perfect simulator truth.

---

## Detailed description

AstraLoop's closed-loop path is:

```text
TRUE VEHICLE STATE
        |
        v
 SIMULATED SENSORS
        |
        v
MeasurementSnapshot
        |
        v
 CLOSED-LOOP CONTROLLERS
        |
        v
   ControlCommand
        |
        v
  ACTUATOR MODELING
        |
        v
 AppliedActuation
        |
        v
     DYNAMICS
```

The controller layer must behave like actual flight software:

- it receives imperfect software-visible measurements;
- it does not know the exact truth state;
- it owns discrete control memory;
- it reacts to error between measured state and configured targets;
- it outputs desired actuator commands;
- it does not directly alter the vehicle.

The MVP contains two primary feedback controllers:

1. **Throttle controller**
   - controls measured vertical velocity;
   - produces desired normalized throttle.

2. **Pitch/attitude controller**
   - controls measured pitch;
   - uses measured angular rate for damping;
   - produces desired gimbal/attitude command.

**[Decision]** Do not add a separate horizontal-position guidance loop to the MVP unless nominal/fault testing demonstrates a concrete need.

**Justification:** The source project direction explicitly calls for throttle and pitch/attitude control. A third guidance layer would increase tuning complexity and blur the project's scope. The 2D model still matters because pitch changes thrust direction and produces horizontal motion. A later guidance extension can generate nonzero pitch targets if required.

---

## Controller API

The source architecture calls for a controller boundary equivalent to:

```python
Controller.update(
    measurement,
    mission_state,
    dt,
) -> ControlCommand
```

**[Decision]** Preserve that basic contract, while allowing the implementation to return lightweight controller-health metadata alongside the command.

Recommended shape:

```python
@dataclass(frozen=True)
class ControlCommand:
    throttle: float
    attitude_command: float
```

and:

```python
@dataclass(frozen=True)
class ControllerUpdate:
    command: ControlCommand
    status: ControllerStatus
    reason: str | None = None
```

The actuator layer consumes:

```python
update.command
```

The later telemetry/mission layers may inspect:

```python
update.status
update.reason
```

### Why return status?

Missing/stale sensor data is a real domain condition, not necessarily a Python crash.

A structured status allows the controller to say:

```text
I did not safely update because required measurement data was invalid.
```

without:

- changing mission state itself;
- crashing the simulation;
- silently pretending the data was valid.

---

## Controller status

Recommended enum:

```text
OK
HELD
INVALID_INPUT
INACTIVE
```

### `OK`

A new valid control update was computed.

### `HELD`

The previous command is intentionally being held, for example between scheduled controller updates.

### `INVALID_INPUT`

A required measurement was unavailable/stale/non-finite, so the controller did not advance its PID state.

### `INACTIVE`

The current mission mode intentionally disables active feedback control.

Examples:

```text
PRELAUNCH
LANDED
ABORT
```

depending on the final mode profile.

---

## Mission-mode dependency

**[Confirmed]** The controller API may receive mission mode, and controller integral state should reset or transition safely between relevant modes.

**[Decision]** Controllers may **consume** the current mission mode but must not decide mission transitions.

Allowed:

```text
MissionState.DESCENT
    -> target vertical velocity = configured DESCENT target
    -> target pitch = configured DESCENT target
```

Not allowed:

```python
if altitude < 10:
    mission_state = LANDING
```

That belongs to Feature 06 Mission State Machine.

---

## Mission-mode controller profiles

Each active mission mode can supply:

```text
target vertical velocity
target pitch
base/feed-forward throttle
controller enabled/disabled flags
```

Recommended conceptual profile:

```python
@dataclass(frozen=True)
class ControlProfile:
    target_vertical_velocity: float
    target_pitch: float
    base_throttle: float
    throttle_enabled: bool
    attitude_enabled: bool
```

**[Decision]** Keep gains global per controller for the initial MVP unless testing proves state-specific gains are necessary.

**Justification:** State-specific setpoints are valuable and source-supported. State-specific gains create substantially more tuning parameters. Start with one stable throttle PID and one stable attitude PID, then change gains only if a specific mission phase cannot be handled cleanly.

**[Open Question]** Final mission-mode target values and whether any mode needs distinct PID gains must be determined during nominal mission tuning.

---

## Recommended mode behavior

The following is a **controller behavior decision**, not a mission-transition definition.

### `PRELAUNCH`

Recommended:

```text
throttle control inactive
attitude control may hold neutral target
desired throttle = 0
desired attitude/gimbal = 0
```

Controller memory should be reset.

---

### `ASCENT`

If the final mission includes active ascent:

```text
throttle feedback enabled
target vertical velocity > 0
attitude target usually 0 rad
```

**[Open Question]** Exact ascent target is not specified by the planning documents.

---

### `COAST`

Recommended:

```text
throttle command = 0
attitude controller may remain active to hold pitch
```

**Decision:** Do not integrate throttle error while throttle control is intentionally inactive.

---

### `DESCENT`

Recommended:

```text
throttle feedback enabled
target vertical velocity < 0
attitude target = 0 rad unless later guidance requests otherwise
```

---

### `LANDING`

Recommended:

```text
throttle feedback enabled
target vertical velocity closer to 0 than DESCENT target
attitude target = 0 rad
```

**[Decision]** A reasonable final landing descent target should be strictly inside the project validation limit of:

```text
|vertical landing speed| <= 2.0 m/s
```

A candidate design target is approximately:

```text
target_vy = -1.0 m/s
```

but the exact value remains tunable.

This is a project-defined controller target, not a real launch-vehicle specification.

---

### `LANDED`

Recommended:

```text
throttle = 0
attitude command = 0
controllers inactive/reset
```

---

### `ABORT`

Recommended controller-side safe command:

```text
throttle = 0
attitude command = 0
controllers inactive/reset
```

**Decision:** The state machine decides to enter `ABORT`. The controller only follows the profile associated with that mode.

---

## Throttle controller

### Control objective

Control:

```text
measured vertical velocity
```

toward:

```text
target vertical velocity
```

Error:

```text
e_vy = target_vy - measured_vy
```

AstraLoop's vertical convention is:

```text
positive vy = upward
negative vy = downward
```

Therefore:

If:

```text
target_vy = -1 m/s
measured_vy = -5 m/s
```

then:

```text
e_vy = +4 m/s
```

A positive correction should increase throttle.

This sign convention must be protected by tests.

---

## Why control vertical velocity rather than altitude directly

**[Decision]** The MVP throttle loop directly controls **vertical velocity** rather than using a large altitude-position PID.

**Justification:**

- vertical velocity is directly measured by the selected sensor suite;
- the project validation criterion is strongly tied to landing vertical speed;
- fixed mission modes can provide different descent-rate targets;
- the state machine can switch from `DESCENT` to `LANDING` using measured altitude;
- this avoids adding a cascaded altitude-guidance loop before it is needed.

A later extension may use altitude to generate a vertical-velocity target, but that is not required for the initial controller feature.

---

## Throttle feed-forward/base command

A pure velocity PID with zero output at zero error would command:

```text
0 throttle
```

even when nonzero thrust is required to maintain a steady descent rate against gravity.

**[Decision]** Use a configurable per-mode `base_throttle` feed-forward term:

```text
throttle_unclamped =
    base_throttle
    + PID_correction
```

**Justification:**

- gives the feedback loop a sensible operating point;
- reduces integral burden;
- improves explainability;
- does not require exposing perfect current mass to the controller.

The base throttle is a configured software parameter, not a truth-state measurement.

The PID then corrects for:

- changing mass;
- sensor error;
- dynamic mismatch;
- imperfect tuning.

**[Open Question]** Final base-throttle values must be tuned against the final vehicle parameters.

---

## Throttle output domain

Desired throttle:

```text
0.0 <= command.throttle <= 1.0
```

**[Decision]** The controller clamps its **desired software command** to this normalized range.

The later actuator layer remains responsible for physical actuator behavior and can independently enforce its own bounds.

### Why both controller and actuator can have limits

Controller limit:

```text
prevents PID windup / nonsensical requested command
```

Actuator limit:

```text
models the actual physical actuator constraint
```

They serve different purposes.

---

## Attitude controller

### Control objective

Control measured pitch:

```text
theta
```

toward configured target pitch:

```text
theta_target
```

using:

- attitude measurement;
- gyro/angular-rate measurement.

Pitch error:

```text
e_theta = wrap_angle(theta_target - measured_theta)
```

For normal AstraLoop operation, pitch should remain near upright, but using a shortest-angle error helper makes the controller robust to finite angles outside the immediate small-angle region.

---

## Pitch sign convention

Feature 01 defines:

```text
theta = 0      upright
positive theta rightward/clockwise
positive gimbal produces positive pitch torque
```

If:

```text
measured theta > target theta
```

then:

```text
error = target - measured < 0
```

A positive proportional gain produces:

```text
negative gimbal command
```

which generates negative angular acceleration and restores attitude.

This restoring-sign relationship must be directly tested.

---

## Attitude derivative/rate damping

The sensor suite provides:

```text
omega = measured angular rate
```

**[Decision]** The attitude controller uses measured angular rate as the derivative/rate-feedback term rather than estimating pitch rate only through successive angle differences.

For a constant target pitch:

```text
error_rate ≈ -measured_omega
```

Therefore:

```text
D contribution = kd * (-measured_omega)
```

### Why

- the gyro already provides angular-rate measurement;
- avoids an unnecessary finite-difference derivative;
- reduces derivative kick from abrupt setpoint changes;
- gives a clean use for the gyro channel.

If the target pitch itself later changes dynamically, the exact derivative handling can be revisited.

---

## Attitude command output

Recommended interpretation:

```text
ControlCommand.attitude_command
```

means:

```text
desired gimbal angle [rad]
```

before actuator dynamics.

The later actuator layer converts this desired command into:

```text
actual applied gimbal angle
```

after physical saturation/lag/rate effects.

---

## Attitude command limit

The controller should have a configured desired-command bound:

```text
-command_limit_rad
<= attitude_command
<= command_limit_rad
```

**Decision:** This is a software controller bound, not the final actuator physics model.

When Actuator Modeling exists, cross-field configuration validation should ensure the controller limit is sensible relative to the actuator's physical maximum.

---

## Reusable PID component

Recommended state:

```python
@dataclass
class PIDState:
    integral: float
    previous_error: float | None
```

Recommended configuration:

```python
@dataclass(frozen=True)
class PIDConfig:
    kp: float
    ki: float
    kd: float

    output_min: float
    output_max: float

    integral_min: float
    integral_max: float
```

Potential update API:

```python
def update(
    error: float,
    dt: float,
    *,
    derivative_value: float | None = None,
    feed_forward: float = 0.0,
) -> PIDResult:
    ...
```

---

## PID equation

Base form:

```text
P = kp * error
```

Candidate integral:

```text
I_candidate =
    clamp(
        integral + error * dt,
        integral_min,
        integral_max
    )
```

Derivative:

If an explicit derivative/error-rate signal is provided:

```text
D = kd * derivative_value
```

Otherwise:

```text
if previous_error is None:
    error_derivative = 0
else:
    error_derivative =
        (error - previous_error) / dt

D = kd * error_derivative
```

Unclamped output:

```text
u_raw =
    feed_forward
    + P
    + ki * I_candidate
    + D
```

Final output:

```text
u =
    clamp(
        u_raw,
        output_min,
        output_max
    )
```

---

## Anti-windup

Integral windup is a source-identified edge case.

**[Decision]** Use **conditional integration plus explicit integral bounds**.

Recommended behavior:

1. calculate candidate integral;
2. calculate candidate output;
3. if output is within limits:
   - accept the candidate integral;
4. if output is saturated:
   - accept integration only if the error would drive the output back toward the valid range;
   - otherwise hold the previous integral.

### Example: upper saturation

If:

```text
u_raw > output_max
```

and:

```text
error > 0
```

for a controller where positive error increases output, further positive integration would worsen saturation.

Do not integrate further.

If:

```text
error < 0
```

allow the integral to unwind.

### Why this method

- easy to explain;
- easy to test;
- no extra back-calculation gain;
- suitable for the MVP;
- prevents persistent integral buildup while commands are limited.

---

## Integral bounds

Even with conditional integration:

**[Decision]** Keep explicit:

```text
integral_min
integral_max
```

as a second safety bound.

Do not allow the integral state to become arbitrarily large.

---

## PID reset behavior

A PID must expose:

```python
reset()
```

which returns:

```text
integral = 0
previous_error = None
```

Controllers call reset when required by mission-mode changes or terminal/inactive modes.

---

## Mission-mode transition behavior

**[Decision]** On a mission-mode change:

- reset throttle PID integral/history;
- reset attitude PID integral/history;
- apply the new mode's targets/profile immediately;
- allow a controller update on the transition tick.

### Why reset by default

Carrying integral state from one mission phase into another can produce an inappropriate command because:

- setpoint changes;
- control objective changes;
- throttle may have been disabled during coast;
- a previous saturation state may no longer be relevant.

Resetting is the safest simple MVP rule.

**[Open Question]** If controller tuning later reveals unacceptable command discontinuity, implement explicit bumpless transfer rather than silently preserving arbitrary integral state.

---

## Controller update cadence

The simulation engine uses a deterministic fixed tick.

**[Decision]** Controller update cadence must also resolve to an integer number of simulation ticks.

Example:

```text
simulation dt = 0.02 s
controller interval = 0.04 s

controller update every 2 ticks
```

Recommended setup:

```text
control_interval_s / simulation_dt
```

must be integer-like.

The Simulation Engine should invoke `Controller.update(...)` only when the controller is due, except a mission-mode change may force an immediate update.

Between controller update ticks:

```text
last desired ControlCommand is held
```

and:

```text
PID state does not advance
```

### PID timestep

When the controller updates every N simulation ticks:

```text
control_dt = N * simulation_dt
```

Pass `control_dt` to PID update.

Do not pass the smaller simulation `dt` if the PID was not actually updated on each simulation tick.

---

## Why the engine owns cadence

The Numerical Simulation Engine owns deterministic time and tick scheduling.

The controller should not use wall-clock time.

This preserves the architecture:

```text
engine decides when software executes
controller decides what command to compute
```

---

## Required measurements

### Throttle controller requires

```text
vy
```

with a usable status.

The baseline velocity-feedback controller does not require perfect mass or truth altitude.

---

### Attitude controller requires

```text
theta
omega
```

when rate damping is enabled.

If:

```text
kd == 0
```

the implementation may not require gyro input for the mathematical update, but the normal MVP attitude controller is expected to use gyro damping.

---

## Measurement validity

A required sensor reading is usable when:

```text
value is finite
status == VALID
```

**[Decision]** Treat:

```text
STALE
UNAVAILABLE
DISABLED
```

as invalid for required control inputs.

Why:

- the sensor layer already distinguishes healthy delayed data from genuinely stale data;
- using known-stale data silently weakens the project's failure semantics;
- mission logic can respond to sensor validity separately.

---

## Invalid-input behavior

The controller must not crash the whole simulation merely because a sensor fault created a domain-level missing/stale reading.

**[Decision]** If a required measurement is invalid:

1. do not update that controller's PID memory;
2. hold its last valid command;
3. if no previous command exists, use the mode's safe default command;
4. return `ControllerStatus.INVALID_INPUT`;
5. include a concise reason.

Examples:

```text
"vertical_velocity measurement unavailable"
"attitude measurement stale"
"gyro measurement non-finite"
```

### Why hold last command?

It avoids introducing an unrelated abrupt controller command solely due to API error handling.

The mission state machine can independently detect sensor validity and move to `ABORT` if that is the configured policy.

This controller does not decide the mission outcome.

---

## Safe default command

Before any valid active update:

```text
throttle = 0.0
attitude_command = 0.0
```

unless a mission profile explicitly defines a different inactive/base output.

For `LANDED` and `ABORT`, use the safe neutral command by default.

---

## Determinism

Given identical:

```text
MeasurementSnapshot sequence
MissionState sequence
PID configuration
ControlProfile configuration
controller update timing
```

the controller must produce the same:

```text
ControlCommand sequence
ControllerStatus sequence
internal PID state evolution
```

No random number generation belongs in the controller layer.

---

## Why it matters

This feature creates the actual **closed loop** in AstraLoop.

Without it, the project is only:

```text
physics + sensors + plots
```

With it:

```text
measurements
    -> control decision
    -> actuator request
    -> physics
    -> new measurements
```

The system becomes stateful and interactive.

This is a strong portfolio signal because it proves the developer can design software that responds to imperfect inputs over time rather than processing static data.

---

## Skill it demonstrates

A strong implementation demonstrates:

- feedback-control logic;
- reusable component design;
- PID implementation;
- anti-windup;
- stateful software;
- measurement-only interfaces;
- explicit dependency boundaries;
- mode-aware behavior;
- deterministic discrete-time updates;
- configuration-driven setpoints;
- defensive input handling;
- command limiting;
- integration testing;
- system-level reasoning.

---

## Priority

**P0/P1 — Core MVP**

The project is not genuinely software-in-the-loop until:

```text
sensor output
 -> controller
 -> actuator
 -> dynamics
```

forms a closed loop.

This feature should be completed after:

1. 2D Flight Dynamics;
2. Numerical Simulation Engine;
3. Simulated Sensor System.

---

## Complexity

**High**

The code can remain relatively small, but successful behavior depends on:

- correct signs;
- appropriate controller targets;
- gains;
- integral behavior;
- sensor timing;
- output bounds;
- mode transitions;
- actuator interaction.

Tuning must not be allowed to turn into an endless research project.

---

# 2. User / Demo Flow

The direct user is the simulation runtime, but the reviewer should see obvious evidence that feedback control changes the vehicle behavior.

---

## Happy path

1. Current truth state exists inside the Simulation Engine.
2. Simulated sensors produce `MeasurementSnapshot`.
3. Mission State Machine supplies current mode.
4. Engine determines that a controller update is due.
5. Controller validates required measurements.
6. Mission mode selects the configured controller profile.
7. Throttle controller computes vertical-velocity error.
8. Throttle PID computes correction around base throttle.
9. Attitude controller computes wrapped pitch error.
10. Attitude PID uses measured gyro rate for damping.
11. Controller outputs bounded desired throttle and gimbal commands.
12. Actuator Modeling receives those desired commands.
13. Actuator output affects physics.
14. New truth state produces new sensor measurements.
15. The process repeats as a closed loop.

---

## First-time path

### Stage A — Test generic PID without vehicle physics

Use synthetic error sequences.

Verify:

- P term;
- I term;
- D term;
- clamping;
- reset;
- anti-windup.

---

### Stage B — Test throttle sign

Give:

```text
target_vy = -1
measured_vy = -5
```

Verify throttle correction increases.

Then:

```text
measured_vy = 0
```

Verify throttle correction decreases relative to target.

---

### Stage C — Test attitude sign

Give:

```text
target_theta = 0
measured_theta > 0
omega = 0
```

Verify command is negative under the Feature 01 sign convention.

Mirror with negative pitch.

---

### Stage D — Test gyro damping

Give:

```text
theta error = 0
omega > 0
```

Verify attitude controller commands a negative damping action.

---

### Stage E — Test invalid measurements

Verify:

- stale `vy` does not advance throttle PID;
- unavailable `theta` does not advance attitude PID;
- last valid command is held;
- status explains why.

---

### Stage F — Close the pitch loop

Use the actual sensor + engine + 2D dynamics with a simple applied-actuation adapter or later actuator model.

Start with a small nonzero pitch.

Verify pitch moves toward zero.

---

### Stage G — Close vertical-velocity loop

Start with an overly fast descent.

Verify controller increases throttle and reduces downward velocity toward target.

Only after both isolated loops are stable should the complete nominal mission be tuned.

---

## Empty state

### No active control profile

Treat as configuration error before runtime if an active mission mode has no profile.

For terminal/inactive mission states:

```text
safe command
status = INACTIVE
```

is valid.

---

## Error path

### Invalid controller configuration

Examples:

```text
non-finite gain
output_min > output_max
integral_min > integral_max
negative control interval
non-aligned control interval
base throttle outside normalized range
invalid pitch target
```

Expected:

- fail before simulation starts.

### Invalid required measurement

Expected:

- hold last command / safe default;
- do not update PID state;
- return `INVALID_INPUT`.

### Non-finite PID intermediate value

Expected:

- raise a controller runtime error;
- do not commit updated PID state.

### Invalid timestep

If:

```text
dt <= 0
```

during PID update:

- fail loudly.

### Unknown mission mode/profile

Fail configuration/setup if possible.

Do not silently choose a random/default active profile.

---

## Demo path for a reviewer

### Demo A — Open-loop vs closed-loop pitch

Run identical initial nonzero-pitch conditions.

Open loop:

```text
no corrective attitude command
```

Closed loop:

```text
attitude controller enabled
```

Show measured pitch returning toward target.

Reviewer takeaway:

> "The vehicle is reacting to sensor feedback, not following a scripted attitude."

---

### Demo B — Vertical descent-rate recovery

Start with:

```text
measured descent faster than target
```

Show:

- positive vertical-velocity error;
- increased throttle command;
- actual vertical velocity moving toward target after actuator/physics response.

---

### Demo C — Requested vs actual actuation

After Feature 05 exists, plot:

```text
requested throttle
actual throttle

requested gimbal
actual gimbal
```

This clearly demonstrates controller/actuator separation.

---

### Demo D — Measurement-only API

Show:

```python
controller.update(
    measurement=MeasurementSnapshot(...),
    mission_state=...,
    dt=...,
)
```

and that no `VehicleState` argument exists.

---

### Demo E — Anti-windup test

Show a unit test where output is saturated for several updates.

Demonstrate that:

```text
integral does not grow without bound
```

Reviewer takeaway:

> "I tested control-software failure modes, not just whether one tuned trajectory looked good."

---

# 3. UX / UI Requirements

## Screens/pages

**[Decision]** No dedicated controller UI/page is required.

The feature must run headlessly.

Later diagnostic visualization should show:

- measured target variable;
- target/setpoint;
- requested command;
- actual actuator output;
- mission mode;
- saturation/invalid-input periods where useful.

---

## Components

Recommended software components:

```text
PIDConfig
PIDState
PIDController
PIDResult

ControlProfile
ThrottleController
AttitudeController
FlightController

ControlCommand
ControllerStatus
ControllerUpdate
```

Avoid additional abstraction unless a real second implementation needs it.

---

## Forms/inputs

No GUI form.

Configuration should provide:

### General controller timing

```text
update_interval_s
```

### Throttle PID

```text
kp
ki
kd
output_min
output_max
integral_min
integral_max
```

### Attitude PID

```text
kp
ki
kd
output_min_rad
output_max_rad
integral_min
integral_max
```

### Per mission-mode profile

```text
target_vertical_velocity
target_pitch
base_throttle
throttle_enabled
attitude_enabled
```

---

## Buttons/actions

None.

---

## Validation messages

Examples:

```text
Invalid controller config [throttle]: output_min=0.8 exceeds output_max=0.2.
Invalid controller config [attitude]: kd must be finite.
Invalid controller timing: update_interval_s=0.03 is not aligned to simulation dt=0.02.
Missing control profile for mission state LANDING.
Controller input invalid [throttle]: vertical_velocity measurement is STALE.
Controller input invalid [attitude]: attitude measurement is UNAVAILABLE.
PID update failed: dt must be finite and > 0.
```

---

## Empty states

### Controller inactive

Return:

```text
safe command
status = INACTIVE
```

### Required measurement unavailable

Return:

```text
held/safe command
status = INVALID_INPUT
```

Do not fabricate sensor values.

---

## Loading states

None.

Control updates are synchronous and local.

---

## Error states

Recommended minimal error categories:

```text
ControllerConfigError
ControllerRuntimeError
```

Do not create a large hierarchy.

Missing/stale measurements are normally represented through `ControllerStatus.INVALID_INPUT`, not exceptions.

---

## Responsive behavior

Not relevant.

---

# 4. Data Requirements

## Entities involved

### `ControlCommand`

```python
@dataclass(frozen=True)
class ControlCommand:
    throttle: float
    attitude_command: float
```

Units:

```text
throttle          normalized [0, 1]
attitude_command  desired gimbal angle [rad]
```

---

### `ControllerStatus`

```text
OK
HELD
INVALID_INPUT
INACTIVE
```

---

### `ControllerUpdate`

```python
@dataclass(frozen=True)
class ControllerUpdate:
    command: ControlCommand
    status: ControllerStatus
    reason: str | None
```

---

### `PIDConfig`

```python
@dataclass(frozen=True)
class PIDConfig:
    kp: float
    ki: float
    kd: float

    output_min: float
    output_max: float

    integral_min: float
    integral_max: float
```

---

### `PIDState`

```python
@dataclass
class PIDState:
    integral: float = 0.0
    previous_error: float | None = None
```

State is mutable only inside its owning controller object.

---

### `PIDResult`

Useful for testing/debugging:

```python
@dataclass(frozen=True)
class PIDResult:
    output: float
    proportional: float
    integral: float
    derivative: float
    saturated: bool
```

**Decision:** Keep this if it materially helps tests/telemetry. Do not make every internal value a public API requirement if it adds noise.

---

### `ControlProfile`

```python
@dataclass(frozen=True)
class ControlProfile:
    target_vertical_velocity: float
    target_pitch: float
    base_throttle: float
    throttle_enabled: bool
    attitude_enabled: bool
```

---

### `ControllerConfig`

Conceptually:

```python
@dataclass(frozen=True)
class ControllerConfig:
    update_interval: float
    throttle_pid: PIDConfig
    attitude_pid: PIDConfig
    profiles: Mapping[MissionState, ControlProfile]
```

Resolved runtime configuration may replace seconds with:

```text
update_every_ticks
control_dt
```

---

### `MeasurementSnapshot`

Defined by Feature 03.

Controller consumes:

```text
vy
theta
omega
measurement metadata/status
```

It must not require a truth-state reference.

---

### `MissionState`

Defined by Feature 06.

Feature 04 consumes it as an enum/value.

Feature 04 does not own legal transitions.

---

## Fields and units

| Field | Unit / type | Constraint |
|---|---|---|
| `throttle` | normalized | `[0, 1]` |
| `attitude_command` | rad | finite, controller-limited |
| `target_vertical_velocity` | m/s | finite |
| `target_pitch` | rad | finite |
| `base_throttle` | normalized | `[0, 1]` |
| `kp` | controller-specific | finite |
| `ki` | controller-specific | finite |
| `kd` | controller-specific | finite |
| `integral` | accumulated error-time | finite and bounded |
| `update_interval` | s | finite, `> 0` |
| `control_dt` | s | finite, `> 0` |

---

## Relationships

```text
MeasurementSnapshot
         |
         v
   FlightController <---- MissionState
         |
         +----> ThrottleController
         |          |
         |          v
         |      throttle PID
         |
         +----> AttitudeController
                    |
                    v
                attitude PID
         |
         v
 ControllerUpdate
         |
         v
   ControlCommand
         |
         v
  Actuator Modeling
```

---

## Example seed/config shape

**Important:** Final gains are not provided by the planning documents and cannot be responsibly locked until the dynamics/actuator model is tuned.

The following shows **configuration structure**, not validated final gains:

```toml
[controller]
update_interval_s = 0.04

[controller.throttle_pid]
kp = 0.0            # placeholder: tune
ki = 0.0            # placeholder: tune
kd = 0.0            # placeholder: tune
output_min = -0.5   # PID correction limit, example only
output_max = 0.5
integral_min = -5.0
integral_max = 5.0

[controller.attitude_pid]
kp = 0.0            # placeholder: tune
ki = 0.0            # placeholder: tune
kd = 0.0            # placeholder: tune
output_min_rad = -0.10
output_max_rad = 0.10
integral_min = -1.0
integral_max = 1.0

[controller.profiles.DESCENT]
target_vertical_velocity_m_s = -5.0   # development example
target_pitch_deg = 0.0
base_throttle = 0.5                   # placeholder: tune
throttle_enabled = true
attitude_enabled = true

[controller.profiles.LANDING]
target_vertical_velocity_m_s = -1.0   # project design target example
target_pitch_deg = 0.0
base_throttle = 0.5                   # placeholder: tune
throttle_enabled = true
attitude_enabled = true
```

**Decision:** Do not copy placeholder zero gains into the final nominal scenario and call the controller complete.

Final gain values, base throttle, and descent targets are tuning outputs and must be validated through tests.

---

## Local persistence needs

**[Decision]** None inside the controller feature.

Controller state remains in memory during a simulation.

The module does not:

- write telemetry;
- serialize PID state;
- create files;
- save plots;
- access a database.

Later telemetry may record commands and optional controller diagnostics.

---

# 5. Logic Requirements

## Rule 1 — Controller receives measurements, never truth

Normal controller APIs must not accept:

```text
VehicleState
```

No hidden callback may fetch truth from the engine.

---

## Rule 2 — Controller does not mutate measurements

`MeasurementSnapshot` is read-only input.

---

## Rule 3 — Controller does not mutate mission state

Mission mode is input context only.

---

## Rule 4 — Throttle error sign must be restoring

```text
e_vy = target_vy - measured_vy
```

Faster-than-target downward descent produces positive correction.

---

## Rule 5 — Attitude error sign must be restoring

```text
e_theta = wrap(target_theta - measured_theta)
```

Positive pitch error away from target must produce command in the restoring direction under Feature 01's torque convention.

---

## Rule 6 — Attitude derivative uses gyro rate

For fixed target:

```text
error_rate = -measured_omega
```

unless a later explicit target-rate model is introduced.

---

## Rule 7 — Throttle includes configured base/feed-forward

```text
throttle =
    clamp(
        base_throttle
        + feedback_correction,
        0,
        1
    )
```

---

## Rule 8 — Controller output is desired command, not applied actuator state

Controller must not model actuator lag.

---

## Rule 9 — Controller output is explicitly bounded

Commands must never be NaN/Inf or outside configured controller command limits.

---

## Rule 10 — Actuator physical saturation remains separate

Do not import ActuatorState or mutate actuator internals.

---

## Rule 11 — PID update requires positive finite `dt`

Reject invalid control timestep.

---

## Rule 12 — PID integral is bounded

Never allow unbounded integral growth.

---

## Rule 13 — Conditional integration prevents windup

When output saturation and error direction would push farther into saturation, hold integral.

---

## Rule 14 — PID derivative is zero on first update when no explicit derivative signal exists

Avoid artificial first-step spike.

---

## Rule 15 — PID reset clears integral and previous error

Reset must be deterministic and tested.

---

## Rule 16 — Mission-mode change resets controller memory by default

Apply new profile on the same controller update.

---

## Rule 17 — Inactive modes do not integrate error

No hidden PID buildup during:

```text
PRELAUNCH
LANDED
ABORT
```

or any other profile where the relevant controller is disabled.

---

## Rule 18 — Invalid required measurement does not advance PID memory

No integral or derivative-state update.

---

## Rule 19 — Invalid required measurement holds last valid command

If none exists, use safe neutral/default command.

---

## Rule 20 — Controller status identifies invalid-input behavior

Do not silently hold a command with status `OK`.

---

## Rule 21 — Stale required measurement is invalid

Do not use known-stale critical data as if healthy.

---

## Rule 22 — Healthy delayed measurements remain usable

Feature 03 already distinguishes normal delayed `VALID` data from `STALE` data.

Controller uses valid delayed measurements normally.

---

## Rule 23 — Controller is deterministic

No RNG.

No wall-clock dependency.

---

## Rule 24 — Controller update cadence is simulation-tick aligned

No `sleep()` or real-time scheduler.

---

## Rule 25 — PID advances only on actual controller update ticks

Not on held ticks.

---

## Rule 26 — Mode transition may force an immediate controller update

This prevents carrying an old mode's command for a full control interval after the mission state changes.

---

## Rule 27 — Config errors fail before the nominal run

Do not tune around invalid config silently.

---

## Rule 28 — No scenario-name branching

Controller behavior depends on:

```text
measurement
mission mode
controller config
```

not the scenario ID.

---

## Rule 29 — No mission outcome logic

Controller must not declare:

```text
PASS
FAIL
LANDED
```

---

## Rule 30 — No truth-based feed-forward

Do not use current perfect mass, altitude, or velocity from `VehicleState`.

Configured static model parameters may be used only if intentionally part of controller configuration.

---

## PID pseudocode

```python
def update(
    error: float,
    dt: float,
    *,
    feed_forward: float = 0.0,
    derivative_value: float | None = None,
) -> PIDResult:

    validate_finite(error, dt, feed_forward)

    p = kp * error

    if derivative_value is not None:
        d_signal = derivative_value
    elif previous_error is None:
        d_signal = 0.0
    else:
        d_signal = (error - previous_error) / dt

    d = kd * d_signal

    candidate_integral = clamp(
        integral + error * dt,
        integral_min,
        integral_max,
    )

    candidate_raw = (
        feed_forward
        + p
        + ki * candidate_integral
        + d
    )

    candidate_output = clamp(
        candidate_raw,
        output_min,
        output_max,
    )

    if saturation_would_be_worsened(
        raw=candidate_raw,
        error=error,
    ):
        accepted_integral = integral
    else:
        accepted_integral = candidate_integral

    raw = (
        feed_forward
        + p
        + ki * accepted_integral
        + d
    )

    output = clamp(raw, output_min, output_max)

    integral = accepted_integral
    previous_error = error

    return PIDResult(...)
```

The exact anti-windup helper must be unit tested for upper and lower saturation.

---

## Throttle controller pseudocode

```python
def update(
    measurement: MeasurementSnapshot,
    profile: ControlProfile,
    dt: float,
) -> ControllerChannelResult:

    if not profile.throttle_enabled:
        reset_if_required()
        return inactive_throttle()

    if not valid(measurement.vy):
        return hold_last_throttle_invalid_input()

    error = (
        profile.target_vertical_velocity
        - measurement.vy
    )

    pid_result = pid.update(
        error,
        dt,
        feed_forward=profile.base_throttle,
    )

    throttle = clamp(
        pid_result.output,
        0.0,
        1.0,
    )

    return ...
```

---

## Attitude controller pseudocode

```python
def update(
    measurement: MeasurementSnapshot,
    profile: ControlProfile,
    dt: float,
) -> ControllerChannelResult:

    if not profile.attitude_enabled:
        reset_if_required()
        return inactive_attitude()

    if not valid(measurement.theta):
        return hold_last_attitude_invalid_input()

    if attitude_pid.kd != 0 and not valid(measurement.omega):
        return hold_last_attitude_invalid_input()

    angle_error = wrap_angle(
        profile.target_pitch
        - measurement.theta
    )

    error_rate = (
        -measurement.omega
        if measurement.omega is not None
        else 0.0
    )

    pid_result = pid.update(
        angle_error,
        dt,
        derivative_value=error_rate,
    )

    return ...
```

---

## Flight controller pseudocode

```python
def update(
    measurement: MeasurementSnapshot,
    mission_state: MissionState,
    dt: float,
) -> ControllerUpdate:

    profile = profiles[mission_state]

    if mission_state != previous_mission_state:
        reset_for_mode_change()
        previous_mission_state = mission_state

    throttle_result = throttle_controller.update(
        measurement,
        profile,
        dt,
    )

    attitude_result = attitude_controller.update(
        measurement,
        profile,
        dt,
    )

    command = ControlCommand(
        throttle=throttle_result.command,
        attitude_command=attitude_result.command,
    )

    status = combine_statuses(
        throttle_result.status,
        attitude_result.status,
    )

    return ControllerUpdate(
        command=command,
        status=status,
        reason=...
    )
```

---

## Edge cases

### `dt <= 0`

Reject.

---

### First PID update

Derivative from previous error is zero unless explicit derivative input is supplied.

---

### Full throttle saturation

Throttle output remains `1.0`.

Integral must not continue winding upward if positive error keeps pushing into upper saturation.

---

### Zero throttle saturation

Throttle output remains `0.0`.

Integral must not wind downward if negative error keeps pushing into lower saturation.

---

### Attitude command saturation

Bound desired gimbal request.

Actuator layer later applies its own physical model.

---

### Integral already at limit

It must remain inside configured limits.

---

### Large setpoint change on mode transition

Reset PID state first.

---

### Missing `vy`

Hold previous throttle/safe default, status invalid.

---

### Stale `vy`

Same behavior.

---

### Missing pitch

Hold previous attitude command/safe default.

---

### Missing gyro with nonzero attitude `kd`

Treat attitude input as invalid.

---

### Missing gyro with attitude `kd == 0`

Implementation may continue with P/PI attitude control, provided this is explicitly tested.

---

### Non-finite measurement value

Invalid input.

Do not feed NaN/Inf into PID state.

---

### Noise causes small rapid errors

Controller must remain deterministic.

Tuning/derivative choice should avoid excessive response.

Do not add filtering automatically unless a concrete need appears.

---

### Target vertical velocity impossible for current vehicle

Controller may saturate.

This is not automatically a software exception.

Later validation may show that the mission cannot meet the target.

---

### Target pitch outside controller's meaningful envelope

**Decision:** Validate configured targets as finite and within a conservative project-defined range if one is established.

**[Open Question]** Exact target-pitch configuration bounds should be aligned with the actuator/vehicle limits.

---

### Controller update period greater than sensor period

Use newest valid measurement at the controller update tick.

---

### Controller update period shorter than sensor period

Controller may see the same held valid measurement across multiple updates.

This is allowed, but gain tuning must account for it.

---

### Mission state changes on a non-scheduled controller tick

Force immediate update and reset.

---

### `LANDED` / `ABORT`

Return neutral/safe command and do not integrate.

---

# 6. Acceptance Criteria

## AC-01 — Controller public API does not accept truth state

**Given** the normal flight-controller API  
**When** its input types are inspected  
**Then** it accepts `MeasurementSnapshot`, mission mode, and controller timestep/context, and does not require `VehicleState`.

---

## AC-02 — Throttle controller uses measured vertical velocity

**Given** a valid measurement snapshot and active throttle profile  
**When** throttle control updates  
**Then** its feedback error is calculated from measured `vy`, not truth `vy`.

---

## AC-03 — Faster-than-target descent increases throttle correction

**Given** target `vy = -1 m/s` and measured `vy = -5 m/s`  
**When** throttle control updates with positive proportional gain  
**Then** the feedback correction is positive.

---

## AC-04 — Slower-than-target descent decreases throttle correction

**Given** target `vy = -1 m/s` and measured `vy = 0 m/s`  
**When** throttle control updates  
**Then** the feedback correction is negative.

---

## AC-05 — Base throttle contributes at zero error

**Given** measured vertical velocity equals target velocity and all PID state/derivative contributions are zero  
**When** throttle control updates  
**Then** requested throttle equals configured base throttle within bounds.

---

## AC-06 — Throttle command stays normalized

**Given** any finite valid feedback state  
**When** throttle control produces a command  
**Then** `0.0 <= throttle <= 1.0`.

---

## AC-07 — Positive pitch error produces restoring command

**Given** target pitch `0`, measured pitch positive, zero angular rate, and positive attitude `kp`  
**When** attitude control updates  
**Then** desired gimbal/attitude command is negative under the documented Feature 01 convention.

---

## AC-08 — Negative pitch error produces opposite restoring command

**Given** target pitch `0` and measured pitch negative  
**When** attitude control updates  
**Then** desired attitude command is positive.

---

## AC-09 — Gyro rate produces damping action

**Given** zero pitch error, positive measured angular rate, and positive attitude `kd`  
**When** attitude control updates  
**Then** derivative/rate contribution is negative.

---

## AC-10 — Attitude command respects software bounds

**Given** a very large attitude error  
**When** the controller updates  
**Then** desired attitude command remains within configured controller output bounds.

---

## AC-11 — PID proportional term is correct

**Given** error `e` and gain `kp`  
**When** PID updates  
**Then** proportional contribution equals `kp * e`.

---

## AC-12 — PID integral accumulates with control timestep

**Given** constant valid error and no saturation preventing integration  
**When** PID updates repeatedly  
**Then** integral state increases by `error * dt` per update before integral clamping.

---

## AC-13 — PID integral respects configured bounds

**Given** persistent error  
**When** integral accumulation reaches configured limit  
**Then** it does not exceed that limit.

---

## AC-14 — PID derivative uses error difference when no explicit derivative is supplied

**Given** two consecutive errors and positive `dt`  
**When** PID updates without explicit derivative input  
**Then** derivative signal equals `(current_error - previous_error) / dt`.

---

## AC-15 — First finite-difference derivative is zero

**Given** no previous error exists  
**When** PID updates without explicit derivative input  
**Then** derivative contribution is zero.

---

## AC-16 — Explicit derivative input overrides finite-difference derivative

**Given** an explicit derivative/error-rate signal  
**When** PID updates  
**Then** that signal is used for the derivative term.

---

## AC-17 — Attitude controller uses measured angular rate

**Given** valid pitch and gyro measurements  
**When** attitude control updates  
**Then** it uses measured `omega` as its rate-damping input rather than truth angular rate.

---

## AC-18 — Upper saturation prevents further positive windup

**Given** PID output is at its upper limit and positive error would push it farther upward  
**When** another update occurs  
**Then** integral state does not grow in the saturating direction.

---

## AC-19 — Upper saturation allows integral unwind

**Given** PID output is upper-saturated and error reverses direction  
**When** another update occurs  
**Then** integral state is allowed to move back toward the unsaturated region.

---

## AC-20 — Lower saturation prevents further negative windup

**Given** PID output is at its lower limit and error would push it farther downward  
**When** another update occurs  
**Then** integral does not continue winding downward.

---

## AC-21 — PID reset clears memory

**Given** nonzero integral and previous error  
**When** `reset()` is called  
**Then** integral becomes zero and previous error becomes `None`.

---

## AC-22 — Mission-mode change resets PID state

**Given** controller has accumulated state in one mission mode  
**When** the mission mode changes  
**Then** throttle and attitude PID memory reset before computing the new mode's control update.

---

## AC-23 — New mode profile applies immediately

**Given** a mission transition occurs on a controller tick or forces an update  
**When** controller update executes  
**Then** targets/base throttle come from the new mission-mode profile.

---

## AC-24 — Inactive throttle mode does not integrate

**Given** the current profile disables throttle control  
**When** controller updates  
**Then** throttle PID state does not accumulate error.

---

## AC-25 — Inactive attitude mode does not integrate

**Given** current profile disables attitude control  
**When** controller updates  
**Then** attitude PID state does not accumulate error.

---

## AC-26 — `LANDED` produces safe neutral command

**Given** mission state is `LANDED` under the default profile  
**When** controller updates  
**Then** desired throttle is `0` and desired attitude command is `0`.

---

## AC-27 — `ABORT` produces safe neutral controller command

**Given** mission state is `ABORT` under the default profile  
**When** controller updates  
**Then** desired throttle and attitude command are neutral and PID state is not integrating.

---

## AC-28 — Unavailable vertical velocity does not update throttle PID

**Given** `vy` is unavailable  
**When** throttle control is requested  
**Then** throttle PID memory is unchanged and controller status indicates invalid input.

---

## AC-29 — Stale vertical velocity does not update throttle PID

**Given** `vy` exists but sensor status is `STALE`  
**When** throttle control is requested  
**Then** the stale value is not treated as healthy input.

---

## AC-30 — Invalid throttle input holds last valid throttle

**Given** a prior valid throttle command exists and current required `vy` is invalid  
**When** controller updates  
**Then** requested throttle remains the prior valid requested throttle and status is `INVALID_INPUT`.

---

## AC-31 — Invalid throttle input with no history uses safe default

**Given** no previous valid throttle command exists and required `vy` is invalid  
**When** controller updates  
**Then** the safe default throttle command is used.

---

## AC-32 — Unavailable attitude does not update attitude PID

**Given** measured pitch is unavailable  
**When** attitude control updates  
**Then** attitude PID memory is unchanged and status identifies invalid input.

---

## AC-33 — Stale attitude is invalid

**Given** measured pitch status is stale  
**When** attitude control updates  
**Then** the controller does not treat it as a valid feedback value.

---

## AC-34 — Missing gyro is invalid when `kd != 0`

**Given** attitude derivative gain is nonzero and gyro measurement is unavailable/stale  
**When** attitude control updates  
**Then** the attitude update is invalid and PID state is not advanced.

---

## AC-35 — Missing gyro may be tolerated when `kd == 0`

**Given** attitude derivative gain is zero and pitch measurement is valid  
**When** attitude control updates without gyro data  
**Then** P/PI attitude control may proceed according to documented implementation behavior.

---

## AC-36 — Non-finite measurements never enter PID state

**Given** required measured value is NaN or Inf  
**When** controller input validation runs  
**Then** PID memory remains unchanged and the update is invalid.

---

## AC-37 — Invalid controller timestep is rejected

**Given** `dt <= 0` or non-finite `dt`  
**When** PID/controller update is attempted  
**Then** a controller runtime/config error is raised.

---

## AC-38 — Controller update cadence aligns to simulation ticks

**Given** configured control interval and simulation `dt`  
**When** controller timing is resolved  
**Then** update interval is represented as a positive integer number of simulation ticks or configuration is rejected.

---

## AC-39 — PID state advances only on controller update ticks

**Given** controller is configured to update every `N > 1` simulation ticks  
**When** intermediate simulation ticks occur  
**Then** PID integral/previous-error state is not advanced on held ticks.

---

## AC-40 — Last command is held between controller updates

**Given** controller update is not due on the current tick  
**When** simulation continues  
**Then** the previous desired `ControlCommand` is retained and status may indicate `HELD`.

---

## AC-41 — Mode change can force immediate control update

**Given** mission mode changes between normal scheduled controller updates  
**When** the engine processes the transition tick  
**Then** the controller may reset and compute the new mode command immediately rather than holding the old mode's command.

---

## AC-42 — Controller is deterministic

**Given** identical measurement, mission-mode, timing, profile, and PID-state sequences  
**When** two controller instances execute  
**Then** their command/status sequences match.

---

## AC-43 — Controller does not mutate measurements

**Given** an immutable `MeasurementSnapshot`  
**When** controller update completes  
**Then** no measurement field or metadata has changed.

---

## AC-44 — Controller contains no scenario-name branches

**Given** controller source code  
**When** it is inspected  
**Then** behavior is not selected using scenario IDs such as `altimeter_freeze` or `degraded_actuator`.

---

## AC-45 — Controller does not apply actuator lag

**Given** a desired command change  
**When** controller returns a `ControlCommand`  
**Then** it does not simulate actuator time constant, slew rate, or physical response lag.

---

## AC-46 — Controller does not decide mission transitions

**Given** measurements cross a mission transition threshold  
**When** controller updates  
**Then** it does not change `MissionState` itself.

---

## AC-47 — Closed-loop pitch control is restoring

**Given** the real Feature 01/02/03 plant and a small initial pitch error under nominal sensing  
**When** attitude control is connected through an applied-actuation path  
**Then** pitch error decreases toward the configured target without sustained divergence under the documented nominal test configuration.

---

## AC-48 — Closed-loop vertical control responds to excessive descent

**Given** measured descent is faster than target and the plant has available thrust authority  
**When** throttle control closes the loop  
**Then** requested throttle increases and measured vertical velocity moves toward the configured target over the nominal test window.

---

## AC-49 — Nominal controller remains measurement-only in integration tests

**Given** the complete closed-loop test wiring  
**When** dependencies are inspected  
**Then** the controller receives only `MeasurementSnapshot`, mission mode/profile, and controller timing—not `VehicleState`.

---

## AC-50 — Cross-feature nominal mission controller gate

**Given** Mission State Machine and Actuator Modeling are later connected and nominal configuration is tuned  
**When** the nominal mission runs end-to-end  
**Then** the controller must support a mission that satisfies the project-defined landing limits:

```text
|landing vertical speed| <= 2.0 m/s
horizontal error <= 5.0 m
pitch error <= 5 degrees
```

This criterion is a cross-feature completion gate and cannot be fully proven by Feature 04 in isolation.

---

# 7. Test Plan

## Unit tests

### `tests/unit/test_pid.py`

Required:

```text
test_proportional_term
test_integral_accumulation
test_integral_upper_bound
test_integral_lower_bound
test_derivative_from_error_difference
test_first_derivative_is_zero
test_explicit_derivative_signal
test_output_upper_clamp
test_output_lower_clamp
test_upper_saturation_prevents_windup
test_upper_saturation_allows_unwind
test_lower_saturation_prevents_windup
test_lower_saturation_allows_unwind
test_reset_clears_integral
test_reset_clears_previous_error
test_invalid_dt_rejected
test_non_finite_error_rejected
test_non_finite_gain_config_rejected
```

---

### `tests/unit/test_throttle_controller.py`

Recommended:

```text
test_fast_descent_increases_throttle_correction
test_slow_descent_decreases_throttle_correction
test_zero_error_returns_base_throttle
test_throttle_never_below_zero
test_throttle_never_above_one
test_unavailable_vy_holds_last_command
test_stale_vy_holds_last_command
test_invalid_vy_does_not_update_pid
test_no_history_invalid_vy_uses_safe_default
test_inactive_profile_returns_safe_command
test_mode_change_resets_pid
```

---

### `tests/unit/test_attitude_controller.py`

Recommended:

```text
test_positive_pitch_generates_negative_restoring_command
test_negative_pitch_generates_positive_restoring_command
test_positive_omega_generates_negative_damping
test_negative_omega_generates_positive_damping
test_angle_error_wraps_shortest_direction
test_attitude_command_limit
test_unavailable_theta_holds_command
test_stale_theta_invalid
test_missing_gyro_invalid_when_kd_nonzero
test_missing_gyro_allowed_when_kd_zero
test_invalid_attitude_input_does_not_update_pid
test_mode_change_resets_attitude_pid
```

---

### `tests/unit/test_flight_controller.py`

Recommended:

```text
test_combines_throttle_and_attitude_commands
test_controller_status_ok_when_both_channels_valid
test_invalid_channel_propagates_status
test_landed_profile_is_inactive
test_abort_profile_is_inactive
test_unknown_profile_rejected
test_controller_does_not_mutate_measurement
test_deterministic_command_sequence
```

---

## Configuration tests

Recommended:

```text
test_control_interval_resolves_to_integer_ticks
test_non_aligned_control_interval_rejected
test_output_min_greater_than_max_rejected
test_integral_min_greater_than_max_rejected
test_base_throttle_out_of_range_rejected
test_missing_active_mode_profile_rejected
test_non_finite_target_rejected
```

---

## Integration tests with Features 01–03

Recommended file:

```text
tests/integration/test_closed_loop.py
```

### Pitch stabilization

Setup:

- simplified plant;
- nominal sensors;
- initial small pitch error;
- target pitch zero;
- controlled gimbal path.

Assert:

- error decreases;
- command sign is restoring;
- all values remain finite;
- controller never receives truth.

---

### Vertical-velocity regulation

Setup:

- descending vehicle;
- nominal vertical-velocity sensor;
- active throttle controller;
- simplified direct/temporary actuator application until Feature 05 exists.

Assert:

- too-fast descent causes throttle increase;
- `vy` trends toward target;
- no command leaves normalized range.

---

### Sensor noise robustness

Use small deterministic noise.

Assert:

- closed loop remains finite;
- same seed reproduces command trajectory;
- controller does not become nondeterministic.

Do not require unrealistically perfect tracking.

---

### Sensor delay behavior

Use a valid delayed measurement from Feature 03.

Assert:

- controller accepts it while status remains `VALID`;
- command changes reflect delayed data;
- no wall-clock dependency exists.

---

### Stale measurement behavior

Force sensor stale.

Assert:

- controller holds command;
- PID state freezes;
- status becomes invalid-input.

---

## Integration tests with Feature 05 Actuator Modeling

Add once Feature 05 exists:

```text
requested throttle -> actuator -> actual throttle
requested gimbal -> actuator -> actual gimbal
```

Verify controller remains unaware of actuator internal lag.

---

## Integration tests with Feature 06 Mission State Machine

Add once Feature 06 exists:

- state transition resets PID memory;
- new profile applies on transition tick;
- `LANDED`/`ABORT` produce safe command;
- controller never owns transition rules.

---

## End-to-end test deferred until required dependencies exist

The complete nominal landing criterion requires:

- mission-state logic;
- actuator dynamics;
- tuned controller profiles;
- validation.

Once those exist:

```python
def test_nominal_controller_supports_valid_landing():
    ...
```

must assert the documented mission limits.

---

## Manual QA checklist

- [ ] Controller imports measurement type, not `VehicleState`.
- [ ] No hidden engine/truth callback exists.
- [ ] Throttle error sign is documented.
- [ ] Attitude restoring sign is documented.
- [ ] Attitude controller uses gyro rate.
- [ ] Output commands have explicit units.
- [ ] Throttle command remains `[0,1]`.
- [ ] Attitude command remains inside software bounds.
- [ ] Controller and actuator limits are conceptually separated.
- [ ] PID `dt` is control-update interval, not blindly simulation `dt`.
- [ ] PID integral has explicit bounds.
- [ ] Conditional anti-windup is implemented.
- [ ] PID reset is implemented.
- [ ] Mode changes reset safely.
- [ ] Inactive modes do not integrate.
- [ ] Stale measurements are not treated as healthy.
- [ ] Invalid measurements do not modify PID memory.
- [ ] Invalid measurements do not crash the simulation as normal domain behavior.
- [ ] Command hold behavior is explicit.
- [ ] Controller uses no RNG.
- [ ] Controller uses no wall-clock timing.
- [ ] No scenario-name branches exist.
- [ ] Controller does not modify mission state.
- [ ] Controller does not model actuator lag.
- [ ] All unit tests pass.
- [ ] Closed-loop pitch test passes.
- [ ] Closed-loop vertical-velocity test passes.

---

## Demo verification checklist

- [ ] Reviewer can see controller API accepts measurements, not truth.
- [ ] Pitch error produces restoring requested gimbal.
- [ ] Angular-rate feedback damps rotation.
- [ ] Fast descent produces increased requested throttle.
- [ ] Requested throttle remains normalized.
- [ ] Requested gimbal remains bounded.
- [ ] PID anti-windup has a passing unit test.
- [ ] Mode transition/reset behavior has a passing test.
- [ ] Invalid/stale sensor input has explicit controller status.
- [ ] Same deterministic input sequence produces same command sequence.
- [ ] Later requested-vs-actual actuator plot clearly shows controller/actuator separation.
- [ ] Full nominal mission eventually satisfies the cross-feature landing criteria.

---

# 8. Portfolio Value

## How this feature helps the project stand out

This is the point where AstraLoop stops being a passive simulation and becomes a real closed-loop software system.

The strong story is:

> "My controller never reads perfect simulation state. It receives timestamped simulated measurements, maintains its own PID state, handles saturation and stale inputs, outputs desired commands, and is tested both in isolation and against the numerical plant."

That is stronger than:

> "I added a PID to a rocket animation."

The feature creates interview depth around:

- control laws;
- software interfaces;
- state ownership;
- command vs actuator output;
- anti-windup;
- measurement validity;
- deterministic timing;
- mission-mode changes;
- testing continuously evolving behavior.

---

## What to mention in README

Recommended wording:

> **Closed-loop flight control:** AstraLoop uses measurement-driven throttle and pitch controllers built on a reusable PID implementation. Controllers receive `MeasurementSnapshot` data—not simulator truth—maintain explicit control state, apply bounded desired commands, and reset safely across mission-mode changes.

Useful bullets:

- vertical-velocity → throttle feedback;
- pitch + gyro → desired gimbal feedback;
- configurable mission-mode targets;
- base-throttle feed-forward;
- integral clamping and anti-windup;
- stale/missing input handling;
- deterministic update cadence;
- desired command separated from actual actuator response.

---

## What to mention in interviews

### How did you prevent perfect-state cheating?

> "The controller API only accepts `MeasurementSnapshot`. `VehicleState` is not part of the normal control interface, so the control law has to work with the same imperfect data the software layer sees."

### Why control vertical velocity?

> "The mission state machine can switch descent-rate targets by phase, and vertical landing speed is one of the project's objective validation criteria. It keeps the MVP controller simple and directly tied to a measurable mission outcome."

### Why use a base throttle?

> "At zero velocity error, the vehicle still needs thrust to oppose gravity. A configured feed-forward/base throttle gives the loop an operating point, while feedback corrects model mismatch and changing conditions."

### Why use gyro rate for the attitude derivative?

> "I already have a simulated angular-rate sensor, so using measured omega provides direct damping and avoids creating a noisy numerical derivative of pitch."

### How did you handle integral windup?

> "I combined integral bounds with conditional integration. If the output is saturated and the error would push it farther into saturation, I stop integrating; if the error reverses, the integral can unwind."

### What happens on a mission-mode change?

> "The state machine owns the transition. The controller receives the new mode, resets PID memory by default, switches to the new profile, and recomputes the command immediately."

### What happens if a sensor becomes stale?

> "The controller does not treat stale data as healthy. It freezes that PID state, holds the last valid requested command or uses a safe default if none exists, and returns an invalid-input status so mission logic can respond."

### Why not build a sophisticated guidance controller?

> "I wanted the strongest software-engineering signal for a finishable project. Throttle and attitude feedback are enough to create a genuine closed loop. I would only add horizontal guidance if testing shows a concrete need."

---

# 9. Implementation Notes for Codex

## Likely files/folders

Primary:

```text
src/astraloop/model/commands.py

src/astraloop/control/
├── __init__.py
├── pid.py
├── throttle.py
└── attitude.py
```

Potential coordinator:

```text
src/astraloop/control/controller.py
```

or:

```text
src/astraloop/control/flight_controller.py
```

Config touchpoints:

```text
src/astraloop/config/schema.py
src/astraloop/config/validation.py
```

Tests:

```text
tests/unit/test_pid.py
tests/unit/test_throttle.py
tests/unit/test_attitude.py
tests/integration/test_closed_loop.py
```

---

## Suggested responsibilities

### `model/commands.py`

Own:

```text
ControlCommand
ControllerStatus / ControllerUpdate if shared
```

Do not place controller equations here.

---

### `control/pid.py`

Own only reusable PID behavior:

- gains;
- integral state;
- previous error;
- update;
- reset;
- output clamp;
- anti-windup.

It must not know:

- vertical velocity;
- pitch;
- mission states;
- actuator models.

---

### `control/throttle.py`

Own:

- `vy` measurement validation;
- vertical-velocity error;
- base-throttle/feed-forward;
- throttle PID;
- normalized requested throttle.

---

### `control/attitude.py`

Own:

- pitch measurement validation;
- gyro validation;
- angle error;
- rate damping;
- attitude PID;
- requested gimbal command.

---

### `control/flight_controller.py`

If needed, own:

- mission-profile lookup;
- mode-change detection/reset;
- combining channel outputs;
- controller status composition.

Do not let it become the Mission State Machine.

---

## Build order

### Step 1 — Lock command meaning and units

Before PID tuning, define:

```text
throttle            normalized desired command
attitude_command    desired gimbal angle in radians
```

This prevents controller/actuator confusion later.

---

### Step 2 — Implement generic PID with tests

Do not connect vehicle physics yet.

Pass:

- P;
- I;
- D;
- clamp;
- anti-windup;
- reset;
- invalid `dt`.

---

### Step 3 — Implement throttle controller with synthetic measurements

Use zero/noise-free `MeasurementSnapshot`.

Verify error signs and limits.

---

### Step 4 — Implement attitude controller with synthetic measurements

Verify:

- angle sign;
- gyro damping sign;
- angle wrapping;
- command limits.

---

### Step 5 — Implement invalid-measurement behavior

Before closing the plant loop, test:

- unavailable;
- stale;
- NaN;
- hold last command;
- PID state does not advance.

---

### Step 6 — Implement mission-mode profiles

Use the MissionState enum contract/skeleton if it already exists.

Do not implement transition guards.

---

### Step 7 — Implement mode-change reset

Test every controller-state reset path.

---

### Step 8 — Resolve controller cadence

Add config validation against simulation `dt`.

Keep timing driven by simulation ticks.

---

### Step 9 — Connect sensor → controller

Prove normal controller code sees only `MeasurementSnapshot`.

---

### Step 10 — Close attitude loop first

Pitch stabilization is usually the cleaner isolated feedback test.

Tune enough to achieve stable restoring behavior.

---

### Step 11 — Close vertical-velocity loop

Tune throttle controller around a selected base throttle.

---

### Step 12 — Stop tuning once behavior is robust enough

Do not chase unrealistic optimality.

The target is:

```text
stable
explainable
testable
good enough for mission criteria
```

not research-grade guidance.

---

## Risks

### Risk 1 — Wrong feedback sign

A sign error makes the loop actively diverge.

**Mitigation:**

- synthetic sign tests before full simulation;
- small initial-error closed-loop tests;
- documented coordinate convention.

---

### Risk 2 — Truth-state leakage

A developer may pass `VehicleState` into controller "just for one calculation."

**Mitigation:** do not import the truth type into normal control modules.

---

### Risk 3 — Controller and actuator responsibilities blur

Controller starts simulating lag/slew.

**Mitigation:** controller outputs desired command; Feature 05 models actual actuation.

---

### Risk 4 — Integral windup

Persistent saturation can make recovery slow/unstable.

**Mitigation:** conditional integration + explicit integral bounds.

---

### Risk 5 — Controller tuning consumes the project

This is explicitly identified as a project risk.

**Mitigation:**

- simple control objective;
- one global gain set per controller initially;
- state-specific setpoints;
- bounded commands;
- avoid advanced optimal control.

---

### Risk 6 — No feed-forward causes large integral burden

**Mitigation:** configurable base throttle.

---

### Risk 7 — Too many gain schedules

State-specific gains can turn the config into a tuning maze.

**Mitigation:** start with global throttle and attitude gains.

---

### Risk 8 — Stale measurements corrupt PID state

**Mitigation:** reject stale required input and freeze controller state.

---

### Risk 9 — Controller update `dt` is wrong

Using simulation `dt` while controller updates less often changes integral/derivative behavior.

**Mitigation:** pass actual control-update interval.

---

### Risk 10 — Derivative amplifies sensor noise

**Mitigation:**

- attitude derivative uses gyro;
- throttle `kd` may remain zero initially;
- do not add filtering unless needed.

---

### Risk 11 — Mode transition creates command jump

Resetting integral can cause a discontinuity.

**Mitigation:** accept simple reset for MVP; implement bumpless transfer only if real tests demonstrate a problem.

---

### Risk 12 — Horizontal guidance scope creep

Adding x/vx guidance can multiply tuning complexity.

**Mitigation:** keep target pitch configurable and add guidance only after the MVP controller is stable.

---

## What not to change

While implementing Feature 04, Codex should **not**:

- modify 2D physics equations;
- modify RK4;
- change simulation tick/time semantics;
- give controller access to `VehicleState`;
- change sensor noise/delay/freeze implementation;
- implement actuator response lag;
- implement actuator slew rate;
- implement physical actuator state;
- implement mission transition guards;
- decide when `DESCENT` changes to `LANDING`;
- implement fault scheduling;
- branch on scenario names;
- write telemetry files;
- implement mission PASS/FAIL;
- create plots;
- implement CLI commands;
- add horizontal guidance unless a concrete tested need exists;
- add MPC/LQR unless explicitly approved later;
- add Kalman filtering;
- add machine learning;
- add reinforcement learning;
- add 6-DOF control;
- add orbital guidance;
- add web/SaaS infrastructure;
- add a database.

If Feature 05 or Feature 06 is not implemented yet, use the smallest typed boundary/stub necessary to test the controller.

---

# Feature-Specific Definition of Done

Feature 04 is complete when:

- [ ] A reusable PID implementation exists.
- [ ] PID supports P/I/D terms.
- [ ] PID output limits exist.
- [ ] PID integral limits exist.
- [ ] Conditional anti-windup exists.
- [ ] PID reset behavior exists.
- [ ] Throttle controller exists.
- [ ] Throttle controller uses measured `vy`.
- [ ] Throttle controller uses configured target vertical velocity.
- [ ] Throttle controller supports base/feed-forward throttle.
- [ ] Throttle output remains `[0,1]`.
- [ ] Attitude controller exists.
- [ ] Attitude controller uses measured pitch.
- [ ] Attitude controller uses measured gyro rate for damping.
- [ ] Attitude command uses radians.
- [ ] Attitude output is explicitly bounded.
- [ ] Controller API does not accept `VehicleState`.
- [ ] Controller consumes mission mode/profile but does not own transitions.
- [ ] Mission-mode profiles provide setpoints/enabled state.
- [ ] Mode changes reset PID state safely.
- [ ] Inactive modes do not accumulate PID error.
- [ ] `LANDED` default command is safe neutral.
- [ ] `ABORT` default command is safe neutral.
- [ ] Missing/stale required measurement is handled without corrupting PID state.
- [ ] Invalid-input behavior holds last valid command or uses safe default.
- [ ] Controller status identifies invalid input.
- [ ] Controller cadence is deterministic and tick-aligned.
- [ ] PID uses actual control-update `dt`.
- [ ] Commands are held between controller updates.
- [ ] Same deterministic inputs reproduce the same command sequence.
- [ ] Controller does not use RNG.
- [ ] Controller performs no persistence.
- [ ] Controller does not simulate actuator lag.
- [ ] Controller contains no scenario-name branches.
- [ ] PID unit tests pass.
- [ ] Throttle unit tests pass.
- [ ] Attitude unit tests pass.
- [ ] Closed-loop pitch stabilization integration test passes.
- [ ] Closed-loop vertical-velocity response test passes.
- [ ] Truth-state isolation is verified in integration tests.
- [ ] Final nominal gains/targets are documented once tuning is complete.
- [ ] When Features 05/06/10 are available, the full nominal mission satisfies project landing criteria.

---

# Open Questions

1. **[Open Question] What final throttle PID gains should be used?**  
   The planning documents do not specify them. They must be tuned against the implemented plant.

2. **[Open Question] What final attitude PID gains should be used?**  
   Same requirement.

3. **[Open Question] What base throttle should each active mission mode use?**  
   It depends on the final vehicle mass/thrust parameters.

4. **[Open Question] What exact `DESCENT` target vertical velocity should be used?**  
   It should be faster than the final landing target but remain controllable.

5. **[Open Question] Should the final `LANDING` target remain approximately `-1.0 m/s` or use another value inside the `2.0 m/s` validation limit?**

6. **[Open Question] What controller update interval provides the best balance of stable behavior and clear discrete-time semantics?**  
   It must be an integer multiple of simulation `dt`.

7. **[Open Question] Should attitude integral gain be nonzero at all?**  
   A PD attitude controller may be sufficient. Keep `ki` configurable, but do not force integral action without evidence.

8. **[Open Question] Should throttle derivative gain remain zero for the MVP?**  
   Velocity measurement noise can make derivative action undesirable. Start with PI/PID infrastructure but tune empirically.

9. **[Open Question] Does the nominal/fault mission actually require a horizontal-position guidance outer loop?**  
   Recommended: do not add one unless testing shows the project cannot meet horizontal-error goals with the selected mission setup.

10. **[Open Question] Should state-specific PID gains be introduced?**  
    Recommended: only if one global gain set cannot handle active mission modes.

11. **[Open Question] Does mode-reset behavior need bumpless transfer?**  
    Start with explicit reset; add bumpless transfer only if command jumps create a demonstrated issue.

12. **[Open Question] What conservative pitch-target bounds should config validation enforce?**  
    Align with the final vehicle/actuator capabilities in Feature 05.

---

# Move On When

- [ ] Every major control-law behavior has Given/When/Then acceptance criteria.
- [ ] PID behavior is independently unit tested.
- [ ] Throttle and attitude feedback signs are correct.
- [ ] Anti-windup is tested.
- [ ] Controller uses only `MeasurementSnapshot`.
- [ ] Mode/reset behavior is deterministic.
- [ ] Missing/stale input behavior is explicit.
- [ ] A reviewer can see pitch and vertical-velocity closed-loop demos.
- [ ] The controller clearly demonstrates feedback-control and stateful-software skill.
- [ ] Actuator physics remains outside this feature.
- [ ] Mission transitions remain outside this feature.
- [ ] No unnecessary guidance, estimator, ML, SaaS, database, or GUI scope has been added.
- [ ] The feature remains finishable and ready to connect to Feature 05 — Actuator Modeling.
