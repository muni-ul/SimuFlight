# Feature 10 — Mission Validation

> **Project:** AstraLoop — Python Software-in-the-Loop Flight Control & Validation System  
> **Feature:** Mission Validation  
> **Document path:** `docs/features/10-mission-validation.md`  
> **Status:** Implementation specification  
> **Primary goal:** Evaluate completed AstraLoop runs objectively from immutable telemetry and events, derive landing and mission metrics from simulator truth, classify the actual mission outcome, compare it with the scenario's expected outcome, verify transition and fault contracts, and return structured validation results suitable for tests, summaries, and CLI reporting.

---

## Scope Boundary

**[Confirmed]** Objective mission validation is a required AstraLoop capability and must not be reduced to visual plot inspection.

**[Confirmed]** The source-defined nominal landing limits are project engineering targets:

```text
absolute landing vertical speed <= 2.0 m/s
horizontal landing error <= 5.0 m
landing pitch error <= 5 degrees
```

**[Confirmed]** Additional required validation concepts include:

- final mission-state check;
- no invalid mission-state transitions;
- scenario expected-outcome check;
- fault scenarios must recover within limits or reach a deliberate `ABORT`/failure outcome;
- the same seed and configuration must reproduce the same mission result.

**[Confirmed]** `LANDED` is a mission state, not proof of a good landing.

The system must support:

```text
final state = LANDED
landing metric exceeds limit
actual outcome = VALIDATION_FAIL
```

**[Confirmed]** A hard landing or expected controlled abort is a domain result, not a Python crash.

**[Confirmed]** Validation runs after simulation completion and must not mutate:

- telemetry;
- simulation state;
- controller state;
- mission state;
- fault state.

**[Confirmed]** Validation must not decide control commands.

**[Confirmed]** Mission validation failures, expected controlled aborts, configuration errors, and simulator/internal errors must remain distinct.

**[Decision]** Feature 10 owns the **post-run mission and scenario-contract evaluation layer**.

It owns:

- validation configuration/runtime types;
- derived mission metrics;
- selection of the authoritative touchdown frame;
- truth-based landing-speed calculation;
- truth-based horizontal-error calculation;
- truth-based pitch-error calculation;
- maximum-tilt calculation;
- fuel-remaining calculation;
- flight/touchdown timing metrics;
- final mission-state checks;
- mission-transition validity checks;
- configured-fault activation checks;
- unexpected fault-event checks;
- actual mission-outcome classification;
- expected-vs-actual outcome comparison;
- distinction between mission success and scenario regression success;
- immutable validation results;
- human-readable validation check records;
- unit tests;
- deterministic end-to-end scenario regression assertions.

It does **not** own:

- live control decisions;
- state-machine transitions;
- telemetry capture;
- event generation;
- scenario TOML parsing;
- simulation execution;
- artifact file writing;
- plot generation;
- terminal formatting;
- numerical-integrator verification;
- repeated-run reproducibility orchestration.

Feature 10 can validate one completed run. Feature 12/13 and scenario tests prove reproducibility/numerical correctness across runs.

---

# 1. Feature Overview

## Feature name

**Mission Validation**

---

## One-sentence description

**[Decision]** Implement a pure post-run validator that derives objective truth-based mission metrics from completed telemetry, classifies `PASS`, `CONTROLLED_ABORT`, or `VALIDATION_FAIL`, verifies the scenario contract, and produces structured checks that can be asserted by pytest and serialized into the run summary.

---

## Detailed description

AstraLoop has two separate questions after a run:

```text
1. What physically/software-wise happened to the mission?
2. Did that result match what this scenario was designed to prove?
```

These questions are related but not identical.

Consider a fault scenario configured to prove that a frozen altimeter produces a controlled abort.

The correct result may be:

```text
actual mission outcome = CONTROLLED_ABORT
expected scenario outcome = CONTROLLED_ABORT
scenario regression result = PASS
```

Calling the whole run simply `"FAIL"` would hide the fact that the software behaved exactly as expected.

The validator therefore separates:

```text
ActualOutcome
```

from:

```text
scenario_passed
```

---

## Validation flow

```text
CompletedTelemetry
ResolvedScenarioConfig.validation
Resolved fault definitions
        |
        v
validate structural preconditions
        |
        v
identify final and touchdown frames
        |
        v
derive objective metrics from truth
        |
        v
evaluate mission checks
        |
        v
classify actual mission outcome
        |
        v
evaluate scenario-contract checks
        |
        v
compare expected vs actual outcome
        |
        v
ValidationResult
```

---

## Mission outcome vs scenario success

### Actual mission outcome

Recommended enum:

```python
class ActualOutcome(Enum):
    PASS = "pass"
    CONTROLLED_ABORT = "controlled_abort"
    VALIDATION_FAIL = "validation_fail"
```

A simulator error is not an `ActualOutcome`.

If the engine raises `SimulationError`, normal mission validation does not produce one of these three outcomes.

---

### Scenario regression success

A scenario passes its validation contract when:

- the completed run is structurally valid;
- the actual outcome matches the configured expected outcome;
- every required configured fault activated as expected;
- no unexpected fault lifecycle inconsistency occurred;
- mission-transition assertions pass;
- any additional scenario-specific required checks pass.

Therefore:

```text
actual_outcome = VALIDATION_FAIL
expected_outcome = VALIDATION_FAIL
scenario_passed = true
```

is valid and useful.

---

## Mission success

Convenience property:

```python
mission_succeeded =
    actual_outcome is ActualOutcome.PASS
```

This remains false for an expected controlled abort or expected validation failure.

---

## Scenario success

Convenience property:

```python
scenario_passed =
    all(required scenario-contract checks)
```

The expected-outcome comparison is a required scenario-contract check.

---

## Why use simulator truth for objective validation

The controller and Mission State Machine must operate only on software-visible measurements.

The validator has a different responsibility:

```text
determine what actually happened in the simulation
```

**[Decision]** Objective landing metrics use **truth state recorded in telemetry**, not sensor measurements.

Why:

- noisy/bias/delayed measurements should not redefine physical landing quality;
- the simulator owns the ground-truth test oracle;
- a sensor fault can make software believe something incorrect while validation still measures the real outcome;
- this clearly separates control inputs from acceptance evidence.

This is analogous to a test harness observing internal ground truth while the system under test receives constrained inputs.

---

## Core nominal validation metrics

### 1. Landing vertical speed

At authoritative touchdown:

```text
signed_landing_vy =
    touchdown_truth.vy
```

Magnitude:

```text
landing_vertical_speed =
    abs(signed_landing_vy)
```

Core nominal check:

```text
landing_vertical_speed
<=
max_landing_vertical_speed
```

Source project target:

```text
2.0 m/s
```

---

### 2. Horizontal landing error

Configured landing target:

```text
target_x
```

Metric:

```text
horizontal_error =
    abs(touchdown_truth.x - target_x)
```

Core nominal check:

```text
horizontal_error
<=
max_horizontal_error
```

Source project target:

```text
5.0 m
```

---

### 3. Landing pitch error

Configured landing target pitch:

```text
target_pitch
```

Angular error:

```text
pitch_error =
    abs(
        wrap_angle(
            touchdown_truth.theta
            - target_pitch
        )
    )
```

Core nominal check:

```text
pitch_error
<=
max_pitch_error
```

Internal comparison unit:

```text
radians
```

Source reporting target:

```text
5 degrees
```

---

### 4. Final mission state

For a successful nominal landing:

```text
final mission state == LANDED
```

This is required but not sufficient for mission `PASS`.

---

### 5. Valid transition history

All recorded mission transitions must be legal and internally consistent.

Core project target:

```text
no invalid mission-state transitions
```

---

## Authoritative touchdown frame

Selecting touchdown data incorrectly can create a hidden off-by-one validation bug.

Feature 06 produces a structured mission transition:

```text
LANDING -> LANDED
```

Feature 09 records a telemetry frame at the same state tick.

**[Decision]** The authoritative touchdown tick is the tick of the first valid:

```text
LANDING -> LANDED
```

mission-transition event.

The authoritative touchdown frame is:

```text
telemetry frame whose tick == touchdown event tick
```

This frame contains the truth state at the start of the tick where flight software recognized landing/contact.

### Why not always use final TERMINAL frame

The engine may complete one final deterministic interval after the Mission State Machine enters `LANDED`, depending on final orchestration semantics.

Using the transition-aligned frame avoids measuring a later post-contact/neutral-actuator interval as the landing instant.

It also ties landing metrics to one explicit event.

---

## Touchdown fallback policy

**[Decision]** For a run whose final state is `LANDED`:

- a valid `LANDING -> LANDED` event is required;
- a corresponding telemetry frame is required;
- if either is missing, the mission-transition consistency check fails;
- the validator does not silently substitute an arbitrary final frame for portfolio-ready validation.

For isolated unit fixtures, a private helper may accept an explicitly supplied touchdown frame, but normal `validate_run(...)` remains strict.

---

## Runs without touchdown

If final mission state is:

```text
ABORT
```

or another non-landed state:

- touchdown metrics are `None`;
- landing-limit checks are marked `NOT_APPLICABLE`, not failed by themselves;
- actual-outcome classification handles the terminal state.

If final state is active at max time:

- touchdown metrics are `None`;
- final-state requirement fails;
- actual outcome is `VALIDATION_FAIL`.

---

## Maximum tilt

Summary/debug metric:

```text
maximum_tilt =
    max(
        abs(wrap_angle(frame.truth.theta))
        for frames in evaluated trajectory
    )
```

Default upright reference:

```text
0 rad
```

**Decision]** Maximum tilt is calculated from truth over all valid frames through the terminal/error endpoint.

It is always reported.

It is not a core PASS criterion unless an optional configured maximum-tilt limit is supplied.

