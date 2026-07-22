import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "astraloop"


def imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }


def test_controller_does_not_import_truth_state():
    modules = set().union(*(imports(path) for path in (SRC / "control").glob("*.py")))
    assert "astraloop.model.state" not in modules


def test_core_subsystems_do_not_branch_on_scenario_names():
    forbidden = {"altimeter_freeze", "velocity_bias", "sensor_delay", "degraded_actuator"}
    core = [SRC / name for name in ("simulation", "sensors", "control", "actuators", "mission", "faults")]
    text = "\n".join(path.read_text(encoding="utf-8") for root in core for path in root.glob("*.py"))
    assert not forbidden.intersection(text.split())
