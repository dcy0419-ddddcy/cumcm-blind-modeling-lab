from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL_PACKAGES = ROOT / "tmp" / "python_packages"
if LOCAL_PACKAGES.exists():
    sys.path.insert(0, str(LOCAL_PACKAGES))

import numpy as np
from scipy.optimize import differential_evolution

from a_model import (
    Bomb,
    DRONES,
    G,
    TARGET_AXIS,
    TARGET_POINTS_FAST,
    TARGET_POINTS_FINE,
    coverage_margin,
    missile_arrival_time,
    union_duration,
)
from a_optimize import describe


OUT = ROOT / "outputs" / "independent"
SMALL_POINTS = TARGET_POINTS_FAST[::5]


def heading_to_target(drone: str) -> float:
    p = DRONES[drone]
    return math.degrees(math.atan2(200.0 - p[1], -p[0])) % 360.0


def one_from_x(drone: str, missile: str, x: np.ndarray) -> Bomb:
    heading, speed, burst, fuse = map(float, x)
    return Bomb(drone, missile, heading % 360.0, speed, burst - fuse, fuse)


def valid_penalty(bombs: list[Bomb]) -> float:
    p = 0.0
    for b in bombs:
        if b.drop_time < 0:
            p += 10.0 * -b.drop_time
        if b.burst_point[2] < 0:
            p += 0.01 * -b.burst_point[2]
        if b.burst_time > missile_arrival_time(b.missile):
            p += 10.0 * (b.burst_time - missile_arrival_time(b.missile))
    by_drone: dict[str, list[float]] = {}
    for b in bombs:
        by_drone.setdefault(b.drone, []).append(b.drop_time)
    for drops in by_drone.values():
        drops.sort()
        for a, b in zip(drops, drops[1:]):
            if b - a < 1.0:
                p += 100.0 * (1.0 - (b - a))
    return p


def shaped_score(bombs: list[Bomb], missile: str, dt: float = 0.08, points: np.ndarray = TARGET_AXIS) -> float:
    p = valid_penalty(bombs)
    if p:
        return -1000.0 - p
    duration = union_duration(bombs, missile, dt=dt, points=points)
    best_margins = []
    for b in bombs:
        hi = min(b.burst_time + 20.0, missile_arrival_time(missile))
        if hi <= b.burst_time:
            best_margins.append(-1000.0)
            continue
        t = np.arange(b.burst_time, hi + 0.1, 0.2)
        best_margins.append(float(np.max(coverage_margin(b, t, points))))
    proximity = sum(min(m, 0.0) for m in best_margins)
    return duration + 0.01 * proximity


def optimize_single_fast(drone: str, missile: str, seed: int, maxiter: int = 70) -> Bomb:
    arrival = missile_arrival_time(missile)
    max_fuse = float(np.sqrt(2.0 * DRONES[drone][2] / G))
    h = heading_to_target(drone)
    bounds = [(h - 35.0, h + 35.0), (70.0, 140.0), (0.0, arrival), (0.0, max_fuse)]

    def objective(x: np.ndarray) -> float:
        return -shaped_score([one_from_x(drone, missile, x)], missile)

    result = differential_evolution(
        objective,
        bounds,
        seed=seed,
        maxiter=maxiter,
        popsize=8,
        tol=1e-5,
        polish=False,
    )
    return one_from_x(drone, missile, result.x)


def schedule_from_x(drone: str, missile: str, x: np.ndarray) -> list[Bomb]:
    heading, speed, d1, gap2, gap3, f1, f2, f3 = map(float, x)
    drops = [d1, d1 + gap2, d1 + gap2 + gap3]
    return [Bomb(drone, missile, heading % 360.0, speed, d, f) for d, f in zip(drops, [f1, f2, f3])]


