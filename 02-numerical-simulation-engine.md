# Feature 02 — Numerical Simulation Engine

> **Project:** AstraLoop — Python Software-in-the-Loop Flight Control & Validation System  
> **Feature:** Numerical Simulation Engine  
> **Document path:** `docs/features/02-numerical-simulation-engine.md`  
> **Status:** Implementation specification  
> **Primary goal:** Build the deterministic fixed-step runtime that advances AstraLoop's 2D truth state using a project-owned RK4 integrator and a simulation-time clock, while defining clean extension points for later sensors, controllers, actuators, mission logic, faults, telemetry, and validation.

---

## Scope Boundary

**[Confirmed]** AstraLoop's selected architecture uses a **project-owned fixed-step RK4 integrator** as the production runtime and keeps SciPy `solve_ivp` as an independent numerical reference in later verification tests.

**[Confirmed]** The simulation uses an integer tick counter with:

```python
sim_time = tick * dt
```

instead of repeatedly accumulating floating-point time.

**[Confirmed]** The fixed-step design is intentional because AstraLoop will eventually combine continuous vehicle dynamics with discrete-time behavior such as sensor sampling, sensor delay buffers, controller update periods, actuator lag, state transitions, fault activation, and telemetry frames.

**[Decision]** Feature 02 owns the **deterministic numerical runtime and simulation lifecycle**, not the domain behavior of those later subsystems.

It owns:

- simulation configuration needed for numerical execution;
- integer tick-based simulation time;
- fixed-step RK4 integration;
- conversion between named vehicle-state records and numerical state vectors if needed;
- advancement of the 2D truth state by exactly one configured `dt`;
- pre-step and post-step invariant checks;
- physical-bound enforcement after a numerical step;
- maximum-time / maximum-tick termination;
- simulator error detection;
- deterministic step ordering contract;
- generic extension points/hooks for later subsystems;
- minimal in-memory simulation result needed for tests;
- numerical-engine unit and integration tests.

It does **not** own the implementation of:

- 2D flight equations themselves;
- sensor noise, delay, freeze, bias, or sampling logic;
- closed-loop controllers;
- actuator lag, saturation, or slew behavior;
- mission-state transition rules;
- fault definitions or activation behavior;
- scenario TOML loading;
- telemetry file writing;
- event persistence;
- plots;
- mission PASS/FAIL validation;
- polished CLI behavior;
- SciPy-based numerical verification;
- Monte Carlo campaigns.

Those are separate AstraLoop features.

---

# 1. Feature Overview

## Feature name

**Numerical Simulation Engine**

## One-sentence description

**[Decision]** Implement a deterministic fixed-step simulation runtime that advances AstraLoop's 2D vehicle truth state with a custom RK4 integrator, derives simulation time from an integer tick, enforces runtime invariants, and provides stable extension points for later flight-software subsystems.

---

## Detailed description

Feature 01 defines the physical truth model as a derivative function:

```text
current VehicleState
+ applied physical actuation
+ vehicle parameters
+ environment inputs
        |
        v
VehicleStateDerivative
```

Feature 02 turns that mathematical derivative model into an evolving simulation.

The core responsibility is:

```text
state at time t
      |
      v
 fixed-step RK4
      |
      v
state at time t + dt
```

while maintaining a deterministic simulation clock and enforcing a clear lifecycle around each step.

The engine must be usable in two modes:

### Mode A — Minimal/open-loop engine use

During early development, the engine can advance the 2D dynamics with fixed applied inputs.

Example:

```text
constant throttle
constant gimbal
zero external force
```

This is sufficient to prove that:

- RK4 works;
- time advances correctly;
- the vehicle state evolves numerically;
- physical bounds are enforced;
- runs terminate deterministically.

### Mode B — Full AstraLoop orchestration later

As later features are implemented, the same engine becomes the owner of the master per-tick ordering:

```text
A. inspect terminal/simulator safety conditions
B. activate/deactivate faults for this tick
C. sample sensors from current truth
D. apply sensor faults / delay / stale behavior
E. construct measurement snapshot
F. update flight-software mission state
G. compute desired control command
H. update actuator models and actuator faults
I. advance truth state by exactly dt
J. validate runtime invariants
K. record telemetry frame and events
L. increment integer tick
```

**[Decision]** Feature 02 defines and protects this ordering contract, but it must not implement the later subsystem behavior before those features exist.

During Feature 02 implementation, missing subsystems should be represented by the smallest possible no-op or explicitly supplied dependency required to exercise the engine.

---

## Why fixed-step RK4

**[Decision]** Use a project-owned classical fourth-order Runge-Kutta method:

```text
k1 = f(t, state)

k2 = f(
    t + dt/2,
    state + dt*k1/2
)

k3 = f(
    t + dt/2,
    state + dt*k2/2
)

k4 = f(
    t + dt,
    state + dt*k3
)

next_state =
    state
    + dt/6 * (k1 + 2*k2 + 2*k3 + k4)
```

For AstraLoop's current dynamics, the derivative function does not need wall-clock time, but the integrator interface may accept simulation time so the abstraction remains mathematically conventional and can support future explicitly time-dependent environmental inputs.

### Why RK4 instead of Euler

**[Decision]** Euler is not the production integrator.

**Justification:**

- Euler is simple but less accurate for a given timestep;
- AstraLoop includes coupled translational and rotational dynamics;
- RK4 provides a strong accuracy/complexity balance;
- RK4 is understandable enough to implement and explain completely;
- it gives the project real numerical-engineering substance without becoming a numerical-methods research project.

### Why not `solve_ivp` as the production scheduler

**[Decision]** Do not use adaptive `solve_ivp` as the main runtime scheduler.

**Justification:**

AstraLoop is a hybrid continuous/discrete software system. Later components will depend on precise, simple timing semantics:

```text
sensor updates
delay buffers
controller updates
fault activation
state transitions
actuator updates
telemetry samples
```

A fixed tick lets all of them agree on exactly when an event happens.

SciPy remains valuable later as an **independent reference oracle** in the Numerical Verification feature.

---

## Simulation clock

The engine stores:

```text
tick: int
dt: float
```

and derives:

```python
sim_time = tick * dt
```

**[Decision]** Never advance simulation time using:

```python
sim_time += dt
```

as the authoritative time source.

### Why

Repeated floating-point accumulation can create small drift:

```text
expected: 20.0
actual:   19.999999999...
```

That becomes dangerous when later logic depends on exact tick-aligned conditions such as:

```text
activate fault at 20.0 s
sample sensor every 0.1 s
change controller mode at a deterministic time
```

With an integer tick, time is always derived from a stable discrete index.

---

## Timestep configuration

Required runtime values:

```text
dt
max_time
```

Recommended derived value:

```text
max_ticks
```

### `dt`

**[Decision]**

```text
dt > 0
```

