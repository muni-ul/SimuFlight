# Feature 11 — Diagnostic Visualization

> **Project:** AstraLoop — Python Software-in-the-Loop Flight Control & Validation System  
> **Feature:** Diagnostic Visualization  
> **Document path:** `docs/features/11-diagnostic-visualization.md`  
> **Status:** Implementation specification  
> **Primary goal:** Generate one clean, deterministic, headless Matplotlib diagnostic figure from completed immutable telemetry, events, resolved configuration, and validation results so a reviewer can inspect trajectory, truth-vs-measurement behavior, requested-vs-applied actuation, mission phases, fault timing, and final outcome without launching a GUI or relying on plot appearance as the validation oracle.

---

## Scope Boundary

**[Confirmed]** AstraLoop should prefer:

```text
one clean diagnostic figure
```

over:

```text
a complex GUI/dashboard
```

for the MVP.

**[Confirmed]** The recommended plot content is:

- trajectory;
- altitude and vertical velocity versus time;
- pitch versus time;
- throttle command versus actual throttle;
- mission-state markers;
- fault-event markers.

**[Confirmed]** Every portfolio-ready persisted run should include:

```text
flight_plot.png
```

inside the same immutable run bundle as:

```text
telemetry.csv
events.json
resolved_config.json
summary.json
```

**[Confirmed]** The plotter must consume completed telemetry or a completed run result, not mutable live simulation state.

**[Confirmed]** Validation must remain separate from plotting.

The plot must not decide whether a mission passed.

**[Confirmed]** Plot generation must work with a non-interactive/headless Matplotlib backend so that:

```text
pytest
CI
local batch runs
```

do not launch a window.

**[Confirmed]** Tests should not rely on exact pixel comparison.

**[Confirmed]** A lightweight replay/GIF is optional only after the static diagnostic plot is stable.

**[Decision]** Feature 11 owns the **post-run static diagnostic-figure layer**.

It owns:

- typed plot input/view models;
- extraction of plot-ready arrays from completed telemetry;
- plot-time data validation;
- mission-state interval derivation;
- mission-transition marker derivation;
- fault activation/deactivation marker derivation;
- one stable multi-panel figure layout;
- truth-vs-measurement plotting;
- requested-vs-applied actuation plotting;
- mission/fault annotations;
- validation/outcome annotations;
- headless Matplotlib figure creation;
- deterministic figure sizing/dpi/layout;
- `flight_plot.png` rendering;
- clean figure-resource closure;
- plot-generation errors;
- unit and integration tests for plot structure and output existence.

It does **not** own:

- simulation execution;
- telemetry recording;
- event generation;
- mission validation formulas;
- scenario loading;
- control logic;
- fault activation;
- artifact-directory selection;
- summary/CSV/JSON serialization;
- CLI rendering;
- interactive animation;
- live dashboards;
- 3D visualization;
- browser UI.

---

# 1. Feature Overview

## Feature name

**Diagnostic Visualization**

---

## One-sentence description

**[Decision]** Implement a deterministic headless Matplotlib plotter that turns completed AstraLoop run data into one reviewer-friendly multi-panel PNG showing the vehicle trajectory, software-visible measurements, controller requests, physical actuator response, mission phases, faults, and objective run result.

---

## Detailed description

AstraLoop's strongest demo is not just:

```text
the vehicle moved
```

It is the relationship between:

```text
truth
measurements
mission state
controller command
actuator response
fault timing
physical outcome
```

A high-value diagnostic figure should let the reviewer answer:

1. Where did the vehicle travel?
2. Did measured altitude/velocity/pitch follow truth?
3. When did mission phases change?
4. What did the controller request?
5. What did the actuator actually apply?
6. When did a fault activate or deactivate?
7. What changed after the fault?
8. What was the final validated outcome?

The plotting flow is:

```text
CompletedTelemetry
ValidationResult
ResolvedScenarioConfig
        |
        v
build PlotData
        |
        v
create Matplotlib Figure/Axes
        |
        +--> trajectory panel
        +--> altitude panel
        +--> vertical velocity panel
        +--> pitch panel
        +--> throttle panel
        +--> gimbal panel
        |
        +--> mission-state spans
        +--> mission transition markers
        +--> fault lifecycle markers
        +--> result/metric summary
        |
        v
Figure
        |
        v
flight_plot.png
```

---

## Primary visual artifact

**[Decision]** The MVP creates exactly one required static figure:

```text
flight_plot.png
```

A second figure should not be required to understand the run.

### Why one figure

- easy to open during a recruiter demo;
- easy to place in README screenshots;
- no dashboard navigation;
- clear artifact contract;
- keeps plotting implementation finishable;
- encourages disciplined information hierarchy.

---

## Figure layout

**[Decision]** Use one figure with a 3-row × 2-column layout:

```text
+---------------------------+---------------------------+
| A. 2D trajectory          | B. Altitude vs time       |
| true path + target/ground | truth + measured          |
+---------------------------+---------------------------+
| C. Vertical velocity      | D. Pitch vs time          |
| truth + measured + target | truth + measured + target |
+---------------------------+---------------------------+
| E. Throttle               | F. Gimbal / attitude cmd  |
| requested vs actual       | requested vs actual       |
+---------------------------+---------------------------+
```

Recommended Matplotlib structure:

```python
fig, axes = plt.subplots(
    nrows=3,
    ncols=2,
    figsize=(14, 12),
    constrained_layout=True,
)
```

A `GridSpec` is acceptable if a more readable trajectory panel needs additional width, but the first implementation should remain simple.

---

## Why separate altitude and vertical velocity panels

The source wording says:

```text
altitude and vertical velocity vs time
```

They have different units and different diagnostic meaning.

**Decision]** Use separate panels rather than dual y-axes.

### Why

Dual axes can make:

- scale comparison misleading;
- legends confusing;
- fault effects harder to read;
- tests/layout less predictable.

---

## Why include a gimbal panel

The source explicitly requires pitch and requested-vs-actual actuation.

Feature 05 models both:

```text
throttle
gimbal
```

**Decision]** Include requested-vs-actual gimbal in the sixth panel.

This gives a complete actuator story and makes degraded gimbal response immediately visible.

---

## Figure title

Recommended:

```text
AstraLoop — <scenario_id>
<ACTUAL_OUTCOME> | expected <EXPECTED_OUTCOME> | seed <seed>
```

Example:

```text
AstraLoop — altimeter_freeze
CONTROLLED ABORT | expected CONTROLLED ABORT | seed 42
```

A concise subtitle may include:

```text
final state
final time
config digest prefix
```

Do not put every metric in the title.

---

## Validation summary box

**[Decision]** Add one compact figure-level text box containing the most important validation results.

For a landed run:

```text
Landing |vy|: 1.31 m/s  (limit 2.00)
Horizontal error: 2.18 m (limit 5.00)
Pitch error: 1.84°       (limit 5.00)
Scenario: PASS
```

For a controlled abort:

```text
Final state: ABORT
Actual outcome: CONTROLLED_ABORT
Expected: CONTROLLED_ABORT
Faults activated: 1/1
Scenario: PASS
```

For a simulator error/diagnostic plot:

```text
SIMULATOR ERROR
tick 241, t=4.82 s
<concise error code/message>
```

### Source of values

The plotter receives these values from:

```text
ValidationResult
RunSummary/error data
```

It does not recompute PASS/FAIL criteria.

---

## Plot data source

Primary input:

```python
CompletedTelemetry
```

Additional inputs:

```python
ResolvedScenarioConfig
ValidationResult | None
Run error metadata | None
```

Recommended public boundary:

```python
def create_flight_figure(
    *,
    telemetry: CompletedTelemetry,
    config: ResolvedScenarioConfig,
    validation: ValidationResult | None,
    error: ErrorSummary | None = None,
) -> Figure:
    ...
```

And file boundary:

```python
def write_flight_plot(
    path: Path,
    *,
    telemetry: CompletedTelemetry,
    config: ResolvedScenarioConfig,
    validation: ValidationResult | None,
    error: ErrorSummary | None = None,
    dpi: int = 150,
) -> None:
    ...
```

---

## Why accept CompletedTelemetry rather than read CSV

Feature 11 is integrated directly after the run.

Using typed in-memory data:

- avoids reparsing;
- preserves enums and missing-value semantics;
- allows stronger type checking;
- avoids CSV precision/format concerns.

### Optional later offline boundary

A future helper may read a finalized run directory:

```python
plot_run_directory(path)
```

but it is not required for the MVP.

The existing PNG already allows post-run inspection.

---

## PlotData view model

Recommended immutable flattened representation:

