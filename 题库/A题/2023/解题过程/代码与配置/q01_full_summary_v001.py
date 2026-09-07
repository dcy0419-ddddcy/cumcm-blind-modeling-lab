"""Rebuild Q1 complete summaries from immutable per-time sufficient statistics."""
import sys, math, json, hashlib
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import q01_full_run_v001 as run
c=run.c; OUT=run.OUT
LABELS=['optical','cosine','shadow_blocking','truncation','power_kw','unit_power_kw_m2']

def metrics(sums,cos,tau,dni,areas,invalid=None,raw_n=None):
    a=sums[...,0];b=sums[...,1];d=sums[...,2]
    with np.errstate(divide='ignore',invalid='ignore'):
        sb=b/a; tr=d/b; net=d/a
    if raw_n is not None:
        sb=(b/raw_n)/cos;net=(d/raw_n)/cos
    # N05: numerical estimates retained separately in shards; undefined records poison fixed population.
    invalid=np.zeros_like(a,dtype=bool) if invalid is None else invalid
    sb=np.where(invalid|(b<=0),np.nan,sb)
    tr=np.where(invalid|(b<=0)|(d<=0),np.nan,tr)
    opt=np.where(invalid|(b<=0)|(d<=0),np.nan,.92*cos*tau*net)
    powers=dni*np.sum(opt*areas,axis=1)
    temporal=np.column_stack([opt.mean(1),cos.mean(1),sb.mean(1),tr.mean(1),powers,powers/areas.sum()])
    monthly=temporal.reshape(12,5,6).mean(1)
    return np.vstack([monthly,temporal.mean(0)]),temporal

def energy_ratios(sums,cos,tau,dni,areas,invalid):
    a,b,d=np.moveaxis(sums,-1,0)
    scale=.92*dni[:,None]*areas[None,:]*cos
    with np.errstate(divide='ignore',invalid='ignore'):
        p0=scale;p1=scale*b/a;p2=scale*d/a
        if invalid.any(): p1=np.where(invalid,np.nan,p1);p2=np.where(invalid,np.nan,p2)
    def ratio(ids):
        x=p0[ids].sum();y=p1[ids].sum();z=p2[ids].sum()
        return [y/x,z/y if y>0 else np.nan,z/x]
    return np.array([ratio(slice(m*5,(m+1)*5)) for m in range(12)]+[ratio(slice(None))])

def jackknife(sum_by_batch,cos,tau,dni,areas,invalid):
    B=len(sum_by_batch); pooled=sum_by_batch.sum(0)
    point,_=metrics(pooled,cos,tau,dni,areas,invalid)
    leave=np.array([metrics(pooled-sum_by_batch[b],cos,tau,dni,areas,invalid)[0] for b in range(B)])
    pseudo=B*point-(B-1)*leave
    se=np.sqrt(np.sum((pseudo-pseudo.mean(0))**2,axis=0)/(B*(B-1)))
    return point,se,leave,pseudo

def read_ensemble(name):
    cfg=run.load(run.CFG);en=cfg['ensembles'][name];SS=[];CC=[];KK=[];UU=[];cos=[];tau=[];dni=[];shards=[]
    for ti in range(60):
        p=OUT/name/f't{ti:03d}.npz'
        if not p.exists(): raise RuntimeError(f'Missing {name} time {ti}; no partial extrapolation')
        with np.load(p,allow_pickle=False) as z:
            assert int(z['time_index'])==ti and int(z['completed'])==1745 and int(z['batches'])==8
            assert str(z['config_sha256'])==run.sha(run.CFG)
            assert list(z['levels'])==en['prefix_levels']
            SS.append(z['sums']);CC.append(z['cross']);KK.append(z['counts']);UU.append(z['unknown_weights']);cos.append(z['cosine']);tau.append(z['tau']);dni.append(float(z['dni']))
        shards.append({'path':str(p.relative_to(run.ROOT)).replace('\\','/'),'sha256':run.sha(p)})
    return {'sums':np.stack(SS,axis=2),'cross':np.stack(CC,axis=2),'counts':np.stack(KK,axis=2),'unknown_weights':np.stack(UU,axis=2),'cos':np.array(cos),'tau':np.array(tau),'dni':np.array(dni),'shards':shards,'n':en['n']}

