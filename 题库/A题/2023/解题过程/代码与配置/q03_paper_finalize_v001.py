"""Finalize the Q3 manuscript from already delivered local evidence.

This module performs document post-processing only.  It does not run search,
ray tracing, statistical reconstruction, figure generation, TeX compilation,
PDF rendering, Git, or network access.  ``run()`` must be called only after the
formal delivery report and the separately generated figure files exist.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import q03_paper_v001 as paper


ROOT = Path(__file__).resolve().parents[2]
Q3_OUT = ROOT / "工作记录/诊断结果/Q03-实施-v001"
REPORT = Q3_OUT / "delivery/report.json"
FINE_COMPARISON = Q3_OUT / "comparison-fine-v001.json"
DECISIONS = ROOT / "工作记录/决策记录.md"
SEARCH_RULES = Q3_OUT / "搜索规则冻结-v001.json"
CONFIRMATION_FREEZE = Q3_OUT / "最终候选与确认冻结-v001.json"
PROTOTYPE_REPORT = Q3_OUT / "prototype/report-v001.json"
Q2_PAPER = ROOT / "工作记录/论文/第2问-模型建立与求解-v002.md"
FIGURE_SCRIPT = ROOT / "工作记录/诊断代码/q03_figures_v002.py"
FIGURE_RECEIPT = Q3_OUT / "delivery/图表生成核验-v001.json"
FIGURE_DIR = ROOT / "工作记录/论文/图表/Q03-v001"
HEIGHT_FIGURE = FIGURE_DIR / "Q03-镜高分组.png"
MONTHLY_FIGURE = FIGURE_DIR / "Q03-月度单位面积功率.png"
REVISION_RECORD = ROOT / "工作记录/论文/第3问-写稿修订记录-v001.md"
FINALIZE_RECORD = Q3_OUT / "delivery/论文终稿后处理记录-v001.json"
CORRESPONDENCE = Q3_OUT / "delivery/正式Markdown与TeX对应-v001.json"
FAILURE_EVIDENCE = Q3_OUT / "delivery/finalize-failure-v001"
FAILED_MARKDOWN_SNAPSHOT = FAILURE_EVIDENCE / "第3问-模型建立与求解-v001-after-failed-run.md"
RECOVERY_RECORD = FAILURE_EVIDENCE / "失败与恢复记录-v001.json"

EXPECTED_SELECTED = "Q3F013"
EXPECTED_FINE_NAMES = ["Q3R000", "Q3R010", "Q3R012", "Q3R013"]
FINALIZE_MARKER = "<!-- Q03-PAPER-FINALIZE-V001 -->"

OLD_N04_LEAD = "N04 对未接收路径采用接收体包围球后切平面作为有限终点："
NEW_N04_LEAD = (
    "N04 对未接收路径采用接收体包围球后切平面作为有限终点。"
    "令 \\(\\boldsymbol y\\) 表示该终止平面上的任意点，则："
)
OLD_N04_PLANE = (
    "(\\boldsymbol x-\\boldsymbol c_R)\\cdot\\boldsymbol t_i=R_b,"
)
NEW_N04_PLANE = (
    "(\\boldsymbol y-\\boldsymbol c_R)\\cdot\\boldsymbol t_i=R_b,"
)
OLD_CAP_WORDING = "静态全对报告给出的全场上限为约"
NEW_CAP_WORDING = "静态全对报告给出的全场共同宽度上限为约"
OLD_RANK_WORDING = (
    "为降低变量维数，先按镜心到塔的距离排序，同距时按稳定镜身份排序，再按径向秩等分为3组；"
    "相对塔位的方位角归一到 \\([0,2\\pi)\\)，用两个半开半平面区间划分。"
    "径向编号为 \\(r_i\\in\\{0,1,2\\}\\)，半平面编号为 \\(b_i\\in\\{0,1\\}\\)，组号为"
)
NEW_RANK_WORDING = (
    "为降低变量维数，先按镜心到塔的距离排序，同距时按稳定镜身份排序；排序秩从0开始，即 "
    "\\({\\rm rank}_i\\in\\{0,1,\\ldots,N-1\\}\\)，再按径向秩等分为3组。"
    "相对塔位的方位角归一到 \\([0,2\\pi)\\)，用两个半开半平面区间划分。"
    "径向编号为 \\(r_i\\in\\{0,1,2\\}\\)，半平面编号为 \\(b_i\\in\\{0,1\\}\\)，组号为"
)
OLD_PHYSICS_LEAD = (
    "太阳位置、DNI、硬截止圆锥光源、反射率 \\(\\rho=0.92\\)、有限矩形和单次理想反射采用第2问的同一口径。"
    "每个候选仍在全部镜面作为障碍的场景中评价；改变任一 \\(w_i,h_i,z_i\\) 都重新建立镜面边界、三维中心、"
    "遮挡候选和场景身份。"
)
NEW_PHYSICS_LEAD = (
    "太阳位置、DNI、有限矩形、反射率 \\(\\rho=0.92\\) 和单次理想反射沿用"
    "[第2问已验收正文](第2问-模型建立与求解-v002.md)第2.1节及第4节的定义。"
    "光源仍取半角 \\(\\beta=0.00465\\,\\mathrm{rad}\\) 的硬截止圆锥，并在立体角上均匀抽样；"
    "\\(\\boldsymbol s\\) 指向光源，\\(\\mathrm{DNI}_k\\) 表示单位面积对参考太阳中心方向 "
    "\\(\\boldsymbol s_{0k}\\) 法面的直接辐照通量。每个候选仍在全部镜面作为障碍的场景中评价；"
    "改变任一 \\(w_i,h_i,z_i\\) 都重新建立镜面边界、三维中心、遮挡候选和场景身份，不引入新的物理输入。"
)
OLD_AFTER_G = (
    "其中，大气透射公式用于 \\(d_i\\le1000\\,\\mathrm m\\) 的当前场景。"
    "对镜面源点 \\(\\boldsymbol x\\)，从源点向光源回查且无其他镜面或接收器实体遮阴时记 \\(S=1\\)；"
)
NEW_AFTER_G = (
    "其中，大气透射公式用于 \\(d_i\\le1000\\,\\mathrm m\\) 的当前场景。"
    "只有当完整光源圆锥内各方向均位于镜面正面和地平线上方、"
    "\\(\\boldsymbol s_{0k}\\!\\cdot\\!\\boldsymbol s>0\\)，且N04终点参数为正时，"
    "才使用完整圆锥积分关系 \\(\\mathbb E[g_{ik}]=c_{ik}\\)；上述前提对每个设计的规定60时点逐一检查。"
    "对镜面源点 \\(\\boldsymbol x\\)，从源点向光源回查且无其他镜面或接收器实体遮阴时记 \\(S=1\\)；"
)
OLD_ZERO_WORDING = (
    "另以 \\(M_{\\ell,ik}/n_{\\rm tot}\\) 构造原始积分替代量，作为数值诊断而非另一套物理模型。"
    "真实零只有在当前完整场景的可验证证书成立时才写为0；有限样本零、未知交点和非法分母保留未定义状态，"
    "不通过换种子或删除镜面隐藏。"
)
NEW_ZERO_WORDING = (
    "另以 \\(M_{\\ell,ik}/n_{\\rm tot}\\) 构造原始积分替代量，作为数值诊断而非另一套物理模型。"
    "真实零只有在当前完整场景的可验证证书成立时才据此认定；必需分母不足或非法、存在未知交点时保留未定义状态。"
    "若存活分母为正而接收计数为零，则相应条件比保留有限样本估计零，但该估计不证明真实截断为零；"
    "不通过换种子或删除镜面隐藏任何状态。"
)
OLD_SEARCH_METHOD = (
    "搜索只在6组参数构成的有限邻域内进行，每个参数组合先逐镜展开，再核验尺寸、高度、离地、中心边界及全部异宽镜对。"
    "较精比较均采用完整60时点；低样本出现的抽样零或其他未定义状态促使增样，并继续保留原状态，不据此给出正式额定认证。"
    "搜索评分只用于候选排序。"
)
NEW_SEARCH_METHOD = (
    "搜索只在6组参数构成的有限邻域内进行，每个参数组合先逐镜展开，再核验尺寸、高度、离地、中心边界及全部异宽镜对。"
    "低样本层采用2个独立批次、每批16条源样本及批内8条半量前缀；较精层采用4批、每批64条及32条半量前缀。"
    "两层均覆盖2981面镜和完整60时点，只在层内比较。批内前缀与终值嵌套，汇总只池化每批最大样本层，"
    "不把前缀重复计数。必需分母不足造成的抽样零保留为未定义；正存活分母下的零接收形成估计零但不证明真实零。"
    "这些状态用于决定是否增样，不作为正式额定认证；搜索评分只用于候选排序。"
)
OLD_CONFIRM_METHOD = (
    "冻结候选后，额定确认和相对改进比较使用未继续调参的新随机流。对任一月度或年度汇总量 \\(Q\\)，数值工作指标取"
)
NEW_CONFIRM_METHOD = (
    "冻结候选后，额定确认和相对改进比较使用未继续调参的新随机流：候选与R027基线均取8个独立批次、"
    "每批256条源样本，批内128条前缀只作相关诊断而不重复计入终值。两设计按稳定镜身份、规定时点和批次配对，"
    "使用共同随机流；每一设计均完整评价60个时点与2981面镜。对任一月度或年度汇总量 \\(Q\\)，数值工作指标取"
)


class FinalizeInputError(ValueError):
    """Delivered document evidence is absent or inconsistent."""


def _local(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(ROOT.resolve()):
        raise FinalizeInputError(f"path leaves A-P8C3: {resolved}")
    return resolved


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with _local(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(_local(path).read_text(encoding="utf-8-sig"))


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FinalizeInputError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise FinalizeInputError(f"{name} must be finite")
    return result


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise FinalizeInputError(f"{label}: expected one source occurrence, found {count}")
    return text.replace(old, new, 1)


def _relative(path: Path) -> str:
    return _local(path).relative_to(ROOT.resolve()).as_posix()


def _write_new(path: Path, text: str) -> None:
    target = _local(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = text.rstrip() + "\n"
    if target.exists():
        if target.read_text(encoding="utf-8") == encoded:
            return
        raise FileExistsError(f"refusing to replace existing version: {target}")
    target.write_text(encoded, encoding="utf-8")


def _write_json_new(path: Path, payload: dict[str, Any]) -> None:
    _write_new(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False),
    )


def _bound_report() -> dict[str, Any]:
    if not REPORT.is_file():
        raise FinalizeInputError("formal delivery/report.json does not exist")
    report = _load_json(REPORT)
    if not isinstance(report, dict) or report.get("status") != "CONFIRMED_IMPROVEMENT":
        raise FinalizeInputError("Q3 delivery is not CONFIRMED_IMPROVEMENT")
    if report.get("selected_design") != EXPECTED_SELECTED:
        raise FinalizeInputError(
            f"expected delivered design {EXPECTED_SELECTED}, got {report.get('selected_design')!r}"
        )
    # Reuse the manuscript module's formal evidence gate before writing anything.
    paper._formal_context(report)
    return report


def _decision_section() -> tuple[str, str]:
    text = _local(DECISIONS).read_text(encoding="utf-8")
    heading = "## D046 —"
    start = text.find(heading)
    if start < 0:
        raise FinalizeInputError("D046 decision section is missing")
    end = text.find("\n## ", start + len(heading))
    section = text[start:] if end < 0 else text[start:end]
    required = (
        "14个全场低样本候选",
        "4个全场较精比较",
        "Q3R013",
        "Q3F013",
        "8.638175158703234 kW",
        "30 kW余量",
        "软偏好而非必要门禁",
    )
    missing = [snippet for snippet in required if snippet not in section]
    if missing:
        raise FinalizeInputError(f"D046 lacks required selection evidence: {missing}")
    return section, _sha_text(section)


def _trace_counts(report: dict[str, Any]) -> dict[str, Any]:
    relative = report.get("search_trace")
    if not isinstance(relative, str) or not relative:
        raise FinalizeInputError("delivery report lacks search_trace")
    path = _local(Q3_OUT / relative)
    expected = report.get("sha256", {}).get(relative)
    if not isinstance(expected, str) or _sha(path) != expected.lower():
        raise FinalizeInputError("search trace differs from delivery binding")
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise FinalizeInputError(f"search trace line {line_number} is not an object")
        rows.append(row)
    low = [row for row in rows if row.get("tag") == "low"]
    fine = [row for row in rows if row.get("tag") == "fine"]
    if len(low) != 14 or len(fine) != 4:
        raise FinalizeInputError(
            f"expected 14 low and 4 fine rows, found {len(low)} and {len(fine)}"
        )
    if [row.get("name") for row in fine] != EXPECTED_FINE_NAMES:
        raise FinalizeInputError("fine rows in search trace have unexpected identity/order")
    return {"path": path, "rows": rows, "low": low, "fine": fine}


def _fine_rows(trace: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _load_json(FINE_COMPARISON)
    if not isinstance(payload, list) or len(payload) != 4:
        raise FinalizeInputError("comparison-fine-v001.json must contain four rows")
    if [row.get("name") for row in payload if isinstance(row, dict)] != EXPECTED_FINE_NAMES:
        raise FinalizeInputError("fine comparison identity/order differs from frozen four")

    validated = []
    for index, (row, trace_row) in enumerate(zip(payload, trace["fine"])):
        if not isinstance(row, dict):
            raise FinalizeInputError(f"fine comparison row {index} is not an object")
        if (
            row.get("tag") != "fine"
            or row.get("formal_rating") != "NOT_PERMITTED_HEURISTIC"
            or row.get("actual_time_count") != 60
            or row.get("actual_mirror_count") != 2981
        ):
            raise FinalizeInputError(f"fine row {row.get('name')} has invalid scope/status")
        for field in ("zero_survivor", "zero_capture", "unknown"):
            if row.get(field) != 0:
                raise FinalizeInputError(f"fine row {row.get('name')} has unresolved {field}")
        numeric = {
            field: _finite(row.get(field), f"{row.get('name')}.{field}")
            for field in (
                "P_score_kw",
                "q_score_kw_m2",
                "area",
                "delta_q",
                "paired_search_se",
                "power_search_work",
                "power_search_margin",
            )
        }
        score = trace_row.get("score")
        if not isinstance(score, dict):
            raise FinalizeInputError("fine search trace lacks score object")
        for field in ("P_score_kw", "q_score_kw_m2"):
            if numeric[field] != _finite(score.get(field), f"trace.{row.get('name')}.{field}"):
                raise FinalizeInputError(f"fine table differs from search trace for {field}")
        if numeric["area"] != _finite(trace_row.get("area"), "trace.area"):
            raise FinalizeInputError("fine table area differs from search trace")
        validated.append({**row, **numeric})

    selected = validated[-1]
    if selected["name"] != "Q3R013":
        raise FinalizeInputError("Q3R013 is not the frozen fine parent")
    if selected["q_score_kw_m2"] != max(row["q_score_kw_m2"] for row in validated):
        raise FinalizeInputError("Q3R013 is not highest-q in the frozen fine comparison")
    if not math.isclose(
        selected["power_search_margin"],
        8.638175158703234,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise FinalizeInputError("Q3R013 search margin differs from D046")
    return validated


def _figure_binding(report: dict[str, Any]) -> dict[str, Any]:
    for path in (FIGURE_SCRIPT, FIGURE_RECEIPT, HEIGHT_FIGURE, MONTHLY_FIGURE):
        if not _local(path).is_file():
            raise FinalizeInputError(f"required separately generated figure evidence is missing: {path}")
    receipt = _load_json(FIGURE_RECEIPT)
    if not isinstance(receipt, dict):
        raise FinalizeInputError("figure receipt is not a JSON object")
    listed = receipt.get("figures")
    expected_figures = {_relative(HEIGHT_FIGURE), _relative(MONTHLY_FIGURE)}
    listed_normalized = (
        {Path(item).as_posix() for item in listed if isinstance(item, str)}
        if isinstance(listed, list)
        else set()
    )
    if not expected_figures.issubset(listed_normalized):
        raise FinalizeInputError("figure receipt does not list both required Q3 figures")
    sources = receipt.get("sources")
    receipt_hashes = receipt.get("source_sha256")
    report_hashes = report.get("sha256")
    for field in (
        "design_file",
        "candidate_confirmation_summary",
        "baseline_confirmation_summary",
    ):
        if not isinstance(sources, dict) or sources.get(field) != report.get(field):
            raise FinalizeInputError(f"figure source differs from delivery report: {field}")
        reference = report[field]
        if (
            not isinstance(receipt_hashes, dict)
            or not isinstance(report_hashes, dict)
            or receipt_hashes.get(reference) != report_hashes.get(reference)
        ):
            raise FinalizeInputError(f"figure source hash differs from delivery report: {field}")
    if receipt.get("script_sha256") != _sha(FIGURE_SCRIPT):
        raise FinalizeInputError("figure receipt script hash differs from q03_figures_v002.py")
    return {
        "receipt": receipt,
        "receipt_sha256": _sha(FIGURE_RECEIPT),
        "script_sha256": _sha(FIGURE_SCRIPT),
        "figures": {
            _relative(HEIGHT_FIGURE): _sha(HEIGHT_FIGURE),
            _relative(MONTHLY_FIGURE): _sha(MONTHLY_FIGURE),
        },
    }


def _delivery_source(report: dict[str, Any], field: str) -> Path:
    relative = report.get(field)
    if not isinstance(relative, str) or not relative:
        raise FinalizeInputError(f"delivery report lacks {field}")
    path = _local(Q3_OUT / relative)
    if not path.is_file():
        raise FinalizeInputError(f"delivery source is missing: {field}")
    hashes = report.get("sha256")
    expected = hashes.get(relative) if isinstance(hashes, dict) else None
    if not isinstance(expected, str) or _sha(path) != expected.lower():
        raise FinalizeInputError(f"delivery source differs from bound hash: {field}")
    return path


def _validation_evidence(report: dict[str, Any]) -> dict[str, Any]:
    for path in (SEARCH_RULES, CONFIRMATION_FREEZE, PROTOTYPE_REPORT, Q2_PAPER):
        if not _local(path).is_file():
            raise FinalizeInputError(f"required validation evidence is missing: {path}")

    rules = _load_json(SEARCH_RULES)
    low = rules.get("score", {}).get("low", {}) if isinstance(rules, dict) else {}
    fine = rules.get("score", {}).get("fine", {}) if isinstance(rules, dict) else {}
    if (low.get("B"), low.get("n"), low.get("prefix")) != (2, 16, 8):
        raise FinalizeInputError("low search configuration is not frozen 2x16 with prefix 8")
    if (fine.get("B"), fine.get("n"), fine.get("prefix")) != (4, 64, 32):
        raise FinalizeInputError("fine search configuration is not frozen 4x64 with prefix 32")

    freeze = _load_json(CONFIRMATION_FREEZE)
    plan = freeze.get("planned_confirmation", {}) if isinstance(freeze, dict) else {}
    if (
        plan.get("B") != 8
        or plan.get("n") != 256
        or plan.get("levels") != [128, 256]
        or plan.get("time_count") != 60
        or plan.get("actual_mirrors") != 2981
        or plan.get("candidate_and_baseline_paired") is not True
    ):
        raise FinalizeInputError("confirmation freeze is not paired 8x256 with nested 128 prefix")
    if freeze.get("readback_changes") != []:
        raise FinalizeInputError("frozen Excel readback contains field changes")

    prototype = _load_json(PROTOTYPE_REPORT)
    checks = prototype.get("checks") if isinstance(prototype, dict) else None
    expected_check_names = {
        "P01_identity_and_preregistration",
        "P02_roundtrip_0",
        "P02_roundtrip_1",
        *(f"P03_old_new_{index}" for index in range(6)),
        *(f"P04_heterogeneous_{outer}_{inner}" for outer in range(2) for inner in range(3)),
        "P05_immutable_cache_checkpoint",
        "P06_real_runner_zero_certificate_0",
        "P06_real_runner_zero_certificate_1",
    }
    actual_names = {
        item.get("name") for item in checks if isinstance(item, dict)
    } if isinstance(checks, list) else set()
    if (
        prototype.get("all_pass") is not True
        or not isinstance(checks, list)
        or len(checks) != 18
        or actual_names != expected_check_names
        or any(item.get("passed") is not True for item in checks)
    ):
        raise FinalizeInputError("prototype report is not the complete 18-check PASS set")

    candidate_path = _delivery_source(report, "candidate_confirmation_summary")
    baseline_path = _delivery_source(report, "baseline_confirmation_summary")
    candidate = _load_json(candidate_path)
    baseline = _load_json(baseline_path)
    for label, summary in (("candidate", candidate), ("baseline", baseline)):
        coverage = summary.get("coverage", {}) if isinstance(summary, dict) else {}
        if (
            coverage.get("levels_n_per_batch") != [128, 256]
            or coverage.get("batches") != 8
            or coverage.get("times") != 60
            or coverage.get("objects") != 2981
            or coverage.get("final_samples_per_object_time") != 2048
            or coverage.get("complete_time_population") is not True
        ):
            raise FinalizeInputError(f"{label} confirmation coverage differs from freeze")

    low_survival = candidate.get("low_survival", {})
    low_cases = low_survival.get("cases") if isinstance(low_survival, dict) else None
    if (
        low_survival.get("threshold_exclusive") != 100
        or low_survival.get("screened_count") != 2
        or not isinstance(low_cases, list)
        or [(case.get("survive"), case.get("capture")) for case in low_cases]
        != [(39, 36), (62, 62)]
    ):
        raise FinalizeInputError("candidate low-survival cases differ from delivered summary")

    target_pass = candidate.get("target_pass")
    if (
        not isinstance(target_pass, list)
        or len(target_pass) != 13
        or any(not isinstance(row, list) or len(row) != 6 for row in target_pass)
        or any(value is not True for row in target_pass for value in row)
        or candidate.get("all_table_items_precision_met") is not True
    ):
        raise FinalizeInputError("candidate does not contain 78 passed table precision items")

    work = candidate.get("conservative_work_indicator")
    point = candidate.get("point")
    if (
        not isinstance(work, list)
        or not isinstance(point, list)
        or len(work) != 13
        or len(point) != 13
        or any(not isinstance(row, list) or len(row) != 6 for row in work + point)
    ):
        raise FinalizeInputError("candidate point/work matrices are not 13 by 6")
    max_efficiency_u = max(_finite(value, "efficiency work indicator") for row in work for value in row[:4])
    relative_power_q_u = []
    for row_index, (work_row, point_row) in enumerate(zip(work, point)):
        for column in (4, 5):
            denominator = abs(_finite(point_row[column], f"point[{row_index},{column}]"))
            if denominator <= 0.0:
                raise FinalizeInputError("relative P/q work indicator has non-positive denominator")
            relative_power_q_u.append(
                _finite(work_row[column], f"work[{row_index},{column}]") / denominator
            )
    max_relative_power_q_u = max(relative_power_q_u)
    if not math.isclose(max_efficiency_u, 0.00035746639128648284, rel_tol=0.0, abs_tol=1e-16):
        raise FinalizeInputError("maximum candidate efficiency work indicator differs from delivery")
    if not math.isclose(max_relative_power_q_u, 0.00047429377499650125, rel_tol=0.0, abs_tol=1e-16):
        raise FinalizeInputError("maximum relative P/q work indicator differs from delivery")

    geometry_path = candidate_path.parent.parent / "geometry.json"
    geometry = _load_json(geometry_path)
    minima = geometry.get("minima", {}) if isinstance(geometry, dict) else {}
    expected_minima = freeze.get("readback_geometry", {}).get("minima")
    if geometry.get("accepted") is not True or minima != expected_minima:
        raise FinalizeInputError("candidate geometry and frozen Excel readback geometry differ")
    if (
        minima.get("pair_count_checked") != 4441690
        or not math.isclose(_finite(minima.get("pair_margin_m"), "pair margin"), 0.009999999932485792, rel_tol=0.0, abs_tol=1e-15)
        or _finite(minima.get("ground_margin_m"), "ground margin") != 2.675
    ):
        raise FinalizeInputError("candidate geometry minima differ from delivered values")

    q2_text = Q2_PAPER.read_text(encoding="utf-8")
    for snippet in (
        "### 2.1 共同光学假设",
        "## 4 复用的光学评价模型",
        "\\beta=0.00465",
        "按立体角均匀",
        "指向光源",
    ):
        if snippet not in q2_text:
            raise FinalizeInputError(f"accepted Q2 source lacks expected common definition: {snippet}")

    return {
        "sources": {
            _relative(SEARCH_RULES): _sha(SEARCH_RULES),
            _relative(CONFIRMATION_FREEZE): _sha(CONFIRMATION_FREEZE),
            _relative(PROTOTYPE_REPORT): _sha(PROTOTYPE_REPORT),
            _relative(candidate_path): _sha(candidate_path),
            _relative(baseline_path): _sha(baseline_path),
            _relative(geometry_path): _sha(geometry_path),
            _relative(Q2_PAPER): _sha(Q2_PAPER),
        },
        "search": {"low": [2, 16, 8], "fine": [4, 64, 32]},
        "confirmation": {"batches": 8, "n": 256, "prefix": 128, "times": 60, "mirrors": 2981},
        "prototype_passed_checks": 18,
        "old_scalar_compatibility_checks": 6,
        "new_heterogeneous_checks": 6,
        "precision_items_passed": 78,
        "low_survival": low_survival,
        "max_efficiency_u": max_efficiency_u,
        "max_relative_power_q_u": max_relative_power_q_u,
        "geometry_minima": minima,
        "excel_readback_field_changes": 0,
    }


def _revised_method() -> tuple[str, list[dict[str, str]]]:
    changes = [
        {
            "location": "第3问方法正文，N04终止平面引导句",
            "reason": "原式沿用源点符号x，容易误读为源点本身位于终止平面；改用平面任意点y。",
            "before": OLD_N04_LEAD,
            "after": NEW_N04_LEAD,
            "basis": "第2问已验收的N04后切平面定义和D046沿用同一光学核。",
        },
        {
            "location": "第3问方法正文，N04终止平面公式",
            "reason": "区分反射源点与终止平面上的任意点，不改变后切平面的几何位置。",
            "before": OLD_N04_PLANE,
            "after": NEW_N04_PLANE,
            "basis": "接收体包围球后切平面方程；本次只消除符号歧义。",
        },
        {
            "location": "第3问方法正文，异宽镜几何上限说明",
            "reason": "说明6.70 m是所有镜共同受限的宽度上限，避免误读为一般场界上限。",
            "before": OLD_CAP_WORDING,
            "after": NEW_CAP_WORDING,
            "basis": "groups-v001.json的all_pair_actual_width_upper_bound_m及六个组上限。",
        },
        {
            "location": "第3问方法正文，分组秩定义",
            "reason": "明确径向排序采用从0开始的秩，消除组边界的下标歧义。",
            "before": OLD_RANK_WORDING,
            "after": NEW_RANK_WORDING,
            "basis": "q03_design_v001.py的确定性径向秩分组实现及groups-v001.json。",
        },
        {
            "location": "第3问第3节，共同光学输入与方向约定",
            "reason": "把复用来源、圆锥半角、立体角抽样、DNI参考面和方向约定写成可独立阅读的定义。",
            "before": OLD_PHYSICS_LEAD,
            "after": NEW_PHYSICS_LEAD,
            "basis": "已验收第2问v002第2.1节和第4节；本问未增加物理输入。",
        },
        {
            "location": "第3问第3节，完整圆锥积分适用条件",
            "reason": "说明E[g]=c只在正入射、地平线、正投影分母和正终点条件同时成立时使用。",
            "before": OLD_AFTER_G,
            "after": NEW_AFTER_G,
            "basis": "第2问v002光学评价口径及Q3逐设计60时点前提检查。",
        },
        {
            "location": "第3问第3节，有限样本零与未定义状态",
            "reason": "区分必需分母不足导致的未定义、正存活下的估计零和需要完整证书支持的真实零。",
            "before": OLD_ZERO_WORDING,
            "after": NEW_ZERO_WORDING,
            "basis": "确认summary的状态通道和prototype中的真实零证书检查。",
        },
        {
            "location": "第3问第4节，搜索抽样层级",
            "reason": "补足实际low/fine批数、每批样本数、嵌套前缀及有限样本零的处理。",
            "before": OLD_SEARCH_METHOD,
            "after": NEW_SEARCH_METHOD,
            "basis": "搜索规则冻结-v001.json与实际14个low、4个fine搜索轨迹。",
        },
        {
            "location": "第3问第4节，独立确认与配对随机流",
            "reason": "补足最终8×256、128前缀不重复计数及候选—基线共同随机流的实际设计。",
            "before": OLD_CONFIRM_METHOD,
            "after": NEW_CONFIRM_METHOD,
            "basis": "最终候选与确认冻结-v001.json及两份确认summary。",
        },
    ]
    method = paper.METHOD
    for change in changes:
        method = _replace_once(
            method,
            change["before"],
            change["after"],
            change["location"],
        )
    return method, changes


def _fmt(value: float, digits: int) -> str:
    return f"{value:.{digits}f}"


def _fine_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "表S5　完整60时点较精搜索比较（搜索层）",
        "",
        "| 设计 | 总面积（m²） | 年均功率评分（kW） | 单位面积功率评分（kW/m²） | 配对搜索SE（kW/m²） | 功率正余量（kW） |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['name']} | {_fmt(row['area'],4)} | "
            f"{_fmt(row['P_score_kw'],4)} | {_fmt(row['q_score_kw_m2'],7)} | "
            f"{row['paired_search_se']:.7e} | {_fmt(row['power_search_margin'],4)} |"
        )
    return "\n".join(lines)


def _height_figure_block() -> str:
    figure = HEIGHT_FIGURE.resolve().as_posix()
    return "\n".join(
        [
            FINALIZE_MARKER,
            "",
            f"![Q3F013镜面高度空间分布]({figure})",
            "图1　Q3F013镜面高度的空间分布",
            "",
            "图1以颜色表示逐镜尺寸中的高度 \(h_i\)，不是安装高度 \(z_i\)。外圆、塔周虚线圆和塔位符号分别辅助核对固定场界、禁布区及塔位；该图用于说明异尺寸参数在固定镜位上的空间分布，不能代替全对间距核验。",
            "",
        ]
    )


def _search_section(rows: list[dict[str, Any]], low_count: int) -> str:
    selected = next(row for row in rows if row["name"] == "Q3R013")
    return "\n".join(
        [
            "### 5.4 有限搜索的分层比较",
            "",
            f"实际搜索先以2批×16条源样本完成{low_count}个全场低样本候选，再以4批×64条源样本比较4个对象；两层的半量前缀分别为每批8条和32条。所有对象均覆盖2981面镜和规定60时点，批内前缀与终值嵌套且不重复计数。两层只在各自层内排序，不把低样本和较精数值混排。必需分母不足造成的抽样零保留为未定义并促使增样；正存活分母下的零接收保留为估计零，但不作为真实零或额定通过证据。",
            "",
            _fine_table(rows),
            "",
            f"表S5是候选选择阶段的搜索层结果，不是最终独立确认。Q3R013在4个较精对象中的单位面积功率评分最高；其功率评分扣除搜索工作量后仅保留 {_fmt(selected['power_search_margin'],3)} kW 正余量，低于搜索前预先登记的额外30 kW软偏好。该30 kW仅用于风险排序，并非额定功率硬门禁；Q3R013仍满足预先冻结的正余量条件，且低样本与较精功率变化较小，因此按原单位面积功率目标选择它，并以交付精度身份Q3F013进入未参与调参的新独立确认。",
            "",
            "这一选择只说明为什么安排Q3F013接受确认，不提前证明其额定可行或相对改进。Q3R010和Q3R012没有接受本轮最终独立确认，不能依据表S5称为已确认可行设计；Q3R000的正式基线状态也只由后续新配对确认给出，不由该搜索表给出。",
            "",
        ]
    )


def _monthly_figure_block() -> str:
    figure = MONTHLY_FIGURE.resolve().as_posix()
    return "\n".join(
        [
            f"![Q3F013与R027月度单位面积功率]({figure})",
            "图2　Q3F013与R027在规定月样本上的单位面积输出热功率",
            "",
            "图2中的实线圆点及误差棒分别为Q3F013的月度点估计和数值工作指标 \(U_Q\)，虚线圆点为同一新配对数据下R027的月度点估计。误差棒不是严格置信区间、物理误差界或工程保证；折线只连接12个规定月份21日的样本均值，不表示逐日连续变化。正式相对改进仍以年度配对差及其差值工作指标判断。",
            "",
        ]
    )


def _validation_section(evidence: dict[str, Any]) -> str:
    low_cases = evidence["low_survival"]["cases"]
    max_efficiency_u = evidence["max_efficiency_u"]
    max_relative = evidence["max_relative_power_q_u"]
    minima = evidence["geometry_minima"]
    return "\n".join(
        [
            "### 5.5 实现、精度与清单核验",
            "",
            "异尺寸接口原型的18项人工测试全部通过，其中包括6个旧统一尺寸兼容组合和6个新异尺寸组合。"
            "最终候选与R027新基线分别完整评价60个规定时点、2981面镜和8个独立批次；每批终值采用256条源样本，"
            "128条嵌套前缀只作相关诊断，两份确认按稳定镜身份、时点和批次使用共同随机流。",
            "",
            f"Q3F013共有{evidence['precision_items_passed']}项题表精度检查通过。全部月度及年度效率项中的最大数值工作指标为 "
            f"{max_efficiency_u:.10f}；功率和单位面积功率的最大相对工作指标为 {max_relative:.10f}，即 "
            f"{100.0 * max_relative:.6f}%。这些数值只刻画既定模型下的抽样、批间、前缀、原始积分替代和低存活敏感性，"
            "不表示物理误差。",
            "",
            f"合并确认中有2个对象—时点组合的存活数低于100，存活/接收计数分别为 "
            f"{low_cases[0]['survive']}/{low_cases[0]['capture']} 和 "
            f"{low_cases[1]['survive']}/{low_cases[1]['capture']}。阈值100是预先设定的数值筛查阈值，不是物理边界；"
            "相应全范围影响量按各镜实际面积进入功率和单位面积功率工作指标。两个组合均有正存活分母，其状态为估计值，"
            "未被改写为真实零或删除。",
            "",
            f"逐镜清单回读的字段变化数为{evidence['excel_readback_field_changes']}。几何核验实际检查 "
            f"{minima['pair_count_checked']:,} 个无序镜对，最小间距余量为 {minima['pair_margin_m']:.11f} m，"
            f"最小离地净空为 {minima['ground_margin_m']:.3f} m；这些数值来自冻结设计和清单回读的同一几何报告。",
            "",
        ]
    )


def _postprocess_markdown(
    source: str,
    rows: list[dict[str, Any]],
    low_count: int,
    evidence: dict[str, Any],
) -> str:
    if FINALIZE_MARKER in source:
        raise FinalizeInputError("formal Markdown is already finalized")
    text = source
    text = _replace_once(
        text,
        "### 5.4 文件与重建验证",
        "### 5.6 文件与重建验证",
        "renumber file/rebuild section after search and validation additions",
    )
    formal_anchor = "### 5.2 正式题表与额定确认"
    text = _replace_once(
        text,
        formal_anchor,
        _height_figure_block() + formal_anchor,
        "insert height figure",
    )
    files_anchor = "### 5.6 文件与重建验证"
    text = _replace_once(
        text,
        files_anchor,
        _search_section(rows, low_count) + _validation_section(evidence) + files_anchor,
        "insert fine comparison and validation evidence",
    )
    table3_anchor = f"表3　{EXPECTED_SELECTED} 定日镜场设计参数"
    text = _replace_once(
        text,
        table3_anchor,
        _monthly_figure_block() + table3_anchor,
        "insert monthly figure",
    )
    return text.rstrip() + "\n"


def _make_final_tex(source: Path, target: Path, record: Path) -> dict[str, Any]:
    """Reuse the accepted converter with a six-column S5 layout override."""
    import q02_repair_paper_tex_v002 as converter

    original_table_tex = converter.table_tex

    def q03_table_tex(rows: list[list[str]], caption: str) -> list[str]:
        if not caption.startswith("表S5") or len(rows[0]) != 6:
            return original_table_tex(rows, caption)
        n = 6
        ratios = [0.10, 0.18, 0.18, 0.20, 0.17, 0.17]
        columns = "".join(
            r">{\raggedright\arraybackslash}p{" + f"{ratio:.6f}"
            + r"\dimexpr\linewidth-" + str(2 * n) + r"\tabcolsep\relax}"
            for ratio in ratios
        )
        header = " & ".join(converter.inline(cell) for cell in rows[0]) + r" \\"
        result = [
            r"\par\medskip\noindent\begin{minipage}{\linewidth}",
            r"\small",
            r"\textbf{" + converter.inline(caption) + r"}\par\smallskip",
            r"\begin{tabular}{" + columns + "}",
            r"\toprule",
            header,
            r"\midrule",
        ]
        result.extend(
            " & ".join(converter.inline(cell) for cell in row) + r" \\"
            for row in rows[1:]
        )
        result.extend(
            [r"\bottomrule", r"\end{tabular}", r"\end{minipage}\par\medskip"]
        )
        return result

    converter.table_tex = q03_table_tex
    try:
        result = paper._make_tex(source, target, record)
    finally:
        converter.table_tex = original_table_tex
    result["q03_s5_layout"] = {
        "columns": 6,
        "ratios": [0.10, 0.18, 0.18, 0.20, 0.17, 0.17],
        "scope": "document-only override; accepted converter source unchanged",
    }
    return result


def _revision_markdown(
    method_changes: list[dict[str, str]],
    before_md_sha: str,
    after_md_sha: str,
    before_tex_sha: str,
    after_tex_sha: str,
    fine_sha: str,
    decisions_sha: str,
    decision_section_sha: str,
    figures: dict[str, Any],
    evidence: dict[str, Any],
) -> str:
    lines = [
        "# 第3问写稿修订记录 v001",
        "",
        "> 本记录对应尚未由用户验收的第3问正式稿后处理。只修改论文表达、证据表和图文对应，不改变设计、光学统计、确认结果或交付清单。未执行TeX编译、PDF渲染或新增数值计算。",
        "",
        "## 1 符号与几何措辞修订",
        "",
    ]
    for index, change in enumerate(method_changes, 1):
        before = change["before"]
        after = change["after"]
        if before.startswith("(") and "\\boldsymbol" in before:
            before = f"\\({before}\\)"
            after = f"\\({after}\\)"
        lines.extend(
            [
                f"### M{index:02d}　{change['location']}",
                "",
                f"修改原因：{change['reason']}",
                "",
                "修改前：",
                "",
                f"> {before}",
                "",
                "修改后：",
                "",
                f"> {after}",
                "",
                f"依据：{change['basis']}",
                "",
            ]
        )
    lines.extend(
        [
            "## 2 搜索过程、表格与图件补充",
            "",
            "### M10　增加分层搜索比较并压缩搜索表",
            "",
            "修改原因：原基础正文直接从冻结候选进入正式确认结果，没有展示14个low和4个fine的真实筛选层次，也没有解释Q3R013的较窄功率余量与30 kW软偏好之间的关系。",
            "",
            "修改前：第5节仅含冻结候选、正式题表、配对确认和文件重建说明；首次后处理表S5含10列，并在正文直接出现内部决策编号。",
            "",
            "修改后：新增第5.4节和6列表S5，仅列4个完整60时点fine结果；正文给出2×16和4×64的实际层级，不把low与fine数值混排。明确Q3R013的8.638 kW为搜索层正余量，30 kW为预设软偏好，正式正文不出现内部决策编号；未确认的Q3R010、Q3R012不称为可行设计。",
            "",
            "依据：`comparison-fine-v001.json`、`scores.jsonl`及决策记录D046。",
            "",
            "### M11　增加两张本地图",
            "",
            "修改原因：补充逐镜异尺寸的空间分布和候选与基线的月度单位面积功率关系，同时把图示范围与正式年度判据分开。",
            "",
            "修改前：基础正文没有第3问图件。",
            "",
            "修改后：新增图1“Q3F013镜面高度的空间分布”和图2“Q3F013与R027在规定月样本上的单位面积输出热功率”。图1明确颜色为尺寸高度 \(h_i\)，图2按实际绘图实现说明候选与基线均为圆点，并明确误差棒为数值工作指标而非严格置信或物理误差界。",
            "",
            "依据：`q03_figures_v002.py`生成的两张本地图及`图表生成核验-v001.json`。v001因本地缺少matplotlib而失败，未通过联网或安装依赖规避。",
            "",
            "### M12　增加实现、精度与清单核验",
            "",
            "修改原因：基础正文没有集中报告原型兼容核验、最终覆盖、低存活对象、全部题表精度和逐镜清单几何回读，容易把数值工作指标误解成物理误差。",
            "",
            "修改前：仅在正式题表和文件重建段概括确认通过。",
            "",
            f"修改后：新增第5.5节，报告18项原型检查、6个旧兼容与6个新异尺寸组合、候选和基线各8×256的完整确认、{evidence['precision_items_passed']}项精度通过、39和62的低存活计数、最大效率工作指标{evidence['max_efficiency_u']:.10f}、最大功率/单位面积功率相对工作指标{evidence['max_relative_power_q_u']:.10f}，以及4,441,690个无序镜对、间距余量、离地净空和Excel回读零字段变化。",
            "",
            "依据：prototype/report-v001.json、两份confirmation/summary.json、候选geometry.json及最终候选与确认冻结-v001.json。",
            "",
            "### M13　同步节号、六列表格版式和TeX",
            "",
            "修改原因：新增搜索和核验小节后，文件与重建小节需顺延；表S5从10列缩为6列后需使用匹配的列宽，并重新建立Markdown与TeX对应。首次运行还因Windows换行转换导致内存LF哈希与落盘字节哈希误比。",
            "",
            "修改前：第5.2—5.4节依次为正式题表、配对比较、文件与重建验证。",
            "",
            "修改后：保留第5.2节正式题表和第5.3节配对比较，新增第5.4节有限搜索分层比较和第5.5节核验，原文件与重建验证顺延为第5.6节；不修改既有转换器源码，仅在本次调用中为6列表S5设置列宽。恢复逻辑改为比较换行归一后的文本内容，并以实际落盘文件哈希绑定Markdown与TeX。",
            "",
            "## 3 版本和证据绑定",
            "",
            f"- Markdown修改前SHA-256：`{before_md_sha}`",
            f"- Markdown修改后SHA-256：`{after_md_sha}`",
            f"- TeX初次生成SHA-256：`{before_tex_sha}`",
            f"- TeX同步后SHA-256：`{after_tex_sha}`",
            f"- fine比较JSON SHA-256：`{fine_sha}`",
            f"- 决策记录文件SHA-256：`{decisions_sha}`",
            f"- D046节文本SHA-256：`{decision_section_sha}`",
            f"- 图表生成核验SHA-256：`{figures['receipt_sha256']}`",
        ]
    )
    for path, digest in figures["figures"].items():
        lines.append(f"- 图件 `{path}` SHA-256：`{digest}`")
    for path, digest in evidence["sources"].items():
        lines.append(f"- 核验证据 `{path}` SHA-256：`{digest}`")
    lines.extend(
        [
            "",
            "本记录不把fine搜索评分改写为最终确认结果。正式额定功率、题表精度和相对改进仍只来自delivery/report.json绑定的候选确认、R027新基线确认、配对比较和独立重建。",
            "",
        ]
    )
    return "\n".join(lines)


def run(report_path: Path = REPORT) -> dict[str, Any]:
    """Build and post-process the formal Q3 Markdown/TeX from delivered files."""
    if _local(report_path) != REPORT.resolve():
        raise FinalizeInputError("v001 finalizer accepts only the frozen default delivery report")
    if REVISION_RECORD.exists() or FINALIZE_RECORD.exists():
        raise FileExistsError("Q3 paper finalization v001 already has an output record")

    report = _bound_report()
    decision_section, decision_section_sha = _decision_section()
    trace = _trace_counts(report)
    fine_rows = _fine_rows(trace)
    figure_binding = _figure_binding(report)
    validation_evidence = _validation_evidence(report)
    revised_method, method_changes = _revised_method()
    markdown_path = paper.FORMAL_MD.resolve()
    tex_path = paper.FORMAL_TEX.resolve()
    original_method = paper.METHOD
    try:
        paper.METHOD = revised_method
        context = paper._formal_context(report)
        expected_base_markdown = paper._formal_markdown(context).rstrip() + "\n"
    finally:
        paper.METHOD = original_method
    revised_markdown = _postprocess_markdown(
        expected_base_markdown,
        fine_rows,
        len(trace["low"]),
        validation_evidence,
    )

    recovered_from_failed_run = False
    if markdown_path.exists():
        current_markdown = markdown_path.read_text(encoding="utf-8")
        if current_markdown == revised_markdown and FINALIZE_MARKER in current_markdown:
            recovered_from_failed_run = True
            if not FAILURE_EVIDENCE.is_dir():
                raise FinalizeInputError("failed-run draft exists but failure evidence was not preserved")
            base_generation = _load_json(paper.PAPER_RECORD)
        elif (
            FINALIZE_MARKER in current_markdown
            and FAILED_MARKDOWN_SNAPSHOT.is_file()
            and current_markdown == FAILED_MARKDOWN_SNAPSHOT.read_text(encoding="utf-8")
        ):
            recovered_from_failed_run = True
            base_generation = _load_json(paper.PAPER_RECORD)
        elif current_markdown == expected_base_markdown:
            base_generation = _load_json(paper.PAPER_RECORD)
        else:
            raise FileExistsError(
                "existing Q3 formal Markdown is neither the deterministic base nor the preserved failed-run final draft"
            )
    else:
        original_method = paper.METHOD
        try:
            paper.METHOD = revised_method
            base_generation = paper.generate(REPORT)
        finally:
            paper.METHOD = original_method
        if base_generation.get("formal") is not True:
            raise FinalizeInputError(
                "base paper generator did not produce a formal manuscript: "
                + str(base_generation.get("reason_if_incomplete"))
            )
        current_markdown = markdown_path.read_text(encoding="utf-8")
        if current_markdown != expected_base_markdown:
            raise FinalizeInputError("base paper Markdown differs from deterministic in-memory assembly")

    if not isinstance(base_generation, dict) or base_generation.get("formal") is not True:
        raise FinalizeInputError("base paper generation record is unavailable")
    source_hashes = base_generation.get("source_hashes")
    if not isinstance(source_hashes, dict):
        raise FinalizeInputError("base paper generation record lacks source hashes")
    before_md_sha = source_hashes.get("markdown")
    before_tex_sha = source_hashes.get("tex")
    if not isinstance(before_md_sha, str) or not isinstance(before_tex_sha, str):
        raise FinalizeInputError("base paper generation hashes are missing")
    if not tex_path.is_file():
        raise FinalizeInputError("base Q3 TeX is missing")

    rollback_markdown = current_markdown
    rollback_tex = tex_path.read_bytes()
    rollback_correspondence = CORRESPONDENCE.read_bytes() if CORRESPONDENCE.exists() else None
    if current_markdown != revised_markdown:
        markdown_path.write_text(revised_markdown, encoding="utf-8")
    try:
        tex_result = _make_final_tex(markdown_path, tex_path, CORRESPONDENCE)
    except Exception:
        markdown_path.write_text(rollback_markdown, encoding="utf-8")
        tex_path.write_bytes(rollback_tex)
        if rollback_correspondence is None:
            if CORRESPONDENCE.exists():
                CORRESPONDENCE.unlink()
        else:
            CORRESPONDENCE.write_bytes(rollback_correspondence)
        raise

    after_md_sha = _sha(markdown_path)
    after_tex_sha = _sha(tex_path)
    if markdown_path.read_text(encoding="utf-8") != revised_markdown:
        raise FinalizeInputError("formal Markdown readback differs from assembled text")
    if tex_result.get("source_sha256") != after_md_sha or tex_result.get("tex_sha256") != after_tex_sha:
        raise FinalizeInputError("final Markdown/TeX correspondence hashes disagree")

    generation_record = _load_json(paper.PAPER_RECORD)
    generation_record["postprocessed_by"] = _relative(Path(__file__))
    generation_record["pre_finalize_markdown_sha256"] = before_md_sha
    generation_record["pre_finalize_tex_sha256"] = before_tex_sha
    generation_record["source_hashes"]["markdown"] = after_md_sha
    generation_record["source_hashes"]["tex"] = after_tex_sha
    generation_record["tex_conversion"] = tex_result
    generation_record["finalization_record"] = _relative(FINALIZE_RECORD)
    generation_record["compilation_performed"] = False
    generation_record["pdf_rendering_performed"] = False
    paper.PAPER_RECORD.write_text(
        json.dumps(generation_record, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    revision = _revision_markdown(
        method_changes,
        before_md_sha,
        after_md_sha,
        before_tex_sha,
        after_tex_sha,
        _sha(FINE_COMPARISON),
        _sha(DECISIONS),
        decision_section_sha,
        figure_binding,
        validation_evidence,
    )
    _write_new(REVISION_RECORD, revision)

    recovery_payload = None
    if recovered_from_failed_run:
        recovery_payload = {
            "schema": "q03-paper-finalize-failure-recovery-v001",
            "scope": "Q3 manuscript Markdown/TeX and document records only",
            "original_failure": "formal Markdown byte hash was compared with an LF-only in-memory hash after Windows newline translation",
            "preserved_before_repair": {
                "finalizer_source": _relative(
                    FAILURE_EVIDENCE / "q03_paper_finalize_v001-before-newline-fix.py"
                ),
                "finalizer_source_sha256": _sha(
                    FAILURE_EVIDENCE / "q03_paper_finalize_v001-before-newline-fix.py"
                ),
                "failed_markdown": _relative(FAILED_MARKDOWN_SNAPSHOT),
                "failed_markdown_sha256": _sha(FAILED_MARKDOWN_SNAPSHOT),
                "failed_tex": _relative(
                    FAILURE_EVIDENCE / "第3问-模型建立与求解-v001-after-failed-run.tex"
                ),
                "failed_tex_sha256": _sha(
                    FAILURE_EVIDENCE / "第3问-模型建立与求解-v001-after-failed-run.tex"
                ),
            },
            "repair": "compare normalized read_text content, preserve actual on-disk hashes for binding, and allow only the exact preserved failed draft as a resumable predecessor",
            "recovered_outputs": {
                _relative(markdown_path): after_md_sha,
                _relative(tex_path): after_tex_sha,
                _relative(CORRESPONDENCE): _sha(CORRESPONDENCE),
            },
            "optical_or_search_computation_performed": False,
            "tex_compilation_or_pdf_rendering_performed": False,
        }
        _write_json_new(RECOVERY_RECORD, recovery_payload)

    record = {
        "schema": "q03-paper-finalization-v001",
        "formal_delivery_status": report["status"],
        "selected_design": report["selected_design"],
        "base_generation": base_generation,
        "recovered_from_failed_run": recovered_from_failed_run,
        "failure_evidence": _relative(FAILURE_EVIDENCE) if recovered_from_failed_run else None,
        "failure_recovery_record": _relative(RECOVERY_RECORD) if recovery_payload else None,
        "failure_recovery_record_sha256": _sha(RECOVERY_RECORD) if recovery_payload else None,
        "runtime_method_changes": method_changes,
        "template_source_unchanged": True,
        "template_source": _relative(Path(paper.__file__)),
        "template_source_sha256": _sha(Path(paper.__file__)),
        "markdown": {
            "path": _relative(markdown_path),
            "before_sha256": before_md_sha,
            "after_sha256": after_md_sha,
        },
        "tex": {
            "path": _relative(tex_path),
            "before_sha256": before_tex_sha,
            "after_sha256": after_tex_sha,
            "correspondence": _relative(CORRESPONDENCE),
            "correspondence_sha256": _sha(CORRESPONDENCE),
        },
        "fine_table_binding": {
            "source": _relative(FINE_COMPARISON),
            "source_sha256": _sha(FINE_COMPARISON),
            "row_names": [row["name"] for row in fine_rows],
            "row_count": len(fine_rows),
            "scope": "four full-60-time fine search rows; not final confirmation and not mixed with low",
        },
        "search_trace_binding": {
            "source": _relative(trace["path"]),
            "source_sha256": _sha(trace["path"]),
            "low_rows": len(trace["low"]),
            "fine_rows": len(trace["fine"]),
        },
        "selection_basis": {
            "source": _relative(DECISIONS),
            "source_sha256": _sha(DECISIONS),
            "D046_section_sha256": decision_section_sha,
            "D046_section": decision_section,
            "soft_margin_preference_kw": 30.0,
            "Q3R013_search_positive_margin_kw": next(
                row["power_search_margin"] for row in fine_rows if row["name"] == "Q3R013"
            ),
        },
        "figure_binding": figure_binding,
        "validation_evidence": validation_evidence,
        "delivery_report": _relative(REPORT),
        "delivery_report_sha256": _sha(REPORT),
        "delivery_source_hashes": report["sha256"],
        "revision_record": _relative(REVISION_RECORD),
        "revision_record_sha256": _sha(REVISION_RECORD),
        "finalizer_source": _relative(Path(__file__)),
        "finalizer_source_sha256": _sha(Path(__file__)),
        "numerical_or_optical_computation_performed_by_finalizer": False,
        "figure_generation_performed_by_finalizer": False,
        "tex_compilation_performed_by_finalizer": False,
        "pdf_rendering_performed_by_finalizer": False,
        "internet_or_git_used_by_finalizer": False,
    }
    _write_json_new(FINALIZE_RECORD, record)
    return record


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "schema": result["schema"],
                "selected_design": result["selected_design"],
                "markdown": result["markdown"],
                "tex": result["tex"],
                "tex_compilation_performed": False,
            },
            ensure_ascii=False,
        )
    )
