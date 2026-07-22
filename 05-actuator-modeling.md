# Feature 05 — Actuator Modeling

> **Project:** AstraLoop — Python Software-in-the-Loop Flight Control & Validation System  
> **Feature:** Actuator Modeling  
> **Document path:** `docs/features/05-actuator-modeling.md`  
> **Status:** Implementation specification  
> **Primary goal:** Convert the controller's desired throttle and attitude/gimbal commands into deterministic, physically constrained applied actuator state using explicit saturation and response dynamics, while preserving a clean boundary between control software, actuator behavior, fault injection, and vehicle dynamics.

---

## Scope Boundary

**[Confirmed]** AstraLoop's architecture separates:

```text
Controller
    |
    v
ControlCommand
    |
    v
Actuator Modeling
    |
    v
ActuatorState
    |
    v
2D Flight Dynamics
```

**[Confirmed]** The actuator layer owns:

- command saturation;
- actuator response lag;
- actuator-specific modeled limits;
- the actual applied actuator state.

**[Confirmed]** The controller produces **desired commands**, while the dynamics layer consumes the **actual applied actuator state**.

**[Confirmed]** The project includes a future `degraded_actuator` fault scenario, and faults must change real subsystem behavior rather than merely alter a final result label.

**[Decision]** Feature 05 owns the **deterministic command-to-applied-actuation model**.

It owns:

- throttle actuator state;
- gimbal/attitude actuator state;
- physical actuator bounds;
- command saturation at the actuator boundary;
- first-order response lag;
- optional deterministic slew/rate limits where justified;
- actuator initialization;
- per-tick actuator updates;
- actual applied actuation exposed to dynamics;
- actuator status/diagnostics useful to later telemetry;
- target-local runtime degradation hooks for the later Fault Injection System;
- unit tests and controller/engine/dynamics integration tests.

It does **not** own:

- PID/control-law logic;
- controller anti-windup;
- sensor modeling;
- mission-state transitions;
- general fault scheduling;
- scenario expected outcomes;
- telemetry file writing;
- mission validation;
- plotting;
- CLI behavior;
- propulsion thermodynamics;
- engine spool physics beyond the simple actuator lag;
- detailed servo/motor/electrical models.

---

# 1. Feature Overview

## Feature name

**Actuator Modeling**

---

## One-sentence description

**[Decision]** Implement deterministic throttle and gimbal actuator models that transform desired controller commands into bounded, lagged, physically applied commands used by the 2D flight dynamics.

---

## Detailed description

Feature 04 ends at a desired software command:

```python
ControlCommand(
    throttle=...,
    attitude_command=...,
)
```

That command is not automatically equal to what the simulated vehicle physically receives.

Feature 05 creates the physical command-response layer:

```text
desired throttle
      |
      v
 actuator saturation
      |
      v
 response lag / optional rate limit
      |
      v
 actual throttle


desired gimbal
      |
      v
 actuator saturation
      |
      v
 response lag / optional rate limit
      |
      v
 actual gimbal
```

The resulting `ActuatorState` is what Feature 01's dynamics uses.

This separation matters because real commanded systems do not respond infinitely fast or without limits.

---

## Why the actuator layer must be separate

Without a separate actuator layer, code could effectively do:

```python
applied_throttle = controller_command.throttle
applied_gimbal = controller_command.attitude_command
```

This would remove several important engineering behaviors:

- command saturation;
- delayed physical response;
- command-vs-applied mismatch;
- degraded actuator scenarios;
- realistic control tuning pressure;
- fault-injection hooks.

A separate actuator model lets AstraLoop demonstrate:

```text
what the controller asked for
```

versus:

```text
what the vehicle actually received
```

which is one of the clearest reviewer-facing signals in the project.

---

## Actuator channels

The MVP has two actuator channels.

### 1. Throttle actuator

Input:

```text
ControlCommand.throttle
```

Desired command unit:

```text
normalized throttle
```

Nominal physical range:

```text
0.0 to 1.0
```

Output:

```text
ActuatorState.throttle
```

Meaning:

```text
actual normalized throttle applied to the dynamics model
```

---

### 2. Gimbal/attitude actuator

Input:

```text
ControlCommand.attitude_command
```

Desired command unit:

```text
rad
```

Output:

```text
ActuatorState.gimbal_angle
```

Meaning:

```text
actual physical gimbal angle applied to thrust-vector dynamics
```

**Decision:** Use `gimbal_angle` in the actuator-state object even if Feature 04 calls the controller output `attitude_command`.

**Justification:** The controller expresses the desired attitude-control actuation; the physical plant consumes an actual gimbal angle. The naming difference makes the software/physical boundary clearer.

---

## Actuator state

Recommended shared domain record:

```python
@dataclass(frozen=True)
class ActuatorState:
    throttle: float
    gimbal_angle: float
```

This object is immutable after each update.

The actuator model itself owns the current applied state internally and returns a new state each update.

---

## Initial actuator state

**[Decision]** Default initial applied state:

```text
throttle = 0.0
gimbal_angle = 0.0 rad
```

unless an explicit valid initial actuator state is configured for a special test.

### Why

- deterministic;
- physically neutral;
- matches PRELAUNCH behavior;
- avoids hidden initial energy/control input.

---

## Command saturation

The actuator layer must explicitly enforce physical bounds.

### Throttle

Nominal physical bounds:

```text
min_throttle <= actual/target throttle <= max_throttle
```

Recommended MVP:

```text
min_throttle = 0.0
max_throttle = 1.0
```

The controller should already produce normalized commands, but the actuator **must still enforce its own physical limits**.

### Gimbal

Physical bounds:

```text
-min_gimbal_limit <= gimbal <= +max_gimbal_limit
```

For symmetric MVP configuration:

```text
-gimbal_limit <= gimbal <= +gimbal_limit
```

**[Open Question]** The final gimbal limit must be selected with the vehicle/controller configuration.

---

## Why actuator saturation exists even if controller limits exist

Controller bounds and actuator bounds are not redundant.

### Controller limit

Represents:

```text
software-level requested command constraint
```

and helps avoid PID windup/nonsensical commands.

### Actuator limit

Represents:

```text
physical actuator capability
```

and remains authoritative.

A later degraded-actuator fault may reduce the physical actuator limit even though the controller's requested-command bounds remain unchanged.

This is exactly the kind of mismatch AstraLoop should be able to simulate.

---

## Response-lag model

**[Decision]** Model nominal actuator response with a first-order lag.

Continuous form:

```text
d(actual)/dt =
    (target - actual) / tau
```

where:

```text
tau > 0
```

is the actuator time constant.

A small `tau` responds quickly.

A large `tau` responds slowly.

---

## Discrete-time lag update

Because actuators update on the deterministic simulation tick, use an exact discrete update for a constant target over one tick:

```text
alpha = 1 - exp(-dt / tau)

next_actual =
    current_actual
    + alpha * (target - current_actual)
```

### Why use the exact first-order discrete form

Compared with forward Euler:

```text
actual += dt/tau * (target - actual)
```

the exponential update:

- remains stable for positive `dt` and `tau`;
- preserves the intended first-order behavior cleanly;
- prevents overshoot solely from a large `dt/tau` ratio;
- is simple to test;
- is easy to explain.

**Decision:** This is the preferred nominal lag implementation.

---

## Zero-lag option

A test or future config may want effectively instantaneous response.

**Decision:** Support an explicit:

