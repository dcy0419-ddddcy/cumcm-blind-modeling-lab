from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCAL_PACKAGES = ROOT / "tmp" / "python_packages"
if LOCAL_PACKAGES.exists():
    sys.path.insert(0, str(LOCAL_PACKAGES))

import numpy as np
from scipy.optimize import differential_evolution, minimize

from a_model import (
    Bomb,
    DRONES,
    G,
    TARGET_POINTS_FAST,
    TARGET_POINTS_FINE,
    bomb_duration,
    coverage_margin,
    effective_mask,
    intervals,
    mask_duration,
    missile_arrival_time,
    union_duration,
)


OUT = ROOT / "outputs" / "independent"
COARSE_POINTS = TARGET_POINTS_FAST[::2]


def make_bomb(drone: str, missile: str, x: np.ndarray) -> Bomb:
    heading, speed, burst, fuse = map(float, x)
    return Bomb(drone, missile, heading % 360.0, speed, burst - fuse, fuse)


def penalty_one(b: Bomb) -> float:
    p = 0.0
    if b.drop_time < 0:
        p += 20.0 * (-b.drop_time)
    if b.burst_point[2] < 0:
        p += 0.02 * (-b.burst_point[2])
    if b.burst_time > missile_arrival_time(b.missile):
        p += 20.0 * (b.burst_time - missile_arrival_time(b.missile))
    return p


def optimize_one(drone: str, missile: str, seed: int = 2025, maxiter: int = 180) -> tuple[Bomb, dict]:
    z = DRONES[drone][2]
    max_fuse = float(np.sqrt(2.0 * z / G))
    arrival = missile_arrival_time(missile)

    def objective(x: np.ndarray) -> float:
        b = make_bomb(drone, missile, x)
        p = penalty_one(b)
        if p:
            return 1000.0 + p
        duration = bomb_duration(b, dt=0.05, points=COARSE_POINTS)
        hi = min(b.burst_time + 20.0, arrival)
        t = np.arange(b.burst_time, hi + 0.05, 0.1)
        best_margin = float(np.max(coverage_margin(b, t, COARSE_POINTS)))
        score = duration + 0.02 * min(best_margin, 0.0)
        return -score

    result = differential_evolution(
        objective,
        bounds=[(0, 360), (70, 140), (0, arrival), (0, max_fuse)],
        seed=seed,
        maxiter=maxiter,
        popsize=14,
        tol=1e-6,
        polish=False,
        updating="immediate",
    )

    # Polish on a finer grid; Powell handles the nonsmooth interval-length objective.
    def fine_objective(x: np.ndarray) -> float:
        b = make_bomb(drone, missile, x)
        p = penalty_one(b)
        if p:
            return 1000.0 + p
        return -bomb_duration(b, dt=0.01, points=TARGET_POINTS_FINE)

    local = minimize(
        fine_objective,
        result.x,
        method="Powell",
        bounds=[(0, 360), (70, 140), (0, arrival), (0, max_fuse)],
        options={"maxiter": 400, "xtol": 1e-5, "ftol": 1e-5},
    )
    best_x = local.x if local.fun < fine_objective(result.x) else result.x
    bomb = make_bomb(drone, missile, best_x)
    details = describe([bomb])
    details["optimizer"] = {
        "de_fun": float(result.fun),
        "de_nfev": int(result.nfev),
        "local_fun": float(local.fun),
        "local_nfev": int(local.nfev),
    }
    return bomb, details


def describe(bombs: list[Bomb], dt: float = 0.001) -> dict:
    rows = []
    for b in bombs:
        hi = min(b.burst_time + 20.0, missile_arrival_time(b.missile))
        t = np.arange(b.burst_time, hi + dt / 2, dt)
        m = effective_mask(b, t, TARGET_POINTS_FINE)
        rows.append(
            {
                "drone": b.drone,
                "missile": b.missile,
                "heading_deg": b.heading_deg,
                "speed": b.speed,
                "drop_time": b.drop_time,
                "fuse_time": b.fuse_time,
                "burst_time": b.burst_time,
                "drop_point": b.drop_point.tolist(),
                "burst_point": b.burst_point.tolist(),
                "duration": mask_duration(t, m),
                "intervals": intervals(t, m),
            }
        )
    unions = {}
    for missile in sorted({b.missile for b in bombs}):
        unions[missile] = union_duration(bombs, missile, dt=dt, points=TARGET_POINTS_FINE)
    return {"bombs": rows, "union_duration": unions, "total": float(sum(unions.values()))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["one", "grid"])
    parser.add_argument("--drone", default="FY1")
    parser.add_argument("--missile", default="M1")
    parser.add_argument("--maxiter", type=int, default=180)
    parser.add_argument("--seed", type=int, default=2025)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.mode == "one":
        bomb, result = optimize_one(args.drone, args.missile, args.seed, args.maxiter)
        path = OUT / f"A_one_{args.drone}_{args.missile}.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    grid = {}
    for di, drone in enumerate(DRONES):
        for mi, missile in enumerate(("M1", "M2", "M3")):
            _, result = optimize_one(drone, missile, args.seed + 10 * di + mi, args.maxiter)
            grid[f"{drone}-{missile}"] = result
            print(f"{drone}-{missile}: {result['total']:.3f}")
    path = OUT / "A_single_bomb_grid.json"
    path.write_text(json.dumps(grid, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
