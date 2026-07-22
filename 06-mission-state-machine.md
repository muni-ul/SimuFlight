# Feature 06 — Mission State Machine

> **Project:** AstraLoop — Python Software-in-the-Loop Flight Control & Validation System  
> **Feature:** Mission State Machine  
> **Document path:** `docs/features/06-mission-state-machine.md`  
> **Status:** Implementation specification  
> **Primary goal:** Implement explicit, deterministic, measurement-driven mission phases with centralized legal transitions, guarded transition logic, terminal states, transition events, and robust handling of noisy/missing inputs without allowing flight-software logic to read perfect simulator truth.

---

## Scope Boundary

**[Confirmed]** AstraLoop requires an explicit mission state machine with candidate states:

```text
PRELAUNCH
ASCENT
COAST
DESCENT
LANDING
LANDED
ABORT
```

**[Confirmed]** The recommended nominal state flow is:

```text
PRELAUNCH
    |
    v
ASCENT
    |
    v
COAST
    |
    v
DESCENT
    |
    v
LANDING
    |
    v
LANDED
```

with:

```text
any active state
    |
    v
ABORT
```

**[Confirmed]** `LANDED` and `ABORT` are terminal states.

**[Confirmed]** The mission layer owns:

- `MissionState`;
- legal transition definitions;
- transition-guard evaluation;
- transition events.

**[Confirmed]** Active flight-software transitions should use **software-visible measurements and mission context**, not perfect simulator `VehicleState`.

**[Confirmed]** Simulator-only physical checks such as:

- non-finite truth state;
- numerical failure;
- physical ground penetration;

belong to the simulation safety/termination layer rather than the flight-software mission state machine.

**[Decision]** Feature 06 owns the **discrete flight-software mission-mode logic**.

It owns:

- mission-state enum;
- current mission state;
- state-entry tick/time;
- centralized legal-transition map;
- deterministic nominal transition guards;
- configurable transition thresholds;
- transition confirmation/debounce counters;
- critical-measurement health checks used by mission logic;
- generic abort-request handling;
- deterministic priority when multiple transition conditions are true;
- transition reasons;
- transition events returned to the engine;
- terminal-state semantics;
- state-machine unit and integration tests.

It does **not** own:

- 2D physical truth evolution;
- RK4/numerical stepping;
- sensor noise/bias/delay/freeze implementation;
- PID/controller equations;
- actuator lag/saturation;
- fault scheduling or fault definitions;
- telemetry persistence;
- mission PASS/FAIL evaluation;
- hard-landing quality thresholds as final validation;
- CLI behavior;
- scenario campaign logic;
- simulator numerical safety checks.

---

# 1. Feature Overview

## Feature name

**Mission State Machine**

---

## One-sentence description

**[Decision]** Implement a deterministic finite-state machine that moves AstraLoop through `PRELAUNCH`, `ASCENT`, `COAST`, `DESCENT`, `LANDING`, and terminal `LANDED`/`ABORT` states using explicit software-visible guards, legal-transition rules, confirmation logic, and structured transition events.

---

## Detailed description

AstraLoop contains both:

```text
continuous vehicle dynamics
```

and:

```text
discrete flight-software mission modes
```

The 2D vehicle state changes continuously through numerical integration, but the controller should not behave identically throughout the mission.

For example:

- PRELAUNCH should not command active flight thrust;
- ASCENT uses an ascent control profile;
- COAST can disable throttle while retaining attitude control;
- DESCENT uses a downward velocity target;
- LANDING uses a slower final descent target;
- LANDED disables active flight control;
- ABORT uses a safe terminal controller profile.

The Mission State Machine is the component that decides **which mission mode is currently active**.

The core architecture is:

```text
MeasurementSnapshot
        |
        v
Mission State Machine
        |
        v
MissionState
        |
        v
Closed-Loop Controller
        |
        v
mode-specific control profile
```

The controller consumes the current mission mode but does not decide transitions.

---

## Why the mission state machine must be explicit

Without an explicit state machine, mission logic tends to spread across code such as:

```python
if altitude < ...
if velocity > ...
if time > ...
if fault ...
```

inside:

- controller code;
- simulation engine;
- scenario runner;
- actuator code.

That makes behavior difficult to test and explain.

**[Decision]** AstraLoop instead centralizes mission behavior around:

```text
current state
+ software-visible context
+ explicit guard
+ legal transition map
= deterministic state update
```

This makes:

- every state visible;
- every transition testable;
- every transition reason inspectable;
- invalid transitions rejectable;
- controller behavior cleanly separated.

---

## State set

### `PRELAUNCH`

Meaning:

```text
mission initialized but active flight has not started
```

Default initial state.

Primary purpose:

- validate software-visible readiness;
- provide deterministic initial hold period if configured;
- prevent controller state from accumulating before flight.

---

### `ASCENT`

Meaning:

```text
powered positive-altitude flight toward the configured ascent/coast condition
```

Typical controller profile:

- throttle enabled;
- positive vertical-velocity target;
- attitude target near upright.

Exact controller profile belongs to Feature 04.

---

### `COAST`

Meaning:

```text
throttle-reduced/disabled ballistic phase after ascent and before confirmed descent
```

Typical controller profile:

- throttle disabled/zero;
- attitude stabilization may remain active.

---

### `DESCENT`

Meaning:

```text
controlled downward flight before final landing phase
```

Typical controller profile:

- throttle enabled;
- negative vertical-velocity target;
- attitude stabilization enabled.

---

### `LANDING`

Meaning:

```text
final low-altitude descent phase with tighter/slower control target
```

Typical controller profile:

- throttle enabled;
- slower downward velocity target;
- upright attitude target.

---

### `LANDED`

Meaning:

```text
flight software has concluded that the landing/contact condition has been reached
```

**[Decision]** `LANDED` means the mission state machine has recognized the configured landing/contact condition.

It does **not** automatically mean:

```text
mission validation PASS
```

The later Mission Validation feature still evaluates:

- landing vertical speed;
- horizontal error;
- pitch error;
- final state;
- expected scenario outcome.

This separation allows:

```text
LANDED + poor landing metrics = completed landing but validation FAIL
```

rather than forcing quality criteria into state-transition logic.

---

### `ABORT`

Meaning:

```text
flight software deliberately entered a terminal safe/controlled-abort mission mode
```

`ABORT` is a domain outcome, not a Python exception.

The state machine may enter ABORT due to:

- explicit external abort request;
- sustained loss of required software-visible measurement health;
- a later safety/flight-software condition explicitly modeled as an abort guard.

Exact fault activation remains outside this feature.

---

## Initial state

**[Confirmed]** The example nominal mission begins in:

```text
PRELAUNCH
```

**[Decision]** The normal mission state-machine constructor initializes:

```text
state = PRELAUNCH
entered_tick = 0
```

A custom initial mission state should be allowed only for focused tests/development fixtures, not normal bundled scenario execution unless explicitly configured and validated.

---

## Legal transition map

**[Decision]** Centralize legal transitions in one immutable structure.

Recommended:

```python
LEGAL_TRANSITIONS = {
    MissionState.PRELAUNCH: {
        MissionState.ASCENT,
        MissionState.ABORT,
    },
    MissionState.ASCENT: {
        MissionState.COAST,
        MissionState.ABORT,
    },
    MissionState.COAST: {
        MissionState.DESCENT,
        MissionState.ABORT,
    },
    MissionState.DESCENT: {
        MissionState.LANDING,
        MissionState.ABORT,
    },
    MissionState.LANDING: {
        MissionState.LANDED,
        MissionState.ABORT,
    },
    MissionState.LANDED: set(),
    MissionState.ABORT: set(),
}
```

### Why this map matters

It makes the intended flow auditable.

A reviewer can immediately see that:

- no state can jump directly from PRELAUNCH to LANDING;
- ASCENT cannot revert to PRELAUNCH;
- LANDED cannot restart;
- ABORT cannot return to flight;
- any active state may abort.

---

## One transition maximum per simulation tick

**[Decision]** The state machine may commit **at most one state transition per engine tick**.

Example:

If on the same tick:

```text
ASCENT -> COAST guard = true
abort guard = true
```

the state machine must not do:

```text
ASCENT -> COAST -> ABORT
```

within a single call.

Instead, evaluate transition priority and commit exactly one transition.

---

## Transition priority

Source material explicitly identifies the edge case:

```text
fault forces abort during a transition
```

**[Decision]** Transition priority is:

```text
1. ABORT guard / explicit abort request
2. nominal forward transition guard
3. remain in current state
```

### Why

Safety/abort behavior should not be delayed by a simultaneous nominal phase transition.

Example:

```text
current state = DESCENT
landing-entry altitude guard = true
critical sensor failure abort guard = true
```

Result:

```text
DESCENT -> ABORT
```

not:

```text
DESCENT -> LANDING
```

---

## State machine inputs

Recommended API boundary:

```python
StateMachine.update(
    measurement: MeasurementSnapshot,
    context: MissionContext,
) -> MissionUpdate
```

The architecture source explicitly supports a boundary of:

```python
StateMachine.update(measurement, context) -> MissionUpdate
```

---

## `MissionContext`

The exact source documents do not define a final `MissionContext` schema.

**[Decision]** Keep it small and software-oriented.

