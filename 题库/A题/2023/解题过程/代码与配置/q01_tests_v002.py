"""Independent analytic tests and local R1/R2 checks; no target data read."""
import json, math, sys, time, hashlib, traceback
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import q01_core_v002 as core
ROOT=Path(__file__).resolve().parents[2]
CFG=json.loads((Path(__file__).parent/"Q01-原型配置-v001.json").read_text(encoding="utf-8-sig"))
OUT=ROOT/"工作记录/诊断结果/Q01-基础与交叉验证-v002.json"
if OUT.exists(): raise SystemExit("Preserve previous test evidence; new version required.")
checks=[]; started=time.perf_counter(); tol=core.Tolerance()
def add(name, expected, fn):
    try:
        actual,ok=fn()
        checks.append({"name":name,"expected":expected,"actual":actual,"passed":bool(ok)})
    except Exception:
        checks.append({"name":name,"expected":expected,"passed":False,"failure":traceback.format_exc()})
def geometry_fixture(radius=5,height=10,shadow=False):
    cyl=core.Cylinder((10.,0.,0.),radius,height); s0=np.array([0.,0.,1.])
    centers=[[0,0,0]]; normals=[core.unit([1,0,1])]
    if shadow: centers.append([0,1,5]); normals.append([0,0,1])
    field=core.make_mirrors(centers,normals,width=[2,4] if shadow else 2,
                            height=[2,2] if shadow else 2)
    target=np.tile([1.,0.,0.],(len(centers),1))
    return field,s0,target,cyl

def directions_test():
    sun=core.solar(3,12); am=core.solar(3,9); pm=core.solar(3,15)
    d=np.array([.6,0,-.8]); r=core.reflect(d,np.array([0,0,1.]))
    f,s,t,c=geometry_fixture()
    aimed=core.reflect(-s,f.normals[0])
    coords=np.array([.3,-.7,0.])
    R=np.column_stack((f.u[0],f.v[0],f.normals[0]))
    nnear=core.make_mirrors([[0,0,0]],[[1e-14,0,1]])
    nvert=core.make_mirrors([[0,0,0]],[[0,0,1]])
    err=max(np.max(np.abs(r-[.6,0,.8])),np.max(np.abs(aimed-t[0])),
            np.max(np.abs(R.T@R-np.eye(3))),np.max(np.abs(R.T@(R@coords)-coords)))
    ok=err<1e-13 and am["s0"][0]>0 and pm["s0"][0]<0 and sun["D"]==0 and \
       not nnear.vertical[0] and nvert.vertical[0] and core.solar(4,12)["D"]==31
    return {"max_algebra_error":float(err),"morning_east":float(am["s0"][0]),
            "afternoon_east":float(pm["s0"][0]),"strict_vertical":bool(nvert.vertical[0]),
            "near_vertical_not_substituted":not bool(nnear.vertical[0])},ok
add("T01_direction_time_frame","reflection [.6,0,.8]; central ray +x; AM east/PM west; strict vs near vertical distinct",directions_test)

def rect_test():
    f=core.make_mirrors([[0,0,0]],[[0,0,1]],2,2)
    o=np.array([[0,0,1],[2,0,1],[1,0,1],[0,0,1],[0,0,0],[0,0,-1],[0,0,0]],float)
    d=np.array([[0,0,-1],[0,0,-1],[0,0,-1],[1,0,0],[0,0,1],[0,0,-1],[1,0,0]],float)
    t,u,ids=core.rectangles(o,d,f,[0],np.inf,tol)
    hits=np.isfinite(t).tolist(); uncertain=u.tolist()
    return {"hits":hits,"uncertain":uncertain},hits==[True,False,True,False,False,False,False] and \
         uncertain==[False,False,True,False,True,False,True]
add("T02_finite_rectangle","inside/outside/edge/parallel/self/behind/coplanar explicit",rect_test)

