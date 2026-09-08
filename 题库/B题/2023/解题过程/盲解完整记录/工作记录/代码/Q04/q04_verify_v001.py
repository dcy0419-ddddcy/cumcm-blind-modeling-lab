from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from q04_terrain_v001 import GAMMA, NMI, OUT_DIR, ROOT, Terrain


DESIGN_JSON = OUT_DIR / "q04_design_output_v001.json"
VERIFY_JSON = OUT_DIR / "q04_verification_v001.json"
COVERAGE_PLOT = OUT_DIR / "第4问覆盖与漏测图-v001.png"
OVERLAP_PLOT = OUT_DIR / "第4问过度重叠位置-v001.png"


def cell_centers(lo: float, hi: float, nominal_step: float) -> tuple[np.ndarray, float]:
    count = max(1, int(math.ceil((hi - lo) / nominal_step)))
    step = (hi - lo) / count
    return lo + (np.arange(count) + 0.5) * step, step


def local_bounds(terrain: Terrain, line: dict, along: np.ndarray, representation: str) -> tuple[np.ndarray, np.ndarray]:
    """Independent implementation of the plan-view ray/plane footprint."""
    center = line["center_m"]
    if line["axis"] == "vertical":
        depth, elevation_x, _ = terrain.evaluate(np.full_like(along, center), along, representation)
        cross_slope = elevation_x
    elif line["axis"] == "horizontal":
        depth, _, elevation_y = terrain.evaluate(along, np.full_like(along, center), representation)
        cross_slope = elevation_y
    else:
        raise ValueError(line["axis"])
    sine = math.sin(GAMMA)
    cosine = math.cos(GAMMA)
    left = center - depth * sine / (cosine - cross_slope * sine)
    right = center + depth * sine / (cosine + cross_slope * sine)
    return left, right


def raster_block(terrain: Terrain, block: dict, representation: str, nominal_step: float) -> dict:
    line0 = block["lines"][0]
    cross, dc = cell_centers(line0["cross_min_m"], line0["cross_max_m"], nominal_step)
    along, da = cell_centers(line0["along_min_m"], line0["along_max_m"], nominal_step)
    covered = np.zeros((along.size, cross.size), dtype=bool)
    for line in block["lines"]:
        left, right = local_bounds(terrain, line, along, representation)
        covered |= (cross[None, :] >= left[:, None]) & (cross[None, :] <= right[:, None])
    missing_cells = int(np.size(covered) - int(np.count_nonzero(covered)))
    return {
        "covered": covered,
        "cross": cross,
        "along": along,
        "dc": dc,
        "da": da,
        "missing_cells": missing_cells,
        "missing_area_m2": missing_cells * dc * da,
        "missing_percent": 100.0 * missing_cells / covered.size,
    }


def independent_over20(terrain: Terrain, block: dict, representation: str, nominal_step: float) -> tuple[float, list[dict]]:
    line0 = block["lines"][0]
    along, da = cell_centers(line0["along_min_m"], line0["along_max_m"], nominal_step)
    bounds = [local_bounds(terrain, line, along, representation) for line in block["lines"]]
    total = 0.0
    rows: list[dict] = []
    for previous, current, (prev_left, prev_right), (cur_left, _) in zip(
        block["lines"], block["lines"][1:], bounds, bounds[1:]
    ):
        width = prev_right - prev_left
        eta = np.divide(prev_right - cur_left, width, out=np.full_like(width, np.nan), where=width > 0)
        mask = eta > 0.20
        length = float(np.count_nonzero(mask) * da)
        total += length
        rows.append({
            "previous": previous["line_id"],
            "current": current["line_id"],
            "min_eta": float(np.nanmin(eta)),
            "max_eta": float(np.nanmax(eta)),
            "over20_length_m": length,
            "along": along,
            "mask": mask,
            "line": current,
        })
    return total, rows


