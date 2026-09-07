"""Time-block parallel adapter; unchanged repair engine/fast kernel and RNG identities.

No numerical imports or computation before a parent's Budget is active. Workers
never create or update Budget. Use evaluate_parallel from a spawn-safe parent;
this file's only CLI action is a budgeted, small same-ray scheduling test.
"""
from __future__ import annotations
import time
START = time.perf_counter()
CPU_START = time.process_time()
from pathlib import Path
import sys, os, json, traceback, multiprocessing as mp
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import q03_common_v001 as io
VERSION = 'q03-parallel-v001'
_W = {}
DEPENDENCY_NAMES = ('q03_engine_v001.py','q03_fast_v001.py','q03_common_v001.py','q03_design_v001.py','q03_summary_v001.py','q01_core_v003.py','q02_eval_v003.py','q02_design_v002.py','q03_parallel_v001.py')

def _source_hashes():
    return {name:io.sha(HERE/name) for name in DEPENDENCY_NAMES}

def _check_sources(expected):
    for name,digest in expected.items():
        if name not in DEPENDENCY_NAMES or io.sha(HERE/name)!=digest:
            raise RuntimeError('WORKER_SOURCE_BINDING_CHANGED: '+name)


def _inside(path):
    p = Path(path).resolve()
    if not p.is_relative_to(io.ROOT.resolve()):
        raise RuntimeError('OUTSIDE_AUTHORIZED_ROOT')
    return p


def _deadline(budget, reserve_after):
    cap = budget.cap()
    left = cap - budget.used() - float(reserve_after)
    if left <= 2:
        raise RuntimeError('INSUFFICIENT_PHASE_BUDGET_FOR_PARALLEL_START')
    return time.perf_counter() + left


def _guard(deadline, reserve=0.):
    if time.perf_counter() + reserve >= deadline:
        raise RuntimeError('PARALLEL_ABSOLUTE_DEADLINE; partial chunks retained')


def _initializer(bundle, bundle_sha, expected_key, deadline, audit, source_hashes):
    """Exactly one detached, fully validated design per worker process."""
    global _W
    _W = {'error': None, 'deadline': deadline, 'audit': audit}
    try:
        _guard(deadline)
        _check_sources(source_hashes)
        import q03_engine_v001 as eng
        _check_sources(source_hashes)
        if io.sha(bundle)!=bundle_sha: raise RuntimeError('DESIGN_FILE_CHANGED')
        des = eng.design_module.read_design(bundle)
        frozen = eng.f.freeze_design(des)
        if frozen.key != expected_key:
            raise RuntimeError('WORKER_FROZEN_DESIGN_KEY_MISMATCH')
        _guard(deadline)
        _W.update(eng=eng, frozen=frozen)
    except BaseException:
        _W['error'] = traceback.format_exc()
    finally:
        io.save(Path(audit) / ('init-%s.json' % os.getpid()),
                {'pid': os.getpid(), 'initializer_cpu_seconds': time.process_time()-CPU_START,
                 'error': _W['error'], 'source_hashes': source_hashes, 'cpu_scope': 'since this spawned module import; interpreter bootstrap excluded'})


