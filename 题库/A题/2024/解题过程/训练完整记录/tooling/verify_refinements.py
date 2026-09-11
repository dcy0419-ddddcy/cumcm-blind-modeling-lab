"""Independent refinement checks whose outputs are persisted in logs/JSON."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
from scipy.optimize import minimize_scalar

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.bench_dragon import (  # noqa: E402
    BiarcTurnPath,
    find_collision_time,
    path_configuration,
    trajectory_clearance,
)


def q5_local_check(step: float) -> dict:
    path = BiarcTurnPath()
    grid = np.arange(13.0, 16.0 + 0.5 * step, step)
    values = []
    for s in grid:
        values.append(float(np.max(path_configuration(path, float(s)).speeds)))
    k = int(np.argmax(values))
    lo = float(grid[max(0, k - 1)])
    hi = float(grid[min(len(grid) - 1, k + 1)])
    result = minimize_scalar(
        lambda s: -float(np.max(path_configuration(path, float(s)).speeds)),
        bounds=(lo, hi), method="bounded",
        options={"xatol": 2e-10, "maxiter": 120},
    )
    cfg = path_configuration(path, float(result.x))
    peak = float(np.max(cfg.speeds))
    handles = [
        int(i) for i, value in enumerate(cfg.speeds)
        if peak - float(value) < 1e-8
    ]
    return {
        "local_grid_step_m": step,
        "local_interval_head_s_m": [13.0, 16.0],
        "grid_peak": max(values),
        "refined_head_s_m": float(result.x),
        "refined_amplification": peak,
        "head_speed_limit_mps": 2.0 / peak,
        "co_limiting_handle_indices_within_1e-8": handles,
    }


def main() -> None:
    checks = {
        "question2_scan_0_5_s": find_collision_time(scan_step=0.5),
        "question2_scan_1_0_s": find_collision_time(scan_step=1.0),
        "question3_radial_step_0_02_m": trajectory_clearance(
            0.4503373930271521, radial_step=0.02
        ),
        "question5_local_step_0_25_m": q5_local_check(0.25),
        "question5_local_step_0_125_m": q5_local_check(0.125),
    }
    serializable = {}
    for key, value in checks.items():
        if isinstance(value, tuple):
            serializable[key] = list(value)
        else:
            serializable[key] = value
    computed = ROOT / "computed"
    logs = ROOT / "logs"
    computed.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    text = json.dumps(serializable, ensure_ascii=False, indent=2)
    (computed / "refinement_checks.json").write_text(text, encoding="utf-8")
    (logs / "refinement_checks.log").write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
