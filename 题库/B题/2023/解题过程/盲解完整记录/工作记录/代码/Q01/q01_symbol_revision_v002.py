from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PAPER_V1 = ROOT / "工作记录" / "论文" / "第1问-模型建立与求解-v001.md"
PAPER_V2 = ROOT / "工作记录" / "论文" / "第1问-模型建立与求解-v002.md"
MAP_V1 = ROOT / "工作记录" / "论文" / "第1问-正文证据映射-v001.md"
MAP_V2 = ROOT / "工作记录" / "论文" / "第1问-正文证据映射-v002.md"
CHECK_JSON = ROOT / "工作记录" / "诊断结果" / "Q01" / "q01_symbol_equivalence_v002.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def model(angle_name: str) -> list[dict[str, float]]:
    theta_deg = 120.0
    alpha_deg = 1.5
    d0 = 70.0
    angle_deg = theta_deg / 2.0
    alpha = math.radians(alpha_deg)
    half_angle = math.radians(angle_deg)
    rows: list[dict[str, float]] = []
    for x in range(-800, 801, 200):
        depth = d0 - x * math.tan(alpha)
        a = depth * math.sin(half_angle) / math.cos(half_angle + alpha)
        b = depth * math.sin(half_angle) / math.cos(half_angle - alpha)
        q = x / math.cos(alpha)
        rows.append(
            {
                "x_m": float(x),
                "depth_m": depth,
                "down_slope_width_m": a,
                "up_slope_width_m": b,
                "left_q_m": q - a,
                "right_q_m": q + b,
                "coverage_width_m": a + b,
                "angle_symbol": angle_name,
            }
        )
    for i, row in enumerate(rows):
        if i == 0:
            row["signed_overlap_m"] = math.nan
            row["overlap_rate"] = math.nan
        else:
            previous = rows[i - 1]
            signed = min(previous["right_q_m"], row["right_q_m"]) - max(
                previous["left_q_m"], row["left_q_m"]
            )
            row["signed_overlap_m"] = signed
            row["overlap_rate"] = signed / previous["coverage_width_m"]
    return rows


def main() -> None:
    paper_v1 = PAPER_V1.read_text(encoding="utf-8")
    beta_count = paper_v1.count(r"\beta")
    eta_plain_count = paper_v1.count("$eta_i$")
    if beta_count != 21 or eta_plain_count != 1:
        raise RuntimeError(
            f"Unexpected source markers: beta={beta_count}, eta_plain={eta_plain_count}"
        )
    paper_v2 = paper_v1.replace(r"\beta", r"\gamma").replace("$eta_i$", r"$\eta_i$")
    PAPER_V2.write_text(paper_v2, encoding="utf-8")

    mapping = MAP_V1.read_text(encoding="utf-8")
    mapping = mapping.replace("# 第 1 问正文证据映射 v001", "# 第 1 问正文证据映射 v002", 1)
    mapping = mapping.replace(
        "`第1问-模型建立与求解-v001.md` 中的公式",
        "`第1问-模型建立与求解-v002.md` 中的公式",
        1,
    )
    mapping = mapping.replace("$eta_i=S_i/W_{i-1}$", r"$\eta_i=S_i/W_{i-1}$")
    mapping = mapping.replace(r"$eta_i^{\mathrm{cur}}=S_i/W_i$", r"$\eta_i^{\mathrm{cur}}=S_i/W_i$")
    mapping += r"""

## 9. v002 符号一致性修订

- 修改原因：第 2 问题面以 $\beta$ 表示测线方向角；为避免完整论文出现同符异义，第 1 问半开角改记为 $\gamma=\theta/2$。
- 修改位置：第 1 问正文第 2、3、4、6、11 节，涉及模型假设、符号表、边界射线、交点参数、两侧分宽、总宽与平坦极限。
- 修改前：半开角记为 $\beta=\theta/2$，符号表的正式重叠率写作普通文本 `$eta_i$`。
- 修改后：半开角统一记为 $\gamma=\theta/2$，并把正式重叠率统一写为 $\eta_i$；从第 2 问起，$\beta$ 专用于题面规定的测线方向角。
- 影响范围：只改变数学记号和排版，不改变坐标、物理量、定义域、推导结构、输入、算法、表 1、代码、JSON、Excel 或任何正式数值。
- 验证结果：`q01_symbol_equivalence_v002.json` 分别以旧变量名和新变量名对 9 个位置计算水深、两侧分宽、端点、总宽、有符号重叠和正式重叠率，全部有限项的最大绝对差为 0；v002 正文将 $\gamma$ 规范化回 $\beta$ 并将 $\eta_i$ 恢复为旧排版后，与 v001 逐字符一致。
- 代关系：本文件与 `第1问-模型建立与求解-v002.md` 为当前有效论文版本；v001 保留为已验收的历史版本，未删除、未覆盖。
"""
    MAP_V2.write_text(mapping, encoding="utf-8")

    old = model("beta")
    new = model("gamma")
    fields = [
        "depth_m",
        "down_slope_width_m",
        "up_slope_width_m",
        "left_q_m",
        "right_q_m",
        "coverage_width_m",
        "signed_overlap_m",
        "overlap_rate",
    ]
    diffs = []
    for ro, rn in zip(old, new, strict=True):
        for field in fields:
            a, b = ro[field], rn[field]
            if math.isnan(a) and math.isnan(b):
                continue
            diffs.append(abs(a - b))

    normalized_v2 = paper_v2.replace(r"\gamma", r"\beta").replace(r"$\eta_i$", "$eta_i$")
    result1_root = ROOT / "result1.xlsx"
    result1_versioned = ROOT / "工作记录" / "结果" / "Q01" / "result1-v001.xlsx"
    report = {
        "revision": "Q01 notation-only beta-to-gamma",
        "beta_markers_replaced": beta_count,
        "plain_eta_markers_fixed": eta_plain_count,
        "paper_normalized_text_equal": normalized_v2 == paper_v1,
        "numeric_field_comparisons": len(diffs),
        "max_absolute_difference": max(diffs, default=0.0),
        "all_numeric_equal": all(value == 0.0 for value in diffs),
        "result1_root_sha256": sha256(result1_root),
        "result1_versioned_sha256": sha256(result1_versioned),
        "result1_files_byte_equal": result1_root.read_bytes() == result1_versioned.read_bytes(),
        "paper_v001_sha256": sha256(PAPER_V1),
        "paper_v002_sha256": sha256(PAPER_V2),
        "mapping_v001_sha256": sha256(MAP_V1),
        "mapping_v002_sha256": sha256(MAP_V2),
    }
    CHECK_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
