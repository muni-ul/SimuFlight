# Feature 08 — Config-Driven Scenario Runner

> **Project:** AstraLoop — Python Software-in-the-Loop Flight Control & Validation System  
> **Feature:** Config-Driven Scenario Runner  
> **Document path:** `docs/features/08-config-driven-scenario-runner.md`  
> **Status:** Implementation specification  
> **Primary goal:** Load a complete local TOML scenario into a strict, typed, fully resolved configuration; construct fresh deterministic simulation subsystems; run the same application service for CLI demos and automated tests; and return a structured `RunResult` without embedding scenario-specific behavior in the engine.

---

## Scope Boundary

**[Confirmed]** AstraLoop is configuration-driven and uses local TOML scenario files parsed with the standard-library `tomllib`.

**[Confirmed]** The selected architecture defines the application boundary:

```python
def load_scenario(path: Path) -> ScenarioConfig:
    ...

def run_scenario(
    config: ScenarioConfig,
    *,
    artifact_root: Path | None = None,
) -> RunResult:
    ...
```

**[Confirmed]** Both the CLI and end-to-end tests must call the same `run_scenario(...)` service.

**[Confirmed]** A scenario should resolve typed configuration for:

```text
scenario identity
seed
dt
maximum simulation time
initial state
vehicle parameters
environment parameters
sensor parameters
controller parameters
actuator parameters
mission parameters
fault definitions
validation limits
expected outcome
```

**[Confirmed]** The MVP curated scenario set is approximately:

```text
nominal
altimeter_freeze
velocity_bias
sensor_delay
degraded_actuator
```

with optional:

```text
external_disturbance
```

only after the core five are stable.

**[Confirmed]** Runs must be deterministic for the same resolved configuration and seed.

**[Confirmed]** Invalid configuration must produce a `ConfigError` before normal simulation begins.

**[Decision]** Feature 08 owns the **configuration and application-orchestration boundary**.

It owns:

- scenario-file discovery;
- TOML file reading/parsing;
- raw key/type validation;
- strict unknown-key detection;
- typed scenario dataclasses;
- defaults;
- unit conversion;
- time-to-tick resolution;
- cross-field configuration validation;
- canonical resolved configuration;
- resolved-config digest;
- deterministic RNG stream construction;
- construction of fresh subsystem instances;
- wiring subsystem dependencies;
- invoking the Simulation Engine;
- invoking later telemetry and validation boundaries when available;
- returning one structured `RunResult`;
- scenario-level errors and tests;
- ensuring a new supported scenario can be added without editing the core engine.

It does **not** own the internal implementation of:

- numerical dynamics;
- RK4;
- sensors;
- controllers;
- actuators;
- mission transitions;
- fault lifecycle behavior;
- telemetry frame capture/serialization;
- mission validation calculations;
- diagnostic plotting;
- polished terminal rendering;
- CLI argument parsing;
- batch/campaign presentation;
- benchmark execution.

Feature 08 coordinates those components but does not absorb their domain logic.

---

# 1. Feature Overview

## Feature name

**Config-Driven Scenario Runner**

---

## One-sentence description

**[Decision]** Implement a strict TOML-to-runtime application service that resolves one complete AstraLoop scenario, validates all subsystem relationships before execution, constructs deterministic fresh components, runs the simulation, and returns a reusable structured result.

---

## Detailed description

AstraLoop should not require Python source edits to change:

- initial conditions;
- numerical timestep;
- sensor behavior;
- controller gains;
- actuator limits;
- mission thresholds;
- fault timing;
- validation limits;
- expected result.

Those choices belong in scenario configuration.

The complete flow is:

```text
Scenario TOML path
        |
        v
read local file
        |
        v
tomllib parse
        |
        v
raw schema validation
        |
        v
typed unresolved ScenarioConfig
        |
        v
defaults + units + tick resolution
        |
        v
cross-field validation
        |
        v
ResolvedScenarioConfig
        |
        +--> config digest
        |
        +--> dedicated RNG streams
        |
        +--> fresh subsystem construction
        |
        v
run_scenario(...)
        |
        v
Simulation Engine
        |
        v
completed runtime data
        |
        +--> Telemetry finalization (Feature 09)
        |
        +--> Validation (Feature 10)
        |
        v
RunResult
```

The scenario runner is the **imperative application shell** around the already-separated domain modules.

---

## Why it matters

A configuration-driven runner proves that AstraLoop is an engineering system rather than a set of hard-coded demonstrations.

Without it, fault scenarios might become:

```python
if scenario == "altimeter_freeze":
    freeze_sensor()
```

or separate Python scripts with duplicated setup.

With Feature 08:

```text
same loader
same resolver
same runner
same engine
same controller
same validation pathway
different typed scenario data
```

This is one of the project's strongest architecture signals.

---

## Scenario file philosophy

**[Decision]** Every bundled MVP scenario is represented by one readable TOML file under:

```text
scenarios/
```

Recommended files:

```text
scenarios/
├── nominal.toml
├── altimeter_freeze.toml
├── velocity_bias.toml
├── sensor_delay.toml
└── degraded_actuator.toml
```

Optional later:

```text
scenarios/external_disturbance.toml
```

---

## Self-contained configuration vs inheritance

The source materials identify scenario fields and mention possible vehicle/environment references, but do not define a configuration-inheritance mechanism.

**[Decision]** Use **self-contained scenario files for the MVP**.

Do not implement:

- `extends`;
- YAML-style anchors;
- remote includes;
- multi-level base scenarios;
- arbitrary merge rules;
- environment-variable substitution.

### Why

There are only approximately five core scenarios.

Some duplication is preferable to:

- hidden values;
- confusing merge precedence;
- fragile relative-path resolution;
- hard-to-inspect final configuration;
- additional loader complexity.

Every scenario should be understandable by opening one file.

### Later option

**[Open Question]** If duplication becomes a real maintenance problem, add one deliberately small local-reference mechanism after the core scenarios are stable.

Any future reference mechanism must still produce and save a complete resolved configuration.

---

## TOML parser

**[Confirmed]** Use:

```python
tomllib
```

from the Python standard library.

Do not add:

- Pydantic;
- YAML parser;
- custom config language;
- remote config service;

for the MVP.

---

## Configuration phases

Feature 08 should explicitly separate four phases.

### Phase 1 — File parsing

Input:

```text
Path
```

Output:

```text
dict[str, object]
```

Responsibilities:

- confirm file exists;
- confirm file is a regular readable `.toml` file;
- parse with `tomllib`;
- translate TOML syntax errors into `ConfigError` with file context.

---

### Phase 2 — Raw schema validation

Input:

```text
raw mapping
```

Output:

```text
typed raw/unresolved dataclasses
```

Responsibilities:

- required keys;
- allowed keys;
- primitive types;
- table/list structure;
- enums/identifiers;
- local value constraints that do not require other fields.

Examples:

- `seed` is integer;
- `dt` is number;
- sensor table exists;
- fault target is a string that maps to a known enum;
- `noise_std >= 0`.

---

### Phase 3 — Resolution

Input:

```text
typed raw config
```

Output:

```text
ResolvedScenarioConfig
```

Responsibilities:

- apply defaults;
- convert degrees to radians;
- convert seconds to integer ticks;
- derive maximum ticks;
- derive controller/sensor update cadences;
- derive fault activation/deactivation ticks;
- normalize enums;
- freeze lists as tuples;
- derive dedicated RNG stream seeds/keys;
- produce canonical values.

---

### Phase 4 — Cross-field validation

Input:

```text
ResolvedScenarioConfig
```

Output:

```text
validated ResolvedScenarioConfig
```

Responsibilities:

- relationships between fields/subsystems;
- no-op fault detection;
- timing compatibility;
- mission threshold consistency;
- initial mass vs dry mass;
- active sensor/controller requirements;
- expected-outcome schema compatibility;
- maximum-time/fault timing compatibility.

No runtime component should be constructed until all four phases succeed.

---

## Raw vs resolved configuration

### Raw scenario configuration

Represents what the user wrote.

It may contain:

```text
degrees
seconds
omitted optional defaults
human-readable enum strings
```

Example:

```toml
theta_deg = 5.0
sample_interval_s = 0.10
activation_time = 20.0
```

---

### Resolved scenario configuration

Represents exactly what the runtime uses.

It should contain:

```text
radians
integer tick periods
integer activation ticks
all defaults expanded
typed enums
immutable collections
validated subsystem configs
```

Example:

```text
theta_rad = 0.087266...
sample_every_ticks = 5
activation_tick = 1000
```

**[Decision]** The Simulation Engine and subsystems consume only the resolved configuration.

They must not repeatedly interpret TOML units or defaults.

---

## Schema version

**[Decision]** Include:

```toml
schema_version = 1
```

as a required top-level field.

### Why

- clear future migration boundary;
- prevents silently interpreting an older/newer schema;
- easy to validate;
- nearly zero complexity.

Unsupported versions produce `ConfigError`.

---

## Recommended scenario identity fields

```toml
schema_version = 1
id = "nominal"
description = "Nominal autonomous flight and landing"
seed = 42
dt = 0.02
max_time = 60.0
```

### `id`

Requirements:

- non-empty;
- stable;
- lowercase slug;
- characters:

```text
a-z
0-9
underscore
hyphen
```

Recommended regex:

```text
^[a-z0-9][a-z0-9_-]*$
```

### `description`

Requirements:

- non-empty after trimming;
- concise human-readable explanation;
- no runtime behavior attached to wording.

### `seed`

Requirements:

- integer;
- nonnegative;
- within a documented supported integer range.

Recommended:

```text
0 <= seed <= 2**64 - 1
```

### `dt`

Unit:

```text
seconds
```

Requirements inherited from Feature 02:

- finite;
- `> 0`;
- fixed for run.

### `max_time`

Unit:

```text
seconds
```

Requirements:

- finite;
- `> 0`;
- aligned to exact integer tick semantics.

---

## File name and scenario ID

**[Decision]** For bundled scenarios under the repository `scenarios/` directory:

```text
file stem == scenario id
```

Example:

```text
scenarios/velocity_bias.toml
id = "velocity_bias"
```

### Why

- avoids reviewer confusion;
- makes CLI output predictable;
- prevents two names for one scenario;
- simplifies discovery.

For programmatically created test configs, no filename relationship exists.

---

## Unknown-key policy

**[Decision]** Reject unknown keys at every schema level.

Example typo:

