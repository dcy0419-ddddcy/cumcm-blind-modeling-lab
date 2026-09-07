"""Preserve frozen v001; fix comparison-only NA schema in a new caller/config."""
from pathlib import Path
import json,hashlib
H=Path(__file__).resolve().parent;W=H.parent;O=W/'诊断结果/Q02-修复-v001'
old=H/'q02_repair_run_v001.py';new=H/'q02_repair_run_v002.py'
s=old.read_text(encoding='utf-8').replace("CP=O/'搜索与确认冻结配置-v001.json'","CP=O/'搜索与确认冻结配置-v002.json'")
s=s.replace("defined=np.isfinite(np.asarray(point,dtype=float)).all();margin=None;gate=False", "required_na=[{'row':i,'metric':j} for i,row in enumerate(summary['point']) for j,value in enumerate(row) if not np.isfinite(float(value) if value is not None else float('nan'))]\n   defined=np.isfinite(np.asarray(point,dtype=float)).all();margin=None;gate=False")
s=s.replace("summary['required_table_na_locations']",'required_na')
if new.exists():raise RuntimeError('Do not overwrite new caller')
new.write_text(s,encoding='utf-8')
entry=(H/'q02_repair_entry_v001.py').read_text(encoding='utf-8').replace('q02_repair_run_v001.py','q02_repair_run_v002.py')
(H/'q02_repair_entry_v002.py').write_text(entry,encoding='utf-8')
cfg=json.loads((O/'搜索与确认冻结配置-v001.json').read_text(encoding='utf-8'))
cfg['version']='repair-v002-caller-schema-fix';cfg['parent_config_sha256']=hashlib.sha256((O/'搜索与确认冻结配置-v001.json').read_bytes()).hexdigest();cfg['revision']='Comparison summary has no confirmation-only NA key; derive required rows from unchanged H02 point finiteness. Physics, random streams, plans and thresholds unchanged; saved time chunks reused.'
cfg['bindings'].pop('q02_repair_run_v001.py');cfg['bindings'][new.name]=hashlib.sha256(new.read_bytes()).hexdigest()
(O/'搜索与确认冻结配置-v002.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(O/'请求-续R023.json').write_text('{"name":"R023"}\n',encoding='utf-8')
print('new caller/config retained beside old version')
