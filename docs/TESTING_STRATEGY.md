# Testing strategy

AstraLoop uses five complementary layers:

1. Unit tests for equations, buffers, PID state, guards, serialization, and validation helpers.
2. Integration tests for sensor/control/actuator/fault/telemetry handoffs and tick ordering.
3. Scenario tests through the same `run_scenario(...)` application service used by the CLI.
4. Architecture tests for truth isolation, test-only SciPy, and absence of scenario-name branches.
5. Numerical tests using analytical solutions, refinement, and DOP853 reference trajectories.

Run:

```bash
pytest
pytest tests/unit
pytest tests/integration
pytest tests/scenarios
pytest tests/numerical
ruff check .
pyright
```

Exact comparisons are reserved for integer ticks, enums, IDs, schemas, and other exact contracts. Floating-point physics uses problem-specific tolerances, invariants, or independent references. Tests use explicit seeds, a headless Matplotlib backend, and temporary/no-artifact roots.
