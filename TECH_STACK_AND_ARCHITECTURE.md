# TECH_STACK_AND_ARCHITECTURE.md

# AstraLoop — Tech Stack and Architecture

> **Project:** AstraLoop — Python Software-in-the-Loop Flight Control & Validation System  
> **Primary target:** Software Engineering Intern — Systems / Simulation / Validation  
> **Architecture goal:** Maximize systems/simulation engineering signal while keeping the project deterministic, local, testable, understandable, and finishable.

---

# 1. Target Role Interpretation

## What role this project is meant to support

**[Confirmed]** AstraLoop is intended to support software engineering internships focused on **systems, simulation, validation, testing, and hardware-adjacent software**, with AMD-like companies as a reference target.

**[Confirmed]** The project is deliberately **Python-first, fully local, non-SaaS, and software-in-the-loop**. The rocket is the application domain; the portfolio signal is software engineering.

**[Decision]** The stack should therefore optimize for:

1. deterministic numerical simulation;
2. explicit state and timing;
3. clean separation between simulation truth and software-visible measurements;
4. fault injection and reproducible scenario execution;
5. automated validation;
6. unit, integration, and end-to-end testing;
7. readable telemetry and diagnostics;
8. architecture that can be explained in an interview without framework magic.

## What skills the stack should prove

**[Decision]** The stack should visibly prove:

- strong Python engineering;
- numerical programming with arrays and ODE-style state evolution;
- deterministic simulation-loop design;
- state-machine design;
- feedback-control implementation;
- sensor and actuator modeling;
- fault injection;
- configuration-driven execution;
- observability and telemetry;
- test architecture;
- static typing and code-quality discipline;
- separation of domain logic from I/O and presentation.

**[Decision]** It should **not** primarily signal:

- CRUD/web development;
- database design;
- frontend engineering;
- SaaS architecture;
- cloud deployment;
- machine-learning experimentation.

Those are valid skills, but they are not the strongest use of this specific project.

---

# 2. Stack Options

## Option A — Lean Scientific Python + Deterministic CLI Core

### Stack

| Layer | Choice |
|---|---|
| Language | Python 3.13 baseline |
| Frontend/UI | CLI using standard-library `argparse`; terminal formatting with `rich`; generated Matplotlib figures |
| Backend/API | No network backend; importable Python package with `run_scenario(...)` as the application boundary |
| Numerical core | NumPy |
| Runtime integrator | Project-owned fixed-step RK4 |
| Numerical reference | SciPy `solve_ivp` used in verification/reference tests, not as the main simulation clock |
| Configuration | TOML parsed with standard-library `tomllib` |
| Data models | `dataclasses`, `Enum`, standard typing, small `Protocol` interfaces only where multiple implementations exist |
| Storage | TOML inputs; CSV telemetry; JSON events/config/summary; PNG diagnostic plots |
| Testing | `pytest`; `pytest.approx`; `tmp_path`; parametrized scenario tests |
| Static analysis | Pyright |
| Lint/format | Ruff |
| Dependency/environment management | `uv` + `pyproject.toml` + committed `uv.lock` |
| Version control | Git |
| Optional CI | One small GitHub Actions workflow for lint + type-check + test |
| Database | None |
| AI/ML | None |

### Why this stack fits

**[Decision]** This is the strongest fit because it keeps the engineering center of gravity on the actual problem:

```text
simulation timing
    -> sensors
    -> faults
    -> mission logic
    -> controller
    -> actuators
    -> numerical dynamics
    -> telemetry
    -> validation
```

rather than on framework configuration.

**[Decision]** A fixed-step RK4 runtime is preferable to an adaptive solver as the main engine because AstraLoop contains **discrete-time software components** in addition to continuous dynamics:

- sensor sampling;
- sensor delay buffers;
- controller update periods;
- actuator lag;
- state transitions;
- fault activation times;
- telemetry frames.

A fixed simulation tick gives these components one shared, deterministic timing model.

**[Decision]** SciPy remains valuable as an independent numerical reference. Selected open-loop tests can compare the custom RK4 trajectory against `solve_ivp` within a tolerance. This demonstrates both numerical understanding and engineering verification without letting an adaptive integrator dictate the software timing model.

**[Decision]** `argparse` is preferred over a CLI framework because AstraLoop needs only a few commands. The parser stays explicit and dependency-light. `rich` is used only for presentation quality, not application structure.

**[Decision]** Standard-library dataclasses are preferred over Pydantic for the MVP because the configuration surface is controlled, local, and small enough to validate explicitly. This keeps domain types transparent.