and finite.

The timestep is constant for the entire run.

No adaptive timestep logic belongs in the MVP.

### `max_time`

**[Decision]**

```text
max_time > 0
```

and finite.

The engine must always have a deterministic upper bound on simulated duration.

### `max_ticks`

Recommended derivation:

```python
max_ticks = ceil(max_time / dt)
```

The exact final-time convention must be explicitly tested.

**[Decision]** A run must never continue indefinitely because a later mission state failed to transition.

---

## Step semantics

One engine step represents:

```text
current simulation instant: tick
current simulation time:    tick * dt

perform configured work for this tick
advance truth state by one dt
validate next truth state
increment tick

new simulation time:        new_tick * dt
```

**[Decision]** The state stored after a completed step corresponds to the **new tick time**.

Example:

```text
initial tick = 0
initial time = 0.00

step with dt = 0.02

new tick = 1
new time = 0.02
state = state at t = 0.02
```

This relationship must stay true everywhere in the engine.

---

## Initial-state semantics

**[Decision]**

At run start:

```text
tick = 0
sim_time = 0.0
state = configured initial VehicleState
```

The engine validates the initial state before the first integration step.

The engine does not automatically "repair" a materially invalid initial condition.

Examples that must fail:

- non-finite state;
- mass materially below dry mass;
- invalid numerical configuration;
- invalid physical parameters.

---

## RK4 and applied inputs

Feature 01's dynamics depend on applied actuation and environment inputs.

For one RK4 step, the simplest MVP rule is:

**[Decision]** Hold the externally supplied applied actuation and environment inputs constant across all four RK4 derivative evaluations within that one `dt`.

Conceptually:

```text
tick begins
  |
  +--> determine applied inputs for this tick
  |
  +--> k1 uses those inputs
  +--> k2 uses those inputs
  +--> k3 uses those inputs
  +--> k4 uses those inputs
  |
  +--> produce next state
```

### Why

Later sensors/controllers/actuators operate on discrete ticks.

Recomputing discrete controller or actuator state inside RK4 sub-stages would blur the boundary between:

```text
continuous integration
```

and:

```text
discrete software update
```

The applied input for a tick should be determined once, then treated as constant over that fixed integration interval.

This is a standard and explainable zero-order-hold style approximation for the project's discrete/continuous architecture.

---

## State-vector conversion

Feature 01 intentionally uses named domain records such as:

```python
VehicleState(
    x=...,
    y=...,
    vx=...,
    vy=...,
    theta=...,
    omega=...,
    mass=...,
)
```

RK4 arithmetic benefits from vector operations.

**[Decision]** Keep named records at public module boundaries and use a clearly documented internal vector ordering where numerical arithmetic is simpler.

Recommended order:

```text
0 x
1 y
2 vx
3 vy
4 theta
5 omega
6 mass
```

Required helpers:

```python
state_to_vector(state) -> NDArray
vector_to_state(vector) -> VehicleState
derivative_to_vector(derivative) -> NDArray
```

**Decision:** This ordering must exist in one place only.

Do not spread raw numeric indices through the codebase.

---

## Runtime invariant checks

The engine is responsible for detecting impossible or numerically invalid runtime state after each integration step.

At minimum check:

```text
all state fields finite
mass >= dry_mass within documented tolerance
state shape/field count is valid
tick is nonnegative
dt is valid and unchanged
sim_time is consistent with tick * dt
```

Possible later invariant:

```text
ground penetration handling
```

must remain physically separate from mission-result interpretation.

---

## Post-step physical bounds

Feature 01 defines that a finite numerical step may slightly overshoot dry mass even when the derivative is correct.

**[Decision]** Feature 02 owns post-step bound enforcement because this is caused by numerical stepping.

Recommended logic:

```text
if next_mass >= dry_mass:
    accept

elif next_mass is below dry_mass only within configured/tiny numerical tolerance:
    replace with dry_mass

else:
    raise SimulationError
```

### Better handling for predictable fuel depletion

**[Decision]** Prefer preventing a known dry-mass overshoot during RK4 when practical rather than relying only on a tolerance clamp.

A robust MVP approach is:

1. dynamics returns zero mass-flow at dry mass;
2. after the RK4 step, engine clamps only a small numerical overshoot to dry mass;
3. materially impossible mass values trigger an error.

Do not add event-location algorithms or variable sub-stepping solely to find the exact fuel-exhaustion instant in the MVP.

---

## Ground boundary

Feature 01 intentionally does not decide mission state.

**[Decision]** The engine may detect a physically invalid state such as severe ground penetration, but it does not decide whether the mission is:

```text
LANDED
HARD_LANDING
PASS
FAIL
ABORT
```

Those are later mission/validation decisions.

For Feature 02, the engine needs only a safe rule preventing uncontrolled numerical continuation.

Recommended initial behavior:

```text
if configured open-loop test intentionally allows y < ground:
    let the test control termination

for normal full runtime:
    expose a terminal/safety hook that later mission logic can use
```

**[Open Question]** Exact ground-contact clamping behavior should be finalized together with the Mission State Machine and Mission Validation features so the engine does not accidentally encode mission outcome policy.

---

## Simulation lifecycle

Recommended lifecycle:

```text
1. validate numerical configuration
2. validate physical parameters
3. validate initial state
4. initialize tick = 0
5. initialize deterministic subsystem dependencies
6. expose initial state/time if needed
7. repeat:
      a. inspect terminal/safety condition
      b. execute tick-order dependencies
      c. obtain applied physical inputs
      d. integrate truth state by exactly dt
      e. enforce post-step physical bounds
      f. validate runtime invariants
      g. expose post-step snapshot to later observers
      h. increment/commit tick consistently
8. stop on terminal condition or max ticks
9. return structured in-memory simulation result
```

The exact placement of telemetry/event recording will be finalized when those later features are implemented, but the engine's timing semantics must not change casually after that point.

---

## Why it matters

This feature is the bridge between:

```text
equations on paper
```

and:

```text
a deterministic software-in-the-loop runtime
```

Without it:

- the vehicle state cannot evolve through time;
- later controllers have no consistent control interval;
- sensor delay cannot be defined cleanly;
- fault activation timing becomes ambiguous;
- telemetry timestamps become fragile;
- end-to-end tests become difficult to reproduce;
- numerical correctness cannot be independently verified.

It is one of the strongest systems/simulation engineering signals in AstraLoop.

---

## Skill it demonstrates

A strong implementation demonstrates:

- deterministic simulation architecture;
- numerical integration;
- RK4 implementation;
- discrete/continuous system reasoning;
- explicit timing semantics;
- typed Python interfaces;
- NumPy vector arithmetic;
- invariant design;
- error handling;
- separation of numerical and domain logic;
- reproducibility;
- testability;
- architectural restraint.

---

## Priority

**P0 — Foundational**

