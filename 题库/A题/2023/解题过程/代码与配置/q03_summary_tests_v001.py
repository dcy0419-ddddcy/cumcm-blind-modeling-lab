"""Independent artificial-array expectations for Q3 summary; no optical calls.

Run only under the root's cumulative budget. These inputs are teaching
sufficient-statistic fixtures, not generated Q3 layouts or physical proofs.
Certificate payloads test validation plumbing with explicitly artificial pins.
"""
from __future__ import annotations

import copy
import json
import math
import traceback

import numpy as np

import q03_summary_v001 as summary


def _fixture(areas=(4., 12.)):
    levels = np.array([64, 128], dtype=np.int64)
    sums = np.zeros((2, 8, 60, 2, 3), dtype=float)
    counts = np.zeros((2, 8, 60, 2, 6), dtype=np.int64)
    for li, n in enumerate(levels):
        sums[li, ..., 0] = n
        for mi, survival, capture in [(0, .5, .25), (1, .75, .5)]:
            sums[li, :, :, mi, 1] = n * survival
            sums[li, :, :, mi, 2] = n * capture
            counts[li, :, :, mi, 0] = int(n * (1 - survival))
            counts[li, :, :, mi, 2] = int(n * survival)
            counts[li, :, :, mi, 3] = int(n * capture)
            counts[li, :, :, mi, 5] = int(n * capture)
    return dict(sums=sums, counts=counts, unknown_weights=np.zeros((2, 8, 60, 2)),
                cosine=np.ones((60, 2)), tau=np.ones((60, 2)), dni=np.ones(60),
                areas=np.array(areas), levels_n=levels)


def _run(data, **kwargs):
    return summary.summarize_search_statistics(**data, **kwargs)


def _close(actual, expected, atol=2e-12):
    assert np.allclose(actual, expected, atol=atol, rtol=2e-12, equal_nan=True), (
        np.asarray(actual).tolist(), np.asarray(expected).tolist())


def _zero(data, kind, ti=0, mi=0, survival_zero=False):
    data['sums'][:, :, ti, mi, 2] = 0
    data['counts'][:, :, ti, mi, 3] = 0
    data['counts'][:, :, ti, mi, 5] = 0
    if kind == 'zero_survivor' or survival_zero:
        data['sums'][:, :, ti, mi, 1] = 0
        data['counts'][:, :, ti, mi, 0] = data['levels_n'][:, None]
        data['counts'][:, :, ti, mi, 1:3] = 0


def _certificate(kind, ti=0, mi=0):
    scene, source = 'a' * 64, 'b' * 64
    cap = dict(proof='source_ball_to_cap_interior_v001', source_radius_m=.25,
               source_plane_gap_m=2., axis_to_vertical_plus_beta_rad=0.,
               radial_upper_m=.25, cap_radius_m=1., strict_margin_m=.75, side='bottom')
    payload = dict(scene_sha256=scene, mirror_index=mi, kind=kind)
    payload['incoming_cap' if kind == 'zero_survivor' else 'outgoing_cap'] = cap
    return dict(certificate_records=[dict(time_index=ti, mirror_index=mi,
                scene_sha256=scene, source=dict(name='artificial-certificate-fixture', sha256=source),
                certificate=payload)], scene_keys=[scene] * 60,
                trusted_certificate_sources={'artificial-certificate-fixture': source})


def _unequal_area():
    out = _run(_fixture())
    area = out['area_weighted_efficiencies']
    # Mirror efficiencies .23/.46; weights 1/4 and 3/4. Survival .5/.75,
    # conditional capture .5/(2/3). These are independent pencil expectations.
    _close(out['point'][:, :4], [.345, 1., .625, 7 / 12])
    _close(area['point'], [.4025, 1., .6875, .625])
    _close(out['point'][:, 4:], [6.44, .4025])
    _close(area['conservative_work_indicator'], 0.)
    _close(out['energy_total_ratios']['values'], [11 / 16, 7 / 11, 7 / 16])
    assert area['required_for_main_table_gate'] is False


def _equal_area():
    out = _run(_fixture((4., 4.)))
    area = out['area_weighted_efficiencies']
    _close(out['point'][:, :4], [.345, 1., .625, 7 / 12])
    _close(out['point'][:, 4:], [2.76, .345])
    _close(area['point'], out['point'][:, :4])
    _close(area['jackknife_se'], out['jackknife_se'][:, :4])
    _close(area['conservative_work_indicator'], out['conservative_work_indicator'][:, :4])


