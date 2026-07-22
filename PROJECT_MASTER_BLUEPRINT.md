# PROJECT MASTER BLUEPRINT

## AstraLoop — Python Software-in-the-Loop Flight Control & Validation System

> **Purpose:** Master implementation blueprint for a finishable, local, Python-first portfolio project aimed at software engineering internships in systems, simulation, validation, testing, and hardware-adjacent software.
>
> **Positioning rule:** The rocket is the domain. The hiring signal is the software engineering.

---

# 1. Project Summary

## Project name

**[Decision] AstraLoop**

**Subtitle:** *Python Software-in-the-Loop Flight Control & Validation System*

## One-sentence description

**[Decision]** AstraLoop is a local Python simulation and validation system for a simplified 2D reusable launch vehicle, where autonomous flight software controls numerically simulated physics using imperfect sensor measurements and is tested against reproducible nominal and fault-injected missions.

## Longer description

**[Confirmed]** The Step 1 direction defines AstraLoop as a fully local, Python-only software-in-the-loop project rather than a SaaS product, physical rocket, scripted animation, or Starship replica.

**[Decision]** The system will simulate a simplified planar vehicle with horizontal/vertical motion, pitch dynamics, actuator behavior, fuel/mass change, imperfect sensors, closed-loop control, an explicit mission state machine, reproducible fault injection, telemetry, automated scenario validation, and reviewer-friendly visualization.

The most important architectural separation is:

```text
TRUE SIMULATION STATE
        |
        v
   SENSOR MODELS
(noise/bias/delay/faults)
        |
        v
   ESTIMATED / MEASURED STATE
        |
        v
    CONTROLLERS
        |
        v
   ACTUATOR MODELS
(saturation/lag/faults)
        |
        v
   PHYSICS / DYNAMICS
        |
        +------> next true state
```

**[Decision]** The controller must not use perfect simulator truth as its normal input. This design forces the project to deal with uncertainty, timing, failure modes, interfaces, and validation.

## Target role

**[Decision] Primary target:** Software Engineering Intern — Systems / Simulation / Validation

**[Decision] Secondary targets:**
- Software Test / Validation Engineering Intern
- Modeling & Simulation Software Intern
- Systems Software Intern
- Hardware-adjacent Software Engineering Intern

**[Researched]** The Step 1 research found that AMD software and validation-oriented roles commonly value software-engineering fundamentals plus Python/scripting, testing, debugging, simulation, emulation, or validation. AstraLoop should therefore be marketed as a simulation/validation software project rather than as an aerospace-specialist project.

## Target reviewer

### Recruiter
Needs to understand the project in approximately one minute.

They should immediately see:
- Python
- simulation
- autonomous control
- fault injection
- automated testing
- reproducible scenarios
- telemetry
- clean architecture

### Hiring manager
Needs evidence that the project was engineered rather than merely demonstrated.

They should see:
- clear boundaries between modules
- deterministic execution
- automated verification
- sensible scope decisions
- error handling
- configuration-driven behavior
- realistic tradeoffs

### Technical interviewer
Needs enough depth to ask strong engineering questions.

Likely discussion areas:
- Why truth state is isolated from controller input
- How sensor delay/bias/noise are modeled
- Why a fixed simulation timestep was chosen
- How mission states and transition guards are designed
- How controllers are tuned
- How fault scenarios are injected without duplicating code
- How deterministic runs are guaranteed
- How PASS/FAIL criteria are defined
- How continuous numerical output is tested

## Main skill signal

**[Decision]** The primary signal is:

> **Ability to turn a stateful, numerical, failure-prone system into clean, testable, deterministic Python software.**

Supporting signals:
- numerical programming
- software architecture
- control-system logic
- validation engineering
- automated testing
- observability and debugging
- reproducibility
- technical communication

---

# 2. Why This Project Is Worth Building

## What it proves

**[Decision]** AstraLoop proves more than Python syntax or UI development. A strong finished build demonstrates that the developer can:

1. Model a nontrivial evolving system.
2. Separate domain logic into clean modules.
3. Define interfaces between simulation, sensing, control, and actuation.
4. Handle imperfect data rather than perfect inputs.
5. Design deterministic stateful logic.
6. Inject failures deliberately.
7. Capture telemetry for debugging.
8. Create objective mission-level validation criteria.
9. Test numerical and discrete behavior.
10. Document design tradeoffs.

## Why it is not just a tutorial clone

**[Confirmed]** The Step 1 brief explicitly rejects:
- hard-coded flight paths
- precomputed rocket animations
- one giant notebook
- perfect-state PID control
- a single nominal demonstration
- visual complexity without testing

**[Decision]** AstraLoop becomes portfolio-grade because multiple engineering concerns interact:

```text
physics
  + sensors
  + timing
  + control
  + actuators
  + state transitions
  + failures
  + telemetry
  + automated acceptance criteria
```

A tutorial commonly teaches one of those components. AstraLoop's value comes from integrating them into one coherent validation system.

## What makes it memorable

**[Decision]** The memorable demonstration is not merely "a rocket lands."

It is:

> "Here is the exact same autonomous controller in two deterministic simulations. In the nominal run it lands within limits. In the fault run, the altitude sensor freezes, telemetry shows the effect, the state machine responds, and the run produces an objective PASS/FAIL result."

That is concrete, visual, testable, and easy to discuss.

## What interview questions it can create

AstraLoop should naturally invite questions such as:

- How did you prevent the controller from cheating with perfect simulation state?
- Why did you choose 2D planar dynamics instead of 1D or full 6-DOF?
- How did you choose the integration strategy?
- How are sensor measurements timestamped?
- How is sensor delay implemented?
- How does actuator lag differ from command saturation?
- How do you guarantee reproducibility?
- What makes a mission pass or fail?
- How do you test a PID controller?
- How do you test state-machine transitions?
- What happens when a sensor value becomes stale?
- How would you add a new fault without changing the core simulator?
- What did telemetry reveal while debugging?
- What would you change for real-time or hardware-in-the-loop execution?
- What did you intentionally leave out?

---

# 3. User / Use Case

## Who would use it locally

**[Decision] Primary local user:** the developer or technical reviewer running engineering scenarios from a terminal.

**[Assumption] Secondary local user:** a student, interviewer, or engineering teammate who wants to inspect how a closed-loop controller behaves under nominal and faulty conditions.

This is not intended for a large public user base.

## Main use case

Run a configured flight scenario locally, observe the autonomous system, inspect generated telemetry, and receive objective mission validation results.

Example command shape:

```bash
python -m astraloop run scenarios/nominal.toml
```

Possible output:

```text
Scenario: nominal
Seed: 42
Result: PASS
Final state: LANDED

Landing vertical speed: 1.31 m/s   [limit <= 2.00]
Horizontal error:       2.18 m     [limit <= 5.00]
Pitch error:            1.84 deg   [limit <= 5.00]

Artifacts:
  runs/2026-07-21_184500_nominal/telemetry.csv
  runs/2026-07-21_184500_nominal/events.json
  runs/2026-07-21_184500_nominal/summary.json
  runs/2026-07-21_184500_nominal/flight_plot.png
```

## Example scenario

### Nominal descent and landing

1. Scenario configuration loads.
2. Simulation seed is fixed.
3. Initial state is created.
4. Mission begins in `PRELAUNCH`.
5. State machine transitions through the defined mission phases.
6. Sensors produce measured values.
7. Controller calculates throttle and pitch commands.
8. Actuator models apply saturation and lag.
9. Physics advances by one timestep.
10. Telemetry records truth, measurement, command, actuator output, state, and events.
11. Mission reaches `LANDED` or a terminal failure state.
12. Validator evaluates objective metrics.
13. Artifacts are saved.
14. CLI prints PASS/FAIL summary.

## Demo story

**[Decision] Recommended recruiter demo: approximately 60–90 seconds.**

### Step A — Show architecture
Open the README architecture diagram and explain:

> "The controller never reads perfect simulator state. Physics feeds simulated sensors, the controller sees only those measurements, actuator commands feed back into the dynamics, and every run is validated automatically."

### Step B — Run nominal mission

```bash
python -m astraloop run scenarios/nominal.toml
```

Show:
- PASS
- landing metrics
- plot

### Step C — Run one failure

```bash
python -m astraloop run scenarios/altimeter_freeze.toml
```

Show:
- injected fault event
- changed behavior
- resulting PASS/recovery or controlled FAIL/ABORT
- telemetry comparison

### Step D — Run tests

```bash
pytest
```

End with:

> "The same engine powers interactive runs and automated scenario tests."

---

# 4. Core Feature Set

## Feature 1: 2D Planar Vehicle Dynamics

### Description

**[Confirmed]** The Step 1 Gold direction calls for 2D planar dynamics rather than 1D or full 6-DOF.

**[Decision]** The minimum true-state vector should include:

```text
x       horizontal position [m]
y       vertical position [m]
vx      horizontal velocity [m/s]
vy      vertical velocity [m/s]
theta   pitch angle [rad]
omega   angular rate [rad/s]
mass    current vehicle mass [kg]
```

Possible control-related state:
- actual throttle
- actual gimbal/pitch actuator state

The dynamics should include simplified:
- gravity
- thrust
- thrust direction
- translational acceleration
- rotational acceleration
- fuel consumption / mass change
- optional bounded disturbance force

### Why it matters for the project

This is the numerical core. Without real state evolution, the rest becomes a scripted visualization.

### Skill it demonstrates

- NumPy
- mathematical modeling
- numerical integration
- unit consistency
- state representation
- clean separation between model and orchestration

### User flow

The user does not manipulate equations directly.

1. Select scenario.
2. Scenario supplies vehicle parameters and initial state.
3. Simulation engine advances vehicle state.
4. Results appear through telemetry and plots.

### Data needed

Vehicle parameters, such as:
- dry mass
- initial fuel mass
- maximum thrust
- nominal specific fuel-use approximation
- moment of inertia
- maximum gimbal angle
- gravitational acceleration
- initial state

### UI/UX requirements

CLI should expose only useful information:
- scenario name
- timestep
- elapsed simulated time
- final mission result
- artifact paths

Detailed physics output should be written to telemetry rather than flooding the terminal.

### Backend or logic requirements

**[Decision]**
- Use explicit typed data structures.
- Dynamics function accepts current state + applied actuator state + environment.
- Dynamics function returns derivatives or next-state contribution.
- No controller logic inside the dynamics module.
- No file I/O inside core equations.
- Prevent negative mass/fuel.
- Normalize or safely handle pitch angle representation.

### Local-run considerations

- Must run entirely offline.
- No GPU required.
- One nominal mission should complete quickly enough for a live demo.
- Simulation should support headless execution.

### Acceptance criteria

- [ ] State evolves numerically rather than through hard-coded coordinates.
- [ ] Zero thrust produces physically sensible downward acceleration.
- [ ] Symmetric vertical thrust does not spontaneously create horizontal acceleration.
- [ ] Pitch angle changes thrust direction.
- [ ] Mass never drops below dry mass.
- [ ] Integrator remains stable for the documented timestep.
- [ ] Dynamics unit tests cover known/simple conditions.
- [ ] Same initial conditions and actuator sequence produce the same result.

### Edge cases

- fuel reaches zero
- vehicle reaches/breaches ground level
- pitch wraps beyond expected range
- actuator command is NaN or infinite
- negative timestep
- extreme command values
- numeric instability
- state vector contains non-finite values

### Complexity

**High**

### Job-market value

**High**

---

## Feature 2: Simulated Sensors, Closed-Loop Controllers, and Actuators

### Description

**[Confirmed]** The controller must consume simulated measurements rather than perfect truth.

**[Decision]** Build a small sensor suite:

- altimeter → measured altitude
- vertical velocity sensor
- horizontal position/velocity sensor
- attitude sensor → pitch
- gyro → angular rate

Each sensor should share a common interface and support selected imperfections:
- noise
- constant bias
- latency/delay
- freeze
- stale reading behavior

**[Decision]** Build:
- throttle controller
- pitch/attitude controller
- actuator saturation
- actuator response lag

Avoid advanced estimation in the MVP unless basic raw measurement control proves insufficient.

### Why it matters for the project

This is the feature that turns the project from "physics animation" into closed-loop software-in-the-loop engineering.

### Skill it demonstrates

- interfaces
- dependency boundaries
- feedback control
- imperfect-data handling
- configuration
- deterministic randomness
- modular design

### User flow

1. Physics produces true state.
2. Sensor subsystem samples that state.
3. Fault model modifies measurements when configured.
4. Controller receives a measurement snapshot.
5. Controller produces desired commands.
6. Actuator subsystem applies limits and lag.
7. Physics receives actual actuator output.

### Data needed

Per-sensor configuration:
- sample interval
- noise standard deviation
- bias
- delay
- enabled/disabled
- fault parameters

Controller configuration:
- proportional gain
- integral gain if used
- derivative gain if used
- output limits
- integral windup limit
- state-specific setpoints