Feature 02 should be completed immediately after the Feature 01 dynamics equations are trustworthy.

Later closed-loop features should not be built on an untested simulation clock or unverified RK4 implementation.

---

## Complexity

**High**

The implementation itself can remain compact, but subtle bugs in:

- RK4 staging;
- time indexing;
- tick ordering;
- state/vector mapping;
- input-hold semantics;
- max-time termination;
- post-step bound handling;

can silently contaminate every later feature.

---

# 2. User / Demo Flow

This is primarily an internal runtime feature, so the "user" is the scenario runner, tests, and technical reviewer.

---

## Happy path

1. Valid numerical configuration is supplied:

```text
dt = 0.02
max_time = 60.0
```

2. Valid initial `VehicleState` and physical parameters are supplied.
3. The engine initializes:

```text
tick = 0
sim_time = 0.0
```

4. The engine obtains the applied physical inputs for tick 0.
5. RK4 evaluates the dynamics four times.
6. A next state is produced for:

```text
t = 0.02
```

7. The engine enforces physical bounds.
8. Runtime invariants pass.
9. Tick becomes 1.
10. The process repeats until a terminal condition or maximum simulated duration is reached.
11. The engine returns a structured in-memory result.

Expected characteristics:

- no wall-clock sleep;
- no dependency on machine speed;
- same inputs produce same trajectory;
- each state/time pair is internally consistent;
- the run cannot continue forever.

---

## First-time path

Recommended first implementation path:

### Stage 1 — Test RK4 on a simple scalar ODE

Use a tiny test-only equation such as:

```text
dy/dt = -2y
```

with a known analytical solution:

```text
y(t) = y0 * exp(-2t)
```

This isolates RK4 correctness from flight dynamics.

### Stage 2 — Test RK4 on a small vector ODE

Use a two-state system to prove vector handling.

### Stage 3 — Connect Feature 01 dynamics

Run a short gravity-only vehicle simulation.

Verify:

```text
tick/time relationship
state evolves
no NaN/Inf
mass remains valid
```

### Stage 4 — Run upright-thrust symmetry case

Verify:

```text
x remains approximately symmetric/zero
vertical state changes
```

### Stage 5 — Run gimbaled input case

Verify coupled translational/rotational evolution.

### Stage 6 — Add max-time termination and invariant tests

Only after these pass should later subsystems connect to the runtime.

---

## Empty state

There is no valid run without:

- initial state;
- valid `dt`;
- valid `max_time`;
- dynamics dependency;
- required physical parameters.

Missing required inputs are configuration/programming errors.

The engine must not invent:

- a default initial vehicle state;
- an arbitrary timestep;
- an arbitrary maximum duration.

---

## Error path

### Invalid `dt`

Examples:

```text
0
negative
NaN
Inf
```

Expected:

- fail before simulation begins.

### Invalid `max_time`

Same principle.

### Invalid initial state

Expected:

- fail before the first integration step.

### Non-finite derivative

If any RK4 derivative stage returns NaN/Inf:

- abort the simulation;
- raise `SimulationError`;
- identify the failing stage where practical.

### Non-finite next state

- abort;
- raise `SimulationError`.

### Impossible mass

- small numerical overshoot may be clamped to dry mass;
- material violation raises `SimulationError`.

### Impossible internal time state

Examples:

```text
negative tick
sim_time not consistent with tick * dt
tick exceeds expected max without termination
```

Expected:

- raise `SimulationError`.

### Dependency callback failure

A later subsystem hook may raise its own domain error.

**[Decision]** The engine should preserve the causal exception where practical rather than swallow it and continue with corrupted state.

---

## Demo path for a reviewer

The strongest reviewer demo for Feature 02 is not a flashy UI.

It is a short reproducible numerical proof.

### Demo A — Show the engine timing model

Open the core code and show:

```python
sim_time = tick * dt
```

Explain:

> "The simulation is driven entirely by simulation time, not wall-clock time. That lets later sensor delays, controller updates, faults, and telemetry use one deterministic clock."

### Demo B — Run a deterministic open-loop flight case

Use:

```text
same initial state
same fixed applied actuation
same dt
```

Run twice.

Show that the final state/trajectory matches.

### Demo C — Show a timestep comparison

Run a small deterministic open-loop case at:

```text
dt
dt / 2
```

The full rigorous convergence/reference analysis belongs to Numerical Verification, but a development-level comparison can show that the engine supports controlled timestep refinement.

### Demo D — Show tests

Highlight:

- analytical RK4 unit test;
- deterministic tick/time test;
- max-duration termination test;
- invalid-state failure test.

Reviewer takeaway:

> "I did not just call a black-box ODE function. I designed the simulation scheduler, implemented the integrator, made timing deterministic, and protected it with tests."

---

# 3. UX / UI Requirements

## Screens/pages

**[Decision]** No dedicated UI page is required.

The Numerical Simulation Engine must work headlessly.

Later user-facing surfaces may include:

- CLI summary;
- telemetry artifacts;
- plots;
- README screenshots.

None of those may be required for the engine's correctness.

---

## Components

Software-facing components should include equivalents of:

```text
SimulationConfig
SimulationClock or tick/time helpers
RK4 integrator
SimulationEngine
SimulationResult
SimulationError
state/vector conversion helpers
runtime invariant checks
```

Do not create components solely for architectural decoration.

---

## Forms/inputs

No direct form.

Required numerical configuration fields:

```text
dt
max_time
```

Potential optional development/test field:

```text
max_ticks
```

but avoid exposing two independently configurable termination limits if they can contradict each other.

**[Decision]** Prefer `dt + max_time` as human configuration and derive `max_ticks`.

---

## Buttons/actions

None in this feature.

Later CLI actions will call the scenario/application boundary.

---

## Validation messages

Messages should be actionable.

Examples:

```text
Invalid simulation timestep: dt must be finite and > 0; received 0.0.
Invalid simulation duration: max_time must be finite and > 0; received -1.0.
Simulation became non-finite at tick 241 (t=4.82 s): state.vy=nan.
RK4 stage k3 returned a non-finite derivative for omega.
Simulation invariant violated at tick 500: mass=899.91 kg is below dry_mass=900.0 kg beyond tolerance.
```

Avoid:

```text
Simulation failed.
```

without diagnostic context.

---

## Empty states

Not visually relevant.

A run with no valid initial condition is an error.

---

## Loading states

No fake loading UI.

Simulation should execute as fast as the computer allows.

**[Decision]** Never call `sleep()` to make simulation appear real-time.

---

## Error states

The engine should differentiate:

### Configuration error

Detected before execution.

Examples:

- invalid `dt`;
- invalid duration;
- invalid initial state.

### Runtime simulation error

Detected after run start.

Examples:

- NaN;
- Inf;
- impossible state;
- broken invariant;
- internal timing inconsistency.

