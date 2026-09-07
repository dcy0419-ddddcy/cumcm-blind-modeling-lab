"""All-object low-survivor audit of saved confirmation counts; no ray evaluation."""
import sys,json,hashlib,csv,time
from pathlib import Path
from datetime import datetime
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[2];DATA=ROOT/'工作记录/诊断结果/Q01-全场-v001';OUT=ROOT/'工作记录/诊断结果/Q01-论文收尾-v001'
OUT.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,a):
    with (OUT/name).open('x',encoding='utf-8') as f:json.dump(a,f,ensure_ascii=False,indent=2,allow_nan=False)
start=time.perf_counter(); result=json.loads((DATA/'汇总与数值核验-v001.json').read_text(encoding='utf-8'))
source_map={x['path']:x['sha256'] for x in result['shards']};mapping=json.loads((DATA/'输入映射与时间.json').read_text(encoding='utf-8'))
counts=[];capture=[];cases=[];bindings=[];delta=np.zeros((13,6))
for ti in range(60):
    path=DATA/'confirmation'/f't{ti:03d}.npz';rel=path.relative_to(ROOT).as_posix();h=sha(path)
    assert h==source_map[rel]
    with np.load(path,allow_pickle=False) as z:
        assert int(z['completed'])==1745 and list(z['levels'])==[128,256]
        kk=z['counts'][-1];ss=z['sums'][-1];pool=ss.sum(0);surv=kk[:,:,1].sum(0);cap=kk[:,:,2].sum(0)
        assert np.all((0<=cap)&(cap<=surv)&(surv<=2048))
        counts.append(surv);capture.append(cap)
        for i in np.flatnonzero(surv<100):
            F=.92*float(z['cosine'][i])*float(z['tau'][i]);dni=float(z['dni']);tm=mapping['times'][ti];row=mapping['rows'][i]
            a={'time_index':ti,'month':tm['month'],'hour':tm['hour'],'mirror_id':i+1,'excel_row':row['excel_row'],'x':row['x'],'y':row['y'],'survivors':int(surv[i]),'captured':int(cap[i]),'per_batch_survivors':kk[:,i,1].tolist(),'per_batch_captured':kk[:,i,2].tolist(),'f1':float(pool[i,1]/pool[i,0]),'f2':float(pool[i,2]/pool[i,0]),'truncation':float(pool[i,2]/pool[i,1]) if pool[i,1]>0 else None}
            cases.append(a)
            for idx,T in [(ti//5,5),(12,60)]:
                delta[idx,0]+=F/(1745*T);delta[idx,2]+=1/(1745*T);delta[idx,3]+=1/(1745*T)
                delta[idx,4]+=dni*36*F/T;delta[idx,5]+=dni*36*F/(T*62820)
    bindings.append({'path':rel,'sha256':h})
allc=np.array(counts);capc=np.array(capture);uniq,freq=np.unique(allc,return_counts=True)
with (OUT/'合并存活数频数-v001.csv').open('x',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['survivors','combination_count']);w.writerows(zip(uniq.tolist(),freq.tolist()))
with (OUT/'低存活组合-v001.csv').open('x',encoding='utf-8-sig',newline='') as f:
    fields=['month','hour','mirror_id','excel_row','x','y','survivors','captured','f1','f2','truncation'];w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(cases)
with (OUT/'全组合存活计数-v001.npz').open('xb') as f:np.savez_compressed(f,survivors=allc,captured=capc)
bins=[0,1,10,25,50,100,250,500,1000,1500,2000,2049];hist,edges=np.histogram(allc,bins)
U=np.array(result['work_uncertainty_indicator']);pt=np.array(result['point']);extended=U+delta
passed=np.column_stack([extended[:,:4]<=.001,extended[:,4:]<=.005*np.abs(pt[:,4:])])
previous=json.loads((DATA/'稀有分母补充核查-v001.json').read_text(encoding='utf-8'));prior={(x['time_index'],x['mirror_id']) for x in previous['cases']}
obj={'created':datetime.now().astimezone().isoformat(),'scope':'retrospective management screen; threshold100 not universal precision standard; no new rays','expected_combinations':104700,'checked_combinations':int(allc.size),'minimum':int(allc.min()),'maximum':int(allc.max()),'quantiles':{str(q):float(np.quantile(allc,q)) for q in [0,.001,.01,.05,.25,.5,.75,.95,.99,1]},'histogram':[{'lower_inclusive':int(edges[i]),'upper_exclusive':int(edges[i+1]),'count':int(hist[i])} for i in range(len(hist))],'zero_survivor_combinations':int((allc==0).sum()),'count_below100':len(cases),'cases':cases,'new_cases_vs_prior':[x for x in cases if (x['time_index'],x['mirror_id']) not in prior],'constraints':'0 <= f2 <= f1 <=1; trunc=f2/f1 only f1>0; net efficiency=rho*cos*tau*f2. Each reported component bound is its coordinatewise diameter over the feasible set, not independent contradictory choices. f1=0 has undefined truncation; diameter of truncation covers all positive-denominator cases. No substitution into point estimates.','effect_diameter_bound':delta.tolist(),'frozen_U':U.tolist(),'supplementary_U_plus_bound':extended.tolist(),'supplementary_passes':passed.tolist(),'supports_original_targets':bool(passed.all()),'max_efficiency_added_bound':float(delta[:,:4].max()),'max_efficiency_U_plus_bound':float(extended[:,:4].max()),'max_power_relative_U_plus_bound':float(np.max(extended[:,4:]/np.abs(pt[:,4:]))),'limits':'conservative effect bounds for screened objects only; U+bound is a supplementary diagnostic, not strict joint confidence. Objects >=100 may still have local error.','sources':bindings+[{'path':(DATA/'汇总与数值核验-v001.json').relative_to(ROOT).as_posix(),'sha256':sha(DATA/'汇总与数值核验-v001.json')}],'script_sha256':sha(Path(__file__)),'elapsed_seconds':time.perf_counter()-start,'new_optical_rays':0}
save('低存活全量核查-v001.json',obj)
print(json.dumps({k:obj[k] for k in ['checked_combinations','minimum','maximum','count_below100','cases','supports_original_targets','max_efficiency_U_plus_bound','max_power_relative_U_plus_bound']},ensure_ascii=False))