```text
tau = 0
```

mode meaning:

```text
next_actual = saturated_target
```

Do not divide by zero.

Configuration rules therefore become:

```text
tau >= 0
```

rather than strictly `> 0`.

---

## Slew/rate limiting

The master blueprint lists:

```text
slew/rate limit if used
```

rather than requiring it unconditionally.

**Decision:** Implement optional rate limiting in a way that can be disabled.

For a maximum absolute rate:

```text
max_rate
```

the maximum permitted change in one actuator update is:

```text
max_delta = max_rate * dt
```

Then:

```text
delta = lagged_candidate - current_actual

rate_limited_delta =
    clamp(delta, -max_delta, +max_delta)

next_actual =
    current_actual + rate_limited_delta
```

### Order

Recommended:

```text
1. saturate desired target to physical position/value bounds
2. compute first-order lag candidate
3. apply optional slew/rate limit to the state change
4. enforce final hard physical bounds
```

### Why optional

A first-order lag alone already makes the actuator non-instantaneous.

Adding a rate limit creates another parameter and tuning interaction.

Use it only if it improves the degraded-actuator story or nominal realism enough to justify the added complexity.

**Recommended MVP default:** no explicit rate limit for throttle; optional finite gimbal slew limit if testing shows it is useful.

---

## Command update cadence

**Decision]** Actuator state updates every simulation tick.

The engine's fixed timestep is:

```text
dt
```

and the actuator update uses the same `dt`.

This means:

- controller may update less often;
- its desired command may be held between controller updates;
- actuator continues evolving toward that held command every simulation tick.

Example:

```text
controller updates every 2 ticks

tick 0:
  new command
  actuator moves toward it

tick 1:
  same held controller command
  actuator moves closer

tick 2:
  new controller command
  actuator moves toward new target
```

This creates a clean multi-rate system without a separate actuator scheduler.

---

## Applied input during RK4

Feature 02 defines that the applied physical input is held constant across the four RK4 stages within a single simulation tick.

Therefore the ordering is:

```text
controller command for tick
        |
        v
actuator state update for tick
        |
        v
freeze resulting ActuatorState
        |
        v
RK4 k1/k2/k3/k4 all use same applied state
        |
        v
next truth state
```

**Decision:** The actuator model updates once per simulation tick, not once per RK4 sub-stage.

This prevents actuator lag from being integrated four times per engine tick.

---

## Throttle actuator model

Recommended nominal update:

```text
requested =
    ControlCommand.throttle

target =
    clamp(
        requested,
        effective_min_throttle,
        effective_max_throttle
    )

candidate =
    first_order_update(
        current=actual_throttle,
        target=target,
        tau=effective_throttle_tau,
        dt=dt
    )

next_throttle =
    apply_optional_rate_limit(
        current=actual_throttle,
        candidate=candidate,
        max_rate=effective_throttle_rate,
        dt=dt
    )
```

Final:

```text
effective_min_throttle
<= next_throttle
<= effective_max_throttle
```

---

## Gimbal actuator model

Recommended:

```text
requested =
    ControlCommand.attitude_command

target =
    clamp(
        requested,
        -effective_gimbal_limit,
        +effective_gimbal_limit
    )

candidate =
    first_order_update(
        current=actual_gimbal,
        target=target,
        tau=effective_gimbal_tau,
        dt=dt
    )

next_gimbal =
    apply_optional_rate_limit(
        current=actual_gimbal,
        candidate=candidate,
        max_rate=effective_gimbal_rate,
        dt=dt
    )
```

Then enforce final physical bounds.

---

## Degraded actuator hooks

The future Fault Injection System must be able to model a **degraded actuator response** without rewriting core actuator code.

**Decision]** Feature 05 exposes target-local runtime modifiers for parameters such as:

```text
response time constant multiplier
maximum output scale
maximum rate scale
```

Examples:

```text
effective_tau =
    nominal_tau * response_lag_multiplier
```

```text
effective_max_throttle =
    nominal_max_throttle * authority_scale
```

```text
effective_gimbal_limit =
    nominal_gimbal_limit * authority_scale
```

```text
effective_rate =
    nominal_rate * rate_scale
```

### What Feature 05 does not decide

It does not decide:

```text
when degradation starts
which scenario activates it
how long it lasts
what final mission outcome is expected
```

Those belong to Feature 07 Fault Injection System.

---

## Recommended degraded-actuator MVP behavior

The source documents require a `degraded_actuator` scenario but do not prescribe the exact degradation.

**[Decision]** Prefer a slower-response fault as the primary degraded-actuator behavior:

```text
response_lag_multiplier > 1
```

because it directly demonstrates the difference between:

```text
desired command
```

and:

```text
actual applied command
```

Optional secondary degradation:

```text
rate_scale < 1
```

or:

```text
authority_scale < 1
```

should be added only if needed.

**Justification:** A lag increase is simple, deterministic, visible in telemetry, and aligned with the source language that asks what happens when "an actuator becomes sluggish."

---

## Actuator status metadata

Useful later for telemetry:

```text
throttle_saturated
gimbal_saturated
throttle_rate_limited
gimbal_rate_limited
degraded
```

**Decision:** Feature 05 may expose these as an immutable `ActuatorUpdate` result without writing telemetry itself.

Recommended:

```python
@dataclass(frozen=True)
class ActuatorUpdate:
    state: ActuatorState
    throttle_target: float
    gimbal_target: float
    throttle_saturated: bool
    gimbal_saturated: bool
    throttle_rate_limited: bool
    gimbal_rate_limited: bool
```

The exact fields may be kept smaller if telemetry does not require them.

---

## Why it matters

The actuator layer creates the final boundary between software commands and simulated physics.

It proves the project understands that:

```text
command != physical response
```

This makes:

- controller tuning more meaningful;
- degraded-actuator faults real;
- telemetry more diagnostic;
- subsystem boundaries clearer;
- integration testing stronger.

---

## Skill it demonstrates

A successful actuator model demonstrates:

- stateful component design;
- discrete-time dynamic modeling;
- physical command limits;
- deterministic lag modeling;
- multi-rate system reasoning;
- clean controller/plant interfaces;
- fault-ready architecture;
- configuration validation;
- unit testing;
- closed-loop integration testing;
- explicit state ownership.

---

## Priority

**P0/P1 — Core closed-loop prerequisite**

The complete physical loop is not real until:

```text
Controller
 -> Actuator
 -> Dynamics
```

is implemented.

Feature 05 should be completed after Feature 04 and before full nominal mission tuning is finalized.

---

## Complexity

**Medium**

The mathematical model is intentionally simple.

The main complexity is in:

- clear semantics;
- update ordering;
- saturation behavior;
- time constants;
- rate-limit interaction;
- degraded-runtime modifiers;
- controller integration.

---

# 2. User / Demo Flow

## Happy path

1. Controller generates:

```text
desired throttle
desired gimbal
```

2. Simulation Engine passes the command to the actuator subsystem.
3. Actuator subsystem validates the command and `dt`.
4. Desired values are saturated to effective physical bounds.
5. First-order lag moves actual state toward each target.
6. Optional rate limits constrain per-tick change.
7. Final physical bounds are enforced.
8. A new immutable `ActuatorState` is produced.
9. That exact state is held constant during the RK4 step.
10. Feature 01 dynamics uses:
   - actual throttle;
   - actual gimbal.
11. On the next tick, actuator state evolves again toward the current desired command.

