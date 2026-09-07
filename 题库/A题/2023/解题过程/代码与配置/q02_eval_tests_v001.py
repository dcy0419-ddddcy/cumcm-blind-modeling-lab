"""Q2 parameter, geometry, binding and zero-state tests. No diagnostic layouts or optimizer."""
import copy, math, traceback
import numpy as np
import q02_eval_v002 as e
from q02_design_v002 import Design
c=e.c

def artificial_scene(centers,s0,receiver,width=2.,height=2.,beta=e.BETA):
    centers=np.asarray(centers,float);s0=np.asarray(s0,float);target=c.unit(np.asarray(receiver.center)-centers)
    f=c.make_mirrors(centers,c.unit(target+s0),width,height)
    c.check_domain(f,s0,beta,receiver,target)
    return e.Scene(f,s0,target,receiver,1.,np.ones(len(centers)),beta=beta,tag={'scope':'artificial_geometry_only','ids':list(range(1,len(centers)+1))})

def observation(scene,i,n=128,seed=(2026090503,1)):
    o,s=e.rays(scene,i,n,list(seed));g,ev=e.trace(scene,i,o,s);st=e.stats(g,ev)
    return e.summarize(scene,i,st),st,ev

def expect_raises(fn,part):
    try: fn()
    except Exception as ex:
        if part not in str(ex): raise AssertionError('wrong rejection: '+str(ex))
        return str(ex)
    raise AssertionError('expected rejection '+part)