### Normal terminal outcome

Later mission outcomes are **not** engine exceptions.

Examples:

- `LANDED`;
- controlled `ABORT`;
- mission validation failure.

Those belong to later features.

---

## Responsive behavior

Not relevant.

---

# 4. Data Requirements

## Entities involved

### `SimulationConfig`

Recommended:

```python
@dataclass(frozen=True)
class SimulationConfig:
    dt: float
    max_time: float
```

Derived:

```python
max_ticks: int
```

either as a property or validated helper.

---

### `SimulationClock`

Two acceptable designs:

#### Option A — No dedicated class

Engine stores:

```python
tick: int
dt: float
```

and calculates time directly.

#### Option B — Tiny immutable/helper clock

```python
@dataclass(frozen=True)
class SimulationClock:
    tick: int
    dt: float

    @property
    def time(self) -> float:
        return self.tick * self.dt
```

**[Decision]** Use whichever is simpler in the actual codebase.

Do not build a scheduling framework.

---

### `VehicleState`

Defined by Feature 01:

```text
x
y
vx
vy
theta
omega
mass
```

Feature 02 consumes and advances this state.

---

### `AppliedActuation`

Defined as the physical input boundary by Feature 01.

For the early engine, this can be provided by:

- a constant test fixture;
- a simple callback;
- later, the actuator subsystem.

---

### `EnvironmentForces`

Likewise supplied to dynamics.

---

### `SimulationSnapshot`

Useful in-memory boundary:

```python
@dataclass(frozen=True)
class SimulationSnapshot:
    tick: int
    sim_time: float
    state: VehicleState
```

**[Decision]** Keep this minimal.

Do not duplicate future telemetry schema here.

---

### `SimulationResult`

Minimal recommended shape:

```python
@dataclass(frozen=True)
class SimulationResult:
    final_tick: int
    final_time: float
    final_state: VehicleState
    termination_reason: str
```

Potential test/development extension:

```text
snapshots
```

but avoid storing an entire mission trajectory by default if later telemetry will own that responsibility.

**[Decision]** The engine may optionally expose snapshot callbacks/observers rather than permanently storing every state itself.

---

### `TerminationReason`

Recommended enum or clear typed value:

```text
MAX_TIME
TERMINAL_CONDITION
SIMULATION_ERROR
```

**Decision:** Do not place mission-specific values such as `LANDED` or `HARD_LANDING` in the core engine termination enum.

---

## Fields and constraints

| Field | Type | Constraint |
|---|---:|---|
| `dt` | float | finite, `> 0` |
| `max_time` | float | finite, `> 0` |
| `tick` | int | `>= 0` |
| `sim_time` | float | exactly derived from `tick * dt` |
| `max_ticks` | int | positive |
| state fields | float | finite; physical constraints delegated/shared with Feature 01 |
| termination reason | enum/string | known value |

---

## Relationships

```text
SimulationConfig
       |
       v
SimulationEngine
       |
       +--> tick / sim_time
       |
       +--> current VehicleState
       |
       +--> applied inputs for current tick
       |
       v
   RK4 Integrator
       |
       v
Feature 01 compute_derivatives(...)
       |
       v
next VehicleState
       |
       v
post-step bounds + invariant checks
       |
       v
next tick
```

Future extension:

```text
Engine tick
   |
   +--> faults
   +--> sensors
   +--> mission
   +--> controller
   +--> actuators
   +--> RK4
   +--> telemetry
```

but those later modules remain outside Feature 02 implementation scope.

---

## Example seed data

Example numerical configuration:

```toml
[simulation]
dt = 0.02
max_time = 60.0
```

These values are development configuration examples.

**[Open Question]** The final supported production `dt` for the nominal mission must be established through later Numerical Verification rather than assumed correct solely because the simulation appears stable.

---

## Local persistence needs

**[Decision]** None.

The Numerical Simulation Engine must not directly write:

- telemetry CSV;
- event JSON;
- summary JSON;
- plots;
- run folders.

It should return data and/or call an injected observer boundary.

Persistence belongs to the Telemetry & Event Logging feature.

---

# 5. Logic Requirements

## Rule 1 — Simulation time is derived from integer ticks

Authoritative time:

```python
sim_time = tick * dt
```

Never use wall-clock time for physics.

Never use `time.sleep()` to model simulation time.

---

## Rule 2 — `dt` is constant during a run

The engine must not silently change the timestep in response to:

- state magnitude;
- errors;
- faults;
- controller behavior.

Adaptive stepping is out of scope.

---

## Rule 3 — RK4 is the production integrator

The engine must use the project's RK4 implementation rather than delegating production stepping to SciPy.

---

## Rule 4 — RK4 contains no mission logic

`integrator.py` must be mathematically focused.

It must not know:

- mission states;
- fault names;
- sensors;
- controller modes;
- telemetry;
- CLI commands.

---

## Rule 5 — Discrete applied inputs are held constant across one RK4 step

Determine applied actuation/environment input once for the tick.

Use that same discrete input for:

```text
k1
k2
k3
k4
```

unless a future explicitly continuous time-dependent environment function is intentionally designed.

Do not run controller state updates four times per simulation tick.

---

## Rule 6 — Engine validates initial conditions before stepping

A bad state should fail at tick 0, not several steps later.

---

## Rule 7 — Engine validates each completed next state

At minimum:

```text
finite
mass physically valid
state structure valid
```

---

## Rule 8 — Simulation has a hard maximum duration

A run cannot become infinite because later terminal logic fails.

---

## Rule 9 — Same deterministic dependencies produce the same result

No internal randomness.

No wall-clock dependence.

No unordered global mutable state.

---

## Rule 10 — Engine owns truth-state progression

Only the engine commits the next `VehicleState` during normal runtime.

Sensors/controllers/telemetry must never mutate truth state directly.

---

## Rule 11 — Integrator operates on copies/new values

Do not mutate the current `VehicleState` in place during RK4 stages.

Intermediate stage states must be temporary values.

---

## Rule 12 — State-vector ordering is centralized

If numerical arrays are used:

```text
[x, y, vx, vy, theta, omega, mass]
```

must be defined and converted in one well-tested location.

---

## Rule 13 — Runtime failures stop safely

A NaN/Inf or impossible state must terminate the engine.

Do not continue and write hundreds of corrupt states.

---

## Rule 14 — Mission failure is not a simulation exception

Later:

```text
hard landing
missed target
controlled abort
```

are domain outcomes.

The engine raises errors only for invalid runtime operation.

---

## Rule 15 — Exact tick ordering is architecture

When later subsystems connect, the documented order must be preserved unless a deliberate architecture decision changes it.

A timing-order change can alter:

- sensor readings;
- controller actions;
- fault timing;
- telemetry;
- mission result.

Therefore it must be treated like a behavior change, not a refactor.