```toml
noise_stdd = 0.5
```

must not be silently ignored.

Expected error:

```text
ConfigError: scenarios/nominal.toml
[sensors.altimeter]: unknown key 'noise_stdd'; did you mean 'noise_std'?
```

Suggestion support is optional.

Strict rejection is required.

---

## Required top-level sections

Recommended complete schema:

```text
schema_version
id
description
seed
dt
max_time

initial_state
vehicle
environment
sensors
controller
actuators
mission
validation
faults[]
```

A zero-fault nominal scenario may omit `faults` or provide an empty list/table array.

**Decision:** Normalize omitted faults to:

```python
faults=()
```

---

## Recommended top-level TOML structure

```toml
schema_version = 1
id = "nominal"
description = "Nominal autonomous flight and landing"
seed = 42
dt = 0.02
max_time = 60.0

[initial_state]
...

[vehicle]
...

[environment]
...

[sensors.altimeter]
...

[sensors.vertical_velocity]
...

[sensors.horizontal_position]
...

[sensors.horizontal_velocity]
...

[sensors.attitude]
...

[sensors.gyro]
...

[controller]
...

[controller.throttle_pid]
...

[controller.attitude_pid]
...

[controller.profiles.PRELAUNCH]
...

[controller.profiles.ASCENT]
...

[actuators.throttle]
...

[actuators.gimbal]
...

[mission]
...

[validation]
...

[[faults]]
...
```

---

## Initial-state section

Recommended raw fields:

```toml
[initial_state]
x_m = 0.0
y_m = 0.0
vx_m_s = 0.0
vy_m_s = 0.0
theta_deg = 0.0
omega_deg_s = 0.0
mass_kg = 1200.0
```

**Decision]** Use explicit unit suffixes for new scenario fields even where earlier examples used shorter names.

The source examples are illustrative and do not lock the exact final field names.

Resolved state:

```text
x
y
vx
vy
theta [rad]
omega [rad/s]
mass
```

---

## Vehicle section

Fields should match Feature 01's final `VehicleParameters`.

Likely:

```toml
[vehicle]
dry_mass_kg = 900.0
max_thrust_n = 18000.0
max_mass_flow_rate_kg_s = 5.0
moment_of_inertia_kg_m2 = 4500.0
thrust_lever_arm_m = 2.0
```

Do not add parameters that the dynamics does not use.

---

## Environment section

Likely:

```toml
[environment]
gravity_m_s2 = 9.80665
ground_y_m = 0.0
```

Optional disturbance defaults should remain zero.

---

## Sensor section

Each required sensor table follows Feature 03.

Example:

```toml
[sensors.altimeter]
enabled = true
sample_interval_s = 0.10
noise_std = 0.50
bias = 0.0
delay_s = 0.00
```

Required sensor names:

```text
altimeter
vertical_velocity
horizontal_position
horizontal_velocity
attitude
gyro
```

**Decision]** Require all six tables in a complete scenario, even if a sensor is disabled.

### Why

- resolved config always has complete topology;
- no hidden defaults about which sensor exists;
- fault-target validation becomes straightforward.

---

## Controller section

Example structure:

```toml
[controller]
update_interval_s = 0.04

[controller.throttle_pid]
kp = 0.0
ki = 0.0
kd = 0.0
output_min = -0.5
output_max = 0.5
integral_min = -5.0
integral_max = 5.0

[controller.attitude_pid]
kp = 0.0
ki = 0.0
kd = 0.0
output_min_deg = -8.0
output_max_deg = 8.0
integral_min = -1.0
integral_max = 1.0
```

Profiles:

```toml
[controller.profiles.PRELAUNCH]
target_vertical_velocity_m_s = 0.0
target_pitch_deg = 0.0
base_throttle = 0.0
throttle_enabled = false
attitude_enabled = false
```

Repeat for required mission states.

**Decision]** Use mission-state table names matching enum names exactly or define one explicit case policy.

Recommended raw TOML names:

```text
PRELAUNCH
ASCENT
COAST
DESCENT
LANDING
LANDED
ABORT
```

---

## Actuator section

Example:

```toml
[actuators.throttle]
min = 0.0
max = 1.0
response_time_constant_s = 0.20

[actuators.gimbal]
max_angle_deg = 8.0
response_time_constant_s = 0.10
max_rate_deg_s = 30.0
```

Optional values should be explicit or resolved to clear `None`.

---

## Mission section

Example structure from Feature 06:

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

`prelaunch_hold_s` resolves to ticks.

Confirmation counts are already discrete integers.

---

## Fault list

Uses Feature 07's typed fault schema.

Example:

```toml
[[faults]]
id = "freeze_altimeter_01"
type = "sensor_freeze"
target = "altimeter"
activation_time = 20.0
```

The raw loader converts:

```text
activation_time seconds
```

into:

```text
activation_tick
```

during resolution.

Fault-specific unknown parameters must be rejected.

---

## Validation section

Feature 10 owns validation calculations.

Feature 08 owns loading and passing validation configuration.

Recommended:

```toml
[validation]
expected_outcome = "pass"
max_landing_vertical_speed_m_s = 2.0
max_horizontal_error_m = 5.0
max_pitch_error_deg = 5.0
require_valid_transitions = true
```

---

## Expected-outcome categories

The blueprint requires expected result categories and distinguishes:

```text
mission PASS
controlled ABORT
validation FAIL
simulator ERROR
```

**[Decision]** Supported expected scenario outcomes:

```text
pass
controlled_abort
validation_fail
```

Do not allow:

```text
simulator_error
```

as a normal expected scenario outcome.

### Why

A simulator/runtime error means the software failed internally.

It should not be accepted as a successful validation scenario.

Feature 10 will define the exact mapping between runtime data and these categories.

Feature 08 only validates and transports the enum.

---

## Nominal vs fault scenario semantics

**[Decision]** Do not branch runtime behavior based on scenario ID.

The file named `nominal.toml` is nominal because:

```text
faults = ()
```

and its configuration/expected outcome reflect nominal behavior.

The file named `altimeter_freeze.toml` is a freeze scenario because it contains a typed sensor-freeze fault.

No code should say:

```python
if config.id == "nominal":
```

to choose engine behavior.

---

## Curated scenario requirements

### `nominal.toml`

Must:

- have no active fault definitions;
- expect `pass`;
- use the complete real closed-loop stack.

### `altimeter_freeze.toml`

Must:

- contain at least one sensor-freeze fault targeting altimeter;
- document expected behavior;
- use the same underlying engine/controller architecture.

### `velocity_bias.toml`

Must:

- contain a nonzero velocity-sensor bias fault;
- preferably target vertical velocity unless project tuning chooses otherwise.

### `sensor_delay.toml`

Must:

- contain a meaningful sensor-delay fault;
- target an enabled sensor;
- change effective delay relative to nominal.

### `degraded_actuator.toml`

Must:

- contain a real actuator degradation;
- change effective actuator behavior;
- not mutate controller configuration merely to fake the fault.

---

## Scenario discovery

Recommended API:

```python
def discover_scenarios(
    root: Path,
) -> tuple[ScenarioDescriptor, ...]:
    ...
```

### Behavior

- inspect direct `.toml` files in the supplied directory;
- ignore non-TOML files;
- reject unreadable TOML scenario files when full loading is requested;
- return deterministic order, preferably by scenario ID;
- do not scan arbitrary user home directories;
- do not use network discovery.

### Recursive discovery

**[Decision]** Top-level discovery is sufficient for MVP.

Optional campaign subdirectories may use an explicit root supplied to discovery later.

Do not recursively crawl by default.

---

## Scenario descriptor

Useful for later `list-scenarios` CLI:

```python
@dataclass(frozen=True)
class ScenarioDescriptor:
    id: str
    description: str
    path: Path
    expected_outcome: ExpectedOutcome
    fault_count: int
```

For only five files, discovery may load/validate full configs rather than build a separate partial metadata parser.

**Decision:** Prefer correctness and simplicity over a metadata-only parser.

---

## Loader API

Recommended:

```python
def load_scenario(
    path: str | Path,
) -> ResolvedScenarioConfig:
    ...
```

The architecture examples name the output `ScenarioConfig`.

**Decision]** Either:

1. make `ScenarioConfig` mean fully resolved runtime config; or
2. explicitly use `RawScenarioConfig` and `ResolvedScenarioConfig`.

Recommended:

```text
RawScenarioConfig
ResolvedScenarioConfig
```

and public:

```python
load_scenario(...) -> ResolvedScenarioConfig
```

This avoids ambiguity.

---

## Config error context

Every `ConfigError` should include:

- scenario file path;
- section/key path;
- offending value where safe/useful;
- expected rule.

Example:

```text
ConfigError in scenarios/sensor_delay.toml
at faults[0].delay_s:
delay_s=0.07 is not aligned to dt=0.02.
```

---

## Deterministic RNG construction

**[Confirmed]** One scenario seed must derive dedicated RNGs for stochastic subsystems.

Feature 03 defines per-sensor RNG independence.

Feature 08 owns run setup.

Recommended:

```python
@dataclass(frozen=True)
class RngBundle:
    altimeter: np.random.Generator
    vertical_velocity: np.random.Generator
    horizontal_position: np.random.Generator
    horizontal_velocity: np.random.Generator
    attitude: np.random.Generator
    gyro: np.random.Generator
```

Optional disturbance RNG only when needed.

### Construction

Use:

```python
numpy.random.SeedSequence(config.seed)
```

and spawn child sequences in a canonical fixed order.

**Decision]** Never derive streams from Python's randomized `hash()`.

---

## Resolved RNG metadata

The actual NumPy generator object is runtime state and not serialized directly.

Resolved configuration should record enough deterministic metadata:

```text
scenario seed
RNG stream names
stream derivation version/order
```

Recommended:

```text
rng_scheme = "seedsequence-v1"
```

This protects future reproducibility if stream assignment changes.

---

## Config digest

The architecture suggests a short run-directory suffix derived from resolved configuration.

**[Decision]** Feature 08 computes a stable digest from a canonical serialization of `ResolvedScenarioConfig`.

Recommended:

```text
SHA-256
```

Store full digest in `RunResult`/resolved config metadata.

Use a short prefix for display/artifact directory suffix:

```text
first 8 or 12 hexadecimal characters
```

### Canonicalization requirements

The digest input must:

