# Feature 01 — 2D Flight Dynamics

> **Project:** AstraLoop — Python Software-in-the-Loop Flight Control & Validation System  
> **Feature:** 2D Flight Dynamics  
> **Document path:** `docs/features/01-2d-flight-dynamics.md`  
> **Status:** Implementation specification  
> **Primary goal:** Define the vehicle's planar physical model and its software contract without expanding the numerical simulation engine, sensors, controllers, actuator dynamics, mission logic, faults, telemetry system, or CLI.

---

## Scope Boundary

**[Confirmed]** AstraLoop is a local, Python-first software-in-the-loop flight-control validation project. The vehicle must evolve from numerical physics rather than scripted coordinates, and the project intentionally uses a simplified **2D planar** model instead of full 3D/6-DOF dynamics.

**[Decision]** This feature owns only the **physical state representation and equations of motion** for the simplified vehicle.

It owns:

- planar position and velocity;
- pitch angle and angular rate;
- current vehicle mass;
- gravity;
- thrust magnitude and direction as physical inputs;
- simplified pitch torque from applied gimbal;
- fuel/mass depletion;
- optional externally supplied disturbance force/torque inputs;
- physical invariants and dynamics-input validation;
- deterministic derivative calculations.

It does **not** own:

- RK4 or any other numerical stepping algorithm;
- simulation tick scheduling;
- controller logic;
- sensor noise, delay, bias, or faults;
- actuator saturation, lag, or slew limits;
- mission-state transitions;
- fault activation logic;
- telemetry persistence;
- scenario loading;
- plotting;
- CLI commands;
- numerical comparison against SciPy.

Those belong to later AstraLoop features and should consume this feature through explicit interfaces.

---

# 1. Feature Overview

## Feature name

**2D Flight Dynamics**

## One-sentence description

**[Decision]** Implement a deterministic planar rigid-body vehicle model whose horizontal motion, vertical motion, pitch, angular rate, and mass evolve from gravity, applied thrust, gimbal-induced torque, fuel consumption, and optional external forces.

## Detailed description

AstraLoop needs a physical "truth" model that represents what the simulated vehicle is actually doing.

The minimum vehicle state is:

```text
x       horizontal position [m]
y       vertical position [m]
vx      horizontal velocity [m/s]
vy      vertical velocity [m/s]
theta   pitch angle [rad]
omega   pitch angular rate [rad/s]
mass    current total mass [kg]
```

**[Decision]** Simulation time is **not** stored inside `VehicleState`. The simulation engine owns the deterministic simulation clock. This keeps the dynamics state focused on physical quantities and prevents two competing sources of time.

The dynamics module receives:

1. the current `VehicleState`;
2. immutable vehicle parameters;
3. the **already-applied** actuator state for the current instant;
4. environment/external force inputs.

It returns the time derivative of the vehicle state:

```text
dx/dt
dy/dt
dvx/dt
dvy/dt
dtheta/dt
domega/dt
dmass/dt
```

The separate Numerical Simulation Engine will later integrate these derivatives over a fixed timestep.

### Coordinate and angle convention

**[Decision]** Use a deliberately simple, controller-friendly coordinate system:

```text
+x  = horizontal right
+y  = vertical up
theta = 0 rad when the vehicle is upright
positive theta = clockwise/rightward pitch
omega = d(theta)/dt using the same sign convention
```

This convention makes an upright vehicle easy to represent and keeps common control setpoints near `theta = 0`.

With no gimbal deflection, the thrust direction follows vehicle pitch.

For total thrust-vector angle:

```text
alpha = theta + gimbal_angle
```

the thrust components are:

```text
Fx_thrust = thrust * sin(alpha)
Fy_thrust = thrust * cos(alpha)
```

Therefore:

- `alpha = 0` produces purely upward thrust;
- positive `alpha` produces positive/rightward horizontal thrust;
- negative `alpha` produces negative/leftward horizontal thrust.

**Justification:** A vertical-zero convention is easier to understand during landing/control work than a standard mathematical angle measured from the positive x-axis. The nonstandard sign convention must be explicitly documented and protected by tests so it never becomes ambiguous.

### Translational equations

Let:

```text
m  = current vehicle mass
T  = applied thrust magnitude
g  = gravitational acceleration
Fx_external = optional externally supplied horizontal force
Fy_external = optional externally supplied vertical force
```

Then:

```text
dx/dt  = vx
dy/dt  = vy

dvx/dt = (T * sin(theta + gimbal_angle) + Fx_external) / m

dvy/dt = (T * cos(theta + gimbal_angle) + Fy_external) / m - g
```

**[Decision]** Aerodynamic lift and drag are excluded from the MVP dynamics model.

**Justification:** Drag, atmospheric density, aerodynamic coefficients, and angle-of-attack modeling add substantial physics scope without materially improving the software-engineering signal targeted by AstraLoop. The architecture still permits later environment forces to be supplied through `Fx_external` and `Fy_external`.

### Rotational equation

Use a simplified planar pitch model:

```text
dtheta/dt = omega

domega/dt = total_torque / moment_of_inertia
```

The nominal gimbal-generated torque is:

```text
gimbal_torque =
    thrust_lever_arm
    * thrust
    * sin(gimbal_angle)
```

and:

```text
total_torque = gimbal_torque + external_torque
```

**[Decision]** By model convention, a positive gimbal angle produces a positive pitch torque.

**Justification:** AstraLoop does not need a full propulsion-system rigid-body geometry model. The important requirement is a documented, deterministic coupling between applied thrust-vector deflection and pitch dynamics. Unit tests must lock the sign convention.

### Moment of inertia

**[Decision]** Use one configured constant `moment_of_inertia` for the MVP.

**Justification:** Vehicle mass changes during the mission, but modeling a dynamically changing inertia tensor requires assumptions about fuel-tank geometry and center-of-mass movement that are outside the intended portfolio scope. A constant planar inertia is sufficient to demonstrate rotational dynamics and closed-loop pitch control.

**[Open Question]** The final nominal value for `moment_of_inertia` is not fixed by the planning documents and must be chosen during vehicle-parameter calibration.