---

## First-time path

### Stage A — Instantaneous zero-lag model

Configure:

```text
tau = 0
no rate limit
```

Verify:

```text
actual == saturated desired
```

This proves command boundary and saturation first.

### Stage B — Throttle lag

Start:

```text
actual = 0
desired = 1
tau > 0
```

Verify:

- actual increases monotonically;
- it remains below target after one finite step;
- it approaches target over repeated updates.

### Stage C — Gimbal lag

Same idea with positive/negative gimbal commands.

### Stage D — Saturation

Command beyond physical limits.

Verify:

```text
target is clipped
actual never exceeds physical bound
```

### Stage E — Optional rate limit

Configure a small maximum rate.

Verify per-step change is no greater than:

```text
max_rate * dt
```

### Stage F — Controller integration

Send a controller command sequence.

Verify:

```text
requested command
!=
actual actuator output
```

during transients.

### Stage G — Dynamics integration

Feed `ActuatorState` into Feature 01.

Verify actual physical trajectory follows applied—not requested—actuation.

### Stage H — Degradation primitive

Increase effective lag multiplier.

Verify slower response for identical command input.

Do not add fault timing yet.

---

## Empty state

There is no meaningful actuator update without:

- valid `ControlCommand`;
- valid actuator config;
- valid current actuator state;
- positive finite `dt`.

Missing state/config is a programming/configuration error.

---

## Error path

### Non-finite requested command

Examples:

```text
NaN throttle
Inf gimbal
```

Expected:

- fail safely;
- do not update actuator state.

### Invalid physical bounds

Examples:

```text
min_throttle > max_throttle
negative max throttle
gimbal limit < 0
```

Expected:

- fail before simulation begins.

### Invalid time constant

```text
tau < 0
NaN
Inf
```

Expected:

- configuration error.

### Invalid rate limit

```text
max_rate <= 0
```

if rate limiting is enabled.

Expected:

- configuration error.

### Invalid degradation multiplier

Examples:

```text
lag multiplier <= 0
authority scale < 0
rate scale < 0
```

Expected:

- reject.

### Non-finite current actuator state

Expected:

- runtime error;
- do not propagate invalid state into dynamics.

---

## Demo path for a reviewer

### Demo A — Step response

Command throttle from:

```text
0 -> 1
```

Plot or show test data:

```text
requested throttle
actual throttle
```

Actual response rises gradually.

Explain:

> "The controller command is not applied instantly. The actuator has its own state and response dynamics."

### Demo B — Gimbal saturation

Request a gimbal command beyond the physical limit.

Show:

```text
requested > physical target
actual never exceeds bound
```

### Demo C — Nominal vs degraded response

Feed the same command history into:

```text
nominal actuator
degraded actuator
```

Show the degraded actuator responding more slowly.

### Demo D — Closed-loop consequence

Run the same controller with:

```text
nominal actuator
sluggish actuator
```

Show that the applied trajectory differs even though the controller logic is identical.

This is the strongest fault/validation story.

---

# 3. UX / UI Requirements

## Screens/pages

**[Decision]** No dedicated actuator UI.

This feature is headless.

Later diagnostic visualization should compare:

```text
requested throttle vs actual throttle
requested gimbal vs actual gimbal
```

This comparison is explicitly valuable to the project reviewer.

---

## Components

Recommended software components:

```text
ActuatorState
ActuatorConfig
ThrottleActuatorConfig
GimbalActuatorConfig
ActuatorRuntimeModifiers
ActuatorModel / ActuatorSuite
ActuatorUpdate
```

Do not create a complex plugin architecture.

---

## Forms/inputs

No GUI form.

Configuration should support:

### Throttle

```text
min_throttle
max_throttle
response_time_constant_s
optional max_rate_per_s
```

### Gimbal

```text
max_angle_rad or max_angle_deg at config boundary
response_time_constant_s
optional max_rate_rad_s
```

### Runtime degradation defaults

Nominally:

```text
lag_multiplier = 1.0
authority_scale = 1.0
rate_scale = 1.0
```

These are runtime behavior hooks, not scenario activation rules.

---

## Buttons/actions

None.

---

## Validation messages

Examples:

```text
Invalid throttle actuator config: min_throttle=1.0 exceeds max_throttle=0.0.
Invalid gimbal actuator config: max_angle must be finite and >= 0.
Invalid throttle actuator config: response_time_constant_s must be >= 0.
Invalid actuator update: dt must be finite and > 0.
Invalid actuator command: throttle must be finite.
Invalid actuator state: gimbal_angle=nan.
Invalid actuator degradation: lag_multiplier must be > 0.
```

---

## Empty states

Not applicable visually.

Initial actuator state defaults to neutral zero state unless explicitly configured.

---

## Loading states

None.

Actuator updates are small synchronous calculations.

---

## Error states

Recommended minimal categories:

```text
ActuatorConfigError
ActuatorRuntimeError
```

Do not build a large hierarchy.

---

## Responsive behavior

Not relevant.

---

# 4. Data Requirements

## Entities involved

### `ControlCommand`

Defined by Feature 04:

```python
@dataclass(frozen=True)
class ControlCommand:
    throttle: float
    attitude_command: float
```

Meaning:

```text
desired software command
```

---

### `ActuatorState`

Recommended:

```python
@dataclass(frozen=True)
class ActuatorState:
    throttle: float
    gimbal_angle: float
```

Meaning:

```text
actual physically applied actuator state
```

---

### `ThrottleActuatorConfig`

Recommended:

```python
@dataclass(frozen=True)
class ThrottleActuatorConfig:
    min_value: float
    max_value: float
    time_constant: float
    max_rate: float | None
```

---

### `GimbalActuatorConfig`

Recommended:

```python
@dataclass(frozen=True)
class GimbalActuatorConfig:
    max_angle: float
    time_constant: float
    max_rate: float | None
```

Use radians internally.

---

### `ActuatorConfig`

```python
@dataclass(frozen=True)
class ActuatorConfig:
    throttle: ThrottleActuatorConfig
    gimbal: GimbalActuatorConfig
```

---

### `ActuatorRuntimeModifiers`

Recommended:

```python
@dataclass(frozen=True)
class ActuatorRuntimeModifiers:
    throttle_lag_multiplier: float = 1.0
    gimbal_lag_multiplier: float = 1.0

    throttle_authority_scale: float = 1.0
    gimbal_authority_scale: float = 1.0

    throttle_rate_scale: float = 1.0
    gimbal_rate_scale: float = 1.0
```

**Decision:** This record is optional if a smaller target-local modifier API is clearer.

Do not over-generalize.

---

### `ActuatorUpdate`

Potential:

```python
@dataclass(frozen=True)
class ActuatorUpdate:
    state: ActuatorState

    requested_throttle: float
    target_throttle: float

    requested_gimbal: float
    target_gimbal: float

    throttle_saturated: bool
    gimbal_saturated: bool

    throttle_rate_limited: bool
    gimbal_rate_limited: bool
```

This is useful later for telemetry without letting telemetry own actuator logic.

---

## Fields and units

| Field | Unit | Constraint |
|---|---|---|
| requested throttle | normalized | finite |
| applied throttle | normalized | within effective physical bounds |
| requested gimbal | rad | finite |
| applied gimbal | rad | within effective physical bounds |
| throttle time constant | s | finite, `>= 0` |
| gimbal time constant | s | finite, `>= 0` |
| throttle max rate | normalized/s | `> 0` if enabled |
| gimbal max rate | rad/s | `> 0` if enabled |
| lag multiplier | unitless | finite, `> 0` |
| authority scale | unitless | finite, typically `[0,1]` for degradation |
| rate scale | unitless | finite, `>= 0` |

