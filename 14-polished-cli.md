# Feature 14 — Polished CLI

> **Project:** AstraLoop — Python Software-in-the-Loop Flight Control & Validation System  
> **Feature:** Polished CLI  
> **Document path:** `docs/features/14-polished-cli.md`  
> **Status:** Implementation specification  
> **Primary goal:** Provide a small, explicit, testable command-line interface that lets a reviewer discover and run local scenarios with one command, immediately understand the actual mission outcome and scenario-contract result, locate generated artifacts, and receive actionable configuration/runtime errors without exposing internal tracebacks or duplicating application logic.

---

## Scope Boundary

**[Confirmed]** AstraLoop is a local engineering tool whose primary user interface is:

```text
CLI
+
generated diagnostic plot
+
saved run directory
```

It is not a web application or dashboard.

**[Confirmed]** The selected stack is:

```text
standard-library argparse
Rich for terminal presentation
```

`argparse` is preferred over Typer or another CLI framework because AstraLoop needs only a few commands and should remain dependency-light and explicit.

**[Confirmed]** The package entry point is conceptually:

```toml
[project.scripts]
astraloop = "astraloop.cli:main"
```

**[Confirmed]** The preferred run command is:

```bash
uv run astraloop run scenarios/nominal.toml
```

The module invocation must also work:

```bash
uv run python -m astraloop run scenarios/nominal.toml
```

**[Confirmed]** Bundled-scenario discovery is exposed through:

```bash
uv run astraloop list-scenarios
```

**[Confirmed]** The CLI must call the same application service used by tests:

```python
run_scenario(...)
```

or:

```python
run_scenario_file(...)
```

The CLI must not contain an alternate simulation pathway.

**[Confirmed]** The CLI must clearly distinguish:

```text
configuration/user-input error
simulator/internal error
mission validation failure
expected controlled abort
expected validation failure
successful expected mission
```

A hard landing or controlled abort must not look like a Python crash.

**[Confirmed]** Suggested primary exit-code mapping is:

```text
0  command completed successfully;
   scenario matched its expected outcome

1  completed scenario did not match its expected contract

2  configuration or user-input error

3  simulator/internal/runtime/artifact error
```

**[Confirmed]** The UX goal is that a reviewer can:

```text
install
run
understand the result
find artifacts
```

without reading source code first.

**[Decision]** Feature 14 owns the **terminal command and presentation layer**.

It owns:

- CLI entry points;
- `argparse` parser construction;
- command dispatch;
- global help;
- global version output;
- `run` command arguments;
- `list-scenarios` command arguments;
- default artifact-root policy for CLI runs;
- optional no-artifact execution mode;
- Rich consoles/renderables;
- scenario-list table;
- run-summary table/panels;
- validation-check presentation;
- fault-summary presentation;
- artifact-path presentation;
- user-facing error rendering;
- exit-code mapping;
- optional debug traceback mode;
- `KeyboardInterrupt` behavior;
- color/no-color behavior;
- unit and integration tests for parsing, rendering, dispatch, and exit codes.

It does **not** own:

- TOML parsing or configuration validation;
- scenario discovery implementation;
- runtime construction;
- simulation execution;
- numerical integration;
- mission validation formulas;
- telemetry recording;
- artifact writing;
- plot generation;
- campaign orchestration;
- README/documentation content;
- a desktop/web interface.

The CLI translates arguments into calls to existing services and translates structured results/errors into readable terminal output.

---

# 1. Feature Overview

## Feature name

**Polished CLI**

---

## One-sentence description

**[Decision]** Implement a concise `argparse` and Rich command-line interface that exposes scenario discovery and one-command execution, reports actual versus expected mission behavior, maps structured outcomes to stable exit codes, and points directly to local artifacts.

---

## Detailed description

AstraLoop has deep technical internals, but a reviewer should not need to understand the package structure before running it.

The primary flow is:

```text
terminal command
      |
      v
argparse
      |
      v
CLI command handler
      |
      +--> discover_scenarios(...)
      |
      +--> run_scenario_file(...)
      |
      v
structured descriptors/results/errors
      |
      v
Rich renderers
      |
      v
human-readable terminal output
      |
      v
stable process exit code
```

The CLI is a thin adapter around existing application services.

It should contain no:

- physics;
- controller behavior;
- fault logic;
- validation criteria;
- direct CSV/JSON writing;
- Matplotlib plotting code.

---

## Required MVP command set

**[Decision]** The required CLI has exactly two subcommands:

```text
run
list-scenarios
```

It also supports:

```text
--help
--version
```

This is enough for a complete reviewer workflow.

---

## Optional MVP+ commands

The project blueprint mentions:

```text
campaign
plot
```

as possible commands.

**[Decision]** These are not required for Feature 14 MVP completion.

### Optional `campaign`

Could run every scenario in a directory sequentially.

Do not add until:

- all single-scenario behavior is stable;
- exit-code aggregation is defined;
- output remains readable;
- implementation remains a thin loop around `run_scenario`.

No concurrency, worker pool, retries, or distributed execution.

### Optional `plot`

Could regenerate a plot from an existing completed run.

Do not add until a reliable run-directory reader exists.

Automatic plot generation during `run` already satisfies the primary artifact contract.

---

## Required invocation forms

### Installed script

```bash
uv run astraloop --help
uv run astraloop list-scenarios
uv run astraloop run scenarios/nominal.toml
```

### Module

```bash
uv run python -m astraloop --help
uv run python -m astraloop list-scenarios
uv run python -m astraloop run scenarios/nominal.toml
```

Both entry paths call the same `main()`.

---

## Entry-point files

Recommended:

```text
src/astraloop/cli.py
src/astraloop/__main__.py
```

`__main__.py`:

```python
from astraloop.cli import main

raise SystemExit(main())
```

Project script:

```toml
[project.scripts]
astraloop = "astraloop.cli:main"
```

Because Python project-script entry points call the function directly, `main()` must return an integer exit code rather than unconditionally raising.

---

## Main boundary

Recommended:

```python
def main(
    argv: Sequence[str] | None = None,
) -> int:
    ...
```

For stronger testability, split:

```python
def run_cli(
    argv: Sequence[str],
    *,
    console: Console,
    error_console: Console,
) -> int:
    ...
```

`main()` creates consoles and delegates.

---

## Parser boundary

Recommended:

```python
def build_parser() -> argparse.ArgumentParser:
    ...
```

Parser construction must not:

- read files;
- discover scenarios;
- execute a run;
- import Matplotlib;
- create artifacts.

It only defines the command grammar.

---

## Command-handler boundary

Recommended:

```python
def handle_run(
    args: argparse.Namespace,
    *,
    console: Console,
    error_console: Console,
) -> int:
    ...
```

```python
def handle_list_scenarios(
    args: argparse.Namespace,
    *,
    console: Console,
    error_console: Console,
) -> int:
    ...
```

The handlers call Feature 08 services.

---

## CLI command grammar

Recommended help shape:

```text
usage: astraloop [-h] [--version] [--debug]
                 {run,list-scenarios} ...

AstraLoop — local Python software-in-the-loop flight-control
simulation and validation.

commands:
  run             Run one TOML scenario.
  list-scenarios  List available local scenarios.

options:
  -h, --help      Show help and exit.
  --version       Show AstraLoop version and exit.
  --debug         Show full traceback for unexpected errors.
```

`--debug` may be global-only and must appear before the subcommand under normal argparse behavior unless deliberately supported in each parser.

---

## Global options

### `--help`

Standard argparse help.

Exit:

```text
0
```

---

### `--version`

Displays:

```text
AstraLoop <version>
```

Version source:

- installed package metadata;
- one project version constant as fallback only if needed.

Recommended:

```python
importlib.metadata.version("astraloop")
```

Do not duplicate version strings across multiple files.

Exit:

```text
0
```

---

### `--debug`

Default:

```text
false
```

When disabled:

- known errors show concise actionable messages;
- unexpected exceptions show a concise internal-error panel;
- no traceback is printed.

When enabled:

- full traceback is printed to stderr after the concise error heading;
- exit-code mapping does not change.

This is a developer aid, not a different execution path.

---

## `run` command

Required shape:

```bash
astraloop run SCENARIO
```

Example:

```bash
uv run astraloop run scenarios/nominal.toml
```

### Positional argument

```text
SCENARIO
```

Type:

```text
local .toml path
```

The CLI passes it to Feature 08.

The CLI does not parse the file itself.

---

## `run` command options

### `--artifact-root PATH`

Default:

```text
runs
```

Example:

```bash
uv run astraloop run scenarios/nominal.toml \
  --artifact-root output/runs
```