---

## Fuel remaining

Vehicle dry mass comes from resolved vehicle configuration.

At the evaluation frame:

```text
fuel_remaining =
    max(
        0,
        evaluation_truth.mass
        - dry_mass
    )
```

### Evaluation frame

- if LANDED: touchdown frame;
- otherwise: final terminal frame.

**Decision]** Tiny negative results caused only by floating-point tolerance may normalize to zero.

A materially negative value indicates a simulator invariant failure and should not reach validation.

---

## Flight duration metrics

Always derive:

```text
final_tick
final_time
completed_steps
```

When landed:

```text
touchdown_tick
touchdown_time
```

Potential additional metric:

```text
time_in_flight =
    touchdown_time - ascent_start_time
```

is not required for MVP.

---

## Final truth state

Validation metrics should expose a concise final/evaluation truth record:

```text
x
y
vx
vy
theta
omega
mass
```

Feature 09 may store this in `summary.json`.

---

## Validation limits

Recommended resolved runtime config:

```python
@dataclass(frozen=True)
class ValidationConfig:
    expected_outcome: ExpectedOutcome

    target_x: float
    target_pitch: float

    max_landing_vertical_speed: float
    max_horizontal_error: float
    max_pitch_error: float

    max_flight_tilt: float | None

    require_valid_transitions: bool
    require_configured_faults_activated: bool
    reject_unexpected_fault_events: bool
```

Raw TOML can use:

```text
target_pitch_deg
max_pitch_error_deg
max_flight_tilt_deg
```

Feature 08 converts them to radians.

---

## Default target values

Recommended project defaults:

```text
target_x = 0.0 m
target_pitch = 0.0 rad
```

These defaults must become explicit in `ResolvedScenarioConfig`.

---

## Limit validation

All enabled numerical limits must be:

- finite;
- nonnegative.

The source-defined nominal values are:

```text
max_landing_vertical_speed = 2.0 m/s
max_horizontal_error = 5.0 m
max_pitch_error = 5 degrees
```

These are project targets, not real launch-vehicle certification limits.

---

## Comparison semantics

Core limits use inclusive comparison:

```text
actual <= limit
```

**[Decision]** Use one very small absolute numerical tolerance for boundary comparison:

```python
VALIDATION_ABS_TOL = 1e-9
```

Pass when:

```python
actual < limit
or
math.isclose(
    actual,
    limit,
    rel_tol=0.0,
    abs_tol=VALIDATION_ABS_TOL,
)
```

### Why

- preserves inclusive stated limits;
- avoids an irrelevant binary floating-point boundary failure;
- does not create a large hidden acceptance margin.

The unrounded raw value is always stored.

---

## No pre-comparison rounding

**[Decision]** Never round metrics before validation.

Bad:

```python
round(speed, 2) <= 2.00
```

Good:

```python
speed <= 2.0
```

with only the documented tiny tolerance.

CLI/summary presentation may round separately.

---

## Angle wrapping

Use one shared helper:

```python
wrap_angle(angle) -> [-pi, pi)
```

Landing pitch error:

```python
abs(wrap_angle(theta - target_pitch))
```

Maximum tilt:

```python
abs(wrap_angle(theta - upright_reference))
```

Do not compare unwrapped values such as:

```text
359 degrees
```

as a 359-degree error from 0.

---

## Required mission checks

Recommended IDs:

```text
final_state_landed
landing_vertical_speed
horizontal_landing_error
landing_pitch_error
valid_mission_transitions
```

For a landed mission, all must pass to classify actual outcome `PASS`.

---

## Optional mission checks

Potential:

```text
maximum_flight_tilt
fuel_remaining_nonnegative
terminal_reason_consistent
```

Some are structural/invariant checks rather than acceptance targets.

---

## Transition validation

Feature 06 already prevents illegal transitions.

Feature 10 independently verifies the completed event trace as scenario-level evidence.

### Required checks

1. mission-transition events are ordered by event sequence/tick;
2. first transition starts from `PRELAUNCH` for normal bundled scenarios;
3. every transition target is legal under `LEGAL_TRANSITIONS`;
4. each event's `from_state` matches the previously committed state;
5. no more than one mission transition occurs at one tick;
6. no transition occurs after terminal `LANDED`/`ABORT`;
7. final event/current state matches final telemetry mission state;
8. a `LANDED` final state has a `LANDING -> LANDED` event;
9. an `ABORT` final state has an active-state -> `ABORT` event unless initialized as ABORT only in a focused fixture.

---

## Validation source for transitions

Use:

```text
events.json in persisted form
```

or, internally:

```text
CompletedTelemetry.events
```

Do not infer the entire transition history only by scanning telemetry state changes.

Why:

- events preserve reason codes;
- events preserve authoritative old/new state;
- transition events are a required architecture output.

Telemetry scanning may be used as a consistency cross-check.

---

## Transition event vs telemetry consistency

For every mission transition event at tick `t`:

```text
frame t mission_state == event.to_state
```

The preceding frame/state relationship should be consistent with the event's `from_state`.

At tick zero, special PRELAUNCH behavior follows initial-state policy.

A mismatch fails:

```text
mission_event_telemetry_consistency
```

---

## Fault activation validation

A configured fault scenario should prove its fault actually ran.

Feature 07 provides lifecycle events.

Recommended checks:

```text
fault_activated:<fault_id>
fault_deactivated:<fault_id>   # only if bounded and expected to end before run termination
```

---

## Configured fault activation

When:

```text
require_configured_faults_activated = true
```

every configured fault ID must have exactly one activation event.

If a mission terminates before activation:

```text
actual mission outcome may still be classified normally
scenario_passed = false
```

because the intended fault scenario did not exercise its fault.

This directly addresses pending/unactivated faults.

---

## Nominal scenario fault check

For a scenario with:

```text
faults = ()
```

the validator requires:

```text
no fault activation/deactivation events
```

when:

```text
reject_unexpected_fault_events = true
```

---

## Unexpected fault events

Fault lifecycle events whose ID is not in resolved scenario configuration fail:

```text
no_unexpected_fault_events
```

This protects against leaked state or incorrect runtime construction.

---

## Duplicate fault lifecycle events

Fail if:

- same fault activates more than once;
- same fault deactivates more than once;
- deactivation appears before activation;
- completed/deactivation timing contradicts definition.

Feature 07 should prevent this, but validation confirms the run artifact.

---

## Permanent fault semantics

A permanent fault:

- requires activation event;
- does not require deactivation;
- may remain listed active at terminal frame.

---

## Bounded fault semantics

If configured deactivation tick occurred before/equal final executed tick:

- require deactivation event at exact configured tick.

If run terminated before the deactivation tick:

- no deactivation event is required;
- summary reports fault still active at termination.

---

## Fault-effect validation

Feature 07 integration tests prove detailed subsystem effects.

Feature 10 can include scenario-specific high-level effect checks only where they are stable and objective.

Examples:

```text
altimeter freeze produced stale reading
degraded actuator created requested-vs-actual separation
```

**Decision]** Keep the core validator generic.

Do not hard-code checks based on scenario ID.

A future scenario can configure additional check specifications if needed, but the MVP should rely on:

- configured fault activated;
- actual mission outcome matched expectation;
- telemetry remains structurally consistent.

Scenario tests may assert more detailed effect evidence directly.

---

## Actual outcome classification

Classification occurs only after required structural/transition data is available.

Recommended rules in priority order.

### 1. Controlled abort

If:

```text
final mission state == ABORT
```

and the completed run did not end in simulator error:

```text
actual_outcome = CONTROLLED_ABORT
```

Mission landing checks are not applicable.

Transition consistency remains required for scenario success.

---

### 2. Mission pass

If:

```text
final mission state == LANDED
```

and all required mission checks pass:

```text
actual_outcome = PASS
```

Required mission checks include:

- valid touchdown event/frame;
- landing vertical speed limit;
- horizontal error limit;
- pitch error limit;
- valid transition history.

---

### 3. Validation fail

Any other completed non-error run:

```text
actual_outcome = VALIDATION_FAIL
```

Examples:

- final state LANDED but hard landing;
- final state LANDED but horizontal miss;
- final state LANDED but excessive pitch;
- final state remains DESCENT at max time;
- invalid transition trace;
- final state inconsistent with events;
- terminal state is not accepted.

---

## Why ABORT classification precedes landing checks

An abort scenario does not have touchdown metrics by definition.

It should be classified as controlled abort rather than "failed vertical landing speed because no landing existed."

Scenario expected-outcome comparison determines whether that abort was desired.

---

## Expected outcome matching

Feature 08 defines:

```text
PASS
CONTROLLED_ABORT
VALIDATION_FAIL
```

Check:

```text
actual_outcome == expected_outcome
```

Result ID:

```text
expected_outcome_matched
```

This check is always required.

---

## Scenario passed calculation

Recommended:

```python
scenario_passed = all(
    check.passed
    for check in checks
    if check.required_for_scenario
)
```

Required scenario checks include:

- expected outcome matched;
- transition/event consistency;
- configured-fault activation contract;
- no unexpected fault events;
- other structural scenario checks.

### Important

Landing checks are mission-outcome inputs.

For a scenario expecting `VALIDATION_FAIL`, those checks can fail while:

```text
scenario_passed = true
```

because the actual outcome correctly becomes `VALIDATION_FAIL`.

To avoid treating failed mission checks as failed scenario-contract checks, each check has a scope.

---

## Check scopes

Recommended enum:

```python
class ValidationCheckScope(Enum):
    DATA = "data"
    MISSION = "mission"
    SCENARIO = "scenario"
```

### DATA

Input consistency required to trust validation.

Examples:

- final frame exists;
- event/frame tick consistency.

