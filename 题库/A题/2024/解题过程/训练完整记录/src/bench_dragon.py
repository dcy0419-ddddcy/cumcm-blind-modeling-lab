"""Numerical models for 2024 CUMCM Problem A (bench dragon).

The module contains only deterministic geometry and numerical solvers.  Lengths
are in metres, time in seconds and angles in radians.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
from typing import Callable, Iterable

import numpy as np
from scipy.optimize import brentq, minimize_scalar


N_BOARDS = 223
N_HANDLES = N_BOARDS + 1
HEAD_HOLE_DISTANCE = 2.86
BODY_HOLE_DISTANCE = 1.65
BOARD_WIDTH = 0.30
END_OVERHANG = 0.275
TURN_RADIUS = 4.5


def cross2(a: np.ndarray, b: np.ndarray) -> float:
    """Scalar two-dimensional cross product."""

    return float(a[0] * b[1] - a[1] * b[0])


def rot90(v: np.ndarray) -> np.ndarray:
    return np.array([-v[1], v[0]], dtype=float)


def rotate(v: np.ndarray, angle: float) -> np.ndarray:
    c, s = math.cos(angle), math.sin(angle)
    return np.array([c * v[0] - s * v[1], s * v[0] + c * v[1]], dtype=float)


@dataclass(frozen=True)
class ArchimedeanSpiral:
    """Archimedean spiral r=b*theta, theta >= 0."""

    pitch: float

    @property
    def b(self) -> float:
        return self.pitch / (2.0 * math.pi)

    def point(self, theta: float) -> np.ndarray:
        return self.b * theta * np.array([math.cos(theta), math.sin(theta)])

    def derivative(self, theta: float) -> np.ndarray:
        b = self.b
        return b * np.array(
            [math.cos(theta) - theta * math.sin(theta),
             math.sin(theta) + theta * math.cos(theta)]
        )

    def inward_tangent(self, theta: float) -> np.ndarray:
        d = self.derivative(theta)
        return -d / np.linalg.norm(d)

    def arc_primitive(self, theta: float) -> float:
        """Arc length primitive integral_0^theta b*sqrt(1+u^2) du."""

        return 0.5 * self.b * (
            theta * math.sqrt(1.0 + theta * theta) + math.asinh(theta)
        )

    def invert_arc_primitive(self, value: float) -> float:
        """Invert the strictly increasing arc primitive for a nonnegative value."""

        if value < -1e-12:
            raise ValueError(f"arc primitive must be nonnegative, got {value}")
        if value <= 0.0:
            return 0.0
        # The leading term is b*theta^2/2.  Newton converges very rapidly, but
        # the guarded fallback keeps the solver reliable near theta=0.
        theta = max(math.sqrt(2.0 * value / self.b), value / self.b)
        for _ in range(12):
            f = self.arc_primitive(theta) - value
            if abs(f) <= 2e-13 * max(1.0, value):
                return theta
            derivative = self.b * math.sqrt(1.0 + theta * theta)
            candidate = theta - f / derivative
            if candidate <= 0.0 or not math.isfinite(candidate):
                break
            theta = candidate
        hi = max(1.0, theta)
        while self.arc_primitive(hi) < value:
            hi *= 2.0
        return float(brentq(lambda z: self.arc_primitive(z) - value, 0.0, hi,
                            xtol=1e-13, rtol=1e-14))

    def theta_after_inward_distance(self, theta0: float, distance: float) -> float:
        target = self.arc_primitive(theta0) - distance
        if target < 0.0:
            raise ValueError("requested inward distance passes the spiral origin")
        return self.invert_arc_primitive(target)


@dataclass
class Configuration:
    parameters: np.ndarray
    points: np.ndarray
    tangents: np.ndarray
    speeds: np.ndarray


def _next_spiral_theta(spiral: ArchimedeanSpiral, theta_front: float,
                       distance: float) -> float:
    """First outward parameter whose chord to theta_front has the given length."""

    p0 = spiral.point(theta_front)

    def residual(theta: float) -> float:
        return float(np.linalg.norm(spiral.point(theta) - p0) - distance)

    # The local arc-length estimate is a lower bound for the angle increment
    # needed to produce the chord.  A short expanding bracket stays well before
    # the first turn of the chord-length function in every configuration used
    # here (verified maximum increment < 1.4 rad).
    local_increment = distance / (
        spiral.b * math.sqrt(1.0 + theta_front * theta_front)
    )
    hi = theta_front + max(0.08, 1.08 * local_increment)
    for _ in range(30):
        if residual(hi) >= 0.0:
            return float(brentq(residual, theta_front, hi,
                                xtol=2e-13, rtol=1e-14))
        hi = theta_front + 1.35 * (hi - theta_front)
    raise RuntimeError("failed to bracket next handle on spiral")


def spiral_configuration(theta_head: float, pitch: float = 0.55,
                         head_speed: float = 1.0,
                         n_handles: int = N_HANDLES) -> Configuration:
    """Build the handle chain on an inward-moving Archimedean spiral."""

    spiral = ArchimedeanSpiral(pitch)
    theta = np.empty(n_handles, dtype=float)
    points = np.empty((n_handles, 2), dtype=float)
    tangents = np.empty((n_handles, 2), dtype=float)
    speeds = np.empty(n_handles, dtype=float)
    theta[0] = theta_head
    points[0] = spiral.point(theta_head)
    tangents[0] = spiral.inward_tangent(theta_head)
    speeds[0] = head_speed
    for i in range(1, n_handles):
        length = HEAD_HOLE_DISTANCE if i == 1 else BODY_HOLE_DISTANCE
        theta[i] = _next_spiral_theta(spiral, theta[i - 1], length)
        points[i] = spiral.point(theta[i])
        tangents[i] = spiral.inward_tangent(theta[i])
        chord = points[i] - points[i - 1]
        denominator = float(np.dot(chord, tangents[i]))
        if abs(denominator) < 1e-12:
            raise RuntimeError(f"singular velocity recursion at handle {i}")
        speeds[i] = speeds[i - 1] * float(np.dot(chord, tangents[i - 1])) / denominator
    return Configuration(theta, points, tangents, speeds)


def spiral_configuration_at_time(time: float, pitch: float = 0.55,
                                 initial_turns: float = 16.0,
                                 head_speed: float = 1.0,
                                 n_handles: int = N_HANDLES) -> Configuration:
    spiral = ArchimedeanSpiral(pitch)
    theta0 = 2.0 * math.pi * initial_turns
    theta_head = spiral.theta_after_inward_distance(theta0, head_speed * time)
    return spiral_configuration(theta_head, pitch, head_speed, n_handles)


@dataclass
class BoardGeometry:
    centers: np.ndarray
    axes: np.ndarray
    normals: np.ndarray
    half_lengths: np.ndarray
    half_width: float = BOARD_WIDTH / 2.0


def board_geometry(points: np.ndarray) -> BoardGeometry:
    chords = points[1:] - points[:-1]
    distances = np.linalg.norm(chords, axis=1)
    axes = chords / distances[:, None]
    normals = np.column_stack((-axes[:, 1], axes[:, 0]))
    centers = 0.5 * (points[1:] + points[:-1])
    half_lengths = 0.5 * distances + END_OVERHANG
    return BoardGeometry(centers, axes, normals, half_lengths)


def rectangle_sat_gap(geom: BoardGeometry, i: int, j: int) -> float:
    """Signed SAT separation: positive apart, zero touching, negative overlap."""

    delta = geom.centers[j] - geom.centers[i]
    ei, ni = geom.axes[i], geom.normals[i]
    ej, nj = geom.axes[j], geom.normals[j]
    li, lj, w = geom.half_lengths[i], geom.half_lengths[j], geom.half_width
    values = []
    for axis, own_extent, other_l, other_e, other_n in (
        (ei, li, lj, ej, nj),
        (ni, w, lj, ej, nj),
        (ej, lj, li, ei, ni),
        (nj, w, li, ei, ni),
    ):
        other_extent = other_l * abs(float(np.dot(other_e, axis))) + \
            w * abs(float(np.dot(other_n, axis)))
        values.append(abs(float(np.dot(delta, axis))) - own_extent - other_extent)
    return max(values)


def minimum_collision_gap(points: np.ndarray, return_pair: bool = False,
                          neighbor_exclusion: int = 1) -> float | tuple[float, tuple[int, int]]:
    """Minimum signed rectangle gap over non-neighbouring bench boards."""

    geom = board_geometry(points)
    n = len(geom.centers)
    radii = np.hypot(geom.half_lengths, geom.half_width)
    best_gap = math.inf
    best_pair = (-1, -1)
    # Bounding circles safely discard pairs that cannot overlap.  A 0.6 m
    # guard band ensures a smooth positive diagnostic before first contact.
    for i in range(n):
        delta = geom.centers[i + neighbor_exclusion + 1:] - geom.centers[i]
        if delta.size == 0:
            continue
        distances = np.linalg.norm(delta, axis=1)
        js = np.nonzero(distances <= radii[i] + radii[i + neighbor_exclusion + 1:] + 0.6)[0]
        for offset in js:
            j = i + neighbor_exclusion + 1 + int(offset)
            gap = rectangle_sat_gap(geom, i, j)
            if gap < best_gap:
                best_gap = gap
                best_pair = (i, j)
    if not math.isfinite(best_gap):
        # This cannot occur for the full dragon but provides a safe sentinel for
        # smaller diagnostic configurations.
        best_gap = 0.6
    return (best_gap, best_pair) if return_pair else best_gap


def find_collision_time(pitch: float = 0.55, initial_turns: float = 16.0,
                        head_speed: float = 1.0,
                        scan_step: float = 0.5) -> tuple[float, tuple[int, int], float]:
    """Return the first rectangle contact time on the inward spiral."""

    spiral = ArchimedeanSpiral(pitch)
    theta0 = 2.0 * math.pi * initial_turns
    max_time = spiral.arc_primitive(theta0) - 1e-8

    @lru_cache(maxsize=512)
    def gap(time_key: float) -> float:
        cfg = spiral_configuration_at_time(time_key, pitch, initial_turns,
                                           head_speed, N_HANDLES)
        return float(minimum_collision_gap(cfg.points))

    lo = 0.0
    flo = gap(lo)
    hi = scan_step
    while hi < max_time:
        fhi = gap(hi)
        if fhi <= 0.0:
            root = float(brentq(lambda z: gap(float(z)), lo, hi,
                                xtol=2e-9, rtol=1e-12))
            cfg = spiral_configuration_at_time(root, pitch, initial_turns,
                                               head_speed, N_HANDLES)
            final_gap, pair = minimum_collision_gap(cfg.points, return_pair=True)
            return root, pair, float(final_gap)
        lo, flo = hi, fhi
        hi += scan_step
    raise RuntimeError("no collision found before the spiral origin")


def pitch_boundary_gap(pitch: float, radius: float = TURN_RADIUS,
                       return_pair: bool = False):
    spiral = ArchimedeanSpiral(pitch)
    theta_head = radius / spiral.b
    cfg = spiral_configuration(theta_head, pitch, 1.0, N_HANDLES)
    return minimum_collision_gap(cfg.points, return_pair=return_pair)


def trajectory_clearance(pitch: float, radius: float = TURN_RADIUS,
                         initial_turns: float = 16.0,
                         radial_step: float = 0.08) \
                         -> tuple[float, float, tuple[int, int]]:
    """Minimum board clearance before the head reaches the turn boundary.

    A coarse radial sweep identifies every local candidate, then each is
    refined with bounded scalar minimization of the global SAT gap.  This is
    essential: the gap need not be monotone and can become negative and then
    positive again before the boundary.
    """

    spiral = ArchimedeanSpiral(pitch)
    start_radius = initial_turns * pitch
    if start_radius <= radius:
        raise ValueError("initial head point must lie outside the turn boundary")

    count = max(3, int(math.ceil((start_radius - radius) / radial_step)) + 1)
    radii = np.linspace(radius, start_radius, count)

    def gap_at_radius(r: float, with_pair: bool = False):
        cfg = spiral_configuration(float(r) / spiral.b, pitch, 1.0, N_HANDLES)
        return minimum_collision_gap(cfg.points, return_pair=with_pair)

    gaps = np.array([float(gap_at_radius(float(r))) for r in radii])
    candidate_indices = [0, len(radii) - 1]
    candidate_indices.extend(
        k for k in range(1, len(radii) - 1)
        if gaps[k] <= gaps[k - 1] and gaps[k] <= gaps[k + 1]
    )
    candidates: list[tuple[float, float]] = [
        (float(gaps[0]), float(radii[0])),
        (float(gaps[-1]), float(radii[-1])),
    ]
    for k in candidate_indices:
        if k == 0 or k == len(radii) - 1:
            continue
        result = minimize_scalar(
            lambda r: float(gap_at_radius(float(r))),
            bounds=(float(radii[k - 1]), float(radii[k + 1])),
            method="bounded", options={"xatol": 2e-9, "maxiter": 80},
        )
        candidates.append((float(result.fun), float(result.x)))
    best_gap, best_radius = min(candidates, key=lambda z: z[0])
    checked_gap, pair = gap_at_radius(best_radius, with_pair=True)
    return float(checked_gap), best_radius, pair


def find_minimum_pitch(radius: float = TURN_RADIUS,
                       bracket: tuple[float, float] = (0.44, 0.46)) \
                       -> tuple[float, float, tuple[int, int], float]:
    """Smallest pitch with no collision during the complete inward approach."""

    lo, hi = bracket
    flo = trajectory_clearance(lo, radius)[0]
    fhi = trajectory_clearance(hi, radius)[0]
    if flo > 0.0 or fhi < 0.0:
        raise ValueError(f"pitch bracket does not straddle contact: {flo=}, {fhi=}")
    root = float(brentq(lambda p: trajectory_clearance(float(p), radius)[0],
                        lo, hi, xtol=2e-10, rtol=2e-10))
    gap, limiting_radius, pair = trajectory_clearance(root, radius,
                                                      radial_step=0.04)
    return root, limiting_radius, pair, float(gap)


@dataclass(frozen=True)
class BiarcTurnPath:
    """Inward spiral, two tangent circular arcs, and central-symmetric outward spiral.

    The coordinate ``s`` is signed travelled arc length.  ``s=0`` is the entry
    point on the radius-4.5 m turn-space boundary.
    """

    pitch: float = 1.7
    turn_radius: float = TURN_RADIUS
    first_radius_fraction: float = 2.0 / 3.0

    def __post_init__(self):
        spiral = ArchimedeanSpiral(self.pitch)
        theta_a = self.turn_radius / spiral.b
        a = spiral.point(theta_a)
        tangent = spiral.inward_tangent(theta_a)
        n = rot90(tangent)
        bpoint = -a
        displacement = bpoint - a
        radius_sum = -float(np.dot(displacement, displacement)) / \
            (2.0 * float(np.dot(displacement, n)))
        r1 = self.first_radius_fraction * radius_sum
        r2 = radius_sum - r1
        if r1 <= 0.0 or r2 <= 0.0:
            raise ValueError("both circular-arc radii must be positive")
        c1 = a - r1 * n
        c2 = bpoint + r2 * n
        center_line = c2 - c1
        d = center_line / np.linalg.norm(center_line)
        join = c1 + r1 * d
        alpha = (math.atan2(n[1], n[0]) - math.atan2(d[1], d[0])) % (2.0 * math.pi)
        if alpha > math.pi:
            # The path inside the turn space uses the minor clockwise/CCW arcs.
            alpha = 2.0 * math.pi - alpha
            raise ValueError("unexpected biarc orientation")
        object.__setattr__(self, "spiral", spiral)
        object.__setattr__(self, "theta_a", theta_a)
        object.__setattr__(self, "entry", a)
        object.__setattr__(self, "exit", bpoint)
        object.__setattr__(self, "entry_tangent", tangent)
        object.__setattr__(self, "normal", n)
        object.__setattr__(self, "radius_sum", radius_sum)
        object.__setattr__(self, "r1", r1)
        object.__setattr__(self, "r2", r2)
        object.__setattr__(self, "c1", c1)
        object.__setattr__(self, "c2", c2)
        object.__setattr__(self, "center_direction", d)
        object.__setattr__(self, "join", join)
        object.__setattr__(self, "alpha", alpha)
        object.__setattr__(self, "l1", r1 * alpha)
        object.__setattr__(self, "l2", r2 * alpha)
        object.__setattr__(self, "turn_length", radius_sum * alpha)
        object.__setattr__(self, "entry_arc_value", spiral.arc_primitive(theta_a))

    def point_tangent(self, s: float) -> tuple[np.ndarray, np.ndarray]:
        if s < 0.0:
            theta = self.spiral.invert_arc_primitive(self.entry_arc_value - s)
            return self.spiral.point(theta), self.spiral.inward_tangent(theta)
        if s <= self.l1:
            radial = rotate(self.normal, -s / self.r1)
            return self.c1 + self.r1 * radial, -rot90(radial)
        if s <= self.turn_length:
            psi = (s - self.l1) / self.r2
            radial = rotate(-self.center_direction, psi)
            return self.c2 + self.r2 * radial, rot90(radial)
        theta = self.spiral.invert_arc_primitive(
            self.entry_arc_value + s - self.turn_length
        )
        # The outward spiral is the central reflection -P(theta), travelled as
        # theta increases, so its tangent is -P'(theta)/|P'(theta)|.
        return -self.spiral.point(theta), self.spiral.inward_tangent(theta)

    def point(self, s: float) -> np.ndarray:
        return self.point_tangent(s)[0]

    def tangent(self, s: float) -> np.ndarray:
        return self.point_tangent(s)[1]


def _previous_path_parameter(path: BiarcTurnPath, s_front: float,
                             p_front: np.ndarray, distance: float) -> float:
    """First earlier path coordinate at the requested chord distance."""

    def residual(s: float) -> float:
        return float(np.linalg.norm(path.point(s) - p_front) - distance)

    hi = s_front
    # A fine scan avoids skipping the first chord root on the small circular arc.
    step = min(0.20, distance / 8.0)
    f_hi = -distance
    for _ in range(20000):
        lo = hi - step
        f_lo = residual(lo)
        if f_lo >= 0.0:
            return float(brentq(residual, lo, hi, xtol=2e-12, rtol=1e-13))
        hi, f_hi = lo, f_lo
        step = min(step * 1.08, 0.12)
    raise RuntimeError("failed to bracket previous handle on composite path")


def path_configuration(path: BiarcTurnPath, s_head: float,
                       head_speed: float = 1.0,
                       n_handles: int = N_HANDLES) -> Configuration:
    parameters = np.empty(n_handles, dtype=float)
    points = np.empty((n_handles, 2), dtype=float)
    tangents = np.empty((n_handles, 2), dtype=float)
    speeds = np.empty(n_handles, dtype=float)
    parameters[0] = s_head
    points[0], tangents[0] = path.point_tangent(s_head)
    speeds[0] = head_speed
    for i in range(1, n_handles):
        length = HEAD_HOLE_DISTANCE if i == 1 else BODY_HOLE_DISTANCE
        parameters[i] = _previous_path_parameter(path, parameters[i - 1],
                                                 points[i - 1], length)
        points[i], tangents[i] = path.point_tangent(parameters[i])
        chord = points[i] - points[i - 1]
        denominator = float(np.dot(chord, tangents[i]))
        if abs(denominator) < 1e-12:
            raise RuntimeError(f"singular velocity recursion at handle {i}")
        speeds[i] = speeds[i - 1] * float(np.dot(chord, tangents[i - 1])) / denominator
    return Configuration(parameters, points, tangents, speeds)


def maximum_unit_head_speed_amplification(
        path: BiarcTurnPath,
        scan_interval: tuple[float, float] | None = None,
        step: float = 0.5,
        refinement_count: int = 24) -> tuple[float, float, int]:
    """Max handle-speed ratio over a complete passage of the dragon.

    The default interval starts one head-board length before the first arc and
    ends after the rear handle has passed the second arc.  A grid scan locates
    candidate peaks and bounded scalar optimization refines them.
    """

    if scan_interval is None:
        # The total centre-to-centre chain length is a conservative arc-length
        # delay.  Chord constraints need slightly more path length on curves.
        chain_chords = HEAD_HOLE_DISTANCE + (N_HANDLES - 2) * BODY_HOLE_DISTANCE
        scan_interval = (-4.0, path.turn_length + chain_chords + 35.0)
    start, stop = scan_interval
    grid = np.arange(start, stop + 0.5 * step, step)
    values = np.empty_like(grid)
    indices = np.empty(len(grid), dtype=int)
    for k, s in enumerate(grid):
        cfg = path_configuration(path, float(s), 1.0, N_HANDLES)
        indices[k] = int(np.argmax(cfg.speeds))
        values[k] = float(cfg.speeds[indices[k]])
    coarse_candidates: list[int] = []
    for k in range(1, len(grid) - 1):
        if values[k] >= values[k - 1] and values[k] >= values[k + 1]:
            coarse_candidates.append(k)
    # Curvature changes when a handle crosses one of three path junctions and
    # can create many shallow local peaks.  Refine the strongest coarse peaks;
    # the complete grid remains the global coverage check.
    coarse_candidates.sort(key=lambda k: values[k], reverse=True)
    selected: list[int] = []
    for k in coarse_candidates:
        if all(abs(grid[k] - grid[j]) >= 0.45 * step for j in selected):
            selected.append(k)
        if len(selected) >= refinement_count:
            break

    candidates: list[tuple[float, float, int]] = [
        (float(values[0]), float(grid[0]), int(indices[0])),
        (float(values[-1]), float(grid[-1]), int(indices[-1])),
    ]
    for k in selected:

        def objective(s: float) -> float:
            cfg = path_configuration(path, float(s), 1.0, N_HANDLES)
            return -float(np.max(cfg.speeds))

        result = minimize_scalar(objective, bounds=(grid[k - 1], grid[k + 1]),
                                 method="bounded",
                                 options={"xatol": 2e-7, "maxiter": 80})
        cfg = path_configuration(path, float(result.x), 1.0, N_HANDLES)
        idx = int(np.argmax(cfg.speeds))
        candidates.append((-float(result.fun), float(result.x), idx))
    return max(candidates, key=lambda z: z[0])


def key_handle_indices() -> list[int]:
    """Handle indices requested in the paper tables."""

    return [0, 1, 51, 101, 151, 201, 223]