Recommended:

```python
@dataclass(frozen=True)
class MissionContext:
    tick: int
    dt: float

    abort_requested: bool = False
    abort_reason: str | None = None

    controller_status: ControllerStatus | None = None
```

Potential future additions must be justified individually.

### What belongs in context

Allowed examples:

- current deterministic simulation tick;
- simulation timestep;
- explicit software-level abort request;
- controller health/status;
- discrete software-visible subsystem status.

### What should not be placed in context casually

Do not expose:

```text
perfect truth altitude
perfect truth velocity
perfect truth pitch
perfect truth mass
raw VehicleState
```

solely to make transition guards easier.

That would break the truth/measurement separation.

---

## Fuel status

The master blueprint notes that transition logic **may** use fuel status.

However, the current sensor/controller specs do not expose perfect mass as normal flight-software input.

**[Decision]** Do not use perfect truth mass or fuel quantity in baseline mission transitions.

**[Open Question]** If fuel-aware mission logic becomes necessary, introduce an explicit software-visible discrete status such as:

```text
fuel_available
fuel_low
fuel_depleted
```

through `MissionContext`.

Do not pass raw perfect mass into the state machine.

---

## Mission status data

Recommended:

```python
@dataclass(frozen=True)
class MissionStatus:
    state: MissionState
    entered_tick: int
```

Convenience:

```text
entered_time = entered_tick * dt
state_age_ticks = current_tick - entered_tick
state_age_seconds = state_age_ticks * dt
```

The blueprint previously proposed a `MissionStatus` containing state and entry time; using ticks preserves AstraLoop's deterministic clock model.

---

## Mission update result

Recommended:

```python
@dataclass(frozen=True)
class MissionUpdate:
    previous_state: MissionState
    current_state: MissionState
    changed: bool
    reason: str | None
    event: MissionTransitionEvent | None
```

Optional:

```text
is_terminal
```

as a convenience property.

---

## Transition event

The source blueprint requires:

```text
every transition logged with time and reason
```

and defines a broader `MissionEvent` concept.

**[Decision]** The state machine should **generate**, but not persist, a structured transition event.

Recommended:

```python
@dataclass(frozen=True)
class MissionTransitionEvent:
    tick: int
    time: float

    from_state: MissionState
    to_state: MissionState

    reason_code: str
    message: str
```

Potential metadata:

```python
metadata: Mapping[str, float | int | str | bool]
```

only if it remains simple and useful.

Telemetry/Event Logging later serializes this event.

---

## Transition reason codes

**[Decision]** Use stable machine-readable reason codes plus human-readable messages.

Examples:

```text
prelaunch_complete
ascent_altitude_reached
descent_confirmed
landing_phase_altitude_reached
landing_contact_confirmed
abort_requested
critical_measurement_invalid
controller_invalid_input
```

Do not make tests depend only on free-form English message strings.

---

## Transition guards

The source materials specify that transitions should be explicit, guarded, testable, and may use:

- simulation time;
- measured altitude;
- measured velocity;
- measured pitch;
- controller/status flags;
- fuel status;
- safety thresholds.

They do **not** specify the exact final guard values.

The following guard structure is therefore a **project design decision**, with thresholds remaining configurable/open until nominal mission tuning is complete.

---

## PRELAUNCH → ASCENT

### Intent

Begin active flight after a deterministic prelaunch period and required measurements are ready.

Recommended guard:

```text
state_age >= prelaunch_hold
AND required launch measurements are VALID
```

Potential required measurements:

```text
altitude
vertical velocity
pitch
gyro
```

### Why include readiness

It prevents launching while delayed/disabled sensors have not produced initial usable readings.

### Why include hold time

It gives:

- deterministic startup;
- clean initial telemetry;
- clear controller reset/initialization behavior.

**[Open Question]** Exact `prelaunch_hold_s`.

A development value might be small, but final value should be treated as a project configuration parameter, not a real launch-vehicle claim.

---

## ASCENT → COAST

### Intent

End the powered ascent phase once the software-visible ascent objective is reached.

Recommended guard:

```text
measured altitude >= ascent_cutoff_altitude
AND measured vertical velocity > 0
```

with confirmation for a configured number of consecutive state-machine updates.

### Why use measured altitude

The state machine is flight software and should respond to the sensor view, not perfect truth.

### Why require upward velocity

It prevents a corrupted/noisy altitude sample during descent from satisfying an ascent-transition guard in an unexpected test fixture.

**[Open Question]** Final ascent cutoff altitude.

---

## COAST → DESCENT

### Intent

Detect that the vehicle has passed apex and is now descending.

A naive guard:

```text
measured_vy <= 0
```

can chatter around zero because of sensor noise.

**[Decision]** Use a small negative descent-entry threshold:

```text
measured_vy <= descent_entry_velocity_threshold
```

where:

```text
descent_entry_velocity_threshold < 0
```

and require consecutive confirmation.

Example concept:

```text
vy <= -0.25 m/s for N state-machine updates
```

The exact numerical value is not source-defined.

**[Open Question]** Final descent-entry velocity threshold and confirmation count.

---

## DESCENT → LANDING

### Intent

Switch from general descent control to final landing control.

Recommended guard:

```text
measured altitude <= landing_entry_altitude
AND measured vertical velocity < 0
```

with consecutive confirmation.

### Why

The transition is naturally tied to software-visible altitude.

The negative vertical-velocity condition prevents entering LANDING during an unusual upward crossing of the altitude threshold.

**[Open Question]** Final landing-entry altitude.

---

## LANDING → LANDED

### Intent

Conclude the flight-software mission once the software-visible altitude indicates ground/contact proximity.

A tempting implementation is to require all final validation metrics:

```text
speed within 2 m/s
horizontal error <= 5 m
pitch <= 5 deg
```

before allowing `LANDED`.

**[Decision]** Do **not** use all mission validation criteria as the transition guard.

Instead, use a contact/near-ground recognition guard such as:

```text
measured altitude <= landed_altitude_threshold
```

with consecutive confirmation and optional requirement that:

```text
measured vertical velocity <= small_positive_tolerance
```

### Why

`LANDED` is a mission mode, while:

```text
good landing vs bad landing
```

belongs to Mission Validation.

This allows:

```text
final state = LANDED
landing speed too high
result = validation FAIL
```

which is a clean separation of responsibilities.

### Horizontal error

Do not require horizontal error to enter LANDED.

A vehicle can physically land away from target and then fail validation.

### Pitch error

Do not require pitch error to enter LANDED.

A vehicle can touch down badly and fail validation.

**[Open Question]** Final measured-altitude threshold and confirmation count.

---

## ABORT guard

`ABORT` must be reachable from every active state.

Recommended active states:

```text
PRELAUNCH
ASCENT
COAST
DESCENT
LANDING
```

### Abort source A — explicit abort request

`MissionContext.abort_requested == True`

Transition immediately to:

```text
ABORT
```

Reason comes from:

```text
abort_reason
```

where supplied.

This lets a future flight-software safety component or scenario behavior request a controlled abort without placing fault-manager logic inside the state machine.

---

## Abort source B — sustained critical measurement failure

The sensor feature defines:

```text
VALID
STALE
UNAVAILABLE
DISABLED
```

**[Decision]** Active mission modes may require specific critical measurements to remain `VALID`.

If one or more required critical measurements remain invalid for a configurable number of consecutive mission updates:

```text
transition -> ABORT
```

### Why use confirmation

A one-tick transient should not necessarily abort the entire mission.

A persistent stale/unavailable critical measurement is different.

### Example critical measurement policy

Potential baseline:

```text
ASCENT:
    y, vy, theta, omega

COAST:
    y, vy, theta, omega

DESCENT:
    y, vy, theta, omega

LANDING:
    y, vy, theta, omega
```

Horizontal x/vx may be important for final targeting but are not necessarily required for the minimal throttle/attitude controller defined in Feature 04.

**[Open Question]** Whether x/vx should become abort-critical once horizontal guidance is implemented.

---

## Abort source C — sustained controller invalid-input status

Feature 04 defines:

```text
ControllerStatus.INVALID_INPUT
```

**[Decision]** The state machine may optionally use the **previous/available controller health status** as a second abort signal.

However, because sensor validity already captures most input failures:

**Recommended MVP:** treat direct critical-measurement health as the primary mission abort rule and keep controller-status abort as optional/redundant safety logic.

**[Open Question]** Whether to enable controller-status abort in the nominal MVP.

---

## Critical measurement invalid counter

Recommended deterministic state:

```text
critical_invalid_count: int
```

Behavior:

```text
if all required critical measurements valid:
    critical_invalid_count = 0
else:
    critical_invalid_count += 1
```

Abort when:

```text
critical_invalid_count >= abort_invalid_confirm_ticks
```

Reset:

- when data becomes valid again;
- when a state transition changes the required critical-sensor set.

---

## Guard confirmation / debounce

The master blueprint explicitly identifies an edge case where a landing threshold may briefly oscillate.

**[Decision]** Every noise-sensitive nominal transition may require its guard to remain true for a configurable number of consecutive state-machine updates.

Recommended generic mechanism:

```text
transition_confirm_counts[
    (from_state, to_state)
]
```

For the current candidate nominal transition:

