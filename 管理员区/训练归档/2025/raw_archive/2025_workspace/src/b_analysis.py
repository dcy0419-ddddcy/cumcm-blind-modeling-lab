from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL_PACKAGES = ROOT / "tmp" / "python_packages"
if LOCAL_PACKAGES.exists():
    sys.path.insert(0, str(LOCAL_PACKAGES))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d
from scipy.optimize import minimize_scalar
from scipy.signal import find_peaks, savgol_filter


DATA = ROOT / "附件_B题" / "附件"
OUT = ROOT / "outputs" / "independent" / "B"


def load(index: int) -> tuple[np.ndarray, np.ndarray]:
    df = pd.read_excel(DATA / f"附件{index}.xlsx")
    x = pd.to_numeric(df.iloc[:, 0], errors="coerce").to_numpy(float)
    y = pd.to_numeric(df.iloc[:, 1], errors="coerce").to_numpy(float)
    mask = np.isfinite(x) & np.isfinite(y) & (y > 0)
    return x[mask], y[mask]


def detrend(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    step = float(np.median(np.diff(x)))
    window = int(round(500.0 / step))
    window = min(window if window % 2 else window + 1, len(y) - (1 - len(y) % 2))
    window = max(window, 101)
    baseline = savgol_filter(y, window, 3)
    residual = y - baseline
    return residual, baseline


def peak_table(x: np.ndarray, y: np.ndarray, lo: float, hi: float) -> dict:
    mask = (x >= lo) & (x <= hi)
    xb, yb = x[mask], y[mask]
    residual, baseline = detrend(xb, yb)
    smooth = gaussian_filter1d(residual, 3)
    prom = max(0.08 * float(np.ptp(smooth)), float(np.std(smooth)) * 0.45)
    distance = max(5, int(25.0 / np.median(np.diff(xb))))
    idx, props = find_peaks(smooth, prominence=prom, distance=distance)
    peaks = xb[idx]
    deltas = np.diff(peaks)
    return {
        "band": [lo, hi],
        "count": int(len(peaks)),
        "peaks": peaks.tolist(),
        "median_spacing": float(np.median(deltas)) if len(deltas) else None,
        "mean_spacing": float(np.mean(deltas)) if len(deltas) else None,
        "spacing_cv": float(np.std(deltas, ddof=1) / np.mean(deltas)) if len(deltas) > 1 else None,
        "prominence": prom,
    }


def exploratory() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(4, 1, figsize=(11, 12), sharex=True)
    result = {}
    bands = [(500, 900), (1000, 1800), (1800, 2800), (2800, 3900)]
    for i, ax in enumerate(axes, start=1):
        x, y = load(i)
        ax.plot(x, y, color="#1f4e79", lw=0.7)
        ax.set_ylabel(f"File {i}\nR (%)")
        ax.grid(alpha=0.18)
        result[f"file{i}"] = {
            "range": [float(x.min()), float(x.max())],
            "n": int(len(x)),
            "reflectance": [float(y.min()), float(y.max())],
            "bands": [peak_table(x, y, lo, hi) for lo, hi in bands],
        }
    axes[-1].set_xlabel("Wavenumber (cm$^{-1}$)")
    fig.tight_layout()
    fig.savefig(OUT / "spectra_overview.png", dpi=180)
    plt.close(fig)
    (OUT / "exploratory.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def n_sic(wavenumber: np.ndarray) -> np.ndarray:
    """Ordinary-ray Sellmeier approximation for SiC; wavelength is in micrometres."""
    wavelength = 1.0e4 / wavenumber
    return np.sqrt(1.0 + 5.5515 * wavelength**2 / (wavelength**2 - 0.026406))


def n_si(wavenumber: np.ndarray) -> np.ndarray:
    """Mid-infrared dispersion approximation for crystalline silicon."""
    wavelength = 1.0e4 / wavenumber
    return np.sqrt(11.6858 + 0.939816 / wavelength**2 + 0.00304347 / wavelength**4)


def optical_coordinate(wavenumber: np.ndarray, angle_deg: float, material: str) -> np.ndarray:
    n = n_sic(wavenumber) if material == "SiC" else n_si(wavenumber)
    return wavenumber * np.sqrt(n**2 - math.sin(math.radians(angle_deg)) ** 2)


def raw_peaks(index: int, band: tuple[float, float]) -> np.ndarray:
    x, y = load(index)
    mask = (x >= band[0]) & (x <= band[1])
    xb = x[mask]
    smooth = gaussian_filter1d(y[mask], 6)
    if index <= 2:
        distance_cm, prominence = 150.0, 0.08
    else:
        distance_cm, prominence = 300.0, 0.2
    distance = int(distance_cm / np.median(np.diff(xb)))
    idx, _ = find_peaks(smooth, prominence=prominence, distance=distance)
    return xb[idx]


def peak_regression(index: int, angle: float, material: str, band: tuple[float, float]) -> dict:
    peaks = raw_peaks(index, band)
    g = optical_coordinate(peaks, angle, material)
    order = np.arange(len(peaks), dtype=float)
    design = np.column_stack([np.ones(len(g)), g])
    beta, *_ = np.linalg.lstsq(design, order, rcond=None)
    fitted = design @ beta
    residual = order - fitted
    dof = max(len(order) - 2, 1)
    sigma2 = float(residual @ residual / dof)
    covariance = sigma2 * np.linalg.inv(design.T @ design)
    slope = float(beta[1])
    se_slope = float(np.sqrt(covariance[1, 1]))
    thickness_um = slope * 5000.0
    ci = [(slope - 1.96 * se_slope) * 5000.0, (slope + 1.96 * se_slope) * 5000.0]
    ss_tot = float(np.sum((order - order.mean()) ** 2))
    r2 = 1.0 - float(residual @ residual) / ss_tot
    return {
        "file": index,
        "angle_deg": angle,
        "material": material,
        "band": list(band),
        "peak_count": int(len(peaks)),
        "peaks_cm-1": peaks.tolist(),
        "thickness_um": thickness_um,
        "ci95_um": ci,
        "r2": r2,
    }


def polynomial_columns(z: np.ndarray, degree: int) -> list[np.ndarray]:
    return [z**k for k in range(degree + 1)]


def harmonic_design(g: np.ndarray, d_um: float, harmonics: int, baseline_degree: int) -> np.ndarray:
    z = (g - g.mean()) / (g.max() - g.min())
    phase = 4.0 * math.pi * d_um * 1.0e-4 * g
    cols = polynomial_columns(z, baseline_degree)
    # Linear amplitude drift absorbs the slow instrumental/envelope change.
    for k in range(1, harmonics + 1):
        cols.extend([np.cos(k * phase), np.sin(k * phase), z * np.cos(k * phase), z * np.sin(k * phase)])
    return np.column_stack(cols)


def harmonic_sse(
    datasets: list[tuple[np.ndarray, np.ndarray, float, str]], d_um: float, harmonics: int
) -> tuple[float, list[tuple[np.ndarray, np.ndarray]], int, int]:
    total = 0.0
    fits = []
    k_total = 1
    n_total = 0
    for x, y, angle, material in datasets:
        g = optical_coordinate(x, angle, material)
        design = harmonic_design(g, d_um, harmonics, baseline_degree=5)
        scale = float(np.std(y))
        ys = y / scale
        beta, *_ = np.linalg.lstsq(design, ys, rcond=None)
        pred = design @ beta
        residual = ys - pred
        total += float(residual @ residual)
        fits.append((pred * scale, beta))
        k_total += design.shape[1]
        n_total += len(y)
    return total, fits, k_total, n_total


def fit_harmonics(
    indices: tuple[int, int], angles: tuple[float, float], material: str, band: tuple[float, float], bounds: tuple[float, float],
    fixed_d_um: float | None = None,
) -> dict:
    datasets = []
    raw = []
    for index, angle in zip(indices, angles):
        x, y = load(index)
        mask = (x >= band[0]) & (x <= band[1])
        # Downsampling retains at least hundreds of points per fringe.
        xb, yb = x[mask][::2], y[mask][::2]
        datasets.append((xb, yb, angle, material))
        raw.append((xb, yb))
    models = {}
    for harmonics in (1, 4):
        objective = lambda d: harmonic_sse(datasets, float(d), harmonics)[0]
        if fixed_d_um is None:
            grid = np.linspace(bounds[0], bounds[1], 401)
            grid_sse = np.asarray([objective(float(d)) for d in grid])
            j = int(np.argmin(grid_sse))
            lo = grid[max(0, j - 2)]
            hi = grid[min(len(grid) - 1, j + 2)]
            result = minimize_scalar(objective, bounds=(float(lo), float(hi)), method="bounded", options={"xatol": 1e-8})
            thickness = float(result.x)
        else:
            thickness = float(fixed_d_um)
        sse, fits, k, n = harmonic_sse(datasets, thickness, harmonics)
        aic = n * math.log(sse / n) + 2 * k
        models[str(harmonics)] = {
            "thickness_um": thickness,
            "sse": sse,
            "aic": aic,
            "k": k,
            "n": n,
            "fits": fits,
        }

    # Harmonic magnitude ratio summarizes departure from a sinusoid.
    ratios = []
    for _, beta in models["4"]["fits"]:
        start = 6
        mags = []
        for h in range(4):
            b = beta[start + 4 * h : start + 4 * h + 4]
            mags.append(float(np.linalg.norm(b)))
        ratios.append(mags[1] / mags[0])

    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    for ax, (index, angle), (x, y), (fit, _) in zip(axes, zip(indices, angles), raw, models["4"]["fits"]):
        ax.plot(x, y, color="#243447", lw=0.8, label="measurement")
        ax.plot(x, fit, color="#b33b2e", lw=1.0, label="four-harmonic fit")
        ax.set_ylabel(f"File {index}  R (%)")
        ax.text(0.01, 0.91, f"incidence {angle:.0f}°", transform=ax.transAxes)
        ax.grid(alpha=0.18)
        ax.legend(loc="upper right")
    axes[-1].set_xlabel("Wavenumber (cm$^{-1}$)")
    fig.tight_layout()
    fig.savefig(OUT / f"{material.lower()}_fit.png", dpi=180)
    plt.close(fig)

    answer = {
        "material": material,
        "band": list(band),
        "two_beam": {k: v for k, v in models["1"].items() if k != "fits"},
        "four_harmonic": {k: v for k, v in models["4"].items() if k != "fits"},
        "delta_aic_two_minus_four": models["1"]["aic"] - models["4"]["aic"],
        "second_to_first_harmonic_ratio": ratios,
    }
    return answer


def final_analysis() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    peak_results = [
        peak_regression(1, 10.0, "SiC", (1800.0, 3900.0)),
        peak_regression(2, 15.0, "SiC", (1800.0, 3900.0)),
        peak_regression(3, 10.0, "Si", (1000.0, 3800.0)),
        peak_regression(4, 15.0, "Si", (1000.0, 3800.0)),
    ]
    sic_d = float(np.mean([peak_results[0]["thickness_um"], peak_results[1]["thickness_um"]]))
    si_d = float(np.mean([peak_results[2]["thickness_um"], peak_results[3]["thickness_um"]]))
    sic = fit_harmonics((1, 2), (10.0, 15.0), "SiC", (1800.0, 3900.0), (6.0, 10.0), sic_d)
    silicon = fit_harmonics((3, 4), (10.0, 15.0), "Si", (1000.0, 3800.0), (2.0, 6.0), si_d)
    result = {"peak_regression": peak_results, "harmonic_models": {"SiC": sic, "Si": silicon}}
    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    exploratory()
    print(json.dumps(final_analysis(), ensure_ascii=False, indent=2))
