# -*- coding: utf-8 -*-
import csv
import math
import os

import matplotlib.pyplot as plt
import numpy as np

EXPERIMENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
OUTPUT_DIR = os.path.join(EXPERIMENT_DIR, "outputs")
PROJECT_ROOT = os.path.abspath(os.path.join(EXPERIMENT_DIR, os.pardir, os.pardir))

LENGTH_M = 0.820
WIDTH_M = 0.345
RAW_NX = 201
RAW_NY = 85
NX = 16
NY = 8
TARGET_MEAN_MPA = 0.448

# Equivalent compliant layer parameters. Larger SIGMA spreads local mismatch
# over neighboring cells; ALPHA controls sensitivity to geometric mismatch.
SIGMA_CELLS = 1.15
ALPHA = 1.25
POWER = 1.15

CASES = [
    {
        "case": "min_distance_sum",
        "label": "Min-distance-sum order",
        "order": [1, 10, 9, 7, 11, 8, 12, 4, 14, 3, 5, 13, 15, 6, 2],
    },
    {
        "case": "natural",
        "label": "Natural order",
        "order": list(range(1, 16)),
    },
    {
        "case": "max_distance_sum",
        "label": "Max-distance-sum order",
        "order": [11, 12, 13, 7, 14, 9, 5, 6, 8, 15, 3, 1, 2, 10, 4],
    },
]


def ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def find_data_dir():
    for root, _dirs, files in os.walk(PROJECT_ROOT):
        if "820x345mm" in root:
            if len([n for n in files if n.lower().endswith(".csv")]) >= 15:
                return root
    raise RuntimeError("Cannot find 820x345mm CSV data directory under %s" % PROJECT_ROOT)


DATA_DIR = find_data_dir()


def read_plate_grid(plate_index):
    token = "_%02d_" % plate_index
    matches = [name for name in os.listdir(DATA_DIR) if name.lower().endswith(".csv") and token in name]
    if not matches:
        raise RuntimeError("Cannot find CSV for plate %02d in %s" % (plate_index, DATA_DIR))
    path = os.path.join(DATA_DIR, sorted(matches)[0])
    with open(path, "rb") as f:
        text = f.read()
    if text.startswith(b"\xef\xbb\xbf"):
        text = text[3:]
    rows = list(csv.DictReader(text.decode("utf-8").splitlines()))
    grid = np.zeros((RAW_NY, RAW_NX), dtype=float)
    for k, row in enumerate(rows):
        j = k // RAW_NX
        i = k % RAW_NX
        grid[j, i] = float(row["z_mm"]) / 1000.0
    return grid


def interpolate_z(grid, x_m, y_m):
    fx = (x_m / LENGTH_M + 0.5) * (RAW_NX - 1)
    fy = (y_m / WIDTH_M + 0.5) * (RAW_NY - 1)
    i0 = max(0, min(RAW_NX - 2, int(math.floor(fx))))
    j0 = max(0, min(RAW_NY - 2, int(math.floor(fy))))
    u = fx - i0
    v = fy - j0
    a = grid[j0, i0]
    b = grid[j0, i0 + 1]
    c = grid[j0 + 1, i0]
    d = grid[j0 + 1, i0 + 1]
    if u + v <= 1.0:
        return a + u * (b - a) + v * (c - a)
    return b * (1.0 - v) + c * (1.0 - u) + d * (u + v - 1.0)


def sample_plate(grid):
    xs = -LENGTH_M * 0.5 + (np.arange(NX) + 0.5) * (LENGTH_M / NX)
    ys = -WIDTH_M * 0.5 + (np.arange(NY) + 0.5) * (WIDTH_M / NY)
    out = np.zeros((NY, NX), dtype=float)
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            out[j, i] = interpolate_z(grid, float(x), float(y))
    return out


def gaussian_kernel(sigma):
    radius = max(1, int(math.ceil(3.0 * sigma)))
    ys, xs = np.mgrid[-radius:radius + 1, -radius:radius + 1]
    kernel = np.exp(-(xs ** 2 + ys ** 2) / (2.0 * sigma ** 2))
    kernel /= np.sum(kernel)
    return kernel


def convolve_edge(values, kernel):
    ky, kx = kernel.shape
    ry = ky // 2
    rx = kx // 2
    padded = np.pad(values, ((ry, ry), (rx, rx)), mode="edge")
    out = np.zeros_like(values, dtype=float)
    for j in range(values.shape[0]):
        for i in range(values.shape[1]):
            out[j, i] = float(np.sum(padded[j:j + ky, i:i + kx] * kernel))
    return out


def interface_mismatch(upper, lower, kernel):
    diff = upper - lower
    diff = diff - np.mean(diff)
    mismatch_um = np.abs(diff) * 1.0e6
    spread = convolve_edge(mismatch_um, kernel)
    return mismatch_um, spread


def interface_pressure(upper, lower, kernel, global_scale_um):
    mismatch_um, spread = interface_mismatch(upper, lower, kernel)
    normalized = (spread / global_scale_um) ** POWER
    pressure = TARGET_MEAN_MPA * (1.0 + ALPHA * normalized)
    pressure *= TARGET_MEAN_MPA / np.mean(pressure)
    return pressure, mismatch_um, spread


def gini(values):
    x = np.asarray(values, dtype=float).ravel()
    x = np.maximum(x[np.isfinite(x)], 0.0)
    if x.size == 0:
        return np.nan
    if np.allclose(x, 0.0):
        return 0.0
    x = np.sort(x)
    n = x.size
    return float((2.0 * np.sum(np.arange(1, n + 1) * x) / (n * np.sum(x))) - (n + 1.0) / n)