Actuator configuration:
- min/max throttle
- max gimbal/pitch command
- response time constant
- slew/rate limit if used

### UI/UX requirements

Plots should allow a reviewer to compare:
- truth vs measured altitude
- truth vs measured pitch
- requested vs actual throttle
- requested vs actual attitude/gimbal command

### Backend or logic requirements

- Controller API receives a measurement object, mission mode, and timestep.
- Controller module must not import or depend on the true vehicle state type as a normal control input.
- Random noise must use an injected seeded RNG.
- Delay should use timestamped/sample buffering, not arbitrary sleeps.
- Saturation should be applied explicitly and recorded.
- Integral state should reset or transition safely between relevant mission modes.

### Local-run considerations

- Never use real wall-clock sleep to model sensor delay.
- Simulation time must be independent of computer speed.
- Seed should be part of scenario metadata.

### Acceptance criteria

- [ ] Controller cannot access perfect truth through its public API.
- [ ] Sensor noise is deterministic for the same seed.
- [ ] Bias changes measurement by the configured amount.
- [ ] Freeze fault holds the last valid sensor reading after activation.
- [ ] Delay returns appropriately older simulation-time samples.
- [ ] Commands respect actuator bounds.
- [ ] Actual actuator output exhibits configured lag.
- [ ] Nominal controller reaches MVP landing criteria.
- [ ] Truth, measurement, command, and actual actuator output are all recorded.

### Edge cases

- first sample before delay buffer is full
- frozen sensor before first valid measurement
- missing measurement
- stale timestamp
- integral windup
- controller mode transition
- impossible setpoint
- NaN sensor value
- full actuator saturation

### Complexity

**High**

### Job-market value

**High**

---

## Feature 3: Explicit Mission State Machine

### Description

**[Confirmed]** Candidate modes from Step 1 include:

```text
PRELAUNCH
ASCENT
COAST
DESCENT
LANDING
LANDED
ABORT
```

**[Decision]** The MVP may simplify the exact flight sequence while preserving explicit, testable transition logic.

Recommended state flow:

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

Any active state
    |
    +-------> ABORT
```

### Why it matters for the project

The state machine demonstrates discrete software logic layered on top of continuous simulation. It also makes behavior understandable and testable.

### Skill it demonstrates

- stateful design
- enums
- transition guards
- deterministic logic
- separation of concerns
- event logging
- edge-case testing

### User flow

The user does not manually move states.

The run summary should show transitions:

```text
00.00s PRELAUNCH
00.50s PRELAUNCH -> ASCENT
08.20s ASCENT -> COAST
12.85s COAST -> DESCENT
22.40s DESCENT -> LANDING
31.17s LANDING -> LANDED
```

### Data needed

Each transition may use:
- simulation time
- measured altitude
- measured velocity
- measured pitch
- controller/status flags
- fuel status
- safety thresholds

### UI/UX requirements

- State should appear as a distinct telemetry channel.
- Plot backgrounds or vertical markers may show transition times.
- Terminal summary should show final state.
- Event log should include transition reasons.

### Backend or logic requirements

- Use an enum for mission modes.
- Centralize legal transitions.
- Every transition must have an explicit guard/reason.
- State machine should return state changes/events, not directly mutate unrelated modules.
- Invalid transitions should fail loudly in tests.

### Local-run considerations

No special infrastructure required.

### Acceptance criteria

- [ ] Legal transition map is explicit.
- [ ] Every transition is logged with time and reason.
- [ ] Invalid transitions are rejected.
- [ ] `LANDED` and `ABORT` are terminal.
- [ ] State transitions are deterministic given the same measurement/event stream.
- [ ] Tests cover every legal transition and selected illegal transitions.
- [ ] Controller behavior can vary by mission state without mixing state-transition logic into controller internals.

### Edge cases

- landing condition briefly oscillates around threshold
- ground contact occurs while not in `LANDING`
- fault forces abort during a transition
- repeated transition request
- sensor dropout makes a guard unavailable

### Complexity

**Medium**

### Job-market value

**High**

---

## Feature 4: Reproducible Fault-Injection Scenario Runner

### Description

**[Confirmed]** Fault injection is a central Step 1 portfolio feature.

**[Decision]** The MVP should ship with a curated set of approximately five scenarios:

1. `nominal`
2. `altimeter_freeze`
3. `velocity_bias`
4. `sensor_delay`
5. `degraded_actuator`

**[Decision]** A sixth `external_disturbance` scenario can be included if the first five are stable and tested.

Each scenario is configuration-driven and should specify:
- seed
- initial conditions
- controller parameters
- fault type
- fault activation condition or time
- fault magnitude
- expected result category

### Why it matters for the project

This is the strongest direct signal for validation/testing roles.

It demonstrates that the software is designed to answer:
- Does the system still work?
- How does it fail?
- Can the failure be reproduced?
- Is the outcome automatically evaluated?

### Skill it demonstrates

- test architecture
- dependency injection
- configuration-driven design
- failure modeling
- deterministic execution
- end-to-end validation

### User flow

```bash
python -m astraloop list-scenarios
python -m astraloop run scenarios/velocity_bias.toml
```

Optional batch command:

```bash
python -m astraloop campaign scenarios/regression/
```

Batch output:

```text
PASS  nominal
PASS  velocity_bias
PASS  sensor_delay
FAIL  altimeter_freeze     expected: controlled_abort, got: hard_landing
PASS  degraded_actuator

