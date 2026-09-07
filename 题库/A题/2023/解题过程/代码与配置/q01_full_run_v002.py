"""Q1 full run v002 (bounded retry of atomic checkpoint replacement). Local only; immutable shards, cumulative timed budget."""
import time
START=time.perf_counter()
import sys,json,hashlib,platform,math,traceback,os
from pathlib import Path
from datetime import datetime
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0,str(Path(__file__).resolve().parent))
import q01_core_v003 as c
ROOT=Path(__file__).resolve().parents[2]
CODE=Path(__file__).parent
OUT=ROOT/'工作记录/诊断结果/Q01-全场-v001'
OUT.mkdir(exist_ok=True)
CFG=CODE/'Q01-全场配置-v001.json'
BETA=.00465; CYL=c.Cylinder(); TOL=c.Tolerance(); TIMES=[(m,h) for m in range(1,13) for h in [9,10.5,12,13.5,15]]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
    if isinstance(x,dict): return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)): return [clean(v) for v in x]
    if isinstance(x,np.ndarray): return clean(x.tolist())
    if isinstance(x,np.generic): return clean(x.item())
    if isinstance(x,float) and not math.isfinite(x): return None
    return x
def atomic_replace(tmp,p):
    # Windows may transiently deny replacing a file opened by another process.
    # Retry the identical committed bytes, never change numeric state to force a write.
    for attempt in range(20):
        try:
            tmp.replace(p)
            return
        except PermissionError:
            if attempt==19: raise
            time.sleep(min(.02*(attempt+1),.2))

