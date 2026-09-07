"""Prototype delivery integrity checks. No optical evaluation or test reruns."""
import json,hashlib,re,sys,ast
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"工作记录/诊断结果/Q01-原型交付核验-v001.json"
if OUT.exists(): raise SystemExit("Preserve existing evidence")
def path(rel):
    p=(ROOT/rel).resolve()
    if not p.is_relative_to(ROOT): raise ValueError("Outside task")
    return p
def read(rel): return path(rel).read_text(encoding="utf-8-sig")
def js(rel): return json.loads(read(rel))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
checks=[]
def record(name,ok,details): checks.append({"name":name,"passed":bool(ok),"details":details})
baseline=js("工作记录/诊断结果/Q01-方案输入版本-v001.json")["files"]
prior=js("工作记录/诊断结果/Q01-文档核验-v001.json")
planpath="工作记录/阶段记录/Q01-方案构造-v001.md"
baseline=baseline+[next(x for x in prior["artifacts"] if x["path"]==planpath)]
preserved=[{"path":x["path"],"unchanged":sha(path(x["path"]))==x["sha256"]} for x in baseline]
record("13_historical_and_method_inputs_preserved",all(x["unchanged"] for x in preserved),preserved)
corehash=sha(path("工作记录/诊断代码/q01_core_v002.py"))
cfghash=sha(path("工作记录/诊断代码/Q01-原型配置-v001.json"))
tests=js("工作记录/诊断结果/Q01-基础与交叉验证-v002.json")
trial=js("工作记录/诊断结果/Q01-本题局部试算-v001.json")
pilot=js("工作记录/诊断结果/Q01-小样本计时与筛选核对-v001.json")
selection=js("工作记录/诊断结果/Q01-预选与适用域-v001.json")
local=js("工作记录/诊断结果/Q01-局部细化补充-v002.json")
record("actual_tests_and_code_config_binding",
       tests["all_pass"] and len(tests["checks"])==11 and len(tests["cross_checks"])==2
       and tests["core_sha256"]==corehash and tests["config_sha256"]==cfghash
       and trial["metadata"]["core_sha256"]==corehash and trial["metadata"]["config_sha256"]==cfghash
       and pilot["metadata"]["core_sha256"]==corehash and local["core_sha256"]==corehash
       and local["all_checks_pass"],
       {"foundation":len(tests["checks"]),"local_cross":len(tests["cross_checks"]),
        "local_followup":local["all_checks_pass"],"core_hash":corehash})
unique={(r["mirror_id"],r["month"],r["hour"]) for r in trial["records"]}
planned={(x["mirror_id"],t["month"],t["hour"]) for x in selection["selected"] for t in selection["times"]}
record("bounded_preselected_trial_and_full_obstacles",
       unique==planned and len(unique)==18 and len(selection["selected"])==6
       and len(selection["times"])==3 and trial["full_obstacle_count"]==1745
       and trial["rays"]==290304 and trial["rays"]<=300000 and trial["elapsed_seconds"]<=360
       and trial["all_planned_completed"] and trial["all_diagnostic_stability_met"]
       and trial["failure"] is None and len(trial["records"])==162
       and all(r["status"]=="ESTIMATED" for r in trial["records"])
       and pilot["all_equal"] and selection["selection_frozen_before_optics"],
       {"combinations":len(unique),"records":len(trial["records"]),"rays":trial["rays"],
        "selection_time":selection["metadata"]["time"],"pilot_time":pilot["metadata"]["time"],
        "trial_time":trial["metadata"]["time"],"full_obstacles":trial["full_obstacle_count"]})
