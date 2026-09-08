from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "工作记录" / "诊断结果" / "Q02" / "q02_model_output_v001.json"
TEMPLATE = ROOT / "附件" / "附件02.xlsx"

THETA_DEG = 120.0
GAMMA_DEG = THETA_DEG / 2.0
ALPHA_DEG = 1.5
D0_M = 120.0
NMI_TO_M = 1852.0
BETAS_DEG = tuple(range(0, 360, 45))
DISTANCES_NMI = tuple(round(0.3 * i, 1) for i in range(8))


@dataclass(frozen=True)
class Coverage:
    beta_deg: float
    distance_nmi: float
    distance_m: float
    ship_x_m: float
    ship_y_m: float
    depth_m: float
    effective_slope: float
    effective_slope_deg: float
    negative_q_width_m: float
    positive_q_width_m: float
    coverage_width_m: float


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analytic_coverage(beta_deg: float, distance_nmi: float, alpha_deg: float = ALPHA_DEG) -> Coverage:
    beta = math.radians(beta_deg)
    gamma = math.radians(GAMMA_DEG)
    alpha = math.radians(alpha_deg)
    k = math.tan(alpha)
    distance_m = distance_nmi * NMI_TO_M
    # The horizontal projection of the upward seabed normal points downslope/west.
    # beta is measured counter-clockwise from that reference direction.
    ship_x = -distance_m * math.cos(beta)
    ship_y = -distance_m * math.sin(beta)
    depth = D0_M - k * ship_x
    m_eff = k * math.sin(beta)
    alpha_eff = math.atan(m_eff)
    denom_neg = math.cos(gamma + alpha_eff)
    denom_pos = math.cos(gamma - alpha_eff)
    if depth <= 0 or denom_neg <= 0 or denom_pos <= 0:
        raise ValueError("Input lies outside the finite forward-intersection domain")
    width_neg = depth * math.sin(gamma) / denom_neg
    width_pos = depth * math.sin(gamma) / denom_pos
    return Coverage(
        beta_deg=float(beta_deg),
        distance_nmi=float(distance_nmi),
        distance_m=distance_m,
        ship_x_m=ship_x,
        ship_y_m=ship_y,
        depth_m=depth,
        effective_slope=m_eff,
        effective_slope_deg=math.degrees(alpha_eff),
        negative_q_width_m=width_neg,
        positive_q_width_m=width_pos,
        coverage_width_m=width_neg + width_pos,
    )


def main() -> None:
    records = [analytic_coverage(beta, distance) for beta in BETAS_DEG for distance in DISTANCES_NMI]
    matrix = [
        [analytic_coverage(beta, distance).coverage_width_m for distance in DISTANCES_NMI]
        for beta in BETAS_DEG
    ]
    report = {
        "model": "Q2-A effective cross-track slope analytic model",
        "coordinate_convention": {
            "x": "east/up-slope, m",
            "y": "north, m",
            "z": "up, m",
            "seabed_plane": "z=-D0+x*tan(alpha)",
            "upward_normal_horizontal_projection": "west/down-slope (-x)",
            "beta_zero": "directed survey line points west/down-slope",
            "beta_positive": "counter-clockwise viewed from +z",
            "positive_distance": "from center along the directed survey line of that row",
        },
        "parameters": {
            "theta_deg": THETA_DEG,
            "gamma_deg": GAMMA_DEG,
            "alpha_deg": ALPHA_DEG,
            "center_depth_m": D0_M,
            "nmi_to_m": NMI_TO_M,
            "beta_deg": list(BETAS_DEG),
            "distance_nmi": list(DISTANCES_NMI),
        },
        "template": {
            "relative_path": "附件/附件02.xlsx",
            "sha256": sha256(TEMPLATE),
        },
        "records": [asdict(row) for row in records],
        "formal_table": {
            "rows_beta_deg": list(BETAS_DEG),
            "columns_distance_nmi": list(DISTANCES_NMI),
            "coverage_width_m_full_precision": matrix,
            "coverage_width_m_2dp": [[round(value, 2) for value in row] for row in matrix],
        },
        "summary": {
            "minimum_width_m": min(value for row in matrix for value in row),
            "maximum_width_m": max(value for row in matrix for value in row),
            "minimum_depth_m": min(row.depth_m for row in records),
            "maximum_depth_m": max(row.depth_m for row in records),
        },
        "random_seed": "not applicable; deterministic analytic calculation",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["formal_table"]["coverage_width_m_2dp"], ensure_ascii=False))


if __name__ == "__main__":
    main()