4/5 scenarios matched expected outcomes
```

### Data needed

Scenario config fields:
- scenario ID
- description
- seed
- simulation duration
- dt
- vehicle config reference
- environment config
- sensor config
- control config
- fault list
- expected outcome
- validation limits

### UI/UX requirements

- Fault activation should be obvious in event logs.
- Plot should mark fault injection time.
- Summary should distinguish:
  - mission PASS
  - controlled ABORT
  - validation FAIL
  - simulator ERROR

### Backend or logic requirements

- Faults should modify sensor/actuator/environment behavior through defined hooks.
- Avoid `if scenario_name == ...` scattered throughout the code.
- Faults must be composable enough that a future scenario can contain more than one.
- Activation should depend on simulation time or explicit event/condition.
- Fault metadata should be saved with run artifacts.

### Local-run considerations

- Config files live in repository.
- Batch runs should work headlessly.
- No database is required.

### Acceptance criteria

- [ ] At least four non-nominal scenarios genuinely alter runtime behavior.
- [ ] Same scenario + same seed reproduces the same result.
- [ ] Fault activation is logged.
- [ ] Fault implementation changes a real subsystem, not merely the final result label.
- [ ] Each scenario has documented expected behavior.
- [ ] Scenario results can be tested through `pytest`.
- [ ] New scenarios can be added without editing the core simulation loop.

### Edge cases

- fault activates after mission already ended
- two faults target same sensor
- invalid target sensor
- impossible activation time
- fault parameter omitted
- scenario expected outcome does not match validator schema

### Complexity

**Medium**

### Job-market value

**High**

---

## Feature 5: Telemetry, Validation, Visualization, and Automated Tests

### Description

**[Confirmed]** The Step 1 direction requires structured telemetry, plots/replay, objective PASS/FAIL criteria, and `pytest`.

**[Decision]** Every simulation run should produce:

```text
run_directory/
├── telemetry.csv
├── events.json
├── summary.json
├── resolved_config.json
└── flight_plot.png
```

Optional after MVP:
- `replay.gif`
- richer multi-panel diagnostic plots

### Why it matters for the project

A complex system is only impressive if its behavior can be inspected, explained, and verified.

### Skill it demonstrates

- observability
- data serialization
- test design
- validation logic
- debugging workflow
- scientific plotting
- reproducibility
- artifact management

### User flow

1. Run scenario.
2. Read concise terminal result.
3. Open plot.
4. Inspect event/telemetry data if needed.
5. Re-run test suite for automated verification.

### Data needed

Telemetry rows should include at minimum:

```text
time
mission_state

true_x
true_y
true_vx
true_vy
true_theta
true_omega
true_mass

measured_x
measured_y
measured_vx
measured_vy
measured_theta
measured_omega

command_throttle
command_attitude
actual_throttle
actual_attitude

active_faults
```

Summary should include:
- scenario ID
- seed
- result
- final state
- flight duration
- landing vertical speed
- horizontal landing error
- pitch error
- maximum tilt
- fuel remaining
- validation checks and limits

### UI/UX requirements

**[Decision]** Prefer one clean diagnostic figure over a complex GUI.

Recommended plot sections:
- trajectory
- altitude and vertical velocity vs time
- pitch vs time
- throttle command vs actual throttle
- mission state/fault event markers

A lightweight replay is optional after the static diagnostic plot works.

### Backend or logic requirements

- Telemetry recorder should subscribe to or receive a snapshot each simulation step.
- Validation must be separate from plotting.
- Validation consumes final run data and produces structured checks.
- Plotter consumes saved telemetry or a run result, not internal mutable simulation state.
- Tests should avoid relying on pixel output.

### Local-run considerations

- CSV + JSON are sufficient for MVP.
- Parquet may be a future improvement if telemetry becomes large.
- Matplotlib should support non-interactive/headless backend during tests.

### Acceptance criteria

- [ ] Every successful run generates telemetry.
- [ ] Events and state transitions are separately inspectable.
- [ ] Summary contains objective checks.
- [ ] Nominal landing uses project-defined limits:
  - `|vertical speed| <= 2.0 m/s`
  - `horizontal error <= 5 m`
  - `pitch error <= 5 degrees`
- [ ] Same run can be analyzed after simulation has ended.
- [ ] Unit tests cover core modules.
- [ ] Integration tests run complete scenarios.
- [ ] Scenario tests assert expected mission outcomes.
- [ ] `pytest` can run without launching a GUI.
- [ ] Plot generation is automated and deterministic enough for documentation.

### Edge cases

- run ends in simulator exception
- telemetry path already exists
- missing telemetry field
- non-finite values
- mission never reaches terminal state
- validator receives incomplete run
- plot contains no samples
- output directory is unwritable

### Complexity

**Medium**

### Job-market value

**High**

---

# 5. Out-of-Scope List

## Features not worth building for the MVP

**[Decision]**
- Full 3D or 6-DOF vehicle dynamics
- orbital mechanics
- realistic atmosphere tables
- multi-stage launch vehicle
- aerodynamic CFD
- high-fidelity engine thermodynamics
- real navigation stack
- Kalman filter unless a concrete need appears
- reinforcement learning or ML controller
- real-time multiplayer visualization
- giant custom GUI
- game-engine rendering
- photorealistic rocket assets
- hardware interfaces
- external flight hardware
- CAN bus or serial integrations
- C++ rewrite

## Features that would make it too SaaS-like

**[Decision] Do not build:**
- user accounts
- authentication
- cloud-hosted dashboard
- subscription tiers
- billing
- payment integrations
- organizations/workspaces
- enterprise permissions
- remote team collaboration
- hosted scenario marketplace
- cloud database
- public API service solely for productization

## Features that can be future improvements

Only after MVP definition of done:

- Monte Carlo scenario campaigns
- additional compound faults
- configurable wind/disturbance profiles
- lightweight state estimator
- replay GIF generation
- comparative report between multiple runs
- controller tuning experiments
- alternative numerical integrator
- run-to-run regression visualization
- optional small local desktop UI
- richer documentation on numerical accuracy
- performance profiling/benchmark command
- 3D/6-DOF experimental branch

---

# 6. UX Blueprint

## UX philosophy

**[Decision]** AstraLoop is an engineering tool, not a consumer application.

The UX should optimize for:
- clarity
- fast local execution
- obvious scenario selection
- readable PASS/FAIL output
- easy artifact discovery
- easy debugging

The CLI and generated plots are the primary interface.

## Main screens/pages

There are no traditional web pages.

### 1. CLI help screen

```bash
python -m astraloop --help
```

Should expose a small command set:

```text
run             Run one scenario
list-scenarios  List bundled scenarios
campaign        Run a directory/set of scenarios
plot            Regenerate plot from saved telemetry (optional MVP+)
```

### 2. Single-run terminal summary

Shows:
- scenario
- seed
- final result
- final state
- key validation metrics
- artifact directory

### 3. Diagnostic plot

Shows the mission in one reviewer-friendly figure.

### 4. Saved run directory

Acts as the detailed "results page."

## Main flows

### Flow A — Run nominal mission

```text
Open terminal
  -> choose nominal scenario
  -> run command
  -> see PASS summary
  -> open generated plot
```

### Flow B — Run fault mission

```text
Run fault scenario
  -> see fault activation event
  -> see changed outcome/metrics
  -> inspect plot
  -> inspect events.json if needed
```

### Flow C — Validate repository

```text
pytest
  -> unit tests
  -> state-machine tests
  -> integration tests
  -> scenario acceptance tests
