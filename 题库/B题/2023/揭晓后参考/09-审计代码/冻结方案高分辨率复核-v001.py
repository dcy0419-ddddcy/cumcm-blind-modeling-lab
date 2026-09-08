from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np


REVIEW = Path(r"C:\Users\admin\OneDrive\Desktop\26国赛\题库\B题\2023\揭晓后参考")
BLIND = Path(r"C:\Users\admin\OneDrive\Desktop\26国赛-单题盲解区\B-M9R2")
Q04_CODE = BLIND / "工作记录" / "代码" / "Q04"
Q04_DIAG = BLIND / "工作记录" / "诊断结果" / "Q04"
DESIGN_PATH = Q04_DIAG / "q04_design_output_v001.json"
OUTPUT = REVIEW / "10-审计结果" / "冻结方案高分辨率复核-v001.json"

sys.path.insert(0, str(Q04_CODE))
from q04_terrain_v001 import NMI, Terrain  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sample_axis(lo: float, hi: float, step: float, offset_fraction: float, add_nodes: np.ndarray | None = None) -> np.ndarray:
    start = lo + offset_fraction * step
    values = np.arange(start, hi + 0.5 * step, step, dtype=float)
    values = values[(values >= lo) & (values <= hi)]
    extra = [lo, hi]
    if add_nodes is not None:
        extra.extend(float(value) for value in add_nodes if lo <= value <= hi)
    return np.unique(np.concatenate([values, np.asarray(extra, dtype=float)]))


def line_bounds(terrain: Terrain, line: dict, along: np.ndarray, representation: str) -> tuple[np.ndarray, np.ndarray]:
    left, right, _, _ = terrain.strip_bounds(line["axis"], line["center_m"], along, representation)
    return np.asarray(left, dtype=float), np.asarray(right, dtype=float)


def slice_union_audit(
    terrain: Terrain,
    block: dict,
    representation: str,
    step: float,
    offset_fraction: float,
) -> dict:
    line0 = block["lines"][0]
    along_nodes = terrain.y if line0["axis"] == "vertical" else terrain.x
    along = sample_axis(
        float(line0["along_min_m"]),
        float(line0["along_max_m"]),
        step,
        offset_fraction,
        along_nodes,
    )
    cross_min = float(line0["cross_min_m"])
    cross_max = float(line0["cross_max_m"])
    pairs = [line_bounds(terrain, line, along, representation) for line in block["lines"]]
    lefts = np.vstack([pair[0] for pair in pairs])
    rights = np.vstack([pair[1] for pair in pairs])
    order = np.argsort(lefts, axis=0)
    lefts = np.take_along_axis(lefts, order, axis=0)
    rights = np.take_along_axis(rights, order, axis=0)
    lefts = np.clip(lefts, cross_min, cross_max)
    rights = np.clip(rights, cross_min, cross_max)
    rights = np.maximum(rights, lefts)

    current_right = rights[0].copy()
    union = rights[0] - lefts[0]
    max_internal_gap = np.zeros_like(along)
    for index in range(1, lefts.shape[0]):
        gap = np.maximum(0.0, lefts[index] - current_right)
        max_internal_gap = np.maximum(max_internal_gap, gap)
        union += np.maximum(0.0, rights[index] - np.maximum(lefts[index], current_right))
        current_right = np.maximum(current_right, rights[index])

    missing_width = np.maximum(0.0, (cross_max - cross_min) - union)
    left_gap = np.maximum(0.0, lefts[0] - cross_min)
    right_gap = np.maximum(0.0, cross_max - current_right)
    trapezoid_missing_area = float(np.trapezoid(missing_width, along))
    worst = int(np.argmax(missing_width))
    return {
        "block": block["name"],
        "axis": line0["axis"],
        "representation": representation,
        "nominal_step_m": step,
        "offset_fraction": offset_fraction,
        "slice_count_including_endpoints_and_source_nodes": int(along.size),
        "max_missing_cross_width_m": float(np.max(missing_width)),
        "worst_along_coordinate_m": float(along[worst]),
        "slices_with_positive_missing_width": int(np.count_nonzero(missing_width > 1e-9)),
        "trapezoid_missing_area_m2": trapezoid_missing_area,
        "max_internal_gap_m": float(np.max(max_internal_gap)),
        "max_left_boundary_gap_m": float(np.max(left_gap)),
        "max_right_boundary_gap_m": float(np.max(right_gap)),
        "minimum_left_overreach_m": float(np.min(cross_min - np.min(np.vstack([pair[0] for pair in pairs]), axis=0))),
        "minimum_right_overreach_m": float(np.min(np.max(np.vstack([pair[1] for pair in pairs]), axis=0) - cross_max)),
        "continuous_claim": False,
        "interpretation": "Dense one-dimensional slices with exact interval unions on each slice; this is stronger than a cell-center raster but is not a formal continuous-domain certificate.",
    }


