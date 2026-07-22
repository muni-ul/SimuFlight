# Feature 13 — Numerical Verification

> **Project:** AstraLoop — Python Software-in-the-Loop Flight Control & Validation System  
> **Feature:** Numerical Verification  
> **Document path:** `docs/features/13-numerical-verification.md`  
> **Status:** Implementation specification  
> **Primary goal:** Independently verify AstraLoop’s project-owned fixed-step RK4 integrator and open-loop 2D dynamics using analytical solutions, step-refinement/order-of-accuracy studies, and high-accuracy SciPy `solve_ivp` references, then document the supported timestep and measured error without allowing the reference solver to become the production mission scheduler.

---

## Scope Boundary

**[Confirmed]** AstraLoop’s production simulation uses a project-owned fixed-step fourth-order Runge–Kutta integrator.

**[Confirmed]** The fixed-step runtime is selected because AstraLoop is a hybrid continuous/discrete system containing:

```text
sensor sampling
sensor delay buffers
controller update periods
actuator updates
mission transitions
fault activation
telemetry frames
```

A shared fixed tick gives these components deterministic timing semantics.

**[Confirmed]** SciPy `solve_ivp` is retained as an **independent numerical reference in tests**, not as the production scheduler.

**[Confirmed]** The architecture specifically requires:

- simple analytical verification cases;
- selected open-loop comparisons with SciPy;
- order-of-accuracy behavior;
- a documented supported `dt`;
- safe failure for non-finite/numerically invalid states.

**[Confirmed]** Feature 02 intentionally deferred the following work to Feature 13:

```text
RK4 versus SciPy solve_ivp
formal step-refinement/convergence tables
documented numerical-error tolerance for the flight model
stability-envelope studies
production-dt justification
```

**[Confirmed]** Feature 12 owns the overall pytest architecture, while Feature 13 owns the numerical-reference derivations and verification evidence.

**[Decision]** Feature 13 owns the **independent numerical verification layer**.

It owns:

- analytical test ODEs;
- analytical solution helpers used only by verification tests;
- one-step RK4 formula verification;
- vector-state RK4 verification;
- global-error measurements;
- step-refinement studies;
- observed convergence-order calculation;
- error-ratio calculation;
- open-loop AstraLoop dynamics reference cases;
- SciPy `solve_ivp` reference integration;
- piecewise-constant input segmentation at exact tick boundaries;
- state-component tolerances;
- normalized error metrics;
- reference-solver settings;
- supported production timestep evidence;
- timestep-sensitivity/stability study;
- verification tables and concise technical documentation;
- deterministic numerical pytest tests;
- regression tests for numerical bugs.

It does **not** own:

- production mission scheduling;
- adaptive stepping in normal scenarios;
- live controller/sensor/fault/state-machine execution inside SciPy;
- controller tuning;
- mission PASS/FAIL validation;
- broad test organization;
- runtime performance benchmarking;
- Monte Carlo campaigns;
- high-fidelity aerospace validation;
- real launch-vehicle certification;
- a generic ODE solver library;
- multiple production integrators.

---

# 1. Feature Overview

## Feature name

**Numerical Verification**

---

## One-sentence description

**[Decision]** Verify the custom RK4 and 2D dynamics against exact mathematical solutions and an independent high-accuracy SciPy oracle, demonstrate fourth-order convergence under smooth conditions, and freeze a measured timestep/tolerance contract for the production simulation.

---

## Detailed description

A custom integrator creates strong portfolio value only if the repository can answer:

```text
How do you know it is correct?
How accurate is it?
Why is this timestep acceptable?
What happens when the step is refined?
Which problems were compared against an independent solver?
What parts of the hybrid mission are not appropriate for direct solver comparison?
```

Feature 13 provides those answers.

The verification stack is:

```text
Level 1 — Formula and analytical ODE verification
        |
        v
Level 2 — Step refinement and observed RK4 order
        |
        v
Level 3 — Open-loop AstraLoop dynamics vs solve_ivp
        |
        v
Level 4 — Production-dt sensitivity and documented limits
```

No single reference case is sufficient.

- Analytical tests prove known mathematical behavior.
- Convergence tests catch methods that happen to match one endpoint accidentally.
- SciPy comparisons exercise the actual vehicle derivative implementation.
- Timestep-sensitivity evidence justifies the production setting.

---

## Verification principles

### 1. The reference must be independent

The SciPy reference must not call the custom RK4 internally.

The analytical reference must not reproduce the same RK4 formula.

The reference path may reuse the **same physical derivative function** for the actual AstraLoop open-loop comparison because the goal there is to isolate integration error.

Separate analytical dynamics tests protect the derivative function itself.

---

### 2. Verify smooth continuous problems

Classical RK4’s fourth-order convergence assumes sufficiently smooth derivatives over the step.

Do not claim fourth-order behavior across:

- ground-contact clamping;
- dry-mass clamping;
- mission-state jumps;
- fault activation discontinuities;
- command changes inside a step;
- sensor/controller updates;
- saturation branch changes occurring at unknown substep times.

Verification cases must define discontinuities explicitly and align them to segment/tick boundaries.

---

### 3. Compare like with like

Production RK4 holds applied actuation constant during one simulation tick.

The SciPy reference for a piecewise-constant command schedule must use the same input semantics:

```text
input u_k applies on [t_k, t_{k+1})
```

At command changes, restart/reference-integrate at the exact boundary.

Do not allow adaptive solver interpolation across an unmodeled discontinuity.

---

### 4. Use state-specific scales

A seven-component state contains different units and magnitudes:

```text
x       m
y       m
vx      m/s
vy      m/s
theta   rad
omega   rad/s
mass    kg
```

A single raw maximum absolute error can be misleading.

Feature 13 uses:

- per-component absolute error;
- per-component relative/scaled error;
- one normalized maximum state error;
- endpoint and trajectory errors.

---

### 5. Separate verification from validation

Numerical verification asks:

```text
Did the integrator accurately solve the defined equations?
```

Mission validation asks:

```text
Did the completed mission meet project acceptance criteria?
```

A mission can pass validation despite a poorly verified solver.

A solver can be numerically accurate while the controller fails the mission.

Both layers are required and separate.

---

## Verification levels

### Level 1 — RK4 implementation correctness

Tests the generic integrator using ODEs with exact solutions.

Required cases:

1. constant derivative;
2. scalar exponential;
3. time-dependent polynomial derivative;
4. harmonic oscillator;
5. decoupled/mixed vector system.

---

### Level 2 — Fourth-order convergence

Tests global error over a fixed interval using step refinement.

Required:

```text
dt
dt / 2
dt / 4
dt / 8
```

Expected asymptotic global-error ratio:

```text
E(dt) / E(dt/2) ≈ 2^4 = 16
```

Expected observed order:

```text
p = log2(E_h / E_h/2) ≈ 4
```

---

### Level 3 — Actual open-loop vehicle dynamics

Uses the real Feature 01 derivative function with controlled inputs and no hybrid event logic.

Required reference cases:

1. gravity-only ballistic motion;
2. constant upright thrust with constant mass or zero configured mass flow;
3. rotational/thrust-coupled motion with fixed gimbal;
4. fuel-burning open-loop motion before dry mass;
5. piecewise-constant actuation schedule with exact segment boundaries.

Not every case needs an analytical solution.

Cases 2–5 can compare custom RK4 against `solve_ivp`.

---

### Level 4 — Production timestep study

Runs representative smooth/open-loop cases at:

```text
dt_production
dt_production / 2
dt_production / 4
```

and compares:

- endpoint state;
- selected trajectory samples;
- derived physical values;
- stability/invariant behavior.

The final production timestep is documented only after measured results exist.

---

## Why SciPy is not the production scheduler

`solve_ivp` is designed for continuous ODE integration and may use adaptive internal steps.

AstraLoop’s runtime must define exact, simple semantics for:

```text
fault at tick 1000
sensor samples every 5 ticks
controller updates every 2 ticks
actuator updates once per tick
telemetry frame per tick
```

The production engine therefore stays fixed-step.

SciPy provides an independent continuous reference only for carefully isolated continuous problems.

