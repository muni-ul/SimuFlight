# PROJECT SELECTION BRIEF

## Project name ideas

1. **AstraLoop** - Autonomous Flight Control & Fault Simulation
2. **PyFlight SIL** - Software-in-the-Loop Launch Vehicle Simulator
3. **VectorDescent** - Autonomous Reusable Vehicle Simulation
4. **FlightForge** - Closed-Loop Flight Software Testbed
5. **FaultTolerant Flight Lab** - Python Flight-Control Simulator

**[Decision] Recommended name:** **AstraLoop**  
**Subtitle:** *Python Software-in-the-Loop Flight Control & Validation System*

---

## 1. Restated project idea

**[Confirmed]** The source brief defines the project as a **Python-only, fully local software-in-the-loop simulation of a simplified reusable launch vehicle**. The simulated vehicle evolves from numerical physics; simulated sensors expose noisy or faulty measurements; a flight controller makes autonomous decisions; actuator commands affect the physics model; a mission state machine controls flight phases; failure scenarios can be injected; and telemetry plus automated tests determine whether each mission passes or fails.

**[Confirmed]** This is specifically **not** a pre-scripted rocket animation and **not** a Starship replica. The controller should never directly modify or read perfect “true” vehicle state as its normal control input.

---

## Best target role

### Recommended target

**[Decision] Software Engineering Intern - Systems / Simulation / Validation**  
Secondary fit: **Software Test / Validation Engineering Intern**, **Modeling & Simulation Software Intern**, or **Systems Software Intern** at hardware-focused companies such as AMD.

**[Researched]** Current AMD career listings include software internships that ask for software-engineering fundamentals, C/C++, and scripting such as Python. AMD validation-oriented roles also explicitly reference Python/C++ together with simulation, emulation, validation, testing, and debugging. That makes this project more naturally aligned with **simulation/validation/systems software** than with a pure embedded-firmware or driver role.

**[Decision]** Do **not** market this project primarily as “flight software for rockets.” Market it as a **software-in-the-loop engineering simulator and automated validation system**. The rocket is the domain; the hiring signal is the software engineering.

### Why not target pure firmware?

**[Researched]** Many lower-level AMD roles lean heavily on C/C++, hardware interfaces, architecture knowledge, or verification languages. A Python-first local simulator can still help for those roles, but it will not by itself prove low-level memory management, device-driver work, embedded constraints, or RTL verification.

**[Decision]** Keep Python as the main implementation language rather than forcing C++ into this project just to imitate a job posting. A polished Python engineering system is stronger than a half-finished mixed-language project.

---

## Final project direction

### Three stronger versions

| Version | Description | Job-market relevance | Technical depth | Originality | Local-run feasibility | Demo value | Interview discussion |
|---|---|---:|---:|---:|---:|---:|---:|
| **Safe** | 1D vertical reusable vehicle: altitude/velocity dynamics, noisy sensors, throttle PID, mission state machine, several injected faults, CLI, telemetry, pytest PASS/FAIL scenarios | 8/10 | 7/10 | 7/10 | 10/10 | 8/10 | 8/10 |
| **Gold** | 2D planar reusable vehicle: translational + pitch dynamics, closed-loop throttle/attitude control, sensor/actuator models, explicit mission states, fault injection, scenario runner, deterministic telemetry/replay, automated mission validation | **9/10** | **9/10** | **9/10** | **8/10** | **9/10** | **10/10** |
| **Stretch** | 3D/6-DOF vehicle with state estimation, multi-rate sensors, wind model, actuator constraints, Monte Carlo campaigns, advanced guidance and recovery logic | 9/10 | 10/10 | 10/10 | 4/10 | 10/10 | 10/10 |

### Best version: GOLD

**[Decision]** Build the **Gold version**.

It is the strongest balance because it is complicated enough to prove real engineering skill but still small enough to finish. A 2D planar model gives you meaningful coupling between position, velocity, pitch, angular rate, thrust direction, and control without forcing you into the large mathematical and debugging burden of a full 6-DOF aerospace simulator.

The Gold version also creates strong interview questions naturally:

- Why did you separate true state from sensed state?
- How did you model sensor delay or bias?
- How did you tune and test the controller?
- How does the state machine prevent invalid transitions?
- What happens when an altimeter freezes or an actuator becomes sluggish?
- How do you make simulations deterministic and reproducible?
- How did you define PASS/FAIL mission criteria?
- How do you test a system whose output evolves continuously over time?

Those are much stronger discussions than “I made a rocket animation.”

---

## Exact project goal

**[Decision]** Build **AstraLoop**, a local Python software-in-the-loop simulator for a simplified 2D reusable launch vehicle. The vehicle must evolve through numerical dynamics rather than scripted motion; the autonomous controller must operate only on simulated sensor measurements; mission behavior must be organized through an explicit flight-state machine; and a repeatable scenario runner must evaluate nominal and faulty missions using measurable PASS/FAIL criteria. The final repository should demonstrate clean Python architecture, numerical computing, feedback control, fault injection, logging, automated testing, debugging, and concise technical documentation in a form a recruiter can understand in under one minute and a technical interviewer can explore in depth.

