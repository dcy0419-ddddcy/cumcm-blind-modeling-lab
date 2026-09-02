#!/usr/bin/env python3
"""Blind, reproducible solver for the three questions.

Only the four attachments in this workspace are read.  The script writes
machine-readable diagnostics and the data used to create result.xlsx.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


SEED = 20260902
NOMINAL_RADIUS = 300.0
FOCAL_RATIO = 0.466
APERTURE_RADIUS = 150.0
EDGE_LIMIT = 0.0007
# A small deterministic margin prevents spreadsheet rounding from crossing 0.07%.
EDGE_WORK_LIMIT = 0.00069
ACTUATOR_LIMIT = 0.6
RECEIVER_RADIUS = 0.5
ALPHA = math.radians(36.795)
BETA = math.radians(78.169)


def unit_from_angles(alpha: float, beta: float, convention: str = "xy") -> np.ndarray:
    """Azimuth from +x toward +y; elevation above xy unless noted."""
    if convention == "xy":
        u = np.array([math.cos(beta) * math.cos(alpha),
                      math.cos(beta) * math.sin(alpha),
                      math.sin(beta)])
    elif convention == "mirror_y":
        u = np.array([math.cos(beta) * math.cos(alpha),
                      -math.cos(beta) * math.sin(alpha),
                      math.sin(beta)])
    elif convention == "swap_xy":
        u = np.array([math.cos(beta) * math.sin(alpha),
                      math.cos(beta) * math.cos(alpha),
                      math.sin(beta)])
    else:
        raise ValueError(convention)
    return u / np.linalg.norm(u)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def paraboloid_target_displacement(q0: np.ndarray, rhat: np.ndarray,
                                    u: np.ndarray, radius: float,
                                    h: float) -> np.ndarray:
    """Stable positive ray/paraboloid intersection minus baseline radius."""
    f = FOCAL_RATIO * radius - h
    a = rhat @ u
    b = -4.0 * f * a
    disc = b * b + 16.0 * f * (radius - h) * (1.0 - a * a)
    if np.any(disc < -1e-10):
        raise RuntimeError("negative paraboloid intersection discriminant")
    s = 8.0 * f * (radius - h) / (b + np.sqrt(np.maximum(disc, 0.0)))
    return s - np.linalg.norm(q0, axis=1)


def aperture_mask(q0: np.ndarray, u: np.ndarray) -> np.ndarray:
    axial = q0 @ u
    transverse = q0 - axial[:, None] * u
    return np.linalg.norm(transverse, axis=1) <= APERTURE_RADIUS


def edge_relative_strain(d: np.ndarray, q0: np.ndarray, rhat: np.ndarray,
                         edges: np.ndarray, base_edge_len: np.ndarray) -> np.ndarray:
    q = q0 + d[:, None] * rhat
    lengths = np.linalg.norm(q[edges[:, 0]] - q[edges[:, 1]], axis=1)
    return (lengths - base_edge_len) / base_edge_len


def globally_scale_to_feasible(d_target: np.ndarray, q0: np.ndarray,
                               rhat: np.ndarray, edges: np.ndarray,
                               base_edge_len: np.ndarray,
                               eps: float) -> tuple[np.ndarray, float]:
    if np.max(np.abs(edge_relative_strain(d_target, q0, rhat, edges,
                                           base_edge_len))) <= eps:
        return d_target.copy(), 1.0
    lo, hi = 0.0, 1.0
    for _ in range(64):
        mid = (lo + hi) / 2.0
        strain = edge_relative_strain(mid * d_target, q0, rhat, edges,
                                      base_edge_len)
        if np.max(np.abs(strain)) <= eps:
            lo = mid
        else:
            hi = mid
    return lo * d_target, lo


def feasible_interval_for_node(i: int, d: np.ndarray, q0: np.ndarray,
                               rhat: np.ndarray, neighbors: list[list[tuple[int, float]]],
                               eps: float) -> tuple[float, float]:
    """Exact interval for radial displacement d_i with neighbors held fixed."""
    low, high = -math.inf, math.inf
    ai = rhat[i]
    qi0 = q0[i]
    for j, l0 in neighbors[i]:
        qj = q0[j] + d[j] * rhat[j]
        w = qi0 - qj
        aw = float(ai @ w)
        w2 = float(w @ w)
        lmax = l0 * (1.0 + eps)
        disc_max = aw * aw - (w2 - lmax * lmax)
        if disc_max < -1e-11:
            return 1.0, 0.0
        root = math.sqrt(max(disc_max, 0.0))
        lo_max, hi_max = -aw - root, -aw + root
        low, high = max(low, lo_max), min(high, hi_max)

        lmin = l0 * (1.0 - eps)
        disc_min = aw * aw - (w2 - lmin * lmin)
        if disc_min > 0.0:
            rmin = math.sqrt(disc_min)
            forbidden_lo, forbidden_hi = -aw - rmin, -aw + rmin
            # The feasible component containing the current point is used;
            # all iterates begin globally feasible and therefore remain so.
            current = d[i]
            if current <= forbidden_lo + 1e-12:
                high = min(high, forbidden_lo)
            elif current >= forbidden_hi - 1e-12:
                low = max(low, forbidden_hi)
            else:
                # Binary scaling can land a few ulps inside the excluded
                # interval.  Project to the nearer connected component.
                if current - forbidden_lo <= forbidden_hi - current:
                    high = min(high, forbidden_lo)
                else:
                    low = max(low, forbidden_hi)
    return low, high


def improve_coordinatewise(d_start: np.ndarray, d_target: np.ndarray,
                           active: np.ndarray, q0: np.ndarray,
                           rhat: np.ndarray,
                           neighbors: list[list[tuple[int, float]]],
                           mode: str, eps: float) -> np.ndarray:
    d = d_start.copy()
    ids = np.flatnonzero(active)
    if mode == "forward":
        base_order = ids
    elif mode == "reverse":
        base_order = ids[::-1]
    elif mode == "descending_residual":
        base_order = ids[np.argsort(-np.abs(d_target[ids] - d[ids]))]
    elif mode == "ascending_residual":
        base_order = ids[np.argsort(np.abs(d_target[ids] - d[ids]))]
    elif mode == "fixed_seed_random":
        base_order = ids.copy()
    else:
        raise ValueError(mode)
    rng = np.random.default_rng(SEED)
    for _ in range(400):
        order = base_order.copy()
        if mode == "fixed_seed_random":
            rng.shuffle(order)
        largest = 0.0
        for i in order:
            low, high = feasible_interval_for_node(int(i), d, q0, rhat,
                                                   neighbors, eps)
            if low > high + 1e-11:
                raise RuntimeError(f"empty feasible interval at node {i}")
            proposed = min(max(float(d_target[i]), low), high)
            change = abs(proposed - d[i])
            if change > largest:
                largest = change
            d[i] = proposed
        if largest < 1e-11:
            break
    d[~active] = 0.0
    return d


def solve_surface(q0: np.ndarray, rhat: np.ndarray, u: np.ndarray,
                  radius: float, h: float, edges: np.ndarray,
                  base_edge_len: np.ndarray,
                  neighbors: list[list[tuple[int, float]]],
                  modes: tuple[str, ...] = ("forward", "reverse",
                                             "descending_residual",
                                             "ascending_residual",
                                             "fixed_seed_random")) -> dict:
    active = aperture_mask(q0, u)
    d_target = paraboloid_target_displacement(q0, rhat, u, radius, h)
    d_target[~active] = 0.0
    d0, scale = globally_scale_to_feasible(d_target, q0, rhat, edges,
                                            base_edge_len, EDGE_WORK_LIMIT)
    candidates: dict[str, np.ndarray] = {}
    scores: dict[str, float] = {}
    for mode in modes:
        candidate = improve_coordinatewise(d0, d_target, active, q0, rhat,
                                           neighbors, mode, EDGE_WORK_LIMIT)
        strain = edge_relative_strain(candidate, q0, rhat, edges, base_edge_len)
        if np.max(np.abs(strain)) > EDGE_LIMIT + 2e-11:
            raise RuntimeError(f"edge constraint failure in {mode}")
        candidates[mode] = candidate
        scores[mode] = float(np.sqrt(np.mean((candidate[active] -
                                              d_target[active]) ** 2)))
    best_mode = min(scores, key=lambda key: (scores[key], key))
    return {"d": candidates[best_mode], "d_target": d_target,
            "active": active, "scale": float(scale),
            "best_mode": best_mode, "order_rms": scores}


def select_h(q0: np.ndarray, rhat: np.ndarray, u: np.ndarray, radius: float,
             fitted_radius: float, edges: np.ndarray, base_edge_len: np.ndarray,
             neighbors: list[list[tuple[int, float]]]) -> tuple[float, list[dict]]:
    """Grid-search h by constrained Q1 radial RMS; no known answer is used."""
    offset = radius - fitted_radius
    coarse = np.arange(offset - 0.45, offset - 0.25 + 1e-12, 0.005)
    history: list[dict] = []
    modes = ("forward", "reverse")
    for h in coarse:
        sol = solve_surface(q0, rhat, u, radius, float(h), edges,
                            base_edge_len, neighbors, modes=modes)
        history.append({"h": float(h), "rms": min(sol["order_rms"].values())})
    h0 = min(history, key=lambda item: (item["rms"], item["h"]))["h"]
    refine = np.arange(h0 - 0.005, h0 + 0.005 + 1e-12, 0.00125)
    for h in refine:
        if any(abs(row["h"] - float(h)) < 1e-10 for row in history):
            continue
        sol = solve_surface(q0, rhat, u, radius, float(h), edges,
                            base_edge_len, neighbors, modes=modes)
        history.append({"h": float(h), "rms": min(sol["order_rms"].values())})
    best = min(history, key=lambda item: (item["rms"], item["h"]))
    return float(best["h"]), sorted(history, key=lambda item: item["h"])


def normal_surface_residual(q: np.ndarray, u: np.ndarray, radius: float,
                            h: float) -> np.ndarray:
    axial = q @ u
    rho2 = np.sum(q * q, axis=1) - axial * axial
    f = FOCAL_RATIO * radius - h
    implicit = rho2 - 4.0 * f * (axial + radius - h)
    grad_norm = np.sqrt(4.0 * rho2 + 16.0 * f * f)
    return implicit / grad_norm


def extensions_for_axis(q: np.ndarray, q0: np.ndarray, top0: np.ndarray,
                        inward: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Solve the fixed-drop-cable quadratic for a specified unit axis."""
    cable = np.linalg.norm(q0 - top0, axis=1)
    w = q - top0
    a = np.sum(inward * w, axis=1)
    disc = a * a - (np.sum(w * w, axis=1) - cable * cable)
    if np.min(disc) < -1e-9:
        raise RuntimeError("negative actuator quadratic discriminant")
    root = np.sqrt(np.maximum(disc, 0.0))
    d1, d2 = a - root, a + root
    delta = np.where(np.abs(d1) <= np.abs(d2), d1, d2)
    top = top0 + delta[:, None] * inward
    cable_residual = np.linalg.norm(q - top, axis=1) - cable
    return delta, disc, cable_residual