**[Decision]** CSV/JSON/TOML are preferred over a database because every run is naturally an immutable artifact bundle. No relational query or concurrent persistence requirement exists.

### Risks

- **[Risk]** A custom RK4 implementation can contain numerical bugs.
  - **Mitigation:** verify against SciPy on simple/open-loop cases; test order-of-accuracy behavior; document the supported `dt`.

- **[Risk]** Manual config validation is more code than using Pydantic.
  - **Mitigation:** centralize validation in `config/schema.py`; keep the schema intentionally small.

- **[Risk]** A CLI is less visually impressive than a dashboard.
  - **Mitigation:** use polished terminal summaries and one strong multi-panel Matplotlib diagnostic figure.

### Job-market signal

**[Decision] Very strong.**

This option says:

> “I designed and tested a deterministic simulation system in Python, understood the timing model, built the numerical core, isolated software-visible state from truth state, and created reproducible fault-driven validation.”

That is directly aligned with the project’s target role.

---

## Option B — Typed Application Framework Stack

### Stack

| Layer | Choice |
|---|---|
| Language | Python 3.13 |
| Frontend/UI | Typer CLI + Rich |
| Backend/API | Importable Python service layer |
| Numerical core | NumPy + SciPy |
| Runtime integration | Fixed-step RK4 or SciPy stepper wrapped behind an integrator interface |
| Configuration | TOML + Pydantic v2 models |
| Data layer | Pandas DataFrames for telemetry analysis/export |
| Visualization | Matplotlib |
| Storage | TOML + CSV/JSON/PNG |
| Testing | pytest |
| Static analysis | Pyright |
| Lint/format | Ruff |
| Dependency management | uv |
| Database | None |
| AI/ML | None |

### Why this stack fits

**[Decision]** This option improves developer ergonomics:

- Pydantic gives strong config parsing and error messages.
- Typer makes CLI commands concise.
- Pandas makes telemetry transformation convenient.

It is still local and still Python-centric.

### Risks

**[Decision]** The main risk is that frameworks begin solving problems AstraLoop does not actually have.

- Typer is unnecessary for four small CLI commands.
- Pydantic can leak configuration concerns into domain objects.
- Pandas can hide simple row-oriented telemetry behind DataFrame transformations.
- More dependencies create more setup and more concepts for a reviewer to mentally filter out.

### Job-market signal

**[Decision] Strong, but less focused than Option A.**

This stack demonstrates professional Python application tooling, but slightly reduces the signal that the developer personally understood the core timing/data flow.

---

## Option C — Local Interactive Dashboard

### Stack

| Layer | Choice |
|---|---|
| Language | Python 3.13 |
| Frontend/UI | Streamlit |
| Visualization | Plotly |
| Backend/API | Python package called directly from Streamlit; no network service required |
| Numerical core | NumPy + SciPy |
| Configuration | Pydantic + TOML |
| Data layer | Pandas |
| Storage | CSV/JSON; optional SQLite run index |
| Testing | pytest for core; limited Streamlit/UI testing |
| Static analysis | Pyright |
| Lint/format | Ruff |
| Dependency management | uv |
| Database | Optional SQLite only for run indexing |
| AI/ML | None |

### Why this stack fits

**[Decision]** It produces the most immediately interactive demo:

- scenario dropdown;
- run button;
- plots;
- validation cards;
- run comparisons.

A recruiter can understand it quickly.

### Risks

**[Decision]** This option has the weakest target-role alignment of the three.

- It shifts development time toward UI state and dashboard behavior.
- It risks looking like another Streamlit portfolio app.
- It makes the project easier to misread as “a rocket dashboard” rather than a simulation/validation system.
- UI testing becomes less central than the numerical and scenario testing that should define AstraLoop.
- SQLite is still unnecessary unless a real run-history query requirement appears.

### Job-market signal

**[Decision] Moderate to strong.**

Excellent demo value, but less differentiated for systems/simulation/validation internships.

---

# 3. Stack Scoring Table

Scores are from **1 to 10**, where 10 is strongest for this project.

| Criterion | Option A: Lean Scientific CLI | Option B: Typed Framework | Option C: Dashboard |
|---|---:|---:|---:|
| Target role alignment | **10** | 8 | 6 |
| Technical depth | **9** | 9 | 7 |
| Local-run simplicity | **9** | 7 | 7 |
| Maintainability | **9** | 8 | 7 |
| Testability | **10** | 9 | 7 |
| Demo value | 8 | 9 | **10** |
| Recruiter readability | **9** | 9 | **9** |
| Interviewer discussion value | **10** | 9 | 7 |
| **Total / 80** | **74** | **68** | **60** |
| **Average / 10** | **9.25** | **8.50** | **7.50** |