---

## RK4 pseudocode

Recommended generic implementation:

```python
def rk4_step(
    state: VehicleState,
    *,
    dt: float,
    derivative_fn: DerivativeFunction,
) -> VehicleState:
    y0 = state_to_vector(state)

    k1 = derivative_to_vector(
        derivative_fn(vector_to_state(y0))
    )

    k2 = derivative_to_vector(
        derivative_fn(
            vector_to_state(y0 + 0.5 * dt * k1)
        )
    )

    k3 = derivative_to_vector(
        derivative_fn(
            vector_to_state(y0 + 0.5 * dt * k2)
        )
    )

    k4 = derivative_to_vector(
        derivative_fn(
            vector_to_state(y0 + dt * k3)
        )
    )

    y_next = y0 + (dt / 6.0) * (
        k1 + 2.0 * k2 + 2.0 * k3 + k4
    )

    return vector_to_state(y_next)
```

The actual derivative callable can close over:

- applied actuation;
- vehicle parameters;
- environment inputs;
- current simulation time if required.

**Decision:** Keep the integrator generic enough to test with simple ODEs, but do not create a large plugin framework.

---

## Engine pseudocode — Feature 02 stage

Before later subsystems:

```python
tick = 0
state = initial_state

validate_startup(...)

while tick < max_ticks:
    sim_time = tick * dt

    if terminal_condition(state, sim_time):
        break

    actuation = input_provider(state, sim_time)
    environment = environment_provider(state, sim_time)

    derivative_fn = make_derivative_fn(
        actuation=actuation,
        params=params,
        environment=environment,
    )

    next_state = rk4_step(
        state,
        dt=dt,
        derivative_fn=derivative_fn,
    )

    next_state = enforce_physical_bounds(
        next_state,
        params,
    )

    validate_runtime_state(
        next_state,
        ...
    )

    state = next_state
    tick += 1
```

**Decision:** A callback/provider used during Feature 02 is only a temporary clean boundary. Do not build a general dependency-injection framework.

---

## Engine pseudocode — future full ordering contract

Later, conceptually:

```text
current tick/time
    |
    +--> safety/terminal checks
    +--> fault activation
    +--> sensor sampling
    +--> sensor fault effects
    +--> measurement snapshot
    +--> mission-state update
    +--> controller update
    +--> actuator update
    +--> actuator fault effects
    +--> freeze applied input for this dt
    +--> RK4 truth-state advancement
    +--> post-step invariant checks
    +--> telemetry/event capture
    +--> increment tick
```

Feature 02 must make this future composition possible without rewriting the integrator.

---

## Edge cases

### `dt` larger than `max_time`

The engine still needs deterministic behavior.

**Decision:** Derive max ticks predictably and document whether one step is allowed.

Recommended:

```python
max_ticks = ceil(max_time / dt)
```

but do not allow reported final time to silently claim an exact `max_time` if the final tick lies beyond it.

**[Open Question]** Final maximum-time convention should be locked with tests: either require `max_time / dt` to be integer-like for scenarios, or explicitly permit the final tick to reach/exceed the configured bound.

**Recommended decision:** For AstraLoop scenario configs, validate that `max_time / dt` is integer-like within tolerance. This gives simple exact timing semantics.

---

### Very small `dt`

Numerically valid but may create an excessive number of ticks.

Do not reject solely for performance unless a practical guard is needed.

---

### Very large `dt`

May be numerically unstable.

Feature 02 can validate positivity but should not pretend to know the physically supported maximum `dt` before Numerical Verification.

Document the supported tested timestep later.

---

### Derivative raises an error during `k2`, `k3`, or `k4`

Abort the step.

Do not partially commit state.

---

### Intermediate RK4 state below dry mass

Because RK4 constructs temporary states, an intermediate stage can theoretically cross a physical boundary.

**Decision:** The derivative function must remain safe around the dry-mass boundary, and final physical bounds must be enforced after the completed step.

Do not introduce adaptive event solving in the MVP.

---

### Intermediate non-finite state

Abort immediately.

---

### Final state is identical to current state

This is valid if the system genuinely has zero derivatives.

Do not treat no change as an error.

---

### Terminal condition true at tick 0

Engine returns without integrating.

This supports initial states that are already terminal/invalid according to a later termination hook.

The exact domain interpretation belongs outside the engine.

---

### Maximum duration reached without mission termination

Return a normal engine termination reason such as:

```text
MAX_TIME
```

Later mission validation can decide that this is a failed mission.

---

# 6. Acceptance Criteria

## AC-01 — Clock begins at zero

**Given** a valid simulation configuration and initial state  
**When** the engine is initialized  
**Then** `tick == 0` and `sim_time == 0.0`.

---

## AC-02 — Time is derived from tick

**Given** `dt = 0.02` and `tick = 125`  
**When** simulation time is requested  
**Then** it equals `125 * 0.02`.

---

## AC-03 — One step advances exactly one tick

**Given** an initialized engine at tick `n`  
**When** one successful step completes  
**Then** the committed tick is `n + 1`.

---

## AC-04 — State/time alignment after one step

**Given** tick `0`, `dt = 0.02`, and a valid initial state  
**When** one step completes  
**Then** the new state represents simulation time `0.02` and the engine tick is `1`.

---

## AC-05 — Invalid timestep is rejected

**Given** `dt <= 0` or non-finite `dt`  
**When** simulation configuration is validated  
**Then** execution does not begin and a clear configuration error is raised.

---

## AC-06 — Invalid maximum duration is rejected

**Given** `max_time <= 0` or non-finite `max_time`  
**When** simulation configuration is validated  
**Then** execution does not begin.

---

## AC-07 — RK4 integrates a known scalar equation accurately

**Given** a simple ODE with known analytical solution  
**When** the custom RK4 integrator advances the state using a documented test timestep  
**Then** the numerical value matches the analytical result within an explicit tolerance.

---

## AC-08 — RK4 supports vector state

**Given** a deterministic multi-variable ODE  
**When** RK4 performs a step  
**Then** every state component is advanced according to the RK4 calculation.

---

## AC-09 — RK4 does not mutate the input state

**Given** an immutable or copied current state  
**When** `rk4_step(...)` completes  
**Then** the original state remains unchanged.

---

## AC-10 — RK4 evaluates four stages

**Given** a derivative function instrumented for a unit test  
**When** one RK4 step executes  
**Then** exactly four derivative evaluations occur.

---

## AC-11 — Applied tick input is held constant across RK4 stages

**Given** a fixed applied actuation selected for one engine tick  
**When** RK4 evaluates `k1` through `k4`  
**Then** all four stages use that same applied discrete actuation.

---

## AC-12 — Gravity-only flight evolves numerically

**Given** Feature 01 dynamics, zero throttle, and a valid initial state above ground  
**When** the engine advances multiple steps  
**Then** vertical velocity and position change according to the dynamics rather than hard-coded coordinates.

