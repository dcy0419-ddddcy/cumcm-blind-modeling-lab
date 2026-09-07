"""Q3 heterogeneous-area summary from in-memory sufficient statistics only.

This module deliberately has no runner, geometry, filesystem, or Q1 imports.  A
caller supplies already-bound arrays.  ``full_confirmation`` is the only mode
that produces a 60 MW decision; ``full_comparison`` gives 12-month/annual
estimates without a rating. ``heuristic`` gives per-time diagnostics only.
The main H02 table remains mirror-count weighted. Area-weighted efficiencies
are a separate auxiliary population and never enter its mandatory gate.

Array contract
--------------
``sums`` has shape ``(L,B,T,N,3)`` for ``sum(g)``, ``sum(g*SB)``, and
``sum(g*SBR)``.  ``counts`` has shape ``(L,B,T,N,6)`` with columns listed in
``COUNT_LABELS``.  Each level is a nested prefix with ``levels_n[l]`` rays per
batch/object/time.  ``unknown_weights`` has shape ``(L,B,T,N)``.

True-zero results are never accepted as caller-supplied Boolean masks.  Optional
certificate records must carry a bound scene key, a pinned source hash, and the
complete geometric certificate emitted by the evaluator; this module checks
that evidence again before it changes a sampled-zero state.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence

import numpy as np


RHO = 0.92
T7_975 = 2.3646242515927844
LABELS = (
    "optical",
    "cosine",
    "shadow_blocking",
    "truncation",
    "power_kw",
    "unit_power_kw_m2",
)
COUNT_LABELS = (
    "shadow",
    "blocked_after_unshadowed",
    "survive",
    "capture",
    "unknown",
    "raw_R",
)
STANDARD_MONTHS = np.repeat(np.arange(1, 13, dtype=np.int64), 5)
STANDARD_HOURS = np.tile(np.array([9.0, 10.5, 12.0, 13.5, 15.0]), 12)

CERT_NONE = 0
CERT_ZERO_SURVIVOR = 1
CERT_ZERO_CAPTURE = 2
CERT_ZERO_CAPTURE_SURVIVOR_ONE = 3
CERTIFICATE_CODES = {
    CERT_NONE: "NONE",
    CERT_ZERO_SURVIVOR: "TRUE_ZERO_SURVIVOR",
    CERT_ZERO_CAPTURE: "TRUE_ZERO_CAPTURE",
    CERT_ZERO_CAPTURE_SURVIVOR_ONE: "TRUE_ZERO_CAPTURE_SURVIVOR_ONE",
}

STATE_ESTIMATED = 0
STATE_TRUE_ZERO_SURVIVOR = 1
STATE_TRUE_ZERO_CAPTURE = 2
STATE_TRUE_ZERO_CAPTURE_SURVIVOR_ONE = 3
STATE_SAMPLED_ZERO_SURVIVOR = 4
STATE_SAMPLED_ZERO_CAPTURE = 5
STATE_BOUNDARY_UNCERTAIN = 6
STATE_ZERO_PRIMARY_DENOMINATOR = 7
STATE_INVALID_STATISTICS = 8
STATE_CERTIFICATE_CONTRADICTION = 9
STATE_CERTIFICATE_WITH_UNKNOWN = 10
STATE_CODES = {
    STATE_ESTIMATED: "ESTIMATED",
    STATE_TRUE_ZERO_SURVIVOR: "TRUE_ZERO_SURVIVOR",
    STATE_TRUE_ZERO_CAPTURE: "TRUE_ZERO_CAPTURE",
    STATE_TRUE_ZERO_CAPTURE_SURVIVOR_ONE: "TRUE_ZERO_CAPTURE_SURVIVOR_ONE",
    STATE_SAMPLED_ZERO_SURVIVOR: "SAMPLED_ZERO_SURVIVOR",
    STATE_SAMPLED_ZERO_CAPTURE: "SAMPLED_ZERO_CAPTURE",
    STATE_BOUNDARY_UNCERTAIN: "BOUNDARY_UNCERTAIN",
    STATE_ZERO_PRIMARY_DENOMINATOR: "ZERO_PRIMARY_DENOMINATOR",
    STATE_INVALID_STATISTICS: "INVALID_STATISTICS",
    STATE_CERTIFICATE_CONTRADICTION: "CERTIFICATE_CONTRADICTION",
    STATE_CERTIFICATE_WITH_UNKNOWN: "CERTIFICATE_WITH_UNKNOWN",
}

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ORDER_ATOL = 1.0e-10


class SummaryInputError(ValueError):
    """Structural input failure for the summary interface."""


def jsonable(value):
    """Convert module output to strict-JSON-compatible Python values."""
    if isinstance(value, np.ndarray):
        return jsonable(value.tolist())
    if isinstance(value, np.generic):
        return jsonable(value.item())
    if isinstance(value, Mapping):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [jsonable(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _require_sha256(value, name):
    text = str(value).lower()
    if _SHA256.fullmatch(text) is None:
        raise SummaryInputError(f"{name} must be a lowercase 64-character SHA-256")
    return text


def _verify_cap_evidence(cap):
    if not isinstance(cap, Mapping):
        return False, "cap evidence is not a mapping"
    if cap.get("proof") != "source_ball_to_cap_interior_v001":
        return False, "unsupported cap proof"
    required = (
        "source_radius_m",
        "source_plane_gap_m",
        "axis_to_vertical_plus_beta_rad",
        "radial_upper_m",
        "cap_radius_m",
        "strict_margin_m",
    )
    try:
        vals = {k: float(cap[k]) for k in required}
    except (KeyError, TypeError, ValueError):
        return False, "missing or nonnumeric cap evidence"
    if not all(math.isfinite(v) for v in vals.values()):
        return False, "nonfinite cap evidence"
    radius = vals["source_radius_m"]
    gap = vals["source_plane_gap_m"]
    theta = vals["axis_to_vertical_plus_beta_rad"]
    radial = vals["radial_upper_m"]
    cap_radius = vals["cap_radius_m"]
    margin = vals["strict_margin_m"]
    if radius < 0 or gap <= radius:
        return False, "source ball is not strictly before the cap"
    if not 0 <= theta < math.pi / 2:
        return False, "cone enclosure is not forward toward a finite cap"
    if radial < 0 or cap_radius <= 0 or radial >= cap_radius or margin <= 0:
        return False, "radial cap enclosure is not strict"
    scale = max(1.0, abs(cap_radius), abs(radial), abs(margin))
    if abs((cap_radius - radial) - margin) > 1.0e-12 * scale:
        return False, "strict cap margin is internally inconsistent"
    if cap.get("side") not in {"top", "bottom"}:
        return False, "cap side is missing"
    return True, "verified"


def _verified_certificate_codes(
    certificate_records,
    scene_keys,
    trusted_certificate_sources,
    T,
    N,
):
    codes = np.zeros((T, N), dtype=np.int8)
    audit = {"accepted": [], "rejected": [], "all_valid": True}
    if certificate_records is None:
        audit["note"] = "no true-zero certificates supplied; sampled zeros remain unresolved"
        return codes, audit
    if isinstance(certificate_records, (str, bytes, Mapping)):
        raise SummaryInputError("certificate_records must be a sequence of full evidence records")
    if scene_keys is None or trusted_certificate_sources is None:
        raise SummaryInputError("certificate records require scene_keys and trusted source hashes")
    scene_keys = list(scene_keys)
    if len(scene_keys) != T:
        raise SummaryInputError("scene_keys must have length T")
    scene_keys = [_require_sha256(x, f"scene_keys[{i}]") for i, x in enumerate(scene_keys)]
    trusted = {
        str(name): _require_sha256(sha, f"trusted_certificate_sources[{name!r}]")
        for name, sha in dict(trusted_certificate_sources).items()
    }
    occupied = set()
    for record_index, wrapper in enumerate(certificate_records):
        reason = None
        try:
            if not isinstance(wrapper, Mapping):
                raise SummaryInputError("record is not a mapping")
            ti = int(wrapper["time_index"])
            mi = int(wrapper["mirror_index"])
            if not 0 <= ti < T or not 0 <= mi < N:
                raise SummaryInputError("time/object index out of range")
            if (ti, mi) in occupied:
                raise SummaryInputError("duplicate certificate for one time/object")
            outer_scene = _require_sha256(wrapper["scene_sha256"], "certificate scene_sha256")
            if outer_scene != scene_keys[ti]:
                raise SummaryInputError("certificate scene key does not match supplied time binding")
            source = wrapper["source"]
            if not isinstance(source, Mapping):
                raise SummaryInputError("certificate source is not a mapping")
            source_name = str(source["name"])
            source_sha = _require_sha256(source["sha256"], "certificate source sha256")
            if source_name not in trusted or trusted[source_name] != source_sha:
                raise SummaryInputError("certificate source is not pinned by the caller")
            cert = wrapper["certificate"]
            if not isinstance(cert, Mapping):
                raise SummaryInputError("certificate payload is not a mapping")
            if _require_sha256(cert.get("scene_sha256"), "payload scene_sha256") != outer_scene:
                raise SummaryInputError("payload scene binding differs")
            if int(cert.get("mirror_index", -1)) != mi:
                raise SummaryInputError("payload object binding differs")
            kind = cert.get("kind")
            if kind == "zero_survivor":
                ok, why = _verify_cap_evidence(cert.get("incoming_cap"))
                if not ok:
                    raise SummaryInputError(why)
                code = CERT_ZERO_SURVIVOR
            elif kind == "zero_capture":
                ok, why = _verify_cap_evidence(cert.get("outgoing_cap"))
                if not ok:
                    raise SummaryInputError(why)
                survivor_flag = cert.get("survivor_identically_one", False)
                if survivor_flag not in {True, False}:
                    raise SummaryInputError("survivor_identically_one must be a Boolean evidence field")
                survivor_one = survivor_flag is True
                if survivor_one:
                    miss = cert.get("incoming_receiver_miss")
                    candidates = cert.get("candidate_counts")
                    if not isinstance(miss, Mapping) or miss.get("proven") is not True:
                        raise SummaryInputError("survivor-one certificate lacks receiver-miss proof")
                    if list(candidates or ()) != [0, 0]:
                        raise SummaryInputError("survivor-one certificate has nonempty candidates")
                    code = CERT_ZERO_CAPTURE_SURVIVOR_ONE
                else:
                    code = CERT_ZERO_CAPTURE
            else:
                raise SummaryInputError("unsupported or unproven certificate kind")
            codes[ti, mi] = code
            occupied.add((ti, mi))
            audit["accepted"].append(
                {
                    "record_index": record_index,
                    "time_index": ti,
                    "mirror_index": mi,
                    "scene_sha256": outer_scene,
                    "source": {"name": source_name, "sha256": source_sha},
                    "kind": CERTIFICATE_CODES[code],
                }
            )
        except (KeyError, TypeError, ValueError, SummaryInputError) as exc:
            reason = str(exc)
        if reason is not None:
            audit["rejected"].append({"record_index": record_index, "reason": reason})
    audit["all_valid"] = len(audit["rejected"]) == 0
    audit["accepted_count"] = len(audit["accepted"])
    audit["rejected_count"] = len(audit["rejected"])
    return codes, audit


def _validate_arrays(sums, counts, unknown_weights, levels_n):
    """Return per-level/batch bad masks and non-destructive validation evidence."""
    L, B, T, N, _ = sums.shape
    ngrid = levels_n[:, None, None, None]
    energy_nonfinite = ~np.all(np.isfinite(sums), axis=-1)
    energy_negative = np.any(sums < 0, axis=-1)
    energy_order = (sums[..., 1] > sums[..., 0] + _ORDER_ATOL) | (
        sums[..., 2] > sums[..., 1] + _ORDER_ATOL
    )
    counts_nonfinite = ~np.all(np.isfinite(counts), axis=-1)
    rounded = np.rint(np.where(np.isfinite(counts), counts, 0.0))
    counts_noninteger = np.any(np.abs(np.where(np.isfinite(counts), counts, 0.0) - rounded) > 0, axis=-1)
    counts_negative = np.any(counts < 0, axis=-1)
    counts_above_n = np.any(counts > ngrid[..., None], axis=-1)
    partition_bad = np.abs(counts[..., 0] + counts[..., 1] + counts[..., 2] - ngrid) > 0
    capture_bad = counts[..., 3] > counts[..., 2]
    raw_receiver_bad = counts[..., 3] > counts[..., 5]
    unknown_nonfinite = ~np.isfinite(unknown_weights)
    unknown_negative = unknown_weights < 0
    unknown_above_total = unknown_weights > sums[..., 0] + _ORDER_ATOL
    unknown_mismatch = ((counts[..., 4] == 0) & (unknown_weights > 0)) | (
        (counts[..., 4] > 0) & (unknown_weights <= 0)
    )
    survivor_sum_mismatch = ((counts[..., 2] == 0) & (np.abs(sums[..., 1]) > _ORDER_ATOL)) | (
        (counts[..., 2] > 0) & (sums[..., 1] <= 0)
    )
    capture_sum_mismatch = ((counts[..., 3] == 0) & (np.abs(sums[..., 2]) > _ORDER_ATOL)) | (
        (counts[..., 3] > 0) & (sums[..., 2] <= 0)
    )
    bad = (
        energy_nonfinite
        | energy_negative
        | energy_order
        | counts_nonfinite
        | counts_noninteger
        | counts_negative
        | counts_above_n
        | partition_bad
        | capture_bad
        | raw_receiver_bad
        | unknown_nonfinite
        | unknown_negative
        | unknown_above_total
        | unknown_mismatch
        | survivor_sum_mismatch
        | capture_sum_mismatch
    )
    nested_bad = np.zeros((B, T, N), dtype=bool)
    if L > 1:
        nested_energy = np.any(np.diff(sums, axis=0) < -_ORDER_ATOL, axis=-1)
        nested_counts = np.any(np.diff(counts, axis=0) < 0, axis=-1)
        nested_unknown = np.diff(unknown_weights, axis=0) < -_ORDER_ATOL
        nested_bad = np.any(nested_energy | nested_counts | nested_unknown, axis=0)
    evidence = {
        "energy_nonfinite": int(energy_nonfinite.sum()),
        "energy_negative": int(energy_negative.sum()),
        "energy_order_violation": int(energy_order.sum()),
        "counts_nonfinite": int(counts_nonfinite.sum()),
        "counts_noninteger": int(counts_noninteger.sum()),
        "counts_negative": int(counts_negative.sum()),
        "counts_above_level_n": int(counts_above_n.sum()),
        "shadow_block_survive_partition_violation": int(partition_bad.sum()),
        "capture_above_survive": int(capture_bad.sum()),
        "capture_above_raw_R": int(raw_receiver_bad.sum()),
        "unknown_weight_nonfinite": int(unknown_nonfinite.sum()),
        "unknown_weight_negative": int(unknown_negative.sum()),
        "unknown_weight_above_total_weight": int(unknown_above_total.sum()),
        "unknown_count_weight_mismatch": int(unknown_mismatch.sum()),
        "survivor_count_weight_mismatch": int(survivor_sum_mismatch.sum()),
        "capture_count_weight_mismatch": int(capture_sum_mismatch.sum()),
        "prefix_nesting_violation": int(nested_bad.sum()),
    }
    evidence["all_valid"] = not any(v for k, v in evidence.items() if k != "all_valid")
    return bad, nested_bad, evidence, rounded.astype(np.int64)


def _object_metrics(sums, counts, unknown_weights, cosine, tau, dni, areas, n_total, cert_codes, bad):
    """Build formal object metrics while preserving state and total/component distinctions."""
    T, N, _ = sums.shape
    a, b, c = np.moveaxis(sums, -1, 0)
    state = np.full((T, N), STATE_ESTIMATED, dtype=np.int8)
    total_defined = np.zeros((T, N), dtype=bool)
    components = np.full((T, N, 4), np.nan, dtype=float)
    components[..., 1] = cosine
    powers = np.full((T, N), np.nan, dtype=float)
    f1 = np.full((T, N), np.nan, dtype=float)
    f2 = np.full((T, N), np.nan, dtype=float)
    pi1 = np.full((T, N), np.nan, dtype=float)
    pi2 = np.full((T, N), np.nan, dtype=float)
    unknown = (counts[..., 4] > 0) | (unknown_weights > 0)
    primary_zero = a <= 0
    invalid = np.asarray(bad, dtype=bool)

    state[invalid] = STATE_INVALID_STATISTICS
    state[~invalid & primary_zero] = STATE_ZERO_PRIMARY_DENOMINATOR
    eligible = ~invalid & ~primary_zero
    has_cert = cert_codes != CERT_NONE
    state[eligible & has_cert & unknown] = STATE_CERTIFICATE_WITH_UNKNOWN

    zsurv = eligible & ~unknown & (cert_codes == CERT_ZERO_SURVIVOR)
    zcap = eligible & ~unknown & (cert_codes == CERT_ZERO_CAPTURE)
    zone = eligible & ~unknown & (cert_codes == CERT_ZERO_CAPTURE_SURVIVOR_ONE)
    contradiction_zsurv = zsurv & (
        (np.abs(b) > _ORDER_ATOL)
        | (np.abs(c) > _ORDER_ATOL)
        | (counts[..., 2] != 0)
        | (counts[..., 3] != 0)
    )
    contradiction_zcap = zcap & ((np.abs(c) > _ORDER_ATOL) | (counts[..., 3] != 0))
    contradiction_zone = zone & (
        (np.abs(c) > _ORDER_ATOL)
        | (np.abs(b - a) > _ORDER_ATOL)
        | (counts[..., 0] != 0)
        | (counts[..., 1] != 0)
        | (counts[..., 2] != n_total)
        | (counts[..., 3] != 0)
    )
    contradiction = contradiction_zsurv | contradiction_zcap | contradiction_zone
    state[contradiction] = STATE_CERTIFICATE_CONTRADICTION

    ordinary = eligible & ~has_cert
    state[ordinary & unknown] = STATE_BOUNDARY_UNCERTAIN
    ordinary_known = ordinary & ~unknown
    sampled_zero_survivor = ordinary_known & (b <= 0)
    sampled_zero_capture = ordinary_known & (b > 0) & (c <= 0)
    estimated = ordinary_known & (b > 0) & (c > 0)
    state[sampled_zero_survivor] = STATE_SAMPLED_ZERO_SURVIVOR
    state[sampled_zero_capture] = STATE_SAMPLED_ZERO_CAPTURE

    with np.errstate(divide="ignore", invalid="ignore"):
        ratio1 = b / a
        ratio2 = c / a
        trunc = c / b
    p0 = RHO * dni[:, None] * areas[None, :] * cosine

    f1[estimated | sampled_zero_capture] = ratio1[estimated | sampled_zero_capture]
    f2[estimated] = ratio2[estimated]
    components[..., 2][estimated | sampled_zero_capture] = ratio1[estimated | sampled_zero_capture]
    components[..., 3][estimated] = trunc[estimated]
    components[..., 0][estimated] = (RHO * cosine * tau * ratio2)[estimated]
    powers[estimated] = (dni[:, None] * areas[None, :] * components[..., 0])[estimated]
    pi1[estimated | sampled_zero_capture] = (p0 * ratio1)[estimated | sampled_zero_capture]
    pi2[estimated] = (p0 * ratio2)[estimated]
    total_defined[estimated] = True

    valid_zsurv = zsurv & ~contradiction
    state[valid_zsurv] = STATE_TRUE_ZERO_SURVIVOR
    f1[valid_zsurv] = 0.0
    f2[valid_zsurv] = 0.0
    components[..., 2][valid_zsurv] = 0.0
    components[..., 0][valid_zsurv] = 0.0
    powers[valid_zsurv] = 0.0
    pi1[valid_zsurv] = 0.0
    pi2[valid_zsurv] = 0.0
    total_defined[valid_zsurv] = True

    valid_zcap = zcap & ~contradiction
    state[valid_zcap] = STATE_TRUE_ZERO_CAPTURE
    f2[valid_zcap] = 0.0
    components[..., 0][valid_zcap] = 0.0
    powers[valid_zcap] = 0.0
    pi2[valid_zcap] = 0.0
    total_defined[valid_zcap] = True
    zcap_with_survival = valid_zcap & (b > 0)
    f1[zcap_with_survival] = ratio1[zcap_with_survival]
    components[..., 2][zcap_with_survival] = ratio1[zcap_with_survival]
    components[..., 3][zcap_with_survival] = 0.0
    pi1[zcap_with_survival] = (p0 * ratio1)[zcap_with_survival]

    valid_zone = zone & ~contradiction
    state[valid_zone] = STATE_TRUE_ZERO_CAPTURE_SURVIVOR_ONE
    f1[valid_zone] = 1.0
    f2[valid_zone] = 0.0
    components[..., 2][valid_zone] = 1.0
    components[..., 3][valid_zone] = 0.0
    components[..., 0][valid_zone] = 0.0
    powers[valid_zone] = 0.0
    pi1[valid_zone] = p0[valid_zone]
    pi2[valid_zone] = 0.0
    total_defined[valid_zone] = True

    return {
        "components": components,
        "powers": powers,
        "f1": f1,
        "f2": f2,
        "pi0": p0,
        "pi1": pi1,
        "pi2": pi2,
        "state": state,
        "total_defined": total_defined,
        "component_defined": np.isfinite(components),
        "unknown": unknown,
    }


def _raw_object_metrics(sums, counts, cosine, tau, dni, areas, n_total, formal):
    """Raw-integration alternative, masked by the same formal state policy."""
    a, b, c = np.moveaxis(sums, -1, 0)
    state = formal["state"]
    raw = np.full_like(formal["components"], np.nan)
    raw[..., 1] = cosine
    powers = np.full_like(formal["powers"], np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        raw_sb = (b / n_total) / cosine
        raw_net = (c / n_total) / cosine
        raw_trunc = c / b
    raw_opt = RHO * cosine * tau * raw_net
    estimated = state == STATE_ESTIMATED
    sampled_capture = state == STATE_SAMPLED_ZERO_CAPTURE
    raw[..., 2][estimated | sampled_capture] = raw_sb[estimated | sampled_capture]
    raw[..., 3][estimated] = raw_trunc[estimated]
    raw[..., 0][estimated] = raw_opt[estimated]
    powers[estimated] = (dni[:, None] * areas[None, :] * raw_opt)[estimated]

    zsurv = state == STATE_TRUE_ZERO_SURVIVOR
    raw[..., 0][zsurv] = 0.0
    raw[..., 2][zsurv] = 0.0
    powers[zsurv] = 0.0
    zcap = state == STATE_TRUE_ZERO_CAPTURE
    zcap_survive = zcap & (b > 0)
    raw[..., 0][zcap] = 0.0
    powers[zcap] = 0.0
    raw[..., 2][zcap_survive] = raw_sb[zcap_survive]
    raw[..., 3][zcap_survive] = 0.0
    zone = state == STATE_TRUE_ZERO_CAPTURE_SURVIVOR_ONE
    raw[..., 0][zone] = 0.0
    raw[..., 2][zone] = 1.0
    raw[..., 3][zone] = 0.0
    powers[zone] = 0.0
    return {"components": raw, "powers": powers}


def _strict_mean(values, axis):
    values = np.asarray(values, dtype=float)
    finite = np.all(np.isfinite(values), axis=axis)
    with np.errstate(invalid="ignore"):
        mean = np.mean(values, axis=axis)
    return np.where(finite, mean, np.nan)


def _temporal_population(metrics, total_area):
    comp = metrics["components"]
    power = metrics["powers"]
    temporal_comp = _strict_mean(comp, axis=1)
    temporal_power = np.where(np.all(np.isfinite(power), axis=1), np.sum(power, axis=1), np.nan)
    return np.column_stack(
        [temporal_comp, temporal_power, temporal_power / total_area]
    )


def _h02_rows(temporal):
    if temporal.shape != (60, 6):
        raise SummaryInputError("formal H02 rows require exactly 60 standard-order times")
    monthly = _strict_mean(temporal.reshape(12, 5, 6), axis=1)
    annual = _strict_mean(temporal, axis=0)[None, :]
    return np.vstack([monthly, annual])


def _area_temporal(metrics, areas):
    """Strict fixed-population area mean; no dropping even tiny NA objects."""
    components = metrics["components"]
    weights = areas / areas.sum()
    valid = np.all(np.isfinite(components), axis=1)
    values = np.sum(components * weights[None, :, None], axis=1)
    return np.where(valid, values, np.nan)


def _area_rows(temporal):
    if temporal.shape != (60, 4):
        raise SummaryInputError("area summaries require exactly 60 standard-order times")
    return np.vstack([_strict_mean(temporal.reshape(12, 5, 4), axis=1),
                      _strict_mean(temporal, axis=0)[None, :]])


def _summaries_for_pool(sums, counts, unknown_weights, cosine, tau, dni, areas, n_total, cert_codes, bad):
    formal = _object_metrics(
        sums, counts, unknown_weights, cosine, tau, dni, areas, n_total, cert_codes, bad
    )
    temporal = _temporal_population(formal, float(areas.sum()))
    return formal, temporal, _h02_rows(temporal)


def _state_counts(state):
    return {STATE_CODES[k]: int(np.sum(state == k)) for k in STATE_CODES}


def _state_cases(state, months, hours, object_ids, counts=None, unknown_weights=None, sums=None):
    rows = []
    for ti, mi in np.argwhere(state != STATE_ESTIMATED):
        row = {
            "time_index": int(ti),
            "month": int(months[ti]),
            "hour": float(hours[ti]),
            "object_index": int(mi),
            "object_id": jsonable(object_ids[mi]),
            "state": STATE_CODES[int(state[ti, mi])],
        }
        if counts is not None:
            row["counts"] = {COUNT_LABELS[j]: int(counts[ti, mi, j]) for j in range(6)}
        if unknown_weights is not None:
            row["unknown_weight"] = float(unknown_weights[ti, mi])
        if sums is not None:
            row["sums"] = [float(x) for x in sums[ti, mi]]
        rows.append(row)
    return rows


def _energy_total_ratios(formal):
    p0, p1, p2 = formal["pi0"], formal["pi1"], formal["pi2"]

    def one(indices):
        x, y, z = p0[indices], p1[indices], p2[indices]
        def ratio(numerator, denominator):
            if not (np.all(np.isfinite(numerator)) and np.all(np.isfinite(denominator))):
                return np.nan
            sn, sd = float(numerator.sum()), float(denominator.sum())
            return sn / sd if math.isfinite(sn) and math.isfinite(sd) and sd > 0 else np.nan
        # Each ratio depends only on its own energy quantities. In particular,
        # undefined Pi1 must not hide a independently known Pi2/Pi0 true zero.
        return [ratio(y, x), ratio(z, y), ratio(z, x)]

    rows = [one(slice(m * 5, (m + 1) * 5)) for m in range(12)]
    rows.append(one(slice(None)))
    return np.asarray(rows, dtype=float)


def _low_survival_bound(
    pooled_counts,
    formal,
    certificate_codes,
    cosine,
    tau,
    dni,
    areas,
    months,
    hours,
    object_ids,
    threshold,
    area_weighted=False,
    include_cases=True,
):
    survive = pooled_counts[..., 2]
    low = survive < threshold
    F = RHO * cosine * tau
    T, N = survive.shape
    comp_bound = np.zeros((T, N, 4), dtype=float)
    power_bound = np.zeros((T, N), dtype=float)
    # Default coordinatewise feasible diameters for every screened estimate or
    # unresolved sample.  Exact certificate dimensions are removed below.
    comp_bound[..., 0][low] = F[low]
    comp_bound[..., 2][low] = 1.0
    comp_bound[..., 3][low] = 1.0
    power_bound[low] = (dni[:, None] * areas[None, :] * F)[low]

    zsurv = low & (certificate_codes == CERT_ZERO_SURVIVOR)
    comp_bound[..., 0][zsurv] = 0.0
    comp_bound[..., 2][zsurv] = 0.0
    power_bound[zsurv] = 0.0
    zcap = low & (certificate_codes == CERT_ZERO_CAPTURE)
    comp_bound[..., 0][zcap] = 0.0
    comp_bound[..., 3][zcap & np.isfinite(formal["components"][..., 3])] = 0.0
    power_bound[zcap] = 0.0
    zone = low & (certificate_codes == CERT_ZERO_CAPTURE_SURVIVOR_ONE)
    comp_bound[zone] = 0.0
    power_bound[zone] = 0.0

    temporal = np.column_stack(
        [
            (np.sum(comp_bound * (areas / areas.sum())[None, :, None], axis=1)
             if area_weighted else comp_bound.sum(axis=1) / N),
            power_bound.sum(axis=1),
            power_bound.sum(axis=1) / areas.sum(),
        ]
    )
    rows = np.vstack([temporal.reshape(12, 5, 6).mean(axis=1), temporal.mean(axis=0)])
    cases = []
    case_indices = np.argwhere(low) if include_cases else ()
    for ti, mi in case_indices:
        cases.append(
            {
                "time_index": int(ti),
                "month": int(months[ti]),
                "hour": float(hours[ti]),
                "object_index": int(mi),
                "object_id": jsonable(object_ids[mi]),
                "survive": int(survive[ti, mi]),
                "capture": int(pooled_counts[ti, mi, 3]),
                "unknown": int(pooled_counts[ti, mi, 4]),
                "raw_R": int(pooled_counts[ti, mi, 5]),
                "state": STATE_CODES[int(formal["state"][ti, mi])],
                "certificate": CERTIFICATE_CODES[int(certificate_codes[ti, mi])],
            }
        )
    return rows, low, cases


def _required_na_locations(matrix, row_labels):
    ans = []
    for ri, ci in np.argwhere(~np.isfinite(matrix)):
        ans.append({"row": row_labels[int(ri)], "metric": LABELS[int(ci)]})
    return ans


def summarize_search_statistics(
    sums,
    counts,
    unknown_weights,
    cosine,
    tau,
    dni,
    areas,
    *,
    levels_n,
    months=None,
    hours=None,
    object_ids=None,
    mode="full_confirmation",
    certificate_records=None,
    scene_keys=None,
    trusted_certificate_sources=None,
    low_survival_threshold=100,
    efficiency_abs_target=0.001,
    power_relative_target=0.005,
    rated_power_kw=60000.0,
):
    """Summarize one Q3 candidate without running any optical calculation.

    The conservative formal work indicator is

    ``max(t7*jackknife_se, |final-prefix_half|, |final-raw|) + low_count_bound``.

    It is a work diagnostic, not a confidence interval or physical-error bound.
    """
    sums = np.asarray(sums, dtype=float)
    counts = np.asarray(counts, dtype=float)
    unknown_weights = np.asarray(unknown_weights, dtype=float)
    cosine = np.asarray(cosine, dtype=float)
    tau = np.asarray(tau, dtype=float)
    dni = np.asarray(dni, dtype=float)
    areas = np.asarray(areas, dtype=float)
    levels_n = np.asarray(levels_n, dtype=np.int64)
    if sums.ndim != 5 or sums.shape[-1] != 3:
        raise SummaryInputError("sums must have shape (L,B,T,N,3)")
    L, B, T, N, _ = sums.shape
    if counts.shape != (L, B, T, N, 6):
        raise SummaryInputError("counts must have shape (L,B,T,N,6) in COUNT_LABELS order")
    if unknown_weights.shape != (L, B, T, N):
        raise SummaryInputError("unknown_weights must have shape (L,B,T,N)")
    if cosine.shape != (T, N) or tau.shape != (T, N):
        raise SummaryInputError("cosine and tau must both have shape (T,N)")
    if dni.shape != (T,) or areas.shape != (N,):
        raise SummaryInputError("dni must have shape (T,) and areas shape (N,)")
    if levels_n.shape != (L,) or np.any(levels_n <= 0) or np.any(np.diff(levels_n) <= 0):
        raise SummaryInputError("levels_n must be strictly increasing positive integers of length L")
    if not np.all(np.isfinite(cosine)) or np.any(cosine <= 0) or np.any(cosine > 1 + _ORDER_ATOL):
        raise SummaryInputError("cosine must be finite in (0,1]")
    if not np.all(np.isfinite(tau)) or np.any(tau <= 0) or np.any(tau > 1 + _ORDER_ATOL):
        raise SummaryInputError("tau must be finite in (0,1]")
    if not np.all(np.isfinite(dni)) or np.any(dni <= 0):
        raise SummaryInputError("dni must be finite and positive")
    if not np.all(np.isfinite(areas)) or np.any(areas <= 0):
        raise SummaryInputError("areas must be finite and positive")
    if not isinstance(low_survival_threshold, (int, np.integer)) or low_survival_threshold <= 0:
        raise SummaryInputError("low_survival_threshold must be a positive integer")
    if mode not in {"full_confirmation", "full_comparison", "heuristic"}:
        raise SummaryInputError("mode must be 'full_confirmation', 'full_comparison' or 'heuristic'")

    months = STANDARD_MONTHS.copy() if months is None and T == 60 else np.asarray(months)
    hours = STANDARD_HOURS.copy() if hours is None and T == 60 else np.asarray(hours)
    if months.shape != (T,) or hours.shape != (T,):
        raise SummaryInputError("months and hours must have length T")
    if not np.all(np.isfinite(hours)) or not np.all(np.equal(months, np.rint(months))):
        raise SummaryInputError("months must be integers and hours finite")
    months = np.asarray(np.rint(months), dtype=np.int64)
    hours = np.asarray(hours, dtype=float)
    if np.any((months < 1) | (months > 12)):
        raise SummaryInputError("months must lie in 1..12")
    if object_ids is None:
        object_ids = np.arange(1, N + 1, dtype=np.int64)
    else:
        object_ids = np.asarray(object_ids, dtype=object)
        if object_ids.shape != (N,) or len(set(map(str, object_ids.tolist()))) != N:
            raise SummaryInputError("object_ids must contain N unique identities")

    if mode in {"full_confirmation", "full_comparison"}:
        if B < 2: raise SummaryInputError("full comparison requires B>=2")
        if mode == "full_confirmation" and B != 8:
            raise SummaryInputError("full confirmation requires exactly 8 whole independent batches")
        if T != 60 or not np.array_equal(months, STANDARD_MONTHS) or not np.array_equal(hours, STANDARD_HOURS):
            raise SummaryInputError("full confirmation requires the standard 12x5 time order")
        if mode == "full_confirmation" and int(levels_n[-1]) not in {128, 256}:
            raise SummaryInputError("full confirmation final n per batch must be 128 or 256")
        half_candidates = np.flatnonzero(levels_n * 2 == levels_n[-1])
        if len(half_candidates) != 1:
            raise SummaryInputError("full confirmation requires exactly one stored half-prefix level")
        prefix_index = int(half_candidates[0])
    else:
        prefix_index = None

    bad, nested_bad, validation, counts_i = _validate_arrays(sums, counts, unknown_weights, levels_n)
    cert_codes, certificate_audit = _verified_certificate_codes(
        certificate_records, scene_keys, trusted_certificate_sources, T, N
    )
    final_sums_by_batch = sums[-1]
    final_counts_by_batch = counts_i[-1]
    final_unknown_by_batch = unknown_weights[-1]
    pooled_sums = final_sums_by_batch.sum(axis=0)
    pooled_counts = final_counts_by_batch.sum(axis=0)
    pooled_unknown = final_unknown_by_batch.sum(axis=0)
    pooled_bad = np.any(bad[-1] | nested_bad, axis=0)
    final_n_total = int(B * levels_n[-1])
    formal = _object_metrics(
        pooled_sums,
        pooled_counts,
        pooled_unknown,
        cosine,
        tau,
        dni,
        areas,
        final_n_total,
        cert_codes,
        pooled_bad,
    )
    temporal = _temporal_population(formal, float(areas.sum()))

    base = {
        "kind": "Q03_FULL_CONFIRMATION_SUMMARY" if mode == "full_confirmation" else "Q03_PARTIAL_TIME_HEURISTIC",
        "summary_version": "q03-summary-v001",
        "labels": list(LABELS),
        "count_labels": list(COUNT_LABELS),
        "coverage": {
            "levels_n_per_batch": levels_n.copy(),
            "levels": int(L),
            "batches": int(B),
            "times": int(T),
            "objects": int(N),
            "final_samples_per_object_time": final_n_total,
            "complete_time_population": bool(mode in {"full_confirmation", "full_comparison"}),
        },
        "months": months.copy(),
        "hours": hours.copy(),
        "object_ids": object_ids.copy(),
        "input_validation": validation,
        "certificate_audit": certificate_audit,
        "certificate_codes": cert_codes,
        "certificate_code_labels": CERTIFICATE_CODES,
        "pooled_state_codes": formal["state"],
        "state_code_labels": STATE_CODES,
        "pooled_total_defined": formal["total_defined"],
        "pooled_component_defined": formal["component_defined"],
        "pooled_state_counts": _state_counts(formal["state"]),
        "pooled_state_cases": _state_cases(
            formal["state"], months, hours, object_ids, pooled_counts, pooled_unknown, pooled_sums
        ),
        "temporal_point": temporal,
        "area_weighted_efficiencies": {
            "labels": list(LABELS[:4]),
            "weights": areas / areas.sum(),
            "total_area_m2": float(areas.sum()),
            "temporal_point": _area_temporal(formal, areas),
            "required_for_main_table_gate": False,
            "scope": "fixed full mirror population, area weights, strict component NA propagation",
        },
        "limitations": [
            "finite-sample self-normalized ratios can be biased",
            "Student-t jackknife halfwidth is approximate and not simultaneous coverage",
            "low-survival diameter is a coordinatewise work bound for screened objects, not a confidence interval",
            "physical model error is outside this summary",
        ],
    }
    if mode == "heuristic":
        base.update(
            {
                "formal_h02_rows": None,
                "formal_decision": "NOT_AVAILABLE_HEURISTIC_PARTIAL_TIME",
                "heuristic_only": True,
                "note": "partial-time values may rank a coarse screen but cannot establish monthly/annual H02 tables, precision, or rated power",
            }
        )
        return base

    row_labels = [f"{m:02d}-21" for m in range(1, 13)] + ["annual"]
    point = _h02_rows(temporal)
    auxiliary = base["area_weighted_efficiencies"]
    area_point = _area_rows(auxiliary["temporal_point"])
    base["energy_total_ratios"] = {
        "labels": ["Pi1/Pi0", "Pi2/Pi1", "Pi2/Pi0"],
        "values": _energy_total_ratios(formal),
        "note": "each ratio checks only its own legal numerator and positive denominator; not mean conditional efficiencies",
    }

    # Stored half-prefix comparison.  Prefixes are correlated with the final
    # level; the absolute change is a refinement diagnostic, not an independent
    # replicate.
    prefix_sums = sums[prefix_index].sum(axis=0)
    prefix_counts = counts_i[prefix_index].sum(axis=0)
    prefix_unknown = unknown_weights[prefix_index].sum(axis=0)
    prefix_bad = np.any(bad[prefix_index] | nested_bad, axis=0)
    prefix_formal, _, prefix_point = _summaries_for_pool(
        prefix_sums,
        prefix_counts,
        prefix_unknown,
        cosine,
        tau,
        dni,
        areas,
        int(B * levels_n[prefix_index]),
        cert_codes,
        prefix_bad,
    )

    # Raw integration uses the analytic reference scale only through division
    # by cosine; it remains separate from the self-normalized final estimator.
    raw_object = _raw_object_metrics(
        pooled_sums, pooled_counts, cosine, tau, dni, areas, final_n_total, formal
    )
    raw_temporal = _temporal_population(raw_object, float(areas.sum()))
    raw_point = _h02_rows(raw_temporal)
    area_prefix = _area_rows(_area_temporal(prefix_formal, areas))
    area_raw = _area_rows(_area_temporal(raw_object, areas))

    leave_points = []
    area_leave_points = []
    leave_states = []
    leave_state_cases = []
    for batch in range(B):
        keep = np.arange(B) != batch
        leave_bad = np.any((bad[-1] | nested_bad)[keep], axis=0)
        leave_formal, _, leave_point = _summaries_for_pool(
            final_sums_by_batch[keep].sum(axis=0),
            final_counts_by_batch[keep].sum(axis=0),
            final_unknown_by_batch[keep].sum(axis=0),
            cosine,
            tau,
            dni,
            areas,
            int((B - 1) * levels_n[-1]),
            cert_codes,
            leave_bad,
        )
        leave_points.append(leave_point)
        area_leave_points.append(_area_rows(_area_temporal(leave_formal, areas)))
        leave_states.append(_state_counts(leave_formal["state"]))
        leave_state_cases.append(_state_cases(leave_formal["state"], months, hours, object_ids))
    leave_points = np.asarray(leave_points)
    pseudo_values = B * point - (B - 1) * leave_points
    with np.errstate(invalid="ignore"):
        jackknife_se = np.sqrt(
            np.sum((pseudo_values - np.mean(pseudo_values, axis=0)) ** 2, axis=0) / (B * (B - 1))
        )
    area_leave_points = np.asarray(area_leave_points)
    area_pseudo = B * area_point - (B - 1) * area_leave_points
    area_se = np.sqrt(np.sum((area_pseudo - np.mean(area_pseudo, axis=0)) ** 2, axis=0)
                      / (B * (B - 1)))
    area_prefix_change = np.abs(area_point - area_prefix)
    area_raw_change = np.abs(area_point - area_raw)
    area_low, area_low_mask, area_low_cases = _low_survival_bound(
        pooled_counts, formal, cert_codes, cosine, tau, dni, areas, months, hours,
        object_ids, int(low_survival_threshold), area_weighted=True, include_cases=False)
    auxiliary.update({
        "rows": row_labels, "point": area_point,
        "leave_one_batch_estimates": area_leave_points, "pseudo_values": area_pseudo,
        "jackknife_se": area_se, "prefix_half_point": area_prefix,
        "raw_integral_alternative": area_raw,
        "absolute_changes": {"prefix_half": area_prefix_change, "raw_integral": area_raw_change},
        "low_survival": {"threshold_exclusive": int(low_survival_threshold),
                         "screened_count": int(area_low_mask.sum()),
                         "cases_source": "main low_survival.cases in confirmation; not expanded during comparison",
                         "effect_diameter_bound": area_low[:, :4],
                         "scope": "per-object feasible component diameter times A_i/total_area; exact certificate dimensions removed"},
        "conservative_work_indicator": None,
        "work_indicator_status": "NOT_AVAILABLE_SEARCH_COMPARISON",
    })
    if mode == "full_comparison":
        base.update({"kind":"Q03_FULL_COMPARISON_NOT_CONFIRMATION", "heuristic_only":False,
                     "rows":row_labels, "point":point, "formal_h02_rows":point,
                     "jackknife_se":jackknife_se, "leave_one_batch_estimates":leave_points,
                     "pseudo_values":pseudo_values, "prefix_half_point":prefix_point,
                     "raw_integral_alternative":raw_point,
                     "formal_decision":"NOT_AVAILABLE_SEARCH_COMPARISON",
                     "rated_power_met":None, "all_table_items_precision_met":None,
                     "note":"Full60 search comparison under common random numbers; JK SE diagnostic only; no confirmation interval or rated decision."})
        return base
    halfwidth = T7_975 * jackknife_se
    area_halfwidth = T7_975 * area_se
    area_base_u = np.maximum.reduce([area_halfwidth, area_prefix_change, area_raw_change])
    auxiliary.update({
        "approx_pointwise_t7_95_halfwidth": area_halfwidth,
        "base_numeric_work_indicator": area_base_u,
        "conservative_work_indicator": area_base_u + area_low[:, :4],
        "work_indicator_status": "AUXILIARY_CONFIRMATION_DIAGNOSTIC_NOT_A_MAIN_GATE",
        "work_indicator_definition": "max(t7 whole-batch JK halfwidth, prefix change, raw change) plus area-weighted low-survival diameter; not a confidence bound",
    })

    batch_points = []
    batch_states = []
    batch_state_cases = []
    for batch in range(B):
        batch_formal, _, batch_point = _summaries_for_pool(
            final_sums_by_batch[batch],
            final_counts_by_batch[batch],
            final_unknown_by_batch[batch],
            cosine,
            tau,
            dni,
            areas,
            int(levels_n[-1]),
            cert_codes,
            bad[-1, batch] | nested_bad[batch],
        )
        batch_points.append(batch_point)
        batch_states.append(_state_counts(batch_formal["state"]))
        batch_state_cases.append(_state_cases(batch_formal["state"], months, hours, object_ids))
    batch_points = np.asarray(batch_points)

    prefix_change = np.abs(point - prefix_point)
    raw_shift = np.abs(point - raw_point)
    base_numeric_u = np.maximum.reduce([halfwidth, prefix_change, raw_shift])
    low_bound, low_mask, low_cases = _low_survival_bound(
        pooled_counts,
        formal,
        cert_codes,
        cosine,
        tau,
        dni,
        areas,
        months,
        hours,
        object_ids,
        int(low_survival_threshold),
    )
    conservative_u = base_numeric_u + low_bound
    # The main confirmation case list already identifies every screened object;
    # area weights are stored once in the auxiliary header. Do not duplicate
    # potentially large object/time receipt lists in serialized summaries.

    efficiency_pass = np.isfinite(point[:, :4]) & np.isfinite(conservative_u[:, :4]) & (
        conservative_u[:, :4] <= efficiency_abs_target
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        power_relative_u = conservative_u[:, 4:] / np.abs(point[:, 4:])
    power_pass = (
        np.isfinite(point[:, 4:])
        & (np.abs(point[:, 4:]) > 0)
        & np.isfinite(power_relative_u)
        & (power_relative_u <= power_relative_target)
    )
    target_pass = np.concatenate([efficiency_pass, power_pass], axis=1)
    required_na = _required_na_locations(point, row_labels)
    diagnostic_na = _required_na_locations(conservative_u, row_labels)
    required_defined = len(required_na) == 0
    diagnostics_defined = len(diagnostic_na) == 0
    rated_lower_kw = point[-1, 4] - conservative_u[-1, 4]
    rated_defined = bool(math.isfinite(float(rated_lower_kw)))
    rated_met = bool(rated_defined and rated_lower_kw >= rated_power_kw)
    all_precision_met = bool(target_pass.all())
    ready = bool(
        validation["all_valid"]
        and certificate_audit["all_valid"]
        and required_defined
        and diagnostics_defined
        and np.all(formal["total_defined"])
    )
    if not ready:
        decision = "UNRESOLVED"
    elif rated_met and all_precision_met:
        decision = "PASS"
    else:
        decision = "FAIL"

    ratios = _energy_total_ratios(formal)
    estimated = formal["state"] == STATE_ESTIMATED
    factor_error = np.nan
    if np.any(estimated):
        factor_product = (
            formal["components"][..., 2]
            * cosine
            * tau
            * formal["components"][..., 3]
            * RHO
        )
        factor_error = float(
            np.max(np.abs(factor_product[estimated] - formal["components"][..., 0][estimated]))
        )
    numeric_checks = {
        "factor_product_abs_error_on_estimated_objects": factor_error,
        "area_relation_abs_kw": float(np.nanmax(np.abs(point[:, 5] * areas.sum() - point[:, 4]))),
        "max_raw_projection_residual": float(
            np.max(np.abs(pooled_sums[..., 0] / final_n_total - cosine))
        ),
        "energy_and_count_inputs_valid": bool(validation["all_valid"]),
        "certificate_evidence_valid": bool(certificate_audit["all_valid"]),
    }
    base.update(
        {
            "heuristic_only": False,
            "rows": row_labels,
            "point": point,
            "formal_h02_rows": point,
            "jackknife_se": jackknife_se,
            "approx_pointwise_t7_95_halfwidth": halfwidth,
            "leave_one_batch_estimates": leave_points,
            "pseudo_values": pseudo_values,
            "individual_batch_metrics": batch_points,
            "individual_batch_state_counts": batch_states,
            "individual_batch_state_cases": batch_state_cases,
            "leave_one_batch_state_counts": leave_states,
            "leave_one_batch_state_cases": leave_state_cases,
            "prefix_half_level_index": prefix_index,
            "prefix_half_n_per_batch": int(levels_n[prefix_index]),
            "prefix_half_point": prefix_point,
            "prefix_half_state_counts": _state_counts(prefix_formal["state"]),
            "prefix_half_state_cases": _state_cases(prefix_formal["state"], months, hours, object_ids),
            "raw_integral_alternative": raw_point,
            "absolute_changes": {"prefix_half": prefix_change, "raw_integral": raw_shift},
            "base_numeric_work_indicator": base_numeric_u,
            "low_survival": {
                "threshold_exclusive": int(low_survival_threshold),
                "screened_count": int(low_mask.sum()),
                "cases": low_cases,
                "effect_diameter_bound": low_bound,
                "scope": "all final pooled object-times with unweighted survive count below threshold; coordinatewise feasible diameters, certificate-exact dimensions removed",
            },
            "conservative_work_indicator": conservative_u,
            "work_indicator_definition": "max(t7 jackknife halfwidth, final-minus-half-prefix, final-minus-raw-integral) plus low-survival coordinatewise effect-diameter bound; not a confidence interval",
            "targets": {
                "efficiency_absolute": float(efficiency_abs_target),
                "power_relative": float(power_relative_target),
                "rated_power_kw": float(rated_power_kw),
            },
            "target_pass": target_pass,
            "power_relative_work_indicator": power_relative_u,
            "all_table_items_precision_met": all_precision_met,
            "required_table_na_locations": required_na,
            "diagnostic_na_locations": diagnostic_na,
            "all_formal_totals_defined": bool(np.all(formal["total_defined"])),
            "rated_power_lower_work_value_kw": float(rated_lower_kw),
            "rated_power_met": rated_met,
            "formal_ready": ready,
            "formal_decision": decision,
            "numeric_checks": numeric_checks,
            "energy_total_ratios": {
                "labels": ["Pi1/Pi0", "Pi2/Pi1", "Pi2/Pi0"],
                "values": ratios,
                "note": "each energy ratio has its own numerator/denominator NA check; totals over each month/all 60 times, not H02 conditional means",
            },
        }
    )
    return base


__all__ = [
    "COUNT_LABELS",
    "LABELS",
    "STANDARD_HOURS",
    "STANDARD_MONTHS",
    "STATE_CODES",
    "SummaryInputError",
    "jsonable",
    "summarize_search_statistics",
]