---

## Verification target

The numerical target is not:

```text
prove a real rocket simulator is physically accurate
```

It is:

```text
prove the implemented equations are integrated correctly and predictably
within a documented project-scale timestep/error envelope
```

The project remains a simplified portfolio simulator.

---

## Priority

**P0 — Required numerical credibility**

The source feature index classifies SciPy RK4 verification as P0.

A custom numerical core without independent verification weakens the entire project.

---

## Complexity

**Medium**

The mathematics is manageable.

The key difficulty is designing independent, smooth, correctly aligned reference cases and choosing honest tolerances.

---

# 2. Verification Flow

## Developer flow

1. Implement/preserve a small pure RK4 function.
2. Run analytical one-step tests.
3. Run multi-step exact-solution tests.
4. Run step-refinement tests.
5. Confirm observed order approaches four.
6. Build open-loop vehicle reference fixtures.
7. Integrate the same derivative with high-accuracy SciPy.
8. Sample SciPy at production tick times.
9. Compare component/trajectory errors.
10. Run production-dt sensitivity study.
11. Record measured results.
12. Freeze supported timestep/tolerances in documentation/tests.
13. Add any discovered bug as a permanent regression.

---

## Reviewer flow

A technical reviewer can see:

```text
Analytical scalar convergence:
dt      error          observed order
0.200   ...
0.100   ...            3.9...
0.050   ...            4.0...

Open-loop vehicle vs SciPy:
state   max abs error  endpoint error
x       ...
y       ...
...
```

Then hear:

> “The production engine is fixed-step because of the software timing model. I used SciPy only as an independent reference on continuous open-loop segments and verified fourth-order convergence.”

---

## Happy path

- all exact-solution tests pass;
- observed order is within the documented acceptable range;
- open-loop SciPy comparisons pass per-state limits;
- production timestep remains stable and sufficiently close to refined results;
- numerical test suite runs as part of normal `pytest`.

---

## Error path

### Formula error in RK4

Examples:

- wrong half step;
- missing factor of two;
- wrong final weights;
- stage evaluated from wrong base state.

Analytical/convergence tests fail.

### Dynamics sign/unit error

Analytical ballistic/symmetry tests fail even if both RK4 and SciPy integrate the same wrong derivative.

### Comparison discontinuity error

Piecewise schedule reference differs only near command changes.

Segmentation/timing test reveals it.

### Production timestep too coarse

Reference comparison or refinement error exceeds limits.

Resolution:

- reduce production `dt`;
- fix dynamics/integrator bug;
- document a narrower supported envelope.

Do not widen tolerances without evidence.

---

# 3. Numerical Reference Problems

## Problem A — Constant derivative

ODE:

```text
dy/dt = c
y(0) = y0
```

Exact solution:

```text
y(t) = y0 + c t
```

### Why it matters

Classical RK4 should integrate a constant derivative exactly up to floating-point roundoff.

### Test variants

- positive `c`;
- negative `c`;
- zero `c`;
- scalar;
- vector constant derivative.

### Contract

For representative finite values:

```text
numerical == approximate exact at near-machine precision
```

---

## Problem B — Scalar exponential

ODE:

```text
dy/dt = λy
y(0) = y0
```

Exact:

```text
y(t) = y0 exp(λt)
```

Recommended cases:

```text
λ = -1.0     decaying
λ = +0.5     growing over bounded interval
```

Avoid long intervals causing huge magnitudes.

### Why it matters

- nonlinear-in-time solution;
- standard global-error convergence case;
- easy exact endpoint;
- catches stage/weight errors.

---

## Problem C — Time-dependent polynomial derivative

ODE:

```text
dy/dt = t^3
y(0) = y0
```

Exact:

```text
y(t) = y0 + t^4 / 4
```

Classical RK4 is exact for this derivative under ideal arithmetic because its quadrature is exact for cubic-in-time functions.

### Why it matters

It verifies that the integrator passes the correct stage times:

```text
t
t + h/2
t + h/2
t + h
```

A state-only autonomous test cannot catch every time-argument bug.

**Decision]** The generic RK4 interface should support derivative functions that receive time explicitly:

```python
f(t, state, inputs)
```

If production dynamics is autonomous, it may ignore `t`.

---

## Problem D — Harmonic oscillator

System:

```text
dx/dt = v
dv/dt = -ω²x
```

Initial:

```text
x(0) = 1
v(0) = 0
```

Exact:

```text
x(t) = cos(ωt)
v(t) = -ω sin(ωt)
```

Use:

```text
ω = 1
```

and bounded intervals such as one or two periods.

### Why it matters

- verifies coupled vector state;
- oscillatory behavior;
- phase error;
- both position and velocity components;
- energy-drift diagnostic.

### Optional derived diagnostic

Oscillator energy:

```text
E = 0.5 (v² + ω²x²)
```

RK4 does not conserve energy exactly.

The test may report bounded drift but should not demand symplectic conservation.

---

## Problem E — Mixed vector system

Example:

```text
dy1/dt = -y1
dy2/dt = 2t
dy3/dt = 0
```

Exact:

```text
y1 = y1,0 exp(-t)
y2 = y2,0 + t²
y3 = y3,0
```

### Why it matters

- multiple components;
- autonomous and time-dependent terms;
- constant component;
- validates vector ordering and shape handling.

---

## Problem F — Gravity-only vehicle motion

Applied actuation:

```text
throttle = 0
gimbal = 0
```

No disturbance.

Assuming ground contact is disabled/not reached during interval.

Dynamics:

```text
x(t)  = x0 + vx0 t
vx(t) = vx0

y(t)  = y0 + vy0 t - 0.5 g t²
vy(t) = vy0 - g t

theta(t) = theta0 + omega0 t
omega(t) = omega0

mass(t) = mass0
```

if no torque and no fuel flow.

### Why it matters

This verifies both:

- actual `VehicleState` derivative mapping;
- RK4 integration through the real state adapter.

### Contract

All seven state components compare to exact values.

---

## Problem G — Upright constant thrust with constant mass

Configure:

```text
mass_flow_rate = 0
theta = 0
gimbal = 0
omega = 0
constant throttle
constant mass
```

With the project's thrust-axis convention, acceleration is constant.

Analytical translational motion is available.

### Why it matters

- verifies thrust magnitude;
- thrust direction;
- gravity combination;
- horizontal symmetry;
- actual vehicle derivative.

### Requirement

This reference case must be constructed only if the final dynamics configuration allows zero mass flow cleanly.

Otherwise use SciPy reference rather than changing production equations solely for this test.

---

## Problem H — Fixed gimbal open-loop vehicle

Apply a constant nonzero gimbal and throttle.

Use real vehicle dynamics.

No sensors/controller/mission/faults.

Stop before:

- ground contact;
- dry mass;
- extreme angle;
- any discontinuity.

Reference:

```text
solve_ivp
```

### Why it matters

Exercises:

- coupled translational/rotational dynamics;
- mass evolution if enabled;
- trigonometric thrust direction;
- torque;
- seven-state vector.

---

## Problem I — Fuel-burning open-loop vehicle

Apply fixed actuation with positive configured mass flow.

Choose:

```text
mass(t_end) > dry_mass + safety_margin
```

No mass clamp is reached.

Reference:

```text
solve_ivp
```

### Why it matters

Exercises varying mass and coupled acceleration while remaining smooth.

---

## Problem J — Piecewise-constant actuation schedule

Example schedule:

```text
[0.0, 1.0)  throttle 0.30, gimbal  0°
[1.0, 2.0)  throttle 0.60, gimbal +2°
[2.0, 3.0]  throttle 0.45, gimbal -1°
```

All boundaries align exactly with production ticks.

Production RK4:

- input selected at interval start;
- input held for one full tick.

SciPy reference:

- integrate each segment independently;
- use previous segment final state as next initial state;
- do not integrate through discontinuity with one continuous RHS closure.

### Why it matters

This verifies the production input-hold semantics against a high-accuracy continuous reference.

---

# 4. RK4 Verification Requirements

## Generic RK4 formula

For:

```text
y' = f(t, y, u)
```

