# Numerical verification

AstraLoop uses a project-owned fixed-step classical RK4 integrator in production so sensors, controllers, actuators, faults, mission logic, and telemetry share one deterministic integer-tick clock. SciPy is a development-only independent reference and is never imported by the production scheduler.

The numerical suite covers:

- direct RK4 stage-time and immutability contracts;
- constant, exponential, time-polynomial, and harmonic-oscillator problems;
- observed fourth-order step refinement on smooth ODEs;
- analytical seven-state gravity-only flight;
- coupled fixed-gimbal vehicle motion against `solve_ivp(method="DOP853", rtol=1e-12, atol=1e-14)`;
- timestep sensitivity at `0.02`, `0.01`, and `0.005` seconds.

The intended production timestep is `0.02 s`. Its acceptance is encoded in the numerical reference tests using state-specific tolerances substantially below mission-level limits. Numerical claims are limited to the simplified planar model and tested parameter envelope. They exclude ground contact, dry-mass clamps, discrete fault transitions, and real-vehicle fidelity or certification.

Run the evidence with:

```bash
pytest tests/numerical
```

This document intentionally contains no copied measured output because verification results should come from the executing environment rather than hand-maintained numbers.
