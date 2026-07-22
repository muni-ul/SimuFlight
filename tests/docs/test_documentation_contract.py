from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def test_readme_names_commands_scenarios_and_artifacts():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    required = (
        "python -m astraloop run scenarios/nominal.toml",
        "python -m astraloop list-scenarios",
        "pytest tests/numerical",
        "altimeter_freeze",
        "velocity_bias",
        "sensor_delay",
        "degraded_actuator",
        "telemetry.csv",
        "events.json",
        "resolved_config.json",
        "summary.json",
        "flight_plot.png",
    )
    assert all(item in readme for item in required)


def test_repository_relative_markdown_links_exist():
    documents = [ROOT / "README.md", ROOT / "AGENTS.md", *sorted((ROOT / "docs").glob("*.md"))]
    pattern = re.compile(r"\[[^]]+\]\((?!https?://|#)([^)]+)\)")
    missing = []
    for document in documents:
        for target in pattern.findall(document.read_text(encoding="utf-8")):
            path = (document.parent / target.split("#", 1)[0]).resolve()
            if not path.exists():
                missing.append(f"{document.relative_to(ROOT)} -> {target}")
    assert not missing, "Missing documentation links:\n" + "\n".join(missing)