def selftest():
    # Independent integer artificial arrays: product/mean and source-time DNI pairing.
    cos=np.full((60,2),.8);tau=np.full((60,2),.9);areas=np.array([2.,2.]);dni=np.tile([1.,2.,3.,4.,5.],12)
    sums=np.broadcast_to(np.array([8.,4.,2.]),(8,60,2,3)).copy()
    point,se,leave,pseudo=jackknife(sums,cos,tau,dni,areas,np.zeros((60,2),bool))
    expected=.92*.8*.9*.25
    exact=bool(np.allclose(point[:,0],expected,atol=1e-14) and np.allclose(point[:,2],.5) and np.allclose(point[:,3],.5) and np.allclose(point[:,4],3*4*expected))
    varied=sums.copy()
    for b in range(8): varied[b,...,2]=1.+b*.1
    pt,se,_,_=jackknife(varied,cos,tau,dni,areas,None)
    batchopt=.92*.8*.9*(1+np.arange(8)*.1)/8
    jexact=bool(np.allclose(se[:,0],np.std(batchopt,ddof=1)/math.sqrt(8),atol=1e-14))
    bad=np.zeros((60,2),bool);bad[0,0]=True
    na=metrics(sums.sum(0),cos,tau,dni,areas,bad)[0]
    napass=bool(np.isnan(na[0,0]) and np.isnan(na[-1,0]) and np.isfinite(na[1,0]))
    # Verify t quantile with independent Simpson integration of Student density, df=7.
    q=2.3646242515927844;nu=7;xx=np.linspace(0,q,4001)
    density=math.gamma(4)/(math.sqrt(nu*math.pi)*math.gamma(3.5))*(1+xx*xx/nu)**(-4)
    integral=(q/4000)/3*(density[0]+density[-1]+4*density[1:-1:2].sum()+2*density[2:-1:2].sum())
    quantile=bool(abs(.5+integral-.975)<1e-10)
    # pooled ratio differs from mean of batch ratios, and leave-one uses same pooled target
    small=np.array([[1.,.8,.4],[3.,.6,.3]])
    pooling=not np.isclose((small[:,2]/small[:,0]).mean(),small[:,2].sum()/small[:,0].sum())
    checks={'H02_independent_expected':exact,'jackknife_linear_independent_sd':jexact,'fixed_population_NA':napass,'student_quantile_integral':quantile,'pooled_not_batch_ratio_mean':bool(pooling)}
    return {'checks':checks,'all_pass':all(checks.values()),'t_cdf':float(.5+integral),'scope':'synthetic artificial arrays only'}