---

## AC-13 — Upright symmetry is preserved

**Given** `x = 0`, `vx = 0`, upright attitude, zero gimbal, no external horizontal force, and positive thrust  
**When** the engine advances the state  
**Then** horizontal drift remains zero/within documented numerical tolerance.

---

## AC-14 — Gimbaled input changes trajectory

**Given** the same initial state as AC-13 but a nonzero applied gimbal  
**When** the engine advances multiple steps  
**Then** the resulting trajectory differs in the direction predicted by Feature 01's dynamics convention.

---

## AC-15 — Initial invalid state fails before integration

**Given** a non-finite or materially invalid initial `VehicleState`  
**When** a run starts  
**Then** no RK4 step is executed.

---

## AC-16 — Non-finite RK4 derivative aborts safely

**Given** a derivative stage returns NaN or Inf  
**When** a step is attempted  
**Then** the engine raises `SimulationError` and does not commit a next state.

---

## AC-17 — Non-finite final state aborts safely

**Given** RK4 produces a non-finite next state  
**When** post-step validation runs  
**Then** execution stops with `SimulationError`.

---

## AC-18 — Small dry-mass overshoot is bounded

**Given** a numerical step produces a mass only within the documented tolerance below dry mass  
**When** post-step physical bounds are enforced  
**Then** mass is set to exactly dry mass.

---

## AC-19 — Material dry-mass violation fails

**Given** a next state is materially below dry mass  
**When** runtime invariant validation runs  
**Then** a simulation invariant error is raised.

---

## AC-20 — Run cannot exceed deterministic maximum ticks

**Given** no earlier terminal condition occurs  
**When** the run reaches its configured maximum duration  
**Then** the engine terminates with a maximum-time/max-tick reason.

---

## AC-21 — Same deterministic inputs reproduce the same final state

**Given** identical initial state, configuration, parameters, and input-provider behavior  
**When** the simulation is run twice  
**Then** final tick, final time, termination reason, and numerical final state match within deterministic floating-point expectations.

---

## AC-22 — Wall-clock speed does not change simulation results

**Given** identical deterministic inputs  
**When** the simulation executes on different wall-clock schedules or machine load  
**Then** the simulation-time result is unchanged.

---

## AC-23 — No `sleep()` is used for physics timing

**Given** the engine implementation  
**When** its runtime timing logic is inspected/tested  
**Then** physics progression depends on tick and `dt`, not `time.sleep()`.

---

## AC-24 — Engine contains no scenario-name branches

**Given** the simulation-engine source  
**When** it is inspected  
**Then** it does not contain behavior such as `if scenario_name == ...`.

---

## AC-25 — Integrator is mission-logic independent

**Given** `simulation/integrator.py`  
**When** dependencies are inspected  
**Then** it does not import sensors, control, actuators, mission, faults, telemetry, validation, or CLI code.

---

## AC-26 — Engine does not write telemetry files

**Given** a core engine test  
**When** it executes without a telemetry dependency  
**Then** the simulation can run successfully without creating CSV/JSON/PNG artifacts.

---

## AC-27 — Terminal-at-start condition performs zero integration steps

**Given** an injected terminal predicate that is true at tick `0`  
**When** the engine runs  
**Then** the result returns at tick `0` without calling RK4.

---

## AC-28 — Failed step does not partially commit state

**Given** an error occurs during any RK4 stage or post-step invariant check  
**When** the step aborts  
**Then** the previously committed engine state/tick remain the last valid committed values.

---

## AC-29 — State-vector conversion is round-trip safe

**Given** a valid `VehicleState`  
**When** it is converted to the internal numerical vector and back  
**Then** all named fields match the original within exact/appropriate floating-point expectations.

---

## AC-30 — Internal vector ordering is single-source

**Given** the codebase  
**When** state/vector mapping is inspected  
**Then** the `[x, y, vx, vy, theta, omega, mass]` ordering is defined centrally rather than duplicated through magic numeric indices.

---

## AC-31 — The engine remains local and headless

**Given** a clean test environment  
**When** the engine tests run  
**Then** no browser, database, cloud service, GUI, or external hardware is required.

---

## AC-32 — Production runtime does not call SciPy integrator

**Given** the core production simulation path  
**When** it is inspected/executed  
**Then** truth-state advancement uses the project-owned RK4 implementation, not `scipy.integrate.solve_ivp`.

---

# 7. Test Plan

## Unit tests

### `tests/unit/test_integrator.py`

Required areas:

```text
test_rk4_scalar_known_solution
test_rk4_vector_system
test_rk4_does_not_mutate_input
test_rk4_calls_derivative_four_times
test_rk4_constant_derivative_exact_step
test_rk4_zero_derivative_preserves_state
test_state_vector_round_trip
test_derivative_vector_ordering
test_non_finite_k1_rejected
test_non_finite_k2_rejected
test_non_finite_k3_rejected
test_non_finite_k4_rejected
```

---

### `tests/unit/test_simulation_clock.py`

If a clock helper exists:

```text
test_clock_starts_at_zero
test_time_is_tick_times_dt
test_invalid_dt_rejected
test_tick_must_be_nonnegative
```

If no separate class exists, these tests may live in `test_engine.py`.

---

### `tests/unit/test_engine.py`

Recommended:

```text
test_engine_rejects_invalid_dt
test_engine_rejects_invalid_max_time
test_engine_rejects_invalid_initial_state
test_one_step_advances_one_tick
test_state_time_alignment_after_step
test_terminal_at_start_skips_integration
test_max_time_terminates_run
test_failed_step_does_not_commit_state
test_non_finite_next_state_aborts
test_small_mass_overshoot_clamps_to_dry_mass
test_material_mass_violation_aborts
test_identical_runs_are_deterministic
```

---

## Numerical behavior tests

These are still Feature 02 tests when they use known equations, not SciPy.

### Known scalar ODE

Example:

```text
dy/dt = -2y
y(0) = 10
```

Analytical:

```text
y(t) = 10e^(-2t)
```

Use this to confirm basic RK4 correctness.

### Constant derivative

Example:

```text
dy/dt = 3
```

RK4 should reproduce the exact linear step to floating-point tolerance.

### Simple harmonic oscillator

Optional but valuable vector test:

```text
dx/dt = v
dv/dt = -x
```

Use over a short horizon.

Do not overbuild numerical theory here.

---

## Integration tests with Feature 01

Recommended file:

```text
tests/integration/test_dynamics_engine.py
```

### Gravity-only

- initial altitude > 0;
- zero throttle;
- run short duration;
- assert downward velocity develops;
- assert finite state;
- assert expected tick count.

### Upright constant thrust

- zero initial horizontal state;
- upright;
- zero gimbal;
- assert horizontal symmetry;
- assert vertical acceleration effect.