```

### Flow D — Reviewer exploration

```text
README
  -> architecture diagram
  -> one-command demo
  -> nominal screenshot
  -> fault screenshot
  -> design decisions
  -> source tree
  -> tests
```

## Empty states

Examples:
- no scenarios found
- run output directory contains no telemetry
- campaign directory is empty

Required behavior:
- print clear message
- give corrective action
- return appropriate non-zero exit code where applicable

Example:

```text
No scenario files found in scenarios/custom/.
Add a .toml scenario or choose a bundled scenario with:
python -m astraloop list-scenarios
```

## Loading states

**[Decision]** Most runs should be fast enough that a spinner is unnecessary.

For longer batch campaigns:
- print scenario currently running
- print compact result after each run

Avoid fake progress bars unless simulation runtime becomes long enough to justify one.

## Error states

Errors should be categorized:

### Configuration error
Example: invalid fault target.

### Simulation error
Example: non-finite state.

### Validation failure
Simulation completed, but mission failed criteria.

### Expected controlled abort
Mission logic deliberately entered `ABORT`.

These should not all look identical.

## Mobile/responsive needs

**[Decision] Not relevant.**

This is a local engineering portfolio project. Responsive web design adds no meaningful hiring signal.

README images should still be readable on GitHub at normal widths.

## Demo path for a reviewer

Recommended order:

1. README hero section
2. architecture diagram
3. nominal command + result
4. nominal plot
5. fault command + result
6. fault plot
7. `pytest` result
8. short design-decision table
9. source tree

---

# 7. Data Blueprint

## Main entities

### `VehicleState`

Represents perfect simulation truth.

Suggested fields:

```python
time: float
x: float
y: float
vx: float
vy: float
theta: float
omega: float
mass: float
```

### `SensorMeasurement`

Represents what flight software can observe.

Suggested fields:

```python
timestamp: float
x: float | None
y: float | None
vx: float | None
vy: float | None
theta: float | None
omega: float | None
```

Optional metadata:
- stale flags
- per-sensor age
- validity flags

### `ControlCommand`

Desired outputs from controller.

```python
throttle: float
attitude_command: float
```

### `ActuatorState`

Actual applied commands after limits/lag.

```python
throttle: float
attitude: float
```

### `MissionStatus`

```python
state: MissionState
entered_at: float
```

### `FaultDefinition`

```python
id: str
type: str
target: str
activation_time: float | None
parameters: dict
```

### `ScenarioConfig`

```python
id: str
description: str
seed: int
dt: float
max_time: float
vehicle: ...
sensors: ...
controller: ...
faults: ...
validation: ...
```

### `TelemetrySample`

Flattened snapshot used for output.

### `MissionEvent`

```python
time: float
event_type: str
message: str
metadata: dict
```

### `ValidationResult`

```python
passed: bool
outcome: str
checks: list[ValidationCheck]
```

## Relationships

```text
ScenarioConfig
   |
   +--> VehicleConfig
   +--> SensorConfig
   +--> ControllerConfig
   +--> FaultDefinition[]
   +--> ValidationConfig

SimulationRun
   |
   +--> VehicleState (evolves)
   +--> SensorMeasurement (per sample)
   +--> ControlCommand
   +--> ActuatorState
   +--> MissionStatus
   +--> TelemetrySample[]
   +--> MissionEvent[]
   +--> ValidationResult
```

## Example seed data

### `scenarios/nominal.toml`

```toml
id = "nominal"
description = "Nominal autonomous flight and landing"
seed = 42
dt = 0.02
max_time = 60.0

[initial_state]
x = 0.0
y = 0.0
vx = 0.0
vy = 0.0
theta_deg = 0.0
omega_deg_s = 0.0

[validation]
max_landing_vertical_speed = 2.0
max_horizontal_error = 5.0
max_pitch_error_deg = 5.0
```

### `scenarios/altimeter_freeze.toml`

```toml
id = "altimeter_freeze"
description = "Altitude reading freezes during descent"
seed = 42
dt = 0.02
max_time = 60.0

[[faults]]
id = "freeze_altimeter_01"
type = "sensor_freeze"
target = "altimeter"
activation_time = 20.0
```

Values in these examples are project configuration examples, not real launch-vehicle specifications.

## Local storage/database needs

**[Decision] No database for MVP.**

Use:
- TOML for scenario configuration
- CSV for telemetry
- JSON for events, resolved config, and summaries
- PNG for plots

Why:
- inspectable
- portable
- easy to diff
- easy to use in tests
- zero setup
- appropriate for a local project

---

# 8. Engineering Blueprint

## Technical direction

**[Decision]** Python is the implementation language for the complete MVP.

Likely libraries:
- Python 3.12+
- NumPy
- SciPy
- Matplotlib
- pytest
- standard-library `dataclasses` or typed classes
- standard-library `tomllib` for TOML parsing where possible

**[Decision]** Do not add frameworks without a concrete engineering need.

## Recommended repository structure

```text
astraloop/
├── README.md
├── pyproject.toml
├── docs/
│   ├── PROJECT_MASTER_BLUEPRINT.md
│   ├── ARCHITECTURE.md
│   └── DESIGN_DECISIONS.md
├── scenarios/
│   ├── nominal.toml
│   ├── altimeter_freeze.toml
│   ├── velocity_bias.toml
│   ├── sensor_delay.toml
│   └── degraded_actuator.toml
├── src/
│   └── astraloop/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── config.py
│       ├── types.py
│       ├── simulation/
│       │   ├── engine.py
│       │   ├── dynamics.py
│       │   ├── integrator.py
│       │   └── environment.py
│       ├── sensors/
│       │   ├── base.py
│       │   ├── models.py
│       │   └── suite.py
│       ├── control/
│       │   ├── pid.py
│       │   ├── throttle.py
│       │   └── attitude.py
│       ├── actuators/
│       │   └── models.py
│       ├── mission/
│       │   ├── states.py
│       │   └── state_machine.py
│       ├── faults/
│       │   ├── base.py
│       │   ├── sensors.py
│       │   ├── actuators.py
│       │   └── disturbances.py
│       ├── telemetry/
│       │   ├── recorder.py
│       │   ├── serialization.py
│       │   └── plotting.py
│       ├── validation/
│       │   ├── checks.py
│       │   └── evaluator.py
│       └── scenarios/
│           └── runner.py
├── tests/
│   ├── unit/
│   │   ├── test_dynamics.py
│   │   ├── test_pid.py
│   │   ├── test_sensors.py
│   │   ├── test_actuators.py
│   │   └── test_state_machine.py
│   ├── integration/
│   │   ├── test_closed_loop.py
│   │   └── test_fault_injection.py
│   └── scenarios/
│       ├── test_nominal.py
│       └── test_regression_scenarios.py
└── runs/
    └── .gitkeep
