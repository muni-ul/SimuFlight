# Interview story

## Problem

Autonomous software is difficult to validate without hardware because continuous physics, sampled measurements, software state, timing, and failure modes interact.

## Approach

I built a deterministic Python software-in-the-loop environment with a strict truth/measurement boundary. Typed configuration constructs fresh sensors, controllers, actuators, mission logic, and faults for every run. One integer clock aligns subsystem behavior, telemetry, and validation.

## Decisions worth discussing

- 2D planar dynamics rather than 6-DOF to keep the project finishable and software-focused.
- A transparent custom RK4 production stepper, with SciPy restricted to independent verification tests.
- Dedicated sensor RNG streams and tick-based delay buffers for reproducibility.
- Desired versus applied commands to make actuator degradation physically causal.
- Actual mission outcome separated from scenario success to model expected failures correctly.

## Limitations

This is a simplified engineering testbed, not a real vehicle model. It omits aerodynamics, estimation, 3D motion, hardware timing, and certification claims.

## Resume-ready wording

Built AstraLoop, a Python software-in-the-loop flight-control validation system with deterministic 2D dynamics, imperfect sensors, actuator response, explicit mission modes, configuration-driven fault injection, structured telemetry, and objective scenario contracts.

Designed a fixed-step RK4 runtime and layered validation architecture that isolates flight software from simulator truth and compares selected open-loop dynamics against analytical and SciPy development references.
