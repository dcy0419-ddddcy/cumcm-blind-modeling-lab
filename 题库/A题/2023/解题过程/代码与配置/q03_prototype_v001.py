"""Bounded Q3 prototype. Call run(parent_budget); never starts its own budget.

The only scored field fixtures are two heterogeneous expansions of fixed R027.
All ray identities are registered before tracing. Synthetic zero fixtures exercise
the real time runner, disk rebuild and certificate-aware summary in isolation.
"""
from __future__ import annotations
from pathlib import Path
import copy
import hashlib
import json
import time
import traceback
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VERSION = 'q03-prototype-v001'
ROOT_SEED = 2026090506
LOW_REFERENCES = ((52, 77, 176473955952466), (57, 144, 174303916202366))


def _must_reject(fn, text=None):
    try:
        fn()
    except Exception as exc:
        if text and text not in str(exc):
            raise AssertionError('wrong rejection: ' + str(exc)) from exc
        return str(exc)
    raise AssertionError('required rejection did not occur')


def run(budget):
    """Return JSON-safe evidence; fail closed and retain each attempt separately."""
    import numpy as np
    import q03_common_v001 as io
    import q03_design_v001 as design
    import q03_fast_v001 as f
    import q02_fast_v002 as old
    import q02_compact_v001 as compact
    import q03_engine_v001 as eng
    import q03_parallel_v001 as parallel
    import q03_summary_v001 as summary
    started = time.perf_counter()
    budget.guard(30)
    out = io.OUT / 'prototype' / ('attempt-%s' % time.time_ns())
    out.mkdir(parents=True, exist_ok=False)
    result = {'version': VERSION, 'all_pass': False, 'artifact_folder': str(out),
              'checks': [], 'started': io.now(), 'new_design_combinations_completed': 0,
              'compatibility_combinations_completed': 0,
              'unique_field_source_samples': 0,
              'limitations': ['bounded interface validation, not a full-year design evaluation',
                              'synthetic zero fixtures are not feasible competition layouts',
                              'checkpoint rejection below validates the actual binding entry path; no worker is spawned']}
    dependency_names = (*parallel.DEPENDENCY_NAMES, 'q02_fast_v002.py',
                        'q02_compact_v001.py', Path(__file__).name)
    source_sha = {p: io.sha(HERE / p) for p in dependency_names}
    io.save(out / 'source-binding.json', source_sha)

    def record(name, details):
        result['checks'].append({'name': name, 'passed': True, 'details': details})
        io.save(out / 'progress.json', result)
        budget.tick()

    def deadline():
        budget.guard(20)
        return time.perf_counter() + max(0., budget.cap() - budget.used() - 15.)

    try:
        base_payload = design.from_r027()
        base = f.freeze_design(base_payload)
        old_path = io.ROOT / '工作记录/诊断结果/Q02-修复-v001/frozen/design.bundle.json'
        old_design, old_receipt = compact.read_compact(old_path)
        previous = old.freeze_design(old_design)
        assert base.n == previous.n and base.mirror_ids == previous.mirror_ids
        assert base.position_keys == previous.position_keys
        assert np.array_equal(base.centers, previous.centers)
        assert np.array_equal(base.areas, previous.areas)
        for ti, i, mid in LOW_REFERENCES:
            assert base.mirror_ids[i] == mid, 'historical low-survival index changed'
        grouped, grouping = design.group_baseline(base_payload, radial_bins=3, angular_bins=2)
        groups = grouping['nonempty_groups']
        assert len(groups) >= 2
        # Both changes only shrink width/height and lower installation height.
        # Deliberately modify all groups: selected rays necessarily use new dimensions.
        specs = [
            {g: {'width': 6.60 if g % 2 == 0 else 6.55,
                 'height': 6.40 if g % 2 == 0 else 6.35,
                 'z': 5.75 if g % 2 == 0 else 5.50} for g in groups},
            {g: {'width': 6.55 if g % 2 == 0 else 6.60,
                 'height': 6.30 if g % 2 == 0 else 6.45,
                 'z': 5.25 if g % 2 == 0 else 5.80} for g in groups},
        ]
        designs = [design.apply_groups(grouped, changes, 'Q03-prototype-%s' % chr(65+k))
                   for k, changes in enumerate(specs)]
        frozen = [f.freeze_design(d) for d in designs]
        # One deterministic full geometry scan at a fixed time; no rays or optical scores.
        pressure_scene = f.scene_at(base, 1, 9.)
        max_i, max_count = 0, -1
        for i in range(base.n):
            if i % 128 == 0:
                budget.guard(20)
            pair = f.candidate_pair(pressure_scene, i)
            count = len(pair.incoming) + len(pair.outgoing)
            if count > max_count:
                max_i, max_count = i, count
        compatibility = [(0, max_i), (52, 77), (57, 144), (59, base.n-1), (30, 0), (29, base.n//2)]
        assert len(set(compatibility)) == 6
        combinations = [(0, max_i), (52, 77), (57, 144)]
        planned = {'version': VERSION, 'created_before_any_rays': io.now(),
                   'root_seed': ROOT_SEED, 'source_sha256': source_sha,
                   'old_bundle_sha256': io.sha(old_path), 'base_key': base.key,
                   'selection': {'pressure_time': [1, 9.], 'max_candidate_index': max_i,
                                 'max_candidate_count_sum': max_count,
                                 'tie_rule': 'smallest original index',
                                 'historical_low_references': LOW_REFERENCES,
                                 'historical_source': 'Q02-修复-v001/frozen/confirmation/summary.json'},
                   'compatibility': [], 'heterogeneous': [],
                   'synthetic_contract_scope': 'cache-only three-mirror subset has no rays; two under-tower zero fixtures have 2x256 each and are not competition designs',
                   'synthetic_zero_streams': [{'namespace': 3090+k, 'time_index': 0,
                                               'position_key': 'synthetic-zero', 'B': 2, 'n': 256}
                                              for k in range(2)],
                   'complete_obstacle_population': base.n,
                   'limits': {'old_compatibility_combinations': 6,
                              'new_field_designs': 2, 'new_field_combinations': 6,
                              'new_field_batches': 2, 'new_field_samples_per_batch': 256},
                   'replay_rule': 'screen/all and old/new traces reuse the registered source arrays; sample_stats replays the same seed words'}
        for ti, i in compatibility:
            planned['compatibility'].append({'time_index': ti, 'time': eng.TIMES[ti],
                'mirror_index': i, 'mirror_id': base.mirror_ids[i], 'position_key': base.position_keys[i],
                'namespace': 3000, 'B': 2, 'n': 64,
                'seed_words': [f.reference.seed_words(ROOT_SEED,3000,ti,base.position_keys[i],b) for b in range(2)]})
        for k, fd in enumerate(frozen):
            rows=[]
            for ti, i in combinations:
                rows.append({'time_index': ti, 'time': eng.TIMES[ti], 'mirror_index': i,
                             'mirror_id': fd.mirror_ids[i], 'position_key': fd.position_keys[i],
                             'namespace': 3010+k, 'B': 2, 'n': 256,
                             'seed_words': [f.reference.seed_words(ROOT_SEED,3010+k,ti,fd.position_keys[i],b) for b in range(2)]})
            planned['heterogeneous'].append({'name': fd.name, 'key': fd.key,
                                            'group_changes': specs[k], 'combinations': rows})
        io.save(out / 'preregistration.json', planned)
        result['preregistration'] = str(out / 'preregistration.json')
        record('P01_identity_and_preregistration', {'n': base.n, 'max_candidate_index': max_i,
               'new_combinations_registered': 6, 'old_compact_receipt': old_receipt})

        # Roundtrip checks every scalar, identity, ordered row and metadata field.
        for k, fd in enumerate(frozen):
            budget.guard(20)
            folder=out / ('heterogeneous-%d' % k); folder.mkdir()
            receipt=design.save_design(designs[k], folder/'design.json')
            loaded=design.read_design(folder/'design.json'); rebuilt=f.freeze_design(loaded)
            assert loaded == designs[k] and rebuilt.key == fd.key
            assert np.array_equal(rebuilt.areas,fd.areas) and rebuilt.total_area == fd.total_area
            mapping=[{'export_index':i+1,'mirror_id':r['mirror_id'],'position_key':r['position_key']}
                     for i,r in enumerate(loaded['mirrors'])]
            io.save(folder/'identity-map.json',mapping)
            io.save(folder/'geometry.json',fd.validation)
            record('P02_roundtrip_%d'%k, {'receipt':receipt,'complete_fields_equal':True,
                   'ordered_identity_equal':True,'total_area_m2':fd.total_area})

        def trace_comparison(sc, entry, folder, other=None):
            budget.guard(20)
            i=entry['mirror_index']; n=entry['n']; seeds=entry['seed_words']
            sources=[f.c.random_rays(sc.mirrors,i,sc.s0,sc.beta,n,words) for words in seeds]
            o=np.concatenate([x[0]for x in sources]); s=np.concatenate([x[1]for x in sources])
            g,ev=f.trace_same(sc,i,o,s)
            gx,ex=f.trace_same(sc,i,o,s,screen=False)
            comparisons={'screen_all_weights_equal':bool(np.array_equal(g,gx)),
                         'screen_all_events_equal':{key:bool(np.array_equal(ev[key],ex[key]))for key in f.EVENT_KEYS}}
            assert comparisons['screen_all_weights_equal'] and all(comparisons['screen_all_events_equal'].values())
            if other is not None:
                go,eo=old.trace_same(other,i,o,s)
                comparisons['old_new_weights_equal']=bool(np.array_equal(go,g))
                comparisons['old_new_events_equal']={key:bool(np.array_equal(eo[key],ev[key]))for key in f.EVENT_KEYS}
                assert comparisons['old_new_weights_equal'] and all(comparisons['old_new_events_equal'].values())
                a=f.reference.stats(g,ev); b=f.reference.stats(go,eo)
                assert np.array_equal(a['sums'],b['sums']) and np.array_equal(a['cross'],b['cross'])
                assert a['counts']==b['counts']
                pa=sc.dni*sc.areas[i]*f.RHO*sc.cosine[i]*sc.tau[i]*a['sums'][2]/a['sums'][0]
                pb=other.dni*other.areas[i]*old.RHO*other.cosine[i]*other.tau[i]*b['sums'][2]/b['sums'][0]
                assert pa == pb
                comparisons.update(statistics_exactly_equal=True,pooled_power_estimate_kw=float(pa),
                                   old_new_power_exactly_equal=True,
                                   power_scope='same-ray pooled estimator; no formal zero/status or rating conclusion')
            else:
                stats=f.sample_stats(sc,i,seeds,n,[128,256])
                for b in range(2):
                    sl=slice(b*n,(b+1)*n)
                    sliced={key:ev[key][sl]for key in f.EVENT_KEYS}
                    sliced.update(scene_sha256=sc.key,mirror_index=i)
                    manual=f.reference.stats(g[sl],sliced)
                    actual=f.batch_as_reference(stats,1,b)
                    assert np.allclose(manual['sums'],actual['sums'],rtol=0,atol=1e-11)
                    assert np.allclose(manual['cross'],actual['cross'],rtol=0,atol=1e-10)
                    assert manual['counts']==actual['counts']
                comparisons['sample_stats_manual_batch_match']=True
                eng.save_npz(folder.with_name(folder.stem+'-stats.npz'),**{
                    key:stats[key]for key in ['sums','cross','counts','unknown_weights','known_capture_weights']})
            eng.save_npz(folder,o=o,s=s,g=g,**{key:ev[key]for key in f.EVENT_KEYS})
            comparisons.update(source_samples=len(o),source_npz_sha256=io.sha(folder),
                               full_obstacles=sc.n,scene_key=sc.key,
                               candidate_counts=[len(f.candidate_pair(sc,i).incoming),len(f.candidate_pair(sc,i).outgoing)])
            result['unique_field_source_samples'] += len(o)
            return comparisons

        for j, entry in enumerate(planned['compatibility']):
            sc=f.scene_at(base,*entry['time']); other=old.scene_at(previous,*entry['time'])
            for key in ('centers','normals','u','v','widths','heights','vertical'):
                assert np.array_equal(getattr(sc.mirrors,key),getattr(other.mirrors,key)),key
            assert np.array_equal(sc.tau,other.tau) and sc.dni==other.dni
            details=trace_comparison(sc,entry,out/('compatibility-%d.npz'%j),other)
            result['compatibility_combinations_completed']+=1
            record('P03_old_new_%d'%j,details)

        for k, fd in enumerate(frozen):
            for j, entry in enumerate(planned['heterogeneous'][k]['combinations']):
                sc=f.scene_at(fd,*entry['time']); i=entry['mirror_index']; row=designs[k]['mirrors'][i]
                assert sc.mirrors.widths[i]==row['width'] and sc.mirrors.heights[i]==row['height']
                assert sc.mirrors.centers[i,2]==row['z'] and sc.areas[i]==row['area']
                assert np.isclose(sc.mirrors.radii[i],np.hypot(row['width'],row['height'])/2,rtol=0,atol=1e-14)
                old_sc=f.scene_at(base,*entry['time'])
                assert not np.array_equal(sc.target[i],old_sc.target[i])
                assert sc.tau[i]!=old_sc.tau[i] and not np.array_equal(sc.mirrors.normals[i],old_sc.mirrors.normals[i])
                details=trace_comparison(sc,entry,out/('heterogeneous-%d'%k)/('combo-%d.npz'%j))
                details.update(width=row['width'],height=row['height'],z=row['z'],area=row['area'],
                               target_normal_tau_changed=True)
                result['new_design_combinations_completed']+=1
                assert result['new_design_combinations_completed']<=18
                record('P04_heterogeneous_%d_%d'%(k,j),details)

        # Cache-only contract fixture: no sampling and no optical trace occurs here.
        small=copy.deepcopy(base_payload);small['name']='artificial-cache-contract';small['mirrors']=small['mirrors'][:3]
        for row in small['mirrors']:
            row.update(width=6.,height=4.,z=5.,area=24.)
        fd=f.freeze_design(small);sc=f.scene_at(fd,1,9.);pair=f.candidate_pair(sc,0)
        original_key=fd.key; snapshot=fd.centers.copy();small['mirrors'][0]['z']=4.75
        assert fd.key==original_key and np.array_equal(fd.centers,snapshot)
        detached=fd.to_design();detached['mirrors'][0]['width']=2.
        assert fd.widths[0]==6.
        arrays=[fd.widths,fd.heights,fd.installation_heights,fd.centers,fd.groups,fd.areas,
                sc.s0,sc.target,sc.tau,sc.cosine,sc.mirrors.normals,sc.mirrors.u,sc.mirrors.v,sc.mirrors.radii]
        for array in arrays:_must_reject(lambda a=array:a.setflags(write=True))
        rejected=[]
        for label in ('width','height','z','order','group_expansion','beta','tolerance'):
            variant=fd.to_design()
            if label in ('width','height','z'):
                variant['mirrors'][0][label]-=.25
                for r in variant['mirrors']:r['area']=r['width']*r['height']
            elif label=='order':variant['mirrors'].reverse()
            elif label=='group_expansion':
                variant=design.apply_groups(variant,{0:{'height':3.5}},'artificial-cache-expanded')
            vf=f.freeze_design(variant)
            other=f.scene_at(vf,1,9.,beta=f.BETA*.9 if label=='beta' else f.BETA,
                            tolerance=f.c.Tolerance(factor=512) if label=='tolerance' else None)
            rejected.append({'changed':label,'message':_must_reject(lambda:f._checked_pair(other,0,pair),'CACHE_INVALID')})
        group_only=fd.to_design();group_only['mirrors'][0]['group']=1
        assert f.freeze_design(group_only).key!=fd.key
        # Test checkpoint binding rejection before dispatch using the actual runner.
        checkpoint=out/'checkpoint-contract';checkpoint.mkdir()
        design.save_design(fd.to_design(),checkpoint/'design.json')
        io.save(checkpoint/'probe'/'binding.json',{'design_key':'incompatible-artificial-checkpoint'})
        message=_must_reject(lambda:parallel.evaluate_parallel(fd,checkpoint,'probe',[(1,9.)],2,256,[128,256],3080,budget,workers=1),
                             'CHECKPOINT_BINDING_MISMATCH')
        record('P05_immutable_cache_checkpoint',{'immutable_arrays':len(arrays),'cache_rejections':rejected,
               'group_only_frozen_identity_changed':True,'checkpoint_rejection':message,'new_rays':0})

        # Isolated engine facade keeps the complete production certificate pipeline.
        # These analytic under-tower scenes are deliberately outside field constraints.
        for k,sun in enumerate(([0.,0.,1.],[.6,0.,.8])):
            sun=np.asarray(sun); centers=np.asarray([[0.,0.,4.]])
            receiver=f.c.Cylinder(); target=f.c.unit(np.asarray(receiver.center)-centers)
            raw=f.c.make_mirrors(centers,f.c.unit(target+sun),2.,2.)
            domain=f.c.check_domain(raw,sun,f.BETA,receiver,target)
            mirrors=f.FrozenMirrors(*(f._immutable_array(getattr(raw,key))for key in
                 ('centers','normals','u','v','widths','heights','vertical')),f._immutable_array(raw.radii))
            mock=SimpleNamespace(n=1,mirror_ids=(1,),position_keys=('synthetic-zero',),
                                 areas=f._immutable_array([4.]),total_area=4.,key='synthetic-zero-%d'%k)
            tag={'scope':'artificial_under_tower_certificate_pipeline','ids':[1]}
            ref=f.reference.Scene(mirrors,sun,target,receiver,1.,np.ones(1),tag=tag,domain=domain)
            artificial=f.PreparedScene(mock,mirrors,f._immutable_array(sun),f._immutable_array(target),receiver,
                         1.,f._immutable_array([1.]),f._immutable_array(raw.normals@sun),f.BETA,ref.tol,ref.key,
                         1,9.,f._json(tag),f._json(domain))
            api=SimpleNamespace(scene_at=lambda _fd,_m,_h,sc=artificial:sc,
                  sample_stats=f.sample_stats,reference=f.reference,as_reference=f.as_reference,
                  c=f.c,trace_same=f.trace_same,EVENT_KEYS=f.EVENT_KEYS)
            engine=SimpleNamespace(f=api,TIMES=eng.TIMES,save_npz=eng.save_npz)
            folder=out/('artificial-zero-%d'%k);folder.mkdir()
            job={'folder':str(folder),'local_t':0,'time':(1,9.),'B':2,'n':256,'levels':[128,256],
                 'root_seed':ROOT_SEED,'namespace':3090+k}
            meta=parallel._compute_time(engine,mock,job,deadline())
            arrays=parallel._rebuild(engine,mock,folder,[(1,9.)],[128,256],budget)
            answer=summary.summarize_search_statistics(**arrays,mode='heuristic')
            io.save(folder/'summary.json',answer)
            assert len(meta['certificate_records'])==1
            cert=meta['certificate_records'][0]['certificate']
            assert cert['kind']==('zero_survivor' if k==0 else 'zero_capture')
            assert bool(np.asarray(answer['pooled_total_defined'])[0,0])
            assert float(np.asarray(answer['temporal_point'])[0,4])==0.
            states=answer['pooled_state_counts']
            assert any(count==1 and key.startswith('TRUE_ZERO') for key,count in states.items())
            stripped={**arrays,'certificate_records':[]}
            no_proof=summary.summarize_search_statistics(**stripped,mode='heuristic')
            assert not bool(np.asarray(no_proof['pooled_total_defined'])[0,0])
            assert any(count==1 and key.startswith('SAMPLED_ZERO') for key,count in no_proof['pooled_state_counts'].items())
            io.save(folder/'same_statistics_without_certificate.json',no_proof)
            record('P06_real_runner_zero_certificate_%d'%k,{'certificate_kind':cert['kind'],
                   'state_counts':states,'with_certificate_zero_defined':True,
                   'without_certificate_sampled_zero_na':True,'source_samples':512,
                   'scope':'artificial only; production _compute_time -> disk -> _rebuild -> summary'})
        assert result['compatibility_combinations_completed']==6
        assert result['new_design_combinations_completed']==6
        for name,digest in source_sha.items():
            assert io.sha(HERE/name)==digest,'source changed during prototype: '+name
        result['all_pass']=True
    except BaseException:
        result['failure']=traceback.format_exc()
        io.save(out/'failure.json',result)
    finally:
        result['finished']=io.now();result['elapsed_seconds']=time.perf_counter()-started
        io.save(out/'result.json',result);budget.tick()
    return io.convert(result)


if __name__ == '__main__':
    raise SystemExit('Use run(parent_budget) from the registered parent; this module does not create a budget.')
