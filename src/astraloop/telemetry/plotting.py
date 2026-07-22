"""Headless six-panel diagnostic visualization for completed runs."""

from dataclasses import dataclass
from math import degrees, nan
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from astraloop.config.schema import ResolvedScenarioConfig
from astraloop.mission.modes import MissionMode
from astraloop.telemetry.recorder import CompletedTelemetry


class PlotError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PlotData:
    time: np.ndarray
    x: np.ndarray
    y: np.ndarray
    measured_y: np.ndarray
    vy: np.ndarray
    measured_vy: np.ndarray
    theta_deg: np.ndarray
    measured_theta_deg: np.ndarray
    command_throttle: np.ndarray
    actual_throttle: np.ndarray
    command_gimbal_deg: np.ndarray
    actual_gimbal_deg: np.ndarray
    mission_states: tuple[str, ...]


def build_plot_data(telemetry: CompletedTelemetry) -> PlotData:
    frames = telemetry.frames
    def measured(name: str, *, angle: bool = False):
        values = []
        for frame in frames:
            value = None if frame.measurement is None else getattr(frame.measurement, name)
            values.append(nan if value is None else degrees(value) if angle else value)
        return np.asarray(values, dtype=float)
    def nested(parent: str, child: str, *, angle: bool = False):
        values = []
        for frame in frames:
            obj = getattr(frame, parent)
            value = nan if obj is None else getattr(obj.command if parent == "controller" else obj.state, child)
            values.append(degrees(value) if angle and not np.isnan(value) else value)
        return np.asarray(values, dtype=float)
    return PlotData(
        np.asarray([frame.time for frame in frames]),
        np.asarray([frame.truth.x for frame in frames]), np.asarray([frame.truth.y for frame in frames]),
        measured("y"), np.asarray([frame.truth.vy for frame in frames]), measured("vy"),
        np.asarray([degrees(frame.truth.theta) for frame in frames]), measured("theta", angle=True),
        nested("controller", "throttle"), nested("actuator", "throttle"),
        nested("controller", "attitude_command", angle=True), nested("actuator", "gimbal_angle", angle=True),
        tuple(frame.mission_state for frame in frames),
    )


def write_diagnostic_plot(
    path: Path,
    telemetry: CompletedTelemetry,
    config: ResolvedScenarioConfig,
    validation: Any,
) -> None:
    data = build_plot_data(telemetry)
    profiles = config.profile_mapping()
    modes = tuple(MissionMode(state) for state in data.mission_states)
    target_vy = np.asarray([profiles[state].target_vertical_velocity for state in modes])
    target_pitch = np.asarray([degrees(profiles[state].target_pitch) for state in modes])
    colors = {"truth": "#165DFF", "measured": "#F59E0B", "target": "#64748B", "actual": "#16A34A", "fault": "#DC2626"}
    try:
        with plt.rc_context({"axes.grid": True, "grid.alpha": 0.22, "figure.facecolor": "white", "axes.facecolor": "white"}):
            fig, axes = plt.subplots(3, 2, figsize=(14, 12), constrained_layout=True)
            ax = axes.ravel()
            ax[0].plot(data.x, data.y, color=colors["truth"], label="Truth trajectory")
            ax[0].scatter([data.x[0], data.x[-1]], [data.y[0], data.y[-1]], c=[colors["actual"], colors["fault"]], marker="o")
            ax[0].axhline(0.0, color="black", linewidth=1, label="Ground")
            ax[0].scatter([0], [0], marker="x", color=colors["target"], label="Target")
            ax[0].set(title="2D trajectory", xlabel="Horizontal position (m)", ylabel="Altitude (m)")
            ax[0].legend(loc="best")
            ax[1].plot(data.time, data.y, color=colors["truth"], label="Truth")
            ax[1].step(data.time, data.measured_y, where="post", color=colors["measured"], label="Measured")
            ax[1].set(title="Altitude", xlabel="Time (s)", ylabel="Altitude (m)")
            ax[2].plot(data.time, data.vy, color=colors["truth"], label="Truth")
            ax[2].step(data.time, data.measured_vy, where="post", color=colors["measured"], label="Measured")
            ax[2].step(data.time, target_vy, where="post", linestyle="--", color=colors["target"], label="Target")
            ax[2].set(title="Vertical velocity", xlabel="Time (s)", ylabel="Velocity (m/s)")
            ax[3].plot(data.time, data.theta_deg, color=colors["truth"], label="Truth")
            ax[3].step(data.time, data.measured_theta_deg, where="post", color=colors["measured"], label="Measured")
            ax[3].step(data.time, target_pitch, where="post", linestyle="--", color=colors["target"], label="Target")
            ax[3].set(title="Pitch attitude", xlabel="Time (s)", ylabel="Pitch (deg)")
            ax[4].step(data.time, data.command_throttle, where="post", color=colors["measured"], label="Requested")
            ax[4].plot(data.time, data.actual_throttle, color=colors["actual"], label="Applied")
            ax[4].set(title="Throttle response", xlabel="Time (s)", ylabel="Normalized throttle", ylim=(-0.05, 1.05))
            ax[5].step(data.time, data.command_gimbal_deg, where="post", color=colors["measured"], label="Requested")
            ax[5].plot(data.time, data.actual_gimbal_deg, color=colors["actual"], label="Applied")
            ax[5].set(title="Gimbal response", xlabel="Time (s)", ylabel="Gimbal (deg)")
            for axis in ax[1:]:
                axis.legend(loc="best")
            for event in telemetry.events:
                if event.source == "fault":
                    for axis in ax[1:]: axis.axvline(event.time, color=colors["fault"], linestyle=":" if "activated" in event.event_type else "--", linewidth=1)
            result = "PASS" if validation.scenario_passed else "FAIL"
            fig.suptitle(f"{config.id} — {validation.actual_outcome.value} (scenario {result})")
            fig.savefig(path, dpi=150, metadata={"Software": "AstraLoop"})
            plt.close(fig)
    except Exception as exc:
        raise PlotError(f"Unable to generate diagnostic plot: {exc}") from exc
