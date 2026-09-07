"""Independent Q3 file-based reconstruction and paired work diagnostic.

Does not import or call q03_summary, engine, sampler, or optical kernel.  True-zero
certificates are deliberately not implemented here: a nonempty certificate
stream fails this verifier visibly instead of silently changing state policy.
The caller supplies its existing numerical Budget; no new budget is started.
"""
from pathlib import Path
import hashlib
import json
import math
import time
import numpy as np
import q03_common_v001 as io

HERE = Path(__file__).resolve().parent
T7 = 2.3646242515927844
TIMES = [[m, h] for m in range(1, 13) for h in (9., 10.5, 12., 13.5, 15.)]


def _rows(a):
    a = np.asarray(a, float)
    return np.concatenate((a.reshape(12, 5, a.shape[-1]).mean(1), a.mean(0)[None]), axis=0)


def _key(payload):
    s = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(s.encode()).hexdigest()


def _one(s, cc, uw, co, tau, dni, areas, n, raw=False):
    """Independent object equations, with strict fixed-population NA propagation."""
    N = len(areas)
    a, b, c = s.T
    valid = np.all(np.isfinite(s), axis=1) & (a > 0) & (cc[:, 4] == 0) & (uw == 0)
    surv = valid & (b > 0)
    received = surv & (c > 0)
    comp = np.full((N, 4), np.nan)
    comp[:, 1] = co
    energy = np.full((N, 3), np.nan)
    energy[:, 0] = .92 * dni * areas * co
    with np.errstate(divide='ignore', invalid='ignore'):
        comp[surv, 2] = b[surv] / (n * co[surv] if raw else a[surv])
        comp[received, 3] = c[received] / b[received]
        comp[received, 0] = .92 * tau[received] * (c[received] / n if raw else co[received] * c[received] / a[received])
        energy[surv, 1] = energy[surv, 0] * b[surv] / a[surv]
        energy[received, 2] = energy[received, 0] * c[received] / a[received]
    p = dni * np.sum(areas * comp[:, 0])
    main = np.r_[comp.mean(0), p, p / areas.sum()]
    area_mean = np.sum(comp * (areas / areas.sum())[:, None], axis=0)
    return main, area_mean, energy, comp


def _valid_stats(s, c, u, levels):
    n = np.asarray(levels)[:, None, None]
    tests = {
        'finite_energy': np.isfinite(s).all(), 'nonnegative_energy': (s >= 0).all(),
        'ordered_energy': ((s[..., 1] <= s[..., 0] + 1e-10) & (s[..., 2] <= s[..., 1] + 1e-10)).all(),
        'integer_nonnegative_counts': (np.isfinite(c).all() and (c == np.rint(c)).all() and (c >= 0).all()),
        'counts_within_samples': (c <= n[..., None]).all(),
        'partition': (c[..., 0] + c[..., 1] + c[..., 2] == n).all(),
        'capture_subset': ((c[..., 3] <= c[..., 2]) & (c[..., 3] <= c[..., 5])).all(),
        'unknown_weight_valid': (np.isfinite(u).all() and (u >= 0).all() and (u <= s[..., 0] + 1e-10).all()),
        'unknown_count_weight_consistent': (((c[..., 4] == 0) & (u == 0)) | ((c[..., 4] > 0) & (u > 0))).all(),
        'survive_count_weight_consistent': (((c[..., 2] == 0) & (np.abs(s[..., 1]) <= 1e-10)) | ((c[..., 2] > 0) & (s[..., 1] > 0))).all(),
        'capture_count_weight_consistent': (((c[..., 3] == 0) & (np.abs(s[..., 2]) <= 1e-10)) | ((c[..., 3] > 0) & (s[..., 2] > 0))).all(),
        'prefix_energy': (np.diff(s, axis=0) >= -1e-10).all(),
        'prefix_counts': (np.diff(c, axis=0) >= 0).all(),
        'prefix_unknown': (np.diff(u, axis=0) >= -1e-10).all(),
    }
    return {k: bool(v) for k, v in tests.items()}


def _jk(point, leave):
    B = len(leave)
    pseudo = B * point - (B - 1) * leave
    se = np.sqrt(np.sum((pseudo - pseudo.mean(0)) ** 2, axis=0) / (B * (B - 1)))
    return pseudo, se


def _energy_rows(energies):
    def each(v):
        out = []
        for numerator, denominator in ((1, 0), (2, 1), (2, 0)):
            x, y = v[..., numerator], v[..., denominator]
            out.append(float(x.sum() / y.sum()) if np.isfinite(x).all() and np.isfinite(y).all() and y.sum() > 0 else np.nan)
        return out
    return np.asarray([each(energies[i*5:i*5+5]) for i in range(12)] + [each(energies)])


