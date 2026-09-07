"""Q3 sufficient-statistics engine. Full scenes; sparse certificates; no optimization."""
from pathlib import Path
import time, json
import numpy as np
import q03_fast_v001 as f
import q03_design_v001 as design_module
import q03_common_v001 as io
HERE=Path(__file__).resolve().parent
TIMES=[(m,h)for m in range(1,13)for h in [9.,10.5,12.,13.5,15.]]
def save_npz(path,**arrays):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.part')
 with tmp.open('wb')as handle:np.savez(handle,**arrays)
 io.replace(tmp,path)
def load_design(folder):
 p=Path(folder)/'design.json'
 des=design_module.read_design(p)
 return f.freeze_design(des),{'path':str(p),'sha256':io.sha(p)}
def prepare_design(design,folder,budget,domain60=True):
 start=time.perf_counter();folder=Path(folder)
 frozen=f.freeze_design(design);folder.mkdir(parents=True,exist_ok=True)
 target=folder/'design.json'
 if target.exists():
  if io.load(target)!=io.convert(design):raise RuntimeError('EXISTING_DESIGN_CHANGED')
 else:design_module.save_design(design,target)
 io.save(folder/'geometry.json',frozen.validation)
 domains=[]
 if domain60:
  for m,h in TIMES:
   budget.guard(5);sc=f.scene_at(frozen,m,h)
   domains.append({'month':m,'hour':h,'scene_key':sc.key,'domain':sc.domain})
  io.save(folder/'domain60.json',domains)
 io.save(folder/'identity.json',{'name':frozen.name,'key':frozen.key,'sha256':io.sha(target),'n':frozen.n,'area':frozen.total_area,'prepare_and_geometry_domain_seconds':time.perf_counter()-start})
 budget.tick();return frozen
def quick_score(arrays):
 a=arrays['sums'][-1].sum(0);cnt=arrays['counts'][-1].sum(0)
 with np.errstate(divide='ignore',invalid='ignore'):
  eta=arrays['cosine']*arrays['tau']*.92*a[...,2]/a[...,0]
 p=arrays['dni']*(eta*arrays['areas']).sum(1)
 return {'P_score_kw':float(p.mean()),'q_score_kw_m2':float(p.mean()/arrays['areas'].sum()),
         'zero_survivor':int((cnt[...,2]==0).sum()),'zero_capture':int((cnt[...,3]==0).sum()),
         'unknown':int(cnt[...,4].sum()),'formal_rating':'NOT_PERMITTED_HEURISTIC',
         'actual_time_count':len(p),'actual_mirror_count':len(arrays['areas'])}
def stored_summary(arrays,folder,mode):
 import q03_summary_v001 as su
 ans=su.summarize_search_statistics(**arrays,mode=mode)
 io.save(Path(folder)/'summary.json',ans);return ans