```python
@dataclass(frozen=True)
class PlotData:
    time_s: np.ndarray

    true_x_m: np.ndarray
    true_y_m: np.ndarray
    true_vy_m_s: np.ndarray
    true_theta_deg: np.ndarray

    measured_y_m: np.ndarray
    measured_vy_m_s: np.ndarray
    measured_theta_deg: np.ndarray

    command_throttle: np.ndarray
    actual_throttle: np.ndarray

    command_gimbal_deg: np.ndarray
    actual_gimbal_deg: np.ndarray

    mission_state: tuple[MissionState, ...]
    frame_kind: tuple[TelemetryFrameKind, ...]

    mission_intervals: tuple[MissionInterval, ...]
    mission_events: tuple[PlotEvent, ...]
    fault_events: tuple[PlotEvent, ...]
```

Use NumPy arrays for numerical plotting convenience.

---

## Missing measurements

A sensor can be:

```text
UNAVAILABLE
DISABLED
```

and therefore store `None`.

Matplotlib should not receive object arrays of mixed floats/None.

**[Decision]** Convert missing values to:

```text
np.nan
```

inside the **plot-only view model**.

This does not violate Feature 09's no-NaN persistence rule because:

- completed telemetry remains unchanged;
- NaN is used only as Matplotlib's conventional line-gap marker;
- the plotter does not serialize NaN to run data.

Matplotlib naturally breaks the measured line at unavailable intervals.

---

## Stale measurements

Feature 03 stale readings retain a finite held value.

**[Decision]** Plot the stale measured value continuously, but mark stale intervals/points distinctly.

Recommended:

- measured line remains visible;
- overlay small markers only where status is `STALE`;
- do not draw markers on every valid sample.

This makes an altimeter freeze obvious:

```text
flat measured line
stale markers
truth continues changing
fault activation marker
```

---

## Disabled measurements

Do not draw a legend entry for a channel that is:

```text
DISABLED/UNAVAILABLE for every frame
```

The panel still plots truth.

If a required comparison series has no finite values, add a concise panel annotation:

```text
measurement unavailable
```

---

## Sample-and-hold appearance

Sensor values may update less frequently than the simulation tick.

**Decision]** Plot measured state with a step style:

```python
drawstyle="steps-post"
```

Truth remains a continuous line.

### Why

This visually communicates discrete sensor sampling and held values.

It also makes:

- sampling cadence;
- freeze behavior;
- delay behavior;

more interpretable.

---

## Trajectory panel

Panel A shows:

```text
true x versus true y
```

Required elements:

- true trajectory line;
- start marker;
- end/touchdown/abort marker;
- ground line at configured `ground_y`;
- landing target marker at:

```text
(target_x, ground_y)
```

- equal or data-preserving aspect decision;
- axis labels with units;
- grid;
- legend.

---

## Trajectory aspect ratio

**Decision]** Default to:

```python
ax.set_aspect("equal", adjustable="datalim")
```

when the data range remains readable.

### Risk

Very tall/narrow flight can make horizontal error visually tiny.

**Fallback decision:** use normal auto aspect if equal aspect produces an unusably compressed figure according to a simple range-ratio rule.

Recommended rule:

```text
if max_range / min_nonzero_range > 20:
    use auto aspect
else:
    use equal
```

This is visualization logic, not validation.

---

## Trajectory target

Validation config provides:

```text
target_x
```

Environment config provides:

```text
ground_y
```

Plot target as a distinct marker.

Do not assume target x is zero inside plot logic.

---

## Endpoint marker

Use endpoint type based on outcome:

```text
LANDED/PASS
LANDED/VALIDATION_FAIL
ABORT
MAX_TIME/nonterminal
ERROR
```

Exact marker shape/color is presentation configuration.

Do not infer outcome by scenario name.

---

## Altitude panel

Panel B plots:

```text
true y
measured y
```

against simulation time.

Optional/required references:

- ground altitude line;
- landing-entry altitude threshold;
- landed/contact threshold;
- ascent/coast altitude threshold.

**Decision]** To prevent clutter, show:

- ground line always;
- mission threshold lines only when they materially help and labels fit.

Recommended default:

```text
landing-entry altitude
landed threshold
```

Ascent cutoff may be shown in long ascent scenarios.

---

## Altitude panel fault story

For altimeter freeze:

- measured line becomes flat;
- true line continues;
- fault activation line appears;
- stale markers appear when status changes;
- mission transition/abort marker appears.

This is the primary recruiter fault demo.

---

## Vertical-velocity panel

Panel C plots:

```text
true vy
measured vy
```

against time.

Also show mode-specific controller target vertical velocity as a step series.

### Target extraction

Use:

```text
frame mission_state
+ resolved controller profile
```

to create:

```text
target_vy(t)
```

This is a configured target, not recalculated control logic.

---

## Landing limit reference

**Decision]** Show horizontal lines at:

```text
+max_landing_vertical_speed
-max_landing_vertical_speed
```

only during/near the landing phase or with a clear label.

A full-run line is acceptable because it is easy to interpret, but it must not imply the vehicle must remain inside landing limits throughout ascent/descent.

Recommended:

- use a light shaded band across the LANDING mission interval;
- label it:

```text
landing-speed limit
```

Do not allow the plot to become the validator.

---

## Pitch panel

Panel D plots:

```text
true pitch [deg]
measured pitch [deg]
target pitch [deg]
```

against time.

Use degrees for reviewer readability.

Source telemetry remains radians.

### Optional validation band

Show:

```text
target pitch ± max landing pitch error
```

only during the LANDING phase.

### Angular representation

**Decision]** Convert each stored theta independently to degrees.

Do not apply temporal unwrapping by default.

Why:

- control/validation operate on orientation near upright;
- unwrapping could display multiple rotations differently from the validation angle;
- the simplified mission should remain within a moderate tilt envelope.

If discontinuities near ±180° become a real debugging problem, add an optional unwrapped diagnostic later.

---

## Throttle panel

Panel E plots:

```text
requested throttle
actual throttle
```

against time.

Required:

- y range normally includes `[0, 1]`;
- requested line;
- actual line;
- optional saturation markers/regions;
- grid/legend.

### Plot style

Use step style for requested command.

Actual throttle can use continuous line because actuator lag evolves each simulation tick.

---

## Gimbal panel

Panel F plots:

```text
requested gimbal [deg]
actual gimbal [deg]
```

against time.

Required:

- zero reference line;
- requested step line;
- actual continuous line;
- physical gimbal limits if available from config;
- optional saturation/rate-limit markers.

This panel is especially valuable for `degraded_actuator`.

---

## Mission-state intervals

Mission state should be understandable without adding a seventh axis.

**[Decision]** Render mission state as subtle vertical background spans on all time-series panels:

```text
B–F
```

Each contiguous state interval receives a stable translucent span.

Do not add mission spans to the 2D trajectory panel.

---

## Mission interval derivation

Given frame mission states:

```text
PRELAUNCH, PRELAUNCH, ASCENT, ASCENT, ...
```

derive contiguous intervals:

```python
@dataclass(frozen=True)
class MissionInterval:
    state: MissionState
    start_time: float
    end_time: float
```

The final interval ends at final telemetry time.

---

## Mission colors

The plot requires stable state differentiation.

Recommended semantic palette:

```text
PRELAUNCH  neutral gray
ASCENT     blue
COAST      purple
DESCENT    orange
LANDING    green
LANDED     dark green
ABORT      red
```

**Decision]** Define one centralized palette in plotting code.

Do not derive colors from Python hash/order.

### Accessibility

Use low-opacity spans and readable labels/line styles.

Do not rely on background color alone:

- transition markers/labels exist;
- titles/legends identify series;
- line styles distinguish truth/measurement/requested/actual.

---

## Mission interval legend

Adding all state spans to every axis legend would create duplicates.

**Decision]** Use one compact figure-level mission-state legend or annotate state names at the top of one time-series panel.

Recommended initial implementation:

- annotate state names near the top of altitude panel at interval midpoint;
- omit span handles from normal legends.

Only annotate intervals wide enough to fit.

---

## Mission transition markers

Use mission transition events as thin vertical markers on time-series panels.

Recommended:

- draw vertical line at transition time;
- label on altitude panel only:

```text
ASCENT→COAST
DESCENT→LANDING
```

- avoid labels on all panels.

### Why both spans and markers

Spans show duration.

Markers show exact transition tick.

---

## Fault markers

Fault activation/deactivation must be obvious.

**Decision]** Render:

- activation: prominent vertical line with label;
- deactivation: distinct dashed vertical line with label;
- apply marker to all time-series panels;
- label activation/deactivation on the top/altitude panel only.

Example labels:

```text
FAULT ON
freeze_altimeter_01
```

```text
FAULT OFF
freeze_altimeter_01
```

For multiple same-tick faults, combine or vertically stagger labels to avoid complete overlap.

---

## Fault marker colors

Use one consistent activation/deactivation presentation separate from mission colors.

Recommended semantics:

```text
activation = red/crimson
deactivation = dark neutral or red dashed
```

Exact style belongs to the centralized plot theme.

---

## Multiple faults

**Decision]** Display every lifecycle event.

When many fault events occur:

- group same-tick activations into one multiline label;
- keep event tick lines;
- avoid a giant fault legend;
- title/summary box reports activated count.

