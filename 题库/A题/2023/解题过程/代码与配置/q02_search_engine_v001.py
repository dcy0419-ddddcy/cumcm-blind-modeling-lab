"""Q2 immutable candidate evaluation, all obstacles, per-time checkpoints, no optimizer import effects."""
from pathlib import Path
import sys,time,json,hashlib,os
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import numpy as np
import q02_fast_v002 as f
import q02_compact_v001 as compact
import q02_search_common_v001 as io
TIMES=[(m,h)for m in range(1,13)for h in [9,10.5,12,13.5,15]]
COARSE_TIMES=[(m,h)for m in [3,6,9,12]for h in [9,12,15]]
def save_npz(path,**arrays):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_suffix('.part')
 with tmp.open('wb')as handle:np.savez(handle,**arrays)
 io.replace(tmp,path)
def load_design(folder):
 obj,report=compact.read_compact(Path(folder)/'design.bundle.json')
 return f.freeze_design(obj),report

class CandidateRejected(RuntimeError):
 """Only generation, geometry/search-scope or explicit whole-scene domain rejection."""

def generate(spec,folder,budget):
 folder=Path(folder);budget.guard();start=time.perf_counter()
 parameters=folder/'parameters.json'
 if parameters.exists()and io.load(parameters)!=io.convert(spec):raise RuntimeError('CANDIDATE_SPEC_CHANGED')
 if (folder/'design.bundle.json').exists():
  if not parameters.exists():raise RuntimeError('CANDIDATE_SPEC_BINDING_MISSING')
  frozen,rr=load_design(folder)
 else:
  try:des,gr=f.design_module.generate_ring_design(**spec)
  except ValueError as ex:raise CandidateRejected('GENERATION_FAILURE: '+str(ex))from ex
  # Search coordinates are frozen to the planned 10-decimal output grid before any optical score.
  for row in des.mirrors:row['x']=round(row['x'],10);row['y']=round(row['y'],10)
  des.metadata['output_coordinate_decimal_places']=10
  try:frozen=f.freeze_design(des)
  except f.reference.StateError as ex:
   if str(ex).startswith(('GEOMETRY_FAILURE:','SEARCH_SCOPE_FAILURE:')):raise CandidateRejected(str(ex))from ex
   raise
  io.save(parameters,spec)
  compact.save_compact(des,folder);io.save(folder/'generation.json',gr)
 io.save(folder/'geometry.json',frozen.validation)
 domains=[]
 for m,h in TIMES:
  budget.guard(5)
  try:sc=f.scene_at(frozen,m,h)
  except f.c.DomainError as ex:raise CandidateRejected('MODEL_DOMAIN_FAILURE: '+str(ex))from ex
  domains.append({'month':m,'hour':h,'scene_key':sc.key,'domain':sc.domain})
 io.save(folder/'domain60.json',domains)
 io.event('计算轨迹.jsonl',{'action':'generate_validate_domain','name':frozen.name,'n':frozen.n,'area':frozen.total_area,'seconds':time.perf_counter()-start,'key':frozen.key})
 budget.tick();return frozen

