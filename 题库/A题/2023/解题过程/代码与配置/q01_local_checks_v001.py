"""Targeted synthetic follow-up; original cross-test results remain unchanged."""
import sys,json,math,time,hashlib
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import q01_core_v002 as core
ROOT=Path(__file__).resolve().parents[2]; start=time.perf_counter()
cfg=json.loads((Path(__file__).parent/"Q01-补充验证配置-v001.json").read_text(encoding="utf-8-sig"))
OUT=ROOT/"工作记录/诊断结果/Q01-局部细化补充-v001.json"
if OUT.exists(): raise SystemExit("Preserve evidence")
s=np.array([0.,0,1]); normal=core.unit([1,0,1]); t=np.array([[1.,0,0]])
f=core.make_mirrors([[0,0,0]],[normal],2,2)
c=core.Cylinder((10,0,0),.6,1); tol=core.Tolerance()
spatial=[]; rays=0
for n in cfg["spatial_na"]:
    o,ds=core.quadrature_rays(f,0,s,0,n,1,1)
    a,_=core.evaluate(f,0,s,t,c,0,tol,o,ds)
    # Independent reduction: receiver event is |u|<=.6 and |v|<=1/sqrt(2).
    edges=np.linspace(-1,1,n+1); lo,hi=edges[:-1],edges[1:]
    mx=np.maximum(np.abs(lo),np.abs(hi))
    minabs=np.where((lo<=0)&(hi>=0),0,np.minimum(np.abs(lo),np.abs(hi)))
    inside=(mx[:,None]<=.6)&(mx[None,:]<=1/math.sqrt(2))
    outside=(minabs[:,None]>.6)|(minabs[None,:]>1/math.sqrt(2))
    lower=float(inside.mean()); upper=float((~outside).mean())
    spatial.append({"na":n,"f2":a["estimate_f2"],"analytic":.6/math.sqrt(2),
                    "independent_cell_lower":lower,"independent_cell_upper":upper,
                    "inside_bound":lower<=.6/math.sqrt(2)<=upper,
                    "estimate_inside_bound":lower<=a["estimate_f2"]<=upper})
    rays+=len(o)
# Hold mirror-space grid fixed, vary angular resolution and shift azimuth nodes.
fh=core.make_mirrors([[0,0,0],[0,1,5]],[normal,[0,0,1]],width=[2,4],height=[2,2])
th=np.tile(t,(2,1)); ch=core.Cylinder((10,0,0),5,10); angular=[]
for nmu,nphi in cfg["angle_levels"]:
    o,ds=core.quadrature_rays(fh,0,s,.00465,cfg["angle_na"],nmu,nphi,phase=cfg["phase"])
    a,_=core.evaluate(fh,0,s,th,ch,.00465,tol,o,ds)
    angular.append({"nmu":nmu,"nphi":nphi,"azimuth_phase":cfg["phase"],
                    "f2":a["estimate_f2"],"analytic":.5})
    rays+=len(o)
a,b=core.random_rays(f,0,s,.00465,16,[2026090401,999,0])
aa,bb=core.random_rays(f,0,s,.00465,16,[2026090401,999,0])
ac,bc=core.random_rays(f,0,s,.00465,16,[2026090401,999,1])
repro=bool(np.array_equal(a,aa) and np.array_equal(b,bb) and not np.array_equal(b,bc))
result={"scope":cfg["scope"],"spatial":spatial,"angular":angular,"seed_repeatable":repro,
        "rays":rays,"elapsed_seconds":time.perf_counter()-start,"core_sha256":hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest(),
        "all_checks_pass":all(x["inside_bound"] and x["estimate_inside_bound"] for x in spatial)
           and all(abs(x["f2"]-.5)<1e-10 for x in angular) and repro and rays<=cfg["synthetic_ray_cap"],
        "claim":"Bounds valid only for this independently reduced rectangle event; no universal order or error bound"}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(result,ensure_ascii=False,indent=2))