A failed required DATA check should normally raise `ValidationError` if the metric cannot be evaluated, or produce a failed structural result if still evaluable.

---

### MISSION

Determines physical/software mission outcome.

Examples:

- landing-speed limit;
- horizontal error;
- pitch error;
- final state;
- transition legality.

Mission check failure can be expected in a fault scenario.

---

### SCENARIO

Determines whether the configured regression case behaved as intended.

Examples:

- expected outcome match;
- configured fault activated;
- no unexpected fault events.

---

## Validation check status

Some checks are not applicable.

Recommended enum:

```python
class ValidationCheckStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"
```

Do not represent N/A as a passed Boolean without explanation.

---

## ValidationCheck record

Recommended:

```python
@dataclass(frozen=True)
class ValidationCheck:
    id: str
    scope: ValidationCheckScope
    status: ValidationCheckStatus

    description: str

    actual: JsonValue | None
    expected: JsonValue | None
    operator: str | None
    units: str | None

    required_for_outcome: bool
    required_for_scenario: bool

    details: str | None = None
```

Convenience:

```python
passed -> status is PASS
```

---

## Check IDs

Stable machine-readable IDs.

Examples:

```text
data_final_frame
data_touchdown_event_frame
data_event_frame_consistency

mission_final_state_landed
mission_landing_vertical_speed
mission_horizontal_error
mission_landing_pitch_error
mission_transition_history

mission_maximum_tilt  # optional

scenario_expected_outcome
scenario_fault_activated.freeze_altimeter_01
scenario_no_unexpected_fault_events
```

Do not make tests depend on human description text.

---

## ValidationMetrics record

Recommended:

```python
@dataclass(frozen=True)
class ValidationMetrics:
    final_tick: int
    final_time: float
    completed_steps: int

    final_mission_state: MissionState
    termination_reason: str

    touchdown_tick: int | None
    touchdown_time: float | None

    signed_landing_vertical_velocity: float | None
    landing_vertical_speed: float | None
    horizontal_landing_error: float | None
    landing_pitch_error: float | None

    maximum_tilt: float
    fuel_remaining: float

    final_truth: VehicleState
    evaluation_truth: VehicleState
```

Internal angles remain radians.

Reporting helpers may expose degrees.

---

## ValidationResult record

Recommended:

```python
@dataclass(frozen=True)
class ValidationResult:
    actual_outcome: ActualOutcome
    expected_outcome: ExpectedOutcome

    mission_succeeded: bool
    outcome_matched: bool
    scenario_passed: bool

    metrics: ValidationMetrics
    checks: tuple[ValidationCheck, ...]

    configured_fault_ids: tuple[str, ...]
    activated_fault_ids: tuple[str, ...]
    pending_fault_ids: tuple[str, ...]

    failure_reasons: tuple[str, ...]
```

---

## Failure reasons

Provide concise stable summaries derived from failed checks.

Examples:

```text
landing vertical speed 2.31 m/s exceeded 2.00 m/s
expected controlled_abort but actual outcome was validation_fail
configured fault freeze_altimeter_01 did not activate
mission transition event at tick 220 did not match telemetry state
```

Do not duplicate full traceback or every passing check.

---

## ValidationError

Use:

```python
class ValidationError(Exception):
    ...
```

only when completed data cannot be safely interpreted due to structural/programming inconsistency.

Examples:

- no telemetry frames;
- final frame is CONTROL despite "completed" input;
- unsupported telemetry/event schema;
- non-finite truth reaches validator;
- duplicate frame ticks despite recorder guarantees;
- required config object missing.

Do not raise `ValidationError` for:

- hard landing;
- wrong final mission state;
- expected outcome mismatch;
- fault not activated;
- controlled abort.

Those return `ValidationResult`.

---

## Pure-function boundary

Recommended:

```python
def validate_run(
    *,
    telemetry: CompletedTelemetry,
    config: ResolvedScenarioConfig,
) -> ValidationResult:
    ...
```

Potential narrower:

```python
def validate_mission(
    telemetry: CompletedTelemetry,
    validation_config: ValidationConfig,
    *,
    vehicle: VehicleParameters,
    configured_faults: tuple[FaultDefinition, ...],
) -> ValidationResult:
    ...
```

**[Decision]** Prefer the full resolved scenario config for one clear application boundary, while validation logic accesses only the fields it needs.

The function must not mutate inputs or write files.

---

## Determinism

Given the same:

```text
CompletedTelemetry
ResolvedScenarioConfig
```

validation must return exactly the same:

```text
metrics
checks
actual outcome
scenario_passed
failure reasons
```

No wall-clock data.

No RNG.

---

## Reproducibility check scope

The source requires:

```text
same seed + same config -> same mission result
```

One validator call cannot prove this across two runs.

**[Decision]** Feature 10 exposes a comparison helper for tests:

```python
def compare_validation_results(
    left: ValidationResult,
    right: ValidationResult,
) -> ReproducibilityComparison:
    ...
```

But full repeated-run execution belongs to scenario tests/Feature 12.

---

## Reproducibility comparison

Recommended exact fields:

- actual outcome;
- outcome-matched status;
- final mission state;
- final tick/time;
- transition sequence/reason codes;
- fault activation/deactivation ticks;
- check statuses;
- metrics within defined numerical tolerance.

For deterministic same-seed runs, most values should be exactly equal or bitwise-repeatable under the pinned environment.

Use tolerances for floating metrics to avoid coupling tests to serialization.

---

## Why it matters

Objective mission validation converts a simulation demo into a validation system.

Without Feature 10, the reviewer must decide:

```text
"Does this plot look okay?"
```

With Feature 10:

```text
Landing vertical speed: 1.31 m/s  PASS <= 2.00
Horizontal error:       2.18 m    PASS <= 5.00
Pitch error:            1.84 deg  PASS <= 5.00
Final state:            LANDED    PASS
Transition history:               PASS
Mission outcome:        PASS
Expected outcome:       PASS
Scenario regression:   PASS
```

or:

```text
Mission outcome:        CONTROLLED_ABORT
Expected outcome:       CONTROLLED_ABORT
Scenario regression:   PASS
```

This is the central validation/testing hiring signal.

---

## Skill it demonstrates

A strong implementation demonstrates:

- test-oracle design;
- objective acceptance criteria;
- truth-vs-measurement reasoning;
- post-run data analysis;
- state-machine trace verification;
- fault-contract verification;
- outcome taxonomy;
- deterministic regression testing;
- typed result modeling;
- floating-point comparison discipline;
- separation of domain failure and software error;
- scenario-level test architecture.

---

## Priority

**P0 — Required MVP**

The source blueprint explicitly says not to cut:

```text
objective mission validation
deterministic testing
```

The project is portfolio-ready only when nominal and fault scenarios have automated expected outcomes.

---

## Complexity

**Medium to high**

The formulas are simple.

The difficult parts are:

- touchdown-frame semantics;
- outcome taxonomy;
- expected failures;
- transition/event consistency;
- missing metrics on abort;
- fault activation requirements;
- making pytest assertions meaningful without brittle trajectory equality.

---

# 2. User / Demo Flow

## Happy path — nominal PASS

1. Simulation completes with terminal mission state `LANDED`.
2. Telemetry recorder finalizes.
3. Validator checks final data structure.
4. `LANDING -> LANDED` event is found.
5. Touchdown frame at same tick is found.
6. Truth-based metrics are calculated.
7. Landing-speed check passes.
8. Horizontal-error check passes.
9. Pitch-error check passes.
10. Transition-history check passes.
11. Actual outcome is classified `PASS`.
12. Expected outcome is `PASS`.
13. Configured fault set is empty and no fault events exist.
14. `scenario_passed = true`.
15. Feature 09 serializes metrics/checks into summary.

---

## Happy path — expected controlled abort

1. Fault activates.
2. Sensor/mission behavior leads to terminal `ABORT`.
3. Validator sees final mission state `ABORT`.
4. Landing checks become `NOT_APPLICABLE`.
5. Transition history passes.
6. Configured fault activation check passes.
7. Actual outcome is `CONTROLLED_ABORT`.
8. Expected outcome is `CONTROLLED_ABORT`.
9. `scenario_passed = true`.

---

## Happy path — expected validation failure

1. Vehicle reaches `LANDED`.
2. Touchdown speed exceeds configured limit.
3. Landing-speed check fails.
4. Actual outcome is `VALIDATION_FAIL`.
5. Scenario config expects `VALIDATION_FAIL`.
6. Configured fault activated.
7. Transition trace remains valid.
8. `scenario_passed = true`.

---

## Unexpected mission failure

1. Nominal scenario reaches LANDED too fast.
2. Actual outcome becomes `VALIDATION_FAIL`.
3. Expected outcome is `PASS`.
4. Outcome-match check fails.
5. `scenario_passed = false`.
6. The runner still writes complete artifacts.
7. Pytest scenario regression fails with check details.

---

## First-time implementation path

### Stage A — Validate synthetic landed frame

Build a minimal immutable completed telemetry fixture.

Calculate speed/error/pitch.

### Stage B — Check boundaries

Exactly at limits passes.

Slightly above fails.

### Stage C — Add transition trace validation

Use synthetic mission events.

### Stage D — Add outcome classification

PASS, controlled abort, validation fail.

### Stage E — Add expected-outcome comparison

Prove expected failure scenario can pass regression.

### Stage F — Add fault activation contract

Configured vs activated/pending IDs.

### Stage G — Integrate with real telemetry

Run short deterministic fixtures.

### Stage H — Add full scenario pytest tests

Nominal + four fault scenarios.

---

## Empty state

Completed telemetry cannot be empty.

Raise `ValidationError`.

A valid run may have:

- no faults;
- no touchdown;
- no landing metrics because it aborted.

Those are handled structurally.

---

## Error path

### Missing terminal/error final frame

