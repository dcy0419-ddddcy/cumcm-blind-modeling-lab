"""Pure-array checks for q02_search_summary_v001; no files or optical calls."""
from __future__ import annotations

import json

import numpy as np

import q02_search_summary_v001 as summary


def _fixture():
    levels_n = np.array([64, 128], dtype=np.int64)
    L, B, T, N = 2, 8, 60, 2
    cosine = np.full((T, N), 0.8)
    tau = np.full((T, N), 0.9)
    dni = np.tile(np.array([1.0, 2.0, 3.0, 4.0, 5.0]), 12)
    areas = np.array([2.0, 2.0])
    sums = np.empty((L, B, T, N, 3), dtype=float)
    counts = np.zeros((L, B, T, N, 6), dtype=np.int64)
    unknown = np.zeros((L, B, T, N), dtype=float)
    for level, n in enumerate(levels_n):
        sums[level, ..., 0] = 0.8 * n
        sums[level, ..., 1] = 0.4 * n
        sums[level, ..., 2] = 0.2 * n
        counts[level, ..., 0] = n // 4
        counts[level, ..., 1] = n // 4
        counts[level, ..., 2] = n // 2
        counts[level, ..., 3] = n // 4
        counts[level, ..., 5] = n // 4
    return {
        "sums": sums,
        "counts": counts,
        "unknown_weights": unknown,
        "cosine": cosine,
        "tau": tau,
        "dni": dni,
        "areas": areas,
        "levels_n": levels_n,
    }


def _run(data, **kwargs):
    return summary.summarize_search_statistics(
        data["sums"],
        data["counts"],
        data["unknown_weights"],
        data["cosine"],
        data["tau"],
        data["dni"],
        data["areas"],
        levels_n=data["levels_n"],
        **kwargs,
    )


def run_checks():
    checks = {}

    base = _run(_fixture())
    expected_optical = 0.92 * 0.8 * 0.9 * 0.25
    expected_power = 3.0 * 4.0 * expected_optical
    checks["H02_fixed_population_and_DNI_pairing"] = bool(
        np.allclose(base["point"][:, 0], expected_optical)
        and np.allclose(base["point"][:, 1], 0.8)
        and np.allclose(base["point"][:, 2:4], 0.5)
        and np.allclose(base["point"][:, 4], expected_power)
        and np.allclose(base["point"][:, 5], expected_power / 4.0)
    )
    checks["identical_batches_zero_numeric_U"] = bool(
        np.allclose(base["base_numeric_work_indicator"], 0.0)
        and base["low_survival"]["screened_count"] == 0
    )
    checks["rated_test_uses_lower_work_value"] = bool(
        np.isclose(
            base["rated_power_lower_work_value_kw"],
            base["point"][-1, 4] - base["conservative_work_indicator"][-1, 4],
        )
        and base["formal_decision"] == "FAIL"
    )

    varied = _fixture()
    for batch in range(8):
        varied["sums"][-1, batch, ..., 0] = (0.72 + 0.02 * batch) * 128
        varied["sums"][-1, batch, ..., 1] = (0.36 + 0.005 * batch) * 128
        varied["sums"][-1, batch, ..., 2] = (0.12 + 0.01 * batch) * 128
        varied["counts"][-1, batch, ..., 3] = 20 + batch
        varied["counts"][-1, batch, ..., 5] = 20 + batch
    pooled = _run(varied)
    batch_mean = np.nanmean(pooled["individual_batch_metrics"][:, -1, 0])
    checks["pooled_point_not_substituted_by_batch_ratio_mean"] = bool(
        not np.isclose(pooled["point"][-1, 0], batch_mean)
    )
    checks["whole_batch_jackknife_saved"] = bool(
        pooled["leave_one_batch_estimates"].shape == (8, 13, 6)
        and pooled["pseudo_values"].shape == (8, 13, 6)
        and np.all(pooled["jackknife_se"] >= 0)
    )

    low = _fixture()
    low["counts"][:, :, 0, 0, 0] = low["levels_n"][:, None] - 24
    low["counts"][:, :, 0, 0, 1] = 12
    low["counts"][:, :, 0, 0, 2] = 12
    low["counts"][:, :, 0, 0, 3] = 6
    low["counts"][:, :, 0, 0, 5] = 6
    low["sums"][:, :, 0, 0, 1] = 0.08 * low["levels_n"][:, None]
    low["sums"][:, :, 0, 0, 2] = 0.04 * low["levels_n"][:, None]
    low_result = _run(low)
    expected_shadow_bound = 1.0 / (5 * 2)
    checks["low_survival_all_object_time_screen"] = bool(
        low_result["low_survival"]["screened_count"] == 1
        and np.isclose(low_result["low_survival"]["effect_diameter_bound"][0, 2], expected_shadow_bound)
        and np.all(
            low_result["conservative_work_indicator"]
            >= low_result["base_numeric_work_indicator"]
        )
    )

    sampled_zero = _fixture()
    sampled_zero["sums"][:, :, 0, 0, 1:] = 0.0
    sampled_zero["counts"][:, :, 0, 0, 0] = sampled_zero["levels_n"][:, None]
    sampled_zero["counts"][:, :, 0, 0, 1:4] = 0
    sampled_zero["counts"][:, :, 0, 0, 5] = 0
    zero_result = _run(sampled_zero)
    checks["sampled_zero_without_proof_is_unresolved"] = bool(
        zero_result["pooled_state_counts"]["SAMPLED_ZERO_SURVIVOR"] == 1
        and zero_result["formal_decision"] == "UNRESOLVED"
        and not zero_result["pooled_total_defined"][0, 0]
        and zero_result["pooled_component_defined"][0, 0, 1]
        and not zero_result["pooled_component_defined"][0, 0, 0]
        and any(x["metric"] == "optical" for x in zero_result["required_table_na_locations"])
    )

    unknown = _fixture()
    unknown["counts"][-1, 0, 0, 0, 4] = 1
    unknown["unknown_weights"][-1, 0, 0, 0] = 0.8
    unknown_result = _run(unknown)
    checks["boundary_unknown_is_not_hidden"] = bool(
        unknown_result["pooled_state_counts"]["BOUNDARY_UNCERTAIN"] == 1
        and unknown_result["formal_decision"] == "UNRESOLVED"
    )

    partial = _fixture()
    keep = np.array([0, 27])
    heuristic = summary.summarize_search_statistics(
        partial["sums"][:, :, keep],
        partial["counts"][:, :, keep],
        partial["unknown_weights"][:, :, keep],
        partial["cosine"][keep],
        partial["tau"][keep],
        partial["dni"][keep],
        partial["areas"],
        levels_n=partial["levels_n"],
        months=np.array([1, 6]),
        hours=np.array([9.0, 12.0]),
        mode="heuristic",
    )
    checks["partial_time_is_heuristic_only"] = bool(
        heuristic["formal_h02_rows"] is None
        and heuristic["formal_decision"] == "NOT_AVAILABLE_HEURISTIC_PARTIAL_TIME"
    )

    return {
        "checks": checks,
        "all_pass": all(checks.values()),
        "scope": "synthetic in-memory arrays only; no file, geometry, search, or optical execution",
    }


if __name__ == "__main__":
    result = run_checks()
    print(json.dumps(summary.jsonable(result), ensure_ascii=False, sort_keys=True))
    if not result["all_pass"]:
        raise SystemExit(1)
