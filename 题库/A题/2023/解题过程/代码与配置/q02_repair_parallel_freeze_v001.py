"""File-only execution binding update after actual scheduling regression passes."""
from pathlib import Path
import json,hashlib,datetime
H=Path(__file__).resolve().parent;O=H.parent/'诊断结果/Q02-修复-v001'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):
 if p.exists():raise RuntimeError('VERSION_EXISTS: '+str(p))
 p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
proof_path=O/'并行调度同射线测试-v001/测试结论.json';proof=read(proof_path)
if not proof['all_pass']or proof['scheduler_sha']!=sha(H/'q02_repair_parallel_v001.py'):raise RuntimeError('SCHEDULER_NOT_TESTED')
fp=O/'最终拟提交候选冻结.json';fr=read(fp)
if proof['frozen_preflight_binding']['frozen_candidate_sha256']!=sha(fp):raise RuntimeError('PREVIOUS_FREEZE_CHANGED')
if (O/'frozen/confirmation/binding.json').exists():raise RuntimeError('CONFIRMATION_ALREADY_STARTED')
oldcp=O/fr['config_file'];cfg=read(oldcp)
cfg['version']='repair-v004-parallel-confirmation';cfg['parent_config_sha256']=sha(oldcp)
cfg['revision']='Post-freeze, validated time-block scheduling only. Physical design, seeds, B8n256, pooling, U and gates unchanged.'
cfg['bindings']['q02_repair_parallel_v001.py']=sha(H/'q02_repair_parallel_v001.py')
cfg['bindings']['q02_repair_confirm_parallel_v001.py']=sha(H/'q02_repair_confirm_parallel_v001.py')
cfg['execution']={'workers':4,'scheduler':'q02_repair_parallel_v001.py','test_record':'并行调度同射线测试-v001/测试结论.json','test_sha256':sha(proof_path),'task_unit':'one full time, all mirrors/obstacles, original per-key RNG','reserve_after_seconds':90,'accounting':'whole parent job wall time includes spawn/wait/read/write/termination; overlapping internal worker wall times not double counted; worker CPU separately recorded','performance_limit':'tiny test establishes numeric equivalence only, not full throughput guarantee'}
newcp=O/'搜索与确认冻结配置-v004.json';write(newcp,cfg)
prior=O/'最终拟提交候选冻结-v001-串行配置.json';prior.write_bytes(fp.read_bytes())
fr['previous_freeze_file']=prior.name;fr['previous_freeze_sha256']=sha(prior);fr['config_file']=newcp.name;fr['execution_update_time']=datetime.datetime.now().astimezone().isoformat();fr['physical_design_unchanged']=True;fr['execution_binding']=cfg['execution']
fp.write_text(json.dumps(fr,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('v004 execution binding saved; no new design, parameter or optical evaluation.')