**[Decision]** Option A wins even before weighting target-role alignment more heavily.

---

# 4. Final Stack Decision

## Recommended stack

**[Decision] Choose Option A: Lean Scientific Python + Deterministic CLI Core.**

### Final selected stack

```text
Python 3.13
uv + pyproject.toml + uv.lock

Runtime:
  NumPy
  Matplotlib
  Rich
  Python stdlib:
    argparse
    dataclasses
    enum
    typing
    tomllib
    json
    csv
    pathlib
    collections.deque
    logging

Numerics:
  custom fixed-step RK4 in the production simulation loop
  SciPy solve_ivp as an independent numerical-reference tool in tests

Quality:
  pytest
  Ruff
  Pyright

Persistence:
  TOML scenarios
  CSV telemetry
  JSON events/resolved config/summary
  PNG plots

No:
  FastAPI
  database
  web frontend
  ORM
  Docker requirement
  cloud service
  ML framework
```

## Why it is the best choice

### 1. It is the closest match to the target role

**[Confirmed]** The project is intended to signal systems/simulation/validation ability rather than product-web development.

**[Decision]** The selected stack puts nearly all complexity into:

- simulation architecture;
- timing;
- numerical state evolution;
- fault behavior;
- interfaces;
- observability;
- validation;
- testing.

Those are the areas most worth discussing in an interview.

### 2. It preserves Python as the obvious center of the project

**[Decision]** A reviewer should open the repository and see a serious Python software system, not a thin Python model hidden behind a large framework.

### 3. It makes timing semantics explicit

**[Decision]** The simulation uses an integer tick counter and a configured fixed `dt`.

Recommended model:

```python
sim_time = tick * dt
```

rather than repeatedly accumulating wall-clock time.

This gives stable semantics for:

- fault activation;
- delayed sensor samples;
- controller update cadence;
- mission transition timestamps;
- telemetry indexing.

### 4. It is easy to run locally

**[Decision]** `uv` provides one project workflow for environment creation, dependency resolution, lockfile reproduction, and command execution.

The project does not require:

- a database server;
- Node.js;
- a browser;
- Docker;
- cloud credentials;
- environment secrets.

### 5. It is highly testable

**[Decision]** The architecture supports testing from pure equations all the way to complete mission scenarios.

### 6. It avoids generic tutorial energy

**[Decision]** The strongest differentiators remain visible:

- controller cannot read truth state;
- custom deterministic simulation loop;
- fault injection;
- mission-state logic;
- independent numerical verification;
- objective PASS/FAIL scenario tests.

## Alternatives rejected and why

### Adaptive `solve_ivp` as the main simulation runtime

**[Decision] Rejected as the default runtime.**

`solve_ivp` is excellent for continuous ODE integration, but AstraLoop is a hybrid continuous/discrete system. Adaptive internal timesteps make it harder to define simple, exact semantics for controller sampling, sensor buffers, actuator updates, and fault ticks.

**[Decision]** Use it as a **reference oracle for selected numerical tests**, not as the mission scheduler.

### FastAPI

**[Decision] Rejected.**

There is no remote client, network boundary, or service deployment requirement.

### Streamlit

**[Decision] Rejected for MVP.**

It adds demo polish but weakens the systems/software-validation positioning and consumes time that should go into simulation and tests.

### Pydantic

**[Decision] Rejected for MVP, not banned forever.**

The local configuration schema is small enough for typed dataclasses plus explicit validation. Add Pydantic only if config complexity materially grows.

### Pandas

**[Decision] Rejected for core telemetry.**

Telemetry is append-only, fixed-schema, time-series output. Standard CSV writing plus NumPy/Matplotlib is sufficient and keeps the data model explicit.

### SQLite

**[Decision] Rejected.**

A run is best represented as an immutable directory of artifacts. There is no meaningful relational query requirement in the MVP.

### Docker

**[Decision] Not required.**

A Python-only local repository using `uv.lock` is already reproducible enough for this scope. Docker would increase setup cost without proving a target-role skill.

## What this stack proves to employers

**[Decision]** A finished AstraLoop using this stack can honestly demonstrate:

