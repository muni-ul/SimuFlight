"""Stable CSV/JSON artifact serialization with staging publication."""

import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any

from astraloop.config.schema import ResolvedScenarioConfig
from astraloop.model.measurements import SensorName
from astraloop.telemetry.recorder import CompletedTelemetry, TelemetryFrame
from astraloop.telemetry.plotting import write_diagnostic_plot


class ArtifactError(OSError):
    pass


@dataclass(frozen=True, slots=True)
class RunArtifacts:
    directory: Path
    telemetry_csv: Path
    events_json: Path
    resolved_config_json: Path
    summary_json: Path
    flight_plot_png: Path


CSV_COLUMNS = (
    "telemetry_schema_version", "frame_kind", "tick", "time_s", "mission_state",
    "termination_reason", "true_x_m", "true_y_m", "true_vx_m_s", "true_vy_m_s",
    "true_theta_rad", "true_omega_rad_s", "true_mass_kg", "measured_x_m",
    "measured_y_m", "measured_vx_m_s", "measured_vy_m_s", "measured_theta_rad",
    "measured_omega_rad_s", "command_throttle", "command_attitude_rad",
    "actual_throttle", "actual_gimbal_rad", "controller_status", "active_faults",
)


def _row(frame: TelemetryFrame) -> dict[str, Any]:
    measurement = frame.measurement
    command = frame.controller.command if frame.controller else None
    actuator = frame.actuator.state if frame.actuator else None
    return {
        "telemetry_schema_version": frame.schema_version, "frame_kind": frame.kind.value,
        "tick": frame.tick, "time_s": repr(frame.time), "mission_state": frame.mission_state,
        "termination_reason": frame.termination_reason or "", "true_x_m": repr(frame.truth.x),
        "true_y_m": repr(frame.truth.y), "true_vx_m_s": repr(frame.truth.vx),
        "true_vy_m_s": repr(frame.truth.vy), "true_theta_rad": repr(frame.truth.theta),
        "true_omega_rad_s": repr(frame.truth.omega), "true_mass_kg": repr(frame.truth.mass),
        "measured_x_m": "" if measurement is None or measurement.x is None else repr(measurement.x),
        "measured_y_m": "" if measurement is None or measurement.y is None else repr(measurement.y),
        "measured_vx_m_s": "" if measurement is None or measurement.vx is None else repr(measurement.vx),
        "measured_vy_m_s": "" if measurement is None or measurement.vy is None else repr(measurement.vy),
        "measured_theta_rad": "" if measurement is None or measurement.theta is None else repr(measurement.theta),
        "measured_omega_rad_s": "" if measurement is None or measurement.omega is None else repr(measurement.omega),
        "command_throttle": "" if command is None else repr(command.throttle),
        "command_attitude_rad": "" if command is None else repr(command.attitude_command),
        "actual_throttle": "" if actuator is None else repr(actuator.throttle),
        "actual_gimbal_rad": "" if actuator is None else repr(actuator.gimbal_angle),
        "controller_status": "" if frame.controller is None else frame.controller.status.value,
        "active_faults": json.dumps(frame.active_fault_ids, separators=(",", ":")),
    }


class ArtifactWriter:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def write(
        self,
        config: ResolvedScenarioConfig,
        telemetry: CompletedTelemetry,
        summary: dict[str, Any],
        validation: Any,
    ) -> RunArtifacts:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        scenario_root = self.root / config.id
        scenario_root.mkdir(parents=True, exist_ok=True)
        base = f"{stamp}_{config.digest[:8]}"
        final = scenario_root / base
        suffix = 1
        while final.exists():
            final = scenario_root / f"{base}_{suffix}"; suffix += 1
        staging = scenario_root / f".{final.name}.staging"
        try:
            staging.mkdir()
            with (staging / "telemetry.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS, lineterminator="\n")
                writer.writeheader(); writer.writerows(_row(frame) for frame in telemetry.frames)
            events = {"event_schema_version": telemetry.event_schema_version, "scenario_id": config.id, "seed": config.seed, "config_digest": config.digest, "events": [asdict(event) for event in telemetry.events]}
            self._json(staging / "events.json", events)
            self._json(staging / "resolved_config.json", asdict(config))
            self._json(staging / "summary.json", summary)
            write_diagnostic_plot(staging / "flight_plot.png", telemetry, config, validation)
            staging.rename(final)
        except Exception as exc:
            shutil.rmtree(staging, ignore_errors=True)
            raise ArtifactError(f"Failed to publish run artifacts: {exc}") from exc
        return RunArtifacts(final, final / "telemetry.csv", final / "events.json", final / "resolved_config.json", final / "summary.json", final / "flight_plot.png")

    @staticmethod
    def _json(path: Path, value: Any) -> None:
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False, default=str)
            stream.write("\n")
