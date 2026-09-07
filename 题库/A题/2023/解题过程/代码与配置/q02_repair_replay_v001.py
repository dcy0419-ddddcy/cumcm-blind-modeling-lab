"""Same-source replay from actual delivered Excel at three fixed indices; no search."""
import time
START=time.perf_counter()
from pathlib import Path
import sys,json,traceback
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H))
import q02_repair_common_v001 as io
budget=io.Budget('delivered_excel_same_source_replay','confirmation',START)
try:
 import numpy as np
 from openpyxl import load_workbook
 import q02_fast_v002 as F
 import q02_compact_v001 as compact
 O=io.OUT;fr=io.load(O/'最终拟提交候选冻结.json');cfg=io.load(O/fr['config_file']);des,_=compact.read_compact(O/'frozen/design.bundle.json')
 if not(O/'result2.xlsx').exists():raise RuntimeError('NO_OFFICIAL_DELIVERY')
 if io.sha(O/'result2.xlsx')!=fr['excel_sha256']:raise RuntimeError('DELIVERY_HASH_CHANGED')
 wb=load_workbook(O/'result2.xlsx',read_only=True,data_only=True);rows=list(wb['镜场设计'].values)[1:];wb.close()
 mirrors=[]
 for j,r in enumerate(rows):
  if r[:5]!=(*des.tower_xy,j+1,des.width,des.height)or r[7]!=des.installation_height:raise RuntimeError('COMMON_INPUT_CHANGED')
  old=des.mirrors[j];mirrors.append({'mirror_id':old['mirror_id'],'position_key':old['position_key'],'x':r[5],'y':r[6],'export_row':j+2})
 actual=F.design_module.Design(des.name,des.version,des.tower_xy,des.width,des.height,des.installation_height,mirrors,des.metadata);fd=F.freeze_design(actual)
 if fd.key!=fr['design_key']:raise RuntimeError('REBUILT_DESIGN_CHANGED')
 selected=[(0,0),(fd.n//2,27),(fd.n-1,59)]
 io.save(O/'交付清单重放预登记.json',{'selection':'first/middle/last exported mirror at fixed standard time indices0/27/59, chosen without optical filtering','pairs':selected,'source':'actual result2.xlsx rebuilt, frozen stable identity sidecar','before_replay':True})
 checks=[];plan=cfg['confirmation'];n=plan['n'];B=plan['B'];levels=plan['levels'];times=[(m,h)for m in range(1,13)for h in [9,10.5,12,13.5,15]]
 for j,t in selected:
  budget.guard(15);m,h=times[t];sc=F.scene_at(fd,m,h);seeds=[F.reference.seed_words(cfg['root_seed'],plan['namespace'],t,fd.position_keys[j],b)for b in range(B)]
  r=F.sample_stats(sc,j,seeds,n,levels)
  with np.load(O/'frozen/confirmation'/('time-%02d.npz'%t))as x:
   same={k:bool(np.array_equal(r[k],x[k][:,:,j]))for k in ['sums','cross','counts','unknown_weights','known_capture_weights']}
  checks.append({'export_index':j+1,'mirror_id':fd.mirror_ids[j],'time_index':t,'month':m,'hour':h,'exact_equal':same})
  if not all(same.values()):raise RuntimeError('SAME_SOURCE_REPLAY_DIFFERENCE')
 io.save(O/'实际Excel同源重放核验.json',{'all_pass':True,'design_key':fd.key,'excel_sha256':io.sha(O/'result2.xlsx'),'checks':checks,'replayed_source_samples':len(selected)*B*n,'additional_independent_confirmation_samples':0,'purpose':'replay same rays, not extra independent evidence or new candidate score'})
 budget.finish();print('EXCEL_REPLAY_ALL_PASS')
except BaseException:
 io.save(io.OUT/'实际Excel同源重放失败.json',{'error':traceback.format_exc()});budget.finish('FAILED');raise
