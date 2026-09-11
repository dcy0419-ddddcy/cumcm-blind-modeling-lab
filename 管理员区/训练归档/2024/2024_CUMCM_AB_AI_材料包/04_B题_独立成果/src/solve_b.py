#!/usr/bin/env python3
"""2024 CUMCM Problem B - independent reproducible solver.

The program uses only the numerical data transcribed from the original problem.
It generates every CSV/JSON result used by the accompanying report.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import logging
import math
import platform
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
LOGS = ROOT / "logs"


def setup_logging() -> logging.Logger:
    RESULTS.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("solve_b")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler = logging.FileHandler(LOGS / "run.log", mode="w", encoding="utf-8")
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def write_csv(path: Path, rows: Iterable[dict], fieldnames: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Question 1: two one-sided anytime-valid SPRTs.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Q1Config:
    p0: float = 0.10
    p_low: float = 0.05
    p_high: float = 0.15
    alpha_reject: float = 0.05
    alpha_accept: float = 0.10
    max_n: int = 2000


def q1_log_lr(n: int, x: int, alternative: float, p0: float) -> float:
    return x * math.log(alternative / p0) + (n - x) * math.log(
        (1.0 - alternative) / (1.0 - p0)
    )


def q1_decision(n: int, x: int, cfg: Q1Config = Q1Config()) -> str:
    """Return accept/reject/continue after n tests and x defects.

    Reject controls P(reject) <= alpha_reject for every p <= p0.
    Accept controls P(accept) <= alpha_accept for every p >= p0.
    """
    reject_lr = q1_log_lr(n, x, cfg.p_high, cfg.p0)
    accept_lr = q1_log_lr(n, x, cfg.p_low, cfg.p0)
    if reject_lr >= math.log(1.0 / cfg.alpha_reject) - 1e-12:
        return "reject"
    if accept_lr >= math.log(1.0 / cfg.alpha_accept) - 1e-12:
        return "accept"
    return "continue"


def q1_boundary(n: int, cfg: Q1Config = Q1Config()) -> tuple[int | None, int | None]:
    accepts = [x for x in range(n + 1) if q1_decision(n, x, cfg) == "accept"]
    rejects = [x for x in range(n + 1) if q1_decision(n, x, cfg) == "reject"]
    return (max(accepts) if accepts else None, min(rejects) if rejects else None)


def q1_operating_characteristic(
    true_p: float, cfg: Q1Config = Q1Config()
) -> dict[str, float]:
    """Exact finite-horizon path recursion; no Monte Carlo is used."""
    live: dict[int, float] = {0: 1.0}
    accept_probability = 0.0
    reject_probability = 0.0
    truncated_expected_n = 0.0
    for n in range(1, cfg.max_n + 1):
        next_live: dict[int, float] = {}
        for old_x, path_probability in live.items():
            for new_x, transition in (
                (old_x, 1.0 - true_p),
                (old_x + 1, true_p),
            ):
                probability = path_probability * transition
                decision = q1_decision(n, new_x, cfg)
                if decision == "accept":
                    accept_probability += probability
                    truncated_expected_n += n * probability
                elif decision == "reject":
                    reject_probability += probability
                    truncated_expected_n += n * probability
                else:
                    next_live[new_x] = next_live.get(new_x, 0.0) + probability
        live = next_live
    unresolved_probability = sum(live.values())
    truncated_expected_n += cfg.max_n * unresolved_probability
    return {
        "true_defect_rate": true_p,
        "accept_probability": accept_probability,
        "reject_probability": reject_probability,
        "unresolved_probability_at_max_n": unresolved_probability,
        "truncated_expected_sample_size": truncated_expected_n,
    }


# ---------------------------------------------------------------------------
# Question 2: regenerative expected fulfillment cost.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Q2Case:
    case: int
    p1: float
    buy1: float
    test1: float
    p2: float
    buy2: float
    test2: float
    p_final: float
    assembly: float
    test_final: float
    sale: float
    exchange_loss: float
    dismantle: float


Q2_CASES = (
    Q2Case(1, 0.10, 4, 2, 0.10, 18, 3, 0.10, 6, 3, 56, 6, 5),
    Q2Case(2, 0.20, 4, 2, 0.20, 18, 3, 0.20, 6, 3, 56, 6, 5),
    Q2Case(3, 0.10, 4, 2, 0.10, 18, 3, 0.10, 6, 3, 56, 30, 5),
    Q2Case(4, 0.20, 4, 1, 0.20, 18, 1, 0.20, 6, 2, 56, 30, 5),
    Q2Case(5, 0.10, 4, 8, 0.20, 18, 1, 0.10, 6, 2, 56, 10, 5),
    Q2Case(6, 0.05, 4, 2, 0.05, 18, 3, 0.05, 6, 3, 56, 10, 40),
)


def q2_evaluate(
    case: Q2Case,
    policy: tuple[int, int, int, int],
    rates: tuple[float, float, float] | None = None,
) -> dict[str, float | bool | str]:
    """Evaluate one stationary policy.

    Policy bits are (inspect component 1, inspect component 2,
    inspect final, dismantle a known/returned defective final).

    A dismantled product reuses exactly the same physical components. Hence a
    stationary reuse loop has infinite expected cost if either component was
    never screened: with positive probability a persistent bad component is
    reused forever. Such policies are explicitly labelled infeasible.
    """
    x1, x2, y, z = policy
    p1, p2, pf = rates if rates is not None else (case.p1, case.p2, case.p_final)
    if not all(0.0 <= p < 1.0 for p in (p1, p2, pf)):
        raise ValueError("Defect rates must be in [0, 1).")
    component_cost_1 = (case.buy1 + case.test1) / (1.0 - p1) if x1 else case.buy1
    component_cost_2 = (case.buy2 + case.test2) / (1.0 - p2) if x2 else case.buy2
    good1 = 1.0 if x1 else 1.0 - p1
    good2 = 1.0 if x2 else 1.0 - p2
    pass_probability = good1 * good2 * (1.0 - pf)
    if z and not (x1 and x2):
        return {
            "feasible": False,
            "reason": "persistent defective unscreened component may be reused forever",
            "pass_probability_per_assembly": pass_probability,
            "expected_fulfillment_cost": math.inf,
            "expected_profit": -math.inf,
        }
    if z:
        # Both recovered components are known good and paid for only once.
        repeated_stage_cost = (
            case.assembly
            + y * case.test_final
            + pf * (case.dismantle + (1 - y) * case.exchange_loss)
        ) / (1.0 - pf)
        expected_cost = component_cost_1 + component_cost_2 + repeated_stage_cost
    else:
        attempt_cost = component_cost_1 + component_cost_2 + case.assembly + y * case.test_final
        expected_cost = (
            attempt_cost
            + (1 - y) * (1.0 - pass_probability) * case.exchange_loss
        ) / pass_probability
    return {
        "feasible": True,
        "reason": "",
        "pass_probability_per_assembly": pass_probability,
        "expected_fulfillment_cost": expected_cost,
        "expected_profit": case.sale - expected_cost,
    }


def q2_policy_text(policy: tuple[int, int, int, int]) -> str:
    return "".join(str(bit) for bit in policy)


# ---------------------------------------------------------------------------
# Question 3: tree-structured recursive production model.
# ---------------------------------------------------------------------------


COMPONENT_GROUPS = ((0, 1, 2), (3, 4, 5), (6, 7))
Q3_COMPONENTS = (
    (2.0, 1.0),
    (8.0, 1.0),
    (12.0, 2.0),
    (2.0, 1.0),
    (8.0, 1.0),
    (12.0, 2.0),
    (8.0, 1.0),
    (12.0, 2.0),
)
Q3_SEMI_ASSEMBLY = 8.0
Q3_SEMI_TEST = 4.0
Q3_SEMI_DISMANTLE = 6.0
Q3_FINAL_ASSEMBLY = 8.0
Q3_FINAL_TEST = 6.0
Q3_FINAL_DISMANTLE = 10.0
Q3_SALE = 200.0
Q3_EXCHANGE_LOSS = 40.0


Q3Policy = tuple[
    tuple[int, ...], tuple[int, ...], tuple[int, ...], int, int
]


def generate_q3_policies() -> list[Q3Policy]:
    policies: list[Q3Policy] = []
    for inspect_components in itertools.product((0, 1), repeat=8):
        for inspect_semis in itertools.product((0, 1), repeat=3):
            for dismantle_semis in itertools.product((0, 1), repeat=3):
                if any(
                    not inspect_semis[j] and dismantle_semis[j] for j in range(3)
                ):
                    continue
                if any(
                    dismantle_semis[j]
                    and not all(inspect_components[i] for i in COMPONENT_GROUPS[j])
                    for j in range(3)
                ):
                    continue
                for inspect_final, dismantle_final in itertools.product((0, 1), repeat=2):
                    if dismantle_final and not all(inspect_semis):
                        continue
                    policies.append(
                        (
                            inspect_components,
                            inspect_semis,
                            dismantle_semis,
                            inspect_final,
                            dismantle_final,
                        )
                    )
    return policies


def q3_evaluate(
    policy: Q3Policy,
    component_rates: Sequence[float] | None = None,
    semi_rates: Sequence[float] | None = None,
    final_rate: float = 0.10,
) -> dict[str, float | list[float]]:
    component_rates = tuple((0.10,) * 8 if component_rates is None else component_rates)
    semi_rates = tuple((0.10,) * 3 if semi_rates is None else semi_rates)
    if len(component_rates) != 8 or len(semi_rates) != 3:
        raise ValueError("Question 3 needs 8 component rates and 3 semi-product rates.")
    inspect_components, inspect_semis, dismantle_semis, inspect_final, dismantle_final = policy
    semi_outputs: list[tuple[float, float]] = []
    for j, group in enumerate(COMPONENT_GROUPS):
        input_cost = 0.0
        input_good_probability = 1.0
        for i in group:
            buy, test = Q3_COMPONENTS[i]
            p = component_rates[i]
            if inspect_components[i]:
                input_cost += (buy + test) / (1.0 - p)
            else:
                input_cost += buy
                input_good_probability *= 1.0 - p
        process_good_probability = 1.0 - semi_rates[j]
        pass_probability = input_good_probability * process_good_probability
        if inspect_semis[j]:
            if dismantle_semis[j]:
                # Feasibility is enforced by generate_q3_policies: all leaves are known good.
                output_cost = input_cost + (
                    Q3_SEMI_ASSEMBLY
                    + Q3_SEMI_TEST
                    + semi_rates[j] * Q3_SEMI_DISMANTLE
                ) / process_good_probability
            else:
                output_cost = (
                    input_cost + Q3_SEMI_ASSEMBLY + Q3_SEMI_TEST
                ) / pass_probability
            output_good_probability = 1.0
        else:
            output_cost = input_cost + Q3_SEMI_ASSEMBLY
            output_good_probability = pass_probability
        semi_outputs.append((output_cost, output_good_probability))

    process_good_probability = 1.0 - final_rate
    if dismantle_final:
        expected_cost = sum(item[0] for item in semi_outputs) + (
            Q3_FINAL_ASSEMBLY
            + inspect_final * Q3_FINAL_TEST
            + final_rate
            * (Q3_FINAL_DISMANTLE + (1 - inspect_final) * Q3_EXCHANGE_LOSS)
        ) / process_good_probability
        pass_probability = process_good_probability
    else:
        pass_probability = process_good_probability * math.prod(
            item[1] for item in semi_outputs
        )
        attempt_cost = (
            sum(item[0] for item in semi_outputs)
            + Q3_FINAL_ASSEMBLY
            + inspect_final * Q3_FINAL_TEST
        )
        expected_cost = (
            attempt_cost
            + (1 - inspect_final)
            * (1.0 - pass_probability)
            * Q3_EXCHANGE_LOSS
        ) / pass_probability
    return {
        "semi_expected_costs": [item[0] for item in semi_outputs],
        "semi_output_good_probabilities": [item[1] for item in semi_outputs],
        "pass_probability_per_final_assembly": pass_probability,
        "expected_fulfillment_cost": expected_cost,
        "expected_profit": Q3_SALE - expected_cost,
    }


def q3_policy_fields(policy: Q3Policy) -> dict[str, str | int]:
    components, semis, dismantles, inspect_final, dismantle_final = policy
    return {
        "inspect_components": "".join(map(str, components)),
        "inspect_semis": "".join(map(str, semis)),
        "dismantle_semis": "".join(map(str, dismantles)),
        "inspect_final": inspect_final,
        "dismantle_final": dismantle_final,
    }


# ---------------------------------------------------------------------------
# Question 4: uncertainty propagation from explicitly labelled sample records.
# ---------------------------------------------------------------------------


def beta_draws_for_nominal(
    nominal: float, sample_size: int, draw_count: int, rng: np.random.Generator
) -> tuple[np.ndarray, int]:
    observed_defects = int(round(nominal * sample_size))
    if not math.isclose(observed_defects / sample_size, nominal, abs_tol=1e-12):
        raise ValueError("Sample size does not reproduce the stated nominal rate exactly.")
    # Jeffreys prior Beta(1/2, 1/2).
    draws = rng.beta(
        observed_defects + 0.5,
        sample_size - observed_defects + 0.5,
        size=draw_count,
    )
    return draws, observed_defects


def q2_cost_array(
    case: Q2Case,
    policy: tuple[int, int, int, int],
    p1: np.ndarray,
    p2: np.ndarray,
    pf: np.ndarray,
) -> np.ndarray:
    x1, x2, y, z = policy
    k1 = (case.buy1 + case.test1) / (1.0 - p1) if x1 else np.full_like(p1, case.buy1)
    k2 = (case.buy2 + case.test2) / (1.0 - p2) if x2 else np.full_like(p2, case.buy2)
    r1 = np.ones_like(p1) if x1 else 1.0 - p1
    r2 = np.ones_like(p2) if x2 else 1.0 - p2
    probability = r1 * r2 * (1.0 - pf)
    if z and not (x1 and x2):
        return np.full_like(p1, np.inf)
    if z:
        return k1 + k2 + (
            case.assembly
            + y * case.test_final
            + pf * (case.dismantle + (1 - y) * case.exchange_loss)
        ) / (1.0 - pf)
    return (
        k1
        + k2
        + case.assembly
        + y * case.test_final
        + (1 - y) * (1.0 - probability) * case.exchange_loss
    ) / probability


def q4_q2_analysis(
    sample_size: int = 100, draw_count: int = 20000, seed: int = 20240905
) -> tuple[list[dict], list[dict]]:
    detail_rows: list[dict] = []
    summary_rows: list[dict] = []
    policies = list(itertools.product((0, 1), repeat=4))
    for case in Q2_CASES:
        rng = np.random.default_rng(seed + case.case)
        p1, x1 = beta_draws_for_nominal(case.p1, sample_size, draw_count, rng)
        p2, x2 = beta_draws_for_nominal(case.p2, sample_size, draw_count, rng)
        pf, xf = beta_draws_for_nominal(case.p_final, sample_size, draw_count, rng)
        arrays = [q2_cost_array(case, policy, p1, p2, pf) for policy in policies]
        matrix = np.stack(arrays)
        means = np.mean(matrix, axis=1)
        winners = np.argmin(matrix, axis=0)
        best_index = int(np.argmin(means))
        for index, (policy, costs) in enumerate(zip(policies, arrays)):
            finite = bool(np.all(np.isfinite(costs)))
            detail_rows.append(
                {
                    "case": case.case,
                    "sample_size_each_rate": sample_size,
                    "observed_defects_p1": x1,
                    "observed_defects_p2": x2,
                    "observed_defects_p_final": xf,
                    "policy": q2_policy_text(policy),
                    "posterior_mean_cost": float(np.mean(costs)) if finite else "inf",
                    "posterior_mean_cost_mc_se": (
                        float(np.std(costs, ddof=1) / math.sqrt(draw_count))
                        if finite
                        else "inf"
                    ),
                    "posterior_cost_q025": float(np.quantile(costs, 0.025)) if finite else "inf",
                    "posterior_cost_q975": float(np.quantile(costs, 0.975)) if finite else "inf",
                    "probability_ex_post_optimal": float(np.mean(winners == index)),
                    "bayes_selected": int(index == best_index),
                }
            )
        best_costs = arrays[best_index]
        summary_rows.append(
            {
                "case": case.case,
                "sample_size_each_rate": sample_size,
                "draw_count": draw_count,
                "selected_policy": q2_policy_text(policies[best_index]),
                "posterior_mean_cost": float(np.mean(best_costs)),
                "posterior_mean_cost_mc_se": float(
                    np.std(best_costs, ddof=1) / math.sqrt(draw_count)
                ),
                "posterior_mean_profit": float(case.sale - np.mean(best_costs)),
                "posterior_cost_q025": float(np.quantile(best_costs, 0.025)),
                "posterior_cost_q975": float(np.quantile(best_costs, 0.975)),
                "probability_ex_post_optimal": float(np.mean(winners == best_index)),
            }
        )
    return detail_rows, summary_rows


def q3_cost_array(
    policy: Q3Policy,
    component_rates: Sequence[np.ndarray],
    semi_rates: Sequence[np.ndarray],
    final_rate: np.ndarray,
) -> np.ndarray:
    inspect_components, inspect_semis, dismantle_semis, inspect_final, dismantle_final = policy
    semi_outputs: list[tuple[np.ndarray, np.ndarray | float]] = []
    for j, group in enumerate(COMPONENT_GROUPS):
        input_cost = np.zeros_like(final_rate)
        input_good_probability = np.ones_like(final_rate)
        for i in group:
            buy, test = Q3_COMPONENTS[i]
            if inspect_components[i]:
                input_cost = input_cost + (buy + test) / (1.0 - component_rates[i])
            else:
                input_cost = input_cost + buy
                input_good_probability = input_good_probability * (1.0 - component_rates[i])
        process_good_probability = 1.0 - semi_rates[j]
        pass_probability = input_good_probability * process_good_probability
        if inspect_semis[j]:
            if dismantle_semis[j]:
                output_cost = input_cost + (
                    Q3_SEMI_ASSEMBLY
                    + Q3_SEMI_TEST
                    + semi_rates[j] * Q3_SEMI_DISMANTLE
                ) / process_good_probability
            else:
                output_cost = (
                    input_cost + Q3_SEMI_ASSEMBLY + Q3_SEMI_TEST
                ) / pass_probability
            output_good_probability: np.ndarray | float = 1.0
        else:
            output_cost = input_cost + Q3_SEMI_ASSEMBLY
            output_good_probability = pass_probability
        semi_outputs.append((output_cost, output_good_probability))
    final_good_probability = 1.0 - final_rate
    if dismantle_final:
        return sum(item[0] for item in semi_outputs) + (
            Q3_FINAL_ASSEMBLY
            + inspect_final * Q3_FINAL_TEST
            + final_rate
            * (Q3_FINAL_DISMANTLE + (1 - inspect_final) * Q3_EXCHANGE_LOSS)
        ) / final_good_probability
    pass_probability = final_good_probability
    for _, probability in semi_outputs:
        pass_probability = pass_probability * probability
    return (
        sum(item[0] for item in semi_outputs)
        + Q3_FINAL_ASSEMBLY
        + inspect_final * Q3_FINAL_TEST
        + (1 - inspect_final) * (1.0 - pass_probability) * Q3_EXCHANGE_LOSS
    ) / pass_probability


def q4_q3_analysis(
    sample_size: int = 100, draw_count: int = 5000, seed: int = 20240906
) -> tuple[list[dict], dict]:
    rng = np.random.default_rng(seed)
    component_rates = [
        beta_draws_for_nominal(0.10, sample_size, draw_count, rng)[0]
        for _ in range(8)
    ]
    semi_rates = [
        beta_draws_for_nominal(0.10, sample_size, draw_count, rng)[0]
        for _ in range(3)
    ]
    final_rate = beta_draws_for_nominal(0.10, sample_size, draw_count, rng)[0]
    policies = generate_q3_policies()
    means = np.empty(len(policies))
    winner_cost = np.full(draw_count, np.inf)
    winner_index = np.full(draw_count, -1, dtype=int)
    for index, policy in enumerate(policies):
        costs = q3_cost_array(policy, component_rates, semi_rates, final_rate)
        means[index] = float(np.mean(costs))
        mask = costs < winner_cost
        winner_cost[mask] = costs[mask]
        winner_index[mask] = index
    top_indices = np.argsort(means)[:20]
    top_rows: list[dict] = []
    for rank, index in enumerate(top_indices, start=1):
        policy = policies[int(index)]
        costs = q3_cost_array(policy, component_rates, semi_rates, final_rate)
        row = {
            "rank": rank,
            **q3_policy_fields(policy),
            "sample_size_each_rate": sample_size,
            "draw_count": draw_count,
            "posterior_mean_cost": float(np.mean(costs)),
            "posterior_mean_cost_mc_se": float(
                np.std(costs, ddof=1) / math.sqrt(draw_count)
            ),
            "posterior_mean_profit": float(Q3_SALE - np.mean(costs)),
            "posterior_cost_q025": float(np.quantile(costs, 0.025)),
            "posterior_cost_q975": float(np.quantile(costs, 0.975)),
            "probability_ex_post_optimal": float(np.mean(winner_index == index)),
        }
        top_rows.append(row)
    best = top_rows[0]
    summary = dict(best)
    summary["feasible_policy_count"] = len(policies)
    return top_rows, summary


def q4_sensitivity() -> list[dict]:
    rows: list[dict] = []
    for n in (100, 200, 500):
        _, q2_summary = q4_q2_analysis(
            sample_size=n, draw_count=4000, seed=20250000 + n
        )
        for item in q2_summary:
            rows.append(
                {
                    "problem": "Q2",
                    "case": item["case"],
                    "sample_size_each_rate": n,
                    "selected_policy": item["selected_policy"],
                    "posterior_mean_cost": item["posterior_mean_cost"],
                    "posterior_mean_profit": item["posterior_mean_profit"],
                    "probability_ex_post_optimal": item[
                        "probability_ex_post_optimal"
                    ],
                }
            )
        _, q3_summary = q4_q3_analysis(
            sample_size=n, draw_count=2000, seed=20260000 + n
        )
        q3_policy = (
            f"{q3_summary['inspect_components']}/"
            f"{q3_summary['inspect_semis']}/"
            f"{q3_summary['dismantle_semis']}/"
            f"{q3_summary['inspect_final']}{q3_summary['dismantle_final']}"
        )
        rows.append(
            {
                "problem": "Q3",
                "case": "tree",
                "sample_size_each_rate": n,
                "selected_policy": q3_policy,
                "posterior_mean_cost": q3_summary["posterior_mean_cost"],
                "posterior_mean_profit": q3_summary["posterior_mean_profit"],
                "probability_ex_post_optimal": q3_summary[
                    "probability_ex_post_optimal"
                ],
            }
        )
    return rows


def run_all(logger: logging.Logger) -> dict:
    logger.info("Python=%s; NumPy=%s; platform=%s", sys.version.split()[0], np.__version__, platform.platform())

    cfg = Q1Config()
    logger.info("Q1: computing exact boundaries and path probabilities to N=%d", cfg.max_n)
    boundary_rows = []
    for n in list(range(1, 501)) + [1000, 2000]:
        accept_max, reject_min = q1_boundary(n, cfg)
        boundary_rows.append(
            {
                "n": n,
                "accept_if_x_at_most": "" if accept_max is None else accept_max,
                "reject_if_x_at_least": "" if reject_min is None else reject_min,
            }
        )
    write_csv(
        RESULTS / "q1_boundaries.csv",
        boundary_rows,
        ("n", "accept_if_x_at_most", "reject_if_x_at_least"),
    )
    q1_rates = (0.02, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.30)
    q1_oc = [q1_operating_characteristic(p, cfg) for p in q1_rates]
    write_csv(
        RESULTS / "q1_operating_characteristics.csv",
        q1_oc,
        tuple(q1_oc[0].keys()),
    )
    logger.info("Q1 boundary examples: n=43 accept x<=0; n=100 accept x<=4, reject x>=19")

    logger.info("Q2: enumerating all 16 policies for each of 6 cases")
    q2_rows: list[dict] = []
    q2_optimal_rows: list[dict] = []
    q2_summary: list[dict] = []
    for case in Q2_CASES:
        case_rows = []
        for policy in itertools.product((0, 1), repeat=4):
            metrics = q2_evaluate(case, policy)
            row = {
                "case": case.case,
                "policy": q2_policy_text(policy),
                "inspect_component_1": policy[0],
                "inspect_component_2": policy[1],
                "inspect_final": policy[2],
                "dismantle_defective_final": policy[3],
                **metrics,
            }
            case_rows.append(row)
            q2_rows.append(row)
        finite_rows = [row for row in case_rows if row["feasible"]]
        minimum = min(float(row["expected_fulfillment_cost"]) for row in finite_rows)
        ties = [
            row
            for row in finite_rows
            if math.isclose(float(row["expected_fulfillment_cost"]), minimum, abs_tol=1e-10)
        ]
        for row in ties:
            q2_optimal_rows.append(row)
        selected = sorted(ties, key=lambda row: str(row["policy"]))[0]
        q2_summary.append(
            {
                "case": case.case,
                "optimal_policies": [row["policy"] for row in ties],
                "selected_policy_for_display": selected["policy"],
                "expected_fulfillment_cost": minimum,
                "expected_profit": case.sale - minimum,
                "pass_probability_per_assembly": selected[
                    "pass_probability_per_assembly"
                ],
            }
        )
        logger.info(
            "Q2 case %d: policy=%s, cost=%.6f, profit=%.6f",
            case.case,
            "/".join(str(row["policy"]) for row in ties),
            minimum,
            case.sale - minimum,
        )
    q2_fields = (
        "case",
        "policy",
        "inspect_component_1",
        "inspect_component_2",
        "inspect_final",
        "dismantle_defective_final",
        "feasible",
        "reason",
        "pass_probability_per_assembly",
        "expected_fulfillment_cost",
        "expected_profit",
    )
    write_csv(RESULTS / "q2_all_policies.csv", q2_rows, q2_fields)
    write_csv(RESULTS / "q2_optimal_policies.csv", q2_optimal_rows, q2_fields)

    logger.info("Q3: enumerating all feasible stationary tree policies")
    q3_policies = generate_q3_policies()
    q3_rows = []
    for policy in q3_policies:
        metrics = q3_evaluate(policy)
        q3_rows.append({**q3_policy_fields(policy), **metrics})
    q3_rows.sort(key=lambda row: float(row["expected_fulfillment_cost"]))
    for rank, row in enumerate(q3_rows, start=1):
        row["rank"] = rank
        row["semi_expected_costs"] = json.dumps(row["semi_expected_costs"])
        row["semi_output_good_probabilities"] = json.dumps(
            row["semi_output_good_probabilities"]
        )
    q3_fields = (
        "rank",
        "inspect_components",
        "inspect_semis",
        "dismantle_semis",
        "inspect_final",
        "dismantle_final",
        "semi_expected_costs",
        "semi_output_good_probabilities",
        "pass_probability_per_final_assembly",
        "expected_fulfillment_cost",
        "expected_profit",
    )
    write_csv(RESULTS / "q3_all_feasible_policies.csv", q3_rows, q3_fields)
    write_csv(RESULTS / "q3_top20_policies.csv", q3_rows[:20], q3_fields)
    q3_best = q3_rows[0]
    logger.info(
        "Q3: feasible=%d, best=%s/%s/%s/%s%s, cost=%.6f, profit=%.6f",
        len(q3_rows),
        q3_best["inspect_components"],
        q3_best["inspect_semis"],
        q3_best["dismantle_semis"],
        q3_best["inspect_final"],
        q3_best["dismantle_final"],
        q3_best["expected_fulfillment_cost"],
        q3_best["expected_profit"],
    )

    logger.info("Q4: posterior propagation under labelled n=100 illustrative records")
    q4_q2_detail, q4_q2_summary = q4_q2_analysis()
    write_csv(
        RESULTS / "q4_q2_posterior_all_policies.csv",
        q4_q2_detail,
        tuple(q4_q2_detail[0].keys()),
    )
    write_csv(
        RESULTS / "q4_q2_posterior_selected.csv",
        q4_q2_summary,
        tuple(q4_q2_summary[0].keys()),
    )
    q4_q3_top, q4_q3_summary = q4_q3_analysis()
    write_csv(
        RESULTS / "q4_q3_posterior_top20.csv",
        q4_q3_top,
        tuple(q4_q3_top[0].keys()),
    )
    logger.info(
        "Q4 Q3: selected=%s/%s/%s/%s%s, posterior mean cost=%.6f",
        q4_q3_summary["inspect_components"],
        q4_q3_summary["inspect_semis"],
        q4_q3_summary["dismantle_semis"],
        q4_q3_summary["inspect_final"],
        q4_q3_summary["dismantle_final"],
        q4_q3_summary["posterior_mean_cost"],
    )
    sensitivity = q4_sensitivity()
    write_csv(
        RESULTS / "q4_sample_size_sensitivity.csv",
        sensitivity,
        tuple(sensitivity[0].keys()),
    )

    summary = {
        "provenance": {
            "problem": "2024 CUMCM B - production process decisions",
            "solution_mode": "independent; original statement only",
            "generated_by": Path(__file__).name,
        },
        "q1": {
            "configuration": asdict(cfg),
            "selected_boundaries": {
                str(n): {
                    "accept_max": q1_boundary(n, cfg)[0],
                    "reject_min": q1_boundary(n, cfg)[1],
                }
                for n in (8, 43, 50, 100, 200, 500, 1000, 2000)
            },
            "operating_characteristics": q1_oc,
        },
        "q2": q2_summary,
        "q3": {
            "feasible_policy_count": len(q3_rows),
            "best_policy": {
                key: q3_best[key]
                for key in (
                    "inspect_components",
                    "inspect_semis",
                    "dismantle_semis",
                    "inspect_final",
                    "dismantle_final",
                    "expected_fulfillment_cost",
                    "expected_profit",
                    "pass_probability_per_final_assembly",
                )
            },
        },
        "q4": {
            "data_status": (
                "The statement gives no raw sample sizes/counts. Numerical uncertainty results "
                "are explicitly illustrative records with n=100 and x=n*listed_rate, not claimed observations."
            ),
            "prior": "independent Jeffreys Beta(0.5, 0.5)",
            "q2_selected": q4_q2_summary,
            "q3_selected": q4_q3_summary,
        },
    }
    with (RESULTS / "summary.json").open("w", encoding="utf-8") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
    logger.info("All result files generated successfully under %s", RESULTS)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    logger = setup_logging()
    run_all(logger)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