def _compute_time(eng, frozen, job, deadline):
    """Original evaluate's single-time loop; only deadline and I/O orchestration differ."""
    import numpy as np
    _guard(deadline)
    folder = Path(job['folder']); local_t = job['local_t']
    month, hour = job['time']; B, n = job['B'], job['n']; levels = job['levels']
    indices = list(range(frozen.n)) if job.get('indices') is None else job['indices']
    L, N = len(levels), len(indices)
    t = time.perf_counter(); sc = eng.f.scene_at(frozen, month, hour)
    prep = time.perf_counter()-t; _guard(deadline)
    sums = np.zeros((L,B,N,3)); cross = np.zeros((L,B,N,3,3))
    counts = np.zeros((L,B,N,6),np.int64); uw = np.zeros((L,B,N)); known = np.zeros((L,B,N))
    cand = np.zeros((N,2),np.int64); abnormal=[]; event_arrays={}; certificates=[]
    time_index = eng.TIMES.index((month,hour)); t=time.perf_counter()
    for j,i in enumerate(indices):
        _guard(deadline, .1)
        key = frozen.position_keys[i]
        seeds = [eng.f.reference.seed_words(job['root_seed'],job['namespace'],time_index,key,b) for b in range(B)]
        r = eng.f.sample_stats(sc,i,seeds,n,levels)
        sums[:,:,j]=r['sums']; cross[:,:,j]=r['cross']; counts[:,:,j]=r['counts']
        uw[:,:,j]=r['unknown_weights']; known[:,:,j]=r['known_capture_weights']; cand[j]=r['candidate_counts']
        if r['abnormal_paths']:
            abnormal.append({'i':i,'id':frozen.mirror_ids[i],'paths':r['abnormal_paths']})
        pooled=r['counts'][-1].sum(0)
        if pooled[2]==0 or pooled[3]==0:
            cert=eng.f.reference.certify_zero(eng.f.as_reference(sc),i)
            if cert['kind']!='unproven':
                certificates.append({'time_index':local_t,'mirror_index':i,'scene_sha256':sc.key,
                    'source':{'name':'q02_eval_v003.py','sha256':io.sha(HERE/'q02_eval_v003.py')},'certificate':cert})

        if job.get('events'):
            # Exact replay of already used source streams, no new independent rays.
            oo=[]; ss=[]
            for words in seeds:
                o,s=eng.f.c.random_rays(sc.mirrors,i,sc.s0,sc.beta,n,words);oo.append(o);ss.append(s)
            o=np.concatenate(oo);s=np.concatenate(ss);g,ev=eng.f.trace_same(sc,i,o,s)
            event_arrays['source_%d_o'%i]=o; event_arrays['source_%d_s'%i]=s
            event_arrays['source_%d_g'%i]=g
            for key in eng.f.EVENT_KEYS:event_arrays['event_%d_%s'%(i,key)]=np.asarray(ev[key])
    integral=time.perf_counter()-t; _guard(deadline);t=time.perf_counter()
    target=folder/('time-%02d.npz'%local_t)
    eng.save_npz(target,sums=sums,cross=cross,counts=counts,unknown_weights=uw,
                 known_capture_weights=known,cosine=sc.cosine[indices],tau=sc.tau[indices],
                 dni=np.array(sc.dni),areas=frozen.areas[indices],candidate_counts=cand,**event_arrays)
    _guard(deadline)
    record={'month':month,'hour':hour,'scene_key':sc.key,'design_key':frozen.key,
            'sha256':io.sha(target),'prepare_seconds':prep,'integral_seconds':integral,
            'save_seconds_before_metadata':time.perf_counter()-t,
            'candidate_mean':cand.mean(0),'candidate_max':cand.max(0),
            'abnormal_paths':abnormal,'certificate_records':certificates,'combinations':N,'unique_source_samples':B*n*N}
    io.save(target.with_suffix('.json'),record)
    return io.convert(record)


def _worker(job):
    started=time.perf_counter(); cpu=time.process_time(); record=None; error=None
    try:
        if _W['error']:raise RuntimeError('WORKER_INITIALIZER_FAILURE: '+_W['error'])
        record=_compute_time(_W['eng'],_W['frozen'],job,_W['deadline'])
        return record
    except BaseException:
        error=traceback.format_exc(); raise
    finally:
        io.save(Path(_W['audit'])/('job-%02d.json'%job['local_t']),
                {'pid':os.getpid(),'local_time_index':job['local_t'],
                 'standard_time':job['time'],'worker_cpu_seconds':time.process_time()-cpu,
                 'worker_cpu_cumulative_seconds':time.process_time()-CPU_START,
                 'worker_wall_seconds':time.perf_counter()-started,'completed':record is not None,
                 'error':error})


