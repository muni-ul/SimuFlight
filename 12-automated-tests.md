# Feature 12 — Automated Tests

> **Project:** AstraLoop — Python Software-in-the-Loop Flight Control & Validation System  
> **Feature:** Automated Tests  
> **Document path:** `docs/features/12-automated-tests.md`  
> **Status:** Implementation specification  
> **Primary goal:** Build a deterministic, layered `pytest` suite that protects AstraLoop from the level of pure equations and stateful subsystem behavior through complete nominal/fault missions, failure handling, architecture boundaries, and local artifact generation—while avoiding brittle implementation-detail assertions, arbitrary floating-point equality, GUI-dependent tests, hidden network/filesystem state, and duplicated simulation pathways.

---

## Scope Boundary

**[Confirmed]** AstraLoop's selected engineering direction requires:

- unit tests;
- state-machine tests;
- integration tests;
- nominal end-to-end tests;
- fault-scenario regression tests;
- reproducibility tests;
- `pytest` execution from a clean local environment.

**[Confirmed]** The project testing discipline is:

- test behavior, not implementation trivia;
- use unit + integration + scenario tests;
- add regression tests for real bugs;
- avoid brittle screenshot/pixel tests;
- avoid exact equality for arbitrary floating-point trajectories;
- keep end-to-end scenarios deterministic.

**[Confirmed]** The production CLI and automated scenario tests must use the same application service:

```python
run_scenario(...)
```

There must not be a test-only simulator or demo-only engine.

**[Confirmed]** `pytest.approx`, `tmp_path`, and parametrized scenario tests are part of the selected test stack.

**[Confirmed]** Core quality commands are:

```bash
uv run pytest
uv run pytest tests/unit
uv run pytest tests/integration
uv run pytest tests/scenarios
uv run pytest tests/numerical

uv run ruff check .
uv run ruff format --check .
uv run pyright
```

**[Confirmed]** SciPy `solve_ivp` is an independent numerical reference used in verification tests rather than the production scheduler.

**[Decision]** Feature 12 owns the **overall automated test architecture and regression suite**.

It owns:

- test directory organization;
- `pytest` configuration;
- shared fixtures and test-data builders;
- deterministic seed policy for tests;
- floating-point assertion policy;
- unit-test strategy for Features 01–11;
- integration-test strategy for subsystem boundaries;
- end-to-end scenario-regression strategy;
- reproducibility tests;
- architecture-contract tests;
- failure-path tests;
- filesystem/artifact isolation;
- headless plotting test setup;
- test naming and parametrization conventions;
- regression-test workflow;
- one-command local quality gate;
- optional minimal continuous-integration workflow;
- test-suite acceptance criteria.

It does **not** own:

- production feature behavior;
- scientific/numerical reference derivations in detail;
- RK4-vs-SciPy order/convergence verification, which is Feature 13;
- benchmark/performance reporting;
- CLI implementation details, which are Feature 14;
- README/documentation implementation, which is Feature 15;
- a coverage-percentage vanity goal;
- randomized fuzzing infrastructure;
- cloud test farms;
- hardware testing;
- browser/UI automation.

---

# 1. Feature Overview

## Feature name

**Automated Tests**

---

## One-sentence description

**[Decision]** Implement a layered deterministic `pytest` suite that verifies AstraLoop's pure logic, stateful components, subsystem contracts, complete mission scenarios, reproducibility, failure handling, artifact outputs, and non-negotiable architecture boundaries through the same code paths used by the local application.

---

## Detailed description

AstraLoop is not one algorithm.

It is a hybrid system containing:

```text
continuous dynamics
fixed-step numerical integration
sampled sensors
seeded randomness
delay buffers
stateful controllers
actuator lag
mission states
fault lifecycle
telemetry
post-run validation
plotting
file artifacts
```

Testing only small helper functions would create a false sense of reliability.

Testing only complete missions would make failures difficult to diagnose.

The test suite therefore uses a layered structure:

```text
                     Scenario tests
              complete expected missions
                         /\
                        /  \
               Integration tests
            subsystem boundaries/order
                      /      \
                     /        \
                  Unit tests
        equations, state, guards, serializers
```

Feature 13 adds a separate numerical-verification layer beside this pyramid:

```text
custom RK4 <-> analytical/SciPy references
```

The full suite proves both:

```text
components behave correctly
```

and:

```text
the complete system behaves correctly
```

---

## Core testing philosophy

### 1. Behavior over implementation

Good:

```python
def test_freeze_holds_last_deliverable_value():
    ...
```

Weak/brittle:

```python
def test_sensor_has_private_attribute_named_buffer():
    ...
```

Tests should survive internal refactoring when externally observable behavior stays correct.

---

### 2. Exact assertions only where exactness is part of the contract

Use exact equality for:

- enum states;
- integer ticks;
- event order;
- fault IDs;
- config digests;
- legal transition sets;
- CSV headers;
- JSON keys;
- deterministic serialized files;
- Boolean/status outcomes.

Use tolerance/range assertions for:

- integrated trajectories;
- floating-point control response;
- numerical state;
- convergence;
- physical metrics.

---

### 3. Deterministic tests by default

Every stochastic test supplies an explicit seed or injected RNG.

No test depends on:

- global `random`;
- global NumPy RNG;
- current time;
- machine speed;
- unordered filesystem results;
- hash-randomized set ordering;
- network availability.

---

### 4. Smallest test that proves the contract

A PID saturation rule belongs in a unit test.

The entire controller-actuator-dynamics loop belongs in an integration test.

A nominal autonomous landing belongs in a scenario test.

Do not use a full 60-second simulation to test a clamp helper.

---

### 5. Failures should be diagnosable

Scenario tests should expose:

- scenario ID;
- config digest;
- actual vs expected outcome;
- failed validation checks;
- final state/time;
- activated/pending fault IDs.

A scenario failure should not produce only:

```text
assert False
```

---

### 6. The test suite is part of the portfolio demo

A reviewer should be able to run:

```bash
uv run pytest
```

and see that AstraLoop validates:

- nominal behavior;
- fault behavior;
- architecture;
- reproducibility;
- artifacts;
- error handling.

---

## Test layers

### Layer 1 — Unit tests

Purpose:

```text
prove one component's behavior in isolation
```

Targets:

- dynamics;
- integrator local behavior;
- sensors/buffers;
- PID/controller helpers;
- actuators;
- state machine;
- fault manager;
- config parsing/resolution;
- telemetry recorder/serializers;
- validation;
- plotting data/structure.

Characteristics:

- fast;
- focused;
- minimal dependencies;
- synthetic fixtures;
- precise failure location.

---

### Layer 2 — Integration tests

Purpose:

```text
prove subsystem boundaries and tick ordering
```

Targets:

- sensor → measurement → controller;
- controller → actuator;
- actuator → dynamics;
- fault → sensor;
- fault → actuator;
- sensor health → mission abort;
- mission state → controller profile;
- engine → telemetry alignment;
- runner → artifacts;
- validation → summary;
- telemetry → plot.

Characteristics:

- multiple real components;
- short runs;
- deterministic;
- often use simplified vehicle/config values;
- no scenario-ID branching.

---

### Layer 3 — Scenario tests

Purpose:

```text
prove complete configured missions through the production application boundary
```

Required scenarios:

```text
nominal
altimeter_freeze
velocity_bias
sensor_delay
degraded_actuator
```

Characteristics:

- call `load_scenario(...)`;
- call `run_scenario(...)` or `run_scenario_file(...)`;
- use the same engine as CLI;
- assert `ValidationResult`;
- assert configured faults activated;
- assert expected outcome matched;
- avoid duplicating validator formulas.

---

### Layer 4 — Reproducibility and regression tests

Purpose:

```text
prove same seed/config gives repeatable mission behavior
and prevent real bugs from returning
```

Targets:

- sensor RNG stream isolation;
- same config digest;
- same event sequence;
- same final state/outcome;
- same validation metrics;
- stable data artifacts;
- bug-specific minimal reproductions.

---

### Layer 5 — Artifact and failure-path tests

Purpose:

```text
prove the local application remains usable when inputs/runs fail
```

Targets:

- ConfigError;
- SimulationError;
- Validation failure;
- controlled abort;
- ArtifactError;
- PlotError;
- incomplete/corrupt telemetry;
- output collisions;
- temporary staging cleanup;
- no repository pollution.

---

## Feature 13 boundary

Feature 12 includes ordinary integrator unit tests such as:

- constant derivative;
- zero derivative;
- invalid timestep;
- deterministic stepping.

Feature 13 owns deeper numerical verification such as:

- RK4 order of accuracy;
- convergence-ratio tests;
- comparison against `solve_ivp`;
- independent open-loop references;
- documented numerical tolerances.

This separation prevents Feature 12 from becoming a duplicate numerical-analysis document while keeping the full `pytest` suite unified.

---

## Test directory structure

Recommended:

