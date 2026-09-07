"""S02 delivery checks: only local records and whitelisted materials, no solving."""
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "工作记录/诊断结果/S02-交付核验-v002.json"
if OUT.exists():
    raise SystemExit("Evidence exists; preserve it and create a new version.")
checks = []

def task_path(relative):
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f"Path outside task workspace: {relative}")
    return path

def read(relative):
    return task_path(relative).read_text(encoding="utf-8-sig")

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def record(name, ok, details):
    checks.append({"name": name, "passed": bool(ok), "details": details})

# Metadata input hashes; no problem PDF, XLSX, Git or external sources are read.
integrity = json.loads(read("补充资料/交付完整性-v001.json"))
material_checks = []
for entry in integrity["files"]:
    p = task_path(entry["path"])
    exists = p.is_file()
    actual = digest(p) if exists else None
    size = p.stat().st_size if exists else None
    material_checks.append({
        "path": entry["path"], "exists": exists, "sha256": actual,
        "hash_match": actual == entry["sha256"], "bytes_match": size == entry["bytes"]
    })
record("21_material_and_metadata_files_unchanged",
       len(material_checks) == 21 and all(x["hash_match"] and x["bytes_match"] for x in material_checks),
       material_checks)

old_stages = {
    "工作记录/阶段记录/S00-材料审计-v001.md": "5602f8230036e7a4ce2c45122ef220ee0936d3f50c490f0cff3e87c83d16cd72",
    "工作记录/阶段记录/S01-题目理解-v001.md": "c3b5491d0e8bc2981be3a2f2917675cf825b3a0bb5d5e655d865ea6266c2ad8d",
    "工作记录/阶段记录/S01-补充澄清-v001.md": "9b0dee47ec43cb2880ab71b7a8097c77cd9a6bc5e19a32698fd2bdcbd2d6d646",
}
old_checks = []
for relative, expected in old_stages.items():
    actual = digest(task_path(relative))
    old_checks.append({"path": relative, "expected_sha256": expected,
                       "actual_sha256": actual, "unchanged": actual == expected})
record("three_delivered_stages_preserved", all(x["unchanged"] for x in old_checks), old_checks)

docs = [
    "工作记录/阶段记录/S02-方法学习与第1问知识准备-v001.md",
    "工作记录/00-任务状态.md", "工作记录/记录索引.md",
    "工作记录/方法库查阅记录.md", "工作记录/决策记录.md",
    "工作记录/06-更新记录.md", "工作记录/归档清单.md",
    "工作记录/诊断代码/S02-运行与核验说明-v001.md",
]
doc_checks = []
for relative in docs:
    p = task_path(relative)
    text = p.read_text(encoding="utf-8-sig")
    issues = []
    if "\ufffd" in text:
        issues.append("Unicode replacement character found")
    for opening, closing in [(r"\(", r"\)"), (r"\[", r"\]")]:
        if text.count(opening) != text.count(closing):
            issues.append(f"Unbalanced math delimiters {opening} {closing}")
    if re.search(r"\\\\[\[\]\(\)]", text):
        issues.append("Double escaped math delimiters")
    # Check local Markdown link targets; intentionally do not open any URL.
    links = []
    for match in re.finditer(r"(?<!!)\[[^\]\n]*\]\(([^)\n]+)\)", text):
        target = match.group(1).strip().strip("<>")
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", target) or target.startswith("#"):
            continue
        target = target.split("#", 1)[0]
        dest = (p.parent / target).resolve()
        if not dest.is_relative_to(ROOT):
            issues.append(f"External local path rejected: {target}")
            continue
        exists = dest.exists() or dest == OUT
        links.append({"target": target, "exists_or_output_being_written": exists})
        if not exists:
            issues.append(f"Missing local link target: {target}")
    # Complete Markdown table headers and consistent cells (escaped pipes ignored).
    lines = text.splitlines()
    i = 0
    table_count = 0
    in_display_math = False
    code_fence = None
    while i < len(lines):
        stripped = lines[i].strip()
        if code_fence is not None:
            if stripped.startswith(code_fence):
                code_fence = None
            i += 1
            continue
        if stripped.startswith("~~~") or stripped.startswith("```"):
            code_fence = stripped[:3]
            i += 1
            continue
        if stripped == r"\[":
            in_display_math = True
            i += 1
            continue
        if stripped == r"\]":
            in_display_math = False
            i += 1
            continue
        if in_display_math or not stripped.startswith("|"):
            i += 1
            continue
        start = i
        block = []
        while i < len(lines) and lines[i].strip().startswith("|"):
            block.append(lines[i].strip())
            i += 1
        table_count += 1
        rows = [re.split(r"(?<!\\)\|", line)[1:-1] for line in block]
        if len(rows) < 2 or not all(re.fullmatch(r"\s*:?-{3,}:?\s*", c) for c in rows[1]):
            issues.append(f"Table missing full separator/header near line {start+1}")
        if any(not c.strip() for c in rows[0]):
            issues.append(f"Empty table header near line {start+1}")
        if any(len(row) != len(rows[0]) for row in rows):
            issues.append(f"Inconsistent table cell count near line {start+1}")
    doc_checks.append({"path": relative, "bytes": p.stat().st_size,
                       "sha256": digest(p), "tables": table_count,
                       "local_links_checked": len(links), "issues": issues})
