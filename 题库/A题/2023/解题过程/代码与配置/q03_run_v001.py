"""Budgeted Q3 commands. Import numerical modules only inside main."""
import time
START=time.perf_counter()
from pathlib import Path
import sys,json,traceback
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import q03_common_v001 as io

def main():
 action=sys.argv[1]; phase='confirmation' if action in ('freeze','confirm','rebuild','deliver') else 'prototype' if action in ('unit','prototype','init') else 'search'
 budget=io.Budget(action,phase,START)
 try:
  if action=='unit':
   import q03_design_tests_v001 as dt, q03_summary_tests_v001 as st
   report={'design':dt.run_tests(include_r027=True),'summary':st.run_tests()}
   io.save(io.OUT/'prototype/artificial-tests-v001.json',report)
   assert report['design']['all_pass'] and report['summary']['all_pass'], 'ARTIFICIAL_TEST_FAILED'
   print(json.dumps(io.convert(report),ensure_ascii=False),flush=True)
  elif action=='init':
   import q03_design_v001 as d,q03_engine_v001 as e
   base,groups=d.group_baseline(d.from_r027(),3,2)
   base['name']='Q3R000';base['version']='v001'
   io.save(io.OUT/'groups-v001.json',groups)
   f=e.prepare_design(base,io.OUT/'candidates/Q3R000',budget)
   print(json.dumps({'N':f.n,'area':f.total_area,'groups':groups['groups']},ensure_ascii=False),flush=True)
  elif action=='prototype':
   import q03_prototype_v001 as p
   report=p.run(budget);io.save(io.OUT/'prototype/report-v001.json',report)
   assert report.get('all_pass'), 'PROTOTYPE_FAILED'
   print(json.dumps(io.convert(report),ensure_ascii=False),flush=True)
  elif action=='old-analysis':
   import numpy as np
   base=io.load(io.OUT/'candidates/Q3R000/design.json');gg=np.array([r['group']for r in base['mirrors']]);aa=np.array([r['area']for r in base['mirrors']]);qs=[]
   old=io.ROOT/'工作记录/诊断结果/Q02-修复-v001/frozen/confirmation'
   for ti in range(60):
    budget.guard()
    with np.load(old/('time-%02d.npz'%ti),allow_pickle=False)as x:
     s=x['sums'][-1].sum(0);qs.append(float(x['dni'])*.92*x['cosine']*x['tau']*s[:,2]/s[:,0])
   q=np.mean(qs,axis=0);rows=[{'group':g,'n':int((gg==g).sum()),'q_old':float(q[gg==g].mean()),'P_old_kw':float((q[gg==g]*aa[gg==g]).sum())}for g in range(6)]
   io.save(io.OUT/'old-baseline-group-analysis.json',{'rows':rows,'use':'USED_SEARCH_EVIDENCE_NOT_NEW_INDEPENDENT_CONFIRMATION','source':str(old),'old_summary_sha256':io.sha(old/'summary.json')});print(json.dumps(rows),flush=True)
  elif action=='budget-probe':
   actual=io.OUT;fixture=actual/'prototype/budget-edge-fixture';fixture.mkdir(exist_ok=True)
   io.save(fixture/'累计计算预算.json',{'used_seconds':3599.,'records':[]})
   try:
    io.OUT=fixture
    try:io.Budget('synthetic-rejected-start','search');raise AssertionError('Budget failed to reject')
    except RuntimeError as exc:assert 'COMPUTE_BUDGET_LIMIT'in str(exc)
   finally:io.OUT=actual
   rr=io.load(fixture/'累计计算预算.json');assert rr['records'][-1]['status']=='REJECTED_BEFORE_COMPUTE'
   io.save(actual/'prototype/budget-edge-check.json',{'passed':True,'scope':'artificial child ledger only; live numerical round not reset','record':rr})
   print('budget constructor edge PASS',flush=True)
  elif action=='compare':
   import numpy as np
   tag=sys.argv[2]or'low';rows=[]
   bp=io.OUT/'candidates/Q3R000'/tag/'summary.json';bs=io.load(bp)if bp.exists()else None
   for folder in sorted((io.OUT/'candidates').glob('Q3R*')):
    sp=folder/tag/'summary.json';qp=folder/tag/'score.json'
    if not(sp.exists()and qp.exists()):continue
    s=io.load(sp);q=io.load(qp);row={'name':folder.name,'tag':tag,**q['quick'],'area':q['total_area'],'summary_sha256':io.sha(sp)}
    a=np.asarray(s['point'],float);row['annual_formal_point']=a[-1]
    if bs and np.isfinite(a[-1,4:]).all():
     b=np.asarray(bs['point'],float);pp=np.asarray(s['pseudo_values'],float);pb=np.asarray(bs['pseudo_values'],float)
     delta=a[-1,5]-b[-1,5];se=np.std((pp-pb)[:,-1,5],ddof=1)/np.sqrt(len(pp))
     us=np.max([3*np.asarray(s['jackknife_se'],float)[-1,4],abs(a[-1,4]-np.asarray(s['prefix_half_point'],float)[-1,4]),abs(a[-1,4]-np.asarray(s['raw_integral_alternative'],float)[-1,4])])
     row.update(delta_q=delta,paired_search_se=se,power_search_work=us,power_search_margin=a[-1,4]-us-60000,finite_freeze_gate=bool(np.isfinite(se)and a[-1,4]-us>60000 and delta>3*se))
    rows.append(row)
   io.save(io.OUT/('comparison-'+tag+'-v001.json'),rows);print(json.dumps(io.convert(rows),ensure_ascii=False),flush=True)
  elif action=='deliver':
   import q03_delivery_v001 as dl
   ans=dl.deliver(budget);print(json.dumps(io.convert(ans),ensure_ascii=False),flush=True)
  elif action=='freeze':
   import q03_delivery_v001 as dl
   ans=dl.freeze(sys.argv[2],sys.argv[3],budget);print(json.dumps({'candidate':ans['candidate'],'changes_count':len(ans['readback_changes']),'key':ans['frozen_design_key']},ensure_ascii=False),flush=True)
  elif action in ('score','confirm'):
   import q03_engine_v001 as e,q03_parallel_v001 as p,q03_design_v001 as d
   spec=io.load(io.OUT/sys.argv[2]);folder=io.OUT/'candidates'/spec['name']
   rules_path=io.OUT/spec.get('rules','搜索规则冻结-v001.json')
   launch={'rules_sha256':io.sha(rules_path),'spec_sha256':io.sha(io.OUT/sys.argv[2]),'runner_sha256':io.sha(__file__),'wrapper_sha256':io.sha(HERE/'q03_job_v001.ps1'),'action':action}
   if action=='confirm':
    freeze=io.load(io.OUT/spec['freeze']);plan=freeze['planned_confirmation']
    if spec['name']not in (freeze['candidate'],'Q3R000'):raise ValueError('CONFIRMATION_CANDIDATE_NOT_FROZEN')
    for key in ('B','n','levels','namespace'):
     if spec[key]!=plan[key]:raise ValueError('CONFIRMATION_SPEC_DIFFERS:'+key)
    if launch['rules_sha256']!=freeze['rules_sha256']:raise ValueError('CONFIRMATION_RULES_CHANGED')
    for key,digest in freeze['launch_sources'].items():
     if io.sha(HERE/key)!=digest:raise ValueError('CONFIRMATION_LAUNCH_SOURCE_CHANGED:'+key)
    expected=freeze['frozen_design_sha256']if spec['name']==freeze['candidate']else freeze['baseline_design_sha256']
    if io.sha(folder/'design.json')!=expected:raise ValueError('CONFIRMATION_DESIGN_CHANGED')
    if io.sha(io.OUT/freeze['xlsx'])!=freeze['xlsx_sha256']:raise ValueError('CONFIRMATION_XLSX_CHANGED')
    launch['freeze_sha256']=io.sha(io.OUT/spec['freeze']);launch['passed']=True
   lp=folder/spec['tag']/'launch-binding.json'
   if lp.exists()and io.load(lp)!=launch:raise ValueError('LAUNCH_BINDING_MISMATCH')
   io.save(lp,launch)
   if not(folder/'design.json').exists():
    parent=io.load(io.OUT/'candidates'/spec.get('parent','Q3R000')/'design.json')
    des=d.apply_groups(parent,{int(k):v for k,v in spec['changes'].items()},spec['name'])
    e.prepare_design(des,folder,budget)
   elif action=='score'and spec['name']!='Q3R000':
    parent=io.load(io.OUT/'candidates'/spec.get('parent','Q3R000')/'design.json')
    expected=d.apply_groups(parent,{int(k):v for k,v in spec['changes'].items()},spec['name'])
    if expected!=io.load(folder/'design.json'):raise ValueError('EXISTING_DESIGN_SPEC_EXPANSION_MISMATCH')
   f,read=e.load_design(folder)
   arrays,records=p.evaluate_parallel(f,folder,spec['tag'],e.TIMES,spec['B'],spec['n'],spec['levels'],spec['namespace'],budget,reserve_after=spec.get('reserve_after',60))
   quick=e.quick_score(arrays);summary=e.stored_summary(arrays,folder/spec['tag'],spec['mode'])
   io.save(folder/spec['tag']/'score.json',{'quick':quick,'source_spec':spec,'source_spec_sha256':io.sha(io.OUT/sys.argv[2]),'summary_sha256':io.sha(folder/spec['tag']/'summary.json'),'total_area':f.total_area,'used_seconds':budget.used()})
   io.event('scores.jsonl',{'name':spec['name'],'tag':spec['tag'],'score':quick,'area':f.total_area,'used_seconds':budget.used()})
   print(json.dumps(quick,ensure_ascii=False),flush=True)
  else:raise ValueError('Unknown action '+action)
  budget.finish()
 except BaseException:
  io.event('failures.jsonl',{'action':action,'at':io.now(),'traceback':traceback.format_exc(),'runner_sha256':io.sha(__file__)})
  budget.finish('FAILED');raise

if __name__=='__main__':main()


