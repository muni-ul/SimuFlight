"""Pure objective post-run mission and scenario-contract validation."""

from dataclasses import dataclass
from enum import StrEnum
from math import isclose, pi

from astraloop.config.schema import ExpectedOutcome, ResolvedScenarioConfig
from astraloop.mission.modes import LEGAL_TRANSITIONS, MissionMode
from astraloop.telemetry.recorder import CompletedTelemetry, TelemetryFrame

VALIDATION_ABS_TOL = 1e-9


class ActualOutcome(StrEnum):
    PASS = "pass"
    CONTROLLED_ABORT = "controlled_abort"
    VALIDATION_FAIL = "validation_fail"


class CheckStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class ValidationCheck:
    id: str
    status: CheckStatus
    message: str
    actual: float | str | None = None
    limit: float | str | None = None


@dataclass(frozen=True, slots=True)
class ValidationMetrics:
    signed_landing_vy: float | None
    landing_vertical_speed: float | None
    horizontal_error: float | None
    pitch_error: float | None
    maximum_tilt: float
    fuel_remaining: float
    touchdown_tick: int | None
    touchdown_time: float | None
    final_tick: int
    final_time: float


@dataclass(frozen=True, slots=True)
class ValidationResult:
    actual_outcome: ActualOutcome
    expected_outcome: ExpectedOutcome
    outcome_matched: bool
    mission_succeeded: bool
    scenario_passed: bool
    metrics: ValidationMetrics
    checks: tuple[ValidationCheck, ...]
    failure_reasons: tuple[str, ...]
    activated_fault_ids: tuple[str, ...]
    pending_fault_ids: tuple[str, ...]


class ValidationError(ValueError):
    pass


def _wrap(angle: float) -> float:
    return (angle + pi) % (2.0 * pi) - pi


def _within(value: float, limit: float) -> bool:
    return value < limit or isclose(value, limit, rel_tol=0.0, abs_tol=VALIDATION_ABS_TOL)


def _transition_check(telemetry: CompletedTelemetry) -> tuple[bool, str]:
    events = [event for event in telemetry.events if event.source == "mission"]
    state = MissionMode.PRELAUNCH
    seen_ticks: set[int] = set()
    frames = {frame.tick: frame for frame in telemetry.frames}
    for event in events:
        try:
            before = MissionMode(event.data["from_state"])
            after = MissionMode(event.data["to_state"])
        except (KeyError, ValueError):
            return False, "Malformed mission transition event."
        if event.tick in seen_ticks or before is not state or after not in LEGAL_TRANSITIONS[before]:
            return False, "Mission transition trace is illegal or inconsistent."
        if event.tick not in frames or frames[event.tick].mission_state != after.value:
            return False, "Mission event does not match its telemetry frame."
        seen_ticks.add(event.tick)
        state = after
    if telemetry.frames[-1].mission_state != state.value:
        return False, "Final mission state does not match transition trace."
    return True, "Mission transition trace is legal and consistent."


