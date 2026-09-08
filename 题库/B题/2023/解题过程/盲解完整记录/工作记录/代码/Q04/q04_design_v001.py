from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from q04_terrain_v001 import NMI, OUT_DIR, ROOT, Terrain


RESULT_DIR = ROOT / "工作记录" / "结果" / "Q04"
JSON_PATH = OUT_DIR / "q04_design_output_v001.json"
CSV_PATH = RESULT_DIR / "第4问测线设计-v001.csv"


def samples(lo: float, hi: float, step: float) -> np.ndarray:
    count = max(2, int(math.ceil((hi - lo) / step)) + 1)
    return np.linspace(lo, hi, count)


def midpoint_samples(lo: float, hi: float, step: float) -> tuple[np.ndarray, float]:
    count = max(1, int(math.ceil((hi - lo) / step)))
    actual = (hi - lo) / count
    return lo + (np.arange(count) + 0.5) * actual, actual


def bounds(terrain: Terrain, line: dict, along: np.ndarray, representation: str):
    return terrain.strip_bounds(line["axis"], line["center_m"], along, representation)[:2]


def make_line(axis: str, center: float, block: str, cross_min: float, cross_max: float, along_min: float, along_max: float, order: int) -> dict:
    if axis == "vertical":
        start = [center, along_min]
        end = [center, along_max]
        direction = "south-to-north"
        angle = 90.0
    else:
        start = [along_min, center]
        end = [along_max, center]
        direction = "west-to-east"
        angle = 0.0
    return {
        "line_id": f"{block}-L{order:03d}",
        "block": block,
        "axis": axis,
        "direction": direction,
        "direction_deg_from_east_ccw": angle,
        "center_m": center,
        "start_x_m": start[0],
        "start_y_m": start[1],
        "end_x_m": end[0],
        "end_y_m": end[1],
        "length_inside_m": along_max - along_min,
        "cross_min_m": cross_min,
        "cross_max_m": cross_max,
        "along_min_m": along_min,
        "along_max_m": along_max,
    }


def bisect_increasing(function, lo: float, hi: float, target: float = 0.0) -> float:
    flo = function(lo) - target
    fhi = function(hi) - target
    if flo > 0 or fhi < 0:
        raise ValueError(f"Root not bracketed: {flo}, {fhi}")
    for _ in range(55):
        mid = 0.5 * (lo + hi)
        if function(mid) < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def generate_adaptive(terrain: Terrain, axis: str, rectangle: tuple[float, float, float, float], target_eta: float, block: str, step: float = 10.0) -> list[dict]:
    xmin, xmax, ymin, ymax = rectangle
    if axis == "vertical":
        cross_min, cross_max, along_min, along_max = xmin, xmax, ymin, ymax
    else:
        cross_min, cross_max, along_min, along_max = ymin, ymax, xmin, xmax
    along = samples(along_min, along_max, step)

    def left_margin(center: float) -> float:
        left, _, _, _ = terrain.strip_bounds(axis, center, along, "bilinear")
        return float(np.max(left))

    hi = min(cross_max, cross_min + 1500.0)
    while left_margin(hi) < cross_min and hi < cross_max:
        hi = min(cross_max, hi + 1000.0)
    first_center = bisect_increasing(left_margin, cross_min, hi, cross_min)
    lines = [make_line(axis, first_center, block, cross_min, cross_max, along_min, along_max, 1)]

    while True:
        previous = lines[-1]
        _, previous_right, _, _ = terrain.strip_bounds(axis, previous["center_m"], along, "bilinear")
        first_left, first_right, _, _ = terrain.strip_bounds(axis, previous["center_m"], along, "bilinear")
        if float(np.min(previous_right)) >= cross_max:
            break

        def min_eta(center: float) -> float:
            current_left, _, _, _ = terrain.strip_bounds(axis, center, along, "bilinear")
            return float(np.min((previous_right - current_left) / (previous_right - first_left)))

        lo = previous["center_m"] + 0.01
        hi = min(cross_max, lo + 1000.0)
        while min_eta(hi) > target_eta and hi < cross_max:
            hi = min(cross_max, hi + 1000.0)
        if min_eta(hi) > target_eta and hi >= cross_max:
            center = cross_max
        else:
            center = bisect_increasing(lambda c: -min_eta(c), lo, hi, -target_eta)
        lines.append(make_line(axis, center, block, cross_min, cross_max, along_min, along_max, len(lines) + 1))
        if len(lines) > 180:
            raise RuntimeError("Too many lines")
    return lines


