"""问题 1：二维斜坡覆盖解析模型与正式数值结果生成。"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_PATH = ROOT / "工作记录" / "诊断结果" / "Q01" / "q01_model_output_v001.json"

OPENING_DEG = 120.0
HALF_ANGLE_DEG = OPENING_DEG / 2.0
SLOPE_DEG = 1.5
CENTER_DEPTH_M = 70.0
POSITIONS_M = tuple(float(x) for x in range(-800, 801, 200))


@dataclass(frozen=True)
class CoverageRecord:
    index: int
    position_x_m: float
    slope_coordinate_q_m: float
    depth_m: float
    left_endpoint_q_m: float
    right_endpoint_q_m: float
    downhill_width_m: float
    uphill_width_m: float
    coverage_width_m: float
    signed_overlap_with_previous_m: float | None
    actual_overlap_with_previous_m: float | None
    gap_with_previous_m: float | None
    overlap_rate_previous_pct: float | None
    overlap_rate_current_pct: float | None
    overlap_rate_mean_pct: float | None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def interval_metrics(
    previous: tuple[float, float], current: tuple[float, float]
) -> tuple[float, float, float]:
    """返回有符号重叠、实际交长和漏测间隙，单位与端点相同。"""
    prev_left, prev_right = sorted(previous)
    curr_left, curr_right = sorted(current)
    signed = min(prev_right, curr_right) - max(prev_left, curr_left)
    actual = max(0.0, signed)
    gap = max(0.0, -signed)
    return signed, actual, gap


def analytic_coverage(
    position_x_m: float,
    *,
    slope_rad: float,
    half_angle_rad: float,
    center_depth_m: float,
) -> dict[str, float]:
    """由解析三角几何计算一个测线位置的坡面覆盖区间。"""
    depth_m = center_depth_m - position_x_m * math.tan(slope_rad)
    denom_downhill = math.cos(half_angle_rad + slope_rad)
    denom_uphill = math.cos(half_angle_rad - slope_rad)
    if depth_m <= 0.0:
        raise ValueError(f"水深必须为正，当前为 {depth_m!r} m")
    tolerance = 64.0 * math.ulp(1.0)
    if denom_downhill <= tolerance or denom_uphill <= tolerance:
        raise ValueError("边界射线与坡面平行、背向或过于接近退化位置")

    downhill_width_m = depth_m * math.sin(half_angle_rad) / denom_downhill
    uphill_width_m = depth_m * math.sin(half_angle_rad) / denom_uphill
    slope_coordinate_q_m = position_x_m / math.cos(slope_rad)
    left_endpoint_q_m = slope_coordinate_q_m - downhill_width_m
    right_endpoint_q_m = slope_coordinate_q_m + uphill_width_m
    coverage_width_m = right_endpoint_q_m - left_endpoint_q_m

    values = {
        "position_x_m": position_x_m,
        "slope_coordinate_q_m": slope_coordinate_q_m,
        "depth_m": depth_m,
        "left_endpoint_q_m": left_endpoint_q_m,
        "right_endpoint_q_m": right_endpoint_q_m,
        "downhill_width_m": downhill_width_m,
        "uphill_width_m": uphill_width_m,
        "coverage_width_m": coverage_width_m,
    }
    if not all(math.isfinite(value) for value in values.values()):
        raise ValueError("解析结果出现非有限数值")
    if not left_endpoint_q_m <= right_endpoint_q_m:
        raise ValueError("覆盖区间端点顺序异常")
    return values


def build_records(
    positions_m: Iterable[float] = POSITIONS_M,
    *,
    slope_deg: float = SLOPE_DEG,
    opening_deg: float = OPENING_DEG,
    center_depth_m: float = CENTER_DEPTH_M,
) -> list[CoverageRecord]:
    slope_rad = math.radians(slope_deg)
    half_angle_rad = math.radians(opening_deg / 2.0)
    records: list[CoverageRecord] = []

    for index, position_x_m in enumerate(positions_m):
        current = analytic_coverage(
            position_x_m,
            slope_rad=slope_rad,
            half_angle_rad=half_angle_rad,
            center_depth_m=center_depth_m,
        )
        signed = actual = gap = None
        rate_previous = rate_current = rate_mean = None
        if records:
            previous = records[-1]
            signed, actual, gap = interval_metrics(
                (previous.left_endpoint_q_m, previous.right_endpoint_q_m),
                (current["left_endpoint_q_m"], current["right_endpoint_q_m"]),
            )
            rate_previous = 100.0 * signed / previous.coverage_width_m
            rate_current = 100.0 * signed / current["coverage_width_m"]
            rate_mean = 200.0 * signed / (
                previous.coverage_width_m + current["coverage_width_m"]
            )

        records.append(
            CoverageRecord(
                index=index,
                **current,
                signed_overlap_with_previous_m=signed,
                actual_overlap_with_previous_m=actual,
                gap_with_previous_m=gap,
                overlap_rate_previous_pct=rate_previous,
                overlap_rate_current_pct=rate_current,
                overlap_rate_mean_pct=rate_mean,
            )
        )
    return records


def main() -> None:
    records = build_records()
    source = ROOT / "附件" / "附件01.xlsx"
    payload = {
        "schema_version": "q01-model-v001",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "coordinate_convention": {
            "x": "水平坐标，原点为海域中心，正向指向浅水/上坡",
            "z": "竖直坐标，向上为正，换能器位于 z=0",
            "q": "坡面弧长坐标，q=x/cos(alpha)，正向同 x",
            "previous": "表 1 顺序中当前测线左侧紧邻且先出现的测线",
        },
        "parameters": {
            "opening_deg": OPENING_DEG,
            "half_angle_deg": HALF_ANGLE_DEG,
            "slope_deg": SLOPE_DEG,
            "center_depth_m": CENTER_DEPTH_M,
            "positions_m": list(POSITIONS_M),
        },
        "definitions": {
            "reported_width": "坡面上两边界波束交点之间的实际长度",
            "signed_overlap": "min(R_prev,R_cur)-max(L_prev,L_cur)",
            "actual_overlap": "max(0,signed_overlap)",
            "gap": "max(0,-signed_overlap)",
            "formal_overlap_rate": "100*signed_overlap/W_prev",
            "alternative_current": "100*signed_overlap/W_cur",
            "alternative_mean": "200*signed_overlap/(W_prev+W_cur)",
        },
        "display_policy": {
            "depth_m_decimals": 2,
            "coverage_width_m_decimals": 2,
            "overlap_rate_pct_decimals": 2,
            "internal_calculation": "Python binary64, values retained before display rounding",
        },
        "source_template": {
            "path": "附件/附件01.xlsx",
            "sha256": sha256(source),
        },
        "randomness": "不涉及随机过程；随机种子不适用",
        "records": [asdict(record) for record in records],
        "formal_table": {
            "positions_m": [record.position_x_m for record in records],
            "depth_m": [round(record.depth_m, 2) for record in records],
            "coverage_width_m": [round(record.coverage_width_m, 2) for record in records],
            "overlap_rate_previous_pct": [
                None
                if record.overlap_rate_previous_pct is None
                else round(record.overlap_rate_previous_pct, 2)
                for record in records
            ],
        },
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload["formal_table"], ensure_ascii=False, indent=2))
    print(f"saved={OUTPUT_PATH}")


if __name__ == "__main__":
    main()