---

## Relationships

```text
ControlCommand
      |
      v
Actuator Model
      |
      +--> physical saturation
      +--> lag
      +--> optional rate limit
      +--> runtime degradation modifiers
      |
      v
ActuatorState
      |
      v
2D Flight Dynamics
```

---

## Example seed/config data

These are development examples, not real launch-vehicle actuator specifications.

```toml
[actuators.throttle]
min = 0.0
max = 1.0
response_time_constant_s = 0.20
# max_rate_per_s = 2.0

[actuators.gimbal]
max_angle_deg = 8.0
response_time_constant_s = 0.10
max_rate_deg_s = 30.0
```

**[Open Question]** Final nominal time constants, gimbal limit, and rate limits must be tuned with the controller and dynamics.

### Example degraded runtime modifier

```toml
# This structure belongs conceptually to the later fault system,
# shown here only to document the actuator hook.
response_lag_multiplier = 3.0
```

---

## Local persistence needs

**[Decision]** None.

Actuator state is in-memory runtime state.

The actuator module does not:

- write CSV;
- write JSON;
- create run folders;
- generate plots;
- access a database.

Later telemetry records command and actual actuator output.

---

# 5. Logic Requirements

## Rule 1 — Actuator receives desired command, not sensor data

The actuator layer does not know why the controller produced a command.

---

## Rule 2 — Actuator produces actual applied state

Dynamics consumes `ActuatorState`, not `ControlCommand`.

---

## Rule 3 — Physical bounds are authoritative

Even if the controller already limits output, the actuator applies its own configured bounds.

---

## Rule 4 — Saturation is explicit

Do not silently rely on controller limits.

Expose saturation state where useful.

---

## Rule 5 — Lag state is actuator-owned

The current actual throttle/gimbal state belongs to the actuator component.

---

## Rule 6 — Actuator updates once per simulation tick

Not once per controller update only.

Not once per RK4 stage.

---

## Rule 7 — Applied state is held constant across RK4 stages

Feature 02's fixed-step contract must be preserved.

---

## Rule 8 — Time response uses simulation `dt`

No wall-clock timing.

No `sleep()`.

---

## Rule 9 — First-order lag uses deterministic update

Preferred:

```text
alpha = 1 - exp(-dt/tau)
next = current + alpha*(target-current)
```

for `tau > 0`.

---

## Rule 10 — `tau == 0` means instantaneous response

```text
next = target
```

after saturation/rate semantics as documented.

---

## Rule 11 — No overshoot from lag alone

For a constant target and no additional rate behavior, a first-order step should move monotonically toward target.

---

## Rule 12 — Optional rate limit constrains per-tick state change

```text
abs(next-current) <= max_rate*dt
```

when enabled.

---

## Rule 13 — Final output is re-clamped to hard bounds

Floating-point arithmetic must never permit the actuator to exceed physical limits.

---

## Rule 14 — Throttle state must stay finite

No NaN/Inf.

---

## Rule 15 — Gimbal state must stay finite

No NaN/Inf.

---

## Rule 16 — Controller command is not mutated

Input `ControlCommand` is read-only.

---

## Rule 17 — Actuator update is deterministic

No RNG belongs in nominal actuator behavior.

---

## Rule 18 — Degradation hooks change real actuator behavior

A lag degradation must actually alter the update response.

Do not merely set:

```text
degraded = true
```

without changing behavior.

---

## Rule 19 — Fault timing is external

No:

```python
if sim_time >= 20:
    degraded = True
```

inside the actuator model.

Feature 07 decides activation.

---

## Rule 20 — No scenario-name branching

No:

```python
if scenario_name == "degraded_actuator":
```

---

## Rule 21 — Actuator does not compute control error

No PID logic.

---

## Rule 22 — Actuator does not read measurements

No sensor dependency.

---

## Rule 23 — Actuator does not own mission mode

Mission state may indirectly affect controller commands, but the actuator does not select behavior by mission mode unless a later explicit physical requirement is documented.

---

## Rule 24 — Physical configuration validation happens before run where possible

Bad time constants/bounds should fail early.

---

## Rule 25 — Runtime modifier validation happens when applied

Invalid degradation must not corrupt state.

---

## First-order helper pseudocode

```python
def first_order_step(
    current: float,
    target: float,
    *,
    tau: float,
    dt: float,
) -> float:
    if tau == 0.0:
        return target

    alpha = 1.0 - math.exp(-dt / tau)

    return current + alpha * (target - current)
```

---

## Rate-limit helper pseudocode

```python
def apply_rate_limit(
    current: float,
    candidate: float,
    *,
    max_rate: float | None,
    dt: float,
) -> tuple[float, bool]:

    if max_rate is None:
        return candidate, False

    max_delta = max_rate * dt
    delta = candidate - current

    limited_delta = clamp(
        delta,
        -max_delta,
        max_delta,
    )

    return (
        current + limited_delta,
        limited_delta != delta,
    )
```

Use an appropriate tolerance for floating comparison rather than brittle exact comparison if needed.

---

## Throttle update pseudocode

```python
def update_throttle(
    current: float,
    requested: float,
    config: ThrottleActuatorConfig,
    modifiers: ThrottleModifiers,
    dt: float,
) -> ChannelUpdate:

    min_value = config.min_value

    max_value = (
        config.max_value
        * modifiers.authority_scale
    )

    tau = (
        config.time_constant
        * modifiers.lag_multiplier
    )

    target = clamp(
        requested,
        min_value,
        max_value,
    )

    candidate = first_order_step(
        current,
        target,
        tau=tau,
        dt=dt,
    )

    effective_rate = resolve_rate(
        config.max_rate,
        modifiers.rate_scale,
    )

    next_value, rate_limited = apply_rate_limit(
        current,
        candidate,
        max_rate=effective_rate,
        dt=dt,
    )

    next_value = clamp(
        next_value,
        min_value,
        max_value,
    )

    return ...
```

---

## Gimbal update pseudocode

```python
def update_gimbal(
    current: float,
    requested: float,
    config: GimbalActuatorConfig,
    modifiers: GimbalModifiers,
    dt: float,
) -> ChannelUpdate:

    limit = (
        config.max_angle
        * modifiers.authority_scale
    )

    target = clamp(
        requested,
        -limit,
        +limit,
    )

    tau = (
        config.time_constant
        * modifiers.lag_multiplier
    )

    candidate = first_order_step(
        current,
        target,
        tau=tau,
        dt=dt,
    )

    effective_rate = resolve_rate(
        config.max_rate,
        modifiers.rate_scale,
    )

    next_value, rate_limited = apply_rate_limit(
        current,
        candidate,
        max_rate=effective_rate,
        dt=dt,
    )

    next_value = clamp(
        next_value,
        -limit,
        +limit,
    )

    return ...
```

---

## Full actuator-suite pseudocode

```python
def update(
    command: ControlCommand,
    dt: float,
) -> ActuatorUpdate:

    validate_command(command)
    validate_dt(dt)

    throttle_update = ...
    gimbal_update = ...

    new_state = ActuatorState(
        throttle=throttle_update.actual,
        gimbal_angle=gimbal_update.actual,
    )

    self._state = new_state

    return ActuatorUpdate(
        state=new_state,
        ...
    )
```

