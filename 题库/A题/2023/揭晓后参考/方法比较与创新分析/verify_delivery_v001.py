from pathlib import Path
import datetime
import hashlib
import json
import re


WORKSPACE = Path(r"C:\Users\admin\OneDrive\Desktop\26国赛-单题盲解区\A-P8C3")
ROOT = Path(__file__).resolve().parent
EXPECTED = [
    "00-校准与小型检查计划-v001.md",
    "01-阅读范围与证据清单-v001.md",
    "02-三问方法差异与取舍-v001.md",
    "03-创新机制拆解-v001.md",
    "04-自身方法评估与互补建议-v001.md",
    "05-经验条目与旧经验审查-v001.md",
    "06-可迁移经验候选-v001.md",
    "07-论文排版对照与改进清单-v001.md",
    "calibrate_comparisons_v001.py",
    "校准百分比-v001.json",
    "verify_frozen_package_v001.py",
    "冻结成果复核-v001.json",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


existence = {name: (ROOT / name).is_file() for name in EXPECTED}
hashes = {name: sha256(ROOT / name) for name in EXPECTED if (ROOT / name).is_file()}

broken_links = []
table_errors = []
markdown_files = [ROOT / name for name in EXPECTED if name.endswith(".md")]
for path in markdown_files:
    text = path.read_text(encoding="utf-8")
    for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
        target = match.group(1).strip()
        if target.startswith(("http://", "https://", "#")):
            continue
        target = target.split("#", 1)[0]
        if target and not (path.parent / target).resolve().exists():
            broken_links.append({"file": path.name, "target": target})
    lines = text.splitlines()
    for i in range(len(lines) - 1):
        if lines[i].lstrip().startswith("|") and re.match(r"^\s*\|(?:\s*:?-+:?\s*\|)+\s*$", lines[i + 1]):
            head_cols = lines[i].count("|")
            sep_cols = lines[i + 1].count("|")
            if head_cols != sep_cols:
                table_errors.append({"file": path.name, "line": i + 1, "header_pipes": head_cols, "separator_pipes": sep_cols})

controls = {
    "state": (WORKSPACE / "工作记录/00-任务状态.md").read_text(encoding="utf-8"),
    "index": (WORKSPACE / "工作记录/记录索引.md").read_text(encoding="utf-8"),
    "decision": (WORKSPACE / "工作记录/决策记录.md").read_text(encoding="utf-8"),
    "update": (WORKSPACE / "工作记录/06-更新记录.md").read_text(encoding="utf-8"),
    "archive": (WORKSPACE / "工作记录/归档清单.md").read_text(encoding="utf-8"),
    "methods": (WORKSPACE / "工作记录/方法库查阅记录.md").read_text(encoding="utf-8"),
    "experience": (WORKSPACE / "工作记录/经验.md").read_text(encoding="utf-8"),
}
control_checks = {
    "state_phrase": "首次揭晓后方法比较、创新机制分析与经验提炼完成，待用户验收" in controls["state"],
    "index_section": "首次揭晓后方法比较与经验提炼 — D052/U059" in controls["index"],
    "decision_D052": "## D052" in controls["decision"],
    "update_U059": "## U059" in controls["update"],
    "archive_section": "首次揭晓后方法比较与经验提炼交接" in controls["archive"],
    "method_reading_recorded": "揭晓后方法比较补充阅读" in controls["methods"],
    "experience_E022_to_E030": all(f"E{i:03d}" in controls["experience"] for i in range(22, 31)),
    "external_total_experience_not_updated": "本轮未写入工作区外总经验库" in controls["experience"],
}

freeze = json.loads((ROOT / "冻结成果复核-v001.json").read_text(encoding="utf-8"))
result = {
    "checked_at": datetime.datetime.now().astimezone().isoformat(),
    "expected_files": existence,
    "hashes": hashes,
    "broken_markdown_links": broken_links,
    "table_header_errors": table_errors,
    "control_checks": control_checks,
    "freeze_check_passed": freeze.get("passed"),
    "scope": "文档、链接、表头、控制状态和冻结包字节；不替代方法判断或物理验证",
}
result["passed"] = (
    all(existence.values())
    and not broken_links
    and not table_errors
    and all(control_checks.values())
    and freeze.get("passed") is True
)
(ROOT / "交付核验-v001.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