The MVP scenarios have few faults, so elaborate collision-avoidance algorithms are unnecessary.

---

## Truth vs measurement line semantics

Use consistent line meaning across panels:

```text
truth       solid line
measurement step line, different color/style
target      dashed step line
requested   dashed/step
actual      solid
```

A reviewer should infer line meaning without relearning each panel.

---

## Line labels

Recommended:

```text
Truth
Measured
Target
Requested
Actual
```

Add variable context in axis title, not every legend label.

---

## Units

Use explicit units on axes:

```text
Horizontal position [m]
Altitude [m]
Vertical velocity [m/s]
Pitch [deg]
Throttle command [-]
Gimbal angle [deg]
Time [s]
```

Trajectory y-axis:

```text
Vertical position [m]
```

---

## Grid

Use a light grid on every panel.

Do not apply heavy styling that obscures data.

---

## Matplotlib style

The stack specifies Matplotlib, not a design framework.

**[Decision]** Use a small project-owned style helper:

```python
def apply_plot_style() -> None:
    ...
```

or use `matplotlib.rc_context(...)`.

Do not globally mutate Matplotlib settings at import time.

### Why context-local styling

- tests do not leak styles;
- embedding remains predictable;
- unrelated figures are unaffected;
- repeated calls are deterministic.

---

## Backend

**[Decision]** Plotting tests and normal headless runs use:

```text
Agg
```

non-interactive backend.

Recommended implementation guidance:

- do not call `matplotlib.use(...)` after importing `pyplot`;
- configure backend through environment/test setup before `pyplot` import, or import `Figure`/canvas APIs carefully;
- use `MPLBACKEND=Agg` in test/CI environment if simplest.

The core plotter never calls:

```python
plt.show()
```

---

## Figure creation without global pyplot state

Recommended:

```python
from matplotlib.figure import Figure

figure = Figure(...)
canvas = FigureCanvasAgg(figure)
```

or disciplined `pyplot` usage with explicit close.

**Decision]** Prefer explicit `Figure` plus Agg canvas if it remains straightforward.

This minimizes global state and supports headless execution cleanly.

---

## Figure closure

When `write_flight_plot(...)` creates a figure:

- save it;
- close/release it in `finally`;
- do not leave accumulating open figures during campaigns/tests.

A function returning a `Figure` transfers closure responsibility to caller.

Document this distinction.

---

## Output format

Required:

```text
PNG
```

File:

```text
flight_plot.png
```

Recommended:

```text
dpi = 150
bbox_inches = "tight"
```

Use RGB/RGBA standard output.

No SVG/PDF requirement for MVP.

---

## Figure size

Recommended:

```text
14 × 12 inches
```

at:

```text
150 dpi
```

approximately:

```text
2100 × 1800 pixels
```

This is detailed enough for local inspection and README cropping without producing huge files.

**[Open Question]** Final exact dimensions after visual QA.

---

## Determinism

Given identical:

```text
CompletedTelemetry
ResolvedScenarioConfig
ValidationResult
plot configuration
Matplotlib version
```

the figure structure and visible data must be deterministic.

PNG byte identity is not a required cross-platform guarantee because metadata/font rendering may differ.

---

## Plot schema/version

**[Decision]** Define:

```text
plot layout version = 1
```

Include it in internal metadata and optionally PNG metadata.

Recommended PNG metadata:

```text
Title
Description
Software
AstraLoopPlotVersion
ScenarioId
ConfigDigest
```

Do not include wall-clock generation time if deterministic PNG metadata is desired.

---

## PNG metadata

Optional implementation:

```python
metadata = {
    "Title": ...,
    "Software": "AstraLoop",
    "AstraLoopPlotVersion": "1",
    "ScenarioId": config.id,
    "ConfigDigest": config_digest,
}
```

The exact supported Matplotlib/Pillow metadata behavior should be tested before making it a hard contract.

Do not let metadata implementation delay the figure.

---

## Validation annotation

The plotter receives `ValidationResult`.

It may display:

- actual outcome;
- expected outcome;
- scenario passed;
- core landing metrics;
- fault activation count.

It must not recompute outcome.

---

## Outcome presentation

Recommended prominent text:

```text
SCENARIO PASS
```

or:

```text
SCENARIO FAIL
```

plus:

```text
actual: CONTROLLED_ABORT
expected: CONTROLLED_ABORT
```

This prevents the viewer from mistaking an expected abort for a broken test.

---

## Diagnostic error plot

Feature 09 allows a partial ERROR telemetry bundle.

**[Decision]** Feature 11 supports best-effort plotting of partial/error telemetry when at least one frame exists.

Behavior:

- title shows `SIMULATOR ERROR`;
- plot available valid data;
- final error tick vertical marker;
- validation metrics omitted;
- summary box contains concise error information;
- missing controller/actuator/measurement data create gaps/annotations.

If safe plotting cannot be completed, error bundle may omit PNG.

Plot failure must never hide the original `SimulationError`.

---

## Empty/incomplete telemetry behavior

### No frames

Raise:

```text
PlotError
```

### One terminal frame

Generate a valid minimal figure:

- one trajectory point;
- time-series point;
- annotations;
- no line assumptions.

### ERROR frame only

Generate if required fields are valid.

### Final frame CONTROL

Feature 09/10 should reject incomplete telemetry.

Plotter also rejects it rather than presenting an apparently completed run.

---

## Non-finite values

Completed telemetry should not contain non-finite truth/controller/actuator values.

PlotData conversion validates:

- truth arrays finite;
- controller/actuator arrays finite where present;
- measured `np.nan` only for intentionally missing plot values.

If unexpected non-finite data exists:

```text
raise PlotError
```

Do not autoscale or silently drop corrupt truth data.

---

## Missing controller/actuator data

A terminal-at-start or error frame may have no controller/actuator data.

Behavior:

- convert to `np.nan`;
- annotate panel if no finite data exists;
- do not invent zero command.

---

## Mismatched lengths

All frame-derived arrays must have the same length.

If not:

```text
PlotError
```

This should be impossible with a correctly built `PlotData`, but validate.

---

## Event outside telemetry time range

A mission/fault event tick/time outside frame range indicates artifact inconsistency.

**Decision]** Raise `PlotError` rather than drawing it off-plot.

---

## Duplicate mission transition events

Feature 10 should identify this.

Plotter may still render them, but the figure should not silently hide inconsistency.

**Decision]** Plotter accepts ordered events and renders them; validation result/summary box shows scenario failure.

Only structurally malformed events cause PlotError.

---

## Data decimation

MVP expected frames:

```text
approximately 3,000
```

No decimation required.

Do not add:

- downsampling framework;
- LTTB;
- data aggregation;
- streaming visualization.

Matplotlib handles this scale easily.

---

## Legends

Each panel has a concise legend only for visible series.

Do not include:

- duplicate mission-state entries;
- every fault ID as a legend item;
- empty series.

Use figure-level annotations for mission/fault context.

---

## Tight label management

Potential label collisions:

- mission state text;
- fault activation text;
- fault deactivation text;
- transition markers.

**Decision]** Labels appear only on altitude panel.

Other time-series panels receive vertical lines/spans without text.

Use small font and stagger y-position by event index when same-tick events occur.

---

## Figure accessibility

MVP requirements:

- line styles distinguish series;
- markers identify starts/endpoints/stale samples;
- labels/units are explicit;
- outcome text is present;
- do not rely exclusively on color.

No formal WCAG certification is required for the local artifact.

---

## Optional replay

A replay GIF is explicitly optional after the static plot.

**Decision]** Do not implement in Feature 11 MVP.

Future:

```text
replay.gif
```

may animate:

- vehicle trajectory;
- orientation;
- mission state;
- fault markers.

It must reuse completed telemetry and must not introduce a live simulation UI.

---

## Why it matters

AstraLoop contains a real architecture, but a reviewer may spend only 60–90 seconds on the demo.

The figure condenses the system into one inspectable artifact:

```text
trajectory
truth vs measurement
control target
requested vs actual actuator response
state transitions
fault timing
validated outcome
```

That is much stronger than:

- a terminal wall of numbers;
- a generic rocket animation;
- a dashboard that hides engineering details;
- a plot with no objective result.

---

## Skill it demonstrates

A strong implementation demonstrates:

- scientific plotting;
- engineering communication;
- post-run observability;
- time-series alignment;
- event annotation;
- immutable data consumption;
- headless graphics;
- testable visualization architecture;
- figure-resource management;
- failure visualization;
- disciplined scope.

---

## Priority

**P1 — High-value portfolio polish**

Objective telemetry and validation are P0.

The static diagnostic figure is the strongest visual layer after the core system is stable.

It should be completed before README screenshots/demo media.

---

## Complexity

**Medium**

The figure is not mathematically complex.

The main risks are:

- clutter;
- time alignment;
- misleading line semantics;
- missing data;
- event-label collisions;
- GUI/backend issues;
- tests that become brittle.