def validate_run(config: ResolvedScenarioConfig, telemetry: CompletedTelemetry) -> ValidationResult:
    if not telemetry.frames:
        raise ValidationError("Completed telemetry contains no frames.")
    final = telemetry.frames[-1]
    valid_transitions, transition_message = _transition_check(telemetry)
    mission_events = [event for event in telemetry.events if event.source == "mission"]
    touchdown_event = next((event for event in mission_events if event.data.get("from_state") == "LANDING" and event.data.get("to_state") == "LANDED"), None)
    touchdown: TelemetryFrame | None = None
    if touchdown_event is not None:
        touchdown = next((frame for frame in telemetry.frames if frame.tick == touchdown_event.tick), None)

    checks: list[ValidationCheck] = [
        ValidationCheck("valid_mission_transitions", CheckStatus.PASS if valid_transitions else CheckStatus.FAIL, transition_message)
    ]
    signed_vy = speed = horizontal = pitch = None
    if final.mission_state == MissionMode.LANDED.value and touchdown is not None:
        signed_vy = touchdown.truth.vy
        speed = abs(signed_vy)
        horizontal = abs(touchdown.truth.x)
        pitch = abs(_wrap(touchdown.truth.theta))
        for check_id, value, limit in (
            ("landing_vertical_speed", speed, config.validation.max_landing_vertical_speed),
            ("horizontal_landing_error", horizontal, config.validation.max_horizontal_error),
            ("landing_pitch_error", pitch, config.validation.max_pitch_error),
        ):
            passed = _within(value, limit)
            checks.append(ValidationCheck(check_id, CheckStatus.PASS if passed else CheckStatus.FAIL, f"{check_id} {'within' if passed else 'exceeded'} configured limit.", value, limit))
        checks.append(ValidationCheck("final_state_landed", CheckStatus.PASS, "Final mission state is LANDED.", final.mission_state, MissionMode.LANDED.value))
    elif final.mission_state == MissionMode.ABORT.value:
        for check_id in ("landing_vertical_speed", "horizontal_landing_error", "landing_pitch_error", "final_state_landed"):
            checks.append(ValidationCheck(check_id, CheckStatus.NOT_APPLICABLE, "Landing check is not applicable to controlled abort."))
    else:
        checks.append(ValidationCheck("final_state_landed", CheckStatus.FAIL, "Run did not reach LANDED.", final.mission_state, MissionMode.LANDED.value))

    configured_ids = {fault.id for fault in config.faults}
    activation_events = [event for event in telemetry.events if event.source == "fault" and event.event_type == "fault_activated"]
    activated = tuple(sorted({event.data["fault_id"] for event in activation_events}))
    pending = tuple(sorted(configured_ids - set(activated)))
    faults_ok = not pending and all(fault_id in configured_ids for fault_id in activated)
    checks.append(ValidationCheck("configured_faults_activated", CheckStatus.PASS if faults_ok else CheckStatus.FAIL, "All configured faults activated exactly as expected." if faults_ok else "Configured fault activation contract was not satisfied."))

    required_landing = [check for check in checks if check.id in {"valid_mission_transitions", "landing_vertical_speed", "horizontal_landing_error", "landing_pitch_error", "final_state_landed"}]
    if final.mission_state == MissionMode.ABORT.value:
        actual = ActualOutcome.CONTROLLED_ABORT
    elif final.mission_state == MissionMode.LANDED.value and all(check.status is CheckStatus.PASS for check in required_landing):
        actual = ActualOutcome.PASS
    else:
        actual = ActualOutcome.VALIDATION_FAIL
    matched = actual.value == config.validation.expected_outcome.value
    checks.append(ValidationCheck("expected_outcome", CheckStatus.PASS if matched else CheckStatus.FAIL, f"Actual outcome {actual.value} {'matched' if matched else 'did not match'} expected {config.validation.expected_outcome.value}.", actual.value, config.validation.expected_outcome.value))
    # A curated scenario is a regression contract, not necessarily a successful
    # physical mission.  For example, a deliberately biased sensor should make
    # the landing validation fail; reproducing that declared outcome is a
    # successful scenario test.  Infrastructure checks must still pass.
    scenario_passed = matched and faults_ok and (
        valid_transitions or not config.validation.require_valid_transitions
    )
    evaluation = touchdown or final
    metrics = ValidationMetrics(
        signed_vy, speed, horizontal, pitch,
        max(abs(_wrap(frame.truth.theta)) for frame in telemetry.frames),
        max(0.0, evaluation.truth.mass - config.vehicle.dry_mass),
        touchdown.tick if touchdown else None, touchdown.time if touchdown else None,
        final.tick, final.time,
    )
    failures = tuple(check.message for check in checks if check.status is CheckStatus.FAIL)
    return ValidationResult(actual, config.validation.expected_outcome, matched, actual is ActualOutcome.PASS, scenario_passed, metrics, tuple(checks), failures, activated, pending)