- Python package architecture;
- numerical simulation;
- deterministic execution;
- discrete/continuous system integration;
- state machines;
- control logic;
- reproducible randomness;
- fault injection;
- telemetry design;
- file-based serialization;
- automated validation;
- unit/integration/end-to-end testing;
- static typing;
- linting and formatting;
- dependency reproducibility;
- technical tradeoff reasoning.

---

# 5. Architecture Plan

## Architecture style

**[Decision]** Use a **functional core + imperative shell**.

### Functional core

Prefer pure or nearly pure logic for:

- state derivatives;
- RK4 stepping;
- validation checks;
- unit conversions;
- transition predicates where practical;
- command limit calculations.

### Imperative shell

The simulation engine coordinates stateful components:

- sensor buffers;
- controller memory;
- actuator lag state;
- mission state;
- RNG state;
- telemetry recorder;
- fault activation state.

**[Decision]** Do not use global mutable state.

---

## Folder structure

```text
astraloop/
├── README.md
├── pyproject.toml
├── uv.lock
├── .gitignore
├── docs/
│   ├── PROJECT_SELECTION_BRIEF.md
│   ├── PROJECT_MASTER_BLUEPRINT.md
│   ├── TECH_STACK_AND_ARCHITECTURE.md
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
│       │
│       ├── config/
│       │   ├── loader.py
│       │   ├── schema.py
│       │   └── validation.py
│       │
│       ├── model/
│       │   ├── state.py
│       │   ├── measurements.py
│       │   ├── commands.py
│       │   ├── events.py
│       │   └── results.py
│       │
│       ├── simulation/
│       │   ├── dynamics.py
│       │   ├── integrator.py
│       │   ├── environment.py
│       │   └── engine.py
│       │
│       ├── sensors/
│       │   ├── base.py
│       │   ├── models.py
│       │   ├── buffers.py
│       │   └── suite.py
│       │
│       ├── control/
│       │   ├── pid.py
│       │   ├── throttle.py
│       │   └── attitude.py
│       │
│       ├── actuators/
│       │   └── models.py
│       │
│       ├── mission/
│       │   ├── states.py
│       │   └── state_machine.py
│       │
│       ├── faults/
│       │   ├── base.py
│       │   ├── manager.py
│       │   ├── sensor_faults.py
│       │   ├── actuator_faults.py
│       │   └── disturbances.py
│       │
│       ├── telemetry/
│       │   ├── recorder.py
│       │   ├── serialization.py
│       │   └── plotting.py
│       │
│       ├── validation/
│       │   ├── checks.py
│       │   └── evaluator.py
│       │
│       └── scenarios/
│           └── runner.py
│
├── tests/
│   ├── unit/
│   │   ├── test_dynamics.py
│   │   ├── test_integrator.py
│   │   ├── test_pid.py
│   │   ├── test_sensors.py
│   │   ├── test_actuators.py
│   │   ├── test_state_machine.py
│   │   └── test_validation.py
│   ├── numerical/
│   │   └── test_rk4_against_scipy.py
│   ├── integration/
│   │   ├── test_closed_loop.py
│   │   ├── test_fault_injection.py
│   │   └── test_telemetry_output.py
│   └── scenarios/
│       ├── test_nominal.py
│       └── test_regression_scenarios.py
│
└── runs/
    └── .gitkeep
```

## Main modules

### `config/`

Responsibilities:

- load TOML;
- convert raw mappings to typed configuration objects;
- validate ranges, names, and cross-field constraints;
- produce a resolved configuration snapshot for each run.

**[Decision]** Configuration errors must be detected before simulation begins whenever possible.

---

### `model/`

Contains shared data structures only.

Examples:

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

```python
@dataclass(frozen=True)
class ControlCommand:
    throttle: float
    attitude_command: float
```

**[Decision]** Truth-state types and measurement types stay separate. The normal controller API accepts `MeasurementSnapshot`, not `VehicleState`.

---

### `simulation/dynamics.py`

Responsibilities:

- compute translational acceleration;
- compute rotational acceleration;
- apply gravity;
- apply thrust direction;
- compute fuel/mass derivative;
- enforce only mathematical/domain constraints that belong to dynamics.

Must not:

- read config files;
- know scenario names;
- sample sensors;
- run controllers;
- write telemetry;
- plot.

---

### `simulation/integrator.py`

Responsibilities:

- implement fixed-step RK4;
- accept a derivative function and current state;
- return the next state;
- contain no mission logic.