Meaning:

- pass the path as artifact root to the scenario runner;
- Feature 09 creates the scenario/timestamp/digest run directory below it.

The CLI must not construct the final run-directory name.

---

### `--no-artifacts`

Example:

```bash
uv run astraloop run scenarios/nominal.toml \
  --no-artifacts
```

Meaning:

```text
artifact_root=None
```

The run still:

- simulates;
- records in memory;
- validates;
- returns a summary.

It does not persist CSV/JSON/PNG.

Use cases:

- quick local validation;
- debugging;
- automated scripts;
- demonstrating the in-memory application boundary.

---

### Mutual exclusion

`--artifact-root` and `--no-artifacts` must be mutually exclusive.

Argparse should reject:

```bash
astraloop run scenario.toml \
  --artifact-root runs \
  --no-artifacts
```

Exit:

```text
2
```

---

## Deliberately omitted `run` options

Do not add for MVP:

```text
--seed
--dt
--max-time
--fault
--controller-gain
--expected-outcome
```

### Why

The scenario TOML is the reproducible source of run configuration.

Ad-hoc command-line overrides would:

- create hidden resolved configurations;
- complicate artifact provenance;
- make commands harder to reproduce;
- duplicate Feature 08 validation.

To change a run, edit/copy a scenario file.

---

## Optional future run options

Potential only after demonstrated need:

```text
--quiet
--json
--open-plot
```

### Recommendation

Do not add them to MVP.

- `--quiet` is unnecessary for a concise summary.
- `--json` duplicates `summary.json`.
- `--open-plot` adds platform-specific process-launch behavior.

---

## `list-scenarios` command

Required shape:

```bash
astraloop list-scenarios
```

Default discovery root:

```text
scenarios
```

---

## `list-scenarios` option

### `--root PATH`

Example:

```bash
uv run astraloop list-scenarios \
  --root scenarios/custom
```

The CLI passes the root to:

```python
discover_scenarios(root)
```

Recommended default:

```python
Path("scenarios")
```

---

## Scenario-list table

Required columns:

```text
ID
Expected
Faults
Description
Path
```

Example:

```text
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ID                 ┃ Expected         ┃ Faults ┃ Description        ┃ Path                         ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ nominal            │ PASS             │ 0      │ Nominal flight...  │ scenarios/nominal.toml       │
│ altimeter_freeze   │ CONTROLLED_ABORT │ 1      │ Altimeter...       │ scenarios/altimeter_freeze...│
└────────────────────┴──────────────────┴────────┴────────────────────┴──────────────────────────────┘
```

The exact border rendering is Rich-controlled.

---

## Scenario ordering

Use Feature 08's deterministic discovery order.

The CLI must not reorder with locale-dependent rules.

Recommended final order:

```text
lexicographic by scenario ID
```

unless the descriptor service already guarantees another documented order.

---

## Empty scenario list

Required message:

```text
No scenario TOML files found under scenarios/custom/.

Add a .toml scenario or choose another directory with:
  astraloop list-scenarios --root <path>
```

The source blueprint also suggests pointing the user toward `list-scenarios`; because the user is already in that command, the correction should instead explain how to add/select a root.

**Decision]** Empty discovery is a user-input/discovery error.

Exit:

```text
2
```

Reason:

The requested command could not perform its purpose due to the supplied/default directory contents.

---

## Missing scenario root

Feature 08 may raise ConfigError or a discovery-specific configuration error.

Render as:

```text
CONFIGURATION ERROR
Scenario directory does not exist: <path>
```

Exit:

```text
2
```

---

## CLI presentation principles

### 1. Result category must be obvious

The first visible result line/panel must communicate:

```text
SCENARIO PASS
```

or:

```text
SCENARIO FAIL
```

This refers to:

```text
ValidationResult.scenario_passed
```

not merely:

```text
mission_succeeded
```

---

### 2. Actual and expected outcomes are both visible

Required:

```text
Actual outcome
Expected outcome
```

This prevents an expected abort from looking like a broken simulation.

---

### 3. Mission and scenario concepts remain distinct

Example:

```text
Scenario contract: PASS
Actual mission:    CONTROLLED_ABORT
Expected mission:  CONTROLLED_ABORT
```

An expected controlled abort must:

- use exit code 0;
- visually show scenario PASS;
- still label the mission as controlled abort.

---

### 4. Artifacts are easy to find

If persisted:

```text
Artifacts: <final run directory>
```

Then list important relative/absolute paths.

If not persisted:

```text
Artifacts: not written (--no-artifacts)
```

---

### 5. Errors are actionable

Show:

- category;
- concise message;
- offending path/field where available;
- one next action/hint when useful.

Do not show a traceback by default.

---

### 6. No fake progress UI

Do not use:

- simulated percentages;
- indeterminate spinner that remains for negligible runs;
- wall-clock progress tied to simulation time;
- per-tick console output.

A run should print a concise start line, execute, and print the final summary.

---

## Terminal output streams

### stdout

Use for:

- help/version;
- scenario table;
- successful completed-run summaries;
- scenario-contract mismatch summaries;
- artifact paths.

### stderr

Use for:

- configuration/user errors;
- simulator/internal errors;
- artifact/plot errors;
- unexpected exceptions;
- keyboard interruption message.

This supports shell redirection.

---

## Rich usage

Rich is presentation-only.

Recommended:

```python
Console()
```

for stdout and:

```python
Console(stderr=True)
```

for stderr.

Use Rich:

- `Panel`;
- `Table`;
- styled `Text`;
- paths;
- concise rule/header if useful.

Do not use Rich:

- to own command parsing;
- to store application state;
- to calculate outcomes;
- to catch domain errors.

---

## Color policy

**[Decision]** Let Rich automatically disable color when stdout/stderr is not a terminal.

Also honor:

```text
NO_COLOR
```

through Rich/default console behavior or an explicit project wrapper.

Do not require color to interpret the output.

Every result also includes plain text:

```text
PASS
FAIL
CONTROLLED_ABORT
VALIDATION_FAIL
```

---

## Unicode policy

Rich borders may use Unicode in capable terminals.

The result must remain understandable when:

- redirected to a file;
- color is disabled;
- terminal renders plain text.

Do not use emoji as the sole status indicator.

Recommended:

```text
PASS
FAIL
ERROR
```

rather than relying on icons.

---

## Terminal width

Rich should adapt to terminal width.

Requirements:

- scenario descriptions wrap;
- paths wrap/fold;
- metric names remain visible;
- no fixed 200-column assumption.

For tests, inject a deterministic width such as:

```text
120
```

---

## Start message

Recommended:

```text
Running scenario: nominal
Source: scenarios/nominal.toml
Seed: 42
```

But seed is only known after loading.

**Decision]** The CLI may print a simple pre-load line:

```text
Running scenario: scenarios/nominal.toml
```

Then display resolved scenario ID/seed in the final summary.

To keep output concise, it is acceptable to print only the final summary for fast runs.

---

## Run-result summary

Recommended top section:

```text
SCENARIO PASS

Scenario            nominal
Actual outcome      PASS
Expected outcome    PASS
Final mission state LANDED
Seed                42
Final time          31.17 s
Config digest       a1b2c3d4
```

For an expected abort:

```text
SCENARIO PASS

Scenario            altimeter_freeze
Actual outcome      CONTROLLED_ABORT
Expected outcome    CONTROLLED_ABORT
Final mission state ABORT
Seed                42
Final time          20.84 s
Config digest       c4d5e6f7
```

For mismatch:

```text
SCENARIO FAIL

Scenario            nominal
Actual outcome      VALIDATION_FAIL
Expected outcome    PASS
...
```

---

## Core metric table

For a landed run:

```text
Check                         Actual      Limit       Result
Landing vertical speed       1.31 m/s    <= 2.00     PASS
Horizontal landing error     2.18 m      <= 5.00     PASS
Landing pitch error          1.84 deg    <= 5.00     PASS
Mission transition history   valid       required    PASS
```

Use Feature 10 `ValidationCheck` records.

Do not recalculate values.

---

## Abort metric table

For a controlled abort:

```text
Check                         Result
Landing vertical speed       N/A
Horizontal landing error     N/A
Landing pitch error          N/A
Mission transition history   PASS
Expected outcome             PASS
```

Do not display missing values as zero.

---

## Failed-check detail

If:

```text
scenario_passed == false
```

show a concise failed-check/failure-reasons section.

Example:

```text
Failed checks
- landing vertical speed 2.31 m/s exceeded 2.00 m/s
- expected PASS but actual outcome was VALIDATION_FAIL
```