one step of size `h`:

```text
k1 = f(t,       y,             u)
k2 = f(t+h/2,   y+h*k1/2,      u)
k3 = f(t+h/2,   y+h*k2/2,      u)
k4 = f(t+h,     y+h*k3,        u)

y_next =
    y
    + h/6 * (k1 + 2*k2 + 2*k3 + k4)
```

Applied discrete input `u` is held constant across all four stages.

---

## Direct formula test

Use an instrumented derivative returning stage-dependent values.

Assert:

- four calls;
- correct stage times;
- correct intermediate states;
- same input identity/value;
- correct final weighted sum.

This test protects the exact implementation independently of endpoint comparisons.

---

## Input immutability

RK4 must not mutate:

- current state;
- applied input;
- derivative output arrays used elsewhere.

Test with:

- immutable state;
- copied NumPy arrays;
- derivative spy.

---

## Shape/type behavior

The integrator should reject:

- wrong derivative shape;
- non-finite derivative;
- non-finite intermediate state;
- invalid timestep;
- unsupported state representation.

These are ordinary unit tests, but numerical verification should ensure the failure semantics remain compatible with reference tests.

---

# 5. Convergence and Error Requirements

## Global error definition

For exact solution `y_exact(T)` and numerical result `y_h(T)`:

```text
E_h = || y_h(T) - y_exact(T) ||
```

For scalar:

```text
absolute endpoint error
```

For vector:

- component-wise error;
- optional L-infinity norm;
- scaled maximum error.

---

## Observed order

For step sizes `h` and `h/2`:

```text
p_h =
    log(E_h / E_h/2)
    / log(2)
```

Equivalent:

```text
p_h = log2(E_h / E_h/2)
```

Expected:

```text
p_h -> 4
```

as `h` enters the asymptotic truncation-error regime.

---

## Error ratio

Expected:

```text
E_h / E_h/2 -> 16
```

Do not require exactly 16.

Roundoff and problem-specific constants matter.

---

## Required refinement sequence

Recommended for scalar exponential:

```text
h = 0.2
h = 0.1
h = 0.05
h = 0.025
```

over:

```text
T = 1.0
```

All step sizes divide the interval exactly.

Alternative values are acceptable if they produce a clear asymptotic region.

---

## Observed-order acceptance

**[Decision]** For at least two consecutive refined pairs before roundoff dominates:

```text
3.7 <= observed_order <= 4.3
```

This range is intentionally tight enough to distinguish RK4 from lower-order implementations while tolerating finite precision/problem effects.

The final values must be measured before freezing tests.

If a chosen reference problem produces roundoff-dominated errors too early, adjust the step range rather than widening the order requirement arbitrarily.

---

## Monotonic refinement

For selected smooth cases:

```text
E_h/2 < E_h
```

over the documented range.

Do not require monotonicity down to extremely tiny `h`, where roundoff can dominate.

---

## Log-log slope

Optional evidence:

Fit:

```text
log(error) vs log(h)
```

using the asymptotic points.

Expected slope:

```text
approximately 4
```

This may be documented but should not replace pairwise order tests.

No plot is required for MVP.

---

## Local versus global error

The portfolio claim should say:

```text
fourth-order global convergence for smooth verification problems
```

Do not casually state:

```text
error is h^4 everywhere
```

Classical RK4 has:

- local truncation error order 5;
- global accumulated error order 4.

---

## Avoiding zero-error order calculations

Some polynomial/constant cases can be exact to roundoff.

Do not use an exact-to-machine-precision case to compute observed order because:

```text
log(0)
```

or roundoff noise makes the result meaningless.

Use scalar exponential/harmonic oscillator for convergence.

---

# 6. SciPy Reference Requirements

## Reference API

Use:

```python
scipy.integrate.solve_ivp
```

only in:

```text
tests/numerical
verification helper code used exclusively by tests/docs
```

No production engine import.

---

## Reference method

**[Decision]** Prefer:

```text
DOP853
```

as the high-order adaptive reference for smooth non-stiff open-loop cases.

Acceptable fallback:

```text
RK45
```

if a specific environment/API constraint exists.

The final chosen method is recorded in verification documentation.

### Why DOP853

- high-order explicit method;
- suitable for smooth non-stiff dynamics;
- reference error can be made much smaller than production RK4 error;
- independent implementation.

No claim is made that it is mathematically exact.

---

## Reference tolerances

Recommended starting values:

```python
rtol = 1e-11
atol = component-specific array
```

Potential component absolute tolerances:

```text
x, y      1e-12 to 1e-10 m
vx, vy    1e-12 to 1e-10 m/s
theta     1e-13 to 1e-11 rad
omega     1e-13 to 1e-11 rad/s
mass      1e-12 to 1e-10 kg
```

**Decision]** Final values must be measured.

The reference tolerances must be materially tighter than the custom-RK4 acceptance tolerances.

---

## Reference self-consistency check

Before treating one SciPy run as oracle, compare:

```text
reference settings A
vs
tighter reference settings B
```

or:

```text
DOP853
vs
another tighter DOP853 run
```

Requirement:

```text
reference change << custom RK4 allowed error
```

Recommended:

```text
reference self-difference <= 1% of custom comparison tolerance
```

where practical.

This prevents a loose reference from being treated as truth.

---

## Evaluation times

Use:

```python
t_eval = production_tick_times
```

or dense output evaluated exactly at those times.

**Decision]** Prefer explicit `t_eval` for straightforward array alignment.

For segment boundaries:

- avoid duplicate concatenated sample at shared boundary;
- preserve exact tick order;
- include initial time once;
- include final time once.

---

## State adapter

Production `VehicleState` is a named dataclass.

SciPy expects array-like state.

Use one centralized adapter shared with the integrator if already architecture-approved:

```python
vehicle_state_to_array
array_to_vehicle_state
```

Verification tests must catch incorrect index ordering.

Do not duplicate raw indices in multiple test files.

---

## RHS wrapper

Example:

```python
def scipy_rhs(
    t: float,
    y: NDArray[np.float64],
) -> NDArray[np.float64]:
    state = array_to_vehicle_state(y)
    derivative = vehicle_derivatives(
        time=t,
        state=state,
        actuation=applied_actuation,
        vehicle=vehicle,
        environment=environment,
    )
    return derivative_to_array(derivative)
```

The wrapper performs no:

- ground event;
- state-machine transition;
- sensor/controller update;
- fault update;
- telemetry write.

---

## `solve_ivp` result validation

Require:

```text
solution.success is true
solution.status indicates normal completion
solution.t matches expected evaluation times
solution.y has expected shape
all values finite
```

If the reference fails, the test must fail clearly.

Do not compare against partial failed reference output.

---

## Piecewise integration helper

Recommended test-only API:

```python
def solve_piecewise_reference(
    *,
    initial_state: VehicleState,
    segments: tuple[InputSegment, ...],
    vehicle: VehicleParameters,
    environment: EnvironmentConfig,
    t_eval: NDArray[np.float64],
    method: str = "DOP853",
    rtol: float = 1e-11,
    atol: NDArray[np.float64],
) -> ReferenceTrajectory:
    ...
```

Each `InputSegment` contains:

```text
start_time
end_time
applied actuation
```

Validate:

- contiguous;
- ordered;
- no overlap/gap;
- exact coverage;
- boundaries align with requested tick times where required.

---

## No production dependency on SciPy

Architecture test:

```text
src/astraloop/simulation/
```

must not import:

```text
scipy.integrate
```

unless a clearly test-only module lives outside the production runtime package.

Recommended location for reference helpers:

```text
tests/numerical/reference.py
```

or:

```text
tests/helpers/numerical_reference.py
```

This makes the separation obvious.

---

# 7. Vehicle-Dynamics Comparison Metrics

## Component absolute error

For component `i` at time `t_j`:

```text
e_abs[i,j] =
    | y_rk4[i,j] - y_ref[i,j] |
```

Record:

```text
max over time
endpoint
RMS over samples (optional)
```

---

## Component relative/scaled error

Simple relative error is unstable near zero.

Use:

```text
e_scaled[i,j] =
    |difference|
    /
    (abs_scale_i + rel_scale * |reference|)
```

