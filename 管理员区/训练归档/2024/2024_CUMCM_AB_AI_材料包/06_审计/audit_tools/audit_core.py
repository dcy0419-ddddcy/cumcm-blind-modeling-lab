"""Independent pre-reference audit primitives for 2024 CUMCM A/B.

This module contains no answer values and does not read any solution output.
Run: python audit_core.py --self-test
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from typing import Iterable, Sequence


PITCH_Q1 = 0.55
HOLE_OFFSET = 0.275
BOARD_WIDTH = 0.30
HEAD_LENGTH = 3.41
BODY_LENGTH = 2.20
HEAD_HANDLE_DISTANCE = HEAD_LENGTH - 2 * HOLE_OFFSET
BODY_HANDLE_DISTANCE = BODY_LENGTH - 2 * HOLE_OFFSET
HANDLE_COUNT = 224
BOARD_COUNT = 223


def spiral_xy(theta: float, pitch: float) -> tuple[float, float]:
    b = pitch / (2 * math.pi)
    return b * theta * math.cos(theta), b * theta * math.sin(theta)


def spiral_dxy(theta: float, pitch: float) -> tuple[float, float]:
    b = pitch / (2 * math.pi)
    return (
        b * (math.cos(theta) - theta * math.sin(theta)),
        b * (math.sin(theta) + theta * math.cos(theta)),
    )


def spiral_arclength_primitive(theta: float, pitch: float) -> float:
    b = pitch / (2 * math.pi)
    return 0.5 * b * (
        theta * math.sqrt(1 + theta * theta) + math.asinh(theta)
    )


def _sub(a: Sequence[float], b: Sequence[float]) -> tuple[float, float]:
    return float(a[0] - b[0]), float(a[1] - b[1])


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return float(a[0] * b[0] + a[1] * b[1])


def _norm(a: Sequence[float]) -> float:
    return math.hypot(a[0], a[1])


def board_corners(
    front_handle: Sequence[float],
    rear_handle: Sequence[float],
    width: float = BOARD_WIDTH,
    end_offset: float = HOLE_OFFSET,
) -> tuple[tuple[float, float], ...]:
    """Return rectangle corners in cyclic order from two handle centers."""
    axis = _sub(rear_handle, front_handle)
    distance = _norm(axis)
    if distance <= 0:
        raise ValueError("Coincident handle centers cannot define a board")
    ux, uy = axis[0] / distance, axis[1] / distance
    nx, ny = -uy, ux
    fx = front_handle[0] - end_offset * ux
    fy = front_handle[1] - end_offset * uy
    rx = rear_handle[0] + end_offset * ux
    ry = rear_handle[1] + end_offset * uy
    h = width / 2
    return (
        (fx + h * nx, fy + h * ny),
        (rx + h * nx, ry + h * ny),
        (rx - h * nx, ry - h * ny),
        (fx - h * nx, fy - h * ny),
    )


def _polygon_axes(poly: Sequence[Sequence[float]]) -> Iterable[tuple[float, float]]:
    for i in range(len(poly)):
        edge = _sub(poly[(i + 1) % len(poly)], poly[i])
        length = _norm(edge)
        if length <= 0:
            raise ValueError("Degenerate polygon edge")
        yield -edge[1] / length, edge[0] / length


def sat_clearance(
    poly_a: Sequence[Sequence[float]], poly_b: Sequence[Sequence[float]]
) -> float:
    """SAT signed clearance: positive separated, zero touching, negative overlap.

    The negative magnitude is only a penetration proxy, not Euclidean distance.
    """
    best = -math.inf
    for axis in (*_polygon_axes(poly_a), *_polygon_axes(poly_b)):
        pa = [_dot(p, axis) for p in poly_a]
        pb = [_dot(p, axis) for p in poly_b]
        sep = max(min(pb) - max(pa), min(pa) - max(pb))
        best = max(best, sep)
    return best


def binomial_tail_ge(n: int, x: int, p: float) -> float:
    if not (0 <= x <= n and 0 <= p <= 1):
        raise ValueError("Require 0 <= x <= n and 0 <= p <= 1")
    return sum(
        math.comb(n, k) * p**k * (1 - p) ** (n - k) for k in range(x, n + 1)
    )


def binomial_tail_le(n: int, x: int, p: float) -> float:
    if not (0 <= x <= n and 0 <= p <= 1):
        raise ValueError("Require 0 <= x <= n and 0 <= p <= 1")
    return sum(
        math.comb(n, k) * p**k * (1 - p) ** (n - k) for k in range(0, x + 1)
    )


@dataclass(frozen=True)
class NoDisassemblyBaseline:
    good_probability: float
    expected_cost_per_fulfilled_good: float
    expected_profit_per_fulfilled_good: float


def no_disassembly_baseline(
    defect_rates: Sequence[float],
    purchase_costs: Sequence[float],
    component_test_costs: Sequence[float],
    component_tests: Sequence[bool],
    intrinsic_final_defect: float,
    assembly_cost: float,
    final_test_cost: float,
    final_test: bool,
    sale_price: float,
    replacement_loss: float,
) -> NoDisassemblyBaseline:
    """Closed-form oracle under perfect tests, independence, and no disassembly."""
    m = len(defect_rates)
    if not (
        len(purchase_costs)
        == len(component_test_costs)
        == len(component_tests)
        == m
    ):
        raise ValueError("Component vectors must have equal length")
    if any(not 0 <= p < 1 for p in defect_rates) or not 0 <= intrinsic_final_defect <= 1:
        raise ValueError("Defect probabilities are outside the supported range")

    acquisition = 0.0
    good_probability = 1.0 - intrinsic_final_defect
    for p, buy, test_cost, test in zip(
        defect_rates, purchase_costs, component_test_costs, component_tests
    ):
        if test:
            acquisition += (buy + test_cost) / (1 - p)
        else:
            acquisition += buy
            good_probability *= 1 - p

    if good_probability <= 0:
        return NoDisassemblyBaseline(0.0, math.inf, -math.inf)

    attempt_cost = acquisition + assembly_cost + (final_test_cost if final_test else 0)
    if final_test:
        expected_cost = attempt_cost / good_probability
    else:
        expected_cost = (
            attempt_cost + (1 - good_probability) * replacement_loss
        ) / good_probability
    return NoDisassemblyBaseline(
        good_probability, expected_cost, sale_price - expected_cost
    )


def _assert_close(actual: float, expected: float, tol: float = 1e-12) -> None:
    if not math.isclose(actual, expected, rel_tol=tol, abs_tol=tol):
        raise AssertionError(f"{actual!r} != {expected!r}")


def self_test() -> None:
    _assert_close(HEAD_HANDLE_DISTANCE, 2.86)
    _assert_close(BODY_HANDLE_DISTANCE, 1.65)
    if HANDLE_COUNT != BOARD_COUNT + 1:
        raise AssertionError("Handle/board count invariant failed")

    theta0 = 32 * math.pi
    x0, y0 = spiral_xy(theta0, PITCH_Q1)
    _assert_close(x0, 8.8, 1e-12)
    _assert_close(y0, 0.0, 1e-12)
    dx, dy = spiral_dxy(theta0, PITCH_Q1)
    speed_per_theta = math.hypot(dx, dy)
    b = PITCH_Q1 / (2 * math.pi)
    _assert_close(speed_per_theta, b * math.sqrt(1 + theta0 * theta0))

    rect_a = board_corners((0.0, 0.0), (1.65, 0.0))
    rect_separated = board_corners((0.0, 0.31), (1.65, 0.31))
    rect_touching = board_corners((0.0, 0.30), (1.65, 0.30))
    rect_overlap = board_corners((0.0, 0.29), (1.65, 0.29))
    if sat_clearance(rect_a, rect_separated) <= 0:
        raise AssertionError("Separated rectangles classified as collision")
    _assert_close(sat_clearance(rect_a, rect_touching), 0.0)
    if sat_clearance(rect_a, rect_overlap) >= 0:
        raise AssertionError("Overlapping rectangles classified as separated")

    _assert_close(binomial_tail_ge(2, 2, 0.1), 0.01)
    _assert_close(binomial_tail_le(22, 0, 0.1), 0.9**22)
    if not binomial_tail_ge(2, 2, 0.1) <= 0.05:
        raise AssertionError("95% rejection boundary sanity check failed")
    if not binomial_tail_le(22, 0, 0.1) <= 0.10:
        raise AssertionError("90% acceptance boundary sanity check failed")

    baseline = no_disassembly_baseline(
        defect_rates=(0.0, 0.0),
        purchase_costs=(4.0, 18.0),
        component_test_costs=(2.0, 3.0),
        component_tests=(False, False),
        intrinsic_final_defect=0.0,
        assembly_cost=6.0,
        final_test_cost=3.0,
        final_test=False,
        sale_price=56.0,
        replacement_loss=30.0,
    )
    _assert_close(baseline.good_probability, 1.0)
    _assert_close(baseline.expected_cost_per_fulfilled_good, 28.0)
    _assert_close(baseline.expected_profit_per_fulfilled_good, 28.0)

    impossible = no_disassembly_baseline(
        defect_rates=(0.0, 0.0),
        purchase_costs=(4.0, 18.0),
        component_test_costs=(2.0, 3.0),
        component_tests=(False, False),
        intrinsic_final_defect=1.0,
        assembly_cost=6.0,
        final_test_cost=3.0,
        final_test=True,
        sale_price=56.0,
        replacement_loss=30.0,
    )
    if not math.isinf(impossible.expected_cost_per_fulfilled_good):
        raise AssertionError("Non-absorbing production should have infinite expected cost")

    print("audit_core self-test: PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
