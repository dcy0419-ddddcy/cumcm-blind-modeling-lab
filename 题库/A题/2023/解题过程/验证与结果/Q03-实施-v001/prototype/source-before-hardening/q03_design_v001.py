"""Strict heterogeneous Q3 design schema and geometry helpers.

This module does not run optimization, optics, or tests on import.  It keeps
the accepted Q2 sources immutable and represents every effective mirror
dimension explicitly.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from numbers import Integral, Real
from pathlib import Path
from typing import Any, Mapping

import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCHEMA = "q03-heterogeneous-design-v001"
TOP_LEVEL_KEYS = frozenset(
    {"schema", "name", "version", "tower_xy", "metadata", "mirrors"}
)
MIRROR_KEYS = frozenset(
    {
        "mirror_id",
        "position_key",
        "x",
        "y",
        "z",
        "width",
        "height",
        "area",
        "group",
    }
)
FIELD_RADIUS_M = 350.0
TOWER_POSITION_RADIUS_M = 350.0
TOWER_EXCLUSION_RADIUS_M = 100.0
MIN_EDGE_M = 2.0
MAX_EDGE_M = 8.0
MIN_INSTALLATION_HEIGHT_M = 2.0
MAX_INSTALLATION_HEIGHT_M = 6.0


class DesignError(ValueError):
    """The requested design operation cannot preserve the strict Q3 contract."""


def _is_integer(value: Any) -> bool:
    return isinstance(value, Integral) and not isinstance(value, (bool, np.bool_))


def _is_finite_number(value: Any) -> bool:
    return (
        isinstance(value, Real)
        and not isinstance(value, (bool, np.bool_))
        and math.isfinite(float(value))
    )


def _shown(value: Any) -> Any:
    if _is_integer(value):
        return int(value)
    if _is_finite_number(value):
        return float(value)
    if isinstance(value, (str, bool)) or value is None:
        return value
    return repr(value)


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def payload_sha256(payload: Mapping[str, Any]) -> str:
    """Hash the complete ordered design payload with round-trip float repr."""
    return hashlib.sha256(_json_bytes(payload)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _workspace_path(path: str | Path) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = ROOT / resolved
    resolved = resolved.resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise DesignError("Q3 design path must remain inside the authorized workspace") from exc
    return resolved


def validate_design(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the complete Q3 schema and every unordered mirror pair.

    Exact real comparisons are used.  No tolerance can turn a negative margin
    into a pass.  Width >= height is reported separately as search scope.
    """
    violations: list[dict[str, Any]] = []
    schema_valid = True
    geometry_valid = True
    search_scope_valid = True

    def issue(kind: str, rule: str, **details: Any) -> None:
        nonlocal schema_valid, geometry_valid, search_scope_valid
        if kind == "schema":
            schema_valid = False
        elif kind == "geometry":
            geometry_valid = False
        elif kind == "search_scope":
            search_scope_valid = False
        else:
            raise RuntimeError("unknown validation issue kind")
        violations.append(
            {"kind": kind, "rule": rule, **{k: _shown(v) for k, v in details.items()}}
        )

    if not isinstance(payload, dict):
        issue("schema", "payload_must_be_dict", actual_type=type(payload).__name__)
        return {
            "schema_valid": False,
            "geometry_valid": False,
            "search_scope_valid": False,
            "accepted": False,
            "n": 0,
            "total_area": None,
            "minima": {},
            "violations": violations,
        }

    actual_top = set(payload)
    for key in sorted(TOP_LEVEL_KEYS - actual_top):
        issue("schema", "missing_top_level_field", field=key)
    for key in sorted(actual_top - TOP_LEVEL_KEYS):
        issue("schema", "unexpected_top_level_field", field=key)

    if payload.get("schema") != SCHEMA:
        issue("schema", "schema_version", expected=SCHEMA, actual=payload.get("schema"))
    for field in ("name", "version"):
        if not isinstance(payload.get(field), str) or not payload.get(field):
            issue("schema", "nonempty_string", field=field, value=payload.get(field))
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        issue("schema", "metadata_must_be_dict")
    else:
        binding = metadata.get("source_binding")
        if not isinstance(binding, dict):
            issue("schema", "source_binding_must_be_dict")
        else:
            for field in ("kind", "source_schema", "source_version", "sha256"):
                if not isinstance(binding.get(field), str) or not binding.get(field):
                    issue("schema", "source_binding_field", field=field)
            source_sha = binding.get("sha256")
            if isinstance(source_sha, str) and (
                len(source_sha) != 64
                or any(ch not in "0123456789abcdef" for ch in source_sha.lower())
            ):
                issue("schema", "source_binding_sha256", value=source_sha)

    tower = payload.get("tower_xy")
    tower_xy: tuple[float, float] | None = None
    if (
        not isinstance(tower, (list, tuple))
        or len(tower) != 2
        or not all(_is_finite_number(v) for v in tower)
    ):
        issue("schema", "tower_xy_two_finite_numbers", value=tower)
    else:
        tower_xy = (float(tower[0]), float(tower[1]))
        tower_radius = math.hypot(*tower_xy)
        if tower_radius > TOWER_POSITION_RADIUS_M:
            issue(
                "geometry",
                "tower_within_field_radius",
                value=tower_radius,
                bound=TOWER_POSITION_RADIUS_M,
            )

    mirrors = payload.get("mirrors")
    if not isinstance(mirrors, list) or not mirrors:
        issue("schema", "mirrors_nonempty_list")
        mirrors = [] if not isinstance(mirrors, list) else mirrors

    ids: dict[int, int] = {}
    keys: dict[str, int] = {}
    parsed: list[dict[str, Any]] = []
    area_values: list[float] = []
    field_margins: list[float] = []
    exclusion_margins: list[float] = []
    ground_margins: list[float] = []

    for index, mirror in enumerate(mirrors):
        ref = {"mirror_index": index}
        if not isinstance(mirror, dict):
            issue("schema", "mirror_must_be_dict", **ref)
            continue
        actual = set(mirror)
        for field in sorted(MIRROR_KEYS - actual):
            issue("schema", "missing_mirror_field", **ref, field=field)
        for field in sorted(actual - MIRROR_KEYS):
            issue("schema", "unexpected_mirror_field", **ref, field=field)

        mirror_id = mirror.get("mirror_id")
        if not _is_integer(mirror_id) or int(mirror_id) <= 0:
            issue("schema", "positive_integer_mirror_id", **ref, value=mirror_id)
        else:
            mirror_id = int(mirror_id)
            if mirror_id in ids:
                issue(
                    "schema",
                    "duplicate_mirror_id",
                    **ref,
                    mirror_id=mirror_id,
                    first_index=ids[mirror_id],
                )
            else:
                ids[mirror_id] = index

        position_key = mirror.get("position_key")
        if not isinstance(position_key, str) or not position_key:
            issue("schema", "nonempty_position_key", **ref, value=position_key)
        elif position_key in keys:
            issue(
                "schema",
                "duplicate_position_key",
                **ref,
                position_key=position_key,
                first_index=keys[position_key],
            )
        else:
            keys[position_key] = index

        group = mirror.get("group")
        if not _is_integer(group) or int(group) < 0:
            issue("schema", "nonnegative_integer_group", **ref, value=group)

        numeric: dict[str, float] = {}
        for field in ("x", "y", "z", "width", "height", "area"):
            value = mirror.get(field)
            if not _is_finite_number(value):
                issue("schema", "finite_mirror_number", **ref, field=field, value=value)
            else:
                numeric[field] = float(value)
        if len(numeric) != 6:
            continue

        expected_area = numeric["width"] * numeric["height"]
        if numeric["area"] != expected_area:
            issue(
                "schema",
                "declared_area_equals_width_times_height",
                **ref,
                declared=numeric["area"],
                expected=expected_area,
            )
        area_values.append(numeric["area"])

        for field in ("width", "height"):
            value = numeric[field]
            if value < MIN_EDGE_M or value > MAX_EDGE_M:
                issue(
                    "geometry",
                    "edge_range",
                    **ref,
                    field=field,
                    value=value,
                    lower=MIN_EDGE_M,
                    upper=MAX_EDGE_M,
                )
        z = numeric["z"]
        if z < MIN_INSTALLATION_HEIGHT_M or z > MAX_INSTALLATION_HEIGHT_M:
            issue(
                "geometry",
                "installation_height_range",
                **ref,
                value=z,
                lower=MIN_INSTALLATION_HEIGHT_M,
                upper=MAX_INSTALLATION_HEIGHT_M,
            )
        ground_margin = z - numeric["height"] / 2.0
        ground_margins.append(ground_margin)
        if ground_margin <= 0.0:
            issue("geometry", "strictly_above_ground", **ref, margin=ground_margin)
        if numeric["width"] < numeric["height"]:
            issue(
                "search_scope",
                "width_at_least_height",
                **ref,
                width=numeric["width"],
                height=numeric["height"],
            )

        center_radius = math.hypot(numeric["x"], numeric["y"])
        field_margin = FIELD_RADIUS_M - center_radius
        field_margins.append(field_margin)
        if field_margin < 0.0:
            issue("geometry", "mirror_center_in_field", **ref, margin=field_margin)
        if tower_xy is not None:
            exclusion_margin = (
                math.hypot(numeric["x"] - tower_xy[0], numeric["y"] - tower_xy[1])
                - TOWER_EXCLUSION_RADIUS_M
            )
            exclusion_margins.append(exclusion_margin)
            if exclusion_margin < 0.0:
                issue(
                    "geometry",
                    "mirror_center_outside_tower_exclusion",
                    **ref,
                    margin=exclusion_margin,
                )
        parsed.append(
            {
                "index": index,
                "mirror_id": mirror_id,
                "position_key": position_key,
                **numeric,
            }
        )

    pair_distance = math.inf
    pair_margin = math.inf
    pair_count = 0
    for left in range(len(parsed)):
        a = parsed[left]
        for right in range(left + 1, len(parsed)):
            b = parsed[right]
            distance = math.hypot(a["x"] - b["x"], a["y"] - b["y"])
            required = max(a["width"], b["width"]) + 5.0
            margin = distance - required
            pair_count += 1
            pair_distance = min(pair_distance, distance)
            pair_margin = min(pair_margin, margin)
            if margin < 0.0:
                issue(
                    "geometry",
                    "all_pair_max_width_spacing",
                    left_index=a["index"],
                    right_index=b["index"],
                    distance=distance,
                    required=required,
                    margin=margin,
                )

    def finite_min(values: list[float]) -> float | None:
        return float(min(values)) if values else None

    tower_margin = None
    if tower_xy is not None:
        tower_margin = TOWER_POSITION_RADIUS_M - math.hypot(*tower_xy)
    total_area = (
        float(math.fsum(area_values))
        if len(area_values) == len(mirrors) and mirrors
        else None
    )
    minima = {
        "tower_position_margin_m": tower_margin,
        "field_center_margin_m": finite_min(field_margins),
        "tower_exclusion_margin_m": finite_min(exclusion_margins),
        "ground_margin_m": finite_min(ground_margins),
        "pair_distance_m": None if math.isinf(pair_distance) else float(pair_distance),
        "pair_margin_m": None if math.isinf(pair_margin) else float(pair_margin),
        "pair_count_checked": pair_count,
    }
    accepted = bool(schema_valid and geometry_valid and search_scope_valid)
    return {
        "schema_valid": bool(schema_valid),
        "geometry_valid": bool(geometry_valid),
        "search_scope_valid": bool(search_scope_valid),
        "accepted": accepted,
        "n": len(mirrors),
        "total_area": total_area,
        "minima": minima,
        "violations": violations,
    }


