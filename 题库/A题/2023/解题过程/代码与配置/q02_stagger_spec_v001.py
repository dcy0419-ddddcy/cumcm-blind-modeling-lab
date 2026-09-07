"""Unexecuted staggered full-ring parameter helper, independent of frozen code.

This module only creates/inspects ring specifications.  It never expands mirror
positions, imports an optimizer/optical core, writes files, or changes a frozen
configuration.  Root execution and a new configuration freeze are separate.

Construction proof (exact real arithmetic): let d=w+5+positive margin.  Within a
group all full rings have the same count m, chosen so the innermost ring chord
2*r0*sin(pi/m) >= d.  Phases alternate 0 and .5.  Adjacent rings r and r+delta
then have exact minimum squared separation

    delta**2 + 4*r*(r+delta)*sin(pi/(2*m))**2.

Since 4*r*sin(pi/(2*m))*cos(pi/(2*m)) >= d, the second term is >= d**2/4.
For delta >= .90*d, the full expression is >= 1.06*d**2.  Nonadjacent rings
within the group have radial separation >= 1.80*d.  Between groups the gap
from the last ring to the next first ring is >= d, sufficient for every
cross-group pair, irrespective of counts or phase.  Single-point rings are
handled directly.  Fixed-field/exclusion clipping removes points and cannot
reduce any retained pair distance; it changes actual N, which is not generated
here.  Floating coordinates and final delivery rounding still require the
existing independent geometry validator with no negative-tolerance acceptance.

The default .90 radial ratio and common count per group are search restrictions,
not new hard problem constraints.  This helper supports full circles only;
independently cut sectors or unequal within-group counts need another proof.
"""
from __future__ import annotations

import math
from typing import Any


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite real number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{label} must be a finite real number")
    return value


def _next_radius(radius: float, step: float) -> float:
    following = math.nextafter(radius + step, math.inf)
    while math.isfinite(following) and following - radius < step:
        following = math.nextafter(following, math.inf)
    if not math.isfinite(following) or following <= radius:
        raise ValueError("Radial stepping overflow or stagnation")
    return following


def _full_ring_count(radius: float, target: float) -> int:
    if target >= 2 * radius:
        return 2 if target == 2 * radius else 1
    count = max(1, math.floor(math.pi / math.asin(target / (2 * radius))))
    while count >= 2 and 2 * radius * math.sin(math.pi / count) < target:
        count -= 1
    return count


def make_stagger_spec(
    tower: tuple[float, float], w: float, h: float, z: float, *,
    group_size: int = 4, radial_ratio: float = 0.90,
    phase: float = 0.0, inner: float = 100.5, outer: float | None = None,
    spacing_margin: float = 0.05, name: str = "stagger_candidate",
    version: str = "v001",
) -> dict[str, Any]:
    """Return kwargs accepted by q02_design_v002.generate_ring_design.

    group_size bounds the number of consecutive same-count rings.  The last
    group may be shorter when the radial outer bound is reached.  Each group's
    first radius determines its exact chord-limited count.  Within-group gaps
    are radial_ratio*d, between-group gaps d, rounded upward in binary64.
    phase is exactly 0 or .5 and resets at the start of each group.

    outer=None uses 350+||tower||.  An explicit outer bound may be smaller, but
    cannot exceed this field-covering bound.  No tower position, mirror count,
    square shape or height is fixed.  Returned nominal slot count is not actual
    retained N; downstream generation must clip and recount it.
    """
    if not isinstance(tower, (tuple, list)) or len(tower) != 2:
        raise ValueError("tower must contain two coordinates")
    tower = tuple(_number(v, "tower") for v in tower)
    w, h, z = (_number(value, label) for value, label in ((w, "w"), (h, "h"), (z, "z")))
    if not (2 <= w <= 8 and 2 <= h <= 8 and 2 <= z <= 6 and z > h / 2):
        raise ValueError("Dimensions/height violate approved geometry")
    if w < h:
        raise ValueError("w<h is outside current approved search scope")
    if math.hypot(*tower) > 350:
        raise ValueError("Tower center is outside the fixed field")
    if type(group_size) is not int or group_size < 2:
        raise ValueError("group_size must be an integer >=2")
    radial_ratio = _number(radial_ratio, "radial_ratio")
    phase = _number(phase, "phase")
    spacing_margin = _number(spacing_margin, "spacing_margin")
    inner = _number(inner, "inner")
    if not 0.90 <= radial_ratio < 1:
        raise ValueError("This bounded construction requires 0.90<=radial_ratio<1")
    if phase not in (0.0, 0.5):
        raise ValueError("phase must be exactly 0 or 0.5")
    target = w + 5 + spacing_margin
    if spacing_margin <= 0 or not math.isfinite(target) or not target > w + 5:
        raise ValueError("spacing_margin must remain strictly positive numerically")
    if inner <= 100:
        raise ValueError("inner must exceed the tower exclusion radius 100")
    cover = 350 + math.hypot(*tower)
    outer = cover if outer is None else _number(outer, "outer")
    if not inner <= outer <= cover:
        raise ValueError("outer must lie between inner and 350+||tower||")
    if not isinstance(name, str) or not name or not isinstance(version, str) or not version:
        raise ValueError("Nonempty name and version required")
    rings: list[dict[str, Any]] = []
    radius, group_id = inner, 0
    while radius <= outer:
        group_id += 1
        count = _full_ring_count(radius, target)
        for local_ring in range(group_size):
            if radius > outer:
                break
            if local_ring:
                previous_radius = rings[-1]["radius"]
                adjacent_minimum = math.sqrt(
                    (radius - previous_radius) ** 2
                    + 4 * previous_radius * radius * math.sin(math.pi / (2 * count)) ** 2
                )
                if not math.isfinite(adjacent_minimum) or adjacent_minimum < target:
                    raise ValueError("Adjacent-ring formula failed the construction target")
            ring_phase = phase if local_ring % 2 == 0 else 0.5 - phase
            rings.append({
                "ring_id": f"stagger_g{group_id:04d}_r{local_ring + 1:04d}",
                "radius": radius,
                "sectors": [{"sector_id": "full", "start": 0.0,
                             "end": math.tau, "count": count, "phase": ring_phase}],
            })
            step = target if local_ring == group_size - 1 else radial_ratio * target
            radius = _next_radius(radius, step)
    return {"name": name, "version": version, "tower_xy": tower, "width": w,
            "height": h, "installation_height": z, "rings": rings}