**[Decision]** Keep the integrator small enough that a reviewer can read it completely.

---

### `simulation/engine.py`

Owns the deterministic simulation clock and orchestration loop.

Recommended high-level tick:

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

**[Decision]** The exact ordering becomes part of the architecture contract and must be documented.

---

### `sensors/`

Responsibilities:

- simulate nominal measurement;
- apply noise/bias;
- maintain sample/delay buffers;
- expose measurement age/validity when relevant.

**[Decision]** Delay is modeled using simulation-time sample buffers, never `sleep()`.

---

### `control/`

Responsibilities:

- reusable PID logic;
- throttle control;
- attitude control;
- controller internal memory.

**[Decision]** Controller code must not import or receive the simulator’s normal truth-state object.

---

### `actuators/`

Responsibilities:

- command saturation;
- rate/response lag;
- actual applied actuator state.

---

### `mission/`

Responsibilities:

- define `MissionState`;
- define legal transitions;
- evaluate transition guards;
- generate transition events.

**[Decision]** Active flight-software transitions should use software-visible measurements and mission context.

**[Decision]** Simulator-only physical checks, such as detecting ground penetration or a non-finite truth state, belong to the simulation safety/termination layer rather than the flight-software state machine. This preserves the “controller does not cheat with truth” rule without preventing the simulator itself from enforcing physical invariants.

---

### `faults/`

Responsibilities:

- describe fault definitions;
- activate faults based on simulation time or explicit conditions;
- modify real subsystem behavior;
- emit activation/deactivation events.

**[Decision]** Do not scatter code such as:

```python
if scenario_name == "altimeter_freeze":
```

through the simulator.

Use fault objects/handlers targeted at a defined subsystem.

---

### `telemetry/`

Responsibilities:

- capture one consistent frame per simulation tick;
- save CSV;
- save events JSON;
- save resolved config;
- save summary;
- generate diagnostic figures.

**[Decision]** Plotting consumes completed telemetry. It does not own or mutate live simulation state.

---

### `validation/`

Responsibilities:

- evaluate objective mission checks;
- separate mission failure from software exception;
- generate structured validation results.

Example checks:

```text
final state == LANDED
|landing_vy| <= 2.0 m/s
horizontal error <= 5.0 m
pitch error <= 5 degrees
no invalid transition occurred
actual outcome matches expected scenario outcome
```

---

### `scenarios/runner.py`

Primary application service boundary:

```python
def run_scenario(
    config: ScenarioConfig,
    *,
    artifact_root: Path | None = None,
) -> RunResult:
    ...
```

Both CLI commands and end-to-end tests call this function.

---

## Data flow

```text
                 Scenario TOML
                      |
                      v
             Config Loader/Validator
                      |
                      v
              Resolved ScenarioConfig
                      |
          +-----------+-----------+
          |                       |
          v                       v
   subsystem setup           seeded RNG setup
          |                       |
          +-----------+-----------+
                      |
                      v
                Simulation Engine
                      |
                      v
               TRUE VehicleState
                      |
                      v
                  Sensors
                      |
                sensor faults
                      |
                      v
            MeasurementSnapshot
                      |
          +-----------+-----------+
          |                       |
          v                       v
   Mission State Machine      Controller
                                  |
                                  v
                           ControlCommand
                                  |
                                  v
                              Actuators
                                  |
                           actuator faults
                                  |
                                  v
                           ActuatorState
                                  |
                                  v
                              Dynamics
                                  |
                                  v
                               RK4 dt
                                  |
                                  +------> next TRUE VehicleState

Every tick
   |
   +------> Telemetry Recorder
                |
                +--> CSV
                +--> events JSON
                +--> resolved config JSON
                +--> summary JSON
                +--> diagnostic PNG

Completed run
   |
   v
Validator
   |
   v
PASS / FAIL / CONTROLLED ABORT / SIMULATOR ERROR
```

---

## State flow

**[Decision]** State ownership is explicit.

| State | Owner |
|---|---|
| True vehicle state | `SimulationEngine` |
| Simulation tick/time | `SimulationEngine` |
| Sensor history/delay buffers | Individual sensor/sensor suite |
| Sensor RNG state | Sensor/suite RNG objects |
| PID integral/previous-error memory | Controller objects |
| Actuator lag state | Actuator models |
| Current mission mode | `MissionStateMachine` |
| Active fault state | `FaultManager` |
| Telemetry rows/events | `TelemetryRecorder` |

**[Decision]** No singleton, global registry, or module-level mutable simulation object.