`ValidationError`.

### Final state LANDED but no touchdown event

Return failed mission/data consistency checks if the data can otherwise be read.

Actual outcome becomes `VALIDATION_FAIL`.

### Touchdown event with no matching frame

`ValidationError` or required DATA-check failure depending on implementation boundary.

Recommended:

- if tick is outside frame range: `ValidationError`;
- if frame exists but state does not match: failed consistency check and `VALIDATION_FAIL`.

### Non-finite metric

`ValidationError`.

### Invalid validation limit

Should have been caught by Feature 08.

Treat as `ValidationError` if encountered.

### Simulator error

Validator is not called as a normal completed-run validator.

Diagnostic summary uses no `ActualOutcome`.

---

## Reviewer demo path

### Demo A — Nominal check table

Show concise objective result.

### Demo B — Expected failure

Show:

```text
Mission outcome: VALIDATION_FAIL
Expected:        VALIDATION_FAIL
Scenario:        PASS
```

Explain distinction.

### Demo C — Truth-based oracle

Point to sensor fault:

```text
controller used biased vy
validator used true vy at touchdown
```

### Demo D — Pytest regression

Run scenario tests.

Show deterministic pass/fail.

### Demo E — Failure reason

Temporarily tighten one limit in a test fixture and show actionable failed check.

---

# 3. UX / UI Requirements

## Screens/pages

No GUI.

Feature 10 returns structured data consumed by:

- Feature 09 `summary.json`;
- Feature 14/15 CLI;
- pytest;
- Feature 11 plot annotations if useful.

---

## Components

Recommended:

```text
ActualOutcome
ValidationCheckScope
ValidationCheckStatus
ValidationCheck
ValidationMetrics
ValidationResult
ValidationError
Validator / validate_run
reproducibility comparison helper
```

Do not build a generic rules engine.

---

## Forms/inputs

No interactive form.

Validation thresholds come from resolved scenario configuration.

---

## Buttons/actions

None.

---

## Validation output messages

Examples:

```text
Landing vertical speed 2.31 m/s exceeded limit 2.00 m/s.
```

```text
Horizontal landing error 4.82 m satisfied limit 5.00 m.
```

```text
Expected outcome controlled_abort matched actual outcome controlled_abort.
```

```text
Configured fault freeze_altimeter_01 did not activate before termination.
```

```text
Mission transition at tick 320 was illegal: COAST -> LANDING.
```

---

## Loading states

None.

Validation is synchronous and small.

---

## Error states

Distinguish:

```text
ValidationResult(actual_outcome=VALIDATION_FAIL)
```

from:

```text
ValidationError
```

The first is a valid evaluated mission result.

The second means the validator could not trust/interpret its inputs.

---

## Reporting units

Internal:

```text
meters
seconds
m/s
radians
kilograms
ticks
```

Human report:

- pitch values in degrees;
- retain raw radians in structured metrics if desired;
- do not convert landing speed to positive/negative ambiguously.

Recommended display:

```text
Landing vertical speed magnitude: 1.31 m/s
Signed touchdown vy:             -1.31 m/s
```

---

# 4. Data Requirements

## Entities involved

### `ExpectedOutcome`

From Feature 08:

```text
PASS
CONTROLLED_ABORT
VALIDATION_FAIL
```

---

### `ActualOutcome`

Feature 10 equivalent result enum.

Keep separate types if it improves semantic clarity, even if string values match.

---

### `ValidationConfig`

Resolved thresholds/contract flags.

---

### `ValidationCheck`

One objective assertion.

---

### `ValidationMetrics`

Derived facts.

---

### `ValidationResult`

Complete validator output.

---

### `CompletedTelemetry`

Feature 09 immutable frames/events.

---

### `ResolvedScenarioConfig`

Feature 08.

---

### `MissionState`

Feature 06.

---

### `FaultDefinition` / `FaultEvent`

Feature 07.

---

### `VehicleState`

Feature 01 truth values.

---

## Relationships

```text
CompletedTelemetry
       |
       +--> truth frames
       +--> mission events
       +--> fault events
       |
ResolvedScenarioConfig
       |
       +--> limits
       +--> expected outcome
       +--> dry mass
       +--> configured faults
       |
       v
validate_run
       |
       v
ValidationResult
       |
       +--> pytest assertions
       +--> summary.json
       +--> CLI check table
```

---

## Example validation TOML

```toml
[validation]
expected_outcome = "pass"

target_x_m = 0.0
target_pitch_deg = 0.0

max_landing_vertical_speed_m_s = 2.0
max_horizontal_error_m = 5.0
max_pitch_error_deg = 5.0

require_valid_transitions = true
require_configured_faults_activated = true
reject_unexpected_fault_events = true
```

Optional:

```toml
max_flight_tilt_deg = 25.0
```

Values are project-defined targets.

---

## Summary-facing JSON example

```json
{
  "actual_outcome": "pass",
  "expected_outcome": "pass",
  "mission_succeeded": true,
  "outcome_matched": true,
  "scenario_passed": true,
  "metrics": {
    "touchdown_time_s": 31.17,
    "signed_landing_vertical_velocity_m_s": -1.31,
    "landing_vertical_speed_m_s": 1.31,
    "horizontal_landing_error_m": 2.18,
    "landing_pitch_error_rad": 0.0321,
    "landing_pitch_error_deg": 1.84,
    "maximum_tilt_rad": 0.142,
    "maximum_tilt_deg": 8.14,
    "fuel_remaining_kg": 112.5
  },
  "checks": [
    {
      "id": "mission_landing_vertical_speed",
      "scope": "mission",
      "status": "pass",
      "actual": 1.31,
      "expected": 2.0,
      "operator": "<=",
      "units": "m/s"
    }
  ]
}
```

Feature 09 owns exact JSON serialization.

---

## Local persistence needs

None directly.

Feature 10 returns immutable Python records.

Feature 09 serializes them.

No database.

---

# 5. Logic Requirements

## Rule 1 — Validation runs only on completed immutable telemetry

No live-state mutation.

---

## Rule 2 — Simulator truth is the physical validation oracle

Measurements are not used for physical landing metrics.

---

## Rule 3 — Touchdown tick comes from LANDING -> LANDED event

No arbitrary final-frame substitution.

---

## Rule 4 — Touchdown frame tick must match event tick

---

## Rule 5 — Vertical landing speed uses absolute true vy

Signed vy is retained separately.

---

## Rule 6 — Horizontal error is absolute x distance from configured target

---

## Rule 7 — Pitch error uses wrapped angular distance to configured target

---

## Rule 8 — Limit comparisons are inclusive

---

## Rule 9 — Metrics are not rounded before comparison

---

## Rule 10 — Tiny documented absolute tolerance only

---

## Rule 11 — Maximum tilt uses truth over trajectory

---

## Rule 12 — Fuel remaining derives from mass minus dry mass

---

## Rule 13 — Final state LANDED is required for actual PASS

---

## Rule 14 — LANDED alone is insufficient

---

## Rule 15 — Final state ABORT classifies controlled abort

---

## Rule 16 — Non-LANDED/non-ABORT completed terminal state classifies validation fail

---

## Rule 17 — Invalid transition history prevents actual PASS

---

## Rule 18 — Landing checks are N/A for abort

---

## Rule 19 — Actual outcome and expected outcome are separate

---

## Rule 20 — Scenario can pass with expected controlled abort

---

## Rule 21 — Scenario can pass with expected validation failure

---

## Rule 22 — Mission success is true only for ActualOutcome.PASS

---

## Rule 23 — Expected-outcome match is always a required scenario check

---

## Rule 24 — Configured fault activation is independently checked

---

## Rule 25 — Missing expected fault makes scenario fail, not necessarily change actual mission outcome

---

## Rule 26 — Unexpected fault events fail scenario contract

---

## Rule 27 — Nominal run expects no fault lifecycle events

---

## Rule 28 — Duplicate fault activation/deactivation events fail contract

---

## Rule 29 — Bounded fault deactivation requirement respects early termination

---

## Rule 30 — Permanent faults need no deactivation event

---

## Rule 31 — Mission transition events are authoritative history

---

## Rule 32 — Telemetry mission states cross-check events

---

## Rule 33 — No transition after terminal state

---

## Rule 34 — No more than one mission transition per tick

---

## Rule 35 — Final event state must match final telemetry state

---

## Rule 36 — Validation failures return result, not exception

---

## Rule 37 — Structurally unusable inputs raise ValidationError

---

## Rule 38 — SimulationError is not an expected validation outcome

---

## Rule 39 — Validator never writes files

---

## Rule 40 — Validator never prints directly

---

## Rule 41 — Validator never plots

---

## Rule 42 — Validator never reads raw TOML

---

## Rule 43 — Validator never changes mission/controller/fault state

---

## Rule 44 — Validation is deterministic

---

## Rule 45 — Check IDs are stable

---

## Rule 46 — N/A is explicit

---

## Rule 47 — Failure reasons derive from failed checks

---

## Rule 48 — Summary receives raw metrics and formatted reporting can occur later

---

## Rule 49 — Scenario-specific branches by scenario ID are forbidden

---

## Rule 50 — Repeated-run reproducibility is tested outside one validation call

---

## Touchdown lookup pseudocode

```python
def find_touchdown(
    telemetry: CompletedTelemetry,
) -> tuple[RecordedEvent, TelemetryFrame] | None:

    candidates = [
        event
        for event in telemetry.events
        if (
            event.source == EventSource.MISSION
            and event.type == "mission_transition"
            and event.data["from_state"] == "landing"
            and event.data["to_state"] == "landed"
        )
    ]

    if not candidates:
        return None

    if len(candidates) != 1:
        raise ValidationError(
            "expected exactly one touchdown transition"
        )

    event = candidates[0]
    frame = telemetry.frames[event.tick]

    return event, frame
```