def overlap_statistics(terrain: Terrain, block: dict, representation: str, step: float) -> dict:
    line0 = block["lines"][0]
    along_nodes = terrain.y if line0["axis"] == "vertical" else terrain.x
    along = sample_axis(
        float(line0["along_min_m"]),
        float(line0["along_max_m"]),
        step,
        0.5,
        along_nodes,
    )
    bounds = [line_bounds(terrain, line, along, representation) for line in block["lines"]]
    pair_counted = 0.0
    masks_by_physical_line: dict[str, np.ndarray] = {}
    over_area_width = np.zeros_like(along)
    over_intervals_by_slice: list[list[tuple[float, float]]] = [[] for _ in range(along.size)]
    pair_rows = []
    cross_min = float(line0["cross_min_m"])
    cross_max = float(line0["cross_max_m"])

    for pair_index, (previous, current) in enumerate(zip(block["lines"], block["lines"][1:])):
        prev_left, prev_right = bounds[pair_index]
        cur_left, _ = bounds[pair_index + 1]
        width = prev_right - prev_left
        eta = np.divide(prev_right - cur_left, width, out=np.full_like(width, np.nan), where=width > 0)
        mask = eta > 0.20
        length = float(np.trapezoid(mask.astype(float), along))
        pair_counted += length
        existing = masks_by_physical_line.get(current["line_id"])
        masks_by_physical_line[current["line_id"]] = mask.copy() if existing is None else (existing | mask)
        for slice_index in np.flatnonzero(mask):
            lo = max(cross_min, float(cur_left[slice_index]))
            hi = min(cross_max, float(prev_right[slice_index]))
            if hi > lo:
                over_intervals_by_slice[int(slice_index)].append((lo, hi))
        pair_rows.append({
            "previous": previous["line_id"],
            "current": current["line_id"],
            "min_eta": float(np.nanmin(eta)),
            "max_eta": float(np.nanmax(eta)),
            "over20_length_m_trapezoid": length,
        })

    physical_deduplicated = float(sum(np.trapezoid(mask.astype(float), along) for mask in masks_by_physical_line.values()))
    for slice_index, intervals in enumerate(over_intervals_by_slice):
        if not intervals:
            continue
        intervals.sort()
        lo, hi = intervals[0]
        total = 0.0
        for next_lo, next_hi in intervals[1:]:
            if next_lo > hi:
                total += hi - lo
                lo, hi = next_lo, next_hi
            else:
                hi = max(hi, next_hi)
        over_area_width[slice_index] = total + hi - lo
    over_area = float(np.trapezoid(over_area_width, along))
    return {
        "block": block["name"],
        "representation": representation,
        "nominal_step_m": step,
        "slice_count": int(along.size),
        "pair_counted_over20_length_m": pair_counted,
        "physical_current_line_segments_deduplicated_m": physical_deduplicated,
        "area_where_an_adjacent_pair_exceeds_20_percent_m2": over_area,
        "pair_rows": pair_rows,
        "note": "The area metric is not a length and is not directly comparable with papers that report a line-length statistic.",
    }


