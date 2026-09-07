"""Q02 approved C22 geometry and *diagnostic* design serialization, v002.

No optical evaluator, optimizer, result2.xlsx writer, or import-time execution.
Geometry uses center boundaries. Width >= height is reported as search scope.
All lengths are metres; generator angles are radians. A tolerance only labels
near-boundary observations; it never changes the sign of a constraint test.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from dataclasses import dataclass, field
from numbers import Real
from pathlib import Path
from typing import Any


SCHEMA = "q02-diagnostic-design-v002"
FIELD_RADIUS = 350.0
EXCLUSION_RADIUS = 100.0
CSV_FIELDS = [
    "schema", "name", "version", "declared_n", "tower_x", "tower_y",
    "width", "height", "installation_height", "mirror_id", "position_key",
    "x", "y", "metadata_json",
]
_MIRROR_REQUIRED = {"mirror_id", "position_key", "x", "y"}
_MIRROR_ALLOWED = _MIRROR_REQUIRED | {"export_row", "source_record_index"}


@dataclass
class Design:
    name: str
    version: str
    tower_xy: tuple[float, float]
    width: float
    height: float
    installation_height: float
    mirrors: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def n(self) -> int:
        return len(self.mirrors)

    @property
    def total_area(self) -> float:
        return self.n * self.width * self.height


def _is_finite(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, Real):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, TypeError, ValueError):
        return False


def _json_safe(value: Any) -> Any:
    """Preserve bad-input evidence while keeping reports strict JSON encodable."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, Real):
        return float(value) if _is_finite(value) else repr(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(v) for v in value]
    return repr(value)