def cyl_test():
    c=core.Cylinder((0,0,0),1,2)
    o=np.array([[-2,0,0],[0,0,3],[0,0,0],[-2,1,0],[2,0,0],[-2,0,2]],float)
    d=core.unit(np.array([[1,0,0],[0,0,-1],[1,0,0],[1,0,0],[1,0,0],[1,0,-1]],float))
    t,k,a,u=core.cylinder_first(o,d,c,tol)
    return {"kind":k.tolist(),"active":a.tolist(),"uncertain":u.tolist(),
            "first_distances":[float(x) if np.isfinite(x) else None for x in t]}, \
           k.tolist()==["side","cap","exit","side","miss","side"] and \
           a[:5].tolist()==[True,False,False,False,False] and bool(u[3]) and bool(u[5]) and \
           abs(t[0]-1)<1e-13 and abs(t[1]-2)<1e-13
add("T03_finite_cylinder","side entry t=1; cap first t=2; interior exit inactive; tangent/rim uncertain; backward miss",cyl_test)

def trace_test():
    f,s,t,c=geometry_fixture(radius=1,height=2)
    # Second test ray intentionally starts at y=2: independent ray-event fixture.
    o=np.array([[0,0,0],[0,2,0]],float); rays=np.tile(s,(2,1))
    ext=core.make_mirrors([[0,0,0],[13,2,0]],[f.normals[0],[1,0,0]],width=[2,1],height=[2,1])
    tar=np.tile([1.,0,0],(2,1))
    e0=core.trace(o,rays,ext,0,s,tar,c,0,tol,False)
    e1=core.trace(o,rays,ext,0,s,tar,c,0,tol,False,end_offset=5)
    g=np.ones(2)
    a=core.summarize(g,e0["S"],e0["B"],e0["R"],e0["unknown"],1,1,1,1)
    b=core.summarize(g,e1["S"],e1["B"],e1["R"],e1["unknown"],1,1,1,1)
    # Move obstruction behind the captured ray: must remain received.
    ext.centers[1]=[13,0,0]
    after=core.trace(o[:1],rays[:1],ext,0,s,tar,c,0,tol,False,end_offset=5)
    return {"baseline":[a["estimate_f1"],a["eta_trunc"],a["estimate_f2"]],
            "extended":[b["estimate_f1"],b["eta_trunc"],b["estimate_f2"]],
            "behind_receiver_captured":bool(after["S"][0]&after["B"][0]&after["R"][0])}, \
           abs(a["estimate_f2"]-.5)<1e-13 and abs(b["estimate_f2"]-.5)<1e-13 and \
           a["eta_sb"]==1 and b["eta_sb"]==.5 and a["eta_trunc"]==.5 and b["eta_trunc"]==1 and bool(after["B"][0])
add("T04_N04_and_first_receiver","endpoint extends only miss ray: sb 1->.5, trunc .5->1, capture .5 unchanged",trace_test)

def overlaps():
    f,s,t,c=geometry_fixture()
    o=np.array([[0,0,0],[0,.3,0]],float); rays=np.tile(s,(2,1))
    one=core.make_mirrors([[0,0,0],[0,0,3]],[f.normals[0],[0,0,1]],width=[2,10],height=[2,10])
    two=core.make_mirrors([[0,0,0],[0,0,3],[0,0,3]],[f.normals[0],[0,0,1],[0,0,1]],width=[2,10,10],height=[2,10,10])
    a=core.trace(o,rays,one,0,s,np.tile([1.,0,0],(2,1)),c,0,tol,False)
    b=core.trace(o,rays,two,0,s,np.tile([1.,0,0],(3,1)),c,0,tol,False)
    return {"one_S":a["S"].tolist(),"duplicate_S":b["S"].tolist()}, \
        not a["S"].any() and np.array_equal(a["S"],b["S"])
add("T05_overlap_union","duplicate opaque obstacles do not deduct twice",overlaps)

def energy_zero():
    g=np.array([.1,.2,.3,.4]); S=np.array([1,1,0,1],bool); B=np.array([1,0,1,1],bool); R=np.array([0,1,1,1],bool)
    a=core.summarize(g,S,B,R,np.zeros(4,bool),.25,1,1,1)
    z=core.summarize(g,np.zeros(4,bool),B,R,np.zeros(4,bool),.25,1,1,1,certificate="zero_survivor")
    sample=core.summarize(g,np.zeros(4,bool),B,R,np.zeros(4,bool),.25,1,1,1)
    failed=False
    try: core.summarize(np.array([-1]),[1],[1],[1],[0],1,1,1,1)
    except core.DomainError: failed=True
    return {"weighted":[a["eta_sb"],a["eta_trunc"],a["estimate_f2"]],
            "true_zero_status":z["status"],"true_zero_power":z["power_kw"],
            "sample_zero_status":sample["status"],"sample_zero_power":sample["power_kw"],
            "input_rejected":failed}, \
            np.allclose([a["eta_sb"],a["eta_trunc"],a["estimate_f2"]],[.5,.8,.4]) and \
            z["eta_trunc"] is None and z["power_kw"]==0 and sample["power_kw"] is None and failed
