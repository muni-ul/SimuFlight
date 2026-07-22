from pathlib import Path

import pytest

from astraloop.config.loader import ConfigError, load_scenario

ROOT = Path(__file__).resolve().parents[2]


def test_nominal_config_resolves_with_stable_digest():
    first = load_scenario(ROOT / "scenarios" / "nominal.toml")
    second = load_scenario(ROOT / "scenarios" / "nominal.toml")
    assert first.digest == second.digest
    assert first.id == "nominal"


def test_non_toml_path_is_rejected(tmp_path):
    path = tmp_path / "scenario.txt"
    path.write_text("schema_version=1", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_scenario(path)