```text
if guard true:
    count += 1
else:
    count = 0
```

Transition when:

```text
count >= required_confirm_ticks
```

### Benefits

- prevents one noisy sample from changing mission phase;
- remains deterministic;
- easy to unit test;
- no complicated filtering required;
- no reverse-transition logic required.

---

## Why not implement reverse transitions

**[Decision]** The nominal mission state graph is one-way.

Do not add:

```text
LANDING -> DESCENT
DESCENT -> COAST
COAST -> ASCENT
```

solely to handle threshold noise.

Use confirmation before the forward transition instead.

This keeps the state graph simple and easier to reason about.

---

## State entry time

On successful transition at tick `t`:

```text
new_state = target
entered_tick = t
```

The event timestamp is:

```python
time = t * dt
```

**Decision:** The transition is considered to occur at the current mission-update tick before the controller executes for that tick.

This aligns with the architecture order:

```text
sensor snapshot
 -> mission state update
 -> controller uses new state
```

Therefore the controller can immediately use the new mission profile on the same tick.

---

## Engine integration order

The selected architecture orders each tick broadly as:

```text
fault activation
sensor sampling
sensor fault effects
measurement snapshot
mission state update
controller
actuator
dynamics
telemetry
```

For Feature 06:

```text
1. receive current tick MeasurementSnapshot
2. receive MissionContext
3. evaluate abort conditions
4. evaluate current state's nominal forward guard
5. commit at most one transition
6. produce MissionUpdate / event
7. controller receives resulting current mission state
```

This makes fault effects visible to mission logic on the same tick after the fault has affected sensor behavior.

---

## Terminal-state semantics

### `LANDED`

No outgoing legal transitions.

### `ABORT`

No outgoing legal transitions.

**Decision]** Calling `update(...)` while already terminal:

```text
returns same state
changed = false
event = None
```

It does not raise merely because the engine queried it again.

### Engine termination

The Mission State Machine exposes:

```text
is_terminal
```

but does not itself stop the simulation loop.

The Simulation Engine/runner decides when to terminate execution based on terminal mission state.

This keeps state logic separate from orchestration.

---

## Invalid transitions

Internal transition code must validate:

```text
target in LEGAL_TRANSITIONS[current_state]
```

If not:

```text
raise MissionTransitionError
```

Examples:

```text
PRELAUNCH -> LANDING
ASCENT -> LANDED
LANDED -> ASCENT
ABORT -> DESCENT
```

must fail loudly in tests.

---

## Repeated transition request

If internal/external code explicitly requests:

```text
ASCENT -> ASCENT
```

**[Decision]** Treat this as an invalid explicit transition request, not a transition event.

Normal `update(...)` simply remaining in ASCENT is valid and produces no event.

This distinguishes:

```text
"no guard fired"
```

from:

```text
"someone attempted an invalid transition operation"
```

---

## Determinism

Given the same:

```text
initial MissionState
MeasurementSnapshot sequence
MissionContext sequence
transition config
tick sequence
```

the state machine must produce the same:

```text
state sequence
transition ticks
reason codes
events
terminal state
```

No randomness belongs in mission logic.

---

## Why it matters

This feature proves AstraLoop can layer deterministic discrete software behavior on top of continuous numerical simulation.

It demonstrates:

- state ownership;
- explicit modes;
- guard logic;
- noisy-input handling;
- terminal outcomes;
- fault response;
- event generation;
- deterministic testing.

It is a strong systems-software signal because the project is no longer just:

```text
ODE + PID
```

It becomes:

```text
continuous plant
+ discrete flight software
+ imperfect sensors
+ failure behavior
```

---

## Skill it demonstrates

A strong implementation demonstrates:

- finite-state-machine design;
- Python `Enum` usage;
- deterministic stateful logic;
- transition guard design;
- threshold/debounce handling;
- event modeling;
- separation between software-visible state and simulator truth;
- fault/safety integration boundaries;
- explicit terminal-state semantics;
- unit testing;
- integration testing;
- edge-case reasoning.

---

## Priority

**P0 — Core MVP**

The source blueprint explicitly lists mission logic as required:

- explicit mission states;
- guarded transitions;
- terminal `LANDED`;
- terminal `ABORT`;
- event log.

The full nominal closed-loop mission should not be considered complete until the state machine is implemented and tested.

---

## Complexity

**Medium**

The individual transitions are simple.

The engineering difficulty comes from:

- clean ownership;
- noisy measurements;
- invalid/stale data;
- transition priority;
- terminal behavior;
- state/controller coupling;
- deterministic timing;
- avoiding truth-state cheating.

---

# 2. User / Demo Flow

The mission state machine is automatic. The user/reviewer does not manually select flight phases during a normal run.

---

## Happy path

1. Mission initializes in `PRELAUNCH`.
2. Sensors produce valid software-visible measurements.
3. Prelaunch readiness/hold guard confirms.
4. State changes:

```text
PRELAUNCH -> ASCENT
```

5. Controller immediately uses ASCENT profile.
6. Measured ascent guard becomes true for required confirmation updates.
7. State changes:

```text
ASCENT -> COAST
```

8. Measured vertical velocity confirms descent.
9. State changes:

```text
COAST -> DESCENT
```

10. Measured altitude reaches landing-entry threshold.
11. State changes:

```text
DESCENT -> LANDING
```

12. Measured near-ground/contact condition confirms.
13. State changes:

```text
LANDING -> LANDED
```

14. `LANDED` is terminal.
15. Later validator evaluates whether the landing met quality criteria.

---

## First-time path

Recommended implementation/proving sequence:

### Stage A — Define enum and legal map

No guards yet.

Test:

- legal transitions accepted;
- illegal transitions rejected;
- terminal states have no outgoing transitions.

### Stage B — Implement `MissionStatus`

Track:

```text
state
entered_tick
state age
```

### Stage C — Implement explicit manual transition helper

Test atomic transition/event behavior independently.

### Stage D — Implement PRELAUNCH → ASCENT

Use only tick/time + measurement readiness.

### Stage E — Implement ASCENT → COAST

Synthetic measurement sequence.

### Stage F — Implement COAST → DESCENT

Use threshold + confirmation count.

### Stage G — Implement DESCENT → LANDING

Use measured altitude.

### Stage H — Implement LANDING → LANDED

Use measured near-ground threshold + confirmation.

### Stage I — Implement explicit abort request

Verify ABORT wins over nominal guard on same tick.

### Stage J — Implement critical-measurement health abort

Use Feature 03 statuses.

### Stage K — Integrate with Feature 04 controller

Verify mode transition changes controller profile/reset behavior without placing transition logic inside controller.

---

## Empty state

There is no "no mission state" during a valid run.

A state machine must always have exactly one current `MissionState`.

Missing/unknown state is a programming/configuration error.

---

## Error path

### Invalid legal-transition configuration

Fail setup/tests.

### Invalid mission threshold

Examples:

```text
NaN landing altitude
negative confirmation count
prelaunch hold < 0
```

Fail configuration before simulation.

### Missing required measurement

For a nominal transition:

```text
guard cannot confirm
remain in current state
```

For sustained missing **critical** measurement:

```text
critical invalid counter increments
eventually transition -> ABORT
```

### Invalid explicit transition request

Raise `MissionTransitionError`.

### Non-finite software-visible measurement

Treat as invalid measurement health.

Do not use it in threshold comparisons.

### Unknown mission state/profile integration

Fail clearly.

---

## Demo path for a reviewer

### Demo A — Nominal transition trace

Show a compact state timeline:

```text
00.00s PRELAUNCH
00.50s PRELAUNCH -> ASCENT      prelaunch_complete
08.20s ASCENT -> COAST          ascent_altitude_reached
12.85s COAST -> DESCENT         descent_confirmed
22.40s DESCENT -> LANDING       landing_phase_altitude_reached
31.17s LANDING -> LANDED        landing_contact_confirmed
```

Exact times are run results, not hard-coded expectations.

### Demo B — State-dependent control

Show the controller target changing when:

```text
DESCENT -> LANDING
```

Example:

```text
DESCENT target vy = faster downward
LANDING target vy = slower downward
```

Explain:

> "The state machine owns the phase change; the controller only consumes the new mode."

### Demo C — Sensor-fault response

Freeze altimeter later through Feature 07.

Show:

```text
measurement becomes stale
critical invalid counter increases
state machine enters ABORT
```

if that is the configured expected behavior.

### Demo D — Invalid transition test

Show a test proving:

```text
ASCENT -> LANDED
```

is rejected.

Reviewer takeaway:

> "Mission phases are a tested software state machine, not scattered if-statements."

---

# 3. UX / UI Requirements

## Screens/pages

**[Decision]** No dedicated UI page.

The state machine is headless.

Later presentation should expose mission state through:

- telemetry channel;
- transition-event log;
- terminal final-state summary;
- plot background/markers.

---

## Components

Recommended software-facing components:

```text
MissionState
MissionStatus
MissionConfig / MissionTransitionConfig
MissionContext
MissionTransitionEvent
MissionUpdate
MissionStateMachine
MissionTransitionError
```

Optional small helper:

```text
GuardConfirmation
```

if it materially improves clarity.

Do not build a generic workflow engine.

---

## Forms/inputs

No GUI form.

Mission configuration should support the thresholds/timing needed by guards.