Equivalent to an `allclose`-style scale.

Recommended per-state project comparison scales are measured and documented.

---

## Normalized maximum state error

```text
E_norm =
    max over i,j (
        |difference_i,j|
        /
        tolerance_i,j
    )
```

Pass when:

```text
E_norm <= 1
```

This gives one concise verification indicator while preserving per-state diagnostics.

---

## State-specific comparison tolerances

**[Decision]** Use separate absolute tolerances.

Illustrative starting values for a short representative open-loop case:

```text
x          1e-5 m
y          1e-5 m
vx         1e-5 m/s
vy         1e-5 m/s
theta      1e-7 rad
omega      1e-7 rad/s
mass       1e-7 kg
```

These are **not final source-supported values**.

They must be replaced with measured tolerances that are:

- tighter than mission-acceptance limits by a wide margin;
- loose enough to avoid platform-specific false failures;
- justified by production `dt`, duration, and case scale.

Do not silently keep placeholders.

---

## Endpoint and trajectory checks

Required for each open-loop case:

1. final component errors;
2. maximum sampled component errors across trajectory;
3. all finite;
4. invariant checks;
5. reference success;
6. repeated custom run determinism.

Endpoint-only comparison can miss transient/phase errors.

---

## Angle error

Use wrapped angular difference for physical orientation comparison:

```text
abs(wrap_angle(theta_rk4 - theta_ref))
```

For short cases guaranteed not to cross wrapping boundaries, raw difference may also be recorded.

Angular-rate comparison is direct.

---

## Mass error

Compare directly while the case remains above dry mass.

Do not include the dry-mass clamp in formal fourth-order comparison.

The clamp is a discrete/non-smooth runtime behavior tested separately.

---

# 8. Production Timestep Verification

## Goal

Provide evidence for one documented production timestep, likely:

```text
dt = 0.02 s
```

based on prior architecture examples.

**[Open Question]** The exact final production `dt` is not source-mandated until measured.

---

## Timestep study cases

Use at least:

1. scalar exponential convergence;
2. harmonic oscillator;
3. fixed-gimbal open-loop vehicle;
4. fuel-burning open-loop vehicle;
5. short representative nominal-like applied-input schedule without software feedback.

---

## Candidate steps

If candidate production dt is `0.02`:

```text
0.04
0.02
0.01
0.005
```

or:

```text
0.02
0.01
0.005
```

depending on test duration.

All command/schedule boundaries must align with each tested step.

---

## Production-dt acceptance

The final documented production `dt` must satisfy:

- no non-finite state;
- no numerical invariant violation;
- SciPy reference comparison passes;
- refinement to `dt/2` changes key state/metrics by less than documented tolerance;
- refinement trend is consistent with expected order for smooth open-loop cases;
- runtime remains practical for live local demo;
- discrete subsystem intervals are integer multiples of `dt`.

Performance itself is measured separately; numerical verification records only that the step is viable.

---

## Refinement difference

When exact/reference data is unavailable for a representative schedule:

```text
D_h =
    || y_h - y_h/2 ||
```

For a fourth-order method in the asymptotic regime:

```text
D_h / D_h/2 ≈ 16
```

Richardson-style estimated fine-grid error:

```text
E_h/2 ≈ D_h / (2^4 - 1)
      = D_h / 15
```

**Decision]** Richardson estimates may support documentation, but SciPy/analytical references remain preferred where available.

---

## Stability language

Do not claim:

```text
RK4 is unconditionally stable
```

It is not.

The documentation should say:

```text
The selected timestep was verified for the documented AstraLoop parameter and scenario envelope.
```

Not:

```text
The timestep is stable for all possible configurations.
```

---

## Supported envelope

The numerical verification document should list the tested ranges, such as:

```text
duration
mass range
throttle range
gimbal range
attitude range
vehicle parameter set
gravity/environment
no dry-mass/ground discontinuity in formal convergence cases
```

The exact ranges are measured from final cases.

---

## Configuration outside envelope

Extremely altered user parameters may require a smaller timestep.

Feature 08 local config validation may enforce basic ranges.

Feature 13 does not promise accuracy for arbitrary physically extreme TOML values.

---

# 9. Verification Report

## Required repository document

Recommended:

```text
docs/NUMERICAL_VERIFICATION.md
```

Feature 13 implementation should produce a concise measured document once tests are complete.

It should contain:

1. production integrator description;
2. why fixed-step is used;
3. analytical problems;
4. convergence table;
5. SciPy reference settings;
6. open-loop vehicle comparison table;
7. production timestep decision;
8. supported envelope;
9. known limitations;
10. exact commands to reproduce.

---

## Example convergence table

```text
Scalar exponential y'=-y, T=1

dt       endpoint error       ratio        observed order
0.200    <measured>
0.100    <measured>           <measured>   <measured>
0.050    <measured>           <measured>   <measured>
0.025    <measured>           <measured>   <measured>
```

No fabricated values.

---

## Example vehicle comparison table

```text
Case: fixed-gimbal open-loop, T=<measured>

Component   max abs error   endpoint error   tolerance   result
x           <measured>      <measured>        <final>     PASS
y           <measured>      <measured>        <final>     PASS
vx          <measured>      <measured>        <final>     PASS
vy          <measured>      <measured>        <final>     PASS
theta       <measured>      <measured>        <final>     PASS
omega       <measured>      <measured>        <final>     PASS
mass        <measured>      <measured>        <final>     PASS
```

---

## Verification result serialization

Optional test-only data class:

```python
@dataclass(frozen=True)
class NumericalVerificationResult:
    case_id: str
    step_size: float
    final_time: float

    component_max_abs_error: Mapping[str, float]
    component_endpoint_error: Mapping[str, float]
    normalized_max_error: float

    observed_order: float | None
    passed: bool
```

Do not add a production database/artifact system for numerical results.

---

## Generated versus manually maintained report

**[Decision]** Tests are the source of truth.

The markdown report may be:

- generated by a small explicit developer command; or
- manually updated from measured test helper output.

Avoid a test that rewrites repository documentation automatically during normal `pytest`.

Normal tests must not modify tracked files.

---

## Optional report-generation helper

Possible:

```bash
uv run python scripts/generate_numerical_verification.py
```

Only if it provides real value.

Feature 14 CLI does not need a user-facing numerical command for MVP.

A simple test/helper output copied into docs is acceptable.

---

# 10. Logic Requirements

## Rule 1 — Production integrator remains custom fixed-step RK4

---

## Rule 2 — SciPy remains test/reference only

---

## Rule 3 — Reference problems are deterministic

---

## Rule 4 — Analytical cases use independently derived solutions

---

## Rule 5 — Convergence is measured over a fixed final time

---

## Rule 6 — Step sizes divide the final interval exactly

---

## Rule 7 — Time is derived consistently from integer steps

---

## Rule 8 — Fourth-order convergence is checked on smooth problems

---

## Rule 9 — Exact/roundoff cases are not used for order estimation

---

## Rule 10 — Observed order uses unrounded errors

---

## Rule 11 — Reference tolerances are tighter than comparison tolerances

---

## Rule 12 — SciPy reference success is validated

---

## Rule 13 — SciPy is sampled at production tick times

---

## Rule 14 — Piecewise commands are segmented at exact discontinuities

---

## Rule 15 — No controller/sensor/mission/fault logic runs inside the continuous reference

---

## Rule 16 — Applied input is held constant across one production RK4 step

---

## Rule 17 — Open-loop cases avoid ground contact

---

## Rule 18 — Formal convergence cases avoid dry-mass clamping

---

## Rule 19 — Formal convergence cases avoid angle-reset discontinuities

---

## Rule 20 — Actual VehicleState ordering is verified

---

## Rule 21 — Component errors preserve physical units

---

## Rule 22 — Angle comparison uses wrapped error where appropriate

---

## Rule 23 — Relative error is not used alone near zero

---

## Rule 24 — State-specific absolute scales are used

---

## Rule 25 — Endpoint and full sampled trajectory are checked

---

## Rule 26 — No NaN/Inf is accepted in custom/reference outputs

