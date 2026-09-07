"""Budgeted Q2 prototype actions; no optimizer or full-field optical evaluation entry."""
from pathlib import Path
import sys,json,time,hashlib,traceback,math,copy,datetime,argparse
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=ROOT/'工作记录/诊断结果/Q02-原型-v001';CFG=HERE/'Q02-原型配置-v002.json'
sys.path.insert(0,str(HERE))
import q02_eval_v003 as e
import q02_design_v002 as d
IO_RETRIES=[]

def load(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.part')
    tmp.write_text(json.dumps(e.clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    for retry in range(8):
        try:
            tmp.replace(p);break
        except PermissionError as ex:
            IO_RETRIES.append({'path':str(p.relative_to(ROOT)),'retry':retry+1,'error':str(ex),'time':timestamp()})
            if retry==7:raise
            time.sleep(min(.05*(2**retry),.8))

def timestamp(): return datetime.datetime.now().astimezone().isoformat()
class Budget:
    def __init__(self,label,attempt):
        self.path=OUT/'累计计算预算.json';self.data=load(self.path) if self.path.exists() else {'limit_seconds':1800.,'spent_seconds':0.,'runs':[]}
        if any(x.get('status')=='RUNNING' for x in self.data['runs']):raise RuntimeError('UNRESOLVED_BUDGET_CHECKPOINT: inspect interrupted/concurrent action before resuming')
        self.label=label;self.attempt=attempt;self.start=time.perf_counter();self.record={'action':label,'attempt':attempt,'started':timestamp(),'status':'RUNNING'}
        if self.data['spent_seconds']>=1800:raise RuntimeError('BUDGET_EXHAUSTED')
        self.data['runs'].append(self.record);self.persist()
    def remaining(self): return 1800-self.data['spent_seconds']-(time.perf_counter()-self.start)
    def guard(self,reserve=5):
        if self.remaining()<reserve: raise RuntimeError('BUDGET_EXHAUSTED: checkpoint retained')
    def persist(self):
        self.record['elapsed_seconds']=time.perf_counter()-self.start
        save(self.path,self.data)
    def finish(self,status):
        self.record.update(status=status,elapsed_seconds=time.perf_counter()-self.start,finished=timestamp())
        self.data['spent_seconds']+=self.record['elapsed_seconds'];save(self.path,self.data)

def binding_check(cfg):
    revision=load(OUT/'执行修订-v003.json')
    if sha(Path(__file__))!=revision['runner_sha256'] or sha(CFG)!=revision['config_sha256']:raise RuntimeError('EXECUTION_REVISION_BINDING_CHANGED')
    for b in cfg['bindings']:
        if sha(ROOT/b['path'])!=b['sha256']:raise RuntimeError('FROZEN_BINDING_CHANGED: '+b['path'])

def tests(cfg,budget,attempt):
    import q02_design_tests_v002 as dt
    import q02_eval_tests_v002 as et
    folder=OUT/f'artificial_roundtrip_attempt{attempt}';folder.mkdir(exist_ok=False)
    a=dt.run_tests(folder);budget.guard();b=et.run_tests();budget.guard()
    result={'config_sha256':sha(CFG),'geometry':a,'evaluation':b,'environment':{'python':sys.version,'numpy':np.__version__},'scope':'artificial/parameter tests, no new target optical design'}
    result['all_pass']=a['all_passed'] and b['all_pass']
    save(OUT/f'人工测试-attempt{attempt}.json',result)
    if not result['all_pass']:raise RuntimeError('BASIC_TESTS_FAILED: evidence retained')
    return {'all_pass':True,'geometry_cases':len(a['results']),'evaluation_cases':len(b['checks']),'artificial_ray_evaluations':b['ray_evaluations']}

def base_design():
    centers,rows=e.c.read_field(ROOT/'附件/附件03.xlsx')
    mirrors=[{'mirror_id':r['mirror_id'],'position_key':'q1-excel-row-'+str(r['excel_row']),'x':r['x'],'y':r['y']} for r in rows]
    return d.Design('Q1-compatible-regression','v001',(0.,0.),6.,6.,4.,mirrors,{'scope':'read-only Q1 scene compatibility','source':'附件/附件03.xlsx'}),centers,rows

def prerequisites():
    successful=[]
    for p in OUT.glob('人工测试-attempt*.json'):
        if load(p).get('all_pass') and load(p).get('config_sha256')==sha(CFG): successful.append(p.name)
    if not successful:raise RuntimeError('Prerequisite: passing artificial tests')
    return successful

def old_regression(cfg,budget,attempt):
    prerequisites();design,centers,rows=base_design();results=[]
    for month,hour,mid in cfg['old_combinations']:
        budget.guard();t0=time.perf_counter();i=mid-1;sc=e.prepare(design,month,hour);sun=e.c.solar(month,hour)
        old,target=e.c.aim_field(centers,sun['s0'],e.c.Cylinder())
        words=[cfg['root_seed'],701,month,int(hour*100),mid]
        o,s=e.c.random_rays(old,i,sun['s0'],cfg['beta'],cfg['regression_samples'],words)
        oldans,ev0=e.c.evaluate(old,i,sun['s0'],target,e.c.Cylinder(),cfg['beta'],sc.tol,o,s,dni=sun['dni'],tau=sc.tau[i])
        g,ev1=e.trace(sc,i,o,s);st=e.stats(g,ev1);new=e.summarize(sc,i,st)
        events={k:bool(np.array_equal(ev0[k],ev1[k])) for k in ['S','B','R','unknown','incoming_object','blocking_object','receiver_kind']}
        stats_err=max(float(np.max(np.abs(np.asarray(oldans['raw_sums'])-st['sums']))),float(np.max(np.abs(np.asarray(oldans['raw_cross_sums'])-st['cross']))))
        diffs={}
        for k in ['eta_sb','eta_trunc','eta_total','power_kw']:
            x,y=oldans[k],new[k];diffs[k]=0. if x is None and y is None else None if x is None or y is None else abs(x-y)
        ok=all(events.values()) and stats_err<=cfg['comparison_abs'] and all(v is not None and v<=cfg['comparison_abs'] for v in diffs.values())
        row={'month':month,'hour':hour,'mirror_id':mid,'source_excel_row':rows[i]['excel_row'],'samples':cfg['regression_samples'],'seed_words':words,'events_equal':events,'raw_stat_max_abs':stats_err,'differences':diffs,'new':new,'all_pass':ok,'elapsed_seconds':time.perf_counter()-t0}
        results.append(row);save(OUT/f'旧场回归-attempt{attempt}.json',{'config_sha256':sha(CFG),'combinations':results,'all_pass':all(x['all_pass'] for x in results),'optical_path_evaluations':len(results)*2*cfg['regression_samples'],'unique_source_samples':len(results)*cfg['regression_samples']})
        if not ok:raise RuntimeError('OLD_SCENE_REGRESSION_FAILED')
        budget.persist()
    return {'old_combinations':len(results),'all_pass':True,'unique_source_samples':len(results)*cfg['regression_samples']}

def prep(cfg,budget,attempt):
    prerequisites()
    oldok=any(load(p).get('all_pass') and load(p).get('config_sha256')==sha(CFG) for p in OUT.glob('旧场回归-attempt*.json'))
    if not oldok:raise RuntimeError('Prerequisite: old scene compatibility')
    prepared=[]
    for spec in cfg['design_specs']:
        budget.guard();t0=time.perf_counter();name=spec['name'];folder=OUT/name;folder.mkdir(exist_ok=False)
        design,generation=d.generate_ring_design(**spec)
        save(folder/'生成记录.json',generation);geometry=d.validate_design(design);save(folder/'几何检查.json',geometry)
        if not geometry['accepted']:raise RuntimeError('NEW_DESIGN_GEOMETRY_FAILURE: '+name)
        d.save_json(design,folder/'非正式诊断清单.json');d.save_csv(design,folder/'非正式诊断清单.csv')
        jr=d.read_json(folder/'非正式诊断清单.json');cr=d.read_csv(folder/'非正式诊断清单.csv')
        equal=d.design_to_dict(design)==d.design_to_dict(jr)==d.design_to_dict(cr)
        if not equal:raise RuntimeError('ROUNDTRIP_IDENTITY_FAILED')
        roundtrip={'payload_bitwise_equal':equal,'json_geometry':d.validate_design(jr),'csv_geometry':d.validate_design(cr),
                   'csv_precision':'17 significant digits, roundtrip binary float preservation','ground_margin_m':geometry['minima']['ground_margin'],
                   'export_rows_preview':[x['export_row'] for x in cr.mirrors[:3]],'source_excel_rows_assigned':False}
        save(folder/'清单往返.json',roundtrip)
        domains=[];chosen_scenes={}
        for month in range(1,13):
            for hour in cfg['hours']:
                budget.guard();sc=e.prepare(design,month,hour);domains.append({'month':month,'hour':hour,'domain':sc.domain,'status':'VALID'})
                if [month,hour] in cfg['new_times']:chosen_scenes[(month,hour)]=sc
            budget.persist();save(folder/'60时点轻量域检查.json',{'items':domains,'complete':len(domains)==60})
        cache_by_time={};counts=[]
        for month,hour in cfg['new_times']:
            sc=chosen_scenes[(month,hour)];cc=[e.candidates(sc,i) for i in range(sc.n)];cache_by_time[(month,hour)]=cc
            counts.append(np.array([[len(x.incoming),len(x.outgoing)] for x in cc]));budget.guard()
        arr=np.array(counts);xy=np.array([[x['x'],x['y']] for x in design.mirrors]);rr=np.linalg.norm(xy,axis=1);tt=np.linalg.norm(xy-design.tower_xy,axis=1)
        nearest=np.full(design.n,np.inf)
        for i in range(design.n):
            v=np.linalg.norm(xy-xy[i],axis=1);v[i]=np.inf;nearest[i]=v.min()
        seam=np.abs(xy[:,1]-design.tower_xy[1]);seam=np.where(xy[:,0]>=design.tower_xy[0],seam,np.inf)
        criteria=[('largest_candidate_sum',-(arr[:,:,0]+arr[:,:,1]).max(0)),('largest_outgoing',-arr[:,:,1].max(0)),('outer_boundary',350-rr),('near_exclusion',tt-100),('nearest_neighbor',nearest),('sector_seam',seam)]
        picked=[];reasons=[]
        for label,score in criteria:
            order=sorted(range(design.n),key=lambda i:(float(score[i]),design.mirrors[i]['mirror_id']))
            i=next(j for j in order if j not in picked);picked.append(i);reasons.append({'index':i,'mirror_id':design.mirrors[i]['mirror_id'],'position_key':design.mirrors[i]['position_key'],'reason':label,'score':float(score[i])})
        selections=[]
        for ti,(month,hour) in enumerate(cfg['new_times']):
            difficult=sorted(picked,key=lambda i:(-int(arr[ti,i].sum()),design.mirrors[i]['mirror_id']))[:2]
            for i in picked:
                selections.append({'month':month,'hour':hour,'index':i,'mirror_id':design.mirrors[i]['mirror_id'],'position_key':design.mirrors[i]['position_key'],
                                   'candidate_in':int(arr[ti,i,0]),'candidate_out':int(arr[ti,i,1]),'screen_vs_exhaustive':i in difficult})
        rec={'created_before_new_optical_outputs':timestamp(),'design':name,'n':design.n,'total_area_m2':design.total_area,'reason_rules':reasons,'combinations':selections,
             'candidate_statistics':{'incoming_min':int(arr[:,:,0].min()),'incoming_max':int(arr[:,:,0].max()),'outgoing_min':int(arr[:,:,1].min()),'outgoing_max':int(arr[:,:,1].max())},
             'design_json_sha256':sha(folder/'非正式诊断清单.json'),'config_sha256':sha(CFG),'geometry_generation_and_60_domain_seconds':time.perf_counter()-t0}
        save(folder/'光学组合预登记.json',rec);np.savez_compressed(folder/'候选数统计.npz',counts=arr,mirror_ids=np.array([x['mirror_id'] for x in design.mirrors]))
        prepared.append(rec);save(OUT/'新诊断布局预登记汇总.json',{'designs':prepared,'combination_count':sum(len(x['combinations']) for x in prepared),'optical_started':False});budget.persist()
    assert len(prepared)<=3 and sum(len(x['combinations']) for x in prepared)<=54
    return {'new_designs':len(prepared),'pre_registered_combinations':sum(len(x['combinations']) for x in prepared),'geometry_only':True}

def slice_event(ev,n):return {k:v[:n] if isinstance(v,np.ndarray) else v for k,v in ev.items()}
def diagnostics(cfg,budget,attempt):
    prerequisites();pre=load(OUT/'新诊断布局预登记汇总.json')
    if len(pre['designs'])>3 or pre['combination_count']>54:raise RuntimeError('SCOPE_LIMIT')
    finished=[];unique=0;path_count=0;start_total=time.perf_counter()
    for selected in pre['designs']:
        name=selected['design'];folder=OUT/name
        if sha(folder/'非正式诊断清单.json')!=selected['design_json_sha256']:raise RuntimeError('DESIGN_CHANGED_AFTER_PREREGISTRATION')
        design=d.read_json(folder/'非正式诊断清单.json');rebuilt=d.read_csv(folder/'非正式诊断清单.csv');scene_cache={}
        for no,sel in enumerate(selected['combinations']):
            budget.guard(10);i=sel['index'];month=sel['month'];hour=sel['hour'];key=(month,hour);targetfile=folder/f'optical_m{month:02d}_h{hour:g}_id{sel["mirror_id"]}.json'
            if targetfile.exists():
                row=load(targetfile)
                if row['config_sha256']!=sha(CFG) or row['design_sha256']!=selected['design_json_sha256']:raise RuntimeError('CHECKPOINT_BINDING_MISMATCH')
                finished.append(row['coverage']);unique+=row['unique_integral_samples'];path_count+=row['path_evaluations'];continue
            t0=time.perf_counter()
            if key not in scene_cache:scene_cache[key]=e.prepare(design,month,hour)
            sc=scene_cache[key];cache=e.candidates(sc,i);batches={n:[] for n in cfg['levels']};saved=[];comparison=None;roundtrip=None;examples=[];paths=0
            for batch in range(cfg['batches']):
                words=e.seed_words(cfg['root_seed'],801,month*100+int(hour*2),name+'/'+sel['position_key'],batch)
                o,s=e.rays(sc,i,max(cfg['levels']),words);g,ev=e.trace(sc,i,o,s,cache);paths+=len(o)
                for n in cfg['levels']:batches[n].append(e.stats(g[:n],slice_event(ev,n)))
                saved.append({'batch':batch,'seed_words':words,'levels':{str(n):batches[n][-1] for n in cfg['levels']}})
                for j in np.flatnonzero(ev['unknown'])[:4]:examples.append({'batch':batch,'sample':int(j),'point':o[j],'sun_direction':s[j],'receiver_kind':str(ev['receiver_kind'][j])})
                if batch==0 and sel['screen_vs_exhaustive']:
                    n=cfg['exhaustive_samples'];gg,ex=e.trace(sc,i,o[:n],s[:n],screen=False);paths+=n
                    tests={k:bool(np.array_equal(ev[k][:n],ex[k])) for k in ['S','B','R','unknown','incoming_object','blocking_object','receiver_kind']}
                    comparison={'n':n,'same_rays':True,'events_equal':tests,'weight_max_abs':float(np.max(np.abs(g[:n]-gg))),'all_pass':all(tests.values())}
                    if not comparison['all_pass']:
                        save(folder/f'筛选失败_{no}.json',{'selection':sel,'comparison':comparison,'points':o[:n],'directions':s[:n],'screen':slice_event(ev,n),'exhaustive':ex})
                        raise RuntimeError('SCREENING_MISMATCH: stop new optics')
                if batch==0 and no==0:
                    rc=e.prepare(rebuilt,month,hour);ro,rs=e.rays(rc,i,cfg['roundtrip_samples'],words);rg,rev=e.trace(rc,i,ro,rs);paths+=len(ro)
                    equal=all(np.array_equal(ev[k][:len(ro)],rev[k]) for k in ['S','B','R','unknown'])
                    roundtrip={'samples':len(ro),'points_identical':bool(np.array_equal(ro,o[:len(ro)])),'directions_identical':bool(np.array_equal(rs,s[:len(ro)])),'events_identical':equal,'raw_stats_max_abs':float(np.max(np.abs(np.asarray(e.stats(rg,rev)['sums'])-e.stats(g[:len(ro)],slice_event(ev,len(ro)))['sums'])))}
                    if not all(roundtrip[k] for k in ['points_identical','directions_identical','events_identical']) or roundtrip['raw_stats_max_abs']>cfg['comparison_abs']:raise RuntimeError('ROUNDTRIP_OPTICS_MISMATCH')
                budget.guard()
            summaries={str(n):e.summarize(sc,i,e.combine(batches[n])) for n in cfg['levels']}
            pooled=e.combine(batches[max(cfg['levels'])]);point=summaries[str(max(cfg['levels']))]
            leaves=[e.summarize(sc,i,e.combine([b for j,b in enumerate(batches[max(cfg['levels'])]) if j!=q])) for q in range(cfg['batches'])]
            variability={}
            for metric in ['eta_sb','eta_trunc','eta_total','power_kw']:
                val=point[metric];vs=[x[metric] for x in leaves];low=summaries[str(min(cfg['levels']))][metric]
                se=None if val is None or any(x is None for x in vs) else float(np.sqrt((cfg['batches']-1)/cfg['batches']*np.sum((np.array(vs)-np.mean(vs))**2)))
                change=None if val is None or low is None else abs(val-low)
                variability[metric]={'delete_batch_se_approx':se,'prefix_change_abs':change,'note':'same pooled estimator; equal independent batches; correlated nested prefix; no confidence/accuracy certification'}
            flag=(point['counts']['survive']<cfg['low_survival_screen']) or point['status']!='ESTIMATED'
            row={'coverage':{'design':name,'month':month,'hour':hour,'mirror_id':sel['mirror_id'],'position_key':sel['position_key']},'config_sha256':sha(CFG),'design_sha256':selected['design_json_sha256'],
                 'scene_sha256':sc.key,'all_obstacles':sc.n,'candidate_counts':[len(cache.incoming),len(cache.outgoing)],'batches':saved,'level_summaries':summaries,'variability':variability,
                 'screen_vs_exhaustive':comparison,'roundtrip_optics':roundtrip,'abnormal_paths':examples[:8],'diagnostic_flag':flag,
                 'unique_integral_samples':cfg['batches']*max(cfg['levels']),'path_evaluations':paths,'elapsed_seconds':time.perf_counter()-t0,
                 'states':{'input':'VALID','geometry':'PASS_APPROVED_CENTER_RULES','model_domain':'VALID','numerical':point['status'],'rated_power':'NOT_ASSESSED_DIAGNOSTIC_ONLY'}}
            save(targetfile,row);finished.append(row['coverage']);unique+=row['unique_integral_samples'];path_count+=paths;budget.persist()
            save(OUT/'光学诊断检查点.json',{'completed':finished,'completed_count':len(finished),'expected_count':pre['combination_count'],'unique_integral_samples':unique,'path_evaluations':path_count,'current_budget_remaining_s':budget.remaining()})
    # Rebuild from saved records, not only current in-memory statistics.
    rebuilt_results=[]
    for selected in pre['designs']:
        folder=OUT/selected['design'];rows=[load(p) for p in folder.glob('optical_*.json')]
        records=[r['level_summaries'][str(max(cfg['levels']))] for r in rows]
        states={s:sum(v['status']==s for v in records) for s in sorted({v['status'] for v in records})}
        comps=[r['screen_vs_exhaustive'] for r in rows if r['screen_vs_exhaustive']]
        rebuilt_results.append({'design':selected['design'],'n':selected['n'],'total_area_m2':selected['total_area_m2'],'combinations':len(rows),'states':states,
             'survivor_min':min(v['counts']['survive'] for v in records),'capture_min':min(v['counts']['capture'] for v in records),
             'screen_comparisons':len(comps),'all_screen_equal':all(x['all_pass'] for x in comps),'optical_seconds':sum(x['elapsed_seconds'] for x in rows),
             'candidate_in_max_selected':max(x['candidate_counts'][0] for x in rows),'candidate_out_max_selected':max(x['candidate_counts'][1] for x in rows),
             'rated_power':'NOT_ASSESSED','field_power':'NOT_COMPUTED_PARTIAL_MIRROR_POPULATION'})
    result={'designs':rebuilt_results,'new_combinations':len(finished),'unique_integral_samples':unique,'path_evaluations_including_replays':path_count,
            'elapsed_action_seconds':time.perf_counter()-start_total,'full_search_started':False,'formal_tables_generated':False,'config_sha256':sha(CFG)}
    save(OUT/'诊断重建汇总.json',result);return result

def io_test(cfg,budget,attempt):
    probe=OUT/f'io-retry-probe-attempt{attempt}.json';original=Path.replace;count=[0]
    def fail_twice(self,target):
        if Path(target)==probe and count[0]<2:
            count[0]+=1;raise PermissionError('controlled transient replace failure for retry test')
        return original(self,target)
    Path.replace=fail_twice
    try:save(probe,{'value':17,'purpose':'I/O recovery artificial test'})
    finally:Path.replace=original
    assert count[0]==2 and load(probe)['value']==17
    return {'all_pass':True,'injected_failures':count[0],'finite_retries':IO_RETRIES,'no_optical_samples':True}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['tests','old','prep','diagnostics','iotest']);parser.add_argument('--attempt',type=int,default=1);args=parser.parse_args()
    OUT.mkdir(exist_ok=True);cfg=load(CFG);binding_check(cfg)
    record=OUT/f'运行-{args.action}-attempt{args.attempt}.json'
    if record.exists():raise RuntimeError('Preserve old attempt; choose new attempt number')
    budget=Budget(args.action,args.attempt)
    try:
        func={'tests':tests,'old':old_regression,'prep':prep,'diagnostics':diagnostics,'iotest':io_test}[args.action]
        result=func(cfg,budget,args.attempt);save(record,{'status':'COMPLETED','result':result,'config_sha256':sha(CFG),'io_retries':IO_RETRIES});budget.finish('COMPLETED');print(json.dumps(e.clean(result),ensure_ascii=False))
    except Exception:
        error=traceback.format_exc();save(record,{'status':'FAILED_OR_STOPPED','error':error,'config_sha256':sha(CFG)});budget.finish('FAILED_OR_STOPPED');print(error);sys.exit(1)
if __name__=='__main__':main()