### Constant gimbal

- compare against upright run;
- assert nonzero horizontal response;
- assert angular response.

### Fuel depletion

- configure small fuel margin;
- run powered;
- assert mass never ends below dry mass;
- assert finite state.

---

## Integration tests with later features

Add only when those features exist.

Examples:

```text
engine -> actuator output
engine -> sensor sampling
engine -> telemetry observer
fault activation at exact tick
controller update at configured tick cadence
```

Feature 02 does not implement those components now.

---

## Tests intentionally deferred to Numerical Verification

Do **not** duplicate the full Feature 13 Numerical Verification scope here.

Deferred:

- RK4 vs SciPy `solve_ivp`;
- formal step-refinement/convergence tables;
- documented numerical error tolerance for the flight model;
- stability envelope studies;
- production `dt` justification.

Feature 02 must be locally correct and testable, while Feature 13 independently verifies numerical fidelity.

---

## Manual QA checklist

- [ ] `sim_time` is derived from integer tick.
- [ ] No authoritative `sim_time += dt` accumulation exists.
- [ ] No `sleep()` controls physics.
- [ ] RK4 code is short enough to inspect completely.
- [ ] RK4 uses correct `1, 2, 2, 1` weights.
- [ ] Half-step factors are correct for `k2` and `k3`.
- [ ] Full-step factor is correct for `k4`.
- [ ] Public boundaries use named state data.
- [ ] Raw state indices are centralized.
- [ ] Current state is not mutated in place.
- [ ] A failed RK4 stage does not commit partial state.
- [ ] Applied discrete input is held constant across one step.
- [ ] Initial state is validated.
- [ ] Post-step state is validated.
- [ ] Maximum run duration exists.
- [ ] Engine does not contain controller logic.
- [ ] Engine does not contain sensor logic.
- [ ] Integrator does not contain fault logic.
- [ ] Engine does not write telemetry files directly.
- [ ] No SciPy integration occurs in production runtime.
- [ ] All engine/integrator tests pass.

---

## Demo verification checklist

- [ ] Reviewer can see one clear line deriving `sim_time = tick * dt`.
- [ ] Reviewer can understand the RK4 implementation without framework indirection.
- [ ] Same open-loop run produces the same final result twice.
- [ ] Gravity-only test produces expected physical change.
- [ ] Upright thrust preserves horizontal symmetry.
- [ ] Nonzero gimbal changes trajectory.
- [ ] Engine stops at deterministic max duration.
- [ ] Invalid/non-finite state fails safely.
- [ ] `pytest` proves integrator and engine behavior.
- [ ] Demo does not depend on a GUI or network.

---

# 8. Portfolio Value

## How this feature helps the project stand out

A large number of portfolio simulations outsource all numerical behavior to a black-box solver and then focus mainly on plots.

AstraLoop can make a stronger engineering argument:

> "I implemented the simulation scheduler and fixed-step RK4 runtime myself because the project combines continuous dynamics with discrete software behavior. I used an integer tick as the source of simulation time so sensor delays, controller updates, faults, state transitions, and telemetry can all be deterministic."

That creates multiple valuable discussion points:

- continuous vs discrete systems;
- numerical integration;
- deterministic simulation;
- timing semantics;
- reproducibility;
- error handling;
- module boundaries;
- verification strategy.

---

## What to mention in README

Recommended wording:

> **Deterministic simulation engine:** AstraLoop advances the 2D truth model using a project-owned fixed-step RK4 integrator. Simulation time is derived from an integer tick (`time = tick × dt`) rather than wall-clock time, giving later sensors, controllers, faults, and telemetry one reproducible timing model.

Also mention:

- fixed `dt`;
- no `sleep()` for simulation latency;
- RK4 production runtime;
- SciPy reserved for independent verification;
- post-step invariant checks;
- maximum simulation duration.

Avoid claiming numerical accuracy until measured by Numerical Verification.

---

## What to mention in interviews

### Why build your own RK4?

> "I wanted the core numerical behavior to be transparent and testable. RK4 is compact enough to implement correctly, accurate enough for this simplified model, and gives me a clear production stepper that I can verify independently against SciPy later."

### Why fixed step?

> "AstraLoop is hybrid continuous/discrete software. Sensors, delays, controllers, actuator updates, mission transitions, faults, and telemetry all need consistent timing. A fixed tick gives every component the same deterministic clock."

### Why integer ticks?

> "I did not want fault or sampling behavior to depend on floating-point time accumulation. I store an integer tick and calculate simulation time as tick times dt."

### Why not `solve_ivp`?

> "Adaptive ODE solvers are excellent for continuous systems, but I did not want an adaptive internal scheduler to define when discrete flight-software events occur. I still use SciPy later as an independent numerical oracle."

### How do discrete commands interact with RK4?

> "The actuator output is selected once for the simulation tick and held constant across the four RK4 stages. That preserves a clean boundary between discrete software updates and continuous physical integration."

### How did you prevent numerical failures from corrupting the run?

> "The engine validates the initial state, checks RK4 stages/final state for non-finite values, enforces post-step physical bounds, and never commits a partially failed step."

---

# 9. Implementation Notes for Codex

## Likely files/folders

Primary:

```text
src/astraloop/simulation/integrator.py
src/astraloop/simulation/engine.py
src/astraloop/simulation/dynamics.py       # consume only; Feature 01 owns equations
src/astraloop/model/state.py               # consume VehicleState
src/astraloop/model/results.py
src/astraloop/config/schema.py             # add numerical config only if present

tests/unit/test_integrator.py
tests/unit/test_engine.py
tests/integration/test_dynamics_engine.py
```

Optional:

```text
src/astraloop/simulation/clock.py
```

Only create `clock.py` if it genuinely improves clarity.

Do not create one-file-per-concept architecture unnecessarily.

---

## Build order

### Step 1 — Confirm Feature 01 contract

Before engine implementation, confirm:

- `VehicleState`;
- derivative output;
- dynamics callable;
- physical-bound helper or invariant rules;
- internal units.

Do not duplicate physics equations in the engine.

---

### Step 2 — Implement state/vector conversion

Create and test the single canonical mapping:

```text
[x, y, vx, vy, theta, omega, mass]
```

Keep it local to numerical infrastructure.

---

### Step 3 — Implement generic RK4

Start with test-only ODEs.

Do not connect the full engine until RK4 unit tests pass.

---

### Step 4 — Implement `SimulationConfig`

Validate:

```text
dt
max_time
derived max_ticks
```

Keep schema small.

---

### Step 5 — Implement tick/time semantics

Ensure:

```python
time = tick * dt
```

and test state/time alignment.

---

### Step 6 — Build minimal engine around constant/input-provider actuation

Connect:

```text
engine
 -> RK4
 -> Feature 01 dynamics
```