def _pool_jobs(jobs,bundle,bundle_sha,key,deadline,audit,budget,workers,on_result=None,source_hashes=None):
    """Parent hard deadline terminates in-flight workers; no detached computation."""
    source_hashes=_source_hashes() if source_hashes is None else source_hashes
    audit=Path(audit);audit.mkdir(parents=True,exist_ok=False)
    receipt={'version':VERSION,'workers':workers,'started':io.now(),
             'absolute_perf_counter_deadline':deadline,'remaining_seconds_at_dispatch':deadline-time.perf_counter(),
             'accounting':'parent whole-job wall time only; worker CPU is separate audit, never added to wall ledger',
             'complete':False,'completed_local_indices':[],'worker_source_sha256':source_hashes,
             'deadline_scope':'parent checks and terminates; OS shutdown is measured and is not a hard real-time guarantee'}
    io.save(audit/'run.json',receipt)
    start=time.perf_counter();parent_cpu=time.process_time();pool=None;result={}
    try:
        _guard(deadline,2)
        pool=mp.get_context('spawn').Pool(workers,initializer=_initializer,
              initargs=(str(bundle),bundle_sha,key,deadline,str(audit),source_hashes))
        pending={j['local_t']:pool.apply_async(_worker,(j,)) for j in jobs}
        pool.close()
        while pending:
            _guard(deadline)
            ready=[i for i,r in pending.items() if r.ready()]
            for i in ready:
                record=pending.pop(i).get();result[i]=record
                receipt['completed_local_indices'].append(i)
                if on_result:on_result(i,record)
                budget.tick()
            if pending:time.sleep(min(.1,max(.001,deadline-time.perf_counter())))
        # Pool.join has no timeout. Wait for worker exit with a deadline first;
        # its bookkeeping threads may then be joined after all children stopped.
        while any(p.is_alive() for p in pool._pool):
            _guard(deadline)
            time.sleep(min(.05,max(.001,deadline-time.perf_counter())))
        pool.join();pool=None;receipt['complete']=True
        return result
    except BaseException:
        receipt['error']=traceback.format_exc();raise
    finally:
        if pool is not None:
            pool.terminate();pool.join()
        # Summation is CPU only: each initializer once, each completed/error job once.
        init=[io.load(p) for p in audit.glob('init-*.json')]
        tasks=[io.load(p) for p in audit.glob('job-*.json')]
        receipt.update(finished=io.now(),parent_elapsed_seconds=time.perf_counter()-start,
                       parent_cpu_seconds=time.process_time()-parent_cpu,
                       initializer_cpu_seconds=sum(x['initializer_cpu_seconds'] for x in init),
                       task_cpu_seconds=sum(x['worker_cpu_seconds'] for x in tasks),
                       workers_initialized=len(init),task_receipts=len(tasks),
                       terminated_unfinished_worker_cpu_may_be_unavailable=not receipt['complete'],
                       worker_receipts=tasks,initializer_receipts=init)
        receipt['worker_cpu_seconds_total']=receipt['initializer_cpu_seconds']+receipt['task_cpu_seconds']
        by_pid={str(x['pid']):x['initializer_cpu_seconds'] for x in init}
        for x in tasks:
            pid=str(x['pid']);by_pid[pid]=max(by_pid.get(pid,0.),x['worker_cpu_cumulative_seconds'])
        receipt['worker_cpu_cumulative_by_pid']=by_pid
        receipt['worker_cpu_cumulative_sum']=sum(by_pid.values())
        receipt['cpu_scope']='measured CPU lower bound: cumulative maxima through last saved task; interpreter bootstrap, last receipt and shutdown may be excluded; never added to wall ledger'
        io.save(audit/'run.json',receipt);budget.tick()


def _rebuild(eng,frozen,folder,times,levels,budget):
    import numpy as np
    arrays={k:[] for k in ['sums','counts','unknown_weights','cosine','tau','dni']}
    for ti in range(len(times)):
        budget.guard(12)
        with np.load(folder/('time-%02d.npz'%ti),allow_pickle=False) as x:
            if not np.array_equal(x['areas'],frozen.areas): raise RuntimeError('CHECKPOINT_AREA_PROFILE_DIFFERS')
            for k in arrays:arrays[k].append(x[k].copy())
    budget.guard(15)
    for k in ['sums','counts','unknown_weights']:arrays[k]=np.stack(arrays[k],axis=2)
    for k in ['cosine','tau','dni']:arrays[k]=np.stack(arrays[k],axis=0)
    arrays.update(areas=np.asarray(frozen.areas),levels_n=levels,
                  months=[m for m,h in times],hours=[h for m,h in times],object_ids=list(frozen.mirror_ids))
    records=[io.load(folder/('time-%02d.json'%ti))for ti in range(len(times))]
    arrays['certificate_records']=[c for r in records for c in r.get('certificate_records',[])]
    arrays['scene_keys']=[r['scene_key']for r in records]
    arrays['trusted_certificate_sources']={'q02_eval_v003.py':io.sha(HERE/'q02_eval_v003.py')}
    return arrays


