"""Prerequisites, dense geometry pre-registration and timing; no search scores."""
import time
START=time.perf_counter()
from pathlib import Path
import sys,traceback,hashlib,json
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import q02_search_common_v001 as io
budget=io.Budget('preflight','search',START)
try:
 import numpy as np
 import q02_fast_v001 as f
 import q02_compact_v001 as compact
 import q02_fast_tests_v001 as tests
 d=f.design_module;e=f.reference;O=io.OUT
 t=time.perf_counter();tr=tests.run_tests();io.save(O/'提速人工回归.json',tr)
 if not tr['all_pass']:raise RuntimeError('FAST_TEST_FAILURE')
 ct=compact.run_tests(O/'紧凑格式人工测试');io.save(O/'紧凑人工回归.json',ct)
 if not ct['all_passed']:raise RuntimeError('COMPACT_TEST_FAILURE')
 report={'environment':{'python':sys.version,'numpy':np.__version__},'artificial_seconds':time.perf_counter()-t,'designs':[]}
 specs=[compact.make_ring_spec((0,-100),6,5.5,4.5,radial_gap_factor=1.005,angular_gap_factor=1.005,inner=100.5,spacing_margin=.05,name='DenseA'),
        compact.make_ring_spec((80,-160),8,7,5.5,radial_gap_factor=1.005,angular_gap_factor=1.005,inner=100.5,spacing_margin=.05,name='DenseB')]
 io.save(O/'密集诊断配置预登记.json',{'created':io.now(),'specs':specs,'times':[[12,9],[3,12],[6,15]],'selection':'four distinct mirrors: largest incoming+outgoing count, smallest outer boundary margin, smallest nearest neighbor, smallest exclusion margin; stable ID ties; same rays before/after and exhaustive for first two','root_seed':2026090505,'samples_per_batch':128,'independent_batches':8,'comparison_rays':64,'before_any_dense_optical_output':True})
 for spec in specs:
  budget.guard();folder=O/'diagnostics'/spec['name'];t=time.perf_counter();design,gr=d.generate_ring_design(**spec)
  frozen=f.freeze_design(design);geometry_seconds=time.perf_counter()-t
  t=time.perf_counter();receipt=compact.save_compact(design,folder);rebuilt,rr=compact.read_compact(receipt['bundle_path']);disk_seconds=time.perf_counter()-t
  io.save(folder/'generation.json',gr);io.save(folder/'geometry.json',frozen.validation);io.save(folder/'compact_receipt.json',receipt)
  t=time.perf_counter();domains=[]
  for m in range(1,13):
   for h in [9,10.5,12,13.5,15]:
    sc=f.scene_at(frozen,m,h);domains.append({'month':m,'hour':h,'key':sc.key,'domain':sc.domain})
  domain_seconds=time.perf_counter()-t;io.save(folder/'domain60.json',domains)
  scenes=[];selection=[];preparation_seconds=0
  xy=frozen.centers[:,:2];nearest=np.full(frozen.n,np.inf)
  for i in range(frozen.n):
   dx=np.linalg.norm(xy-xy[i],axis=1);dx[i]=np.inf;nearest[i]=dx.min()
  for m,h in [[12,9],[3,12],[6,15]]:
   t=time.perf_counter();sc=f.scene_at(frozen,m,h)
   pairs=[f.candidate_pair(sc,i)for i in range(sc.n)];arr=np.array([[len(q.incoming),len(q.outgoing)]for q in pairs])
   preparation_seconds+=time.perf_counter()-t
   criteria=[-arr.sum(1),350-np.linalg.norm(xy,axis=1),nearest,np.linalg.norm(xy-np.asarray(design.tower_xy),axis=1)-100];picked=[]
   for score in criteria:
    idx=next(i for i in sorted(range(sc.n),key=lambda i:(score[i],frozen.mirror_ids[i]))if i not in picked);picked.append(idx)
   selection.append({'month':m,'hour':h,'indices':picked,'ids':[frozen.mirror_ids[i]for i in picked],'candidate_counts':arr[picked],'all_candidate_max':arr.max(0)})
   scenes.append(sc)
  io.save(folder/'selection_before_optics.json',selection)
  rows=[];fast_s=old_s=exhaustive_s=0
  for sc,sel in zip(scenes,selection):
   for j,i in enumerate(sel['indices']):
    budget.guard();words=[[2026090505,880,sc.month,int(sc.hour*100),int(frozen.mirror_ids[i])&0xffffffff,b]for b in range(8)]
    t=time.perf_counter();st=f.sample_stats(sc,i,words,128,[64,128]);ft=time.perf_counter()-t;fast_s+=ft
    o,ss=f.c.random_rays(sc.mirrors,i,sc.s0,sc.beta,64,words[0]);g,ev=f.trace_same(sc,i,o,ss)
    t=time.perf_counter();rg,rev=e.trace(f.as_reference(sc),i,o,ss);ot=time.perf_counter()-t;old_s+=ot
    eq={k:bool(np.array_equal(ev[k],rev[k]))for k in f.EVENT_KEYS};err=float(np.max(np.abs(g-rg)))
    rs=e.stats(rg,rev);bs=f.batch_as_reference(st,0,0);rawerr=float(np.max(np.abs(np.array(rs['sums'])-bs['sums'])))
    p0=e.summarize(f.as_reference(sc),i,rs);p1=e.summarize(f.as_reference(sc),i,bs)
    pd=0 if p0['power_kw'] is None and p1['power_kw'] is None else None if p0['power_kw'] is None or p1['power_kw'] is None else abs(p0['power_kw']-p1['power_kw'])
    ex=None
    if j<2:
     t=time.perf_counter();xg,xv=f.trace_same(sc,i,o,ss,screen=False);exhaustive_s+=time.perf_counter()-t
     ex={k:bool(np.array_equal(ev[k],xv[k]))for k in f.EVENT_KEYS}
    row={'month':sc.month,'hour':sc.hour,'index':i,'mirror_id':frozen.mirror_ids[i],'seeds':words,'events_equal':eq,'weight_abs':err,'raw_abs':rawerr,'power_abs':pd,'screen_exhaustive':ex,'fast_1024_seconds':ft,'reference_64_seconds':ot,'candidate_counts':st['candidate_counts'],'n_unique':1024,'final_counts':st['counts'][-1].sum(0)}
    rows.append(row);io.save(folder/'optical_comparisons.json',rows)
    if not all(eq.values())or err>1e-12 or rawerr>1e-10 or pd is None or pd>1e-10 or(ex is not None and not all(ex.values())):raise RuntimeError('DENSE_SAME_RAY_REGRESSION_FAILURE')
  # Selected first scene/object rebuilt from compact; identical input and optical event checks.
  rfd=f.freeze_design(rebuilt);rsc=f.scene_at(rfd,12,9);sc=scenes[0];i=selection[0]['indices'][0]
  o,ss=f.c.random_rays(sc.mirrors,i,sc.s0,sc.beta,64,[2026090505,889])
  g,v=f.trace_same(sc,i,o,ss);rg,rv=f.trace_same(rsc,i,o,ss)
  disk_eq=all(np.array_equal(v[k],rv[k])for k in f.EVENT_KEYS)and np.array_equal(g,rg)and rfd.key==frozen.key
  if not disk_eq:raise RuntimeError('DENSE_DISK_INPUT_FAILURE')
  one={'name':design.name,'n':design.n,'area':design.total_area,'geometry_seconds':geometry_seconds,'compact_io_seconds':disk_seconds,'domain60_seconds':domain_seconds,'all_candidates_3_times_seconds':preparation_seconds,
       'fast_integral_seconds':fast_s,'reference_seconds_64_per_combination':old_s,'exhaustive_seconds':exhaustive_s,'combinations':len(rows),'mean_fast_1024_seconds':fast_s/len(rows),'all_comparisons_pass':True,'compact_optical_pass':disk_eq,'compact_csv_bytes':receipt['bytes']['mirrors'],'max_candidates':np.max(np.array([x['all_candidate_max']for x in selection]),axis=0)}
  report['designs'].append(one);io.save(O/'密集压力与计时.json',report);budget.tick()
 # Regression to genuine Q1 old full field, limited same-ray sample.
 centers,rows=f.c.read_field(io.ROOT/'附件/附件03.xlsx')
 olddesign=d.Design('Q1-fast-regression','v001',(0,0),6,6,4,[{'mirror_id':r['mirror_id'],'position_key':'q1-row-'+str(r['excel_row']),'x':r['x'],'y':r['y']}for r in rows],{})
 frozen=f.freeze_design(olddesign);sc=f.scene_at(frozen,12,9);i=56
 o,ss=f.c.random_rays(sc.mirrors,i,sc.s0,sc.beta,256,[2026090505,887])
 g,v=f.trace_same(sc,i,o,ss);rg,rv=e.trace(f.as_reference(sc),i,o,ss)
 check={k:bool(np.array_equal(v[k],rv[k]))for k in f.EVENT_KEYS};check['weight']=bool(np.array_equal(g,rg))
 io.save(O/'Q1限定提速回归.json',{'mirror_id':57,'excel_row':58,'month':12,'hour':9,'samples':256,'checks':check,'all_pass':all(check.values())})
 if not all(check.values()):raise RuntimeError('Q1_FAST_REGRESSION_FAILURE')
 report['all_pass']=True;report['no_search_scores_generated']=True;report['code_bindings']={p.name:io.sha(p)for p in [HERE/'q02_fast_v001.py',HERE/'q02_compact_v001.py',Path(__file__)]}
 io.save(O/'密集压力与计时.json',report);budget.finish()
 print(json.dumps(io.convert(report),ensure_ascii=False))
except BaseException:
 io.event('失败运行.jsonl',{'time':io.now(),'mode':'preflight','error':traceback.format_exc(),'used':budget.used()});budget.finish('FAILED');raise