def run(budget):
    start = time.perf_counter()
    out = io.OUT / 'delivery'
    out.mkdir(parents=True, exist_ok=True)
    report = {'kind': 'Q03_INDEPENDENT_SAVED_STATISTICS_REBUILD_V001', 'created': io.now(),
              'scope': 'saved-data arithmetic and binding validation, not independent physical validation; no optical rays generated',
              'checks': {}, 'limitations': ['True-zero certificates are unsupported in this independent implementation and force an explicit failure.',
              'Work indicators are approximate pointwise numerical diagnostics; no simultaneous or physical-error guarantee.']}
    checks = report['checks']

    def check(name, condition, evidence=None):
        checks[name] = {'passed': bool(condition), 'evidence': io.convert(evidence)}
        return bool(condition)

    def compare(name, actual, expected):
        a, b = np.asarray(actual, float), np.asarray(expected, float)
        if a.shape != b.shape:
            return check(name, False, {'actual_shape': a.shape, 'expected_shape': b.shape})
        finite = np.isfinite(a) & np.isfinite(b)
        err = float(np.max(np.abs(a[finite] - b[finite]))) if finite.any() else None
        return check(name, np.array_equal(np.isfinite(a), np.isfinite(b)) and np.allclose(a, b, atol=2e-9, rtol=2e-9, equal_nan=True),
                     {'max_abs_difference': err, 'na_pattern_equal': np.array_equal(np.isfinite(a), np.isfinite(b)), 'atol': 2e-9, 'rtol': 2e-9})

    freeze_path = io.OUT / '最终候选与确认冻结-v001.json'
    freeze = io.load(freeze_path)
    cand_name = freeze['candidate']
    report['frozen_candidate'] = cand_name
    report['freeze_sha256'] = io.sha(freeze_path)
    rebuilt = {}

    def rebuild(name):
        folder = io.OUT / 'candidates' / name
        statdir = folder / 'confirmation'
        design = io.load(folder / 'design.json')
        binding = io.load(statdir / 'binding.json')
        summary = io.load(statdir / 'summary.json')
        identity = io.load(folder / 'identity.json')
        domains = io.load(folder / 'domain60.json')
        rows = design['mirrors']
        areas = np.asarray([m['width'] * m['height'] for m in rows], float)
        N, B, n, levels = len(rows), binding['B'], binding['n'], binding['levels']
        prefix_index = levels.index(n // 2)
        prefix = name + ':'
        check(prefix + 'binding_population_time_rng', binding['name'] == name and binding['times'] == TIMES and binding['n_mirrors'] == N
              and B == 8 and n in (256, 512) and levels[-1] == n and binding['namespace'] == 3190 and binding['root_seed'] == 2026090506)
        check(prefix + 'design_hash_and_key', binding['design_file_sha256'] == io.sha(folder/'design.json')
              and binding['design_key'] == _key(design) == identity['key'] and identity['n'] == N and identity['area'] == float(areas.sum()))
        check(prefix + 'declared_mirror_areas', all(m['area'] == float(a) for m, a in zip(rows, areas)))
        check(prefix + 'unique_stable_identity', len({m['mirror_id'] for m in rows}) == N and len({m['position_key'] for m in rows}) == N)
        check(prefix + 'all60_saved_model_domains', len(domains) == 60 and all(
            [r['month'],r['hour']] == TIMES[j] and all(math.isfinite(r['domain'][k]) and r['domain'][k] > 0
            for k in ('distance_min','min_end_start_margin_m','min_front','min_horizon','min_outgoing_axis_dot'))
            and math.isfinite(r['domain']['target_reflection_error']) and r['domain']['target_reflection_error'] <= 1e-10
            for j,r in enumerate(domains)), 'Saved domain margins bound to each independently checked statistics scene key; no new optical evaluation.')
        check(prefix + 'frozen_source_binding', binding['worker_dependency_sha256'] == freeze['execution_sources'])
        for filename, digest in binding['worker_dependency_sha256'].items():
            check(prefix+'source:'+filename, Path(filename).name == filename and (HERE/filename).is_file() and io.sha(HERE/filename) == digest)
        check(prefix+'no_unsupported_certificate_codes', np.asarray(summary.get('certificate_codes')).shape == (60, N)
              and np.all(np.asarray(summary.get('certificate_codes')) == 0))
        main, pre, raw, aw, aw_pre, aw_raw, energies, lows, area_lows = ([] for _ in range(9))
        leave, area_leave = [[] for _ in range(B)], [[] for _ in range(B)]
        hashes, lowcases, count_totals = [], [], np.zeros(6, dtype=np.int64)
        for ti, (month, hour) in enumerate(TIMES):
            budget.guard(12)
            path = statdir / ('time-%02d.npz' % ti)
            meta = io.load(path.with_suffix('.json'))
            digest = io.sha(path)
            check(prefix+'time_%02d_binding'%ti, meta['sha256'] == digest and meta['design_key'] == binding['design_key']
                  and [meta['month'],meta['hour']] == [month,hour] and meta['combinations'] == N and meta['unique_source_samples'] == B*n*N
                  and len(domains) == 60 and domains[ti]['scene_key'] == meta['scene_key'])
            check(prefix+'time_%02d_no_unsupported_certificates'%ti, not meta.get('certificate_records'))
            if meta.get('certificate_records'):
                raise RuntimeError('INDEPENDENT_REBUILD_UNSUPPORTED_TRUE_ZERO_CERTIFICATE:'+name+':'+str(ti))
            hashes.append({'time_index': ti, 'statistics_sha256': digest, 'metadata_sha256': io.sha(path.with_suffix('.json')), 'scene_key': meta['scene_key']})
            with np.load(path, allow_pickle=False) as x:
                ss, cc, uw = x['sums'], x['counts'], x['unknown_weights']
                co, ta, dni = x['cosine'], x['tau'], float(x['dni'])
                shape_ok = ss.shape == (len(levels),B,N,3) and cc.shape == (len(levels),B,N,6) and uw.shape == (len(levels),B,N)
                if not check(prefix+'time_%02d_shapes'%ti, shape_ok): raise ValueError('STATISTICS_SHAPE')
                check(prefix+'time_%02d_area'%ti, np.array_equal(x['areas'], areas))
                check(prefix+'time_%02d_units_range'%ti, co.shape == (N,) and ta.shape == (N,) and np.isfinite(co).all()
                      and np.isfinite(ta).all() and (co>0).all() and (co<=1+1e-10).all() and (ta>0).all() and (ta<=1+1e-10).all() and math.isfinite(dni) and dni>0)
                validation = _valid_stats(ss,cc,uw,levels)
                if not check(prefix+'time_%02d_statistics'%ti, all(validation.values()), validation):
                    raise ValueError('INVALID_SAVED_STATISTICS:'+name+':'+str(ti))
                s,c,u = ss[-1].sum(0),cc[-1].sum(0),uw[-1].sum(0)
                count_totals += c.sum(0)
                state = np.zeros(N,np.int8)
                state[(s[:,1]<=0)] = 4
                state[(s[:,1]>0)&(s[:,2]<=0)] = 5
                state[(c[:,4]>0)|(u>0)] = 6
                state[s[:,0]<=0] = 7
                compare(prefix+'time_%02d_pooled_states'%ti,state,summary['pooled_state_codes'][ti])
                v,a,en,comps = _one(s,c,u,co,ta,dni,areas,B*n)
                p,ap,_,_ = _one(ss[prefix_index].sum(0),cc[prefix_index].sum(0),uw[prefix_index].sum(0),co,ta,dni,areas,B*levels[prefix_index])
                r,ar,_,_ = _one(s,c,u,co,ta,dni,areas,B*n,raw=True)
                main.append(v);aw.append(a);energies.append(en);pre.append(p);aw_pre.append(ap);raw.append(r);aw_raw.append(ar)
                for batch in range(B):
                    # Sum the remaining independent batches directly, avoiding subtractive cancellation.
                    keep = np.arange(B) != batch
                    vj,aj,_,_ = _one(ss[-1,keep].sum(0),cc[-1,keep].sum(0),uw[-1,keep].sum(0),co,ta,dni,areas,(B-1)*n)
                    leave[batch].append(vj);area_leave[batch].append(aj)
                mask = c[:,2] < 100
                compbound = np.zeros((N,4));compbound[mask,0] = .92*co[mask]*ta[mask];compbound[mask,2:] = 1
                pbound = float(np.sum(dni*areas[mask]*.92*co[mask]*ta[mask]))
                lows.append(np.r_[compbound.sum(0)/N,pbound,pbound/areas.sum()])
                area_lows.append(np.sum(compbound*(areas/areas.sum())[:,None],axis=0))
                for j in np.flatnonzero(mask):
                    lowcases.append({'time_index':ti,'object_index':int(j),'object_id':rows[j]['mirror_id'],'area_m2':float(areas[j]),'survive':int(c[j,2]),'capture':int(c[j,3]),'unknown':int(c[j,4])})
                prod = comps[:,2]*co*ta*comps[:,3]*.92
                compare(prefix+'time_%02d_factor_direct_relation'%ti,prod,comps[:,0])
        point, pp, rr = _rows(main),_rows(pre),_rows(raw)
        aa, aa_pre, aa_raw = _rows(aw),_rows(aw_pre),_rows(aw_raw)
        lp = np.asarray([_rows(v) for v in leave]);al = np.asarray([_rows(v) for v in area_leave])
        pseudo,se = _jk(point,lp);area_pseudo,area_se = _jk(aa,al)
        low,alow = _rows(lows),_rows(area_lows)
        baseu = np.maximum.reduce([T7*se,np.abs(point-pp),np.abs(point-rr)])
        U = baseu+low
        au = np.maximum.reduce([T7*area_se,np.abs(aa-aa_pre),np.abs(aa-aa_raw)])+alow
        rebuilt_fields = {'point':point,'formal_h02_rows':point,'temporal_point':main,'prefix_half_point':pp,'raw_integral_alternative':rr,
                          'leave_one_batch_estimates':lp,'pseudo_values':pseudo,'jackknife_se':se,'approx_pointwise_t7_95_halfwidth':T7*se,
                          'base_numeric_work_indicator':baseu,'conservative_work_indicator':U}
        for k,v in rebuilt_fields.items():compare(prefix+'main:'+k,v,summary[k])
        compare(prefix+'low_survival_bound',low,summary['low_survival']['effect_diameter_bound'])
        check(prefix+'low_survival_cases',len(lowcases)==summary['low_survival']['screened_count']
              and {(v['time_index'],v['object_index'],v['survive']) for v in lowcases}=={(v['time_index'],v['object_index'],v['survive']) for v in summary['low_survival']['cases']})
        aux = summary['area_weighted_efficiencies']
        for k,v in {'point':aa,'temporal_point':aw,'prefix_half_point':aa_pre,'raw_integral_alternative':aa_raw,'leave_one_batch_estimates':al,
                    'pseudo_values':area_pseudo,'jackknife_se':area_se,'conservative_work_indicator':au}.items():compare(prefix+'area:'+k,v,aux[k])
        compare(prefix+'area_low_bound',alow,aux['low_survival']['effect_diameter_bound'])
        er = _energy_rows(np.asarray(energies))
        compare(prefix+'energy_ratios',er,summary['energy_total_ratios']['values'])
        compare(prefix+'area_power_relation',point[:,5]*areas.sum(),point[:,4])
        defined = bool(np.isfinite(point).all() and np.isfinite(U).all() and count_totals[4] == 0)
        target = np.zeros((13,6),bool)
        target[:,:4] = np.isfinite(U[:,:4]) & (U[:,:4] <= .001) & np.isfinite(point[:,:4])
        with np.errstate(divide='ignore',invalid='ignore'):
            target[:,4:] = np.isfinite(U[:,4:]) & (np.abs(point[:,4:])>0) & (U[:,4:]/np.abs(point[:,4:])<=.005)
        rating = bool(defined and point[-1,4]-U[-1,4]>=60000.)
        compare(prefix+'target_matrix',target,summary['target_pass'])
        check(prefix+'formal_ready_matches',defined==summary['formal_ready'])
        check(prefix+'precision_matches',bool(target.all())==summary['all_table_items_precision_met'])
        check(prefix+'rating_matches',rating==summary['rated_power_met'])
        check(prefix+'no_unknown_counts',count_totals[4]==0,{'counts_totals':count_totals})
        return {'name':name,'design':design,'binding':binding,'point':point,'prefix':pp,'raw':rr,'leave':lp,'U':U,'low':low,
                'area_point':aa,'area_U':au,'energy_ratios':er,'formal_ready':defined,'precision_met':bool(target.all()),'rated_power_met':rating,
                'low_survival_cases':lowcases,'statistics_files':hashes,'source_hashes':{'design.json':io.sha(folder/'design.json'),
                'binding.json':io.sha(statdir/'binding.json'),'summary.json':io.sha(statdir/'summary.json')},'population':N,'area':float(areas.sum())}

    paired = {'kind':'Q03_NEW_PAIRED_CONFIRMATION_V001','candidate':cand_name,'baseline':'Q3R000','improvement_supported':False}
    try:
        for name in [cand_name,'Q3R000']:
            rebuilt[name] = rebuild(name)
        c,b = rebuilt[cand_name],rebuilt['Q3R000']
        check('candidate_freeze_file',io.sha(io.OUT/'candidates'/cand_name/'design.json')==freeze['frozen_design_sha256']
              and c['binding']['design_key']==freeze['frozen_design_key'])
        cb,bb = c['binding'],b['binding']
        same = all(cb[k]==bb[k] for k in ('times','B','n','levels','namespace','root_seed','rng','worker_dependency_sha256'))
        same = same and [(v['mirror_id'],v['position_key'],v['x'],v['y'],v['group']) for v in c['design']['mirrors']]==[(v['mirror_id'],v['position_key'],v['x'],v['y'],v['group']) for v in b['design']['mirrors']]
        check('paired_stream_identity',same,'same batch/time/position-key seeds; dimensions change physical source mapping but not the underlying uniform variates')
        delta = c['point'][-1,5]-b['point'][-1,5]
        leave_delta = c['leave'][:,-1,5]-b['leave'][:,-1,5]
        pseudo,se = _jk(delta,leave_delta)
        dp = c['prefix'][-1,5]-b['prefix'][-1,5]
        dr = c['raw'][-1,5]-b['raw'][-1,5]
        low_sum = c['low'][-1,5]+b['low'][-1,5]
        ud = max(T7*float(se),abs(float(delta-dp)),abs(float(delta-dr)))+low_sum
        pair_defined = same and c['formal_ready'] and b['formal_ready'] and np.isfinite(ud) and np.isfinite(delta)
        paired.update(delta_q_kw_m2=float(delta),delta_power_kw=float(c['point'][-1,4]-b['point'][-1,4]),
                      baseline_q_kw_m2=float(b['point'][-1,5]),candidate_q_kw_m2=float(c['point'][-1,5]),
                      relative_q_difference=float(delta/b['point'][-1,5]),paired_leave_estimates=leave_delta,paired_pseudo_values=pseudo,
                      paired_jackknife_se=float(se),paired_t7_term=float(T7*se),prefix_delta=float(dp),raw_delta=float(dr),
                      low_survival_q_bound_sum=float(low_sum),work_indicator_delta_q=float(ud),difference_minus_work_indicator=float(delta-ud),
                      paired_identity_valid=same,improvement_supported=bool(pair_defined and delta>ud),
                      method='paired whole-batch delete-one jackknife; max(t7 SE, paired-prefix shift, paired-raw shift)+sum of separate actual-area low-survival bounds; pointwise numerical work evidence, not confidence or physical-error guarantee')
        import q03_delivery_v001 as delivery
        import q03_design_v001 as design_module
        xlsx = io.OUT / freeze['xlsx']
        check('actual_excel_sha256',io.sha(xlsx)==freeze['xlsx_sha256'])
        back = delivery.read_excel(xlsx,c['design'])
        check('actual_excel_exact_payload',back==c['design'])
        geom = design_module.validate_design(back)
        check('actual_excel_reconstructed_geometry',geom['accepted'],geom)
        report['excel'] = {'path':str(xlsx.relative_to(io.OUT)),'sha256':io.sha(xlsx),'geometry':geom,'exact_frozen_payload':back==c['design']}
        report['reconstructed'] = {name:{k:v for k,v in item.items() if k not in ('design','binding','leave')} for name,item in rebuilt.items()}
    except Exception as exc:
        report['failure'] = {'type':type(exc).__name__,'message':str(exc)}
        check('completed_without_exception',False,report['failure'])
    all_pass = bool(checks and all(v['passed'] for v in checks.values()))
    c = rebuilt.get(cand_name,{})
    formal_ready = bool(all_pass and c.get('formal_ready') and c.get('precision_met') and c.get('rated_power_met'))
    paired['improvement_supported'] = bool(all_pass and paired.get('improvement_supported'))
    report.update(all_pass=all_pass,formal_ready=formal_ready,improvement_supported=paired['improvement_supported'],
                  elapsed_seconds=time.perf_counter()-start,implementation_sha256=io.sha(Path(__file__)))
    report_path=out/'独立重建核验-v001.json';pair_path=out/'paired-comparison-v001.json'
    io.save(pair_path,paired);io.save(report_path,report);budget.tick()
    return {'all_pass':all_pass,'formal_ready':formal_ready,'improvement_supported':paired['improvement_supported'],
            'report':str(report_path),'paired':str(pair_path),'elapsed_seconds':report['elapsed_seconds']}
