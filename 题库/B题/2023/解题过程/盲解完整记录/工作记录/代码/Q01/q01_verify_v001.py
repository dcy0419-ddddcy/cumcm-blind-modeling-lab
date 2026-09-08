"""问题 1：独立射线—直线求交、边界例与结果验证。"""

from __future__ import annotations

import json
import math
import platform
import sys
from datetime import datetime
from pathlib import Path

from q01_model_v001 import (
    CENTER_DEPTH_M,
    HALF_ANGLE_DEG,
    OPENING_DEG,
    POSITIONS_M,
    SLOPE_DEG,
    build_records,
    interval_metrics,
)


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_PATH = (
    ROOT / "工作记录" / "诊断结果" / "Q01" / "q01_verification_v001.json"
)
ABS_TOL_LENGTH_M = 1.0e-10
ABS_TOL_PERCENT_POINT = 1.0e-10
REL_TOL = 1.0e-12


def ray_line_coverage(
    position_x_m: float,
    *,
    slope_deg: float,
    opening_deg: float,
    center_depth_m: float,
) -> dict[str, float]:
    """不调用解析宽度公式，直接以参数射线和海底直线求交。"""
    alpha = math.radians(slope_deg)
    beta = math.radians(opening_deg / 2.0)
    # 海底：n·(x,z)=c，其中 z=-D0+x tan(alpha)。
    normal = (-math.tan(alpha), 1.0)
    line_constant = -center_depth_m
    origin = (position_x_m, 0.0)

    def intersect(direction: tuple[float, float]) -> tuple[float, float, float]:
        denominator = normal[0] * direction[0] + normal[1] * direction[1]
        scale = math.hypot(*normal) * math.hypot(*direction)
        if abs(denominator) <= 64.0 * math.ulp(1.0) * scale:
            raise ValueError("独立求交发现射线与海底直线近似平行")
        numerator = line_constant - (
            normal[0] * origin[0] + normal[1] * origin[1]
        )
        parameter = numerator / denominator
        if parameter < 0.0:
            raise ValueError("独立求交发现交点位于射线反向")
        return (
            origin[0] + parameter * direction[0],
            origin[1] + parameter * direction[1],
            parameter,
        )

    left = intersect((-math.sin(beta), -math.cos(beta)))
    center = intersect((0.0, -1.0))
    right = intersect((math.sin(beta), -math.cos(beta)))
    q_left = left[0] / math.cos(alpha)
    q_center = position_x_m / math.cos(alpha)
    q_right = right[0] / math.cos(alpha)
    if not q_left <= q_right:
        raise ValueError("独立求交得到的覆盖端点次序异常")
    return {
        "position_x_m": position_x_m,
        "slope_coordinate_q_m": q_center,
        "depth_m": -center[1],
        "left_endpoint_q_m": q_left,
        "right_endpoint_q_m": q_right,
        "downhill_width_m": q_center - q_left,
        "uphill_width_m": q_right - q_center,
        "coverage_width_m": q_right - q_left,
        "left_ray_parameter_m": left[2],
        "center_ray_parameter_m": center[2],
        "right_ray_parameter_m": right[2],
    }


def relative_difference(a: float, b: float) -> float:
    scale = max(abs(a), abs(b))
    return 0.0 if scale == 0.0 else abs(a - b) / scale


