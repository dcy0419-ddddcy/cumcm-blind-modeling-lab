"""Bounded Q1 prototype prepare/pilot/trial. Never exposes a full-year optical mode."""
import argparse, json, sys, time, hashlib, platform, traceback
from datetime import datetime
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import q01_core_v002 as core
ROOT=Path(__file__).resolve().parents[2]
if ROOT!=Path(r"C:\Users\admin\OneDrive\Desktop\26国赛-单题盲解区\A-P8C3"):
    raise SystemExit("Unexpected workspace")
CONFIG=Path(__file__).parent/"Q01-原型配置-v001.json"
cfg=json.loads(CONFIG.read_text(encoding="utf-8-sig"))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(rel): return json.loads((ROOT/rel).read_text(encoding="utf-8-sig"))
def save(rel,data):
    p=ROOT/rel
    with p.open("x",encoding="utf-8") as f:
        json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False,
                  default=lambda x:x.item() if isinstance(x,np.generic) else x.tolist())
        f.write("\n")
def metadata():
    return {"time":datetime.now().astimezone().isoformat(),"python":sys.version,
            "numpy":np.__version__,"platform":platform.platform(),
            "core_sha256":sha(Path(core.__file__)),"runner_sha256":sha(Path(__file__)),
            "config_sha256":sha(CONFIG),"input_sha256":sha(ROOT/"附件/附件03.xlsx"),
            "scope":"diagnostic only; not field/year estimate"}
cyl=core.Cylinder(); tol=core.Tolerance(cfg["geometry"]["length_scale_m"],cfg["geometry"]["factor"])
def tau_for(center):
    dist=np.linalg.norm(np.array(cyl.center)-center)
    if dist>1000: raise core.DomainError("Atmosphere domain")
    return .99321-.0001176*dist+1.97e-8*dist**2

def frozen_selection():
    plan=read("工作记录/诊断结果/Q01-预选与适用域-v001.json")
    if plan["metadata"]["config_sha256"]!=sha(CONFIG) or plan["metadata"]["input_sha256"]!=sha(ROOT/"附件/附件03.xlsx"):
        raise RuntimeError("Frozen selection inputs changed")
    ids=[x["mirror_id"]-1 for x in plan["selected"]]
    times=plan["times"]
    if len(ids)>6 or len(times)>3 or len(ids)*len(times)>18: raise RuntimeError("Scope cap")
    return plan,ids,times
def foundation_gate():
    result=read("工作记录/诊断结果/Q01-基础与交叉验证-v002.json")
    if not result["all_pass"] or result["core_sha256"]!=sha(Path(core.__file__)):
        raise RuntimeError("Foundation gate or code version failed")

def run_one(field,i,sun,target,n,batch,stage,screen=True):
    words=[cfg["seed"],stage,int(sun["month"]),int(sun["hour"]*100),i+1,batch]
    o,s=core.random_rays(field,i,sun["s0"],cfg["beta_rad"],n,words)
    arrays={k:[] for k in ["S","B","R","unknown","incoming_object","blocking_object","receiver_kind"]}
    chunk=cfg["trial"]["chunk_size"]
    for start in range(0,n,chunk):
        ev=core.trace(o[start:start+chunk],s[start:start+chunk],field,i,sun["s0"],target,cyl,
                      cfg["beta_rad"],tol,screen)
        for key in arrays: arrays[key].append(ev[key])
    ev_all={k:np.concatenate(v) for k,v in arrays.items()}
    g=(s@field.normals[i])/(s@sun["s0"])
    result=core.summarize(g,ev_all["S"],ev_all["B"],ev_all["R"],ev_all["unknown"],
          float(field.normals[i]@sun["s0"]),36.,sun["dni"],tau_for(field.centers[i]),cfg["rho"])
    result["candidate_counts"]=[ev["candidate_in"],ev["candidate_out"]]
    result["seed_words"]=words
    result["abnormal_examples"]=[{"sample":int(j),"point":o[j].tolist(),"direction":s[j].tolist(),
             "receiver_kind":str(ev_all["receiver_kind"][j]),"incoming_object_index":int(ev_all["incoming_object"][j]),
             "blocking_object_index":int(ev_all["blocking_object"][j])}
             for j in np.flatnonzero(ev_all["unknown"])[:8]]
    return result,ev_all

