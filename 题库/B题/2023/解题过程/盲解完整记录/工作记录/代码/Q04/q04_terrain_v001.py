from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "工作记录" / "诊断结果" / "Q04" / "q04_source_grid_v001.json"
OUT_DIR = ROOT / "工作记录" / "诊断结果" / "Q04"
NMI = 1852.0
GAMMA = math.radians(60.0)


class Terrain:
    def __init__(self) -> None:
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        self.source_hash = source["source_sha256"]
        self.x = np.asarray(source["x_nmi"], dtype=float) * NMI
        self.y = np.asarray(source["y_nmi"], dtype=float) * NMI
        self.depth = np.asarray(source["depth_m"], dtype=float)
        if self.depth.shape != (self.y.size, self.x.size):
            raise ValueError("Grid shape mismatch")
        self.dx = float(self.x[1] - self.x[0])
        self.dy = float(self.y[1] - self.y[0])

    def evaluate(self, xq, yq, representation: str = "bilinear"):
        xq = np.asarray(xq, dtype=float)
        yq = np.asarray(yq, dtype=float)
        xq, yq = np.broadcast_arrays(xq, yq)
        if np.any(xq < self.x[0]) or np.any(xq > self.x[-1]) or np.any(yq < self.y[0]) or np.any(yq > self.y[-1]):
            raise ValueError("Query outside terrain domain")
        ix = np.floor((xq - self.x[0]) / self.dx).astype(int)
        iy = np.floor((yq - self.y[0]) / self.dy).astype(int)
        ix = np.clip(ix, 0, self.x.size - 2)
        iy = np.clip(iy, 0, self.y.size - 2)
        u = (xq - self.x[ix]) / self.dx
        v = (yq - self.y[iy]) / self.dy
        f00 = self.depth[iy, ix]
        f10 = self.depth[iy, ix + 1]
        f01 = self.depth[iy + 1, ix]
        f11 = self.depth[iy + 1, ix + 1]

        if representation == "bilinear":
            depth = (1 - u) * (1 - v) * f00 + u * (1 - v) * f10 + (1 - u) * v * f01 + u * v * f11
            ddx = ((1 - v) * (f10 - f00) + v * (f11 - f01)) / self.dx
            ddy = ((1 - u) * (f01 - f00) + u * (f11 - f10)) / self.dy
        elif representation == "tri_main":
            lower = v <= u
            depth = np.where(
                lower,
                f00 + u * (f10 - f00) + v * (f11 - f10),
                f00 + u * (f11 - f01) + v * (f01 - f00),
            )
            ddx = np.where(lower, (f10 - f00) / self.dx, (f11 - f01) / self.dx)
            ddy = np.where(lower, (f11 - f10) / self.dy, (f01 - f00) / self.dy)
        elif representation == "tri_anti":
            lower = u + v <= 1
            depth = np.where(
                lower,
                f00 + u * (f10 - f00) + v * (f01 - f00),
                f11 + (u - 1) * (f11 - f01) + (v - 1) * (f11 - f10),
            )
            ddx = np.where(lower, (f10 - f00) / self.dx, (f11 - f01) / self.dx)
            ddy = np.where(lower, (f01 - f00) / self.dy, (f11 - f10) / self.dy)
        else:
            raise ValueError(representation)
        return depth, -ddx, -ddy

    def strip_bounds(self, axis: str, center: float, along, representation: str = "bilinear"):
        along = np.asarray(along, dtype=float)
        if axis == "vertical":
            depth, zx, _ = self.evaluate(np.full_like(along, center), along, representation)
            slope = zx
        elif axis == "horizontal":
            depth, _, zy = self.evaluate(along, np.full_like(along, center), representation)
            slope = zy
        else:
            raise ValueError(axis)
        sg = math.sin(GAMMA)
        cg = math.cos(GAMMA)
        denom_left = cg - slope * sg
        denom_right = cg + slope * sg
        if np.any(depth <= 0) or np.any(denom_left <= 0) or np.any(denom_right <= 0):
            raise ValueError("Invalid local ray-plane domain")
        left_width = depth * sg / denom_left
        right_width = depth * sg / denom_right
        return center - left_width, center + right_width, depth, slope