---

## Rule 27 — Input state is not mutated

---

## Rule 28 — Reference helpers do not alter production state

---

## Rule 29 — Verification tests run under pytest

---

## Rule 30 — Numerical tests are included in the default full suite when reasonably fast

---

## Rule 31 — No network/display/database is required

---

## Rule 32 — No wall-clock performance threshold determines correctness

---

## Rule 33 — Numerical tolerances are documented and measured

---

## Rule 34 — Placeholder tolerances are not left in portfolio-ready code

---

## Rule 35 — Production dt is justified by evidence

---

## Rule 36 — Production dt is not claimed universal

---

## Rule 37 — Refining dt should reduce smooth-problem error in the tested regime

---

## Rule 38 — Reference self-consistency is checked

---

## Rule 39 — Solver comparisons use the same equations/parameters/inputs

---

## Rule 40 — Dynamics-specific analytical tests prevent shared-equation false confidence

---

## Rule 41 — A bug discovered through verification gets a regression test

---

## Rule 42 — Report values are measured, never invented

---

## Rule 43 — Test output is concise unless failure/debug mode

---

## Rule 44 — Normal pytest does not rewrite documentation

---

## Rule 45 — No large golden trajectory is the primary oracle

---

## Rule 46 — No mission PASS/FAIL criteria are calculated here

---

## Rule 47 — No controller tuning occurs here

---

## Rule 48 — No adaptive solver is added to production scenarios

---

## Rule 49 — Verification code remains inspectable and small

---

## Rule 50 — Claims remain honest about simplified physics

---

# 11. Acceptance Criteria

## AC-01 — Constant derivative integrates to exact solution

**Given** `dy/dt=c` and finite `h`  
**When** one or multiple RK4 steps execute  
**Then** the result matches `y0+cT` at near-roundoff tolerance.

---

## AC-02 — Zero derivative preserves state

**Given** `dy/dt=0`  
**When** RK4 steps execute  
**Then** state remains unchanged.

---

## AC-03 — Negative constant derivative works

**Given** negative constant derivative  
**When** integrated  
**Then** exact linear decrease is reproduced.

---

## AC-04 — Vector constant derivative works

**Given** a vector of constants  
**When** RK4 integrates  
**Then** every component matches its exact linear solution.

---

## AC-05 — Scalar decay matches exponential solution

**Given** `y'=-y`, `y(0)=1`  
**When** integrated to documented final time  
**Then** endpoint matches `exp(-T)` within explicit tolerance.

---

## AC-06 — Scalar growth matches exponential solution

**Given** bounded positive λ  
**When** integrated  
**Then** endpoint matches analytical exponential within tolerance.

---

## AC-07 — Time-dependent polynomial uses correct stage times

**Given** `y'=t^3`  
**When** RK4 advances  
**Then** result matches `y0+t^4/4` at near-roundoff tolerance.

---

## AC-08 — Harmonic oscillator position matches analytical solution

**Given** oscillator initial conditions  
**When** integrated  
**Then** sampled position matches cosine solution within documented tolerance.

---

## AC-09 — Harmonic oscillator velocity matches analytical solution

**Given** oscillator case  
**When** integrated  
**Then** sampled velocity matches negative-sine solution.

---

## AC-10 — Harmonic oscillator phase remains within tolerance

**Given** one/two periods  
**When** integrated at documented dt  
**Then** endpoint phase/state error passes.

---

## AC-11 — Mixed vector system matches exact components

**Given** decaying, time-dependent, and constant components  
**When** integrated  
**Then** all components match independent exact solutions.

---

## AC-12 — RK4 performs exactly four derivative evaluations per step

**Given** instrumented derivative  
**When** one step runs  
**Then** call count is four.

---

## AC-13 — RK4 uses correct stage times

**Given** instrumented time-dependent derivative  
**When** one step runs  
**Then** calls occur at `t`, `t+h/2`, `t+h/2`, `t+h`.

---

## AC-14 — RK4 uses correct intermediate states

**Given** a derivative spy  
**When** one step runs  
**Then** k2/k3/k4 state arguments follow classical RK4 formulas.

---

## AC-15 — RK4 uses 1-2-2-1 final weights

**Given** known stage values  
**When** final state is calculated  
**Then** weighted sum matches the classical formula.

---

## AC-16 — Applied input is identical across stages

**Given** fixed actuation input for a step  
**When** k1–k4 execute  
**Then** all receive the same input value/identity.

---

## AC-17 — RK4 does not mutate input state

**Given** original state/array  
**When** step completes  
**Then** original remains unchanged.

---

## AC-18 — Wrong derivative shape fails clearly

**Given** derivative returns incompatible shape  
**When** step executes  
**Then** numerical/runtime error is raised before committing state.

---

## AC-19 — Non-finite derivative fails clearly

**Given** derivative returns NaN/Inf  
**When** step executes  
**Then** state is not committed and error is raised.

---

## AC-20 — Exponential refinement errors decrease

**Given** documented h sequence  
**When** endpoint errors are calculated  
**Then** each asymptotic refinement has lower error.

---

## AC-21 — Exponential observed order approaches four

**Given** at least two consecutive asymptotic pairs  
**When** order is calculated  
**Then** it lies within the frozen accepted range around four.

---

## AC-22 — Exponential error ratio approaches sixteen

**Given** h and h/2 errors  
**When** ratio is calculated  
**Then** it lies within a documented range consistent with fourth-order convergence.

---

## AC-23 — Harmonic oscillator refinement demonstrates fourth-order behavior

**Given** suitable step sequence  
**When** position/velocity norm errors are measured  
**Then** observed order is consistent with RK4.

---

## AC-24 — Order calculation uses unrounded errors

**Given** measured errors  
**When** p is calculated  
**Then** raw values are used.

---

## AC-25 — Exact polynomial case is not used for observed-order assertion

**Given** near-roundoff polynomial errors  
**When** convergence suite is inspected  
**Then** order test uses a nonzero-error smooth case.

---

## AC-26 — Gravity-only vehicle matches analytical x

**Given** zero thrust/no horizontal force  
**When** real vehicle dynamics is integrated  
**Then** x matches `x0+vx0 t`.

---

## AC-27 — Gravity-only vehicle matches analytical vx

**Given** same case  
**When** integrated  
**Then** vx remains constant.

---

## AC-28 — Gravity-only vehicle matches analytical y

**Given** no ground contact during interval  
**When** integrated  
**Then** y matches ballistic formula.

---

## AC-29 — Gravity-only vehicle matches analytical vy

**Given** same case  
**When** integrated  
**Then** vy matches `vy0-g t`.

---

## AC-30 — Gravity-only attitude evolves correctly

**Given** zero torque  
**When** omega is constant  
**Then** theta matches `theta0+omega0t`.

---

## AC-31 — Gravity-only mass remains constant

**Given** zero throttle/fuel flow  
**When** integrated  
**Then** mass remains initial mass.

---

## AC-32 — Upright constant thrust preserves horizontal symmetry

**Given** upright zero-gimbal constant-mass case  
**When** integrated  
**Then** horizontal state matches analytical/no-drift result within tight tolerance.

---

## AC-33 — Upright constant thrust vertical motion matches analytical acceleration

**Given** constant thrust/mass/gravity  
**When** integrated  
**Then** y/vy match constant-acceleration solution.

---

## AC-34 — Fixed-gimbal custom RK4 reference succeeds

**Given** smooth open-loop vehicle case  
**When** custom trajectory is produced  
**Then** all states remain finite and above/away from discontinuity limits.

---

## AC-35 — Fixed-gimbal SciPy reference succeeds

**Given** the same equations/parameters/inputs  
**When** `solve_ivp` runs  
**Then** success/status/shape/finite checks pass.

---

## AC-36 — Fixed-gimbal x trajectory matches reference

**Given** aligned sample times  
**When** compared  
**Then** max and endpoint x errors pass measured tolerance.

---

## AC-37 — Fixed-gimbal y trajectory matches reference

**Given** aligned sample times  
**When** compared  
**Then** y errors pass.

---

## AC-38 — Fixed-gimbal velocity trajectories match reference