def validate_design(design: Design, near_boundary: float = 1e-9) -> dict[str, Any]:
    """Independent exhaustive center-geometry check; no repair or optical claim.

    ``accepted`` means valid schema, approved center geometry and current search
    scope. It does not mean model-domain validity, power feasibility or optimality.
    ``near_boundary`` is a reporting distance, including violations just outside.
    N is derived from the actual list; readers additionally check declared N.
    """
    if not _is_finite(near_boundary) or near_boundary < 0:
        raise ValueError("near_boundary must be a finite nonnegative reporting distance")
    violations: list[dict[str, Any]] = []
    near: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    minima: dict[str, Any] = {
        "field_margin": None, "exclusion_margin": None,
        "pair_distance": None, "pair_margin": None,
        "ground_margin": None, "tower_margin": None,
    }

    def issue(category: str, code: str, **details: Any) -> None:
        violations.append(_json_safe({"category": category, "code": code, **details}))

    def observe(code: str, margin: float, strict: bool = False, **details: Any) -> None:
        good = margin > 0 if strict else margin >= 0
        if not good:
            issue("geometry", code, margin=margin, strict=strict, **details)
        if abs(margin) <= near_boundary:
            near.append(_json_safe({"code": code, "margin": margin,
                                    "passes_exact_test": good, **details}))

    if not isinstance(design, Design):
        issue("schema", "design_type", observed=type(design).__name__)
        return {"schema": SCHEMA, "schema_valid": False, "geometry_valid": False,
                "search_scope_valid": False, "accepted": False,
                "violations": violations, "near_boundaries": [], "duplicate_pairs": [],
                "minima": minima, "n": None, "pair_count_checked": 0,
                "validation_scope": "documented center geometry only; no optical evaluation"}
    for key in ("name", "version"):
        if not isinstance(getattr(design, key), str) or not getattr(design, key):
            issue("schema", "nonempty_string", field=key, value=getattr(design, key))
    globals_valid = True
    for key in ("width", "height", "installation_height"):
        value = getattr(design, key)
        if not _is_finite(value):
            globals_valid = False
            issue("schema", "finite_number", field=key, value=value)
    tower_valid = (isinstance(design.tower_xy, (list, tuple))
                   and len(design.tower_xy) == 2
                   and all(_is_finite(v) for v in design.tower_xy))
    if not tower_valid:
        issue("schema", "tower_xy", value=design.tower_xy)
    if not isinstance(design.metadata, dict):
        issue("schema", "metadata_mapping", value=design.metadata)
    else:
        try:
            json.dumps(design.metadata, allow_nan=False)
        except (TypeError, ValueError, OverflowError):
            issue("schema", "metadata_not_strict_json", value=design.metadata)

    search_ok = None
    if globals_valid:
        for key, low, high in (("width", 2.0, 8.0), ("height", 2.0, 8.0),
                               ("installation_height", 2.0, 6.0)):
            value = float(getattr(design, key))
            observe(key + "_lower", value - low, value=value, bound=low)
            observe(key + "_upper", high - value, value=value, bound=high)
        search_ok = bool(design.width >= design.height)
        if not search_ok:
            issue("search_scope", "width_at_least_height", width=design.width,
                  height=design.height, not_a_problem_hard_constraint=True)
        minima["ground_margin"] = design.installation_height - design.height / 2
        observe("all_pitch_ground", minima["ground_margin"], strict=True)
    if tower_valid:
        tower_radius = math.hypot(*design.tower_xy)
        minima["tower_margin"] = FIELD_RADIUS - tower_radius
        observe("tower_field", minima["tower_margin"], tower_radius=tower_radius)

    good_positions: list[tuple[int, dict[str, Any]]] = []
    if not isinstance(design.mirrors, list):
        issue("schema", "mirrors_list", value=design.mirrors)
        actual_n = None
    else:
        actual_n = len(design.mirrors)
        if actual_n < 1:
            issue("schema", "positive_actual_n", actual_n=actual_n)
        ids: dict[int, int] = {}
        keys: dict[str, int] = {}
        for index, mirror in enumerate(design.mirrors):
            ref = {"record_index": index + 1}
            if not isinstance(mirror, dict):
                issue("schema", "mirror_mapping", **ref, value=mirror)
                continue
            if set(mirror) - _MIRROR_ALLOWED or not _MIRROR_REQUIRED <= set(mirror):
                issue("schema", "mirror_fields", **ref,
                      missing=sorted(_MIRROR_REQUIRED - set(mirror)),
                      unexpected=sorted(str(v) for v in set(mirror) - _MIRROR_ALLOWED))
            mirror_id = mirror.get("mirror_id")
            ref["mirror_id"] = mirror_id
            if type(mirror_id) is not int or mirror_id < 1:
                issue("schema", "positive_integer_mirror_id", **ref)
            elif mirror_id in ids:
                issue("schema", "duplicate_mirror_id", **ref, first_record=ids[mirror_id])
            else:
                ids[mirror_id] = index + 1
            key = mirror.get("position_key")
            if not isinstance(key, str) or not key:
                issue("schema", "position_key", **ref, value=key)
            elif key in keys:
                issue("schema", "duplicate_position_key", **ref, position_key=key,
                      first_record=keys[key])
            else:
                keys[key] = index + 1
            xy_ok = True
            for axis in ("x", "y"):
                if not _is_finite(mirror.get(axis)):
                    xy_ok = False
                    issue("schema", "finite_coordinate", **ref,
                          field=axis, value=mirror.get(axis))
            if not xy_ok:
                continue
            good_positions.append((index, mirror))
            radius = math.hypot(mirror["x"], mirror["y"])
            field_margin = FIELD_RADIUS - radius
            observe("mirror_field", field_margin, **ref, radius=radius)
            minima["field_margin"] = (field_margin if minima["field_margin"] is None
                                      else min(minima["field_margin"], field_margin))
            if tower_valid:
                distance = math.hypot(mirror["x"] - design.tower_xy[0],
                                      mirror["y"] - design.tower_xy[1])
                exclusion_margin = distance - EXCLUSION_RADIUS
                observe("tower_exclusion", exclusion_margin, **ref, distance=distance)
                minima["exclusion_margin"] = (exclusion_margin
                    if minima["exclusion_margin"] is None
                    else min(minima["exclusion_margin"], exclusion_margin))

    pair_count = 0
    for left in range(len(good_positions)):
        ia, ma = good_positions[left]
        for ib, mb in good_positions[left + 1:]:
            pair_count += 1
            distance = math.hypot(ma["x"] - mb["x"], ma["y"] - mb["y"])
            refs = {"record_indices": [ia + 1, ib + 1],
                    "mirror_ids": [ma.get("mirror_id"), mb.get("mirror_id")]}
            if ma["x"] == mb["x"] and ma["y"] == mb["y"]:
                duplicates.append(_json_safe({**refs, "x": ma["x"], "y": ma["y"]}))
                issue("geometry", "duplicate_position", **refs,
                      x=ma["x"], y=ma["y"])
            if minima["pair_distance"] is None or distance < minima["pair_distance"]:
                minima["pair_distance"] = distance
            if globals_valid:
                margin = distance - (design.width + 5)
                observe("pair_spacing", margin, **refs, distance=distance,
                        required_distance=design.width + 5)
                minima["pair_margin"] = (margin if minima["pair_margin"] is None
                                          else min(minima["pair_margin"], margin))
    schema_ok = not any(v["category"] == "schema" for v in violations)
    geometry_ok = schema_ok and not any(v["category"] == "geometry" for v in violations)
    return _json_safe({
        "schema": SCHEMA, "schema_valid": schema_ok, "geometry_valid": geometry_ok,
        "search_scope_valid": schema_ok and search_ok is True,
        "accepted": geometry_ok and search_ok is True,
        "n": actual_n, "total_area": design.total_area if schema_ok else None,
        "violations": violations, "violation_count": len(violations),
        "near_boundaries": near, "near_boundary_reporting_distance": near_boundary,
        "duplicate_pairs": duplicates, "minima": minima,
        "pair_count_checked": pair_count,
        "validation_scope": "approved center geometry and declared search scope; no optical or power validation",
        "comparison_policy": "strict sign tests; near-boundary threshold never relaxes constraints",
    })