### Thrust and throttle input

The dynamics feature receives an **applied throttle value**, not the raw controller request.

Nominal thrust:

```text
T = applied_throttle * max_thrust
```

where applied throttle is expected to satisfy:

```text
0.0 <= applied_throttle <= 1.0
```

**[Decision]** This feature validates the physical input range but does not implement actuator clipping, response lag, rate limits, or command saturation behavior.

**Justification:** Those behaviors belong to the separate **Actuator Modeling** feature. The dynamics module should consume the actuator's physical output, not duplicate actuator behavior.

### Fuel and mass depletion

Use a simple maximum mass-flow parameter:

```text
fuel_mass_flow =
    applied_throttle * max_mass_flow_rate
```

while fuel remains.

Therefore:

```text
dmass/dt = -fuel_mass_flow
```

If:

```text
mass <= dry_mass
```

then:

```text
effective thrust = 0
dmass/dt = 0
```

**[Decision]** Use `max_mass_flow_rate` rather than requiring an engine-specific thermodynamic or specific-impulse model.

**Justification:** The project goal is simulation/validation software engineering, not high-fidelity propulsion modeling. An explicit mass-flow parameter is easy to configure, test, and explain while still making vehicle mass evolve during flight.

### Dry-mass invariant

The physical contract is:

```text
mass >= dry_mass > 0
```

**[Decision]** The dynamics module exposes a helper for enforcing/checking physical bounds after a numerical step, but the Numerical Simulation Engine remains responsible for calling it at the correct point in the stepping process.

This avoids letting the dynamics feature secretly own the integrator.

### External force and torque hook

The dynamics function may receive:

```text
external_force_x
external_force_y
external_torque
```

with default values of zero.

**[Decision]** These values are plain physical inputs. This feature does not decide when a disturbance or fault activates.

**Justification:** Later fault/disturbance systems can alter physical inputs without introducing scenario-name conditionals inside `dynamics.py`.

---

## Why it matters

**[Confirmed]** The project selection and master blueprint identify real numerical state evolution as a non-negotiable difference between AstraLoop and a scripted rocket animation.

This feature matters because every major system later depends on it:

```text
actuator output
      |
      v
2D flight dynamics
      |
      v
true vehicle state
      |
      v
simulated sensors
```

Without a clean truth model:

- closed-loop control is meaningless;
- sensor models have nothing physical to observe;
- actuator commands cannot produce real consequences;
- mission validation becomes scripted;
- fault scenarios become cosmetic.

---

## Skill it demonstrates

A successful implementation visibly demonstrates:

- Python domain modeling;
- NumPy/math-based numerical programming;
- mathematical translation into readable software;
- units and sign-convention discipline;
- immutable/typed state modeling;
- pure-function design;
- separation between domain physics and orchestration;
- explicit physical invariants;
- boundary validation;
- deterministic behavior;
- unit testing of numerical software.

---

## Priority

**P0 — Foundational**

**[Decision]** This is the first physical feature to implement because every later runtime feature requires a trustworthy truth-state model.

The project should not begin controller tuning, sensor faults, or mission logic until the basic dynamics tests pass.

---

## Complexity

**High**

The equations are intentionally simplified, but this feature is still high-complexity because mistakes in:

- coordinate conventions;
- signs;
- units;
- thrust-vector decomposition;
- torque direction;
- fuel depletion;
- mass handling;

can propagate into every later feature.

---

# 2. User / Demo Flow

This feature has no independent consumer UI. Its "user" is primarily the Numerical Simulation Engine and, secondarily, the reviewer inspecting tests and resulting trajectories.

## Happy path

1. A valid `VehicleState` is provided.
2. Valid `VehicleParameters` are provided.
3. Applied throttle and gimbal values are provided by the actuator layer.
4. Environment inputs provide gravity and zero or configured external forces.
5. `compute_derivatives(...)` calculates a deterministic state derivative.
6. The Numerical Simulation Engine integrates that derivative.
7. The next true state is produced.
8. The process repeats for the mission.

Expected behavior:

- zero/low thrust causes descent under gravity;
- sufficient upright thrust produces upward acceleration;
- rightward pitch/gimbal produces rightward acceleration;
- gimbal torque changes angular rate;
- fuel use reduces mass;
- dry mass is never physically crossed after state bounds are enforced.

---

## First-time path

For the first successful implementation:

1. Create the state/parameter dataclasses.
2. Run a derivative calculation for an upright vehicle with zero throttle.
3. Verify:
   - `dx/dt == vx`;
   - `dy/dt == vy`;
   - `dvx/dt == 0`;
   - `dvy/dt == -g`;
   - `domega/dt == 0`;
   - `dmass/dt == 0`.
4. Add upright thrust.
5. Verify vertical acceleration changes correctly.
6. Add a positive gimbal angle.
7. Verify horizontal acceleration and angular acceleration have the documented signs.
8. Add mass-flow behavior.
9. Run the full unit-test file before connecting the dynamics to the Numerical Simulation Engine.

**[Decision]** This order isolates sign/unit bugs before integration complexity is introduced.

---

## Empty state

There is no meaningful "empty vehicle state."

Invalid or absent required state/parameter data is a configuration/programming error.

Examples:

- missing `VehicleParameters`;
- missing state;
- mass omitted;
- non-finite state field.

Expected behavior:

```text
Raise a clear domain/configuration error before or at the dynamics boundary.
Do not silently invent default physical values.
```

Optional external-force inputs may default to zero.

---

## Error path

### Invalid current state

Examples:

- `mass <= 0`;
- `mass < dry_mass` outside permitted floating-point tolerance;
- NaN position;
- infinite velocity;
- non-finite angle.

Expected:

- reject the state;
- raise a clear dynamics/domain error;
- do not return a derivative containing more invalid values.

### Invalid vehicle parameters

Examples:

- `dry_mass <= 0`;
- `max_thrust < 0`;
- `max_mass_flow_rate < 0`;
- `moment_of_inertia <= 0`;
- `thrust_lever_arm < 0`;
- `gravity < 0`.