**Given** aligned samples  
**When** compared  
**Then** vx/vy errors pass.

---

## AC-39 — Fixed-gimbal attitude trajectory matches reference

**Given** aligned samples  
**When** compared  
**Then** wrapped theta and omega errors pass.

---

## AC-40 — Fuel-burning mass trajectory matches reference

**Given** smooth pre-dry-mass case  
**When** compared  
**Then** mass max/endpoint errors pass.

---

## AC-41 — Fuel-burning case never reaches dry-mass clamp

**Given** configured end time  
**When** both trajectories run  
**Then** all sampled masses exceed dry mass by documented margin.

---

## AC-42 — Open-loop comparison checks full trajectory

**Given** custom/reference samples  
**When** verification runs  
**Then** max sampled errors are checked, not endpoint only.

---

## AC-43 — Open-loop comparison checks endpoint

**Given** same data  
**When** verification runs  
**Then** endpoint component errors are also reported/asserted.

---

## AC-44 — Open-loop comparison uses per-state tolerances

**Given** seven-state trajectory  
**When** compared  
**Then** errors are not judged by one unscaled raw norm only.

---

## AC-45 — Near-zero components use absolute scale

**Given** reference value near zero  
**When** normalized error is calculated  
**Then** denominator remains meaningful and no infinite relative error appears.

---

## AC-46 — Angle comparison handles wrapping

**Given** equivalent angles across ±π boundary  
**When** compared  
**Then** shortest wrapped error is used.

---

## AC-47 — SciPy reference uses high-accuracy settings

**Given** reference helper  
**When** inspected/executed  
**Then** method/tolerances are explicitly documented and materially tighter than custom acceptance limits.

---

## AC-48 — Reference self-consistency passes

**Given** baseline and tighter reference settings  
**When** trajectories compare  
**Then** their difference is much smaller than custom-RK4 allowed error.

---

## AC-49 — Reference sample times align with production ticks

**Given** production tick array  
**When** SciPy output is requested  
**Then** each reference sample corresponds to the same time.

---

## AC-50 — Reference result shape matches seven-state order

**Given** solve_ivp output  
**When** adapted  
**Then** state ordering and sample count are correct.

---

## AC-51 — State adapter round-trips

**Given** representative VehicleState  
**When** converted to array and back  
**Then** every named field is preserved.

---

## AC-52 — State adapter ordering error is detectable

**Given** a deliberately swapped test fixture/component  
**When** verification runs  
**Then** analytical/reference comparison fails.

---

## AC-53 — Piecewise schedule boundaries align to ticks

**Given** command schedule  
**When** verification config validates  
**Then** every boundary maps exactly to an integer tick for each tested dt.

---

## AC-54 — Piecewise SciPy reference restarts at each discontinuity

**Given** multiple input segments  
**When** helper executes  
**Then** one solver segment is used per constant-input interval.

---

## AC-55 — Piecewise reference does not duplicate shared-boundary samples

**Given** concatenated segments  
**When** trajectory is assembled  
**Then** sample times are strictly ordered and unique.

---

## AC-56 — Piecewise custom/reference trajectories match

**Given** same input-hold schedule  
**When** compared  
**Then** all state tolerances pass.

---

## AC-57 — Time-triggered software subsystems are absent from open-loop reference

**Given** numerical reference test  
**When** dependencies/calls are inspected  
**Then** no sensor/controller/mission/fault scheduler is executed.

---

## AC-58 — Ground contact is absent from formal smooth comparisons

**Given** verification case interval  
**When** trajectories run  
**Then** y stays above ground margin and no contact clamp/event occurs.

---

## AC-59 — Dry-mass clamp is absent from formal convergence comparisons

**Given** fuel-burning case  
**When** interval completes  
**Then** mass remains above clamp margin.

---

## AC-60 — Production module does not import solve_ivp

**Given** production simulation source  
**When** architecture test scans imports  
**Then** SciPy integration is absent from runtime scheduler/integrator.

---

## AC-61 — Numerical tests use solve_ivp only in reference/test code

**Given** repository source  
**When** imports are inspected  
**Then** allowed references are limited to numerical test/helper locations.

---

## AC-62 — Candidate production dt passes all required reference cases

**Given** selected dt  
**When** analytical/SciPy comparisons run  
**Then** all frozen component tolerances pass.

---

## AC-63 — Refining production dt reduces smooth-case error

**Given** dt and dt/2  
**When** compared to reference  
**Then** refined error is lower in documented cases.

---

## AC-64 — Production dt versus dt/2 difference is within documented envelope

**Given** representative open-loop cases  
**When** state/metric differences are measured  
**Then** they pass the final step-sensitivity tolerance.

---

## AC-65 — Coarser step can expose a meaningful error increase

**Given** a deliberately coarser verification step  
**When** compared  
**Then** error trend increases as expected, demonstrating the test is sensitive.

The coarse step need not be a production-supported configuration.

---

## AC-66 — Production dt remains finite/stable over tested duration

**Given** documented parameter envelope  
**When** open-loop cases execute  
**Then** no non-finite state or numerical invariant failure occurs.

---

## AC-67 — Numerical verification does not impose a wall-clock performance assertion

**Given** numerical suite  
**When** inspected  
**Then** correctness is not based on elapsed machine time.

---

## AC-68 — Numerical tests run deterministically

**Given** identical environment/config  
**When** executed repeatedly  
**Then** custom trajectories and verification results match.

---

## AC-69 — Numerical tests are included in full pytest

**Given** default quality gate  
**When** `uv run pytest` executes  
**Then** reasonably fast analytical/SciPy verification tests run.

---

## AC-70 — Focused numerical command works

**Given** dev environment  
**When** `uv run pytest tests/numerical` executes  
**Then** all numerical cases run independently.

---

## AC-71 — Verification failures identify case/component/tolerance

**Given** component error exceeds limit  
**When** test fails  
**Then** output names the case, state component, measured error, and tolerance.

---

## AC-72 — Verification report contains measured values only

**Given** completed implementation  
**When** `docs/NUMERICAL_VERIFICATION.md` is reviewed  
**Then** convergence/error tables contain actual test results, not placeholders.

---

## AC-73 — Verification report states reference settings

**Given** documentation  
**When** reviewed  
**Then** SciPy method, rtol, atol, evaluation interval, and sample policy are recorded.

---

## AC-74 — Verification report states production dt decision

**Given** measured study  
**When** reviewed  
**Then** selected dt and justification are explicit.

---

## AC-75 — Verification report states supported envelope

**Given** documentation  
**When** reviewed  
**Then** tested durations/parameters/discontinuity exclusions are clear.

---

## AC-76 — Verification report states limitations honestly

**Given** documentation  
**When** reviewed  
**Then** it does not claim real-vehicle fidelity, unconditional stability, or certification.

---

## AC-77 — Normal pytest does not rewrite verification docs

**Given** test execution  
**When** repository status is checked  
**Then** no tracked report file is modified.

---

## AC-78 — Numerical bug receives permanent regression test

**Given** a confirmed stage/sign/index/timing bug  
**When** fixed  
**Then** a minimal deterministic test remains.

---

## AC-79 — Mission validation remains separate

**Given** numerical verification source  
**When** inspected  
**Then** it does not calculate landing PASS/FAIL scenario outcomes.

---

## AC-80 — Portfolio numerical claim is reproducible

**Given** clean locked dev environment  
**When** reviewer runs the documented numerical command  
**Then** analytical convergence, open-loop SciPy comparisons, and supported-dt checks pass without manual intervention.

---

# 12. Test Plan

## Directory

```text
tests/numerical/
├── __init__.py
├── reference.py
├── test_rk4_formula.py
├── test_rk4_analytical.py
├── test_rk4_convergence.py
├── test_vehicle_analytical.py
├── test_vehicle_against_scipy.py
├── test_piecewise_actuation.py
└── test_timestep_sensitivity.py
```

`reference.py` is test helper code, not production runtime.

---

## `test_rk4_formula.py`

Required:

```text
four stage calls
stage times
intermediate states
1-2-2-1 weights
constant discrete input
input state immutability
shape/non-finite errors
```

