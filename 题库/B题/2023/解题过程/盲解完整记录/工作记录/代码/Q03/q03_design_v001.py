from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / "工作记录" / "诊断结果" / "Q03"
RESULT_DIR = ROOT / "工作记录" / "结果" / "Q03"
JSON_PATH = OUT_DIR / "q03_design_output_v001.json"
CSV_PATH = RESULT_DIR / "第3问测线设计-v001.csv"

NMI = 1852.0
X_WEST = -2.0 * NMI
X_EAST = 2.0 * NMI
Y_SOUTH = -1.0 * NMI
Y_NORTH = 1.0 * NMI
D0 = 110.0
ALPHA = math.radians(1.5)
GAMMA = math.radians(60.0)
K = math.tan(ALPHA)
SEC = 1.0 / math.cos(ALPHA)
A_DOWN = math.sin(GAMMA) / math.cos(GAMMA + ALPHA)
B_UP = math.sin(GAMMA) / math.cos(GAMMA - ALPHA)


def line_at_x(x: float) -> dict[str, float]:
    depth = D0 - K * x
    q = x * SEC
    a = A_DOWN * depth
    b = B_UP * depth
    return {
        "x_m": x,
        "x_nmi": x / NMI,
        "depth_m": depth,
        "q_m": q,
        "left_q_m": q - a,
        "right_q_m": q + b,
        "width_slope_m": a + b,
        "left_x_m": (q - a) / SEC,
        "right_x_m": (q + b) / SEC,
    }


def solve_x_from_left(left_q: float) -> float:
    return (left_q + A_DOWN * D0) / (SEC + A_DOWN * K)


def generate(target_eta: float) -> list[dict[str, float | int | str | None]]:
    x = solve_x_from_left(X_WEST * SEC)
    lines: list[dict[str, float | int | str | None]] = []
    while True:
        geom = line_at_x(x)
        row: dict[str, float | int | str | None] = {
            "line_id": f"L{len(lines) + 1:02d}",
            "order_west_to_east": len(lines) + 1,
            "direction": "south-to-north",
            "direction_deg_from_east_ccw": 90.0,
            "start_x_m": x,
            "start_y_m": Y_SOUTH,
            "end_x_m": x,
            "end_y_m": Y_NORTH,
            "length_inside_m": Y_NORTH - Y_SOUTH,
            **geom,
            "spacing_from_previous_m": None,
            "signed_overlap_m": None,
            "overlap_rate_previous": None,
            "overlap_rate_current": None,
        }
        if lines:
            previous = lines[-1]
            signed = float(previous["right_q_m"]) - float(geom["left_q_m"])
            row["spacing_from_previous_m"] = x - float(previous["x_m"])
            row["signed_overlap_m"] = signed
            row["overlap_rate_previous"] = signed / float(previous["width_slope_m"])
            row["overlap_rate_current"] = signed / float(geom["width_slope_m"])
        lines.append(row)
        if float(geom["right_q_m"]) >= X_EAST * SEC:
            break
        next_left = float(geom["right_q_m"]) - target_eta * float(geom["width_slope_m"])
        x = solve_x_from_left(next_left)
        if len(lines) > 200:
            raise RuntimeError("Unexpected non-termination")
    return lines


