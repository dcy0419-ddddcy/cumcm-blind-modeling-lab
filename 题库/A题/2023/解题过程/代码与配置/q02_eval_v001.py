"""Q2 parameterized evaluation v001. Pinned Q1 geometry only; no search or annual runner."""
from __future__ import annotations
import hashlib, json, math, sys
from dataclasses import dataclass, field as dcfield
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
CORE=HERE/'q01_core_v003.py'
CORE_SHA='7d7e70b8c85b1bc7762efdc08fadc972635d810ceb852bf74bfb2cc318ed1693'
if hashlib.sha256(CORE.read_bytes()).hexdigest()!=CORE_SHA: raise RuntimeError('Pinned Q1 core changed')
sys.path.insert(0,str(HERE))
import q01_core_v003 as c
BETA=.00465; RHO=.92
class StateError(ValueError): pass

def clean(x):
    if isinstance(x,np.ndarray): return clean(x.tolist())
    if isinstance(x,np.generic): return clean(x.item())
    if isinstance(x,dict): return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)): return [clean(v) for v in x]
    if isinstance(x,float) and not math.isfinite(x): return None
    return x

def digest(x): return hashlib.sha256(json.dumps(clean(x),sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()

@dataclass
class Scene:
    mirrors: object
    s0: np.ndarray
    target: np.ndarray
    receiver: object
    dni: float
    tau: np.ndarray
    beta: float=BETA
    tol: object=dcfield(default_factory=c.Tolerance)
    tag: dict=dcfield(default_factory=dict)
    domain: dict=dcfield(default_factory=dict)
    @property
    def n(self): return len(self.mirrors.centers)
    @property
    def areas(self): return self.mirrors.widths*self.mirrors.heights
    @property
    def key(self):
        f=self.mirrors
        return digest({'tag':self.tag,'centers':f.centers,'normals':f.normals,'u':f.u,'v':f.v,
                       'widths':f.widths,'heights':f.heights,'sun':self.s0,'target':self.target,
                       'receiver':[self.receiver.center,self.receiver.radius,self.receiver.height],
                       'beta':self.beta,'tolerance':[self.tol.scale_m,self.tol.factor],'core_sha':CORE_SHA})

@dataclass(frozen=True)
class BoundCandidates:
    scene_sha256: str
    index: int
    incoming: tuple
    outgoing: tuple

def candidates(scene,i):
    if not 0<=i<scene.n: raise StateError('INPUT_FAILURE: object index')
    return BoundCandidates(scene.key,i,tuple(int(x) for x in c.conservative_candidates(scene.mirrors,i,scene.s0,scene.beta,scene.tol)),
                           tuple(int(x) for x in c.conservative_candidates(scene.mirrors,i,scene.target[i],scene.beta,scene.tol)))

def checked_cache(scene,i,cache):
    if not isinstance(cache,BoundCandidates) or cache.scene_sha256!=scene.key or cache.index!=i:
        raise StateError('CACHE_INVALID: scene/layout/ordering/dimensions/tower/time/cone/tolerance binding differs')
    for seq in [cache.incoming,cache.outgoing]:
        if len(seq)!=len(set(seq)) or any(j==i or j<0 or j>=scene.n for j in seq): raise StateError('CACHE_INVALID: indices')
    return cache.incoming,cache.outgoing

def prepare(design,month,hour):
    from q02_design_v001 import validate_design
    validation=validate_design(design)
    if not validation['schema_valid']: raise StateError('INPUT_FAILURE: '+json.dumps(validation,ensure_ascii=False))
    if not validation['geometry_valid']: raise StateError('GEOMETRY_FAILURE: '+json.dumps(validation,ensure_ascii=False))
    if not validation['search_scope_valid']: raise StateError('SEARCH_SCOPE_FAILURE: w<h')
    centers=np.array([[r['x'],r['y'],design.installation_height] for r in design.mirrors],float)
    receiver=c.Cylinder((float(design.tower_xy[0]),float(design.tower_xy[1]),80.),3.5,8.)
    sun=c.solar(month,hour);target=c.unit(np.asarray(receiver.center)-centers)
    mirrors=c.make_mirrors(centers,c.unit(target+sun['s0']),design.width,design.height)
    domain=c.check_domain(mirrors,sun['s0'],BETA,receiver,target)
    direction_error=float(np.max(np.abs(c.reflect(-np.broadcast_to(sun['s0'],mirrors.normals.shape),mirrors.normals)-target)))
    if direction_error>1e-12: raise StateError('MODEL_DOMAIN_FAILURE: reflected center direction')
    distance=np.linalg.norm(np.asarray(receiver.center)-centers,axis=1)
    tau=.99321-.0001176*distance+1.97e-8*distance**2
    domain.update(target_reflection_error=direction_error,distance_min=float(distance.min()),distance_max=float(distance.max()))
    return Scene(mirrors,sun['s0'],target,receiver,float(sun['dni']),tau,tag={'design_name':design.name,'design_version':design.version,
                'month':int(month),'hour':float(hour),'ids':[r['mirror_id'] for r in design.mirrors],
                'position_keys':[r['position_key'] for r in design.mirrors]},domain=domain)

def seed_words(root,namespace,time_index,position_key,batch):
    words=np.frombuffer(hashlib.sha256(str(position_key).encode()).digest()[:16],dtype='<u4').astype(np.uint64).tolist()
    return [int(root),int(namespace),int(time_index),*map(int,words),int(batch)]

def rays(scene,i,n,seed): return c.random_rays(scene.mirrors,i,scene.s0,scene.beta,n,seed)

def trace(scene,i,o,s,cache=None,screen=True):
    o=np.asarray(o,float);s=np.asarray(s,float)
    if o.shape!=s.shape or o.ndim!=2 or o.shape[1]!=3 or not np.all(np.isfinite(o)) or not np.all(np.isfinite(s)):
        raise StateError('INPUT_FAILURE: ray array')
    if np.max(np.abs(np.linalg.norm(s,axis=1)-1))>1e-12: raise StateError('INPUT_FAILURE: nonunit rays')
    if np.any(s@scene.s0<=0) or np.any(s@scene.mirrors.normals[i]<=0): raise StateError('MODEL_DOMAIN_FAILURE: projection')
    cache=candidates(scene,i) if screen and cache is None else cache
    pair=checked_cache(scene,i,cache) if screen else None
    ev=c.trace(o,s,scene.mirrors,i,scene.s0,scene.target,scene.receiver,scene.beta,scene.tol,screen=screen,candidate_ids=pair)
    g=(s@scene.mirrors.normals[i])/(s@scene.s0)
    return g,ev

def stats(g,ev):
    g=np.asarray(g,float);S=ev['S'];B=ev['B'];R=ev['R'];u=ev['unknown'];f1=S&B;f2=f1&R
    if len(g)==0 or np.any(g<0) or not np.all(np.isfinite(g)): raise StateError('INPUT_FAILURE: weight')
    X=np.column_stack([g,g*f1,g*f2])
    return {'n':len(g),'sums':X.sum(0),'cross':X.T@X,
            'counts':{'shadow':int((~S).sum()),'blocked_after_unshadowed':int((S&~B).sum()),'survive':int(f1.sum()),'capture':int(f2.sum()),'unknown':int(u.sum())},
            'unknown_weight':float(g[u].sum()),'known_capture_weight':float(g[f2&~u].sum())}

def combine(batches):
    if not batches: raise StateError('INPUT_FAILURE: no batches')
    return {'n':sum(b['n'] for b in batches),'sums':sum((np.asarray(b['sums'],float) for b in batches),np.zeros(3)),
            'cross':sum((np.asarray(b['cross'],float) for b in batches),np.zeros((3,3))),
            'counts':{k:sum(b['counts'][k] for b in batches) for k in batches[0]['counts']},
            'unknown_weight':sum(b['unknown_weight'] for b in batches),
            'known_capture_weight':sum(b['known_capture_weight'] for b in batches)}

def cap_certificate(scene,i,axis):
    """Sufficient interval enclosure: every ray from source bounding ball first crosses a finite cap interior."""
    ci=scene.mirrors.centers[i];ri=float(scene.mirrors.radii[i]);cr=np.asarray(scene.receiver.center);tol=scene.tol.length
    if abs(np.linalg.norm(axis)-1)>1e-12: return None
    for sign,side in [(1.,'bottom'),(-1.,'top')]:
        if sign*(cr[2]-ci[2])<=0: continue
        capz=cr[2]-sign*scene.receiver.height/2
        gap=sign*(capz-ci[2]); az=sign*float(axis[2])
        if gap<=ri+tol or az<=0: continue
        theta=math.atan2(float(np.linalg.norm(axis[:2])),az)+scene.beta
        if theta>=math.pi/2: continue
        radial_bound=float(np.linalg.norm(ci[:2]-cr[:2]))+ri+(gap+ri)*math.tan(theta)
        if radial_bound<scene.receiver.radius-tol:
            return {'proof':'source_ball_to_cap_interior_v001','side':side,'source_radius_m':ri,
                    'source_plane_gap_m':gap,'axis_to_vertical_plus_beta_rad':theta,'radial_upper_m':radial_bound,
                    'cap_radius_m':scene.receiver.radius,'strict_margin_m':scene.receiver.radius-radial_bound,
                    'meaning':'all directions in complete cone and all points in mirror bounding ball; first solid contact is nonactive cap'}
    return None

def sphere_miss(scene,i,axis):
    delta=np.asarray(scene.receiver.center)-scene.mirrors.centers[i];distance=float(np.linalg.norm(delta)); axial=float(delta@axis)
    perp=float(np.linalg.norm(delta-axial*axis));rad=float(scene.mirrors.radii[i])+math.hypot(scene.receiver.radius,scene.receiver.height/2)
    excess=perp-(rad+(distance+rad)*math.sin(scene.beta))
    return {'proven':bool(axial<-rad-scene.tol.length or excess>scene.tol.length),'axial_m':axial,'perpendicular_excess_m':excess}

def certify_zero(scene,i):
    """No caller boolean accepted. Recompute sufficient proofs from current bound scene."""
    inc=cap_certificate(scene,i,scene.s0)
    if inc is not None:
        return {'kind':'zero_survivor','scene_sha256':scene.key,'mirror_index':i,'incoming_cap':inc,
                'basis':'incoming first opaque receiver cap implies S=0 everywhere, hence SB=SBR=0'}
    axis=c.reflect(-scene.s0,scene.mirrors.normals[i]); out=cap_certificate(scene,i,axis)
    if out is not None:
        cc=candidates(scene,i); missed=sphere_miss(scene,i,scene.s0)
        clear=len(cc.incoming)==0 and len(cc.outgoing)==0 and missed['proven']
        return {'kind':'zero_capture','scene_sha256':scene.key,'mirror_index':i,'outgoing_cap':out,
                'survivor_identically_one':clear,'incoming_receiver_miss':missed,
                'candidate_counts':[len(cc.incoming),len(cc.outgoing)],'basis':'all reflected rays hit a nonactive cap first, hence SBR=0; SB=1 only if both mirror candidate sets empty and incoming cylinder sphere missed'}
    return {'kind':'unproven','scene_sha256':scene.key,'mirror_index':i,
            'basis':'supported sufficient cap proofs do not apply; sampled zero is not a true-zero certificate'}

def summarize(scene,i,batch,certificate=None):
    if certificate is not None: raise StateError('UNTRUSTED_ZERO_CERTIFICATE: caller-supplied flags are prohibited')
    cert=certify_zero(scene,i);n=int(batch['n']);a,b,d=map(float,batch['sums']);cos=float(scene.mirrors.normals[i]@scene.s0)
    area=float(scene.areas[i]);tau=float(scene.tau[i]);p0=RHO*scene.dni*area*cos
    if n<=0 or a<=0 or cos<=0 or scene.dni<=0: raise StateError('INPUT_FAILURE: positive scale and denominator required')
    if not(0<=d<=b+1e-12 and b<=a+1e-12): raise StateError('IMPLEMENTATION_FAILURE: energy containment')
    f1=b/a;f2=d/a;tr=d/b if b>0 else None;eta=RHO*cos*tau*f2;power=tau*p0*f2;sb=f1
    status='ESTIMATED';total_state='ESTIMATED';comp_state='DEFINED_ESTIMATES'
    if cert['kind']=='zero_survivor':
        if b!=0 or d!=0: raise StateError('CERTIFICATE_CONTRADICTION: observed survival against proof')
        status='TRUE_ZERO_SURVIVOR';sb=0.;tr=None;eta=power=0.;total_state='DEFINED_TRUE_ZERO';comp_state='TRUNCATION_UNDEFINED_ZERO_DENOMINATOR'
    elif cert['kind']=='zero_capture':
        if d!=0: raise StateError('CERTIFICATE_CONTRADICTION: observed capture against proof')
        status='TRUE_ZERO_CAPTURE';eta=power=0.;total_state='DEFINED_TRUE_ZERO';tr=0. if b>0 else None
        if cert.get('survivor_identically_one'): sb=1.;tr=0.
        elif b==0: sb=None;comp_state='SURVIVOR_DENOMINATOR_UNRESOLVED'
    elif b==0:
        status='SAMPLED_ZERO_SURVIVOR';sb=tr=eta=power=None;total_state='UNRESOLVED_SAMPLE_ZERO';comp_state='UNRESOLVED_SAMPLE_ZERO'
    elif d==0:
        status='SAMPLED_ZERO_CAPTURE';tr=eta=power=None;total_state='UNRESOLVED_SAMPLE_ZERO';comp_state='TRUNCATION_UNRESOLVED_SAMPLE_ZERO'
    if batch['counts']['unknown']>0:
        status='BOUNDARY_UNCERTAIN';sb=tr=eta=power=None;total_state='BOUNDARY_UNCERTAIN';comp_state='BOUNDARY_UNCERTAIN'
    raw=np.array([a,b,d])/n;scale=RHO*scene.dni*area
    ans={'status':status,'total_state':total_state,'component_state':comp_state,'certificate':cert,'n':n,'counts':batch['counts'],
         'eta_sb':sb,'eta_cos':cos,'eta_at':tau,'eta_trunc':tr,'eta_ref':RHO,'eta_total':eta,'power_kw':power,
         'area_m2':area,'unit_power_kw_m2':None if power is None else power/area,'dni_kw_m2':scene.dni,
         'analytic_pi0_kw':p0,'estimate_pi1_kw':p0*f1,'estimate_pi2_kw':p0*f2,'estimate_f1':f1,'estimate_f2':f2,
         'estimate_power_kw':tau*p0*f2,'raw_mean':raw,'raw_energy_kw':raw*scale,'raw_projection_residual':raw[0]-cos,
         'boundary_fraction':[batch['known_capture_weight']/a,(batch['known_capture_weight']+batch['unknown_weight'])/a],
         'rated_power_state':'NOT_ASSESSED_DIAGNOSTIC_ONLY'}
    if all(x is not None for x in [sb,tr,eta]):
        ans['five_factor_error']=abs(sb*cos*tau*tr*RHO-eta)
    return clean(ans)

def aggregate(expected_ids,records,total_area):
    """One explicit statistical population only. Incomplete coverage never extrapolated."""
    expected=list(expected_ids);ids=[r['mirror_id'] for r in records]
    if len(expected)!=len(set(expected)) or len(ids)!=len(set(ids)) or not set(ids).issubset(set(expected)):
        raise StateError('INPUT_FAILURE: aggregate identity/uniqueness')
    complete=set(ids)==set(expected)
    fields=['eta_sb','eta_cos','eta_at','eta_trunc','eta_ref','eta_total']
    comps={k:c.fixed_mean([r[k] for r in records]) if complete else None for k in fields}
    p=None if not complete or any(r['power_kw'] is None for r in records) else sum(r['power_kw'] for r in records)
    if complete and not math.isclose(sum(r['area_m2'] for r in records),total_area,rel_tol=1e-13,abs_tol=1e-12):
        raise StateError('INPUT_FAILURE: total area disagrees with records')
    return {'coverage':'COMPLETE_EXPLICIT_POPULATION' if complete else 'PARTIAL_NO_FIELD_EXTRAPOLATION',
            'expected_count':len(expected),'completed_count':len(ids),'missing_ids':sorted(set(expected)-set(ids)),
            'component_means':comps,'total_power_kw':p,'total_power_state':'DEFINED' if p is not None else 'UNDEFINED_OR_INCOMPLETE',
            'total_area_m2':total_area,'unit_power_kw_m2':None if p is None else p/total_area,
            'rated_power_state':'NOT_ASSESSED_DIAGNOSTIC_ONLY'}