# AstraLoop contributor guidance

Read `README.md`, `docs/ARCHITECTURE.md`, and the relevant numbered feature specification before changing behavior.

Non-negotiable boundaries:

- Controllers and mission logic consume `MeasurementSnapshot`, never `VehicleState`.
- Simulation time is `tick * dt`; never use wall-clock sleep for modeled behavior.
- Production stepping uses the project-owned RK4; SciPy remains test-only.
- Controller commands pass through actuator dynamics before reaching physics.
- Faults modify real subsystem hooks and never set validation outcomes directly.
- Core modules never branch on scenario IDs.
- Validation and plotting consume completed telemetry and do not mutate a live run.
- Keep the project local, headless, deterministic, and free of database/cloud requirements.

Primary commands:

```bash
python -m pip install -e ".[dev]"
python -m astraloop run scenarios/nominal.toml
pytest
ruff check .
pyright
```

Add behavior at the smallest owning subsystem, preserve immutable public records, and add or update the matching unit/integration/scenario contract.
