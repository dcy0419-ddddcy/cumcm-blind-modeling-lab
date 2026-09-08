from __future__ import annotations

import json
import math
from pathlib import Path

from q03_design_v001 import (
    ALPHA, D0, GAMMA, K, NMI, ROOT, SEC, X_EAST, X_WEST, Y_NORTH, Y_SOUTH,
    generate, line_at_x,
)


OUT = ROOT / "工作记录" / "诊断结果" / "Q03" / "q03_verification_v001.json"
DESIGN = ROOT / "工作记录" / "诊断结果" / "Q03" / "q03_design_output_v001.json"


def ray_line_endpoints(x_ship: float) -> tuple[float, float]:
    depth = D0 - K * x_ship
    points = []
    for sign in (-1.0, 1.0):
        dx = sign * math.sin(GAMMA)
        dz = -math.cos(GAMMA)
        denominator = dz - K * dx
        parameter = -depth / denominator
        if parameter < 0:
            raise ValueError("Backward ray")
        points.append(x_ship + parameter * dx)
    return min(points), max(points)


def merge(intervals: list[tuple[float, float]]) -> tuple[float, float]:
    ordered = sorted(intervals)
    left, right = ordered[0]
    total = 0.0
    gap = 0.0
    for a, b in ordered[1:]:
        if a > right:
            total += right - left
            gap = max(gap, a - right)
            left, right = a, b
        else:
            right = max(right, b)
    return total + right - left, gap


def main() -> None:
    report = json.loads(DESIGN.read_text(encoding="utf-8"))
    lines = report["final"]["lines"]

    endpoint_errors = []
    intervals = []
    for row in lines:
        x = float(row["x_m"])
        left, right = ray_line_endpoints(x)
        endpoint_errors.extend([abs(left - float(row["left_x_m"])), abs(right - float(row["right_x_m"]))])
        intervals.append((max(X_WEST, left), min(X_EAST, right)))

    union, gap = merge(intervals)
    region_width = X_EAST - X_WEST
    region_height = Y_NORTH - Y_SOUTH
    missing_area = max(0.0, region_width - union) * region_height
    etas = []
    current_etas = []
    signed = []
    for previous, current in zip(lines, lines[1:]):
        overlap = float(previous["right_q_m"]) - float(current["left_q_m"])
        signed.append(overlap)
        etas.append(overlap / float(previous["width_slope_m"]))
        current_etas.append(overlap / float(current["width_slope_m"]))

    total_from_rows = sum(float(row["length_inside_m"]) for row in lines)
    target_counts = {str(target): len(generate(target)) for target in [0.10, 0.1001, 0.101, 0.105, 0.15, 0.20]}
    first = lines[0]
    last = lines[-1]

    checks = {
        "independent_ray_endpoints": max(endpoint_errors) < 1e-9,
        "whole_rectangle_covered": missing_area < 1e-8,
        "west_boundary_covered": float(first["left_x_m"]) <= X_WEST + 1e-9,
        "east_boundary_covered": float(last["right_x_m"]) >= X_EAST - 1e-9,
        "overlap_previous_between_10_and_20_percent": min(etas) >= 0.10 - 1e-12 and max(etas) <= 0.20 + 1e-12,
        "no_negative_overlap_or_gap": min(signed) > 0 and gap < 1e-10,
        "current_denominator_sensitivity_still_feasible": min(current_etas) >= 0.10 and max(current_etas) <= 0.20,
        "row_length_sum_matches": abs(total_from_rows - float(report["final"]["total_length_m"])) < 1e-9,
        "directions_and_units": all(float(row["direction_deg_from_east_ccw"]) == 90.0 for row in lines),
        "all_depths_positive": all(float(row["depth_m"]) > 0 for row in lines),
        "target_perturbation_line_count_stable": target_counts["0.1"] == target_counts["0.1001"] == target_counts["0.101"] == 34,
    }

    verification = {
        "checks": checks,
        "all_passed": all(checks.values()),
        "metrics": {
            "maximum_endpoint_error_m": max(endpoint_errors),
            "union_x_length_m": union,
            "maximum_gap_m": gap,
            "missing_area_m2": missing_area,
            "min_overlap_previous": min(etas),
            "max_overlap_previous": max(etas),
            "min_overlap_current": min(current_etas),
            "max_overlap_current": max(current_etas),
            "total_length_from_rows_m": total_from_rows,
            "target_line_counts": target_counts,
        },
        "optimality_statement": "minimum line count in the ordered north-south contour-parallel recurrence class; finite direction screening does not prove global optimality over all straight or curved designs",
        "random_seed": "not applicable",
    }
    OUT.write_text(json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"all_passed": verification["all_passed"], **verification["metrics"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