add("T06_energy_zero_states","weighted .5/.8/.4; certified zero power differs from sampled zero",energy_zero)

def angular():
    n=131072; beta=math.pi/6; s0=np.array([0.,0.,1.]); normal=np.array([.6,0,.8])
    rng=np.random.Generator(np.random.PCG64(202609041))
    uv=rng.random((n,2)); s=core.cone_directions(s0,beta,uv[:,0],uv[:,1])
    mu=s@s0; normalized=(1-mu)/(1-math.cos(beta))
    fractions=[.1,.25,.5,.75,.9]
    cdf=[float(np.mean(normalized<=x)) for x in fractions]
    err=max(abs(a-b) for a,b in zip(cdf,fractions))
    g=(s@normal)/mu
    analytic_variance=(1-.8**2)/2*(1/math.cos(beta)-1)
    se=math.sqrt(analytic_variance/n)
    # Independent product quadrature in mu/phi verifies analytic projection integral.
    u,v=np.meshgrid((np.arange(128)+.5)/128,(np.arange(128)+.5)/128,indexing="ij")
    sq=core.cone_directions(s0,beta,u.ravel(),v.ravel())
    exactq=float(np.mean((sq@normal)/(sq@s0)))
    return {"cdf":cdf,"max_cdf_error":err,"raw_mean_g":float(g.mean()),"analytic_mean":.8,
            "analytic_se":se,"quadrature_g":exactq,"variance":float(g.var())}, \
        err<.006 and abs(g.mean()-.8)<6*se and abs(exactq-.8)<1e-13
add("T07_distribution_and_independent_projection","U cumulative mass and E[g]=.8; analytic variance used independently",angular)

def bias_check():
    # One iid draw from two equally likely states (weight,event)=(1,0),(3,1).
    exact_weighted=.75
    expected_one_sample=(0+1)/2
    return {"ratio_of_expectations":exact_weighted,
            "expectation_of_one_sample_ratio":expected_one_sample},expected_one_sample!=exact_weighted
add("T08_ratio_bias_counterexample","one-sample self-normalized expectation .5 differs from weighted target .75",bias_check)

def h02_test():
    arr=np.ones((2,2,2,5))
    arr[:,:,:,0]=np.array([[[.2,.8],[.4,.6]],[[.3,.7],[.9,.1]]])
    arr[:,:,:,1]=1-arr[:,:,:,0]
    dni=np.array([[1,2],[3,4.]])
    a=core.h02_summary(arr,dni,[2,2])
    expected_power=float(np.mean([.64,1.92,2.52,1.44]))
    missing=arr.copy(); missing[0,0,0,0]=np.nan
    b=core.h02_summary(missing,dni,[2,2])
    return {"power_year":a["power_year"],"expected":expected_power,
            "total_year":a["total_year"],"product_means":float(np.prod(a["component_year"])),
            "NA_propagates":bool(np.isnan(b["power_year"]))}, \
            abs(a["power_year"]-expected_power)<1e-13 and np.isnan(b["power_year"]) and \
            abs(a["total_year"]-np.prod(a["component_year"]))>.01 and core.fixed_mean([1,None]) is None
add("T09_H02_synthetic","same-time power paired before averaging; NA propagates; mean product not product mean",h02_test)

def direct_zero_aggregate():
    a=np.ones((1,1,2,5)); a[0,0,0,0]=0; a[0,0,0,3]=np.nan
    out=core.h02_summary(a,[[1.]],[2.,2.],direct_total=[[[0.,1.]]])
    return {"power":out["power_year"],"component_NA":bool(np.isnan(out["component_year"][3]))}, \
           out["power_year"]==2. and np.isnan(out["component_year"][3])