Expected:

- fail validation before the simulation starts whenever configuration validation is available.

### Invalid applied actuation

Examples:

- applied throttle `< 0` or `> 1`;
- non-finite gimbal angle;
- non-finite throttle.

Expected:

- reject the input;
- do **not** silently clip it in the dynamics module.

**Justification:** Silent clipping would hide bugs in the later actuator layer.

---

## Demo path for a reviewer

Once the separate Numerical Simulation Engine exists, demonstrate the physics with two tiny open-loop diagnostic runs.

### Demo A — Upright symmetry

Initial conditions:

```text
x = 0
vx = 0
theta = 0
omega = 0
```

Apply:

```text
gimbal = 0
constant throttle > 0
no external force
```

Show:

- vertical motion changes;
- horizontal position remains approximately zero within numerical tolerance;
- pitch remains approximately zero;
- mass decreases while thrust is active.

Reviewer takeaway:

> "The vehicle is not following scripted coordinates. Its trajectory follows the equations and preserves expected symmetry."

### Demo B — Pitch/thrust coupling

Use the same initial conditions but apply a small positive gimbal angle.

Show:

- positive horizontal acceleration;
- positive angular acceleration under the documented convention;
- trajectory diverges from the vertical case;
- changing the physical input changes the physical path.

Reviewer takeaway:

> "Thrust direction and rotational dynamics are coupled, giving the later controller a real system to control."

**Decision:** Keep these as tests or lightweight development fixtures, not as a new permanent product feature or separate GUI.

---

# 3. UX / UI Requirements

## Screens/pages

**[Decision]** No dedicated screen or page is required for 2D Flight Dynamics.

The feature is intentionally headless.

Later features may expose its behavior through:

- CLI-run summaries;
- telemetry;
- diagnostic plots;
- README screenshots.

The dynamics module itself must not know about any of those presentation layers.

---

## Components

No GUI components are required.

Software-facing components:

```text
VehicleState
VehicleStateDerivative
VehicleParameters
AppliedActuation
EnvironmentForces
compute_derivatives(...)
validate_state(...)
validate_parameters(...)
enforce_physical_bounds(...)
```

Naming may be adjusted to match the final codebase, but responsibilities should remain equivalent.

---

## Forms/inputs

No UI form is required.

Later scenario/config files will supply vehicle parameters.

Expected physics-related configuration fields:

```text
dry_mass_kg
max_thrust_n
max_mass_flow_rate_kg_s
moment_of_inertia_kg_m2
thrust_lever_arm_m
gravity_m_s2
```

Initial-state fields:

```text
x_m
y_m
vx_m_s
vy_m_s
theta_deg or theta_rad at configuration boundary
omega_deg_s or omega_rad_s at configuration boundary
initial_mass_kg
```

**[Decision]** Use radians internally.

If human-readable configuration uses degrees, convert exactly once at the configuration boundary.

---

## Buttons/actions

None for this feature.

A later CLI/scenario runner will initiate simulation.

---

## Validation messages

Validation messages should identify the exact field and constraint.

Examples:

```text
Invalid vehicle parameter: moment_of_inertia must be > 0 kg·m².
Invalid state: mass=870.0 kg is below dry_mass=900.0 kg.
Invalid applied throttle: expected value in [0.0, 1.0], received 1.12.
Invalid state: vy must be finite.
```

Avoid generic messages such as:

```text
Bad physics config.
```

---

## Empty states

Not applicable as a visual state.

Missing required physical data is an error, not an empty state.

---

## Loading states

None.

Dynamics evaluation should be fast and synchronous.

---

## Error states

Errors should be surfaced through typed/domain exceptions or validation results, then translated by the later simulation/CLI layers.

Recommended categories:

```text
DynamicsInputError
DynamicsInvariantError
```

**[Decision]** Keep the exception taxonomy small. Do not create a deep exception hierarchy.

---

## Responsive behavior

Not relevant.

AstraLoop is a local engineering tool, not a responsive web application.

---

# 4. Data Requirements

## Entities involved

### `VehicleState`

Represents perfect simulator truth.

Recommended shape:

```python
@dataclass(frozen=True)
class VehicleState:
    x: float
    y: float
    vx: float
    vy: float
    theta: float
    omega: float
    mass: float
```

**[Decision]** Keep it immutable (`frozen=True`) where practical.

**Justification:** Numerical stepping should produce a new state rather than allow unrelated modules to mutate truth in place. This makes state ownership easier to reason about and test.

---

### `VehicleStateDerivative`

Recommended shape:

```python
@dataclass(frozen=True)
class VehicleStateDerivative:
    dx: float
    dy: float
    dvx: float
    dvy: float
    dtheta: float
    domega: float
    dmass: float
```

Alternative: a small NumPy vector may be used inside the integrator adapter.

**[Decision]** Prefer a named derivative record at the public domain boundary and convert to/from NumPy arrays inside numerical code if required.

**Justification:** Named fields make code review and unit tests clearer than magic array indices.

---

### `VehicleParameters`

Recommended fields:

```python
@dataclass(frozen=True)
class VehicleParameters:
    dry_mass: float
    max_thrust: float
    max_mass_flow_rate: float
    moment_of_inertia: float
    thrust_lever_arm: float
```

Possible later additions should require a demonstrated need.

Do not pre-add:

- aerodynamic coefficients;
- atmosphere models;
- center-of-mass tables;
- multiple engines;
- staging parameters.

---

### `AppliedActuation`

This is a **boundary object**, not the Actuator Modeling feature itself.

```python
@dataclass(frozen=True)
class AppliedActuation:
    throttle: float
    gimbal_angle: float
```

Meaning:

- `throttle` is the physical throttle actually applied after later actuator behavior;
- `gimbal_angle` is the physical gimbal angle actually applied.

The dynamics module must not care what controller requested.

---

### `EnvironmentForces`

Recommended:

```python
@dataclass(frozen=True)
class EnvironmentForces:
    gravity: float = 9.80665
    force_x: float = 0.0
    force_y: float = 0.0
    torque: float = 0.0
```