```

## Module responsibilities

### `simulation/dynamics.py`
Pure domain math.

Must not:
- read files
- know CLI
- know scenario names
- plot
- decide mission state

### `simulation/engine.py`
Owns the simulation loop and simulation clock.

Suggested step order:

```text
1. evaluate mission status / terminal condition
2. sample sensors from current truth
3. apply sensor faults
4. build measurement snapshot
5. update mission state if appropriate
6. controller computes desired command
7. apply actuator limits/dynamics/faults
8. advance physics
9. record telemetry/events
10. advance simulation clock
```

Exact ordering should be documented and kept consistent.

### `control/`
Pure controller logic with small internal state where needed.

### `mission/`
Owns mission modes and legal transitions.

### `faults/`
Owns fault definitions/activation/modification.

### `validation/`
Evaluates completed run against configured criteria.

### `telemetry/`
Captures and persists observability data.

### `scenarios/runner.py`
Composes configured modules and executes runs.

## API or service layer

**[Decision] No network API.**

Internal Python service boundaries are enough.

Recommended top-level callable:

```python
result = run_scenario(config)
```

Where `result` includes:
- summary
- telemetry reference/data
- events
- validation result
- artifact directory

This function should be usable by both:
- CLI
- tests

## State management needs

**[Decision]** Avoid a global mutable state container.

State should live in explicit objects:
- simulation engine owns current truth state
- sensor models own buffers where necessary
- controllers own integral/derivative memory
- actuator models own lag state
- state machine owns current mission mode
- telemetry recorder owns collected samples

Dependencies should be passed explicitly.

## Error handling approach

### Configuration validation
Fail before simulation starts when possible.

Examples:
- `dt <= 0`
- unknown fault type
- invalid target
- dry mass > initial total mass
- negative noise standard deviation

### Runtime invariant checks
Stop simulation cleanly for:
- non-finite state
- impossible mass
- invalid mission transition
- numerical blow-up

### Domain outcomes are not exceptions
A hard landing or controlled abort is a valid simulation result, not necessarily a Python exception.

### CLI exit codes

Suggested:
- `0` command completed; scenario matched expected outcome or single run completed normally
- `1` validation/scenario mismatch
- `2` configuration/user input error
- `3` simulator/internal error

## Testing approach

### Unit tests

Test:
- dynamics under simple conditions
- sensor noise/bias/freeze/delay
- PID output
- actuator saturation/lag
- legal and illegal state transitions
- validation thresholds
- config parsing

### Integration tests

Test:
- sensor -> controller -> actuator chain
- simulation loop over short deterministic interval
- fault activates at correct simulation time
- telemetry samples align with run state

### End-to-end scenario tests

Test full configured missions.

Examples:

```python
def test_nominal_lands_within_limits():
    result = run_scenario(load_scenario("nominal"))
    assert result.validation.passed
    assert result.final_state is MissionState.LANDED
```

```python
def test_altimeter_freeze_matches_expected_outcome():
    result = run_scenario(load_scenario("altimeter_freeze"))
    assert result.outcome == result.expected_outcome
```

### Numerical test principle

Do not assert every floating-point value exactly.

Prefer:
- tolerances
- invariant checks
- ranges
- reproducible summary metrics
- expected state/outcome

## Local setup approach

Recommended:

```bash
git clone <repo>
cd astraloop
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Then:

```bash
pip install -e ".[dev]"
pytest
python -m astraloop run scenarios/nominal.toml
```

**[Decision]** One documented setup path is better than maintaining multiple package-manager workflows.

---

# 9. Project Polish Plan

## README requirements

The first screen of the README should answer:

1. What is AstraLoop?
2. Why is it technically interesting?
3. What can I run right now?
4. What does success/failure look like?

## Recommended README structure

```text
# AstraLoop

One-sentence description

[hero diagnostic plot or short GIF]

## Why this exists
5 concise engineering bullets

## Quick demo
setup + one command

## Nominal vs fault example
two results side by side

## Architecture
diagram

## Key design decisions
truth vs sensing
2D vs 6-DOF
deterministic simulation
configuration-driven faults

## Testing
pytest command
test categories

## Project structure

## Known limitations / non-goals

## What I learned
```

## Screenshots / GIF / demo video needs

### Required
- architecture diagram
- nominal diagnostic plot
- one fault diagnostic plot
- terminal PASS output
- terminal test-suite output

### Recommended
- 20–40 second GIF or video showing:
  - command
  - simulation result
  - generated plot

### Avoid
- long cinematic video
- excessive editing
- visual effects that obscure the engineering

## Seed data requirements

Repository should include:
- all MVP scenario configs
- stable seeds
- README-compatible expected outputs

Do not commit large generated `runs/` directories except a small curated example if useful.

## Portfolio case study notes

A portfolio page should tell this story:

### Problem
How do you validate autonomous control software without physical hardware?

### Approach
Build a deterministic software-in-the-loop environment with imperfect sensors, actuator dynamics, mission states, fault injection, and automated acceptance checks.

### Main engineering decisions
- 2D instead of 6-DOF
- truth/measurement separation
- simulation clock instead of wall time
- configuration-driven faults
- headless core + separate visualization
- mission-level automated tests

### Hardest bugs / lessons
Document 2–3 real examples after implementation.

Potential examples:
- sign convention in pitch/thrust
- delay buffer off-by-one error
- controller saturation/integral windup
- state transition threshold oscillation
- numerical timestep instability

These are more valuable than claiming everything worked immediately.

## Resume bullet opportunities

Use truthful numbers from the finished project only.

Template:

> Built **AstraLoop**, a Python software-in-the-loop flight-control validation system modeling 2D vehicle dynamics, imperfect sensors, actuator response, and closed-loop control; added deterministic fault injection and automated `pytest` mission validation across **N** scenarios.

Second bullet:

> Designed modular simulation, mission-state, telemetry, and validation components using NumPy/SciPy; generated reproducible run artifacts and objective landing/failure metrics for nominal and degraded-system tests.

Do not insert scenario counts, test counts, or performance numbers until measured.

---

# 10. Build Roadmap

# Phase 0: Setup and Docs

## Goal
Freeze the system boundaries before implementation.

## Tasks