def _require_accepted(payload: dict[str, Any], operation: str) -> dict[str, Any]:
    report = validate_design(payload)
    if not report["accepted"]:
        raise DesignError(
            operation
            + " requires an accepted design: "
            + json.dumps(report["violations"][:20], ensure_ascii=False, allow_nan=False)
        )
    return report


def from_r027() -> dict[str, Any]:
    """Expand the accepted R027 compact Q2 bundle into the strict Q3 schema."""
    import q02_compact_v001 as compact

    bundle = (
        ROOT
        / "工作记录"
        / "诊断结果"
        / "Q02-修复-v001"
        / "frozen"
        / "design.bundle.json"
    )
    source, receipt = compact.read_compact(bundle)
    bundle_manifest = json.loads(bundle.read_text(encoding="utf-8"))
    width = float(source.width)
    height = float(source.height)
    z = float(source.installation_height)
    mirrors = [
        {
            "mirror_id": int(row["mirror_id"]),
            "position_key": str(row["position_key"]),
            "x": float(row["x"]),
            "y": float(row["y"]),
            "z": z,
            "width": width,
            "height": height,
            "area": width * height,
            "group": 0,
        }
        for row in source.mirrors
    ]
    payload = {
        "schema": SCHEMA,
        "name": "R027-Q03-baseline",
        "version": "q03-from-r027-v001",
        "tower_xy": [float(v) for v in source.tower_xy],
        "metadata": {
            "source_binding": {
                "kind": "Q02_R027_FROZEN_COMPACT_BUNDLE",
                "source_schema": str(bundle_manifest["schema"]),
                "source_version": str(source.version),
                "sha256": _file_sha256(bundle),
                "relative_path": bundle.relative_to(ROOT).as_posix(),
                "canonical_design_sha256": receipt["canonical_design_sha256"],
            },
            "source_name": str(source.name),
            "source_metadata": copy.deepcopy(source.metadata),
            "expansion": "uniform Q2 scalars copied exactly into every Q3 mirror row",
        },
        "mirrors": mirrors,
    }
    _require_accepted(payload, "from_r027")
    return payload