**Decision:** `gravity` may ultimately live in an `EnvironmentConfig`; the exact file placement may differ, but it must arrive at dynamics as explicit data rather than a hidden mutable global.

---

## Fields and units

| Field | Type | Unit | Constraint |
|---|---:|---|---|
| `x` | float | m | finite |
| `y` | float | m | finite |
| `vx` | float | m/s | finite |
| `vy` | float | m/s | finite |
| `theta` | float | rad | finite |
| `omega` | float | rad/s | finite |
| `mass` | float | kg | `>= dry_mass` |
| `dry_mass` | float | kg | `> 0` |
| `max_thrust` | float | N | `>= 0` |
| `max_mass_flow_rate` | float | kg/s | `>= 0` |
| `moment_of_inertia` | float | kg·m² | `> 0` |
| `thrust_lever_arm` | float | m | `>= 0` |
| `throttle` | float | unitless | `[0, 1]` |
| `gimbal_angle` | float | rad | finite; physical limit owned elsewhere |
| `gravity` | float | m/s² | `>= 0` |
| `force_x` | float | N | finite |
| `force_y` | float | N | finite |
| `torque` | float | N·m | finite |

---

## Relationships

```text
VehicleParameters
        |
        v
VehicleState ---> compute_derivatives <--- AppliedActuation
                        ^
                        |
                EnvironmentForces
                        |
                        v
             VehicleStateDerivative
                        |
                        v
         Numerical Simulation Engine
                        |
                        v
                next VehicleState
```

---

## Example seed data

**Important:** The planning documents do not lock realistic vehicle constants. The following values are development/example values only and must not be described as real launch-vehicle specifications.

```toml
[vehicle]
dry_mass_kg = 900.0
initial_mass_kg = 1200.0
max_thrust_n = 18000.0
max_mass_flow_rate_kg_s = 5.0
moment_of_inertia_kg_m2 = 4500.0
thrust_lever_arm_m = 2.0

[environment]
gravity_m_s2 = 9.80665

[initial_state]
x_m = 0.0
y_m = 100.0
vx_m_s = 0.0
vy_m_s = -5.0
theta_deg = 0.0
omega_deg_s = 0.0
```

**[Open Question]** Final nominal development constants must be calibrated together with the later controller so the nominal scenario is controllable without requiring unrealistic gains or actuator behavior.

---

## Local persistence needs

**[Decision]** The 2D Flight Dynamics feature requires **no persistence of its own**.

It should not:

- write CSV;
- write JSON;
- save plots;
- create run directories;
- read TOML directly.

The later scenario/config layer will construct the required objects, and the later telemetry layer will serialize output.

This keeps the dynamics code pure and reusable in tests.

---

# 5. Logic Requirements

## Business/domain rules

Although this is not a business application, the dynamics domain has strict rules.

### Rule 1 — Dynamics is deterministic

Given identical:

```text
state
parameters
applied actuation
environment forces
```

`compute_derivatives(...)` must return the same derivative every time.

No random number generation is permitted inside this module.

---

### Rule 2 — Dynamics does not mutate inputs

The function must not mutate:

- `VehicleState`;
- parameters;
- actuation;
- environment input.

---

### Rule 3 — Dynamics never reads controller state

No imports from controller modules.

No PID state.

No setpoints.

No mission modes.

---

### Rule 4 — Dynamics receives applied actuation, not desired commands

The distinction is:

```text
controller command
      |
      v
Actuator Modeling
      |
      v
applied actuation
      |
      v
2D Flight Dynamics
```

This protects module boundaries.

---

### Rule 5 — No thrust after usable fuel is exhausted

When:

```text
mass <= dry_mass
```

effective thrust and fuel consumption are both zero.

**Decision:** Use a small numerical tolerance when comparing mass to dry mass, but keep the tolerance centralized and documented.

---

### Rule 6 — Mass cannot physically fall below dry mass

The post-step state must be corrected/rejected according to the shared physical-bound contract.

Recommended behavior:

```text
if mass is only slightly below dry_mass because of numerical stepping:
    clamp to dry_mass
elif mass is materially below dry_mass:
    raise an invariant error
```

**[Open Question]** The exact floating-point tolerance should be selected alongside the Numerical Simulation Engine's timestep and tests.

---

### Rule 7 — Internal angle units are radians

All trigonometric dynamics calculations use radians.

No degree values should reach `compute_derivatives(...)`.

---

### Rule 8 — Non-finite values fail loudly

Any NaN/Inf in:

- state;
- parameters;
- actuation;
- environment;
- returned derivatives;

must cause a controlled simulation error rather than silently propagating.

---

### Rule 9 — Ground contact is not a mission-state transition

The dynamics layer may provide a physical helper such as:

```python
is_at_or_below_ground(state, ground_y=0.0) -> bool
```

but it must not set:

```text
LANDED
ABORT
FAIL
```

Those decisions belong to mission/validation logic.

**Decision:** The Numerical Simulation Engine may use the physical ground boundary to prevent continued penetration below the ground, but the state-machine outcome remains outside this feature.

---

### Rule 10 — External disturbance inputs are physics only

A future fault manager may supply forces/torque.

The dynamics layer must not contain logic like:

```python
if scenario_name == "wind_fault":
    ...
```

---

## Calculations

### Effective thrust

```text
if mass > dry_mass:
    thrust = throttle * max_thrust
else:
    thrust = 0
```

### Thrust direction

```text
alpha = theta + gimbal_angle
```

### Horizontal force

```text
Fx = thrust * sin(alpha) + external_force_x
```

### Vertical force

```text
Fy = thrust * cos(alpha) + external_force_y - mass * gravity
```

### Linear acceleration

```text
ax = Fx / mass
ay = Fy / mass
```

Equivalent expanded form:

```text
ax = (thrust * sin(alpha) + external_force_x) / mass

ay = (thrust * cos(alpha) + external_force_y) / mass - gravity
```

### Gimbal torque

```text
gimbal_torque =
    thrust_lever_arm
    * thrust
    * sin(gimbal_angle)
```

### Angular acceleration

