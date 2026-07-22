from pathlib import Path

import pytest

from astraloop.scenarios.runner import run_scenario_file

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.scenario
@pytest.mark.parametrize("name", ["nominal", "altimeter_freeze", "velocity_bias", "sensor_delay", "degraded_actuator"])
def test_curated_scenario_matches_declared_contract(name):
    result = run_scenario_file(ROOT / "scenarios" / f"{name}.toml", artifact_root=None)
    assert result.validation is not None
    assert result.validation.outcome_matched
    assert result.validation.scenario_passed


@pytest.mark.scenario
def test_nominal_is_reproducible():
    path = ROOT / "scenarios" / "nominal.toml"
    first = run_scenario_file(path, artifact_root=None)
    second = run_scenario_file(path, artifact_root=None)
    assert first.config_digest == second.config_digest
    assert first.simulation.final_state == second.simulation.final_state
    assert first.validation == second.validation
