"""Bounded artificial fast-adapter regression; call run_tests under root budget.

No files, layouts from the target search, random streams, or optics are created
on import. All actions below occur only when explicitly called by the budgeted
runner. Timing is descriptive and never used as a correctness gate.
"""
from __future__ import annotations
import copy
import math
import time
import traceback
from dataclasses import FrozenInstanceError
import numpy as np
import q02_fast_v002 as f


def artificial_design():
    d = f.design_module
    points = [(150., 0.), (160., -10.), (160., 10.), (170., 0.)]
    mirrors = [{'mirror_id': i + 1, 'position_key': 'fast-artificial-slot-' + str(i),
                'x': x, 'y': y} for i, (x, y) in enumerate(points)]
    return d.Design('fast-artificial', 'v001', (0., 0.), 8., 6., 4., mirrors,
                    {'scope': 'artificial API regression, no target search', 'nested': [1, 2]})


def _must_reject(call, contains=None):
    try:
        call()
    except Exception as ex:
        if contains is not None and contains not in str(ex):
            raise AssertionError('Wrong rejection: ' + str(ex)) from ex
        return type(ex).__name__ + ': ' + str(ex)
    raise AssertionError('Expected rejection did not occur')


def run_tests(benchmark_repeats=3):
    """Artificial correctness + bounded same-scene timing; caller saves returned JSON."""
    if not isinstance(benchmark_repeats, int) or not 0 <= benchmark_repeats <= 10:
        raise ValueError('benchmark_repeats must be an integer from 0 through 10')
    checks = []
    counters = {'path_evaluations': 0, 'unique_source_samples': 0}
    started = time.perf_counter()

    def check(name, fn):
        t0 = time.perf_counter()
        try:
            evidence = fn()
            checks.append({'name': name, 'passed': True, 'evidence': evidence,
                           'elapsed_seconds': time.perf_counter() - t0})
        except Exception:
            checks.append({'name': name, 'passed': False, 'traceback': traceback.format_exc(),
                           'elapsed_seconds': time.perf_counter() - t0})

    original = artificial_design()
    snapshot = copy.deepcopy(original)
    t0 = time.perf_counter(); frozen = f.freeze_design(original); freeze_seconds = time.perf_counter() - t0
    t0 = time.perf_counter(); scene = f.scene_at(frozen, 12, 9.); prepare_seconds = time.perf_counter() - t0
    old = f.reference.prepare(snapshot, 12, 9.)

    def immutable_snapshot():
        key = frozen.key; scene_key = scene.key; centers = frozen.centers.copy()
        normals = scene.mirrors.normals.copy(); target = scene.target.copy()
        original.width = 2.
        original.tower_xy = (300., 0.)
        original.mirrors[0]['x'] = 349.
        original.metadata['nested'].append(3)
        original.mirrors.reverse()
        assert frozen.key == key and scene.key == scene_key
        assert np.array_equal(frozen.centers, centers) and np.array_equal(scene.mirrors.normals, normals)
        assert np.array_equal(scene.target, target) and frozen.width == 8.
        restored = frozen.to_design(); restored.mirrors[0]['x'] += 9
        assert np.array_equal(frozen.centers, centers)
        arrays = [frozen.centers, frozen.areas, scene.s0, scene.target, scene.tau,
                  scene.cosine, scene.mirrors.centers, scene.mirrors.normals,
                  scene.mirrors.u, scene.mirrors.v, scene.mirrors.widths,
                  scene.mirrors.heights, scene.mirrors.vertical, scene.mirrors.radii]
        rejected = [_must_reject(lambda a=a: a.setflags(write=True)) for a in arrays]
        rejected.append(_must_reject(lambda: setattr(scene, 'beta', .1)))
        rejected.append(_must_reject(lambda: setattr(scene.receiver, 'radius', 100.)))
        ref = f.as_reference(scene)
        ref.mirrors.centers = np.zeros_like(ref.mirrors.centers)
        ref.tag['ids'][0] = -1
        assert np.array_equal(scene.mirrors.centers, centers)
        assert scene.design.mirror_ids[0] == 1
        return {'original_mutation_isolated': True, 'returned_copy_mutation_isolated': True,
                'immutable_array_rejections': len(arrays), 'other_rejections': rejected[-2:],
                'reference_wrapper_isolated': True, 'n': frozen.n, 'area_m2': frozen.total_area}
    check('F01_detached_immutable_snapshot', immutable_snapshot)

    def mapping_and_candidates():
        assert scene.key == old.key
        for name in ('centers', 'normals', 'u', 'v', 'widths', 'heights', 'vertical'):
            assert np.array_equal(getattr(scene.mirrors, name), getattr(old.mirrors, name)), name
        assert np.array_equal(scene.tau, old.tau) and scene.dni == old.dni
        counts = []
        for i in range(scene.n):
            pair = f.candidate_pair(scene, i)
            inc = f.c.conservative_candidates(old.mirrors, i, old.s0, old.beta, old.tol)
            out = f.c.conservative_candidates(old.mirrors, i, old.target[i], old.beta, old.tol)
            assert np.array_equal(inc, pair.incoming) and np.array_equal(out, pair.outgoing)
            assert f.candidate_pair(scene, i) is pair
            _must_reject(lambda: pair.incoming.setflags(write=True))
            assert pair.incoming.dtype == np.int64 and pair.outgoing.dtype == np.int64
            counts.append([len(inc), len(out)])
        assert max(x[0] + x[1] for x in counts) > 0, 'Artificial pressure must include nonempty candidates'
        return {'reference_scene_key_equal': True, 'all_candidate_indices_equal': True,
                'candidate_counts': counts, 'lazy_pair_reused': True,
                'all_parameters_equal': True}
    check('F02_parameter_and_candidate_identity', mapping_and_candidates)

    def ray_identity():
        evidence = []
        for i in (0, 1):
            words = [2026090504, 410, i]
            o, s = f.c.random_rays(scene.mirrors, i, scene.s0, scene.beta, 128, words)
            go, eo = f.reference.trace(old, i, o, s)
            gf, ef = f.trace_same(scene, i, o, s)
            gx, ex = f.trace_same(scene, i, o, s, screen=False)
            counters['unique_source_samples'] += 128; counters['path_evaluations'] += 3 * 128
            assert np.array_equal(go, gf) and np.array_equal(gf, gx)
            eq = {k: bool(np.array_equal(eo[k], ef[k]) and np.array_equal(ef[k], ex[k])) for k in f.EVENT_KEYS}
            assert all(eq.values())
            evidence.append({'mirror_index': i, 'samples': 128, 'events_equal': eq,
                             'weights_exactly_equal': True})
        return evidence
    check('F03_reference_fast_exhaustive_same_rays', ray_identity)

    def bound_cache_and_source():
        o, s = f.c.random_rays(scene.mirrors, 0, scene.s0, scene.beta, 4, [2026090504, 411])
        pair = f.candidate_pair(scene, 0)
        variants = []
        for label in ('width_height', 'height', 'tower', 'count', 'order', 'time'):
            d = copy.deepcopy(snapshot)
            if label == 'width_height': d.width = 6.; d.height = 4.
            elif label == 'height': d.installation_height = 5.
            elif label == 'tower': d.tower_xy = (10., 5.)
            elif label == 'count': d.mirrors.pop()
            elif label == 'order': d.mirrors.reverse()
            other = f.scene_at(f.freeze_design(d), 3 if label == 'time' else 12, 12. if label == 'time' else 9.)
            # Fresh local rays avoid rejecting a stale source before checking a foreign cache.
            oo, ss = f.c.random_rays(other.mirrors, 0, other.s0, other.beta, 4, [2026090504, 412])
            msg = _must_reject(lambda: f.trace_same(other, 0, oo, ss, cache=pair), 'CACHE_INVALID')
            variants.append({'changed': label, 'rejected': msg})
        outside = o.copy(); outside[0] += 20 * scene.mirrors.u[0]
        _must_reject(lambda: f.trace_same(scene, 0, outside, s), 'RAY_DOMAIN_FAILURE')
        angular = s.copy()
        angular[0] = f.c.cone_directions(scene.s0, scene.beta * 3, [1.], [.25])[0]
        _must_reject(lambda: f.trace_same(scene, 0, o, angular), 'RAY_DOMAIN_FAILURE')
        edge = (scene.mirrors.centers[0] + scene.mirrors.widths[0] / 2 * scene.mirrors.u[0])[None, :]
        central = scene.s0[None, :]
        _, ef = f.trace_same(scene, 0, edge, central)
        _, er = f.reference.trace(old, 0, edge, central)
        counters['path_evaluations'] += 2
        assert bool(ef['unknown'][0]) and np.array_equal(ef['unknown'], er['unknown'])
        return {'foreign_cache_rejections': variants, 'outside_source_and_cone_rejected': True,
                'edge_unknown_matches_reference': True}
    check('F04_cache_invalidation_and_source_boundaries', bound_cache_and_source)

    def raw_statistics():
        seeds = [[2026090504, 420, b] for b in range(3)]
        got = f.sample_stats(scene, 0, seeds, 32, [8, 32])
        counters['path_evaluations'] += 96; counters['unique_source_samples'] += 96
        max_error = 0.
        for b, words in enumerate(seeds):
            o, s = f.c.random_rays(old.mirrors, 0, old.s0, old.beta, 32, words)
            g, ev = f.reference.trace(old, 0, o, s)
            counters['path_evaluations'] += 32
            for j, k in enumerate((8, 32)):
                sliced = {key: value[:k] if isinstance(value, np.ndarray) else value for key, value in ev.items()}
                expected = f.reference.stats(g[:k], sliced)
                converted = f.batch_as_reference(got, j, b)
                for field in ('sums', 'cross'):
                    err = float(np.max(np.abs(np.asarray(expected[field]) - converted[field])))
                    max_error = max(max_error, err)
                    assert err < 1e-12, (field, err)
                assert expected['counts'] == converted['counts']
                assert got['counts'][j, b, 5] == int(ev['R'][:k].sum())
                assert abs(expected['unknown_weight'] - converted['unknown_weight']) < 1e-12
                assert abs(expected['known_capture_weight'] - converted['known_capture_weight']) < 1e-12
        assert got['sums'].shape == (2, 3, 3) and got['cross'].shape == (2, 3, 3, 3)
        assert got['counts'].shape == (2, 3, 6)
        assert got['unique_source_samples'] == 96 and got['path_evaluations'] == 96
        _must_reject(lambda: f.sample_stats(scene, 0, [seeds[0], seeds[0]], 32), 'distinct seed')
        _must_reject(lambda: f.sample_stats(scene, 0, seeds, 32, [8, 8, 32]), 'unique ordered')
        return {'max_absolute_stat_error': max_error, 'count_order': f.COUNT_LABELS,
                'shape_sums': got['sums'].shape, 'shape_cross': got['cross'].shape,
                'shape_counts': got['counts'].shape, 'n_final_only': 96,
                'duplicate_batch_and_prefix_rejected': True}
    check('F05_one_trace_multi_batch_raw_statistics', raw_statistics)

    def bounded_timing():
        if benchmark_repeats == 0:
            return {'scope': 'timing disabled'}
        o, s = f.c.random_rays(scene.mirrors, 0, scene.s0, scene.beta, 256, [2026090504, 430])
        pair = f.candidate_pair(scene, 0)
        oldpair = f.reference.candidates(old, 0)
        t0 = time.perf_counter()
        for _ in range(benchmark_repeats): f.reference.trace(old, 0, o, s, cache=oldpair)
        old_seconds = time.perf_counter() - t0
        t0 = time.perf_counter()
        for _ in range(benchmark_repeats): f.trace_same(scene, 0, o, s, cache=pair)
        fast_seconds = time.perf_counter() - t0
        counters['path_evaluations'] += 2 * benchmark_repeats * 256
        counters['unique_source_samples'] += 256
        return {'repeats': benchmark_repeats, 'samples_per_replay': 256,
                'reference_seconds': old_seconds, 'fast_seconds': fast_seconds,
                'ratio_reference_over_fast': old_seconds / fast_seconds if fast_seconds else None,
                'freeze_seconds': freeze_seconds, 'prepare_once_seconds': prepare_seconds,
                'scope': 'four-mirror artificial frame only; no full-field timing guarantee; replayed samples not extra independent evidence'}
    check('F06_bounded_same_scene_timing', bounded_timing)

    def provenance_identity():
        readback = copy.deepcopy(snapshot)
        for row_index, row in enumerate(readback.mirrors):
            row['export_row'] = row_index + 2
            row['source_record_index'] = row_index + 1
        restored_frozen = f.freeze_design(readback)
        restored_scene = f.scene_at(restored_frozen, 12, 9.)
        assert restored_frozen.key == frozen.key
        assert restored_scene.key == scene.key
        assert restored_frozen.payload_json != frozen.payload_json
        restored = restored_frozen.to_design()
        for row_index, row in enumerate(restored.mirrors):
            assert row['export_row'] == row_index + 2
            assert row['source_record_index'] == row_index + 1
        # Reader row numbering is retained but does not describe the design.
        shifted = copy.deepcopy(readback)
        for row in shifted.mirrors:
            row['export_row'] += 17
            row['source_record_index'] += 23
        shifted_frozen = f.freeze_design(shifted)
        assert shifted_frozen.key == frozen.key
        assert shifted_frozen.payload_json != restored_frozen.payload_json
        assert f.scene_at(shifted_frozen, 12, 9.).key == scene.key
        changed = []
        for label in ('x', 'y', 'width', 'height', 'installation_height',
                      'tower_xy', 'count', 'order', 'mirror_id',
                      'position_key', 'name', 'version', 'metadata'):
            variant = copy.deepcopy(snapshot)
            if label == 'x': variant.mirrors[0]['x'] += .125
            elif label == 'y': variant.mirrors[0]['y'] += .125
            elif label == 'width': variant.width = 7.
            elif label == 'height': variant.height = 5.
            elif label == 'installation_height': variant.installation_height = 5.
            elif label == 'tower_xy': variant.tower_xy = (5., -2.)
            elif label == 'count': variant.mirrors.pop()
            elif label == 'order': variant.mirrors.reverse()
            elif label == 'mirror_id': variant.mirrors[0]['mirror_id'] = 100
            elif label == 'position_key': variant.mirrors[0]['position_key'] += '-changed'
            elif label == 'name': variant.name += '-changed'
            elif label == 'version': variant.version = 'v002'
            elif label == 'metadata': variant.metadata['nested'].append(3)
            frozen_variant = f.freeze_design(variant)
            assert frozen_variant.key != frozen.key, label
            scene_variant = f.scene_at(frozen_variant, 12, 9.)
            if label != 'metadata':
                assert scene_variant.key != scene.key, label
            else:
                # Metadata affects frozen design identity; the reference scene
                # identity covers optical geometry and evaluation tag only.
                assert scene_variant.key == scene.key
            changed.append({'field': label, 'frozen_key_changed': True,
                            'scene_key_changed': scene_variant.key != scene.key})
        return {'provenance_only_frozen_and_scene_keys_equal': True,
                'provenance_retained_in_payload_and_to_design': True,
                'different_provenance_numbering_preserved_without_key_change': True,
                'stable_physical_and_identity_fields': changed,
                'new_optical_path_evaluations': 0,
                'scope': 'Artificial identity checks; full-field compact readback remains a separate caller gate.'}
    check('F07_provenance_stable_identity', provenance_identity)
    return {'suite': 'q02-fast-v002', 'checks': checks,
            'all_pass': all(row['passed'] for row in checks),
            'elapsed_seconds': time.perf_counter() - started, **counters,
            'no_target_search_layouts_generated': True,
            'no_formal_power_result': True,
            'limits': 'Artificial cases only; caller must add pinned old-scene and dense/new-scene comparisons under its shared budget.'}

