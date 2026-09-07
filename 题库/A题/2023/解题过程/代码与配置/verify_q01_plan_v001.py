"""Q01 document-only delivery check; no target geometry, solar or power computation."""
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
EXPECTED_ROOT = Path(r"C:\Users\admin\OneDrive\Desktop\26国赛-单题盲解区\A-P8C3").resolve()
if ROOT != EXPECTED_ROOT:
    raise SystemExit("Run only inside the explicitly authorized anonymous workspace.")
OUT = ROOT / "工作记录/诊断结果/Q01-文档核验-v001.json"
if OUT.exists():
    raise SystemExit("Existing evidence must be preserved; use a new version.")
checks = []

def path_in_task(relative):
    p = (ROOT / relative).resolve()
    if not p.is_relative_to(ROOT):
        raise ValueError("Path outside task workspace")
    return p

def read(relative):
    return path_in_task(relative).read_text(encoding="utf-8-sig")

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def record(name, passed, details):
    checks.append({"name": name, "passed": bool(passed), "details": details})

# Only explicitly named previous records and method/physical cards are hashed.
# Do not enumerate task inputs, open raw PDF/XLSX, or rerun previous tests.
baseline = json.loads(read("工作记录/诊断结果/Q01-方案输入版本-v001.json"))
baseline_checks = []
for entry in baseline["files"]:
    p = path_in_task(entry["path"])
    actual = sha(p)
    baseline_checks.append({
        "path": entry["path"], "sha256": actual,
        "unchanged": actual == entry["sha256"] and p.stat().st_size == entry["bytes"]
    })
record("12_reread_inputs_unchanged",
       len(baseline_checks) == 12 and all(e["unchanged"] for e in baseline_checks),
       baseline_checks)

old_expected = {
    "工作记录/阶段记录/S00-材料审计-v001.md":
        "5602f8230036e7a4ce2c45122ef220ee0936d3f50c490f0cff3e87c83d16cd72",
    "工作记录/阶段记录/S01-题目理解-v001.md":
        "c3b5491d0e8bc2981be3a2f2917675cf825b3a0bb5d5e655d865ea6266c2ad8d",
    "工作记录/阶段记录/S01-补充澄清-v001.md":
        "9b0dee47ec43cb2880ab71b7a8097c77cd9a6bc5e19a32698fd2bdcbd2d6d646",
}
old_delivery = json.loads(read("工作记录/诊断结果/S02-交付核验-v002.json"))
s02path = "工作记录/阶段记录/S02-方法学习与第1问知识准备-v001.md"
old_expected[s02path] = next(e["sha256"] for e in old_delivery["artifacts"] if e["path"] == s02path)
old_checks = [{"path": rel, "expected": expected,
               "unchanged": sha(path_in_task(rel)) == expected}
              for rel, expected in old_expected.items()]
record("four_accepted_stages_preserved", all(e["unchanged"] for e in old_checks), old_checks)