def _whole_batch_jk():
    data = _fixture()
    for li, n in enumerate(data['levels_n']):
        for bi in range(8):
            count = int(n * (bi + 1) / 32)
            data['sums'][li, bi, :, 1, 2] = count
            data['counts'][li, bi, :, 1, 3] = count
            data['counts'][li, bi, :, 1, 5] = count
    area = _run(data)['area_weighted_efficiencies']
    expected_point = .92 * (1 / 16 + .75 * 9 / 64)
    expected_se = (.92 * 3 / 128) * math.sqrt(3 / 4)
    _close(area['point'][:, 0], expected_point)
    _close(area['jackknife_se'][:, 0], expected_se)
    for bi in range(8):
        expected_leave = .92 * (1 / 16 + .75 * (36 - (bi + 1)) / (7 * 32))
        _close(area['leave_one_batch_estimates'][bi, :, 0], expected_leave)
    _close(area['absolute_changes']['prefix_half'], 0.)
    _close(area['absolute_changes']['raw_integral'], 0.)
    _close(area['conservative_work_indicator'][:, 0], summary.T7_975 * expected_se)


def _prefix_and_raw():
    data = _fixture()
    data['sums'][0, :, :, 1, 2] = 16
    data['counts'][0, :, :, 1, 3] = 16
    data['counts'][0, :, :, 1, 5] = 16
    area = _run(data)['area_weighted_efficiencies']
    _close(area['prefix_half_point'], [.23, 1., .6875, .375])
    _close(area['absolute_changes']['prefix_half'], [.1725, 0., 0., .25])
    _close(area['conservative_work_indicator'], [.1725, 0., 0., .25])
    # Scale all raw sums together: self-normalized fractions do not change;
    # the raw integral must divide by pooled 8*128, not per-batch 128.
    raw_data = _fixture()
    raw_data['sums'] *= .8
    raw_area = _run(raw_data)['area_weighted_efficiencies']
    _close(raw_area['point'], [.4025, 1., .6875, .625])
    _close(raw_area['raw_integral_alternative'], [.322, 1., .55, .625])
    _close(raw_area['absolute_changes']['raw_integral'], [.0805, 0., .1375, 0.])


def _low_area_and_gate():
    data = _fixture()
    for li, n in enumerate(data['levels_n']):
        data['counts'][li, :, 0, 1, 0] = n - 6
        data['counts'][li, :, 0, 1, 2] = 6
        data['counts'][li, :, 0, 1, 3] = 3
        data['counts'][li, :, 0, 1, 5] = 3
        data['sums'][li, :, 0, 1, 1] = 6
        data['sums'][li, :, 0, 1, 2] = 3
    out = _run(data, efficiency_abs_target=.12, power_relative_target=1., rated_power_kw=1.)
    area = out['area_weighted_efficiencies']
    bounds = area['low_survival']['effect_diameter_bound']
    _close(bounds[0], [.138, 0., .15, .15])
    _close(bounds[-1], [.92 * .75 / 60, 0., .75 / 60, .75 / 60])
    _close(bounds[1:12], 0.)
    _close(out['low_survival']['effect_diameter_bound'][0], [.092, 0., .1, .1, 2.208, .138])
    assert area['low_survival']['screened_count'] == 1
    assert area['conservative_work_indicator'][0, 2] > .12
    assert out['all_table_items_precision_met'] and out['formal_decision'] == 'PASS'


def _true_zero_survivor():
    data = _fixture()
    _zero(data, 'zero_survivor')
    out = _run(data, **_certificate('zero_survivor'))
    assert out['certificate_audit']['all_valid']
    assert out['pooled_state_counts']['TRUE_ZERO_SURVIVOR'] == 1
    assert out['pooled_total_defined'][0, 0]
    assert np.isnan(out['point'][0, 3])
    _close(out['energy_total_ratios']['values'][0], [53 / 80, 34 / 53, 34 / 80])
    _close(out['area_weighted_efficiencies']['low_survival']['effect_diameter_bound'][0],
           [0., 0., 0., .25 / 5])


def _true_zero_capture():
    data = _fixture()
    _zero(data, 'zero_capture')
    out = _run(data, **_certificate('zero_capture'))
    assert out['pooled_state_counts']['TRUE_ZERO_CAPTURE'] == 1
    assert out['pooled_component_defined'][0, 0, 3]
    _close(out['energy_total_ratios']['values'][0], [55 / 80, 34 / 55, 34 / 80])


def _capture_known_survival_unknown():
    data = _fixture()
    _zero(data, 'zero_capture', survival_zero=True)
    out = _run(data, **_certificate('zero_capture'))
    assert out['pooled_total_defined'][0, 0]
    assert not out['pooled_component_defined'][0, 0, 2]
    assert not out['pooled_component_defined'][0, 0, 3]
    _close(out['energy_total_ratios']['values'][0], [np.nan, np.nan, 34 / 80])
    _close(out['area_weighted_efficiencies']['low_survival']['effect_diameter_bound'][0],
           [0., 0., .25 / 5, .25 / 5])


