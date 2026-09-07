"""Frozen independent confirmation, parallel time blocks; one job wall-clock budget."""
import time
START=time.perf_counter()
from pathlib import Path
import sys,json,traceback
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import q02_repair_common_v001 as io

def main():
 budget=io.Budget('frozen_independent_confirmation_parallel','confirmation',START)
 try:
  import q02_repair_engine_v001 as eng
  import q02_repair_parallel_v001 as parallel
  O=io.OUT;fr=io.load(O/'最终拟提交候选冻结.json');cfg=io.load(O/fr['config_file']);plan=fr['confirmation_config']
  for name,digest in cfg['bindings'].items():
   if io.sha(HERE/name)!=digest:raise RuntimeError('FROZEN_SOURCE_CHANGED: '+name)
  if plan!=cfg['confirmation']or plan['namespace']in cfg['search_namespaces']:raise RuntimeError('CONFIRMATION_PLAN_CHANGED')
  proof=io.load(O/cfg['execution']['test_record'])
  if not proof['all_pass']or io.sha(O/cfg['execution']['test_record'])!=cfg['execution']['test_sha256']:raise RuntimeError('SCHEDULER_REGRESSION_NOT_PASSED')
  if io.sha(O/fr['excel_file'])!=fr['excel_sha256']:raise RuntimeError('FROZEN_EXCEL_CHANGED')
  fd,_=eng.load_design(O/'frozen')
  if fd.key!=fr['design_key']or io.sha(O/'frozen/design.bundle.json')!=fr['bundle_sha256']:raise RuntimeError('FROZEN_DESIGN_CHANGED')
  arrays,records=parallel.evaluate_parallel(fd,O/'frozen','confirmation',eng.TIMES,plan['B'],plan['n'],plan['levels'],plan['namespace'],budget,root_seed=cfg['root_seed'],workers=cfg['execution']['workers'],reserve_after=90)
  budget.guard(45);ans=eng.stored_summary(arrays,O/'frozen/confirmation','full_confirmation')
  io.save(O/'独立确认结论.json',{'name':fd.name,'design_key':fd.key,'decision':ans['formal_decision'],'annual':ans['point'][-1],'annual_U':ans['conservative_work_indicator'][-1],'all_precision':ans['all_table_items_precision_met'],'rating_lower_kw':ans['rated_power_lower_work_value_kw'],'unresolved':ans['required_table_na_locations'],'low_survival':ans['low_survival'],'numeric_checks':ans['numeric_checks'],'reconstructed_from_saved_chunks':True,'independent_batch_count':plan['B'],'full_combinations':fd.n*60,'source_samples':fd.n*60*plan['B']*plan['n'],'execution':'four independent time-block workers, original optical kernel and per-position random streams unchanged'})
  budget.finish();print(json.dumps(io.load(O/'独立确认结论.json'),ensure_ascii=False))
 except BaseException:
  io.event('失败运行.jsonl',{'action':'parallel_confirm','error':traceback.format_exc(),'used':budget.used()});budget.finish('FAILED');raise

if __name__=='__main__':main()
