"""Artificial geometry/serialization checks, v002; root runs under its budget.

No import-time tests, no optical calls, no Q1 data access. run_tests(workdir=None)
performs in-memory roundtrips; if workdir is supplied it also writes/reads two
new diagnostic files under this authorized workspace. Test constructions are
artificial assertions, not the three planned problem-specific diagnostic fields.
"""
from __future__ import annotations

import copy
import csv
import io
import json
import math
from pathlib import Path
from typing import Callable

import q02_design_v002 as design_module
from q02_design_v002 import (
    Design, csv_text, design_from_csv_text, design_from_dict, design_to_dict,
    generate_ring_design, read_csv, read_json, save_csv, save_json, stable_mirror_id,
    validate_design,
)


def _design(points=((100.0, 0.0), (111.0, 0.0)), **changes) -> Design:
    params = {"name": "artificial", "version": "v001", "tower_xy": (0.0, 0.0),
              "width": 6.0, "height": 6.0, "installation_height": 4.0,
              "mirrors": [{"mirror_id": i + 1, "position_key": f"artificial-{i + 1}",
                           "x": x, "y": y} for i, (x, y) in enumerate(points)],
              "metadata": {"purpose": "artificial test; not a design proposal"}}
    params.update(changes)
    return Design(**params)


def _has(report: dict, code: str, category: str | None = None) -> bool:
    return any(v["code"] == code and (category is None or v["category"] == category)
               for v in report["violations"])


def _expect_error(action: Callable, text: str = "") -> None:
    try:
        action()
    except (ValueError, FileExistsError) as exc:
        assert not text or text in str(exc), str(exc)
    else:
        raise AssertionError("Expected explicit rejection")


def _ring(ring_id="r", radius=120.0, count=4, phase=0.0, start=0.0, end=math.tau):
    return {"ring_id": ring_id, "radius": radius,
            "sectors": [{"sector_id": "s", "start": start, "end": end,
                         "count": count, "phase": phase}]}


