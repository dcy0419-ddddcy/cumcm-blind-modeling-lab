"""Generate the Q3 manuscript package from a bound local delivery manifest.

The script performs document assembly only.  It never runs layout search,
optical evaluation, numerical confirmation, TeX compilation, PDF rendering,
Git, or network access.

Formal output is permitted only when delivery/report.json declares
CONFIRMED_IMPROVEMENT and every bound confirmation/comparison/rebuild gate is
independently readable and consistent.  All other states produce a separate
unfinished draft without fabricated result values.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
Q3_OUT = ROOT / "工作记录/诊断结果/Q03-实施-v001"
DELIVERY_REPORT = Q3_OUT / "delivery/report.json"
PAPER = ROOT / "工作记录/论文"
TEX_DIR = PAPER / "LaTeX"
FORMAL_MD = PAPER / "第3问-模型建立与求解-v001.md"
FORMAL_TEX = TEX_DIR / "第3问-模型建立与求解-v001.tex"
INCOMPLETE_MD = PAPER / "第3问-模型建立与求解-v001-未完成.md"
INCOMPLETE_TEX = TEX_DIR / "第3问-模型建立与求解-v001-未完成.tex"
PAPER_RECORD = Q3_OUT / "delivery/论文生成记录-v001.json"
BASELINE_DESIGN = Q3_OUT / "candidates/Q3R000/design.json"
TEX_CONVERTER = ROOT / "工作记录/诊断代码/q02_repair_paper_tex_v002.py"

REFERENCE_FIELDS = (
    "design_file",
    "candidate_confirmation_summary",
    "baseline_confirmation_summary",
    "comparison_report",
    "excel_file",
    "rebuild_report",
    "search_trace",
    "result_data",
)
JSON_FIELDS = {
    "design_file",
    "candidate_confirmation_summary",
    "baseline_confirmation_summary",
    "comparison_report",
    "rebuild_report",
    "result_data",
}
EXPECTED_MONTHS = [f"{month:02d}-21" for month in range(1, 13)] + ["annual"]


class PaperInputError(ValueError):
    """Bound delivery evidence is absent, inconsistent, or not publication-ready."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def local(path: Path, *, within_q3: bool = False) -> Path:
    resolved = path.resolve()
    anchor = Q3_OUT.resolve() if within_q3 else ROOT.resolve()
    if not resolved.is_relative_to(anchor):
        raise PaperInputError(f"path leaves authorized local scope: {resolved}")
    return resolved


def load_json(path: Path) -> Any:
    return json.loads(local(path).read_text(encoding="utf-8-sig"))


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PaperInputError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise PaperInputError(f"{name} must be finite")
    return result


def _plain_inline(value: Any, name: str) -> str:
    """Accept one plain Markdown-safe inline value from bound JSON evidence."""
    if not isinstance(value, str) or not value.strip():
        raise PaperInputError(f"{name} must be a nonempty string")
    result = value.strip()
    if any(marker in result for marker in ("\r", "\n", "|")):
        raise PaperInputError(f"{name} cannot contain a line break or table delimiter")
    return result


def _matrix(value: Any, rows: int, columns: int, name: str) -> list[list[float]]:
    if not isinstance(value, list) or len(value) != rows:
        raise PaperInputError(f"{name} must have {rows} rows")
    result = []
    for ri, row in enumerate(value):
        if not isinstance(row, list) or len(row) != columns:
            raise PaperInputError(f"{name}[{ri}] must have {columns} columns")
        result.append([_finite(item, f"{name}[{ri}]") for item in row])
    return result


def _artifact(report: dict[str, Any], field: str) -> Path:
    reference = report.get(field)
    if not isinstance(reference, str) or not reference:
        raise PaperInputError(f"delivery report lacks {field}")
    relative = Path(reference)
    if relative.is_absolute():
        raise PaperInputError(f"{field} must be relative to Q03-实施-v001")
    path = local(Q3_OUT / relative, within_q3=True)
    if not path.is_file():
        raise PaperInputError(f"bound artifact is missing: {reference}")
    hashes = report.get("sha256")
    if not isinstance(hashes, dict):
        raise PaperInputError("delivery report lacks sha256 mapping")
    expected = hashes.get(reference)
    if expected is None:
        expected = hashes.get(relative.as_posix())
    if (
        not isinstance(expected, str)
        or len(expected) != 64
        or any(ch not in "0123456789abcdef" for ch in expected.lower())
    ):
        raise PaperInputError(f"delivery report lacks valid sha256 for {reference}")
    observed = sha256(path)
    if observed != expected.lower():
        raise PaperInputError(f"bound artifact changed: {reference}")
    return path


def _load_formal_artifacts(report: dict[str, Any]) -> dict[str, Any]:
    paths = {field: _artifact(report, field) for field in REFERENCE_FIELDS}
    values = {
        field: load_json(paths[field])
        for field in JSON_FIELDS
    }
    values["_paths"] = paths
    return values