No sensor/controller code yet.

---

### Step 7 — Add startup validation

Fail before tick 0 integration when configuration/state is invalid.

---

### Step 8 — Add post-step invariant handling

Include:

- finite check;
- dry-mass bound contract;
- partial-step failure behavior.

---

### Step 9 — Add deterministic termination

Implement:

- terminal predicate extension point;
- max-time/max-tick stop.

Do not implement mission states.

---

### Step 10 — Add minimal result object

Return:

```text
final tick
final time
final state
termination reason
```

Do not build the future telemetry schema here.

---

### Step 11 — Add Feature 01 integration tests

Gravity, vertical thrust, gimbal coupling, fuel/dry-mass behavior.

---

### Step 12 — Freeze engine timing contract

Document the eventual full per-tick ordering in code/docs before later subsystem features begin.

Changing ordering later should require deliberate test updates.

---

## Risks

### Risk 1 — Incorrect RK4 stage math

Potential bugs:

- wrong half-step;
- using `k1` where `k2` is required;
- wrong final weights;
- mutating the base state.

**Mitigation:** known analytical ODE tests before flight dynamics integration.

---

### Risk 2 — Time off-by-one errors

Example:

- state is at `t=0.02` but telemetry later labels it `0.00`.

**Mitigation:** define and test exactly when tick increments and what time the committed state represents.

---

### Risk 3 — Repeated floating-point time accumulation

**Mitigation:** integer tick is authoritative.

---

### Risk 4 — Running discrete software inside RK4 stages

This can accidentally update:

- PID integrals four times;
- sensor buffers four times;
- mission logic four times.

**Mitigation:** discrete subsystem update once per tick; hold applied physical inputs constant across RK4 sub-stages.

---

### Risk 5 — Engine becomes a giant god object

As later features are added, `engine.py` can become overloaded.

**Mitigation:** engine coordinates; modules own behavior.

The engine should call:

```text
sensor suite
mission state machine
controller
actuator model
fault manager
telemetry recorder
```

rather than implement their internals.

---

### Risk 6 — Premature generic scheduler framework

Do not build:

- arbitrary event queues;
- plugin registries;
- asynchronous schedulers;
- actor systems;
- message buses.

The fixed tick is enough for the MVP.

---

### Risk 7 — Timestep chosen by appearance

A simulation can "look fine" while being numerically inaccurate.

**Mitigation:** Feature 02 only provides the timestep mechanism; later Numerical Verification must justify the supported `dt`.

---

### Risk 8 — Engine silently corrects serious invalid state

Over-clamping can hide bugs.

**Mitigation:** only clamp explicitly documented tiny numerical boundary overshoots; raise on material violations.

---

## What not to change

While implementing Feature 02, Codex should **not**:

- redesign the Feature 01 flight equations;
- add aerodynamic forces;
- add new 3D state;
- add adaptive timestep logic;
- use `solve_ivp` as the production engine;
- implement formal SciPy comparison tests yet;
- implement sensor models;
- implement PID/control logic;
- implement actuator saturation/lag;
- implement mission-state transitions;
- implement fault definitions;
- implement scenario-file loading beyond any minimal config touchpoint already present;
- implement telemetry persistence;
- implement plots;
- implement mission validation;
- implement a polished CLI;
- add multiprocessing;
- add async execution;
- add a job queue;
- add a database;
- add cloud services;
- add real-time sleeping;
- add GUI behavior.

When later-feature dependencies do not exist, use small temporary typed callbacks/no-op boundaries.

---

# Feature-Specific Definition of Done

Feature 02 is complete when:

- [ ] A project-owned classical RK4 stepper exists.
- [ ] RK4 passes known-equation unit tests.
- [ ] RK4 supports AstraLoop's vector vehicle state.
- [ ] Public state boundaries remain named/typed.
- [ ] State/vector ordering is centralized and tested.
- [ ] The engine owns an integer simulation tick.
- [ ] Simulation time is calculated as `tick * dt`.
- [ ] `dt` is fixed for the run.
- [ ] Invalid `dt` and `max_time` fail before execution.
- [ ] Initial state is validated before integration.
- [ ] Applied discrete inputs are held constant across one RK4 step.
- [ ] Each successful step advances truth state by exactly one `dt`.
- [ ] A successful step advances exactly one tick.
- [ ] Failed steps do not partially commit state.
- [ ] Runtime state is checked for NaN/Inf.
- [ ] Post-step physical mass bounds are enforced.
- [ ] Material physical invariant violations stop the simulation.
- [ ] A deterministic maximum duration/tick limit exists.
- [ ] Identical deterministic runs reproduce the same final result.
- [ ] The engine works without wall-clock timing or `sleep()`.
- [ ] The integrator contains no mission/controller/sensor/fault logic.
- [ ] The engine writes no telemetry files directly.
- [ ] The production runtime does not use SciPy integration.
- [ ] Feature 01 gravity/thrust/gimbal integration tests pass.
- [ ] The future per-tick orchestration order is documented.
- [ ] No adaptive solver, scheduler framework, SaaS system, database, or GUI has been added.

---

# Open Questions

1. **[Open Question] What production timestep will AstraLoop officially support?**  
   The architecture examples use `dt = 0.02`, but final support must be justified by Numerical Verification.

2. **[Open Question] What exact dry-mass overshoot tolerance should the engine use?**  
   This must be small, documented, and tested.

3. **[Open Question] Must `max_time / dt` be an integer number of ticks?**  
   **Recommended decision:** yes, within floating-point tolerance, for scenario configurations. This keeps event timing and final-time semantics simple.

4. **[Open Question] How should physical ground contact modify the truth state?**  
   Engine safety and mission outcome policy must be separated. Finalize this together with Mission State Machine and Mission Validation.

5. **[Open Question] Will later controllers/sensors run every simulation tick or at configurable integer tick multiples?**  
   Feature 02 should support integer-tick cadence later, but the actual policies belong to their respective features.

6. **[Open Question] Should `SimulationSnapshot` be emitted before integration, after integration, or both for telemetry?**  
   The architecture's final telemetry timing convention should be fixed when Telemetry & Event Logging is specified. The engine's state/time alignment rules in this document must remain consistent.

---

# Move On When

- [ ] RK4 has clear acceptance criteria and passing tests.
- [ ] Tick/time semantics are deterministic and tested.
- [ ] Feature 01 dynamics can be advanced through multiple numerical steps.
- [ ] The engine has a clear reviewer demo path.
- [ ] The feature clearly proves numerical simulation and deterministic-systems skill.
- [ ] Numerical runtime errors fail safely.
- [ ] The engine remains independent of later sensors/controllers/mission/fault/telemetry implementations.
- [ ] The scope remains a finishable local Python project.
- [ ] No unnecessary SaaS, infrastructure, adaptive scheduling, or GUI system has been introduced.