def compare_target() -> dict[str, object]:
    analytic = build_records()
    vector = [
        ray_line_coverage(
            x,
            slope_deg=SLOPE_DEG,
            opening_deg=OPENING_DEG,
            center_depth_m=CENTER_DEPTH_M,
        )
        for x in POSITIONS_M
    ]
    vector_signed: list[float | None] = [None]
    vector_rate: list[float | None] = [None]
    for index in range(1, len(vector)):
        previous = vector[index - 1]
        current = vector[index]
        signed, _, _ = interval_metrics(
            (previous["left_endpoint_q_m"], previous["right_endpoint_q_m"]),
            (current["left_endpoint_q_m"], current["right_endpoint_q_m"]),
        )
        vector_signed.append(signed)
        vector_rate.append(100.0 * signed / previous["coverage_width_m"])

    fields = (
        "depth_m",
        "left_endpoint_q_m",
        "right_endpoint_q_m",
        "downhill_width_m",
        "uphill_width_m",
        "coverage_width_m",
    )
    per_field: dict[str, dict[str, float]] = {}
    for field in fields:
        pairs = [(getattr(a, field), v[field]) for a, v in zip(analytic, vector)]
        per_field[field] = {
            "max_absolute_difference": max(abs(a - b) for a, b in pairs),
            "max_relative_difference": max(relative_difference(a, b) for a, b in pairs),
        }

    signed_pairs = [
        (analytic[i].signed_overlap_with_previous_m, vector_signed[i])
        for i in range(1, len(analytic))
    ]
    rate_pairs = [
        (analytic[i].overlap_rate_previous_pct, vector_rate[i])
        for i in range(1, len(analytic))
    ]
    per_field["signed_overlap_with_previous_m"] = {
        "max_absolute_difference": max(abs(a - b) for a, b in signed_pairs),
        "max_relative_difference": max(relative_difference(a, b) for a, b in signed_pairs),
    }
    per_field["overlap_rate_previous_pct"] = {
        "max_absolute_difference": max(abs(a - b) for a, b in rate_pairs),
        "max_relative_difference": max(relative_difference(a, b) for a, b in rate_pairs),
    }
    max_abs_length = max(
        stats["max_absolute_difference"]
        for field, stats in per_field.items()
        if field != "overlap_rate_previous_pct"
    )
    max_abs_rate = per_field["overlap_rate_previous_pct"]["max_absolute_difference"]
    max_rel = max(stats["max_relative_difference"] for stats in per_field.values())
    passed = (
        max_abs_length <= ABS_TOL_LENGTH_M
        and max_abs_rate <= ABS_TOL_PERCENT_POINT
        and max_rel <= REL_TOL
    )
    return {
        "passed": passed,
        "tolerances": {
            "absolute_length_m": ABS_TOL_LENGTH_M,
            "absolute_percentage_point": ABS_TOL_PERCENT_POINT,
            "relative": REL_TOL,
        },
        "max_absolute_length_difference_m": max_abs_length,
        "max_absolute_overlap_rate_difference_percentage_point": max_abs_rate,
        "max_relative_difference": max_rel,
        "per_field": per_field,
    }


def flat_limit_test() -> dict[str, object]:
    opening_deg = 100.0
    beta = math.radians(opening_deg / 2.0)
    depth = 80.0
    spacing = 60.0
    records = build_records(
        (0.0, spacing),
        slope_deg=0.0,
        opening_deg=opening_deg,
        center_depth_m=depth,
    )
    expected_side = depth * math.tan(beta)
    expected_width = 2.0 * expected_side
    expected_rate = 100.0 * (1.0 - spacing / expected_width)
    errors = {
        "left_right_symmetry_m": abs(
            records[0].downhill_width_m - records[0].uphill_width_m
        ),
        "coverage_width_m": abs(records[0].coverage_width_m - expected_width),
        "overlap_rate_percentage_point": abs(
            records[1].overlap_rate_previous_pct - expected_rate
        ),
    }
    return {
        "passed": max(errors.values()) <= 1.0e-12,
        "generic_parameters": {
            "opening_deg": opening_deg,
            "depth_m": depth,
            "spacing_m": spacing,
        },
        "expected": {
            "side_width_m": expected_side,
            "coverage_width_m": expected_width,
            "overlap_rate_pct": expected_rate,
        },
        "absolute_errors": errors,
    }


