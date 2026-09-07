from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\admin\OneDrive\Desktop\26国赛-单题盲解区\A-P8C3")
HERE = ROOT / "工作记录" / "揭晓后对照" / "最终方法与创新总结-v001"
OUT = HERE / "最终交付核验-v001.json"

DOCS = [
    HERE / "README.md",
    HERE / "00-本轮定稿记录-v001.md",
    HERE / "方法卡总集-v001.md",
    HERE / "创新机制与迁移指南-v001.md",
    HERE / "全流程经验汇总-v001.md",
    HERE / "总经验合并候选-v001.md",
    HERE / "归档交接清单-v001.md",
    HERE / "归档清单生成说明-v001.md",
]
CONTROLS = [
    ROOT / "工作记录/00-任务状态.md",
    ROOT / "工作记录/记录索引.md",
    ROOT / "工作记录/经验.md",
    ROOT / "工作记录/决策记录.md",
    ROOT / "工作记录/06-更新记录.md",
    ROOT / "工作记录/方法库查阅记录.md",
    ROOT / "工作记录/归档清单.md",
]
EXPECTED_MANIFEST_HASH = "ed23098187e4479ab250744f6cc35fc84e1ec5bb25afe7e6b4ac21851c0da357"
EXPECTED_SUMS_HASH = "9e6b950d124e16454aaf1715d21d2be183432e2703f4b92ff9a10d0d01820439"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def local_link_failures(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    failures = []
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
        target = target.strip().strip("<>").split("#", 1)[0]
        if not target or re.match(r"^[a-zA-Z]+://", target):
            continue
        candidate = Path(target) if re.match(r"^[A-Za-z]:[/\\]", target) else path.parent / target
        if not candidate.exists():
            failures.append(target)
    return failures


def table_failures(path: Path) -> list[int]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    bad = []
    for i in range(len(lines) - 1):
        if lines[i].lstrip().startswith("|") and lines[i + 1].lstrip().startswith("|"):
            cells = [c.strip() for c in lines[i + 1].strip().strip("|").split("|")]
            if cells and all(re.fullmatch(r":?-{3,}:?", c or "") for c in cells):
                n1 = len(lines[i].strip().strip("|").split("|"))
                n2 = len(cells)
                if n1 != n2:
                    bad.append(i + 1)
    return bad


def verify_freeze() -> dict:
    package = ROOT / "工作记录/冻结候选/盲解-v001"
    mp = package / "文件清单-v001.json"
    sp = package / "SHA256SUMS.txt"
    manifest = json.loads(mp.read_text(encoding="utf-8-sig"))
    mf = []
    for row in manifest["files"]:
        p = package / row["path"]
        if not p.is_file() or p.stat().st_size != row["bytes"] or sha256(p) != row["sha256"]:
            mf.append(row["path"])
    sf = []
    lines = sp.read_text(encoding="utf-8-sig").splitlines()
    for line in lines:
        expected, rel = line.split("  ", 1)
        p = package / rel
        if not p.is_file() or sha256(p) != expected:
            sf.append(rel)
    return {
        "manifest_entries": len(manifest["files"]),
        "manifest_failures": mf,
        "checksum_lines": len(lines),
        "checksum_failures": sf,
        "manifest_sha256": sha256(mp),
        "checksum_file_sha256": sha256(sp),
        "expected_manifest_sha256": EXPECTED_MANIFEST_HASH,
        "expected_checksum_file_sha256": EXPECTED_SUMS_HASH,
        "passed": not mf and not sf and sha256(mp) == EXPECTED_MANIFEST_HASH and sha256(sp) == EXPECTED_SUMS_HASH,
    }


def main() -> None:
    missing = [str(p.relative_to(ROOT)) for p in DOCS + CONTROLS if not p.is_file()]
    links = {str(p.relative_to(ROOT)): local_link_failures(p) for p in DOCS if p.is_file()}
    links = {k: v for k, v in links.items() if v}
    tables = {str(p.relative_to(ROOT)): table_failures(p) for p in DOCS if p.is_file()}
    tables = {k: v for k, v in tables.items() if v}
    experience = (ROOT / "工作记录/经验.md").read_text(encoding="utf-8-sig")
    exp_ids = sorted(set(re.findall(r"E\d{3}", experience)))
    summary = (HERE / "全流程经验汇总-v001.md").read_text(encoding="utf-8-sig")
    mapped = sorted(set(re.findall(r"E\d{3}", summary)))
    required_ids = [f"E{i:03d}" for i in range(1, 31)]
    controls_text = "\n".join(p.read_text(encoding="utf-8-sig") for p in CONTROLS)
    manifest_json = HERE / "归档文件清单-v001.json"
    manifest_csv = HERE / "归档文件清单-v001.csv"
    freeze = verify_freeze()
    result = {
        "checked_at": datetime.now().astimezone().isoformat(),
        "scope": "最终方法总结文档、控制记录、E001—E030映射、归档清单存在性和冻结包字节；无模型重算",
        "missing_files": missing,
        "broken_local_links": links,
        "markdown_table_header_failures": tables,
        "experience_ids_present": exp_ids,
        "required_experience_ids_all_mapped": all(x in mapped for x in required_ids),
        "missing_mapped_ids": [x for x in required_ids if x not in mapped],
        "controls_have_D053": "D053" in controls_text,
        "controls_have_U060": "U060" in controls_text,
        "status_exact_phrase": "本题最后一轮方法与创新总结完成；全流程成果已整理，待用户验收与管理员GitHub归档" in controls_text,
        "archive_manifest_outputs_exist": manifest_json.is_file() and manifest_csv.is_file(),
        "freeze": freeze,
    }
    result["passed"] = (
        not missing and not links and not tables
        and result["required_experience_ids_all_mapped"]
        and result["controls_have_D053"] and result["controls_have_U060"]
        and result["status_exact_phrase"] and result["archive_manifest_outputs_exist"]
        and freeze["passed"]
    )
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