```text
tests/
├── conftest.py
├── helpers/
│   ├── __init__.py
│   ├── builders.py
│   ├── assertions.py
│   └── fakes.py
│
├── unit/
│   ├── test_state.py
│   ├── test_dynamics.py
│   ├── test_integrator.py
│   ├── test_sensors.py
│   ├── test_sensor_buffers.py
│   ├── test_pid.py
│   ├── test_controllers.py
│   ├── test_actuators.py
│   ├── test_state_machine.py
│   ├── test_fault_manager.py
│   ├── test_config_loader.py
│   ├── test_config_validation.py
│   ├── test_telemetry_recorder.py
│   ├── test_serialization.py
│   ├── test_validation.py
│   └── test_plotting.py
│
├── numerical/
│   ├── test_rk4_analytical.py
│   └── test_rk4_against_scipy.py
│
├── integration/
│   ├── test_sensor_controller.py
│   ├── test_controller_actuator.py
│   ├── test_actuator_dynamics.py
│   ├── test_closed_loop.py
│   ├── test_fault_sensor.py
│   ├── test_fault_actuator.py
│   ├── test_fault_mission.py
│   ├── test_engine_order.py
│   ├── test_engine_telemetry.py
│   ├── test_mission_validation.py
│   ├── test_runner_artifacts.py
│   └── test_diagnostic_visualization.py
│
├── scenarios/
│   ├── test_nominal.py
│   ├── test_fault_scenarios.py
│   └── test_reproducibility.py
│
└── architecture/
    ├── test_truth_boundary.py
    ├── test_import_boundaries.py
    └── test_no_scenario_branches.py
```

---

## Why keep architecture tests separate

Some requirements are not merely behavior details.

They are non-negotiable system boundaries:

```text
controller cannot read VehicleState
dynamics cannot import CLI/telemetry
scenario names cannot control core subsystem behavior
plotting cannot import mutable engine internals
```

A small architecture-test directory makes these constraints visible.

Do not turn it into a broad source-code style checker.

Only protect high-value boundaries.

---

## `pytest` configuration

Recommended `pyproject.toml` section:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = [
    "--strict-markers",
    "--strict-config",
]
xfail_strict = true
filterwarnings = [
    "error",
]
```

Potential:

```toml
markers = [
    "scenario: complete scenario regression tests",
    "numerical: numerical reference or convergence tests",
    "slow: deliberately slower tests excluded only by explicit developer choice",
]
```

### Decision

Use directory organization as the main grouping mechanism.

Use markers only where they add a real command/filtering benefit.

Do not assign many redundant markers to every test.

---

## Warning policy

**[Decision]** Treat unexpected warnings as test failures.

Why:

- numerical/runtime warnings can indicate invalid values;
- deprecations should not accumulate unnoticed;
- plotting/backend warnings can reveal resource leaks;
- config parsing warnings should be deliberate.

For one known third-party warning, add the narrowest possible filter with a comment.

Do not globally ignore warnings.

---

## `xfail` policy

Use `pytest.mark.xfail` only when:

- a known documented bug exists;
- a regression test already describes it;
- the issue is not being hidden as "passing";
- `strict=True` behavior applies.

Do not use xfail for unfinished core MVP requirements.

A core feature not implemented should fail or be developed on a branch, not permanently xfailed in portfolio-ready main.

---

## Skip policy

Skip only when the test genuinely requires an unavailable optional condition.

Examples:

- SciPy numerical tests when SciPy dev group is deliberately not installed in a minimal runtime-only environment;
- platform-specific filesystem semantic test if not portable.

In the documented developer environment:

```text
uv sync --all-groups
```

all required tests should run.

Do not skip scenario tests in the primary quality gate.

---

## Test naming convention

Use:

```text
test_<behavior>_<condition>_<expected>
```

when helpful.

Examples:

```text
test_zero_thrust_produces_downward_acceleration
test_freeze_before_first_sample_is_unavailable
test_abort_wins_when_nominal_transition_also_true
test_same_seed_reproduces_sensor_sequence
```

Names should explain the contract without opening the body.

---

## Arrange / Act / Assert

Use clear test structure:

```python
def test_freeze_holds_last_value():
    # Arrange
    ...

    # Act
    ...

    # Assert
    ...
```

Comments are optional when the code is already obvious.

Avoid giant test functions with many unrelated assertions.

---

## Assertion density

A unit test should generally prove one behavior.

An integration/scenario test may use several connected assertions because one complete contract includes:

- final outcome;
- fault activation;
- final state;
- scenario pass.

Do not split one scenario into dozens of tests that each rerun the same expensive mission unless parametrization/fixtures make it efficient and still clear.

---

## Shared fixtures

Recommended `conftest.py` fixtures:

```text
base_dt
base_vehicle_parameters
base_environment
initial_vehicle_state
nominal_sensor_config
nominal_controller_config
nominal_actuator_config
nominal_mission_config
nominal_validation_config
minimal_resolved_config
```

Use factory fixtures rather than one enormous mutable object.

Example:

```python
@pytest.fixture
def make_vehicle_state():
    def factory(**overrides):
        values = {
            "x": 0.0,
            "y": 0.0,
            "vx": 0.0,
            "vy": 0.0,
            "theta": 0.0,
            "omega": 0.0,
            "mass": 1200.0,
        }
        values.update(overrides)
        return VehicleState(**values)
    return factory
```

---

## Fixture mutation policy

Fixtures should return:

- frozen dataclasses;
- fresh mutable components;
- factory functions.

Do not return one module/session-scoped mutable controller, sensor buffer, recorder, or engine.

State leakage between tests is a critical risk.

---

## Fixture scope

Default:

```text
function
```

Use broader scope only for truly immutable data or expensive read-only constants.

Do not use session-scoped stateful runtime components.

---

## Test builders

`tests/helpers/builders.py` may provide:

```text
build_measurement_snapshot
build_control_command
build_actuator_update
build_telemetry_frame
build_completed_telemetry
build_fault_definition
build_resolved_config
```

Requirements:

- produce valid defaults;
- accept explicit overrides;
- never hide important behavior with random values;
- remain test-only;
- avoid duplicating production validation formulas.

---

## Fakes, stubs, and spies

Use small test doubles at real interfaces.

Examples:

- fake integrator that records applied actuation;
- stub sensor returning defined readings;
- spy telemetry recorder recording engine order;
- fake artifact writer that raises;
- fake clock is unnecessary because simulation time is tick-based.

Avoid mocking pure mathematical functions.

Avoid patching deep private internals.

---

## Mocking policy

Mock:

- filesystem failure boundaries;
- plot save failure;
- optional Git metadata collection;
- deliberately injected subsystem interface in an ordering test.

Do not mock:

- entire scenario runner in a scenario test;
- controller in a closed-loop integration test;
- validator in validation integration tests;
- fault manager in fault scenario tests.

A test that mocks the thing it claims to prove is not valuable.

---

## Floating-point assertion policy

### Exact equality

Use only when mathematically/runtime-contract exactness is expected.

Examples:

```text
tick values
zero derivative state unchanged
clamp returns exact bound
enum/status
seed/config digest
serialized strings
```

### `pytest.approx`

Use for known expected numeric results:

```python
assert result == pytest.approx(
    expected,
    rel=1e-9,
    abs=1e-12,
)
```

Tolerance must be chosen from:

- problem scale;
- integration accuracy;
- documented validation tolerance;
- reference method.

Do not copy one tolerance everywhere.

### NumPy arrays

Use:

```python
np.testing.assert_allclose(...)
```

or:

```python
pytest.approx(...)
```

when appropriate.

### Ranges/invariants

Prefer when exact trajectory is not important:

```python
assert state.mass >= dry_mass
assert -limit <= command <= limit
assert next_value > current_value
assert result.final_state is LANDED
```

---

## Arbitrary trajectory rule

**[Decision]** Do not assert every state sample equals hard-coded decimals for a full arbitrary nonlinear mission.

Why:

- harmless implementation/refactoring changes can alter tiny numerical details;
- such tests are difficult to review;
- they obscure which contract matters.

Instead assert:

- deterministic repeatability;
- objective outcome;
- transitions;
- limits/invariants;
- selected meaningful metrics;
- numerical reference tests in Feature 13.

---

## Golden/snapshot files

**[Decision]** Do not use large golden telemetry or PNG snapshots as the main test oracle.

Small schema examples are acceptable.

Reasons:

- large diffs are unreadable;
- updating snapshots can hide regressions;
- plot bytes vary by platform;
- objective validators already provide better assertions.

A curated example run may exist for documentation, but test success should not depend on blindly matching it.

---

## Randomness testing

### Explicit seeds

Every stochastic test supplies:

```text
seed
```

or a dedicated `np.random.Generator`.

### Same-seed test

Assert same sensor sample sequence.

### Different-stream test

Assert adding/disabling another sensor stream does not alter an unrelated sensor's seeded sequence when using the canonical stream assignment.

### Different-seed test

Do not require every generated value to differ, but assert a representative sequence differs.

### No statistical flakiness

Do not write tests such as:

```python
assert random_noise.mean() < 0.01
```

on a tiny random sample unless a deterministic fixed sample/robust tolerance is used.

The MVP is not a statistical-distribution validation project.

---

## Filesystem isolation

Use:

```python
tmp_path
```

for every test that writes:

- scenario files;
- CSV;
- JSON;
- PNG;
- run directories;
- staging directories.

No test should write to repository `runs/` by default.

---

## Working-directory independence

Tests should resolve repository fixture paths through a known project-root helper or `Path(__file__)`.

They must not assume pytest was started from an arbitrary specific current directory unless `pyproject.toml` explicitly defines the root.

---

## Environment isolation

Tests must not require:

- API keys;
- `.env`;
- cloud credentials;
- network;
- browser;
- display server;
- database;
- Docker;
- physical hardware.

---

## Time isolation

No tests use `sleep()` for simulation timing.

Wall-clock timing is not an assertion for correctness.

Avoid tests like:

```python
assert run_finished_in_less_than_1_second
```

as hard correctness gates across arbitrary machines.

Feature 13/benchmarking can measure performance with an appropriate non-flaky methodology.

---

## Headless plotting setup

Recommended test environment:

```text
MPLBACKEND=Agg
```

Set before importing `matplotlib.pyplot`.

Add a test that monkeypatches `plt.show` to raise if called.

Plot tests assert:

- axes/series/markers;
- output file existence;
- image dimensions;
- no leaked figures.

No pixel-perfect assertions.

---

## Test logs/output

By default, test output should remain concise.

Use pytest's captured output/logging.

A failing scenario assertion helper should include a compact diagnostic message.

Example:

```python
assert_scenario_passed(result)
```

failure output:

```text
Scenario degraded_actuator failed:
  expected: controlled_abort
  actual: validation_fail
  final state: LANDED
  final time: 31.18 s
  failed checks:
    - expected_outcome_matched
    - fault_activated.degraded_gimbal_01
