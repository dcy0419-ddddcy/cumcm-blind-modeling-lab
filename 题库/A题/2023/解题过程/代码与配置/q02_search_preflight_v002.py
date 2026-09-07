"""Resume dense Q2 preflight with canonical identity repair; no search scores.

Retains v001 and its DenseA 12 valid optical comparisons. This entry reads the
existing dense pre-registration, reruns only fast-v002 artificial tests, replays
the necessary compact identity/optical check, then completes DenseB and bounded
Q1 comparison. New evidence filenames carry v002. Root executes under Budget.
"""
from __future__ import annotations

import time
START = time.perf_counter()
from pathlib import Path
import json
import math
import sys
import traceback

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import q02_search_common_v001 as io


def main():
    budget = io.Budget('preflight-v002', 'search', START)
    try:
        import numpy as np
        import q02_fast_v002 as f
        import q02_fast_tests_v002 as tests
        import q02_compact_v001 as compact

        d, e, out = f.design_module, f.reference, io.OUT
        prereg_path = out / '密集诊断配置预登记.json'
        prereg = io.load(prereg_path)
        prereg_sha = io.sha(prereg_path)
        if not prereg.get('before_any_dense_optical_output'):
            raise RuntimeError('DENSE_PRE_REGISTRATION_FLAG_MISSING')
        if [spec.get('name') for spec in prereg['specs']] != ['DenseA', 'DenseB']:
            raise RuntimeError('DENSE_PRE_REGISTRATION_NAMES_CHANGED')
        times = prereg['times']
        if times != [[12, 9], [3, 12], [6, 15]]:
            raise RuntimeError('DENSE_PRE_REGISTERED_TIMES_CHANGED')
        n_batch = prereg['independent_batches']
        samples = prereg['samples_per_batch']
        rays = prereg['comparison_rays']
        root_seed = prereg['root_seed']
        if (n_batch, samples, rays, root_seed) != (8, 128, 64, 2026090505):
            raise RuntimeError('DENSE_PRE_REGISTERED_SAMPLE_PLAN_CHANGED')

        t0 = time.perf_counter()
        test_report = tests.run_tests()
        io.save(out / '提速人工回归-v002.json', test_report)
        if not test_report['all_pass']:
            raise RuntimeError('FAST_V002_TEST_FAILURE')
        report = {
            'environment': {'python': sys.version, 'numpy': np.__version__},
            'artificial_seconds': time.perf_counter() - t0,
            'artificial_scope': 'fast-v002 tests only; existing compact seven checks not rerun',
            'dense_preregistration': {'path': str(prereg_path), 'sha256': prereg_sha,
                                     'action': 'read existing v001; not overwritten'},
            'designs': [], 'resumed_from': 'q02_search_preflight_v001.py',
            'old_failure': 'DENSE_DISK_INPUT_FAILURE: provenance polluted frozen identity',
            'new_integral_comparisons': 0, 'reused_integral_comparisons': 0,
        }

        def checked_flags(value, label):
            if not isinstance(value, dict) or set(value) != set(f.EVENT_KEYS) or not all(v is True for v in value.values()):
                raise RuntimeError(label)

        def validate_rows(rows, selection, frozen, reuse):
            """Validate coverage, identity, seeds, same-ray and exhaustive results."""
            if not isinstance(rows, list) or len(rows) != 12:
                raise RuntimeError('DENSE_COMPARISON_COUNT_NOT_TWELVE')
            expected = []
            for sel in selection:
                if len(sel['indices']) != 4 or len(set(sel['indices'])) != 4:
                    raise RuntimeError('DENSE_SELECTION_NOT_FOUR_DISTINCT')
                for j, index in enumerate(sel['indices']):
                    expected.append((sel, j, int(index)))
            for row, (sel, j, index) in zip(rows, expected):
                if (row['month'], row['hour'], row['index'], row['mirror_id']) != (
                        sel['month'], sel['hour'], index, frozen.mirror_ids[index]):
                    raise RuntimeError('DENSE_STORED_COMPARISON_IDENTITY_MISMATCH')
                expected_words = [[root_seed, 880, int(sel['month']), int(sel['hour'] * 100),
                                   int(frozen.mirror_ids[index]) & 0xffffffff, b] for b in range(n_batch)]
                if row['seeds'] != expected_words or row['n_unique'] != n_batch * samples:
                    raise RuntimeError('DENSE_STORED_RANDOM_PLAN_MISMATCH')
                checked_flags(row['events_equal'], 'DENSE_STORED_EVENTS_MISMATCH')
                for label, limit in [('weight_abs', 1e-12), ('raw_abs', 1e-10), ('power_abs', 1e-10)]:
                    value = row[label]
                    if value is None or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= limit:
                        raise RuntimeError('DENSE_STORED_' + label.upper() + '_FAILURE')
                if j < 2:
                    checked_flags(row['screen_exhaustive'], 'DENSE_STORED_EXHAUSTIVE_MISMATCH')
                elif row['screen_exhaustive'] is not None:
                    raise RuntimeError('DENSE_STORED_UNREGISTERED_EXHAUSTIVE_RECORD')
                counts = io.convert(row['candidate_counts'])
                if counts != io.convert(sel['candidate_counts'][j]):
                    raise RuntimeError('DENSE_STORED_CANDIDATE_COUNTS_MISMATCH')
            return {'comparisons': 12, 'exhaustive_comparisons': 6,
                    'all_stored_flags_and_numeric_thresholds_pass': True,
                    'source': 'v001 existing evidence' if reuse else 'v002 new execution'}

        def plain_copy(rebuilt):
            """Remove reader provenance while retaining every design-semantic field."""
            payload = compact.canonical_payload(rebuilt)
            return d.Design(payload['name'], payload['version'], tuple(payload['tower_xy']),
                            payload['width'], payload['height'], payload['installation_height'],
                            payload['mirrors'], payload['metadata'])

        for spec in prereg['specs']:
            budget.guard()
            name = spec['name']
            folder = out / 'diagnostics' / name
            reuse = name == 'DenseA'
            started_geometry = time.perf_counter()
            if reuse:
                receipt_source = folder / 'compact_receipt.json'
                receipt = io.load(receipt_source)
                rebuilt, read_report = compact.read_compact(folder / 'design.bundle.json', receipt['bundle_sha256'])
                design = plain_copy(rebuilt)
                if (design.name != spec['name'] or design.version != spec['version']
                        or list(design.tower_xy) != list(spec['tower_xy'])
                        or design.width != spec['width'] or design.height != spec['height']
                        or design.installation_height != spec['installation_height']
                        or design.metadata['rings'] != spec['rings']):
                    raise RuntimeError('DENSEA_COMPACT_DIFFERS_FROM_FROZEN_SPEC')
                generation = io.load(folder / 'generation.json')
                if generation['actual_n'] != design.n or generation['status'] != 'geometry_and_scope_pass':
                    raise RuntimeError('DENSEA_GENERATION_COUNT_OR_STATUS_MISMATCH')
                frozen = f.freeze_design(design)
                geometry_seconds = time.perf_counter() - started_geometry
                disk_seconds = None  # Existing I/O timing was not committed by failed v001.
                io.save(folder / 'reuse_inputs-v002.json', {
                    'source_version': 'v001', 'regenerated_layout': False,
                    'source_hashes': {p.name: io.sha(p) for p in
                                      [folder / 'generation.json', folder / 'geometry.json',
                                       receipt_source, folder / 'design.bundle.json']},
                    'preregistration_sha256': prereg_sha,
                    'spec_fields_match_bound_bundle': True,
                    'actual_n': design.n, 'canonical_digest': compact.design_digest(design),
                    'new_geometry_seconds_includes_read_and_refreeze': geometry_seconds})
            else:
                design, generation = d.generate_ring_design(**spec)
                frozen = f.freeze_design(design)
                geometry_seconds = time.perf_counter() - started_geometry
                started_disk = time.perf_counter()
                receipt = compact.save_compact(design, folder, stem='design-v002')
                rebuilt, read_report = compact.read_compact(receipt['bundle_path'], receipt['bundle_sha256'])
                disk_seconds = time.perf_counter() - started_disk
                io.save(folder / 'generation-v002.json', generation)
                io.save(folder / 'compact_receipt-v002.json', receipt)
            io.save(folder / 'geometry-v002.json', frozen.validation)

            t0 = time.perf_counter()
            domains = []
            for month in range(1, 13):
                for hour in [9, 10.5, 12, 13.5, 15]:
                    budget.guard()
                    scene = f.scene_at(frozen, month, hour)
                    domains.append({'month': month, 'hour': hour, 'key': scene.key, 'domain': scene.domain})
            domain_seconds = time.perf_counter() - t0
            io.save(folder / 'domain60-v002.json', domains)

            t0 = time.perf_counter()
            xy = frozen.centers[:, :2]
            nearest = np.full(frozen.n, np.inf)
            for index in range(frozen.n):
                distances = np.linalg.norm(xy - xy[index], axis=1)
                distances[index] = np.inf
                nearest[index] = distances.min()
            scenes, selection = [], []
            for month, hour in times:
                budget.guard()
                scene = f.scene_at(frozen, month, hour)
                pairs = [f.candidate_pair(scene, index) for index in range(scene.n)]
                counts = np.array([[len(pair.incoming), len(pair.outgoing)] for pair in pairs])
                criteria = [-counts.sum(1), 350 - np.linalg.norm(xy, axis=1), nearest,
                            np.linalg.norm(xy - np.asarray(design.tower_xy), axis=1) - 100]
                picked = []
                for score in criteria:
                    picked.append(next(index for index in sorted(range(scene.n), key=lambda i: (score[i], frozen.mirror_ids[i]))
                                       if index not in picked))
                selection.append({'month': month, 'hour': hour, 'indices': picked,
                                  'ids': [frozen.mirror_ids[index] for index in picked],
                                  'candidate_counts': counts[picked], 'all_candidate_max': counts.max(0)})
                scenes.append(scene)
            preparation_seconds = time.perf_counter() - t0
            io.save(folder / 'selection_before_optics-v002.json', selection)

            if reuse:
                previous_selection_path = folder / 'selection_before_optics.json'
                old_selection = io.load(previous_selection_path)
                if io.convert(selection) != old_selection:
                    raise RuntimeError('DENSEA_SELECTION_CHANGED_AFTER_IDENTITY_ONLY_REPAIR')
                old_rows_path = folder / 'optical_comparisons.json'
                rows = io.load(old_rows_path)
                comparison_check = validate_rows(rows, selection, frozen, reuse=True)
                io.save(folder / 'optical_reuse_check-v002.json', {
                    **comparison_check, 'source_path': str(old_rows_path), 'source_sha256': io.sha(old_rows_path),
                    'source_selection_sha256': io.sha(previous_selection_path),
                    'no_dense_integrals_repeated': True,
                    'old_fast_code_sha256': io.sha(HERE / 'q02_fast_v001.py'),
                    'new_fast_code_sha256': io.sha(HERE / 'q02_fast_v002.py'),
                    'reason': 'v001 all 12 comparisons completed before compact identity-only failure'})
                fast_seconds = sum(row['fast_1024_seconds'] for row in rows)
                reference_seconds = sum(row['reference_64_seconds'] for row in rows)
                exhaustive_seconds = None
                report['reused_integral_comparisons'] += len(rows)
            else:
                rows = []
                fast_seconds = reference_seconds = exhaustive_seconds = 0.0
                for scene, selected in zip(scenes, selection):
                    for j, index in enumerate(selected['indices']):
                        budget.guard()
                        words = [[root_seed, 880, scene.month, int(scene.hour * 100),
                                  int(frozen.mirror_ids[index]) & 0xffffffff, batch] for batch in range(n_batch)]
                        t0 = time.perf_counter()
                        stats = f.sample_stats(scene, index, words, samples, [rays, samples])
                        fast_elapsed = time.perf_counter() - t0
                        fast_seconds += fast_elapsed
                        origins, directions = f.c.random_rays(scene.mirrors, index, scene.s0, scene.beta, rays, words[0])
                        weight, events = f.trace_same(scene, index, origins, directions)
                        reference_scene = f.as_reference(scene)
                        t0 = time.perf_counter()
                        old_weight, old_events = e.trace(reference_scene, index, origins, directions)
                        old_elapsed = time.perf_counter() - t0
                        reference_seconds += old_elapsed
                        equality = {key: bool(np.array_equal(events[key], old_events[key])) for key in f.EVENT_KEYS}
                        weight_error = float(np.max(np.abs(weight - old_weight)))
                        reference_stats = e.stats(old_weight, old_events)
                        batch_stats = f.batch_as_reference(stats, 0, 0)
                        raw_error = float(np.max(np.abs(np.asarray(reference_stats['sums']) - batch_stats['sums'])))
                        p0 = e.summarize(reference_scene, index, reference_stats)
                        p1 = e.summarize(reference_scene, index, batch_stats)
                        if p0['power_kw'] is None and p1['power_kw'] is None:
                            power_error = 0.0
                        elif p0['power_kw'] is None or p1['power_kw'] is None:
                            power_error = None
                        else:
                            power_error = abs(p0['power_kw'] - p1['power_kw'])
                        exhaustive = None
                        if j < 2:
                            t0 = time.perf_counter()
                            all_weight, all_events = f.trace_same(scene, index, origins, directions, screen=False)
                            exhaustive_seconds += time.perf_counter() - t0
                            exhaustive = {key: bool(np.array_equal(events[key], all_events[key])) for key in f.EVENT_KEYS}
                            if not np.array_equal(weight, all_weight):
                                raise RuntimeError('DENSEB_EXHAUSTIVE_WEIGHT_MISMATCH')
                        row = {'month': scene.month, 'hour': scene.hour, 'index': index,
                               'mirror_id': frozen.mirror_ids[index], 'seeds': words,
                               'events_equal': equality, 'weight_abs': weight_error, 'raw_abs': raw_error,
                               'power_abs': power_error, 'screen_exhaustive': exhaustive,
                               'fast_1024_seconds': fast_elapsed, 'reference_64_seconds': old_elapsed,
                               'candidate_counts': stats['candidate_counts'], 'n_unique': n_batch * samples,
                               'final_counts': stats['counts'][-1].sum(0)}
                        rows.append(row)
                        io.save(folder / 'optical_comparisons-v002.json', rows)
                        checked_flags(equality, 'DENSEB_SAME_RAY_EVENTS_FAILURE')
                        if (weight_error > 1e-12 or raw_error > 1e-10 or power_error is None or power_error > 1e-10):
                            raise RuntimeError('DENSEB_SAME_RAY_NUMERIC_FAILURE')
                        if exhaustive is not None:
                            checked_flags(exhaustive, 'DENSEB_EXHAUSTIVE_FAILURE')
                        budget.tick()
                comparison_check = validate_rows(rows, selection, frozen, reuse=False)
                report['new_integral_comparisons'] += len(rows)

            # Replayed 64-source check: physical events AND canonical frozen key.
            # DenseA uses the same 889 ray seed as the failed v001 attempt.
            budget.guard()
            t0 = time.perf_counter()
            read_frozen = f.freeze_design(rebuilt)
            read_scene = f.scene_at(read_frozen, times[0][0], times[0][1])
            scene = scenes[0]
            index = selection[0]['indices'][0]
            origins, directions = f.c.random_rays(scene.mirrors, index, scene.s0, scene.beta, rays, [root_seed, 889])
            weight, events = f.trace_same(scene, index, origins, directions)
            read_weight, read_events = f.trace_same(read_scene, index, origins, directions)
            disk_flags = {key: bool(np.array_equal(events[key], read_events[key])) for key in f.EVENT_KEYS}
            disk_flags['weight'] = bool(np.array_equal(weight, read_weight))
            disk_flags['frozen_key'] = read_frozen.key == frozen.key
            disk_flags['canonical_fields'] = compact.design_digest(rebuilt) == compact.design_digest(design)
            disk_check = {'design': name, 'samples': rays, 'seed': [root_seed, 889],
                          'month': times[0][0], 'hour': times[0][1], 'index': index,
                          'mirror_id': frozen.mirror_ids[index], 'checks': disk_flags,
                          'all_pass': all(disk_flags.values()), 'original_key': frozen.key,
                          'readback_key': read_frozen.key,
                          'payload_json_equal': read_frozen.payload_json == frozen.payload_json,
                          'provenance_allowed_to_differ': True,
                          'old_source_is_q1_excel_row': False,
                          'seconds': time.perf_counter() - t0}
            io.save(folder / 'compact_optical_recheck-v002.json', disk_check)
            if not disk_check['all_pass']:
                raise RuntimeError('DENSE_DISK_INPUT_FAILURE_V002')

            one = {'name': name, 'n': design.n, 'area': design.total_area,
                   'geometry_seconds': geometry_seconds, 'compact_io_seconds': disk_seconds,
                   'domain60_seconds': domain_seconds, 'all_candidates_3_times_seconds': preparation_seconds,
                   'fast_integral_seconds': fast_seconds, 'reference_seconds_64_per_combination': reference_seconds,
                   'exhaustive_seconds': exhaustive_seconds, 'combinations': len(rows),
                   'mean_fast_1024_seconds': fast_seconds / len(rows),
                   'timing_source': 'v001 stored per-row times; missing old exhaustive/I/O duration left null' if reuse else 'v002 new execution',
                   'all_comparisons_pass': True, 'compact_optical_pass': disk_check['all_pass'],
                   'compact_csv_bytes': receipt['bytes']['mirrors'],
                   'max_candidates': np.max(np.asarray([row['all_candidate_max'] for row in selection]), axis=0),
                   'source_comparisons': 'optical_comparisons.json (v001, reused)' if reuse else 'optical_comparisons-v002.json',
                   'validation': comparison_check}
            report['designs'].append(one)
            io.save(out / '密集压力与计时-v002.json', report)
            budget.tick()

        # Genuine old Q1 field: read_field returns (centers ndarray, list of row
        # dicts), each dict has mirror_id, excel_row, x and y, as core-v003 131-145.
        budget.guard()
        centers, source_rows = f.c.read_field(io.ROOT / '附件' / '附件03.xlsx')
        if (centers.shape != (1745, 3) or len(source_rows) != 1745
                or any(set(row) != {'mirror_id', 'excel_row', 'x', 'y'} for row in source_rows)):
            raise RuntimeError('Q1_READ_FIELD_INTERFACE_CHANGED')
        old_design = d.Design('Q1-fast-regression', 'v001', (0, 0), 6, 6, 4,
            [{'mirror_id': row['mirror_id'], 'position_key': 'q1-row-' + str(row['excel_row']),
              'x': row['x'], 'y': row['y']} for row in source_rows], {})
        frozen = f.freeze_design(old_design)
        scene = f.scene_at(frozen, 12, 9)
        index = 56
        origins, directions = f.c.random_rays(scene.mirrors, index, scene.s0, scene.beta, 256, [root_seed, 887])
        weight, events = f.trace_same(scene, index, origins, directions)
        old_weight, old_events = e.trace(f.as_reference(scene), index, origins, directions)
        flags = {key: bool(np.array_equal(events[key], old_events[key])) for key in f.EVENT_KEYS}
        flags['weight'] = bool(np.array_equal(weight, old_weight))
        q1_check = {'mirror_id': source_rows[index]['mirror_id'], 'excel_row': source_rows[index]['excel_row'],
                    'month': 12, 'hour': 9, 'samples': 256, 'checks': flags, 'all_pass': all(flags.values()),
                    'source_read_field': 'q01_core_v003.read_field: ndarray centers plus dict row records',
                    'full_old_field_as_obstacles': 1745}
        io.save(out / 'Q1限定提速回归-v002.json', q1_check)
        if not q1_check['all_pass']:
            raise RuntimeError('Q1_FAST_REGRESSION_FAILURE_V002')
        if io.sha(prereg_path) != prereg_sha:
            raise RuntimeError('DENSE_PRE_REGISTRATION_MODIFIED_DURING_EXECUTION')
        report['all_pass'] = True
        report['q1_limited_regression'] = q1_check
        report['no_search_scores_generated'] = True
        report['compact_artificial_tests_rerun'] = False
        report['code_bindings'] = {path.name: io.sha(path) for path in
            [HERE / 'q02_fast_v002.py', HERE / 'q02_fast_tests_v002.py', HERE / 'q02_compact_v001.py', Path(__file__)]}
        io.save(out / '密集压力与计时-v002.json', report)
        budget.finish()
        print(json.dumps(io.convert(report), ensure_ascii=False))
    except BaseException:
        io.event('失败运行.jsonl', {'time': io.now(), 'mode': 'preflight-v002',
                                  'error': traceback.format_exc(), 'used': budget.used()})
        budget.finish('FAILED')
        raise


if __name__ == '__main__':
    main()