def interval_union_length(intervals: list[tuple[float, float]]) -> tuple[float, float]:
    ordered = sorted(intervals)
    start, end = ordered[0]
    total = 0.0
    max_gap = 0.0
    for left, right in ordered[1:]:
        if left > end:
            max_gap = max(max_gap, left - end)
            total += end - start
            start, end = left, right
        else:
            end = max(end, right)
    total += end - start
    return total, max_gap


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    targets = [0.10, 0.1001, 0.101, 0.105, 0.15, 0.20]
    candidates = []
    all_designs = {}
    for target in targets:
        lines = generate(target)
        all_designs[f"{target:.4f}"] = lines
        etas = [float(row["overlap_rate_previous"]) for row in lines[1:]]
        current_etas = [float(row["overlap_rate_current"]) for row in lines[1:]]
        candidates.append({
            "candidate": f"contour-adaptive-eta-{target:.4f}",
            "target_eta": target,
            "feasible": min(etas) >= 0.10 - 1e-12 and max(etas) <= 0.20 + 1e-12,
            "line_count": len(lines),
            "total_length_m": len(lines) * (Y_NORTH - Y_SOUTH),
            "min_eta_previous": min(etas),
            "max_eta_previous": max(etas),
            "min_eta_current": min(current_etas),
            "max_eta_current": max(current_etas),
        })

    final_lines = all_designs["0.1001"]
    intervals = [
        (max(X_WEST, float(row["left_x_m"])), min(X_EAST, float(row["right_x_m"])))
        for row in final_lines
    ]
    union_x, max_gap = interval_union_length(intervals)
    total_length = sum(float(row["length_inside_m"]) for row in final_lines)
    etas = [float(row["overlap_rate_previous"]) for row in final_lines[1:]]
    current_etas = [float(row["overlap_rate_current"]) for row in final_lines[1:]]

    midpoint_width = line_at_x(0.0)["width_slope_m"]
    east_flat_width = 2.0 * (D0 - K * X_EAST) * math.tan(GAMMA)
    west_flat_width = 2.0 * (D0 - K * X_WEST) * math.tan(GAMMA)
    slope_spacing = 0.85 * 2.0 * D0 * math.tan(GAMMA)
    slope_eta_west = 1.0 - slope_spacing / west_flat_width
    slope_eta_east = 1.0 - slope_spacing / east_flat_width

    angle_screen = []
    for angle_deg in [85, 88, 89, 89.2, 89.5, 90]:
        angle = math.radians(angle_deg)
        dx = 0.0 if angle_deg == 90 else (Y_NORTH - Y_SOUTH) / math.tan(angle)
        shallow = D0 - K * X_EAST
        deep = shallow + K * abs(dx)
        width_ratio = deep / shallow
        overlap_window_possible = width_ratio <= 0.90 / 0.80 + 1e-12
        chord = (Y_NORTH - Y_SOUTH) / math.sin(angle)
        angle_screen.append({
            "angle_deg_from_east": angle_deg,
            "x_variation_for_full_height_m": abs(dx),
            "shallow_edge_depth_ratio": width_ratio,
            "necessary_overlap_window_passed": overlap_window_possible,
            "full_height_chord_m": chord,
            "34_line_relaxed_length_m": 34 * chord,
        })

    report = {
        "parameters": {
            "region_x_m": [X_WEST, X_EAST],
            "region_y_m": [Y_SOUTH, Y_NORTH],
            "center_depth_m": D0,
            "alpha_deg": math.degrees(ALPHA),
            "theta_deg": 120.0,
            "gamma_deg": math.degrees(GAMMA),
            "formal_length_scope": "sum of line intersections with the rectangle",
            "overlap_definition": "signed overlap divided by previous strip width",
        },
        "final": {
            "name": "north-south contour-parallel adaptive spacing",
            "target_eta": 0.1001,
            "line_count": len(final_lines),
            "total_length_m": total_length,
            "total_length_km": total_length / 1000.0,
            "min_eta_previous": min(etas),
            "max_eta_previous": max(etas),
            "min_eta_current": min(current_etas),
            "max_eta_current": max(current_etas),
            "west_boundary_margin_m": X_WEST - min(float(row["left_x_m"]) for row in final_lines),
            "east_boundary_margin_m": max(float(row["right_x_m"]) for row in final_lines) - X_EAST,
            "covered_x_union_m": union_x,
            "maximum_x_gap_m": max_gap,
            "missing_area_m2": max(0.0, (X_EAST - X_WEST - union_x) * (Y_NORTH - Y_SOUTH)),
            "lines": final_lines,
        },
        "candidate_comparison": candidates,
        "infeasible_baselines": {
            "east_west_slope_parallel": {
                "midpoint_15pct_spacing_m": slope_spacing,
                "overlap_at_west_deep_edge": slope_eta_west,
                "overlap_at_east_shallow_edge": slope_eta_east,
                "feasible": False,
            },
            "constant_spacing_contour": {
                "midpoint_width_m": midpoint_width,
                "reason": "a spacing selected at midpoint cannot satisfy both limits over the full depth range",
                "feasible": False,
            },
        },
        "angle_screen": angle_screen,
        "random_seed": "not applicable; deterministic recurrence and finite screening",
    }
    JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    columns = [
        "line_id", "order_west_to_east", "direction", "direction_deg_from_east_ccw",
        "start_x_m", "start_y_m", "end_x_m", "end_y_m", "length_inside_m",
        "x_nmi", "depth_m", "spacing_from_previous_m", "width_slope_m",
        "signed_overlap_m", "overlap_rate_previous", "overlap_rate_current",
        "left_x_m", "right_x_m",
    ]
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(final_lines)

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.set_xlim(X_WEST / NMI, X_EAST / NMI)
    ax.set_ylim(Y_SOUTH / NMI, Y_NORTH / NMI)
    for row in final_lines:
        x = float(row["x_nmi"])
        ax.plot([x, x], [Y_SOUTH / NMI, Y_NORTH / NMI], color="#155E75", lw=0.8)
    ax.set_xlabel("East-west coordinate (nmi; east positive)")
    ax.set_ylabel("North-south coordinate (nmi)")
    ax.set_title("Question 3 final north-south survey lines")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "第3问测线布局-v001.png", dpi=220)
    plt.close(fig)

    fig, ax1 = plt.subplots(figsize=(10, 5))
    xs = [float(row["x_nmi"]) for row in final_lines]
    spacings = [math.nan if row["spacing_from_previous_m"] is None else float(row["spacing_from_previous_m"]) for row in final_lines]
    rates = [math.nan if row["overlap_rate_previous"] is None else 100.0 * float(row["overlap_rate_previous"]) for row in final_lines]
    ax1.plot(xs, spacings, "o-", color="#2563EB", ms=3, label="Spacing")
    ax1.set_xlabel("Line x coordinate (nmi)")
    ax1.set_ylabel("Spacing from previous line (m)", color="#2563EB")
    ax2 = ax1.twinx()
    ax2.plot(xs, rates, "s-", color="#DC2626", ms=3, label="Overlap")
    ax2.axhspan(10, 20, color="#DCFCE7", alpha=0.7)
    ax2.set_ylabel("Previous-strip overlap rate (%)", color="#DC2626")
    ax1.set_title("Question 3 adaptive spacing and overlap")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "第3问间距与重叠率-v001.png", dpi=220)
    plt.close(fig)

    print(json.dumps({
        "line_count": len(final_lines),
        "total_length_m": total_length,
        "eta_range": [min(etas), max(etas)],
        "current_eta_range": [min(current_etas), max(current_etas)],
        "maximum_x_gap_m": max_gap,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
