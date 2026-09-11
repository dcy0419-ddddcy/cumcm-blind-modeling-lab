"""Run all numerical calculations and create machine-readable intermediate files."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.bench_dragon import (  # noqa: E402
    ArchimedeanSpiral,
    BiarcTurnPath,
    N_HANDLES,
    find_collision_time,
    find_minimum_pitch,
    key_handle_indices,
    maximum_unit_head_speed_amplification,
    path_configuration,
    pitch_boundary_gap,
    spiral_configuration_at_time,
    trajectory_clearance,
)


def write_csv(path: Path, header: list[str], rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def compute(output_dir: Path, quick: bool = False) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary: dict = {}

    # Question 1: one configuration for every integer second.
    q1_times = range(0, 301)
    q1_cfgs = [spiral_configuration_at_time(float(t)) for t in q1_times]
    q1_rows = []
    for t, cfg in zip(q1_times, q1_cfgs):
        for i in range(N_HANDLES):
            q1_rows.append((t, i, cfg.points[i, 0], cfg.points[i, 1], cfg.speeds[i]))
    write_csv(output_dir / "question1_all_handles.csv",
              ["time_s", "handle_index", "x_m", "y_m", "speed_mps"], q1_rows)
    summary["question1"] = {
        "times_s": [0, 60, 120, 180, 240, 300],
        "key_handles": {},
        "max_chord_error_m": float(max(
            max(abs(np.linalg.norm(c.points[1] - c.points[0]) - 2.86),
                np.max(abs(np.linalg.norm(np.diff(c.points, axis=0), axis=1)[1:] - 1.65)))
            for c in q1_cfgs
        )),
    }
    for i in key_handle_indices():
        summary["question1"]["key_handles"][str(i)] = [
            {
                "time_s": t,
                "x_m": float(q1_cfgs[t].points[i, 0]),
                "y_m": float(q1_cfgs[t].points[i, 1]),
                "speed_mps": float(q1_cfgs[t].speeds[i]),
            }
            for t in summary["question1"]["times_s"]
        ]
    print("question 1 complete", flush=True)

    # Question 2: exact first rectangle contact.
    collision_time, collision_pair, collision_gap = find_collision_time()
    q2_cfg = spiral_configuration_at_time(collision_time)
    write_csv(output_dir / "question2_terminal.csv",
              ["handle_index", "x_m", "y_m", "speed_mps"],
              [(i, q2_cfg.points[i, 0], q2_cfg.points[i, 1], q2_cfg.speeds[i])
               for i in range(N_HANDLES)])
    summary["question2"] = {
        "termination_time_s": collision_time,
        "contact_board_indices": list(collision_pair),
        "sat_gap_m": collision_gap,
        "key_handles": {
            str(i): {
                "x_m": float(q2_cfg.points[i, 0]),
                "y_m": float(q2_cfg.points[i, 1]),
                "speed_mps": float(q2_cfg.speeds[i]),
            }
            for i in key_handle_indices()
        },
    }
    print("question 2 complete", collision_time, collision_pair, flush=True)

    # Question 3: limiting pitch at head radius 4.5 m.
    min_pitch, limiting_radius, pitch_pair, pitch_gap = find_minimum_pitch()
    summary["question3"] = {
        "minimum_pitch_m": min_pitch,
        "limiting_head_radius_m": limiting_radius,
        "contact_board_indices": list(pitch_pair),
        "sat_gap_m": pitch_gap,
        "neighbor_checks": [
            {
                "pitch_m": p,
                "minimum_trajectory_gap_m": float(trajectory_clearance(p)[0]),
            }
            for p in (min_pitch - 0.001, min_pitch, min_pitch + 0.001)
        ],
    }
    print("question 3 complete", min_pitch, pitch_pair, flush=True)

    # Question 4: fixed boundary tangency points and the prescribed 2:1 biarc.
    path = BiarcTurnPath()
    q4_times = range(-100, 101)
    q4_cfgs = [path_configuration(path, float(t)) for t in q4_times]
    q4_rows = []
    for t, cfg in zip(q4_times, q4_cfgs):
        for i in range(N_HANDLES):
            q4_rows.append((t, i, cfg.points[i, 0], cfg.points[i, 1], cfg.speeds[i]))
    write_csv(output_dir / "question4_all_handles.csv",
              ["time_s", "handle_index", "x_m", "y_m", "speed_mps"], q4_rows)
    summary["question4"] = {
        "theta_entry_rad": path.theta_a,
        "entry_point_m": path.entry.tolist(),
        "exit_point_m": path.exit.tolist(),
        "large_arc_radius_m": path.r1,
        "small_arc_radius_m": path.r2,
        "common_central_angle_rad": path.alpha,
        "turn_curve_length_m": path.turn_length,
        "radius_sum_invariance_m": path.radius_sum,
        "can_shorten_by_radius_split_with_fixed_endpoints": False,
        "key_handles": {},
    }
    for i in key_handle_indices():
        summary["question4"]["key_handles"][str(i)] = [
            {
                "time_s": t,
                "x_m": float(q4_cfgs[t + 100].points[i, 0]),
                "y_m": float(q4_cfgs[t + 100].points[i, 1]),
                "speed_mps": float(q4_cfgs[t + 100].speeds[i]),
            }
            for t in (-100, -50, 0, 50, 100)
        ]
    print("question 4 complete", path.turn_length, flush=True)

    # Question 5: scaling of all handle velocities with the head velocity.
    if quick:
        amplification, peak_s, peak_handle = maximum_unit_head_speed_amplification(
            path, scan_interval=(-4.0, 120.0), step=1.0
        )
        scan_note = "quick diagnostic interval"
    else:
        amplification, peak_s, peak_handle = maximum_unit_head_speed_amplification(
            path, step=0.5
        )
        scan_note = "complete passage, conservative interval"
    peak_cfg = path_configuration(path, peak_s)
    peak_value = float(np.max(peak_cfg.speeds))
    co_limiting_handles = [
        int(i) for i, value in enumerate(peak_cfg.speeds)
        if peak_value - float(value) < 1e-8
    ]
    chain_chords = 2.86 + (N_HANDLES - 2) * 1.65
    scan_start = -4.0
    scan_stop = path.turn_length + chain_chords + 35.0
    start_cfg = path_configuration(path, scan_start)
    stop_cfg = path_configuration(path, scan_stop)
    summary["question5"] = {
        "maximum_speed_amplification": amplification,
        "maximum_head_speed_mps": 2.0 / amplification,
        "peak_head_path_coordinate_m_at_unit_speed": peak_s,
        "representative_limiting_handle_index": min(co_limiting_handles),
        "co_limiting_handle_indices_within_1e-8": co_limiting_handles,
        "scan_scope": scan_note,
        "full_scan_interval_head_s_m": [scan_start, scan_stop],
        "start_all_handles_before_first_arc": bool(np.max(start_cfg.parameters) < 0.0),
        "stop_rear_handle_after_second_arc": bool(stop_cfg.parameters[-1] > path.turn_length),
        "rear_handle_s_at_stop_m": float(stop_cfg.parameters[-1]),
    }
    print("question 5 complete", summary["question5"], flush=True)

    with (output_dir / "summary.json").open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "computed")
    parser.add_argument("--quick", action="store_true",
                        help="Use a shortened question-5 scan for development only.")
    args = parser.parse_args()
    compute(args.output_dir, args.quick)


if __name__ == "__main__":
    main()