---

## Randomness and reproducibility

**[Decision]** Never use implicit global `numpy.random` state.

Use one scenario seed and derive dedicated RNGs for stochastic subsystems.

Conceptually:

```text
scenario seed
   |
   +--> altimeter RNG
   +--> velocity sensor RNG
   +--> attitude sensor RNG
   +--> disturbance RNG
```

This prevents unrelated random draws in one component from silently controlling another component.

The resolved seed configuration is saved with every run.

---

## API/service boundaries

**[Decision] No HTTP API.**

Internal boundaries are enough:

```python
load_scenario(path) -> ScenarioConfig

run_scenario(config) -> RunResult

SensorSuite.sample(truth, sim_time) -> MeasurementSnapshot

Controller.update(measurement, mission_state, dt) -> ControlCommand

ActuatorModel.update(command, dt) -> ActuatorState

rk4_step(state, actuator_state, params, dt) -> VehicleState

StateMachine.update(measurement, context) -> MissionUpdate

Validator.evaluate(run_result) -> ValidationResult
```

---

## Local database/storage plan

**[Decision] No database.**

Each run is an immutable artifact directory.

Recommended shape:

```text
runs/
└── nominal/
    └── 20260721-184500-a1b2c3/
        ├── telemetry.csv
        ├── events.json
        ├── resolved_config.json
        ├── summary.json
        └── flight_plot.png
```

The short suffix may be derived from a resolved-config hash.

### Why this is better than SQLite here

- human-readable;
- easy to inspect in GitHub/demo material;
- trivial to delete/reset;
- no schema migrations;
- no DB library;
- supports reproducibility;
- artifacts can be opened independently after a run.

---

## Error handling approach

### Configuration errors

Examples:

- `dt <= 0`;
- unknown state/fault;
- invalid target sensor;
- dry mass greater than initial mass;
- negative noise standard deviation;
- invalid actuator bounds.

**[Decision]** Raise a small domain-specific `ConfigError` before the simulation starts.

### Simulation invariant errors

Examples:

- NaN/Inf state;
- mass below dry mass beyond tolerance;
- impossible internal time ordering;
- invalid state-machine transition;
- numerical instability.

**[Decision]** Raise `SimulationError`, terminate cleanly, and save a diagnostic summary where possible.

### Domain mission outcomes

Examples:

- hard landing;
- controlled abort;
- failed landing tolerance.

**[Decision]** These are **results**, not Python exceptions.

### CLI exit codes

```text
0  command completed and result is expected/successful
1  scenario completed but validation/expected-outcome check failed
2  invalid configuration or CLI input
3  internal simulation/runtime error
```

### Logging

**[Decision]**

- Use standard-library `logging`.
- Default CLI output remains concise.
- `--verbose` exposes additional engineering logs.
- Event records belong in `events.json`, not only console text.

---

## Testing approach

### 1. Unit tests

Test pure/small components:

- gravity-only derivative;
- vertical thrust direction;
- pitch-to-thrust-vector mapping;
- mass floor;
- RK4 on equations with known solutions;
- sensor bias;
- deterministic sensor noise;
- sensor freeze;
- delay buffer behavior;
- PID clamping/anti-windup;
- actuator saturation;
- actuator lag;
- legal state transitions;
- rejected state transitions;
- validation thresholds;
- configuration validation.

### 2. Numerical verification tests

**[Decision]** Compare project RK4 against SciPy `solve_ivp` on selected deterministic open-loop cases.

Do not expect bit-for-bit equality.

Assert:

- trajectory agreement within documented tolerance;
- error decreases as `dt` is reduced;
- supported timestep remains numerically stable.

This is a particularly strong interview feature because it validates the code you wrote using an independent numerical implementation.

### 3. Integration tests

Examples:

```text
sensor -> controller -> actuator
fault manager -> sensor
fault manager -> actuator
state machine -> controller mode
engine -> telemetry recorder
```

Use short simulated durations to keep tests fast.

### 4. End-to-end scenario tests

Examples:

```python
def test_nominal_lands_within_limits():
    result = run_scenario(load_scenario("scenarios/nominal.toml"))
    assert result.validation.passed
    assert result.final_state is MissionState.LANDED
```

```python
@pytest.mark.parametrize(
    "scenario_name",
    [
        "altimeter_freeze.toml",
        "velocity_bias.toml",
        "sensor_delay.toml",
        "degraded_actuator.toml",
    ],
)
def test_regression_scenarios_match_expected_outcome(scenario_name):
    ...
```

