from pathlib import Path

from astraloop.scenarios.runner import run_scenario_file

ROOT = Path(__file__).resolve().parents[2]


def test_persisted_run_contains_complete_bundle(tmp_path):
    result = run_scenario_file(ROOT / "scenarios" / "nominal.toml", artifact_root=tmp_path)
    directory = Path(result.artifact_directory)
    assert {path.name for path in directory.iterdir()} == {
        "telemetry.csv", "events.json", "resolved_config.json", "summary.json", "flight_plot.png"
    }