- exclude wall-clock run timestamp;
- exclude artifact directory;
- exclude mutable runtime state;
- use stable key ordering;
- use normalized enum strings;
- use normalized units;
- use deterministic float serialization;
- include seed;
- include faults;
- include expected outcome and validation config.

---

## What config digest means

Same digest implies:

```text
same resolved scenario configuration
```

It does **not** necessarily imply:

```text
same source code version
```

**[Open Question]** Feature 09 may include Git commit hash/package version in run metadata separately.

Do not mix source revision into the resolved scenario config unless deliberately defined.

---

## Scenario runtime construction

Recommended internal boundary:

```python
def build_runtime(
    config: ResolvedScenarioConfig,
) -> ScenarioRuntime:
    ...
```

Potential record:

```python
@dataclass
class ScenarioRuntime:
    engine: SimulationEngine
    sensors: SensorSuite
    controller: FlightController
    actuators: ActuatorModel
    mission: MissionStateMachine
    faults: FaultManager
    telemetry: TelemetryRecorder | None
```

### Important

`ScenarioRuntime` is stateful and must be newly constructed for every run.

It must never be cached globally.

---

## Fresh-run guarantee

**[Decision]** Calling:

```python
run_scenario(config)
run_scenario(config)
```

creates two independent sets of:

- sensor buffers;
- sensor RNG generators;
- PID state;
- actuator state;
- mission state;
- fault lifecycle state;
- telemetry storage;
- simulation tick/state.

No state can leak from the first run into the second.

---

## Application-service boundary

Required:

```python
def run_scenario(
    config: ResolvedScenarioConfig,
    *,
    artifact_root: Path | None = None,
) -> RunResult:
    ...
```

The function should:

1. accept only already validated/resolved configuration;
2. build fresh runtime objects;
3. initialize optional run/artifact coordination;
4. call the Simulation Engine;
5. collect engine/fault/mission output;
6. call validation when Feature 10 exists;
7. finalize artifacts when Feature 09 exists;
8. return structured `RunResult`.

---

## Convenience file boundary

Recommended:

```python
def run_scenario_file(
    path: str | Path,
    *,
    artifact_root: Path | None = None,
) -> RunResult:
    config = load_scenario(path)
    return run_scenario(
        config,
        artifact_root=artifact_root,
    )
```

The CLI may call this function.

Tests can call either:

- `load_scenario` + `run_scenario`;
- `run_scenario_file`.

---

## Artifact-root semantics

The source architecture includes:

```python
artifact_root: Path | None = None
```

**Decision]** Preserve this argument even before Feature 09 is fully implemented.

Final behavior:

- `None` means runner uses configured/default local `runs/` policy or disables persistence in test mode according to explicit final design;
- a path means Feature 09 writes an immutable run bundle below that root.

### Feature boundary

Feature 08 passes artifact context to telemetry/artifact services.

It does not implement CSV/JSON/PNG details.

---

## Testing without persistent artifacts

End-to-end tests should be able to run with:

```text
artifact persistence disabled
```

or:

```python
artifact_root=tmp_path
```

**Decision]** No test should write uncontrolled files into repository `runs/`.

---

## RunResult

Recommended final shape:

```python
@dataclass(frozen=True)
class RunResult:
    scenario_id: str
    seed: int
    config_digest: str

    engine_result: SimulationResult
    validation: ValidationResult | None

    artifact_dir: Path | None
```

Convenience properties may expose:

```text
final_state
final_time
expected_outcome
actual_outcome
outcome_matched
```

Feature 10 owns validation details.

---

## Errors vs results

### `ConfigError`

Raised before simulation begins.

Examples:

- malformed TOML;
- unknown key;
- wrong type;
- timing not aligned;
- no-op fault;
- incompatible subsystem config.

### `SimulationError`

Raised by engine/runtime invariant failure.

Runner should:

- preserve cause;
- allow Feature 09 to save diagnostic summary where possible;
- not relabel it as mission validation failure.

### Domain mission outcome

Returned through `RunResult`.

Examples:

- pass;
- controlled abort;
- validation failure.

These are not Python exceptions.

---

## Scenario runner orchestration sequence

Recommended final sequence:

```text
A. receive resolved config
B. create deterministic config digest
C. derive RNG streams
D. construct fresh sensors
E. construct controller
F. construct actuators
G. construct mission state machine
H. construct fault manager
I. construct optional telemetry recorder
J. construct simulation engine with explicit dependencies
K. run engine
L. finalize completed telemetry data
M. invoke validator
N. persist artifact bundle
O. return RunResult
```

The exact engine dependency constructor can vary, but ownership must remain explicit.

---

## Dependency construction

**[Decision]** Use ordinary constructors/factory functions.

Do not add:

- dependency injection framework;
- global service locator;
- singleton registry;
- plugin container.

The architecture is small enough for transparent Python code.

---

## Headless behavior

Runner must work without:

- terminal;
- browser;
- display server;
- network;
- database;
- cloud credentials;
- external hardware.

Matplotlib output later must use headless-compatible behavior through Feature 09/11.

---

## Batch/campaign behavior

The blueprint lists an optional command:

```bash
python -m astraloop campaign scenarios/regression/
```

**[Decision]** Full campaign execution is optional and is not required inside Feature 08's core implementation.

A later campaign service can simply:

```text
discover configs
for each:
    run_scenario(config)
aggregate results
```

Do not complicate the single-scenario runner with:

- concurrency;
- multiprocessing;
- distributed jobs;
- retries;
- queues.

---

## Why the runner should not print directly

`run_scenario(...)` is called by:

- CLI;
- tests;
- potentially future benchmark/campaign code.

**[Decision]** It returns data and uses standard logging where necessary.

Polished terminal rendering belongs to Feature 14/15.

Avoid unconditional:

```python
print(...)
```

inside core application service.

---

## Why the runner should not inspect scenario names

Bad:

```python
if config.id == "degraded_actuator":
    actuators.slow_down()
```

Good:

```text
config.faults contains ActuatorDegradationFault
FaultManager activates it
ActuatorModel consumes modifiers
```

The runner wires generic components only.

---

## Priority

**P0 — Core application boundary**

Feature 08 is required for:

- one-command demo;
- fault scenario regression tests;
- reproducibility;
- future telemetry artifacts;
- mission validation;
- polished CLI.

---

## Complexity

**High**

The loader and runner are not mathematically complex, but they sit at every subsystem boundary.

Silent configuration errors can invalidate:

- controller tuning;
- sensor timing;
- fault activation;
- expected outcomes;
- reproducibility.

Strict validation is essential.

---

# 2. User / Demo Flow

## Happy path — nominal scenario

1. User/reviewer runs:

```bash
uv run astraloop run scenarios/nominal.toml
```

2. CLI calls `run_scenario_file(...)`.
3. Loader verifies the path and parses TOML.
4. Schema version, IDs, keys, types, and local constraints validate.
5. Config resolves:
   - degrees → radians;
   - seconds → ticks;
   - defaults expanded;
   - enums created;
   - fault list becomes empty tuple.
6. Cross-field validation succeeds.
7. Config digest is calculated.
8. Dedicated sensor RNG streams are created from seed.
9. Fresh runtime subsystems are constructed.
10. Simulation runs.
11. Later telemetry/validation services complete.
12. `RunResult` returns.
13. CLI prints concise result and artifact paths.

---

## Happy path — fault scenario

1. User selects:

```bash
uv run astraloop run scenarios/altimeter_freeze.toml
```

2. Same loader/runner path executes.
3. The difference is data:
   - one sensor-freeze fault;
   - fault activation tick;
   - expected outcome.
4. Fault Manager changes real sensor behavior.
5. Mission naturally reaches resulting outcome.
6. Validator compares actual outcome with expected category.
7. Result/artifacts identify the exact scenario and seed.

---

## First-time path

Recommended implementation order from the user's perspective:

### Stage A — load minimal identity/simulation config

Parse:

```text
id
description
seed
dt
max_time
```

### Stage B — add initial state/vehicle/environment

Resolve units.

### Stage C — add sensor config

Resolve sample/delay ticks.

### Stage D — add controller/actuator config

Resolve control cadence and angles.

### Stage E — add mission config

Resolve hold duration/confirm counts.

### Stage F — add faults

Use typed Feature 07 definitions.

### Stage G — add validation/expected outcome

Transport only.

### Stage H — construct all runtime components

Run a very short deterministic scenario.

### Stage I — wire final full nominal and fault scenarios

---

## Empty state

### Empty scenario directory

Discovery returns:

```text
()
```

The later CLI should display:

```text
No scenario TOML files found under <path>.
```

This is not a simulation error.

### Scenario with empty fault list

Valid nominal configuration.

### Empty TOML file

Invalid: required top-level keys are missing.

### Missing optional faults section

Normalize to empty tuple.

---

## Error path

### File not found

Raise:

```text
ConfigError
```

with path.

### Wrong extension

Recommended:

- loader rejects non-`.toml` scenario path;
- tests using in-memory configs bypass file extension.

### TOML syntax error

Wrap `tomllib.TOMLDecodeError` as `ConfigError` while preserving location/message.

### Unknown key

Reject.

### Missing section

Reject with full key path.

### Wrong primitive type

Reject booleans used as integers where Python's `bool` subclassing could otherwise pass.

Example:

```toml
seed = true
```

must be invalid.

### Cross-field failure

Reject before subsystem construction.

### Runtime failure

Raise/preserve `SimulationError`, not `ConfigError`.

### Validation mismatch

Return a completed `RunResult` whose validation indicates mismatch.

Do not throw merely because the mission failed criteria.

---

## Reviewer demo path

### Demo A — show scenario file

Open:

```text
scenarios/altimeter_freeze.toml
```

Point out:

- same vehicle/controller stack;
- explicit seed;
- fault type/target/time;
- expected outcome.

### Demo B — run it

Show one command.

### Demo C — show resolved config

Later artifact:

```text
resolved_config.json
```

Explain:

> "The runtime does not repeatedly interpret TOML. I resolve all defaults, units, update periods, fault ticks, and typed targets before execution."

### Demo D — add a scenario

Copy one TOML, change:

- ID;
- description;
- fault definition;
- expected outcome.

Run without editing engine code.

Reviewer takeaway:

> "Scenario behavior is data-driven, strict, reproducible, and exercised through the same application service as the test suite."

---

# 3. UX / UI Requirements

## Screens/pages

**[Decision]** No GUI.

The final command surfaces are local CLI commands.

