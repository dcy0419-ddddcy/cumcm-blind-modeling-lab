"""Manual tests for q03_design_v001.

Nothing runs on import.  The root runner may call run_tests under its own
budget.  Optical, layout search, and fast-design-key tests do not belong here.
"""
from __future__ import annotations

import copy
import json
import math
import shutil
import tempfile
from pathlib import Path

import q03_design_v001 as q


WORKSPACE = Path(__file__).resolve().parents[2]


def _binding() -> dict:
    return {
        "kind": "SYNTHETIC_Q03_DESIGN_TEST",
        "source_schema": "manual-array-v001",
        "source_version": "v001",
        "sha256": "0" * 64,
    }


def _mirror(
    mirror_id: int,
    x: float,
    y: float,
    *,
    width: float = 6.0,
    height: float = 6.0,
    z: float = 6.0,
    group: int = 0,
) -> dict:
    return {
        "mirror_id": mirror_id,
        "position_key": json.dumps(["manual", mirror_id], separators=(",", ":")),
        "x": float(x),
        "y": float(y),
        "z": float(z),
        "width": float(width),
        "height": float(height),
        "area": float(width) * float(height),
        "group": group,
    }


def _payload(mirrors: list[dict], tower=(0.0, 0.0), name="manual") -> dict:
    return {
        "schema": q.SCHEMA,
        "name": name,
        "version": "manual-v001",
        "tower_xy": [float(tower[0]), float(tower[1])],
        "metadata": {"source_binding": _binding()},
        "mirrors": mirrors,
    }


def _expect_not_accepted(payload: dict, *, schema=None, geometry=None, scope=None) -> None:
    report = q.validate_design(payload)
    assert not report["accepted"], report
    if schema is not None:
        assert report["schema_valid"] is schema, report
    if geometry is not None:
        assert report["geometry_valid"] is geometry, report
    if scope is not None:
        assert report["search_scope_valid"] is scope, report


def test_valid_and_exact_boundaries() -> None:
    exact_pair = _payload(
        [
            _mirror(1, 100.0, 0.0, width=8.0, height=8.0, z=6.0),
            _mirror(2, 113.0, 0.0, width=2.0, height=2.0, z=2.0),
        ]
    )
    report = q.validate_design(exact_pair)
    assert report["accepted"], report
    assert report["minima"]["pair_margin_m"] == 0.0
    assert report["minima"]["tower_exclusion_margin_m"] == 0.0

    field_boundary = _payload([_mirror(1, 350.0, 0.0)])
    assert q.validate_design(field_boundary)["accepted"]

    tower_boundary = _payload(
        [_mirror(1, 250.0, 0.0)], tower=(350.0, 0.0)
    )
    tower_report = q.validate_design(tower_boundary)
    assert tower_report["accepted"], tower_report
    assert tower_report["minima"]["tower_position_margin_m"] == 0.0
    assert tower_report["minima"]["tower_exclusion_margin_m"] == 0.0


def test_no_tolerance_relaxation() -> None:
    short = _payload(
        [
            _mirror(1, 100.0, 0.0, width=8.0, height=8.0),
            _mirror(2, math.nextafter(113.0, 0.0), 0.0, width=2.0, height=2.0),
        ]
    )
    _expect_not_accepted(short, schema=True, geometry=False, scope=True)

    outside = _payload([_mirror(1, math.nextafter(350.0, math.inf), 0.0)])
    _expect_not_accepted(outside, schema=True, geometry=False, scope=True)

    touching_ground = _payload(
        [_mirror(1, 110.0, 0.0, width=4.0, height=4.0, z=2.0)]
    )
    _expect_not_accepted(touching_ground, schema=True, geometry=False, scope=True)


def test_schema_area_duplicates_and_nonfinite() -> None:
    base = _payload([_mirror(1, 110.0, 0.0), _mirror(2, 121.0, 0.0)])

    wrong_area = copy.deepcopy(base)
    wrong_area["mirrors"][0]["area"] = math.nextafter(
        wrong_area["mirrors"][0]["area"], math.inf
    )
    _expect_not_accepted(wrong_area, schema=False)

    duplicate = copy.deepcopy(base)
    duplicate["mirrors"][1]["mirror_id"] = duplicate["mirrors"][0]["mirror_id"]
    _expect_not_accepted(duplicate, schema=False)

    missing = copy.deepcopy(base)
    del missing["mirrors"][0]["height"]
    _expect_not_accepted(missing, schema=False)

    nonfinite = copy.deepcopy(base)
    nonfinite["mirrors"][0]["width"] = math.nan
    _expect_not_accepted(nonfinite, schema=False)


def test_width_height_is_separate_search_scope() -> None:
    payload = _payload(
        [_mirror(1, 110.0, 0.0, width=5.0, height=6.0, z=4.0)]
    )
    report = q.validate_design(payload)
    assert report["schema_valid"]
    assert report["geometry_valid"]
    assert not report["search_scope_valid"]
    assert not report["accepted"]