def _nearest_xy_distances(mirrors: list[dict[str, Any]]) -> np.ndarray:
    n = len(mirrors)
    if n == 1:
        return np.asarray([math.inf], dtype=float)
    xy = np.asarray([[row["x"], row["y"]] for row in mirrors], dtype=float)
    nearest = np.full(n, np.inf, dtype=float)
    block = 256
    all_indices = np.arange(n)
    for start in range(0, n, block):
        stop = min(start + block, n)
        delta = xy[start:stop, None, :] - xy[None, :, :]
        distance = np.hypot(delta[..., 0], delta[..., 1])
        distance[np.arange(stop - start), all_indices[start:stop]] = np.inf
        nearest[start:stop] = distance.min(axis=1)
    return nearest


def group_baseline(
    payload: dict[str, Any], radial_bins: int = 3, angular_bins: int = 4
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Assign deterministic radial-rank and half-open angular groups."""
    _require_accepted(payload, "group_baseline")
    if not _is_integer(radial_bins) or int(radial_bins) <= 0:
        raise DesignError("radial_bins must be a positive integer")
    if not _is_integer(angular_bins) or int(angular_bins) <= 0:
        raise DesignError("angular_bins must be a positive integer")
    radial_bins, angular_bins = int(radial_bins), int(angular_bins)
    result = copy.deepcopy(payload)
    mirrors = result["mirrors"]
    tower_x, tower_y = map(float, result["tower_xy"])
    radial_distance = [
        math.hypot(float(row["x"]) - tower_x, float(row["y"]) - tower_y)
        for row in mirrors
    ]
    order = sorted(
        range(len(mirrors)),
        key=lambda i: (
            radial_distance[i],
            int(mirrors[i]["mirror_id"]),
            str(mirrors[i]["position_key"]),
        ),
    )
    radial_group = [0] * len(mirrors)
    for rank, index in enumerate(order):
        radial_group[index] = min(
            radial_bins - 1, rank * radial_bins // len(mirrors)
        )
    angular_width = 2.0 * math.pi / angular_bins
    groups: dict[int, list[int]] = {}
    for index, row in enumerate(mirrors):
        angle = math.atan2(float(row["y"]) - tower_y, float(row["x"]) - tower_x)
        angle = angle % (2.0 * math.pi)
        angular_group = min(angular_bins - 1, int(angle / angular_width))
        group = radial_group[index] * angular_bins + angular_group
        row["group"] = group
        groups.setdefault(group, []).append(index)

    nearest = _nearest_xy_distances(mirrors)
    upper = np.minimum(MAX_EDGE_M, nearest - 5.0)
    per_mirror = [
        {
            "mirror_id": int(row["mirror_id"]),
            "position_key": str(row["position_key"]),
            "nearest_other_center_distance_m": (
                None if math.isinf(float(nearest[i])) else float(nearest[i])
            ),
            "actual_width_upper_bound_m": float(upper[i]),
        }
        for i, row in enumerate(mirrors)
    ]
    group_rows = []
    for group in sorted(groups):
        members = groups[group]
        group_rows.append(
            {
                "group": group,
                "radial_bin": group // angular_bins,
                "angular_bin": group % angular_bins,
                "actual_width_upper_bound_m": float(
                    min(float(upper[i]) for i in members)
                ),
                "member_mirror_ids": sorted(
                    int(mirrors[i]["mirror_id"]) for i in members
                ),
            }
        )
    nonempty = sorted(groups)
    report = {
        "schema": "q03-group-report-v001",
        "source_payload_sha256": payload_sha256(payload),
        "grouped_payload_sha256": payload_sha256(result),
        "radial_bins": radial_bins,
        "angular_bins": angular_bins,
        "radial_policy": "tower-distance rank; ties by stable mirror_id then position_key",
        "angular_policy": "atan2 around tower normalized to [0,2pi), half-open equal bins",
        "width_upper_bound_formula": "min(8, min_other_center_distance-5)",
        "all_pair_actual_width_upper_bound_m": float(np.min(upper)),
        "per_mirror": per_mirror,
        "groups": group_rows,
        "nonempty_groups": nonempty,
        "nonempty_group_count": len(nonempty),
    }
    result["metadata"]["grouping"] = {
        "schema": report["schema"],
        "source_payload_sha256": report["source_payload_sha256"],
        "radial_bins": radial_bins,
        "angular_bins": angular_bins,
        "nonempty_groups": nonempty,
    }
    report["grouped_payload_sha256"] = payload_sha256(result)
    _require_accepted(result, "group_baseline result")
    return result, report


def apply_groups(
    base: dict[str, Any],
    changes: Mapping[int, Mapping[str, float]],
    name: str,
) -> dict[str, Any]:
    """Expand group changes per mirror without clipping or repairing them."""
    _require_accepted(base, "apply_groups")
    if not isinstance(name, str) or not name:
        raise DesignError("name must be a nonempty string")
    if not isinstance(changes, Mapping):
        raise DesignError("changes must map integer groups to update mappings")
    existing = {int(row["group"]) for row in base["mirrors"]}
    normalized: dict[int, dict[str, float]] = {}
    for raw_group, raw_update in changes.items():
        if not _is_integer(raw_group):
            raise DesignError("each change key must be an integer group")
        group = int(raw_group)
        if group not in existing:
            raise DesignError("change refers to a group absent from the design")
        if not isinstance(raw_update, Mapping) or not raw_update:
            raise DesignError("each group update must be a nonempty mapping")
        unexpected = set(raw_update) - {"width", "height", "z"}
        if unexpected:
            raise DesignError("unexpected group update fields: " + repr(sorted(unexpected)))
        update: dict[str, float] = {}
        for field, value in raw_update.items():
            if not _is_finite_number(value):
                raise DesignError("group update values must be finite real numbers")
            update[field] = float(value)
        normalized[group] = update

    result = copy.deepcopy(base)
    parent_sha = payload_sha256(base)
    for row in result["mirrors"]:
        update = normalized.get(int(row["group"]))
        if update:
            for field, value in update.items():
                row[field] = value
            row["area"] = float(row["width"]) * float(row["height"])
    result["name"] = name
    result["version"] = "q03-group-application-v001"
    result["metadata"]["parent_binding"] = {
        "schema": base["schema"],
        "name": base["name"],
        "version": base["version"],
        "sha256": parent_sha,
    }
    result["metadata"]["group_changes"] = [
        {"group": group, **normalized[group]} for group in sorted(normalized)
    ]
    return result


def _reject_json_constant(text: str) -> None:
    raise DesignError("non-finite JSON constant is prohibited: " + text)


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DesignError("duplicate JSON object key: " + key)
        result[key] = value
    return result


def save_design(payload: dict[str, Any], path: str | Path) -> dict[str, Any]:
    """Write one accepted design once, preserving Python JSON float repr."""
    report = _require_accepted(payload, "save_design")
    target = _workspace_path(path)
    if target.suffix.lower() != ".json":
        raise DesignError("design path must have a .json suffix")
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = _json_bytes(payload) + b"\n"
    try:
        with target.open("xb") as handle:
            handle.write(encoded)
    except FileExistsError as exc:
        raise FileExistsError("refusing to overwrite an existing design path") from exc
    return {
        "path": target.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "payload_sha256": payload_sha256(payload),
        "schema": SCHEMA,
        "n": report["n"],
        "total_area": report["total_area"],
    }


def read_design(path: str | Path) -> dict[str, Any]:
    """Read a strict full-field Q3 design and reject duplicate JSON keys."""
    source = _workspace_path(path)
    if source.suffix.lower() != ".json":
        raise DesignError("design path must have a .json suffix")
    try:
        payload = json.loads(
            source.read_text(encoding="utf-8"),
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DesignError("cannot read strict Q3 design JSON") from exc
    _require_accepted(payload, "read_design")
    return payload


__all__ = [
    "SCHEMA",
    "DesignError",
    "validate_design",
    "from_r027",
    "group_baseline",
    "apply_groups",
    "save_design",
    "read_design",
    "payload_sha256",
]