add("T09b_direct_total_with_NA","known direct zero preserves power while component remains NA",direct_zero_aggregate)

def invalid_domain():
    f,s,t,c=geometry_fixture()
    failures=[]
    for which in ["horizon","N04"]:
        try:
            if which=="horizon": core.check_domain(f,core.unit([1,0,.0001]),.1,c,t)
            else: core.trace(np.array([[0.,0,0]]),np.array([[0.,0,-1]]),f,0,s,t,c,0,tol)
        except core.DomainError: failures.append(which)
    return failures,failures==["horizon","N04"]
add("T10_domain_failures","no horizon truncation, no infinite N04 fallback",invalid_domain)

# Gate local cross checks on deterministic/analytic foundations.
cross=[]; total_rays=0
if all(c["passed"] for c in checks):
    for name,radius,height,shadow,beta,expected in [
        ("finite_cone_half_shadow",5.,10.,True,.00465,.5),
        ("zero_angle_finite_receiver",.6,1.,False,0.,.6/math.sqrt(2))]:
        f,s,t,c=geometry_fixture(radius,height,shadow)
        rr=[]; qq=[]
        for n in CFG["synthetic"]["r1_samples"]:
            for b in range(CFG["synthetic"]["batches"]):
                o,ds=core.random_rays(f,0,s,beta,n,[CFG["seed"],701,len(cross),b])
                a,_=core.evaluate(f,0,s,t,c,beta,tol,o,ds)
                rr.append({"n":n,"batch":b,"f2":a["estimate_f2"],"trunc":a["eta_trunc"],
                           "raw_mean":a["raw_mean"],"projection_residual":a["raw_projection_residual"],
                           "boundary":a["boundary_weight_fraction"]})
                total_rays+=n
        for dims in CFG["synthetic"]["r2_levels"]:
            o,ds=core.quadrature_rays(f,0,s,beta,*dims)
            a,_=core.evaluate(f,0,s,t,c,beta,tol,o,ds)
            qq.append({"nodes":dims,"count":len(o),"f2":a["estimate_f2"],
                       "projection_residual":a["raw_projection_residual"],
                       "boundary":a["boundary_weight_fraction"]})
            total_rays+=len(o)
        last=[x["f2"] for x in rr if x["n"]==CFG["synthetic"]["r1_samples"][-1]]
        cross.append({"name":name,"analytic_f2":expected,"r1":rr,"r2":qq,
                      "r1_final_mean":float(np.mean(last)),"r1_final_range":float(np.ptp(last)),
                      "passed":abs(np.mean(last)-expected)<CFG["synthetic"]["cross_abs_tolerance"]
                       and abs(qq[-1]["f2"]-expected)<CFG["synthetic"]["cross_abs_tolerance"]
                       and abs(np.mean(last)-qq[-1]["f2"])<CFG["synthetic"]["cross_abs_tolerance"]})
result={"scope":"synthetic tests only, no target rows read","checks":checks,"cross_checks":cross,
        "all_pass":all(c["passed"] for c in checks) and len(cross)==2 and all(c["passed"] for c in cross),
        "synthetic_rays":total_rays,"within_ray_cap":total_rays<=CFG["synthetic"]["max_total_rays"],
        "elapsed_seconds":time.perf_counter()-started,
        "core_sha256":hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest(),
        "config_sha256":hashlib.sha256((Path(__file__).parent/"Q01-原型配置-v001.json").read_bytes()).hexdigest(),
        "python":sys.version,"numpy":np.__version__}
result["all_pass"] &= result["within_ray_cap"]
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=lambda x: x.item() if isinstance(x,np.generic) else str(x))+"\n",encoding="utf-8")
print(json.dumps({"all_pass":result["all_pass"],"failed":[x for x in checks if not x["passed"]],
                  "cross":[{k:v for k,v in x.items() if k not in ["r1","r2"]} for x in cross],
                  "rays":total_rays,"seconds":result["elapsed_seconds"]},ensure_ascii=False,indent=2,default=lambda x: x.item() if isinstance(x,np.generic) else str(x)))
raise SystemExit(0 if result["all_pass"] else 1)