docs = [
    "工作记录/阶段记录/Q01-方案构造-v001.md",
    "工作记录/00-任务状态.md", "工作记录/记录索引.md",
    "工作记录/方法库查阅记录.md", "工作记录/决策记录.md",
    "工作记录/06-更新记录.md", "工作记录/归档清单.md",
    "工作记录/诊断代码/Q01-文档核验说明-v001.md",
]
doc_checks = []
for rel in docs:
    p = path_in_task(rel)
    body = read(rel)
    issues = []
    if "\ufffd" in body:
        issues.append("Unicode replacement character")
    for op, cl in [(r"\(", r"\)"), (r"\[", r"\]")]:
        if body.count(op) != body.count(cl):
            issues.append("Unbalanced math delimiters: " + op)
    if re.search(r"\\\\[\[\]\(\)]", body):
        issues.append("Double-escaped math delimiter")
    n_links = 0
    for match in re.finditer(r"(?<!!)\[[^\]\n]*\]\(([^)\n]+)\)", body):
        target = match.group(1).strip().strip("<>")
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", target) or target.startswith("#"):
            continue
        dest = (p.parent / target.split("#", 1)[0]).resolve()
        n_links += 1
        if not dest.is_relative_to(ROOT):
            issues.append("Local link outside task: " + target)
        elif not dest.exists() and dest != OUT:
            issues.append("Missing link: " + target)
    lines = body.splitlines()
    i, table_count = 0, 0
    display = False
    fence = None
    while i < len(lines):
        line = lines[i].strip()
        if fence is not None:
            if line.startswith(fence):
                fence = None
            i += 1
            continue
        if line.startswith("~~~") or line.startswith(chr(96) * 3):
            fence = line[:3]
            i += 1
            continue
        if line == r"\[":
            display = True
            i += 1
            continue
        if line == r"\]":
            display = False
            i += 1
            continue
        if display or not line.startswith("|"):
            i += 1
            continue
        start, block = i + 1, []
        while i < len(lines) and lines[i].strip().startswith("|"):
            block.append(lines[i].strip())
            i += 1
        table_count += 1
        rows = [re.split(r"(?<!\\)\|", item)[1:-1] for item in block]
        if len(rows) < 2 or not rows[0] or not all(
                re.fullmatch(r"\s*:?-{3,}:?\s*", cell) for cell in rows[1]):
            issues.append(f"Incomplete table header/separator at {start}")
        if any(not cell.strip() for cell in rows[0]):
            issues.append(f"Blank header at {start}")
        if any(len(row) != len(rows[0]) for row in rows):
            issues.append(f"Column count mismatch at {start}")
    if display or fence is not None:
        issues.append("Unclosed display math or code fence")
    doc_checks.append({"path": rel, "bytes": p.stat().st_size, "sha256": sha(p),
                       "tables": table_count, "local_links": n_links, "issues": issues})
record("saved_documents_links_tables_math",
       all(not e["issues"] for e in doc_checks), doc_checks)

status = read("工作记录/00-任务状态.md")
stage = read(docs[0])
record("stage_scope_and_approval_separation",
       "第1问方案构造完成，推荐方案及新增假设待用户批准" in status
       and "第1问方案构造完成，推荐方案及新增假设待用户批准" in stage
       and "S02" in status and "未批准本题数值采用" in status
       and "管理员归档未获确认" in status
       and all(f"N0{i}" in stage for i in range(1, 6))
       and all(f"V0{i}" in stage for i in range(1, 8)),
       "Text-state check only: S02 accepted; R/P/N pending; no model-validation claim.")

sequence_checks = []
for rel, prefix, last in [
        ("工作记录/决策记录.md", "D", 11),
        ("工作记录/06-更新记录.md", "U", 10)]:
    numbers = [int(s) for s in re.findall(r"^## " + prefix + r"(\d{3})(?=\s|—|$)",
                                          read(rel), re.M)]
    sequence_checks.append({"path": rel, "numbers": numbers,
                            "continuous": numbers == list(range(1, last + 1))})
record("decision_update_numbering_continues",
       all(e["continuous"] for e in sequence_checks), sequence_checks)

new_artifacts = [
    docs[0], "工作记录/诊断结果/Q01-方案输入版本-v001.json",
    "工作记录/诊断代码/verify_q01_plan_v001.py", docs[-1],
    "工作记录/诊断结果/Q01-文档核验-v001.json",
]
archive = read("工作记录/归档清单.md")
missing = [rel for rel in new_artifacts if rel not in archive]
record("archive_covers_all_five_new_artifacts", not missing, missing)

artifacts = []
for rel in dict.fromkeys(docs + new_artifacts):
    p = path_in_task(rel)
    if p != OUT:
        artifacts.append({"path": rel, "bytes": p.stat().st_size, "sha256": sha(p)})
result = {
    "stage": "Q01-方案构造-v001", "checked_at": datetime.now().astimezone().isoformat(),
    "python": sys.version, "scope": "Document and historical-version checks only",
    "network_used": False, "target_numerical_evaluation_executed": False,
    "previous_teaching_tests_rerun": False, "raw_pdf_xlsx_content_read": False,
    "checks": checks, "all_pass": all(c["passed"] for c in checks),
    "artifacts": artifacts, "output_self_hash_excluded": True,
}
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"stage": result["stage"], "all_pass": result["all_pass"],
                  "checks": len(checks), "documents": len(docs),
                  "failed": [c for c in checks if not c["passed"]]},
                 ensure_ascii=False, indent=2))
raise SystemExit(0 if result["all_pass"] else 1)