def slope_flip_test() -> dict[str, object]:
    positive = build_records(POSITIONS_M, slope_deg=SLOPE_DEG)
    negative = build_records(POSITIONS_M, slope_deg=-SLOPE_DEG)
    reverse_negative = list(reversed(negative))
    depth_error = max(
        abs(p.depth_m - n.depth_m) for p, n in zip(positive, reverse_negative)
    )
    downhill_uphill_error = max(
        max(
            abs(p.downhill_width_m - n.uphill_width_m),
            abs(p.uphill_width_m - n.downhill_width_m),
        )
        for p, n in zip(positive, reverse_negative)
    )
    total_error = max(
        abs(p.coverage_width_m - n.coverage_width_m)
        for p, n in zip(positive, reverse_negative)
    )
    endpoint_mirror_error = max(
        max(
            abs(p.left_endpoint_q_m + n.right_endpoint_q_m),
            abs(p.right_endpoint_q_m + n.left_endpoint_q_m),
        )
        for p, n in zip(positive, reverse_negative)
    )
    return {
        "passed": max(
            depth_error,
            downhill_uphill_error,
            total_error,
            endpoint_mirror_error,
        )
        <= 1.0e-10,
        "max_depth_mirror_error_m": depth_error,
        "max_left_right_exchange_error_m": downhill_uphill_error,
        "max_total_width_mirror_error_m": total_error,
        "max_endpoint_mirror_error_m": endpoint_mirror_error,
    }


def interval_boundary_tests() -> dict[str, object]:
    cases = {
        "separated": ((0.0, 2.0), (3.0, 5.0), (-1.0, 0.0, 1.0)),
        "touching": ((0.0, 2.0), (2.0, 5.0), (0.0, 0.0, 0.0)),
        "partial_overlap": ((0.0, 3.0), (2.0, 5.0), (1.0, 1.0, 0.0)),
        "containment": ((0.0, 5.0), (1.0, 3.0), (2.0, 2.0, 0.0)),
        "unequal_width": ((-2.0, 3.0), (1.0, 5.0), (2.0, 2.0, 0.0)),
    }
    details = {}
    passed = True
    for name, (previous, current, expected) in cases.items():
        actual = interval_metrics(previous, current)
        case_passed = all(
            math.isclose(a, e, rel_tol=0.0, abs_tol=1.0e-12)
            for a, e in zip(actual, expected)
        )
        details[name] = {
            "passed": case_passed,
            "previous": previous,
            "current": current,
            "expected_signed_actual_gap": expected,
            "actual_signed_actual_gap": actual,
        }
        passed = passed and case_passed
    return {"passed": passed, "cases": details}


