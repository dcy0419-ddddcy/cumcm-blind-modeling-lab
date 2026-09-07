"""Independent work-indicator reconstruction and report data. No new rays."""
import time
START=time.perf_counter()
from pathlib import Path
import sys,json,csv,math
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import q02_search_common_v001 as io

def main(budget):
 import numpy as np
 O=io.OUT;S=O/'frozen/confirmation';su=io.load(S/'summary.json');N=su['coverage']['objects'];B=8
 timing={};trajectory=[]
 for p in sorted((O/'candidates').glob('*/coarse/score.json')):
  q=io.load(p);sp=q['spec'];trajectory.append({'candidate':q['name'],'family':sp.get('generator','circle_rings'),'tower':sp['tower_xy'],'width':sp['width'],'height':sp['height'],'z':sp['installation_height'],'n':q['n'],'area':q['area'],'coarse_score_kw':q['P_score_kw'],'coarse_q':q['q_score_kw_m2'],'zero_survivor':q['zero_survivor'],'zero_capture':q['zero_capture'],'unknown':q['unknown'],'fine':(p.parent.parent/'fine/summary.json').exists()})
 fine=[];fines={}
 for name in ['C01','C07','C05','C22','C21']:
  p=O/'candidates'/name/'fine';q=io.load(p/'score.json');f=io.load(p/'summary.json');fines[name]=f
  fine.append({'candidate':name,'n':q['n'],'area':q['area'],'heuristic_P_kw':q['P_score_kw'],'heuristic_q':q['q_score_kw_m2'],'formal_point':f['point'][-1],'state_counts':f['pooled_state_counts'],'jackknife_se':f['jackknife_se'][-1],'sample_plan':f['coverage'],'score_seconds':q.get('evaluation_seconds')})
 times=[];leave=[];prefix=[];raw=[];low_temporal=[];survival=[];batch_zero=[0,0];candcounts=[];record_sums={'prepare_seconds':0.,'integral_seconds':0.,'save_seconds_before_metadata':0.}
 def one(s,c,co,ta,dni,ar):
  good=(s[:,0]>0)&(s[:,1]>0)&(s[:,2]>0)&(c[:,4]==0)
  eta=np.where(good,.92*co*ta*s[:,2]/s[:,0],np.nan)
  sb=np.where((s[:,0]>0)&(s[:,1]>0)&(c[:,4]==0),s[:,1]/s[:,0],np.nan)
  tr=np.divide(s[:,2],s[:,1],out=np.full(len(s),np.nan),where=good)
  P=dni*np.sum(ar*eta)
  return np.array([eta.mean(),co.mean(),sb.mean(),tr.mean(),P,P/ar.sum()])
 def rows(a):
  a=np.asarray(a);return np.vstack([a.reshape(12,5,6).mean(1),a.mean(0)])
 for ti in range(60):
  budget.guard(10);m=io.load(S/f'time-{ti:02d}.json')
  for k in record_sums:record_sums[k]+=m[k]
  with np.load(S/f'time-{ti:02d}.npz',allow_pickle=False) as x:
   ss=x['sums'];cc=x['counts'];co=x['cosine'];ta=x['tau'];dni=float(x['dni']);ar=x['areas'];s=ss[-1].sum(0);c=cc[-1].sum(0)
   times.append(one(s,c,co,ta,dni,ar));prefix.append(one(ss[0].sum(0),cc[0].sum(0),co,ta,dni,ar))
   leave.append([one(s-ss[-1,b],c-cc[-1,b],co,ta,dni,ar)for b in range(8)])
   good=(s[:,1]>0)&(s[:,2]>0)&(c[:,4]==0)
   # Raw weighted integral, separate from analytic-scale self-normalized point.
   aa=s[:,0]/2048;bb=s[:,1]/2048;dd=s[:,2]/2048
   eta=np.where(good,.92*ta*dd,np.nan);sb=np.where(good,bb/co,np.nan);tr=np.where(good,dd/bb,np.nan);P=dni*np.sum(ar*eta)
   raw.append([eta.mean(),co.mean(),sb.mean(),tr.mean(),P,P/ar.sum()])
   low=c[:,2]<100;F=.92*co*ta;pb=dni*np.sum(ar[low]*F[low]);low_temporal.append([F[low].sum()/N,0.,low.sum()/N,low.sum()/N,pb,pb/ar.sum()])
   survival.extend(c[:,2].tolist());batch_zero[0]+=int((cc[-1,:,:,2]==0).sum());batch_zero[1]+=int((cc[-1,:,:,3]==0).sum());candcounts.extend(x['candidate_counts'].tolist())
 point=rows(times);pref=rows(prefix);raw=rows(raw);lp=np.asarray([rows(np.asarray(leave)[:,b,:])for b in range(8)])
 pv=8*point-7*lp;se=np.std(pv,axis=0,ddof=1)/np.sqrt(8);hw=2.3646242510102993*se;lb=rows(low_temporal);U=np.maximum.reduce([hw,abs(point-pref),abs(point-raw)])+lb
 checks={}
 for name,actual,key in [('point',point,'point'),('leave',lp,'leave_one_batch_estimates'),('prefix',pref,'prefix_half_point'),('raw',raw,'raw_integral_alternative'),('jackknife',se,'jackknife_se'),('low_bound',lb,None),('U',U,'conservative_work_indicator')]:
  expected=np.asarray(su['low_survival']['effect_diameter_bound']if key is None else su[key],float)
  mask=np.isfinite(actual)&np.isfinite(expected);err=float(np.max(abs(actual[mask]-expected[mask])))if mask.any()else None
  checks[name]={'passed':bool(np.array_equal(np.isfinite(actual),np.isfinite(expected))and np.allclose(actual,expected,rtol=2e-9,atol=2e-9,equal_nan=True)),'max_abs_difference':err}
 assert all(v['passed']for v in checks.values()),checks
 v=np.asarray(survival);cand=np.asarray(candcounts)
 # Comparison retained only for the two same-plan structural candidates; no holdout-driven retuning.
 a,b=fines['C22'],fines['C21'];diff=np.asarray(a['point'])[-1]-np.asarray(b['point'])[-1]
 ldiff=np.asarray(a['leave_one_batch_estimates'])[:,-1]-np.asarray(b['leave_one_batch_estimates'])[:,-1]
 pvdiff=4*diff-3*ldiff;dse=np.std(pvdiff,axis=0,ddof=1)/2
 comparison={'C22_minus_C21':diff,'paired_delete_batch_se':dse,'approx_t3_halfwidth':3.182446305284263*dse,'scope':'same B4 n32, paired batch labels and CRN for shared stable slots; approximate pointwise diagnostic after search, not selection-adjusted or holdout evidence'}
 for folder in list((O/'candidates').glob('*/coarse'))+list((O/'candidates').glob('*/fine'))+[S]:
  if not(folder/'checkpoint.json').exists():continue
  ck=io.load(folder/'checkpoint.json');records=ck['records'];bind=io.load(folder/'binding.json')
  timing[str(folder.relative_to(O))]={'completed_times':ck['completed_times'],'complete':ck['complete'],'mirror_time_combinations':sum(r['combinations']for r in records),'unique_samples':sum(r['unique_source_samples']for r in records),'B':bind['B'],'n':bind['n'],'prepare_seconds':sum(r['prepare_seconds']for r in records),'integral_seconds':sum(r['integral_seconds']for r in records),'save_seconds_before_metadata':sum(r['save_seconds_before_metadata']for r in records)}
 result={'new_optical_rays':0,'confirmation_summary_sha256':io.sha(S/'summary.json'),'independent_work_indicator_checks':checks,'coarse_candidates':trajectory,'full60_comparisons':fine,'paired_comparison':comparison,'confirmation':{'annual_point':point[-1],'annual_U':U[-1],'decision':su['formal_decision'],'rated_lower_kw':su['rated_power_lower_work_value_kw'],'margin_kw':su['rated_power_lower_work_value_kw']-60000,'precision_pass':su['all_table_items_precision_met'],'target_pass_count':int(np.asarray(su['target_pass']).sum()),'target_count':78,'max_eff_U':float(np.nanmax(U[:,:4])),'max_relative_power_U':float(np.nanmax(U[:,4:]/abs(point[:,4:]))),'state_counts':su['pooled_state_counts'],'low_survival':su['low_survival'],'survivor_quantiles':dict(zip(['min','p01','p05','p25','median','p75','p95','p99','max'],np.quantile(v,[0,.01,.05,.25,.5,.75,.95,.99,1]))),'pooled_zero_survivor':int((v==0).sum()),'single_batch_zero_survivor_capture':batch_zero,'candidate_mean':cand.mean(0),'candidate_max':cand.max(0),'recorded_component_seconds':record_sums,'numeric_checks':su['numeric_checks']},'evaluation_costs':timing}
 io.save(O/'收尾数据与工作指标独立重建-v001.json',result)
 with (O/'候选比较-诊断-v001.csv').open('w',encoding='utf-8-sig',newline='')as h:
  wr=csv.writer(h);wr.writerow(['候选','N','面积_m2','全60搜索功率_kW','单位面积_kW_m2','正式总量是否定义','额定状态'])
  for f in fine:wr.writerow([f['candidate'],f['n'],f['area'],f['heuristic_P_kw'],f['heuristic_q'],f['formal_point'][4]is not None,'未确认搜索评分'])
 with (O/'C22-独立确认诊断汇总-v001.csv').open('w',encoding='utf-8-sig',newline='')as h:
  wr=csv.writer(h);wr.writerow(['样本月份','光学效率','余弦效率','阴影遮挡效率','截断效率','热功率_kW','单位面积功率_kW_m2','U_光学','U_余弦','U_阴影遮挡','U_截断','U_功率_kW','U_单位面积'])
  for i,row in enumerate(point):wr.writerow([i+1 if i<12 else '年规定60点平均',*row,*U[i]])
 print(json.dumps({'confirmation':{k:v for k,v in result['confirmation'].items()if k not in ['low_survival']},'low_count':su['low_survival']['screened_count'],'U_rebuild':checks,'paired':comparison},ensure_ascii=False,default=io.convert),flush=True)

if __name__=='__main__':
 b=io.Budget('report_data_and_U_reconstruction','confirmation',START)
 try:main(b);b.finish()
 except BaseException as e:
  b.finish('FAILED');io.event('失败运行.jsonl',{'mode':b.mode,'error':repr(e)});raise
