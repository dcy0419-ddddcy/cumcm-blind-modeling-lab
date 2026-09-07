from __future__ import annotations

import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\Users\admin\OneDrive\Desktop\26国赛-单题盲解区\A-P8C3")
OUT = ROOT / "工作记录" / "揭晓后对照" / "最终方法与创新总结-v001"
CSV_OUT = OUT / "归档文件清单-v001.csv"
JSON_OUT = OUT / "归档文件清单-v001.json"
EXCLUDED = {CSV_OUT.resolve(), JSON_OUT.resolve()}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def stage(rel: str) -> str:
    p = rel.replace("\\", "/")
    if "/冻结候选/" in "/" + p:
        return "正式盲解冻结"
    if "揭晓后对照/首次正确性核查" in p:
        return "首次揭晓正确性核查"
    if "揭晓后对照/方法比较与经验提炼" in p:
        return "方法比较与经验提炼"
    if "揭晓后对照/最终方法与创新总结" in p:
        return "最终方法与创新总结"
    if "Q01" in p or "第1问" in p:
        return "第1问"
    if "Q02" in p or "第2问" in p or "result2" in p.lower():
        return "第2问"
    if "Q03" in p or "第3问" in p or "result3" in p.lower():
        return "第3问"
    if "S00" in p or "S01" in p:
        return "材料审计与题目理解"
    if "S02" in p or p.startswith("方法库/") or p.startswith("补充资料/"):
        return "方法学习"
    if "全题整合" in p or "S03" in p:
        return "全题整合"
    return "项目控制或公共材料"


def identity(rel: str) -> str:
    p = rel.replace("\\", "/")
    return "揭晓后" if "工作记录/揭晓后对照/" in p else "盲解或项目公共"


def validity(rel: str) -> str:
    name = Path(rel).name.lower()
    p = rel.replace("\\", "/").lower()
    historical_tokens = (
        "before-", "attempt1", "attempt-1", "失败", "partial", "旧版",
        "首次", "未完成草稿", "过程草稿", "临时", "backup", ".bak"
    )
    if any(t in name or t in p for t in historical_tokens):
        return "历史或失败证据（保留，非当前执行入口）"
    if "冻结候选/盲解-v001/" in p:
        return "正式冻结有效字节"
    if name in {"00-任务状态.md", "记录索引.md", "经验.md", "决策记录.md", "06-更新记录.md", "归档清单.md"}:
        return "当前控制入口"
    if "-v00" in name:
        return "版本化成果或证据；当前性以记录索引为准"
    return "现存输入/成果；当前性以记录索引为准"


def third_party(rel: str) -> bool:
    p = rel.replace("\\", "/")
    return (
        "首次正确性核查-v001/参考论文/" in p
        or "首次正确性核查-v001/来源页面/" in p
        or "首次正确性核查-v001/官方来源/" in p
    )


def archive_action(rel: str, size: int) -> tuple[str, str, str]:
    p = rel.replace("\\", "/")
    ext = Path(rel).suffix.lower()
    if third_party(rel):
        return "待管理员许可判断", "第三方或官方外部材料；默认只归档链接、页码、哈希和本方分析", "许可未确认"
    if size >= 25 * 1024 * 1024 or ext in {".npz", ".rar", ".zip", ".7z"}:
        return "需另行存储或管理员判断", "大型原始统计/压缩包；保留哈希与复现依赖，不默认普通Git", "工作区内已包含"
    if ext in {".aux", ".toc", ".out", ".log", ".synctex.gz"}:
        return "管理员判断", "可重建编译或运行中间产物；有失败证据价值者保留", "工作区内已包含"
    if any(s in p for s in ("页面核验", "页面渲染", "page-", "official-page-")) and ext in {".png", ".jpg", ".jpeg"}:
        return "管理员判断", "逐页/重复渲染；可由PDF重建时不必全部进入普通Git", "工作区内已包含"
    return "建议入库", "正文、代码、配置、结果、索引或必要证据", "工作区内已包含"


def main() -> None:
    rows = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames.sort()
        filenames.sort()
        for filename in filenames:
            path = Path(dirpath) / filename
            if path.resolve() in EXCLUDED:
                continue
            rel = path.relative_to(ROOT).as_posix()
            size = path.stat().st_size
            action, category, dependency = archive_action(rel, size)
            rows.append({
                "relative_path": rel,
                "bytes": size,
                "sha256": sha256(path),
                "stage": stage(rel),
                "identity": identity(rel),
                "validity": validity(rel),
                "archive_category": category,
                "dependency_or_inclusion": dependency,
                "recommended_action": action,
            })
    rows.sort(key=lambda x: x["relative_path"])
    fields = list(rows[0]) if rows else []
    with CSV_OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    payload = {
        "schema": "archive-handoff-v001",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "root_label": "A-P8C3",
        "self_reference_policy": "This JSON and its CSV peer are excluded from their own manifest.",
        "file_count": len(rows),
        "total_bytes": sum(r["bytes"] for r in rows),
        "counts_by_action": {a: sum(r["recommended_action"] == a for r in rows) for a in sorted({r["recommended_action"] for r in rows})},
        "files": rows,
    }
    JSON_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("file_count", "total_bytes", "counts_by_action")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