- [ ] Create repository structure.
- [ ] Add `pyproject.toml`.
- [ ] Add formatter/linter only if actually used.
- [ ] Add `pytest`.
- [ ] Copy this blueprint to `docs/PROJECT_MASTER_BLUEPRINT.md`.
- [ ] Write `docs/ARCHITECTURE.md`.
- [ ] Define state vector and units.
- [ ] Define simulation timestep strategy.
- [ ] Define mission states.
- [ ] Define public data types.
- [ ] Define scenario config schema.
- [ ] Define nominal acceptance criteria.
- [ ] Add skeleton README.
- [ ] Add first empty/smoke test.

## Exit criteria

- [ ] `pytest` runs.
- [ ] Package imports.
- [ ] Architecture diagram/data-flow exists.
- [ ] No unresolved ambiguity about controller access to truth state.
- [ ] Nominal mission success metrics are documented.

---

# Phase 1: Skeleton App

## Goal
Make the entire program flow exist before complex math.

## Tasks

- [ ] Implement CLI.
- [ ] Implement scenario loader.
- [ ] Implement typed config objects.
- [ ] Implement `VehicleState`.
- [ ] Implement placeholder simulation engine.
- [ ] Implement telemetry recorder.
- [ ] Implement basic run directory creation.
- [ ] Implement minimal summary output.

At this phase, dynamics can be intentionally simple.

## Exit criteria

Command works:

```bash
python -m astraloop run scenarios/nominal.toml
```

And produces:
- run directory
- telemetry file
- summary file

---

# Phase 2: Core Data / Model Layer

## Goal
Build the numerical system correctly before adding faults.

## Tasks

### Dynamics
- [ ] Implement 2D state equations.
- [ ] Implement thrust direction.
- [ ] Implement gravity.
- [ ] Implement mass/fuel consumption.
- [ ] Implement ground/terminal handling.

### Sensors
- [ ] Implement base sensor abstraction.
- [ ] Implement nominal measurements.
- [ ] Implement deterministic noise.

### Controller
- [ ] Implement reusable PID component.
- [ ] Implement vertical/throttle control.
- [ ] Implement pitch/attitude control.

### Actuators
- [ ] Implement saturation.
- [ ] Implement lag.

### Tests
- [ ] Dynamics tests.
- [ ] Sensor tests.
- [ ] PID tests.
- [ ] Actuator tests.

## Exit criteria

- [ ] Short closed-loop simulation runs deterministically.
- [ ] Controller receives only measurements.
- [ ] Commands visibly affect vehicle dynamics.
- [ ] Core modules have meaningful unit tests.

---

# Phase 3: Feature Build

## Goal
Turn the model into the complete MVP engineering system.

## Tasks

### Mission logic
- [ ] Implement mission enum.
- [ ] Implement transition rules.
- [ ] Add transition events.
- [ ] Test legal/illegal transitions.

### Nominal mission
- [ ] Tune enough to achieve documented landing criteria.
- [ ] Lock nominal scenario seed and config.

### Fault system
- [ ] Implement generic activation mechanism.
- [ ] Implement altitude sensor freeze.
- [ ] Implement velocity sensor bias.
- [ ] Implement sensor delay.
- [ ] Implement degraded actuator response.
- [ ] Optionally implement external disturbance.

### Validation
- [ ] Implement mission checks.
- [ ] Implement expected outcome model.
- [ ] Generate structured PASS/FAIL summary.

### Visualization
- [ ] Create diagnostic plot.
- [ ] Add state/fault event markers.

## Exit criteria

- [ ] Nominal scenario passes.
- [ ] At least four fault scenarios run.
- [ ] Faults visibly alter subsystem behavior.
- [ ] All runs produce telemetry and summaries.

---

# Phase 4: Tests and Fixes

## Goal
Make the project reliable enough to trust.

## Tasks

- [ ] Add full scenario tests.
- [ ] Add regression tests for discovered bugs.
- [ ] Test invalid configuration.
- [ ] Test simulation invariants.
- [ ] Test reproducibility.
- [ ] Test headless plotting.
- [ ] Test output artifacts.
- [ ] Run all bundled scenarios repeatedly.
- [ ] Remove flaky tests.
- [ ] Fix warnings.

## Required tests

- [ ] same seed -> same mission result
- [ ] different fault config -> expected changed behavior
- [ ] illegal mission transition rejected
- [ ] mass never below dry mass
- [ ] actuator never exceeds configured limit
- [ ] nominal metrics inside limits
- [ ] run terminates by max simulation time
- [ ] non-finite state fails safely

## Exit criteria

- [ ] `pytest` passes from clean environment.
- [ ] No flaky scenario test.
- [ ] No known crash in bundled scenarios.
- [ ] Known limitations documented.

---

# Phase 5: UI / UX Polish

## Goal
Make engineering results immediately legible.

## Tasks

- [ ] Improve CLI formatting.
- [ ] Make result category obvious.
- [ ] Improve diagnostic plot labels/units.
- [ ] Add event markers.
- [ ] Ensure plots remain readable at README size.
- [ ] Add `list-scenarios`.
- [ ] Add optional batch/campaign command if small enough.
- [ ] Add friendly errors for bad paths/configs.

## Exit criteria

A reviewer can:
- install
- run
- understand result
- find artifacts

without reading source code first.

---

# Phase 6: README, Screenshots, Demo, Resume Story

## Goal
Turn a functioning repository into a portfolio asset.

## Tasks

- [ ] Capture nominal result screenshot.
- [ ] Capture fault result screenshot.
- [ ] Capture `pytest` result.
- [ ] Create architecture diagram.
- [ ] Finish README.
- [ ] Add design-decision section.
- [ ] Add limitations/non-goals section.
- [ ] Record short GIF/video if useful.
- [ ] Write portfolio case study.
- [ ] Draft resume bullets using measured facts.
- [ ] Prepare 60-second project explanation.
- [ ] Prepare 5-minute technical walkthrough.
- [ ] Prepare answers to likely interview questions.

## Exit criteria

A recruiter can understand the project in under one minute and a technical interviewer can explore it for 15–30 minutes.

---

# 11. Risks and Simplifications

## Risk 1: Physics scope explodes

### Failure mode
You keep adding realism before the software system is complete.

### Simplification
**[Decision]** Keep MVP to planar 2D and simple deterministic equations.

### Cut first
- aerodynamics
- variable atmosphere
- advanced thrust models
- 6-DOF

---

## Risk 2: Controller tuning consumes the project

### Failure mode
Weeks are spent chasing a highly realistic landing controller.

### Simplification
**[Decision]** Use explainable, bounded control objectives. This is a software validation portfolio project, not a guidance research paper.

