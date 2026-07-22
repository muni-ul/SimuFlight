# Demo script

## 60–90 seconds

1. Open the README architecture diagram: “Flight software sees simulated measurements, never perfect truth.”
2. Run `python -m astraloop run scenarios/nominal.toml`.
3. Point to scenario result, actual/expected outcome, objective checks, and artifact directory.
4. Open `flight_plot.png`: identify trajectory, measured versus true state, and requested versus applied actuation.
5. Run `python -m astraloop run scenarios/altimeter_freeze.toml`.
6. Explain the causal chain: typed fault → frozen sensor → stale input → flight-software response → objective contract.

## Five-minute technical path

Add the integer-tick clock, RK4 input hold, sensor delay buffer, PID anti-windup, actuator lag, transition guards, fault composition, telemetry frame contract, and expected-failure validation semantics.

## Fallback

If local execution is unavailable, show only previously generated, unedited artifacts and state clearly when they were produced. Do not imply a live run.