State is only committed after both channel updates succeed.

---

## Edge cases

### Desired throttle below physical minimum

Target saturates to minimum.

---

### Desired throttle above physical maximum

Target saturates to maximum.

---

### Desired gimbal beyond positive limit

Target saturates to positive limit.

---

### Desired gimbal beyond negative limit

Target saturates to negative limit.

---

### Current state exactly equals target

No change.

---

### `tau = 0`

Instant target tracking.

---

### Very small positive `tau`

Response becomes nearly instantaneous but remains finite/stable.

---

### Very large `tau`

Slow response.

---

### Command reverses direction

Actuator should smoothly move toward new target.

Optional rate limit still applies.

---

### Command changes every controller update

Actuator follows latest held target each simulation tick.

---

### Rate limit disabled

Only lag + hard saturation apply.

---

### Rate limit smaller than lag-induced change

Rate limit dominates.

---

### Authority scale equals zero

The targeted actuator has zero usable authority.

For throttle:

```text
effective max throttle = 0
```

For symmetric gimbal:

```text
effective angle limit = 0
```

This is mathematically valid but likely a severe fault.

---

### Lag multiplier greater than one

Response becomes slower.

---

### Lag multiplier below one

Response becomes faster.

For degradation scenarios, normally use values `>= 1`.

---

### Degradation activates while actuator is moving

New effective parameters apply from that actuator update onward.

General activation timing comes from Feature 07.

---

### Degradation removed

Nominal parameters resume on the next update.

No state teleportation occurs; actual state continues from its current value.

---

### Requested command is NaN/Inf

Reject before state change.

---

### Current actuator state is outside physical bounds

Treat as runtime invariant error rather than silently normalize a materially corrupted state.

A tiny floating overshoot may be clamped if explicitly tolerated.

---

# 6. Acceptance Criteria

## AC-01 — Actuator state is separate from control command

**Given** the public data model  
**When** controller and actuator interfaces are inspected  
**Then** `ControlCommand` represents desired software output and `ActuatorState` represents actual applied physical output.

---

## AC-02 — Dynamics consumes actuator state

**Given** the controller-actuator-dynamics integration path  
**When** truth-state advancement occurs  
**Then** Feature 01 receives actual actuator state rather than raw controller command.

---

## AC-03 — Initial state defaults to neutral

**Given** no custom initial actuator state  
**When** the actuator subsystem is initialized  
**Then** actual throttle is `0.0` and actual gimbal is `0.0 rad`.

---

## AC-04 — Throttle requested inside bounds is accepted as target

**Given** a finite throttle request inside physical limits  
**When** actuator saturation is applied  
**Then** target throttle equals the request.

---

## AC-05 — High throttle request saturates

**Given** requested throttle above effective maximum  
**When** actuator target is resolved  
**Then** target equals effective maximum and saturation status is true.

---

## AC-06 — Low throttle request saturates

**Given** requested throttle below effective minimum  
**When** target is resolved  
**Then** target equals effective minimum.

---

## AC-07 — Positive gimbal command saturates at physical limit

**Given** requested gimbal above effective positive limit  
**When** target is resolved  
**Then** target equals positive limit.

---

## AC-08 — Negative gimbal command saturates symmetrically

**Given** requested gimbal below negative limit  
**When** target is resolved  
**Then** target equals negative limit.

---

## AC-09 — Zero time constant tracks target immediately

**Given** `tau = 0` and no restrictive rate limit  
**When** actuator updates  
**Then** actual output becomes the saturated target in one update.

---

## AC-10 — Positive time constant creates lag

**Given** current output differs from target and `tau > 0`  
**When** one update executes  
**Then** actual output moves toward target but does not jump directly to target.

---

## AC-11 — First-order lag moves in correct direction

**Given** target is greater than current output  
**When** lag update executes  
**Then** next output is greater than current output.

---

## AC-12 — First-order lag reverses correctly

**Given** target is below current output  
**When** lag update executes  
**Then** next output is below current output.

---

## AC-13 — Constant target converges toward target

**Given** repeated updates with constant target and valid `tau > 0`  
**When** many ticks execute  
**Then** actual state approaches the target monotonically within numerical tolerance.

---

## AC-14 — Lag alone does not overshoot constant target

**Given** valid first-order lag and constant target  
**When** updates execute  
**Then** actual state remains between its previous value and target.

---

## AC-15 — Update uses simulation timestep

**Given** a fixed current state, target, and tau  
**When** different valid `dt` values are supplied  
**Then** response magnitude changes according to the discrete first-order equation.

---

## AC-16 — Actuator uses no wall-clock timing

**Given** identical commands/configuration and simulation ticks  
**When** execution speed changes  
**Then** actuator trajectory is unchanged.

---

## AC-17 — Optional rate limit bounds state change

**Given** enabled max rate `r`  
**When** one update of length `dt` executes  
**Then** `abs(next-current) <= r * dt`.

---

## AC-18 — Disabled rate limit does not constrain lag candidate

**Given** `max_rate is None`  
**When** update executes  
**Then** the lag candidate is not further limited by rate logic.

---

## AC-19 — Final throttle never exceeds physical bounds

**Given** any finite valid command sequence  
**When** actuator updates execute  
**Then** actual throttle always remains within effective physical bounds.

---

## AC-20 — Final gimbal never exceeds physical bounds

**Given** any finite valid command sequence  
**When** updates execute  
**Then** actual gimbal remains within effective limits.

---

## AC-21 — Actuator updates once per simulation tick

**Given** the engine's per-tick orchestration  
**When** one simulation tick executes  
**Then** actuator state is advanced exactly once.

---

## AC-22 — Actuator is not updated four times by RK4

**Given** one simulation tick with four RK4 derivative stages  
**When** the engine advances truth state  
**Then** actuator state is unchanged across k1/k2/k3/k4 after its once-per-tick update.

---

## AC-23 — Held controller command still allows actuator evolution

**Given** controller command is unchanged across multiple simulation ticks  
**When** actuator lag is nonzero  
**Then** actual state continues moving toward the held target every tick.

---

## AC-24 — Controller command input is not mutated

**Given** an immutable `ControlCommand`  
**When** actuator update completes  
**Then** the input command remains unchanged.

---

## AC-25 — Failed actuator update does not partially commit state

**Given** one channel update fails validation/runtime checks  
**When** the actuator-suite update aborts  
**Then** the previously committed full actuator state remains unchanged.

---

## AC-26 — Non-finite command is rejected

**Given** requested throttle or gimbal is NaN/Inf  
**When** validation runs  
**Then** an actuator runtime/input error is raised and state is not committed.

---

## AC-27 — Non-finite current actuator state is rejected

**Given** current actual state contains NaN/Inf  
**When** update begins  
**Then** execution fails safely.

---

## AC-28 — Invalid time constant is rejected

**Given** negative/non-finite time constant  
**When** configuration is validated  
**Then** setup fails before normal simulation.

---

## AC-29 — Invalid `dt` is rejected

**Given** `dt <= 0` or non-finite  
**When** actuator update is attempted  
**Then** update fails.

---

## AC-30 — Invalid physical bounds are rejected

**Given** contradictory throttle or gimbal limits  
**When** configuration is validated  
**Then** simulation setup fails.

---

## AC-31 — Lag degradation changes actual response