---

## `test_rk4_analytical.py`

Required:

```text
constant derivative
zero derivative
scalar exponential decay
scalar bounded growth
time cubic derivative
harmonic oscillator
mixed vector system
```

---

## `test_rk4_convergence.py`

Required:

```text
step sequence
endpoint errors
error ratios
observed order
asymptotic-range checks
monotonic refinement
optional log-log slope
```

Use readable parametrized IDs.

---

## `test_vehicle_analytical.py`

Required:

```text
gravity-only full state
constant-mass upright thrust if supported
horizontal symmetry
constant angular-rate evolution
mass invariance
```

---

## `test_vehicle_against_scipy.py`

Required:

```text
fixed gimbal
fuel-burning smooth case
reference success
self-consistency
per-component trajectory/endpoint errors
normalized max error
finite states
```

---

## `test_piecewise_actuation.py`

Required:

```text
segment validation
exact boundary alignment
one reference solve per segment
unique concatenated sample times
custom/reference comparison
input-hold semantics
```

---

## `test_timestep_sensitivity.py`

Required:

```text
candidate dt
dt/2
dt/4
reference comparison
refinement differences
supported envelope
coarse-step sensitivity
```

---

## Test helpers

Recommended records:

```python
@dataclass(frozen=True)
class ReferenceTrajectory:
    time: NDArray[np.float64]
    state: NDArray[np.float64]
```

```python
@dataclass(frozen=True)
class ComponentError:
    name: str
    max_abs: float
    endpoint_abs: float
    tolerance: float
```

```python
@dataclass(frozen=True)
class ConvergenceRow:
    step_size: float
    error: float
    ratio: float | None
    observed_order: float | None
```

---

## Failure-message helper

```python
def assert_component_errors(
    *,
    case_id: str,
    errors: tuple[ComponentError, ...],
) -> None:
    failures = [
        error
        for error in errors
        if error.max_abs > error.tolerance
    ]

    if not failures:
        return

    message = "\n".join(
        (
            f"{case_id}: {item.name}: "
            f"max_abs={item.max_abs:.6e}, "
            f"tol={item.tolerance:.6e}"
        )
        for item in failures
    )

    pytest.fail(message, pytrace=False)
```

---

## Manual QA checklist

- [ ] RK4 implementation is short/inspectable.
- [ ] Direct stage formula test exists.
- [ ] Time-dependent derivative case exists.
- [ ] Scalar exact solution exists.
- [ ] Vector exact solution exists.
- [ ] Oscillator case exists.
- [ ] Observed order is measured.
- [ ] Error ratio is measured.
- [ ] Actual vehicle gravity-only analytical test exists.
- [ ] Real vehicle open-loop SciPy case exists.
- [ ] Varying mass case exists.
- [ ] Piecewise actuation is segmented correctly.
- [ ] Reference settings are tighter than test tolerance.
- [ ] Reference self-consistency is checked.
- [ ] Full trajectory and endpoint are checked.
- [ ] Per-state units/tolerances are visible.
- [ ] Angle error is handled.
- [ ] Ground/dry-mass discontinuities are excluded from smooth tests.
- [ ] SciPy does not appear in production runtime.
- [ ] Candidate production dt passes.
- [ ] Refined dt reduces error.
- [ ] Verification report contains measured values.
- [ ] No fabricated numerical claim exists.
- [ ] All tests pass in locked environment.

---

## Demo verification checklist

- [ ] Reviewer can run `uv run pytest tests/numerical`.
- [ ] Output identifies analytical/SciPy verification cases.
- [ ] README/docs show one concise convergence table.
- [ ] Documentation states why fixed-step runtime is used.
- [ ] Documentation states why SciPy is reference-only.
- [ ] Production dt is justified with measured evidence.
- [ ] No claim exceeds tested simplified model.
- [ ] A technical interviewer can inspect the RK4 function and tests quickly.
- [ ] Verification adds depth without adding a second production engine.

---

# 13. Portfolio Value

## How this feature helps the project stand out

Many portfolio simulations either:

- rely entirely on a black-box solver; or
- implement an integrator with no independent evidence.

AstraLoop can make a stronger claim:

> “I implemented a deterministic fixed-step RK4 runtime because the system has exact discrete software timing. I verified the integrator’s fourth-order behavior on analytical problems and compared the actual open-loop vehicle dynamics against a tighter SciPy `solve_ivp` reference.”

That demonstrates:

- numerical methods;
- verification thinking;
- independent test-oracle design;
- error analysis;
- hybrid-system architecture;
- engineering honesty.

---

## What to mention in README

Recommended wording after measurements:

> **Independently verified numerics:** AstraLoop’s production loop uses a project-owned fixed-step RK4 integrator. Analytical convergence tests demonstrate fourth-order behavior on smooth ODEs, and selected open-loop vehicle trajectories are compared against a high-accuracy SciPy `solve_ivp` reference. The documented production timestep is supported only for the tested project parameter/scenario envelope.

Do not include measured error/order numbers until the tests exist.

---

## What to mention in interviews

### Why write RK4 instead of using SciPy in production?

> “The main challenge is hybrid timing, not only continuous integration. Fixed ticks make sensor sampling, controller updates, actuator response, fault activation, state transitions, and telemetry exact and reproducible.”

### How did you verify your implementation?

> “I used exact scalar and vector ODEs, measured fourth-order convergence under step refinement, verified stage times and weights directly, and compared the real open-loop seven-state dynamics against a tighter independent SciPy reference.”

### Why can both custom RK4 and SciPy still agree on a wrong model?

> “They reuse the same vehicle derivative in the open-loop comparison, so that comparison isolates integration error. Separate analytical gravity/thrust/symmetry tests validate the derivative signs, state ordering, and units.”

### How did you handle command discontinuities?

> “Production commands are piecewise constant per tick. I restart the adaptive reference at each exact command boundary so it does not smooth across an unmodeled discontinuity.”

### What does fourth-order convergence mean?

> “For a smooth problem over a fixed interval, halving the step should reduce global error by about sixteen, so the observed order `log2(Eh/Eh/2)` approaches four.”

### How did you choose tolerances?

> “The SciPy reference uses much tighter settings and passes a self-consistency check. I use state-specific tolerances based on measured production-step error and keep them much smaller than mission acceptance limits.”

### Is the selected timestep guaranteed for all configurations?

> “No. It is verified for the documented AstraLoop parameter and scenario envelope. Extreme user parameters may require a smaller step.”

### Did you compare full trajectories or only final values?

> “Both. Endpoint checks can miss transient or phase error, so I also compare the maximum per-component error over aligned sample times.”

---

# 14. Implementation Notes for Codex

## Likely files/folders

Production remains:

```text
src/astraloop/simulation/
├── dynamics.py
├── integrators.py
└── engine.py
```

Verification:

```text
tests/numerical/
├── reference.py
├── test_rk4_formula.py
├── test_rk4_analytical.py
├── test_rk4_convergence.py
├── test_vehicle_analytical.py
├── test_vehicle_against_scipy.py
├── test_piecewise_actuation.py
└── test_timestep_sensitivity.py
```

Documentation after measurement:

```text
docs/NUMERICAL_VERIFICATION.md
```

Optional report helper:

```text
scripts/generate_numerical_verification.py
```

Only add the script if it reduces real manual work.

---

## Build order

### Step 1 — Lock RK4 callable interface

Prefer:

```python
rk4_step(
    *,
    t: float,
    state: State,
    dt: float,
    derivative: DerivativeFn,
    inputs: Inputs,
) -> State
```

Production autonomous dynamics may ignore `t`.

---

### Step 2 — Add direct formula/stage tests

Before SciPy.

---

### Step 3 — Add constant/polynomial/exponential exact tests

---

### Step 4 — Add harmonic oscillator/vector tests

---

### Step 5 — Add convergence table helper

---

### Step 6 — Confirm observed order

Fix implementation before continuing.

---

### Step 7 — Add VehicleState array adapters tests

---

### Step 8 — Add gravity-only vehicle analytical case

---

### Step 9 — Add high-accuracy solve_ivp helper