```

Do not print telemetry rows during successful tests.

---

## Custom assertion helpers

Recommended:

```python
def assert_scenario_passed(
    result: RunResult,
) -> None:
    ...
```

```python
def assert_finite_vehicle_state(
    state: VehicleState,
) -> None:
    ...
```

```python
def assert_event_sequence(
    events,
    expected,
) -> None:
    ...
```

Helpers should improve messages, not hide core assertions behind opaque magic.

---

## Parametrization

Use `pytest.mark.parametrize` for:

- valid/invalid transition pairs;
- sensor status cases;
- fault type/target combinations;
- boundary values;
- curated scenario files;
- serializer None/enum/bool cases.

Avoid deeply nested parametrization that creates unreadable test IDs.

Provide explicit IDs:

```python
@pytest.mark.parametrize(
    "state",
    [...],
    ids=["prelaunch", "ascent", ...],
)
```

---

## Property/invariant tests without extra framework

The selected stack does not include Hypothesis.

Use deterministic loops/parametrized values to test invariants.

Examples:

```text
for representative throttle commands:
    actual stays within physical bounds

for representative pitch angles:
    wrap_angle result is in [-pi, pi)

for a fixed set of dt:
    zero derivative leaves state unchanged

for representative sensor delays:
    returned source tick is not newer than eligible tick
```

Do not add Hypothesis until it solves a demonstrated testing gap.

---

## Unit-test coverage by feature

### Feature 01 — 2D Flight Dynamics

Required unit behaviors:

- state/config finite validation;
- zero thrust;
- vertical thrust;
- pitch changes thrust direction;
- torque sign;
- gravity;
- fuel burn;
- dry-mass floor;
- no negative fuel;
- invalid actuation;
- angle handling;
- deterministic derivatives.

---

### Feature 02 — Numerical Simulation Engine

Required ordinary tests:

- tick starts at zero;
- `time=tick*dt`;
- one RK4 step;
- one tick ordering;
- terminal-at-start;
- max-time semantics;
- invariant failure;
- fixed applied input across RK4 stages;
- one actuator/fault/telemetry update per tick.

Deep numerical verification is Feature 13.

---

### Feature 03 — Simulated Sensors

Required:

- sample cadence;
- deterministic seeded noise;
- constant bias;
- delay-buffer eligibility;
- unavailable initial delay;
- stale age;
- freeze;
- freeze-before-first-sample;
- release semantics;
- independent RNG streams;
- invalid config.

---

### Feature 04 — Closed-Loop Controllers

Required:

- proportional/integral/derivative contributions;
- output clamp;
- integral clamp;
- anti-windup;
- mode reset;
- update cadence;
- held command between updates;
- invalid/stale input behavior;
- no truth-state API;
- deterministic sequence.

---

### Feature 05 — Actuator Modeling

Required:

- saturation;
- zero lag;
- first-order step;
- monotonic convergence;
- rate limit;
- degradation modifiers;
- atomic update;
- no command mutation;
- deterministic sequence.

---

### Feature 06 — Mission State Machine

Required:

- every legal transition;
- selected illegal transitions;
- confirmation/debounce;
- abort priority;
- critical-measurement timeout;
- terminal no-op;
- transition event;
- measurement-not-truth boundary.

---

### Feature 07 — Fault Injection

Required:

- typed config;
- lifecycle;
- exact activation/deactivation tick;
- duplicate/skipped manager tick;
- composition rules;
- no-op fault rejection;
- event identity/order;
- no scenario-name behavior.

---

### Feature 08 — Scenario Runner

Required:

- strict TOML schema;
- unknown/missing key;
- units/tick resolution;
- cross-field validation;
- config digest;
- RNG bundle;
- scenario discovery;
- fresh runtime every run;
- no artifact pollution.

---

### Feature 09 — Telemetry/Event Logging

Required:

- sequential frames;
- terminal/error final frame;
- event sequence;
- CSV schema;
- JSON strictness;
- staging/finalization;
- collision handling;
- diagnostic artifacts;
- deterministic content.

---

### Feature 10 — Mission Validation

Required:

- touchdown frame;
- truth-based metrics;
- limit boundaries;
- angle wrap;
- outcomes;
- expected failure;
- transition validation;
- fault activation contract;
- immutable results.

---

### Feature 11 — Diagnostic Visualization

Required:

- PlotData conversion;
- six axes;
- truth/measurement lines;
- state spans;
- event markers;
- supplied validation annotation;
- headless PNG;
- no `show`;
- no pixel test;
- figure cleanup.

---

## Integration-test matrix

| Integration boundary | Core proof |
|---|---|
| Sensors → Controller | Controller uses MeasurementSnapshot and reacts to measured values |
| Controller → Actuator | Desired command becomes bounded/lagged applied state |
| Actuator → Dynamics | Physics uses actual actuation, not desired command |
| Mission → Controller | New mission state selects/reset correct profile |
| Fault → Sensor | Freeze/bias/delay changes real sensor output |
| Fault → Actuator | Degradation changes real actuator response |
| Sensor → Mission | Sustained invalid critical data can produce ABORT |
| Engine → All | Correct once-per-tick ordering |
| Engine → Telemetry | State tick, command, next state, events align |
| Runner → Engine | Resolved config builds fresh complete runtime |
| Telemetry → Validation | Objective result uses completed immutable truth/events |
| Telemetry → Plot | Completed run produces correct figure structure |
| Runner → Artifacts | Completed/failing/abort runs produce correct local bundle |

---

## Engine-order test

This is one of the highest-value integration tests.

Use spies/stubs to record calls:

```text
fault update
sensor sample
mission update
controller update
actuator update
integrator
invariant validation
telemetry record
```

Assert exact sequence.

Do not infer order only from final output.

This test protects the semantics of:

- same-tick fault activation;
- mission-profile changes;
- applied actuation;
- telemetry alignment.

---

## Truth-boundary tests

### Functional boundary

Attempt to build/run controller using only:

```text
MeasurementSnapshot
MissionState
dt
```

No `VehicleState` should be required.

### Signature/import boundary

A minimal architecture test may inspect:

- public controller signature annotations;
- imports under `astraloop.control`.

Required:

```text
no production control module imports VehicleState
```

Use standard-library `ast` if source-level enforcement is needed.

Keep the test narrow and readable.

---

## Import-boundary tests

Recommended non-negotiable restrictions:

```text
simulation.dynamics
    must not import cli
    must not import telemetry serialization/plotting

control
    must not import VehicleState/dynamics truth API

validation
    must not import controller implementation to decide commands

telemetry.plotting
    must not import SimulationEngine

core modules
    must not import scenario filenames/IDs
```

Do not write a complete generic import graph framework.

---

## No-scenario-branch test

Because source-specific branches are explicitly forbidden, a small test may scan core production modules for bundled scenario identifiers:

```text
"altimeter_freeze"
"velocity_bias"
"sensor_delay"
"degraded_actuator"
```

Allowed locations:

- scenario TOML;
- tests;
- README/docs;
- scenario discovery metadata.

Forbidden locations:

- dynamics;
- sensors;
- controller;
- actuators;
- mission;
- engine;
- fault behavior internals;
- validator;
- plotter.

This is one of the few justified source-inspection tests because the architecture rule is explicit and recruiter-important.

---

## Scenario-test contract

Required scenario test shape:

```python
@pytest.mark.parametrize(
    "scenario_path",
    [
        Path("scenarios/nominal.toml"),
        Path("scenarios/altimeter_freeze.toml"),
        Path("scenarios/velocity_bias.toml"),
        Path("scenarios/sensor_delay.toml"),
        Path("scenarios/degraded_actuator.toml"),
    ],
)
def test_scenario_matches_expected_contract(
    scenario_path: Path,
) -> None:
    result = run_scenario_file(
        scenario_path,
        artifact_root=None,
    )

    assert_scenario_passed(result)