def prepare():
    centers,rows=core.read_field(ROOT/"附件/附件03.xlsx")
    radius=np.linalg.norm(centers[:,:2],axis=1)
    orders=[np.argsort(centers[:,0],kind="stable"),np.argsort(-centers[:,0],kind="stable"),
            np.argsort(centers[:,1],kind="stable"),np.argsort(-centers[:,1],kind="stable"),
            np.argsort(radius,kind="stable"),np.argsort(-radius,kind="stable")]
    used=set(); selected=[]
    for rule,order in zip(cfg["selection"]["rules"],orders):
        i=next(int(j) for j in order if int(j) not in used); used.add(i)
        selected.append(dict(rows[i],rule=rule,radius_m=float(radius[i])))
    checks=[]
    for month in range(1,13):
        for hour in [9,10.5,12,13.5,15]:
            sun=core.solar(month,hour)
            field,target=core.aim_field(centers,sun["s0"],cyl)
            try:
                check=core.check_domain(field,sun["s0"],cfg["beta_rad"],cyl,target)
                check["passed"]=True
            except Exception as e: check={"passed":False,"failure":str(e)}
            checks.append(dict(month=month,hour=hour,D=sun["D"],alpha_rad=sun["alpha"],s0=sun["s0"].tolist(),**check))
    result={"metadata":metadata(),"selection_frozen_before_optics":True,"selected":selected,
            "times":cfg["selection"]["times"],"combination_count":len(selected)*len(cfg["selection"]["times"]),
            "full_obstacle_count":len(centers),"domain_checks_only":checks,
            "all_domain_pass":all(c["passed"] for c in checks)}
    save("工作记录/诊断结果/Q01-预选与适用域-v001.json",result)
    print(json.dumps({"selected":selected,"times":result["times"],"all_domain_pass":result["all_domain_pass"]},ensure_ascii=False,indent=2))

def pilot():
    foundation_gate(); plan,ids,times=frozen_selection()
    centers,_=core.read_field(ROOT/"附件/附件03.xlsx")
    records=[]; begin=time.perf_counter(); n=cfg["pilot"]["rays_per_combination"]
    for tm in times:
        sun=dict(core.solar(tm["month"],tm["hour"]),month=tm["month"],hour=tm["hour"])
        field,target=core.aim_field(centers,sun["s0"],cyl)
        core.check_domain(field,sun["s0"],cfg["beta_rad"],cyl,target)
        for i in ids:
            if time.perf_counter()-begin>cfg["pilot"]["max_seconds"]: raise RuntimeError("Pilot time cap")
            start=time.perf_counter(); a,ea=run_one(field,i,sun,target,n,0,801,False); full_time=time.perf_counter()-start
            start=time.perf_counter(); b,eb=run_one(field,i,sun,target,n,0,801,True); screened_time=time.perf_counter()-start
            equal=all(np.array_equal(ea[k],eb[k]) for k in ["S","B","R","unknown"])
            records.append({"mirror_id":i+1,"month":tm["month"],"hour":tm["hour"],
               "event_equal":equal,"full_seconds":full_time,"screened_seconds":screened_time,
               "screened_candidates":b["candidate_counts"],"unknown_count":a["counts"]["unknown"],
               "projection_residual":a["raw_projection_residual"]})
            print(f"pilot mirror={i+1} month={tm['month']} hour={tm['hour']} equal={equal}",flush=True)
    elapsed=time.perf_counter()-begin
    result={"metadata":metadata(),"n_per_combination":n,"combinations":records,
            "all_equal":all(r["event_equal"] for r in records),"elapsed_seconds":elapsed,
            "same_rays_full_and_screened":True,"full_obstacle_count":len(centers),
            "projected_trial_seconds":sum(r["screened_seconds"] for r in records)/n*
                sum(cfg["trial"]["samples"])*cfg["trial"]["batches"]}
    save("工作记录/诊断结果/Q01-小样本计时与筛选核对-v001.json",result)
    print(json.dumps({k:v for k,v in result.items() if k not in ["metadata","combinations"]},ensure_ascii=False,indent=2))