def design_to_dict(design: Design) -> dict[str, Any]:
    """Canonical payload excludes read-location provenance from physical identity."""
    check = validate_design(design)
    if not check["schema_valid"]:
        raise ValueError("Cannot serialize invalid schema: " + json.dumps(check["violations"], ensure_ascii=False))
    return {
        "schema": SCHEMA, "name": design.name, "version": design.version,
        "declared_n": design.n, "tower_xy": [float(v) for v in design.tower_xy],
        "width": float(design.width), "height": float(design.height),
        "installation_height": float(design.installation_height),
        "mirrors": [{"mirror_id": m["mirror_id"], "position_key": m["position_key"],
                     "x": float(m["x"]), "y": float(m["y"])} for m in design.mirrors],
        "metadata": design.metadata,
    }


def design_from_dict(payload: dict[str, Any]) -> Design:
    """Rebuild new objects; geometry-invalid diagnostic designs remain readable."""
    expected = {"schema", "name", "version", "declared_n", "tower_xy", "width",
                "height", "installation_height", "mirrors", "metadata"}
    if not isinstance(payload, dict) or set(payload) != expected or payload["schema"] != SCHEMA:
        raise ValueError("Unexpected diagnostic design schema or fields")
    if (type(payload["declared_n"]) is not int or not isinstance(payload["mirrors"], list)
            or payload["declared_n"] != len(payload["mirrors"])):
        raise ValueError("declared_n must exactly equal actual record count")
    if not isinstance(payload["tower_xy"], list) or len(payload["tower_xy"]) != 2:
        raise ValueError("tower_xy must contain exactly two coordinates")
    # JSON roundtrip creates fresh nested objects as well as rejecting NaN/Infinity.
    copied = json.loads(json.dumps(payload, ensure_ascii=False, allow_nan=False))
    design = Design(copied["name"], copied["version"], tuple(copied["tower_xy"]),
                    copied["width"], copied["height"], copied["installation_height"],
                    copied["mirrors"], copied["metadata"])
    check = validate_design(design)
    if not check["schema_valid"]:
        raise ValueError("Invalid diagnostic design: " + json.dumps(check["violations"], ensure_ascii=False))
    for record_index, mirror in enumerate(design.mirrors, start=1):
        mirror["source_record_index"] = record_index
    return design


def _write_text(path: str | Path, content: str, overwrite: bool) -> None:
    with Path(path).open("w" if overwrite else "x", encoding="utf-8", newline="") as handle:
        handle.write(content)


def save_json(design: Design, path: str | Path, *, overwrite: bool = False) -> None:
    _write_text(path, json.dumps(design_to_dict(design), ensure_ascii=False,
                                allow_nan=False, indent=2) + "\n", overwrite)


def read_json(path: str | Path) -> Design:
    with Path(path).open(encoding="utf-8") as handle:
        return design_from_dict(json.load(handle))


def csv_text(design: Design) -> str:
    payload = design_to_dict(design)
    metadata = json.dumps(payload["metadata"], ensure_ascii=False, allow_nan=False,
                          sort_keys=True, separators=(",", ":"))
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for mirror in payload["mirrors"]:
        row = {"schema": SCHEMA, "name": design.name, "version": design.version,
               "declared_n": str(design.n), "tower_x": format(design.tower_xy[0], ".17g"),
               "tower_y": format(design.tower_xy[1], ".17g"),
               "width": format(design.width, ".17g"), "height": format(design.height, ".17g"),
               "installation_height": format(design.installation_height, ".17g"),
               "mirror_id": str(mirror["mirror_id"]), "position_key": mirror["position_key"],
               "x": format(mirror["x"], ".17g"), "y": format(mirror["y"], ".17g"),
               "metadata_json": metadata}
        writer.writerow(row)
    return buffer.getvalue()