### Cut first
- advanced guidance optimization
- perfect fuel efficiency
- sophisticated estimator

---

## Risk 3: Visualization becomes the product

### Failure mode
Most time goes into animation instead of architecture/testing.

### Simplification
**[Decision]** Static diagnostic plot is sufficient for MVP.

### Cut first
- interactive 3D
- custom GUI
- game-engine visualization

---

## Risk 4: Fault injection is cosmetic

### Failure mode
Code prints "sensor fault" without changing actual control inputs.

### Simplification
Every fault must alter a real subsystem's output/input path.

### Must prove
Telemetry should make the effect visible.

---

## Risk 5: Tests are shallow

### Failure mode
Only utility functions are tested, while full missions can silently regress.

### Simplification
Prioritize:
1. state-machine tests
2. deterministic end-to-end nominal test
3. fault scenario regression tests

---

## Risk 6: Architecture becomes overengineered

### Failure mode
Too many abstract base classes, factories, protocols, and plugins are added before a second implementation exists.

### Simplification
**[Decision]** Use abstractions only where they protect a real boundary:
- sensors
- faults
- controllers if multiple controller types exist

Prefer normal typed functions/classes elsewhere.

---

## Risk 7: Recruiter cannot understand it

### Failure mode
README starts with equations and aerospace terminology.

### Simplification
Lead with:
- what it does
- why it matters
- one command
- one result
- architecture diagram

Put detailed equations later.

---

## What to cut if the project gets too big

Cut in this order:

1. replay GIF
2. campaign/batch command
3. external disturbance scenario
4. extra plots
5. advanced sensor suite
6. optional estimator
7. additional mission phases
8. sophisticated aerodynamics

Do **not** cut:
- truth vs measurement separation
- real numerical state evolution
- closed-loop control
- state machine
- at least four fault scenarios
- objective mission validation
- deterministic testing
- telemetry

## What must be done well no matter what

**[Decision]**
1. Clean module boundaries
2. Controller cannot cheat with truth state
3. Deterministic scenario runs
4. Nominal mission works
5. Faults genuinely alter behavior
6. State transitions are explicit
7. Telemetry is useful for debugging
8. Mission PASS/FAIL is objective
9. Tests protect system behavior
10. README explains the engineering clearly

---

# 12. Final Recommended MVP

## Exact features to build

### Core simulator
- [ ] 2D planar translational dynamics
- [ ] pitch/angular dynamics
- [ ] mass/fuel state
- [ ] fixed simulation clock and deterministic timestep

### Sensor layer
- [ ] altitude
- [ ] horizontal/vertical velocity
- [ ] horizontal position
- [ ] pitch
- [ ] angular rate
- [ ] configurable noise
- [ ] bias/freeze/delay support where required by scenarios

### Controller
- [ ] throttle controller
- [ ] attitude controller
- [ ] controller reads measurements only

### Actuator layer
- [ ] saturation
- [ ] response lag

### Mission logic
- [ ] explicit mission states
- [ ] guarded transitions
- [ ] terminal `LANDED`
- [ ] terminal `ABORT`
- [ ] event log

### Scenarios
- [ ] nominal
- [ ] altimeter freeze
- [ ] velocity bias
- [ ] sensor delay
- [ ] degraded actuator

### Observability
- [ ] telemetry CSV
- [ ] events JSON
- [ ] resolved config JSON
- [ ] summary JSON
- [ ] diagnostic PNG

### Validation
- [ ] vertical landing speed check
- [ ] horizontal landing error check
- [ ] pitch landing error check
- [ ] final mission-state check
- [ ] scenario expected-outcome check

### Tests
- [ ] unit tests
- [ ] state-machine tests
- [ ] integration tests
- [ ] nominal end-to-end test
- [ ] fault scenario regression tests
- [ ] reproducibility test

### Portfolio polish
- [ ] architecture diagram
- [ ] README quick start
- [ ] nominal screenshot
- [ ] fault screenshot
- [ ] test screenshot
- [ ] design decisions
- [ ] limitations/non-goals
- [ ] resume bullet

## Exact features to delay

**[Decision] Delay until after MVP:**
- 6-DOF
- orbital mechanics
- advanced aerodynamics
- Kalman filter
- Monte Carlo campaigns
- compound fault campaigns
- interactive GUI
- web UI
- cloud deployment
- database
- hardware-in-the-loop
- C++ components
- machine learning
- realistic Starship replication
- high-fidelity engine simulation

## Definition of done

The MVP is done only when all of the following are true:

### Functionality
- [ ] A nominal 2D mission runs from one documented CLI command.
- [ ] The controller uses simulated measurements, not perfect truth state.
- [ ] Vehicle motion comes from numerical dynamics.
- [ ] Mission phases use an explicit tested state machine.
- [ ] At least four non-nominal fault scenarios alter actual runtime behavior.

### Validation
- [ ] Every scenario produces a structured result.
- [ ] Nominal landing meets project-defined limits:
  - `|v_y| <= 2.0 m/s`
  - horizontal error `<= 5 m`
  - pitch error `<= 5 degrees`
- [ ] Fault missions either recover within configured limits or terminate in the documented controlled outcome.
- [ ] Same seed + same config reproduces the same mission outcome.

### Engineering quality
- [ ] `pytest` passes from a clean environment.
- [ ] Core modules have unit tests.
- [ ] Full scenarios have end-to-end tests.
- [ ] No normal controller path can access truth state.
- [ ] Invalid configs fail clearly.
- [ ] Non-finite/numerically invalid states fail safely.
- [ ] Visualization is separate from core simulation logic.

### Portfolio quality
- [ ] README explains the project in under one minute.
- [ ] One architecture diagram is included.
- [ ] One nominal and one fault example are shown.
- [ ] Quick-start instructions work.
- [ ] Known limitations are stated honestly.
- [ ] Resume bullet uses only measured/finished facts.

---

# Final Build Rule

**[Decision]** Do not add a new major feature until the nominal mission, automated validation, and current test suite are stable.

AstraLoop should become impressive through **depth, correctness, reproducibility, and explanation**, not through feature count.

---

# Move On When

- [ ] The project is scoped to a finishable local build.
- [ ] The features are connected to skill signals.
- [ ] The demo path is obvious.
- [ ] There is a clear out-of-scope list.
- [ ] The roadmap has a setup phase, build phase, test phase, and polish phase.

**[Decision]** Once these boxes are satisfied in practice, the next implementation document should be the Phase 0 technical design: exact equations/state vector, units, timestep, module interfaces, mission-transition guards, scenario schema, and nominal acceptance configuration.