docs=[
"工作记录/阶段记录/Q01-建模与原型验证-v001.md","工作记录/00-任务状态.md",
"工作记录/记录索引.md","工作记录/方法库查阅记录.md","工作记录/决策记录.md",
"工作记录/06-更新记录.md","工作记录/归档清单.md",
"工作记录/诊断代码/Q01-原型运行说明-v001.md","工作记录/诊断结果/Q01-首次测试失败-v001.md"]
details=[]
for rel in docs:
    body=read(rel); issues=[]; p=path(rel); links=0
    if "\ufffd" in body: issues.append("Bad Unicode")
    for a,b in [(r"\(",r"\)"),(r"\[",r"\]")]:
        if body.count(a)!=body.count(b): issues.append("Unbalanced math "+a)
    for m in re.finditer(r"(?<!!)\[[^\]\n]*\]\(([^)\n]+)\)",body):
        target=m.group(1).strip("<>")
        if re.match(r"^[A-Za-z][\w+.-]*://",target) or target.startswith("#"): continue
        d=(p.parent/target.split("#")[0]).resolve(); links+=1
        if not d.is_relative_to(ROOT): issues.append("Outside link")
        elif not d.exists() and d!=OUT: issues.append("Missing "+target)
    lines=body.splitlines(); i=0; display=False; fence=None; tables=0
    while i<len(lines):
        s=lines[i].strip()
        if fence:
            if s.startswith(fence): fence=None
            i+=1; continue
        if s.startswith("~~~") or s.startswith(chr(96)*3):
            fence=s[:3]; i+=1; continue
        if s==r"\[": display=True; i+=1; continue
        if s==r"\]": display=False; i+=1; continue
        if display or not s.startswith("|"): i+=1; continue
        rows=[]; start=i+1
        while i<len(lines) and lines[i].strip().startswith("|"):
            rows.append(re.split(r"(?<!\\)\|",lines[i].strip())[1:-1]); i+=1
        tables+=1
        if len(rows)<2 or not rows[0] or not all(re.fullmatch(r"\s*:?-{3,}:?\s*",c) for c in rows[1]):
            issues.append(f"Header/separator {start}")
        if any(not c.strip() for c in rows[0]) or any(len(r)!=len(rows[0]) for r in rows):
            issues.append(f"Table cells {start}")
    details.append({"path":rel,"tables":tables,"links":links,"issues":issues})
record("saved_markdown_links_tables_math",all(not x["issues"] for x in details),details)
artifacts=["工作记录/阶段记录/Q01-建模与原型验证-v001.md","工作记录/诊断代码/q01_core_v001.py","工作记录/诊断代码/q01_core_v002.py","工作记录/诊断代码/q01_tests_v001.py","工作记录/诊断代码/q01_tests_v002.py","工作记录/诊断代码/q01_run_v001.py","工作记录/诊断代码/Q01-原型配置-v001.json","工作记录/诊断代码/Q01-补充验证配置-v001.json","工作记录/诊断代码/q01_local_checks_v001.py","工作记录/诊断代码/q01_local_checks_v002.py","工作记录/诊断代码/q01_report_v001.py","工作记录/诊断代码/Q01-原型运行说明-v001.md","工作记录/诊断代码/verify_q01_prototype_v001.py","工作记录/诊断结果/Q01-首次测试失败-v001.md","工作记录/诊断结果/Q01-基础与交叉验证-v002.json","工作记录/诊断结果/Q01-预选与适用域-v001.json","工作记录/诊断结果/Q01-小样本计时与筛选核对-v001.json","工作记录/诊断结果/Q01-本题局部试算-v001.json","工作记录/诊断结果/Q01-局部细化补充-v001.json","工作记录/诊断结果/Q01-局部细化补充-v002.json","工作记录/诊断结果/Q01-原型交付核验-v001.json"]
archive=read("工作记录/归档清单.md")
missing=[x for x in artifacts if x not in archive or (not path(x).exists() and path(x)!=OUT)]
record("archive_all_21_artifacts",not missing,missing)
syntax=[]
for rel in artifacts:
    if rel.endswith(".py"):
        ast.parse(read(rel)); syntax.append(rel)
record("archived_python_syntax",True,syntax)
seq=[]
for rel,prefix in [("工作记录/决策记录.md","D"),("工作记录/06-更新记录.md","U")]:
    numbers=[int(x) for x in re.findall(r"^## "+prefix+r"(\d{3})(?=\s|—|$)",read(rel),re.M)]
    seq.append({"path":rel,"numbers":numbers,"ok":numbers==list(range(1,15))})
record("continued_D_U_numbering",all(x["ok"] for x in seq),seq)
state=read("工作记录/00-任务状态.md")
record("stage_state_separation",
       "第1问建模与原型验证完成，待用户验收；完整评价尚未开始。" in state
       and "管理员归档未确认" in state and "试验性" in state,
       "Prototype acceptance pending; archival not confirmed; N04 experimental")
snap=[{"path":rel,"bytes":path(rel).stat().st_size,"sha256":sha(path(rel))}
      for rel in dict.fromkeys(docs+artifacts) if path(rel)!=OUT]
result={"stage":"Q01-建模与原型验证-v001","checked_at":datetime.now().astimezone().isoformat(),
        "scope":"Document/result binding only; no test or optical rerun","checks":checks,
        "all_pass":all(c["passed"] for c in checks),"artifacts":snap}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"all_pass":result["all_pass"],"checks":len(checks),
                  "failed":[x for x in checks if not x["passed"]]},ensure_ascii=False,indent=2))
raise SystemExit(0 if result["all_pass"] else 1)