def _validate_summary(summary: Any, label: str) -> dict[str, Any]:
    if not isinstance(summary, dict):
        raise PaperInputError(f"{label} summary must be a JSON object")
    if summary.get("kind") != "Q03_FULL_CONFIRMATION_SUMMARY":
        raise PaperInputError(f"{label} is not a Q3 full-confirmation summary")
    if summary.get("summary_version") != "q03-summary-v001":
        raise PaperInputError(f"{label} summary version is not q03-summary-v001")
    if summary.get("labels") != [
        "optical", "cosine", "shadow_blocking", "truncation",
        "power_kw", "unit_power_kw_m2",
    ]:
        raise PaperInputError(f"{label} summary columns do not match H02")
    coverage = summary.get("coverage")
    if (
        not isinstance(coverage, dict)
        or coverage.get("times") != 60
        or coverage.get("objects") != 2981
        or coverage.get("complete_time_population") is not True
    ):
        raise PaperInputError(f"{label} summary does not cover the fixed 60x2981 population")
    for field in (
        "formal_ready",
        "rated_power_met",
        "all_table_items_precision_met",
    ):
        if summary.get(field) is not True:
            raise PaperInputError(f"{label} summary gate failed: {field}")
    if summary.get("formal_decision") != "PASS":
        raise PaperInputError(f"{label} summary is not PASS")
    if summary.get("required_table_na_locations"):
        raise PaperInputError(f"{label} summary contains required table NA")
    if summary.get("diagnostic_na_locations"):
        raise PaperInputError(f"{label} summary contains diagnostic NA")
    if summary.get("rows") != EXPECTED_MONTHS:
        raise PaperInputError(f"{label} summary row order differs from fixed H02")
    point = _matrix(summary.get("point"), 13, 6, label + ".point")
    work = _matrix(
        summary.get("conservative_work_indicator"),
        13,
        6,
        label + ".conservative_work_indicator",
    )
    area = summary.get("area_weighted_efficiencies")
    if not isinstance(area, dict):
        raise PaperInputError(f"{label} lacks area-weighted efficiency diagnostics")
    if area.get("labels") != ["optical", "cosine", "shadow_blocking", "truncation"]:
        raise PaperInputError(f"{label} area-weighted columns are inconsistent")
    area_point = _matrix(area.get("point"), 13, 4, label + ".area_point")
    area_work = _matrix(
        area.get("conservative_work_indicator"),
        13,
        4,
        label + ".area_work",
    )
    rated_lower = _finite(
        summary.get("rated_power_lower_work_value_kw"),
        label + ".rated_power_lower_work_value_kw",
    )
    return {
        "raw": summary,
        "point": point,
        "work": work,
        "area_point": area_point,
        "area_work": area_work,
        "rated_lower": rated_lower,
    }


def _validate_design(design: Any, selected_name: str) -> dict[str, Any]:
    if not isinstance(design, dict) or design.get("schema") != "q03-heterogeneous-design-v001":
        raise PaperInputError("selected design does not use the Q3 heterogeneous schema")
    if design.get("name") != selected_name:
        raise PaperInputError("selected_design and design name disagree")
    mirrors = design.get("mirrors")
    if not isinstance(mirrors, list) or len(mirrors) != 2981:
        raise PaperInputError("selected design does not preserve the frozen N=2981")
    if design.get("tower_xy") != [0.0, -15.0]:
        raise PaperInputError("selected design does not preserve tower (0,-15)")
    required = {
        "mirror_id", "position_key", "x", "y", "z",
        "width", "height", "area", "group",
    }
    ids, keys, total_area = set(), set(), []
    groups: dict[int, list[dict[str, Any]]] = {}
    for index, row in enumerate(mirrors):
        if not isinstance(row, dict) or set(row) != required:
            raise PaperInputError(f"selected design mirror {index} has incomplete fields")
        mirror_id = row["mirror_id"]
        position_key = row["position_key"]
        group = row["group"]
        if isinstance(mirror_id, bool) or not isinstance(mirror_id, int) or mirror_id <= 0:
            raise PaperInputError(f"invalid mirror_id at row {index}")
        if not isinstance(position_key, str) or not position_key:
            raise PaperInputError(f"invalid position_key at row {index}")
        if mirror_id in ids or position_key in keys:
            raise PaperInputError("duplicate selected-design identity")
        ids.add(mirror_id)
        keys.add(position_key)
        if isinstance(group, bool) or not isinstance(group, int) or group not in range(6):
            raise PaperInputError(f"invalid six-group label at row {index}")
        width = _finite(row["width"], f"width[{index}]")
        height = _finite(row["height"], f"height[{index}]")
        area = _finite(row["area"], f"area[{index}]")
        for field in ("x", "y", "z"):
            _finite(row[field], f"{field}[{index}]")
        if area != width * height:
            raise PaperInputError(f"declared area differs from width*height at row {index}")
        total_area.append(area)
        groups.setdefault(group, []).append(row)
    if sorted(groups) != list(range(6)):
        raise PaperInputError("the frozen 3x2 grouping does not contain six nonempty groups")

    baseline = load_json(BASELINE_DESIGN)
    if not isinstance(baseline, dict):
        raise PaperInputError("Q3R000 baseline design must be a JSON object")
    base_mirrors = baseline.get("mirrors")
    if (
        baseline.get("tower_xy") != design["tower_xy"]
        or not isinstance(base_mirrors, list)
        or len(base_mirrors) != len(mirrors)
    ):
        raise PaperInputError("Q3R000 baseline geometry cannot bind selected design")
    identity_fields = ("mirror_id", "position_key", "x", "y")
    for index, (base, selected) in enumerate(zip(base_mirrors, mirrors)):
        if any(base.get(field) != selected.get(field) for field in identity_fields):
            raise PaperInputError(f"selected design moved or reordered baseline mirror {index}")

    group_rows = []
    for group in sorted(groups):
        members = groups[group]
        parameters = {
            (
                float(row["width"]),
                float(row["height"]),
                float(row["z"]),
            )
            for row in members
        }
        if len(parameters) != 1:
            raise PaperInputError(f"group {group} does not share one parameter triple")
        width, height, z = next(iter(parameters))
        group_rows.append(
            {
                "group": group,
                "radial_bin": group // 2,
                "half_plane": group % 2,
                "count": len(members),
                "width": width,
                "height": height,
                "z": z,
                "area": math.fsum(float(row["area"]) for row in members),
            }
        )
    return {
        "raw": design,
        "mirrors": mirrors,
        "groups": group_rows,
        "total_area": math.fsum(total_area),
        "baseline_design_sha256": sha256(BASELINE_DESIGN),
    }