def certify_stagger_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Parameter-only all-ring-pairs separation certificate against hard w+5.

    This accepts full-ring specs, checks each same-ring chord and every unordered
    ring pair.  Close ring pairs must have identical counts and exact half-step
    phase offset; otherwise a sufficient radial-only bound is used.  It does not
    rely on encoded group IDs or assume every input was produced by this helper.
    It is not an executed all-mirror check, field/ground check or optical result.
    The certificate is an arithmetic diagnostic, not an interval-arithmetic proof
    of final floating coordinates.  No tolerance can turn a negative margin into
    acceptance.  No mirror positions are expanded.
    """
    d = _number(spec["width"], "width") + 5
    if d <= 0:
        raise ValueError("Required separation must be positive")
    rings = spec["rings"]
    if not isinstance(rings, list) or not rings:
        raise ValueError("A nonempty list of rings is required")
    prepared = []
    failures = []
    same_ring = []
    identities = set()
    for ring in rings:
        rid = ring["ring_id"]
        if not isinstance(rid, str) or not rid or rid in identities:
            raise ValueError("Nonempty unique ring identities required")
        identities.add(rid)
        radius = _number(ring["radius"], "radius")
        sectors = ring["sectors"]
        if radius <= 0 or not isinstance(sectors, list) or len(sectors) != 1:
            raise ValueError("Only positive-radius single-full-sector rings are certified")
        sector = sectors[0]
        if sector["start"] != 0.0 or sector["end"] != math.tau:
            raise ValueError("Only common [0,2*pi) full rings are certified")
        count, phase = sector["count"], _number(sector["phase"], "phase")
        if type(count) is not int or count < 1 or phase not in (0.0, 0.5):
            raise ValueError("Positive integer counts and 0/.5 phase required")
        chord = None if count == 1 else 2 * radius * math.sin(math.pi / count)
        if chord is not None and not math.isfinite(chord):
            raise ValueError("Same-ring chord computation overflow")
        same_ring.append({"ring_id": rid, "count": count, "chord": chord,
                          "margin": None if chord is None else chord - d})
        if chord is not None and chord < d:
            failures.append({"kind": "same_ring", "ring_id": rid, "distance": chord,
                             "required": d, "margin": chord - d})
        prepared.append((rid, radius, count, phase))
    pair_checks = []
    for i, (rid, radius, count, phase) in enumerate(prepared):
        for oid, other_radius, other_count, other_phase in prepared[i + 1:]:
            radial = abs(other_radius - radius)
            if radial >= d:
                lower, method = radial, "radial_bound"
            elif count == other_count and abs(phase - other_phase) == 0.5:
                lower = math.sqrt(radial * radial + 4 * radius * other_radius
                                  * math.sin(math.pi / (2 * count)) ** 2)
                method = "exact_half_step_same_count"
            else:
                lower, method = radial, "unsupported_close_pair_radial_bound_only"
            if not math.isfinite(lower):
                raise ValueError("Ring-pair separation computation overflow")
            row = {"ring_ids": [rid, oid], "distance_lower_bound": lower,
                   "required": d, "margin": lower - d, "method": method}
            pair_checks.append(row)
            if lower < d:
                failures.append({"kind": "ring_pair", **row})
    return {"schema": "q02-stagger-parameter-certificate-v001",
            "parameter_separation_accepted": not failures,
            "required_distance": d, "ring_count": len(prepared),
            "nominal_slot_count": sum(row[2] for row in prepared),
            "actual_retained_N": None, "ring_pair_count": len(pair_checks),
            "same_ring_checks": same_ring, "ring_pair_checks": pair_checks,
            "failures": failures, "mirror_positions_generated": False,
            "independent_all_mirror_geometry_validation_performed": False,
            "limitations": ["Full circles and exact 0/.5 phases only",
                            "Numerical parameter check; no interval arithmetic",
                            "Clip/recount and independent final-coordinate checks required",
                            "No optical, power, precision or optimality conclusion"]}