```

Additional focused assertions:

- configured fault activated for fault scenarios;
- nominal has no fault events;
- result config digest exists;
- final result is structured;
- no artifact directory when persistence disabled.

---

## Why scenario tests should not duplicate validation formulas

Weak:

```python
assert abs(result.truth.vy) <= 2.0
assert abs(result.truth.x) <= 5.0
...
```

in every scenario test.

Preferred:

```python
assert result.validation.scenario_passed
```

with validator unit tests proving formulas.

A nominal test may additionally assert:

```python
assert result.validation.actual_outcome is ActualOutcome.PASS
```

This prevents duplicate test-oracle logic.

---

## Scenario expected outcomes

Do not infer from scenario name.

The test reads the expected outcome from resolved configuration and verifies:

```text
actual == expected
```

The final tuned files determine whether a fault:

- recovers and passes;
- causes controlled abort;
- causes expected validation failure.

---

## Reproducibility tests

### Same run twice

Run the same scenario twice with:

```text
artifact_root=None
```

Assert:

- same config digest;
- same final tick/time;
- same final truth state within exact/tolerance contract;
- same mission transition sequence;
- same fault lifecycle sequence;
- same actual outcome;
- same scenario pass;
- same validation metrics/check statuses;
- same telemetry frame count.

### Artifact reproducibility

With separate `tmp_path` roots, assert deterministic files:

```text
telemetry.csv
events.json
resolved_config.json
```

match byte-for-byte.

Do not compare:

- artifact directory name;
- UTC summary timestamps;
- PNG bytes.

---

## Different-seed test

For a noisy scenario:

- config differs only by seed;
- config digest differs;
- deterministic timeline/fault schedule remains structurally valid;
- at least one stochastic measurement sequence differs.

Do not require a different mission outcome.

---

## Failure-path tests

### ConfigError

Assert:

- invalid file fails before tick zero;
- no RNG draw;
- no artifact directory;
- useful key/path message.

### SimulationError

Assert:

- internal error remains exception;
- diagnostic bundle exists when persistence enabled;
- error frame/event exists;
- error is not misclassified as expected outcome.

### Validation failure

Assert:

- run completes;
- no Python crash;
- full artifact bundle exists;
- scenario passes only if validation failure was expected.

### Controlled abort

Assert:

- run completes;
- outcome is controlled abort;
- full artifact bundle exists;
- landing checks are N/A.

### ArtifactError

Assert:

- cause preserved;
- no final normal-looking partial directory;
- staging cleanup best effort.

### PlotError

For completed normal run where plot is required:

- final bundle not published as complete;
- error remains artifact/presentation failure, not mission result.

---

## Regression-test workflow

When a real bug is discovered:

1. Capture the smallest deterministic input/config that reproduces it.
2. Add a test that fails before the fix.
3. Name the test after the behavior, not ticket number only.
4. Fix production code.
5. Keep the test permanently.
6. Optionally document the bug in `docs/DEBUGGING_NOTES.md` or README lessons.
7. Do not weaken assertions merely to make the suite green.

High-value likely regressions:

- thrust/gimbal sign error;
- RK4 state-order mix-up;
- delay buffer off by one;
- freeze activation sample off by one;
- PID integrator not reset;
- actuator updated four times inside RK4;
- mission guard chattering;
- abort losing to nominal transition;
- fault activated after sensor sample;
- telemetry command/state off by one;
- touchdown frame wrong;
- validation uses measured rather than true state;
- expected controlled abort shown as test failure;
- plot opens GUI in pytest;
- artifact run overwritten.

---

## Test data policy

Use three kinds of test data.

### 1. Inline focused values

For simple unit behavior.

### 2. Builders/fixtures

For typed valid records.

### 3. Committed curated scenarios

For full end-to-end tests.

Do not commit large generated run bundles as required test fixtures.

---

## Test count policy

Do not optimize for a large test number.

A recruiter-facing claim should use the measured final count only after implementation.

Quality is demonstrated by:

- important behavior covered;
- layers represented;
- regression tests;
- deterministic scenarios;
- meaningful failures.

---

## Coverage policy

**[Decision]** Code coverage is optional and not a primary MVP gate.

Do not add a hard percentage simply for appearance.

If coverage tooling is added later:

- use it to find untested risk;
- do not write trivial tests to satisfy a number;
- exclude generated/boilerplate only with justification.

The source-selected dev stack does not require a coverage dependency.

---

## Test performance policy

The full curated suite should be practical for local development.

However:

**[Decision]** Do not set a hard wall-clock pass/fail threshold before measuring the implemented suite on ordinary hardware.

Use design controls instead:

- short unit tests;
- short integration runs;
- only five core end-to-end scenarios;
- no GUI;
- no sleeps;
- no network;
- no Monte Carlo;
- no unnecessary repeated missions.

Feature 13 may report measured benchmark/test timing after implementation.

---

## Parallel test execution

Do not require `pytest-xdist`.

State isolation should make future parallel execution possible, but the primary suite must work using plain `pytest`.

Adding parallelism can hide shared-state bugs if introduced too early.

---

## CI

The architecture calls CI optional.

**[Decision]** A single small GitHub Actions workflow is recommended after local commands are stable.

Conceptual steps:

```text
checkout
install uv
uv python install 3.13
uv sync --all-groups --locked
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

Requirements:

- no secrets;
- no Docker service;
- no database;
- no network-dependent tests beyond installing dependencies;
- use committed `uv.lock`.

Feature 12 remains complete locally even before CI, but the portfolio-ready repository benefits from the workflow badge/result.

---

## Local quality gate

Recommended before committing:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

Optionally place in a documented shell command or task runner only if that avoids duplication.

Do not add Make, Nox, Tox, or pre-commit solely to wrap four clear commands unless a real workflow need appears.

---

## Why no Tox/Nox in MVP

`uv` already owns the environment and command workflow.

A single Python 3.13 baseline is selected.

Multiple interpreter matrices are not required.

Use direct commands for transparency.

---

## Error-message quality

Custom assertion helpers and production exceptions should produce actionable test failure output.

Bad:

```text
AssertionError
```

Good:

```text
expected fault freeze_altimeter_01 to activate exactly once;
found 0 activation events;
mission terminated at tick 850 in state ABORT
```

---

## Test documentation

README Feature 15 should list:

```bash
uv run pytest
uv run pytest tests/unit
uv run pytest tests/scenarios
uv run pytest tests/numerical
```

It should briefly explain test layers.

Do not document every test function.

---

## Why it matters

AstraLoop's target role is systems/simulation/validation software.

The test suite is not auxiliary polish.

It is the evidence that:

- timing semantics are deliberate;
- faults genuinely modify behavior;
- controller boundaries are enforced;
- complete missions are reproducible;
- expected failures are understood;
- numerical and I/O errors fail safely;
- refactoring does not silently break the system.

---

## Skill it demonstrates

A strong Feature 12 demonstrates:

- test architecture;
- unit testing;
- integration testing;
- end-to-end validation;
- deterministic test design;
- seeded randomness;
- floating-point test strategy;
- failure injection;
- filesystem isolation;
- headless graphics testing;
- regression testing;
- architecture enforcement;
- quality gates;
- CI readiness.

---

## Priority

**P0 — Core project requirement**

The source explicitly says tests should not be superficial and must include end-to-end scenario assertions.

AstraLoop is not portfolio-ready when it only runs manually.

---

## Complexity

**High in breadth, medium per test**

Most individual tests are straightforward.

The challenge is covering the important cross-feature contracts without:

- excessive duplication;
- brittle numeric snapshots;
- slow full-run overuse;
- hidden shared state;
- tests that only mirror implementation.

---

# 2. User / Developer Flow

## Happy path

1. Developer installs all groups:

```bash
uv sync --all-groups
```

2. Runs:

```bash
uv run pytest
```

3. Unit tests validate components.
4. Numerical tests validate RK4 references.
5. Integration tests validate subsystem boundaries/order.
6. Scenario tests run nominal and four fault missions.
7. Reproducibility tests repeat selected scenarios.
8. Artifact tests use temporary directories.
9. Plot tests use Agg and open no window.
10. Test process exits successfully.
11. Developer runs Ruff/Pyright quality gate.
12. Reviewer sees a real automated validation suite.

---

## Focused development flow

### Editing sensors

Run:

```bash
uv run pytest tests/unit/test_sensors.py
uv run pytest tests/integration/test_fault_sensor.py
```

Then full suite.

### Editing state machine

Run:

```bash
uv run pytest tests/unit/test_state_machine.py
uv run pytest tests/integration/test_fault_mission.py
uv run pytest tests/scenarios
```

### Editing plotting

Run:

```bash
uv run pytest tests/unit/test_plotting.py
uv run pytest tests/integration/test_diagnostic_visualization.py
```

Then full suite.

---

## First-time implementation path

1. Configure pytest.
2. Add package-import smoke test.
3. Add VehicleState/dynamics tests.
4. Add integrator smoke tests.
5. Add sensor/PID/actuator tests.
6. Add state-machine tests.
7. Add engine-order integration test.
8. Add fault integration tests.
9. Add telemetry/validation/artifact tests.
10. Add nominal scenario test.
11. Add four fault scenario tests.
12. Add reproducibility test.
13. Add architecture-boundary tests.
14. Add minimal CI after local gate is stable.

---

## Empty state

A brand-new repository should have at least:

