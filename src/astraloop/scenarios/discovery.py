from dataclasses import dataclass
from pathlib import Path

from astraloop.config.loader import load_scenario
from astraloop.config.schema import ExpectedOutcome


@dataclass(frozen=True, slots=True)
class ScenarioDescriptor:
    id: str
    description: str
    path: Path
    expected_outcome: ExpectedOutcome
    fault_count: int


def discover_scenarios(root: str | Path) -> tuple[ScenarioDescriptor, ...]:
    directory = Path(root).resolve()
    configs = [load_scenario(path) for path in sorted(directory.glob("*.toml"))]
    if len({config.id for config in configs}) != len(configs):
        raise ValueError("Discovered scenario IDs must be unique.")
    return tuple(
        ScenarioDescriptor(config.id, config.description, directory / f"{config.id}.toml", config.validation.expected_outcome, len(config.faults))
        for config in sorted(configs, key=lambda item: item.id)
    )