def generate_uniform(terrain: Terrain, axis: str, rectangle: tuple[float, float, float, float], block: str, step: float = 10.0) -> list[dict]:
    adaptive_first = generate_adaptive(terrain, axis, rectangle, 0.02, block + "-seed", step)[0]
    xmin, xmax, ymin, ymax = rectangle
    if axis == "vertical":
        cross_min, cross_max, along_min, along_max = xmin, xmax, ymin, ymax
    else:
        cross_min, cross_max, along_min, along_max = ymin, ymax, xmin, xmax
    along = samples(along_min, along_max, step)
    center_mid = 0.5 * (cross_min + cross_max)
    left, right, _, _ = terrain.strip_bounds(axis, center_mid, along, "bilinear")
    spacing = 0.9 * float(np.median(right - left))
    centers = [adaptive_first["center_m"]]
    while centers[-1] < cross_max and len(centers) < 180:
        centers.append(min(cross_max, centers[-1] + spacing))
        _, right_last, _, _ = terrain.strip_bounds(axis, centers[-1], along, "bilinear")
        if float(np.min(right_last)) >= cross_max:
            break
    return [make_line(axis, center, block, cross_min, cross_max, along_min, along_max, i + 1) for i, center in enumerate(centers)]


def union_length(intervals: list[tuple[float, float]]) -> float:
    if not intervals:
        return 0.0
    ordered = sorted(intervals)
    left, right = ordered[0]
    total = 0.0
    for a, b in ordered[1:]:
        if a > right:
            total += right - left
            left, right = a, b
        else:
            right = max(right, b)
    return total + right - left


def evaluate_block(terrain: Terrain, lines: list[dict], representation: str, step: float) -> dict:
    first = lines[0]
    along, ds = midpoint_samples(first["along_min_m"], first["along_max_m"], step)
    cross_min = first["cross_min_m"]
    cross_max = first["cross_max_m"]
    strip_bounds = [bounds(terrain, line, along, representation) for line in lines]
    missing_widths = []
    for index in range(along.size):
        intervals = [
            (max(cross_min, float(left[index])), min(cross_max, float(right[index])))
            for left, right in strip_bounds
            if right[index] > cross_min and left[index] < cross_max
        ]
        missing_widths.append((cross_max - cross_min) - union_length(intervals))
    missing_area = max(0.0, float(np.sum(np.maximum(missing_widths, 0.0))) * ds)

    over20_length = 0.0
    pair_metrics = []
    for (previous, current), (previous_bounds, current_bounds) in zip(
        zip(lines, lines[1:]), zip(strip_bounds, strip_bounds[1:])
    ):
        previous_left, previous_right = previous_bounds
        current_left, _ = current_bounds
        eta = (previous_right - current_left) / (previous_right - previous_left)
        over = eta > 0.20
        pair_length = float(np.sum(over) * ds)
        over20_length += pair_length
        pair_metrics.append({
            "previous": previous["line_id"],
            "current": current["line_id"],
            "min_eta": float(np.min(eta)),
            "max_eta": float(np.max(eta)),
            "over20_length_m": pair_length,
        })
    return {
        "missing_area_m2": missing_area,
        "over20_pair_counted_length_m": over20_length,
        "pair_metrics": pair_metrics,
        "slice_step_m": ds,
    }


def evaluate_design(terrain: Terrain, design: dict, representation: str, step: float) -> dict:
    area = 0.0
    over20 = 0.0
    all_pairs = []
    for block in design["blocks"]:
        metric = evaluate_block(terrain, block["lines"], representation, step)
        area += metric["missing_area_m2"]
        over20 += metric["over20_pair_counted_length_m"]
        all_pairs.extend(metric["pair_metrics"])
    over20 += design.get("patch_over20_length_m", 0.0)
    total_length = sum(line["length_inside_m"] for block in design["blocks"] for line in block["lines"])
    total_length += sum(line["length_inside_m"] for line in design.get("patches", []))
    total_area = sum(
        (block["rectangle"][1] - block["rectangle"][0]) * (block["rectangle"][3] - block["rectangle"][2])
        for block in design["blocks"]
    )
    return {
        "representation": representation,
        "step_m": step,
        "missing_area_m2": area,
        "missing_percent": 100.0 * area / total_area,
        "over20_pair_counted_length_m": over20,
        "total_length_m": total_length,
        "pair_metrics": all_pairs,
    }