```text
angular_acceleration =
    (gimbal_torque + external_torque)
    / moment_of_inertia
```

### Mass derivative

```text
if mass > dry_mass and throttle > 0:
    dmass = -(throttle * max_mass_flow_rate)
else:
    dmass = 0
```

### State derivative

```text
dx      = vx
dy      = vy
dvx     = ax
dvy     = ay
dtheta  = omega
domega  = angular_acceleration
dmass   = mass derivative
```

---

## API/service functions

Recommended public functions:

```python
def compute_derivatives(
    state: VehicleState,
    actuation: AppliedActuation,
    params: VehicleParameters,
    environment: EnvironmentForces,
) -> VehicleStateDerivative:
    ...
```

```python
def validate_vehicle_state(
    state: VehicleState,
    params: VehicleParameters,
) -> None:
    ...
```

```python
def validate_vehicle_parameters(
    params: VehicleParameters,
) -> None:
    ...
```

```python
def validate_applied_actuation(
    actuation: AppliedActuation,
) -> None:
    ...
```

```python
def enforce_physical_bounds(
    state: VehicleState,
    params: VehicleParameters,
) -> VehicleState:
    ...
```

Potential helper:

```python
def compute_effective_thrust(
    state: VehicleState,
    actuation: AppliedActuation,
    params: VehicleParameters,
) -> float:
    ...
```

**Decision:** Do not split every equation into a public helper merely to create more files/functions. Extract helpers only when they improve readability or isolated testing.

---

## State management

**[Decision]** The dynamics feature owns **no mutable runtime state**.

The current truth state is owned by the Simulation Engine.

Dynamics behaves like:

```text
input state -> derivatives
```

not:

```text
dynamics object mutates internal vehicle state
```

**Justification:** This supports deterministic tests, clean RK4 integration, and explicit state ownership.

---

## Edge cases

### Zero throttle

Expected:

- zero thrust;
- zero fuel flow;
- gravity still applies;
- external forces still apply.

### Hover-equivalent thrust

If:

```text
thrust == mass * gravity
theta + gimbal_angle == 0
external_force == 0
```

then vertical acceleration should be approximately zero.

This is a valuable physics sanity test.

### Full throttle

Expected:

```text
thrust == max_thrust
mass_flow == max_mass_flow_rate
```

while fuel remains.

### Fuel exhausted

At dry mass:

- thrust = 0;
- mass flow = 0.

### Zero gimbal

With:

```text
external_torque = 0
```

gimbal torque is zero.

The vehicle may still keep rotating if `omega != 0`, but angular acceleration is zero.

### Positive gimbal

Under the documented convention:

- gimbal torque sign is positive;
- angular acceleration sign is positive.

### Negative gimbal

Signs should mirror the positive case.

### Existing pitch with zero gimbal

A nonzero vehicle pitch rotates the thrust vector even when gimbal is zero.

This is essential: body attitude affects translational motion.

### Zero thrust but nonzero gimbal

No gimbal thrust torque should be produced when thrust is zero.

### External force only

A nonzero external force should alter translational acceleration without changing thrust calculation.

### External torque only

A nonzero external torque should alter angular acceleration without changing translational force.

### Extreme but finite angle

Trigonometric equations should remain mathematically valid.

**Decision:** Do not normalize `theta` inside `compute_derivatives(...)` unless a later demonstrated need appears.

**Justification:** Trigonometric functions already handle angles outside `[-π, π]`, and silent angle normalization can complicate debugging/continuous state histories.

### Non-finite input

Reject immediately.

### Negative mass

Reject immediately.

### Mass below dry mass

Reject unless within the small documented post-step numerical tolerance handled by `enforce_physical_bounds(...)`.

---

# 6. Acceptance Criteria

All criteria use Given/When/Then form.

## AC-01 — Gravity-only motion

**Given** a valid state, zero applied throttle, zero external forces, and positive gravity  
**When** the dynamics derivative is computed  
**Then** horizontal acceleration is zero and vertical acceleration equals `-gravity`.

---

## AC-02 — Position derivatives equal velocity

**Given** any valid finite `vx` and `vy`  
**When** the derivative is computed  
**Then** `dx/dt == vx` and `dy/dt == vy`.

---

## AC-03 — Upright thrust preserves horizontal symmetry

**Given** `theta = 0`, `gimbal_angle = 0`, and no external horizontal force  
**When** positive throttle is applied  
**Then** thrust contributes zero horizontal acceleration within floating-point tolerance.

---

## AC-04 — Upright thrust affects vertical acceleration

**Given** `theta = 0`, `gimbal_angle = 0`, and positive throttle  
**When** the derivative is computed  
**Then** vertical acceleration equals `thrust / mass - gravity` within tolerance.

---

## AC-05 — Rightward thrust-vector angle creates rightward acceleration

**Given** a positive `theta + gimbal_angle` under the documented convention  
**When** positive thrust is applied  
**Then** horizontal acceleration is positive.

---

## AC-06 — Leftward thrust-vector angle creates leftward acceleration

**Given** a negative `theta + gimbal_angle`  
**When** positive thrust is applied  
**Then** horizontal acceleration is negative.

---

## AC-07 — Zero gimbal produces zero nominal gimbal torque

**Given** any positive thrust and `gimbal_angle = 0`  
**When** the derivative is computed with zero external torque  
**Then** angular acceleration is zero.

---

## AC-08 — Positive gimbal produces positive angular acceleration

**Given** positive thrust, positive gimbal angle, positive lever arm, and zero external torque  
**When** the derivative is computed  
**Then** angular acceleration is positive under the documented convention.

---

## AC-09 — Negative gimbal reverses angular acceleration

**Given** the same state/parameters as AC-08 but a negative gimbal angle  
**When** the derivative is computed  
**Then** angular acceleration is negative.

---

## AC-10 — Zero thrust produces zero gimbal torque

**Given** zero applied throttle and a nonzero gimbal angle  
**When** the derivative is computed  
**Then** gimbal-generated torque is zero.

---

## AC-11 — Active thrust consumes mass