def run_tests():
    rows=[];ray_count=0
    def add(name,expect,fn):
        nonlocal ray_count
        try:
            data,n=fn();ray_count+=n;rows.append({'name':name,'expected':expect,'actual':e.clean(data),'passed':True,'ray_evaluations':n})
        except Exception:
            rows.append({'name':name,'expected':expect,'passed':False,'failure':traceback.format_exc()})
    def params():
        mirrors=[{'mirror_id':8,'position_key':'a','x':150.,'y':0.},{'mirror_id':13,'position_key':'b','x':164.,'y':0.}]
        d=Design('synthetic-parameter-contract','v001',(20.,10.),6.,4.,3.,mirrors)
        a=e.prepare(d,3,12.);b=e.prepare(Design(d.name,'v002',(-20.,10.),8.,6.,5.,copy.deepcopy(mirrors)),3,12.)
        assert a.n==b.n==2 and np.all(a.areas==24) and np.all(b.areas==48)
        assert np.all(a.mirrors.centers[:,2]==3) and np.all(b.mirrors.centers[:,2]==5)
        assert tuple(b.receiver.center)==(-20.,10.,80.) and not np.allclose(a.target,b.target)
        assert np.allclose(a.mirrors.radii,math.hypot(6,4)/2) and np.allclose(b.mirrors.radii,5)
        o1,s1=e.rays(a,0,16,[33]);o2,s2=e.rays(b,0,16,[33])
        local=lambda sc,o:np.column_stack([(o-sc.mirrors.centers[0])@sc.mirrors.u[0]/sc.mirrors.widths[0],(o-sc.mirrors.centers[0])@sc.mirrors.v[0]/sc.mirrors.heights[0]])
        assert np.max(np.abs(local(a,o1)-local(b,o2)))<1e-13 and np.array_equal(s1,s2)
        cache=e.candidates(a,0);variants=[b,e.prepare(d,3,13.5),copy.deepcopy(a),copy.deepcopy(a),copy.deepcopy(a)]
        variants[2].beta*=.9;variants[3].mirrors.centers=variants[3].mirrors.centers[::-1].copy();variants[4].tol=c.Tolerance(factor=512)
        rejections=[expect_raises(lambda sc=sc:e.checked_cache(sc,0,cache),'CACHE_INVALID') for sc in variants]
        assert e.checked_cache(a,0,cache)==(cache.incoming,cache.outgoing)
        return {'areas':[a.areas,b.areas],'centers_z':[3,5],'target_changed':True,'normalized_source_error':float(np.max(np.abs(local(a,o1)-local(b,o2)))),'stale_cache_rejections':len(rejections),'scope':'pure parameter and source mapping; no optics for these legal point sets'},0
    add('E01_parameter_chain_cache','actual dimensions/height/tower/N used; five stale cache changes rejected',params)
    def rectangle():
        f=c.make_mirrors([[0,0,0]],[[0,0,1]],4,2)
        o=np.array([[1.5,0,1],[2.1,0,1],[0,1,1],[0,0,-1],[0,0,0],[0,0,1]],float)
        d=np.array([[0,0,-1]]*5+[[1,0,0]],float)
        t,u,_=c.rectangles(o,d,f,[0],np.inf,c.Tolerance())
        expected=[True,False,True,False,False,False]
        assert np.isfinite(t).tolist()==expected and u[2] and u[4]
        return {'hits':np.isfinite(t),'uncertain':u},6
    add('E02_finite_non_square_rectangle','w=4/h=2, edges and self/parallel/behind classified',rectangle)
    def cyl():
        cyl=c.Cylinder((2,-3,7),1,2);o=np.array([[-2,0,0],[0,0,3],[0,0,0],[-2,1,0],[2,0,0]],float)
        d=np.array([[1,0,0],[0,0,-1],[1,0,0],[1,0,0],[1,0,0]],float)
        a=c.cylinder_first(o,d,c.Cylinder((0,0,0),1,2),c.Tolerance());b=c.cylinder_first(o+np.array(cyl.center),d,cyl,c.Tolerance())
        assert all(np.array_equal(x,y) for x,y in zip(a,b)) and a[1].tolist()==['side','cap','exit','side','miss']
        assert a[3][3] and abs(a[0][0]-1)<1e-13
        return {'kinds':a[1],'active':a[2],'translated_equal':True,'field_boundary_translated':False},10
    add('E03_cylinder_translation','finite side/cap/exit/tangent and optical-only translation invariance',cyl)
    def zeros():
        receiver=c.Cylinder();a=artificial_scene([[0,0,4]],[0,0,1],receiver)
        b=artificial_scene([[0,0,4]],[.6,0,.8],receiver)
        aa,sa,ea=observation(a,0);bb,sb,eb=observation(b,0)
        assert aa['status']=='TRUE_ZERO_SURVIVOR' and aa['eta_sb']==0 and aa['eta_trunc'] is None and aa['power_kw']==0
        assert bb['status']=='TRUE_ZERO_CAPTURE' and bb['eta_sb']==1 and bb['eta_trunc']==0 and bb['power_kw']==0
        assert np.all(~ea['S']) and np.all(eb['S']&eb['B']&~eb['R'])
        fake=copy.deepcopy(sb);fake['sums'][1]*=.5;fake['counts']['survive']=64
        contradiction=expect_raises(lambda:e.summarize(b,0,fake),'CERTIFICATE_CONTRADICTION')
        fakeflag=expect_raises(lambda:e.summarize(b,0,sb,certificate=True),'UNTRUSTED_ZERO_CERTIFICATE')
        return {'true_zero_survivor':aa,'true_zero_capture':bb,'contradiction_rejected':contradiction,'flag_rejected':fakeflag,'scope':'artificial under-tower geometry, not a C22-feasible diagnostic layout'},256
    add('E04_geometry_proven_zeros','automatic full-cone cap proofs; zero total and undefined component remain distinct',zeros)
    def sampled_zero():
        scene=artificial_scene([[0,0,0]],[0,0,1],c.Cylinder((10,0,0),.01,.02))
        ans,st,ev=observation(scene,0,n=64,seed=(2026090503,99))
        gc,center=e.trace(scene,0,np.array([[0.,0.,0.]]),np.array([[0.,0.,1.]]))
        assert ans['status']=='SAMPLED_ZERO_CAPTURE' and ans['power_kw'] is None and ans['estimate_power_kw']==0
        assert center['S'][0] and center['B'][0] and center['R'][0] and not center['unknown'][0]
        assert ans['certificate']['kind']=='unproven'
        return {'sample':ans,'independent_center_interior_hit':True,'basis':'center ray hits side away from rim/tangent; an open neighborhood has positive reception, yet fixed finite sample has none'},65
    add('E05_sampled_zero','finite zero hit does not imply true zero; independent interior hit exists',sampled_zero)
    def domains():
        scene=artificial_scene([[0,0,0]],[0,0,1],c.Cylinder((10,0,0),5,10))
        o=np.array([[0.,0.,0.]]);sun=np.array([[0.,0.,1.]])
        bad1=expect_raises(lambda:e.trace(scene,0,o+10*scene.mirrors.u[0],sun),'RAY_DOMAIN_FAILURE')
        bad2=expect_raises(lambda:e.trace(scene,0,o,c.unit([[.1,0,1]])),'RAY_DOMAIN_FAILURE')
        stale=copy.deepcopy(scene);stale.target[0]=[0,1,0]
        bad3=expect_raises(lambda:e.trace(stale,0,o,sun),'MODEL_DOMAIN_FAILURE')
        edge=scene.mirrors.centers[0]+scene.mirrors.u[0]*scene.mirrors.widths[0]/2
        g,ev=e.trace(scene,0,edge[None,:],sun);ans=e.summarize(scene,0,e.stats(g,ev))
        assert ans['status']=='BOUNDARY_UNCERTAIN' and ans['power_kw'] is None
        return {'rejections':[bad1,bad2,bad3],'edge':ans},1
    add('E06_ray_domain_and_boundary','out-of-mirror/cone/stale axis rejected; exact source edge unresolved',domains)
    def aggregation():
        scene=artificial_scene([[0,0,4],[150,0,4]],[0,0,1],c.Cylinder())
        records=[observation(scene,i,n=128,seed=(2026090503,30+i))[0] for i in range(2)]
        a=e.aggregate([1,2],records,8)
        assert records[0]['status']=='TRUE_ZERO_SURVIVOR' and records[1]['power_kw']>0
        assert a['component_means']['eta_trunc'] is None and a['total_power_state']=='DEFINED'
        assert a['total_power_kw']==records[1]['power_kw'] and a['unit_power_kw_m2']==a['total_power_kw']/8
        partial=e.aggregate([1,2],records[:1],8);assert partial['total_power_kw'] is None
        mixed=copy.deepcopy(records);mixed[1]['scene_sha256']='different-time'
        rejection=expect_raises(lambda:e.aggregate([1,2],mixed,8),'mixed/unbound')
        pop=expect_raises(lambda:e.aggregate([1],records[:1],4),'population/identity')
        return {'complete_artificial_population':a,'partial':partial,'mixed_rejection':rejection,'subset_relabel_rejected':pop},256
    add('E07_N05_fixed_population_aggregation','undefined component coexists with legal zero contribution; mixed scene rejected',aggregation)
    def analytic():
        scene=artificial_scene([[0,0,0]],[0,0,1],c.Cylinder((10,0,0),5,10))
        ans,st,ev=observation(scene,0,n=256,seed=(2026090503,40))
        o,s=c.quadrature_rays(scene.mirrors,0,scene.s0,scene.beta,4,4,8);g,evq=e.trace(scene,0,o,s)
        aq=e.summarize(scene,0,e.stats(g,evq));cos=math.sqrt(.5)
        assert np.all(ev['S']&ev['B']&ev['R']) and np.all(evq['S']&evq['B']&evq['R'])
        assert abs(ans['eta_total']-e.RHO*cos)<1e-13 and abs(aq['eta_total']-e.RHO*cos)<1e-13
        assert abs(aq['raw_projection_residual'])<1e-13
        return {'R1':ans,'R2':aq,'independent_expected_eta':e.RHO*cos,'scope':'large finite receiver; entire reflected source envelope strictly within side reception'},256+len(o)
    add('E08_local_R1_R2_analytic','simple entire-acceptance geometry, analytical weighted total and R2 symmetry',analytic)
    return {'checks':rows,'all_pass':all(x['passed'] for x in rows),'ray_evaluations':ray_count,'scope':'artificial kernels/parameter mapping only; no target diagnostic layouts or annual result'}