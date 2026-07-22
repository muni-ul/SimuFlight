# Roadmap

## Completed implementation phases

- Core planar physics and immutable domain records
- Fixed-step RK4 and deterministic tick runtime
- Imperfect sensors and independent stochastic streams
- Closed-loop PID control and physical actuator response
- Explicit mission state machine and typed fault lifecycle
- Strict TOML scenarios and full-stack runner
- Telemetry, artifacts, validation, and diagnostic plotting
- Layered test and numerical-reference assets
- CLI and portfolio documentation

## Release evidence gate

The repository owner should execute the documented test, numerical, and scenario commands, calibrate any failed scenario contracts, and capture current terminal/plot evidence before treating results as measured release claims.

## Possible post-release work

- Horizontal guidance outer loop
- Optional external-disturbance scenario
- Sequential campaign command
- Monte Carlo sensitivity analysis
- Hardware-in-the-loop adapter