def applicability_and_trend_tests() -> dict[str, object]:
    records = build_records()
    ray_results = [
        ray_line_coverage(
            x,
            slope_deg=SLOPE_DEG,
            opening_deg=OPENING_DEG,
            center_depth_m=CENTER_DEPTH_M,
        )
        for x in POSITIONS_M
    ]
    finite = all(
        math.isfinite(value)
        for record in records
        for value in (
            record.depth_m,
            record.left_endpoint_q_m,
            record.right_endpoint_q_m,
            record.coverage_width_m,
        )
    )
    positive_depth = all(record.depth_m > 0.0 for record in records)
    ordered_intervals = all(
        record.left_endpoint_q_m <= record.right_endpoint_q_m for record in records
    )
    depth_decreases_uphill = all(
        records[i].depth_m > records[i + 1].depth_m
        for i in range(len(records) - 1)
    )
    width_decreases_uphill = all(
        records[i].coverage_width_m > records[i + 1].coverage_width_m
        for i in range(len(records) - 1)
    )
    downhill_wider = all(
        record.downhill_width_m > record.uphill_width_m for record in records
    )
    signed_geometry_consistent = all(
        (
            record.signed_overlap_with_previous_m >= 0.0
            and record.actual_overlap_with_previous_m
            == record.signed_overlap_with_previous_m
            and record.gap_with_previous_m == 0.0
        )
        or (
            record.signed_overlap_with_previous_m < 0.0
            and record.actual_overlap_with_previous_m == 0.0
            and record.gap_with_previous_m
            == -record.signed_overlap_with_previous_m
        )
        for record in records[1:]
    )
    alpha = math.radians(SLOPE_DEG)
    beta = math.radians(HALF_ANGLE_DEG)
    denominators = {
        "downhill_cos_beta_plus_alpha": math.cos(beta + alpha),
        "uphill_cos_beta_minus_alpha": math.cos(beta - alpha),
    }
    denominator_safe = min(denominators.values()) > 1.0e-8
    minimum_forward_parameter_m = min(
        result[field]
        for result in ray_results
        for field in (
            "left_ray_parameter_m",
            "center_ray_parameter_m",
            "right_ray_parameter_m",
        )
    )
    all_intersections_forward = minimum_forward_parameter_m >= 0.0
    passed = all(
        (
            finite,
            positive_depth,
            ordered_intervals,
            depth_decreases_uphill,
            width_decreases_uphill,
            downhill_wider,
            signed_geometry_consistent,
            denominator_safe,
            all_intersections_forward,
        )
    )
    return {
        "passed": passed,
        "finite": finite,
        "positive_depth": positive_depth,
        "ordered_intervals": ordered_intervals,
        "depth_decreases_toward_uphill": depth_decreases_uphill,
        "coverage_width_decreases_with_depth": width_decreases_uphill,
        "downhill_side_wider_than_uphill_side": downhill_wider,
        "signed_overlap_actual_overlap_gap_consistent": signed_geometry_consistent,
        "ray_line_denominators_safe": denominator_safe,
        "all_intersections_on_forward_rays": all_intersections_forward,
        "minimum_forward_ray_parameter_m": minimum_forward_parameter_m,
        "denominators": denominators,
        "unit_audit": {
            "input_lengths": "m",
            "internal_angles": "rad after one explicit degrees-to-radians conversion",
            "overlap_rate": "dimensionless; multiplied by 100 only at output interface",
            "nautical_miles_used": False,
        },
    }


def sensitivity_summary() -> dict[str, object]:
    records = build_records()
    rows = []
    for record in records[1:]:
        rows.append(
            {
                "position_x_m": record.position_x_m,
                "signed_overlap_m": record.signed_overlap_with_previous_m,
                "formal_previous_pct": record.overlap_rate_previous_pct,
                "alternative_current_pct": record.overlap_rate_current_pct,
                "alternative_mean_pct": record.overlap_rate_mean_pct,
                "current_minus_previous_percentage_point": (
                    record.overlap_rate_current_pct
                    - record.overlap_rate_previous_pct
                ),
                "leakage_classification_unchanged": (
                    (record.overlap_rate_previous_pct < 0.0)
                    == (record.overlap_rate_current_pct < 0.0)
                ),
            }
        )
    differences = [
        abs(row["current_minus_previous_percentage_point"]) for row in rows
    ]
    return {
        "formal_denominator": "previous strip width",
        "alternative_denominator": "current strip width",
        "rows": rows,
        "max_absolute_difference_percentage_point": max(differences),
        "geometry_unchanged": True,
        "leakage_classification_unchanged_all_rows": all(
            row["leakage_classification_unchanged"] for row in rows
        ),
    }


def main() -> None:
    checks = {
        "analytic_vs_independent_ray_line": compare_target(),
        "flat_limit": flat_limit_test(),
        "slope_flip": slope_flip_test(),
        "interval_boundaries": interval_boundary_tests(),
        "applicability_units_and_trends": applicability_and_trend_tests(),
    }
    all_passed = all(check["passed"] for check in checks.values())
    payload = {
        "schema_version": "q01-verification-v001",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "dependencies": ["Python standard library"],
            "randomness": "不涉及随机过程；随机种子不适用",
        },
        "checks": checks,
        "sensitivity": sensitivity_summary(),
        "all_passed": all_passed,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not all_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
