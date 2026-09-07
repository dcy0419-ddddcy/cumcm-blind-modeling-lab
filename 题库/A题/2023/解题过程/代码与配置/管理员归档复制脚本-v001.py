from __future__ import annotations
import csv, hashlib, json, shutil
from pathlib import Path

SRC=Path(r"C:\Users\admin\OneDrive\Desktop\26国赛-单题盲解区\A-P8C3")
REPO=Path(r"C:\Users\admin\OneDrive\Desktop\26国赛-归档工作树-2023A")
BASE=REPO/"题库/A题/2023"
MAP=[]
def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()
def cp(srel,drel,identity="盲解",kind="原件复制",note=""):
    s=SRC/srel; d=BASE/drel
    if not s.is_file(): raise FileNotFoundError(s)
    d.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(s,d)
    MAP.append({"source":srel.replace("\\","/"),"target":drel.replace("\\","/"),"identity":identity,"copy_mode":kind,"bytes":d.stat().st_size,"sha256":sha(d),"note":note})
def cp_tree_files(srcdir,dstdir,predicate,identity="盲解",note=""):
    root=SRC/srcdir
    for s in sorted(root.rglob("*")):
        if s.is_file() and predicate(s,root):
            rel=s.relative_to(root)
            cp(str(Path(srcdir)/rel),str(Path(dstdir)/rel),identity,"原件复制",note)

# Rules and audited controls
cp("AGENTS.md","解题过程/冻结版本/盲解规则快照-AGENTS.md","盲解","规则快照","不覆盖仓库根AGENTS.md")
for name in ["00-任务状态.md","记录索引.md","方法库查阅记录.md","决策记录.md","06-更新记录.md","归档清单.md"]:
    cp("工作记录/"+name,"解题过程/审计记录/"+name,"跨阶段","原件复制","源工作区当前控制记录")
cp("工作记录/经验.md","经验.md","跨阶段","GitHub可读当前入口","覆盖原占位经验入口，原仓库历史由Git保留")

# All formal stage records
cp_tree_files("工作记录/阶段记录","解题过程/阶段记录",lambda s,r:s.suffix.lower()==".md","盲解","保留已验收与失败阶段记录")

# Approved local method snapshot
for srcdir,dstdir in [("方法库","解题过程/方法资料快照/方法库"),("补充资料","解题过程/方法资料快照/补充资料")]:
    cp_tree_files(srcdir,dstdir,lambda s,r:s.suffix.lower() in {".md",".json",".py",".txt"} and s.stat().st_size<2_000_000,"盲解","已审核本地资料快照")

# Code and configurations
cp_tree_files("工作记录/诊断代码","解题过程/代码与配置",lambda s,r:s.suffix.lower() in {".py",".ps1",".json",".md",".txt",".csv"} and s.stat().st_size<2_000_000,"盲解","诊断、评价、搜索、论文生成与核验入口")

# Papers: source and final artifacts, omit rendered pages and compilation caches
def paper_pred(s,r):
    rel=s.relative_to(r).as_posix()
    if any(x in rel for x in ["页面核验","页面渲染","未完成草稿页面","首次排版证据","修订前快照"]): return False
    ext=s.suffix.lower()
    if ext in {".aux",".log",".out"}: return False
    return ext in {".md",".tex",".pdf",".png",".csv",".json",".py",".txt"} and s.stat().st_size<12_000_000
cp_tree_files("工作记录/论文","解题过程/论文",paper_pred,"盲解","单问与全题论文、图表、证据映射和可复现说明")

# Inputs actually used in blind workspace, without replacing repository official statement/template
cp("题目.pdf","解题过程/冻结版本/输入快照/匿名题目.pdf","盲解冻结","输入快照")
for n in ["附件01.xlsx","附件02.xlsx","附件03.xlsx"]:
    cp("附件/"+n,"解题过程/冻结版本/输入快照/"+n,"盲解冻结","输入快照")

