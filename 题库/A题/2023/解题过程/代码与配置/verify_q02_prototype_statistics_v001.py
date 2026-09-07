"""Saved-statistics verification only. No rays, layouts, or optimization generated."""
from pathlib import Path
import sys, json, hashlib, math, struct, traceback, time
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import q02_prototype_run_v003 as run
ROOT=HERE.parents[1]; OUT=run.OUT; CFG=run.CFG
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    cfg=read(CFG);run.binding_check(cfg)
    budget=run.Budget('saved_statistics_verification',1)
    checks=[]; errors=[]; details=[];seed_set=set(); nfiles=0;paths=0;ns=0;screen=0;rt=0
    def ck(name,ok,detail=None):
        row={'name':name,'pass':bool(ok)}
        if detail is not None:row['detail']=detail
        checks.append(row)
        if not ok:errors.append(row)
    maxerr=0.;allmetric={k:{'se':0.,'change':0.} for k in ['eta_sb','eta_trunc','eta_total','power_kw']}
    try:
        base=read(OUT/'只读输入基线-v001.json')
        ck('read_only_baseline',all(sha(ROOT/x['path'])==x['sha256'] for x in base['files']))
        pre=read(OUT/'新诊断布局预登记汇总.json')
        ck('scope',len(pre['designs'])<=3 and pre['combination_count']==54)
        for dr in pre['designs']:
            folder=OUT/dr['design']; payload=read(folder/'非正式诊断清单.json')
            ids=[x['mirror_id'] for x in payload['mirrors']]
            geo=read(folder/'几何检查.json'); rd=read(folder/'清单往返.json')
            dom=read(folder/'60时点轻量域检查.json'); psel=read(folder/'光学组合预登记.json')
            ck(dr['design']+'_geometry_roundtrip',geo['accepted'] and rd['payload_bitwise_equal'] and rd['json_geometry']['accepted'] and rd['csv_geometry']['accepted'])
            ck(dr['design']+'_60_domain',len(dom['items'])==60 and dom['complete'] and all(x['status']=='VALID' for x in dom['items']))
            selected={(r['month'],r['hour'],r['mirror_id']):r for r in dr['combinations']}
            seen=set(); dd={'design':dr['design'],'n':dr['n'],'area_m2':dr['total_area_m2'],'nominal_n':payload['metadata'].get('nominal_n'),
                'file_count':0,'low_survival':[],'numerical_warnings':[],'pooled_states':{},'batch_zero_survive':0,'batch_zero_capture':0,
                'prefix_zero_survive':0,'prefix_zero_capture':0,'unknown_samples':0,'survive_min':10**9,'capture_min':10**9,
                'min_batch_survive':10**9,'min_batch_capture':10**9,'metric_ranges':{},'optical_seconds':0.,
                'csv_bytes':(folder/'非正式诊断清单.csv').stat().st_size}
            for fp in sorted(folder.glob('optical_*.json')):
                budget.guard()
                x=read(fp);cov=x['coverage'];key=(cov['month'],cov['hour'],cov['mirror_id']);seen.add(key)
                s=selected[key];dd['file_count']+=1;nfiles+=1;paths+=x['path_evaluations'];ns+=x['unique_integral_samples']
                ck(fp.name+'_bindings',x['config_sha256']==sha(CFG) and x['design_sha256']==sha(folder/'非正式诊断清单.json') and x['all_obstacles']==dr['n'] and ids[s['index']]==s['mirror_id'])
                ck(fp.name+'_batches',len(x['batches'])==cfg['batches'] and [b['batch'] for b in x['batches']]==list(range(4)))
                totals={}
                for lev in cfg['levels']:
                    bs=[b['levels'][str(lev)] for b in x['batches']]
                    for b,st in zip(x['batches'],bs):
                        digest=hashlib.sha256((dr['design']+'/'+s['position_key']).encode()).digest()
                        expected=[cfg['root_seed'],801,cov['month']*100+int(cov['hour']*2),*struct.unpack('<4I',digest[:16]),b['batch']]
                        ck(fp.name+f'_seed_{lev}_{b["batch"]}',expected==b['seed_words'] and st['n']==lev and st['scene_sha256']==x['scene_sha256'] and st['mirror_index']==s['index'])
                        if lev==max(cfg['levels']):
                            tup=tuple(expected);ck(fp.name+'_unique_seed',tup not in seed_set);seed_set.add(tup)
                        ct=st['counts'];a,v,c=st['sums'];mat=np.array(st['cross'])
                        ck(fp.name+'_energy_containment',0<=c<=v+1e-12 and v<=a+1e-12 and ct['capture']<=ct['survive']<=lev and ct['shadow']+ct['blocked_after_unshadowed']+ct['survive']==lev and np.isfinite(mat).all() and np.allclose(mat,mat.T,rtol=0,atol=1e-12))
                        if lev==256:
                            dd['batch_zero_survive']+=int(ct['survive']==0);dd['batch_zero_capture']+=int(ct['capture']==0)
                            dd['unknown_samples']+=ct['unknown']
                            dd['min_batch_survive']=min(dd['min_batch_survive'],ct['survive']);dd['min_batch_capture']=min(dd['min_batch_capture'],ct['capture'])
                        else:
                            dd['prefix_zero_survive']+=int(ct['survive']==0);dd['prefix_zero_capture']+=int(ct['capture']==0)
                    sums=np.array([b['sums'] for b in bs]).sum(axis=0);totals[lev]=sums
                    p=x['level_summaries'][str(lev)];a,v,c=sums;f1=v/a;f2=c/a;tr=c/v
                    eta=p['eta_cos']*p['eta_at']*cfg['rho']*f2
                    power=dr['total_area_m2']/dr['n']*p['dni_kw_m2']*eta
                    vals={'eta_sb':f1,'eta_trunc':tr,'eta_total':eta,'power_kw':power,'unit_power_kw_m2':power/p['area_m2'],
                        'analytic_pi0_kw':cfg['rho']*p['dni_kw_m2']*p['area_m2']*p['eta_cos']}
                    countsum={k:sum(b['counts'][k] for b in bs) for k in bs[0]['counts']}
                    ck(fp.name+'_population_and_counts',p['scene_mirror_ids']==ids and p['n']==4*lev and p['counts']==countsum and p['area_m2']==dr['total_area_m2']/dr['n'])
                    err=max(abs(float(p[k])-v) for k,v in vals.items());maxerr=max(maxerr,err)
                    ck(fp.name+'_rebuilt_estimator',err<=cfg['comparison_abs'] and np.max(np.abs(sums/(4*lev)-p['raw_mean']))<=cfg['comparison_abs'])
                    if lev==256:
                        dd['pooled_states'][p['status']]=dd['pooled_states'].get(p['status'],0)+1
                        dd['survive_min']=min(dd['survive_min'],p['counts']['survive']);dd['capture_min']=min(dd['capture_min'],p['counts']['capture'])
                        if p['counts']['survive']<cfg['low_survival_screen']:dd['low_survival'].append(cov)
                        for k in allmetric:
                            rr=dd['metric_ranges'].setdefault(k,[float('inf'),-float('inf')]);rr[0]=min(rr[0],p[k]);rr[1]=max(rr[1],p[k])
                final=x['level_summaries']['256'];cos=final['eta_cos'];tau=final['eta_at'];dn=final['dni_kw_m2'];ar=final['area_m2']
                leaves={k:[] for k in allmetric}
                for omitted in range(4):
                    a,v,c=sum((np.array(b['levels']['256']['sums']) for j,b in enumerate(x['batches']) if j!=omitted),np.zeros(3))
                    vals={'eta_sb':v/a,'eta_trunc':c/v,'eta_total':cfg['rho']*cos*tau*c/a}
                    vals['power_kw']=ar*dn*vals['eta_total']
                    for k in leaves:leaves[k].append(vals[k])
                for k,vs in leaves.items():
                    se=float(math.sqrt(.75*sum((v-np.mean(vs))**2 for v in vs)));change=abs(final[k]-x['level_summaries']['64'][k])
                    ck(fp.name+'_jackknife_'+k,abs(se-x['variability'][k]['delete_batch_se_approx'])<=cfg['comparison_abs'] and abs(change-x['variability'][k]['prefix_change_abs'])<=cfg['comparison_abs'])
                    allmetric[k]['se']=max(allmetric[k]['se'],se);allmetric[k]['change']=max(allmetric[k]['change'],change)
                    if k!='power_kw' and (se>cfg['diagnostic_thresholds']['jackknife_efficiency_se_warning'] or change>cfg['diagnostic_thresholds']['level_efficiency_change_warning']):
                        dd['numerical_warnings'].append({'coverage':cov,'metric':k,'se':se,'prefix_change':change})
                comp=x['screen_vs_exhaustive']
                if comp:
                    screen+=1;ck(fp.name+'_exhaustive',comp['n']==64 and all(comp['events_equal'].values()) and comp['weight_max_abs']==0.)
                re=x['roundtrip_optics']
                if re:
                    rt+=1;ck(fp.name+'_optical_roundtrip',re['samples']==64 and all(re[k] for k in ['points_identical','directions_identical','events_identical']) and re['raw_stats_max_abs']==0.)
                dd['optical_seconds']+=x['elapsed_seconds']
                ck(fp.name+'_no_rating',x['states']['rated_power']=='NOT_ASSESSED_DIAGNOSTIC_ONLY')
            ck(dr['design']+'_coverage',set(selected)==seen and dd['file_count']==18 and len(seen)==18)
            dd['preregistered_geometry_seconds']=psel['geometry_generation_and_60_domain_seconds']
            dd['geometric_minima']=geo['minima'];dd['cost_seconds_per_evaluated_combination']=dd['optical_seconds']/18
            # Scenario illustration only, not a measured full-field performance claim.
            dd['naive_same_cost_60_time_seconds']=dd['cost_seconds_per_evaluated_combination']*dr['n']*60
            details.append(dd)
        ck('total_scope_and_replays',nfiles==54 and ns==55296 and paths==56640 and screen==18 and rt==3 and len(seed_set)==216)
        result={'all_pass':not errors,'check_count':len(checks),'failed_checks':errors,'checks':checks,'designs':details,'unique_combinations':nfiles,
                'unique_integral_samples':ns,'independent_batch_streams':len(seed_set),'independent_batches_per_combination':4,'path_evaluations_including_replays':paths,
                'screen_comparisons':screen,'optical_roundtrip_comparisons':rt,'max_estimator_rebuild_absolute_difference':maxerr,
                'maximum_numerical_diagnostics':allmetric,'no_optical_rays_generated':True,'evidence_scope':'saved-statistic arithmetic/bindings/coverage; not independent physical validation',
                'config_sha256':sha(CFG),'code_sha256':sha(Path(__file__))}
        run.save(OUT/'落盘统计独立核验-v001.json',result);budget.finish('COMPLETED' if not errors else 'FAILED_OR_STOPPED')
        print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False))
        if errors:sys.exit(1)
    except Exception:
        run.save(OUT/'落盘统计核验失败-v001.json',{'error':traceback.format_exc()});budget.finish('FAILED_OR_STOPPED');raise
if __name__=='__main__':main()