Feature 08 exposes data/services needed by:

```text
run
list-scenarios
optional campaign
```

Feature 15 owns polished CLI formatting and argument behavior.

---

## Components

Recommended:

```text
ScenarioDescriptor

RawScenarioConfig
ResolvedScenarioConfig

config loader
schema parser
resolver
cross-field validator
RNG builder
runtime builder
scenario runner
RunResult
```

---

## Forms/inputs

Input is a TOML file.

No interactive questionnaire is required.

Users edit text files under `scenarios/`.

---

## Buttons/actions

None.

---

## Validation messages

High-quality examples:

```text
ConfigError in scenarios/nominal.toml
at controller.update_interval_s:
0.03 s is not aligned to simulation dt=0.02 s.
```

```text
ConfigError in scenarios/velocity_bias.toml
at faults[0].target:
unknown sensor 'vertical_speed'; expected one of:
altimeter, vertical_velocity, horizontal_position,
horizontal_velocity, attitude, gyro.
```

```text
ConfigError in scenarios/degraded_actuator.toml
at faults[0]:
actuator_degradation is a no-op; at least one of
lag_multiplier, authority_scale, or rate_scale
must differ from its nominal value.
```

---

## Loading states

Most runs should start quickly.

Feature 08 itself needs no spinner.

For future campaign execution, CLI may print scenario currently running.

No fake progress bars.

---

## Error-state categories

Must remain distinguishable:

```text
CONFIG ERROR
SIMULATION ERROR
VALIDATION FAILURE
CONTROLLED ABORT
EXPECTED SUCCESS
```

Feature 08 preserves structured distinctions for the CLI.

---

## Responsive behavior

Not relevant.

---

# 4. Data Requirements

## Main entities

### `ScenarioDescriptor`

```python
@dataclass(frozen=True)
class ScenarioDescriptor:
    id: str
    description: str
    path: Path
    expected_outcome: ExpectedOutcome
    fault_count: int
```

---

### `RawScenarioConfig`

Conceptual:

```python
@dataclass(frozen=True)
class RawScenarioConfig:
    schema_version: int
    id: str
    description: str
    seed: int
    dt: float
    max_time: float

    initial_state: RawInitialStateConfig
    vehicle: VehicleConfig
    environment: EnvironmentConfig
    sensors: RawSensorSuiteConfig
    controller: RawControllerConfig
    actuators: RawActuatorConfig
    mission: RawMissionConfig
    faults: tuple[RawFaultConfig, ...]
    validation: RawValidationConfig
```

---

### `ResolvedScenarioConfig`

Conceptual:

```python
@dataclass(frozen=True)
class ResolvedScenarioConfig:
    schema_version: int
    id: str
    description: str
    seed: int

    simulation: SimulationConfig
    initial_state: VehicleState
    vehicle: VehicleParameters
    environment: EnvironmentConfig
    sensors: SensorSuiteConfig
    controller: ControllerConfig
    actuators: ActuatorConfig
    mission: MissionTransitionConfig
    faults: tuple[FaultDefinition, ...]
    validation: ValidationConfig

    rng_scheme: str
```

All child configs are final typed runtime forms.

---

### `ExpectedOutcome`

Recommended:

```python
class ExpectedOutcome(Enum):
    PASS = "pass"
    CONTROLLED_ABORT = "controlled_abort"
    VALIDATION_FAIL = "validation_fail"
```

---

### `ScenarioRuntime`

Internal stateful composition object.

---

### `RunResult`

Final application result shared by CLI/tests.

---

## Relationships

```text
Path
 |
 v
Raw TOML mapping
 |
 v
RawScenarioConfig
 |
 v
ResolvedScenarioConfig
 |
 +--> config digest
 +--> RNG bundle
 +--> fresh ScenarioRuntime
 |
 v
SimulationResult
 |
 +--> ValidationResult
 +--> artifacts
 |
 v
RunResult
```

---

## Canonical resolved-config representation

Feature 09 must serialize a JSON-safe view.

Recommended helper:

```python
def resolved_config_to_dict(
    config: ResolvedScenarioConfig,
) -> dict[str, object]:
    ...
```

Requirements:

- stable key order during canonical digest encoding;
- enums become explicit strings;
- tuples become arrays;
- paths become normalized strings only if included;
- no NumPy generator objects;
- no live component state;
- no Python class repr strings.

---

## Scenario path metadata

Source path may be stored in `RunResult` metadata for debugging.

It should not affect the config digest by default because the same scenario content copied to another location should represent the same resolved configuration.

**Decision]** Exclude source file path from digest.

---

## Example complete skeleton

```toml
schema_version = 1
id = "nominal"
description = "Nominal autonomous flight and landing"
seed = 42
dt = 0.02
max_time = 60.0

[initial_state]
x_m = 0.0
y_m = 0.0
vx_m_s = 0.0
vy_m_s = 0.0
theta_deg = 0.0
omega_deg_s = 0.0
mass_kg = 1200.0

[vehicle]
dry_mass_kg = 900.0
max_thrust_n = 18000.0
max_mass_flow_rate_kg_s = 5.0
moment_of_inertia_kg_m2 = 4500.0
thrust_lever_arm_m = 2.0

[environment]
gravity_m_s2 = 9.80665
ground_y_m = 0.0

[sensors.altimeter]
enabled = true
sample_interval_s = 0.10
noise_std = 0.50
bias = 0.0
delay_s = 0.0

# Repeat remaining required sensor tables.

[controller]
update_interval_s = 0.04

# PID and mission-profile tables.

[actuators.throttle]
min = 0.0
max = 1.0
response_time_constant_s = 0.20

[actuators.gimbal]
max_angle_deg = 8.0
response_time_constant_s = 0.10
max_rate_deg_s = 30.0

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

[validation]
expected_outcome = "pass"
max_landing_vertical_speed_m_s = 2.0
max_horizontal_error_m = 5.0
max_pitch_error_deg = 5.0
require_valid_transitions = true
```

Values are project-development parameters, not real launch-vehicle claims.

---

## Local persistence needs

Feature 08 reads local TOML.

It may pass configuration/result data to Feature 09.

It does not directly implement:

- CSV encoding;
- events JSON;
- summary JSON;
- plot generation.

No database.

---

# 5. Logic Requirements

## Rule 1 — Configuration is the source of scenario behavior

No scenario-name behavior branches.

---

## Rule 2 — Only local TOML is supported for MVP

No URL loading.

No remote includes.

No cloud config.

---

## Rule 3 — Parsing uses `tomllib`

---

## Rule 4 — Unknown keys are rejected

At every level.

---

## Rule 5 — Missing required keys are rejected

---

## Rule 6 — Types are strict

Do not accept bool where int/float is expected.

---

## Rule 7 — All numeric config values must be finite unless field is integer/enum

Reject NaN/Inf if parser/construction path permits them.

---

## Rule 8 — Units are normalized once

Degrees and seconds are resolved before runtime use.

---

## Rule 9 — Time/cadence values align to simulation ticks

Including:

- max time;
- sensor sample periods;
- sensor delay;
- controller update interval;
- mission hold period;
- fault activation/deactivation/duration.

---

## Rule 10 — Runtime receives immutable resolved config

Use frozen dataclasses/tuples.

---

## Rule 11 — Defaults become explicit

No subsystem silently invents a default not present in resolved config.

---

## Rule 12 — Cross-field validation finishes before runtime construction

---

## Rule 13 — Initial mass must be >= dry mass

---

## Rule 14 — Initial state must pass Feature 01 validation

---

## Rule 15 — `max_time / dt` follows Feature 02 exact-tick convention

Recommended integer-like requirement.

---

## Rule 16 — Every enabled sensor has valid tick cadence

---

## Rule 17 — Required controller measurements must exist in topology

If throttle control is enabled in any active profile:

```text
vertical_velocity sensor must exist and be enabled
```

If attitude control is enabled with nonzero `kd`:

```text
attitude and gyro sensors must exist and be enabled
```

---

## Rule 18 — Controller interval aligns to `dt`

---

## Rule 19 — Controller profiles exist for every MissionState

---

## Rule 20 — Inactive terminal profiles are safe

Recommended cross-field validation:

```text
LANDED/ABORT throttle disabled or zero base command
```

Do not change controller config automatically.

---

## Rule 21 — Actuator bounds are valid

Delegate local checks to Feature 05 validators.

---

## Rule 22 — Controller desired limits and actuator physical limits are intentionally compatible

**Decision]** Do not necessarily reject a controller software limit larger than actuator physical limit.

This can intentionally exercise physical saturation.

However, provide a clear validation warning or documented condition if mismatch is extreme.

For MVP, warnings may be represented as `ConfigWarning` records rather than printed.

---

## Rule 23 — Mission thresholds are finite and coherent

Recommended relationships:

```text
landed altitude threshold
<
landing-entry altitude
<
ascent cutoff altitude
```

when using the standard mission profile.

Reject obviously inverted threshold order.

Do not overconstrain unusual focused test configs without need.

---

## Rule 24 — Descent-entry velocity threshold is negative

Per Feature 06 recommended semantics.

---

## Rule 25 — Confirmation counts are positive integers

---

## Rule 26 — Fault IDs are unique

---

## Rule 27 — Fault types and targets are valid

---

## Rule 28 — Fault times align to ticks

---

## Rule 29 — Time-based faults are meaningful within configured maximum runtime

Negative/beyond-unreachable timing invalid at setup, accounting for engine tick semantics.

---

## Rule 30 — No-op faults are rejected

Examples:

- zero bias;
- delay identical to nominal;
- lag multiplier one with no other change.

---

## Rule 31 — Fault target must exist

---

## Rule 32 — Bundled fault targeting disabled subsystem is rejected

A freeze on a disabled sensor does not demonstrate real behavior.

---

## Rule 33 — Degraded lag fault requires nominal actuator tau > 0 or another real changed parameter

---

## Rule 34 — Expected outcome is a supported enum

---

## Rule 35 — `simulator_error` is not a valid expected success category

---

## Rule 36 — Validation limits are finite/nonnegative

---

## Rule 37 — Same resolved config produces same digest

---

## Rule 38 — Source path does not change digest

---

## Rule 39 — Same config/seed creates same RNG streams

---

## Rule 40 — Every run constructs fresh stateful components

---

## Rule 41 — `run_scenario` does not mutate config

---

## Rule 42 — `run_scenario` does not print unconditionally

---