---

## Core features

### 1. 2D vehicle dynamics + numerical simulation

**[Confirmed]** The source brief calls for numerical evolution of vehicle state.

**[Decision]** Simulate a planar state such as:

- horizontal and vertical position
- horizontal and vertical velocity
- pitch angle
- angular velocity
- mass/fuel

Use **NumPy** for state/math and **SciPy `solve_ivp`** or a clearly implemented fixed-step integrator for dynamics.

Why it matters: proves numerical reasoning, scientific Python, state modeling, and debugging of a nontrivial system.

### 2. Closed-loop flight control through simulated sensors

**[Confirmed]** The controller should receive simulated measurements instead of perfect truth.

**[Decision]** Build sensor models with configurable noise, bias, delay, and at least one failure mode. Build throttle and pitch controllers with actuator saturation/lag.

Why it matters: separates this from a scripted simulation and demonstrates interfaces, abstractions, feedback systems, and handling imperfect inputs.

### 3. Mission state machine

**[Confirmed]** The source brief proposes modes such as PRELAUNCH, ASCENT, COAST, DESCENT, LANDING, LANDED, and ABORT.

**[Decision]** Implement explicit transition conditions and record every transition in telemetry. Invalid state transitions should be testable.

Why it matters: shows deterministic program logic, stateful software design, edge-case reasoning, and testability.

### 4. Fault-injection scenario runner

**[Confirmed]** Failure injection is a major portfolio component in the source brief.

**[Decision]** Support a small curated scenario set rather than dozens of faults. Example scenarios:

- nominal mission
- altitude-sensor freeze
- velocity-sensor bias
- delayed sensor readings
- degraded actuator response
- strong external disturbance

Each scenario must be seeded/reproducible and end with explicit PASS/FAIL criteria.

Why it matters: strongly resembles validation and systems-testing work at hardware/software companies.

### 5. Telemetry + automated mission validation

**[Confirmed]** The source brief calls for telemetry, plots, replay/visualization, and pytest-based mission testing.

**[Decision]** Every run should generate structured telemetry, a concise mission summary, and plots/replay. `pytest` should cover unit logic plus complete scenario-level mission checks.

Why it matters: demonstrates observability, testing, reproducibility, data analysis, and software quality.

---

## Skills demonstrated

### Software engineering

- **[Decision] Modular architecture:** dynamics, sensors, controller, actuators, state machine, faults, scenarios, telemetry, visualization, tests.
- **[Decision] Interfaces and dependency boundaries:** controller consumes sensor outputs rather than true simulation state.
- **[Decision] Configuration-driven behavior:** scenario parameters in TOML/YAML/JSON rather than duplicated code.
- **[Decision] Reproducibility:** deterministic random seeds and repeatable scenario execution.
- **[Decision] Testing:** unit, state-transition, integration, and end-to-end mission tests.
- **[Decision] Debugging/observability:** logs, telemetry, event traces, and clear failure summaries.

### Technical / numerical

- **[Confirmed]** NumPy-based numerical calculations.
- **[Confirmed]** SciPy ODE integration / numerical methods.
- **[Confirmed]** Feedback-control logic.
- **[Confirmed]** Noisy/faulty sensor modeling.
- **[Confirmed]** Failure handling and mission-state logic.
- **[Confirmed]** Matplotlib telemetry visualization.

### Employer-facing signal

**[Decision]** The project should prove that you can take a system with physics, uncertainty, state, failures, and tests and turn it into a clean software architecture - not merely write individual Python scripts.

---

## What would make the project look generic or tutorial-like

- **[Decision]** A rocket that follows hard-coded coordinates or a precomputed animation.
- **[Decision]** A single notebook containing physics, control, plots, and tests all mixed together.
- **[Decision]** One nominal flight with no failure cases.
- **[Decision]** A PID controller reading perfect altitude/velocity directly from true simulation state.
- **[Decision]** A giant GUI before the underlying simulator is reliable.
- **[Decision]** Copying a “rocket simulation in Python” tutorial and mainly changing constants/colors.
- **[Decision]** Claiming realism comparable to SpaceX/Starship.
- **[Decision]** Hundreds of configuration options that do not improve the engineering story.
- **[Decision]** Fancy 3D rendering with weak automated testing.

---

## What NOT to build

1. **[Decision] No SaaS/web product.** No accounts, subscriptions, billing, cloud backend, or enterprise dashboard.
2. **[Decision] No physical rocket or external hardware.** Keep this completely local and computer-based.
3. **[Decision] No full orbital mechanics simulator.** The goal is flight-control software architecture, not aerospace research.
4. **[Decision] No full 6-DOF model for the Gold version.** It creates too much math/debug scope relative to hiring value.
5. **[Decision] No machine learning controller.** Classical deterministic control is easier to validate and discuss honestly.
6. **[Decision] No huge GUI framework.** Matplotlib plots plus an optional lightweight replay are enough.
7. **[Decision] No database unless a concrete need appears.** CSV/JSON/Parquet-style run artifacts are sufficient.
8. **[Decision] No forced C++ rewrite.** Python remains the engineering focus.