**Given** two otherwise identical actuator models and command sequences where one uses a lag multiplier greater than one  
**When** both update  
**Then** the degraded actuator responds more slowly.

---

## AC-32 — Lag degradation does not change requested command

**Given** degraded actuator response  
**When** controller output is inspected  
**Then** the requested `ControlCommand` remains unchanged by the actuator fault behavior.

---

## AC-33 — Authority degradation reduces physical target capability

**Given** authority scale below one  
**When** command exceeds degraded physical capability  
**Then** actuator target saturates to the reduced effective limit.

---

## AC-34 — Rate degradation reduces maximum state-change rate

**Given** an enabled nominal rate limit and rate scale below one  
**When** update occurs  
**Then** permitted change is reduced proportionally.

---

## AC-35 — Degradation hooks contain no activation schedule

**Given** actuator model source  
**When** inspected  
**Then** it does not decide activation based on scenario time or mission state unless explicitly supplied as runtime modifiers by another subsystem.

---

## AC-36 — No scenario-name branches exist

**Given** actuator source  
**When** inspected  
**Then** no behavior depends on strings such as `degraded_actuator`.

---

## AC-37 — Actuator contains no PID logic

**Given** actuator package  
**When** inspected  
**Then** it does not compute tracking/control error, PID terms, or setpoints.

---

## AC-38 — Actuator contains no sensor dependency

**Given** actuator package  
**When** inspected  
**Then** it does not read `MeasurementSnapshot`.

---

## AC-39 — Actuator is deterministic

**Given** identical initial state, command sequence, `dt`, config, and runtime modifiers  
**When** two actuator instances execute  
**Then** their applied-state sequences match.

---

## AC-40 — Requested vs actual values can differ during transient

**Given** nonzero lag and a step command  
**When** first update executes  
**Then** requested and actual actuation are different unless already at target.

---

## AC-41 — Requested vs actual converge under constant healthy command

**Given** stable constant command and nominal actuator  
**When** sufficient simulation ticks pass  
**Then** actual state converges toward the saturated requested target.

---

## AC-42 — Throttle actuator affects dynamics through actual state

**Given** controller requests full throttle but lagged actuator is still below full output  
**When** dynamics is advanced  
**Then** thrust uses the lagged actual throttle, not the full requested value.

---

## AC-43 — Gimbal actuator affects dynamics through actual state

**Given** controller requests a gimbal step and actual gimbal lags  
**When** dynamics is advanced  
**Then** thrust direction/torque use actual gimbal angle.

---

## AC-44 — Neutral command drives actuator toward neutral

**Given** nonzero current actuator state and desired neutral command  
**When** repeated updates execute  
**Then** actual state approaches neutral according to lag/rate constraints.

---

## AC-45 — Removing degradation does not teleport state

**Given** a degraded actuator with non-nominal current state  
**When** runtime modifiers return to nominal  
**Then** actual state continues from its current value and evolves under nominal parameters.

---

## AC-46 — Actuator performs no persistence

**Given** isolated actuator tests  
**When** update sequences execute  
**Then** no CSV, JSON, database, or plot output is produced by actuator code.

---

## AC-47 — Actuator works headlessly and locally

**Given** a clean Python test environment  
**When** actuator tests run  
**Then** no browser, cloud service, external hardware, or network is required.

---

## AC-48 — Closed-loop nominal controller remains stable with actuator model

**Given** Features 01–04 and nominal actuator configuration  
**When** pitch and vertical-velocity closed-loop integration tests run  
**Then** actuator lag does not cause uncontrolled divergence under the documented tuned configuration.

---

## AC-49 — Degraded actuator visibly changes closed-loop behavior

**Given** identical controller/sensor/dynamics conditions except for actuator lag degradation  
**When** both simulations run  
**Then** actual command trajectory and vehicle response differ measurably.

---

## AC-50 — Cross-feature degraded-actuator scenario gate

**Given** Feature 07 scenario/fault activation and later validation infrastructure  
**When** the `degraded_actuator` scenario runs  
**Then** the fault modifies the real actuator response through Feature 05 and the resulting mission outcome matches the scenario's documented expectation.

---

# 7. Test Plan

## Unit tests

Primary file:

```text
tests/unit/test_actuators.py
```

Recommended groups follow.

---

## Saturation tests

```text
test_throttle_inside_bounds_not_saturated
test_throttle_above_max_saturates
test_throttle_below_min_saturates
test_gimbal_inside_bounds_not_saturated
test_gimbal_above_positive_limit_saturates
test_gimbal_below_negative_limit_saturates
```

---

## First-order lag tests

```text
test_zero_tau_is_instantaneous
test_positive_tau_moves_toward_target
test_lag_does_not_overshoot
test_lag_converges_over_repeated_updates
test_larger_tau_is_slower
test_response_reverses_when_target_reverses
test_at_target_remains_at_target
```

For known first-order response, compare to:

```text
x(t) =
target
+ (x0 - target) * exp(-t/tau)
```

at tick-aligned times within floating tolerance.

This is a strong unit test because the simplified actuator model has a known analytical response.

---

## Rate-limit tests

```text
test_rate_limit_caps_positive_change
test_rate_limit_caps_negative_change
test_rate_limit_disabled
test_rate_limit_combines_with_lag
test_rate_limit_never_breaks_hard_bounds
```

If explicit rate limits are not enabled in the final MVP configuration, keep helper tests if the feature remains implemented.

---

## State/validation tests

```text
test_default_initial_state_zero
test_non_finite_command_rejected
test_non_finite_state_rejected
test_invalid_dt_rejected
test_negative_tau_rejected
test_invalid_throttle_bounds_rejected
test_negative_gimbal_limit_rejected
test_invalid_rate_limit_rejected
test_failed_update_does_not_commit_partial_state
test_command_not_mutated
```

---

## Degradation-hook tests

```text
test_lag_multiplier_slows_response
test_authority_scale_reduces_throttle_limit
test_authority_scale_reduces_gimbal_limit
test_rate_scale_reduces_slew_rate
test_invalid_lag_multiplier_rejected
test_invalid_authority_scale_rejected
test_invalid_rate_scale_rejected
test_removing_degradation_preserves_current_state
```

---

## Determinism tests

```text
test_identical_command_sequences_match
test_no_rng_dependency
```

---

## Integration tests with Feature 04

Recommended:

```text
tests/integration/test_controller_actuator.py
```

### Command-to-applied lag

Controller produces a command step.

Assert:

```text
requested != actual initially
actual moves toward requested
```

### Controller holds command, actuator continues

Controller updates every N ticks.

Assert actuator continues evolving on intermediate engine ticks.

### Controller output limit vs actuator limit

Configure actuator physical limit stricter than controller software limit.

Assert actuator physical saturation wins.

---

## Integration tests with Features 01–02

Recommended:

```text
tests/integration/test_actuator_dynamics.py
```

### Throttle lag affects acceleration

Compare:

```text
instantaneous actuator
lagged actuator
```

for same desired throttle step.

Assert early acceleration differs.

### Gimbal lag affects pitch response

Compare actual gimbal and resulting angular response.

Assert dynamics uses actual gimbal.

---

## Integration test with complete closed loop

Once controller tuning is stable:

```text
tests/integration/test_closed_loop.py
```

Assert:

- pitch stabilization remains bounded;
- vertical control remains bounded;
- actual actuator values stay finite;
- physical limits are never exceeded.