def direct_ray_offsets(depth: float, slope: float) -> tuple[float, float]:
    sine = math.sin(GAMMA)
    cosine = math.cos(GAMMA)
    left_parameter = depth / (cosine - slope * sine)
    right_parameter = depth / (cosine + slope * sine)
    return left_parameter * sine, right_parameter * sine


def artificial_geometry_tests() -> dict:
    rng = np.random.default_rng(20230910)
    maximum_ray_error = 0.0
    maximum_plane_error = 0.0
    for depth, slope in zip(rng.uniform(10.0, 220.0, 100), rng.uniform(-0.06, 0.06, 100)):
        left_ray, right_ray = direct_ray_offsets(float(depth), float(slope))
        sine = math.sin(GAMMA)
        cosine = math.cos(GAMMA)
        left_formula = depth * sine / (cosine - slope * sine)
        right_formula = depth * sine / (cosine + slope * sine)
        maximum_ray_error = max(maximum_ray_error, abs(left_ray - left_formula), abs(right_ray - right_formula))

        alpha = math.atan(float(slope))
        seabed_width = (left_formula + right_formula) * math.sqrt(1.0 + slope * slope)
        q2_width = depth * sine * (
            1.0 / math.cos(GAMMA + alpha) + 1.0 / math.cos(GAMMA - alpha)
        )
        maximum_plane_error = max(maximum_plane_error, abs(seabed_width - q2_width))

    depth = 110.0
    flat_width = sum(direct_ray_offsets(depth, 0.0))
    flat_expected = 2.0 * depth * math.tan(GAMMA)
    return {
        "random_seed": 20230910,
        "ray_plane_max_abs_error_m": maximum_ray_error,
        "q2_seabed_width_degeneracy_max_abs_error_m": maximum_plane_error,
        "flat_width_m": flat_width,
        "flat_expected_m": flat_expected,
        "flat_abs_error_m": abs(flat_width - flat_expected),
    }


def make_coverage_plot(terrain: Terrain, design: dict) -> None:
    south = raster_block(terrain, design["blocks"][0], "bilinear", 20.0)
    north = raster_block(terrain, design["blocks"][1], "bilinear", 20.0)
    south_map = south["covered"]
    north_map = north["covered"].T
    coverage = np.vstack([south_map, north_map])
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.imshow(
        coverage.astype(int), origin="lower", extent=[0, 4, 0, 5], aspect="auto",
        cmap="RdYlGn", vmin=0, vmax=1, interpolation="nearest",
    )
    ax.axhline(2.5, color="white", linewidth=1.2, linestyle="--", label="Block interface")
    ax.set_xlabel("East-west coordinate (nmi)")
    ax.set_ylabel("South-north coordinate (nmi)")
    ax.set_title("Question 4 independent 20 m coverage raster (green = covered)")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(COVERAGE_PLOT, dpi=220)
    plt.close(fig)


def make_overlap_plot(terrain: Terrain, design: dict) -> None:
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.set_xlim(0, 4)
    ax.set_ylim(0, 5)
    ax.axhline(2.5, color="0.7", linewidth=1.0, linestyle="--")
    for block in design["blocks"]:
        for line in block["lines"]:
            ax.plot(
                [line["start_x_m"] / NMI, line["end_x_m"] / NMI],
                [line["start_y_m"] / NMI, line["end_y_m"] / NMI],
                color="#9ecae1", linewidth=0.45, alpha=0.65,
            )
        _, rows = independent_over20(terrain, block, "bilinear", 10.0)
        for row in rows:
            line = row["line"]
            along = row["along"][row["mask"]]
            if line["axis"] == "vertical":
                ax.scatter(np.full_like(along, line["center_m"]) / NMI, along / NMI, s=2.5, c="#d7301f")
            else:
                ax.scatter(along / NMI, np.full_like(along, line["center_m"]) / NMI, s=2.5, c="#d7301f")
    ax.set_xlabel("East-west coordinate (nmi)")
    ax.set_ylabel("South-north coordinate (nmi)")
    ax.set_title("Question 4 locations where adjacent-line overlap exceeds 20%")
    ax.scatter([], [], s=12, c="#d7301f", label="Overlap > 20%")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(OVERLAP_PLOT, dpi=220)
    plt.close(fig)