def _sampled_zeros():
    data = _fixture()
    _zero(data, 'zero_capture')
    out = _run(data)
    assert out['pooled_state_counts']['SAMPLED_ZERO_CAPTURE'] == 1
    assert not out['pooled_total_defined'][0, 0]
    _close(out['energy_total_ratios']['values'][0], [55 / 80, np.nan, np.nan])
    assert np.isnan(out['area_weighted_efficiencies']['point'][0, 0])
    assert out['formal_decision'] == 'UNRESOLVED'
    _zero(data, 'zero_survivor')
    out = _run(data)
    assert out['pooled_state_counts']['SAMPLED_ZERO_SURVIVOR'] == 1
    assert out['formal_decision'] == 'UNRESOLVED'


def _ratio_own_denominator():
    # All true-zero survival energies: Pi1/Pi0=0 and Pi2/Pi0=0, Pi2/Pi1=NA.
    formal = dict(pi0=np.ones((60, 2)), pi1=np.zeros((60, 2)), pi2=np.zeros((60, 2)))
    _close(summary._energy_total_ratios(formal), [0., np.nan, 0.])
    formal['pi1'][0, 0] = np.nan
    _close(summary._energy_total_ratios(formal)[0], [np.nan, np.nan, 0.])
    formal['pi1'][0, 0] = 0.
    formal['pi2'][0, 0] = np.nan
    _close(summary._energy_total_ratios(formal)[0], [0., np.nan, np.nan])


def _bad_certificate_and_unknown():
    data = _fixture()
    _zero(data, 'zero_survivor')
    cert = _certificate('zero_survivor')
    cert['certificate_records'][0]['source']['sha256'] = 'c' * 64
    out = _run(data, **cert)
    assert not out['certificate_audit']['all_valid']
    assert out['pooled_state_counts']['SAMPLED_ZERO_SURVIVOR'] == 1
    assert out['formal_decision'] == 'UNRESOLVED'
    data = _fixture()
    data['counts'][-1, 0, 0, 0, 4] = 1
    data['unknown_weights'][-1, 0, 0, 0] = 1.
    out = _run(data)
    assert out['pooled_state_counts']['BOUNDARY_UNCERTAIN'] == 1
    assert np.isnan(out['area_weighted_efficiencies']['point'][0, 0])


def _mode_isolation():
    data = _fixture()
    for key in ('sums', 'counts', 'unknown_weights'):
        data[key] = data[key][:, :4]
    out = _run(data, mode='full_comparison')
    assert out['formal_decision'] == 'NOT_AVAILABLE_SEARCH_COMPARISON'
    assert out['rated_power_met'] is None
    assert out['area_weighted_efficiencies']['conservative_work_indicator'] is None
    _close(out['area_weighted_efficiencies']['point'], [.4025, 1., .6875, .625])
    partial = _fixture()
    for key in ('sums', 'counts', 'unknown_weights'):
        partial[key] = partial[key][:, :, :1]
    for key in ('cosine', 'tau', 'dni'):
        partial[key] = partial[key][:1]
    partial.update(months=np.array([1]), hours=np.array([9.]))
    out = _run(partial, mode='heuristic')
    assert out['formal_h02_rows'] is None
    assert 'point' not in out['area_weighted_efficiencies']
    _close(out['area_weighted_efficiencies']['temporal_point'], [[.4025, 1., .6875, .625]])


def run_tests():
    checks = []
    cases = [
        ('A01_unequal_area_manual', _unequal_area),
        ('A02_equal_area_reduction', _equal_area),
        ('A03_whole_batch_JK_manual', _whole_batch_jk),
        ('A04_prefix_raw_and_pooled_n', _prefix_and_raw),
        ('A05_area_low_bound_not_main_gate', _low_area_and_gate),
        ('A06_true_zero_survivor', _true_zero_survivor),
        ('A07_true_zero_capture', _true_zero_capture),
        ('A08_known_capture_independent_energy_NA', _capture_known_survival_unknown),
        ('A09_sampled_zeros_preserved', _sampled_zeros),
        ('A10_each_energy_ratio_own_denominator', _ratio_own_denominator),
        ('A11_bad_source_and_unknown', _bad_certificate_and_unknown),
        ('A12_comparison_and_heuristic_isolation', _mode_isolation),
    ]
    for name, fn in cases:
        try:
            fn()
            checks.append(dict(name=name, passed=True))
        except Exception:
            checks.append(dict(name=name, passed=False, error=traceback.format_exc()))
    return dict(suite='q03-summary-v001', checks=checks,
                all_pass=all(c['passed'] for c in checks),
                scope='artificial arrays and artificial certificate pins only; no rays, layouts, data files or old-result re-evaluation')


run_checks = run_tests
run = run_tests


if __name__ == '__main__':
    result = run_tests()
    print(json.dumps(summary.jsonable(result), ensure_ascii=False, sort_keys=True, allow_nan=False))
    if not result['all_pass']:
        raise SystemExit(1)