---

## Main risks

### Risk 1 - Physics scope explodes
**[Decision] Mitigation:** lock the Gold version to planar 2D dynamics. Do not add 3D until every Gold acceptance criterion passes.

### Risk 2 - Too much time tuning the controller
**[Decision] Mitigation:** use simple, explainable controllers and bounded goals. The project is a software-engineering demonstration, not a research-grade guidance system.

### Risk 3 - Visualization becomes the project
**[Decision] Mitigation:** make plots/replay consume saved telemetry. Simulation code must work headlessly without visualization.

### Risk 4 - Tests become superficial
**[Decision] Mitigation:** include end-to-end scenario assertions, not only tiny utility-function tests.

### Risk 5 - Failure handling is fake
**[Decision] Mitigation:** failures must actually change sensor/actuator behavior and be visible in telemetry. Do not merely print “fault detected.”

### Risk 6 - Recruiter cannot understand it quickly
**[Decision] Mitigation:** README opening section should show one architecture diagram, one command, one nominal result, one failure result, and five concise engineering bullets.

---

## Success scorecard

A strong finished project should meet **at least 9/11** of these criteria before you call it portfolio-ready.

| Criterion | Success condition |
|---|---|
| **Clear positioning** | README describes it as a Python software-in-the-loop flight-control **simulation and validation** system, not a Starship clone |
| **One-command demo** | A fresh user can run a nominal scenario from the command line with one documented command |
| **Real closed loop** | Controller receives simulated sensor data and cannot directly use true vehicle state during normal control |
| **2D dynamics** | Position, velocity, pitch, angular rate, and control inputs evolve through numerical integration |
| **State machine** | Mission modes and transition rules are explicit, logged, and tested |
| **Fault scenarios** | At least 4 non-nominal scenarios meaningfully alter sensor, actuator, or disturbance behavior |
| **PASS/FAIL criteria** | Every scenario produces objective mission results rather than subjective plot inspection |
| **Automated tests** | Unit + integration/scenario tests run through `pytest` and protect core behavior |
| **Reproducibility** | Randomized effects use explicit seeds; the same configured run can be reproduced |
| **Telemetry** | Runs save structured time-series data plus event/state transitions and a concise summary |
| **Recruiter demo quality** | README includes architecture diagram, example plots, nominal vs fault comparison, and a short explanation of major design decisions |

### Suggested Gold acceptance metrics

These are **project-defined engineering targets**, not claims about real launch vehicles.

- **[Decision]** Nominal landing vertical speed: `|v_y| <= 2.0 m/s`
- **[Decision]** Nominal horizontal position error: `<= 5 m`
- **[Decision]** Nominal landing pitch error: `<= 5 degrees`
- **[Decision]** Simulation must never produce invalid mission-state transitions
- **[Decision]** Fault scenarios must either recover within defined limits or enter a deliberate ABORT/FAIL outcome
- **[Decision]** Same seed + same config must produce the same mission result

---

## FINAL PROJECT DIRECTION

### Project
**AstraLoop - Python Software-in-the-Loop Flight Control & Validation System**

### Best target role
**Software Engineering Intern - Systems / Simulation / Validation**, especially at hardware-focused companies such as AMD.

### Final direction
Build a **2D planar reusable-launch-vehicle simulator** in Python where numerical physics evolves the vehicle, controllers operate only on simulated sensor data, mission phases are governed by a tested state machine, failures can be injected reproducibly, and every run produces telemetry plus objective PASS/FAIL results. Prioritize architecture, testing, deterministic simulations, and failure analysis over visual complexity.

### Core features
1. 2D vehicle dynamics and numerical integration
2. Simulated sensors/actuators with closed-loop control
3. Explicit mission state machine
4. Reproducible fault-injection scenario runner
5. Telemetry, visualization, and automated mission validation

### Skills demonstrated
Python, NumPy, SciPy, numerical simulation, control logic, state machines, modular architecture, testing with pytest, fault injection, logging/telemetry, debugging, deterministic configuration, scientific visualization, and technical documentation.

### What to avoid
Do not build a SaaS, full Starship replica, 6-DOF aerospace research simulator, ML controller, giant GUI, or mixed-language rewrite before the core Python system is excellent.

### Success scorecard
Portfolio-ready when the project has a one-command local demo, real closed-loop behavior, explicit state transitions, at least four meaningful fault scenarios, deterministic PASS/FAIL missions, automated tests, saved telemetry, and a recruiter-readable README/demo.

### Recommended next step
**[Decision] Freeze the architecture before writing the simulator.** Create a one-page technical design defining the state vector, module boundaries, data flow, mission states, scenario/config format, and the exact nominal PASS criteria. Then implement only the nominal 2D simulator and controller before adding faults or visualization polish.

---

## Move On When

- [x] The project has a clear target role.
- [x] The idea is not generic.
- [x] The scope feels finishable.
- [x] There are 3 to 5 core features, not a massive feature list.
- [x] You can explain why this project would impress a hiring manager.
