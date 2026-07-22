from io import StringIO

from rich.console import Console

from astraloop.cli import EXIT_SUCCESS, build_parser, run_cli


def consoles():
    out, err = StringIO(), StringIO()
    return Console(file=out, force_terminal=False, width=120), Console(file=err, force_terminal=False, width=120), out, err


def test_parser_defaults_artifacts_to_runs():
    args = build_parser().parse_args(["run", "scenarios/nominal.toml"])
    assert str(args.artifact_root) == "runs"
    assert not args.no_artifacts


def test_list_scenarios_renders_required_columns():
    out_console, err_console, out, _ = consoles()
    code = run_cli(["list-scenarios"], console=out_console, error_console=err_console)
    assert code == EXIT_SUCCESS
    assert all(label in out.getvalue() for label in ("ID", "Expected", "Faults", "Description", "Path"))