```text
one package import/smoke test
```

`pytest` should collect and pass.

A portfolio-ready project cannot have an empty test suite.

---

## Error path

### Test collection error

Treat as suite failure.

### Unknown marker

Strict marker mode fails.

### Warning

Unexpected warning fails.

### GUI call

Headless test fails.

### Repository write

Tests should fail/assert if unintended files appear.

### Flaky scenario

Do not rerun automatically to hide it.

Diagnose seed/state leakage/tolerance.

---

# 3. UX / Developer Experience Requirements

## Commands

Required:

```bash
uv run pytest
uv run pytest tests/unit
uv run pytest tests/integration
uv run pytest tests/scenarios
uv run pytest tests/numerical
```

---

## Test output

Normal success should be concise.

Failure should show:

- clear test name;
- scenario ID where relevant;
- actual/expected outcome;
- failed check details;
- no uncontrolled telemetry dump.

---

## No interactive requirements

Tests must not ask for:

- user input;
- confirmation;
- terminal dimensions;
- GUI window interaction;
- external files not in repo/tmp path.

---

## Test IDs

Parametrized tests use readable IDs.

Example output:

```text
test_fault_scenario_contract[altimeter_freeze]
```

not:

```text
test_fault_scenario_contract[case3]
```

---

## Temporary artifact visibility

On a failing artifact test, pytest's `tmp_path` is available in traceback.

Do not copy temporary outputs to permanent `runs/` automatically.

---

# 4. Test Data and Fixture Requirements

## Entities commonly built

```text
VehicleState
VehicleParameters
EnvironmentConfig
SensorConfig
MeasurementSnapshot
PIDConfig
ControlCommand
ActuatorState
MissionContext
FaultDefinition
TelemetryFrame
CompletedTelemetry
ResolvedScenarioConfig
ValidationResult
```

---

## Fixture principles

- valid by default;
- immutable where possible;
- explicit overrides;
- no hidden randomness;
- no shared mutable state;
- production types, not dictionary imitations where avoidable.

---

## Scenario paths

Central helper:

```python
SCENARIOS_ROOT = PROJECT_ROOT / "scenarios"
```

Do not repeat fragile relative strings across tests.

---

## Seed constants

Use semantically named constants:

```python
DEFAULT_TEST_SEED = 42
ALTERNATE_TEST_SEED = 43
```

A test may choose another explicit value when meaningful.

---

## Tolerance constants

Centralize only shared, truly common tolerances.

Examples:

```text
STATE_ABS_TOL
ANGLE_ABS_TOL
TIME_ABS_TOL
```

Do not force all numerical tests to one tolerance.

Feature 13 defines numerical-reference tolerances.

---

# 5. Logic Requirements

## Rule 1 — Plain pytest is the primary test runner

---

## Rule 2 — Test the production application boundary

Scenario tests use `run_scenario`.

---

## Rule 3 — No test-only simulation implementation

---

## Rule 4 — Unit tests isolate one behavior

---

## Rule 5 — Integration tests prove boundaries/order

---

## Rule 6 — Scenario tests prove configured outcomes

---

## Rule 7 — Reproducibility tests repeat real runs

---

## Rule 8 — Expected failure can be a passing scenario contract

---

## Rule 9 — Simulator errors never count as expected scenario success

---

## Rule 10 — Exact equality is restricted to exact contracts

---

## Rule 11 — Arbitrary trajectories use tolerances/invariants/outcomes

---

## Rule 12 — Every random source is injected/seeded

---

## Rule 13 — Tests do not depend on global RNG state

---

## Rule 14 — Tests do not depend on wall-clock timing

---

## Rule 15 — Tests never use sleep for simulation behavior

---

## Rule 16 — Filesystem writes use tmp_path

---

## Rule 17 — Tests do not write repository runs by default

---

## Rule 18 — Plot tests use headless backend

---

## Rule 19 — Plot tests do not use pixel equality

---

## Rule 20 — Unexpected warnings fail

---

## Rule 21 — Unknown markers/config fail

---

## Rule 22 — Xfail is strict and exceptional

---

## Rule 23 — Core MVP scenario tests are not skipped

---

## Rule 24 — Fixture state does not leak

---

## Rule 25 — Every run builds fresh components

---

## Rule 26 — Architecture boundaries have explicit tests

---

## Rule 27 — Controller truth access is forbidden

---

## Rule 28 — Scenario-name branching is forbidden

---

## Rule 29 — Faults must change real behavior

---

## Rule 30 — Telemetry/event tick alignment is tested

---

## Rule 31 — Validation uses truth and completed data

---

## Rule 32 — Config errors occur before tick zero

---

## Rule 33 — Validation failure remains a result

---

## Rule 34 — Controlled abort remains a result

---

## Rule 35 — SimulationError remains an exception

---

## Rule 36 — Artifact failure remains distinct

---

## Rule 37 — Every real bug receives a regression test

---

## Rule 38 — Tests should survive internal refactoring

---

## Rule 39 — Avoid testing private attributes unless state ownership itself is the contract

---

## Rule 40 — Avoid mocks at the behavior being proven

---

## Rule 41 — Test builders do not duplicate production formulas

---

## Rule 42 — Test names describe behavior

---

## Rule 43 — Parametrized IDs are readable

---

## Rule 44 — No hard coverage vanity target

---

## Rule 45 — No hard runtime gate before measurement

---

## Rule 46 — No network/database/hardware dependency

---

## Rule 47 — Same lockfile/developer environment runs full suite

---

## Rule 48 — Full suite is one documented command

---

## Rule 49 — Ruff/Pyright complement, not replace, tests

---

## Rule 50 — Test suite itself is reviewer-readable

---

# 6. Acceptance Criteria

## AC-01 — Pytest collects the suite from tests/

**Given** a clean development environment  
**When** `uv run pytest --collect-only` executes  
**Then** tests are discovered under the documented directory structure without collection errors.

---

## AC-02 — Full suite runs with one command

**Given** dependencies installed through the documented uv workflow  
**When** `uv run pytest` executes  
**Then** unit, integration, scenario, architecture, and numerical test directories are included.

---

## AC-03 — Focused unit command works

**Given** the repository  
**When** `uv run pytest tests/unit` executes  
**Then** only focused unit tests run successfully.

---

## AC-04 — Focused scenario command works

**Given** curated scenarios  
**When** `uv run pytest tests/scenarios` executes  
**Then** complete scenario regressions run through the production runner.

---

## AC-05 — Numerical command works

**Given** dev dependencies including SciPy  
**When** `uv run pytest tests/numerical` executes  
**Then** Feature 13 numerical-reference tests run.

---

## AC-06 — Strict pytest configuration is enabled

**Given** pytest config  
**When** an unknown marker/config key is introduced  
**Then** the suite fails rather than silently ignoring it.

---

## AC-07 — Unexpected warnings fail tests

**Given** production/test code emits an unfiltered warning  
**When** pytest runs  
**Then** the affected test fails.

---

## AC-08 — Tests require no user input

**Given** full suite  
**When** run non-interactively  
**Then** no prompt blocks execution.

---

## AC-09 — Tests require no display server

**Given** a headless environment  
**When** plot tests run  
**Then** Agg/noninteractive generation succeeds.

---

## AC-10 — Tests require no network

**Given** network unavailable after dependencies are installed  
**When** suite runs  
**Then** no test attempts external access.

---

## AC-11 — Tests require no database or hardware

**Given** clean computer-only environment  
**When** suite runs  
**Then** no service/device dependency exists.

---

## AC-12 — Stateful fixtures are fresh per test

**Given** two tests using controller/sensor/engine fixtures  
**When** they run in either order  
**Then** mutable state from one cannot affect the other.

---

## AC-13 — Test order does not change results

**Given** tests executed in a different collection order  
**When** suite runs  
**Then** deterministic results remain unchanged.

---

## AC-14 — Unit tests cover Feature 01 dynamics

**Given** unit suite  
**When** inspected/executed  
**Then** zero thrust, thrust direction, gravity, torque, fuel/dry-mass, invalid input, and determinism behaviors are protected.

---

## AC-15 — Unit tests cover Feature 02 engine basics

**Given** unit suite  
**When** executed  
**Then** tick/time, fixed input, terminal/max-time, ordering hooks, and invariant failure are protected.

---

## AC-16 — Unit tests cover Feature 03 sensors

**Given** unit suite  
**When** executed  
**Then** cadence, noise, bias, delay, stale, freeze, release, and RNG independence are protected.

---

## AC-17 — Unit tests cover Feature 04 controllers

**Given** unit suite  
**When** executed  
**Then** PID terms, limits, anti-windup, cadence, mode reset, invalid input, and deterministic state are protected.

---

## AC-18 — Unit tests cover Feature 05 actuators

**Given** unit suite  
**When** executed  
**Then** saturation, lag, rate, degradation, atomic update, and deterministic behavior are protected.

---

## AC-19 — Unit tests cover every legal mission transition

**Given** state-machine suite  
**When** executed  
**Then** every legal Feature 06 transition has at least one behavior test.

---

## AC-20 — Unit tests cover selected illegal mission transitions

**Given** illegal transition attempts  
**When** tested  
**Then** they fail loudly as specified.

---

## AC-21 — Unit tests cover Feature 07 fault lifecycle/composition