def nondominated(rows: list[dict]) -> list[str]:
    selected = []
    for row in rows:
        dominated = False
        for other in rows:
            if other is row:
                continue
            keys = ["missing_percent", "over20_pair_counted_length_m", "total_length_m"]
            if all(other[key] <= row[key] + 1e-12 for key in keys) and any(other[key] < row[key] - 1e-12 for key in keys):
                dominated = True
                break
        if not dominated:
            selected.append(row["name"])
    return selected


def main() -> None:
    terrain = Terrain()
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    rectangle = (terrain.x[0], terrain.x[-1], terrain.y[0], terrain.y[-1])
    designs = []

    uniform = {"name": "uniform-vertical-baseline", "blocks": [{"name": "all", "rectangle": rectangle, "lines": generate_uniform(terrain, "vertical", rectangle, "U")}], "patches": []}
    designs.append(uniform)
    for target in [0.0, 0.01, 0.02, 0.05, 0.10]:
        designs.append({
            "name": f"dominant-contour-adaptive-{target:.2f}",
            "blocks": [{"name": "all", "rectangle": rectangle, "lines": generate_adaptive(terrain, "vertical", rectangle, target, f"V{int(target*100):02d}")}],
            "patches": [],
        })
    designs.append({
        "name": "adaptive-horizontal-0.02",
        "blocks": [{"name": "all", "rectangle": rectangle, "lines": generate_adaptive(terrain, "horizontal", rectangle, 0.02, "H")}],
        "patches": [],
    })

    ymid = 0.5 * (terrain.y[0] + terrain.y[-1])
    south = (terrain.x[0], terrain.x[-1], terrain.y[0], ymid)
    north = (terrain.x[0], terrain.x[-1], ymid, terrain.y[-1])
    designs.append({
        "name": "mixed-two-direction-blocks",
        "blocks": [
            {"name": "south-vertical", "rectangle": south, "lines": generate_adaptive(terrain, "vertical", south, 0.02, "BSV")},
            {"name": "north-horizontal", "rectangle": north, "lines": generate_adaptive(terrain, "horizontal", north, 0.02, "BNH")},
        ],
        "patches": [],
        "interface_rule": "half-open ownership by block; footprints and adjacency clipped to assigned block, seam has zero area",
    })

    metrics = []
    for design in designs:
        metric = evaluate_design(terrain, design, "bilinear", 20.0)
        metrics.append({"name": design["name"], "line_count": sum(len(b["lines"]) for b in design["blocks"]), **{k: v for k, v in metric.items() if k != "pair_metrics"}})

    zero_level = min(row["missing_percent"] for row in metrics)
    frozen_tolerance = max(1e-8, zero_level + 1e-8)
    feasible = [row for row in metrics if row["missing_percent"] <= frozen_tolerance]
    best_metric = min(feasible, key=lambda row: (row["over20_pair_counted_length_m"], row["total_length_m"]))
    best_design = next(design for design in designs if design["name"] == best_metric["name"])

    patch_line = make_line("horizontal", 0.5 * (terrain.y[0] + terrain.y[-1]), "PATCH", terrain.y[0], terrain.y[-1], 0.4 * terrain.x[-1], 0.6 * terrain.x[-1], 1)
    patch_design = {
        "name": best_design["name"] + "-plus-redundant-patch",
        "blocks": best_design["blocks"],
        "patches": [patch_line],
        "patch_over20_length_m": patch_line["length_inside_m"],
        "note": "patch lies in an already covered zone and is conservatively counted as entirely over-20%; it is dominated",
    }
    patch_metric = evaluate_design(terrain, patch_design, "bilinear", 20.0)
    metrics.append({"name": patch_design["name"], "line_count": sum(len(b["lines"]) for b in patch_design["blocks"]) + 1, **{k: v for k, v in patch_metric.items() if k != "pair_metrics"}})
    designs.append(patch_design)

    final_bilinear_10 = evaluate_design(terrain, best_design, "bilinear", 10.0)
    final_bilinear_5 = evaluate_design(terrain, best_design, "bilinear", 5.0)
    final_tri_main_5 = evaluate_design(terrain, best_design, "tri_main", 5.0)
    final_tri_anti_5 = evaluate_design(terrain, best_design, "tri_anti", 5.0)

    all_lines = [line for block in best_design["blocks"] for line in block["lines"]] + best_design.get("patches", [])
    for i, line in enumerate(all_lines, 1):
        line["final_order"] = i
        along_mid = 0.5 * (line["along_min_m"] + line["along_max_m"])
        if line["axis"] == "vertical":
            depth, zx, zy = terrain.evaluate(line["center_m"], along_mid)
        else:
            depth, zx, zy = terrain.evaluate(along_mid, line["center_m"])
        line["representative_depth_m"] = float(depth)
        line["representative_slope_deg"] = float(math.degrees(math.atan(math.hypot(float(zx), float(zy)))))

    report = {
        "source_sha256": terrain.source_hash,
        "assumptions": {
            "theta_deg": 120.0,
            "gamma_deg": 60.0,
            "opening_angle_status": "user-approved planning baseline, not a Q4 statement fact",
            "terrain_status": "historical grid used as current planning baseline",
            "main_representation": "piecewise bilinear depth surface",
            "formal_length": "sum of line segments inside the target region",
            "over20_counting": "per ordered adjacent pair; the current line segment is counted once per exceeding neighbor pair, so a segment may be counted twice if both sides exceed",
        },
        "candidate_metrics_coarse": metrics,
        "pareto_names": nondominated(metrics),
        "selection": {
            "frozen_missing_tolerance_percent": frozen_tolerance,
            "selected_name": best_design["name"],
            "criterion": "lexicographic: miss, then pair-counted over-20 length, then total length",
        },
        "final_design": {
            "name": best_design["name"],
            "blocks": best_design["blocks"],
            "lines": all_lines,
            "line_count": len(all_lines),
        },
        "final_evaluations": {
            "bilinear_10m": final_bilinear_10,
            "bilinear_5m": final_bilinear_5,
            "tri_main_5m": final_tri_main_5,
            "tri_anti_5m": final_tri_anti_5,
        },
        "random_seed": "not applicable; deterministic candidate generation and evaluation",
    }
    JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    columns = [
        "final_order", "line_id", "block", "axis", "direction", "direction_deg_from_east_ccw",
        "start_x_m", "start_y_m", "end_x_m", "end_y_m", "length_inside_m",
        "representative_depth_m", "representative_slope_deg",
    ]
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_lines)

    fig, ax = plt.subplots(figsize=(10, 7))
    depth_image = ax.contourf(terrain.x / NMI, terrain.y / NMI, terrain.depth, levels=22, cmap="Blues")
    for line in all_lines:
        ax.plot([line["start_x_m"] / NMI, line["end_x_m"] / NMI], [line["start_y_m"] / NMI, line["end_y_m"] / NMI], color="#DC2626", lw=0.7)
    fig.colorbar(depth_image, ax=ax, label="Depth (m)")
    ax.set_xlabel("East-west coordinate (nmi)")
    ax.set_ylabel("South-north coordinate (nmi)")
    ax.set_title("Question 4 final survey-line layout")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "第4问最终测线布局-v001.png", dpi=220)
    plt.close(fig)

    names = [row["name"] for row in metrics]
    miss = [row["missing_percent"] for row in metrics]
    over = [row["over20_pair_counted_length_m"] / 1000.0 for row in metrics]
    length = [row["total_length_m"] / 1000.0 for row in metrics]
    positions = np.arange(len(names))
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    axes[0].bar(positions, miss, color="#2563EB")
    axes[0].set_ylabel("Miss (%)")
    axes[1].bar(positions, over, color="#DC2626")
    axes[1].set_ylabel("Over-20 length (km)")
    axes[2].bar(positions, length, color="#16A34A")
    axes[2].set_ylabel("Line length (km)")
    axes[2].set_xticks(positions, names, rotation=45, ha="right")
    fig.suptitle("Question 4 candidate metrics at 20 m screening resolution")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "第4问候选指标比较-v001.png", dpi=220)
    plt.close(fig)

    print(json.dumps({
        "selected": best_design["name"],
        "line_count": len(all_lines),
        "coarse_selected": best_metric,
        "final_bilinear_10m": {k: v for k, v in final_bilinear_10.items() if k != "pair_metrics"},
        "final_bilinear_5m": {k: v for k, v in final_bilinear_5.items() if k != "pair_metrics"},
        "final_tri_main_5m": {k: v for k, v in final_tri_main_5.items() if k != "pair_metrics"},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