def save(p,obj,exclusive=True):
    p=Path(p)
    if exclusive and p.exists(): raise RuntimeError('Refuse overwrite: '+str(p))
    tmp=p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(json.dumps(clean(obj),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    atomic_replace(tmp,p)
def load(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def now(): return datetime.now().astimezone().isoformat()
class Budget:
    def __init__(self,mode):
        self.path=OUT/'累计计算预算.json'; self.mode=mode
        if self.path.exists(): self.data=load(self.path)
        else: self.data={'limit_seconds':1800,'charged_seconds':3.0,'entries':[{'mode':'core regression v003','charged_seconds':3.0,'observed_process_seconds':2.809666,'note':'rounded up including startup'}]}
        self.base=self.data['charged_seconds']; self.start=START
        self.data['active']=mode; self.tick()
    def used(self): return self.base+2.+time.perf_counter()-self.start
    def tick(self):
        self.data['charged_seconds']=self.used(); self.data['updated']=now(); save(self.path,self.data,False)
    def guard(self,reserve=20):
        if self.used()>1800-reserve: raise TimeoutError('Cumulative calculation budget boundary')
    def finish(self,status='done'):
        charge=self.used()-self.base
        self.data['entries'].append({'mode':self.mode,'charged_seconds':charge,'status':status,'time':now(),'startup_reserve_seconds':2.0})
        self.data['active']=None; self.tick()

def read_input():
    centers,rows=c.read_field(ROOT/'附件/附件03.xlsx')
    assert [r['mirror_id'] for r in rows]==list(range(1,1746))
    assert [r['excel_row'] for r in rows]==list(range(2,1747))
    assert len({(r['x'],r['y']) for r in rows})==1745
    return centers,rows

def field_at(centers,ti):
    m,h=TIMES[ti]; sun=c.solar(m,h); field,target=c.aim_field(centers,sun['s0'],CYL)
    dom=c.check_domain(field,sun['s0'],BETA,CYL,target)
    d=np.linalg.norm(centers-np.array(CYL.center),axis=1); tau=.99321-.0001176*d+1.97e-8*d*d
    return sun,field,target,tau,dom

def candidates(field,i,sun,target): return (c.conservative_candidates(field,i,sun['s0'],BETA,TOL),c.conservative_candidates(field,i,target[i],BETA,TOL))

def stress_prepare(budget):
    centers,rows=read_input(); counts=np.empty((60,1745,2),np.int16); domains=[]
    for ti in range(60):
        sun,f,t,tau,dom=field_at(centers,ti); domains.append(dict(time_index=ti,month=TIMES[ti][0],hour=TIMES[ti][1],**dom))
        for i in range(1745): counts[ti,i]=[len(x) for x in candidates(f,i,sun,t)]
        budget.tick(); budget.guard()
    delta=centers[:,None,:2]-centers[None,:,:2]; dist2=np.sum(delta*delta,axis=-1)
    dense=np.sum((dist2>0)&(dist2<=20**2),axis=1)
    chosen=[]; used=set()
    for channel,label in [(0,'maximum incoming candidate count'),(1,'maximum outgoing candidate count')]:
        order=np.argsort(-counts[:,:,channel].ravel(),kind='stable'); seen_mirrors=set()
        for k in order:
            ti,i=divmod(int(k),1745)
            if (ti,i) in used or i in seen_mirrors: continue
            chosen.append(dict(time_index=ti,month=TIMES[ti][0],hour=TIMES[ti][1],**rows[i],rule=label,candidates=counts[ti,i].tolist(),neighbors_20m=int(dense[i])))
            used.add((ti,i));seen_mirrors.add(i)
            if len(seen_mirrors)==4: break
    density_order=np.argsort(-dense,kind='stable')
    for ti in [0,29,32,59]:
        i=next(int(i) for i in density_order if (ti,int(i)) not in used)
        chosen.append(dict(time_index=ti,month=TIMES[ti][0],hour=TIMES[ti][1],**rows[i],rule='maximum 20m neighbor count at prescribed low/high/mid time',candidates=counts[ti,i].tolist(),neighbors_20m=int(dense[i])))
        used.add((ti,i))
    save(OUT/'压力样本预登记.json',{'created':now(),'before_optics':True,'selection_rules':'four distinct mirrors for each candidate maximum; four fixed time density maxima; stable ties Excel row','selected':chosen,'candidate_range':{'incoming':[int(counts[:,:,0].min()),int(counts[:,:,0].max())],'outgoing':[int(counts[:,:,1].min()),int(counts[:,:,1].max())]},'max_neighbors_20m':int(dense.max()),'domain_checks':domains,'input_sha256':sha(ROOT/'附件/附件03.xlsx'),'core_sha256':sha(c.__file__),'full_obstacles':1745,'test_rays_per_combination':256,'benchmark_batches':8,'benchmark_n':256,'seed_root':2026090402})
    with (OUT/'候选数量几何统计.npz').open('xb') as f: np.savez_compressed(f,counts=counts,density=dense)
    print(json.dumps({'selected':chosen,'range_in':counts[:,:,0].max().item(),'range_out':counts[:,:,1].max().item()},ensure_ascii=False),flush=True)

def stress_run(budget):
    p=load(OUT/'压力样本预登记.json'); centers,rows=read_input(); records=[]
    assert p['core_sha256']==sha(c.__file__) and p['input_sha256']==sha(ROOT/'附件/附件03.xlsx')
    old=load(ROOT/'工作记录/诊断结果/Q01-全场前核心回归-v001.json'); assert old['all_pass'] and old['core_sha256']==sha(c.__file__)
    for item in p['selected']:
        ti=item['time_index'];i=item['mirror_id']-1;sun,f,t,tau,dom=field_at(centers,ti); cand=candidates(f,i,sun,t)
        seed=[2026090402,901,ti,i+1,0];o,s=c.random_rays(f,i,sun['s0'],BETA,256,seed)
        t0=time.perf_counter(); a=c.trace(o,s,f,i,sun['s0'],t,CYL,BETA,TOL,False); full_sec=time.perf_counter()-t0
        t0=time.perf_counter(); b=c.trace(o,s,f,i,sun['s0'],t,CYL,BETA,TOL,True,candidate_ids=cand); screen_sec=time.perf_counter()-t0
        keys=['S','B','R','unknown']; matches={k:bool(np.array_equal(a[k],b[k])) for k in keys}
        t0=time.perf_counter(); oo=[];ss=[]
        for j in range(8):
            op,sp=c.random_rays(f,i,sun['s0'],BETA,256,[2026090402,902,ti,i+1,j]);oo.append(op);ss.append(sp)
        ob,sb=np.concatenate(oo),np.concatenate(ss)
        c.trace(ob,sb,f,i,sun['s0'],t,CYL,BETA,TOL,True,candidate_ids=cand)
        bench=time.perf_counter()-t0
        ext=c.trace(o,s,f,i,sun['s0'],t,CYL,BETA,TOL,True,end_offset=50.,candidate_ids=cand)
        g=(s@f.normals[i])/(s@sun['s0'])
        def shares(e):
            survive=e['S']&e['B']; cap=survive&e['R'];v1=float(np.sum(g*survive)/sum(g));v2=float(np.sum(g*cap)/sum(g))
            return {'sb':v1,'trunc':v2/v1 if v1 else None,'net':v2}
        rec=dict(**item,seed=seed,matches=matches,full_seconds=full_sec,screen_seconds=screen_sec,benchmark_8x256_seconds=bench,N04_original=shares(b),N04_extended_50m=shares(ext),N04_net_event_equal=bool(np.array_equal(b['S']&b['B']&b['R'],ext['S']&ext['B']&ext['R'])),unknown=int(b['unknown'].sum()))
        if not all(matches.values()):
            bad=np.flatnonzero(np.logical_or.reduce([a[k]!=b[k] for k in keys]))
            rec['mismatch_examples']=[{'ray':int(q),'origin':o[q].tolist(),'sun':s[q].tolist()} for q in bad[:16]]
        records.append(rec);budget.tick();budget.guard()
    good=all(all(r['matches'].values()) and r['N04_net_event_equal'] for r in records)
    save(OUT/'压力测试与计时.json',{'created':now(),'passed':good,'records':records,'core_sha256':sha(c.__file__),'prescreened_at':p['created'],'projection_full_8x256_seconds':float(np.median([r['benchmark_8x256_seconds'] for r in records])*104700),'diagnostic_rays':len(records)*(256*3+8*256),'note':'same-ray full/screen/endpoint; benchmark rays separate. Timing only conservative representative estimate, not performance guarantee.'})
    print(json.dumps({'passed':good,'cases':len(records),'max_candidates':max(sum(r['candidates']) for r in records),'median_8x256_seconds':float(np.median([r['benchmark_8x256_seconds'] for r in records]))}),flush=True)
    if not good: raise RuntimeError('Stress gate failed')

def freeze(budget):
    assert load(OUT/'压力测试与计时.json')['passed']
    paths=[ROOT/'附件/附件03.xlsx',ROOT/'题目.pdf',ROOT/'AGENTS.md',Path(c.__file__),Path(__file__),CODE/'q01_full_summary_v001.py',CODE/'q01_tests_v003.py',ROOT/'工作记录/阶段记录/Q01-建模与原型验证-v001.md',ROOT/'工作记录/阶段记录/Q01-方案构造-v001.md']
    paths += [ROOT/'方法库'/f for f in ['M03-条件能量比与分布归一化-v001.md','M04-平均权重与非线性汇总-v001.md','M05-数值误差验证与复现-v001.md']]
    paths += [ROOT/'补充资料'/f for f in ['P01-角尺度来源与边界-v001.md','P02-方向分布与待选假设-v001.md']]
    config={'version':'v001','frozen_at':now(),'scope':'Q1 all 1745 mirrors x 60 times; no Q2/Q3','bindings':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in paths},'beta_rad':BETA,'rho':.92,'H':'H01-H04 Q1 only','N':'N01-N05 approved; N04 computational bookkeeping for this full run','geometry':{'scale_m':1000,'factor':256},'rng':'NumPy PCG64 SeedSequence','seed_root':2026090402,'seed_words':'[root,ensemble_code,time_index,mirror_id,batch]','ensembles':{'initial':{'code':911,'batches':8,'n':128,'prefix_levels':[128]},'confirmation':{'code':912,'batches':8,'n':256,'prefix_levels':[128,256]}},'design':'Fixed before full optics. Independent confirmation not used for tuning. No automatic sample escalation beyond these levels. If unmet, report unmet within budget. Prefixes correlated, never counted twice. Initial and confirmation seeds disjoint.','point_estimator':'per mirror pool raw sums across 8 equal-size batches; self normalized ratios then H02. Final point uses confirmation only.','uncertainty':'delete-one-whole-batch jackknife of exact pooled-summary functional; t_7 0.975 halfwidth approximate pointwise, not simultaneous/strict; no mirror/time sqrt shortcut','t7':2.3646242515927844,'work_indicator':'max(jackknife t halfwidth, absolute confirmation256-confirmation128, absolute confirmation256-initial128, raw-integral alternative shift); refinement terms diagnostics not confidence bounds','efficiency_abs_target':.001,'power_rel_target':.005,'near_zero_rule':'if abs(power)<=10*halfwidth or abs(power)<=1e-12 kW, relative criterion unresolved; report absolute indicator','budget_seconds':1800,'budget_guard_reserve_seconds':20,'checkpoint':'atomic per-time shards plus every 250 mirrors partial checkpoint; charge elapsed every 100; resume identical seeds and verify hashes; completed shards never overwrite','anomalies':'save object/time/batch/ray seed, raw stats, first 8 uncertain rays; sampled zeros stay unresolved until pooled evidence; do not fill/drop. Systemic failures pause.','environment':{'python':sys.version,'numpy':np.__version__,'platform':platform.platform(),'openblas_threads':os.environ.get('OPENBLAS_NUM_THREADS')},'total_unique_final_rays':104700*8*256,'full_optics_started':False}
    save(CFG,config); save(OUT/'配置冻结证明.json',{'created':now(),'config_sha256':sha(CFG),'budget_used':budget.used(),'stress_passed':True})
    print(json.dumps({'frozen':True,'budget_used':budget.used(),'planned_unique_rays_all_ensembles':104700*8*(128+256)}),flush=True)

def check_bindings(cfg):
    for rel,h in cfg['bindings'].items():
        if sha(ROOT/rel)!=h: raise RuntimeError('Frozen input/code changed: '+rel)
    assert load(OUT/'配置冻结证明.json')['config_sha256']==sha(CFG)
    rev=load(OUT/'执行修订-v002.json')
    for rel,h in rev['bindings'].items():
        if sha(ROOT/rel)!=h: raise RuntimeError('Execution revision changed: '+rel)

def statistics(g,e,n,B,levels):
    gg=g.reshape(B,n);S=e['S'].reshape(B,n);BB=e['B'].reshape(B,n);R=e['R'].reshape(B,n);U=e['unknown'].reshape(B,n)
    X=np.stack([gg,gg*S*BB,gg*S*BB*R],axis=-1)
    sums=[];cross=[];counts=[];uw=[]
    for k in levels:
        x=X[:,:k]; sums.append(x.sum(axis=1));cross.append(np.einsum('bni,bnj->bij',x,x))
        counts.append(np.stack([(~S[:,:k]).sum(1),(S[:,:k]&BB[:,:k]).sum(1),(S[:,:k]&BB[:,:k]&R[:,:k]).sum(1),U[:,:k].sum(1),(~BB[:,:k]).sum(1),R[:,:k].sum(1)],axis=-1))
        uw.append((gg[:,:k]*U[:,:k]).sum(1))
    return np.array(sums),np.array(cross),np.array(counts),np.array(uw)

def full_run(ensemble,budget):
    cfg=load(CFG);check_bindings(cfg); centers,rows=read_input();en=cfg['ensembles'][ensemble];B=en['batches'];n=en['n'];levels=en['prefix_levels'];L=len(levels)
    folder=OUT/ensemble;folder.mkdir(exist_ok=True)
    runlog=OUT/'运行事件.jsonl'; meta=OUT/'输入映射与时间.json'
    if not meta.exists():
        save(meta,{'rows':rows,'times':[{'time_index':j,'month':m,'hour':h,'D':c.solar(m,h)['D'],'dni_kw_m2':c.solar(m,h)['dni']} for j,(m,h) in enumerate(TIMES)],'mirror_area_m2':36.,'total_area_m2':1745*36.,'config_sha256':sha(CFG)})
    completed=[]
    for ti in range(60):
        dest=folder/f't{ti:03d}.npz'
        if dest.exists():
            with np.load(dest,allow_pickle=False) as zz:
                assert str(zz['config_sha256'])==sha(CFG) and int(zz['completed'])==1745
            completed.append(ti);continue
        budget.guard();sun,f,target,tau,dom=field_at(centers,ti);cosi=f.normals@sun['s0'];partial=folder/f't{ti:03d}-partial.npz'
        S=np.zeros((L,B,1745,3));X=np.zeros((L,B,1745,3,3));K=np.zeros((L,B,1745,6),np.int32);UW=np.zeros((L,B,1745));CC=np.zeros((1745,2),np.int16);done=0
        if partial.exists():
            with np.load(partial,allow_pickle=False) as z:
                assert str(z['config_sha256'])==sha(CFG)
                S=z['sums'];X=z['cross'];K=z['counts'];UW=z['unknown_weights'];CC=z['candidates'];done=int(z['completed'])
        def checkpoint(final=False):
            p=dest if final else partial
            temp=p.with_suffix('.npz.tmp')
            with temp.open('wb') as stream: np.savez_compressed(stream,sums=S,cross=X,counts=K,unknown_weights=UW,candidates=CC,completed=done,time_index=ti,levels=np.array(levels),n=n,batches=B,ensemble=ensemble,cosine=cosi,tau=tau,dni=sun['dni'],config_sha256=sha(CFG),execution_sha256=sha(Path(__file__)))
            atomic_replace(temp,p)
            budget.tick()
        for i in range(done,1745):
            if i%100==0: budget.tick();budget.guard()
            cand=candidates(f,i,sun,target);CC[i]=[len(q) for q in cand]
            origins=[];dirs=[]
            for b in range(B):
                o,s=c.random_rays(f,i,sun['s0'],BETA,n,[cfg['seed_root'],en['code'],ti,i+1,b]);origins.append(o);dirs.append(s)
            o=np.concatenate(origins);s=np.concatenate(dirs)
            e=c.trace(o,s,f,i,sun['s0'],target,CYL,BETA,TOL,True,candidate_ids=cand)
            g=(s@f.normals[i])/(s@sun['s0'])
            if np.any(g<=0) or not np.all(np.isfinite(g)): raise c.DomainError('Invalid full weight')
            S[:,:,i],X[:,:,i],K[:,:,i],UW[:,:,i]=statistics(g,e,n,B,levels)
            if np.any(e['unknown']) or np.any(K[-1,:,i,1:3]==0):
                example=[]
                for q in np.flatnonzero(e['unknown'])[:8]: example.append({'batch':int(q//n),'ray':int(q%n),'origin':o[q].tolist(),'direction':s[q].tolist(),'receiver':str(e['receiver_kind'][q])})
                with (OUT/'异常事件.jsonl').open('a',encoding='utf-8') as stream: stream.write(json.dumps({'ensemble':ensemble,'time_index':ti,'mirror_id':i+1,'excel_row':rows[i]['excel_row'],'counts':K[-1,:,i].tolist(),'examples':example},ensure_ascii=False)+'\n')
            done=i+1
            if done%250==0: checkpoint()
        checkpoint(True);completed.append(ti)
        with runlog.open('a',encoding='utf-8') as stream: stream.write(json.dumps({'time':now(),'ensemble':ensemble,'time_index':ti,'completed':1745,'rays':1745*B*n,'cumulative_budget':budget.used(),'sha256':sha(dest)})+'\n')
        print(json.dumps({'ensemble':ensemble,'time_index':ti,'of':60,'cumulative_seconds':round(budget.used(),2)},ensure_ascii=False),flush=True)
    save(OUT/f'{ensemble}-完成.json',{'time':now(),'completed_times':completed,'combinations':len(completed)*1745,'independent_batches':B,'n_per_batch_per_combination':n,'unique_rays':len(completed)*1745*B*n,'levels':levels,'config_sha256':sha(CFG)})

if __name__=='__main__':
    mode=sys.argv[1];budget=Budget(mode)
    try:
        if mode=='prepare': stress_prepare(budget)
        elif mode=='stress': stress_run(budget)
        elif mode=='freeze': freeze(budget)
        elif mode in ['initial','confirmation']: full_run(mode,budget)
        else: raise ValueError(mode)
    except BaseException:
        err=traceback.format_exc()
        with (OUT/'失败运行.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'time':now(),'mode':mode,'error':err,'budget':budget.used()},ensure_ascii=False)+'\n')
        budget.finish('failed');print(err,flush=True);raise
    else: budget.finish()