Recommended fields:

```text
prelaunch_hold_s

ascent_cutoff_altitude_m

descent_entry_velocity_m_s

landing_entry_altitude_m

landed_altitude_threshold_m

prelaunch_confirm_ticks
ascent_confirm_ticks
descent_confirm_ticks
landing_entry_confirm_ticks
landed_confirm_ticks

abort_invalid_confirm_ticks
```

Do not add dozens of state-machine parameters without demonstrated need.

---

## Buttons/actions

None.

---

## Validation messages

Examples:

```text
Invalid mission config: prelaunch_hold_s must be finite and >= 0.
Invalid mission config: descent_entry_velocity_m_s must be < 0.
Invalid mission config: landed_confirm_ticks must be >= 1.
Invalid mission transition: ASCENT -> LANDED is not legal.
Mission guard cannot evaluate ASCENT -> COAST: altitude measurement is unavailable.
Mission entered ABORT: critical measurement invalid for 5 consecutive updates.
```

The "cannot evaluate" message does not necessarily need to be printed every tick; it may be available as structured debug/status information later.

---

## Empty states

Not applicable.

Exactly one mission state always exists.

---

## Loading states

None.

Mission evaluation is synchronous and deterministic.

---

## Error states

Recommended minimal categories:

```text
MissionConfigError
MissionTransitionError
MissionRuntimeError
```

Do not use exceptions for normal:

```text
ABORT
LANDED
no transition this tick
```

---

## Responsive behavior

Not relevant.

---

# 4. Data Requirements

## Entities involved

### `MissionState`

Required:

```python
from enum import Enum

class MissionState(Enum):
    PRELAUNCH = "prelaunch"
    ASCENT = "ascent"
    COAST = "coast"
    DESCENT = "descent"
    LANDING = "landing"
    LANDED = "landed"
    ABORT = "abort"
```

Stable explicit string values help later telemetry/JSON.

---

### `MissionStatus`

Recommended:

```python
@dataclass(frozen=True)
class MissionStatus:
    state: MissionState
    entered_tick: int
```

Convenience methods/properties can derive time with `dt`.

---

### `MissionContext`

Recommended baseline:

```python
@dataclass(frozen=True)
class MissionContext:
    tick: int
    dt: float

    abort_requested: bool = False
    abort_reason: str | None = None

    controller_status: ControllerStatus | None = None
```

Avoid truth fields.

---

### `MissionTransitionConfig`

Potential shape:

```python
@dataclass(frozen=True)
class MissionTransitionConfig:
    prelaunch_hold_ticks: int

    ascent_cutoff_altitude: float
    descent_entry_velocity: float
    landing_entry_altitude: float
    landed_altitude_threshold: float

    ascent_confirm_ticks: int
    descent_confirm_ticks: int
    landing_entry_confirm_ticks: int
    landed_confirm_ticks: int

    abort_invalid_confirm_ticks: int
```

Human-authored config may use seconds and be resolved to ticks during configuration loading.

---

### `MissionTransitionEvent`

```python
@dataclass(frozen=True)
class MissionTransitionEvent:
    tick: int
    time: float

    from_state: MissionState
    to_state: MissionState

    reason_code: str
    message: str
```

---

### `MissionUpdate`

```python
@dataclass(frozen=True)
class MissionUpdate:
    previous_state: MissionState
    current_state: MissionState
    changed: bool
    reason: str | None
    event: MissionTransitionEvent | None
```

---

### `MeasurementSnapshot`

Defined by Feature 03.

Mission state machine primarily consumes:

```text
y
vy
theta/omega health where required
measurement metadata/status
```

It may use x/vx later if horizontal guidance/safety requires them.

---

### `ControllerStatus`

Defined by Feature 04:

```text
OK
HELD
INVALID_INPUT
INACTIVE
```

Optional mission context signal.

---

## Fields and units

| Field | Unit/type | Constraint |
|---|---|---|
| state | `MissionState` | valid enum |
| entered tick | tick | integer, `>= 0` |
| current tick | tick | integer, `>= entered_tick` |
| prelaunch hold | ticks/s | `>= 0` |
| ascent cutoff altitude | m | finite |
| descent entry velocity | m/s | finite, normally `< 0` |
| landing entry altitude | m | finite |
| landed altitude threshold | m | finite |
| confirmation counts | ticks | integer, `>= 1` |
| abort invalid count | ticks | integer, `>= 1` |

---

## Relationships

```text
MeasurementSnapshot
       |
       v
MissionStateMachine <---- MissionContext
       |
       v
MissionUpdate
       |
       +--> MissionState
       |
       +--> Transition Event
       |
       v
Closed-Loop Controller
```

Later:

```text
Transition Event
       |
       v
Telemetry/Event Logger
```

---

## Example configuration shape

**Important:** The source planning documents do not provide final guard values.

This example is structural/development-oriented only.

```toml
[mission]
prelaunch_hold_s = 0.50

ascent_cutoff_altitude_m = 100.0
descent_entry_velocity_m_s = -0.25
landing_entry_altitude_m = 20.0
landed_altitude_threshold_m = 0.50

ascent_confirm_ticks = 3
descent_confirm_ticks = 3
landing_entry_confirm_ticks = 3
landed_confirm_ticks = 3

abort_invalid_confirm_ticks = 5
```

These are project-development examples, not real launch-vehicle specifications.

**[Open Question]** All final thresholds/confirmation counts require nominal mission tuning and fault-scenario validation.

---

## Local persistence needs

**[Decision]** None inside the state-machine feature.

The state machine owns only in-memory mission state and counters.

It does not:

- write JSON;
- write CSV;
- create run folders;
- plot state timelines.

It returns transition events for Feature 09 Telemetry & Event Logging.

---

# 5. Logic Requirements

## Rule 1 — Exactly one current state

The state machine always owns exactly one valid `MissionState`.

---

## Rule 2 — Normal initial state is PRELAUNCH

Unless a focused test explicitly overrides it.

---

## Rule 3 — Legal transitions are centralized

Do not scatter transition rules through multiple `if` blocks/files.

---

## Rule 4 — Illegal transitions raise

No silent acceptance.

---

## Rule 5 — LANDED and ABORT are terminal

No outgoing transitions.

---

## Rule 6 — At most one transition per tick

Never chain multiple state changes in one update.

---

## Rule 7 — ABORT has higher priority than nominal transition

If both true:

```text
ABORT wins
```

---

## Rule 8 — Nominal transitions move only forward

```text
PRELAUNCH
-> ASCENT
-> COAST
-> DESCENT
-> LANDING
-> LANDED
```

---

## Rule 9 — Active guards use software-visible measurements

No perfect truth state.

---

## Rule 10 — Measurement status is checked before value

Do not compare stale/unavailable data to thresholds as if healthy.

---

## Rule 11 — Non-finite measurement values are invalid

Do not perform normal guard comparison.

---

## Rule 12 — Simulator safety is outside mission logic

Do not use perfect non-finite truth checks or physical ground penetration logic here.

---

## Rule 13 — Threshold transitions use confirmation where noise matters

Confirmation count resets if guard becomes false/invalid.

---

## Rule 14 — State entry tick updates only on actual transition

Remaining in the same state must not reset state age.

---

## Rule 15 — Transition event occurs only on state change

No event spam every tick.

---

## Rule 16 — Transition event records old state, new state, tick/time, reason

Required for later telemetry.

---

## Rule 17 — Explicit abort request is deterministic

When true in an active state, enter ABORT immediately that update.

---

## Rule 18 — Sustained critical measurement invalidity may abort

Single transient does not necessarily abort.

---

## Rule 19 — Critical-invalid counter resets when health recovers

No hidden accumulation across healthy periods.

---

## Rule 20 — Transition confirmation counters reset after state change

Counters from ASCENT must not influence COAST.

---

## Rule 21 — Terminal-state update is a no-op

No error merely for being queried.

---

## Rule 22 — Mission state machine does not directly modify controller

It returns state; controller consumes it.

---

## Rule 23 — Mission state machine does not directly modify actuators

No physical command output.

---

## Rule 24 — Mission state machine does not directly activate faults

Fault system modifies subsystems independently.

---

## Rule 25 — Mission state machine contains no scenario-name branching

Behavior is based on current state, measurements, context, and config.

---

## Rule 26 — Mission state machine does not decide PASS/FAIL

Validator owns mission quality/outcome checks.

---

## Rule 27 — LANDED does not imply validation success

Landing metrics can still fail.

---

## Rule 28 — ABORT is not an exception

It is a structured terminal mission state.

---

## Rule 29 — All timing uses simulation tick/time

No wall clock.

---

## Rule 30 — Deterministic input stream yields deterministic transitions

No RNG.

---

## Legal transition helper pseudocode

```python
def transition_to(
    target: MissionState,
    *,
    tick: int,
    dt: float,
    reason_code: str,
    message: str,
) -> MissionUpdate:

    previous = self._status.state

    if target == previous:
        raise MissionTransitionError(
            f"explicit self-transition is not allowed: {previous}"
        )

    if target not in LEGAL_TRANSITIONS[previous]:
        raise MissionTransitionError(
            f"illegal mission transition: {previous} -> {target}"
        )

    self._status = MissionStatus(
        state=target,
        entered_tick=tick,
    )

    self._reset_transition_counters()

    event = MissionTransitionEvent(
        tick=tick,
        time=tick * dt,
        from_state=previous,
        to_state=target,
        reason_code=reason_code,
        message=message,
    )

    return MissionUpdate(
        previous_state=previous,
        current_state=target,
        changed=True,
        reason=message,
        event=event,
    )
```