**Given** mass is above dry mass, throttle is positive, and maximum mass-flow rate is positive  
**When** the derivative is computed  
**Then** `dmass/dt` is negative and equals `-(throttle * max_mass_flow_rate)`.

---

## AC-12 — Dry mass stops thrust and fuel flow

**Given** current mass equals dry mass  
**When** positive throttle is supplied  
**Then** effective thrust is zero and `dmass/dt == 0`.

---

## AC-13 — State below dry mass is rejected

**Given** current mass is materially below dry mass  
**When** state validation runs  
**Then** a clear dynamics invariant error is raised.

---

## AC-14 — Invalid throttle is rejected

**Given** an applied throttle outside `[0, 1]`  
**When** actuation validation runs  
**Then** the input is rejected rather than silently clipped.

---

## AC-15 — Invalid inertia is rejected

**Given** `moment_of_inertia <= 0`  
**When** parameter validation runs  
**Then** configuration is rejected before normal simulation.

---

## AC-16 — Non-finite state is rejected

**Given** any state field is NaN or infinite  
**When** state validation runs  
**Then** a clear error is raised.

---

## AC-17 — External horizontal force changes only the expected translational term

**Given** two otherwise identical inputs where the second has a finite nonzero `external_force_x`  
**When** derivatives are compared  
**Then** the difference in horizontal acceleration equals `external_force_x / mass` within tolerance.

---

## AC-18 — External torque changes angular acceleration

**Given** two otherwise identical inputs where the second has a finite nonzero external torque  
**When** derivatives are compared  
**Then** the angular-acceleration difference equals `external_torque / moment_of_inertia` within tolerance.

---

## AC-19 — Determinism

**Given** identical state, parameters, actuation, and environment inputs  
**When** derivatives are calculated repeatedly  
**Then** every returned field is identical within the project's deterministic floating-point expectations.

---

## AC-20 — Inputs are not mutated

**Given** immutable or copied input objects  
**When** derivative calculation completes  
**Then** no input object's fields have changed.

---

## AC-21 — Dynamics remains presentation-independent

**Given** the dynamics package is imported in a headless test environment  
**When** unit tests execute  
**Then** no Matplotlib, Rich, CLI, file-writing, or GUI dependency is required by the dynamics module.

---

## AC-22 — Dynamics remains controller-independent

**Given** the module dependency graph  
**When** the dynamics package is inspected/tested  
**Then** it does not import controller, sensor, mission-state, fault-scenario, telemetry, or CLI modules.

---

## AC-23 — Vehicle attitude affects thrust direction without gimbal

**Given** a nonzero vehicle pitch, zero gimbal angle, and positive thrust  
**When** the derivative is computed  
**Then** the thrust vector contains a horizontal component consistent with the vehicle pitch.

---

## AC-24 — Feature remains 2D

**Given** the completed MVP implementation  
**When** its public state and equations are inspected  
**Then** it models only planar translation plus one pitch rotational degree of freedom and does not introduce roll, yaw, 3D vectors, quaternions, orbital mechanics, or 6-DOF state.

---

# 7. Test Plan

## Unit tests

Primary file:

```text
tests/unit/test_dynamics.py
```

Recommended tests:

```text
test_zero_throttle_applies_gravity_only
test_position_derivatives_match_velocity
test_upright_thrust_has_no_horizontal_component
test_upright_thrust_vertical_acceleration
test_positive_pitch_creates_positive_horizontal_thrust
test_negative_pitch_creates_negative_horizontal_thrust
test_positive_gimbal_creates_positive_torque
test_negative_gimbal_creates_negative_torque
test_zero_gimbal_creates_zero_gimbal_torque
test_zero_thrust_creates_zero_gimbal_torque
test_mass_flow_scales_with_throttle
test_dry_mass_disables_thrust
test_dry_mass_disables_mass_flow
test_external_force_changes_acceleration
test_external_torque_changes_angular_acceleration
test_invalid_throttle_rejected
test_nonpositive_inertia_rejected
test_nonpositive_dry_mass_rejected
test_mass_below_dry_mass_rejected
test_non_finite_state_rejected
test_non_finite_actuation_rejected
test_non_finite_external_force_rejected
test_derivative_calculation_is_deterministic
test_derivative_calculation_does_not_mutate_inputs
```

### Numerical assertions

Use:

```python
pytest.approx(...)
```

with explicit tolerances.

Do not use exact equality for trigonometric or general floating-point calculations unless the value is structurally exact, such as a copied velocity field.

---

## Integration tests

This feature should have very limited integration testing because the **Numerical Simulation Engine** is a separate feature.

Once that engine exists, add a small contract test:

```text
tests/integration/test_dynamics_engine_contract.py
```

Recommended cases:

### Short gravity-only evolution

Verify that an initially stationary vehicle loses altitude after several valid numerical steps.

### Short vertical-thrust evolution

Verify that an upright vehicle with sufficient thrust gains upward velocity without meaningful horizontal drift.

### Short gimbal-coupling evolution

Verify that a nonzero applied gimbal produces both:

- horizontal trajectory change;
- pitch/angular-rate change.

**Decision:** Do not place RK4 convergence testing or SciPy reference comparison in this feature's test plan. Those belong to **Numerical Simulation Engine** and **Numerical Verification**.

---

## Manual QA checklist

- [ ] Read `dynamics.py` and verify equations match this document.
- [ ] Confirm coordinate/sign convention is documented directly beside the equations.
- [ ] Confirm units are visible in data-model/config documentation.
- [ ] Confirm `VehicleState` has exactly the required planar truth fields.
- [ ] Confirm simulation time is not duplicated inside `VehicleState`.
- [ ] Confirm applied throttle is not silently saturated in dynamics.
- [ ] Confirm gimbal lag/slew behavior is absent from dynamics.
- [ ] Confirm controller code is not imported.
- [ ] Confirm sensor code is not imported.
- [ ] Confirm mission-state code is not imported.
- [ ] Confirm fault scenario names are not referenced.
- [ ] Confirm no file I/O occurs.
- [ ] Confirm no random number generator is used.
- [ ] Confirm no plotting dependency is imported.
- [ ] Confirm all dynamics unit tests pass.
- [ ] Confirm dry-mass behavior is covered by tests.
- [ ] Confirm positive/negative angle signs are covered by tests.