def trial():
    foundation_gate(); plan,ids,times=frozen_selection()
    timing=read("工作记录/诊断结果/Q01-小样本计时与筛选核对-v001.json")
    if not timing["all_equal"]: raise RuntimeError("Candidate/full mismatch")
    if timing["projected_trial_seconds"]>cfg["trial"]["max_seconds"]:
        raise RuntimeError("Projected budget insufficient; do not expand")
    centers,rows=core.read_field(ROOT/"附件/附件03.xlsx")
    begin=time.perf_counter(); rays=0; records=[]; failure=None
    try:
        for tm in times:
            sun=dict(core.solar(tm["month"],tm["hour"]),month=tm["month"],hour=tm["hour"])
            field,target=core.aim_field(centers,sun["s0"],cyl)
            core.check_domain(field,sun["s0"],cfg["beta_rad"],cyl,target)
            for i in ids:
                for n in cfg["trial"]["samples"]:
                    for b in range(cfg["trial"]["batches"]):
                        if rays+n>cfg["trial"]["max_total_rays"] or time.perf_counter()-begin>cfg["trial"]["max_seconds"]:
                            raise RuntimeError("Trial resource cap reached")
                        start=time.perf_counter()
                        a,_=run_one(field,i,sun,target,n,b,802,True)
                        records.append(dict(mirror_id=i+1,excel_row=rows[i]["excel_row"],
                          month=tm["month"],hour=tm["hour"],n=n,batch=b,seconds=time.perf_counter()-start,**a))
                        rays+=n
                print(f"trial completed mirror={i+1} month={tm['month']} hour={tm['hour']}",flush=True)
    except Exception: failure=traceback.format_exc()
    summaries=[]
    for tm in times:
        for i in ids:
            rr=[r for r in records if r["mirror_id"]==i+1 and r["month"]==tm["month"] and r["hour"]==tm["hour"]]
            levels=[]
            for n in cfg["trial"]["samples"]:
                subset=[r for r in rr if r["n"]==n]
                if len(subset)!=cfg["trial"]["batches"]: continue
                # Pool raw sums, not the batch conditional ratios.
                pooled=np.sum([r["raw_sums"] for r in subset],axis=0)
                f1=pooled[1]/pooled[0]; f2=pooled[2]/pooled[0]
                pi0=subset[0]["analytic_pi0_kw"]; tau=subset[0]["tau"]
                levels.append({"n_per_batch":n,"batches":len(subset),"pooled_f1":float(f1),"pooled_f2":float(f2),
                   "pooled_trunc":float(pooled[2]/pooled[1]) if pooled[1]>0 else None,
                   "estimated_power_kw":float(tau*pi0*f2),"f2_batch_range":float(np.ptp([r["estimate_f2"] for r in subset])),
                   "f2_batch_sd":float(np.std([r["estimate_f2"] for r in subset],ddof=1)),
                   "max_projection_residual":max(abs(r["raw_projection_residual"]) for r in subset),
                   "max_boundary_fraction":max(r["boundary_weight_fraction"] for r in subset),
                   "statuses":[r["status"] for r in subset],"candidate_counts":subset[0]["candidate_counts"]})
            item=dict(mirror_id=i+1,month=tm["month"],hour=tm["hour"],levels=levels)
            if len(levels)==len(cfg["trial"]["samples"]):
                a=levels[-1]; crit=cfg["trial"]["diagnostic_criteria"]
                item["last_level_change"]=abs(a["pooled_f2"]-levels[-2]["pooled_f2"])
                item["diagnostic_stability_met"]=(a["f2_batch_range"]<=crit["batch_f2_range"] and
                    item["last_level_change"]<=crit["level_f2_change"] and
                    a["max_projection_residual"]<=crit["projection_abs_error"] and
                    a["max_boundary_fraction"]<=crit["max_boundary_weight"] and
                    all(s=="ESTIMATED" for s in a["statuses"]))
            else: item["diagnostic_stability_met"]=False
            summaries.append(item)
    result={"metadata":metadata(),"full_obstacle_count":len(centers),"evaluated_mirror_count":len(ids),
            "time_count":len(times),"combination_count":len(ids)*len(times),"rays":rays,
            "elapsed_seconds":time.perf_counter()-begin,"failure":failure,"records":records,"summaries":summaries,
            "all_planned_completed":len(records)==len(ids)*len(times)*len(cfg["trial"]["samples"])*cfg["trial"]["batches"],
            "all_diagnostic_stability_met":all(x["diagnostic_stability_met"] for x in summaries),
            "not_a_field_or_year_estimate":True}
    save("工作记录/诊断结果/Q01-本题局部试算-v001.json",result)
    print(json.dumps({k:v for k,v in result.items() if k not in ["metadata","records","summaries"]},ensure_ascii=False,indent=2))

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=["prepare","pilot","trial"])
    args=parser.parse_args()
    {"prepare":prepare,"pilot":pilot,"trial":trial}[args.mode]()