---

## Mission update pseudocode

```python
def update(
    measurement: MeasurementSnapshot,
    context: MissionContext,
) -> MissionUpdate:

    validate_context(context)
    validate_snapshot_alignment(measurement, context)

    current = self._status.state

    if current in TERMINAL_STATES:
        return no_change(current)

    abort_decision = self._evaluate_abort(
        measurement,
        context,
    )

    if abort_decision.triggered:
        return self._transition_to(
            MissionState.ABORT,
            ...,
        )

    nominal_decision = self._evaluate_nominal_transition(
        current,
        measurement,
        context,
    )

    if nominal_decision.triggered:
        return self._transition_to(
            nominal_decision.target,
            ...,
        )

    return no_change(current)
```

---

## Guard pseudocode — COAST → DESCENT

```python
def coast_to_descent_guard(
    measurement: MeasurementSnapshot,
) -> bool:

    if not is_valid(measurement, SensorName.VERTICAL_VELOCITY):
        return False

    return (
        measurement.vy
        <= config.descent_entry_velocity
    )
```

Then confirmation logic decides when the guard has remained true long enough.

---

## Guard pseudocode — LANDING → LANDED

```python
def landing_to_landed_guard(
    measurement: MeasurementSnapshot,
) -> bool:

    if not is_valid(measurement, SensorName.ALTIMETER):
        return False

    return (
        measurement.y
        <= config.landed_altitude_threshold
    )
```

Optional velocity-sign sanity check can be added if it solves a demonstrated issue.

Do not include final horizontal/pitch/speed validation limits here by default.

---

## Critical health pseudocode

```python
def critical_measurements_valid(
    state: MissionState,
    measurement: MeasurementSnapshot,
) -> bool:

    required = REQUIRED_MEASUREMENTS[state]

    return all(
        measurement.metadata[name].status
        is MeasurementStatus.VALID
        for name in required
    )
```

---

## Edge cases

### Landing threshold oscillates

Confirmation count prevents one-sample transition.

---

### Sensor dropout during transition confirmation

Reset confirmation count.

Increment critical-invalid counter if the sensor is critical.

---

### Abort and nominal transition both true

Abort wins.

---

### Repeated `update()` with no guard

No transition, no event.

---

### Explicit same-state transition request

Rejected.

---

### Fault freezes altimeter

Initially, frozen measurement may remain `VALID`.

As age grows and sensor marks it `STALE`, critical-health policy can eventually trigger ABORT.

This produces a real chain:

```text
fault
-> sensor behavior changes
-> measurement health changes
-> mission state responds
```

without the state machine knowing scenario name.

---

### Delayed but healthy sensor

If Feature 03 labels it `VALID`, mission logic may use it.

Do not reject healthy delayed data merely because source timestamp is old within its allowed delay semantics.

---

### PRELAUNCH sensors unavailable due configured delay

PRELAUNCH -> ASCENT guard remains false.

If PRELAUNCH critical-health abort is enabled, do not abort before the expected startup availability window unless explicitly configured.

**Decision]** PRELAUNCH should use readiness gating rather than the same immediate active-flight invalid-measurement abort counter.

This prevents legitimate initial sensor delay from causing an instant abort.

---

### Mission state queried after LANDED

Return terminal no-change result.

---

### Mission state queried after ABORT

Return terminal no-change result.

---

### Ground contact while state is not LANDING

The source explicitly identifies this edge case.

**Decision]** The state machine itself does not read perfect ground contact.

The Simulation Engine safety layer may detect physical ground penetration/contact independently.

The later Mission Validation layer determines the final domain result.

If a software-visible near-ground measurement occurs while in an unexpected state, a future explicit safety/abort guard may be added, but do not leak truth state into mission logic.

---

### Hard landing

Do not throw `MissionTransitionError`.

Possible behavior:

```text
LANDING -> LANDED
then validation FAIL based on landing speed
```

or simulator safety termination if the physical state becomes invalid.

This is a domain outcome, not a software exception.

---

### Controller invalid-input status on same tick

Because mission update occurs before the current tick's controller update, `MissionContext.controller_status` may represent the most recent available controller status.

Do not design a circular dependency where mission logic needs the controller result that depends on the mission state it is currently computing.

---

### Fault manager explicit abort request

Allowed through a generic context/safety signal if architecture later needs it.

Do not inspect fault IDs or scenario names.

---

# 6. Acceptance Criteria

## AC-01 — MissionState contains required states

**Given** the state enum  
**When** inspected  
**Then** it contains exactly the required MVP mission states:

```text
PRELAUNCH
ASCENT
COAST
DESCENT
LANDING
LANDED
ABORT
```

unless a later documented scope decision intentionally adds one.

---

## AC-02 — Normal initial state is PRELAUNCH

**Given** a default MissionStateMachine  
**When** initialized  
**Then** current state is `PRELAUNCH`.

---

## AC-03 — Initial entered tick is zero

**Given** normal initialization  
**When** status is inspected  
**Then** `entered_tick == 0`.

---

## AC-04 — Legal transition map is explicit

**Given** mission module source  
**When** inspected  
**Then** legal transitions are centrally defined rather than inferred from scattered branches.

---

## AC-05 — PRELAUNCH may transition to ASCENT

**Given** current state PRELAUNCH  
**When** an explicit legal transition to ASCENT is performed  
**Then** it succeeds and emits one transition event.

---

## AC-06 — ASCENT may transition to COAST

**Given** ASCENT  
**When** legal transition to COAST occurs  
**Then** it succeeds.

---

## AC-07 — COAST may transition to DESCENT

**Given** COAST  
**When** legal transition to DESCENT occurs  
**Then** it succeeds.

---

## AC-08 — DESCENT may transition to LANDING

**Given** DESCENT  
**When** legal transition to LANDING occurs  
**Then** it succeeds.

---

## AC-09 — LANDING may transition to LANDED

**Given** LANDING  
**When** legal transition to LANDED occurs  
**Then** it succeeds.

---

## AC-10 — Every active state may transition to ABORT

**Given** any state in PRELAUNCH/ASCENT/COAST/DESCENT/LANDING  
**When** abort guard triggers  
**Then** the next mission state is ABORT.

---

## AC-11 — LANDED is terminal

**Given** current state LANDED  
**When** normal update is called  
**Then** state remains LANDED and no transition event is emitted.

---

## AC-12 — ABORT is terminal

**Given** current state ABORT  
**When** normal update is called  
**Then** state remains ABORT and no transition event is emitted.

---

## AC-13 — Illegal PRELAUNCH → LANDING transition is rejected

**Given** PRELAUNCH  
**When** explicit transition to LANDING is attempted  
**Then** `MissionTransitionError` is raised.

---

## AC-14 — Illegal ASCENT → LANDED transition is rejected

**Given** ASCENT  
**When** explicit transition to LANDED is attempted  
**Then** it is rejected.

---

## AC-15 — Terminal state cannot restart

**Given** LANDED or ABORT  
**When** explicit transition to an active state is attempted  
**Then** it is rejected.

---

## AC-16 — Explicit self-transition is rejected

**Given** current state ASCENT  
**When** code explicitly requests ASCENT → ASCENT  
**Then** it is rejected as an invalid transition request.

---

## AC-17 — No-guard update is a valid no-op

**Given** current state ASCENT and no transition guard is confirmed  
**When** update executes  
**Then** current state remains ASCENT without an event or error.

---

## AC-18 — At most one transition occurs per update

**Given** multiple conditions are simultaneously true  
**When** one update executes  
**Then** no more than one mission transition is committed.

---

## AC-19 — Abort has priority over nominal transition

**Given** a nominal forward guard and abort guard are both true on the same tick  
**When** update executes  
**Then** state transitions to ABORT.

---

## AC-20 — Transition updates entered tick

**Given** a legal transition occurs at tick `t`  
**When** new MissionStatus is created  
**Then** `entered_tick == t`.

---

## AC-21 — No-change update preserves entered tick

**Given** state has been active since tick `s`  
**When** an update produces no transition at later tick `t`  
**Then** `entered_tick` remains `s`.

---

## AC-22 — State age derives from ticks

**Given** `entered_tick = s`, current tick `t`, and timestep `dt`  
**When** state age is requested  
**Then** age equals `(t - s) * dt`.

---

## AC-23 — Transition event records source and target

**Given** a legal transition  
**When** event is created  
**Then** event contains correct `from_state` and `to_state`.

---

## AC-24 — Transition event records deterministic timestamp

**Given** transition at tick `t`  
**When** event is created  
**Then** `event.time == t * dt`.

---

## AC-25 — Transition event includes reason code

**Given** any transition  
**When** event is produced  
**Then** a stable non-empty machine-readable reason code exists.

---

## AC-26 — No transition means no transition event

**Given** guard not confirmed  
**When** update executes  
**Then** `event is None`.

---

## AC-27 — PRELAUNCH guard requires readiness