## Rule 43 — `run_scenario` uses no global mutable runtime state

---

## Rule 44 — CLI and tests call the same runner

No separate demo engine.

---

## Rule 45 — Config errors occur before engine tick zero

---

## Rule 46 — Domain mission failure returns result

It is not converted into `SimulationError`.

---

## Rule 47 — Simulation errors remain distinct

---

## Rule 48 — Artifact persistence is delegated

---

## Rule 49 — Validation calculations are delegated

---

## Rule 50 — New scenario using supported schema needs no core engine edit

---

## Loader pseudocode

```python
def load_scenario(
    path: str | Path,
) -> ResolvedScenarioConfig:

    source_path = normalize_scenario_path(path)
    raw_mapping = parse_toml(source_path)

    raw_config = parse_raw_scenario_config(
        raw_mapping,
        source_path=source_path,
    )

    resolved = resolve_scenario_config(raw_config)

    validate_resolved_scenario(
        resolved,
        source_path=source_path,
    )

    return resolved
```

---

## Numeric type helper

Because:

```python
isinstance(True, int) is True
```

validation helpers must explicitly reject booleans.

Example:

```python
def require_int(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(...)
    return value
```

Equivalent numeric helper may accept int/float but reject bool.

---

## Time-to-tick resolution pseudocode

```python
def seconds_to_ticks(
    seconds: float,
    *,
    dt: float,
    field_path: str,
    allow_zero: bool,
) -> int:

    validate_finite(seconds)

    ratio = seconds / dt
    rounded = round(ratio)

    if not math.isclose(
        ratio,
        rounded,
        rel_tol=0.0,
        abs_tol=CONFIG_ALIGNMENT_TOLERANCE,
    ):
        raise ConfigError(
            f"{field_path} is not aligned to dt"
        )

    ticks = int(rounded)

    if allow_zero:
        if ticks < 0:
            raise ConfigError(...)
    elif ticks <= 0:
        raise ConfigError(...)

    return ticks
```

---

## Cross-field validation pseudocode

```python
def validate_resolved_scenario(
    config: ResolvedScenarioConfig,
) -> None:

    validate_initial_state(
        config.initial_state,
        config.vehicle,
    )

    validate_sensor_controller_dependencies(config)

    validate_mission_threshold_order(config.mission)

    validate_fault_targets(
        config.faults,
        sensors=config.sensors,
        actuators=config.actuators,
    )

    validate_fault_effectiveness(config)

    validate_validation_config(config.validation)
```

---

## Runtime builder pseudocode

```python
def build_runtime(
    config: ResolvedScenarioConfig,
) -> ScenarioRuntime:

    rngs = build_rng_bundle(
        seed=config.seed,
        scheme=config.rng_scheme,
    )

    sensors = SensorSuite.from_config(
        config.sensors,
        rngs=rngs,
    )

    controller = FlightController.from_config(
        config.controller,
    )

    actuators = ActuatorModel.from_config(
        config.actuators,
    )

    mission = MissionStateMachine.from_config(
        config.mission,
    )

    faults = FaultManager(
        definitions=config.faults,
    )

    engine = SimulationEngine(
        config=config.simulation,
        initial_state=config.initial_state,
        vehicle=config.vehicle,
        environment=config.environment,
        sensors=sensors,
        controller=controller,
        actuators=actuators,
        mission=mission,
        faults=faults,
        telemetry=...,
    )

    return ScenarioRuntime(...)
```

Constructors should remain explicit and testable.

---

## Runner pseudocode

```python
def run_scenario(
    config: ResolvedScenarioConfig,
    *,
    artifact_root: Path | None = None,
) -> RunResult:

    config_digest = compute_config_digest(config)

    runtime = build_runtime(config)

    try:
        simulation_result = runtime.engine.run()
    except SimulationError:
        finalize_diagnostic_artifact_if_available(...)
        raise

    validation_result = validator.evaluate(
        simulation_result,
        config.validation,
    )

    artifact_dir = artifact_writer.finalize(
        ...,
        root=artifact_root,
    )

    return RunResult(
        scenario_id=config.id,
        seed=config.seed,
        config_digest=config_digest,
        engine_result=simulation_result,
        validation=validation_result,
        artifact_dir=artifact_dir,
    )
```

Before Features 09/10 are implemented, the corresponding calls may be represented by narrow interfaces/test doubles, but the final boundary should remain.

---

## Config digest pseudocode

```python
def compute_config_digest(
    config: ResolvedScenarioConfig,
) -> str:

    payload = resolved_config_to_dict(config)

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

    return hashlib.sha256(canonical).hexdigest()
```

Use a deliberate stable float representation supported by Python's JSON encoder.

---

## Edge cases

### TOML file contains duplicate key

`tomllib` should reject syntax.

Wrap error.

---

### Scenario ID differs from bundled file stem

Reject for repository-discovered bundled scenario.

---

### Two discovered files have same scenario ID

Reject discovery result.

---

### Hidden/temporary files in scenario directory

Ignore non-`.toml`.

A malformed `.toml` file should not be silently ignored when discovery loads configs.

---

### Empty fault list

Valid.

---

### Fault scheduled exactly at final tick

Validate against actual engine processing semantics.

Do not assume `activation_time <= max_time` is sufficient.

---

### Fault scheduled after likely early mission termination

Configuration may remain valid because early termination depends on runtime.

Later result can report fault not activated.

---

### Same config run twice with artifact persistence

Simulation result should reproduce.

Artifact directory timestamp/path may differ.

Do not compare artifact path as deterministic simulation output.

---

### Same content copied to another path

Resolved config/digest remains same, except any deliberately included source metadata outside digest.

---

### Different comments/formatting

Digest remains same because it is based on resolved config, not raw file bytes.

---

### Integer written where float expected

Accept as numeric where mathematically valid, convert to float.

Reject bool.

---

### Negative zero

Normalize where useful to avoid surprising canonical digest differences:

```text
-0.0 -> 0.0
```

**Decision]** Canonicalization should normalize signed zero for resolved numeric fields.

---

### Degrees and radians both supplied

Reject ambiguous duplicate semantic fields.

Only one raw unit representation per schema field.

---

### Unknown mission profile table

Reject.

### Missing mission profile

Reject.

---

### Disabled required sensor

Reject if active controller/state-machine configuration requires it.

---

### Fault targets disabled sensor

Reject meaningful bundled run.

---

### Validation expected outcome missing

Reject.

Every scenario documents its expected behavior.

---

### Scenario expected outcome does not match fault count

Do not infer outcome from fault count.

A fault scenario may still expect `pass`.

No validation error solely because:

```text
faults nonempty + expected_outcome pass
```

---

### No fault but expected controlled abort

Potentially valid focused scenario if mission config intentionally aborts, but suspicious.

**Decision]** Do not branch on nominal/fault label.

Optionally emit configuration warning, not hard error.

---

### RunResult validation unavailable during staged implementation

Allow an internal development result with `validation=None` only until Feature 10 is complete.

Portfolio-ready runner requires validation.

---

# 6. Acceptance Criteria

## AC-01 — Loader accepts a valid local TOML scenario

**Given** a complete valid scenario file  
**When** `load_scenario(path)` is called  
**Then** it returns a fully typed resolved configuration.

---

## AC-02 — Missing file produces ConfigError

**Given** a nonexistent path  
**When** loading is attempted  
**Then** `ConfigError` identifies the path.

---

## AC-03 — Non-TOML scenario file is rejected

**Given** a `.json` or arbitrary file path  
**When** passed to the scenario loader  
**Then** it is rejected under the MVP local-TOML contract.

---

## AC-04 — Malformed TOML produces contextual ConfigError

**Given** invalid TOML syntax  
**When** parsing occurs  
**Then** the error preserves useful file/location context.

---

## AC-05 — Unsupported schema version is rejected

**Given** `schema_version != 1`  
**When** schema validation runs  
**Then** loading fails clearly.

---

## AC-06 — Missing required top-level key is rejected

**Given** no `seed` or another required field  
**When** config is parsed  
**Then** loading fails with key path.

---

## AC-07 — Unknown top-level key is rejected

**Given** an unsupported key  
**When** parsing occurs  
**Then** it is not silently ignored.

---

## AC-08 — Unknown nested key is rejected

**Given** typo inside sensor/controller/fault table  
**When** parsing occurs  
**Then** loading fails at the nested key path.

---

## AC-09 — Boolean is not accepted as integer seed

**Given** `seed = true`  
**When** type validation runs  
**Then** configuration is rejected.

---

## AC-10 — Valid integer seed is preserved

**Given** a supported seed  
**When** resolution completes  
**Then** resolved seed matches exactly.

---

## AC-11 — Scenario ID format is validated

**Given** an ID with spaces/invalid characters  
**When** loading occurs  
**Then** config is rejected.

---

## AC-12 — Bundled file stem matches ID

**Given** `scenarios/foo.toml` containing `id="bar"`  
**When** loaded as a bundled/discovered scenario  
**Then** configuration is rejected.

---

## AC-13 — Description must be non-empty

**Given** blank description  
**When** validation runs  
**Then** config is rejected.

---

## AC-14 — Invalid dt is rejected

**Given** non-finite or nonpositive `dt`  
**When** resolution occurs  
**Then** config fails before runtime construction.

---

## AC-15 — Invalid max time is rejected

**Given** non-finite/nonpositive max time  
**When** validation runs  
**Then** config fails.

---

## AC-16 — Max time resolves to supported exact tick count

**Given** valid aligned `max_time` and `dt`  
**When** resolution runs  
**Then** resolved simulation config contains deterministic max ticks.

---

## AC-17 — Non-aligned max time is rejected under exact-tick policy

**Given** max time not representable by integer ticks  
**When** resolution runs  
**Then** config fails rather than silently rounding.

---

## AC-18 — Degrees convert to radians once

**Given** an initial pitch in degrees  
**When** config resolves  
**Then** runtime initial state contains the correct radian value.

---

## AC-19 — Resolved config contains no ambiguous degree field

**Given** successful resolution  
**When** runtime config is inspected  
**Then** core angle values use the documented internal radian representation.

---

## AC-20 — Sensor sample interval resolves to ticks

**Given** aligned sensor sample interval  
**When** config resolves  
**Then** `sample_every_ticks` is correct.

---

## AC-21 — Non-aligned sensor sample interval is rejected

**Given** interval not aligned to `dt`  
**When** config resolves  
**Then** loading fails.

---

