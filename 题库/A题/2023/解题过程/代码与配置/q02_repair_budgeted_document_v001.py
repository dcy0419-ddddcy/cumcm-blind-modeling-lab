"""Optional conservative accounting for arithmetic-containing record formatting."""
import time
START=time.perf_counter()
from pathlib import Path
import sys,runpy,traceback
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H))
import q02_repair_common_v001 as io
name=sys.argv[1]
allowed={'q02_repair_records_v001.py','q02_repair_delivery_v001.py','q02_repair_delivery_v002.py'}
if name not in allowed:raise ValueError('Only explicit record/audit formatters allowed')
b=io.Budget('document_arithmetic_'+name,'confirmation',START)
try:
 sys.argv=[str(H/name)];runpy.run_path(str(H/name),run_name='__main__');b.finish()
except BaseException:
 io.event('失败运行.jsonl',{'action':'document_arithmetic','name':name,'error':traceback.format_exc()});b.finish('FAILED');raise