def metrics(panel):
    v = np.asarray(panel, dtype=float).ravel()
    mean = float(np.mean(v))
    std = float(np.std(v))
    peak = float(np.max(v))
    p95 = float(np.percentile(v, 95))
    top = v[v >= float(np.percentile(v, 80))]
    return {
        "mean_mpa": mean,
        "std_mpa": std,
        "cv": std / mean if mean > 0.0 else np.nan,
        "peak_mpa": peak,
        "peak_to_mean": peak / mean if mean > 0.0 else np.nan,
        "p95_to_mean": p95 / mean if mean > 0.0 else np.nan,
        "gini": gini(v),
        "top20_load_share": float(np.sum(top) / np.sum(v)) if np.sum(v) > 0.0 else np.nan,
    }


def write_case_panels(case, panels):
    cols = 4
    rows = 4
    fig, axes = plt.subplots(rows, cols, figsize=(14, 9), dpi=170)
    axes = axes.ravel()
    vmax = max(float(np.max(p)) for p in panels)
    for idx, ax in enumerate(axes):
        ax.axis("off")
        if idx >= len(panels):
            continue
        upper = case["order"][idx]
        lower = case["order"][idx + 1]
        im = ax.imshow(panels[idx], cmap="YlOrRd", vmin=0.0, vmax=vmax, aspect="auto")
        m = metrics(panels[idx])
        ax.set_title("#%d P%d/P%d\nCV %.3f  peak/mean %.2f" % (idx + 1, upper, lower, m["cv"], m["peak_to_mean"]), fontsize=8)
        ax.set_xticks([])
        ax.set_yticks([])
    cbar = fig.colorbar(im, ax=axes.tolist(), fraction=0.025, pad=0.01)
    cbar.set_label("Equivalent pressure / MPa")
    fig.suptitle("%s - equivalent compliant-layer pressure" % case["label"])
    fig.savefig(os.path.join(OUTPUT_DIR, "exp8_%s_pressure_panels.png" % case["case"]))
    plt.close(fig)


def main():
    ensure_dir(OUTPUT_DIR)
    kernel = gaussian_kernel(SIGMA_CELLS)
    sampled = {p: sample_plate(read_plate_grid(p)) for p in range(1, 16)}

    all_spread_means = []
    for i in range(1, 16):
        for j in range(1, 16):
            if i == j:
                continue
            _mismatch, spread = interface_mismatch(sampled[i], sampled[j], kernel)
            all_spread_means.append(float(np.mean(spread)))
    global_scale_um = float(np.mean(all_spread_means))

    rows = []
    summary = []
    series_by_case = {}
    panels_by_case = {}

    for case in CASES:
        panels = []
        series = []
        for idx in range(len(case["order"]) - 1):
            upper_no = case["order"][idx]
            lower_no = case["order"][idx + 1]
            pressure, mismatch_um, spread_um = interface_pressure(sampled[upper_no], sampled[lower_no], kernel, global_scale_um)
            panels.append(pressure)
            m = metrics(pressure)
            row = {
                "case": case["case"],
                "case_label": case["label"],
                "interface_index": idx + 1,
                "interface_label": "P%d/P%d" % (upper_no, lower_no),
                "mismatch_mean_um": float(np.mean(mismatch_um)),
                "mismatch_p95_um": float(np.percentile(mismatch_um, 95)),
                "spread_mismatch_mean_um": float(np.mean(spread_um)),
                "spread_mismatch_p95_um": float(np.percentile(spread_um, 95)),
            }
            row.update(m)
            rows.append(row)
            series.append(m)
        panels_by_case[case["case"]] = panels
        series_by_case[case["case"]] = series
        write_case_panels(case, panels)

        item = {"case": case["case"], "case_label": case["label"]}
        for key in ("cv", "peak_to_mean", "p95_to_mean", "gini", "top20_load_share"):
            values = np.array([m[key] for m in series], dtype=float)
            item[key + "_mean"] = float(np.nanmean(values))
            item[key + "_max"] = float(np.nanmax(values))
        summary.append(item)

    by_interface = os.path.join(OUTPUT_DIR, "exp8_equivalent_compliance_uniformity_by_interface.csv")
    with open(by_interface, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary_csv = os.path.join(OUTPUT_DIR, "exp8_equivalent_compliance_uniformity_summary.csv")
    with open(summary_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)

    metrics_to_plot = ["cv", "peak_to_mean", "p95_to_mean", "gini", "top20_load_share"]
    fig, axes = plt.subplots(len(metrics_to_plot), 1, figsize=(13, 13), dpi=170, sharex=True)
    x = np.arange(1, 15)
    for ax, key in zip(axes, metrics_to_plot):
        for case in CASES:
            ax.plot(x, [m[key] for m in series_by_case[case["case"]]], marker="o", linewidth=1.8, label=case["label"])
        ax.set_ylabel(key)
        ax.grid(True, axis="y", alpha=0.25)
        ax.legend(loc="best")
    axes[-1].set_xlabel("Internal interface index")
    fig.suptitle("Experiment 8 equivalent compliant-layer uniformity comparison")
    fig.tight_layout()
    comparison_png = os.path.join(OUTPUT_DIR, "exp8_equivalent_compliance_uniformity_comparison.png")
    fig.savefig(comparison_png)
    plt.close(fig)

    print("wrote", by_interface)
    print("wrote", summary_csv)
    print("wrote", comparison_png)
    for item in summary:
        print(item)


if __name__ == "__main__":
    main()
