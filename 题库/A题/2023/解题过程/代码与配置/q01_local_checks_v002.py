"""Revise only the floating comparison of saved local diagnostics; no rays rerun."""
import json,sys,math,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"工作记录/诊断结果/Q01-局部细化补充-v001.json"
OUT=ROOT/"工作记录/诊断结果/Q01-局部细化补充-v002.json"
if OUT.exists(): raise SystemExit("Preserve evidence")
r=json.loads(SOURCE.read_text(encoding="utf-8-sig"))
changes=[]
for item in r["spatial"]:
    n=item["na"]**2
    gamma=n*sys.float_info.epsilon/(1-n*sys.float_info.epsilon)
    tol=4*gamma
    # A conservative accumulation/ratio allowance for this bounded constant-weight case.
    before=item["estimate_inside_bound"]
    after=item["independent_cell_lower"]-tol <= item["f2"] <= item["independent_cell_upper"]+tol
    item["estimate_inside_bound_with_roundoff"]=after
    item["machine_comparison_allowance"]=tol
    changes.append({"na":item["na"],"strict_comparison_before":before,"after":after,
                    "lower_residual":item["f2"]-item["independent_cell_lower"],"allowance":tol})
r["revision"]="Only floating comparison changed; original analytic bounds and every computed value retained."
r["source_sha256"]=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
r["source_file"]="工作记录/诊断结果/Q01-局部细化补充-v001.json"
r["comparison_changes"]=changes
r["additional_rays_executed"]=0
r["all_checks_pass"]=all(x["inside_bound"] and x["estimate_inside_bound_with_roundoff"] for x in r["spatial"]) and \
                    all(abs(x["f2"]-.5)<1e-10 for x in r["angular"]) and r["seed_repeatable"]
OUT.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"all_checks_pass":r["all_checks_pass"],"changes":changes,"additional_rays":0},ensure_ascii=False,indent=2))
raise SystemExit(0 if r["all_checks_pass"] else 1)