---

# 2. User / Demo Flow

## Happy path — nominal

1. Scenario completes.
2. Telemetry finalizes.
3. Validation returns PASS.
4. PlotData is built.
5. Figure title identifies scenario/seed/outcome.
6. Trajectory panel shows takeoff/flight/landing target.
7. Altitude panel shows truth and measured altitude.
8. Velocity panel shows truth, measurement, and mode target.
9. Pitch panel shows truth, measurement, and target.
10. Throttle/gimbal panels show requested vs actual response.
11. Mission-state spans show flight phases.
12. Transition markers show exact phase changes.
13. Validation summary box shows the three landing checks.
14. Figure is saved as `flight_plot.png`.
15. Feature 09 publishes it in the final run bundle.

---

## Happy path — altimeter freeze

1. Fault activates at exact tick.
2. Plot shows activation marker.
3. Measured altitude line becomes flat/step-held.
4. Truth altitude continues.
5. Stale markers appear.
6. Mission-state/abort transition appears.
7. Outcome box shows actual vs expected controlled abort/failure/pass.
8. Reviewer can explain the entire causal chain from one image.

---

## Happy path — degraded actuator

1. Controller requests change.
2. Requested line steps.
3. Actual actuator line responds more slowly.
4. Fault activation marker identifies when degradation begins.
5. Vehicle pitch/velocity response changes.
6. Final validation result appears.

---

## First-time implementation path

### Stage A — Synthetic trajectory figure

Build PlotData with ten frames.

Create six axes.

### Stage B — Truth/measurement time series

Verify gaps/step lines.

### Stage C — Requested/actual actuation

Verify line semantics.

### Stage D — Mission spans/transitions

Use synthetic event/state sequence.

### Stage E — Fault markers

Activation/deactivation.

### Stage F — Validation summary box

PASS/abort/fail.

### Stage G — Headless PNG write

`tmp_path`.

### Stage H — Real completed telemetry

Nominal scenario.

### Stage I — Fault scenarios

Freeze, bias, delay, degradation.

### Stage J — Error/partial telemetry

Best-effort diagnostic plot.

---

## Empty state

### No frames

`PlotError`.

### No measurements

Truth still plots.

Measurement line/legend omitted or panel annotated.

### No events

Valid.

No vertical markers.

### No faults

Valid.

No fault markers.

### No validation result during staged/error plot

Show final state/error metadata only.

---

## Error path

### Invalid output suffix

Recommended:

```text
write_flight_plot expects .png
```

Reject non-PNG path for MVP.

### Parent directory missing

The artifact writer should create staging directory before plot call.

Standalone plot writer may create parent only if explicitly documented.

**Decision]** `write_flight_plot` requires existing parent directory.

It should not select/create run directories.

### Unwritable path

Raise `PlotError`, preserving cause.

### Save failure

Close figure, raise.

### PlotData inconsistency

Raise before writing.

### Error plot failure during SimulationError handling

Preserve original SimulationError.

Artifact layer may record secondary plot failure.

---

## Reviewer demo path

### Demo A — Nominal figure

Spend approximately 20–30 seconds:

- trajectory;
- landing metrics;
- mode target tracking;
- command vs actuator.

### Demo B — Fault figure

Spend approximately 20–30 seconds:

- fault marker;
- truth/measurement divergence;
- software/actuator response;
- expected outcome.

### Demo C — Tests

Mention plot structure is tested headlessly while PASS/FAIL comes from the validator, not pixels.

---

# 3. UX / UI Requirements

## Screens/pages

One static PNG.

No interactive window required.

---

## Components

Recommended:

```text
PlotData
MissionInterval
PlotEvent
PlotTheme
PlotError

build_plot_data
create_flight_figure
write_flight_plot

panel helper functions
event/span helper functions
```

---

## Plot panels

### Panel A

Title:

```text
2D Trajectory
```

### Panel B

```text
Altitude
```

### Panel C

```text
Vertical Velocity
```

### Panel D

```text
Pitch
```

### Panel E

```text
Throttle: Requested vs Applied
```

### Panel F

```text
Gimbal: Requested vs Applied
```

---

## Figure annotations

Required:

- scenario;
- actual/expected outcome;
- seed;
- validation summary/error summary;
- mission intervals;
- fault markers;
- transition markers.

Optional:

- config digest prefix;
- final time/state.

---

## Responsive behavior

Not interactive/responsive.

Use fixed high-resolution figure suitable for:

- desktop viewing;
- README screenshot;
- sharing in portfolio.

---

## Loading states

None.

---

## Error states

PlotError is explicit.

Do not produce a blank zero-byte PNG.

---

## Typography

Use standard broadly available Matplotlib fonts.

Do not package or require proprietary/custom font files.

---

# 4. Data Requirements

## Entities involved

### `CompletedTelemetry`

Feature 09.

---

### `ResolvedScenarioConfig`

Feature 08.

---

### `ValidationResult`

Feature 10.

---

### `PlotData`

Flattened immutable numeric view.

---

### `MissionInterval`

```python
@dataclass(frozen=True)
class MissionInterval:
    state: MissionState
    start_time: float
    end_time: float
```

---

### `PlotEvent`

```python
@dataclass(frozen=True)
class PlotEvent:
    tick: int
    time: float
    kind: str
    label: str
    event_id: str | None
```

---

### `PlotTheme`

Potential:

```python
@dataclass(frozen=True)
class PlotTheme:
    figure_size: tuple[float, float]
    dpi: int
    line_width: float
    measurement_line_width: float
    state_alpha: float
    grid_alpha: float
```

Keep defaults internal unless configuration is needed.

---

## Relationships

```text
CompletedTelemetry + Config + Validation
                 |
                 v
            PlotData
                 |
                 v
          Matplotlib Figure
                 |
                 v
          flight_plot.png
```

---

## Persistence

PNG only.

Feature 09 owns final bundle publication.

---

# 5. Logic Requirements

## Rule 1 — Plotter consumes completed immutable data

No live simulation dependency.

---

## Rule 2 — Plotter does not calculate PASS/FAIL

---

## Rule 3 — Plotter does not mutate telemetry/config/validation

---

## Rule 4 — Figure layout is stable

Six defined panels.

---

## Rule 5 — Truth and measurement are visually distinct

---

## Rule 6 — Missing measurement creates a line gap

---

## Rule 7 — Stale measurement is visibly marked

---

## Rule 8 — Sensor measurements use step style

---

## Rule 9 — Controller targets/requests use step style

---

## Rule 10 — Actual actuator response uses continuous line

---

## Rule 11 — Time axis uses simulation time only

---

## Rule 12 — Units are explicit

---

## Rule 13 — Trajectory includes target and ground

---

## Rule 14 — Trajectory includes start/end marker

---

## Rule 15 — Mission spans derive from frame mission states

---

## Rule 16 — Mission transition markers derive from events

---

## Rule 17 — Fault markers derive from lifecycle events

---

## Rule 18 — Fault activation is visible on every time-series panel

---

## Rule 19 — Labels appear only where clutter is controlled

---

## Rule 20 — Same-tick event order remains stable

---

## Rule 21 — Validation summary values are supplied, not recomputed

---

## Rule 22 — Expected abort/failure can display scenario PASS

---

## Rule 23 — Plot uses headless backend

---

## Rule 24 — Plotter never calls show

---

## Rule 25 — Figure resources are closed after file writing

---

## Rule 26 — Output is PNG

---

## Rule 27 — Existing run-directory policy remains Feature 09

---

## Rule 28 — Plotter writes only to supplied path

---

## Rule 29 — Parent directory must already exist

---

## Rule 30 — Plotter rejects empty telemetry

---

## Rule 31 — Plotter rejects incomplete CONTROL-ending telemetry

---

## Rule 32 — Plotter rejects corrupt non-finite truth data

---

## Rule 33 — Plot-only NaN is allowed only for missing optional series

---

## Rule 34 — Plotter validates equal array lengths

---

## Rule 35 — Event times must be in telemetry range

---

## Rule 36 — Single-frame runs render

---

## Rule 37 — Error runs can render best-effort

---

## Rule 38 — Plot structure is deterministic

---

## Rule 39 — PNG byte equality is not a cross-platform acceptance requirement

---

## Rule 40 — Tests inspect data/axes/artists, not subjective appearance

---

## Rule 41 — No scenario-ID-specific plotting branches

---

## Rule 42 — Optional replay is outside MVP

---

## Rule 43 — No GUI/dashboard/web server

---

## Rule 44 — No animation during normal pytest

---

## Rule 45 — Plotting does not import simulation engine internals

---

## Rule 46 — Plotting does not parse raw TOML

---

## Rule 47 — Plotting does not read mutable subsystem objects

---

## Rule 48 — Plot colors/styles are centralized

---

## Rule 49 — Color is not the only distinguishing signal

---

## Rule 50 — Figure fits the artifact contract

---

## PlotData construction pseudocode