def test_grouping_is_deterministic_and_complete() -> None:
    mirrors = [
        _mirror(1, 110.0, 0.0),
        _mirror(2, 0.0, 110.0),
        _mirror(3, -110.0, 0.0),
        _mirror(4, 0.0, -110.0),
        _mirror(5, 130.0, 0.0),
        _mirror(6, 0.0, 130.0),
        _mirror(7, -130.0, 0.0),
        _mirror(8, 0.0, -130.0),
    ]
    base = _payload(mirrors)
    first, report1 = q.group_baseline(base, radial_bins=2, angular_bins=4)
    second, report2 = q.group_baseline(base, radial_bins=2, angular_bins=4)
    assert first == second
    assert report1 == report2
    assert report1["nonempty_groups"] == list(range(8))
    assert report1["nonempty_group_count"] == 8
    member_ids = sorted(
        mirror_id
        for group in report1["groups"]
        for mirror_id in group["member_mirror_ids"]
    )
    assert member_ids == list(range(1, 9))
    assert len(report1["per_mirror"]) == len(mirrors)
    assert all(
        row["actual_width_upper_bound_m"] == 8.0
        for row in report1["per_mirror"]
    )


def test_apply_groups_preserves_identity_and_exposes_spacing_failure() -> None:
    base = _payload(
        [
            _mirror(1, 110.0, 0.0, group=0),
            _mirror(2, 121.0, 0.0, group=1),
        ]
    )
    changed = q.apply_groups(base, {0: {"width": 6.1}}, "cross-group-short")
    for before, after in zip(base["mirrors"], changed["mirrors"]):
        for field in ("mirror_id", "position_key", "x", "y", "group"):
            assert after[field] == before[field]
    assert changed["tower_xy"] == base["tower_xy"]
    assert len(changed["mirrors"]) == len(base["mirrors"])
    assert changed["mirrors"][0]["width"] == 6.1
    assert changed["mirrors"][0]["area"] == 6.1 * 6.0
    report = q.validate_design(changed)
    assert report["schema_valid"]
    assert not report["geometry_valid"]
    assert any(
        row["rule"] == "all_pair_max_width_spacing"
        for row in report["violations"]
    )


def test_group_update_is_not_silently_repaired() -> None:
    base = _payload([_mirror(1, 110.0, 0.0, group=3)])
    changed = q.apply_groups(
        base, {3: {"width": 8.5, "height": 7.5, "z": 2.0}}, "unrepaired"
    )
    row = changed["mirrors"][0]
    assert (row["width"], row["height"], row["z"]) == (8.5, 7.5, 2.0)
    assert row["area"] == 8.5 * 7.5
    report = q.validate_design(changed)
    assert not report["geometry_valid"]
    assert not report["accepted"]


def test_save_read_roundtrip_and_no_overwrite() -> None:
    payload = _payload([_mirror(1, 110.0, 0.0)])
    parent = WORKSPACE / "工作记录" / "诊断结果" / "Q03-准备-v001"
    parent.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="q03-design-test-", dir=parent))
    try:
        path = folder / "design.json"
        receipt = q.save_design(payload, path)
        assert receipt["payload_sha256"] == q.payload_sha256(payload)
        assert q.read_design(path) == payload
        try:
            q.save_design(payload, path)
        except FileExistsError:
            pass
        else:
            raise AssertionError("save_design overwrote an existing path")
    finally:
        shutil.rmtree(folder)


def test_from_r027_adapter() -> None:
    payload = q.from_r027()
    report = q.validate_design(payload)
    assert report["accepted"], report
    assert report["n"] == 2981
    assert payload["tower_xy"] == [0.0, -15.0]
    assert all(
        row["width"] == 6.65 and row["height"] == 6.65 and row["z"] == 6.0
        for row in payload["mirrors"]
    )
    assert report["total_area"] == sum(
        row["width"] * row["height"] for row in payload["mirrors"]
    )


def run_tests(include_r027: bool = False) -> dict:
    tests = [
        test_valid_and_exact_boundaries,
        test_no_tolerance_relaxation,
        test_schema_area_duplicates_and_nonfinite,
        test_width_height_is_separate_search_scope,
        test_grouping_is_deterministic_and_complete,
        test_apply_groups_preserves_identity_and_exposes_spacing_failure,
        test_group_update_is_not_silently_repaired,
        test_save_read_roundtrip_and_no_overwrite,
    ]
    if include_r027:
        tests.append(test_from_r027_adapter)
    completed = []
    for test in tests:
        test()
        completed.append(test.__name__)
    return {
        "all_pass": True,
        "tests": completed,
        "include_r027": include_r027,
        "optical_or_search_computation": False,
        "fast_design_key_test_delegated_to_root": True,
    }


if __name__ == "__main__":
    print(json.dumps(run_tests(include_r027=False), ensure_ascii=False, indent=2))