**Given** prelaunch hold condition is satisfied but a required launch measurement is not valid  
**When** update executes  
**Then** state remains PRELAUNCH.

---

## AC-28 — PRELAUNCH transitions when readiness and hold are satisfied

**Given** required measurements are valid and prelaunch hold requirement is met for configured confirmation semantics  
**When** update executes  
**Then** PRELAUNCH transitions to ASCENT.

---

## AC-29 — ASCENT guard uses measured altitude

**Given** current state ASCENT  
**When** ascent guard is evaluated  
**Then** it uses software-visible altitude measurement and not perfect truth altitude.

---

## AC-30 — ASCENT guard rejects invalid altitude

**Given** altitude measurement is STALE/UNAVAILABLE/DISABLED/non-finite  
**When** ASCENT → COAST guard evaluates  
**Then** the invalid altitude does not satisfy the nominal transition guard.

---

## AC-31 — ASCENT guard may require positive measured vertical velocity

**Given** altitude threshold is met but measured vertical velocity indicates non-ascent  
**When** configured ascent guard evaluates  
**Then** the transition does not confirm until the full guard is satisfied.

---

## AC-32 — COAST → DESCENT uses measured vertical velocity

**Given** current state COAST  
**When** descent guard evaluates  
**Then** it uses measured `vy`, not truth `vy`.

---

## AC-33 — Descent guard resists one noisy threshold crossing

**Given** confirmation count greater than one  
**When** descent guard is true for only one update and false on the next  
**Then** state remains COAST.

---

## AC-34 — Descent guard transitions after consecutive confirmation

**Given** descent guard remains true for required consecutive updates  
**When** required count is reached  
**Then** state transitions COAST → DESCENT.

---

## AC-35 — DESCENT → LANDING uses measured altitude

**Given** current state DESCENT  
**When** landing-entry guard evaluates  
**Then** it uses valid software-visible altitude.

---

## AC-36 — Landing-entry guard can require downward measured motion

**Given** altitude is below landing-entry threshold but measured vertical velocity is upward  
**When** guard evaluates  
**Then** transition does not confirm under the recommended configuration.

---

## AC-37 — LANDING → LANDED uses contact/near-ground guard

**Given** current state LANDING  
**When** valid measured altitude remains below configured landed threshold for required confirmation  
**Then** state transitions to LANDED.

---

## AC-38 — LANDING → LANDED does not require horizontal success metric

**Given** near-ground guard is satisfied but horizontal error would later fail validation  
**When** state transition evaluates  
**Then** horizontal validation quality alone does not prevent entering LANDED.

---

## AC-39 — LANDING → LANDED does not imply validation pass

**Given** state reaches LANDED with excessive landing speed  
**When** mission state is inspected  
**Then** state can still be LANDED while later mission validation may fail.

---

## AC-40 — Guard confirmation resets when guard becomes false

**Given** a transition guard has partial confirmation count  
**When** the guard becomes false  
**Then** its confirmation count resets.

---

## AC-41 — Guard confirmation resets when required measurement becomes invalid

**Given** partial guard confirmation  
**When** required measurement becomes invalid  
**Then** confirmation is reset rather than continuing through missing data.

---

## AC-42 — Transition counters reset after state change

**Given** one transition completes  
**When** next state's guard tracking begins  
**Then** old state's confirmation count does not carry forward.

---

## AC-43 — Explicit abort request causes ABORT

**Given** active state and `abort_requested = True`  
**When** update executes  
**Then** state becomes ABORT immediately that update.

---

## AC-44 — Abort event preserves supplied reason

**Given** explicit abort request with reason  
**When** transition occurs  
**Then** transition event includes a meaningful abort reason/reason code.

---

## AC-45 — Single transient critical sensor invalidity need not abort

**Given** active state and abort-invalid confirmation threshold greater than one  
**When** a critical sensor is invalid for fewer than required updates  
**Then** state does not yet transition to ABORT.

---

## AC-46 — Sustained critical sensor invalidity aborts

**Given** critical measurement health remains invalid for configured consecutive updates  
**When** threshold is reached  
**Then** state transitions to ABORT.

---

## AC-47 — Critical invalid counter resets on recovery

**Given** invalid counter has increased  
**When** all critical measurements become valid before threshold  
**Then** counter resets.

---

## AC-48 — Healthy delayed measurement may be used

**Given** sensor metadata marks a delayed reading as VALID  
**When** mission guard evaluates  
**Then** the state machine may use the value normally.

---

## AC-49 — STALE critical measurement is not treated as valid

**Given** critical sensor status STALE  
**When** health/guard logic evaluates  
**Then** it is treated as invalid.

---

## AC-50 — UNAVAILABLE critical measurement is not treated as valid

**Given** critical sensor status UNAVAILABLE  
**When** logic evaluates  
**Then** it is invalid.

---

## AC-51 — DISABLED critical measurement is not treated as valid

**Given** critical sensor status DISABLED  
**When** logic evaluates  
**Then** it is invalid for active-flight guards that require it.

---

## AC-52 — Non-finite measurement is invalid

**Given** required measurement value NaN/Inf  
**When** guard/health logic evaluates  
**Then** it cannot satisfy a nominal guard.

---

## AC-53 — State machine does not consume VehicleState

**Given** mission module public API and normal engine wiring  
**When** inspected  
**Then** no perfect `VehicleState` is required for active transition guards.

---

## AC-54 — Simulator-only physical invariant logic is absent

**Given** mission-state code  
**When** inspected  
**Then** it does not own non-finite truth checks or physical ground-penetration handling.

---

## AC-55 — State machine does not compute control commands

**Given** mission package  
**When** inspected  
**Then** it does not run PID equations or produce throttle/gimbal values.

---

## AC-56 — State machine does not modify actuator state

**Given** mission update  
**When** it completes  
**Then** actuator state remains owned by Feature 05.

---

## AC-57 — State machine contains no scenario-name branches

**Given** mission source  
**When** inspected  
**Then** it does not check strings such as `altimeter_freeze` or `degraded_actuator`.

---

## AC-58 — State machine does not activate faults

**Given** mission source  
**When** inspected  
**Then** it does not own fault activation schedules.

---

## AC-59 — State machine does not decide mission PASS/FAIL

**Given** state transitions  
**When** mission reaches terminal state  
**Then** no final acceptance result is calculated by Feature 06.

---

## AC-60 — Same measurement/context stream reproduces same state sequence

**Given** identical initial mission state, config, measurements, context, and tick sequence  
**When** two state-machine instances execute  
**Then** states, transition ticks, and reason codes match.

---

## AC-61 — Mission timing uses simulation clock

**Given** state-machine execution  
**When** transition times are calculated  
**Then** they derive from engine tick and `dt`, not wall-clock time.

---

## AC-62 — Controller receives the resulting mission state

**Given** a transition occurs before controller execution on a tick  
**When** controller runs that tick  
**Then** it receives the newly committed mission state/profile.

---

## AC-63 — Controller does not decide transitions

**Given** controller status/command changes  
**When** transition logic is inspected  
**Then** legal state changes remain owned by MissionStateMachine.

---

## AC-64 — Terminal state can be used by engine as termination signal

**Given** state is LANDED or ABORT  
**When** engine queries mission status  
**Then** a deterministic terminal-state property is available without state machine directly stopping the engine.

---

# 7. Test Plan

## Unit tests

Primary file:

```text
tests/unit/test_state_machine.py
```

Recommended groups follow.

---

## Enum/legal-map tests

```text
test_required_mission_states_exist
test_default_initial_state_prelaunch
test_prelaunch_to_ascent_legal
test_ascent_to_coast_legal
test_coast_to_descent_legal
test_descent_to_landing_legal
test_landing_to_landed_legal
test_active_states_can_abort
test_landed_has_no_outgoing_transitions
test_abort_has_no_outgoing_transitions
```

---

## Illegal-transition tests

```text
test_prelaunch_to_landing_rejected
test_ascent_to_landed_rejected
test_landed_to_ascent_rejected
test_abort_to_descent_rejected
test_explicit_self_transition_rejected
```

---

## Mission-status tests

```text
test_entered_tick_set_on_transition
test_no_change_preserves_entered_tick
test_state_age_ticks
test_state_age_seconds
```

---

## Transition-event tests

```text
test_event_from_state
test_event_to_state
test_event_tick
test_event_time
test_event_reason_code
test_no_event_without_transition
```

---

## PRELAUNCH guard tests

```text
test_prelaunch_waits_for_hold_time
test_prelaunch_waits_for_sensor_readiness
test_prelaunch_transitions_when_ready
test_prelaunch_startup_delay_does_not_immediately_abort
```

---

## ASCENT guard tests

```text
test_ascent_uses_measured_altitude
test_ascent_invalid_altitude_blocks_transition
test_ascent_requires_positive_vy_when_configured
test_ascent_confirmation_count
test_ascent_confirmation_resets
```

---

## COAST guard tests

```text
test_coast_does_not_transition_at_small_noise_crossing
test_coast_transitions_after_confirmed_negative_vy
test_coast_invalid_vy_resets_confirmation
```

---

## DESCENT guard tests

```text
test_descent_uses_measured_altitude
test_descent_to_landing_threshold
test_descent_requires_downward_motion_when_configured
test_landing_entry_confirmation
```

