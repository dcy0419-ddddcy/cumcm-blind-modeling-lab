from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


G = 9.8
SMOKE_RADIUS = 10.0
SMOKE_SINK = 3.0
SMOKE_LIFE = 20.0
TARGET_CENTER_BOTTOM = np.array([0.0, 200.0, 0.0])
TARGET_RADIUS = 7.0
TARGET_HEIGHT = 10.0

MISSILES = {
    "M1": np.array([20000.0, 0.0, 2000.0]),
    "M2": np.array([19000.0, 600.0, 2100.0]),
    "M3": np.array([18000.0, -600.0, 1900.0]),
}

DRONES = {
    "FY1": np.array([17800.0, 0.0, 1800.0]),
    "FY2": np.array([12000.0, 1400.0, 1400.0]),
    "FY3": np.array([6000.0, -3000.0, 700.0]),
    "FY4": np.array([11000.0, 2000.0, 1800.0]),
    "FY5": np.array([13000.0, -2000.0, 1300.0]),
}


def target_points(n_azimuth: int = 72, n_height: int = 7) -> np.ndarray:
    """Boundary points sufficient for a converged line-of-sight coverage test."""
    phi = np.linspace(0.0, 2.0 * math.pi, n_azimuth, endpoint=False)
    z = np.linspace(0.0, TARGET_HEIGHT, n_height)
    side = np.array(
        [[TARGET_RADIUS * math.cos(a), 200.0 + TARGET_RADIUS * math.sin(a), h] for h in z for a in phi]
    )
    # Disk centers make the cap interiors explicit; maxima still occur on a convex boundary.
    return np.vstack([side, [[0.0, 200.0, 0.0], [0.0, 200.0, TARGET_HEIGHT]]])


TARGET_POINTS_FINE = target_points()
TARGET_POINTS_FAST = target_points(20, 3)
TARGET_AXIS = np.array([[0.0, 200.0, 5.0]])


def missile_position(missile: str, times: np.ndarray) -> np.ndarray:
    start = MISSILES[missile]
    direction = -start / np.linalg.norm(start)
    return start[None, :] + 300.0 * times[:, None] * direction[None, :]


def missile_arrival_time(missile: str) -> float:
    return float(np.linalg.norm(MISSILES[missile]) / 300.0)


@dataclass(frozen=True)
class Bomb:
    drone: str
    missile: str
    heading_deg: float
    speed: float
    drop_time: float
    fuse_time: float

    @property
    def burst_time(self) -> float:
        return self.drop_time + self.fuse_time

    @property
    def velocity(self) -> np.ndarray:
        a = math.radians(self.heading_deg)
        return np.array([self.speed * math.cos(a), self.speed * math.sin(a), 0.0])

    @property
    def drop_point(self) -> np.ndarray:
        return DRONES[self.drone] + self.velocity * self.drop_time

    @property
    def burst_point(self) -> np.ndarray:
        p = DRONES[self.drone] + self.velocity * self.burst_time
        p = p.copy()
        p[2] -= 0.5 * G * self.fuse_time**2
        return p

    def valid(self) -> bool:
        return (
            70.0 <= self.speed <= 140.0
            and self.drop_time >= 0.0
            and self.fuse_time >= 0.0
            and self.burst_point[2] >= 0.0
            and self.burst_time <= missile_arrival_time(self.missile)
        )


def smoke_centers(bomb: Bomb, times: np.ndarray) -> np.ndarray:
    centers = np.repeat(bomb.burst_point[None, :], len(times), axis=0)
    centers[:, 2] -= SMOKE_SINK * (times - bomb.burst_time)
    return centers


def coverage_margin(
    bomb: Bomb,
    times: np.ndarray,
    points: np.ndarray = TARGET_POINTS_FAST,
) -> np.ndarray:
    """Positive iff every sampled target point's sight segment intersects the cloud."""
    times = np.asarray(times, dtype=float)
    p = missile_position(bomb.missile, times)
    c = smoke_centers(bomb, times)
    # Shapes: time x point x xyz.
    ray = points[None, :, :] - p[:, None, :]
    cp = c[:, None, :] - p[:, None, :]
    alpha = np.sum(cp * ray, axis=2) / np.sum(ray * ray, axis=2)
    alpha = np.clip(alpha, 0.0, 1.0)
    nearest = p[:, None, :] + alpha[:, :, None] * ray
    d2 = np.sum((c[:, None, :] - nearest) ** 2, axis=2)
    max_distance = np.sqrt(np.max(d2, axis=1))
    active = (times >= bomb.burst_time) & (times <= bomb.burst_time + SMOKE_LIFE)
    active &= times <= missile_arrival_time(bomb.missile)
    margin = SMOKE_RADIUS - max_distance
    return np.where(active, margin, -1e6)


def effective_mask(bomb: Bomb, times: np.ndarray, points: np.ndarray = TARGET_POINTS_FAST) -> np.ndarray:
    return coverage_margin(bomb, times, points) >= 0.0


def mask_duration(times: np.ndarray, mask: np.ndarray) -> float:
    """Trapezoidal duration of a boolean mask on an equally spaced grid."""
    if len(times) < 2:
        return 0.0
    return float(np.trapezoid(mask.astype(float), times))


def bomb_duration(bomb: Bomb, dt: float = 0.02, points: np.ndarray = TARGET_POINTS_FAST) -> float:
    if not bomb.valid():
        return -1e6
    hi = min(bomb.burst_time + SMOKE_LIFE, missile_arrival_time(bomb.missile))
    times = np.arange(bomb.burst_time, hi + 0.5 * dt, dt)
    return mask_duration(times, effective_mask(bomb, times, points))


def union_duration(bombs: list[Bomb], missile: str, dt: float = 0.02, points: np.ndarray = TARGET_POINTS_FAST) -> float:
    selected = [b for b in bombs if b.missile == missile and b.valid()]
    if not selected:
        return 0.0
    lo = min(b.burst_time for b in selected)
    hi = min(max(b.burst_time + SMOKE_LIFE for b in selected), missile_arrival_time(missile))
    times = np.arange(lo, hi + 0.5 * dt, dt)
    mask = np.zeros(times.shape, dtype=bool)
    for bomb in selected:
        mask |= effective_mask(bomb, times, points)
    return mask_duration(times, mask)


def intervals(times: np.ndarray, mask: np.ndarray) -> list[tuple[float, float]]:
    if not np.any(mask):
        return []
    changes = np.diff(mask.astype(np.int8))
    starts = list(np.flatnonzero(changes == 1) + 1)
    ends = list(np.flatnonzero(changes == -1) + 1)
    if mask[0]:
        starts.insert(0, 0)
    if mask[-1]:
        ends.append(len(mask))
    return [(float(times[a]), float(times[min(b, len(times) - 1)])) for a, b in zip(starts, ends)]


def problem1() -> None:
    b = Bomb("FY1", "M1", 180.0, 120.0, 1.5, 3.6)
    for label, pts in [("axis", TARGET_AXIS), ("full", TARGET_POINTS_FINE)]:
        times = np.arange(b.burst_time, b.burst_time + SMOKE_LIFE + 0.0005, 0.001)
        mask = effective_mask(b, times, pts)
        print(label, "duration", mask_duration(times, mask), "intervals", intervals(times, mask))
    print("drop", b.drop_point, "burst", b.burst_point)


if __name__ == "__main__":
    problem1()