record("saved_documents_links_headers_math_markers",
       all(not d["issues"] for d in doc_checks), doc_checks)

generic = json.loads(read("工作记录/诊断结果/S02-通用例子复核-v001.json"))
record("generic_teaching_checks_only", generic["tests"] == 20 and generic["passed"] == 20
       and all(c["passed"] for c in generic["checks"]),
       {"tests": generic["tests"], "passed": generic["passed"], "scope": generic["scope"]})
entry_result = json.loads(read("工作记录/诊断结果/S02-资料入场核对-v001.json"))
record("entry_scope_integrity", entry_result["all_pass"] and len(entry_result["files"]) == 17,
       {"file_count": len(entry_result["files"]), "all_pass": entry_result["all_pass"]})

new_artifacts = [
    "工作记录/阶段记录/S02-方法学习与第1问知识准备-v001.md",
    "工作记录/诊断代码/check_s02_materials_v001.ps1",
    "工作记录/诊断结果/S02-资料入场核对-v001.json",
    "工作记录/诊断代码/run_s02_examples_v001.ps1",
    "工作记录/诊断结果/S02-通用例子复核-v001.json",
    "工作记录/诊断代码/verify_s02_delivery_v001.py",
    "工作记录/诊断代码/verify_s02_delivery_v002.py",
    "工作记录/诊断结果/S02-交付核验-v001.json",
    "工作记录/诊断结果/S02-交付核验-v002.json",
    "工作记录/诊断代码/S02-运行与核验说明-v001.md",
]
archive_text = read("工作记录/归档清单.md")
archive_missing = [p for p in new_artifacts + [e["path"] for e in integrity["files"]]
                   + ["补充资料/交付完整性-v001.json"] if p not in archive_text]
record("archive_covers_new_artifacts_and_materials", not archive_missing, archive_missing)
state = read("工作记录/00-任务状态.md")
stage = read(docs[0])
record("stage_acceptance_boundary",
       "本阶段完成，待用户验收" in stage and "待用户验收" in state
       and "P01/P02" in state and "未批准" in state and "管理员归档" in state,
       "S02 pending user acceptance; H approval limited to Q1; P not approved; archival unconfirmed")

# Hash all files whose versions matter to this delivery; exclude self-hash of output.
artifacts = []
for relative in dict.fromkeys(docs + new_artifacts):
    p = task_path(relative)
    if p == OUT:
        continue
    artifacts.append({"path": relative, "sha256": digest(p), "bytes": p.stat().st_size})
result = {
    "stage": "S02-v001",
    "checked_at": datetime.now().astimezone().isoformat(),
    "python": sys.version,
    "scope": "Local material/record integrity and formatting checks, not target numerical validation",
    "network_used": False,
    "raw_problem_or_attachment_content_read": False,
    "checks": checks,
    "all_pass": all(c["passed"] for c in checks),
    "artifacts": artifacts,
    "output_self_hash_excluded": True,
}
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"stage": result["stage"], "all_pass": result["all_pass"],
                  "checks": len(checks),
                  "failed": [c for c in checks if not c["passed"]]},
                 ensure_ascii=False, indent=2))
raise SystemExit(0 if result["all_pass"] else 1)

