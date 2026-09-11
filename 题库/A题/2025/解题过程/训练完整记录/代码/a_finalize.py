from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL_PACKAGES = ROOT / "tmp" / "python_packages"
if LOCAL_PACKAGES.exists():
    sys.path.insert(0, str(LOCAL_PACKAGES))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from a_model import Bomb, TARGET_AXIS, TARGET_POINTS_FINE, bomb_duration
from a_optimize import describe


OUT = ROOT / "outputs" / "independent"


def load_json(name: str) -> dict:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def bomb_from_row(row: dict) -> Bomb:
    return Bomb(
        row["drone"],
        row["missile"],
        row["heading_deg"],
        row["speed"],
        row["drop_time"],
        row["fuse_time"],
    )


def bombs_from(name: str) -> list[Bomb]:
    return [bomb_from_row(row) for row in load_json(name)["bombs"]]


def validation(bombs: list[Bomb]) -> dict:
    issues = []
    for b in bombs:
        if not b.valid():
            issues.append(f"invalid bomb {b.drone}-{b.missile} at {b.drop_time:.3f}")
    for drone in sorted({b.drone for b in bombs}):
        drops = sorted(b.drop_time for b in bombs if b.drone == drone)
        for a, b in zip(drops, drops[1:]):
            if b - a < 1.0 - 1e-9:
                issues.append(f"{drone} drop gap {b-a:.6f} below 1 s")
    return {"valid": not issues, "issues": issues}


def timeline_plot(results: dict) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(10, 7.2), sharex=True)
    colors = {"M1": "#1f4e79", "M2": "#b06a16", "M3": "#2b6f4e"}
    for ax, key in zip(axes, ("q3", "q4", "q5")):
        rows = results[key]["bombs"]
        labels = []
        y = 0
        for row in rows:
            for start, end in row["intervals"]:
                ax.barh(y, end - start, left=start, height=0.6, color=colors[row["missile"]])
            labels.append(f"{row['drone']}-{row['missile']}")
            y += 1
        ax.set_yticks(range(len(labels)), labels)
        ax.set_title(key.upper())
        ax.grid(axis="x", alpha=0.18)
    axes[-1].set_xlabel("Time after assignment (s)")
    fig.tight_layout()
    fig.savefig(OUT / "A_timeline.png", dpi=180)
    plt.close(fig)


def main() -> None:
    q2 = bombs_from("A_one_FY1_M1.json")
    q3 = bombs_from("A_q3.json")
    q4 = bombs_from("A_q4.json")
    single = load_json("A_single_grid_fast.json")
    q5 = []
    q5.extend(q3)
    q5.extend(bombs_from("A_three_FY2_M2.json")[:2])
    q5.append(bomb_from_row(single["FY3-M3"]["bombs"][0]))
    q5.extend(bombs_from("A_three_FY4_M2.json")[1:])
    q5.append(bomb_from_row(single["FY5-M3"]["bombs"][0]))

    problem1 = Bomb("FY1", "M1", 180.0, 120.0, 1.5, 3.6)
    result = {
        "q1": {
            "bomb": describe([problem1], dt=0.002)["bombs"][0],
            "axis_duration": bomb_duration(problem1, dt=0.001, points=TARGET_AXIS),
        },
        "q2": describe(q2, dt=0.005),
        "q3": describe(q3, dt=0.005),
        "q4": describe(q4, dt=0.005),
        "q5": describe(q5, dt=0.005),
        "validation": {
            "q2": validation(q2),
            "q3": validation(q3),
            "q4": validation(q4),
            "q5": validation(q5),
        },
    }
    (OUT / "A_final.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    timeline_plot(result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