Do not display every passing internal check by default.

---

## Fault summary

For all runs:

```text
Configured faults 0
Activated faults  0
Pending faults    0
```

For fault run:

```text
Configured faults 1
Activated faults  1
Pending faults    0

Activated:
- freeze_altimeter_01
```

If a configured fault did not activate:

```text
Pending:
- freeze_altimeter_01
```

This is especially important when a scenario fails because the intended fault was never exercised.

---

## Artifact summary

If artifacts exist:

```text
Artifacts
Run directory       runs/nominal/<timestamp>-<digest>/
Telemetry           .../telemetry.csv
Events              .../events.json
Resolved config     .../resolved_config.json
Summary             .../summary.json
Diagnostic plot     .../flight_plot.png
```

Use `RunArtifacts` paths supplied by Feature 09.

Do not construct filenames by assumption if an optional/error bundle omits a file.

---

## Diagnostic SimulationError artifact summary

If a simulator error occurs after a diagnostic bundle is written:

```text
SIMULATION ERROR

<concise message>

Diagnostic artifacts:
  <path>
```

Then exit 3.

The CLI must preserve the error category even if diagnostics succeeded.

---

## Result styling

Recommended semantic styles:

```text
scenario PASS          bold green
scenario FAIL          bold red
controlled abort       bold yellow
validation fail        red/yellow depending context
configuration error    bold red
simulation error       bold red
artifact paths         cyan/blue
muted labels           dim
```

Exact style names are centralized.

Never infer result solely from color.

---

## Exit-code contract

### Exit 0 — Command success

Use when:

- help/version displayed;
- scenarios successfully listed and at least one exists;
- `run` completed and `validation.scenario_passed is True`.

This includes actual outcomes:

```text
PASS
CONTROLLED_ABORT
VALIDATION_FAIL
```

when that actual outcome matches the configured expected outcome and all scenario-contract checks pass.

---

### Exit 1 — Scenario-contract mismatch

Use when:

- simulation completed normally;
- `ValidationResult.scenario_passed is False`.

Examples:

- expected PASS but actual validation failure;
- expected controlled abort but actual PASS;
- configured fault did not activate;
- unexpected fault event;
- transition artifact inconsistency represented as a completed validation result.

This is not a configuration or Python-runtime error.

---

### Exit 2 — User/configuration error

Use for:

- argparse syntax/usage error;
- missing positional scenario;
- conflicting options;
- file not found;
- wrong extension;
- malformed TOML;
- unknown config key;
- invalid config value;
- invalid scenario root;
- no scenarios found;
- unsupported schema version.

---

### Exit 3 — Simulator/internal/artifact error

Use for:

- SimulationError;
- ArtifactError;
- PlotError that prevents required run completion;
- TelemetryError;
- ValidationError due to structurally unusable completed data;
- unexpected internal exception.

---

### Exit 130 — Interrupted

Use for:

```text
KeyboardInterrupt
```

This follows common shell convention:

```text
128 + SIGINT(2) = 130
```

Print:

```text
Run cancelled by user.
```

No traceback unless debug mode is specifically desired; interruption normally needs none.

---

## Argparse exit behavior

Standard argparse calls:

```text
SystemExit(0)
```

for help and:

```text
SystemExit(2)
```

for usage errors.

Two valid implementation options:

### Option A — Standard argparse behavior

`main()` allows argparse `SystemExit` for help/usage.

Console-script process exit remains correct.

Unit tests assert `SystemExit`.

### Option B — Custom parser subclass

Override `exit/error` so the internal CLI function returns codes.

**[Decision]** Prefer **Option A**.

It is conventional and avoids custom parser complexity.

Command handlers and application outcomes still return explicit integer codes.

---

## Known exception mapping

Recommended central structure:

```python
def execute_command(...) -> int:
    try:
        ...
    except ConfigError as exc:
        render_config_error(...)
        return 2
    except (
        SimulationError,
        TelemetryError,
        ValidationError,
        ArtifactError,
        PlotError,
    ) as exc:
        render_runtime_error(...)
        return 3
    except KeyboardInterrupt:
        render_cancelled(...)
        return 130
    except Exception as exc:
        render_unexpected_error(...)
        if debug:
            render_traceback(...)
        return 3
```

Avoid broad `except Exception` inside domain modules.

The broad final catch is appropriate only at the outer CLI boundary to prevent a raw traceback in normal reviewer use.

---

## Debug traceback

Rich can render a traceback, or Python's `traceback` module can print it.

**Decision]** Use standard traceback or Rich traceback only at CLI boundary.

Requirements:

- shown only with `--debug`;
- sent to stderr;
- does not replace concise error heading;
- does not change exit code;
- does not expose a traceback for ordinary validation mismatch.

---

## Configuration error rendering

Example:

```text
CONFIGURATION ERROR

scenarios/velocity_bias.toml
faults[0].target:
Unknown sensor 'vertical_speed'.

Expected one of:
altimeter, vertical_velocity, horizontal_position,
horizontal_velocity, attitude, gyro
```

Use the structured `ConfigError` path/field data.

Do not parse the exception string if structured fields are available.

---

## File-not-found hint

Example:

```text
CONFIGURATION ERROR

Scenario file not found:
  scenarios/nominl.toml

List bundled scenarios with:
  astraloop list-scenarios
```

Do not automatically guess and run another file.

A "did you mean" suggestion may be shown if Feature 08 provides one, but it must never silently substitute.

---

## Validation mismatch rendering

Validation mismatch is a completed run.

Render the normal run summary first.

Then show:

```text
Scenario contract did not match the configured expectation.
```

Exit 1.

Artifacts remain available and should be displayed.

---

## Expected failure rendering

Example:

```text
SCENARIO PASS

Actual outcome   VALIDATION_FAIL
Expected outcome VALIDATION_FAIL
```

Add a small explanatory line:

```text
The mission failed its physical criteria as expected by this scenario.
```

For controlled abort:

```text
The flight software entered the expected controlled ABORT state.
```

Do not call it "mission success."

---

## Version lookup failure

In editable/source environments, package metadata should still normally exist through `uv run`.

If version lookup fails:

- use a small local fallback such as `"unknown"`;
- `--version` remains functional;
- do not crash.

The fallback should not duplicate a hard-coded release number in many files.

---

## Logging

The CLI may configure standard logging level.

MVP:

- normal runs: warnings/errors only;
- `--debug`: debug logging may be enabled.

**Decision]** Do not add `--verbose` separately if `--debug` already exists.

Core modules do not print directly.

---

## Shell and platform behavior

Support:

- Windows PowerShell/cmd;
- macOS/Linux shells.

Use `pathlib.Path`.

Do not rely on:

- ANSI-only manual codes;
- shell-specific quoting;
- `os.system`;
- POSIX-only path syntax.

Rich handles terminal styling.

---

## Current working directory

Documented commands are run from repository root.

The CLI accepts explicit paths.

**Decision]** Do not search parent directories magically for `scenarios/`.

Default:

```text
list-scenarios --root scenarios
```

is relative to current working directory.

A missing root produces a clear error.

This keeps path behavior predictable.

---

## Symlinks

No special symlink policy is required.

Use normal local filesystem semantics.

Feature 08/09 path safety rules remain responsible for artifact-root containment and scenario validation.

---

## Result duration

Do not print wall-clock execution duration as a correctness metric.

The useful duration is:

```text
simulation final time
```

Wall-clock runtime may be added as a debug/performance metric later, but it must be clearly labeled.

---

## No live per-tick logging

Do not print:

- telemetry rows;
- controller commands every tick;
- sensor readings every tick;
- RK4 stages.

Debugging uses saved artifacts and logging.

The recruiter-facing command remains concise.

---

## No confirmation prompt

Running a scenario does not require interactive confirmation.

Artifacts never overwrite existing runs, so there is no destructive prompt.

---

## No input prompts

All required input comes from arguments/config files.

This ensures:

- scripts work;
- tests work;
- CI works;
- command behavior is reproducible.

---

## Recruiter demo timing

The blueprint recommends a 60–90 second demo.

CLI support:

```text
1. run nominal
2. show scenario PASS and plot path
3. run altimeter freeze
4. show fault outcome and plot path
5. run pytest separately
```

The CLI should not flood the terminal and consume the entire demo time.

---

## Priority

**P1 — Required portfolio interface**

The underlying simulation can work without the CLI, but the repository is not portfolio-ready until a reviewer has a one-command demo and readable results.

---

## Complexity

**Medium**

`argparse` is small.

The main complexity lies in:

- result taxonomy;
- error mapping;
- output readability;
- testable console behavior;
- keeping presentation separate from application services.