## AC-22 — Sensor delay resolves to ticks

**Given** aligned delay  
**When** config resolves  
**Then** resolved sensor delay tick count is correct.

---

## AC-23 — Controller interval resolves to ticks

**Given** aligned update interval  
**When** config resolves  
**Then** controller cadence/control dt are correct.

---

## AC-24 — Mission hold time resolves to ticks

**Given** aligned prelaunch hold  
**When** resolution occurs  
**Then** mission config contains correct hold ticks.

---

## AC-25 — Fault activation time resolves exactly

**Given** `dt=0.02`, activation `20.0`  
**When** resolved  
**Then** activation tick is `1000`.

---

## AC-26 — Non-aligned fault time is rejected

**Given** activation time not aligned to tick  
**When** config resolves  
**Then** loading fails.

---

## AC-27 — Initial mass below dry mass is rejected

**Given** initial state mass lower than vehicle dry mass  
**When** cross-field validation runs  
**Then** simulation does not start.

---

## AC-28 — Initial state receives Feature 01 validation

**Given** non-finite/physically invalid initial state  
**When** scenario validation runs  
**Then** it fails before engine construction.

---

## AC-29 — All required sensor tables exist

**Given** a complete MVP scenario missing gyro table  
**When** schema validation runs  
**Then** loading fails even if another scenario disables gyro use.

---

## AC-30 — Controller dependency on vertical velocity is validated

**Given** throttle control enabled but vertical-velocity sensor disabled  
**When** cross-field validation runs  
**Then** configuration is rejected.

---

## AC-31 — Attitude derivative dependency on gyro is validated

**Given** attitude `kd != 0` and gyro disabled  
**When** cross-field validation runs  
**Then** config is rejected.

---

## AC-32 — Controller profiles cover all mission states

**Given** a missing profile  
**When** configuration validates  
**Then** loading fails.

---

## AC-33 — Invalid PID bounds are rejected

**Given** output/integral min exceeds max  
**When** validation runs  
**Then** config fails.

---

## AC-34 — Invalid actuator bounds are rejected

**Given** invalid throttle/gimbal limits  
**When** config validates  
**Then** config fails before runtime.

---

## AC-35 — Mission threshold inversion is rejected

**Given** landed threshold above landing-entry altitude under standard mission schema  
**When** cross-field validation runs  
**Then** configuration fails.

---

## AC-36 — Descent threshold sign is validated

**Given** nonnegative descent-entry threshold  
**When** standard mission config validates  
**Then** loading fails under Feature 06 semantics.

---

## AC-37 — Confirmation counts must be positive integers

**Given** zero/negative/noninteger confirmation count  
**When** validation runs  
**Then** config fails.

---

## AC-38 — Duplicate fault IDs are rejected

**Given** two fault definitions with same ID  
**When** config loads  
**Then** `ConfigError` occurs.

---

## AC-39 — Unknown fault target is rejected

**Given** invalid sensor/actuator target  
**When** config loads  
**Then** loading fails.

---

## AC-40 — Fault type/target mismatch is rejected

**Given** sensor fault targeting gimbal  
**When** validation runs  
**Then** loading fails.

---

## AC-41 — Fault targeting disabled sensor is rejected for bundled meaningful scenario

**Given** freeze fault targeting disabled altimeter  
**When** cross-field validation runs  
**Then** scenario is rejected as behaviorally invalid.

---

## AC-42 — Zero sensor bias fault is rejected

**Given** bias magnitude zero  
**When** fault effectiveness validation runs  
**Then** configuration fails.

---

## AC-43 — No-op delay fault is rejected

**Given** fault delay equals nominal effective delay  
**When** cross-field validation runs  
**Then** scenario is rejected/flagged invalid as a non-nominal fault.

---

## AC-44 — No-op actuator degradation is rejected

**Given** all degradation modifiers nominal  
**When** validation runs  
**Then** configuration fails.

---

## AC-45 — Lag fault on zero-tau actuator must genuinely change another parameter or fail

**Given** only lag multiplier changed but nominal tau is zero  
**When** effectiveness validation runs  
**Then** config is rejected as no-op.

---

## AC-46 — Expected outcome is required

**Given** no expected outcome  
**When** scenario config loads  
**Then** loading fails.

---

## AC-47 — Unsupported expected outcome is rejected

**Given** unknown outcome string  
**When** validation runs  
**Then** configuration fails.

---

## AC-48 — Simulator error cannot be declared expected success

**Given** `expected_outcome="simulator_error"`  
**When** validation config parses  
**Then** configuration is rejected.

---

## AC-49 — Fault scenario may expect pass

**Given** a real fault and expected outcome `pass`  
**When** config validates  
**Then** it is allowed; fault presence does not automatically imply failure.

---

## AC-50 — Omitted faults normalize to empty tuple

**Given** valid scenario without faults section  
**When** loading completes  
**Then** resolved fault list is empty immutable tuple.

---

## AC-51 — Empty fault config uses same runner path

**Given** nominal config  
**When** run executes  
**Then** no special alternate engine is used.

---

## AC-52 — Resolved config is immutable

**Given** successful load  
**When** downstream code receives config  
**Then** normal mutation is prevented by frozen records/immutable collections.

---

## AC-53 — Runtime receives resolved config only

**Given** subsystem construction  
**When** code is inspected  
**Then** sensors/controllers/fault manager do not parse TOML or convert raw units.

---

## AC-54 — Same resolved config produces same digest

**Given** identical resolved configs  
**When** digest is computed  
**Then** digest matches.

---

## AC-55 — Comments/formatting do not change digest

**Given** two TOML files with same resolved values but different comments/formatting  
**When** loaded  
**Then** resolved config digest matches.

---

## AC-56 — Source path does not change digest

**Given** same scenario content copied to another local path  
**When** loaded  
**Then** digest matches.

---

## AC-57 — Changing seed changes digest

**Given** otherwise identical configs with different seeds  
**When** digests are computed  
**Then** digests differ.

---

## AC-58 — Changing a fault parameter changes digest

**Given** otherwise identical configs  
**When** fault magnitude/time changes  
**Then** digest differs.

---

## AC-59 — Same scenario seed derives same RNG streams

**Given** same config/seed  
**When** runtime bundles are built independently  
**Then** stochastic subsystem streams reproduce.

---

## AC-60 — Sensor streams are independently derived

**Given** one scenario seed  
**When** RNG bundle is constructed  
**Then** each sensor receives its dedicated generator according to canonical scheme.

---

## AC-61 — run_scenario builds fresh components

**Given** two calls with same config  
**When** runtime objects are inspected  
**Then** sensor buffers/PID state/actuator state/mission state/fault state are separate objects.

---

## AC-62 — Prior run state cannot leak into next run

**Given** first run modifies all stateful components  
**When** second run begins with same config  
**Then** it starts from configured initial state and fresh subsystem memory.

---

## AC-63 — run_scenario does not mutate configuration

**Given** resolved config  
**When** run completes  
**Then** config equals its pre-run value.

---

## AC-64 — CLI and tests use same application service

**Given** CLI run command and scenario end-to-end test  
**When** code paths are inspected  
**Then** both call `run_scenario(...)` or its direct file wrapper.

---

## AC-65 — New supported scenario needs no engine edit

**Given** a new TOML using existing config/fault types  
**When** added under scenarios  
**Then** it can load/run without modifying Simulation Engine source.

---

## AC-66 — Scenario discovery is deterministic

**Given** a directory of valid scenario TOMLs  
**When** discovery runs repeatedly  
**Then** descriptors appear in stable order.

---

## AC-67 — Discovery ignores non-TOML files

**Given** README/image files in scenario directory  
**When** discovery runs  
**Then** they are not treated as scenarios.

---

## AC-68 — Duplicate discovered scenario IDs fail

**Given** multiple TOMLs resolving to same ID  
**When** discovery runs  
**Then** it reports configuration conflict.

---

## AC-69 — Empty discovery root returns empty result

**Given** directory with no TOMLs  
**When** discovery runs  
**Then** it returns empty tuple rather than crashing.

---

## AC-70 — Config errors occur before tick zero

**Given** invalid cross-field config  
**When** run is requested  
**Then** no engine step, sensor RNG draw, or fault activation occurs.

---

## AC-71 — Domain mission failure returns structured result

**Given** simulation completes but validation criteria fail  
**When** runner returns  
**Then** failure is represented in `RunResult`, not raised as `SimulationError`.

---

## AC-72 — Controlled abort returns structured result

**Given** mission reaches ABORT normally  
**When** runner completes  
**Then** result preserves controlled-abort outcome.

---

## AC-73 — Simulation invariant failure remains SimulationError

**Given** engine produces non-finite truth/internal invariant failure  
**When** runner executes  
**Then** error is not relabeled as validation failure.

---

## AC-74 — Runner performs no scenario-name branching

**Given** runner source  
**When** inspected  
**Then** it does not select behavior using IDs like `altimeter_freeze`.

---

## AC-75 — Runner does not implement domain equations

**Given** runner source  
**When** inspected  
**Then** it does not calculate dynamics/PID/sensor samples/actuator lag/mission guards.

---

## AC-76 — Runner does not implement validation checks

**Given** runner source  
**When** inspected  
**Then** Feature 10 validator owns metric evaluation.

---

## AC-77 — Runner does not implement artifact formats

**Given** runner source  
**When** inspected  
**Then** CSV/JSON/PNG details belong to Feature 09/11.

---

## AC-78 — Runner can operate without persistent artifacts in tests

**Given** explicit no-artifact/test mode or `tmp_path`  
**When** end-to-end test runs  
**Then** repository `runs/` is not polluted.

---

## AC-79 — Runner is headless/local

**Given** clean local Python environment  
**When** scenario runs  
**Then** no network, browser, database, secrets, or hardware are required.

---

## AC-80 — Same config/seed reproduces mission-level outcome

**Given** complete implemented stack and identical resolved config  
**When** scenario runs twice  
**Then** final mission state, validation outcome, fault lifecycle, and deterministic numerical outputs reproduce within the project's defined equality/tolerance semantics.

---

# 7. Test Plan

## Unit tests — loader

Recommended:

```text
tests/unit/test_config_loader.py
```

Cases:

```text
test_load_valid_scenario
test_missing_file
test_wrong_extension
test_malformed_toml
test_empty_toml
test_unsupported_schema_version
test_missing_required_key
test_unknown_top_level_key
test_unknown_nested_key
test_bool_rejected_as_int
test_invalid_scenario_id
test_blank_description
test_bundled_id_filename_mismatch
```