def evaluate_parallel(frozen,folder,tag,times,B,n,levels,namespace,budget,*,root_seed=2026090506,workers=4,reserve_after=90):
    """Drop-in evaluate return; parent owns Budget and later full confirmation summary."""
    import q03_engine_v001 as eng
    if workers not in (1,4):raise ValueError('REGISTERED_WORKER_COUNTS_1_OR_4')
    if root_seed != 2026090506:raise ValueError('ROOT_SEED_DIFFERS_FROM_BOUND_ENGINE')
    times=[tuple(t) for t in times]
    if len(set(times))!=len(times) or any(t not in eng.TIMES for t in times):raise ValueError('INVALID_TIME_GRID')
    base=_inside(folder); dest=_inside(base/tag);dest.mkdir(parents=True,exist_ok=True)
    bundle=base/'design.json';bundle_sha=io.sha(bundle);source_hashes=_source_hashes()
    binding={'design_key':frozen.key,'name':frozen.name,'n_mirrors':frozen.n,'times':times,
             'B':B,'n':n,'levels':levels,'namespace':namespace,'root_seed':root_seed,
             'rng':'numpy.PCG64 via SeedSequence; per stable position_key, standard time index, namespace, batch',
             'code_sha':io.sha(HERE/'q03_engine_v001.py'),'fast_sha':io.sha(HERE/'q03_fast_v001.py'),
             'scheduler_sha':io.sha(Path(__file__)),'scheduler_version':VERSION,'worker_dependency_sha256':source_hashes,
             'workers':workers,'task_unit':'one complete standard time; all mirrors and all obstacles',
             'design_file_sha256':bundle_sha,'budget_accounting':'parent wall time once; child CPU audit separately',
             'deadline_rule':'parent phase cap minus saved cumulative use minus reserve_after; terminate unfinished processes',
             'reserve_after_seconds':reserve_after,'common_sha':io.sha(HERE/'q03_common_v001.py'),
             'design_schema_sha':io.sha(HERE/'q03_design_v001.py')}
    bp=dest/'binding.json'
    if bp.exists():
        if io.load(bp)!=io.convert(binding):raise RuntimeError('CHECKPOINT_BINDING_MISMATCH')
    else:io.save(bp,binding)
    records={};jobs=[]
    for ti,(m,h) in enumerate(times):
        p=dest/('time-%02d.npz'%ti);meta=p.with_suffix('.json')
        if p.exists() and meta.exists():
            r=io.load(meta)
            if r['sha256']!=io.sha(p):raise RuntimeError('CHECKPOINT_HASH_FAILURE')
            if (r['month'],r['hour'],r['design_key'],r['combinations'],r['unique_source_samples'])!=(m,h,frozen.key,frozen.n,B*n*frozen.n):
                raise RuntimeError('CHECKPOINT_RECORD_BINDING_MISMATCH')
            records[ti]=r
        else:jobs.append({'folder':str(dest),'local_t':ti,'time':(m,h),'B':B,'n':n,
                          'levels':levels,'namespace':namespace,'root_seed':root_seed})
    def checkpoint(i=None,r=None):
        if i is not None:records[i]=r
        ordered=[records[k] for k in sorted(records)]
        io.save(dest/'checkpoint.json',{'completed_times':len(records),'expected_times':len(times),
                 'records':ordered,'complete':len(records)==len(times)})
        if i is not None:print(json.dumps({'name':frozen.name,'tag':tag,'time_done':len(records),
                                           'times':len(times),'used_seconds':budget.used()},ensure_ascii=False),flush=True)
    checkpoint()
    if jobs:
        deadline=_deadline(budget,reserve_after)
        audit=dest/'parallel-audit'/('run-%s'%time.time_ns())
        _pool_jobs(jobs,bundle,bundle_sha,frozen.key,deadline,audit,budget,workers,checkpoint,source_hashes)
    return _rebuild(eng,frozen,dest,times,levels,budget),[records[i] for i in range(len(times))]