---

# 2. User / Demo Flow

## Happy path — list scenarios

1. User runs:

```bash
uv run astraloop list-scenarios
```

2. Parser dispatches to list handler.
3. Feature 08 discovers and validates bundled scenarios.
4. Rich table displays deterministic list.
5. Command exits 0.

---

## Happy path — nominal run

1. User runs:

```bash
uv run astraloop run scenarios/nominal.toml
```

2. CLI passes:

```text
scenario path
artifact root = runs
```

to Feature 08.
3. Scenario loads/resolves.
4. Simulation runs.
5. Telemetry, validation, and plot are finalized.
6. CLI receives `RunResult`.
7. Output shows:
   - scenario PASS;
   - actual PASS;
   - expected PASS;
   - final LANDED;
   - landing metrics;
   - artifact paths.
8. Command exits 0.

---

## Happy path — expected controlled abort

1. User runs a fault scenario.
2. Simulation enters ABORT.
3. Validation says:

```text
actual = CONTROLLED_ABORT
expected = CONTROLLED_ABORT
scenario_passed = true
```

4. CLI displays scenario PASS and controlled-abort explanation.
5. Command exits 0.

---

## Happy path — expected validation failure

1. Scenario intentionally causes a hard/invalid landing outcome.
2. Validation says:

```text
actual = VALIDATION_FAIL
expected = VALIDATION_FAIL
scenario_passed = true
```

3. CLI displays scenario PASS while clearly stating the mission did not satisfy physical criteria.
4. Command exits 0.

---

## Scenario mismatch

1. Simulation completes.
2. Actual outcome differs from expected or another scenario contract fails.
3. CLI displays normal result and artifacts.
4. Failed reasons are shown.
5. Exit 1.

---

## Configuration error

1. User supplies malformed/invalid scenario.
2. Feature 08 raises ConfigError before tick zero.
3. CLI displays configuration error and hint.
4. No normal run artifact exists.
5. Exit 2.

---

## Simulation error

1. Runtime invariant fails.
2. Feature 09 may save diagnostic artifacts.
3. SimulationError reaches CLI.
4. CLI shows concise simulator error and diagnostic path if known.
5. Exit 3.

---

## No-artifact run

1. User runs:

```bash
uv run astraloop run scenarios/nominal.toml \
  --no-artifacts
```

2. Full simulation and validation execute.
3. Summary displays normally.
4. Artifact section says not written.
5. Exit follows scenario contract.

---

## Empty list

1. User runs list command on empty directory.
2. Discovery returns empty.
3. CLI explains no TOMLs were found.
4. Exit 2.

---

# 3. UX / UI Requirements

## Main CLI screens

### 1. Root help

Explains project and commands.

### 2. Run help

Explains path and artifact options.

### 3. List-scenarios help

Explains root option.

### 4. Scenario table

Lists available scenarios.

### 5. Run summary

Displays contract, outcomes, metrics, faults, artifacts.

### 6. Error panel

Displays category/message/hint.

No other screens are required.

---

## Root help example

```text
AstraLoop — local Python software-in-the-loop flight-control
simulation and validation.

Run a bundled scenario:
  astraloop run scenarios/nominal.toml

Discover scenarios:
  astraloop list-scenarios
```

Use argparse `epilog` with `RawDescriptionHelpFormatter` if formatting is needed.

---

## `run --help` example

```text
usage: astraloop run [-h]
                     [--artifact-root PATH | --no-artifacts]
                     SCENARIO

Run one local TOML flight scenario.

positional arguments:
  SCENARIO              Path to a scenario .toml file.

options:
  -h, --help            Show help and exit.
  --artifact-root PATH  Root directory for immutable run artifacts
                        (default: runs).
  --no-artifacts        Run and validate entirely in memory.
```

---

## `list-scenarios --help` example

```text
usage: astraloop list-scenarios [-h] [--root PATH]

List valid local TOML scenarios.

options:
  -h, --help   Show help and exit.
  --root PATH  Scenario directory (default: scenarios).
```

---

## Accessibility

- result words are explicit;
- no color-only meaning;
- concise language;
- units displayed;
- paths are selectable text;
- no moving spinner required;
- redirected output remains readable.

---

## Error-message content

Every known error panel contains:

```text
category
message
context/path/field if available
optional corrective action
```

Do not expose implementation class names unless useful.

---

# 4. Data Requirements

## Inputs

### Global

```text
argv
environment terminal/color context
package version
```

### `run`

```text
scenario Path
artifact_root Path | None
debug bool
```

### `list-scenarios`

```text
root Path
debug bool
```

---

## Outputs

### Process

```text
stdout text/renderables
stderr text/renderables
integer exit code
```

### No new domain data

CLI should not create a second result model.

It consumes:

```text
ScenarioDescriptor
RunResult
ValidationResult
RunArtifacts
structured exceptions
```

---

## Presentation view models

Optional small presentation-only dataclasses are acceptable:

```python
@dataclass(frozen=True)
class RunSummaryView:
    ...
```

But do not duplicate all domain records.

Prefer renderer functions that consume existing immutable results.

---

## CLI style constants

Centralized:

```text
STYLE_SUCCESS
STYLE_FAILURE
STYLE_WARNING
STYLE_ERROR
STYLE_PATH
STYLE_MUTED
```

No ANSI codes embedded manually.

---

# 5. Logic Requirements

## Rule 1 — argparse owns parsing

---

## Rule 2 — Rich owns presentation only

---

## Rule 3 — CLI uses the production scenario runner

---

## Rule 4 — CLI contains no simulation logic

---

## Rule 5 — CLI contains no validation formulas

---

## Rule 6 — CLI contains no artifact serialization

---

## Rule 7 — CLI contains no plotting logic

---

## Rule 8 — Core required commands are run and list-scenarios

---

## Rule 9 — campaign/plot are optional MVP+

---

## Rule 10 — scenario path is positional

---

## Rule 11 — CLI defaults artifact root to runs

---

## Rule 12 — --no-artifacts maps to None

---

## Rule 13 — --artifact-root and --no-artifacts conflict

---

## Rule 14 — no ad-hoc simulation config overrides exist in MVP

---

## Rule 15 — list root defaults to scenarios

---

## Rule 16 — scenario ordering is deterministic

---

## Rule 17 — empty scenario list is actionable

---

## Rule 18 — actual and expected outcomes are always distinct fields

---

## Rule 19 — scenario_passed controls success exit code

---

## Rule 20 — mission_succeeded does not control process success alone

---

## Rule 21 — expected controlled abort exits 0

---

## Rule 22 — expected validation failure exits 0

---

## Rule 23 — scenario mismatch exits 1

---

## Rule 24 — user/config errors exit 2

---

## Rule 25 — simulator/internal/artifact errors exit 3

---

## Rule 26 — interruption exits 130

---

## Rule 27 — help/version exit 0

---

## Rule 28 — known errors have no traceback by default

---

## Rule 29 — --debug may show traceback

---

## Rule 30 — validation mismatch never shows traceback

---

## Rule 31 — errors go to stderr

---

## Rule 32 — completed summaries go to stdout

---

## Rule 33 — no fake progress percentage exists

---

## Rule 34 — no per-tick output exists

---

## Rule 35 — no input prompts exist

---

## Rule 36 — no confirmation prompts exist

---

## Rule 37 — output works without color

---

## Rule 38 — output works when redirected

---

## Rule 39 — terminal width is adaptive

---

## Rule 40 — units are visible

---

## Rule 41 — N/A is explicit

---

## Rule 42 — configured/activated/pending faults are visible

---

## Rule 43 — artifact paths use supplied result metadata

---

## Rule 44 — missing optional artifact is not fabricated

---

## Rule 45 — CLI does not overwrite artifacts

---

## Rule 46 — __main__ and script entry points share main

---

## Rule 47 — main returns integer for command outcomes

---

## Rule 48 — parser help text is testable

---

## Rule 49 — platform paths use pathlib

---

## Rule 50 — no GUI/browser/network/database is introduced

---

