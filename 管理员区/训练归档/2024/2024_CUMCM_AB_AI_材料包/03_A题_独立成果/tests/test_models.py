import math

import numpy as np

from work_independent.A.src.bench_dragon import (
    ArchimedeanSpiral,
    BiarcTurnPath,
    board_geometry,
    minimum_collision_gap,
    path_configuration,
    rectangle_sat_gap,
    rot90,
    spiral_configuration,
    spiral_configuration_at_time,
)


def chord_error(points: np.ndarray) -> float:
    distances = np.linalg.norm(np.diff(points, axis=0), axis=1)
    expected = np.full_like(distances, 1.65)
    expected[0] = 2.86
    return float(np.max(np.abs(distances - expected)))


def velocity_constraint_error(cfg) -> float:
    velocity_vectors = cfg.speeds[:, None] * cfg.tangents
    chords = np.diff(cfg.points, axis=0)
    relative = np.diff(velocity_vectors, axis=0)
    return float(np.max(np.abs(np.sum(chords * relative, axis=1))))


def test_question1_geometry_and_velocity_constraints():
    for time in (0.0, 60.0, 180.0, 300.0):
        cfg = spiral_configuration_at_time(time)
        assert chord_error(cfg.points) < 2e-10
        assert velocity_constraint_error(cfg) < 2e-10


def test_question2_contact_is_bracketed():
    root = 412.47383768213217
    before = spiral_configuration_at_time(root - 1e-3)
    at = spiral_configuration_at_time(root)
    after = spiral_configuration_at_time(root + 1e-3)
    assert minimum_collision_gap(before.points) > 0.0
    gap, pair = minimum_collision_gap(at.points, return_pair=True)
    assert pair == (0, 8)
    assert abs(gap) < 2e-9
    assert minimum_collision_gap(after.points) < 0.0


def test_question3_limiting_configuration_and_neighboring_pitches():
    pitch = 0.4503373930271521
    radius = 4.572603230187777
    for delta, expected_sign in ((-1e-4, -1), (0.0, 0), (1e-4, 1)):
        spiral = ArchimedeanSpiral(pitch + delta)
        # The limiting radius drifts only at O(delta); this fixed-radius check is
        # sufficient to bracket the reported tangency and is independent of the
        # expensive full-trajectory optimizer.
        cfg = spiral_configuration(radius / spiral.b, pitch + delta)
        gap = rectangle_sat_gap(board_geometry(cfg.points), 0, 19)
        if expected_sign < 0:
            assert gap < 0.0
        elif expected_sign > 0:
            assert gap > 0.0
        else:
            assert abs(gap) < 2e-8


def test_question4_biarc_tangency_containment_and_invariance():
    path = BiarcTurnPath()
    assert math.isclose(path.r1 / path.r2, 2.0, rel_tol=0.0, abs_tol=1e-12)
    assert np.linalg.norm(path.tangent(0.0) - path.entry_tangent) < 1e-12
    assert np.linalg.norm(path.tangent(path.turn_length) - path.entry_tangent) < 1e-12
    first_join_tangent = -rot90(path.center_direction)
    second_join_tangent = rot90(-path.center_direction)
    assert np.linalg.norm(first_join_tangent - second_join_tangent) < 1e-12
    samples = np.linspace(0.0, path.turn_length, 20001)
    radii = np.array([np.linalg.norm(path.point(float(s))) for s in samples])
    assert float(np.max(radii)) <= 4.5 + 2e-10
    for fraction in (0.2, 0.4, 2.0 / 3.0, 0.8):
        alternative = BiarcTurnPath(first_radius_fraction=fraction)
        assert math.isclose(alternative.radius_sum, path.radius_sum,
                            rel_tol=0.0, abs_tol=2e-12)
        assert math.isclose(alternative.alpha, path.alpha,
                            rel_tol=0.0, abs_tol=2e-12)
        assert math.isclose(alternative.turn_length, path.turn_length,
                            rel_tol=0.0, abs_tol=2e-12)


def test_question4_chain_constraints():
    path = BiarcTurnPath()
    for time in (-100.0, 0.0, 10.0, 50.0, 100.0):
        cfg = path_configuration(path, time)
        assert chord_error(cfg.points) < 3e-10
        assert velocity_constraint_error(cfg) < 3e-10