```python
def build_plot_data(
    telemetry: CompletedTelemetry,
    config: ResolvedScenarioConfig,
) -> PlotData:

    validate_completed_telemetry_for_plot(telemetry)

    frames = telemetry.frames

    time_s = np.asarray(
        [frame.time for frame in frames],
        dtype=float,
    )

    true_x = np.asarray(
        [frame.truth.x for frame in frames],
        dtype=float,
    )

    measured_y = optional_measurement_array(
        frames,
        sensor=SensorName.ALTIMETER,
    )

    target_vy = np.asarray(
        [
            config.controller.profiles[
                frame.mission_state
            ].target_vertical_velocity
            for frame in frames
        ],
        dtype=float,
    )

    mission_intervals = derive_mission_intervals(
        frames
    )

    mission_events = adapt_mission_plot_events(
        telemetry.events
    )

    fault_events = adapt_fault_plot_events(
        telemetry.events
    )

    return PlotData(...)
```

---

## Missing measurement helper pseudocode

```python
def optional_measurement_array(
    frames,
    sensor,
) -> np.ndarray:

    values = []

    for frame in frames:
        reading = frame.measurement.get(sensor)

        if reading is None or reading.value is None:
            values.append(np.nan)
        else:
            values.append(float(reading.value))

    return np.asarray(values, dtype=float)
```

---

## Mission interval pseudocode

```python
def derive_mission_intervals(
    frames: tuple[TelemetryFrame, ...],
) -> tuple[MissionInterval, ...]:

    intervals = []
    start_index = 0
    current_state = frames[0].mission_state

    for index in range(1, len(frames)):
        state = frames[index].mission_state

        if state is current_state:
            continue

        intervals.append(
            MissionInterval(
                state=current_state,
                start_time=frames[start_index].time,
                end_time=frames[index].time,
            )
        )

        start_index = index
        current_state = state

    intervals.append(
        MissionInterval(
            state=current_state,
            start_time=frames[start_index].time,
            end_time=frames[-1].time,
        )
    )

    return tuple(intervals)
```

---

## Mission spans pseudocode

```python
def add_mission_spans(
    axes,
    intervals,
    theme,
) -> None:

    for interval in intervals:
        for ax in axes:
            ax.axvspan(
                interval.start_time,
                interval.end_time,
                alpha=theme.state_alpha,
                color=theme.mission_colors[
                    interval.state
                ],
                zorder=0,
            )
```

---

## Fault markers pseudocode

```python
def add_fault_markers(
    axes,
    fault_events,
) -> None:

    grouped = group_events_by_time(fault_events)

    for time_s, events in grouped:
        for ax in axes:
            ax.axvline(
                time_s,
                ...,
            )

        label_fault_group_on_altitude_axis(
            time_s,
            events,
        )
```

---

## Create figure pseudocode

```python
def create_flight_figure(...):
    data = build_plot_data(telemetry, config)

    with matplotlib.rc_context(PLOT_RC_PARAMS):
        figure = Figure(
            figsize=(14, 12),
            constrained_layout=True,
        )
        FigureCanvasAgg(figure)

        axes = figure.subplots(3, 2)

        plot_trajectory(axes[0, 0], data, config)
        plot_altitude(axes[0, 1], data, config)
        plot_vertical_velocity(
            axes[1, 0],
            data,
            config,
        )
        plot_pitch(
            axes[1, 1],
            data,
            config,
        )
        plot_throttle(axes[2, 0], data)
        plot_gimbal(axes[2, 1], data, config)

        add_mission_spans(
            time_axes,
            data.mission_intervals,
        )
        add_mission_markers(
            time_axes,
            data.mission_events,
        )
        add_fault_markers(
            time_axes,
            data.fault_events,
        )

        add_title_and_summary(
            figure,
            config,
            validation,
            error,
        )

        return figure
```

---

## Write plot pseudocode

```python
def write_flight_plot(path, ...):
    validate_png_path(path)

    if not path.parent.is_dir():
        raise PlotError(...)

    figure = create_flight_figure(...)

    try:
        figure.savefig(
            path,
            dpi=150,
            bbox_inches="tight",
            metadata=...,
        )
    except Exception as exc:
        raise PlotError(...) from exc
    finally:
        figure.clear()
```

If using pyplot:

```python
plt.close(figure)
```

is required.

---

## Edge cases

### All x values equal

Trajectory panel still renders vertical path.

### All y values equal

Single/flat path still renders.

### Very small horizontal scale vs altitude

Aspect fallback.

### One frame

Use scatter/markers; no divide-by-zero assumptions.

### No finite measured values

Omit measured line and annotate.

### One stale point

Marker renders.

### Freeze from tick zero with no previous valid value

Measured series may be entirely unavailable.

Plot truth + fault marker + unavailable annotation.

### Delay creates older values

Step line visibly trails truth.

### Velocity bias

Measured velocity offset visible.

### Degraded actuator

Actual line lags requested line.

### Controller inactive

Requested command may remain zero/held.

Still plot.

### Missing validation result

Show final state/error only.

### Scenario validation fail

Plot still generated.

### Controlled abort

Plot still generated.

### Max-time termination

Plot still generated.

### Error telemetry

Best-effort plot.

### Multiple same-time mission/fault events

Stagger/merge labels.

### Extremely long fault ID

Truncate visual label with ellipsis while full ID remains in events.json.

Recommended maximum display length:

```text
32 characters
```

Do not alter underlying ID.

### Large number of mission intervals

Mission model has few states; no complex solution required.

---

# 6. Acceptance Criteria

## AC-01 — Plotter accepts valid completed telemetry

**Given** completed telemetry, resolved config, and validation result  
**When** figure creation runs  
**Then** it returns a Matplotlib Figure without modifying inputs.

---

## AC-02 — Plotter rejects empty telemetry

**Given** no frames  
**When** plot creation is attempted  
**Then** `PlotError` is raised.

---

## AC-03 — Plotter rejects CONTROL-ending telemetry

**Given** incomplete telemetry whose last frame is CONTROL  
**When** plotting begins  
**Then** it is rejected.

---

## AC-04 — Terminal telemetry can be plotted

**Given** normal telemetry ending TERMINAL  
**When** plotting runs  
**Then** a figure is created.

---

## AC-05 — Error telemetry can be plotted best-effort

**Given** valid telemetry ending ERROR with at least one frame  
**When** diagnostic plotting runs  
**Then** figure identifies simulator error and displays available data.

---

## AC-06 — Figure has six required axes

**Given** normal figure  
**When** axis structure is inspected  
**Then** it contains trajectory, altitude, vertical velocity, pitch, throttle, and gimbal panels.

---

## AC-07 — Figure title contains scenario ID

**Given** scenario config  
**When** figure is created  
**Then** scenario ID appears in figure-level title text.

---

## AC-08 — Figure identifies actual outcome

**Given** ValidationResult  
**When** figure is created  
**Then** actual outcome appears.

---

## AC-09 — Figure identifies expected outcome

**Given** ValidationResult  
**When** figure is created  
**Then** expected outcome appears.

---

## AC-10 — Figure identifies scenario pass/fail

**Given** ValidationResult  
**When** summary annotation is built  
**Then** `scenario_passed` is visible.

---

## AC-11 — Figure includes seed

**Given** resolved scenario seed  
**When** title/subtitle renders  
**Then** seed is visible.

---

## AC-12 — Trajectory uses true x and true y

**Given** telemetry truth path  
**When** trajectory panel is inspected  
**Then** plotted coordinates match truth.

---

## AC-13 — Trajectory includes start marker

**Given** at least one frame  
**When** trajectory panel renders  
**Then** initial truth position is marked.

---

## AC-14 — Trajectory includes final/evaluation marker

**Given** terminal run  
**When** trajectory renders  
**Then** endpoint is marked distinctly.

---

## AC-15 — Trajectory includes ground reference

**Given** configured ground y  
**When** trajectory renders  
**Then** ground reference is visible.

---

## AC-16 — Trajectory includes configured landing target

**Given** target x and ground y  
**When** trajectory renders  
**Then** target is marked at configured position.

---

## AC-17 — Trajectory does not assume target x zero

**Given** nonzero target x  
**When** plotted  
**Then** marker uses configured value.

---

## AC-18 — Altitude panel plots truth

**Given** true y data  
**When** panel renders  
**Then** a truth series exists with correct points.

---

## AC-19 — Altitude panel plots measured altitude when available

**Given** finite altimeter readings  
**When** panel renders  
**Then** measured series exists.

---

## AC-20 — Measured altitude uses step style

**Given** sampled/held values  
**When** artist is inspected  
**Then** draw style represents steps.

---

## AC-21 — Missing altitude readings create gaps

**Given** unavailable readings  
**When** PlotData builds  
**Then** plot-only measured array contains NaN at those positions and line gaps render.

---

## AC-22 — Plot-only NaN does not mutate telemetry

**Given** missing readings  
**When** PlotData conversion occurs  
**Then** CompletedTelemetry remains unchanged and contains no inserted NaN.

