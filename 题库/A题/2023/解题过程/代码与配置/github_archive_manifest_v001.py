from __future__ import annotations
import csv, hashlib, json, subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO=Path(__file__).resolve().parents[5]
BASE=REPO/"题库/A题/2023"
SRC=Path(r"C:\Users\admin\OneDrive\Desktop\26国赛-单题盲解区\A-P8C3")
SOURCE_MANIFEST=SRC/"工作记录/揭晓后对照/最终方法与创新总结-v001/归档文件清单-v001.json"
COPY_MAP=BASE/"解题过程/归档映射-v001.json"
OUTDIR=BASE/"解题过程"
ACTUAL=OUTDIR/"GitHub实际入库文件清单-v001.csv"
EXCLUDED=OUTDIR/"GitHub未入库依赖与原因清单-v001.csv"
SUMMARY=OUTDIR/"GitHub归档统计-v001.json"
VERIFY=OUTDIR/"管理员归档审计/提交前核验-v001.json"
SELF={ACTUAL.resolve(),EXCLUDED.resolve(),SUMMARY.resolve(),VERIFY.resolve()}

def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()
def git_lines(*args):
    cp=subprocess.run(["git","-c","core.quotepath=false",*args],cwd=REPO,text=True,encoding="utf-8",stdout=subprocess.PIPE,check=True)
    return [x for x in cp.stdout.splitlines() if x]
def reason(row):
    p=row["relative_path"]; ext=Path(p).suffix.lower(); size=row["bytes"]
    if any(x in p for x in ["首次正确性核查-v001/参考论文/","首次正确性核查-v001/来源页面/","首次正确性核查-v001/官方来源/"]):
        return ("第三方或官方材料再分发许可未确认","否；本方分析可用官方链接复核","官方链接、页码和本方分析已入库","管理员许可后再决定")
    if "/冻结候选/盲解-v001/" in "/"+p:
        return ("冻结包与已归档原件大量逐字节重复","视文件而定；冻结清单和正式产物已入库","源工作区正式冻结包","外部对象存储或保留本地")
    if ext==".npz" or size>=5_000_000:
        return ("大型逐批统计、检查点或结果分块不适合普通Git","通常可由入库代码、配置和种子重跑；部分只用于历史恢复","源工作区及冻结依赖清单","Git LFS、Release或外部对象存储，需管理员另审")
    if ext in {".aux",".log",".out",".pyc"} or any(x in p for x in ["页面核验","页面渲染","page-","contact-","__pycache__"]):
        return ("可重建编译缓存、运行日志或批量渲染页","是；由论文PDF、LaTeX、渲染/编译入口重建","源工作区","不入库或按需生成")
    if "partial" in p.lower() or "checkpoint" in p.lower():
        return ("恢复检查点或未完成分块；结论已由阶段记录和最终统计覆盖","非必要；用于历史恢复","源工作区","仅本地保留")
    return ("未被精简映射选为关键原件，或信息已由阶段记录/哈希/当前版本覆盖","视文件而定","源工作区全量清单和SHA","管理员按需补充")
def main():
    archive_changes=set(git_lines("diff","origin/main","--name-only"))
    paths=sorted(archive_changes)
    status_by_path={}
    for line in git_lines("diff","origin/main","--name-status"):
        parts=line.split("\t")
        if len(parts)>=2:status_by_path[parts[-1]]=parts[0]
    rows=[]
    for rel in paths:
        p=REPO/rel
        if p.resolve() in SELF or not p.is_file(): continue
        rows.append({"repo_path":rel.replace("\\","/"),"bytes":p.stat().st_size,"sha256":sha(p),"status":status_by_path.get(rel,"unknown")})
    with ACTUAL.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    source=json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    mapped=json.loads(COPY_MAP.read_text(encoding="utf-8"))["entries"]
    included_sources={x["source"] for x in mapped}
    excluded=[]
    for row in source["files"]:
        if row["relative_path"] in included_sources: continue
        why,rebuild,location,storage=reason(row)
        excluded.append({"source_relative_path":row["relative_path"],"bytes":row["bytes"],"sha256":row["sha256"],"role":row["archive_category"],"not_in_git_reason":why,"rebuildable":rebuild,"current_local_location":str(SRC/row["relative_path"]),"future_storage":storage})
    with EXCLUDED.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(excluded[0])); w.writeheader(); w.writerows(excluded)
    groups=defaultdict(list)
    for row in source["files"]: groups[row["sha256"]].append(row)
    dup_groups=[v for v in groups.values() if len(v)>1]
    duplicate_files=sum(len(v)-1 for v in dup_groups)
    duplicate_savings=sum(v[0]["bytes"]*(len(v)-1) for v in dup_groups)
    top=sorted(rows,key=lambda x:x["bytes"],reverse=True)[:20]
    summary={
      "generated_at":datetime.now().astimezone().isoformat(),
      "source_inventory_files":source["file_count"],
      "source_inventory_bytes":source["total_bytes"],
      "source_duplicate_groups":len(dup_groups),
      "source_duplicate_files_beyond_first":duplicate_files,
      "potential_duplicate_bytes_beyond_first":duplicate_savings,
      "actual_git_files_excluding_manifests":len(rows),
      "actual_git_bytes_excluding_manifests":sum(x["bytes"] for x in rows),
      "largest_20":top,
      "excluded_source_files":len(excluded),
      "excluded_source_bytes":sum(x["bytes"] for x in excluded),
      "files_over_100MiB_in_actual":[x for x in rows if x["bytes"]>100*1024*1024],
      "self_reference_policy":"The two CSV manifests, this summary JSON, and the mutable pre-commit verification receipt are excluded from the actual-file hash list to avoid self-reference and stale hashes."
    }
    SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:summary[k] for k in ["actual_git_files_excluding_manifests","actual_git_bytes_excluding_manifests","excluded_source_files","excluded_source_bytes","source_duplicate_groups","source_duplicate_files_beyond_first","potential_duplicate_bytes_beyond_first","files_over_100MiB_in_actual"]},ensure_ascii=True))
if __name__=="__main__": main()