def main() -> None:
    terrain = Terrain()
    payload = json.loads(DESIGN_JSON.read_text(encoding="utf-8"))
    design = payload["final_design"]
    source = json.loads((OUT_DIR / "q04_source_grid_v001.json").read_text(encoding="utf-8"))

    checks: dict[str, dict] = {}
    node_x, node_y = np.meshgrid(terrain.x, terrain.y)
    node_depth, _, _ = terrain.evaluate(node_x, node_y, "bilinear")
    node_error = float(np.max(np.abs(node_depth - terrain.depth)))
    checks["node_reconstruction"] = {"passed": node_error < 1e-10, "max_abs_error_m": node_error}
    checks["coordinate_units"] = {
        "passed": terrain.x[0] == 0 and terrain.x[-1] == 4 * NMI and terrain.y[0] == 0 and terrain.y[-1] == 5 * NMI,
        "x_range_m": [float(terrain.x[0]), float(terrain.x[-1])],
        "y_range_m": [float(terrain.y[0]), float(terrain.y[-1])],
        "grid_spacing_m": [terrain.dx, terrain.dy],
    }
    checks["source_finite_and_positive"] = {
        "passed": bool(np.all(np.isfinite(terrain.depth)) and np.all(terrain.depth > 0)),
        "nan_count": int(np.count_nonzero(~np.isfinite(terrain.depth))),
        "nonpositive_count": int(np.count_nonzero(terrain.depth <= 0)),
    }

    geometry = artificial_geometry_tests()
    checks["artificial_flat_plane_and_q2_degeneracy"] = {
        "passed": geometry["ray_plane_max_abs_error_m"] < 1e-10
        and geometry["q2_seabed_width_degeneracy_max_abs_error_m"] < 1e-10
        and geometry["flat_abs_error_m"] < 1e-10,
        **geometry,
    }

    line_ids = [line["line_id"] for block in design["blocks"] for line in block["lines"]]
    lines = [line for block in design["blocks"] for line in block["lines"]]
    ordered = all(
        all(block["lines"][i]["center_m"] < block["lines"][i + 1]["center_m"] for i in range(len(block["lines"]) - 1))
        for block in design["blocks"]
    )
    bounds_valid = all(
        line["cross_min_m"] <= line["center_m"] <= line["cross_max_m"]
        and line["along_min_m"] < line["along_max_m"]
        and line["length_inside_m"] > 0
        for line in lines
    )
    checks["line_identity_order_and_clipping"] = {
        "passed": len(line_ids) == len(set(line_ids)) == design["line_count"] and ordered and bounds_valid,
        "line_count": len(line_ids),
        "unique_line_count": len(set(line_ids)),
        "ordered_by_cross_coordinate": ordered,
        "bounds_valid": bounds_valid,
    }

    raster_results = {}
    for representation, step in [("bilinear", 10.0), ("bilinear", 5.0), ("tri_main", 10.0), ("tri_anti", 10.0)]:
        block_rows = [raster_block(terrain, block, representation, step) for block in design["blocks"]]
        missing_area = sum(row["missing_area_m2"] for row in block_rows)
        total_area = 4 * NMI * 5 * NMI
        key = f"{representation}_{int(step)}m"
        raster_results[key] = {
            "missing_area_m2": missing_area,
            "missing_percent": 100.0 * missing_area / total_area,
            "missing_cells": sum(row["missing_cells"] for row in block_rows),
            "cell_area_by_block_m2": [row["dc"] * row["da"] for row in block_rows],
        }
    checks["independent_raster_coverage"] = {
        "passed": raster_results["bilinear_10m"]["missing_cells"] == 0
        and raster_results["bilinear_5m"]["missing_cells"] == 0,
        "results": raster_results,
    }

    independent_overlap = {}
    for representation, step in [("bilinear", 10.0), ("bilinear", 5.0), ("tri_main", 5.0), ("tri_anti", 5.0)]:
        total = sum(independent_over20(terrain, block, representation, step)[0] for block in design["blocks"])
        key = f"{representation}_{int(step)}m"
        reference = payload["final_evaluations"].get(key, {}).get("over20_pair_counted_length_m")
        independent_overlap[key] = {
            "pair_counted_length_m": total,
            "reference_length_m": reference,
            "absolute_difference_m": None if reference is None else abs(total - reference),
        }
    checks["independent_over20_counting"] = {
        "passed": all(
            row["reference_length_m"] is None or row["absolute_difference_m"] < 1e-6
            for row in independent_overlap.values()
        ),
        "results": independent_overlap,
        "definition": "Each ordered adjacent pair is counted only over its shared assigned block; pair lengths are additive.",
    }

    length_sum = sum(line["length_inside_m"] for line in lines)
    checks["total_length_recalculation"] = {
        "passed": abs(length_sum - payload["final_evaluations"]["bilinear_5m"]["total_length_m"]) < 1e-9,
        "recalculated_total_m": length_sum,
        "reported_total_m": payload["final_evaluations"]["bilinear_5m"]["total_length_m"],
    }

    coarse = {row["name"]: row for row in payload["candidate_metrics_coarse"]}
    baseline = coarse["uniform-vertical-baseline"]
    selected = coarse[payload["selection"]["selected_name"]]
    checks["selected_vs_baseline"] = {
        "passed": selected["missing_percent"] <= 1e-8
        and selected["over20_pair_counted_length_m"] < baseline["over20_pair_counted_length_m"]
        and selected["total_length_m"] < baseline["total_length_m"] * 1.10,
        "baseline": baseline,
        "selected": selected,
    }

    tri_anti_miss = payload["final_evaluations"]["tri_anti_5m"]["missing_percent"]
    checks["representation_and_resolution_sensitivity"] = {
        "passed": tri_anti_miss < 1e-6
        and raster_results["bilinear_5m"]["missing_cells"] == 0
        and raster_results["bilinear_10m"]["missing_cells"] == 0,
        "reported_final_evaluations": payload["final_evaluations"],
        "independent_raster_results": raster_results,
    }

    expected_rows = len(source["y_nmi"])
    expected_cols = len(source["x_nmi"])
    checks["source_shape_and_boundary"] = {
        "passed": terrain.depth.shape == (expected_rows, expected_cols)
        and abs(terrain.dx - NMI * 0.02) < 1e-9
        and abs(terrain.dy - NMI * 0.02) < 1e-9,
        "shape": list(terrain.depth.shape),
        "expected_shape": [expected_rows, expected_cols],
    }

    make_coverage_plot(terrain, design)
    make_overlap_plot(terrain, design)
    required_plots = [
        OUT_DIR / "第4问地形图-v001.png",
        OUT_DIR / "第4问坡度坡向图-v001.png",
        OUT_DIR / "第4问最终测线布局-v001.png",
        OUT_DIR / "第4问候选指标比较-v001.png",
        COVERAGE_PLOT,
        OVERLAP_PLOT,
    ]
    checks["evidence_files"] = {
        "passed": all(path.exists() and path.stat().st_size > 0 for path in required_plots),
        "files": [{"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size if path.exists() else 0} for path in required_plots],
    }

    for row in checks.values():
        row["passed"] = bool(row["passed"])
    result = {
        "source_sha256": terrain.source_hash,
        "design_file": str(DESIGN_JSON.relative_to(ROOT)),
        "verification_scope": "Independent formulas and raster checks; no candidate regeneration or optimization.",
        "checks": checks,
        "all_passed": bool(all(row["passed"] for row in checks.values())),
    }
    VERIFY_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"all_passed": result["all_passed"], "checks": {k: v["passed"] for k, v in checks.items()}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
