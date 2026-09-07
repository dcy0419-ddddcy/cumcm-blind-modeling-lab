"""Source adaptation only; no worker or optical evaluation is run here."""
from pathlib import Path
P=Path(__file__).resolve().parent
s=(P/'q02_repair_parallel_v001.py').read_text(encoding='utf-8-sig')
s=s[:s.index('\ndef run_test(')]
s=s.replace('q02_repair_common_v001','q03_common_v001').replace('q02_repair_engine_v001','q03_engine_v001').replace('q02_fast_v002','q03_fast_v001').replace('q02_repair_parallel_v001','q03_parallel_v001')
s=s.replace("VERSION = 'q02-repair-parallel-v001'","VERSION = 'q03-parallel-v001'")
a=s.index('DEPENDENCY_NAMES = ');b=s.index('\ndef _source_hashes',a)
s=s[:a]+"DEPENDENCY_NAMES = ('q03_engine_v001.py','q03_fast_v001.py','q03_common_v001.py','q03_design_v001.py','q03_summary_v001.py','q01_core_v003.py','q02_eval_v003.py','q02_design_v002.py','q03_parallel_v001.py')\n"+s[b:]
s=s.replace("cap = 2400. if budget.phase == 'search' else 3600.","cap = budget.cap()")
s=s.replace("des, _ = eng.compact.read_compact(bundle, bundle_sha)","if io.sha(bundle)!=bundle_sha: raise RuntimeError('DESIGN_FILE_CHANGED')\n        des = eng.design_module.read_design(bundle)")
s=s.replace('abnormal=[]; event_arrays={}','abnormal=[]; event_arrays={}; certificates=[]')
needle="        if r['abnormal_paths']:\n            abnormal.append({'i':i,'id':frozen.mirror_ids[i],'paths':r['abnormal_paths']})"
insert=needle+'''
        pooled=r['counts'][-1].sum(0)
        if pooled[2]==0 or pooled[3]==0:
            cert=eng.f.reference.certify_zero(eng.f.as_reference(sc),i)
            if cert['kind']!='unproven':
                certificates.append({'time_index':local_t,'mirror_index':i,'scene_sha256':sc.key,
                    'source':{'name':'q02_eval_v003.py','sha256':io.sha(HERE/'q02_eval_v003.py')},'certificate':cert})
'''
assert needle in s;s=s.replace(needle,insert)
s=s.replace("'abnormal_paths':abnormal,'combinations':N", "'abnormal_paths':abnormal,'certificate_records':certificates,'combinations':N")
s=s.replace("    return arrays\n\n\ndef evaluate_parallel", """    records=[io.load(folder/('time-%02d.json'%ti))for ti in range(len(times))]
    arrays['certificate_records']=[c for r in records for c in r.get('certificate_records',[])]
    arrays['scene_keys']=[r['scene_key']for r in records]
    arrays['trusted_certificate_sources']={'q02_eval_v003.py':io.sha(HERE/'q02_eval_v003.py')}
    return arrays


def evaluate_parallel""")
s=s.replace('root_seed=2026090505','root_seed=2026090506')
s=s.replace("    if workers != 4:raise ValueError('FROZEN_WORKER_COUNT_MUST_BE_FOUR')", "    if workers not in (1,4):raise ValueError('REGISTERED_WORKER_COUNTS_1_OR_4')")
s=s.replace("    if root_seed != 2026090505:raise ValueError('ROOT_SEED_DIFFERS_FROM_BOUND_ENGINE')", "    if root_seed != 2026090506:raise ValueError('ROOT_SEED_DIFFERS_FROM_BOUND_ENGINE')")
s=s.replace("bundle=base/'design.bundle.json'","bundle=base/'design.json'")
s=s.replace("'compact_bundle_sha256':bundle_sha", "'design_file_sha256':bundle_sha")
s=s.replace("'compact_sha':io.sha(HERE/'q02_compact_v001.py')", "'design_schema_sha':io.sha(HERE/'q03_design_v001.py')")
# Validate recovered area arrays against the exact bound design, not only totals.
s=s.replace("            for k in arrays:arrays[k].append(x[k].copy())", "            if not np.array_equal(x['areas'],frozen.areas): raise RuntimeError('CHECKPOINT_AREA_PROFILE_DIFFERS')\n            for k in arrays:arrays[k].append(x[k].copy())")
target=P/'q03_parallel_v001.py'
if target.exists():raise RuntimeError('new source already exists')
target.write_text(s,encoding='utf-8')