def evaluate(frozen,folder,tag,times,B,n,levels,namespace,budget):
 folder=Path(folder)/tag;folder.mkdir(parents=True,exist_ok=True)
 binding={'design_key':frozen.key,'name':frozen.name,'n_mirrors':frozen.n,'times':times,'B':B,'n':n,'levels':levels,'namespace':namespace,'root_seed':2026090505,'rng':'numpy.PCG64 via SeedSequence; per stable position_key, standard time index, namespace, batch','code_sha':io.sha(Path(__file__)),'fast_sha':io.sha(HERE/'q02_fast_v002.py')}
 if (folder/'binding.json').exists():
  if io.load(folder/'binding.json')!=io.convert(binding):raise RuntimeError('CHECKPOINT_BINDING_MISMATCH')
 else:io.save(folder/'binding.json',binding)
 records=[]
 for local_t,(month,hour)in enumerate(times):
  target=folder/('time-%02d.npz'%local_t);meta=target.with_suffix('.json')
  if target.exists()and meta.exists():
   record=io.load(meta)
   if record['sha256']!=io.sha(target):raise RuntimeError('CHECKPOINT_HASH_FAILURE')
   if (record['month'],record['hour'],record['design_key'],record['combinations'],record['unique_source_samples'])!=(month,hour,frozen.key,frozen.n,B*n*frozen.n):raise RuntimeError('CHECKPOINT_RECORD_BINDING_MISMATCH')
   records.append(record);continue
  budget.guard(10);t=time.perf_counter();sc=f.scene_at(frozen,month,hour);prep=time.perf_counter()-t
  L=len(levels);N=frozen.n
  sums=np.zeros((L,B,N,3));cross=np.zeros((L,B,N,3,3));counts=np.zeros((L,B,N,6),np.int64);uw=np.zeros((L,B,N));known=np.zeros((L,B,N));cand=np.zeros((N,2),np.int64);abnormal=[]
  t=time.perf_counter();time_index=TIMES.index((month,hour))
  for i,key in enumerate(frozen.position_keys):
   if i%128==0:budget.guard(3)
   seeds=[f.reference.seed_words(2026090505,namespace,time_index,key,b)for b in range(B)]
   r=f.sample_stats(sc,i,seeds,n,levels)
   sums[:,:,i]=r['sums'];cross[:,:,i]=r['cross'];counts[:,:,i]=r['counts'];uw[:,:,i]=r['unknown_weights'];known[:,:,i]=r['known_capture_weights'];cand[i]=r['candidate_counts']
   if r['abnormal_paths']:abnormal.append({'i':i,'id':frozen.mirror_ids[i],'paths':r['abnormal_paths']})
  integral=time.perf_counter()-t;t=time.perf_counter()
  save_npz(target,sums=sums,cross=cross,counts=counts,unknown_weights=uw,known_capture_weights=known,cosine=sc.cosine,tau=sc.tau,dni=np.array(sc.dni),areas=frozen.areas,candidate_counts=cand)
  record={'month':month,'hour':hour,'scene_key':sc.key,'design_key':frozen.key,'sha256':io.sha(target),'prepare_seconds':prep,'integral_seconds':integral,'save_seconds_before_metadata':time.perf_counter()-t,'candidate_mean':cand.mean(0),'candidate_max':cand.max(0),'abnormal_paths':abnormal,'combinations':N,'unique_source_samples':B*n*N}
  io.save(meta,record);records.append(io.convert(record));io.save(folder/'checkpoint.json',{'completed_times':len(records),'expected_times':len(times),'records':records,'complete':len(records)==len(times)})
  budget.tick();print(json.dumps({'name':frozen.name,'tag':tag,'time_done':len(records),'times':len(times),'used_seconds':budget.used()},ensure_ascii=False),flush=True)
 # Rebuild statistics from persisted time chunks, never from the integration loop's live arrays.
 arrays={k:[]for k in ['sums','counts','unknown_weights','cosine','tau','dni']}
 for ti in range(len(times)):
  with np.load(folder/('time-%02d.npz'%ti))as x:
   for k in arrays:arrays[k].append(x[k].copy())
 for k in ['sums','counts','unknown_weights']:arrays[k]=np.stack(arrays[k],axis=2)
 for k in ['cosine','tau','dni']:arrays[k]=np.stack(arrays[k],axis=0)
 arrays['areas']=np.asarray(frozen.areas);arrays['levels_n']=levels
 arrays['months']=[m for m,h in times];arrays['hours']=[h for m,h in times];arrays['object_ids']=list(frozen.mirror_ids)
 return arrays,records

def quick_score(arrays):
 """Heuristic self-normalized scoring; sampled zeros reported, never certified as true zero."""
 a=arrays['sums'][-1].sum(0);cnt=arrays['counts'][-1].sum(0)
 eta=arrays['cosine']*arrays['tau']*.92*a[...,2]/a[...,0]
 p=arrays['dni']*(eta*arrays['areas']).sum(1)
 return {'P_score_kw':float(p.mean()),'q_score_kw_m2':float(p.mean()/arrays['areas'].sum()),'zero_survivor':int((cnt[...,2]==0).sum()),'zero_capture':int((cnt[...,3]==0).sum()),'unknown':int(cnt[...,4].sum()),'point_time_power_kw':p,'formal_rating':'NOT_PERMITTED_HEURISTIC','actual_time_count':len(p),'actual_mirror_count':len(arrays['areas'])}

def stored_summary(arrays,folder,mode):
 import q02_search_summary_v002 as su
 ans=su.summarize_search_statistics(**arrays,mode=mode)
 large=['pooled_state','pooled_total_defined','pooled_component_defined']
 # All evidence retained; JSON is auditable while chunks remain the authoritative raw arrays.
 io.save(Path(folder)/'summary.json',ans)
 return ans