def interface_band_audit(terrain: Terrain, design: dict, step_x: float = 5.0, step_y: float = 1.0, half_band_m: float = 120.0) -> dict:
    seam = float(design["blocks"][0]["rectangle"][3])
    xs = sample_axis(float(terrain.x[0]), float(terrain.x[-1]), step_x, 0.5, terrain.x)
    ys = sample_axis(seam - half_band_m, seam + half_band_m, step_y, 0.5, np.asarray([seam]))
    coverage_count = np.zeros((ys.size, xs.size), dtype=np.uint16)

    south = design["blocks"][0]
    for line in south["lines"]:
        valid_y = (ys >= float(line["along_min_m"])) & (ys <= float(line["along_max_m"]))
        if not np.any(valid_y):
            continue
        left, right = line_bounds(terrain, line, ys[valid_y], "bilinear")
        coverage_count[valid_y] += ((xs[None, :] >= left[:, None]) & (xs[None, :] <= right[:, None])).astype(np.uint16)

    north = design["blocks"][1]
    for line in north["lines"]:
        valid_x = (xs >= float(line["along_min_m"])) & (xs <= float(line["along_max_m"]))
        if not np.any(valid_x):
            continue
        left, right = line_bounds(terrain, line, xs[valid_x], "bilinear")
        addition = ((ys[:, None] >= left[None, :]) & (ys[:, None] <= right[None, :])).astype(np.uint16)
        coverage_count[:, valid_x] += addition

    cell_area = step_x * step_y
    seam_index = int(np.argmin(np.abs(ys - seam)))
    return {
        "seam_y_m": seam,
        "band_m": [float(ys[0]), float(ys[-1])],
        "sample_count": int(coverage_count.size),
        "missing_sample_count": int(np.count_nonzero(coverage_count == 0)),
        "minimum_coverage_multiplicity": int(np.min(coverage_count)),
        "maximum_coverage_multiplicity": int(np.max(coverage_count)),
        "estimated_repeated_coverage_area_m2": float(np.count_nonzero(coverage_count >= 2) * cell_area),
        "seam_row_missing_sample_count": int(np.count_nonzero(coverage_count[seam_index] == 0)),
        "seam_row_minimum_multiplicity": int(np.min(coverage_count[seam_index])),
        "model_scope": "Plan-view local cross-track footprints; south vertical-line footprints stop at their declared endpoints, while north horizontal-line footprints cross the interface physically. No along-track cone end-cap extension is modeled.",
    }


