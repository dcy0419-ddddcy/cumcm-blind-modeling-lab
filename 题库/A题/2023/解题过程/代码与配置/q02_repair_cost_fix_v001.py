"""Keep restart cost distinct from full candidate cost for startup prediction."""
from pathlib import Path
import json,hashlib
H=Path(__file__).resolve().parent;O=H.parent/'诊断结果/Q02-修复-v001'
src=H/'q02_repair_run_v002.py';dst=H/'q02_repair_run_v003.py'
s=src.read_text(encoding='utf-8').replace("CP=O/'搜索与确认冻结配置-v002.json'","CP=O/'搜索与确认冻结配置-v003.json'")
s=s.replace('evaluation_seconds=time.perf_counter()-start,actual_full60=True',"evaluation_seconds=max(time.perf_counter()-start,sum(r['prepare_seconds']+r['integral_seconds']+r['save_seconds_before_metadata'] for r in recs)),current_action_seconds=time.perf_counter()-start,actual_full60=True")
if dst.exists():raise RuntimeError('Do not overwrite caller')
dst.write_text(s,encoding='utf-8')
(H/'q02_repair_entry_v003.py').write_text((H/'q02_repair_entry_v002.py').read_text(encoding='utf-8').replace('q02_repair_run_v002.py','q02_repair_run_v003.py'),encoding='utf-8')
cp=O/'搜索与确认冻结配置-v002.json';cfg=json.loads(cp.read_text(encoding='utf-8'));cfg['version']='repair-v003-resume-cost';cfg['parent_config_sha256']=hashlib.sha256(cp.read_bytes()).hexdigest();cfg['revision']='Restored full chunk execution cost for startup predictions; current restart time separately recorded. No numerical or search-target change.'
cfg['bindings'].pop(src.name);cfg['bindings'][dst.name]=hashlib.sha256(dst.read_bytes()).hexdigest()
(O/'搜索与确认冻结配置-v003.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
