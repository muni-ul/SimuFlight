"""Small argparse/Rich terminal adapter over the scenario application service."""

import argparse
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import traceback
from typing import Sequence

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from astraloop.config.loader import ConfigError, load_scenario
from astraloop.scenarios.discovery import discover_scenarios
from astraloop.scenarios.runner import run_scenario
from astraloop.telemetry.serialization import ArtifactError

EXIT_SUCCESS = 0
EXIT_SCENARIO_MISMATCH = 1
EXIT_USAGE_OR_CONFIG = 2
EXIT_INTERNAL_ERROR = 3
EXIT_INTERRUPTED = 130


def _version() -> str:
    try:
        return version("astraloop")
    except PackageNotFoundError:
        from astraloop import __version__
        return __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="astraloop",
        description="Local software-in-the-loop flight-control simulation and validation.",
    )
    parser.add_argument("--version", action="version", version=f"AstraLoop {_version()}")
    parser.add_argument("--debug", action="store_true", help="Show tracebacks for unexpected errors.")
    commands = parser.add_subparsers(dest="command", required=True, title="commands")
    run = commands.add_parser("run", help="Run one TOML scenario.")
    run.add_argument("scenario", type=Path)
    artifacts = run.add_mutually_exclusive_group()
    artifacts.add_argument("--artifact-root", type=Path, default=Path("runs"))
    artifacts.add_argument("--no-artifacts", action="store_true")
    listing = commands.add_parser("list-scenarios", help="List available local scenarios.")
    listing.add_argument("--root", type=Path, default=Path("scenarios"))
    return parser


def _render_result(console: Console, config, result) -> None:
    validation = result.validation
    passed = validation.scenario_passed
    heading = "SCENARIO PASS" if passed else "SCENARIO FAIL"
    style = "bold green" if passed else "bold red"
    identity = Table(show_header=False, box=None)
    identity.add_row("Scenario", result.scenario_id)
    identity.add_row("Actual outcome", validation.actual_outcome.value.upper())
    identity.add_row("Expected outcome", validation.expected_outcome.value.upper())
    identity.add_row("Final mission state", result.final_mission_state)
    identity.add_row("Seed", str(config.seed))
    identity.add_row("Final time", f"{result.simulation.final_time:.2f} s")
    identity.add_row("Config digest", result.config_digest[:12])
    console.print(Panel(identity, title=heading, title_align="left", border_style=style))
    checks = Table("Check", "Actual", "Limit", "Result")
    for check in validation.checks:
        checks.add_row(check.id.replace("_", " ").title(), "—" if check.actual is None else str(check.actual), "—" if check.limit is None else str(check.limit), check.status.value.upper())
    console.print(checks)
    if validation.activated_fault_ids:
        console.print(f"Activated faults: {', '.join(validation.activated_fault_ids)}")
    if validation.failure_reasons:
        console.print("Failure reasons:")
        for reason in validation.failure_reasons:
            console.print(f"  - {reason}")
    console.print(f"Artifacts: {result.artifact_directory or 'not written (--no-artifacts)'}")


def _handle_run(args: argparse.Namespace, console: Console) -> int:
    config = load_scenario(args.scenario)
    artifact_root = None if args.no_artifacts else args.artifact_root
    result = run_scenario(config, artifact_root=artifact_root)
    _render_result(console, config, result)
    return EXIT_SUCCESS if result.validation.scenario_passed else EXIT_SCENARIO_MISMATCH


def _handle_list(args: argparse.Namespace, console: Console) -> int:
    descriptors = discover_scenarios(args.root)
    if not descriptors:
        console.print(f"No scenario TOML files found under {args.root}.")
        return EXIT_USAGE_OR_CONFIG
    table = Table("ID", "Expected", "Faults", "Description", "Path")
    for item in descriptors:
        table.add_row(item.id, item.expected_outcome.value, str(item.fault_count), item.description, str(item.path))
    console.print(table)
    return EXIT_SUCCESS


def run_cli(
    argv: Sequence[str],
    *,
    console: Console,
    error_console: Console,
) -> int:
    args = build_parser().parse_args(list(argv))
    try:
        if args.command == "run":
            return _handle_run(args, console)
        return _handle_list(args, console)
    except ConfigError as exc:
        error_console.print(Panel(str(exc), title="CONFIGURATION ERROR", border_style="red"))
        return EXIT_USAGE_OR_CONFIG
    except KeyboardInterrupt:
        error_console.print("Interrupted.")
        return EXIT_INTERRUPTED
    except (ArtifactError, RuntimeError, ValueError) as exc:
        error_console.print(Panel(str(exc), title="INTERNAL ERROR", border_style="red"))
        if args.debug:
            error_console.print(traceback.format_exc())
        return EXIT_INTERNAL_ERROR
    except Exception as exc:
        error_console.print(Panel(str(exc), title="UNEXPECTED ERROR", border_style="red"))
        if args.debug:
            error_console.print(traceback.format_exc())
        return EXIT_INTERNAL_ERROR


def main(argv: Sequence[str] | None = None) -> int:
    import sys
    return run_cli(
        sys.argv[1:] if argv is None else argv,
        console=Console(),
        error_console=Console(stderr=True),
    )