---

## Unit tests — schema parsing

Recommended:

```text
tests/unit/test_config_schema.py
```

Test each table/dataclass:

```text
initial state
vehicle
environment
six sensors
controller PID/profiles
actuators
mission
faults
validation
```

Use minimal focused raw mappings.

---

## Unit tests — time/unit resolution

Recommended:

```text
tests/unit/test_config_resolution.py
```

Cases:

```text
test_degrees_to_radians
test_omega_degrees_to_radians
test_max_time_to_ticks
test_sensor_interval_to_ticks
test_sensor_delay_to_ticks
test_controller_interval_to_ticks
test_prelaunch_hold_to_ticks
test_fault_activation_to_tick
test_fault_duration_to_tick
test_non_aligned_time_rejected
test_signed_zero_normalized
```

---

## Unit tests — cross-field validation

Recommended:

```text
tests/unit/test_config_validation.py
```

Cases:

```text
test_initial_mass_below_dry_mass
test_throttle_requires_vertical_velocity_sensor
test_attitude_kd_requires_gyro
test_all_mission_profiles_required
test_mission_threshold_order
test_negative_descent_threshold_required
test_fault_target_exists
test_fault_target_enabled
test_noop_bias_rejected
test_noop_delay_rejected
test_noop_actuator_degradation_rejected
test_fault_time_within_engine_semantics
test_expected_outcome_valid
test_simulator_error_not_expected
```

---

## Unit tests — digest

```text
tests/unit/test_config_digest.py
```

Cases:

```text
test_same_resolved_config_same_digest
test_comments_do_not_change_digest
test_formatting_does_not_change_digest
test_source_path_does_not_change_digest
test_seed_changes_digest
test_fault_parameter_changes_digest
test_validation_limit_changes_digest
test_digest_contains_no_nan
```

---

## Unit tests — discovery

```text
tests/unit/test_scenario_discovery.py
```

Cases:

```text
test_discover_toml_files
test_discovery_sorted
test_ignore_non_toml
test_empty_directory
test_duplicate_id_rejected
test_malformed_discovered_toml_reported
```

---

## Unit tests — RNG construction

```text
tests/unit/test_rng_setup.py
```

Cases:

```text
test_same_seed_same_stream_sequence
test_different_seed_changes_stream
test_sensor_streams_independent
test_canonical_stream_order
test_no_python_hash_derivation
```

---

## Unit/integration tests — runtime builder

```text
tests/integration/test_scenario_runtime_builder.py
```

Cases:

```text
test_builds_all_required_subsystems
test_runtime_uses_configured_initial_state
test_runtime_components_are_fresh
test_runtime_wires_measurement_only_controller
test_runtime_wires_actuator_state_to_dynamics
test_runtime_wires_fault_manager_before_sensor
test_runtime_uses_no_global_state
```

---

## End-to-end scenario runner tests

Recommended:

```text
tests/scenarios/test_nominal.py
tests/scenarios/test_fault_scenarios.py
```

### Nominal

```python
def test_nominal_scenario_matches_expected_outcome():
    config = load_scenario(
        Path("scenarios/nominal.toml")
    )
    result = run_scenario(
        config,
        artifact_root=None,
    )
    assert result.validation.outcome_matched
```

Exact validation API belongs to Feature 10.

### Fault scenarios

Parametrize:

```text
altimeter_freeze.toml
velocity_bias.toml
sensor_delay.toml
degraded_actuator.toml
```

Assert:

- config loads;
- expected fault activates unless run legitimately terminates first;
- real subsystem behavior differs;
- expected outcome matches;
- no scenario-name engine branch.

---

## Reproducibility tests

Run same scenario twice.

Compare:

```text
config digest
final tick/time
final truth state
mission transition events
fault activation events
validation result
telemetry rows if deterministic serialization is defined
```

Do not compare:

```text
artifact directory timestamp
wall-clock duration
```

---

## Artifact integration tests deferred to Feature 09

Use `tmp_path`.

Assert:

- runner passes resolved config/digest;
- artifact directory remains under requested root;
- config error creates no normal run artifact;
- simulation error diagnostic behavior follows final policy.

---

## Validation integration tests deferred to Feature 10

Assert runner passes:

- simulation result;
- scenario validation limits;
- expected outcome;
- fault activation metadata.

---

## CLI integration tests deferred to Feature 15

Assert CLI:

- maps run path to runner;
- maps exit codes correctly;
- renders errors without changing runner semantics.

---

## Manual QA checklist

- [ ] Five core TOML scenario files exist.
- [ ] Each has schema version.
- [ ] Each has matching ID/file stem.
- [ ] Each has non-empty description.
- [ ] Each has explicit seed.
- [ ] Each has dt/max time.
- [ ] Each contains complete subsystem config.
- [ ] Every scenario includes expected outcome.
- [ ] Fault scenarios use typed faults.
- [ ] Nominal uses empty faults.
- [ ] `tomllib` is used.
- [ ] Unknown keys fail.
- [ ] Wrong types fail.
- [ ] Unit conversions happen once.
- [ ] Time values resolve to ticks.
- [ ] Cross-field validation runs before runtime construction.
- [ ] Resolved config is immutable.
- [ ] Config digest is stable.
- [ ] Dedicated RNG streams derive from seed.
- [ ] Every run has fresh mutable subsystem state.
- [ ] CLI/tests share runner service.
- [ ] Runner contains no scenario-name branches.
- [ ] Runner contains no physics/control/fault mechanics.
- [ ] Runner does not write artifact formats directly.
- [ ] Runner does not evaluate validation formulas directly.
- [ ] No database/network/environment-secret requirement exists.
- [ ] Unit/integration/end-to-end tests pass.

---

## Demo verification checklist

- [ ] Reviewer can open one complete scenario TOML.
- [ ] Reviewer sees seed and expected outcome.
- [ ] Reviewer sees fault type/target/time in a fault scenario.
- [ ] One command runs nominal.
- [ ] One command runs a fault scenario.
- [ ] Resolved config can be inspected later.
- [ ] Same config/seed reproduces result.
- [ ] New supported scenario can be added by TOML only.
- [ ] Invalid typo produces useful ConfigError.
- [ ] Engine source contains no scenario-specific branch.
- [ ] Same application service is exercised by pytest.
- [ ] Scenario runner works headlessly/offline.

---

# 8. Portfolio Value

## How this feature helps the project stand out

Feature 08 turns AstraLoop from a single simulation into a reusable validation testbed.

The strongest statement is:

> "Every mission is a strict TOML configuration. The loader resolves units, timing, faults, validation limits, and RNG streams into immutable typed config before execution. The CLI and pytest both call the same scenario runner."

This demonstrates:

- real application architecture;
- typed configuration;
- reproducibility;
- dependency wiring;
- testability;
- clean domain boundaries;
- defensive validation.

---

## What to mention in README

Recommended wording:

> **Config-driven scenarios:** Nominal and faulted missions are defined as local TOML files and resolved into immutable typed configuration before execution. The same `run_scenario(...)` application service powers both CLI demos and end-to-end pytest regression tests.

Useful bullets:

- strict unknown-key rejection;
- explicit units;
- seconds-to-tick resolution;
- complete resolved config snapshot;
- explicit seed;
- dedicated RNG streams;
- scenario/fault expected outcomes;
- new scenarios without engine edits.

---

## What to mention in interviews

### Why use TOML?

> "The configuration is local, hierarchical, readable, comment-friendly, and supported by Python's standard library. It is enough for this controlled schema without adding a framework."

### Why separate raw and resolved config?

> "The raw file is human-oriented—degrees, seconds, optional defaults. The resolved config is runtime-oriented—radians, integer tick periods, typed enums, and all defaults explicit. Subsystems never interpret TOML themselves."

### Why reject unknown keys?

> "Simulation config typos can silently change test meaning. Strict unknown-key validation turns those mistakes into immediate ConfigErrors."

### How do you guarantee reproducibility?

> "The resolved config includes an explicit seed. The runner derives dedicated sensor RNG streams in a fixed scheme, creates fresh subsystem instances for every run, and computes a digest from canonical resolved config."

### Why not use Pydantic?

> "The schema is controlled and intentionally small enough for dataclasses plus explicit validation. That keeps runtime types transparent and makes the validation rules visible."

### Why no configuration inheritance?

> "There are only five core scenarios. Self-contained files are easier to inspect and reproduce than hidden merge chains. I would add a small reference mechanism only after duplication became a demonstrated problem."

### How do tests use the runner?

> "The CLI and end-to-end tests call the same `run_scenario` function. There is no separate test simulator or demo-only path."

### What happens when a mission fails?

> "A completed hard landing or controlled abort returns a structured domain result. Invalid config raises ConfigError, while numerical/runtime invariant failures remain SimulationError."

### How would you add a new fault scenario?

> "Create a TOML using an already-supported typed fault. The runner and engine do not need source edits."

---

# 9. Implementation Notes for Codex

## Likely files/folders

```text
src/astraloop/config/
├── __init__.py
├── loader.py
├── schema.py
└── validation.py

src/astraloop/scenarios/
├── __init__.py
├── discovery.py
└── runner.py

src/astraloop/model/
├── results.py
└── errors.py

scenarios/
├── nominal.toml
├── altimeter_freeze.toml
├── velocity_bias.toml
├── sensor_delay.toml
└── degraded_actuator.toml

tests/unit/
├── test_config_loader.py
├── test_config_schema.py
├── test_config_resolution.py
├── test_config_validation.py
├── test_config_digest.py
├── test_scenario_discovery.py
└── test_rng_setup.py

tests/integration/
└── test_scenario_runtime_builder.py

tests/scenarios/
├── test_nominal.py
└── test_fault_scenarios.py
```

---

## Suggested responsibilities

### `config/schema.py`

Own:

- raw/resolved dataclasses;
- config enums;
- JSON-safe canonical conversion helpers if tightly related;
- no file I/O.

---

### `config/loader.py`

Own:

- path validation;
- file reading;
- `tomllib`;
- raw mapping parsing;
- public `load_scenario`.

May call resolver/validator helpers.

---

### `config/validation.py`

Own:

- primitive validation helpers;
- unit/tick resolution;
- cross-field validation;
- `ConfigError` construction.

Keep error paths precise.

---

### `scenarios/discovery.py`