def main() -> None:
    terrain = Terrain()
    xx, yy = np.meshgrid(terrain.x, terrain.y)
    depth, zx, zy = terrain.evaluate(xx, yy)
    slope_deg = np.degrees(np.arctan(np.hypot(zx, zy)))
    node_error = float(np.max(np.abs(depth - terrain.depth)))

    sample_x = np.linspace(terrain.x[0], terrain.x[-1], 121)
    sample_y = np.linspace(terrain.y[0], terrain.y[-1], 151)
    sx, sy = np.meshgrid(sample_x, sample_y)
    bil, _, _ = terrain.evaluate(sx, sy, "bilinear")
    tri1, _, _ = terrain.evaluate(sx, sy, "tri_main")
    tri2, _, _ = terrain.evaluate(sx, sy, "tri_anti")

    tests = {
        "source_sha256": terrain.source_hash,
        "shape": list(terrain.depth.shape),
        "x_range_nmi": [terrain.x[0] / NMI, terrain.x[-1] / NMI],
        "y_range_nmi": [terrain.y[0] / NMI, terrain.y[-1] / NMI],
        "dx_m": terrain.dx,
        "dy_m": terrain.dy,
        "depth_min_m": float(np.min(terrain.depth)),
        "depth_max_m": float(np.max(terrain.depth)),
        "depth_mean_m": float(np.mean(terrain.depth)),
        "bilinear_node_reconstruction_max_error_m": node_error,
        "slope_deg": {
            "min": float(np.min(slope_deg)),
            "median": float(np.median(slope_deg)),
            "p95": float(np.percentile(slope_deg, 95)),
            "max": float(np.max(slope_deg)),
        },
        "mean_elevation_gradient": [float(np.mean(zx)), float(np.mean(zy))],
        "mean_uphill_azimuth_deg_from_east": float(math.degrees(math.atan2(float(np.mean(zy)), float(np.mean(zx))))),
        "bilinear_vs_tri_main_max_depth_difference_m": float(np.max(np.abs(bil - tri1))),
        "bilinear_vs_tri_anti_max_depth_difference_m": float(np.max(np.abs(bil - tri2))),
        "triangulation_max_depth_difference_m": float(np.max(np.abs(tri1 - tri2))),
    }
    (OUT_DIR / "q04_terrain_model_v001.json").write_text(json.dumps(tests, ensure_ascii=False, indent=2), encoding="utf-8")

    fig, ax = plt.subplots(figsize=(10, 7))
    image = ax.contourf(terrain.x / NMI, terrain.y / NMI, terrain.depth, levels=24, cmap="viridis_r")
    fig.colorbar(image, ax=ax, label="Depth (m)")
    ax.set_xlabel("East-west coordinate (nmi)")
    ax.set_ylabel("South-north coordinate (nmi)")
    ax.set_title("Question 4 historical bathymetry")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "第4问地形图-v001.png", dpi=220)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 7))
    image = ax.contourf(terrain.x / NMI, terrain.y / NMI, slope_deg, levels=20, cmap="magma")
    skip = (slice(None, None, 15), slice(None, None, 12))
    norm = np.hypot(zx, zy)
    ax.quiver(
        xx[skip] / NMI, yy[skip] / NMI,
        np.divide(zx[skip], norm[skip], out=np.zeros_like(zx[skip]), where=norm[skip] > 0),
        np.divide(zy[skip], norm[skip], out=np.zeros_like(zy[skip]), where=norm[skip] > 0),
        color="white", alpha=0.7, scale=35,
    )
    fig.colorbar(image, ax=ax, label="Local slope (deg)")
    ax.set_xlabel("East-west coordinate (nmi)")
    ax.set_ylabel("South-north coordinate (nmi)")
    ax.set_title("Question 4 local slope and uphill direction")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "第4问坡度坡向图-v001.png", dpi=220)
    plt.close(fig)

    print(json.dumps(tests, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