**Given** fault-manager suite  
**When** executed  
**Then** exact ticks, events, overlapping effects, no-op faults, duplicate/skipped ticks, and lifecycle state are protected.

---

## AC-22 — Unit tests cover Feature 08 config/runner helpers

**Given** configuration suite  
**When** executed  
**Then** strict TOML keys/types, resolution, cross-field validation, digest, RNG, discovery, and fresh runtime behavior are protected.

---

## AC-23 — Unit tests cover Feature 09 telemetry/artifacts

**Given** telemetry suite  
**When** executed  
**Then** frames/events/schema/serialization/staging/collision/diagnostics are protected.

---

## AC-24 — Unit tests cover Feature 10 validation

**Given** validation suite  
**When** executed  
**Then** truth metrics, limits, transition history, fault contract, outcome matching, and expected failure semantics are protected.

---

## AC-25 — Unit tests cover Feature 11 plotting structure

**Given** plotting suite  
**When** executed  
**Then** PlotData, six axes, series, state/fault markers, annotations, PNG output, and resource cleanup are protected.

---

## AC-26 — Engine-order integration test exists

**Given** instrumented subsystem interfaces  
**When** one tick executes  
**Then** exact fault/sensor/mission/controller/actuator/integrator/invariant/telemetry order is asserted.

---

## AC-27 — Fault activates before same-tick sensor sampling

**Given** a sensor fault activation at tick t  
**When** integration test runs  
**Then** sensor behavior at tick t reflects the fault.

---

## AC-28 — Mission transition affects same-tick controller profile

**Given** transition at tick t  
**When** integration test runs  
**Then** controller at tick t consumes the newly committed state.

---

## AC-29 — Actuator updates once per engine tick

**Given** one tick with RK4 stages  
**When** integration test instruments actuator  
**Then** exactly one update occurs.

---

## AC-30 — Applied actuator state is constant through RK4 stages

**Given** one integration tick  
**When** derivative calls are observed  
**Then** all four stages receive the same applied actuation.

---

## AC-31 — Dynamics uses actual rather than requested actuation

**Given** lagged actuator differs from command  
**When** integration test advances state  
**Then** resulting derivative/trajectory corresponds to actual state.

---

## AC-32 — Controller receives measurements rather than truth

**Given** controller integration  
**When** public call occurs  
**Then** no VehicleState argument is passed or required.

---

## AC-33 — Truth-boundary architecture test passes

**Given** production control modules  
**When** imports/signatures are inspected  
**Then** forbidden VehicleState dependency is absent.

---

## AC-34 — Core modules contain no bundled scenario-ID branch

**Given** production source  
**When** architecture scan runs  
**Then** bundled scenario identifiers are absent from forbidden core modules.

---

## AC-35 — Dynamics does not import CLI/plot serialization

**Given** production import graph  
**When** architecture tests run  
**Then** pure dynamics remains independent.

---

## AC-36 — Plotting does not import live engine state

**Given** plotting module  
**When** architecture tests run  
**Then** it consumes completed data types rather than SimulationEngine.

---

## AC-37 — Nominal scenario runs through production application service

**Given** nominal TOML  
**When** scenario test executes  
**Then** `load_scenario` and `run_scenario`/file wrapper are used.

---

## AC-38 — Nominal scenario meets documented contract

**Given** tuned nominal scenario  
**When** scenario test runs  
**Then** ValidationResult reports actual PASS and scenario_passed true.

---

## AC-39 — Altimeter-freeze scenario matches its configured expected outcome

**Given** curated TOML  
**When** scenario test runs  
**Then** configured freeze activates and scenario_passed is true.

---

## AC-40 — Velocity-bias scenario matches expected outcome

**Given** curated TOML  
**When** scenario test runs  
**Then** configured bias activates and scenario_passed is true.

---

## AC-41 — Sensor-delay scenario matches expected outcome

**Given** curated TOML  
**When** scenario test runs  
**Then** configured delay activates and scenario_passed is true.

---

## AC-42 — Degraded-actuator scenario matches expected outcome

**Given** curated TOML  
**When** scenario test runs  
**Then** configured degradation activates and scenario_passed is true.

---

## AC-43 — Scenario tests do not infer outcome from filename

**Given** scenario test implementation  
**When** inspected  
**Then** expected outcome comes from resolved configuration or explicit parametrized project contract, not string heuristics.

---

## AC-44 — Scenario tests do not duplicate validator formulas

**Given** scenario test implementation  
**When** inspected  
**Then** tests assert structured ValidationResult rather than reimplementing all landing checks.

---

## AC-45 — Expected controlled abort is a passing regression

**Given** a scenario configured for controlled abort  
**When** actual controlled abort occurs with fault/trace checks passing  
**Then** pytest passes.

---

## AC-46 — Expected validation failure is a passing regression

**Given** a scenario configured for validation failure  
**When** actual validation failure occurs as expected  
**Then** pytest passes.

---

## AC-47 — Unexpected validation failure fails regression

**Given** expected PASS but actual validation failure  
**When** scenario test runs  
**Then** assertion fails with actionable details.

---

## AC-48 — Configured fault missing activation fails regression

**Given** fault scenario whose mission ends before fault activates  
**When** scenario test runs  
**Then** scenario_passed is false and test fails.

---

## AC-49 — Same config/seed reproduces mission result

**Given** identical resolved scenario run twice  
**When** reproducibility test compares results  
**Then** final outcome/state/event/fault/metric contracts match.

---

## AC-50 — Same seed reproduces sensor sequence

**Given** same sensor config and seed  
**When** samples are generated  
**Then** sequences match.

---

## AC-51 — Dedicated sensor streams are independent

**Given** canonical stream construction  
**When** unrelated sensor enablement/order changes under supported topology semantics  
**Then** target sensor's assigned stream sequence remains as designed.

---

## AC-52 — Different seed changes stochastic sequence

**Given** otherwise identical noisy sensor run  
**When** seed changes  
**Then** at least one representative measurement value differs.

---

## AC-53 — Different seed does not change deterministic fault ticks

**Given** time-triggered faults  
**When** seed differs  
**Then** activation/deactivation ticks remain the same.

---

## AC-54 — Deterministic artifact files reproduce

**Given** identical completed run written to separate temp roots  
**When** files compare  
**Then** telemetry.csv, events.json, and resolved_config.json are byte-identical.

---

## AC-55 — Reproducibility tests ignore wall-clock artifact paths

**Given** two runs at different times  
**When** compared  
**Then** timestamped directory names/summary UTC fields are excluded from mission reproducibility assertions.

---

## AC-56 — Exact equality is not used for arbitrary nonlinear trajectories

**Given** scenario/numerical assertions  
**When** suite is reviewed  
**Then** full floating trajectories use tolerances/invariants/outcomes rather than arbitrary exact decimal lists.

---

## AC-57 — Boundary values use explicit tolerances

**Given** landing/numeric boundary tests  
**When** assertions run  
**Then** documented tolerance is visible in test/helper.

---

## AC-58 — Unit tests do not rely on sleeps

**Given** test source  
**When** inspected  
**Then** simulation timing uses ticks/buffers, not `time.sleep`.

---

## AC-59 — Filesystem tests use tmp_path

**Given** tests writing artifacts/configs/plots  
**When** inspected/executed  
**Then** writes are under pytest temporary paths.

---

## AC-60 — Full test suite does not pollute repository runs/

**Given** clean repository state  
**When** `uv run pytest` completes  
**Then** no unrequested run bundle appears under production `runs/`.

---

## AC-61 — ConfigError test proves failure before tick zero

**Given** invalid scenario  
**When** runner is instrumented  
**Then** engine/sensor RNG/fault manager are not started.

---

## AC-62 — ConfigError produces no artifact bundle

**Given** invalid config and artifact root  
**When** run is attempted  
**Then** no normal/diagnostic run directory exists.

---

## AC-63 — SimulationError diagnostic path is tested

**Given** injected engine invariant failure  
**When** persisted run is attempted  
**Then** error frame/event/diagnostic files are written where possible and original error remains raised.

---

## AC-64 — Validation failure writes complete artifacts

**Given** completed run failing mission limits  
**When** persistence enabled  
**Then** data/summary/plot artifact contract is preserved.

---

## AC-65 — Controlled abort writes complete artifacts

**Given** completed ABORT run  
**When** persistence enabled  
**Then** full artifact bundle exists.

---

## AC-66 — Artifact write failure publishes no incomplete final directory

**Given** injected serialization/rename failure  
**When** writer runs  
**Then** final directory is absent and ArtifactError is raised.

---

## AC-67 — Plot tests never call show

**Given** monkeypatched `show` that raises  
**When** all plot tests run  
**Then** no call occurs.

---

## AC-68 — Plot tests avoid pixel equality

**Given** plotting test source  
**When** reviewed  
**Then** assertions use axes/data/markers/file properties instead of raster hashes.

---

## AC-69 — Plot writer closes figures

**Given** repeated PNG generation  
**When** test runs  
**Then** open-figure/resource count does not grow unbounded.

---

## AC-70 — Unexpected warnings fail

**Given** code emits a new numerical/deprecation/resource warning  
**When** suite runs  
**Then** a test fails until the issue/filter is addressed.

---

## AC-71 — Regression tests are added for confirmed bugs

