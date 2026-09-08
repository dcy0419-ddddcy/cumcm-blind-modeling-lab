from __future__ import annotations

import json
import math
from q02_model_v001 import (
    ALPHA_DEG,
    BETAS_DEG,
    D0_M,
    DISTANCES_NMI,
    GAMMA_DEG,
    NMI_TO_M,
    ROOT,
    analytic_coverage,
)


OUT = ROOT / "工作记录" / "诊断结果" / "Q02" / "q02_verification_v001.json"


def dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))

def add(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(x + y for x, y in zip(a, b, strict=True))  # type: ignore[return-value]


def scale(s: float, a: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(s * x for x in a)  # type: ignore[return-value]


def norm(a: tuple[float, float, float]) -> float:
    return math.sqrt(dot(a, a))


def independent_ray_plane(beta_deg: float, distance_nmi: float, alpha_deg: float = ALPHA_DEG) -> dict[str, float]:
    beta = math.radians(beta_deg)
    gamma = math.radians(GAMMA_DEG)
    k = math.tan(math.radians(alpha_deg))
    distance_m = distance_nmi * NMI_TO_M
    u = (-math.cos(beta), -math.sin(beta), 0.0)
    q = (-u[1], u[0], 0.0)
    origin = scale(distance_m, u)
    normal = (-k, 0.0, 1.0)
    plane_point = (0.0, 0.0, -D0_M)
    directions = (
        add(scale(-math.sin(gamma), q), (0.0, 0.0, -math.cos(gamma))),
        add(scale(math.sin(gamma), q), (0.0, 0.0, -math.cos(gamma))),
    )
    parameters = []
    points = []
    for direction in directions:
        denominator = dot(normal, direction)
        numerator = dot(normal, tuple(p - o for p, o in zip(plane_point, origin, strict=True)))
        if abs(denominator) < 1e-14:
            raise ValueError("Parallel ray-plane configuration")
        parameter = numerator / denominator
        if parameter < 0:
            raise ValueError("Backward ray-plane intersection")
        parameters.append(parameter)
        points.append(add(origin, scale(parameter, direction)))
    delta = tuple(b - a for a, b in zip(points[0], points[1], strict=True))
    center_parameter = dot(normal, tuple(p - o for p, o in zip(plane_point, origin, strict=True))) / dot(
        normal, (0.0, 0.0, -1.0)
    )
    return {
        "coverage_width_m": norm(delta),
        "depth_m": center_parameter,
        "ray_parameter_min": min(parameters),
        "ray_parameter_max": max(parameters),
        "denominator_abs_min": min(abs(dot(normal, direction)) for direction in directions),
    }


def close(a: float, b: float, atol: float = 1e-10, rtol: float = 1e-12) -> bool:
    return abs(a - b) <= atol + rtol * max(abs(a), abs(b))


def main() -> None:
    comparisons = []
    absolute_errors = []
    relative_errors = []
    all_positive_finite = True
    all_forward = True
    for beta in BETAS_DEG:
        for distance in DISTANCES_NMI:
            analytic = analytic_coverage(beta, distance)
            independent = independent_ray_plane(beta, distance)
            error = abs(analytic.coverage_width_m - independent["coverage_width_m"])
            relative = error / analytic.coverage_width_m
            absolute_errors.append(error)
            relative_errors.append(relative)
            all_positive_finite &= math.isfinite(analytic.coverage_width_m) and analytic.coverage_width_m > 0
            all_forward &= independent["ray_parameter_min"] >= 0 and independent["denominator_abs_min"] > 1e-8
            comparisons.append(
                {
                    "beta_deg": beta,
                    "distance_nmi": distance,
                    "analytic_width_m": analytic.coverage_width_m,
                    "independent_width_m": independent["coverage_width_m"],
                    "absolute_error_m": error,
                    "relative_error": relative,
                }
            )

    center_groups = {
        str(beta): analytic_coverage(beta, 0.0).coverage_width_m for beta in BETAS_DEG
    }
    center_symmetry = all(
        close(center_groups[str(beta)], center_groups[str((beta + 180) % 360)]) for beta in BETAS_DEG
    ) and close(center_groups["45"], center_groups["135"]) and close(center_groups["225"], center_groups["315"])

    opposite_relations = []
    opposite_ok = True
    for beta in BETAS_DEG[:4]:
        for distance in DISTANCES_NMI:
            a = analytic_coverage(beta, distance)
            b = analytic_coverage(beta + 180, distance)
            expected_depth_sum = 2 * D0_M
            row_ok = close(a.ship_x_m, -b.ship_x_m) and close(a.ship_y_m, -b.ship_y_m) and close(
                a.depth_m + b.depth_m, expected_depth_sum
            ) and close(abs(a.effective_slope), abs(b.effective_slope)) and close(
                a.coverage_width_m / a.depth_m, b.coverage_width_m / b.depth_m
            )
            opposite_ok &= row_ok
            opposite_relations.append(
                {
                    "beta_deg": beta,
                    "distance_nmi": distance,
                    "position_opposite": close(a.ship_x_m, -b.ship_x_m) and close(a.ship_y_m, -b.ship_y_m),
                    "depth_sum_m": a.depth_m + b.depth_m,
                    "width_per_depth_equal": close(
                        a.coverage_width_m / a.depth_m, b.coverage_width_m / b.depth_m
                    ),
                    "passed": row_ok,
                }
            )

    flat_checks = []
    flat_ok = True
    flat_expected = 2 * D0_M * math.tan(math.radians(GAMMA_DEG))
    for beta in BETAS_DEG:
        got = analytic_coverage(beta, 0.0, alpha_deg=0.0).coverage_width_m
        ok = close(got, flat_expected)
        flat_ok &= ok
        flat_checks.append({"beta_deg": beta, "got_m": got, "expected_m": flat_expected, "passed": ok})

    cardinal = {
        "beta_0_depth_increases_with_distance": analytic_coverage(0, 2.1).depth_m > D0_M,
        "beta_180_depth_decreases_with_distance": analytic_coverage(180, 2.1).depth_m < D0_M,
        "beta_90_depth_constant": close(analytic_coverage(90, 2.1).depth_m, D0_M),
        "beta_270_depth_constant": close(analytic_coverage(270, 2.1).depth_m, D0_M),
        "beta_90_270_width_equal": close(
            analytic_coverage(90, 2.1).coverage_width_m, analytic_coverage(270, 2.1).coverage_width_m
        ),
        "four_diagonal_center_widths_equal": len(
            {
                round(analytic_coverage(beta, 0).coverage_width_m, 10)
                for beta in (45, 135, 225, 315)
            }
        )
        == 1,
    }

    report = {
        "model_comparison": {
            "count": len(comparisons),
            "maximum_absolute_error_m": max(absolute_errors),
            "maximum_relative_error": max(relative_errors),
            "all_within_tolerance": all(item["absolute_error_m"] <= 1e-9 for item in comparisons),
            "records": comparisons,
        },
        "checks": {
            "distance_zero_direction_symmetry": {"passed": center_symmetry, "values_m": center_groups},
            "beta_plus_180_relation": {"passed": opposite_ok, "records": opposite_relations},
            "special_directions": {"passed": all(cardinal.values()), "details": cardinal},
            "flat_limit": {"passed": flat_ok, "records": flat_checks},
            "single_nmi_conversion": {"passed": close(2.1 * NMI_TO_M, 3889.2), "value_m": 2.1 * NMI_TO_M},
            "angle_conversion": {
                "passed": close(math.degrees(math.radians(GAMMA_DEG)), GAMMA_DEG)
                and close(math.degrees(math.radians(ALPHA_DEG)), ALPHA_DEG)
            },
            "applicability": {"passed": all_positive_finite and all_forward},
            "all_64_positive_finite": {"passed": all_positive_finite},
        },
        "overall_passed": False,
        "tolerances": {"absolute_m": 1e-10, "relative": 1e-12},
        "random_seed": "not applicable; deterministic verification",
    }
    report["overall_passed"] = report["model_comparison"]["all_within_tolerance"] and all(
        item["passed"] for item in report["checks"].values()
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"overall_passed": report["overall_passed"], "max_abs_m": max(absolute_errors)}, indent=2))


if __name__ == "__main__":
    main()