---

## Fault integration tests deferred to Feature 07

Once the Fault Injection System exists:

- activate degraded response at exact simulation tick;
- confirm actuator parameter modifier changes;
- confirm actual response changes on that tick;
- confirm fault event is logged elsewhere;
- confirm removing fault returns nominal parameters without state teleportation.

---

## Telemetry tests deferred to Feature 09

Later telemetry should record:

```text
command_throttle
command_attitude
actual_throttle
actual_attitude
```

and optional saturation/degraded flags.

Feature 05 only exposes data.

---

## Manual QA checklist

- [ ] `ControlCommand` and `ActuatorState` remain distinct types/concepts.
- [ ] Dynamics receives actual actuation.
- [ ] Throttle has hard physical bounds.
- [ ] Gimbal has hard physical bounds.
- [ ] Response lag is explicit.
- [ ] Lag uses simulation `dt`.
- [ ] No wall-clock timing is used.
- [ ] No `sleep()` exists.
- [ ] Zero time constant is handled safely.
- [ ] First-order response does not overshoot.
- [ ] Optional rate limiting is deterministic.
- [ ] Actuator updates exactly once per simulation tick.
- [ ] Actuator does not update during each RK4 stage.
- [ ] State is not partially committed on error.
- [ ] Non-finite input fails clearly.
- [ ] Controller command is not mutated.
- [ ] No PID/controller logic exists in actuator code.
- [ ] No sensor dependency exists.
- [ ] No mission-transition logic exists.
- [ ] No scenario-name branch exists.
- [ ] Degradation hooks change real actuator behavior.
- [ ] Degradation activation timing is not implemented here.
- [ ] Requested-vs-actual data can be exposed later to telemetry.
- [ ] Unit tests pass.
- [ ] Controller-actuator integration tests pass.
- [ ] Actuator-dynamics integration tests pass.

---

## Demo verification checklist

- [ ] Step command shows requested vs actual throttle separation.
- [ ] Step command shows requested vs actual gimbal separation.
- [ ] Throttle actual state approaches target smoothly.
- [ ] Gimbal actual state approaches target smoothly.
- [ ] Saturation is visible under excessive request.
- [ ] Optional rate limit is visible if enabled.
- [ ] Same command sequence reproduces same actuator trajectory.
- [ ] Degraded lag produces visibly slower response.
- [ ] Closed-loop vehicle response changes under degraded actuation.
- [ ] Reviewer can explain why controller command and actuator state are separate.
- [ ] Actuator model works entirely locally/headlessly.

---

# 8. Portfolio Value

## How this feature helps the project stand out

The actuator model is a small feature with strong systems value because it demonstrates that the software architecture respects a real boundary:

```text
desired output
!=
physical response
```

This is especially valuable for a hardware-adjacent software portfolio.

A strong explanation is:

> "My controller produces a desired throttle and gimbal command, but the physical simulator never consumes that command directly. A separate actuator model applies physical bounds and response lag, then the dynamics uses the actual actuator state."

That makes the project more credible than a simplified PID demo.

---

## What to mention in README

Recommended wording:

> **Actuator dynamics:** Controller commands do not reach the vehicle instantly. AstraLoop models physical throttle and gimbal bounds plus configurable first-order response lag, so telemetry can compare requested commands against actual applied actuation.

Useful bullets:

- controller command vs applied state;
- explicit physical saturation;
- deterministic first-order lag;
- optional slew limits;
- actuator state updated every simulation tick;
- applied state held constant across RK4 stages;
- degraded-response hooks for fault testing.

---

## What to mention in interviews

### Why separate controller commands from actuator state?

> "The controller describes what software wants. The actuator model represents what the physical system can actually do. Keeping those separate lets me model limits, lag, and degradation without contaminating the controller."

### How did you model lag?

> "I used a first-order response model and an exact discrete exponential update for a constant target over one simulation tick. It is simple, deterministic, and analytically testable."

### Why not update actuator state inside RK4?

> "The actuator is a discrete simulation component in this architecture. It updates once per simulation tick, then the resulting applied state is held constant through the RK4 sub-stages. Otherwise I would accidentally advance the actuator four times per tick."

### What's the difference between saturation and lag?

> "Saturation limits where the actuator can go. Lag determines how quickly it gets there. A command can be inside the limit and still take time to reach."

### Why keep controller and actuator limits separately?

> "The controller limit is a software constraint and anti-windup mechanism. The actuator limit is the physical authority. A fault can reduce physical authority without changing what the controller requests."

### How is the degraded actuator fault implemented?

> "The actuator exposes target-local modifiers, such as a larger lag time constant. The fault manager decides when to activate them. That changes the actual subsystem behavior instead of just printing a fault message."

### How did you test the model?

> "The first-order response has a known analytical solution, so I can directly test the discrete actuator trajectory. I also test saturation, rate limits, deterministic behavior, and controller-to-dynamics integration."

---

# 9. Implementation Notes for Codex

## Likely files/folders

Primary:

```text
src/astraloop/model/commands.py

src/astraloop/actuators/
├── __init__.py
└── models.py

src/astraloop/config/
├── schema.py
└── validation.py

tests/unit/
└── test_actuators.py

tests/integration/
├── test_controller_actuator.py
└── test_actuator_dynamics.py
```

If `models.py` becomes too large, split only after real need:

```text
actuators/
├── throttle.py
├── gimbal.py
└── suite.py
```

**Decision:** Start with one clear `models.py` rather than over-structuring immediately.

---

## Suggested responsibilities

### `model/commands.py`

Own shared data records:

```text
ControlCommand
ActuatorState
ActuatorUpdate if shared broadly
```

---

### `actuators/models.py`

Own:

- first-order update helper;
- optional rate-limit helper;
- throttle model;
- gimbal model;
- combined actuator model/suite;
- actuator-owned state;
- runtime modifier application.

No controller logic.

---

## Build order

### Step 1 — Lock command/state semantics

Confirm:

```text
ControlCommand.throttle = desired normalized throttle
ControlCommand.attitude_command = desired gimbal command [rad]

ActuatorState.throttle = actual normalized throttle
ActuatorState.gimbal_angle = actual gimbal angle [rad]
```

Do this before coding response equations.

---

### Step 2 — Implement actuator config validation

Validate:

- bounds;
- time constants;
- optional rate limits;
- finite values.

Write tests first.

---

### Step 3 — Implement saturation-only instantaneous behavior

Use:

```text
tau = 0
```

Prove:

```text
desired -> saturated target -> actual
```

---

### Step 4 — Implement first-order lag helper

Test against analytical solution.

Do not connect controller yet.

---

### Step 5 — Add throttle actuator

Test:

- step up;
- step down;
- saturation;
- convergence.

---

### Step 6 — Add gimbal actuator

Test positive/negative symmetry.

---

### Step 7 — Add optional rate limiter only if retained

Test separately before combining.

---

### Step 8 — Implement combined atomic actuator update

Both channels calculate first.

Only commit new `ActuatorState` after successful full update.

---

### Step 9 — Integrate with Simulation Engine

Place actuator update at:

```text
after controller
before RK4
```

exactly as architecture requires.

---

### Step 10 — Connect actual state to Feature 01 dynamics

Remove any temporary path where dynamics receives `ControlCommand` directly.

---

### Step 11 — Add controller-actuator integration tests

Verify requested vs actual separation.

---

### Step 12 — Add degraded-runtime hooks