**Given** a production bug is fixed  
**When** the fix is merged  
**Then** a deterministic test reproducing the prior failure is included unless technically impossible and documented.

---

## AC-72 — Tests do not depend on private attribute names unnecessarily

**Given** refactor preserving behavior  
**When** test suite runs  
**Then** unrelated tests do not fail solely due to renamed private fields.

---

## AC-73 — Mocks do not replace the system under test

**Given** scenario/integration suites  
**When** reviewed  
**Then** the key subsystem behavior being claimed is real, not mocked away.

---

## AC-74 — Full suite can run with committed lockfile environment

**Given** clean clone and `uv sync --all-groups --locked`  
**When** quality commands run  
**Then** dependency resolution is reproducible.

---

## AC-75 — Ruff check is part of documented quality gate

**Given** local developer instructions  
**When** followed  
**Then** `uv run ruff check .` succeeds.

---

## AC-76 — Ruff format check is part of documented quality gate

**Given** local developer instructions  
**When** followed  
**Then** `uv run ruff format --check .` succeeds.

---

## AC-77 — Pyright is part of documented quality gate

**Given** public typed boundaries  
**When** `uv run pyright` executes  
**Then** static type checking succeeds.

---

## AC-78 — No hard coverage percentage is required for MVP

**Given** test policy  
**When** reviewed  
**Then** quality is based on risk/behavior layers rather than an unsupported vanity threshold.

---

## AC-79 — No hard wall-clock suite threshold causes flaky failures

**Given** slower valid machine  
**When** suite runs  
**Then** correctness does not fail solely because elapsed wall time exceeded an arbitrary unmeasured bound.

---

## AC-80 — Portfolio completion gate is automated

**Given** a clean environment and finished core features  
**When** the full quality gate runs  
**Then** nominal + four fault scenarios, architecture boundaries, reproducibility, artifacts, headless plotting, validation, linting, formatting, and typing all succeed without manual intervention.

---

# 7. Test Plan by Directory

## `tests/unit`

Purpose:

- focused behavior;
- edge conditions;
- config validation;
- stateful component updates;
- serializers/plot structure.

Target characteristics:

- no full curated mission runs;
- mostly milliseconds;
- minimal filesystem;
- no network/display.

---

## `tests/numerical`

Purpose:

- independent correctness verification for custom RK4/dynamics.

Owned in detail by Feature 13.

Must use:

- analytical solutions;
- SciPy references;
- convergence/order checks;
- explicit tolerances.

---

## `tests/integration`

Purpose:

- real subsystem boundaries;
- tick ordering;
- short closed-loop runs;
- fault causal chains;
- telemetry/validation/plot/artifact handoffs.

Use short deterministic configs rather than full demo scenarios where possible.

---

## `tests/scenarios`

Purpose:

- complete portfolio contracts;
- same path as CLI;
- curated TOML;
- real validation result;
- reproducibility.

Avoid mocks of core system.

---

## `tests/architecture`

Purpose:

- protect non-negotiable boundaries only.

Use:

- public signatures;
- imports;
- small AST scans;
- forbidden scenario identifier scans.

Keep robust and explicit.

---

## Required smoke test

Recommended:

```python
def test_package_imports() -> None:
    import astraloop

    assert astraloop.__name__ == "astraloop"
```

Optional entry-point import test:

```python
from astraloop.scenarios.runner import run_scenario
```

Do not invoke CLI parsing as the only package smoke test.

---

## Scenario diagnostic helper

Example:

```python
def assert_scenario_passed(
    result: RunResult,
) -> None:
    validation = result.validation

    if validation.scenario_passed:
        return

    failures = "\n".join(
        f"  - {reason}"
        for reason in validation.failure_reasons
    )

    pytest.fail(
        (
            f"Scenario {result.scenario_id} failed\n"
            f"expected={validation.expected_outcome.value}\n"
            f"actual={validation.actual_outcome.value}\n"
            f"final_state={validation.metrics.final_mission_state.value}\n"
            f"final_time={validation.metrics.final_time:.6g}\n"
            f"failures:\n{failures}"
        ),
        pytrace=False,
    )
```

---

## Example unit test

```python
def test_first_order_actuator_does_not_overshoot() -> None:
    next_value = first_order_step(
        current=0.0,
        target=1.0,
        tau=0.2,
        dt=0.02,
    )

    assert 0.0 < next_value < 1.0
```

---

## Example integration test

```python
def test_dynamics_uses_applied_actuation() -> None:
    command = ControlCommand(
        throttle=1.0,
        attitude_command=0.0,
    )

    actuator = ActuatorModel(
        config=slow_actuator_config(),
    )

    update = actuator.update(
        command=command,
        dt=0.02,
    )

    assert update.state.throttle < command.throttle

    next_state = rk4_step(
        state=initial_state(),
        dt=0.02,
        derivative=lambda state: derivatives(
            state,
            actuation=update.state,
            ...
        ),
    )

    # Compare against a run incorrectly using requested full throttle.
    ...
```

---

## Example scenario test

```python
def test_nominal_scenario_contract() -> None:
    result = run_scenario_file(
        SCENARIOS_ROOT / "nominal.toml",
        artifact_root=None,
    )

    assert result.validation is not None
    assert result.validation.actual_outcome is ActualOutcome.PASS
    assert_scenario_passed(result)
```

---

## Example expected-abort test

```python
def test_altimeter_freeze_matches_expected_outcome() -> None:
    result = run_scenario_file(
        SCENARIOS_ROOT / "altimeter_freeze.toml",
        artifact_root=None,
    )

    assert result.validation.outcome_matched
    assert result.validation.scenario_passed
    assert "freeze_altimeter_01" in (
        result.validation.activated_fault_ids
    )
```

The actual outcome enum is read/checked according to the tuned scenario config.

---

## Example reproducibility test

```python
def test_nominal_is_reproducible() -> None:
    config = load_scenario(
        SCENARIOS_ROOT / "nominal.toml"
    )

    first = run_scenario(
        config,
        artifact_root=None,
    )
    second = run_scenario(
        config,
        artifact_root=None,
    )

    assert first.config_digest == second.config_digest
    assert (
        first.validation.actual_outcome
        is second.validation.actual_outcome
    )
    assert (
        first.validation.metrics.final_mission_state
        is second.validation.metrics.final_mission_state
    )
    assert (
        first.validation.metrics.final_time
        == pytest.approx(
            second.validation.metrics.final_time,
            abs=0.0,
            rel=0.0,
        )
    )
```

For deterministic tick-derived final time, exact equality may be appropriate.

---

# 8. Portfolio Value

## How this feature helps the project stand out

AstraLoop's automated test suite demonstrates more than "I used pytest."

The strong story is:

> "I tested the system from pure state equations through complete deterministic fault missions. I enforced that the controller cannot import truth state, verified exact hybrid tick ordering, checked expected controlled failures, and preserved regression tests for real bugs."

This is highly aligned with:

- software validation;
- simulation engineering;
- hardware-adjacent testing;
- systems software.

---

## What to mention in README

Recommended wording:

> **Layered automated testing:** AstraLoop uses `pytest` across unit, integration, numerical-reference, architecture-contract, and complete scenario regression tests. The nominal mission and each fault scenario execute through the same `run_scenario(...)` application service used by the CLI.

Useful bullets:

- deterministic seeds;
- truth-access architecture test;
- exact fault/tick ordering;
- expected failure scenarios;
- artifact/error tests;
- headless plotting;
- SciPy numerical reference;
- one-command quality gate.

Do not publish a test count until measured from the finished suite.

---

## What to mention in interviews

### How did you decide what belongs in a unit vs integration test?

> "A unit test proves one component's contract, such as sensor delay or PID saturation. Integration tests prove timing and subsystem boundaries, such as fault-before-sensor ordering. Scenario tests prove complete configured mission outcomes."

### How do you test a nonlinear simulation without brittle snapshots?

> "I use exact assertions for ticks, states and events, tolerances for known numerical values, invariants/ranges for physical behavior, independent numerical references, and mission-level validation outcomes instead of hard-coding every trajectory sample."

### How did you prevent flaky randomness?

> "All stochastic components receive dedicated generators derived from an explicit scenario seed. Tests compare same-seed sequences and verify stream independence."

### How do you test expected failures?

> "Actual mission outcome is separate from scenario regression success. A controlled abort or validation failure can pass if it was expected, the configured fault activated, and the transition trace stayed valid."

### How do you protect architecture?

> "I have narrow architecture-contract tests for critical rules: the controller cannot import `VehicleState`, dynamics does not depend on CLI/plotting, and bundled scenario IDs do not appear in core behavior code."

### Why not use exact equality on the full trajectory?

> "It would be brittle and obscure the real contract. I use numerical reference tests for the integrator, then scenario assertions on invariants, transitions, objective metrics and expected outcome."

### What happens when you find a bug?

> "I first create the smallest deterministic failing test, then fix it and keep the test as a regression. Telemetry usually helps identify the exact tick and subsystem boundary."

### Why no coverage percentage?

> "Coverage can be useful, but a percentage is not the goal. The suite is organized around risk: numerical behavior, timing, faults, state transitions, architecture boundaries, complete scenarios and failure paths."

---

# 9. Implementation Notes for Codex

## Likely files/folders