## Parser pseudocode

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="astraloop",
        description=(
            "AstraLoop — local Python software-in-the-loop "
            "flight-control simulation and validation."
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"AstraLoop {get_version()}",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show tracebacks for internal errors.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    run_parser = subparsers.add_parser(
        "run",
        help="Run one TOML scenario.",
    )
    run_parser.add_argument(
        "scenario",
        type=Path,
    )

    artifact_group = (
        run_parser.add_mutually_exclusive_group()
    )
    artifact_group.add_argument(
        "--artifact-root",
        type=Path,
        default=Path("runs"),
    )
    artifact_group.add_argument(
        "--no-artifacts",
        action="store_true",
    )

    list_parser = subparsers.add_parser(
        "list-scenarios",
        help="List available local scenarios.",
    )
    list_parser.add_argument(
        "--root",
        type=Path,
        default=Path("scenarios"),
    )

    return parser
```

### Important default nuance

With a mutually exclusive group, `--artifact-root` having a non-None default can coexist in parsed namespace with `--no-artifacts=True`.

Handler resolves:

```python
artifact_root = (
    None
    if args.no_artifacts
    else args.artifact_root
)
```

Argparse still rejects both options explicitly supplied.

---

## Main pseudocode

```python
def main(
    argv: Sequence[str] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    console = build_console()
    error_console = build_error_console()

    return dispatch(
        args,
        console=console,
        error_console=error_console,
    )
```

---

## Dispatch pseudocode

```python
def dispatch(
    args: argparse.Namespace,
    *,
    console: Console,
    error_console: Console,
) -> int:
    try:
        match args.command:
            case "run":
                return handle_run(...)
            case "list-scenarios":
                return handle_list_scenarios(...)
            case _:
                raise CliInternalError(...)

    except ConfigError as exc:
        render_config_error(
            error_console,
            exc,
        )
        return 2

    except KeyboardInterrupt:
        error_console.print(
            "Run cancelled by user."
        )
        return 130

    except KNOWN_RUNTIME_ERRORS as exc:
        render_runtime_error(
            error_console,
            exc,
        )
        if args.debug:
            render_traceback(error_console)
        return 3

    except Exception as exc:
        render_unexpected_error(
            error_console,
            exc,
        )
        if args.debug:
            render_traceback(error_console)
        return 3
```

KeyboardInterrupt inherits from BaseException, not Exception, so catch it explicitly before broad Exception.

---

## Run-handler pseudocode

```python
def handle_run(
    args: argparse.Namespace,
    *,
    console: Console,
    error_console: Console,
) -> int:
    artifact_root = (
        None
        if args.no_artifacts
        else args.artifact_root
    )

    result = run_scenario_file(
        args.scenario,
        artifact_root=artifact_root,
    )

    render_run_result(
        console,
        result,
    )

    return (
        0
        if result.validation.scenario_passed
        else 1
    )
```

A portfolio-ready runner always supplies validation for a completed normal run.

If validation is unexpectedly missing:

```text
internal/runtime error -> exit 3
```

---

## List-handler pseudocode

```python
def handle_list_scenarios(
    args: argparse.Namespace,
    *,
    console: Console,
    error_console: Console,
) -> int:
    scenarios = discover_scenarios(
        args.root
    )

    if not scenarios:
        render_no_scenarios(
            error_console,
            root=args.root,
        )
        return 2

    render_scenario_table(
        console,
        scenarios,
    )
    return 0
```

---

## Edge cases

### No subcommand

Argparse usage error.

Exit 2.

### Unknown subcommand

Argparse usage error.

Exit 2.

### Missing scenario positional

Argparse usage error.

Exit 2.

### Both artifact options

Argparse usage error.

Exit 2.

### Relative scenario path

Pass unchanged/normalized to loader.

### Path with spaces

Works when shell quotes it.

### Scenario result has validation None

Internal error.

Exit 3.

### Actual validation fail expected validation fail

Scenario pass, exit 0.

### Actual abort expected abort

Scenario pass, exit 0.

### Final plot omitted in diagnostic bundle

Artifact renderer displays only paths present.

### Very long path

Rich wraps it.

### No color environment

Plain text remains complete.

### Output piped to file

No spinner/control characters.

### Broken pipe

**[Open Question]** Optionally handle `BrokenPipeError` gracefully.

Not required for MVP.

### Ctrl+C during simulation

Exit 130.

No normal completed artifact guarantee.

Feature 09 staging/cleanup behavior applies.

### Ctrl+C during artifact write

Staging cleanup is best effort.

Exit 130 unless an artifact exception supersedes during cleanup; preserve interruption as primary where practical.

### Unexpected exception

Concise internal error.

Exit 3.

Debug shows traceback.

---

# 6. Acceptance Criteria

## AC-01 — Installed script entry point exists

**Given** installed package  
**When** `astraloop --help` executes  
**Then** the CLI parser is invoked successfully.

---

## AC-02 — Module entry point exists

**Given** installed/source package  
**When** `python -m astraloop --help` executes  
**Then** it uses the same `main()` behavior.

---

## AC-03 — pyproject script points to CLI main

**Given** package metadata  
**When** inspected  
**Then** `[project.scripts]` maps `astraloop` to the documented function.

---

## AC-04 — main accepts optional argv

**Given** a test-supplied argument sequence  
**When** `main(argv)` is called  
**Then** it parses that sequence rather than process argv.

---

## AC-05 — Root help exits zero

**Given** `--help`  
**When** parser runs  
**Then** help is displayed and process exits 0.

---

## AC-06 — Version exits zero

**Given** `--version`  
**When** parser runs  
**Then** `AstraLoop <version>` is displayed and exit is 0.

---

## AC-07 — Version comes from package metadata

**Given** installed version metadata  
**When** version renders  
**Then** it is not independently hard-coded in multiple CLI locations.

---

## AC-08 — No subcommand exits two

**Given** bare `astraloop`  
**When** parser runs  
**Then** usage is shown and exit is 2.

---

## AC-09 — Unknown command exits two

**Given** unsupported subcommand  
**When** parser runs  
**Then** argparse reports usage error and exit 2.

---

## AC-10 — Root help lists required commands

**Given** root help  
**When** text is inspected  
**Then** `run` and `list-scenarios` appear.

---

## AC-11 — Root help includes quick usage examples

**Given** help output  
**When** inspected  
**Then** nominal run and scenario-list examples are available or clearly linked through command help.

---

## AC-12 — Run command requires scenario path

**Given** `astraloop run` with no path  
**When** parsed  
**Then** exit is 2.

---

## AC-13 — Run scenario argument becomes Path

**Given** a valid path argument  
**When** handler receives args  
**Then** it is a `Path`.

---

## AC-14 — Default artifact root is runs

**Given** run command without artifact option  
**When** handler calls runner  
**Then** `artifact_root=Path("runs")`.

---

## AC-15 — Custom artifact root is passed through

**Given** `--artifact-root output/runs`  
**When** run executes  
**Then** runner receives that root.

---

## AC-16 — No-artifacts passes None

**Given** `--no-artifacts`  
**When** run executes  
**Then** runner receives `artifact_root=None`.

---

## AC-17 — Artifact options are mutually exclusive

**Given** both options supplied  
**When** parsed  
**Then** usage error exits 2 before runner call.

---

## AC-18 — CLI does not construct final run-directory name

**Given** persisted run  
**When** CLI source is inspected  
**Then** final timestamp/digest directory comes from `RunArtifacts`.

---

## AC-19 — CLI does not expose ad-hoc seed override

**Given** MVP run help  
**When** inspected  
**Then** no `--seed` option exists.

---

## AC-20 — CLI does not expose ad-hoc timestep override

**Given** MVP run help  
**When** inspected  
**Then** no `--dt` option exists.

---

## AC-21 — List command defaults to scenarios root

**Given** no `--root`  
**When** handler calls discovery  
**Then** root is `Path("scenarios")`.

---

## AC-22 — Custom scenario root is passed through

**Given** `--root custom`  
**When** listing runs  
**Then** discovery receives that path.

---

## AC-23 — Scenario table contains required columns

**Given** nonempty descriptor list  
**When** rendered  
**Then** ID, Expected, Faults, Description, and Path are visible.

---

## AC-24 — Scenario table uses descriptor data

**Given** scenario descriptors  
**When** rendered  
**Then** CLI does not reread raw TOML or recalculate fault counts/outcomes.

---

## AC-25 — Scenario order is deterministic

**Given** the same descriptors  
**When** command runs repeatedly  
**Then** row order is stable.

---

## AC-26 — Empty scenario list is actionable

**Given** empty discovery result  
**When** list command runs  
**Then** stderr explains no TOMLs were found and how to choose/add a root.

---

## AC-27 — Empty scenario list exits two

**Given** empty root  
**When** command completes  
**Then** exit code is 2.

---

## AC-28 — Missing root exits two

**Given** nonexistent root  
**When** discovery raises configuration error  
**Then** CLI renders it and exits 2.

---

## AC-29 — Valid scenario list exits zero

**Given** at least one valid descriptor  
**When** rendered  
**Then** exit code is 0.

---

## AC-30 — Run handler uses production runner

**Given** run command  
**When** source/call is inspected  
**Then** it calls Feature 08 `run_scenario_file`/`run_scenario`.

---

## AC-31 — CLI has no alternate simulation loop

**Given** CLI source  
**When** inspected  
**Then** no tick/integrator/controller logic exists.

---

## AC-32 — Completed scenario result renders to stdout

**Given** normal `RunResult`  
**When** handler completes  
**Then** summary is written to stdout, not stderr.

---

## AC-33 — Scenario contract status is the primary heading

**Given** result  
**When** summary renders  
**Then** `SCENARIO PASS` or `SCENARIO FAIL` is prominent.

---

## AC-34 — Actual outcome is displayed

**Given** ValidationResult  
**When** rendered  
**Then** actual outcome is visible.

---

## AC-35 — Expected outcome is displayed

**Given** ValidationResult  
**When** rendered  
**Then** expected outcome is visible.

---

## AC-36 — Final mission state is displayed

**Given** result metrics  
**When** rendered  
**Then** final state is visible.

---

## AC-37 — Scenario ID is displayed

**Given** RunResult  
**When** rendered  
**Then** scenario ID is visible.

---

## AC-38 — Seed is displayed

**Given** RunResult/config metadata  
**When** rendered  
**Then** seed is visible.

---

## AC-39 — Final simulation time is displayed

**Given** validation metrics  
**When** rendered  
**Then** final time in seconds is visible.

---

## AC-40 — Config digest prefix is displayed

**Given** full digest  
**When** rendered  
**Then** a documented short prefix is shown.

---

## AC-41 — Landed metrics come from ValidationCheck/Result

**Given** landed result  
**When** table renders  
**Then** speed/error/pitch values and limits use structured validation data.

---

## AC-42 — CLI does not recalculate landing metrics

**Given** CLI source  
**When** inspected  
**Then** it does not calculate absolute vy/x/pitch formulas.

---

## AC-43 — N/A validation checks display as N/A

**Given** controlled abort  
**When** metric table renders  
**Then** landing checks are not shown as zero or PASS.

---

## AC-44 — Failed reasons display on scenario mismatch

**Given** `scenario_passed=False`  
**When** result renders  
**Then** concise failure reasons are visible.

---

## AC-45 — Passing scenario omits empty failure section

**Given** no failure reasons  
**When** result renders  
**Then** no meaningless failed-check heading appears.

---

## AC-46 — Configured fault count is displayed

**Given** result  
**When** fault summary renders  
**Then** configured count is visible.

---

## AC-47 — Activated fault IDs are displayed

**Given** activated faults  
**When** rendered  
**Then** stable IDs are visible.

---

## AC-48 — Pending fault IDs are displayed

**Given** configured fault did not activate  
**When** rendered  
**Then** pending ID is visible.

---

## AC-49 — Nominal run displays zero fault counts cleanly

**Given** no faults  
**When** rendered  
**Then** output does not show an empty malformed list.

---

## AC-50 — Persisted run displays artifact directory

**Given** `artifact_dir`  
**When** rendered  
**Then** final path is visible.

---

## AC-51 — Persisted run displays existing artifact files

**Given** RunArtifacts  
**When** rendered  
**Then** telemetry/events/config/summary/plot paths present in result are listed.

---

## AC-52 — Missing optional artifact is not fabricated

**Given** diagnostic bundle without PNG  
**When** rendered  
**Then** CLI omits or labels the plot unavailable rather than inventing a path.

---

## AC-53 — No-artifact run explains no files were written

**Given** artifact directory None  
**When** rendered  
**Then** output explicitly states artifacts were not written.

---

## AC-54 — Expected PASS exits zero

**Given** actual PASS and scenario contract pass  
**When** handler returns  
**Then** exit is 0.

---

## AC-55 — Expected controlled abort exits zero

**Given** actual/expected controlled abort and scenario contract pass  
**When** handler returns  
**Then** exit is 0.

---

## AC-56 — Expected validation failure exits zero

**Given** actual/expected validation fail and scenario contract pass  
**When** handler returns  
**Then** exit is 0.

---

## AC-57 — Expected abort is not labeled mission success

**Given** controlled abort result  
**When** rendered  
**Then** scenario is PASS but actual mission remains `CONTROLLED_ABORT`.

---

## AC-58 — Expected validation failure is explained

**Given** matching validation-fail scenario  
**When** rendered  
**Then** output makes clear physical criteria failed as expected.

---

## AC-59 — Scenario mismatch exits one

**Given** completed result with `scenario_passed=False`  
**When** handler returns  
**Then** exit is 1.

---

## AC-60 — ConfigError exits two

**Given** loader/discovery raises ConfigError  
**When** dispatch handles it  
**Then** error goes to stderr and exit is 2.

---

## AC-61 — Configuration error contains context

**Given** structured file/key error  
**When** rendered  
**Then** path/field and message are shown.

---

## AC-62 — File-not-found error suggests list command

**Given** missing scenario file  
**When** rendered  
**Then** a concise `list-scenarios` hint is shown.

---

## AC-63 — SimulationError exits three

**Given** runtime SimulationError  
**When** handled  
**Then** concise stderr output and exit 3 occur.

---

## AC-64 — Telemetry/Validation/Artifact/Plot internal errors exit three

**Given** one of the known internal/runtime exceptions  
**When** handled  
**Then** category is not mislabeled as user validation mismatch and exit is 3.

---

## AC-65 — Unexpected exception exits three

**Given** uncaught internal exception at command boundary  
**When** handled  
**Then** concise internal-error output and exit 3 occur.

---

## AC-66 — Known errors hide traceback by default

**Given** no `--debug`  
**When** an error occurs  
**Then** no traceback appears.

---

## AC-67 — Debug mode shows traceback

**Given** `--debug` and internal exception  
**When** handled  
**Then** traceback appears on stderr after concise heading.

---

## AC-68 — Debug mode does not change exit code

**Given** same error with/without debug  
**When** compared  
**Then** exit code remains identical.

---

## AC-69 — Validation mismatch never emits traceback

**Given** normal completed mismatch  
**When** rendered  
**Then** no traceback appears even in normal mode.

---

## AC-70 — KeyboardInterrupt exits 130

**Given** command handler raises KeyboardInterrupt  
**When** dispatch handles it  
**Then** cancellation message is shown and exit is 130.

---

## AC-71 — CLI prints no per-tick data

**Given** normal run  
**When** stdout is inspected  
**Then** telemetry/controller/RK4 stages are not streamed.

---

## AC-72 — CLI has no progress percentage

**Given** normal run  
**When** output is inspected  
**Then** no fake percent-complete value appears.

---

## AC-73 — No color output remains understandable

**Given** no-color/non-TTY console  
**When** summary/error renders  
**Then** PASS/FAIL/outcome labels remain explicit.

---

## AC-74 — Redirected output contains no interactive control behavior

**Given** stdout/stderr redirected  
**When** commands run  
**Then** output is stable text without spinner cursor control.

---

## AC-75 — Narrow terminal wraps descriptions and paths

**Given** fixed narrow Rich console width  
**When** tables/panels render  
**Then** important labels remain readable without crashing.

---

## AC-76 — CLI tests can inject consoles

**Given** in-memory Rich Console/file targets  
**When** handlers are tested  
**Then** stdout/stderr text can be asserted without subprocess for every case.

---

## AC-77 — Subprocess smoke tests cover installed/module entry points

**Given** built/installed dev environment  
**When** selected CLI integration tests run  
**Then** both invocation forms return expected codes.

---

## AC-78 — Core modules do not print directly

**Given** scenario run through CLI/test service  
**When** output is captured  
**Then** presentation originates at CLI boundary, not runner/dynamics/controller.

---

## AC-79 — CLI works locally and offline

**Given** clean installed environment  
**When** commands run  
**Then** no network, browser, database, cloud credential, or hardware is required.

---

## AC-80 — Reviewer can complete the core flow without source inspection

**Given** clean setup and bundled scenarios  
**When** reviewer runs help, list-scenarios, and nominal/fault run commands  
**Then** they can identify available scenarios, understand actual versus expected results, and find artifacts using terminal output alone.

---

# 7. Test Plan

## Unit tests — parser

Recommended:

```text
tests/unit/test_cli_parser.py
```

Cases:

```text
test_root_help
test_version
test_no_subcommand
test_unknown_command
test_run_requires_path
test_run_path_is_path
test_default_artifact_root
test_custom_artifact_root
test_no_artifacts
test_artifact_options_conflict
test_list_default_root
test_list_custom_root
test_debug_flag
```

Argparse help/error tests may assert `SystemExit`.

---

## Unit tests — renderers

Recommended:

```text
tests/unit/test_cli_rendering.py
```

Use:

```python
StringIO
Console(file=buffer, force_terminal=False, width=120)
```

Cases:

```text
test_scenario_table_columns
test_empty_scenario_message
test_run_pass_heading
test_run_fail_heading
test_actual_expected_outcome
test_expected_abort_explanation
test_expected_validation_fail_explanation
test_landing_metrics
test_na_metrics
test_failed_reasons
test_fault_summary
test_artifact_paths
test_no_artifact_message
test_config_error
test_runtime_error
test_debug_traceback
test_no_color_readability
test_narrow_console
```

Avoid asserting every Rich border character.

Assert load-bearing text.

---

## Unit tests — handlers/exit codes

Recommended:

```text
tests/unit/test_cli_handlers.py
```

Use monkeypatch/test doubles for application service boundaries.

Cases:

```text
test_list_success_exit_zero
test_list_empty_exit_two
test_run_expected_pass_exit_zero
test_run_expected_abort_exit_zero
test_run_expected_validation_fail_exit_zero
test_run_mismatch_exit_one
test_config_error_exit_two
test_simulation_error_exit_three
test_artifact_error_exit_three
test_unexpected_error_exit_three
test_keyboard_interrupt_exit_130
test_debug_does_not_change_code
```

Mocking runner/discovery is appropriate here because these tests prove CLI mapping, not simulation behavior.

---

## Integration tests — production service mapping

Recommended:

```text
tests/integration/test_cli.py
```

Cases:

```text
test_cli_run_calls_real_runner_for_short_scenario
test_cli_list_calls_real_discovery
test_cli_no_artifacts_writes_nothing
test_cli_default_artifacts_write_bundle
test_cli_validation_mismatch_preserves_artifacts
test_cli_config_error_no_artifacts
```

Use `tmp_path` and a short scenario fixture where appropriate.

---

## Subprocess smoke tests

Recommended:

```text
tests/integration/test_cli_entrypoints.py
```

Cases:

```text
uv run astraloop --help
uv run python -m astraloop --help
uv run astraloop list-scenarios --root <tmp scenarios>
```

Inside pytest, invoking `uv run` recursively may be unnecessary/slow.

Preferred installed-environment subprocess:

```python
subprocess.run(
    [sys.executable, "-m", "astraloop", "--help"],
    ...
)
```

For the console script, use `shutil.which("astraloop")` in a controlled environment or test package metadata separately.

Do not make the suite depend on shell parsing.

---

## End-to-end CLI demo tests

At least one test runs a complete bundled scenario through the CLI boundary using:

```text
--no-artifacts
```

Assert:

- exit code;
- scenario heading;
- actual/expected;
- no artifact files.

A separate persisted integration test uses `tmp_path`.

Do not rerun every scenario through both CLI and direct runner; Feature 12 scenario tests already cover every scenario.

---

## Error-path integration tests

### Invalid TOML

Assert exit 2 and field/path text.

### Runtime invariant failure

Use deterministic failing config/fake service.

Assert exit 3 and no traceback default.

### Validation mismatch

Use completed fixture.

Assert exit 1 and artifact paths visible.

### Plot/artifact failure

Assert exit 3.

---

## Manual QA checklist

- [ ] `uv run astraloop --help` works.
- [ ] `uv run python -m astraloop --help` works.
- [ ] `--version` works.
- [ ] `run` help is concise.
- [ ] `list-scenarios` help is concise.
- [ ] Scenario table is readable.
- [ ] Nominal run result is obvious.
- [ ] Fault run result is obvious.
- [ ] Expected abort shows scenario PASS.
- [ ] Expected validation failure shows scenario PASS.
- [ ] Mismatch shows scenario FAIL and exit 1.
- [ ] Config error is actionable and exit 2.
- [ ] Simulation error is distinct and exit 3.
- [ ] Debug traceback works.
- [ ] Ctrl+C is clean.
- [ ] Artifacts are easy to find.
- [ ] No-artifact mode is clear.
- [ ] No per-tick output appears.
- [ ] No GUI/browser opens.
- [ ] No color mode remains readable.
- [ ] Narrow terminal remains usable.
- [ ] Windows/macOS/Linux path handling is ordinary.
- [ ] CLI tests pass.
- [ ] Ruff/Pyright pass.

---

## Demo verification checklist

- [ ] Recruiter can list scenarios.
- [ ] Recruiter can run nominal in one command.
- [ ] Recruiter immediately sees scenario PASS/FAIL.
- [ ] Recruiter sees actual and expected outcome.
- [ ] Recruiter sees final state and key metrics.
- [ ] Recruiter sees fault activation summary.
- [ ] Recruiter sees exact artifact directory.
- [ ] Fault scenario explanation fits in terminal.
- [ ] Error example does not show raw traceback by default.
- [ ] Same engine path is used by pytest.
- [ ] Core demo fits within 60–90 seconds.

---

# 8. Portfolio Value

## How this feature helps the project stand out

A CLI is not impressive merely because it has colors.

Its value comes from making a complex engineering result immediately legible.

The strongest story is:

> “The CLI is a thin presentation layer over the same typed scenario runner used by pytest. It distinguishes mission outcome from scenario success, maps configuration, validation, and simulator failures to stable exit codes, and points directly to immutable run artifacts.”

That demonstrates:

- application boundaries;
- result modeling;
- operational clarity;
- automation-friendly exit codes;
- error taxonomy;
- testable terminal UX;
- disciplined dependency use.

---

## What to mention in README

Recommended wording:

> **One-command local workflow:** Use `astraloop list-scenarios` to inspect bundled cases and `astraloop run <scenario.toml>` to execute the full sensor–controller–actuator–physics loop. The CLI reports the actual and expected outcome, objective checks, fault activation, and generated artifact paths with stable shell exit codes.

Example:

```bash
uv run astraloop run scenarios/nominal.toml
```

Do not screenshot only decorative borders.

The screenshot should show:

- scenario PASS;
- actual/expected;
- metrics;
- artifacts.

---

## What to mention in interviews

### Why argparse instead of Typer?

> “The project only needs a few commands. Argparse keeps the command grammar explicit and avoids introducing a framework that does not improve the core engineering problem.”

### What role does Rich play?

> “Rich is presentation-only. It formats tables and panels, while argparse handles parsing and `run_scenario` owns the application behavior.”

### Why distinguish scenario success from mission success?

> “Fault tests can intentionally expect a controlled abort or failed landing criteria. The shell command should exit zero when the scenario behaved as designed, even though the actual mission outcome was not PASS.”

### How are exit codes defined?

> “Zero means the command/scenario contract succeeded, one is a completed scenario mismatch, two is bad input/configuration, and three is a simulator/internal/artifact failure. Ctrl+C returns 130.”

### Why no seed overrides?

> “The scenario TOML is the reproducible source of truth. Ad-hoc CLI overrides would create hidden configurations and complicate artifact provenance.”

### How do you test CLI output?

> “Parser and exit-code tests use injected in-memory Rich consoles. Integration tests call real discovery/runner services, and a few subprocess smoke tests verify the module entry point.”

### Why no progress bar?

> “The run is local and short, and simulation time is not wall-clock progress. A fake percentage would be misleading and add terminal noise.”

### How do errors differ?

> “Config errors fail before the engine and return two. A mission mismatch is a valid completed result and returns one. Simulator or artifact failures return three, and tracebacks appear only in debug mode.”

---

# 9. Implementation Notes for Codex

## Likely files/folders

```text
src/astraloop/
├── __main__.py
└── cli.py
```

If `cli.py` becomes too large after real implementation:

```text
src/astraloop/cli/
├── __init__.py
├── parser.py
├── commands.py
└── rendering.py
```

**Decision]** Start with one `cli.py`.

Split only if it becomes difficult to navigate.

Tests:

```text
tests/unit/
├── test_cli_parser.py
├── test_cli_rendering.py
└── test_cli_handlers.py

tests/integration/
├── test_cli.py
└── test_cli_entrypoints.py
```

---

## Suggested responsibilities

### `cli.py`

Own:

- version lookup;
- parser;
- consoles;
- dispatch;
- handlers;
- Rich renderers;
- exception mapping;
- exit constants.

Do not own production domain logic.

---

### `__main__.py`

Only:

```python
from astraloop.cli import main

raise SystemExit(main())
```

No duplicate parser.

---

## Exit-code constants

Recommended:

```python
EXIT_SUCCESS = 0
EXIT_SCENARIO_MISMATCH = 1
EXIT_USAGE_OR_CONFIG = 2
EXIT_INTERNAL_ERROR = 3
EXIT_INTERRUPTED = 130
```

Use constants in tests and handlers.

---

## Build order

### Step 1 — Add project script and __main__

### Step 2 — Build root parser/help/version

### Step 3 — Add list-scenarios handler/table

### Step 4 — Add run handler using real runner

### Step 5 — Add plain result renderer

Get semantics correct before color/style.

### Step 6 — Add validation/fault/artifact sections

### Step 7 — Add known exception mapping

### Step 8 — Add debug traceback

### Step 9 — Add Rich styling/no-color tests

### Step 10 — Add entry-point/integration tests

### Step 11 — Perform one manual 60–90 second demo rehearsal

### Step 12 — Freeze screenshots in Feature 15

---

## Risks

### Risk 1 — CLI duplicates runner logic

**Mitigation:** handlers only call Feature 08.

---

### Risk 2 — Pretty output hides semantics

**Mitigation:** explicit actual/expected/scenario fields.

---

### Risk 3 — Expected abort exits nonzero

**Mitigation:** exit uses `scenario_passed`.

---

### Risk 4 — Validation mismatch looks like Python error

**Mitigation:** normal completed summary, exit 1.

---

### Risk 5 — Artifact error looks like mission failure

**Mitigation:** exit 3/category panel.

---

### Risk 6 — Raw traceback scares reviewer

**Mitigation:** concise default + `--debug`.

---

### Risk 7 — Color-only meaning

**Mitigation:** explicit words.

---

### Risk 8 — Progress/spinner corrupts redirected output

**Mitigation:** no live progress UI.

---

### Risk 9 — Too many command options

**Mitigation:** config stays in TOML.

---

### Risk 10 — Campaign scope expands

**Mitigation:** optional sequential thin loop only after core.

---

### Risk 11 — Cross-platform open-plot behavior

**Mitigation:** do not auto-open files.

---

### Risk 12 — Tests assert Rich borders exactly

**Mitigation:** assert semantic text/exit codes.

---

### Risk 13 — CLI catches errors too early and hides diagnostics

**Mitigation:** catch at outer command boundary; debug traceback; preserve diagnostic artifact path.

---

### Risk 14 — CLI prints from core modules too

**Mitigation:** output-capture architecture tests.

---

### Risk 15 — `--artifact-root` path policy duplicated

**Mitigation:** pass root unchanged; Feature 09 owns final directory.

---

## What not to change

While implementing Feature 14, Codex should **not**:

- change scenario schema;
- change dynamics;
- change RK4;
- change sensors/controllers/actuators;
- change mission logic;
- change fault behavior;
- recalculate validation metrics;
- write CSV/JSON/PNG directly;
- construct final run directories;
- add Typer/Click;
- add Pydantic/Pandas;
- add Streamlit/GUI/web server;
- add interactive prompts;
- add per-tick logging;
- add fake progress percentages;
- add seed/dt/controller/fault overrides;
- auto-open plot files;
- add database/cloud services;
- add campaign concurrency;
- expose expected simulator errors as successful scenario outcomes;
- use scenario IDs to branch behavior;
- show raw tracebacks by default.

---

# Feature-Specific Definition of Done

Feature 14 is complete when:

- [ ] `astraloop` script entry point exists.
- [ ] `python -m astraloop` entry point exists.
- [ ] Both use the same `main`.
- [ ] Argparse root help exists.
- [ ] Version output exists.
- [ ] Required `run` command exists.
- [ ] Required `list-scenarios` command exists.
- [ ] Run accepts local TOML path.
- [ ] Run defaults artifact root to `runs`.
- [ ] `--artifact-root` works.
- [ ] `--no-artifacts` works.
- [ ] Artifact options conflict correctly.
- [ ] No ad-hoc simulation overrides exist.
- [ ] List defaults to `scenarios`.
- [ ] Custom list root works.
- [ ] Scenario table shows ID/expected/faults/description/path.
- [ ] Empty/missing root errors are actionable.
- [ ] CLI uses Feature 08 services.
- [ ] CLI uses no alternate simulation path.
- [ ] Result heading shows scenario PASS/FAIL.
- [ ] Actual outcome is shown.
- [ ] Expected outcome is shown.
- [ ] Final mission state is shown.
- [ ] Seed/time/digest are shown.
- [ ] Validation checks are rendered from Feature 10.
- [ ] N/A checks display correctly.
- [ ] Failure reasons are shown when needed.
- [ ] Fault counts/IDs are shown.
- [ ] Artifact paths are shown.
- [ ] No-artifact status is shown.
- [ ] Exit 0 semantics are correct.
- [ ] Exit 1 semantics are correct.
- [ ] Exit 2 semantics are correct.
- [ ] Exit 3 semantics are correct.
- [ ] Exit 130 interruption behavior exists.
- [ ] Expected abort exits 0.
- [ ] Expected validation failure exits 0.
- [ ] Config errors have no traceback by default.
- [ ] Internal errors have no traceback by default.
- [ ] `--debug` shows traceback.
- [ ] Errors use stderr.
- [ ] Results use stdout.
- [ ] No per-tick output exists.
- [ ] No fake progress exists.
- [ ] No interactive prompts exist.
- [ ] Rich output remains understandable without color.
- [ ] Narrow/redirected output remains usable.
- [ ] Parser/render/handler tests pass.
- [ ] Real service integration tests pass.
- [ ] Module-entry subprocess smoke test passes.
- [ ] Reviewer demo can be completed in 60–90 seconds.
- [ ] Feature remains local, offline, dependency-light, and non-SaaS.

---

# Open Questions

1. **[Open Question] Should the global developer option be named `--debug` or `--traceback`?**  
   Recommended: `--debug`.

2. **[Open Question] Should empty `list-scenarios` return exit 2 or exit 0 with an empty informational result?**  
   Recommended: 2 because the requested discovery action found no runnable scenario.

3. **[Open Question] Should `list-scenarios` fully validate every scenario before displaying it?**  
   Feature 08 recommends full validation for the small curated set.

4. **[Open Question] Should `--no-color` be an explicit option in addition to `NO_COLOR`/Rich TTY detection?**  
   Likely unnecessary for MVP.

5. **[Open Question] Should debug mode also enable standard logging DEBUG level?**  
   Recommended yes if logs are concise and useful.

6. **[Open Question] Should the CLI show every validation check or only core/failed checks?**  
   Recommended core checks plus all failures.

7. **[Open Question] Should the CLI show exact configured fault types/targets in addition to IDs?**  
   IDs/counts are sufficient for MVP; events/config artifacts contain details.

8. **[Open Question] Should artifact paths be absolute or relative?**  
   Recommended display paths as returned by the artifact writer, normally relative to current repository root; avoid forced resolution that makes screenshots machine-specific.

9. **[Open Question] Should a completed run with a plot-generation failure return exit 3 even if telemetry/validation succeeded?**  
   Recommended yes for portfolio-ready persisted runs because the required artifact bundle is incomplete.

10. **[Open Question] Should a machine-readable `--json` mode be added?**  
    Recommended no; `summary.json` already exists.

11. **[Open Question] Should `campaign` be included before Feature 15?**  
    Only if it remains a very small sequential wrapper and does not delay documentation.

12. **[Open Question] Should `plot` regeneration be implemented?**  
    Defer until a typed run-directory reader exists.

13. **[Open Question] Should the CLI print a start line before running?**  
    Optional. Final-only output is cleaner for fast runs.

14. **[Open Question] Should `BrokenPipeError` be handled specially?**  
    Useful polish for piping, but not required.

15. **[Open Question] Should controlled-abort heading use yellow while scenario PASS uses green?**  
    Recommended: green scenario heading, yellow actual-outcome field, so both concepts remain clear.

---

# Move On When

- [ ] A clean reviewer can discover scenarios.
- [ ] A clean reviewer can run nominal in one command.
- [ ] A clean reviewer can run one fault scenario.
- [ ] Actual and expected outcomes are unmistakable.
- [ ] Expected abort/failure semantics are correct.
- [ ] Shell exit codes are automation-friendly.
- [ ] Errors are concise and actionable.
- [ ] Artifacts are immediately discoverable.
- [ ] CLI remains a thin layer over production services.
- [ ] Output works in color, no-color, narrow, redirected, and test contexts.
- [ ] The recruiter demo fits within 60–90 seconds.
- [ ] No unnecessary CLI framework, dashboard, prompt system, override matrix, database, network service, or concurrency has been added.
- [ ] The project is ready for Feature 15 — Polished README & Documentation.
