# Build log

## Architecture decisions

- Chose vertical-zero pitch convention (`theta = 0` upright) and protected it through named records and sign-focused test assets.
- Kept numerical derivatives pure while the engine owns time, RK4, and atomic state commits.
- Derived independent sensor RNG streams with `SeedSequence` to prevent one sensor's draw count from perturbing another.
- Modeled desired and applied actuation as distinct types so physical lag and degradation remain observable.
- Made expected mission outcome distinct from scenario regression success so expected abort/failure cases are first-class validation tests.

## Integration lessons

- Telemetry needs a state-tick contract before plotting or validation can be trustworthy; otherwise truth at `t+dt` can be mislabeled beside commands from `t`.
- Fault effects are recomposed from the full active set every tick so deactivating one overlapping fault cannot clear another.
- Configuration is resolved once at the boundary into radians and integer ticks; subsystems never reinterpret human TOML units.

## Evidence policy

No runtime, test count, scenario result, numerical error, or screenshot is recorded as measured evidence until produced by an actual repository-owner execution.
