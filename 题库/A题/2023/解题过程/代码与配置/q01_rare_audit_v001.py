"""Postrun rare denominator audit using saved data only, no new rays or retuning."""
import sys,json
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import q01_full_run_v002 as r
budget=r.Budget('rare-event-saved-data-audit')
a=r.load(r.OUT/'汇总与数值核验-v001.json');events=[json.loads(x) for x in (r.OUT/'异常事件.jsonl').read_text(encoding='utf-8').splitlines()]
pairs=sorted({(e['time_index'],e['mirror_id']) for e in events});perturb=np.zeros((13,6));cases=[]
for ti,mid in pairs:
    with np.load(r.OUT/'confirmation'/f't{ti:03d}.npz') as z:
        k=z['counts'][-1,:,mid-1];raw=z['sums'][-1,:,mid-1];c=float(z['cosine'][mid-1]);tau=float(z['tau'][mid-1]);dni=float(z['dni']);pooled=raw.sum(0)
    factor=.92*c*tau;mi=ti//5
    # Change identified object's uncertain fractions over full [0,1]; physical inputs stay fixed.
    for row,nt in [(mi,5),(12,60)]:
        perturb[row,0]+=factor/(1745*nt);perturb[row,2]+=1/(1745*nt);perturb[row,3]+=1/(1745*nt)
        perturb[row,4]+=dni*36*factor/nt;perturb[row,5]+=dni*36*factor/(nt*62820)
    cases.append({'time_index':ti,'month':r.TIMES[ti][0],'hour':r.TIMES[ti][1],'mirror_id':mid,'excel_row':mid+1,'confirmation_batch_survivor':k[:,1].tolist(),'confirmation_batch_capture':k[:,2].tolist(),'pooled_survivor':int(k[:,1].sum()),'pooled_capture':int(k[:,2].sum()),'pooled_eta_sb':float(pooled[1]/pooled[0]),'pooled_eta_trunc':float(pooled[2]/pooled[1]),'status':'positive pooled denominator; rare conditional estimate not individually precise'})
combined=np.array(a['work_uncertainty_indicator'])+perturb
point=np.array(a['point']);passes=np.column_stack([combined[:,:4]<=.001,combined[:,4:]<=.005*np.abs(point[:,4:])])
result={'created':r.now(),'scope':'identified rare cases only; read saved statistics, no optical rerun, no change to frozen estimator or U','events':events,'cases':cases,'full_range_effect_bounds':perturb.tolist(),'frozen_U_plus_effect_bound':combined.tolist(),'all_still_within_targets':bool(passes.all()),'max_additional_efficiency_effect':float(perturb[:,:4].max()),'max_U_plus_effect_efficiency':float(combined[:,:4].max()),'max_U_plus_effect_power_relative':float(np.max(combined[:,4:]/np.abs(point[:,4:]))),'limits':'Conservative sensitivity bound for the identified objects only; combined with approximate U it is not a strict confidence bound and does not cover unobserved physical model error.'}
r.save(r.OUT/'稀有分母补充核查-v001.json',result);budget.finish();print(json.dumps({k:result[k] for k in ['cases','all_still_within_targets','max_U_plus_effect_efficiency','max_U_plus_effect_power_relative']},ensure_ascii=False))