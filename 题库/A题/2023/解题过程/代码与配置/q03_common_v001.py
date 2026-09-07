"""Q3 round budget and atomic evidence I/O. No numerical imports."""
from pathlib import Path
import json, math, os, time
from datetime import datetime
import hashlib
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'工作记录/诊断结果/Q03-实施-v001'
def now():return datetime.now().astimezone().isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def convert(x):
 if hasattr(x,'tolist'):return convert(x.tolist())
 if isinstance(x,dict):return {str(k):convert(v)for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [convert(v)for v in x]
 if isinstance(x,float)and not math.isfinite(x):return None
 return x
def replace(p,target):
 for k in range(8):
  try:Path(p).replace(target);return
  except PermissionError:
   if k==7:raise
   time.sleep(min(.05*2**k,.8))
def save(p,x):
 p=Path(p).resolve()
 if not p.is_relative_to((ROOT/'工作记录').resolve()):raise ValueError('write outside task records')
 p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.part')
 tmp.write_text(json.dumps(convert(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8');replace(tmp,p)
def event(name,x):
 OUT.mkdir(parents=True,exist_ok=True)
 with (OUT/name).open('a',encoding='utf-8')as f:f.write(json.dumps(convert(x),ensure_ascii=False,allow_nan=False)+'\n')
class Budget:
 def __init__(self,mode,phase='search',started=None):
  self.path=OUT/'累计计算预算.json';self.last=started if started is not None else time.perf_counter();self.start=self.last
  self.data=load(self.path)if self.path.exists()else {'limit_seconds':5400.,'confirmation_reserve_seconds':1800.,'used_seconds':0.,'records':[],'round':'new Q3 user-approved 5400 seconds; Q1/Q2 ledgers untouched','scope':'parent job wall from entry before numerical imports, startup/wait/I/O/failure included; overlapping child CPU recorded separately; text writing/typesetting separate, no new search budget'}
  if any(r['status']=='RUNNING'for r in self.data['records']):raise RuntimeError('Unsettled previous RUNNING job; account before resume')
  self.phase=phase;self.record={'mode':mode,'phase':phase,'start':now(),'elapsed_seconds':0.,'status':'RUNNING'}
  self.data['records'].append(self.record);self.tick()
  try:self.guard()
  except BaseException:
   self.finish('REJECTED_BEFORE_COMPUTE');raise
 def used(self):return self.data['used_seconds']+time.perf_counter()-self.last
 def cap(self):return 3600. if self.phase in ('search','prototype') else 5400.
 def remaining(self):return self.cap()-self.used()
 def tick(self):
  current=time.perf_counter();elapsed=current-self.last;self.last=current
  self.data['used_seconds']+=elapsed;self.record['elapsed_seconds']+=elapsed;save(self.path,self.data)
 def guard(self,reserve=5):
  if self.used()+reserve>=self.cap():raise RuntimeError('COMPUTE_BUDGET_LIMIT; checkpoint retained and confirmation reserve protected')
 def finish(self,status='COMPLETED'):
  self.tick();self.record.update(status=status,finish=now());save(self.path,self.data)