def design_from_csv_text(content: str) -> Design:
    reader = csv.DictReader(io.StringIO(content, newline=""))
    if reader.fieldnames != CSV_FIELDS:
        raise ValueError("CSV header must exactly match diagnostic CSV_FIELDS")
    common = None
    mirrors = []
    physical_lines = []
    for row in reader:
        if set(row) != set(CSV_FIELDS) or any(v is None for v in row.values()):
            raise ValueError(f"Malformed CSV record ending at physical line {reader.line_num}")
        current = {"schema": row["schema"], "name": row["name"], "version": row["version"],
                   "declared_n": int(row["declared_n"]),
                   "tower_xy": [float(row["tower_x"]), float(row["tower_y"])],
                   "width": float(row["width"]), "height": float(row["height"]),
                   "installation_height": float(row["installation_height"]),
                   "metadata": json.loads(row["metadata_json"])}
        if common is None:
            common = current
        elif current != common:
            raise ValueError(f"Nonuniform common parameters at physical line {reader.line_num}")
        mirrors.append({"mirror_id": int(row["mirror_id"]), "position_key": row["position_key"],
                        "x": float(row["x"]), "y": float(row["y"])})
        physical_lines.append(reader.line_num)
    if common is None:
        raise ValueError("CSV requires at least one actual mirror record")
    design = design_from_dict({**common, "mirrors": mirrors})
    for mirror, physical_line in zip(design.mirrors, physical_lines):
        # Ending physical line of this CSV record, never a Q1 attachment row.
        mirror["export_row"] = physical_line
    return design


def save_csv(design: Design, path: str | Path, *, overwrite: bool = False) -> None:
    _write_text(path, csv_text(design), overwrite)


def read_csv(path: str | Path) -> Design:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return design_from_csv_text(handle.read())


def stable_mirror_id(position_key: str) -> int:
    """Stable key identity in [1, 2**48], independent of generation order.

    SHA-256 over the key's exact UTF-8 bytes; the first 12 hex digits plus one.
    The generator rejects collisions across all nominal keys, including clipped
    keys. Identity denotes a generator slot: changing geometry can move that
    slot without changing its ID. Neither an export row nor a physical-location
    equality claim is encoded in the ID.
    """
    if not isinstance(position_key, str) or not position_key:
        raise ValueError("Stable identity requires a nonempty position_key")
    return int(hashlib.sha256(position_key.encode("utf-8")).hexdigest()[:12], 16) + 1