Keep in tests.

---

### Step 10 — Add fixed-gimbal open-loop comparison

---

### Step 11 — Add fuel-burning smooth comparison

---

### Step 12 — Add piecewise input segmentation

---

### Step 13 — Run production-dt sensitivity

---

### Step 14 — Freeze measured state tolerances

---

### Step 15 — Write measured verification document

---

### Step 16 — Add architecture test forbidding SciPy runtime import

---

## Risks

### Risk 1 — Shared wrong derivative creates false confidence

**Mitigation:** analytical vehicle cases plus SciPy comparison.

---

### Risk 2 — SciPy reference is not accurate enough

**Mitigation:** tighter settings/self-consistency.

---

### Risk 3 — Comparing across discontinuity hides order

**Mitigation:** smooth cases and exact segmentation.

---

### Risk 4 — Step sizes do not divide final interval

**Mitigation:** integer step-count helper and validation.

---

### Risk 5 — Error reaches roundoff floor

**Mitigation:** choose asymptotic step range.

---

### Risk 6 — One raw norm hides angular/mass errors

**Mitigation:** per-component tolerances and normalized max.

---

### Risk 7 — Relative error explodes near zero

**Mitigation:** absolute + relative scales.

---

### Risk 8 — Endpoint passes while transient diverges

**Mitigation:** full aligned trajectory checks.

---

### Risk 9 — Tolerances chosen after failure to make tests green

**Mitigation:** measure, justify, record reference error and mission-scale margin.

---

### Risk 10 — Reference solver leaks into production

**Mitigation:** directory/import architecture test.

---

### Risk 11 — Overclaiming stability/accuracy

**Mitigation:** documented supported envelope and limitations.

---

### Risk 12 — Numerical suite becomes slow

**Mitigation:** short cases, limited step grids, no campaigns.

---

### Risk 13 — Report contains stale copied values

**Mitigation:** measured helper/table generation process and explicit update instructions.

---

### Risk 14 — Production dt chosen only for speed

**Mitigation:** accuracy/refinement evidence first; performance measured separately.

---

### Risk 15 — Dynamics is changed solely to make an analytical test convenient

**Mitigation:** choose a reference-compatible valid configuration or use SciPy; do not distort production model.

---

## What not to change

While implementing Feature 13, Codex should **not**:

- replace production RK4 with `solve_ivp`;
- call adaptive integration inside the mission tick loop;
- add multiple production integrators;
- put SciPy calls in `engine.py`;
- include sensor/controller/mission/fault behavior inside continuous reference RHS;
- compare through ground/dry-mass discontinuities as if smooth;
- hide command discontinuities inside one solver segment;
- round errors before order calculations;
- use exact equality for arbitrary trajectories;
- select tolerances without measured evidence;
- widen tolerances only to pass;
- fabricate report numbers;
- claim real aerospace fidelity;
- claim unconditional stability;
- add Monte Carlo;
- add performance benchmark frameworks;
- add GUI plots for convergence unless genuinely needed;
- write tracked docs during normal pytest;
- turn verification helpers into a general solver package;
- change mission validation criteria.

---

# Feature-Specific Definition of Done

Feature 13 is complete when:

- [ ] Direct RK4 stage/weight test exists.
- [ ] Constant derivative exact test exists.
- [ ] Time-dependent polynomial test exists.
- [ ] Scalar exponential tests exist.
- [ ] Harmonic oscillator test exists.
- [ ] Mixed vector test exists.
- [ ] Input state immutability is tested.
- [ ] Four derivative calls are tested.
- [ ] Fixed input across stages is tested.
- [ ] Non-finite/shape failures are tested.
- [ ] Step-refinement table helper exists.
- [ ] Observed fourth-order behavior is demonstrated.
- [ ] Error-ratio trend is demonstrated.
- [ ] Gravity-only real dynamics analytical test exists.
- [ ] Upright symmetry/constant-thrust case exists when supported.
- [ ] VehicleState adapter ordering is tested.
- [ ] SciPy reference helper exists in tests only.
- [ ] Reference method/tolerances are explicit.
- [ ] Reference self-consistency is checked.
- [ ] Fixed-gimbal full-state comparison exists.
- [ ] Fuel-burning smooth comparison exists.
- [ ] Piecewise actuation reference segmentation exists.
- [ ] Full trajectories and endpoints are checked.
- [ ] Per-state tolerances are measured/frozen.
- [ ] Wrapped angle error is handled.
- [ ] Formal cases avoid ground/dry-mass discontinuities.
- [ ] Candidate production dt is studied.
- [ ] Refinement reduces error.
- [ ] Supported production dt passes.
- [ ] Supported envelope is documented.
- [ ] SciPy is absent from production scheduler.
- [ ] Numerical tests run with default pytest.
- [ ] Focused numerical command works.
- [ ] Failures name component/error/tolerance.
- [ ] Numerical bugs receive regression tests.
- [ ] `docs/NUMERICAL_VERIFICATION.md` contains measured results.
- [ ] Documentation states limitations honestly.
- [ ] No fabricated numerical values remain.
- [ ] README can truthfully claim independent numerical verification.

---

# Open Questions

1. **[Open Question] What final production timestep should AstraLoop use?**  
   `0.02 s` is the current architecture example, not a final measured conclusion.

2. **[Open Question] Which exact step sequence gives the clearest asymptotic fourth-order range?**  
   Measure exponential and oscillator cases.

3. **[Open Question] Should DOP853 or RK45 be the frozen SciPy reference method?**  
   Recommended DOP853 for smooth high-accuracy reference.

4. **[Open Question] What final reference `rtol` and component `atol` values are needed?**  
   Measure self-consistency and keep reference error far below custom tolerance.

5. **[Open Question] What final per-component RK4-versus-SciPy tolerances should be frozen?**  
   They depend on final vehicle parameters, duration, and production dt.

6. **[Open Question] Which fixed-gimbal/throttle values create a useful smooth coupled case without approaching ground/dry mass/extreme angle?**

7. **[Open Question] Can the production vehicle config represent constant thrust with zero mass flow for an analytical test?**  
   Use a valid test config only if supported; otherwise rely on SciPy.

8. **[Open Question] How long should oscillator/open-loop intervals be?**  
   Long enough to expose phase/error, short enough to keep tests quick and smooth.

9. **[Open Question] Should maximum RMS error be reported in addition to max/endpoint?**  
   Optional; max + endpoint are sufficient for MVP.

10. **[Open Question] Should a convergence PNG be generated for documentation?**  
    A small table is sufficient; avoid adding a second required plot.

11. **[Open Question] Should the verification report be generated by script or updated manually from test output?**  
    Prefer the simplest process that prevents stale/fabricated values.

12. **[Open Question] Should source-code/package version metadata appear in the report?**  
    Useful but not required for initial MVP.

13. **[Open Question] Should one representative closed-loop mission be rerun at dt/2 as a sensitivity check?**  
    Useful as a regression observation, but exact hybrid trajectories may change due to discrete cadence. Keep it separate from formal fourth-order claims.

14. **[Open Question] Should the normal full pytest include every SciPy case?**  
    Include all reasonably fast deterministic correctness tests; avoid hidden optional numerical correctness.

15. **[Open Question] What exact numerical claim belongs in the resume/README?**  
    Only measured facts after implementation, such as observed order range and maximum reference error.

---

# Move On When

- [ ] Custom RK4 is independently verified.
- [ ] Fourth-order behavior is demonstrated on smooth problems.
- [ ] Actual open-loop vehicle dynamics match a tighter SciPy reference.
- [ ] Piecewise input semantics are verified correctly.
- [ ] Production dt has measured support.
- [ ] Numerical tolerances are explicit and justified.
- [ ] Verification tests are deterministic and fast enough for normal pytest.
- [ ] Documentation records real measured values and limitations.
- [ ] SciPy remains outside production scheduling.
- [ ] Technical interviewer can understand the verification strategy quickly.
- [ ] No unnecessary adaptive runtime, extra solver framework, Monte Carlo, database, GUI, or certification claim has been added.
- [ ] The project is ready for Feature 14 — Polished CLI.