---

## LANDING guard tests

```text
test_landing_to_landed_near_ground
test_landed_confirmation_required
test_landing_invalid_altitude_blocks_transition
test_landed_transition_does_not_require_horizontal_success
test_landed_transition_does_not_require_validation_pitch_success
```

---

## Abort tests

```text
test_explicit_abort_from_prelaunch
test_explicit_abort_from_ascent
test_explicit_abort_from_coast
test_explicit_abort_from_descent
test_explicit_abort_from_landing
test_abort_priority_over_nominal_transition
test_abort_reason_recorded
```

---

## Critical-health tests

```text
test_one_invalid_tick_does_not_abort
test_sustained_stale_measurement_aborts
test_sustained_unavailable_measurement_aborts
test_invalid_counter_resets_on_recovery
test_delayed_valid_measurement_does_not_count_invalid
test_non_finite_required_measurement_counts_invalid
```

---

## Terminal-state tests

```text
test_landed_update_is_noop
test_abort_update_is_noop
test_terminal_update_emits_no_new_event
```

---

## Determinism tests

```text
test_identical_measurement_sequence_same_transitions
test_no_rng_dependency
test_transition_timestamps_tick_derived
```

---

## Integration tests with Feature 03 Sensors

Recommended:

```text
tests/integration/test_sensor_state_machine.py
```

### Sensor delay

Verify healthy delayed measurements marked VALID do not automatically cause abort.

### Sensor freeze

Freeze a critical sensor at low level.

Verify:

- value initially held;
- eventually becomes STALE;
- mission invalid counter increases;
- state machine reaches ABORT when policy threshold is met.

General fault scheduling remains Feature 07.

---

## Integration tests with Feature 04 Controller

Recommended:

```text
tests/integration/test_state_machine_controller.py
```

### Mode profile switch

Force:

```text
DESCENT -> LANDING
```

Assert controller receives LANDING on the same tick and resets/switches profile according to Feature 04.

### Terminal modes

Verify:

```text
LANDED
ABORT
```

result in controller's inactive/safe profile.

---

## Integration tests with Feature 02 Engine

Recommended:

```text
tests/integration/test_state_machine_engine.py
```

Verify per-tick ordering:

```text
measurement snapshot
-> mission update
-> controller
```

and transition timestamps align with engine ticks.

---

## Fault integration tests deferred to Feature 07

Later test:

```text
fault activates
-> subsystem behavior changes
-> measurement health changes
-> mission state responds
```

without scenario-name branching inside mission logic.

---

## Telemetry tests deferred to Feature 09

Later verify every transition event is persisted with:

- tick/time;
- from state;
- to state;
- reason.

Feature 06 only generates event objects.

---

## Mission Validation tests deferred to Feature 10

Later verify:

- final state expectation;
- landing quality;
- controlled abort vs failure;
- no invalid transitions occurred.

Feature 06 does not calculate final PASS/FAIL.

---

## Manual QA checklist

- [ ] `MissionState` uses Enum.
- [ ] Required seven states exist.
- [ ] Normal initial state is PRELAUNCH.
- [ ] Legal transitions are centralized.
- [ ] LANDED is terminal.
- [ ] ABORT is terminal.
- [ ] Every active state can abort.
- [ ] Illegal transitions fail loudly.
- [ ] One transition maximum per tick.
- [ ] Abort has priority.
- [ ] Mission state owns entered tick.
- [ ] State age derives from tick/time.
- [ ] Active transition guards use MeasurementSnapshot.
- [ ] No VehicleState is passed to normal mission API.
- [ ] Measurement validity/status checked before threshold values.
- [ ] Guard confirmation/debounce exists.
- [ ] Partial confirmation resets when guard fails.
- [ ] Transition counters reset after state change.
- [ ] Explicit abort request works.
- [ ] Critical sensor health policy works.
- [ ] PRELAUNCH startup availability is handled separately from active-flight abort semantics.
- [ ] Every state change creates one structured event.
- [ ] No-change tick creates no transition event.
- [ ] Reason codes are stable.
- [ ] State machine does not compute control commands.
- [ ] State machine does not update actuators.
- [ ] State machine does not activate faults.
- [ ] State machine does not write telemetry files.
- [ ] State machine does not decide PASS/FAIL.
- [ ] Simulator truth-safety checks remain outside mission module.
- [ ] No scenario-name branches exist.
- [ ] All state-machine unit tests pass.

---

## Demo verification checklist

- [ ] Reviewer sees explicit state graph.
- [ ] Reviewer sees deterministic nominal transition trace.
- [ ] Every transition has a reason.
- [ ] DESCENT -> LANDING visibly changes controller profile.
- [ ] Noise confirmation prevents one-sample transition.
- [ ] Illegal transition test is visible.
- [ ] Sensor failure can lead to controlled ABORT through measurement health.
- [ ] ABORT overrides simultaneous nominal transition.
- [ ] LANDED/ABORT are terminal.
- [ ] Mission state machine never receives perfect truth.
- [ ] Later telemetry can display state and transition markers.

---

# 8. Portfolio Value

## How this feature helps the project stand out

The Mission State Machine is one of the clearest features showing that AstraLoop is a **software system**, not just a numerical notebook.

It demonstrates that the project can combine:

```text
continuous physics
+ discrete flight software
+ imperfect sensor inputs
+ deterministic transitions
+ fault response
```

A strong portfolio explanation is:

> "I modeled mission phases as an explicit finite-state machine. Legal transitions are centralized, active guards use only software-visible measurements, noisy threshold crossings require confirmation, any active state can abort, and every state change emits a structured reasoned event."

That is a strong systems/simulation engineering signal.

---

## What to mention in README

Recommended wording:

> **Explicit mission state machine:** AstraLoop moves through `PRELAUNCH → ASCENT → COAST → DESCENT → LANDING → LANDED`, with guarded measurement-driven transitions and terminal `ABORT` handling. Transition rules are centralized, deterministic, tested, and logged with time and reason.

Useful bullets:

- `Enum` mission states;
- centralized legal transition map;
- measurement-driven guards;
- no perfect truth in flight-software transitions;
- consecutive guard confirmation;
- abort priority;
- terminal `LANDED`/`ABORT`;
- structured transition events;
- state-specific controller profiles.

---

## What to mention in interviews

### Why use a state machine instead of controller `if` statements?

> "Mission phase and control law are different responsibilities. The state machine decides which phase the software is in, while the controller consumes that state and applies the configured profile. That makes transitions independently testable."

### How did you prevent invalid transitions?

> "I centralized the legal transition graph and every committed transition validates against it. A jump like ASCENT to LANDED raises a mission transition error in tests."

### Do transition guards use simulator truth?

> "No. Active flight-software guards use the `MeasurementSnapshot` and mission context, which preserves the same truth-vs-software boundary as the controller."

### How did you handle sensor noise around thresholds?

> "I require noise-sensitive guards to remain true for a configurable number of consecutive mission updates. A single noisy altitude or velocity sample cannot immediately change mission phase."

### What happens when a sensor freezes?

> "The sensor subsystem holds the value and eventually marks it stale. The mission state machine sees the software-visible health state, increments its critical-input invalid counter, and can enter ABORT if the problem persists."

### What if a normal transition and abort happen together?

> "The update can commit only one transition per tick, and ABORT has explicit priority."

### Does LANDED mean the mission passed?

> "No. LANDED is a mission state. Mission Validation separately evaluates landing speed, horizontal error, pitch error, and expected scenario outcome."

### Why not let the state machine check ground truth contact?

> "That would let flight software cheat with simulator truth. Physical ground penetration and numerical safety stay in the simulation layer; mission transitions use the software-visible sensor view."

---

# 9. Implementation Notes for Codex

## Likely files/folders

Primary:

```text
src/astraloop/mission/
├── __init__.py
├── states.py
└── state_machine.py

src/astraloop/model/
└── events.py

src/astraloop/config/
├── schema.py
└── validation.py

tests/unit/
└── test_state_machine.py

tests/integration/
├── test_sensor_state_machine.py
├── test_state_machine_controller.py
└── test_state_machine_engine.py
```

Do not create extra guard-framework files unless `state_machine.py` becomes genuinely difficult to read.

---

## Suggested responsibilities

### `mission/states.py`

Own:

```text
MissionState
LEGAL_TRANSITIONS
TERMINAL_STATES
```

Potentially `MissionStatus`.

---

### `mission/state_machine.py`

Own:

- current status;
- guard evaluation;
- confirmation counters;
- critical health counter;
- abort priority;
- transition operation;
- MissionUpdate construction.

---

### `model/events.py`

Own shared event records such as:

```text
MissionTransitionEvent
```

if events are used by multiple modules.

Do not implement event persistence here.

---

## Build order

### Step 1 — Define MissionState

Use explicit stable enum values.

---

### Step 2 — Define legal transition map

Write legal/illegal-transition tests before guard logic.

---

### Step 3 — Implement MissionStatus

Track entered tick and state age.

---

### Step 4 — Implement atomic transition helper

Requirements:

- validates legality;
- updates state;
- updates entered tick;
- resets guard counters;
- creates one event.

---

### Step 5 — Implement terminal no-op behavior

Lock LANDED/ABORT semantics.