Do not assume tuple index equals tick without first confirming recorder's sequential contract/schema.

A tick-to-frame map may be clearer.

---

## Metric calculation pseudocode

```python
def compute_landing_metrics(
    *,
    touchdown: TelemetryFrame,
    config: ResolvedScenarioConfig,
) -> LandingMetrics:

    truth = touchdown.truth

    signed_vy = truth.vy
    speed = abs(signed_vy)

    horizontal_error = abs(
        truth.x - config.validation.target_x
    )

    pitch_error = abs(
        wrap_angle(
            truth.theta
            - config.validation.target_pitch
        )
    )

    fuel_remaining = max(
        0.0,
        truth.mass - config.vehicle.dry_mass
    )

    return ...
```

---

## Outcome classification pseudocode

```python
def classify_actual_outcome(
    *,
    final_state: MissionState,
    mission_checks: tuple[ValidationCheck, ...],
) -> ActualOutcome:

    if final_state is MissionState.ABORT:
        return ActualOutcome.CONTROLLED_ABORT

    if (
        final_state is MissionState.LANDED
        and all_required_outcome_checks_pass(
            mission_checks
        )
    ):
        return ActualOutcome.PASS

    return ActualOutcome.VALIDATION_FAIL
```

---

## Scenario-pass pseudocode

```python
outcome_match = (
    actual_outcome.value
    == config.validation.expected_outcome.value
)

scenario_checks = (
    expected_outcome_check(...),
    *fault_contract_checks(...),
    *required_data_contract_checks(...),
)

scenario_passed = all(
    check.status is ValidationCheckStatus.PASS
    for check in scenario_checks
    if check.required_for_scenario
)
```

Mission-limit failures do not directly fail scenario regression when the expected outcome is validation failure.

---

## Transition validation pseudocode

```python
def validate_transition_history(
    events: tuple[RecordedEvent, ...],
    frames: tuple[TelemetryFrame, ...],
) -> ValidationCheck:

    state = MissionState.PRELAUNCH
    transition_ticks: set[int] = set()

    for event in mission_transition_events(events):
        if event.tick in transition_ticks:
            return failed(...)

        from_state = parse_state(event.data["from_state"])
        to_state = parse_state(event.data["to_state"])

        if from_state is not state:
            return failed(...)

        if to_state not in LEGAL_TRANSITIONS[from_state]:
            return failed(...)

        if frames[event.tick].mission_state is not to_state:
            return failed(...)

        transition_ticks.add(event.tick)
        state = to_state

    if frames[-1].mission_state is not state:
        return failed(...)

    return passed(...)
```

---

## Fault contract pseudocode

```python
def validate_fault_contract(
    *,
    configured_faults: tuple[FaultDefinition, ...],
    events: tuple[RecordedEvent, ...],
    final_tick: int,
) -> tuple[ValidationCheck, ...]:

    configured = {fault.id: fault for fault in configured_faults}
    activated = group_activation_events(events)
    deactivated = group_deactivation_events(events)

    checks = []

    for fault_id, fault in configured.items():
        checks.append(
            check_exactly_one_activation(
                fault_id,
                activated,
            )
        )

        if should_have_deactivated_by(
            fault,
            final_tick=final_tick,
        ):
            checks.append(
                check_exactly_one_deactivation(...)
            )

    checks.append(
        check_no_unexpected_fault_ids(...)
    )

    return tuple(checks)
```

---

## Edge cases

### Landing speed exactly 2.0 m/s

Pass.

### Horizontal error exactly 5.0 m

Pass.

### Pitch error exactly 5 degrees

Pass.

### Tiny floating overshoot within 1e-9

Pass under documented tolerance.

### Material overshoot

Fail.

### Signed vy positive at touchdown

Magnitude still calculated.

A positive upward velocity at declared touchdown may pass the magnitude limit numerically, but it is physically suspicious.

**Decision]** Add a mission sanity check:

```text
touchdown_vertical_direction
```

Recommended requirement:

```text
signed_vy <= positive_touchdown_velocity_tolerance
```

with default tiny tolerance such as:

```text
0.05 m/s
```

**[Open Question]** Whether this should be a core required check.

For MVP, include it as an optional/diagnostic check unless real simulation can produce slight positive bounce under the simplified ground model.

---

### Horizontal target is nonzero

Use configured target.

### Pitch target is nonzero

Use wrapped error.

### Theta is multiple rotations

Wrapped landing error remains shortest angular error.

Maximum tilt using wrapped angle may hide full rotations.

**Decision]** For maximum tilt, use:

```text
abs(wrap_angle(theta))
```

because the project validates orientation rather than accumulated rotation count.

If full rotations need detection, add separate angular-excursion metric later.

---

### Final state LANDED but touchdown event missing

Mission check fails; actual outcome validation fail.

### Touchdown event occurs twice

ValidationError or failed transition-history check.

Recommended: failed transition-history check if events are otherwise structurally parseable.

### ABORT after earlier LANDED

Illegal transition check fails.

### Final active state at max time

Actual outcome validation fail.

### Fault never activated because mission ended early

Actual mission outcome classification remains based on mission.

Scenario fault check fails.

### Expected validation fail but all landing checks pass

Actual outcome pass; expected mismatch; scenario fails.

### Expected controlled abort but mission validation fails without abort

Actual validation fail; scenario fails.

### Fault scenario passes landing limits

Actual pass.

It can be expected pass and scenario passes.

### No configured faults but fault event exists

Scenario fails.

### Optional maximum tilt limit absent

Metric reported; check N/A/omitted.

### Fuel reaches exactly dry mass

Fuel remaining zero.

### Final mass slightly below dry mass

Should be SimulationError before validation.

### Error frame final

Normal `validate_run` rejects/does not classify mission.

Diagnostic summary remains simulator error.

---

# 6. Acceptance Criteria

## AC-01 — Validator accepts completed normal telemetry

**Given** valid immutable telemetry ending in TERMINAL and valid resolved config  
**When** `validate_run(...)` executes  
**Then** it returns immutable `ValidationResult`.

---

## AC-02 — Validator does not mutate telemetry

**Given** completed telemetry  
**When** validation completes  
**Then** frames/events remain unchanged.

---

## AC-03 — Validator does not mutate config

**Given** resolved config  
**When** validation completes  
**Then** config remains unchanged.

---

## AC-04 — Empty telemetry raises ValidationError

**Given** no frames  
**When** validation is attempted  
**Then** it fails structurally rather than inventing a result.

---

## AC-05 — CONTROL final frame is rejected

**Given** supposedly completed telemetry ending in CONTROL  
**When** validator runs  
**Then** `ValidationError` occurs.

---

## AC-06 — ERROR final frame is not classified as normal mission outcome

**Given** diagnostic telemetry ending ERROR  
**When** normal validator is called  
**Then** it rejects/identifies simulator-error input rather than returning PASS/CONTROLLED_ABORT/VALIDATION_FAIL.

---

## AC-07 — Final tick/time are derived correctly

**Given** terminal frame tick `N` and `dt`  
**When** metrics calculate  
**Then** final time equals `N*dt`.

---

## AC-08 — Completed step count is derived consistently

**Given** `N` CONTROL frames plus one TERMINAL frame  
**When** metrics calculate  
**Then** completed steps equals `N`.

---

## AC-09 — Touchdown event is LANDING to LANDED

**Given** landed mission  
**When** touchdown lookup occurs  
**Then** only the explicit `LANDING -> LANDED` transition qualifies.

---

## AC-10 — Touchdown frame uses event tick

**Given** touchdown event at tick `t`  
**When** metrics calculate  
**Then** truth is read from frame `t`.

---

## AC-11 — Final terminal frame is not silently substituted for touchdown

**Given** landed final state but missing touchdown event  
**When** validation runs  
**Then** landed mission cannot pass by using terminal frame as fallback.

---

## AC-12 — Exactly one touchdown event is expected

**Given** multiple `LANDING -> LANDED` events  
**When** transition validation runs  
**Then** history fails/validator reports inconsistency.

---

## AC-13 — Landing vertical speed uses truth vy

**Given** truth vy differs from measured vy at touchdown  
**When** metric calculates  
**Then** truth vy is used.

---

## AC-14 — Landing vertical speed uses magnitude

**Given** touchdown truth `vy=-1.5`  
**When** metric calculates  
**Then** landing speed is `1.5`.

---

## AC-15 — Signed touchdown vy is retained

**Given** touchdown truth vy  
**When** metrics return  
**Then** signed value is available separately from magnitude.

---

## AC-16 — Vertical speed below limit passes

**Given** speed `1.99`, limit `2.0`  
**When** check runs  
**Then** status is PASS.

---

## AC-17 — Vertical speed at limit passes

**Given** speed exactly equal to limit  
**When** check runs  
**Then** status is PASS.

---

## AC-18 — Vertical speed above tolerance fails

**Given** speed materially above limit  
**When** check runs  
**Then** status is FAIL.

---

## AC-19 — Horizontal error uses truth x

**Given** measured x differs from truth x  
**When** metric calculates  
**Then** truth x is used.

---

## AC-20 — Horizontal error uses configured target

**Given** target x nonzero  
**When** metric calculates  
**Then** error is `abs(truth.x-target_x)`.

---

## AC-21 — Horizontal error below limit passes

**Given** error below configured maximum  
**When** check runs  
**Then** PASS.

---

## AC-22 — Horizontal error at limit passes

**Given** error exactly equal to limit  
**When** check runs  
**Then** PASS.

---

## AC-23 — Horizontal error above limit fails

**Given** error materially above limit  
**When** check runs  
**Then** FAIL.

---

## AC-24 — Pitch error uses truth theta