---

## Demo verification checklist

After the Numerical Simulation Engine is available:

- [ ] Upright open-loop case visibly remains horizontally symmetric.
- [ ] Vehicle responds to gravity.
- [ ] Vehicle responds to thrust magnitude.
- [ ] Vehicle responds to thrust direction.
- [ ] Pitch/gimbal behavior changes angular motion.
- [ ] Mass decreases only while powered and above dry mass.
- [ ] Same inputs reproduce the same trajectory.
- [ ] Demo uses simulated physics, not hard-coded coordinates.
- [ ] Reviewer can understand the coordinate convention in under one minute.

---

# 8. Portfolio Value

## How this feature helps the project stand out

Many student simulation projects can look impressive visually while hiding weak system design.

This feature provides a stronger foundation because it allows AstraLoop to truthfully show that:

- motion is generated from equations rather than animation waypoints;
- translational and rotational behavior are coupled;
- vehicle mass changes during powered operation;
- later actuator commands have physical consequences;
- the physics core is isolated and unit tested;
- the simulator can be reasoned about through clear software contracts.

The strongest hiring signal is not "I know rocket physics."

It is:

> "I translated a stateful physical model into a deterministic, typed, testable Python domain layer that later software components can control and validate."

---

## What to mention in README

Recommended concise wording:

> **2D planar dynamics:** AstraLoop evolves horizontal/vertical position, velocity, pitch, angular rate, and mass from gravity, thrust-vector direction, gimbal torque, and fuel consumption. The physics layer is deterministic and independent from control, sensing, telemetry, and visualization.

Mention these design decisions:

- 2D planar instead of 6-DOF to keep scope finishable;
- upright pitch is `0 rad`;
- radians internally;
- constant moment of inertia for MVP;
- no aerodynamic model in MVP;
- applied actuator output is passed into dynamics;
- physics has no knowledge of controllers or scenarios.

Do **not** claim:

- real launch-vehicle fidelity;
- SpaceX/Starship accuracy;
- high-fidelity propulsion;
- CFD/aerodynamics;
- 6-DOF dynamics.

---

## What to mention in interviews

Strong talking points:

### Why 2D instead of 6-DOF?

> "I chose planar translation plus pitch because it creates meaningful coupling between thrust direction, position, velocity, and attitude without making the portfolio project mostly an aerospace-modeling exercise. It let me spend more effort on deterministic simulation, interfaces, fault injection, and testing."

### Why separate physics from the integrator?

> "The dynamics module answers one question: given the current state and applied physical inputs, what are the derivatives? The simulation engine owns time and numerical stepping. That separation makes the physics easy to unit test and lets the integrator be verified independently."

### Why does dynamics receive applied actuator state?

> "I wanted the controller request, actuator behavior, and physical vehicle to be distinct layers. The dynamics only sees what physically reached the vehicle, so actuator lag or degradation can be modeled without contaminating the equations."

### Why no drag/aerodynamics?

> "It was a deliberate scope decision. Drag would require more assumptions and parameters but would not improve the target software-engineering signal as much as getting architecture, reproducibility, and validation right."

### How did you prevent sign-convention bugs?

> "I wrote the coordinate convention down first and added symmetry/sign tests: upright thrust has no x component, positive pitch produces positive x thrust, positive gimbal produces the documented torque direction, and negative inputs mirror the result."

### What was hardest?

Likely honest discussion areas after implementation:

- thrust-vector sign convention;
- mass reaching dry mass during an RK4 step;
- coupling between gimbal torque and trajectory;
- choosing parameters that are controllable but not unstable.

Document the real bugs discovered rather than inventing them in advance.

---

# 9. Implementation Notes for Codex

## Likely files/folders

Primary files:

```text
src/astraloop/model/state.py
src/astraloop/model/commands.py
src/astraloop/simulation/dynamics.py
src/astraloop/simulation/environment.py
tests/unit/test_dynamics.py
```

Potential config/schema touchpoint:

```text
src/astraloop/config/schema.py
```

Only add physics-related configuration fields there if the config layer already exists.

### Recommended ownership

`model/state.py`

- `VehicleState`
- `VehicleStateDerivative`

`model/commands.py`

- `AppliedActuation` or equivalent physical applied-input record

`simulation/environment.py`

- gravity/environment force record if it is not already represented elsewhere

`simulation/dynamics.py`

- parameter validation helpers if not centralized
- derivative calculations
- effective-thrust calculation if useful
- physical-bound helper
- no simulation loop

`tests/unit/test_dynamics.py`

- all isolated equation and invariant tests

---

## Build order

### Step 1 — Lock conventions in comments/docstrings

Before equations are coded, define:

```text
+x right
+y up
theta=0 upright
positive theta rightward/clockwise
radians internally
```

Add this to `dynamics.py` and the relevant state type documentation.

**Reason:** Sign convention is the most dangerous silent source of later controller bugs.

---

### Step 2 — Implement typed immutable data records

Implement:

- `VehicleState`
- `VehicleStateDerivative`
- `VehicleParameters`
- `AppliedActuation`
- environment force/torque record

Keep them minimal.

Do not add future fields "just in case."

---

### Step 3 — Implement validation

Validate:

- finiteness;
- positive/valid masses;
- valid inertia;
- throttle range;
- finite angles;
- finite external inputs.

Write validation tests before the complete dynamics equation if practical.

---

### Step 4 — Implement gravity-only derivative

Start with:

```text
dx = vx
dy = vy
dvx = 0
dvy = -g
dtheta = omega
domega = 0
dmass = 0
```

Make its tests pass.

---

### Step 5 — Add thrust decomposition

Add:

```text
alpha
Fx_thrust
Fy_thrust
```

Pass upright/positive/negative sign tests.

---

### Step 6 — Add pitch torque

Add simplified gimbal torque and moment-of-inertia calculation.

Pass sign and zero-thrust tests.

---