def run_tests(workdir: str | Path | None = None) -> dict:
    results = []

    def run(name: str, check: Callable[[], dict | None]) -> None:
        try:
            details = check()
            results.append({"name": name, "passed": True, "evidence": details or {}})
        except Exception as exc:
            results.append({"name": name, "passed": False,
                            "error_type": type(exc).__name__, "error": str(exc)})

    def equality():
        r = validate_design(_design())
        assert r["accepted"] and r["pair_count_checked"] == 1
        assert r["minima"]["pair_distance"] == 11 and r["minima"]["exclusion_margin"] == 0
        assert {v["code"] for v in r["near_boundaries"]} >= {"pair_spacing", "tower_exclusion"}
        outer = validate_design(_design(((350.0, 0.0),)))
        assert outer["accepted"] and outer["minima"]["field_margin"] == 0
        tower = validate_design(_design(((200.0, 0.0),), tower_xy=(350.0, 0.0)))
        assert tower["accepted"] and tower["minima"]["tower_margin"] == 0
        return {"equal_spacing": r["minima"]["pair_distance"], "boundary_pass": True}
    run("inclusive_center_and_spacing_equalities", equality)

    def outside():
        cases = [(_design(((math.nextafter(350.0, math.inf), 0.0),)), "mirror_field"),
                 (_design(((math.nextafter(100.0, 0.0), 0.0),)), "tower_exclusion"),
                 (_design(((100.0, 0.0), (math.nextafter(111.0, 0.0), 0.0))), "pair_spacing"),
                 (_design(((200.0, 0.0),), tower_xy=(math.nextafter(350.0, math.inf), 0.0)), "tower_field")]
        evidence = []
        for design, code in cases:
            report = validate_design(design, near_boundary=1.0)
            assert not report["geometry_valid"] and _has(report, code)
            observation = next(v for v in report["near_boundaries"] if v["code"] == code)
            assert observation["margin"] < 0 and not observation["passes_exact_test"]
            evidence.append({"code": code, "margin": observation["margin"]})
        return {"one_ulp_violations": evidence, "large_reporting_threshold_did_not_relax": True}
    run("one_ulp_outside_never_accepted_by_tolerance", outside)

    def ground():
        assert _has(validate_design(_design(installation_height=3.0)), "all_pitch_ground")
        above = validate_design(_design(installation_height=math.nextafter(3.0, math.inf)))
        assert above["geometry_valid"] and above["minima"]["ground_margin"] > 0
        rectangle = validate_design(_design(((120.0, 0.0),), width=8.0, height=2.0,
                                             installation_height=2.0))
        assert rectangle["accepted"]
        assert 2.0 < math.hypot(8.0, 2.0) / 2  # Rejects the incorrect diagonal-height rule.
        return {"strict_ground_boundary": True, "horizontal_width_not_vertical_extent": True}
    run("ground_strictness_and_rectangular_vertical_extent", ground)

    def search_separate():
        r = validate_design(_design(((120.0, 0.0),), width=2.0, height=6.0))
        assert r["schema_valid"] and r["geometry_valid"]
        assert not r["search_scope_valid"] and not r["accepted"]
        assert _has(r, "width_at_least_height", "search_scope")
    run("width_height_relation_is_search_scope_only", search_separate)

    def bad_inputs():
        cases = [_design((),), _design(width=float("nan")), _design(tower_xy=(float("inf"), 0)),
                 _design(((float("nan"), 0.0),)), _design(installation_height=float("inf"))]
        for design in cases:
            r = validate_design(design)
            assert not r["schema_valid"] and not r["accepted"]
            json.dumps(r, allow_nan=False)
        for field, value in (("width", 1.0), ("height", 9.0), ("installation_height", 7.0)):
            r = validate_design(_design(**{field: value}))
            assert r["schema_valid"] and not r["geometry_valid"]
        _expect_error(lambda: validate_design(_design(), near_boundary=-1))
        _expect_error(lambda: validate_design(_design(), near_boundary=float("nan")))
    run("finite_inputs_ranges_and_json_safe_failure_reports", bad_inputs)

    def identity():
        for key, value, code in (("mirror_id", 1, "duplicate_mirror_id"),
                                  ("position_key", "artificial-1", "duplicate_position_key")):
            design = _design()
            design.mirrors[1][key] = value
            assert _has(validate_design(design), code, "schema")
        for value in (True, 1.0, 0):
            design = _design()
            design.mirrors[0]["mirror_id"] = value
            assert _has(validate_design(design), "positive_integer_mirror_id", "schema")
        design = _design()
        design.mirrors[0]["z"] = 5.0
        assert _has(validate_design(design), "mirror_fields", "schema")
        duplicates = validate_design(_design(((120.0, 0.0), (120.0, 0.0))))
        assert len(duplicates["duplicate_pairs"]) == 1
        assert _has(duplicates, "duplicate_position") and _has(duplicates, "pair_spacing")
    run("ids_stable_keys_unexpected_dimension_and_duplicate_points", identity)

    def cross_ring():
        design, report = generate_ring_design("artificial-cross", "v001", (0., 0.), 6., 6., 4.,
            [_ring("inner", 120.0, 1), _ring("outer", 125.0, 1)])
        assert design.n == 2 and report["clipped_count"] == 0
        assert _has(report["validation"], "pair_spacing")
        assert report["validation"]["minima"]["pair_distance"] == 5
        assert report["spacing_repair"] == "none"
    run("cross_ring_conflict_is_detected_without_repair", cross_ring)

    def generation_duplicates():
        design, report = generate_ring_design("artificial-duplicate", "v001", (0., 0.), 6., 6., 4.,
            [_ring("a", 120.0, 1), _ring("b", 120.0, 1)])
        assert design.n == 2 and report["nominal_n"] == 2
        assert len(report["validation"]["duplicate_pairs"]) == 1
        assert report["status"] == "validation_failed"
    run("generator_preserves_duplicate_failure_evidence", generation_duplicates)

    def clipping():
        design, report = generate_ring_design("artificial-offset", "v001", (300., 0.), 6., 6., 4.,
            [_ring("small", 90., 1), _ring("wide", 120., 4)])
        assert report["nominal_n"] == 5 and report["actual_n"] == 3 and report["clipped_count"] == 2
        kept_keys = [json.dumps(["wide", "s", slot], separators=(",", ":")) for slot in (1, 2, 3)]
        assert [m["position_key"] for m in design.mirrors] == kept_keys
        assert [m["mirror_id"] for m in design.mirrors] == [stable_mirror_id(key) for key in kept_keys]
        assert [entry["generation_ordinal"] for entry in design.metadata["nominal_order"]
                if entry["status"] == "kept"] == [3, 4, 5]
        assert [entry["generation_ordinal"] for entry in report["clipped"]] == [1, 2]
        assert report["clipped"][0]["reasons"] == ["mirror_field", "tower_exclusion"]
        assert report["clipped"][1]["reasons"] == ["mirror_field"]
        assert not any("export_row" in m for m in design.mirrors)
        assert all(math.hypot(m["x"], m["y"]) <= 350 for m in design.mirrors)
        assert all(math.hypot(m["x"] - 300., m["y"]) >= 100 for m in design.mirrors)
        return {"nominal_n": 5, "actual_n": 3, "surviving_generation_ordinals": [3, 4, 5],
                "stable_mirror_ids": [m["mirror_id"] for m in design.mirrors]}
    run("fixed_field_moving_exclusion_and_separate_generation_order", clipping)

    def stable_count_change():
        before_rings = [_ring("early", 120., 1), _ring("later", 150., 2)]
        after_rings = copy.deepcopy(before_rings)
        after_rings[0]["sectors"][0]["count"] = 3
        before, _ = generate_ring_design("artificial-id-before", "v002", (0., 0.),
                                          6., 6., 4., before_rings)
        after, _ = generate_ring_design("artificial-id-after", "v002", (0., 0.),
                                         6., 6., 4., after_rings)
        before_by_key = {m["position_key"]: m for m in before.mirrors}
        after_by_key = {m["position_key"]: m for m in after.mirrors}
        before_ord = {m["position_key"]: m["generation_ordinal"]
                      for m in before.metadata["nominal_order"]}
        after_ord = {m["position_key"]: m["generation_ordinal"]
                     for m in after.metadata["nominal_order"]}
        assert set(before_by_key) <= set(after_by_key)
        changed_order_keys = []
        for key in before_by_key:
            assert before_by_key[key]["mirror_id"] == after_by_key[key]["mirror_id"]
            assert 1 <= after_by_key[key]["mirror_id"] <= 2 ** 48
            if before_ord[key] != after_ord[key]:
                changed_order_keys.append(key)
        later_keys = [key for key in before_by_key if json.loads(key)[0] == "later"]
        assert len(later_keys) == 2 and set(changed_order_keys) == set(later_keys)
        for key in later_keys:
            assert before_by_key[key]["x"] == after_by_key[key]["x"]
            assert before_by_key[key]["y"] == after_by_key[key]["y"]
        csv_before = design_from_csv_text(csv_text(before))
        csv_after = design_from_csv_text(csv_text(after))
        before_rows = {m["position_key"]: m["export_row"] for m in csv_before.mirrors}
        after_rows = {m["position_key"]: m["export_row"] for m in csv_after.mirrors}
        assert all(before_rows[key] != after_rows[key] for key in later_keys)
        return {"unchanged_ids_for_common_keys": len(before_by_key),
                "generation_and_export_order_changed_keys": changed_order_keys,
                "id_range": "1 through 2**48"}
    run("stable_ids_when_earlier_sector_count_changes", stable_count_change)

    def collision_rejected():
        original = design_module.stable_mirror_id
        try:
            design_module.stable_mirror_id = lambda key: 7
            # The first point is clipped; its nominal identity must still take
            # part in collision detection before the second, retained point.
            _expect_error(lambda: generate_ring_design("artificial-collision", "v002", (0., 0.),
                6., 6., 4., [_ring("clipped", 90., 1), _ring("retained", 120., 1)]),
                "stable_mirror_id_collision")
        finally:
            design_module.stable_mirror_id = original
        _expect_error(lambda: stable_mirror_id(""))
    run("stable_id_collision_is_rejected_including_clipped_keys", collision_rejected)

    def sector_phase():
        design, _ = generate_ring_design("artificial-sector", "v001", (0., 0.), 6., 6., 4.,
                                         [_ring(count=2, start=0., end=math.pi, phase=0.)])
        assert design.n == 2
        assert design.mirrors[0]["x"] == 120. and design.mirrors[0]["y"] == 0.
        assert abs(design.mirrors[1]["x"]) < 1e-12 and abs(design.mirrors[1]["y"] - 120.) < 1e-12
        shifted, _ = generate_ring_design("artificial-phase", "v001", (0., 0.), 6., 6., 4.,
                                         [_ring(count=2, start=0., end=math.pi, phase=.5)])
        assert all(m["y"] > 0 for m in shifted.mirrors)
        assert shifted.mirrors[0]["x"] > 0 and shifted.mirrors[1]["x"] < 0
        assert [m["position_key"] for m in design.mirrors] == [m["position_key"] for m in shifted.mirrors]
        for field, value in (("count", 2.5), ("count", True), ("phase", 1.), ("end", 0.)):
            ring = _ring()
            ring["sectors"][0][field] = value
            _expect_error(lambda: generate_ring_design("bad", "v001", (0., 0.), 6., 6., 4., [ring]))
        _expect_error(lambda: generate_ring_design("bad", "v001", (0., 0.), 6., 6., 3., [_ring()]))
    run("half_open_sectors_fractional_phase_and_parameter_rejections", sector_phase)

    def roundtrip():
        design = _design(((123.12345678901235, -0.000000000000123456789),
                          (145.98765432109877, 0.12345678901234566)),
                         name="人工,清单", tower_xy=(0.12345678901234567, -0.0000123456789012345))
        canonical = design_to_dict(design)
        from_json = design_from_dict(json.loads(json.dumps(canonical, ensure_ascii=False, allow_nan=False)))
        from_csv = design_from_csv_text(csv_text(design))
        assert design_to_dict(from_json) == canonical and design_to_dict(from_csv) == canonical
        assert [m["export_row"] for m in from_csv.mirrors] == [2, 3]
        assert all("export_row" not in m for m in from_json.mirrors)
        assert from_json.mirrors is not design.mirrors and from_json.metadata is not design.metadata
        from_json.mirrors[0]["x"] = 999.
        assert design.mirrors[0]["x"] == canonical["mirrors"][0]["x"]
        wrong = copy.deepcopy(canonical)
        wrong["declared_n"] += 1
        _expect_error(lambda: design_from_dict(wrong), "declared_n")
        parsed = list(csv.DictReader(io.StringIO(csv_text(design))))
        parsed[1]["width"] = "5.9"
        modified = io.StringIO(newline="")
        writer = csv.DictWriter(modified, fieldnames=list(parsed[0]))
        writer.writeheader()
        writer.writerows(parsed)
        _expect_error(lambda: design_from_csv_text(modified.getvalue()), "Nonuniform")
        evidence = {"float_roundtrip_exact": True, "independent_objects": True,
                    "csv_provenance_is_own_file": True, "physical_file_roundtrip": "not_requested"}
        if workdir is not None:
            target_dir = Path(workdir).resolve()
            workspace = Path(__file__).resolve().parents[2]
            if not target_dir.is_relative_to(workspace):
                raise ValueError("Test output must remain within this authorized workspace")
            target_dir.mkdir(parents=True, exist_ok=True)
            json_path = target_dir / "q02-artificial-roundtrip-v002.json"
            csv_path = target_dir / "q02-artificial-roundtrip-v002.csv"
            save_json(design, json_path)
            save_csv(design, csv_path)
            assert design_to_dict(read_json(json_path)) == canonical
            assert design_to_dict(read_csv(csv_path)) == canonical
            _expect_error(lambda: save_json(design, json_path))
            _expect_error(lambda: save_csv(design, csv_path))
            evidence.update({"physical_file_roundtrip": "passed", "json": str(json_path), "csv": str(csv_path)})
        return evidence
    run("json_csv_full_precision_independent_roundtrip_and_uniformity", roundtrip)

    return {"suite": "q02-design-artificial-v002", "test_count": len(results),
            "passed_count": sum(r["passed"] for r in results),
            "all_passed": all(r["passed"] for r in results), "results": results,
            "scope": "artificial geometry and serialization; no optical/power validation",
            "randomness": "none", "problem_specific_diagnostic_layouts_generated": 0}