def _formal_context(report: dict[str, Any]) -> dict[str, Any]:
    if report.get("status") != "CONFIRMED_IMPROVEMENT":
        raise PaperInputError("delivery status is not CONFIRMED_IMPROVEMENT")
    selected_name = _plain_inline(report.get("selected_design"), "selected_design")
    evidence = _load_formal_artifacts(report)
    candidate = _validate_summary(
        evidence["candidate_confirmation_summary"], "candidate"
    )
    baseline = _validate_summary(
        evidence["baseline_confirmation_summary"], "baseline"
    )
    comparison = evidence["comparison_report"]
    if (
        not isinstance(comparison, dict)
        or comparison.get("kind") != "Q03_NEW_PAIRED_CONFIRMATION_V001"
        or comparison.get("candidate") != selected_name
        or comparison.get("baseline") != "Q3R000"
        or comparison.get("paired_identity_valid") is not True
    ):
        raise PaperInputError("comparison report does not bind the selected candidate and Q3R000")
    delta_q = _finite(
        comparison.get("delta_q_kw_m2"),
        "comparison.delta_q_kw_m2",
    )
    delta_q_u = _finite(
        comparison.get("work_indicator_delta_q"),
        "comparison.work_indicator_delta_q",
    )
    delta_p = _finite(
        comparison.get("delta_power_kw"),
        "comparison.delta_power_kw",
    )
    if (
        comparison.get("improvement_supported") is not True
        or delta_q <= 0.0
        or delta_q_u < 0.0
        or delta_q - delta_q_u <= 0.0
    ):
        raise PaperInputError("paired comparison does not support positive delta_q")
    method = _plain_inline(comparison.get("method"), "comparison.method")
    rebuild = evidence["rebuild_report"]
    if (
        not isinstance(rebuild, dict)
        or rebuild.get("kind") != "Q03_INDEPENDENT_SAVED_STATISTICS_REBUILD_V001"
        or rebuild.get("frozen_candidate") != selected_name
        or rebuild.get("all_pass") is not True
        or rebuild.get("formal_ready") is not True
        or rebuild.get("improvement_supported") is not True
    ):
        raise PaperInputError("independent rebuild did not pass")
    design = _validate_design(evidence["design_file"], selected_name)
    candidate_area = _finite(
        candidate["raw"]["area_weighted_efficiencies"].get("total_area_m2"),
        "candidate.area_weighted_efficiencies.total_area_m2",
    )
    if not math.isclose(
        candidate_area,
        design["total_area"],
        rel_tol=0.0,
        abs_tol=1e-8,
    ):
        raise PaperInputError("candidate confirmation area differs from selected design")
    results = evidence["result_data"]
    if (
        not isinstance(results, dict)
        or results.get("version") != "q03-results-v001"
        or results.get("selected_design") != selected_name
        or results.get("N") != 2981
    ):
        raise PaperInputError("official result data does not bind the selected Q3 design")
    result_point = _matrix(results.get("point"), 13, 6, "result_data.point")
    result_work = _matrix(
        results.get("work_indicator"), 13, 6, "result_data.work_indicator"
    )
    if result_point != candidate["point"] or result_work != candidate["work"]:
        raise PaperInputError("official result matrices differ from candidate confirmation")
    result_area = _finite(results.get("total_area"), "result_data.total_area")
    if not math.isclose(
        result_area,
        design["total_area"],
        rel_tol=0.0,
        abs_tol=1e-8,
    ):
        raise PaperInputError("official result area differs from the selected design")
    return {
        "report": report,
        "selected_name": selected_name,
        "candidate": candidate,
        "baseline": baseline,
        "comparison": comparison,
        "delta_q": delta_q,
        "delta_q_u": delta_q_u,
        "delta_p": delta_p,
        "method": method,
        "rebuild": rebuild,
        "results": results,
        "design": design,
        "paths": evidence["_paths"],
    }