### Step 7 — Add mass flow and dry-mass behavior

Add:

- throttle-scaled fuel use;
- no thrust below/at dry mass;
- no mass flow at dry mass;
- physical-bound helper.

---

### Step 8 — Add external force/torque inputs

Keep their default behavior exactly zero.

Do not add fault activation logic.

---

### Step 9 — Finish unit test matrix

All acceptance criteria that can be tested without a simulation engine should pass now.

---

### Step 10 — Add only the minimum engine adapter needed later

When the Numerical Simulation Engine is implemented, expose the derivative function in the form it needs.

Do not redesign the physics around RK4 implementation details unless a real interface mismatch appears.

---

## Risks

### Risk 1 — Sign convention confusion

**Impact:** Very high.

A sign bug can make a controller appear unstable even when the controller is correct.

**Mitigation:**

- convention in code comments;
- diagram in docs;
- positive/negative symmetry tests;
- never change sign convention casually after controller work begins.

---

### Risk 2 — Dynamics starts absorbing other features

Examples:

- throttle clipping;
- gimbal slew;
- mission landing detection;
- random wind activation;
- fault names;
- telemetry calls.

**Mitigation:** Treat `dynamics.py` as a domain-math boundary.

---

### Risk 3 — Unrealistic parameters make control impossible

**Mitigation:** Keep parameter values configurable and calibrate a deliberately simplified vehicle after the equations are stable.

**[Open Question]** Final nominal mass, thrust, inertia, lever arm, and fuel-flow values need calibration.

---

### Risk 4 — Dry-mass overshoot during numerical stepping

A derivative can be correct while a finite integration step crosses below dry mass.

**Mitigation:** Define the invariant here, but enforce it at the numerical engine boundary after a step.

Do not hide integration-specific logic inside the derivative function.

---

### Risk 5 — Overengineering the math model

Potential distractions:

- aerodynamic drag;
- wind-relative velocity;
- changing inertia;
- center-of-mass movement;
- multiple engines;
- engine spool thermodynamics;
- atmospheric density;
- ground reaction models.

**Mitigation:** Do not add them until the complete AstraLoop MVP is done and a specific improvement is justified.

---

### Risk 6 — Array-index ambiguity

Using a raw NumPy vector everywhere can lead to code like:

```python
state[4]
state[5]
```

with unclear meaning.

**Mitigation:** Use named state records at module boundaries. Convert to numerical arrays only where the Numerical Simulation Engine benefits from them.

---

## What not to change

While implementing this feature, Codex should **not**:

- implement RK4;
- select the simulation timestep;
- add SciPy `solve_ivp` runtime logic;
- implement numerical convergence verification;
- build sensor models;
- build PID controllers;
- tune landing controllers;
- add actuator lag or saturation;
- create mission states;
- add fault activation logic;
- add scenario runner behavior;
- add telemetry persistence;
- add plotting;
- add CLI commands;
- add a database;
- add web/SaaS infrastructure;
- add 3D/6-DOF dynamics;
- add orbital mechanics;
- add aerodynamics;
- add machine learning.

If a later-feature dependency is not yet implemented, use the smallest typed boundary object needed to keep this feature testable.

---

# Feature-Specific Definition of Done

The 2D Flight Dynamics feature is complete when:

- [ ] The planar truth-state model contains `x`, `y`, `vx`, `vy`, `theta`, `omega`, and `mass`.
- [ ] Coordinate and angle conventions are documented in code and docs.
- [ ] All internal angular calculations use radians.
- [ ] Gravity is modeled.
- [ ] Thrust magnitude affects acceleration.
- [ ] Vehicle pitch changes thrust direction.
- [ ] Applied gimbal angle changes thrust direction.
- [ ] Applied gimbal angle creates simplified pitch torque.
- [ ] Pitch angular acceleration uses configured moment of inertia.
- [ ] Fuel/mass decreases under powered operation.
- [ ] Dry mass cannot be physically crossed without detection/correction.
- [ ] Thrust and mass flow stop when usable fuel is exhausted.
- [ ] Optional external force and torque inputs exist without fault logic.
- [ ] Dynamics is deterministic.
- [ ] Dynamics does not mutate inputs.
- [ ] Dynamics performs no file I/O.
- [ ] Dynamics imports no UI, telemetry, controller, sensor, mission, or scenario code.
- [ ] Invalid/non-finite physical inputs fail clearly.
- [ ] Unit tests cover symmetry, signs, thrust, gravity, torque, mass flow, bounds, and invalid inputs.
- [ ] `pytest` passes for all feature tests.
- [ ] No 3D/6-DOF, aerodynamic, orbital, or propulsion-fidelity scope has been added.

---

# Open Questions

These questions do **not** block implementation of the software structure, but they must be resolved before locking the nominal scenario.

1. **[Open Question]** What final development values should be used for:
   - dry mass;
   - initial mass;
   - maximum thrust;
   - maximum mass-flow rate;
   - moment of inertia;
   - thrust lever arm?

2. **[Open Question]** What post-step floating-point tolerance should distinguish a tiny dry-mass integration overshoot from a genuine invariant violation?

3. **[Open Question]** Should human-authored scenario configuration expose `theta`/`omega` in degrees for readability and convert at load time, or expose radians directly?  
   **Recommended decision:** degrees at the human configuration boundary, radians everywhere inside the Python domain model.

4. **[Open Question]** Should ground level always be `y = 0`, or should a later environment configuration provide `ground_y`?  
   **Recommended decision:** support `ground_y` in the environment layer if needed, but do not place mission landing logic in dynamics.

---

# Move On When

- [ ] Each acceptance criterion that belongs to this feature has a passing test.
- [ ] The reviewer demo path can show real equation-driven motion once the Numerical Simulation Engine is connected.
- [ ] The feature clearly proves numerical/domain-modeling skill.
- [ ] The dynamics layer remains isolated from sensors, control, actuators, mission logic, faults, telemetry, visualization, and CLI behavior.
- [ ] No unnecessary SaaS or infrastructure system has been added.
- [ ] The scope still matches the finishable 2D AstraLoop Gold project.