def actuator_extensions(q: np.ndarray, q0: np.ndarray, top0: np.ndarray,
                        bottom: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Use the measured Attachment 02 bottom-to-top actuator axis.

    ``top0 - bottom`` points from the outer fixed end toward the sphere center,
    so positive extension retains the statement's inward-positive convention.
    """
    inward = top0 - bottom
    axis_length = np.linalg.norm(inward, axis=1)
    if np.any(axis_length < 1e-12):
        raise RuntimeError("zero-length actuator axis in Attachment 02")
    inward /= axis_length[:, None]
    return extensions_for_axis(q, q0, top0, inward)


def segment_circle_area(a: np.ndarray, b: np.ndarray, radius: float) -> float:
    """Signed area of circle intersection with oriented triangle O-a-b."""
    d = b - a
    aa = float(d @ d)
    cuts = [0.0, 1.0]
    if aa > 1e-30:
        bb = 2.0 * float(a @ d)
        cc = float(a @ a) - radius * radius
        disc = bb * bb - 4.0 * aa * cc
        if disc > 0.0:
            root = math.sqrt(disc)
            for t in ((-bb - root) / (2.0 * aa),
                      (-bb + root) / (2.0 * aa)):
                if 1e-14 < t < 1.0 - 1e-14:
                    cuts.append(t)
    cuts.sort()
    area = 0.0
    for t0, t1 in zip(cuts[:-1], cuts[1:]):
        p = a + t0 * d
        q = a + t1 * d
        mid = a + (t0 + t1) * 0.5 * d
        cross = float(p[0] * q[1] - p[1] * q[0])
        if float(mid @ mid) <= radius * radius + 1e-12:
            area += 0.5 * cross
        else:
            area += 0.5 * radius * radius * math.atan2(
                cross, float(p @ q))
    return area


def circle_triangle_intersection_area(triangle_2d: np.ndarray,
                                      radius: float) -> float:
    area = 0.0
    for i in range(3):
        area += segment_circle_area(triangle_2d[i],
                                    triangle_2d[(i + 1) % 3], radius)
    return abs(area)


def circle_overlap_self_check() -> dict:
    inside = np.array([[0.0, 0.0], [0.1, 0.0], [0.0, 0.1]])
    enclosing = np.array([[-2.0, -2.0], [2.0, -2.0], [0.0, 2.0]])
    disjoint = np.array([[2.0, 2.0], [3.0, 2.0], [2.0, 3.0]])
    inside_error = abs(circle_triangle_intersection_area(inside, 1.0) - 0.005)
    enclosing_error = abs(circle_triangle_intersection_area(enclosing, 0.5) -
                          math.pi * 0.25)
    disjoint_area = circle_triangle_intersection_area(disjoint, 1.0)
    if max(inside_error, enclosing_error, disjoint_area) > 1e-11:
        raise RuntimeError("circle/triangle overlap self-check failed")
    return {"inside_triangle_abs_error_m2": inside_error,
            "enclosing_triangle_abs_error_m2": enclosing_error,
            "disjoint_triangle_area_m2": disjoint_area}


def sampled_footprint_check(trace: dict, samples_per_panel: int = 512) -> dict:
    """Independent fixed-seed Monte Carlo check of exact footprint overlap."""
    rng = np.random.default_rng(SEED)
    weight = trace["_projected_weight"]
    included = trace["_included"]
    mapped = trace["_mapped_triangle_2d"]
    weighted_hits = 0.0
    denominator = float(weight[included].sum())
    for i in np.flatnonzero(included):
        if not np.all(np.isfinite(mapped[i])):
            continue
        r1 = rng.random(samples_per_panel)
        r2 = rng.random(samples_per_panel)
        s = np.sqrt(r1)
        bary = np.column_stack((1.0 - s, s * (1.0 - r2), s * r2))
        points = bary @ mapped[i]
        fraction = float(np.mean(np.sum(points * points, axis=1) <=
                                 RECEIVER_RADIUS ** 2))
        weighted_hits += weight[i] * fraction
    sampled_ratio = weighted_hits / denominator
    return {"samples_per_panel": samples_per_panel,
            "seed": SEED,
            "sampled_ratio": float(sampled_ratio),
            "exact_ratio": float(trace["ratio"]),
            "absolute_difference": float(abs(sampled_ratio - trace["ratio"]))}


def summarize_surface(sol: dict, q0: np.ndarray, rhat: np.ndarray,
                      u: np.ndarray, radius: float, h: float,
                      edges: np.ndarray, base_edge_len: np.ndarray,
                      top0: np.ndarray, bottom: np.ndarray) -> tuple[dict, np.ndarray, np.ndarray]:
    d, target, active = sol["d"], sol["d_target"], sol["active"]
    q = q0 + d[:, None] * rhat
    strain = edge_relative_strain(d, q0, rhat, edges, base_edge_len)
    delta, disc, cable_residual = actuator_extensions(q, q0, top0, bottom)
    radial_error = d[active] - target[active]
    normal_error = normal_surface_residual(q[active], u, radius, h)
    metrics = {
        "active_node_count": int(active.sum()),
        "global_scale": sol["scale"],
        "best_coordinate_order": sol["best_mode"],
        "coordinate_order_rms_m": sol["order_rms"],
        "target_radial_displacement_range_m": [float(target[active].min()),
                                                float(target[active].max())],
        "actual_radial_displacement_range_m": [float(d[active].min()),
                                                float(d[active].max())],
        "radial_fit_rms_m": float(np.sqrt(np.mean(radial_error ** 2))),
        "radial_fit_max_abs_m": float(np.max(np.abs(radial_error))),
        "normal_fit_rms_m": float(np.sqrt(np.mean(normal_error ** 2))),
        "normal_fit_max_abs_m": float(np.max(np.abs(normal_error))),
        "max_edge_relative_change": float(np.max(np.abs(strain))),
        "edge_violation_count": int(np.sum(np.abs(strain) > EDGE_LIMIT + 1e-11)),
        "actuator_extension_range_m": [float(delta[active].min()),
                                        float(delta[active].max())],
        "max_actuator_abs_m": float(np.max(np.abs(delta[active]))),
        "actuator_violation_count": int(np.sum(np.abs(delta[active]) >
                                                  ACTUATOR_LIMIT + 1e-11)),
        "min_actuator_discriminant_m2": float(disc[active].min()),
        "max_fixed_cable_residual_m": float(np.max(np.abs(cable_residual[active]))),
    }
    return metrics, q, delta


def direct_target_summary(q0: np.ndarray, rhat: np.ndarray, u: np.ndarray,
                          radius: float, h: float, edges: np.ndarray,
                          base_edge_len: np.ndarray, top0: np.ndarray,
                          bottom: np.ndarray) -> dict:
    active = aperture_mask(q0, u)
    d = paraboloid_target_displacement(q0, rhat, u, radius, h)
    d[~active] = 0.0
    q = q0 + d[:, None] * rhat
    strain = edge_relative_strain(d, q0, rhat, edges, base_edge_len)
    delta, _, _ = actuator_extensions(q, q0, top0, bottom)
    return {
        "h_m": h,
        "active_node_count": int(active.sum()),
        "max_edge_relative_change": float(np.max(np.abs(strain))),
        "edge_violation_count": int(np.sum(np.abs(strain) > EDGE_LIMIT)),
        "max_actuator_abs_m": float(np.max(np.abs(delta[active]))),
        "actuator_violation_count": int(np.sum(np.abs(delta[active]) >
                                                  ACTUATOR_LIMIT)),
    }


def panel_trace(q: np.ndarray, triangles: np.ndarray, u: np.ndarray,
                focus: np.ndarray, radius: float, h: float,
                boundary: str = "centroid", weight_mode: str = "projected",
                normal_mode: str = "mesh",
                boundary_q: np.ndarray | None = None) -> dict:
    vertices = q[triangles]
    centroid = vertices.mean(axis=1)
    cross = np.cross(vertices[:, 1] - vertices[:, 0],
                     vertices[:, 2] - vertices[:, 0])
    twice_area = np.linalg.norm(cross, axis=1)
    if np.any(twice_area < 1e-12):
        raise RuntimeError("degenerate triangular panel")
    mesh_normal = cross / twice_area[:, None]

    if normal_mode == "mesh":
        normal = mesh_normal
    elif normal_mode == "sphere":
        normal = centroid / np.linalg.norm(centroid, axis=1)[:, None]
    elif normal_mode == "ideal_paraboloid":
        axial = centroid @ u
        transverse = centroid - axial[:, None] * u
        f = FOCAL_RATIO * radius - h
        grad = 2.0 * transverse - 4.0 * f * u
        normal = grad / np.linalg.norm(grad, axis=1)[:, None]
    else:
        raise ValueError(normal_mode)

    k_in = -u
    reflected = k_in - 2.0 * np.sum(k_in * normal, axis=1)[:, None] * normal
    denom = reflected @ u
    t = np.divide((focus - centroid) @ u, denom,
                  out=np.full(len(denom), np.nan),
                  where=np.abs(denom) > 1e-12)
    point = centroid + t[:, None] * reflected
    off = point - focus
    transverse_distance = np.linalg.norm(off - (off @ u)[:, None] * u, axis=1)
    centroid_hit = ((t > 0.0) & np.isfinite(t) &
                    (transverse_distance <= RECEIVER_RADIUS))

    # For a flat triangular panel, parallel incident rays remain parallel after
    # reflection.  The three vertices map affinely to a triangle on the feed
    # plane.  The exact circle/triangle overlap fraction is therefore also the
    # fraction of this panel's incident signal that reaches the receiver disk.
    anchor = np.array([1.0, 0.0, 0.0])
    if abs(float(anchor @ u)) > 0.9:
        anchor = np.array([0.0, 1.0, 0.0])
    e1 = np.cross(u, anchor)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(u, e1)
    footprint_fraction = np.zeros(len(triangles))
    mapped_triangles_2d = np.full((len(triangles), 3, 2), np.nan)
    for panel in range(len(triangles)):
        if not np.isfinite(denom[panel]) or abs(denom[panel]) <= 1e-12:
            continue
        tv = ((focus - vertices[panel]) @ u) / denom[panel]
        if np.any(tv <= 0.0) or not np.all(np.isfinite(tv)):
            continue
        mapped = vertices[panel] + tv[:, None] * reflected[panel]
        shifted = mapped - focus
        tri2 = np.column_stack((shifted @ e1, shifted @ e2))
        mapped_triangles_2d[panel] = tri2
        v10, v20 = tri2[1] - tri2[0], tri2[2] - tri2[0]
        mapped_area = abs(float(v10[0] * v20[1] - v10[1] * v20[0])) / 2.0
        if mapped_area <= 1e-16:
            continue
        overlap = circle_triangle_intersection_area(tri2, RECEIVER_RADIUS)
        footprint_fraction[panel] = min(1.0, max(0.0, overlap / mapped_area))

    boundary_vertices = (q if boundary_q is None else boundary_q)[triangles]
    boundary_centroid = boundary_vertices.mean(axis=1)
    cax = boundary_centroid @ u
    centroid_rho = np.linalg.norm(boundary_centroid - cax[:, None] * u, axis=1)
    vax = np.einsum("mij,j->mi", boundary_vertices, u)
    vertex_rho = np.linalg.norm(boundary_vertices -
                                vax[:, :, None] * u, axis=2)
    if boundary == "centroid":
        included = centroid_rho <= APERTURE_RADIUS
    elif boundary == "all_vertices":
        included = np.max(vertex_rho, axis=1) <= APERTURE_RADIUS
    elif boundary == "any_vertex":
        included = np.min(vertex_rho, axis=1) <= APERTURE_RADIUS
    else:
        raise ValueError(boundary)

    actual_area = twice_area / 2.0
    projected = np.abs(cross @ u) / 2.0
    if weight_mode == "projected":
        weight = projected
    elif weight_mode == "actual_area":
        weight = actual_area
    elif weight_mode == "equal_panel":
        weight = np.ones(len(triangles))
    else:
        raise ValueError(weight_mode)
    denominator = float(weight[included].sum())
    numerator = float(np.sum(weight[included] * footprint_fraction[included]))
    centroid_numerator = float(weight[included & centroid_hit].sum())
    valid_distance = transverse_distance[included & (t > 0.0) & np.isfinite(t)]
    return {
        "ratio": numerator / denominator,
        "centroid_binary_ratio": centroid_numerator / denominator,
        "included_panel_count": int(included.sum()),
        "centroid_hit_panel_count": int(np.sum(included & centroid_hit)),
        "nonzero_footprint_panel_count": int(np.sum(
            included & (footprint_fraction > 0.0))),
        "partial_footprint_panel_count": int(np.sum(
            included & (footprint_fraction > 0.0) &
            (footprint_fraction < 1.0 - 1e-12))),
        "weighted_denominator": denominator,
        "weighted_numerator": numerator,
        "centroid_weighted_numerator": centroid_numerator,
        "projected_area_coverage_vs_circle": float(projected[included].sum() /
                                                    (math.pi * APERTURE_RADIUS ** 2)),
        "distance_quantiles_m": [float(x) for x in np.quantile(
            valid_distance, [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0])],
        "_included": included,
        "_hit": centroid_hit,
        "_footprint_fraction": footprint_fraction,
        "_mapped_triangle_2d": mapped_triangles_2d,
        "_distance": transverse_distance,
        "_projected_weight": projected,
    }


def public_trace(trace: dict) -> dict:
    return {key: value for key, value in trace.items() if not key.startswith("_")}


def paired_reception_summary(adjusted: dict, baseline: dict) -> dict:
    adjusted_ratio = float(adjusted["ratio"])
    baseline_ratio = float(baseline["ratio"])
    return {
        "adjusted_ratio": adjusted_ratio,
        "baseline_ratio": baseline_ratio,
        "absolute_improvement": adjusted_ratio - baseline_ratio,
        "relative_improvement": adjusted_ratio / baseline_ratio - 1.0,
        "improvement_factor": adjusted_ratio / baseline_ratio,
        "adjusted_panel_count": int(adjusted["included_panel_count"]),
        "baseline_panel_count": int(baseline["included_panel_count"]),
    }


def ideal_reflection_self_check(radius: float, h: float) -> dict:
    """Four analytic paraboloid points must reflect exactly to the focus."""
    u = np.array([0.0, 0.0, 1.0])
    f = FOCAL_RATIO * radius - h
    focus = -(radius - FOCAL_RATIO * radius) * u
    rho = np.array([0.0, 50.0, 100.0, 149.0])
    axial = rho * rho / (4.0 * f) - radius + h
    q = np.column_stack((rho, np.zeros_like(rho), axial))
    transverse = q - (q @ u)[:, None] * u
    grad = 2.0 * transverse - 4.0 * f * u
    normal = grad / np.linalg.norm(grad, axis=1)[:, None]
    incoming = -u
    reflected = incoming - 2.0 * np.sum(incoming * normal, axis=1)[:, None] * normal
    t = ((focus - q) @ u) / (reflected @ u)
    hit = q + t[:, None] * reflected
    miss = np.linalg.norm(hit - focus, axis=1)
    maximum = float(miss.max())
    if maximum > 1e-10:
        raise RuntimeError("ideal paraboloid reflection self-check failed")
    return {"test_point_count": len(q), "max_focus_miss_m": maximum}


def solve_case(q0: np.ndarray, rhat: np.ndarray, u: np.ndarray, radius: float,
               h: float, edges: np.ndarray, base_edge_len: np.ndarray,
               neighbors: list[list[tuple[int, float]]], top0: np.ndarray,
               bottom: np.ndarray, triangles: np.ndarray) -> tuple[dict, dict, np.ndarray, np.ndarray, dict]:
    sol = solve_surface(q0, rhat, u, radius, h, edges, base_edge_len, neighbors)
    surface, q, delta = summarize_surface(sol, q0, rhat, u, radius, h,
                                          edges, base_edge_len, top0, bottom)
    focus = -(radius - FOCAL_RATIO * radius) * u
    trace = panel_trace(q, triangles, u, focus, radius, h, boundary_q=q0)
    return sol, surface, q, delta, trace


def json_default(value):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(type(value).__name__)


def main() -> None:
    np.random.seed(SEED)
    root = Path(__file__).resolve().parents[1]
    attach = root / "附件"
    files = {
        "nodes": attach / "附件01.csv",
        "actuators": attach / "附件02.csv",
        "triangles": attach / "附件03.csv",
        "template": attach / "附件04.xlsx",
    }
    if not all(path.is_file() for path in files.values()):
        raise FileNotFoundError("the four expected attachments were not found")

    nodes = pd.read_csv(files["nodes"], encoding="gb18030")
    acts = pd.read_csv(files["actuators"], encoding="gb18030")
    tris = pd.read_csv(files["triangles"], encoding="gb18030")
    node_ids = nodes.iloc[:, 0].astype(str).to_numpy()
    q0 = nodes.iloc[:, 1:4].to_numpy(float)
    act_ids = acts.iloc[:, 0].astype(str).to_numpy()
    bottom = acts.iloc[:, 1:4].to_numpy(float)
    top0 = acts.iloc[:, 4:7].to_numpy(float)
    if len(nodes) != 2226 or len(acts) != 2226 or len(tris) != 4300:
        raise RuntimeError("unexpected attachment dimensions")
    if not np.array_equal(node_ids, act_ids):
        raise RuntimeError("node and actuator identifier order differs")
    id_to_idx = {identifier: i for i, identifier in enumerate(node_ids)}
    tri_ids = tris.iloc[:, :3].astype(str).to_numpy()
    try:
        triangles = np.array([[id_to_idx[x] for x in row] for row in tri_ids], dtype=int)
    except KeyError as exc:
        raise RuntimeError(f"unknown triangle node identifier {exc}") from exc
    edge_set = set()
    for a, b, c in triangles:
        edge_set.add(tuple(sorted((int(a), int(b)))))
        edge_set.add(tuple(sorted((int(b), int(c)))))
        edge_set.add(tuple(sorted((int(c), int(a)))))
    edges = np.array(sorted(edge_set), dtype=int)
    if len(edges) != 6525:
        raise RuntimeError(f"expected 6525 unique main-cable edges, got {len(edges)}")
    base_edge_len = np.linalg.norm(q0[edges[:, 0]] - q0[edges[:, 1]], axis=1)
    neighbors: list[list[tuple[int, float]]] = [[] for _ in range(len(q0))]
    for (i, j), length in zip(edges, base_edge_len):
        neighbors[int(i)].append((int(j), float(length)))
        neighbors[int(j)].append((int(i), float(length)))
    radii = np.linalg.norm(q0, axis=1)
    fitted_radius = float(radii.mean())
    rhat = q0 / radii[:, None]

    u1 = np.array([0.0, 0.0, 1.0])
    u2 = unit_from_angles(ALPHA, BETA)
    h, h_history = select_h(q0, rhat, u1, fitted_radius, fitted_radius,
                            edges, base_edge_len, neighbors)
    sol1, metrics1, q1, delta1, trace1 = solve_case(
        q0, rhat, u1, fitted_radius, h, edges, base_edge_len, neighbors,
        top0, bottom, triangles)
    sol2, metrics2, q2, delta2, adjusted_trace = solve_case(
        q0, rhat, u2, fitted_radius, h, edges, base_edge_len, neighbors,
        top0, bottom, triangles)

    # Sensitivity only: allow Q2 to choose h independently.  The deliverable
    # keeps the Q1-selected h because it represents one instrument design that
    # is rotated with the observing direction rather than redesigned per view.
    h2_independent, h2_history = select_h(
        q0, rhat, u2, fitted_radius, fitted_radius,
        edges, base_edge_len, neighbors)
    _, metrics2_independent, _, _, trace2_independent = solve_case(
        q0, rhat, u2, fitted_radius, h2_independent,
        edges, base_edge_len, neighbors, top0, bottom, triangles)

    actual_actuator_axis = top0 - bottom
    actual_actuator_axis /= np.linalg.norm(actual_actuator_axis, axis=1)[:, None]
    radial_actuator_axis = -top0 / np.linalg.norm(top0, axis=1)[:, None]
    axis_cosine = np.clip(np.sum(actual_actuator_axis * radial_actuator_axis,
                                 axis=1), -1.0, 1.0)
    axis_angle_deg = np.degrees(np.arccos(axis_cosine))
    radial_delta2, _, _ = extensions_for_axis(
        q2, q0, top0, radial_actuator_axis)
    axis_diagnostics = {
        "primary_axis": "normalized Attachment 02 vector from bottom to top (toward sphere center)",
        "radial_approximation": "negative radial unit vector at baseline top",
        "max_axis_angle_difference_deg_all_2226": float(axis_angle_deg.max()),
        "rms_axis_angle_difference_deg_all_2226": float(np.sqrt(
            np.mean(axis_angle_deg ** 2))),
        "min_inward_axis_dot_product_all_2226": float(axis_cosine.min()),
        "max_abs_extension_difference_m_active": float(np.max(np.abs(
            delta2[sol2["active"]] - radial_delta2[sol2["active"]]))),
        "rms_extension_difference_m_active": float(np.sqrt(np.mean((
            delta2[sol2["active"]] - radial_delta2[sol2["active"]]) ** 2))),
    }

    focus2 = -(fitted_radius - FOCAL_RATIO * fitted_radius) * u2
    vertex2 = (-fitted_radius + h) * u2
    baseline_trace = panel_trace(q0, triangles, u2, focus2, fitted_radius, h)
    adjusted_all_trace = panel_trace(
        q2, triangles, u2, focus2, fitted_radius, h,
        boundary="all_vertices", boundary_q=q0)
    baseline_all_trace = panel_trace(
        q0, triangles, u2, focus2, fitted_radius, h,
        boundary="all_vertices", boundary_q=q0)
    adjusted_any_trace = panel_trace(
        q2, triangles, u2, focus2, fitted_radius, h,
        boundary="any_vertex", boundary_q=q0)
    baseline_any_trace = panel_trace(
        q0, triangles, u2, focus2, fitted_radius, h,
        boundary="any_vertex", boundary_q=q0)
    q3_sensitivity = {
        "adjusted_projected_centroid_mesh": public_trace(adjusted_trace),
        "baseline_projected_centroid_mesh": public_trace(baseline_trace),
        "adjusted_actual_area_centroid_mesh": public_trace(panel_trace(
            q2, triangles, u2, focus2, fitted_radius, h,
            weight_mode="actual_area", boundary_q=q0)),
        "baseline_actual_area_centroid_mesh": public_trace(panel_trace(
            q0, triangles, u2, focus2, fitted_radius, h,
            weight_mode="actual_area")),
        "adjusted_equal_panel_centroid_mesh": public_trace(panel_trace(
            q2, triangles, u2, focus2, fitted_radius, h,
            weight_mode="equal_panel", boundary_q=q0)),
        "baseline_equal_panel_centroid_mesh": public_trace(panel_trace(
            q0, triangles, u2, focus2, fitted_radius, h,
            weight_mode="equal_panel")),
        "adjusted_projected_all_vertices_mesh": public_trace(adjusted_all_trace),
        "baseline_projected_all_vertices_mesh": public_trace(baseline_all_trace),
        "adjusted_projected_any_vertex_mesh": public_trace(adjusted_any_trace),
        "baseline_projected_any_vertex_mesh": public_trace(baseline_any_trace),
        "baseline_projected_centroid_sphere_normal": public_trace(panel_trace(
            q0, triangles, u2, focus2, fitted_radius, h,
            normal_mode="sphere")),
        "adjusted_projected_centroid_ideal_normal": public_trace(panel_trace(
            q2, triangles, u2, focus2, fitted_radius, h,
            normal_mode="ideal_paraboloid", boundary_q=q0)),
    }
    ratio_adj = adjusted_trace["ratio"]
    ratio_base = baseline_trace["ratio"]
    q3_primary = {
        "adjusted_reception_ratio": float(ratio_adj),
        "baseline_reception_ratio": float(ratio_base),
        "absolute_improvement": float(ratio_adj - ratio_base),
        "relative_improvement": float(ratio_adj / ratio_base - 1.0),
        "improvement_factor": float(ratio_adj / ratio_base),
        "definition": "projected-area weighted exact feed-plane footprint overlap for flat triangular panels; fixed baseline-geometry centroid aperture rule",
        "boundary_rule_pairs": {
            "all_vertices": paired_reception_summary(
                adjusted_all_trace, baseline_all_trace),
            "centroid": paired_reception_summary(
                adjusted_trace, baseline_trace),
            "any_vertex": paired_reception_summary(
                adjusted_any_trace, baseline_any_trace),
        },
        "centroid_binary_approximation": {
            "adjusted_ratio": float(adjusted_trace["centroid_binary_ratio"]),
            "baseline_ratio": float(baseline_trace["centroid_binary_ratio"]),
            "improvement_factor": float(
                adjusted_trace["centroid_binary_ratio"] /
                baseline_trace["centroid_binary_ratio"]),
            "reason_not_primary": "whole-panel binary credit ignores the within-panel affine footprint and overstates the 0.5 m disk overlap",
        },
    }
    q3_validation = {
        "circle_triangle_overlap": circle_overlap_self_check(),
        "ideal_paraboloid_reflection": ideal_reflection_self_check(fitted_radius, h),
        "adjusted_exact_vs_fixed_seed_sampling": sampled_footprint_check(adjusted_trace),
        "baseline_exact_vs_fixed_seed_sampling": sampled_footprint_check(baseline_trace),
    }

    # Radius sensitivity: re-optimize h under the nominal 300 m convention.
    h_nom, h_nom_history = select_h(q0, rhat, u1, NOMINAL_RADIUS,
                                    fitted_radius, edges, base_edge_len, neighbors)
    _, nominal_surface, q_nom, delta_nom, nominal_trace = solve_case(
        q0, rhat, u2, NOMINAL_RADIUS, h_nom, edges, base_edge_len,
        neighbors, top0, bottom, triangles)
    sensitivity = {
        "question_2_independent_h_reoptimized": {
            "role": "sensitivity only; the deliverable uses the Q1-selected shared instrument design h",
            "shared_h_m": h,
            "independent_h_m": h2_independent,
            "vertex_axial_difference_m": float(abs(h2_independent - h)),
            "independent_vertex_xyz_m": ((-fitted_radius +
                                           h2_independent) * u2).tolist(),
            "radial_rms_improvement_m": float(
                metrics2["radial_fit_rms_m"] -
                metrics2_independent["radial_fit_rms_m"]),
            "radial_rms_relative_improvement": float(
                1.0 - metrics2_independent["radial_fit_rms_m"] /
                metrics2["radial_fit_rms_m"]),
            "surface": metrics2_independent,
            "reception": public_trace(trace2_independent),
            "h_grid_best_neighbors": sorted(
                h2_history, key=lambda x: abs(x["h"] - h2_independent))[:7],
        },
        "radius_nominal_300m_reoptimized": {
            "radius_m": NOMINAL_RADIUS,
            "h_m": h_nom,
            "surface": nominal_surface,
            "reception": public_trace(nominal_trace),
            "h_grid_best_neighbors": sorted(h_nom_history,
                                             key=lambda x: abs(x["h"] - h_nom))[:5],
        },
        "h_perturbations": {},
        "angle_conventions": {},
    }
    for hp in (h - 0.01, h + 0.01):
        _, sm, _, _, tr = solve_case(q0, rhat, u2, fitted_radius, hp,
                                     edges, base_edge_len, neighbors,
                                     top0, bottom, triangles)
        sensitivity["h_perturbations"][f"{hp:.6f}"] = {
            "surface": sm, "reception": public_trace(tr)}
    for convention in ("mirror_y", "swap_xy"):
        ua = unit_from_angles(ALPHA, BETA, convention)
        _, sm, _, _, tr = solve_case(q0, rhat, ua, fitted_radius, h,
                                     edges, base_edge_len, neighbors,
                                     top0, bottom, triangles)
        sensitivity["angle_conventions"][convention] = {
            "unit_vector": ua.tolist(), "surface": sm,
            "reception": public_trace(tr)}

    # Six-decimal delivery validation.  Non-aperture nodes remain the input data.
    active2 = sol2["active"]
    q_round = q0.copy()
    q_round[active2] = np.round(q2[active2], 6)
    rounded_edge_len = np.linalg.norm(q_round[edges[:, 0]] -
                                      q_round[edges[:, 1]], axis=1)
    strain_round = (rounded_edge_len - base_edge_len) / base_edge_len
    delta_round = np.round(delta2, 6)
    inward = top0 - bottom
    inward /= np.linalg.norm(inward, axis=1)[:, None]
    top_round = top0 + delta_round[:, None] * inward
    cable0 = np.linalg.norm(q0 - top0, axis=1)
    cable_round_residual = np.linalg.norm(q_round - top_round, axis=1) - cable0
    round_shift = q_round - q0
    radial_component = np.sum(round_shift * rhat, axis=1)[:, None] * rhat
    radiality_residual = np.linalg.norm(round_shift - radial_component, axis=1)
    delivery_validation = {
        "coordinate_decimals": 6,
        "all_6525_edges_rechecked": True,
        "max_edge_relative_change_after_rounding": float(np.max(np.abs(strain_round))),
        "edge_violation_count_after_rounding": int(np.sum(
            np.abs(strain_round) > EDGE_LIMIT + 1e-11)),
        "all_active_nodes_rechecked": True,
        "active_node_count": int(active2.sum()),
        "all_active_actuators_rechecked": True,
        "actuator_violation_count_after_rounding": int(np.sum(
            np.abs(delta_round[active2]) > ACTUATOR_LIMIT + 1e-11)),
        "max_actuator_abs_after_rounding_m": float(np.max(
            np.abs(delta_round[active2]))),
        "max_fixed_cable_residual_after_rounding_m": float(np.max(
            np.abs(cable_round_residual[active2]))),
        "max_radiality_residual_after_rounding_m": float(np.max(
            radiality_residual[active2])),
    }
    if delivery_validation["edge_violation_count_after_rounding"] != 0:
        raise RuntimeError("rounded delivery crosses edge constraint")
    if delivery_validation["actuator_violation_count_after_rounding"] != 0:
        raise RuntimeError("rounded delivery crosses actuator constraint")

    input_hashes = {name: sha256(path) for name, path in files.items()}
    metrics = {
        "run": {
            "seed": SEED,
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "input_sha256": input_hashes,
        },
        "conventions": {
            "fitted_radius_m": fitted_radius,
            "nominal_radius_m": NOMINAL_RADIUS,
            "primary_radius_choice": "mean Euclidean norm of Attachment 01 nodes",
            "focal_ratio": FOCAL_RATIO,
            "aperture_radius_m": APERTURE_RADIUS,
            "edge_limit": EDGE_LIMIT,
            "edge_work_limit": EDGE_WORK_LIMIT,
            "actuator_limit_m": ACTUATOR_LIMIT,
            "receiver_radius_m": RECEIVER_RADIUS,
            "angle_convention": "azimuth from +x toward +y; elevation above xy",
            "u_question_1": u1.tolist(),
            "u_question_2": u2.tolist(),
            "focus_question_2": focus2.tolist(),
            "selected_h_m": h,
            "shared_h_policy": "Q1 determines one focus-consistent instrument design; Q2 rotates that same design and does not re-optimize the deliverable h",
            "paraboloid_focal_length_m": FOCAL_RATIO * fitted_radius - h,
            "paraboloid_vertex_question_2": vertex2.tolist(),
            "node_motion": "baseline radial ray",
            "actuator_motion": "measured Attachment 02 bottom-to-top axis, oriented toward the sphere center",
            "fixed_drop_cable": True,
        },
        "topology": {
            "node_count": len(q0), "triangle_count": len(triangles),
            "unique_edge_count": len(edges)},
        "question_1": metrics1,
        "question_2": metrics2,
        "actuator_axis_diagnostics": axis_diagnostics,
        "question_3": q3_primary,
        "question_3_diagnostics": q3_sensitivity,
        "question_3_validation": q3_validation,
        "sensitivity": sensitivity,
        "h_selection_question_1": {
            "criterion": "minimum constrained active-node radial RMS",
            "selected_h_m": h,
            "grid_resolution_refined_m": 0.00125,
            "nearest_grid_points": sorted(h_history,
                                          key=lambda x: abs(x["h"] - h))[:7],
        },
        "candidate_rejections": {
            "focus_fixed_h_zero_direct_target": direct_target_summary(
                q0, rhat, u1, fitted_radius, 0.0, edges, base_edge_len,
                top0, bottom),
            "selected_h_direct_target_without_edge_projection": direct_target_summary(
                q0, rhat, u1, fitted_radius, h, edges, base_edge_len,
                top0, bottom),
            "uniform_scaling_only_rms_m": float(np.sqrt(np.mean((
                sol1["scale"] * sol1["d_target"][sol1["active"]] -
                sol1["d_target"][sol1["active"]]) ** 2))),
            "coordinate_refined_rms_m": metrics1["radial_fit_rms_m"],
        },
        "delivery_validation": delivery_validation,
    }

    output = root / "outputs"
    output.mkdir(exist_ok=True)
    (output / "solution_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2,
                   default=json_default) + "\n", encoding="utf-8")
    active_idx = np.flatnonzero(active2)
    result_data = {
        "metadata": {
            "source_template": "附件/附件04.xlsx",
            "selected_node_count": int(len(active_idx)),
            "coordinate_decimals": 6,
        },
        "vertex": np.round(vertex2, 6).tolist(),
        "nodes": [[node_ids[i], *np.round(q2[i], 6).tolist()] for i in active_idx],
        "actuators": [[node_ids[i], float(np.round(delta2[i], 6))]
                      for i in active_idx],
    }
    (output / "result_data.json").write_text(
        json.dumps(result_data, ensure_ascii=False, indent=2,
                   default=json_default) + "\n", encoding="utf-8")
    pd.DataFrame({
        "node_id": node_ids[active_idx],
        "x_adjusted_m": q2[active_idx, 0],
        "y_adjusted_m": q2[active_idx, 1],
        "z_adjusted_m": q2[active_idx, 2],
        "target_radial_displacement_m": sol2["d_target"][active_idx],
        "actual_radial_displacement_m": sol2["d"][active_idx],
        "actuator_extension_m": delta2[active_idx],
    }).to_csv(output / "q2_node_solution.csv", index=False, encoding="utf-8")
    pd.DataFrame({
        "panel_row": np.arange(1, len(triangles) + 1),
        "included_primary": adjusted_trace["_included"],
        "hit_adjusted": adjusted_trace["_hit"],
        "footprint_fraction_adjusted": adjusted_trace["_footprint_fraction"],
        "distance_adjusted_m": adjusted_trace["_distance"],
        "hit_baseline": baseline_trace["_hit"],
        "footprint_fraction_baseline": baseline_trace["_footprint_fraction"],
        "distance_baseline_m": baseline_trace["_distance"],
        "projected_weight_adjusted_m2": adjusted_trace["_projected_weight"],
        "projected_weight_baseline_m2": baseline_trace["_projected_weight"],
    }).to_csv(output / "q3_panel_diagnostics.csv", index=False, encoding="utf-8")

    print(json.dumps({
        "selected_h_m": h,
        "question_1": metrics1,
        "question_2": metrics2,
        "question_3": q3_primary,
        "delivery_validation": delivery_validation,
    }, ensure_ascii=False, indent=2, default=json_default))


if __name__ == "__main__":
    main()