**Given** measured pitch differs from truth pitch  
**When** metric calculates  
**Then** truth theta is used.

---

## AC-25 — Pitch error uses configured target

**Given** nonzero target pitch  
**When** metric calculates  
**Then** shortest angular difference is used.

---

## AC-26 — Pitch error wraps across ±pi

**Given** equivalent orientations across wrap boundary  
**When** metric calculates  
**Then** small shortest error is returned.

---

## AC-27 — Pitch error below limit passes

**Given** error below limit  
**When** check runs  
**Then** PASS.

---

## AC-28 — Pitch error at limit passes

**Given** error exactly equal to limit  
**When** check runs  
**Then** PASS.

---

## AC-29 — Pitch error above limit fails

**Given** error above limit  
**When** check runs  
**Then** FAIL.

---

## AC-30 — Metrics are not rounded before checks

**Given** raw speed `2.004` and display precision two decimals  
**When** validation runs  
**Then** it fails even if displayed rounded value might appear `2.00`.

---

## AC-31 — Numerical comparison tolerance is tiny and explicit

**Given** value within documented absolute tolerance of limit  
**When** comparison runs  
**Then** inclusive boundary passes.

---

## AC-32 — Maximum tilt uses truth trajectory

**Given** truth pitch frames  
**When** metric calculates  
**Then** maximum wrapped absolute tilt is returned.

---

## AC-33 — Maximum tilt is reported without limit

**Given** no max-tilt validation limit  
**When** validation runs  
**Then** metric exists and corresponding check is N/A/omitted.

---

## AC-34 — Optional maximum tilt limit is enforced

**Given** configured max tilt  
**When** trajectory exceeds it  
**Then** optional mission check fails according to configured required semantics.

---

## AC-35 — Fuel remaining uses mass minus dry mass

**Given** evaluation mass and dry mass  
**When** metric calculates  
**Then** fuel remaining equals their difference, clamped only for tiny tolerance.

---

## AC-36 — Zero fuel remaining is valid

**Given** evaluation mass equals dry mass  
**When** metric calculates  
**Then** fuel remaining is zero.

---

## AC-37 — Final truth state is preserved in metrics

**Given** terminal frame  
**When** metrics return  
**Then** final truth values are available.

---

## AC-38 — Evaluation truth is touchdown truth for landed run

**Given** LANDED outcome  
**When** metrics return  
**Then** evaluation truth is touchdown frame truth.

---

## AC-39 — Evaluation truth is final truth for non-landed run

**Given** ABORT/max-time run  
**When** metrics return  
**Then** evaluation truth is terminal truth.

---

## AC-40 — LANDED final state alone does not guarantee PASS

**Given** final LANDED but one required landing check fails  
**When** outcome classifies  
**Then** actual outcome is VALIDATION_FAIL.

---

## AC-41 — LANDED with all required mission checks passes

**Given** final LANDED, valid touchdown/history, and all core limits pass  
**When** outcome classifies  
**Then** actual outcome is PASS.

---

## AC-42 — Final ABORT classifies controlled abort

**Given** completed non-error run ending ABORT  
**When** outcome classifies  
**Then** actual outcome is CONTROLLED_ABORT.

---

## AC-43 — Active final state at max time classifies validation fail

**Given** final state DESCENT/LANDING/etc. with normal max-time termination  
**When** outcome classifies  
**Then** actual outcome is VALIDATION_FAIL.

---

## AC-44 — Abort landing checks are N/A

**Given** final state ABORT  
**When** checks build  
**Then** landing speed/horizontal/pitch checks are NOT_APPLICABLE.

---

## AC-45 — Mission succeeded only for actual PASS

**Given** controlled abort or validation fail  
**When** result property is read  
**Then** `mission_succeeded` is false.

---

## AC-46 — Expected PASS matches actual PASS

**Given** both outcomes PASS  
**When** comparison runs  
**Then** expected-outcome check passes.

---

## AC-47 — Expected controlled abort matches actual controlled abort

**Given** both outcomes controlled abort  
**When** comparison runs  
**Then** expected-outcome check passes.

---

## AC-48 — Expected validation fail matches actual validation fail

**Given** both outcomes validation fail  
**When** comparison runs  
**Then** expected-outcome check passes.

---

## AC-49 — Outcome mismatch fails scenario contract

**Given** expected PASS and actual VALIDATION_FAIL  
**When** result builds  
**Then** `outcome_matched=false` and scenario fails.

---

## AC-50 — Expected failure can pass scenario regression

**Given** expected and actual validation fail with all scenario-contract checks passing  
**When** result builds  
**Then** `scenario_passed=true`.

---

## AC-51 — Expected controlled abort can pass scenario regression

**Given** expected and actual controlled abort with required fault/trace checks passing  
**When** result builds  
**Then** `scenario_passed=true`.

---

## AC-52 — Valid transitions use legal map

**Given** mission transition events  
**When** history validates  
**Then** each `to_state` must be legal from its `from_state`.

---

## AC-53 — Transition from-state must match current reconstructed state

**Given** event claims wrong from-state  
**When** history validates  
**Then** transition check fails.

---

## AC-54 — Multiple transitions same tick fail

**Given** two mission transition events at one tick  
**When** history validates  
**Then** transition check fails.

---

## AC-55 — Transition after terminal state fails

**Given** event after LANDED/ABORT  
**When** history validates  
**Then** transition check fails.

---

## AC-56 — Transition telemetry state must match target

**Given** event at tick `t` to LANDING but frame `t` says DESCENT  
**When** consistency validates  
**Then** check fails.

---

## AC-57 — Final event state matches final telemetry state

**Given** completed transition history  
**When** final state cross-check runs  
**Then** last reconstructed state equals final frame state.

---

## AC-58 — LANDED requires landing transition event

**Given** final state LANDED  
**When** history validates  
**Then** one `LANDING -> LANDED` event is required.

---

## AC-59 — ABORT requires legal abort transition

**Given** final state ABORT in normal bundled run  
**When** history validates  
**Then** a legal active-state -> ABORT event is required.

---

## AC-60 — Configured fault activation is detected by ID

**Given** configured fault and matching activation event  
**When** fault contract validates  
**Then** fault-activation check passes.

---

## AC-61 — Missing configured fault activation fails scenario contract

**Given** configured fault with no activation event  
**When** required activation policy is enabled  
**Then** scenario check fails.

---

## AC-62 — Fault activation exactly once is required

**Given** duplicate activation events for one ID  
**When** fault contract validates  
**Then** check fails.

---

## AC-63 — Unknown activated fault fails scenario contract

**Given** activation event for unconfigured fault ID  
**When** unexpected-event rejection is enabled  
**Then** scenario check fails.

---

## AC-64 — Nominal run rejects fault lifecycle events

**Given** no configured faults and a fault activation event  
**When** validator runs  
**Then** scenario contract fails.

---

## AC-65 — Permanent fault does not require deactivation

**Given** permanent configured fault activated once  
**When** run ends  
**Then** no deactivation check failure occurs.

---

## AC-66 — Bounded fault requires deactivation if tick was executed

**Given** deactivation tick <= final executed tick  
**When** no deactivation event exists  
**Then** scenario check fails.

---

## AC-67 — Early termination before deactivation does not require event

**Given** run ends before configured deactivation tick  
**When** fault contract validates  
**Then** missing deactivation is not a failure.

---

## AC-68 — Deactivation before activation fails

**Given** event sequence deactivates first  
**When** fault history validates  
**Then** scenario check fails.

---

## AC-69 — Pending fault IDs are reported

**Given** configured faults without activation event  
**When** result builds  
**Then** their IDs appear in `pending_fault_ids`.

---

## AC-70 — Activated fault IDs are stable ordered

**Given** multiple activations  
**When** result returns IDs  
**Then** order is deterministic.

---

## AC-71 — Check statuses include explicit N/A

**Given** abort with no touchdown  
**When** checks are inspected  
**Then** landing checks are NOT_APPLICABLE, not ambiguously passed.

---

## AC-72 — Check IDs are stable and unique

**Given** one validation result  
**When** check IDs are inspected  
**Then** no duplicates exist.

---

## AC-73 — Failure reasons identify required failed checks

**Given** scenario failure  
**When** result builds  
**Then** concise reasons explain outcome mismatch/fault/mission issue.

---

## AC-74 — Passing checks do not fill failure reasons

**Given** fully passing scenario  
**When** result builds  
**Then** failure reasons are empty.

---

## AC-75 — Validator performs no file writes

**Given** validation execution  
**When** filesystem is monitored  
**Then** no summary/CSV/plot file is written by Feature 10.

---

## AC-76 — Validator performs no terminal printing

**Given** validation execution  
**When** stdout captured  
**Then** core validator prints nothing.

---

## AC-77 — Same inputs produce same ValidationResult

**Given** identical immutable telemetry/config  
**When** validated twice  
**Then** metrics/checks/outcome/result match.

---

## AC-78 — Different sensor measurements do not change truth landing metrics when truth is identical

**Given** two completed telemetry fixtures with identical truth and different measured landing values  
**When** validated  
**Then** physical landing metrics match.

---

## AC-79 — Reproducibility comparison detects outcome mismatch

**Given** two same-scenario results with different actual outcomes  
**When** comparison helper runs  
**Then** reproducibility fails.

---

## AC-80 — Full curated scenario suite has deterministic expected contracts

**Given** nominal plus four fault scenarios  
**When** pytest runs each through the same runner/validator  
**Then** each produces its documented actual outcome and `scenario_passed=true`.

This is a cross-feature portfolio completion gate.

---

# 7. Test Plan

## Unit tests — metric helpers

Recommended:

```text
tests/unit/test_validation_metrics.py
```

Cases:

```text
test_touchdown_lookup
test_touchdown_missing
test_touchdown_duplicate
test_vertical_speed_magnitude
test_horizontal_error_target_zero
test_horizontal_error_nonzero_target
test_pitch_error_zero
test_pitch_error_wrap
test_maximum_tilt
test_fuel_remaining
test_final_and_touchdown_times
test_truth_not_measurement_used
```

---

## Unit tests — limits

```text
tests/unit/test_validation_limits.py
```

Cases:

```text
test_speed_below_limit
test_speed_equal_limit
test_speed_above_limit
test_horizontal_below_equal_above
test_pitch_below_equal_above
test_no_round_before_compare
test_tiny_boundary_tolerance
test_optional_max_tilt
test_invalid_limit_rejected_upstream
```

---

## Unit tests — transition history

```text
tests/unit/test_transition_validation.py
```

Cases:

```text
test_valid_nominal_sequence
test_valid_abort_sequence
test_illegal_transition
test_wrong_from_state
test_two_transitions_same_tick
test_transition_after_terminal
test_event_frame_state_mismatch
test_final_state_mismatch
test_landed_missing_touchdown
test_abort_missing_abort_event
```

---

## Unit tests — fault contract

```text
tests/unit/test_fault_contract_validation.py
```

Cases:

```text
test_nominal_no_faults
test_nominal_unexpected_fault
test_configured_fault_activated
test_configured_fault_missing
test_duplicate_activation
test_unknown_fault_id
test_permanent_no_deactivation
test_bounded_deactivation
test_bounded_missing_deactivation
test_early_termination_before_deactivation
test_deactivation_before_activation
test_pending_fault_ids
```

---

## Unit tests — outcome classification

```text
tests/unit/test_outcome_classification.py
```

Cases:

```text
test_landed_all_checks_pass
test_landed_speed_fail
test_landed_horizontal_fail
test_landed_pitch_fail
test_landed_transition_fail
test_abort_classification
test_max_time_active_state_fail
test_expected_pass_match
test_expected_abort_match
test_expected_validation_fail_match
test_outcome_mismatch
test_expected_failure_scenario_passes
```

---

## Unit tests — result structure

```text
tests/unit/test_validation_result.py
```

Cases:

```text
test_check_ids_unique
test_na_status
test_failure_reasons
test_no_failure_reasons_on_pass
test_result_immutable
test_same_inputs_same_result
```

---

## Integration tests — real telemetry

Recommended:

```text
tests/integration/test_mission_validation.py
```

### Landed nominal fixture

Use real Feature 09 recorder output.

Assert touchdown event/frame alignment and metrics.

### Controlled abort fixture

Use real state-machine events.

Assert N/A landing checks and controlled-abort classification.

### Hard landing fixture

Final state LANDED but excessive truth vy.

Assert actual validation fail.

### Sensor bias fixture

Keep truth touchdown same while biased measured vy differs.

Assert truth-based metric.

---

## Scenario tests

Required:

```text
tests/scenarios/test_nominal.py
tests/scenarios/test_fault_scenarios.py
```

Recommended assertions:

```python
assert result.validation.scenario_passed
assert result.validation.actual_outcome is EXPECTED
assert result.validation.outcome_matched
```

Additionally assert the relevant configured fault activated.

---

## Nominal scenario test

```python
def test_nominal_mission_passes():
    result = run_scenario_file(
        Path("scenarios/nominal.toml"),
        artifact_root=None,
    )

    validation = result.validation

    assert validation.scenario_passed
    assert validation.actual_outcome is ActualOutcome.PASS
    assert validation.mission_succeeded
```

Avoid manually duplicating every validator formula in the scenario test.

The validator unit tests protect formulas.

---

## Fault scenario parametrization

```python
@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (
            "scenarios/altimeter_freeze.toml",
            ActualOutcome.CONTROLLED_ABORT,
        ),
        (
            "scenarios/velocity_bias.toml",
            ActualOutcome.VALIDATION_FAIL,
        ),
        ...
    ],
)
def test_fault_scenario_contract(path, expected):
    ...
```

The exact expected outcomes remain tuning decisions.

Do not assume from scenario name.

---

## Reproducibility test

Run the same scenario twice.

Assert:

- same config digest;
- same actual outcome;
- same scenario-pass status;
- same final state;
- same transition sequence;
- same fault lifecycle ticks;
- same metric values under exact/tolerance policy.

Do not compare wall-clock artifact paths.

---

## Regression-test philosophy

When a real bug is found:

1. capture the smallest deterministic scenario/config;
2. add a failing test;
3. fix subsystem/validator behavior;
4. keep test permanently;
5. document what telemetry showed.

High-value validation bugs include:

- touchdown frame off by one;
- comparing measured instead of true velocity;
- rounding before limits;
- expected controlled abort labeled generic failure;
- fault never activated but scenario falsely passed;
- invalid transition not detected;
- pitch angle wrap error.

---

## Manual QA checklist

- [ ] Truth is used for physical metrics.
- [ ] Touchdown event/frame semantics are clear.
- [ ] Final LANDED is not sufficient by itself.
- [ ] Speed limit is inclusive.
- [ ] Horizontal limit is inclusive.
- [ ] Pitch limit is inclusive.
- [ ] No pre-check rounding.
- [ ] Angle wrapping is correct.
- [ ] Max tilt is reported.
- [ ] Fuel remaining is reported.
- [ ] Final/touchdown time is reported.
- [ ] Transition history is verified.
- [ ] Event/frame states are cross-checked.
- [ ] Configured faults must activate when required.
- [ ] Unexpected faults are rejected.
- [ ] Abort checks use N/A landing metrics.
- [ ] Actual outcome is separate from scenario result.
- [ ] Expected failure can pass regression.
- [ ] Simulation error is not accepted as expected outcome.
- [ ] Validator writes/prints nothing.
- [ ] ValidationResult is immutable.
- [ ] Unit/integration/scenario tests pass.
- [ ] Same seed/config reproduces validation result.

---

## Demo verification checklist

- [ ] Nominal run prints objective check table.
- [ ] Metrics match summary/telemetry.
- [ ] Fault activation is proven.
- [ ] Expected controlled abort displays as scenario PASS.
- [ ] Expected validation failure displays as scenario PASS.
- [ ] Unexpected nominal hard landing displays scenario FAIL.
- [ ] Truth-vs-measurement validation distinction can be explained.
- [ ] Pytest runs nominal and fault scenarios.
- [ ] Failure reason is actionable.
- [ ] No subjective plot-only decision is required.

---

# 8. Portfolio Value

## How this feature helps the project stand out

Feature 10 is the strongest proof that AstraLoop is a **validation system** rather than a rocket animation.

The best explanation is:

> "I defined objective post-run test oracles using simulator truth, verified mission transition traces and fault activation, classified actual outcomes separately from expected scenario outcomes, and ran the same checks automatically through pytest."

This creates interview depth around:

- what makes a continuously evolving mission pass;
- how to validate expected failures;
- how to use truth without letting the controller cheat;
- how to distinguish domain failure from simulator failure;
- how to build stable regression checks.

---

## What to mention in README

Recommended wording:

> **Automated mission validation:** Completed runs are evaluated against truth-based landing limits, final mission state, transition legality, configured fault activation, and the scenario's expected outcome. Expected controlled aborts and expected validation failures can pass their regression contracts without being mislabeled as simulator errors.

Useful bullets:

- `|landing vy| <= 2.0 m/s`;
- horizontal error `<= 5 m`;
- pitch error `<= 5°`;
- touchdown metrics from simulator truth;
- transition-trace validation;
- fault-activation assertions;
- expected vs actual outcome;
- deterministic pytest scenarios.

---

## What to mention in interviews

### Why use truth for validation if controller cannot use truth?

> "The controller is the system under test, so it receives only simulated measurements. The validation harness is the test oracle, so it uses simulator truth to determine what physically happened."

### How do you define touchdown?

> "The authoritative touchdown tick is the structured `LANDING -> LANDED` transition event. I use the truth frame at the same tick, which avoids validating a later post-contact frame."

### Does LANDED mean PASS?

> "No. LANDED means contact was recognized. The validator separately checks true landing speed, horizontal error, pitch error, and transition history."

### How do you represent expected failures?

> "I separate actual mission outcome from scenario regression success. A scenario can produce `VALIDATION_FAIL` or `CONTROLLED_ABORT` and still pass when that exact outcome was expected and its fault really activated."

### What happens if a fault was configured but the mission ended before it activated?

> "The mission outcome is still classified from what happened, but the scenario contract fails because the intended fault was not exercised."

### Why verify transition events if the state machine already tests legality?

> "It validates the end-to-end artifact and catches integration or logging inconsistencies. The test result proves the actual run trace, not just the state-machine unit implementation."

### How do you handle floating-point boundaries?

> "I compare unrounded raw values with inclusive limits and only a tiny documented absolute tolerance. Display rounding never changes PASS/FAIL."

### What is the difference between validation failure and simulator error?

> "Validation failure is a valid run that missed mission criteria. Simulator error means the software produced an internal/numerical failure and normal mission validation is not used to call it an expected success."

---

# 9. Implementation Notes for Codex

## Likely files/folders

```text
src/astraloop/validation/
├── __init__.py
├── checks.py
└── validator.py

src/astraloop/model/
└── results.py

tests/unit/
├── test_validation_metrics.py
├── test_validation_limits.py
├── test_transition_validation.py
├── test_fault_contract_validation.py
├── test_outcome_classification.py
└── test_validation_result.py

tests/integration/
└── test_mission_validation.py

tests/scenarios/
├── test_nominal.py
└── test_fault_scenarios.py
```

---

## Suggested responsibilities

### `validation/checks.py`

Own pure helpers:

- inclusive limit comparison;
- angle wrapping/error;
- touchdown lookup;
- metric extraction;
- transition-history validation;
- fault-contract validation;
- check-record builders.