### 5. Reproducibility tests

Same:

```text
scenario config
+ seed
+ code version
```

must produce the same structured outcome and equivalent numerical telemetry within the chosen deterministic expectations.

### 6. File/artifact tests

Use pytest `tmp_path`.

Assert:

- required files exist;
- JSON is valid;
- CSV schema is correct;
- plot generation succeeds headlessly;
- a failed validation still writes useful artifacts.

### Floating-point testing rule

**[Decision]** Do not assert exact equality for arbitrary numerical trajectories.

Use:

- `pytest.approx`;
- explicit absolute/relative tolerances;
- invariant/range tests;
- outcome/state checks.

---

# 6. Local Development Plan

## Install dependencies

### Recommended path

1. Install Git.
2. Install `uv`.
3. Clone the repository.
4. From the repository root:

```bash
uv python install 3.13
uv sync --all-groups
```

**[Decision]** `uv.lock` is committed so contributors/reviewers resolve the same tested dependency set.

### `pyproject.toml` dependency shape

Conceptually:

```toml
[project]
name = "astraloop"
requires-python = ">=3.13,<3.15"
dependencies = [
    "numpy",
    "matplotlib",
    "rich",
]

[project.scripts]
astraloop = "astraloop.cli:main"

[dependency-groups]
dev = [
    "scipy",
    "pytest",
    "ruff",
    "pyright",
]
```

**[Decision]** Exact resolved versions belong in `uv.lock`; do not duplicate a long list of exact pins in documentation.

---

## Run the app

Preferred:

```bash
uv run astraloop run scenarios/nominal.toml
```

Also support:

```bash
uv run python -m astraloop run scenarios/nominal.toml
```

List scenarios:

```bash
uv run astraloop list-scenarios
```

Run a fault:

```bash
uv run astraloop run scenarios/altimeter_freeze.toml
```

---

## Seed data

**[Decision]** AstraLoop has no database to seed.

The committed scenario files are the project’s seed/demo data:

```text
scenarios/nominal.toml
scenarios/altimeter_freeze.toml
scenarios/velocity_bias.toml
scenarios/sensor_delay.toml
scenarios/degraded_actuator.toml
```

A clean clone is immediately ready to run one of these scenarios.

---

## Run tests

All tests:

```bash
uv run pytest
```

Focused unit tests:

```bash
uv run pytest tests/unit
```

Scenario tests:

```bash
uv run pytest tests/scenarios
```

Numerical verification:

```bash
uv run pytest tests/numerical
```

Lint:

```bash
uv run ruff check .
```

Format check:

```bash
uv run ruff format --check .
```

Apply formatting:

```bash
uv run ruff format .
```

Type check:

```bash
uv run pyright
```

Recommended local quality gate before committing:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

---

## Reset local state

**[Decision]** There is no persistent application state outside `runs/`.

To reset:

1. delete generated run directories under `runs/`;
2. keep `runs/.gitkeep`;
3. rerun any bundled scenario.

No migrations, cache database, or reset script is required.

---

# 7. Minimum Professional Quality Rules

## Repository and dependency hygiene

**[Decision]**

- Commit `pyproject.toml`.
- Commit `uv.lock`.
- Do not commit `.venv/`.
- Do not commit generated `runs/` except a deliberately curated documentation example if needed.
- Keep one primary dependency workflow: `uv`.

## Secrets

**[Decision]** The MVP should require **no secrets at all**.

- Do not add API keys.
- Do not add cloud credentials.
- Do not add `.env` just because many tutorials do.

**[Decision]** Add `.env.example` only if a real future feature introduces environment variables.

## Input validation

Validate:

- paths;
- scenario schema;
- numeric bounds;
- sensor/fault target names;
- timestep;
- duration;
- mass values;
- actuator limits;
- validation thresholds.

Fail early with actionable messages.

## Numerical safety

**[Decision]**

- Check `math.isfinite` / NumPy finite state values at defined boundaries.
- Prevent mass below dry mass.
- Reject nonpositive `dt`.
- Document units for every physical field.
- Use radians internally for angular equations.
- Convert to degrees only at configuration/reporting boundaries where helpful.
- Do not silently clip invalid values unless clipping is explicitly the modeled behavior.

## Timing safety

**[Decision]**

- Never use wall-clock time to drive simulation physics.
- Never use `sleep()` to model latency.
- Use simulation ticks and buffers.
- Keep controller/sensor/fault timestamps in simulation time.

