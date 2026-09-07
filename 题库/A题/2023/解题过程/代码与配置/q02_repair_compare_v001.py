"""Reconstruct executed candidate comparisons only; no new rays."""
import time
START=time.perf_counter()
from pathlib import Path
import sys,json,csv,math
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H))
import q02_repair_common_v001 as io
budget=io.Budget('repair_comparison_reconstruction','confirmation',START)
try:
 import numpy as np
 O=io.OUT;rows=[];pairs=[]
 for p in sorted((O/'candidates').glob('*/*/score.json')):
  s=io.load(p);rows.append({'name':s['name'],'fidelity':s['score_kind'],'n':s['n'],'area_m2':s['area'],'width':s['spec']['width'],'height':s['spec']['height'],'tower':s['spec']['tower_xy'],'P_formal_kw':s['point'][4],'q_formal_kw_m2':s['point'][5],'P_heuristic_kw':s['P_score_kw'],'q_heuristic_kw_m2':s['q_score_kw_m2'],'state_counts':s['states'],'fine_gate':s['fine_gate'],'search_margin_kw':s['fine_gate_margin_kw'],'source':str(p.relative_to(O))})
 fine=[r for r in rows if r['fidelity']=='fine']
 for i,a in enumerate(fine):
  for b in fine[i+1:]:
   sa=io.load(O/'candidates'/a['name']/'fine/summary.json');sb=io.load(O/'candidates'/b['name']/'fine/summary.json')
   # Whole-batch common-random-number pseudo-value differences; adaptive search diagnostic.
   pa=np.asarray(sa['pseudo_values'],float);pb=np.asarray(sb['pseudo_values'],float);d=pb-pa
   se=np.std(d,axis=0,ddof=1)/math.sqrt(d.shape[0]);diff=np.asarray(sb['point'],float)-np.asarray(sa['point'],float)
   pairs.append({'first':a['name'],'second':b['name'],'difference_second_minus_first':diff,'paired_jackknife_se':se,'approx_pointwise_t3_halfwidth':3.182446305*se,'scope':'same namespace/batch/stable-key pairing, different designs; post-search diagnostic, not selection-corrected or physical confidence'})
 fr=io.load(O/'最终拟提交候选冻结.json')if(O/'最终拟提交候选冻结.json').exists()else None
 final=io.load(O/'独立确认结论.json')if(O/'独立确认结论.json').exists()else None
 old=io.load(O.parent/'Q02-搜索-v001/独立确认结论.json')
 report={'rows':rows,'paired_fine_comparisons':pairs,'new_candidates':len(set(r['name']for r in rows)),'completed_evaluations':len(rows),'low_count':sum(r['fidelity']=='low'for r in rows),'fine_count':len(fine),'all_new_evaluations_full60':True,'old_C22':old,'frozen_name':fr['name']if fr else None,'confirmed_change_from_C22':np.asarray(final['annual'],float)-np.asarray(old['annual'],float)if final else None,'limits':'Low sampled-zero heuristics are NOT formal H02 or rating evidence. Old C22 confirmation now used for search, final new independent namespace only.'}
 io.save(O/'实际候选比较.json',report)
 with(O/'实际候选比较.csv').open('w',encoding='utf-8-sig',newline='')as f:
  keys=['name','fidelity','n','area_m2','width','height','tower','P_formal_kw','q_formal_kw_m2','P_heuristic_kw','q_heuristic_kw_m2','fine_gate','search_margin_kw'];wr=csv.DictWriter(f,fieldnames=keys);wr.writeheader();wr.writerows({k:r[k]for k in keys}for r in rows)
 budget.finish();print(json.dumps({'candidates':report['new_candidates'],'evaluations':len(rows),'fine':len(fine)},ensure_ascii=False))
except BaseException:
 budget.finish('FAILED');raise