No file I/O.

---

### `validation/validator.py`

Own:

- full orchestration;
- actual-outcome classification;
- expected-outcome check;
- scenario-pass calculation;
- failure reasons;
- public `validate_run`.

---

### `model/results.py`

Own shared immutable:

```text
ValidationCheck
ValidationMetrics
ValidationResult
ActualOutcome
```

if used broadly by telemetry/CLI.

---

## Build order

### Step 1 — Define outcome/check/result types

Lock mission vs scenario semantics first.

---

### Step 2 — Implement shared numeric helpers

Angle wrap and inclusive comparison.

---

### Step 3 — Implement touchdown lookup

Use mission event + frame tick.

---

### Step 4 — Implement core landing metrics

Truth only.

---

### Step 5 — Implement core landing checks

Boundary tests.

---

### Step 6 — Implement transition-history validator

Synthetic events/frames.

---

### Step 7 — Implement outcome classification

PASS/ABORT/validation fail.

---

### Step 8 — Implement expected-outcome matching

Prove expected failure behavior.

---

### Step 9 — Implement fault contract checks

Configured/activated/pending.

---

### Step 10 — Assemble ValidationResult

Unique stable check IDs.

---

### Step 11 — Integrate Feature 09 summary

Pass results; do not serialize here.

---

### Step 12 — Add scenario regression tests

Only after nominal/fault configs are tuned.

---

### Step 13 — Add reproducibility comparison/test

Run same scenario twice.

---

## Risks

### Risk 1 — Validator uses measured state

**Mitigation:** direct truth-frame metric tests where measurements intentionally differ.

---

### Risk 2 — Touchdown frame off by one

**Mitigation:** transition-event tick contract and integration test.

---

### Risk 3 — LANDED automatically means pass

**Mitigation:** independent metric checks.

---

### Risk 4 — Expected abort shown as failure

**Mitigation:** actual outcome vs scenario result separation.

---

### Risk 5 — Expected validation failure causes pytest failure

**Mitigation:** scenario tests assert `scenario_passed`, not `mission_succeeded`.

---

### Risk 6 — Fault never activates but outcome coincidentally matches

**Mitigation:** configured-fault activation checks.

---

### Risk 7 — Plot used as acceptance oracle

**Mitigation:** validator consumes telemetry/events/config only.

---

### Risk 8 — Rounding changes result

**Mitigation:** raw comparisons.

---

### Risk 9 — Angle wrap bug

**Mitigation:** boundary tests around ±pi.

---

### Risk 10 — Validator becomes rules framework

Avoid:

- dynamic expression languages;
- arbitrary user Python;
- plugin rule registries;
- generic policy engines.

Typed checks are enough.

---

### Risk 11 — Structural corruption treated as mission failure

**Mitigation:** `ValidationError` for unusable inputs.

---

### Risk 12 — Mission failure treated as exception

**Mitigation:** return `ValidationResult`.

---

### Risk 13 — Reproducibility asserted through exact arbitrary trajectory equality only

**Mitigation:** compare outcomes/events/metrics and use appropriate float tolerance; deterministic telemetry byte checks remain Feature 09 tests.

---

## What not to change

While implementing Feature 10, Codex should **not**:

- change dynamics;
- change RK4;
- change sensor models;
- change controller behavior to make validation pass;
- change actuator behavior to make validation pass;
- change mission thresholds/transitions silently;
- directly activate faults;
- capture telemetry;
- write JSON/CSV;
- generate plots;
- parse TOML;
- implement CLI formatting;
- treat scenario ID as validation logic;
- accept simulator error as expected mission success;
- round before comparisons;
- add a generic validation DSL;
- add a database;
- add cloud/reporting services;
- add Monte Carlo campaigns.

If a scenario fails unexpectedly, diagnose and fix the appropriate subsystem or explicitly revise the documented scenario contract—do not weaken the validator silently.

---

# Feature-Specific Definition of Done

Feature 10 is complete when:

- [ ] ActualOutcome enum exists.
- [ ] ValidationCheck scope/status types exist.
- [ ] ValidationMetrics exists.
- [ ] ValidationResult exists.
- [ ] `validate_run(...)` is pure and typed.
- [ ] Completed telemetry/config remain immutable.
- [ ] Touchdown uses LANDING -> LANDED event tick.
- [ ] Truth frame at touchdown is used.
- [ ] Signed and absolute landing vy are recorded.
- [ ] Horizontal target error is calculated.
- [ ] Wrapped pitch target error is calculated.
- [ ] Source limits 2.0 m/s, 5 m, 5° are supported.
- [ ] Inclusive raw comparisons are implemented.
- [ ] Tiny documented tolerance exists.
- [ ] No pre-check rounding occurs.
- [ ] Maximum tilt is calculated.
- [ ] Fuel remaining is calculated.
- [ ] Final/touchdown timing is calculated.
- [ ] Final truth/evaluation truth are exposed.
- [ ] Mission-transition history is verified.
- [ ] Event/frame state consistency is verified.
- [ ] LANDED does not automatically pass.
- [ ] ABORT classifies controlled abort.
- [ ] Max-time/nonterminal completion classifies validation fail.
- [ ] Landing checks are N/A for abort.
- [ ] Expected outcome comparison exists.
- [ ] Mission success and scenario success are separate.
- [ ] Expected abort can pass scenario regression.
- [ ] Expected validation failure can pass scenario regression.
- [ ] Configured fault activation checks exist.
- [ ] Unexpected fault events are rejected when configured.
- [ ] Pending/activated fault IDs are reported.
- [ ] Failure reasons are actionable.
- [ ] Structural input errors raise ValidationError.
- [ ] Domain mission failures return ValidationResult.
- [ ] SimulationError remains outside normal validation outcomes.
- [ ] Validator performs no I/O/plotting/printing.
- [ ] Metric/limit/transition/fault/outcome unit tests pass.
- [ ] Real telemetry integration tests pass.
- [ ] Nominal scenario test passes.
- [ ] Four fault scenario contracts pass.
- [ ] Same seed/config reproduces validation results.
- [ ] Feature 09 summary includes validator-produced metrics/checks.
- [ ] CLI can render results without recalculating them.

---

# Open Questions

1. **[Open Question] What exact expected outcome should each of the four fault scenarios declare?**  
   Determine after tuning. Do not infer solely from scenario names.

2. **[Open Question] Should positive touchdown vertical velocity be a required failure check?**  
   A small positive value may arise from simplified contact semantics. Start as diagnostic/optional until the ground model is finalized.

3. **[Open Question] Should maximum flight tilt be a required nominal criterion?**  
   The source requires it in summary, not as a core acceptance limit. Keep optional.

4. **[Open Question] Should landing altitude/ground-position error be validated explicitly?**  
   The state machine recognizes contact and the core source metrics do not list vertical position error. Add only if ground handling needs it.

5. **[Open Question] Should horizontal velocity at touchdown be a required metric/check?**  
   The source only requires horizontal position error. Report/add later if it strengthens landing quality without overbuilding.

6. **[Open Question] Should angular rate at touchdown be checked?**  
   Not source-required. Keep out of core MVP unless nominal results show a need.

7. **[Open Question] Should transition validation require the exact full nominal sequence or only legality/consistency?**  
   Recommended: legality/consistency in generic validator; scenario-specific tests may require the expected full sequence.

8. **[Open Question] Should fault-effect evidence be configurable in ValidationConfig?**  
   Recommended defer. Scenario regression tests can assert effect-specific telemetry while generic validator checks activation and outcome.

9. **[Open Question] What exact numerical tolerance should be frozen?**  
   Recommended absolute `1e-9`, but confirm against final units and deterministic platform behavior.

10. **[Open Question] Should final state ABORT always classify `CONTROLLED_ABORT`, even if transition history is invalid?**  
    Recommended: classify actual state as controlled abort, but invalid transition check causes scenario failure. Alternatively invalid transition could force actual validation fail. Lock one policy in tests.

11. **[Open Question] Should a LANDED run with invalid transition history classify validation fail?**  
    Recommended yes because valid transitions are a required project criterion.

12. **[Open Question] Should ValidationError be used for a missing touchdown frame or should it return a failed data check?**  
    Recommended: out-of-range/missing frame is structural ValidationError; frame-state mismatch is a returned failed consistency check.

13. **[Open Question] Should `ValidationResult` include the full reconstructed mission transition sequence?**  
    Useful for summary/debugging; may duplicate events. Consider a compact tuple of states/reason codes.

14. **[Open Question] Should the reproducibility comparison helper live in Feature 10 or Feature 12 tests?**  
    A small pure helper is useful, but repeated execution remains outside the validator.

15. **[Open Question] Should expected-outcome matching alone determine CLI exit code?**  
    Feature 15 should use `scenario_passed`, not `mission_succeeded`, so expected controlled abort/failure scenarios can exit successfully.

---

# Move On When

- [ ] Nominal landing criteria are objective and automated.
- [ ] Touchdown-frame semantics are unambiguous.
- [ ] Truth is used as test oracle without leaking into controller.
- [ ] LANDED and PASS remain separate.
- [ ] Controlled abort and validation failure are distinct.
- [ ] Expected failure scenarios can pass regression.
- [ ] Fault activation is proven.
- [ ] Transition history is proven.
- [ ] Results are structured for pytest, summary, and CLI.
- [ ] Same input data yields same validation result.
- [ ] Reviewer can explain every pass/fail line.
- [ ] No plot inspection is required to decide outcome.
- [ ] Feature clearly demonstrates systems validation and test-oracle design.
- [ ] No unnecessary rules engine, database, cloud reporting, GUI, or Monte Carlo scope has been added.
- [ ] The project is ready for Feature 11 — Diagnostic Visualization.