## Randomness

**[Decision]**

- No hidden global RNG.
- Every stochastic run has an explicit seed.
- Save the resolved seed/config with artifacts.

## Architecture discipline

**[Decision]**

- Dynamics must not import CLI or telemetry.
- Controller must not consume truth state.
- Plotting must not mutate simulation.
- Validation must not decide control commands.
- Faults must alter real subsystem behavior.
- Scenario names must not be hard-coded throughout core modules.

## Type discipline

**[Decision]**

- Type public module boundaries.
- Use dataclasses for meaningful domain records.
- Use `Enum` for mission states.
- Use `Protocol` only at boundaries with real interchangeable implementations.
- Do not create abstract-class hierarchies without a concrete need.

## Error clarity

**[Decision]**

Differentiate:

- CLI/configuration error;
- simulator/internal error;
- mission validation failure;
- expected controlled abort.

A hard landing should not look like a Python crash.

## Testing discipline

**[Decision]**

- Test behavior, not implementation trivia.
- Include unit + integration + scenario tests.
- Add regression tests for real bugs discovered during implementation.
- Avoid brittle screenshot/pixel tests.
- Avoid exact equality for arbitrary floating-point trajectories.
- Keep end-to-end scenarios deterministic.

## Documentation discipline

**[Decision]**

README must include:

- one-sentence explanation;
- one-command demo;
- architecture diagram;
- nominal result;
- one fault result;
- test command;
- design decisions;
- known limitations.

## Security/compliance scope

**[Decision]**

Do not add:

- authentication;
- permissions;
- encryption systems;
- enterprise secrets management;
- compliance frameworks;
- audit infrastructure.

They are unrelated to the portfolio goal.

## Avoiding overengineering

**[Decision]**

Do not add a framework, service, abstraction, or storage system unless it solves a demonstrated problem.

Prefer:

```text
clear function
> generic framework

small dataclass
> object hierarchy

immutable run folder
> database

explicit tick loop
> hidden scheduler

one strong diagnostic plot
> custom GUI
```

---

# 8. Final Architecture Summary

The following section is intentionally concise enough to paste into `docs/ARCHITECTURE.md`.

---

## AstraLoop Architecture Summary

**[Decision]** AstraLoop is a local Python software-in-the-loop flight-control validation system built around a deterministic fixed-step simulation loop. The production runtime uses Python 3.13, NumPy, a project-owned RK4 integrator, standard-library typed data structures/configuration tools, Matplotlib diagnostics, and a small CLI. SciPy is used as an independent numerical reference in verification tests rather than as the main mission scheduler. Development uses `uv`, `pytest`, Ruff, and Pyright.

The architecture enforces a strict separation between **true simulation state** and **software-visible measurements**. The simulation engine owns true vehicle state and simulation time. Sensor models sample truth and apply configured noise, bias, delay, or faults. The mission state machine and controller consume measurement snapshots rather than truth state. Controllers produce desired commands; actuator models apply saturation, lag, and actuator faults; the fixed-step integrator then advances the vehicle dynamics.

AstraLoop uses explicit state ownership and no global mutable simulation state. Sensor buffers, controller memory, actuator lag, mission mode, active faults, and telemetry are owned by their respective components. Simulation time is tick-based and independent of wall-clock speed, enabling deterministic sensor delay, fault activation, controller updates, and repeatable scenario tests.

Scenarios are configured in TOML. Each completed run is stored as an immutable local artifact bundle containing CSV telemetry, JSON events, resolved configuration, JSON summary, and a PNG diagnostic plot. No database or network API is required.

Testing is layered: unit tests validate dynamics, sensors, controllers, actuators, state transitions, and validation checks; numerical tests compare the custom RK4 integrator with SciPy reference solutions; integration tests exercise subsystem boundaries; end-to-end tests execute nominal and fault scenarios with deterministic PASS/FAIL expectations.

This architecture is intentionally framework-light so the portfolio signal remains the engineering itself: numerical simulation, timing, state machines, control, fault injection, observability, reproducibility, and automated validation.

---

# Final Decision Checklist

- [x] The final stack is justified by the target role.
- [x] Alternatives were compared rather than ignored.
- [x] Local setup is intentionally simple.
- [x] The architecture is understandable from the folder structure.
- [x] The testing approach is realistic.
- [x] Python remains the clear primary language.
- [x] No unnecessary database, web backend, cloud service, or SaaS layer was introduced.
- [x] The design preserves deterministic fault-driven simulation and objective validation.