---

## AC-23 — Stale altitude points are marked

**Given** stale altimeter status  
**When** altitude panel renders  
**Then** stale locations have a distinct marker/overlay.

---

## AC-24 — Vertical-velocity panel plots truth and measurement

**Given** valid data  
**When** panel renders  
**Then** both series are visible.

---

## AC-25 — Vertical-velocity target follows mission profiles

**Given** frames with multiple mission states  
**When** target series builds  
**Then** each frame uses the resolved profile target for its mission state.

---

## AC-26 — Velocity bias is visually represented

**Given** measured vy differs from truth due to bias  
**When** panel renders  
**Then** the difference is present without correction by plotter.

---

## AC-27 — Pitch panel uses degrees

**Given** telemetry theta in radians  
**When** panel data builds  
**Then** plotted truth/measurement/target values are converted to degrees.

---

## AC-28 — Pitch target follows mission profiles

**Given** configured mission-state pitch targets  
**When** target series builds  
**Then** correct profile values appear.

---

## AC-29 — Throttle panel plots requested and actual

**Given** controller/actuator data  
**When** panel renders  
**Then** two distinct series exist.

---

## AC-30 — Requested throttle uses step style

**Given** desired commands  
**When** artist is inspected  
**Then** requested series is step-like.

---

## AC-31 — Actual throttle uses continuous line

**Given** actuator response  
**When** panel renders  
**Then** actual series connects tick values normally.

---

## AC-32 — Throttle panel supports [0,1] range

**Given** nominal normalized values  
**When** autoscaling/reference logic runs  
**Then** full physical command range is visible.

---

## AC-33 — Gimbal panel plots requested and actual

**Given** gimbal command/state  
**When** panel renders  
**Then** both series exist in degrees.

---

## AC-34 — Gimbal physical limits can be shown

**Given** configured limit  
**When** panel renders  
**Then** positive/negative physical-reference lines are available.

---

## AC-35 — Degraded actuator response remains visible

**Given** requested and actual values diverge  
**When** plotted  
**Then** plotter does not normalize/replace actual data.

---

## AC-36 — Mission intervals derive from frame state

**Given** contiguous frame-state sequence  
**When** intervals derive  
**Then** boundaries match state changes and final time.

---

## AC-37 — Mission spans cover all time-series panels

**Given** mission intervals  
**When** figure renders  
**Then** altitude, velocity, pitch, throttle, and gimbal axes receive spans.

---

## AC-38 — Trajectory panel does not receive mission spans

**Given** normal layout  
**When** artists are inspected  
**Then** state background spans are restricted to time axes.

---

## AC-39 — Mission span colors are stable

**Given** same mission state across runs  
**When** plotted  
**Then** the same centralized style/color is used.

---

## AC-40 — Mission transition markers use event times

**Given** transition event at time t  
**When** markers render  
**Then** vertical line appears at t.

---

## AC-41 — Transition labels appear once

**Given** one mission event  
**When** figure renders  
**Then** text label is added only to designated top/altitude axis, not every panel.

---

## AC-42 — Fault activation markers use lifecycle events

**Given** fault activation event  
**When** markers render  
**Then** line appears at exact activation time.

---

## AC-43 — Fault deactivation markers use lifecycle events

**Given** deactivation event  
**When** markers render  
**Then** distinct line/style appears at exact time.

---

## AC-44 — Fault activation line appears on every time axis

**Given** active fault event  
**When** figure renders  
**Then** all five time-series panels show its time reference.

---

## AC-45 — Fault labels preserve ID

**Given** fault ID  
**When** label is displayed  
**Then** it identifies the correct fault, allowing visual truncation only under documented display policy.

---

## AC-46 — Same-tick fault labels are grouped/staggered deterministically

**Given** multiple events at same time  
**When** labels render  
**Then** output order follows event sequence and remains readable.

---

## AC-47 — No-fault run has no fault marker

**Given** nominal event list  
**When** figure renders  
**Then** no fault lifecycle line/label appears.

---

## AC-48 — Validation metrics are supplied rather than recalculated

**Given** ValidationResult values intentionally differing from independently recomputable test fixture  
**When** summary box renders  
**Then** it uses the supplied result fields.

---

## AC-49 — Expected controlled abort can display scenario PASS

**Given** actual/expected controlled abort and scenario_passed true  
**When** summary renders  
**Then** visual result is not mislabeled as generic failure.

---

## AC-50 — Expected validation failure can display scenario PASS

**Given** matching validation-fail outcome  
**When** summary renders  
**Then** scenario pass is visible while actual mission outcome remains validation fail.

---

## AC-51 — Error plot omits normal validation metrics when unavailable

**Given** simulator error and validation None  
**When** figure renders  
**Then** error summary replaces landing-result box.

---

## AC-52 — Plotter does not call plt.show

**Given** headless execution  
**When** plot is generated  
**Then** no interactive window call occurs.

---

## AC-53 — Plot writes under Agg/headless backend

**Given** test/CI environment  
**When** PNG generation runs  
**Then** no display server is required.

---

## AC-54 — PNG writer requires .png path

**Given** `.pdf`/`.jpg` output path  
**When** write is attempted  
**Then** MVP plot writer rejects it.

---

## AC-55 — PNG parent directory must exist

**Given** missing parent directory  
**When** writer runs  
**Then** PlotError occurs rather than selecting a different location.

---

## AC-56 — Successful write creates nonempty PNG

**Given** valid inputs/path  
**When** writer completes  
**Then** file exists and size is greater than zero.

---

## AC-57 — PNG has expected minimum dimensions

**Given** default figure size/dpi  
**When** image metadata is inspected  
**Then** dimensions meet the documented minimum without requiring exact pixel hash.

---

## AC-58 — Write failure closes figure

**Given** savefig failure  
**When** exception occurs  
**Then** figure resources are released and PlotError preserves cause.

---

## AC-59 — Repeated writes do not leak open figures

**Given** many plot generations  
**When** figure count/resources are inspected under chosen API  
**Then** no unbounded accumulation occurs.

---

## AC-60 — Plot creation does not mutate global Matplotlib style

**Given** rc_context-based plot generation  
**When** it completes  
**Then** prior external rcParams are restored.

---

## AC-61 — Same input produces same axis structure

**Given** identical data/config  
**When** figures are generated  
**Then** axis count, titles, series counts, event-marker counts, and labels match.

---

## AC-62 — Tests do not require pixel-perfect comparison

**Given** plot test suite  
**When** inspected  
**Then** it verifies structure/data/file properties rather than exact raster bytes.

---

## AC-63 — Truth data must be finite

**Given** non-finite truth value  
**When** PlotData builds  
**Then** PlotError occurs.

---

## AC-64 — Missing optional controller data produces gaps/annotation

**Given** terminal-at-start frames with no controller result  
**When** plot renders  
**Then** no zero command is fabricated.

---

## AC-65 — Mismatched array lengths are rejected

**Given** corrupt PlotData lengths  
**When** plotting starts  
**Then** PlotError occurs.

---

## AC-66 — Event outside telemetry range is rejected

**Given** event time beyond final telemetry  
**When** markers build  
**Then** PlotError occurs.

---

## AC-67 — Single-frame telemetry renders

**Given** one valid TERMINAL frame  
**When** figure creation runs  
**Then** all panels render valid point/empty-state content without crashing.

---

## AC-68 — Freeze-at-start unavailable measurement renders

**Given** no finite measured altitude  
**When** altitude panel renders  
**Then** truth remains visible and panel explains measurement unavailability.

---

## AC-69 — Maximum sample count expected for MVP requires no decimation

**Given** approximately 3,000 frames  
**When** figure generates  
**Then** raw frame data is plotted directly.

---

## AC-70 — Plot contains no scenario-name behavior branches

**Given** plotter source  
**When** inspected  
**Then** it does not check IDs such as `altimeter_freeze` to select data logic.

---

## AC-71 — Plotter does not validate mission outcome

**Given** plotter source  
**When** inspected  
**Then** it does not compare speed/error/pitch to limits to decide PASS/FAIL.

---

## AC-72 — Plotter does not record telemetry

**Given** plotter source  
**When** inspected  
**Then** it consumes CompletedTelemetry only.

---

## AC-73 — Plotter does not parse TOML

**Given** plotter source  
**When** inspected  
**Then** it consumes resolved config.

---

## AC-74 — Plotter does not modify artifact directory naming

**Given** Feature 09 staging/final path  
**When** writer is called  
**Then** it writes only supplied `flight_plot.png` path.

---

## AC-75 — Plot is included in completed run bundle

**Given** Feature 09/11 integration and successful normal run  
**When** final bundle publishes  
**Then** `flight_plot.png` exists beside telemetry/events/config/summary.

---

## AC-76 — Validation failure still produces plot

**Given** completed VALIDATION_FAIL run  
**When** persistence enabled  
**Then** plot is generated with failure annotations.

---

## AC-77 — Controlled abort still produces plot

