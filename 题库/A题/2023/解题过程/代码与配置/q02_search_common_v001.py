"""Shared offline Q2 search I/O and cumulative compute budget; starts before numerical imports."""
from pathlib import Path
import json,hashlib,time,datetime,os
ROOT=Path(__file__).resolve().parents[2]; W=ROOT/'工作记录';OUT=W/'诊断结果/Q02-搜索-v001'
def now():return datetime.datetime.now().astimezone().isoformat()
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def convert(x):
 if hasattr(x,'tolist'):return convert(x.tolist())
 if isinstance(x,dict):return {str(k):convert(v)for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [convert(v)for v in x]
 if isinstance(x,float) and not __import__('math').isfinite(x):return None
 return x
def replace(p,target):
 for trial in range(8):
  try:Path(p).replace(target);return
  except PermissionError:
   if trial==7:raise
   time.sleep(min(.05*2**trial,.8))
def save(p,value):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.part')
 tmp.write_text(json.dumps(convert(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8');replace(tmp,p)
def event(name,value):
 with (OUT/name).open('a',encoding='utf-8')as f:f.write(json.dumps(convert(value),ensure_ascii=False,allow_nan=False)+'\n')
class Budget:
 def __init__(self,mode,phase='search',started=None):
  self.path=OUT/'累计计算预算.json';self.last=started if started is not None else time.perf_counter();self.start=self.last
  self.data=load(self.path)if self.path.exists()else {'limit_seconds':3600.,'confirmation_reserve_seconds':1200.,'used_seconds':0.,'records':[],'scope':'each process main entry starts before numerical imports; includes geometry/optics/statistics and in-process I/O; excludes document reading/writing and typesetting'}
  if any(x['status']=='RUNNING'for x in self.data['records']):raise RuntimeError('Unsettled RUNNING action; verify prior wall time before resume')
  self.mode=mode;self.phase=phase;self.record={'mode':mode,'phase':phase,'start':now(),'elapsed_seconds':0.,'status':'RUNNING'}
  self.data['records'].append(self.record);self.tick();self.guard()
 def used(self):return self.data['used_seconds']+time.perf_counter()-self.last
 def remaining(self):return 3600-self.used()
 def tick(self):
  current=time.perf_counter();elapsed=current-self.last;self.last=current
  self.data['used_seconds']+=elapsed;self.record['elapsed_seconds']+=elapsed;save(self.path,self.data)
 def guard(self,reserve=5):
  cap=2400. if self.phase=='search' else 3600.
  if self.used()+reserve>=cap:raise RuntimeError('COMPUTE_BUDGET_LIMIT; checkpoints retained and confirmation reserve protected')
 def finish(self,status='COMPLETED'):
  self.tick();self.record.update(status=status,finish=now());save(self.path,self.data)