def rebuild(budget,output_name):
    cfg=run.load(run.CFG);run.check_bindings(cfg)
    initial=read_ensemble('initial');confirm=read_ensemble('confirmation'); budget.tick();budget.guard(10)
    cos,tau,dni=confirm['cos'],confirm['tau'],confirm['dni'];areas=np.full(1745,36.)
    final=confirm['sums'][-1]; counts=confirm['counts'][-1]; invalid=confirm['unknown_weights'][-1].sum(0)>0
    pooled=final.sum(0);N=8*confirm['n'];
    point,se,leave,pseudo=jackknife(final,cos,tau,dni,areas,invalid)
    half=cfg['t7']*se
    coarse=metrics(confirm['sums'][0].sum(0),cos,tau,dni,areas,confirm['unknown_weights'][0].sum(0)>0)[0]
    independent=metrics(initial['sums'][-1].sum(0),cos,tau,dni,areas,initial['unknown_weights'][-1].sum(0)>0)[0]
    raw=metrics(pooled,cos,tau,dni,areas,invalid,raw_n=N)[0]
    changes=np.abs(np.stack([point-coarse,point-independent,point-raw]))
    indicator=np.maximum(half,np.max(changes,axis=0))
    efficiencies=indicator[:,:4]<=cfg['efficiency_abs_target']
    near=(np.abs(point[:,4:])<=10*half[:,4:])|(np.abs(point[:,4:])<=1e-12)
    powers=(indicator[:,4:]<=cfg['power_rel_target']*np.abs(point[:,4:]))&(~near)
    met=np.concatenate([efficiencies,powers],axis=1)&np.isfinite(point)&np.isfinite(indicator)
    state=np.zeros((60,1745),np.int8)
    state[pooled[...,1]<=0]=1;state[(pooled[...,1]>0)&(pooled[...,2]<=0)]=2;state[invalid]=3
    # Independently reconstruct from per-object products and direct energy.
    with np.errstate(divide='ignore',invalid='ignore'):
        sb=pooled[...,1]/pooled[...,0];tr=pooled[...,2]/pooled[...,1]
        direct=.92*cos*tau*pooled[...,2]/pooled[...,0]
        factors=np.stack([sb,cos,tau,tr,np.full_like(cos,.92)],axis=-1)
    aggregate=c.h02_summary(factors.reshape(12,5,1745,5),dni.reshape(12,5),areas,direct_total=direct.reshape(12,5,1745))
    identity_error=float(np.nanmax(np.abs(np.prod(factors,axis=-1)-direct)))
    m_power=dni*np.sum(areas*direct,axis=1)
    power_error=float(max(np.max(np.abs(point[:12,4]-m_power.reshape(12,5).mean(1))),abs(point[12,4]-m_power.mean())))
    aggregate_error=float(max(np.max(np.abs(point[:12,0]-aggregate['total_month'])),abs(point[12,0]-aggregate['total_year'])))
    component_error=float(np.max(np.abs(point[:12,1:4]-aggregate['component_month'][:,[1,0,3]])))
    area_error=float(np.max(np.abs(point[:,5]*areas.sum()-point[:,4])))
    valid=state==0
    range_ok=bool(np.all((direct[valid]>=0)&(direct[valid]<=1)) and np.all((sb[valid]>=0)&(sb[valid]<=1)) and np.all((tr[valid]>=0)&(tr[valid]<=1)))
    monotone=bool(np.all(pooled[...,2]<=pooled[...,1]+1e-12) and np.all(pooled[...,1]<=pooled[...,0]+1e-12))
    raw_residual=float(np.max(np.abs(pooled[...,0]/N-cos)))
    batch_states={'sampled_zero_survivor':int((counts[...,1]==0).sum()),'sampled_zero_capture_with_survivor':int(((counts[...,1]>0)&(counts[...,2]==0)).sum()),'boundary_uncertain':int((counts[...,3]>0).sum())}
    # Independent whole-batch estimates saved; their mean is not substituted for pooled point.
    batch_metrics=np.array([metrics(final[b],cos,tau,dni,areas,confirm['unknown_weights'][-1,b]>0)[0] for b in range(8)])
    ratios=energy_ratios(pooled,cos,tau,dni,areas,invalid)
    result={'created':run.now(),'config_sha256':run.sha(run.CFG),'labels':LABELS,'rows':[f'{m:02d}-21' for m in range(1,13)]+['annual'],'point':point,'jackknife_se':se,'approx_pointwise_95_halfwidth':half,'leave_one_batch_estimates':leave,'pseudo_values':pseudo,'individual_batch_metrics':batch_metrics,'confirmation_prefix128':coarse,'independent_initial128':independent,'raw_integral_alternative':raw,'absolute_changes':{'prefix_refinement':changes[0],'independent_initial':changes[1],'raw_alternative':changes[2]},'work_uncertainty_indicator':indicator,'targets_met':met,'near_zero_power':near,'energy_total_ratios':{'labels':['Pi1/Pi0','Pi2/Pi1','Pi2/Pi0'],'values':ratios,'note':'pooled energy totals across each month/all60; not H02 mean conditional efficiencies'},'coverage':{'expected_combinations':104700,'completed_combinations':60*1745,'initial_independent_batches':8,'confirmation_independent_batches':8,'final_point_batches':8,'initial_n':128,'confirmation_n':256,'final_samples_per_combination':N,'initial_unique_rays':104700*8*128,'confirmation_unique_rays':104700*8*256},'states':{'codes':{'0':'ESTIMATED','1':'SAMPLED_ZERO_SURVIVOR','2':'SAMPLED_ZERO_CAPTURE','3':'BOUNDARY_UNCERTAIN'},'pooled_counts':{str(k):int((state==k).sum()) for k in range(4)},'individual_confirmation_batch_counts':batch_states},'numeric_checks':{'factor_product_abs_error':identity_error,'power_reconstruction_abs_kw':power_error,'H02_total_error':aggregate_error,'H02_component_error':component_error,'area_relation_abs_kw':area_error,'bounded_factors':range_ok,'ordered_raw_sums':monotone,'max_raw_projection_residual':raw_residual},'numeric_validation_pass':bool(valid.all() and range_ok and monotone and identity_error<1e-12 and power_error<1e-8 and aggregate_error<1e-12 and component_error<1e-12 and area_error<1e-8),'work_targets_all_met':bool(met.all() and valid.all()),'interval_limit':'approximate pointwise Student t jackknife; no simultaneous 95 percent guarantee; no physical uncertainty included; finite sample ratio bias not rigorously bounded','budget_charged_at_rebuild':budget.used(),'shards':initial['shards']+confirm['shards']}
    run.save(OUT/output_name,result)
    if output_name=='汇总与数值核验-v001.json':
        with (OUT/'逐镜逐时合并结果.npz').open('xb') as f:np.savez_compressed(f,pooled_sums=pooled,cosine=cos,tau=tau,dni=dni,sb=sb,trunc=tr,optical=direct,power_kw=direct*dni[:,None]*36,state=state,config_sha256=run.sha(run.CFG))
    print(json.dumps({'covered':104700,'pooled_states':result['states']['pooled_counts'],'numeric_pass':result['numeric_validation_pass'],'targets_all_met':result['work_targets_all_met'],'target_pass_count':int(met.sum()),'target_count':int(met.size),'annual':run.clean(point[-1]),'max_eff_indicator':run.clean(indicator[:,:4].max()),'max_relative_power_indicator':run.clean(np.max(indicator[:,4:]/np.abs(point[:,4:])))},ensure_ascii=False),flush=True)

if __name__=='__main__':
    mode=sys.argv[1];budget=run.Budget('summary-'+mode)
    try:
        if mode=='selftest':
            r=selftest();run.save(OUT/'汇总接口人工检查.json',r);print(json.dumps(r));assert r['all_pass']
        elif mode=='rebuild': rebuild(budget,'汇总与数值核验-v001.json')
        elif mode=='verify-rebuild':
            rebuild(budget,'汇总独立重建-v001.json')
            a=run.load(OUT/'汇总与数值核验-v001.json');b=run.load(OUT/'汇总独立重建-v001.json')
            eq={k:a[k]==b[k] for k in ['point','work_uncertainty_indicator','targets_met','states','numeric_checks','energy_total_ratios']}
            run.save(OUT/'汇总重建一致性.json',{'checks':eq,'passed':all(eq.values()),'note':'fresh process reloaded immutable shards; no optical rerun'})
            assert all(eq.values())
        else: raise ValueError(mode)
    except BaseException:
        budget.finish('failed');raise
    else: budget.finish()