METHOD = r"""## 1 问题分析

第3问解除统一镜面尺寸和统一安装高度的限制，在与第2问相同的场地、额定功率和光学评价口径下，要求给出逐镜宽度、高度、安装高度和中心坐标。尺寸自由度改变实际采光面积、有限矩形边界以及镜间遮挡关系，安装高度还改变三维传播几何。因此，逐镜参数必须进入设计身份、场景准备、光线求交、功率汇总和交付清单，不能在统一尺寸结果上作面积比例换算。

本问的原优化目标是在满足额定年平均输出热功率的条件下提高单位镜面面积年平均输出热功率：

\[
\max_{\mathcal D_3\in\Omega_3}\ \overline q
=\frac{\overline P}{A_{\rm tot}},
\qquad
\text{s.t.}\quad \overline P\ge60000\ \mathrm{kW}.
\tag{Q3-1}
\]

式（Q3-1）给出模型目标和约束。计算中的条件 \(\widehat{\overline P}-U_{\overline P}\ge60000\,\mathrm{kW}\) 只是预定数值工作标准下支持额定可行性的判据，不改写原目标，也不构成严格概率保证。

本文以第2问通过独立确认的 R027 为可行起点，固定塔位 \((0,-15)\,\mathrm m\)、2981 个稳定镜身份及全部平面坐标，只调整预先冻结的尺寸组参数。这样保留了可行基线并控制搜索维数，但不会探索镜位、镜数或塔位变化。所求结果只属于这一有限分组参数族，不提供原连续设计空间的全局最优性保证。

表A1　主要符号

| 符号 | 含义 | 单位 |
|---|---|---|
| \(\mathcal D_3,\Omega_3\) | 第3问逐镜设计及本轮有限可行搜索域 | — |
| \(\boldsymbol a,\boldsymbol c_R,\boldsymbol c_i\) | 塔平面位置、接收器中心、镜面中心 | m |
| \(\boldsymbol s_{0k},\boldsymbol s,\boldsymbol t_i,\boldsymbol n_{ik}\) | 太阳中心方向、抽样光源方向、镜心至接收器方向、镜面单位法向 | 1 |
| \(c_{ik},g_{ik},\tau_i\) | 中心余弦因子、投影权重、大气透射率 | 1 |
| \(S,B,R\) | 未遮阴、反射段未遮挡、有效侧面首次接收事件 | 0或1 |
| \(A_i,A_{\rm tot},\overline P,\overline q\) | 单镜面积、总面积、年平均总功率、单位面积年平均功率 | m²、m²、kW、kW/m² |
| \(M_{0,ik},M_{1,ik},M_{2,ik},U_Q\) | 三层池化加权和及统计量 \(Q\) 的数值工作指标 | 见定义 |

## 2 设计变量、几何约束与分组

第 \(i\) 面镜的宽、高、安装高度、平面中心和面积分别记为 \(w_i,h_i,z_i,\boldsymbol p_i=(x_i,y_i)\) 和 \(A_i=w_ih_i\)。完整设计写为

\[
\mathcal D_3=\left(\boldsymbol a,N,
\{\boldsymbol p_i,w_i,h_i,z_i\}_{i=1}^{N}\right),
\qquad
\boldsymbol a=(0,-15),\quad N=2981,\quad
A_{\rm tot}=\sum_{i=1}^{N}A_i .
\tag{Q3-2}
\]

场界和塔周禁布区继续按镜面中心判断，安装高度为镜心竖坐标。逐镜基本约束为

\[
\|\boldsymbol a\|\le350,\quad
\|\boldsymbol p_i\|\le350,\quad
\|\boldsymbol p_i-\boldsymbol a\|\ge100,\quad
2\le w_i,h_i\le8,\quad
2\le z_i\le6,\quad
z_i>\frac{h_i}{2}.
\tag{Q3-3}
\]

有限搜索另取 \(w_i\ge h_i\)。该关系延续第2问的搜索范围解释，不作为题面另给的独立硬约束。异宽镜对采用对称的全对间距规则

\[
\|\boldsymbol p_i-\boldsymbol p_j\|
\ge \max(w_i,w_j)+5,
\qquad 1\le i<j\le N .
\tag{Q3-4}
\]

该规则在 \(w_i=w_j\) 时退化为第2问条件。所有无序镜对均直接核验，数值报告阈值只定位近边界对象，不把真实负余量放行为可行。

固定镜位后，每面镜和每组的宽度上限可在光学搜索前由中心间距确定：

\[
w_i^{\rm cap}
=\min\!\left(8,\min_{j\ne i}\|\boldsymbol p_i-\boldsymbol p_j\|-5\right),
\qquad
w_g^{\rm cap}=\min_{i:g_i=g}w_i^{\rm cap}.
\tag{Q3-5}
\]

组参数须满足 \(w_g\le w_g^{\rm cap}\)。对冻结的 R027 坐标，静态全对报告给出的全场上限为约 \(6.70\,\mathrm m\)，6个组的成员最小上限也均约为 \(6.70\,\mathrm m\)；搜索不得以显示舍入把宽度放到该实际上限之外。

为降低变量维数，先按镜心到塔的距离排序，同距时按稳定镜身份排序，再按径向秩等分为3组；相对塔位的方位角归一到 \([0,2\pi)\)，用两个半开半平面区间划分。径向编号为 \(r_i\in\{0,1,2\}\)，半平面编号为 \(b_i\in\{0,1\}\)，组号为

\[
r_i=\min\!\left(2,\left\lfloor\frac{3\,{\rm rank}_i}{N}\right\rfloor\right),
\qquad
b_i=\left\lfloor\frac{\theta_i}{\pi}\right\rfloor,
\qquad
g_i=2r_i+b_i .
\tag{Q3-6}
\]

由此得到6个非空组，每组共享 \((w_g,h_g,z_g)\)。组成员在查看光学结果前冻结，参数改变后不重新分组；所有组同取 R027 参数时完整表示可行基线。

## 3 光学评价与异面积统计

太阳位置、DNI、硬截止圆锥光源、反射率 \(\rho=0.92\)、有限矩形和单次理想反射采用第2问的同一口径。每个候选仍在全部镜面作为障碍的场景中评价；改变任一 \(w_i,h_i,z_i\) 都重新建立镜面边界、三维中心、遮挡候选和场景身份。

令接收器中心为 \(\boldsymbol c_R=(a_x,a_y,80)\)，太阳中心单位方向 \(\boldsymbol s_{0k}\) 和圆锥内抽样方向 \(\boldsymbol s\) 均指向光源。镜心至接收器中心的单位方向、镜面法向、中心余弦、投影权重和大气透射率为

\[
\begin{aligned}
\boldsymbol t_i&=\frac{\boldsymbol c_R-\boldsymbol c_i}
{\|\boldsymbol c_R-\boldsymbol c_i\|},
&\boldsymbol n_{ik}&=\frac{\boldsymbol s_{0k}+\boldsymbol t_i}
{\|\boldsymbol s_{0k}+\boldsymbol t_i\|},\\
c_{ik}&=\boldsymbol n_{ik}\cdot\boldsymbol s_{0k},
&g_{ik}(\boldsymbol s)&=
\frac{\boldsymbol n_{ik}\cdot\boldsymbol s}
{\boldsymbol s_{0k}\cdot\boldsymbol s},\\
d_i&=\|\boldsymbol c_R-\boldsymbol c_i\|,
&\tau_i&=0.99321-0.0001176d_i+1.97\times10^{-8}d_i^2.
\end{aligned}
\tag{Q3-7}
\]

其中，大气透射公式用于 \(d_i\le1000\,\mathrm m\) 的当前场景。对镜面源点 \(\boldsymbol x\)，从源点向光源回查且无其他镜面或接收器实体遮阴时记 \(S=1\)；反射路径在规定终点前未被其他镜面截住时记 \(B=1\)；接收器的首次实体接触为有效外入侧面时记 \(R=1\)。只有联合事件 \(SBR=1\) 计入有效接收。

N04 对未接收路径采用接收体包围球后切平面作为有限终点：

\[
(\boldsymbol x-\boldsymbol c_R)\cdot\boldsymbol t_i=R_b,
\qquad
R_b=\sqrt{3.5^2+4^2}.
\tag{Q3-8}
\]

若路径更早接触接收器实体，则在首次接触处终止；所有终止参数必须为正。该终点只规定阴影遮挡和截断损失的分项归属，不是新增实体。改变未接收路径终点可能改变两个分项而不改变净接收，因此本文不把这一分解称为唯一物理定义。

对镜 \(i\)、时点 \(k\) 的源样本，令 \(g\) 为投影权重，\(S,B,R\) 分别表示未遮阴、反射段未遮挡和首次接触有效受光侧面。合并所纳入批次的 \(n_{\rm tot}\) 条互不重复源样本，保存

\[
M_{0,ik}=\sum g,\qquad
M_{1,ik}=\sum gSB,\qquad
M_{2,ik}=\sum gSBR .
\tag{Q3-9}
\]

在分母为正且没有边界未知状态时，自归一总效率及两个条件比分别为

\[
\widehat\eta_{ik}
=\rho\,c_{ik}\tau_i\frac{M_{2,ik}}{M_{0,ik}},
\qquad
\widehat\eta_{{\rm sb},ik}=\frac{M_{1,ik}}{M_{0,ik}},
\qquad
\widehat\eta_{{\rm trunc},ik}=\frac{M_{2,ik}}{M_{1,ik}} .
\tag{Q3-10}
\]

另以 \(M_{\ell,ik}/n_{\rm tot}\) 构造原始积分替代量，作为数值诊断而非另一套物理模型。真实零只有在当前完整场景的可验证证书成立时才写为0；有限样本零、未知交点和非法分母保留未定义状态，不通过换种子或删除镜面隐藏。

表1、表2中的四项平均效率继续采用固定镜面总体的镜数算术平均

\[
\overline\eta_{N,k}=\frac1N\sum_{i=1}^{N}\eta_{ik}.
\tag{Q3-11}
\]

同时另存面积加权效率作为辅助诊断

\[
\overline\eta_{A,k}
=\frac{\sum_{i=1}^{N}A_i\eta_{ik}}{A_{\rm tot}} .
\tag{Q3-12}
\]

两种平均回答不同问题，不能按数值高低选择报告口径。全场功率必须使用逐镜实际面积：

\[
P_k=\mathrm{DNI}_k\sum_{i=1}^{N}A_i\eta_{ik},
\qquad
\overline P=\frac1{60}\sum_{k=1}^{60}P_k,
\qquad
\overline q=\frac{\overline P}{A_{\rm tot}} .
\tag{Q3-13}
\]

因此，镜数平均效率不能直接乘总面积代替式（Q3-13）。能量总量比与逐镜条件比的镜均值也分别保存，不把二者混写成同一效率。

## 4 有限搜索与独立确认

搜索只在6组参数构成的有限邻域内进行，每个参数组合先逐镜展开，再核验尺寸、高度、离地、中心边界及全部异宽镜对。较精比较均采用完整60时点；低样本出现的抽样零或其他未定义状态促使增样，并继续保留原状态，不据此给出正式额定认证。搜索评分只用于候选排序。

冻结候选后，额定确认和相对改进比较使用未继续调参的新随机流。对任一月度或年度汇总量 \(Q\)，数值工作指标取

\[
U_Q=\max\!\left(
t_{B-1,0.975}\,\mathrm{SE}_{\rm JK},
|\widehat Q-\widehat Q_{1/2}|,
|\widehat Q-\widehat Q_{\rm raw}|
\right)+D_{{\rm low},Q}.
\tag{Q3-14}
\]

其中，\(\mathrm{SE}_{\rm JK}\) 由删除一个完整独立批次的伪值计算，半量前缀与终值相关，\(D_{{\rm low},Q}\) 是合并存活数低于阈值对象的逐坐标全范围影响量。面积加权辅助效率使用 \(A_i/A_{\rm tot}\) 形成自己的低存活界。\(U_Q\) 是预定的数值工作指标，不是严格置信区间、同时误差界或物理误差界。

候选额定条件为 \(\widehat{\overline P}-U_{\overline P}\ge60000\,\mathrm{kW}\)，且全部题表项满足数值精度要求。改进判断在同一新配对批次中分别计算候选与 R027 的实际 \(\overline q\)，再对 \(\Delta q=\overline q_{\rm cand}-\overline q_{\rm base}\) 建立工作指标；不能先相减功率再除以任一设计的面积。
"""


