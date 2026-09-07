"""Compact Q2 design bundles and concentric-ring parameter preparation, v001.

No import-time generation, tests, optimization, optical calls or legacy writes.
Public API:
  save_compact(design, directory, stem='design') -> receipt
  read_compact(bundle_path, expected_bundle_sha256=None) -> (Design, report)
  make_ring_spec(tower, w, h, z, ...) -> kwargs for generate_ring_design
  run_tests(workdir=None) -> artificial test report (caller budgets execution)

The compact bundle stores common fields/metadata once, five columns per mirror,
and a small manifest binding both files and the canonical complete design.
Storage validates structure in linear time; full geometry is deliberately left
to the independent approved validator, called by the root at the proper gate.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from numbers import Real
from pathlib import Path
from typing import Any

from q02_design_v002 import Design, SCHEMA as DESIGN_SCHEMA, FIELD_RADIUS, EXCLUSION_RADIUS


COMPACT_SCHEMA = "q02-compact-bundle-v001"
CSV_FIELDS = ["export_index", "mirror_id", "position_key", "x", "y"]
_META_FIELDS = {"design_schema", "name", "version", "declared_n", "tower_xy",
                "width", "height", "installation_height", "metadata"}
_MANIFEST_FIELDS = {"schema", "metadata_file", "metadata_sha256", "mirrors_file",
                    "mirrors_sha256", "canonical_design_sha256", "declared_n",
                    "csv_fields", "coordinate_precision"}


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{label}: finite real number required")
    try:
        result = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(f"{label}: finite real number required") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label}: finite real number required")
    return result


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_payload(design: Design) -> dict[str, Any]:
    """Complete normalized fields in O(N), excluding export/read provenance.

    This is structural validation, not geometry validation. Floating fields are
    normalized to binary64 before writing. Canonical bytes preserve signed zero;
    metadata must be JSON representable and contains no nonfinite numbers.
    """
    if not isinstance(design, Design):
        raise ValueError("Design instance required")
    if any(not isinstance(v, str) or not v for v in (design.name, design.version)):
        raise ValueError("Nonempty name/version required")
    if not isinstance(design.tower_xy, (tuple, list)) or len(design.tower_xy) != 2:
        raise ValueError("tower_xy requires two coordinates")
    if not isinstance(design.mirrors, list) or not design.mirrors:
        raise ValueError("Positive actual mirror count required")
    if not isinstance(design.metadata, dict):
        raise ValueError("metadata must be a JSON mapping")
    try:
        metadata = json.loads(_json_bytes(design.metadata))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("metadata must be strict JSON") from exc
    ids, keys = set(), set()
    mirrors = []
    required = {"mirror_id", "position_key", "x", "y"}
    allowed = required | {"export_row", "source_record_index"}
    for record_index, mirror in enumerate(design.mirrors, start=1):
        if not isinstance(mirror, dict) or not required <= set(mirror) or set(mirror) - allowed:
            raise ValueError(f"Invalid mirror fields at record {record_index}")
        ident, key = mirror["mirror_id"], mirror["position_key"]
        if type(ident) is not int or ident < 1 or ident in ids:
            raise ValueError(f"Invalid/duplicate internal mirror ID at record {record_index}")
        if not isinstance(key, str) or not key or key in keys:
            raise ValueError(f"Invalid/duplicate position key at record {record_index}")
        ids.add(ident)
        keys.add(key)
        mirrors.append({"mirror_id": ident, "position_key": key,
                        "x": _number(mirror["x"], "mirror.x"),
                        "y": _number(mirror["y"], "mirror.y")})
    return {"design_schema": DESIGN_SCHEMA, "name": design.name, "version": design.version,
            "declared_n": len(mirrors),
            "tower_xy": [_number(v, "tower coordinate") for v in design.tower_xy],
            "width": _number(design.width, "width"), "height": _number(design.height, "height"),
            "installation_height": _number(design.installation_height, "installation_height"),
            "metadata": metadata, "mirrors": mirrors}


def design_digest(design: Design) -> str:
    """Identity of all normalized fields, independent of current working dir."""
    return _digest(_json_bytes(canonical_payload(design)))


def _pack(design: Design, stem: str) -> tuple[bytes, bytes, bytes]:
    if not isinstance(stem, str) or not stem or not stem.replace("_", "").replace("-", "").isalnum():
        raise ValueError("stem must contain only letters/digits/underscores/hyphens")
    payload = canonical_payload(design)
    metadata_bytes = _json_bytes({k: v for k, v in payload.items() if k != "mirrors"})
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for export_index, mirror in enumerate(payload["mirrors"], start=1):
        writer.writerow({"export_index": export_index, "mirror_id": mirror["mirror_id"],
                         "position_key": mirror["position_key"],
                         "x": format(mirror["x"], ".17g"), "y": format(mirror["y"], ".17g")})
    mirrors_bytes = buffer.getvalue().encode("utf-8")
    manifest = {"schema": COMPACT_SCHEMA, "metadata_file": stem + ".metadata.json",
                "metadata_sha256": _digest(metadata_bytes), "mirrors_file": stem + ".mirrors.csv",
                "mirrors_sha256": _digest(mirrors_bytes),
                "canonical_design_sha256": _digest(_json_bytes(payload)),
                "declared_n": payload["declared_n"], "csv_fields": CSV_FIELDS,
                "coordinate_precision": "17 significant digits; common numeric fields use JSON repr"}
    return _json_bytes(manifest), metadata_bytes, mirrors_bytes


def _check_manifest(manifest: Any) -> None:
    if not isinstance(manifest, dict) or set(manifest) != _MANIFEST_FIELDS or manifest["schema"] != COMPACT_SCHEMA:
        raise ValueError("Invalid compact manifest schema")
    if type(manifest["declared_n"]) is not int or manifest["declared_n"] < 1:
        raise ValueError("Invalid manifest actual mirror count")
    if manifest["csv_fields"] != CSV_FIELDS:
        raise ValueError("Unexpected compact CSV fields")
    for label in ("metadata_file", "mirrors_file"):
        name = manifest[label]
        if (not isinstance(name, str) or not name or name in (".", "..")
                or "/" in name or "\\" in name or ":" in name or Path(name).is_absolute()):
            raise ValueError("Bundle members must be simple relative filenames")
    for label in ("metadata_sha256", "mirrors_sha256", "canonical_design_sha256"):
        value = manifest[label]
        if (not isinstance(value, str) or len(value) != 64
                or any(c not in "0123456789abcdef" for c in value)):
            raise ValueError(f"Invalid digest in {label}")


def _unpack(manifest_bytes: bytes, metadata_bytes: bytes, mirrors_bytes: bytes,
            expected_bundle_sha256: str | None = None) -> tuple[Design, dict[str, Any]]:
    bundle_hash = _digest(manifest_bytes)
    if expected_bundle_sha256 is not None and bundle_hash != expected_bundle_sha256:
        raise ValueError("BUNDLE_SHA256_MISMATCH")
    manifest = json.loads(manifest_bytes)
    _check_manifest(manifest)
    if _digest(metadata_bytes) != manifest["metadata_sha256"]:
        raise ValueError("METADATA_SHA256_MISMATCH")
    if _digest(mirrors_bytes) != manifest["mirrors_sha256"]:
        raise ValueError("MIRRORS_SHA256_MISMATCH")
    common = json.loads(metadata_bytes)
    if (not isinstance(common, dict) or set(common) != _META_FIELDS
            or common["design_schema"] != DESIGN_SCHEMA):
        raise ValueError("Unexpected common metadata schema")
    if type(common["declared_n"]) is not int or common["declared_n"] != manifest["declared_n"]:
        raise ValueError("Common/manifest mirror count mismatch")
    reader = csv.DictReader(io.StringIO(mirrors_bytes.decode("utf-8"), newline=""))
    if reader.fieldnames != CSV_FIELDS:
        raise ValueError("Compact CSV header mismatch")
    mirrors, mapping = [], []
    for export_index, row in enumerate(reader, start=1):
        if set(row) != set(CSV_FIELDS) or any(value is None for value in row.values()):
            raise ValueError("Malformed compact CSV record")
        if row["export_index"] != str(export_index):
            raise ValueError("Export indices must be consecutive 1-based decimal integers")
        ident = int(row["mirror_id"])
        if row["mirror_id"] != str(ident):
            raise ValueError("Internal mirror ID must use its exact decimal integer form")
        mirror = {"mirror_id": ident, "position_key": row["position_key"],
                  "x": float(row["x"]), "y": float(row["y"]),
                  "source_record_index": export_index, "export_row": reader.line_num}
        mirrors.append(mirror)
        mapping.append({"mirror_id": ident, "position_key": row["position_key"],
                        "export_index": export_index, "export_row": reader.line_num})
    if len(mirrors) != manifest["declared_n"]:
        raise ValueError("CSV actual mirror count differs from bound count")
    design = Design(common["name"], common["version"], common["tower_xy"], common["width"],
                    common["height"], common["installation_height"], mirrors, common["metadata"])
    payload = canonical_payload(design)
    if _digest(_json_bytes(payload)) != manifest["canonical_design_sha256"]:
        raise ValueError("CANONICAL_DESIGN_SHA256_MISMATCH")
    # Fresh Design fields come entirely from the checked disk payload.
    design.tower_xy = tuple(payload["tower_xy"])
    design.width, design.height = payload["width"], payload["height"]
    design.installation_height = payload["installation_height"]
    report = {"schema": COMPACT_SCHEMA, "bundle_sha256": bundle_hash,
              "metadata_sha256": manifest["metadata_sha256"], "mirrors_sha256": manifest["mirrors_sha256"],
              "canonical_design_sha256": manifest["canonical_design_sha256"],
              "all_bound_fields_equal": True, "actual_n": len(mirrors),
              "identity_to_export": mapping,
              "internal_id_to_export_index": {str(v["mirror_id"]): v["export_index"] for v in mapping},
              "common_metadata_stored_once": True, "geometry_validation_performed": False,
              "precision_claim": "canonical normalized fields match, including signed binary64 zeros",
              "hash_scope": "file integrity relative to manifest; expected bundle hash optionally binds manifest"}
    return design, report


def _write_once(path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() == data:
            return  # Idempotent completion; never overwrite different history.
        raise FileExistsError(f"Existing bundle member differs: {path}")
    with path.open("xb") as handle:
        handle.write(data)


def save_compact(design: Design, directory: str | Path, stem: str = "design") -> dict[str, Any]:
    """Write members then commit manifest; identical repeated saves are idempotent.

    Returns a full readback/integrity receipt and internal-ID/export-index map.
    No geometric/optical evaluation is performed. Different existing bytes are
    preserved and rejected. A failed partial write needs a new stem/version.
    """
    manifest_bytes, metadata_bytes, mirrors_bytes = _pack(design, stem)
    target = Path(directory).resolve()
    target.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_bytes)
    metadata_path, mirrors_path = target / manifest["metadata_file"], target / manifest["mirrors_file"]
    bundle_path = target / (stem + ".bundle.json")
    _write_once(metadata_path, metadata_bytes)
    _write_once(mirrors_path, mirrors_bytes)
    _write_once(bundle_path, manifest_bytes)
    rebuilt, report = read_compact(bundle_path, expected_bundle_sha256=_digest(manifest_bytes))
    if _json_bytes(canonical_payload(rebuilt)) != _json_bytes(canonical_payload(design)):
        raise ValueError("COMPLETE_READBACK_FIELD_MISMATCH")
    report.update({"bundle_path": str(bundle_path), "metadata_path": str(metadata_path),
                   "mirrors_path": str(mirrors_path), "complete_readback_fields_equal": True,
                   "bytes": {"bundle": len(manifest_bytes), "metadata": len(metadata_bytes),
                             "mirrors": len(mirrors_bytes)}})
    return report


def read_compact(bundle_path: str | Path, expected_bundle_sha256: str | None = None) -> tuple[Design, dict[str, Any]]:
    """Rebuild using only bundle-relative files, independent of CWD/optimizer.

    Member path traversal and symlink escapes are rejected before reading files.
    The optional expected hash comes from the caller's frozen search/confirmation
    record, so modifying manifest and members together cannot bypass that binding.
    """
    path = Path(bundle_path).resolve()
    manifest_bytes = path.read_bytes()
    if expected_bundle_sha256 is not None and _digest(manifest_bytes) != expected_bundle_sha256:
        raise ValueError("BUNDLE_SHA256_MISMATCH")
    manifest = json.loads(manifest_bytes)
    _check_manifest(manifest)
    member_paths = []
    for key in ("metadata_file", "mirrors_file"):
        member = (path.parent / manifest[key]).resolve()
        if member.parent != path.parent:
            raise ValueError("Bundle member escapes its containing directory")
        member_paths.append(member)
    return _unpack(manifest_bytes, member_paths[0].read_bytes(), member_paths[1].read_bytes(),
                   expected_bundle_sha256)


def make_ring_spec(
    tower: tuple[float, float], w: float, h: float, z: float,
    radial_gap_factor: float = 1.0, angular_gap_factor: float = 1.0,
    phase: float = 0.5, inner: float = 100.5, outer: float | None = None,
    sector: tuple[float, float] | None = None, *, spacing_margin: float = 0.01,
    name: str = "candidate", version: str = "v001",
) -> dict[str, Any]:
    """Prepare kwargs for old generate_ring_design; does not generate positions.

    Positive spacing_margin is an explicit *search restriction*, not a problem
    or mechanical safety requirement. Factors must be >=1. Defaults therefore
    give radial separation w+5+0.01 and angular chord target w+5+0.01 metres.
    Full-ring count = floor(pi / asin(d/(2*r))) for d<=2*r; one point otherwise.
    For a single partial sector of span L use floor(L/(2*asin(d/(2*r)))), at
    least one point. The old half-open generator makes every angular gap at
    least L/count, including the remaining circular wrap gap. Counts are reduced
    if the floating chord check is below d; no upward tolerance is allowed.

    sector is one unwrapped (start,end) pair with 0<end-start<=2*pi; None means
    (0,2*pi). Multiple independently phased sectors are intentionally excluded:
    their seam spacing would need an additional construction/check.
    outer=None chooses 350+||tower||, the largest tower-distance in the fixed
    field. Rings stop before exceeding that bound; old generation still clips
    fixed outer-circle and tower-exclusion violations and recounts actual N.
    All resulting positions must still pass the independent all-pairs validator.
    No tower, N, square mirror or installation height is fixed by this helper.
    """
    if not isinstance(tower, (tuple, list)) or len(tower) != 2:
        raise ValueError("tower must contain two coordinates")
    tower = tuple(_number(v, "tower") for v in tower)
    w, h, z = (_number(value, label) for value, label in ((w, "w"), (h, "h"), (z, "z")))
    if not (2 <= w <= 8 and 2 <= h <= 8 and 2 <= z <= 6 and z > h / 2):
        raise ValueError("Dimensions/height violate the approved geometry")
    if math.hypot(*tower) > FIELD_RADIUS:
        raise ValueError("Tower center is outside the fixed field")
    if w < h:
        raise ValueError("Width below height is outside the approved current search scope")
    radial_gap_factor = _number(radial_gap_factor, "radial_gap_factor")
    angular_gap_factor = _number(angular_gap_factor, "angular_gap_factor")
    spacing_margin = _number(spacing_margin, "spacing_margin")
    inner = _number(inner, "inner")
    phase = _number(phase, "phase")
    if radial_gap_factor < 1 or angular_gap_factor < 1:
        raise ValueError("Gap factors must be >= 1")
    if spacing_margin <= 0 or not w + 5 + spacing_margin > w + 5:
        raise ValueError("Spacing margin must remain strictly positive at the numeric scale")
    if not 0 <= phase < 1:
        raise ValueError("phase must lie in [0,1)")
    if inner <= EXCLUSION_RADIUS:
        raise ValueError("inner must exceed 100 m for the declared positive radial search margin")
    outer = FIELD_RADIUS + math.hypot(*tower) if outer is None else _number(outer, "outer")
    if outer < inner:
        raise ValueError("outer must not be below inner")
    if not isinstance(name, str) or not name or not isinstance(version, str) or not version:
        raise ValueError("Nonempty name and version required")
    if sector is None:
        start, end = 0.0, math.tau
    else:
        if not isinstance(sector, (tuple, list)) or len(sector) != 2:
            raise ValueError("sector must be one (start,end) pair")
        start, end = (_number(value, "sector angle") for value in sector)
    span = end - start
    if not 0 < span <= math.tau:
        raise ValueError("Sector must have 0 < end-start <= 2*pi")
    radial_step = (w + 5 + spacing_margin) * radial_gap_factor
    chord_target = (w + 5 + spacing_margin) * angular_gap_factor
    if not math.isfinite(radial_step) or not math.isfinite(chord_target):
        raise ValueError("Gap computation overflow")
    rings = []
    radius = inner
    while radius <= outer:
        if chord_target >= 2 * radius:
            count = 2 if chord_target == 2 * radius and span == math.tau else 1
        else:
            delta_min = 2 * math.asin(chord_target / (2 * radius))
            # Same exact chord condition; special full-circle expression makes
            # the stated full-ring count formula directly auditable.
            count = (math.floor(math.pi / math.asin(chord_target / (2 * radius)))
                     if span == math.tau else math.floor(span / delta_min))
            count = max(1, count)
        while count >= 2 and 2 * radius * math.sin(span / (2 * count)) < chord_target:
            count -= 1
        rings.append({"ring_id": f"ring{len(rings) + 1}", "radius": radius,
                      "sectors": [{"sector_id": "active", "start": start, "end": end,
                                   "count": count, "phase": phase}]})
        following = math.nextafter(radius + radial_step, math.inf)
        while math.isfinite(following) and following - radius < radial_step:
            following = math.nextafter(following, math.inf)
        if not math.isfinite(following) or following <= radius:
            break
        radius = following
    return {"name": name, "version": version, "tower_xy": tower, "width": w,
            "height": h, "installation_height": z, "rings": rings}


def run_tests(workdir: str | Path | None = None) -> dict[str, Any]:
    """Artificial checks only. Optional workdir adds real I/O and relocation.

    A supplied directory must lie in this authorized workspace; no changes of
    process working directory or temporary files outside the workspace occur.
    No optical code is imported or called. The root accounts for execution.
    """
    from q02_design_v002 import generate_ring_design, validate_design
    results = []

    def run(name, fn):
        try:
            evidence = fn()
            results.append({"name": name, "passed": True, "evidence": evidence or {}})
        except Exception as exc:
            results.append({"name": name, "passed": False, "error_type": type(exc).__name__, "error": str(exc)})

    def expect_error(action, text):
        try:
            action()
        except (ValueError, FileExistsError) as exc:
            assert text in str(exc), str(exc)
        else:
            raise AssertionError("Expected explicit rejection")

    def artificial():
        return Design("artificial compact,中文", "v001", (0.12345678901234567, -0.0),
                      6.0, 4.0, 3.0,
                      [{"mirror_id": 5482341, "position_key": "slot-one", "x": 120.12345678901234, "y": -0.0},
                       {"mirror_id": 7520132, "position_key": "slot-two", "x": 150.98765432109877, "y": 1e-14}],
                      {"purpose": "artificial test only", "nested": {"fraction": 0.12345678901234567},
                       "nominal_order": [{"generation_ordinal": 9, "mirror_id": 5482341},
                                         {"generation_ordinal": 15, "mirror_id": 7520132}]})

    def exact_roundtrip():
        original = artificial()
        packed = _pack(original, "artificial")
        rebuilt, report = _unpack(*packed, expected_bundle_sha256=_digest(packed[0]))
        assert _json_bytes(canonical_payload(original)) == _json_bytes(canonical_payload(rebuilt))
        assert report["all_bound_fields_equal"] and not report["geometry_validation_performed"]
        assert math.copysign(1.0, rebuilt.tower_xy[1]) == -1
        assert math.copysign(1.0, rebuilt.mirrors[0]["y"]) == -1
        assert report["internal_id_to_export_index"] == {"5482341": 1, "7520132": 2}
        assert [v["export_row"] for v in report["identity_to_export"]] == [2, 3]
        assert "metadata" not in packed[2].decode("utf-8").splitlines()[0]
        assert len(next(csv.reader(io.StringIO(packed[2].decode("utf-8"))))) == 5
        assert rebuilt.metadata is not original.metadata
        return {"complete_canonical_fields_equal": True, "signed_zero_preserved": True,
                "metadata_stored_once": True, "internal_ids_not_export_ordinals": True}
    run("compact_complete_roundtrip_signed_zero_and_field_mapping", exact_roundtrip)

    def tampering():
        packed = _pack(artificial(), "artificial")
        changed_common = json.loads(packed[1])
        changed_common["width"] = 7.0
        expect_error(lambda: _unpack(packed[0], _json_bytes(changed_common), packed[2]), "METADATA_SHA256_MISMATCH")
        expect_error(lambda: _unpack(packed[0], packed[1], packed[2] + b"\n"), "MIRRORS_SHA256_MISMATCH")
        expect_error(lambda: _unpack(packed[0] + b"\n", packed[1], packed[2], _digest(packed[0])), "BUNDLE_SHA256_MISMATCH")
        changed_manifest = json.loads(packed[0])
        changed_manifest["metadata_sha256"] = _digest(_json_bytes(changed_common))
        expect_error(lambda: _unpack(_json_bytes(changed_manifest), _json_bytes(changed_common), packed[2]),
                     "CANONICAL_DESIGN_SHA256_MISMATCH")
        bad_path = json.loads(packed[0])
        bad_path["metadata_file"] = "../outside.json"
        expect_error(lambda: _unpack(_json_bytes(bad_path), packed[1], packed[2]), "relative filenames")
        return {"metadata_csv_manifest_and_canonical_digest_rejections": True}
    run("compact_tamper_binding_and_member_path_rejections", tampering)

    def count_and_fields():
        original = artificial()
        original.mirrors[1]["mirror_id"] = original.mirrors[0]["mirror_id"]
        expect_error(lambda: _pack(original, "bad"), "duplicate")
        original = artificial()
        original.mirrors[0]["x"] = float("nan")
        expect_error(lambda: _pack(original, "bad"), "finite real")
        original = artificial()
        original.mirrors[0]["z"] = 9.
        expect_error(lambda: _pack(original, "bad"), "Invalid mirror fields")
        packed = _pack(artificial(), "artificial")
        wrong_csv = packed[2].replace(b"1,5482341", b"2,5482341")
        manifest = json.loads(packed[0])
        manifest["mirrors_sha256"] = _digest(wrong_csv)
        expect_error(lambda: _unpack(_json_bytes(manifest), packed[1], wrong_csv), "Export indices")
    run("compact_duplicate_finite_fields_and_export_order_rejections", count_and_fields)

    def full_ring_geometry():
        spec = make_ring_spec((20., -10.), 6., 4., 3., inner=110., outer=135., spacing_margin=.02,
                              name="artificial-ring-helper")
        radii = [r["radius"] for r in spec["rings"]]
        assert len(radii) == 3
        assert all(b - a >= 11.02 for a, b in zip(radii, radii[1:]))
        for ring in spec["rings"]:
            radius, count = ring["radius"], ring["sectors"][0]["count"]
            assert 2 * radius * math.sin(math.pi / count) >= 11.02
            assert 2 * radius * math.sin(math.pi / (count + 1)) < 11.02
        design, report = generate_ring_design(**spec)
        assert report["actual_n"] == design.n and validate_design(design)["accepted"]
        assert report["validation"]["minima"]["pair_margin"] > 0
        return {"rings": len(radii), "actual_n": design.n,
                "minimum_pair_margin": report["validation"]["minima"]["pair_margin"]}
    run("exact_chord_count_radial_positive_margin_and_expanded_geometry", full_ring_geometry)

    def sector_and_cover():
        spec = make_ring_spec((300., 0.), 8., 2., 2., phase=.25, inner=101., outer=115.,
                              sector=(0., math.pi), spacing_margin=.01,
                              name="artificial-sector-helper")
        design, report = generate_ring_design(**spec)
        assert report["clipped_count"] > 0 and report["actual_n"] == design.n
        assert report["validation"]["accepted"]
        for mirror in design.mirrors:
            assert math.hypot(mirror["x"], mirror["y"]) <= 350.
            assert math.hypot(mirror["x"] - 300., mirror["y"]) >= 100.
        covering = make_ring_spec((300., 0.), 8., 2., 2.)
        radii = [r["radius"] for r in covering["rings"]]
        assert radii[-1] <= 650. and radii[-1] + 13.01 > 650.
        assert covering["tower_xy"] == (300., 0.) and covering["width"] != covering["height"]
        return {"partial_sector_clipped_count": report["clipped_count"], "actual_n": design.n,
                "full_field_tower_relative_cover_bound": 650.}
    run("partial_sector_fixed_boundary_clipping_and_cover_radius", sector_and_cover)

    def reject_search_parameters():
        for kwargs, fragment in (({"spacing_margin": 0.}, "strictly positive"),
                                  ({"spacing_margin": 1e-300}, "strictly positive"),
                                  ({"radial_gap_factor": .99}, "factors"),
                                  ({"angular_gap_factor": .99}, "factors"),
                                  ({"inner": 100.}, "exceed"), ({"phase": 1.}, "phase")):
            expect_error(lambda kw=kwargs: make_ring_spec((0., 0.), 6., 4., 3., **kw), fragment)
        expect_error(lambda: make_ring_spec((0., 0.), 6., 6., 3.), "geometry")
        expect_error(lambda: make_ring_spec((0., 0.), 2., 6., 4.), "search scope")
    run("search_margin_scope_and_strict_height_rejections", reject_search_parameters)

    if workdir is not None:
        def physical_io():
            import shutil
            base = Path(workdir).resolve()
            workspace = Path(__file__).resolve().parents[2]
            if not base.is_relative_to(workspace):
                raise ValueError("Artificial output must remain in the authorized workspace")
            original = artificial()
            receipt = save_compact(original, base / "original", stem="artificial")
            relocated = base / "relocated"
            relocated.mkdir(parents=True, exist_ok=True)
            for label in ("bundle_path", "metadata_path", "mirrors_path"):
                source = Path(receipt[label])
                destination = relocated / source.name
                if destination.exists():
                    assert destination.read_bytes() == source.read_bytes()
                else:
                    shutil.copyfile(source, destination)
            rebuilt, report = read_compact(relocated / "artificial.bundle.json", receipt["bundle_sha256"])
            assert canonical_payload(rebuilt) == canonical_payload(original)
            repeated = save_compact(original, base / "original", stem="artificial")
            assert repeated["bundle_sha256"] == receipt["bundle_sha256"]
            return {"moved_bundle_rebuilt_without_original_path": True,
                    "complete_readback_fields_equal": receipt["complete_readback_fields_equal"],
                    "id_mapping": report["internal_id_to_export_index"], "bytes": receipt["bytes"]}
        run("physical_roundtrip_relocated_bundle_and_idempotent_save", physical_io)
    return {"suite": "q02-compact-v001", "test_count": len(results),
            "passed_count": sum(v["passed"] for v in results),
            "all_passed": all(v["passed"] for v in results), "results": results,
            "scope": "artificial storage and ring-parameter tests; no optical evaluation",
            "randomness": "none", "physical_io_requested": workdir is not None}