Implement only target-local modifiers.

Do not implement general fault scheduling.

---

### Step 13 — Re-tune nominal controller if necessary

Feature 04 may have been initially tuned with a temporary instantaneous actuator.

Once real lag is connected, adjust controller gains/base throttle only as needed.

Do not weaken actuator behavior merely to preserve old controller tuning.

---

## Risks

### Risk 1 — Controller command accidentally bypasses actuator model

This destroys the architecture.

**Mitigation:** dynamics accepts `ActuatorState`, not raw command.

---

### Risk 2 — Actuator is updated multiple times per RK4 step

This makes lag artificially fast.

**Mitigation:** one actuator update per simulation tick.

---

### Risk 3 — First-order Euler lag becomes unstable for large `dt/tau`

**Mitigation:** use exact exponential discrete response.

---

### Risk 4 — Too many actuator realism parameters

Potential scope creep:

- deadband;
- backlash;
- hysteresis;
- nonlinear servo curves;
- engine ignition delay;
- pump dynamics;
- electrical voltage/current;
- thermal limits.

**Mitigation:** saturation + lag, optional rate limit.

---

### Risk 5 — Rate limit and lag interactions become confusing

**Mitigation:** document fixed operation order and test each independently.

---

### Risk 6 — Controller tuning breaks after lag is added

Expected to some degree.

**Mitigation:** tune the real closed-loop architecture, not the temporary instantaneous model.

---

### Risk 7 — Degraded actuator fault becomes cosmetic

**Mitigation:** runtime modifier must change the actual update equation/physical bound.

---

### Risk 8 — Fault logic leaks into actuator code

**Mitigation:** actuator only receives current effective modifiers.

---

### Risk 9 — Configuration is physically contradictory

Example:

```text
controller requests ±10°
actuator supports ±3°
```

This can be valid, but it should be intentional.

**Mitigation:** later cross-field config validation may warn/reject obviously incompatible settings depending on project needs.

---

### Risk 10 — Neutral ABORT command still takes time to physically reach zero

This is a realistic consequence of lag.

**Decision:** Do not teleport actuator state to neutral solely because mission mode changes.

If later safety semantics require immediate engine cutoff, that must be an explicit modeled exception, not hidden behavior.

**[Open Question]** Whether ABORT should bypass throttle lag and force immediate cutoff should be decided together with the Mission State Machine and Fault/Safety behavior.

---

## What not to change

While implementing Feature 05, Codex should **not**:

- change 2D dynamics equations;
- change RK4;
- change simulation tick/time semantics;
- change sensor behavior;
- modify PID equations unless integration exposes a real bug;
- implement mission-state transition guards;
- implement general fault scheduling;
- hard-code `degraded_actuator` scenario logic;
- write telemetry CSV/JSON;
- implement mission PASS/FAIL;
- generate plots;
- implement CLI commands;
- add engine thermodynamics;
- add realistic combustion/spool modeling;
- add detailed servo electronics;
- add deadband/backlash/hysteresis unless explicitly approved later;
- add randomness to nominal actuator behavior;
- add hardware interfaces;
- add ROS/CAN/serial;
- add a database;
- add SaaS/cloud infrastructure.

---

# Feature-Specific Definition of Done

Feature 05 is complete when:

- [ ] `ControlCommand` and `ActuatorState` are clearly distinct.
- [ ] Actual actuator state contains throttle and physical gimbal angle.
- [ ] Default initial actuator state is neutral.
- [ ] Throttle physical bounds are implemented.
- [ ] Gimbal physical bounds are implemented.
- [ ] Saturation is explicit and tested.
- [ ] First-order response lag is implemented.
- [ ] Zero-lag behavior is defined.
- [ ] Positive time constants produce smooth monotonic response.
- [ ] Lag is updated with simulation `dt`.
- [ ] No wall-clock timing is used.
- [ ] Optional slew/rate limiting is implemented only if retained by final design.
- [ ] Actuator state updates once per simulation tick.
- [ ] Actuator state is held constant across RK4 stages.
- [ ] Dynamics consumes actual actuator state.
- [ ] Requested command is never mutated.
- [ ] Failed updates do not partially commit actuator state.
- [ ] Invalid/non-finite command values fail clearly.
- [ ] Invalid actuator config fails before normal simulation.
- [ ] Actuator behavior is deterministic.
- [ ] No RNG is used in nominal actuator model.
- [ ] Runtime degradation hook exists for slower response.
- [ ] Degradation changes real actuator behavior.
- [ ] Fault activation timing remains outside this feature.
- [ ] No scenario-name branches exist.
- [ ] Actuator contains no PID/controller logic.
- [ ] Actuator contains no sensor logic.
- [ ] Actuator performs no persistence.
- [ ] Unit tests cover saturation, lag, convergence, errors, and degradation.
- [ ] Controller-actuator integration tests pass.
- [ ] Actuator-dynamics integration tests prove actual—not requested—actuation drives physics.
- [ ] Closed-loop nominal behavior remains stable after actuator lag is connected.
- [ ] Requested-vs-actual output can later be recorded by telemetry.

---

# Open Questions

1. **[Open Question] What final throttle response time constant should the nominal model use?**  
   It must be tuned with the controller/dynamics.

2. **[Open Question] What final gimbal response time constant should be used?**

3. **[Open Question] What final maximum physical gimbal angle should be used?**  
   The planning docs require a maximum gimbal/pitch command but do not lock a value.

4. **[Open Question] Should throttle have an explicit slew/rate limit in addition to first-order lag?**  
   Recommended MVP: only if testing shows clear value.

5. **[Open Question] Should gimbal have an explicit slew-rate limit?**  
   This may be more valuable than a throttle slew limit because it gives a visible physical constraint.

6. **[Open Question] What exact degraded-actuator scenario should be canonical?**  
   Recommended: increased response time constant / sluggish response.

7. **[Open Question] Should the degraded scenario affect throttle, gimbal, or both?**  
   Recommended: target one actuator first so the failure is easy to explain.

8. **[Open Question] What degradation multiplier should the bundled scenario use?**  
   It should be large enough to visibly alter behavior but still produce a meaningful validation case.

9. **[Open Question] Should ABORT force immediate throttle cutoff or continue respecting throttle lag?**  
   This is a safety/modeling policy and should be decided with Feature 06.

10. **[Open Question] Should cross-field config validation require controller software limits to be <= actuator physical limits?**  
    It may be useful to permit a larger controller limit intentionally so physical saturation can be exercised. Prefer warning/documentation over automatic rejection unless inconsistency is clearly erroneous.

---

# Move On When

- [ ] Every actuator behavior has clear Given/When/Then acceptance criteria.
- [ ] Saturation and lag are independently unit tested.
- [ ] Actuator state is distinct from controller command.
- [ ] Actual state—not desired command—drives the dynamics.
- [ ] Update timing matches the fixed simulation-tick architecture.
- [ ] Degraded response is a real behavior change.
- [ ] The actuator model has a reviewer-visible requested-vs-actual demo path.
- [ ] The feature clearly demonstrates stateful hardware-adjacent simulation skill.
- [ ] General fault scheduling remains outside this feature.
- [ ] Mission-state logic remains outside this feature.
- [ ] No unnecessary high-fidelity propulsion/servo, SaaS, database, cloud, or hardware scope has been added.
- [ ] The scope remains finishable and ready to connect to Feature 06 — Mission State Machine.
