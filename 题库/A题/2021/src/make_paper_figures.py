#!/usr/bin/env python3
"""Validate machine outputs and generate the two paper figures.

The drawing backend is Pillow rather than a plotting library so the script
runs in the bundled offline Python environment.  Every plotted value is read
from the four attachments or the machine outputs produced by solve_all.py.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


EDGE_LIMIT = 0.0007
ACTUATOR_LIMIT_M = 0.6
BLUE = "#2F6BFF"
ORANGE = "#E87830"
TEAL = "#159D82"
RED = "#D84A4A"
INK = "#1E293B"
MUTED = "#64748B"
GRID = "#DCE3EA"
PANEL = "#FAFBFD"
WHITE = "#FFFFFF"


def font(size: int) -> ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def text_center(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str,
                fill: str, text_font: ImageFont.ImageFont) -> None:
    box = draw.textbbox((0, 0), text, font=text_font)
    draw.text((xy[0] - (box[2] - box[0]) / 2,
               xy[1] - (box[3] - box[1]) / 2), text,
              fill=fill, font=text_font)


def axes(draw: ImageDraw.ImageDraw, panel: tuple[int, int, int, int],
         xlim: tuple[float, float], ylim: tuple[float, float], title: str,
         xlabel: str, ylabel: str,
         x_formatter=lambda x: f"{x:.2f}",
         y_formatter=lambda y: f"{y:.0f}") -> tuple[int, int, int, int]:
    x, y, w, h = panel
    draw.rounded_rectangle((x, y, x + w, y + h), radius=12,
                           fill=PANEL, outline=GRID, width=2)
    plot = (x + 100, y + 80, x + w - 28, y + h - 72)
    left, top, right, bottom = plot
    for value in np.linspace(xlim[0], xlim[1], 5):
        px = left + (value - xlim[0]) / (xlim[1] - xlim[0]) * (right - left)
        draw.line((px, top, px, bottom), fill=GRID, width=1)
        text_center(draw, (px, bottom + 21), x_formatter(float(value)),
                    MUTED, font(18))
    for value in np.linspace(ylim[0], ylim[1], 5):
        py = bottom - (value - ylim[0]) / (ylim[1] - ylim[0]) * (bottom - top)
        draw.line((left, py, right, py), fill=GRID, width=1)
        label = y_formatter(float(value))
        box = draw.textbbox((0, 0), label, font=font(18))
        draw.text((left - 12 - (box[2] - box[0]), py - 10), label,
                  fill=MUTED, font=font(18))
    draw.line((left, bottom, right, bottom), fill=INK, width=2)
    draw.line((left, top, left, bottom), fill=INK, width=2)
    draw.text((x + 22, y + 17), title, fill=INK, font=font(24))
    draw.text((left, y + 50), ylabel, fill=MUTED, font=font(17))
    text_center(draw, ((left + right) / 2, y + h - 24), xlabel,
                INK, font(19))
    return plot


def map_point(value: float, lim: tuple[float, float], lo: float,
              hi: float) -> float:
    return lo + (value - lim[0]) / (lim[1] - lim[0]) * (hi - lo)


def histogram(draw: ImageDraw.ImageDraw, panel: tuple[int, int, int, int],
              values: np.ndarray, bins: np.ndarray, title: str,
              xlabel: str, color: str, annotation: str,
              x_formatter=lambda x: f"{x:.2f}") -> None:
    counts, edges = np.histogram(values, bins=bins)
    ymax = max(1.0, math.ceil(float(counts.max()) * 1.15))
    xlim = (float(edges[0]), float(edges[-1]))
    plot = axes(draw, panel, xlim, (0.0, ymax), title, xlabel,
                "Node/edge count", x_formatter=x_formatter)
    left, top, right, bottom = plot
    for count, a, b in zip(counts, edges[:-1], edges[1:]):
        x0 = map_point(float(a), xlim, left, right) + 1
        x1 = map_point(float(b), xlim, left, right) - 1
        y0 = map_point(float(count), (0.0, ymax), bottom, top)
        draw.rectangle((x0, y0, x1, bottom), fill=color)
    draw.text((panel[0] + panel[2] - 355, panel[1] + 20), annotation,
              fill=MUTED, font=font(17))


def scatter_target(draw: ImageDraw.ImageDraw,
                   panel: tuple[int, int, int, int], target: np.ndarray,
                   actual: np.ndarray, rms: float) -> None:
    lo = float(min(target.min(), actual.min())) - 0.03
    hi = float(max(target.max(), actual.max())) + 0.03
    lim = (lo, hi)
    plot = axes(draw, panel, lim, lim,
                "(A) Target versus feasible displacement",
                "Target radial displacement (m)",
                "Feasible displacement (m)",
                y_formatter=lambda y: f"{y:.2f}")
    left, top, right, bottom = plot
    x0 = map_point(lo, lim, left, right)
    y0 = map_point(lo, lim, bottom, top)
    x1 = map_point(hi, lim, left, right)
    y1 = map_point(hi, lim, bottom, top)
    draw.line((x0, y0, x1, y1), fill=MUTED, width=2)
    for tx, ay in zip(target, actual):
        px = map_point(float(tx), lim, left, right)
        py = map_point(float(ay), lim, bottom, top)
        draw.ellipse((px - 2.2, py - 2.2, px + 2.2, py + 2.2),
                     fill=BLUE)
    draw.text((panel[0] + panel[2] - 290, panel[1] + 20),
              f"RMS residual = {rms:.5f} m", fill=MUTED,
              font=font(17))


def figure_surface_and_constraints(q2: pd.DataFrame, strain: np.ndarray,
                                   output: Path, rms: float) -> None:
    image = Image.new("RGB", (1800, 1120), WHITE)
    draw = ImageDraw.Draw(image)
    draw.text((58, 32), "Question 2: surface adjustment and mechanical feasibility",
              fill=INK, font=font(38))
    draw.text((58, 79),
              "All distributions use the 692-node deliverable and all 6,525 main-cable edges.",
              fill=MUTED, font=font(21))
    panels = [(55, 125, 830, 430), (915, 125, 830, 430),
              (55, 580, 830, 430), (915, 580, 830, 430)]
    target = q2["target_radial_displacement_m"].to_numpy(float)
    actual = q2["actual_radial_displacement_m"].to_numpy(float)
    residual = actual - target
    actuator = q2["actuator_extension_m"].to_numpy(float)
    utilization = np.abs(strain) / EDGE_LIMIT * 100.0
    scatter_target(draw, panels[0], target, actual, rms)
    histogram(draw, panels[1], residual,
              np.linspace(-0.20, 0.20, 33),
              "(B) Surface-fit residual distribution",
              "Feasible minus target displacement (m)", ORANGE,
              f"max |residual| = {np.max(np.abs(residual)):.5f} m")
    histogram(draw, panels[2], actuator,
              np.linspace(-ACTUATOR_LIMIT_M, ACTUATOR_LIMIT_M, 33),
              "(C) Actuator extension distribution",
              "Extension toward sphere center (m)", TEAL,
              f"range = [{actuator.min():.3f}, {actuator.max():.3f}] m")
    histogram(draw, panels[3], utilization,
              np.linspace(0.0, 100.0, 33),
              "(D) Main-cable constraint utilization",
              "Absolute strain / 0.07% limit (%)", RED,
              f"max = {utilization.max():.5f}% of limit",
              x_formatter=lambda x: f"{x:.0f}")
    draw.text((58, 1070),
              "Source: Attachments 01-03 and outputs/q2_node_solution.csv; generated by src/make_paper_figures.py.",
              fill=MUTED, font=font(18))
    image.save(output, format="PNG", optimize=True)


def figure_reception(metrics: dict, output: Path) -> None:
    pairs = metrics["question_3"]["boundary_rule_pairs"]
    keys = ["all_vertices", "centroid", "any_vertex"]
    labels = ["All vertices", "Centroid", "Any vertex"]
    adjusted = np.array([pairs[key]["adjusted_ratio"] for key in keys]) * 100.0
    baseline = np.array([pairs[key]["baseline_ratio"] for key in keys]) * 100.0
    factors = np.array([pairs[key]["improvement_factor"] for key in keys])

    image = Image.new("RGB", (1800, 820), WHITE)
    draw = ImageDraw.Draw(image)
    draw.text((58, 32), "Question 3: reception robustness across aperture-boundary rules",
              fill=INK, font=font(38))
    draw.text((58, 79),
              "Each pair uses a panel set fixed by baseline geometry; improvement factors span 1.312562-1.314138.",
              fill=MUTED, font=font(21))

    left_panel = (55, 125, 1040, 615)
    plot = axes(draw, left_panel, (-0.5, 2.5), (0.0, 1.25),
                "(A) Projected-area weighted reception ratio",
                "", "Reception ratio (%)",
                x_formatter=lambda _: "",
                y_formatter=lambda y: f"{y:.2f}")
    l, t, r, b = plot
    centers = np.linspace(l + (r - l) / 6, r - (r - l) / 6, 3)
    bar_width = 70
    for i, center in enumerate(centers):
        for value, offset, color in ((baseline[i], -bar_width / 2, ORANGE),
                                     (adjusted[i], bar_width / 2, BLUE)):
            yv = map_point(float(value), (0.0, 1.25), b, t)
            draw.rectangle((center + offset - bar_width / 2, yv,
                            center + offset + bar_width / 2, b), fill=color)
            text_center(draw, (center + offset, yv - 14), f"{value:.4f}%",
                        INK, font(17))
        text_center(draw, (center, b + 34), labels[i], INK, font(18))
    text_center(draw, (left_panel[0] + left_panel[2] / 2,
                       left_panel[1] + left_panel[3] - 18),
                "Aperture boundary rule", INK, font(19))
    draw.rectangle((left_panel[0] + 680, left_panel[1] + 17,
                    left_panel[0] + 700, left_panel[1] + 37), fill=BLUE)
    draw.text((left_panel[0] + 710, left_panel[1] + 16), "Adjusted",
              fill=INK, font=font(17))
    draw.rectangle((left_panel[0] + 820, left_panel[1] + 17,
                    left_panel[0] + 840, left_panel[1] + 37), fill=ORANGE)
    draw.text((left_panel[0] + 850, left_panel[1] + 16), "Baseline",
              fill=INK, font=font(17))

    right_panel = (1125, 125, 620, 615)
    ylim = (1.3122, 1.3145)
    plot = axes(draw, right_panel, (-0.35, 2.35), ylim,
                "(B) Improvement factor (zoomed scale)",
                "", "Adjusted / baseline",
                x_formatter=lambda _: "",
                y_formatter=lambda y: f"{y:.4f}")
    l, t, r, b = plot
    centers = np.linspace(l + (r - l) / 6, r - (r - l) / 6, 3)
    points = []
    for i, (center, value) in enumerate(zip(centers, factors)):
        py = map_point(float(value), ylim, b, t)
        points.append((center, py))
        draw.ellipse((center - 8, py - 8, center + 8, py + 8), fill=TEAL)
        text_center(draw, (center, py - 25), f"{value:.6f}", INK, font(17))
        text_center(draw, (center, b + 34), labels[i], INK, font(17))
    draw.line(points, fill=TEAL, width=3)
    text_center(draw, (right_panel[0] + right_panel[2] / 2,
                       right_panel[1] + right_panel[3] - 18),
                "Aperture boundary rule", INK, font(19))
    draw.text((58, 775),
              "Source: outputs/solution_metrics.json; generated by src/make_paper_figures.py.",
              fill=MUTED, font=font(18))
    image.save(output, format="PNG", optimize=True)


def validate_and_load(root: Path) -> tuple[dict, pd.DataFrame, np.ndarray]:
    output = root / "outputs"
    metrics = json.loads((output / "solution_metrics.json").read_text(
        encoding="utf-8"))
    result_data = json.loads((output / "result_data.json").read_text(
        encoding="utf-8"))
    q2 = pd.read_csv(output / "q2_node_solution.csv")
    q3 = pd.read_csv(output / "q3_panel_diagnostics.csv")
    nodes = pd.read_csv(root / "附件" / "附件01.csv", encoding="gb18030")
    actuators = pd.read_csv(root / "附件" / "附件02.csv", encoding="gb18030")
    triangles_table = pd.read_csv(root / "附件" / "附件03.csv",
                                  encoding="gb18030")

    assert len(nodes) == len(actuators) == 2226
    assert len(triangles_table) == len(q3) == 4300
    assert len(q2) == len(result_data["nodes"]) == len(result_data["actuators"]) == 692
    node_ids = nodes.iloc[:, 0].astype(str).to_numpy()
    assert np.array_equal(node_ids, actuators.iloc[:, 0].astype(str).to_numpy())
    q2_ids = q2["node_id"].astype(str).to_numpy()
    assert q2_ids.tolist() == [str(row[0]) for row in result_data["nodes"]]
    assert q2_ids.tolist() == [str(row[0]) for row in result_data["actuators"]]
    assert len(set(q2_ids)) == 692
    assert np.isfinite(q2.select_dtypes(include=[np.number]).to_numpy()).all()
    assert np.isfinite(q3.select_dtypes(include=[np.number]).to_numpy()).all()

    q0 = nodes.iloc[:, 1:4].to_numpy(float)
    id_to_index = {identifier: i for i, identifier in enumerate(node_ids)}
    active = np.array([id_to_index[identifier] for identifier in q2_ids])
    q = q0.copy()
    q[active] = q2[["x_adjusted_m", "y_adjusted_m", "z_adjusted_m"]].to_numpy(float)
    rounded_nodes = np.array([row[1:] for row in result_data["nodes"]], float)
    rounded_actuators = np.array([row[1] for row in result_data["actuators"]], float)
    assert np.array_equal(np.round(q[active], 6), rounded_nodes)
    assert np.array_equal(np.round(q2["actuator_extension_m"].to_numpy(float), 6),
                          rounded_actuators)

    triangle_ids = triangles_table.iloc[:, :3].astype(str).to_numpy()
    triangles = np.array([[id_to_index[x] for x in row]
                          for row in triangle_ids], dtype=int)
    edges = set()
    for a, b, c in triangles:
        edges.update((tuple(sorted((int(a), int(b)))),
                      tuple(sorted((int(b), int(c)))),
                      tuple(sorted((int(c), int(a))))))
    edge_array = np.array(sorted(edges), dtype=int)
    assert len(edge_array) == metrics["topology"]["unique_edge_count"] == 6525
    base_length = np.linalg.norm(q0[edge_array[:, 0]] -
                                 q0[edge_array[:, 1]], axis=1)
    adjusted_length = np.linalg.norm(q[edge_array[:, 0]] -
                                     q[edge_array[:, 1]], axis=1)
    strain = (adjusted_length - base_length) / base_length
    assert np.max(np.abs(strain)) <= EDGE_LIMIT + 2e-11
    assert math.isclose(float(np.max(np.abs(strain))),
                        metrics["question_2"]["max_edge_relative_change"],
                        rel_tol=0.0, abs_tol=2e-13)

    u = np.array(metrics["conventions"]["u_question_2"], float)
    rho = np.linalg.norm(q0 - (q0 @ u)[:, None] * u, axis=1)
    assert np.array_equal(np.flatnonzero(rho <= 150.0), active)

    bottom = actuators.iloc[:, 1:4].to_numpy(float)
    top0 = actuators.iloc[:, 4:7].to_numpy(float)
    inward = top0 - bottom
    inward /= np.linalg.norm(inward, axis=1)[:, None]
    delta = q2["actuator_extension_m"].to_numpy(float)
    cable0 = np.linalg.norm(q0[active] - top0[active], axis=1)
    moved_top = top0[active] + delta[:, None] * inward[active]
    cable_residual = np.linalg.norm(q[active] - moved_top, axis=1) - cable0
    assert np.max(np.abs(delta)) <= ACTUATOR_LIMIT_M + 1e-11
    assert np.max(np.abs(cable_residual)) < 1e-10

    included = q3["included_primary"].astype(bool).to_numpy()
    assert int(included.sum()) == 1374
    for prefix, ratio_name in (("adjusted", "adjusted_reception_ratio"),
                               ("baseline", "baseline_reception_ratio")):
        weights = q3[f"projected_weight_{prefix}_m2"].to_numpy(float)
        fractions = q3[f"footprint_fraction_{prefix}"].to_numpy(float)
        ratio = float(np.sum(weights[included] * fractions[included]) /
                      np.sum(weights[included]))
        assert math.isclose(ratio, metrics["question_3"][ratio_name],
                            rel_tol=0.0, abs_tol=2e-15)

    return metrics, q2, strain


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    metrics, q2, strain = validate_and_load(root)
    figures = root / "figures"
    figures.mkdir(exist_ok=True)
    figure_surface_and_constraints(
        q2, strain, figures / "figure1_surface_constraints.png",
        metrics["question_2"]["radial_fit_rms_m"])
    figure_reception(metrics, figures / "figure2_reception_boundaries.png")
    print(json.dumps({
        "validation": "PASS",
        "active_nodes": len(q2),
        "unique_edges": len(strain),
        "max_edge_relative_change": float(np.max(np.abs(strain))),
        "figure_files": [
            "figures/figure1_surface_constraints.png",
            "figures/figure2_reception_boundaries.png",
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