def generate_ring_design(
    name: str, version: str, tower_xy: tuple[float, float], width: float,
    height: float, installation_height: float, rings: list[dict[str, Any]],
    *, near_boundary: float = 1e-9,
) -> tuple[Design, dict[str, Any]]:
    """Expand predeclared rings/sectors; clip boundaries, never repair spacing.

    A ring has {ring_id: str, radius: number, sectors: list}. A sector has
    {sector_id: str, start: rad, end: rad, count: int>=0, phase: [0,1)}.
    theta_j = start + (j + phase) * (end-start)/count, j=0,...,count-1.
    Thus [start,end) is half-open, including the start only when phase == 0.
    Require 0 < end-start <= 2*pi; wrapped sectors use unwrapped end > start.
    Position keys encode [ring_id, sector_id, slot] and survive clipping.
    Mirror IDs use stable_mirror_id(key), independent of earlier counts/order.
    Nominal 1-based generation ordinals are stored separately in metadata and
    clipping evidence. Hash collisions are explicit errors, never renumbered.
    Duplicate coordinates are retained and reported as validation failures.
    """
    if (not isinstance(name, str) or not name or not isinstance(version, str) or not version
            or not isinstance(tower_xy, (tuple, list)) or len(tower_xy) != 2
            or not all(_is_finite(v) for v in tower_xy)
            or not all(_is_finite(v) for v in (width, height, installation_height))):
        raise ValueError("Invalid generator identity or common numeric parameters")
    if not (2 <= width <= 8 and 2 <= height <= 8 and 2 <= installation_height <= 6
            and installation_height > height / 2 and math.hypot(*tower_xy) <= FIELD_RADIUS):
        raise ValueError("Common generator parameters violate approved geometry")
    if not isinstance(rings, list):
        raise ValueError("rings must be a list")
    ring_keys = set()
    nominal_n = 0
    mirrors = []
    clipped = []
    id_keys: dict[int, str] = {}
    nominal_order = []
    for ring in rings:
        if not isinstance(ring, dict) or set(ring) != {"ring_id", "radius", "sectors"}:
            raise ValueError("Ring fields must be ring_id, radius, sectors")
        ring_id, radius, sectors = ring["ring_id"], ring["radius"], ring["sectors"]
        if (not isinstance(ring_id, str) or not ring_id or ring_id in ring_keys
                or not _is_finite(radius) or radius < 0 or not isinstance(sectors, list)):
            raise ValueError("Invalid/duplicate ring identity, radius or sectors")
        ring_keys.add(ring_id)
        sector_keys = set()
        for sector in sectors:
            if not isinstance(sector, dict) or set(sector) != {"sector_id", "start", "end", "count", "phase"}:
                raise ValueError("Sector requires sector_id, start, end, count, phase")
            sid = sector["sector_id"]
            start, end, count, phase = (sector[k] for k in ("start", "end", "count", "phase"))
            if (not isinstance(sid, str) or not sid or sid in sector_keys
                    or not all(_is_finite(v) for v in (start, end, phase))
                    or not (0 < end - start <= math.tau) or not 0 <= phase < 1
                    or type(count) is not int or count < 0):
                raise ValueError("Invalid/duplicate sector identity or angular/count parameters")
            sector_keys.add(sid)
            for slot in range(count):
                nominal_n += 1
                theta = start + (slot + phase) * (end - start) / count
                x = tower_xy[0] + radius * math.cos(theta)
                y = tower_xy[1] + radius * math.sin(theta)
                key = json.dumps([ring_id, sid, slot], ensure_ascii=False, separators=(",", ":"))
                mirror_id = stable_mirror_id(key)
                if mirror_id in id_keys and id_keys[mirror_id] != key:
                    raise ValueError("stable_mirror_id_collision: " + json.dumps(
                        {"mirror_id": mirror_id, "first_position_key": id_keys[mirror_id],
                         "second_position_key": key, "generation_ordinal": nominal_n},
                        ensure_ascii=False, sort_keys=True))
                id_keys[mirror_id] = key
                mirror = {"mirror_id": mirror_id, "position_key": key, "x": x, "y": y}
                reasons = []
                field_margin = FIELD_RADIUS - math.hypot(x, y)
                exclusion_margin = math.hypot(x - tower_xy[0], y - tower_xy[1]) - EXCLUSION_RADIUS
                if field_margin < 0:
                    reasons.append("mirror_field")
                if exclusion_margin < 0:
                    reasons.append("tower_exclusion")
                if reasons:
                    clipped.append({**mirror, "generation_ordinal": nominal_n, "reasons": reasons,
                                    "field_margin": field_margin,
                                    "exclusion_margin": exclusion_margin})
                else:
                    mirrors.append(mirror)
                nominal_order.append({"generation_ordinal": nominal_n, "mirror_id": mirror_id,
                                      "position_key": key, "status": "clipped" if reasons else "kept"})
    metadata = {"purpose": "non-final diagnostic design", "generator": "rings-v002",
                "angular_unit": "radian", "endpoint_policy": "[start,end)",
                "phase_policy": "fraction of one angular step, 0 <= phase < 1",
                "mirror_id_policy": "SHA256(UTF8(position_key))[:12] as integer plus 1; collisions rejected",
                "identity_scope": "stable generator slot key, not export row or fixed physical coordinate",
                "nominal_order": nominal_order,
                "nominal_n": nominal_n, "actual_n": len(mirrors),
                "rings": json.loads(json.dumps(rings, ensure_ascii=False, allow_nan=False))}
    design = Design(name, version, tuple(tower_xy), width, height, installation_height,
                    mirrors, metadata)
    validation = validate_design(design, near_boundary=near_boundary)
    report = {"generator": "rings-v002", "nominal_n": nominal_n, "actual_n": design.n,
              "clipped_count": len(clipped), "clipped": clipped,
              "mirror_id_policy": metadata["mirror_id_policy"],
              "duplicate_policy": "retained; validation failure; no silent deletion",
              "spacing_repair": "none", "validation": validation,
              "status": "geometry_and_scope_pass" if validation["accepted"] else "validation_failed",
              "optical_evaluation": "not_performed"}
    return design, _json_safe(report)