def point_coverage_count(terrain: Terrain, design: dict, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    counts = np.zeros(xs.shape, dtype=np.uint16)
    for block in design["blocks"]:
        for line in block["lines"]:
            if line["axis"] == "vertical":
                valid = (ys >= line["along_min_m"]) & (ys <= line["along_max_m"])
                if np.any(valid):
                    left, right = line_bounds(terrain, line, ys[valid], "bilinear")
                    counts[valid] += ((xs[valid] >= left) & (xs[valid] <= right)).astype(np.uint16)
            else:
                valid = (xs >= line["along_min_m"]) & (xs <= line["along_max_m"])
                if np.any(valid):
                    left, right = line_bounds(terrain, line, xs[valid], "bilinear")
                    counts[valid] += ((ys[valid] >= left) & (ys[valid] <= right)).astype(np.uint16)
    return counts


def high_slope_node_audit(terrain: Terrain, design: dict) -> dict:
    xx, yy = np.meshgrid(terrain.x, terrain.y)
    _, sx, sy = terrain.evaluate(xx, yy, "bilinear")
    slope = np.degrees(np.arctan(np.hypot(sx, sy)))
    threshold = float(np.percentile(slope, 95.0))
    mask = slope >= threshold
    counts = point_coverage_count(terrain, design, xx[mask], yy[mask])
    max_index = np.unravel_index(int(np.argmax(slope)), slope.shape)
    max_count = int(point_coverage_count(
        terrain,
        design,
        np.asarray([xx[max_index]], dtype=float),
        np.asarray([yy[max_index]], dtype=float),
    )[0])
    return {
        "node_count_at_or_above_95th_percentile": int(np.count_nonzero(mask)),
        "slope_95th_percentile_deg": threshold,
        "maximum_node_slope_deg": float(np.max(slope)),
        "uncovered_high_slope_node_count": int(np.count_nonzero(counts == 0)),
        "minimum_high_slope_node_coverage_multiplicity": int(np.min(counts)),
        "maximum_slope_node_xy_m": [float(xx[max_index]), float(yy[max_index])],
        "maximum_slope_node_coverage_multiplicity": max_count,
    }


def main() -> None:
    terrain = Terrain()
    payload = json.loads(DESIGN_PATH.read_text(encoding="utf-8"))
    design = payload["final_design"]
    resolution_cases = []
    for representation, step, offset in [
        ("bilinear", 2.5, 0.0),
        ("bilinear", 2.5, 0.5),
        ("bilinear", 1.0, 0.5),
        ("tri_main", 2.5, 0.5),
        ("tri_anti", 2.5, 0.5),
    ]:
        for block in design["blocks"]:
            resolution_cases.append(slice_union_audit(terrain, block, representation, step, offset))

    overlap_rows = [overlap_statistics(terrain, block, "bilinear", 1.0) for block in design["blocks"]]
    result = {
        "audit_scope": "Read-only reevaluation of the frozen Q4 line coordinates; no candidate generation, optimization, or write to the blind workspace.",
        "blind_design_path": str(DESIGN_PATH),
        "blind_design_sha256": sha256(DESIGN_PATH),
        "opening_angle_deg": 120.0,
        "opening_angle_status": "User-approved blind-phase assumption; not a Q4 statement fact.",
        "line_count": int(design["line_count"]),
        "line_count_by_block": {block["name"]: len(block["lines"]) for block in design["blocks"]},
        "total_inside_length_m_recomputed": float(sum(line["length_inside_m"] for block in design["blocks"] for line in block["lines"])),
        "resolution_and_offset_slice_union_cases": resolution_cases,
        "all_bilinear_dense_slices_without_detected_gap": bool(all(
            row["max_missing_cross_width_m"] <= 1e-9
            for row in resolution_cases
            if row["representation"] == "bilinear"
        )),
        "all_triangular_2_5m_dense_slices_without_detected_gap": bool(all(
            row["max_missing_cross_width_m"] <= 1e-9
            for row in resolution_cases
            if row["representation"].startswith("tri_")
        )),
        "interface_band": interface_band_audit(terrain, design),
        "high_slope_nodes": high_slope_node_audit(terrain, design),
        "over20_statistics": {
            "by_block": overlap_rows,
            "pair_counted_total_m": float(sum(row["pair_counted_over20_length_m"] for row in overlap_rows)),
            "physical_line_segment_deduplicated_total_m": float(sum(row["physical_current_line_segments_deduplicated_m"] for row in overlap_rows)),
            "adjacent_pair_over20_area_total_m2": float(sum(row["area_where_an_adjacent_pair_exceeds_20_percent_m2"] for row in overlap_rows)),
        },
        "claim_limit": "No sampled gap was found only if the reported checks pass. This does not prove strict zero missing area on the continuous seabed, because the footprint model is a local tangent approximation and the test remains finite-resolution.",
        "runtime": {
            "random_seed": "not applicable; deterministic evaluation",
            "numpy_version": np.__version__,
            "command": "python 冻结方案高分辨率复核-v001.py",
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT),
        "dense_bilinear_no_gap": result["all_bilinear_dense_slices_without_detected_gap"],
        "dense_triangular_no_gap": result["all_triangular_2_5m_dense_slices_without_detected_gap"],
        "interface_missing_samples": result["interface_band"]["missing_sample_count"],
        "over20_pair_counted_m": result["over20_statistics"]["pair_counted_total_m"],
        "over20_physical_deduplicated_m": result["over20_statistics"]["physical_line_segment_deduplicated_total_m"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