Own:

- finding local scenario TOMLs;
- deterministic descriptors;
- duplicate-ID checks.

---

### `scenarios/runner.py`

Own:

- config digest call;
- RNG construction;
- runtime object construction;
- application orchestration;
- `run_scenario`;
- `run_scenario_file`.

Do not place TOML parsing details here.

---

### `model/results.py`

Own shared:

```text
RunResult
```

and potentially scenario result metadata.

---

### `model/errors.py`

Own:

```text
ConfigError
SimulationError
```

if not already placed elsewhere.

---

## Build order

### Step 1 — Define ConfigError

Support:

```text
source path
field path
message
```

---

### Step 2 — Define top-level raw schema

Start with identity/simulation fields.

Test strict keys/types.

---

### Step 3 — Add initial state/vehicle/environment schema

Reuse Feature 01 types.

---

### Step 4 — Add sensor config parsing/resolution

Reuse Feature 03 validation.

Do not duplicate formulas unnecessarily.

---

### Step 5 — Add controller/actuator config

Reuse Features 04/05 validators.

---

### Step 6 — Add mission config

Reuse Feature 06 semantics.

---

### Step 7 — Add typed fault parsing

Reuse Feature 07 definitions.

---

### Step 8 — Add validation config/expected outcome

Transport only; do not calculate results.

---

### Step 9 — Implement time-to-tick resolution

Use one central helper.

---

### Step 10 — Implement cross-field validation

Build tests for every dependency.

---

### Step 11 — Implement canonical resolved-config serialization/digest

Lock it with tests before artifact directories rely on it.

---

### Step 12 — Implement RNG bundle construction

Fixed canonical stream order/version.

---

### Step 13 — Implement runtime builder

Use explicit constructors.

---

### Step 14 — Implement run_scenario

Initially return engine result.

Integrate Features 09/10 through narrow boundaries later.

---

### Step 15 — Add five curated TOMLs

Use tuned values only after nominal controller/mission works.

Do not copy placeholder zero gains into final scenarios.

---

### Step 16 — Add discovery

Needed by polished CLI later.

---

### Step 17 — Add end-to-end scenario tests

Make fault outcomes deterministic.

---

## Risks

### Risk 1 — Giant unmaintainable schema

**Mitigation:** child config dataclasses match real subsystem boundaries.

---

### Risk 2 — Validation logic duplicated in loader and subsystem

**Mitigation:** expose reusable local validators from subsystem/config boundary, or centralize configuration validation while leaving runtime invariants in subsystem.

---

### Risk 3 — Unknown keys silently ignored

**Mitigation:** explicit allowed-key sets.

---

### Risk 4 — Units ambiguous

**Mitigation:** suffix raw field names with units and normalize once.

---

### Risk 5 — Tick alignment silently rounded

**Mitigation:** explicit integer-like validation.

---

### Risk 6 — Configuration inheritance creates hidden behavior

**Mitigation:** self-contained MVP scenarios.

---

### Risk 7 — Runner becomes a god object

**Mitigation:** runner constructs/coordin­ates; engine and modules own behavior.

---

### Risk 8 — Stateful component reused across runs

**Mitigation:** fresh runtime builder every call.

---

### Risk 9 — Global RNG state leaks

**Mitigation:** one explicit `SeedSequence` bundle.

---

### Risk 10 — Config digest depends on path/comments

**Mitigation:** digest canonical resolved data only.

---

### Risk 11 — Scenario name controls behavior

**Mitigation:** all behavior emerges from config fields/fault definitions.

---

### Risk 12 — Runner begins writing telemetry/plots

**Mitigation:** delegate to Feature 09/11 interfaces.

---

### Risk 13 — Runner calculates PASS/FAIL

**Mitigation:** delegate to Validator.

---

### Risk 14 — Overly permissive expected outcomes

**Mitigation:** small explicit enum; simulator error never accepted as expected mission success.

---

### Risk 15 — Final scenario values remain placeholders

**Mitigation:** scenario regression tests must prove tuned outcomes before portfolio-ready status.

---

## What not to change

While implementing Feature 08, Codex should **not**:

- change Feature 01 dynamics;
- change RK4;
- change tick semantics;
- change sensor models;
- change PID equations;
- change actuator equations;
- change mission transition graph solely to satisfy scenario config;
- change fault mechanics;
- implement CSV/event/plot formats;
- implement validation formulas;
- implement polished Rich terminal output;
- implement argparse command definitions;
- add Pydantic;
- add YAML;
- add configuration inheritance;
- add remote includes;
- add environment-variable interpolation;
- add secrets/config service;
- add database;
- add cloud storage;
- add multiprocessing campaign runner;
- add scenario-name branches;
- create global runtime state.

---

# Feature-Specific Definition of Done

Feature 08 is complete when:

- [ ] `schema_version` is required and validated.
- [ ] Local TOML loading uses `tomllib`.
- [ ] `ConfigError` includes useful path/key context.
- [ ] Unknown keys fail at every level.
- [ ] Required keys/sections fail when missing.
- [ ] Primitive types are strictly checked.
- [ ] Booleans are not silently accepted as numbers.
- [ ] Scenario ID/description/seed validate.
- [ ] Bundled file stem matches scenario ID.
- [ ] Raw and resolved config types are distinct/clear.
- [ ] Degrees convert to radians.
- [ ] Seconds/cadences convert to integer ticks.
- [ ] Defaults are explicit in resolved config.
- [ ] Resolved config is immutable.
- [ ] Initial state/vehicle cross-validation passes.
- [ ] Sensor/controller dependencies validate.
- [ ] Controller/actuator config validates.
- [ ] Mission threshold/counter config validates.
- [ ] Fault definitions/targets/timing validate.
- [ ] No-op fault configs are rejected.
- [ ] Validation limits/expected outcome parse.
- [ ] `simulator_error` cannot be an expected success outcome.
- [ ] Canonical resolved-config conversion exists.
- [ ] Stable SHA-256 config digest exists.
- [ ] Source path/comments/formatting do not affect digest.
- [ ] One seed derives dedicated RNG streams in fixed scheme.
- [ ] Every run constructs fresh components.
- [ ] `run_scenario(config, artifact_root=None)` exists.
- [ ] `run_scenario_file(path, ...)` exists.
- [ ] CLI/tests can share the same runner.
- [ ] Scenario discovery exists and is deterministic.
- [ ] Five curated scenario TOMLs exist.
- [ ] Nominal scenario uses the complete real stack.
- [ ] Four fault scenarios contain real typed faults.
- [ ] New supported scenario requires no engine edit.
- [ ] Config errors happen before tick zero.
- [ ] Domain outcomes remain structured results.
- [ ] Simulation errors remain distinct.
- [ ] Runner contains no domain equations.
- [ ] Runner contains no scenario-name branching.
- [ ] Runner delegates telemetry persistence.
- [ ] Runner delegates validation calculations.
- [ ] Tests can avoid repository artifact pollution.
- [ ] Reproducibility tests pass.
- [ ] Scenario end-to-end tests pass after Features 09/10 integrate.
- [ ] Entire runner works locally, offline, and headlessly.

---

# Open Questions

1. **[Open Question] What final tuned values belong in the five bundled scenarios?**  
   Placeholder controller/vehicle/fault values must be replaced only after the closed-loop system is stable.

2. **[Open Question] Should the final raw field names preserve short source examples (`x`, `dt`, `max_time`) or use explicit unit suffixes everywhere?**  
   Recommended: preserve `dt`/`max_time` as documented seconds, use explicit unit suffixes for physical fields.

3. **[Open Question] Should `load_scenario(...)` return `ScenarioConfig` or explicitly named `ResolvedScenarioConfig`?**  
   Recommended: explicit resolved name internally/publicly for clarity.

4. **[Open Question] Should `faults` be required as an explicit empty array for nominal, or optional?**  
   Recommended: optional, normalized to empty tuple.

5. **[Open Question] Should config warnings exist as structured data?**  
   Useful examples include controller command bounds larger than actuator bounds. Do not add a complex warning system unless needed.

6. **[Open Question] Should full scenario files remain self-contained permanently?**  
   Recommended for MVP. Revisit only if duplication causes real errors.

7. **[Open Question] What exact supported seed range should be documented?**  
   Recommended unsigned 64-bit range.

8. **[Open Question] What tolerance should time-to-tick alignment use?**  
   It must tolerate normal decimal representation without permitting materially ambiguous timing.

9. **[Open Question] Should scenario discovery validate complete configs or read only metadata?**  
   Recommended complete validation because the curated set is small.

10. **[Open Question] Should the `external_disturbance` TOML be included?**  
    Only after the first five are stable and tested.

11. **[Open Question] Should Feature 08 implement a minimal campaign helper?**  
    Recommended defer; a campaign is a simple later loop over `run_scenario`.

12. **[Open Question] What exact `RunResult` fields should be available before Feature 09/10 are implemented?**  
    Keep the final shape forward-compatible and avoid temporary public APIs that will immediately change.

13. **[Open Question] Does `artifact_root=None` mean no persistence or default `runs/` persistence?**  
    Recommended final CLI defaults to `runs/`; tests explicitly disable or use `tmp_path`. Lock this with Feature 09.

14. **[Open Question] Should the config digest include package/schema version metadata?**  
    It includes schema version. Source-code revision should likely be separate run metadata.

15. **[Open Question] What exact expected outcomes should each fault scenario declare?**  
    They must be determined from intended validation behavior rather than assumed from fault name.

---

# Move On When

- [ ] A valid scenario loads into immutable typed resolved config.
- [ ] Invalid keys/types/units/cross-field relationships fail before runtime.
- [ ] Every time-based setting has deterministic tick semantics.
- [ ] One scenario seed creates reproducible independent RNG streams.
- [ ] The same runner powers tests and eventual CLI.
- [ ] Every run starts with fresh subsystem state.
- [ ] New supported scenarios require only TOML.
- [ ] Five curated scenarios are present and understandable.
- [ ] Scenario digest/resolved config make runs reproducible.
- [ ] The reviewer demo path is one local command.
- [ ] Runner clearly demonstrates application architecture and configuration discipline.
- [ ] Telemetry, validation, visualization, polished CLI, and campaign behavior remain separate features.
- [ ] No unnecessary SaaS, database, network, config framework, inheritance engine, or cloud system has been added.
- [ ] The scope remains finishable and ready for Feature 09 — Telemetry & Event Logging.