def optimize_three(
    drone: str,
    missile: str,
    seed: int,
    maxiter: int = 120,
    existing: list[Bomb] | None = None,
    points: np.ndarray = TARGET_AXIS,
) -> list[Bomb]:
    existing = existing or []
    arrival = missile_arrival_time(missile)
    max_fuse = float(np.sqrt(2.0 * DRONES[drone][2] / G))
    h = heading_to_target(drone)
    bounds = [
        (h - 35.0, h + 35.0),
        (70.0, 140.0),
        (0.0, max(0.0, arrival - 2.0)),
        (1.0, 20.0),
        (1.0, 20.0),
        (0.0, max_fuse),
        (0.0, max_fuse),
        (0.0, max_fuse),
    ]

    def objective(x: np.ndarray) -> float:
        bombs = schedule_from_x(drone, missile, x)
        score = shaped_score(existing + bombs, missile, dt=0.12, points=points)
        return -score

    result = differential_evolution(
        objective,
        bounds,
        seed=seed,
        maxiter=maxiter,
        popsize=9,
        tol=2e-5,
        polish=False,
    )
    return schedule_from_x(drone, missile, result.x)


def q3(seed: int, maxiter: int) -> dict:
    bombs = optimize_three("FY1", "M1", seed, maxiter)
    return describe(bombs)


def q4_from_x(x: np.ndarray) -> list[Bomb]:
    bombs = []
    for i, drone in enumerate(("FY1", "FY2", "FY3")):
        bombs.append(one_from_x(drone, "M1", x[4 * i : 4 * i + 4]))
    return bombs


def q4(seed: int, maxiter: int) -> dict:
    bounds = []
    initials = []
    for i, drone in enumerate(("FY1", "FY2", "FY3")):
        h = heading_to_target(drone)
        arrival = missile_arrival_time("M1")
        max_fuse = float(np.sqrt(2.0 * DRONES[drone][2] / G))
        bounds.extend([(h - 35.0, h + 35.0), (70.0, 140.0), (0.0, arrival), (0.0, max_fuse)])
        initials.append(optimize_single_fast(drone, "M1", seed + i, maxiter=35))

    def objective(x: np.ndarray) -> float:
        return -shaped_score(q4_from_x(x), "M1", dt=0.1, points=TARGET_AXIS)

    # Seed the population with a staggered version of strong single-bomb candidates.
    rng = np.random.default_rng(seed)
    dim = len(bounds)
    pop_n = 10 * dim
    init = np.empty((pop_n, dim))
    for j, (lo, hi) in enumerate(bounds):
        init[:, j] = rng.uniform(lo, hi, pop_n)
    base = []
    for i, b in enumerate(initials):
        base.extend([b.heading_deg, b.speed, min(b.burst_time + 4.0 * i, missile_arrival_time("M1") - 0.1), b.fuse_time])
    init[0, :] = np.asarray(base)
    result = differential_evolution(
        objective,
        bounds,
        seed=seed,
        maxiter=maxiter,
        popsize=10,
        tol=2e-5,
        polish=False,
        init=init,
    )
    return describe(q4_from_x(result.x))


def single_grid(seed: int, maxiter: int) -> dict:
    out = {}
    for i, drone in enumerate(DRONES):
        for j, missile in enumerate(("M1", "M2", "M3")):
            b = optimize_single_fast(drone, missile, seed + i * 10 + j, maxiter)
            out[f"{drone}-{missile}"] = describe([b])
            print(f"{drone}-{missile}: strict {out[f'{drone}-{missile}']['total']:.3f}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["q3", "q4", "grid", "three", "three_strict"])
    parser.add_argument("--drone", default="FY1")
    parser.add_argument("--missile", default="M1")
    parser.add_argument("--seed", type=int, default=2025)
    parser.add_argument("--maxiter", type=int, default=100)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.mode == "q3":
        result = q3(args.seed, args.maxiter)
        name = "A_q3.json"
    elif args.mode == "q4":
        result = q4(args.seed, args.maxiter)
        name = "A_q4.json"
    elif args.mode == "grid":
        result = single_grid(args.seed, args.maxiter)
        name = "A_single_grid_fast.json"
    else:
        pts = SMALL_POINTS if args.mode == "three_strict" else TARGET_AXIS
        result = describe(optimize_three(args.drone, args.missile, args.seed, args.maxiter, points=pts))
        suffix = "strict" if args.mode == "three_strict" else "axis"
        name = f"A_three_{suffix}_{args.drone}_{args.missile}.json"
    (OUT / name).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