def _fmt(value: float, digits: int = 6) -> str:
    return f"{value:.{digits}f}"


def _scientific(value: float, digits: int = 5) -> str:
    if value == 0.0:
        return "0"
    mantissa, exponent = f"{value:.{digits}e}".split("e")
    return rf"\({mantissa}\times10^{{{int(exponent)}}}\)"


def _formal_markdown(context: dict[str, Any]) -> str:
    name = context["selected_name"]
    candidate = context["candidate"]
    baseline = context["baseline"]
    design = context["design"]
    comparison = context["comparison"]
    point = candidate["point"]
    work = candidate["work"]
    annual = point[-1]
    annual_u = work[-1]
    area_annual = candidate["area_point"][-1]
    area_u = candidate["area_work"][-1]
    baseline_annual = baseline["point"][-1]
    report = context["report"]

    lines = [
        f"# 第3问：逐镜异尺寸定日镜场的分组设计与确认",
        "",
        METHOD.strip(),
        "",
        "## 5 结果分析与验证",
        "",
        "### 5.1 冻结候选与逐组参数",
        "",
        f"有限分组搜索最终冻结候选 {name}。其塔位、镜数、稳定镜身份和全部平面坐标与 R027 保持一致；逐镜宽度、高度和安装高度由表S1的6组参数展开。总镜面面积为 {_fmt(design['total_area'],4)} m²。分组是降维表示，不表示同组镜面的局部光学条件相同。",
        "",
        f"表S1　{name} 的6组逐镜参数",
        "",
        "| 组号 | 径向秩组 | 半平面 | 镜数 | 宽度（m） | 高度（m） | 安装高度（m） | 组面积（m²） |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in design["groups"]:
        lines.append(
            "| {group} | {radial_bin} | {half_plane} | {count} | {width:.6f} | "
            "{height:.6f} | {z:.6f} | {area:.4f} |".format(**row)
        )

    lines.extend(
        [
            "",
            "### 5.2 正式题表与额定确认",
            "",
            f"候选的年平均总功率点估计为 {_fmt(annual[4],4)} kW，功率工作指标为 {_fmt(annual_u[4],4)} kW，工作下限为 {_fmt(candidate['rated_lower'],4)} kW。单位面积年平均输出热功率为 {_fmt(annual[5],7)} kW/m²，相应工作指标为 {_scientific(annual_u[5])} kW/m²。以下题表采用镜数平均效率，功率和单位面积功率按逐镜实际面积汇总。",
            "",
            f"表1　{name} 每月21日的平均光学效率及输出热功率",
            "",
            "| 日期 | 平均光学效率 | 平均余弦效率 | 平均阴影遮挡效率 | 平均截断效率 | 单位面积镜面平均输出热功率（kW/m²） |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for month, row in enumerate(point[:12], 1):
        lines.append(
            f"| {month}月21日 | {_fmt(row[0],4)} | {_fmt(row[1],4)} | "
            f"{_fmt(row[2],4)} | {_fmt(row[3],4)} | {_fmt(row[5],4)} |"
        )
    lines.extend(
        [
            "",
            f"表2　{name} 年平均光学效率及输出热功率",
            "",
            "| 年平均光学效率 | 年平均余弦效率 | 年平均阴影遮挡效率 | 年平均截断效率 | 年平均输出热功率（MW） | 单位面积镜面年平均输出热功率（kW/m²） |",
            "|---:|---:|---:|---:|---:|---:|",
            f"| {_fmt(annual[0],4)} | {_fmt(annual[1],4)} | {_fmt(annual[2],4)} | "
            f"{_fmt(annual[3],4)} | {_fmt(annual[4]/1000.0,3)} | {_fmt(annual[5],4)} |",
            "",
            f"表3　{name} 定日镜场设计参数",
            "",
            "| 吸收塔位置坐标（m） | 定日镜尺寸（宽×高）（m） | 定日镜安装高度（m） | 定日镜总面数 | 定日镜总面积（m²） |",
            "|---|---|---|---:|---:|",
            f"| \\((0,-15)\\) | 逐镜见 result3.xlsx | 逐镜见 result3.xlsx | 2981 | {_fmt(design['total_area'],4)} |",
            "",
            "表S2　面积加权效率辅助结果",
            "",
            "| 时间总体 | 面积加权总光学效率 | 面积加权余弦效率 | 面积加权阴影遮挡效率 | 面积加权截断效率 |",
            "|---|---:|---:|---:|---:|",
            f"| 年平均 | {_fmt(area_annual[0],6)} | {_fmt(area_annual[1],6)} | "
            f"{_fmt(area_annual[2],6)} | {_fmt(area_annual[3],6)} |",
            "",
            "表S3　面积加权效率的年度数值工作指标",
            "",
            "| 总光学效率 | 余弦效率 | 阴影遮挡效率 | 截断效率 |",
            "|---:|---:|---:|---:|",
            f"| {_scientific(area_u[0])} | {_scientific(area_u[1])} | "
            f"{_scientific(area_u[2])} | {_scientific(area_u[3])} |",
            "",
            "### 5.3 与 R027 的新配对比较",
            "",
            f"配对比较使用候选与 R027 的同一组新随机流，对逐批差值作删除一整批 jackknife。差值工作指标取配对批次近似半宽、配对半量前缀差和配对原始积分替代差三者的最大值，再加候选与基线按各自实际面积汇总的低存活影响量。候选相对 R027 的年度单位面积功率差为 {_fmt(context['delta_q'],7)} kW/m²，差值工作指标为 {_scientific(context['delta_q_u'])} kW/m²；总功率点估计差为 {_fmt(context['delta_p'],4)} kW。由于差值扣除工作指标后仍为正，当前新确认数据支持候选在所用模型和分组搜索域内提高单位面积功率。",
            "",
            "表S4　候选与 R027 的年度结果比较",
            "",
            "| 设计 | 年平均总功率（kW） | 功率工作指标（kW） | 单位面积年平均功率（kW/m²） | 单位面积功率工作指标（kW/m²） |",
            "|---|---:|---:|---:|---:|",
            f"| R027 新基线确认 | {_fmt(baseline_annual[4],4)} | {_fmt(baseline['work'][-1][4],4)} | "
            f"{_fmt(baseline_annual[5],7)} | {_scientific(baseline['work'][-1][5])} |",
            f"| {name} | {_fmt(annual[4],4)} | {_fmt(annual_u[4],4)} | "
            f"{_fmt(annual[5],7)} | {_scientific(annual_u[5])} |",
            f"| 差值（候选－基线） | {_fmt(context['delta_p'],4)} | — | "
            f"{_fmt(context['delta_q'],7)} | {_scientific(context['delta_q_u'])} |",
            "",
            "### 5.4 文件与重建验证",
            "",
            f"正式逐镜清单保存于 {_plain_inline(report['excel_file'], 'excel_file')}。交付报告同时绑定候选设计、候选与基线确认汇总、配对比较、搜索轨迹、工作簿和独立重建文件的 SHA-256；独立重建状态为通过。上述文件核对支持清单、统计和正文取值来自同一冻结证据链，不增加新的光学样本。",
            "",
            "## 6 局限",
            "",
            "本问固定 R027 的塔位、镜数和全部镜位，只在3个径向秩组与2个半平面的6组宽、高、安装高度中搜索。分组共享参数会遗漏单镜差异，固定布局也排除了密度、镜数与塔位的联合调整。候选比较经历有限搜索，配对确认隔离了最终估计与继续调参，却不校正整个候选选择过程，也不证明全局最优。",
            "",
            "数值工作指标只描述既定离散光学模型中的批间、前缀、估计形式和低存活敏感性。它不覆盖太阳位置与DNI近似、光源角分布、反射率、镜面形状与跟踪误差、塔身和支架省略、接收器热损失等物理偏差。增加射线数不能消除这些建模误差。面积加权效率是辅助统计，不能替代题表的镜数平均效率；能量总量比也不能与逐镜条件比的镜均值混同。",
            "",
            "## 7 本问小结",
            "",
            f"在固定 R027 塔位、镜数和镜位的6组异尺寸参数族内，{name} 通过候选额定确认和相对 R027 的新配对改进检查。其正式年平均总功率、工作下限和单位面积功率见表2，逐镜参数见 result3.xlsx。该结论限于冻结设计、本文光学模型和预定数值标准，不延伸为工程保证或全局最优性结论。",
            "",
        ]
    )
    return "\n".join(lines)


def _incomplete_markdown(reason: str, report: dict[str, Any] | None) -> str:
    status = report.get("status") if isinstance(report, dict) else "NO_DELIVERY_REPORT"
    return "\n".join(
        [
            "# 第3问：逐镜异尺寸定日镜场的分组设计与确认（未完成稿）",
            "",
            "> 本文件是进行中的写作草稿，不是正式论文交付。当前没有满足正式生成门槛的完整证据，因此不填写候选数值、题表或改进结论。",
            "",
            METHOD.strip(),
            "",
            "## 5 当前状态",
            "",
            f"交付状态：{status}。",
            "",
            f"未形成正式稿的原因：{reason}",
            "",
            "只有 delivery/report.json 标记 CONFIRMED_IMPROVEMENT，且候选额定与精度门槛、全部必需状态、R027 新基线确认、配对改进、实际清单哈希和独立重建同时通过后，脚本才会生成正式表1—3、辅助表和结论。在此之前不从搜索评分、部分时点或未确认候选补写数值。",
            "",
            "## 6 待填证据",
            "",
            "- 冻结候选逐镜设计及 result3.xlsx 同源读回；",
            "- 候选完整60时点独立确认；",
            "- R027 在新配对流中的基线确认；",
            "- 年度总功率、单位面积功率和配对差值工作指标；",
            "- 镜数平均主表、面积加权辅助表、低存活与 NA 状态；",
            "- 独立重建、搜索轨迹及所有交付文件摘要。",
            "",
        ]
    )


def _write_text(path: Path, text: str) -> None:
    local(path).parent.mkdir(parents=True, exist_ok=True)
    encoded = text.rstrip() + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != encoded:
        raise FileExistsError(f"refusing to replace changed manuscript version: {path}")
    path.write_text(encoded, encoding="utf-8")


def _make_tex(source: Path, target: Path, record: Path) -> dict[str, Any]:
    import q02_repair_paper_tex_v002 as converter

    original = converter.SOURCE, converter.TARGET, converter.RECORD
    try:
        converter.SOURCE = local(source)
        converter.TARGET = local(target)
        converter.RECORD = local(record)
        result = converter.convert()
    finally:
        converter.SOURCE, converter.TARGET, converter.RECORD = original
    result["reused_converter"] = TEX_CONVERTER.relative_to(ROOT).as_posix()
    result["reused_converter_sha256"] = sha256(TEX_CONVERTER)
    return result


def generate(report_path: Path = DELIVERY_REPORT) -> dict[str, Any]:
    report: dict[str, Any] | None = None
    formal = False
    reason = ""
    context = None
    if report_path.is_file():
        loaded = load_json(report_path)
        if not isinstance(loaded, dict):
            raise PaperInputError("delivery/report.json must contain one JSON object")
        report = loaded
        try:
            context = _formal_context(report)
            formal = True
        except PaperInputError as exc:
            reason = str(exc)
    else:
        reason = "delivery/report.json 尚未生成"

    if formal:
        markdown = _formal_markdown(context)
        md_target, tex_target = FORMAL_MD, FORMAL_TEX
        tex_record = Q3_OUT / "delivery/正式Markdown与TeX对应-v001.json"
    else:
        markdown = _incomplete_markdown(reason, report)
        md_target, tex_target = INCOMPLETE_MD, INCOMPLETE_TEX
        tex_record = Q3_OUT / "delivery/未完成Markdown与TeX对应-v001.json"

    _write_text(md_target, markdown)
    tex_result = _make_tex(md_target, tex_target, tex_record)
    source_hashes = {
        "delivery_report": sha256(report_path) if report_path.is_file() else None,
        "markdown": sha256(md_target),
        "tex": sha256(tex_target),
        "tex_converter": sha256(TEX_CONVERTER),
    }
    if formal:
        source_hashes["baseline_design"] = context["design"]["baseline_design_sha256"]
        for field, path in context["paths"].items():
            source_hashes[field] = sha256(path)
    record = {
        "schema": "q03-paper-generation-v001",
        "formal": formal,
        "delivery_status": report.get("status") if report else "NO_DELIVERY_REPORT",
        "reason_if_incomplete": None if formal else reason,
        "markdown": md_target.relative_to(ROOT).as_posix(),
        "tex": tex_target.relative_to(ROOT).as_posix(),
        "source_hashes": source_hashes,
        "tex_conversion": tex_result,
        "compilation_performed": False,
        "pdf_rendering_performed": False,
        "numerical_or_optical_computation_performed": False,
        "internet_or_git_used": False,
    }
    PAPER_RECORD.parent.mkdir(parents=True, exist_ok=True)
    PAPER_RECORD.write_text(
        json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return record


if __name__ == "__main__":
    result = generate()
    print(
        json.dumps(
            {
                "formal": result["formal"],
                "delivery_status": result["delivery_status"],
                "markdown": result["markdown"],
                "tex": result["tex"],
                "compilation_performed": False,
            },
            ensure_ascii=False,
        )
    )
