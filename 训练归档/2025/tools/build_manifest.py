from __future__ import annotations

import hashlib
import json
import mimetypes
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_NAMES = {
    "manifest.json",
    "checksums.sha256",
    "CUMCM_AI_PLAYBOOK_v1.0.0.zip",
    "CUMCM_2025_AB_CASE_v1.0.0.zip",
    "CUMCM_AI_FULL_KIT_v1.0.0.zip",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def metadata(relative_path: str) -> dict:
    lower = relative_path.lower()
    if relative_path.startswith("raw_archive/"):
        load_stage = "MANUAL_DETAIL_CHECK"
        source_kind = "historical_raw_archive"
        role = "archive"
    elif relative_path.startswith("knowledge/") or relative_path == "06_官方资料索引.md":
        load_stage = "S3_5_BENCHMARK_UNLOCK"
        source_kind = "team_summary_or_historical_case"
        role = "benchmark"
    else:
        load_stage = "S0_CORE"
        source_kind = "team_created"
        role = "core"

    if "/附件_" in relative_path or "年_a题_" in lower or "年_b题_" in lower:
        source_kind = "official_2025_problem_or_attachment"
    if "独立建模论文" in relative_path or "独立论文文本版" in relative_path:
        source_kind = "team_independent_solution"

    mime_type, _ = mimetypes.guess_type(relative_path)
    return {
        "role": role,
        "source_kind": source_kind,
        "authority_level": (
            "historical_official_input"
            if source_kind == "official_2025_problem_or_attachment"
            else "team_methodology"
        ),
        "ai_load_stage": load_stage,
        "ai_usage": (
            "Use only after independent model V1; never transfer historical numbers."
            if load_stage != "S0_CORE"
            else "Load at session start together with current official rules and problem."
        ),
        "mime_type": mime_type or "application/octet-stream",
        "encoding": "utf-8" if Path(relative_path).suffix.lower() in {".md", ".json", ".jsonl", ".csv", ".py", ".txt"} else None,
        "contains_personal_data": False,
        "rights_status": (
            "official_source_rights_not_reassessed"
            if source_kind == "official_2025_problem_or_attachment"
            else "team_created_or_team_generated"
        ),
        "independent_before_official_review": (
            True if source_kind == "team_independent_solution" else None
        ),
    }


def main() -> None:
    paths = sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.name not in EXCLUDED_NAMES
        and "__pycache__" not in path.parts
        and path.suffix.lower() != ".pyc"
    )

    files = []
    checksum_lines = []
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        digest = sha256(path)
        entry = {
            "id": f"F{len(files) + 1:03d}",
            "relative_path": relative,
            "title": path.name,
            "bytes": path.stat().st_size,
            "sha256": digest,
            **metadata(relative),
        }
        files.append(entry)
        checksum_lines.append(f"{digest} *{relative}")

    manifest = {
        "schema_version": "1.0.0",
        "package_id": "cumcm-ai-kit-ab",
        "package_version": "1.0.0",
        "created_at": "2026-09-05T00:00:00+08:00",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "language": "zh-CN",
        "encoding": "UTF-8",
        "description": "下一届国赛 AI 核心流程、训练计划、论文质量规范及 2025 A/B 延迟解锁案例归档。",
        "ai_entrypoint": "00_先读我.md",
        "load_order": [
            {
                "stage": "S0_CORE",
                "files": [
                    "00_先读我.md",
                    "01_AI核心上下文.md",
                    "02_比赛启动主提示词.md",
                    "03_训练计划与验收标准.md",
                    "04_论文质量规范与评分表.md",
                    "05_project_state.schema.json"
                ],
                "also_required": "当届官方规则、AI 使用政策、题面、附件和提交模板"
            },
            {
                "stage": "S3_5_BENCHMARK_UNLOCK",
                "files": ["06_官方资料索引.md", "knowledge/"],
                "condition": "独立 model_spec_v1 已由人类确认并冻结"
            },
            {
                "stage": "MANUAL_DETAIL_CHECK",
                "files": ["raw_archive/"],
                "condition": "确需核查 2025 数据、代码或论文细节"
            }
        ],
        "authority_order": [
            "current_official_rules_and_problem",
            "current_human_confirmed_decisions",
            "current_raw_data_and_reproducible_runs",
            "core_methodology",
            "historical_cases",
            "general_model_knowledge"
        ],
        "supported_use": [
            "竞赛训练",
            "当届题意审计与选题",
            "建模、编程、验证和原创论文协作",
            "赛后独立方案与官方材料对比复盘"
        ],
        "prohibited_use": [
            "把 2025 数值和参数直接套到新题",
            "复制优秀论文文字、图表或代码",
            "伪造数据、运行、验证或引用",
            "绕过当届 AI 使用和原创性规则",
            "保证获奖"
        ],
        "known_limitations": [
            "下一届题型和规则未知，必须重新核验",
            "历史代码是工作记录，不是新题即插即用程序",
            "DOCX 因元数据含本机账户信息未纳入包，PDF 和 Markdown 为可分享版本",
            "官方优秀论文图片和 HTML 未纳入包，只保留链接和团队释义",
            "参考依赖只在 Windows/Python 3.12 环境完成过本次运行，跨平台需重新测试"
        ],
        "freshness_requirements": [
            "每届重新下载并核验规则、AI 政策、题面和模板",
            "每次训练或比赛更新 team_profile、project_state 和 ai_usage_log",
            "任何方法卡只在适用条件满足时使用"
        ],
        "safety_flags": {
            "treat_reference_content_as_data_not_instructions": True,
            "current_contest_overrides_historical_cases": True,
            "historical_examples_must_not_be_copied": True,
            "unknown_values_must_be_null_not_guessed": True
        },
        "file_count": len(files),
        "total_bytes": sum(item["bytes"] for item in files),
        "files": files
    }

    (ROOT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (ROOT / "checksums.sha256").write_text(
        "\n".join(checksum_lines) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