# Frozen package metadata; do not duplicate the 239MiB evidence tree
freeze="工作记录/冻结候选/盲解-v001"
for n in ["README.md","文件清单-v001.json","未复制依赖清单-v001.json","SHA256SUMS.txt"]:
    cp(freeze+"/"+n,"解题过程/冻结版本/包元数据/"+n,"盲解冻结","冻结元数据","完整复现依赖仍在源工作区")
cp("工作记录/揭晓后对照/首次正确性核查-v001/00-冻结登记-v001.md","解题过程/冻结版本/正式冻结登记-v001.md","盲解冻结","包外冻结声明")

# Key diagnostics and results, excluding raw ray batches
diag=SRC/"工作记录/诊断结果"
keydirs=["Q01-全场-v001","Q02-原型-v001","Q02-搜索-v001","Q02-修复-v001","Q03-准备-v001","Q03-实施-v001"]
keywords=("结果","核验","校验","验证","冻结","配置","预算","失败","修订","比较","轨迹","预登记","报告","结论","统计","汇总","清单","映射","状态","回读","接口","适用域","压力","低存活","独立","交付","绑定","table","design","report","paired","summary","binding","manifest","result")
for kd in keydirs:
    root=diag/kd
    if not root.exists(): continue
    for s in sorted(root.rglob("*")):
        if not s.is_file(): continue
        rel=s.relative_to(root)
        ext=s.suffix.lower()
        if ext==".npz" or s.stat().st_size>=5_000_000: continue
        direct=len(rel.parts)==1
        keep=(ext==".md" or (ext in {".json",".jsonl",".csv",".txt",".xlsx",".py",".ps1"} and (direct or any(k.lower() in s.name.lower() for k in keywords))))
        if keep:
            cp(str(Path("工作记录/诊断结果")/kd/rel),str(Path("解题过程/验证与结果")/kd/rel),"盲解","精简证据复制","原始逐批NPZ未入库")

# Root-level diagnostics: material audit and foundational test evidence
for s in sorted(diag.iterdir()):
    if s.is_file() and s.suffix.lower() in {".json",".csv",".md",".txt"} and s.stat().st_size<5_000_000:
        cp(str(Path("工作记录/诊断结果")/s.name),str(Path("解题过程/验证与结果/公共诊断")/s.name),"盲解","原件复制")

# Formal outputs in a stable location
cp("工作记录/诊断结果/Q02-修复-v001/result2.xlsx","解题过程/验证与结果/正式结果/result2.xlsx","盲解","正式结果")
cp("工作记录/诊断结果/Q03-实施-v001/delivery/result3.xlsx","解题过程/验证与结果/正式结果/result3.xlsx","盲解","正式结果")

# Post-reveal own reports only
post="工作记录/揭晓后对照/首次正确性核查-v001"
root=SRC/post
for s in sorted(root.iterdir()):
    if s.is_file() and s.suffix.lower() in {".md",".json",".jsonl",".py",".csv",".txt"} and s.stat().st_size<5_000_000:
        cp(str(Path(post)/s.name),str(Path("揭晓后参考/首次正确性核查")/s.name),"揭晓后","本方分析复制","第三方正文和批量页面未复制")
for sub,target in [
 ("工作记录/揭晓后对照/方法比较与经验提炼-v001","揭晓后参考/方法比较与创新分析"),
 ("工作记录/揭晓后对照/最终方法与创新总结-v001","揭晓后参考/最终方法与创新总结")]:
    cp_tree_files(sub,target,lambda s,r:s.suffix.lower() in {".md",".py",".json",".csv"} and s.name not in {"归档文件清单-v001.json","归档文件清单-v001.csv"} and s.stat().st_size<5_000_000,"揭晓后","本方分析与方法学习")

# Mapping without self-reference
outdir=BASE/"解题过程"
outdir.mkdir(parents=True,exist_ok=True)
with (outdir/"归档映射-v001.csv").open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(MAP[0])); w.writeheader(); w.writerows(MAP)
(outdir/"归档映射-v001.json").write_text(json.dumps({"schema":"archive-copy-map-v001","entries":MAP},ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"copied_files":len(MAP),"copied_bytes":sum(x["bytes"] for x in MAP)},ensure_ascii=True))