```text
tests/
├── conftest.py
├── helpers/
├── unit/
├── numerical/
├── integration/
├── scenarios/
└── architecture/
```

`pyproject.toml` contains pytest configuration.

Optional portfolio CI:

```text
.github/workflows/quality.yml
```

---

## Suggested responsibilities

### `tests/conftest.py`

Own only broadly useful fixtures.

Do not become a massive hidden setup script.

---

### `tests/helpers/builders.py`

Own valid test record/config builders.

---

### `tests/helpers/assertions.py`

Own high-value diagnostic assertion helpers.

---

### `tests/helpers/fakes.py`

Own small boundary fakes/spies.

No production code imports test helpers.

---

## Build order

### Step 1 — Configure strict pytest

Collection, warnings, xfail.

### Step 2 — Add smoke/import test

### Step 3 — Add Feature 01–05 core unit tests

### Step 4 — Add Feature 06 transition tests

### Step 5 — Add engine-order integration test

### Step 6 — Add Feature 07 fault tests

### Step 7 — Add Feature 08 config/runner tests

### Step 8 — Add Feature 09/10 artifact-validation tests

### Step 9 — Add Feature 11 headless plot tests

### Step 10 — Add nominal scenario regression

### Step 11 — Add four fault regressions

### Step 12 — Add reproducibility

### Step 13 — Add architecture-contract tests

### Step 14 — Add Feature 13 numerical suite

### Step 15 — Add minimal CI

---

## Risks

### Risk 1 — Many tiny tests, no complete mission proof

**Mitigation:** required scenario suite.

---

### Risk 2 — Only full missions, poor diagnosis

**Mitigation:** strong unit/integration layers.

---

### Risk 3 — Brittle floating-point snapshots

**Mitigation:** tolerances/invariants/numerical references.

---

### Risk 4 — Random test flakiness

**Mitigation:** explicit dedicated seeds.

---

### Risk 5 — Test-state leakage

**Mitigation:** fresh function-scoped components.

---

### Risk 6 — Tests use different path from CLI

**Mitigation:** same `run_scenario`.

---

### Risk 7 — Fault tests only check event label

**Mitigation:** integration tests prove subsystem output changed.

---

### Risk 8 — Expected failures make suite red

**Mitigation:** actual outcome vs scenario success.

---

### Risk 9 — Scenario never activates intended fault but passes coincidentally

**Mitigation:** configured-fault activation contract.

---

### Risk 10 — Plot tests depend on screen/pixels

**Mitigation:** Agg and structural tests.

---

### Risk 11 — Files pollute repository

**Mitigation:** tmp_path/artifact_root None.

---

### Risk 12 — Mocks hide behavior

**Mitigation:** mock only external failure boundaries.

---

### Risk 13 — Architecture tests become brittle source checker

**Mitigation:** enforce only critical boundaries.

---

### Risk 14 — Suite becomes slow through repeated full scenarios

**Mitigation:** short unit/integration configs, one parametrized curated scenario pass, no Monte Carlo.

---

### Risk 15 — Green suite with warnings/deprecations

**Mitigation:** warnings as errors.

---

## What not to change

While implementing Feature 12, Codex should **not**:

- weaken production requirements to satisfy tests;
- change expected scenario outcomes without documenting/tuning evidence;
- create a test-only simulation engine;
- add sleep/network/hardware dependencies;
- add Selenium/browser tests;
- add screenshot pixel snapshots;
- add random unseeded inputs;
- add giant committed telemetry golden files;
- add a database for test results;
- add coverage tooling solely for a number;
- add Hypothesis before a demonstrated need;
- add Tox/Nox/pre-commit solely as workflow decoration;
- add pytest-xdist as a requirement;
- skip failing core scenario tests;
- xfail unfinished MVP behavior indefinitely;
- assert arbitrary floating trajectories exactly;
- test private implementation trivia broadly;
- mock away the behavior a test claims to prove;
- let tests write production `runs/`;
- accept simulator errors as expected scenario success.

---

# Feature-Specific Definition of Done

Feature 12 is complete when:

- [ ] Strict pytest config exists.
- [ ] Full suite runs with `uv run pytest`.
- [ ] Unit/integration/scenario/numerical commands work.
- [ ] Test helpers/builders are small and typed.
- [ ] Fixtures are fresh and isolated.
- [ ] Unexpected warnings fail.
- [ ] Headless backend is configured.
- [ ] No test uses sleep/network/database/hardware.
- [ ] Feature 01–11 core unit behaviors are covered.
- [ ] Engine tick ordering is integration-tested.
- [ ] Controller truth boundary is tested.
- [ ] Scenario-name branching boundary is tested.
- [ ] Faults are proven to change real subsystem behavior.
- [ ] Telemetry/event tick alignment is tested.
- [ ] Validation truth/oracle semantics are tested.
- [ ] Nominal end-to-end scenario passes.
- [ ] Four fault scenario contracts pass.
- [ ] Expected controlled abort/failure scenarios can pass.
- [ ] Configured fault activation is asserted.
- [ ] Same seed/config reproducibility is tested.
- [ ] Different seed stochastic difference is tested.
- [ ] Deterministic artifact contents are tested.
- [ ] ConfigError failure path is tested.
- [ ] SimulationError diagnostic path is tested.
- [ ] Validation failure/abort artifact paths are tested.
- [ ] ArtifactError/staging failure is tested.
- [ ] Plotting tests use no GUI/pixel equality.
- [ ] Regression-test policy is followed for real bugs.
- [ ] Tests do not pollute repository runs/.
- [ ] Arbitrary trajectory tests use tolerance/invariants.
- [ ] Scenario tests use production runner.
- [ ] No core test is permanently xfailed/skipped in portfolio-ready state.
- [ ] Ruff format/check and Pyright are documented alongside pytest.
- [ ] Optional minimal CI passes using committed lockfile.
- [ ] README can truthfully describe the test layers.
- [ ] Final suite is understandable to a technical reviewer.

---

# Open Questions

1. **[Open Question] Which fault scenarios should produce PASS, CONTROLLED_ABORT, or VALIDATION_FAIL?**  
   Freeze final expectations only after tuning and preserve them in TOML.

2. **[Open Question] Should the full suite use pytest markers in addition to directories?**  
   Recommended only for scenario/numerical/slow filtering where useful.

3. **[Open Question] Should code coverage tooling be added after MVP?**  
   Only if it helps identify real gaps; no vanity threshold.

4. **[Open Question] What measured full-suite duration is acceptable on an ordinary laptop?**  
   Measure after implementation. Avoid an arbitrary flaky gate.

5. **[Open Question] Should GitHub Actions be required for Feature 12 done or final portfolio polish?**  
   Recommended final repository includes it, but local deterministic quality gate is primary.

6. **[Open Question] How much AST/source inspection should architecture tests use?**  
   Keep only truth-boundary/import/scenario-ID rules that cannot be proven clearly through runtime behavior alone.

7. **[Open Question] Should different sensor enablement preserve named RNG stream sequences exactly?**  
   This depends on final SeedSequence/name mapping. Freeze the contract in Feature 08 tests.

8. **[Open Question] Should scenario tests persist artifacts or use in-memory mode?**  
   Main scenario regression should use `artifact_root=None`; separate artifact integration tests use `tmp_path`.

9. **[Open Question] Should one full persisted scenario be included in the end-to-end suite?**  
   Recommended yes through `tmp_path`, not repository runs.

10. **[Open Question] Should expected-failure scenario tests assert a specific failed mission check?**  
    Useful when the scenario's purpose is stable; avoid overcoupling before tuning.

11. **[Open Question] Should `pytest-randomly` or another order-randomization plugin be added?**  
    Not needed initially. State isolation can be checked with targeted tests and occasional manual randomized order.

12. **[Open Question] Should tests enforce no Python global `random` use in production?**  
    A narrow source/import test may help, but avoid broad brittle scanning if injected NumPy RNG is already enforced at public boundaries.

13. **[Open Question] Should scenario regressions compare full telemetry arrays?**  
    Recommended no; use separate reproducibility/artifact tests and objective mission contracts.

14. **[Open Question] Which Feature 13 numerical tests belong in the default full suite versus a focused numerical command?**  
    All deterministic reasonably fast tests should remain in full pytest; no hidden optional correctness suite.

15. **[Open Question] Should quality commands be wrapped in one script?**  
    Four explicit `uv run` commands are clear. Add a script only when it improves actual workflow.

---

# Move On When

- [ ] One command proves the complete repository.
- [ ] Unit tests isolate core logic.
- [ ] Integration tests prove timing and boundaries.
- [ ] Scenario tests prove nominal and fault outcomes.
- [ ] Reproducibility is automated.
- [ ] Expected failures are modeled correctly.
- [ ] Fault activation/effects are real.
- [ ] Architecture rules are protected.
- [ ] Artifact/error paths are protected.
- [ ] Headless plots are protected.
- [ ] Numerical testing uses principled tolerances.
- [ ] Real bugs become permanent regression tests.
- [ ] Test failures are actionable.
- [ ] Test suite itself is a strong portfolio artifact.
- [ ] No unnecessary test frameworks, cloud systems, GUI tools, hardware, databases, or vanity metrics have been added.
- [ ] The project is ready for Feature 13 — Numerical Verification.