---

### Step 6 — Implement generic confirmation counter

Keep it small and deterministic.

Do not build a generic rules engine.

---

### Step 7 — Implement PRELAUNCH → ASCENT

Readiness + hold.

---

### Step 8 — Implement ASCENT → COAST

Measured altitude/velocity guard.

---

### Step 9 — Implement COAST → DESCENT

Measured negative-velocity confirmation.

---

### Step 10 — Implement DESCENT → LANDING

Measured altitude/downward-motion guard.

---

### Step 11 — Implement LANDING → LANDED

Measured near-ground guard.

Keep validation metrics outside.

---

### Step 12 — Implement explicit abort request

Test priority against simultaneous nominal transition.

---

### Step 13 — Implement critical-measurement health abort

Use Feature 03 metadata.

Do not inspect sensor internals directly.

---

### Step 14 — Integrate with controller

Verify transition occurs before controller profile selection on the tick.

---

### Step 15 — Integrate with engine

Confirm deterministic tick/time ordering.

---

### Step 16 — Leave fault scheduling for Feature 07

Only consume generic effects/context.

---

## Risks

### Risk 1 — Truth-state leakage

A developer may use `VehicleState.y` because it is easier.

**Mitigation:** mission API accepts `MeasurementSnapshot`, not `VehicleState`.

---

### Risk 2 — Transition rules spread into controller

**Mitigation:** controller consumes mode only.

---

### Risk 3 — Noise triggers premature transition

**Mitigation:** consecutive confirmation.

---

### Risk 4 — Too many transition thresholds

A highly configurable state machine can become difficult to tune.

**Mitigation:** keep only the thresholds required by the six nominal transitions/abort health policy.

---

### Risk 5 — Guard logic becomes a generic rules engine

Avoid:

- DSLs;
- expression parsers;
- plugin guard registries;
- dynamic rule trees.

Simple typed functions are stronger for this project.

---

### Risk 6 — ABORT semantics become tied to scenario names

**Mitigation:** abort uses measurement health/context, not `if scenario == ...`.

---

### Risk 7 — LANDED is confused with PASS

**Mitigation:** validator owns landing quality.

---

### Risk 8 — Ground truth contact leaks into software state

**Mitigation:** simulator safety layer remains separate.

---

### Risk 9 — Controller/status circular dependency

Mission state is needed by controller, while controller health may be considered by mission logic.

**Mitigation:** primary abort health is direct measurement status; if controller status is used, consume the most recently available status only. Never require current-tick controller output to compute the state that current-tick controller itself needs.

---

### Risk 10 — PRELAUNCH aborts because delayed sensors are not ready yet

**Mitigation:** PRELAUNCH uses readiness gating/startup semantics rather than active-flight invalid-measurement timeout immediately.

---

### Risk 11 — State machine and engine both try to terminate the run

**Mitigation:** state machine exposes terminal state; engine owns loop termination.

---

### Risk 12 — Hard landing becomes a Python error

**Mitigation:** domain outcome/validation remains separate.

---

## What not to change

While implementing Feature 06, Codex should **not**:

- modify 2D dynamics equations;
- modify RK4;
- change simulation tick/time semantics;
- change sensor noise/delay/freeze implementation;
- give mission logic perfect VehicleState;
- modify PID equations;
- tune controller gains unless integration exposes a real issue;
- modify actuator lag/saturation;
- implement general fault scheduling;
- hard-code `altimeter_freeze` behavior;
- hard-code `degraded_actuator` behavior;
- write events.json;
- write telemetry.csv;
- implement PASS/FAIL validation;
- implement plotting;
- implement CLI commands;
- add reverse mission transitions without a demonstrated need;
- add dozens of mission phases;
- add guidance optimization;
- add a workflow/state-machine framework;
- add a database;
- add SaaS/cloud infrastructure.

---

# Feature-Specific Definition of Done

Feature 06 is complete when:

- [ ] `MissionState` enum contains all required MVP states.
- [ ] Default initial state is PRELAUNCH.
- [ ] Legal transition map is explicit and centralized.
- [ ] PRELAUNCH → ASCENT is legal.
- [ ] ASCENT → COAST is legal.
- [ ] COAST → DESCENT is legal.
- [ ] DESCENT → LANDING is legal.
- [ ] LANDING → LANDED is legal.
- [ ] Every active state can enter ABORT.
- [ ] LANDED is terminal.
- [ ] ABORT is terminal.
- [ ] Illegal transitions fail loudly.
- [ ] Explicit self-transitions are rejected.
- [ ] Normal no-change updates are valid.
- [ ] At most one transition occurs per tick.
- [ ] ABORT has priority over nominal transition.
- [ ] State entry tick/time is tracked.
- [ ] Mission state age is derivable.
- [ ] Active guards use MeasurementSnapshot, not VehicleState.
- [ ] PRELAUNCH readiness/hold guard exists.
- [ ] ASCENT → COAST guard exists.
- [ ] COAST → DESCENT guard exists.
- [ ] DESCENT → LANDING guard exists.
- [ ] LANDING → LANDED guard exists.
- [ ] Noise-sensitive guards use confirmation/debounce.
- [ ] Guard confirmation resets correctly.
- [ ] Critical measurement health policy exists.
- [ ] Sustained critical invalidity can lead to ABORT.
- [ ] PRELAUNCH startup delay is handled without false immediate abort.
- [ ] Generic explicit abort request is supported.
- [ ] Every transition emits structured tick/time/from/to/reason data.
- [ ] No-change tick emits no transition event.
- [ ] Mission state machine does not compute controller commands.
- [ ] Mission state machine does not modify actuator state.
- [ ] Mission state machine does not activate faults.
- [ ] Mission state machine contains no scenario-name branches.
- [ ] Simulator physical safety checks remain outside mission logic.
- [ ] Mission state machine does not calculate final PASS/FAIL.
- [ ] LANDED can still later fail validation.
- [ ] State transitions are deterministic.
- [ ] Unit tests cover every legal transition and selected illegal transitions.
- [ ] Unit tests cover abort priority.
- [ ] Unit tests cover debounce/confirmation.
- [ ] Sensor-state-machine integration tests pass.
- [ ] Controller profile changes correctly when mission state changes.
- [ ] Engine tick/time integration tests pass.
- [ ] Final nominal transition thresholds are documented after tuning.

---

# Open Questions

1. **[Open Question] What final prelaunch hold duration should be used?**

2. **[Open Question] What measured altitude should trigger ASCENT → COAST?**

3. **[Open Question] What negative measured vertical-velocity threshold should confirm COAST → DESCENT?**

4. **[Open Question] What measured altitude should trigger DESCENT → LANDING?**

5. **[Open Question] What measured near-ground altitude threshold should trigger LANDING → LANDED?**

6. **[Open Question] How many consecutive confirmation updates should each transition require?**  
   They may share a common default or use state-specific values.

7. **[Open Question] How many consecutive invalid critical-measurement updates should trigger ABORT?**

8. **[Open Question] Which sensor channels are critical in each active mission state?**  
   Recommended MVP focus: altitude, vertical velocity, pitch, and gyro for modes that require active control.

9. **[Open Question] Should horizontal position/velocity become abort-critical?**  
   Recommended only if a horizontal guidance/controller feature is added.

10. **[Open Question] Should controller `INVALID_INPUT` independently trigger ABORT, or should critical sensor health remain the sole baseline rule?**  
    Recommended baseline: sensor health first; avoid redundant circular logic unless needed.

11. **[Open Question] Should fuel availability become software-visible mission context?**  
    Do not expose perfect mass. Introduce a discrete status only if a real transition/safety requirement appears.

12. **[Open Question] Should LANDING → LANDED require a vertical-velocity sign/tolerance check in addition to altitude?**  
    Recommended: keep it primarily contact/altitude-based so landing quality remains a validation responsibility.

13. **[Open Question] How should the Simulation Engine stop after LANDED/ABORT?**  
    Feature 06 exposes terminal state; the exact final telemetry/controller/physics ordering around termination should be frozen with engine/telemetry integration tests.

14. **[Open Question] Should an explicit ABORT force immediate physical throttle cutoff or allow actuator lag?**  
    This is a cross-feature safety/modeling decision involving Feature 05 and should not be silently encoded in the state machine.

---

# Move On When

- [ ] Every state and transition is explicit.
- [ ] Every major transition has Given/When/Then acceptance criteria.
- [ ] Every legal transition is tested.
- [ ] Selected illegal transitions are tested.
- [ ] Transition guards use software-visible measurements.
- [ ] Threshold noise is handled deterministically.
- [ ] ABORT priority is defined and tested.
- [ ] LANDED/ABORT terminal behavior is tested.
- [ ] Transition events include time and reason.
- [ ] State-dependent controller behavior works without transition logic leaking into controller code.
- [ ] Sensor failure can influence mission state through generic measurement health rather than scenario-name branches.
- [ ] State-machine logic clearly demonstrates deterministic stateful-software skill.
- [ ] Simulator safety, fault scheduling, telemetry persistence, and validation remain separate.
- [ ] No unnecessary SaaS, workflow framework, database, GUI, or extra mission-phase scope has been added.
- [ ] The project remains finishable and ready to proceed to Feature 07 — Fault Injection System.