**Given** completed controlled abort  
**When** persistence enabled  
**Then** plot is generated.

---

## AC-78 — Simulator error plot failure does not hide original error

**Given** original SimulationError and secondary plot error  
**When** runner handles diagnostics  
**Then** original simulator error remains primary and plot failure is reported separately.

---

## AC-79 — Figure works locally/offline

**Given** clean installed environment  
**When** plot runs  
**Then** no browser, network, cloud service, database, or external font file is required.

---

## AC-80 — Static diagnostic figure supports reviewer causal analysis

**Given** a fault scenario with complete telemetry/events  
**When** reviewer opens PNG  
**Then** the figure visibly aligns fault timing, software-visible state, command/applied actuation, mission phase, and final outcome.

This is the cross-feature portfolio gate.

---

# 7. Test Plan

## Unit tests — PlotData

Recommended:

```text
tests/unit/test_plot_data.py
```

Cases:

```text
test_build_time_array
test_truth_arrays
test_measurement_arrays
test_none_to_plot_nan
test_stale_mask
test_target_vy_from_profiles
test_target_pitch_from_profiles
test_requested_actual_arrays
test_angles_to_degrees
test_equal_lengths
test_non_finite_truth_rejected
test_incomplete_telemetry_rejected
```

---

## Unit tests — mission intervals/events

```text
tests/unit/test_plot_events.py
```

Cases:

```text
test_single_mission_interval
test_multiple_mission_intervals
test_final_interval_end_time
test_transition_event_adaptation
test_fault_activation_adaptation
test_fault_deactivation_adaptation
test_same_tick_event_order
test_event_outside_range
test_long_fault_id_display
```

---

## Unit tests — figure structure

```text
tests/unit/test_plotting.py
```

Inspect Figure/Axes/Artists:

```text
test_six_axes
test_axis_titles
test_axis_units
test_trajectory_series
test_start_end_markers
test_target_marker
test_ground_line
test_altitude_truth_measurement
test_velocity_truth_measurement_target
test_pitch_truth_measurement_target
test_throttle_requested_actual
test_gimbal_requested_actual
test_mission_spans
test_transition_markers
test_fault_markers
test_summary_text
test_error_summary_text
```

Avoid assertions on exact RGB pixels.

---

## Unit tests — writer

```text
tests/unit/test_plot_writer.py
```

Using `tmp_path`:

```text
test_write_png
test_nonempty_png
test_image_dimensions
test_wrong_suffix
test_missing_parent
test_save_failure_wrapped
test_repeated_writes_no_leak
test_rcparams_restored
```

Use Pillow only if already transitively available through Matplotlib and justified for reading dimensions; otherwise use Matplotlib/Python image header utilities.

Do not add a direct image-processing dependency solely for one test if avoidable.

---

## Integration tests — telemetry to figure

Recommended:

```text
tests/integration/test_diagnostic_visualization.py
```

### Nominal run

Assert:

- figure generated;
- six axes;
- final bundle plot exists;
- validation summary shows pass.

### Altimeter freeze

Assert:

- activation marker count;
- measured altitude becomes flat/stale in PlotData;
- truth continues;
- abort/final transition marker exists.

### Velocity bias

Assert measured-vs-truth separation in velocity data.

### Sensor delay

Assert measured altitude/velocity trails truth based on actual telemetry.

### Degraded actuator

Assert requested/actual series diverge after activation.

---

## Artifact integration tests

Extend:

```text
tests/integration/test_runner_artifacts.py
```

Cases:

```text
test_full_bundle_includes_flight_plot
test_validation_failure_includes_plot
test_controlled_abort_includes_plot
test_artifact_root_none_does_not_write_plot
test_plot_write_failure_prevents_normal_bundle_publication
test_error_bundle_plot_optional
```

---

## Headless tests

CI/test environment:

```text
MPLBACKEND=Agg
```

Assert no `show()` calls.

A monkeypatch can make `plt.show` raise if invoked.

---

## Structural determinism tests

Generate twice from identical data.

Compare:

- axis count;
- titles;
- plotted x/y arrays;
- line labels/styles;
- number/times of event markers;
- mission span intervals;
- summary text.

Do not require byte-identical PNG.

---

## Manual QA checklist

- [ ] One figure explains the run.
- [ ] Six panels are readable.
- [ ] Truth and measurement are distinguishable.
- [ ] Measured values visibly step/hold.
- [ ] Stale measurements are marked.
- [ ] Trajectory target/ground are visible.
- [ ] Mission phases are visible without dominating.
- [ ] Transition labels are readable.
- [ ] Fault activation is obvious.
- [ ] Fault deactivation is distinguishable.
- [ ] Requested vs actual throttle is visible.
- [ ] Requested vs actual gimbal is visible.
- [ ] Landing/abort/failure outcome is clear.
- [ ] Expected failure can still display scenario PASS.
- [ ] Units are explicit.
- [ ] Legends are not cluttered.
- [ ] Long scenarios remain readable.
- [ ] One-frame/error plots do not crash.
- [ ] No GUI opens in tests.
- [ ] Figure closes after writing.
- [ ] `flight_plot.png` lands in final bundle.
- [ ] Plot does not make validation decisions.
- [ ] No scenario-name branch exists.
- [ ] Pyright/Ruff/pytest pass.

---

## Demo verification checklist

- [ ] Nominal figure fits on one screen.
- [ ] Reviewer can identify start/end/target.
- [ ] Reviewer can point out mission phases.
- [ ] Reviewer can compare truth and measurement.
- [ ] Reviewer can compare request and physical response.
- [ ] Fault marker aligns with changed subsystem behavior.
- [ ] Final outcome/metrics are visible.
- [ ] Figure works in README screenshot.
- [ ] Same runner automatically creates it.
- [ ] Static figure is understandable without a live animation.
- [ ] Optional replay remains unnecessary for MVP.

---

# 8. Portfolio Value

## How this feature helps the project stand out

Feature 11 is the visual bridge between AstraLoop's architecture and a reviewer's limited attention.

The strongest demonstration is:

> "This one figure shows the physical trajectory, what the flight software measured, which mission phase it was in, what control it requested, what the actuator actually applied, when the fault occurred, and the objective result."

That is substantially stronger than:

- a rocket animation with no engineering data;
- a dashboard with unclear source-of-truth;
- a collection of unrelated charts;
- a PASS label with no causal evidence.

---

## What to mention in README

Recommended wording:

> **Diagnostic visualization:** Every persisted run includes one headless Matplotlib figure showing the 2D trajectory, truth-vs-measurement state, mission-state intervals, fault events, controller requests, applied actuator response, and objective outcome.

Useful bullets:

- static `flight_plot.png`;
- six-panel engineering view;
- mission spans;
- fault markers;
- step-held sensor measurements;
- stale-reading markers;
- requested vs actual throttle/gimbal;
- works in CI/headless mode;
- plot is explanatory, not the PASS/FAIL oracle.

---

## What to mention in interviews

### Why a static figure instead of a dashboard?

> "The project is a local validation tool, not a SaaS product. One strong deterministic figure is faster to inspect, easier to test, and keeps the engineering focus on the simulation."

### How do you align events with the plotted data?

> "Telemetry and events use the same integer simulation tick clock. Fault and mission markers use their event times, and the same telemetry frame at that tick reflects the active state/effect."

### Why are measurement lines stepped?

> "Sensors sample discretely and hold values between samples. The step style communicates that software timing rather than implying a continuous perfect measurement."

### What happens to unavailable readings?

> "Telemetry keeps them as explicit missing values and statuses. The plot-only view converts them to NaN so Matplotlib draws a gap instead of inventing zero."

### How do you show a sensor freeze?

> "The measured line holds flat, stale markers appear as age grows, truth continues changing, and the fault activation marker identifies the exact start."

### How do you show actuator degradation?

> "Requested command is a step signal, while actual actuation is continuous. A sluggish actuator visibly lags after the fault marker."

### Does the plot decide PASS/FAIL?

> "No. The validator calculates objective outcomes from completed truth telemetry. The plot only displays the supplied ValidationResult."

### How did you test visualization without brittle screenshots?

> "Tests inspect PlotData, axes, series arrays, labels, spans, marker times, file existence and dimensions. I deliberately avoid pixel-perfect comparisons."

### How does it run in CI?

> "The plotting path uses a non-interactive Agg backend and never calls `show()`."

---

# 9. Implementation Notes for Codex

## Likely files/folders

Recommended source location from the selected architecture:

```text
src/astraloop/telemetry/
├── __init__.py
├── recorder.py
├── serialization.py
└── plotting.py
```

Potential split only if justified:

```text
src/astraloop/telemetry/
├── plotting.py
└── plot_models.py
```

Tests:

```text
tests/unit/
├── test_plot_data.py
├── test_plot_events.py
├── test_plotting.py
└── test_plot_writer.py

tests/integration/
└── test_diagnostic_visualization.py
```

---

## Suggested responsibilities

