import sys,ast
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import q01_full_run_v002 as r
import q01_full_summary_v002 as s
budget=r.Budget('checkpoint-IO-repair-check')
class Fake:
    def __init__(self,n):self.n=n;self.calls=0
    def replace(self,p):
        self.calls+=1
        if self.calls<=self.n:raise PermissionError('artificial transient replacement denial')
a=Fake(1);r.atomic_replace(a,None)
# Check actual saved JSON transaction, preserving both expected input and output in evidence.
p=r.OUT/'检查点IO人工检查临时.json';r.save(p,{'value':1});r.save(p,{'value':2},False)
A=ast.parse((r.CODE/'q01_full_run_v001.py').read_text(encoding='utf-8'));B=ast.parse((r.CODE/'q01_full_run_v002.py').read_text(encoding='utf-8'))
def body(tree,name): return ast.dump(next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name==name),include_attributes=False)
unchanged={name:body(A,name)==body(B,name) for name in ['field_at','candidates','statistics','read_input']}
complete=[f't{k:03d}.npz' for k in range(60) if (r.OUT/'initial'/f't{k:03d}.npz').exists()]
partial=[]
for pth in (r.OUT/'initial').glob('*-partial.npz'):
    if pth.name.replace('-partial','') in complete:continue
    import numpy as np
    with np.load(pth) as z: n=int(z['completed'])
    backup=r.OUT/('失败时-'+pth.name)
    backup.write_bytes(pth.read_bytes())
    partial.append({'path':str(pth.relative_to(r.ROOT)),'completed':n,'backup':str(backup.relative_to(r.ROOT))})
checks={'one_transient_error_retried':a.calls==2,'saved_json_correct':r.load(p)['value']==2,'numeric_functions_unchanged':all(unchanged.values()),'summary_tests':s.selftest()['all_pass']}
r.save(r.OUT/'检查点修订验证.json',{'checks':checks,'all_pass':all(checks.values()),'numeric_functions':unchanged,'completed_before_restart':complete,'partial_before_restart':partial,'failure':'WinError5 during budget atomic replace; external lock cause not identified','discarded_since_partial_upper_mirrors':249,'discarded_ray_process_upper':249*8*128})
assert all(checks.values())
r.save(r.OUT/'执行修订-v002.json',{'created':r.now(),'base_config_sha256':r.sha(r.CFG),'reason':'I/O bounded retry only; retain base numerical configuration and streams; original complete shards still valid','bindings':{str(p.relative_to(r.ROOT)).replace('\\','/'):r.sha(p) for p in [r.CODE/'q01_full_run_v002.py',r.CODE/'q01_full_summary_v002.py']},'previous_versions_retained':['q01_full_run_v001.py','q01_full_summary_v001.py'],'initial_existing_complete_shards':complete,'no_numerical_invalidation':True})
budget.finish();print(checks,flush=True)