### `telemetry/plotting.py`

Own:

- PlotError;
- PlotData;
- MissionInterval;
- PlotEvent;
- theme/constants;
- PlotData conversion;
- figure/panel helpers;
- event/spans;
- summary annotation;
- PNG writer.

Do not own artifact directory selection.

---

## Build order

### Step 1 — Freeze figure contract

Six axes, titles, units, event semantics.

---

### Step 2 — Implement PlotData conversion

No Matplotlib yet.

Test arrays/masks.

---

### Step 3 — Implement mission intervals/events

Test independently.

---

### Step 4 — Create bare six-panel figure

Titles/labels only.

---

### Step 5 — Add trajectory

Start/end/ground/target.

---

### Step 6 — Add truth/measurement/targets

Altitude, vy, pitch.

---

### Step 7 — Add requested/actual actuation

Throttle/gimbal.

---

### Step 8 — Add mission spans/transition markers

Control clutter.

---

### Step 9 — Add fault markers

Exact event times.

---

### Step 10 — Add validation/error summary

No recomputation.

---

### Step 11 — Implement headless writer/closure

PNG + tests.

---

### Step 12 — Integrate Feature 09 staging bundle

`flight_plot.png`.

---

### Step 13 — Add real scenario visual tests

Nominal + four faults.

---

### Step 14 — Do manual visual QA once

Tests cannot decide all layout quality.

Document any deliberate style adjustment.

---

## Risks

### Risk 1 — Figure is too cluttered

**Mitigation:** labels only on altitude panel; subtle spans; six purposeful panels; concise legends.

---

### Risk 2 — Plot becomes a second validator

**Mitigation:** display supplied ValidationResult only.

---

### Risk 3 — Truth/measurement timing appears misaligned

**Mitigation:** use Feature 09 state-tick telemetry contract and step style.

---

### Risk 4 — Missing measurement plotted as zero

**Mitigation:** plot-only NaN gaps.

---

### Risk 5 — Fault marker off by one tick

**Mitigation:** use structured event time directly.

---

### Risk 6 — Mission spans inferred incorrectly

**Mitigation:** derive from frame states; cross-check event tests.

---

### Risk 7 — GUI window opens in pytest

**Mitigation:** Agg backend; no show.

---

### Risk 8 — Matplotlib global state leaks

**Mitigation:** `rc_context` and explicit figure lifecycle.

---

### Risk 9 — Figure resource leak in campaigns

**Mitigation:** writer closes every created figure.

---

### Risk 10 — Pixel tests break across platforms

**Mitigation:** structural artist/data tests.

---

### Risk 11 — Equal trajectory aspect becomes unreadable

**Mitigation:** range-ratio fallback.

---

### Risk 12 — Optional animation delays MVP

**Mitigation:** explicitly out of scope.

---

### Risk 13 — Plot failure hides SimulationError

**Mitigation:** original error remains primary; diagnostic plot best effort.

---

### Risk 14 — Plot colors are inaccessible

**Mitigation:** line style/markers/text also distinguish semantics.

---

### Risk 15 — Too many internal controller signals

**Mitigation:** no PID-term panels in MVP.

---

## What not to change

While implementing Feature 11, Codex should **not**:

- change dynamics;
- change RK4;
- change telemetry timing/schema merely for plotting convenience without explicit cross-feature review;
- change sensor behavior;
- change controller gains/equations;
- change actuator behavior;
- change mission transitions;
- change fault timing;
- calculate PASS/FAIL;
- parse raw TOML;
- select artifact run directories;
- implement Rich CLI formatting;
- build a web dashboard;
- build a desktop GUI;
- build a live animation;
- build a 3D renderer;
- add Plotly/Bokeh/Streamlit;
- add custom font files;
- add database/cloud storage;
- add image pixel-regression framework;
- add replay GIF before static plot is stable;
- branch on scenario IDs.

---

# Feature-Specific Definition of Done

Feature 11 is complete when:

- [ ] One required `flight_plot.png` contract exists.
- [ ] Plotter consumes completed immutable telemetry.
- [ ] Plotter consumes resolved config.
- [ ] Plotter displays supplied validation/error result.
- [ ] PlotData view model exists.
- [ ] Missing measurement becomes plot-only NaN.
- [ ] Stale measurement markers exist.
- [ ] Figure contains six required panels.
- [ ] 2D truth trajectory is plotted.
- [ ] Ground and landing target are plotted.
- [ ] Start and endpoint are marked.
- [ ] Truth/measured altitude are plotted.
- [ ] Truth/measured/target vertical velocity are plotted.
- [ ] Truth/measured/target pitch are plotted in degrees.
- [ ] Requested/actual throttle are plotted.
- [ ] Requested/actual gimbal are plotted in degrees.
- [ ] Mission-state intervals are shown.
- [ ] Mission transition events are marked.
- [ ] Fault activation/deactivation events are marked.
- [ ] Validation summary distinguishes actual/expected/scenario result.
- [ ] Controlled abort and expected failure presentation is correct.
- [ ] Error telemetry can produce best-effort diagnostic plot.
- [ ] Axes and units are explicit.
- [ ] Style is centralized and context-local.
- [ ] Headless Agg execution works.
- [ ] Plotter never calls show.
- [ ] PNG writer creates nonempty file.
- [ ] Figure resources close after writing.
- [ ] Parent/run directory selection remains Feature 09.
- [ ] Plot does not compute validation.
- [ ] Plot does not mutate inputs.
- [ ] No scenario-name branches exist.
- [ ] Tests inspect structure/data rather than exact pixels.
- [ ] PlotData/event/unit tests pass.
- [ ] Figure-structure tests pass.
- [ ] Writer/headless tests pass.
- [ ] Nominal and fault integration plots pass.
- [ ] Full run bundle contains `flight_plot.png`.
- [ ] README screenshot can use the generated figure.
- [ ] Optional replay remains deferred.

---

# Open Questions

1. **[Open Question] Should the trajectory panel use equal aspect unconditionally or the proposed range-ratio fallback?**  
   Recommended: fallback for tall/narrow missions.

2. **[Open Question] What exact six-panel figure dimensions and DPI produce the best README/demo result?**  
   Start with 14×12 at 150 DPI.

3. **[Open Question] Should altitude panel show all mission altitude thresholds or only landing-related thresholds?**  
   Recommended: ground + landing entry + landed threshold by default.

4. **[Open Question] Should landing speed/pitch acceptance bands span only LANDING or the full timeline?**  
   Recommended: only LANDING to avoid misleading interpretation.

5. **[Open Question] Should the figure explicitly plot horizontal position/velocity versus time?**  
   The source prioritizes trajectory, altitude, vertical velocity, pitch and actuation. Keep x/vx in telemetry and trajectory for MVP.

6. **[Open Question] Should controller target setpoints be stored in telemetry instead of reconstructed from mission profiles?**  
   Explicit telemetry is stronger if controller supports dynamic targets. For current static mode profiles, reconstruction is acceptable.

7. **[Open Question] Should actuator saturation/rate-limited moments use markers in MVP?**  
   Useful but potentially cluttered. Add only after core lines/events are readable.

8. **[Open Question] Should mission-state names be annotated inside spans or use a figure-level legend?**  
   Recommended: midpoint labels on altitude panel when interval width permits.

9. **[Open Question] What exact centralized color palette should be frozen?**  
   Choose after manual visual QA; preserve line-style redundancy.

10. **[Open Question] Should PNG metadata be a hard contract?**  
    Recommended optional until library behavior is confirmed.

11. **[Open Question] Should diagnostic error bundles require a PNG when at least one frame exists?**  
    Recommended best-effort, not required.

12. **[Open Question] Should plotting support reading an existing run directory and regenerating the PNG?**  
    Useful future command, but not required for automatic run artifacts.

13. **[Open Question] Should `flight_plot.png` contain scenario description text?**  
    Keep title concise; description may be too long.

14. **[Open Question] Should maximum tilt be shown as a horizontal reference on pitch panel?**  
    Show configured max-tilt limit only if it is an enabled validation check.

15. **[Open Question] Should replay GIF generation become Feature 16/optional polish?**  
    Only after all 15 core features are portfolio-ready.

---

# Move On When

- [ ] One figure clearly explains a nominal run.
- [ ] One figure clearly explains a fault run.
- [ ] Fault timing and consequences are visually aligned.
- [ ] Truth, measurement, requested command and actual response are distinguishable.
- [ ] Objective outcome is displayed without being recalculated.
- [ ] Headless tests generate PNG safely.
- [ ] Plot integrates into the immutable artifact bundle.
- [ ] Reviewer can understand the system in under one minute.
- [ ] Plotting remains post-run and side-effect-contained.
- [ ] Feature clearly demonstrates scientific visualization and engineering communication.
- [ ] No unnecessary dashboard, web UI, 3D renderer, custom fonts, animation or cloud scope has been added.
- [ ] The project is ready for Feature 12 — Automated Tests.
