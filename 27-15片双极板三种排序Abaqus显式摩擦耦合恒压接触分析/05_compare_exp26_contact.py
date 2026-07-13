# -*- coding: utf-8 -*-
import csv
import os

import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.abspath(os.path.join(HERE, os.pardir, "outputs"))

CASES = [
    {
        "case": "min_distance_sum",
        "label": "Min-distance-sum",
        "job": "exp26_min_explicit_s4_pressure0448_contact",
        "order": [1, 10, 9, 7, 11, 8, 12, 4, 14, 3, 5, 13, 15, 6, 2],
    },
    {
        "case": "natural",
        "label": "Natural",
        "job": "exp26_natural_explicit_s4_pressure0448_contact",
        "order": list(range(1, 16)),
    },
    {
        "case": "max_distance_sum",
        "label": "Max-distance-sum",
        "job": "exp26_max_explicit_s4_pressure0448_contact",
        "order": [11, 12, 13, 7, 14, 9, 5, 6, 8, 15, 3, 1, 2, 10, 4],
    },
]

NX_NODES = 17
NY_NODES = 9


def node_grid_to_cell_grid(node_grid):
    return 0.25 * (
        node_grid[:-1, :-1] + node_grid[:-1, 1:] +
        node_grid[1:, :-1] + node_grid[1:, 1:]
    )


def read_panels(case):
    path = os.path.join(OUT_DIR, case["job"] + "_cpress_nodes.csv")
    data = {}
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            idx = int(row["interface_index"])
            if idx not in data:
                data[idx] = np.zeros((NY_NODES, NX_NODES), dtype=float)
            data[idx][int(row["iy"]), int(row["ix"])] = float(row["cpress_pa"]) / 1.0e6
    return [node_grid_to_cell_grid(data[i]) for i in range(1, len(case["order"]))]


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
    v = v[np.isfinite(v)]
    mean = float(np.mean(v))
    std = float(np.std(v))
    peak = float(np.max(v))
    p95 = float(np.percentile(v, 95))
    top = v[v >= float(np.percentile(v, 80))]
    total = float(np.sum(v))
    return {
        "mean_mpa": mean,
        "std_mpa": std,
        "cv": std / mean if mean > 0 else np.nan,
        "peak_mpa": peak,
        "peak_to_mean": peak / mean if mean > 0 else np.nan,
        "p95_to_mean": p95 / mean if mean > 0 else np.nan,
        "gini": gini(v),
        "top20_load_share": float(np.sum(top) / total) if total > 0 else np.nan,
    }


def draw_case(case, panels):
    fig, axes = plt.subplots(4, 4, figsize=(14, 9), dpi=170)
    axes = axes.ravel()
    vmax = max(float(np.max(p)) for p in panels)
    for i, ax in enumerate(axes):
        ax.axis("off")
        if i >= len(panels):
            continue
        im = ax.imshow(panels[i], cmap="YlOrRd", vmin=0.0, vmax=vmax, aspect="auto")
        m = metrics(panels[i])
        ax.set_title("#%d P%d/P%d\nCV %.2f peak/mean %.1f" % (
            i + 1, case["order"][i], case["order"][i + 1], m["cv"], m["peak_to_mean"]
        ), fontsize=8)
    cbar = fig.colorbar(im, ax=axes.tolist(), fraction=0.025, pad=0.01)
    cbar.set_label("CPRESS / MPa")
    fig.suptitle("Experiment 26 Abaqus Explicit S4 CPRESS - %s" % case["label"])
    fig.savefig(os.path.join(OUT_DIR, case["job"] + "_pressure_panels.png"))
    plt.close(fig)


def main():
    rows = []
    summary = []
    series_by_case = {}
    for case in CASES:
        panels = read_panels(case)
        draw_case(case, panels)
        series = []
        for i, panel in enumerate(panels, start=1):
            m = metrics(panel)
            row = {
                "case": case["case"],
                "case_label": case["label"],
                "interface_index": i,
                "interface_label": "P%d/P%d" % (case["order"][i - 1], case["order"][i]),
            }
            row.update(m)
            rows.append(row)
            series.append(m)
        series_by_case[case["case"]] = series
        item = {"case": case["case"], "case_label": case["label"]}
        for key in ("cv", "peak_to_mean", "p95_to_mean", "gini", "top20_load_share"):
            values = np.array([m[key] for m in series], dtype=float)
            item[key + "_mean"] = float(np.nanmean(values))
            item[key + "_max"] = float(np.nanmax(values))
        summary.append(item)

    by_interface = os.path.join(OUT_DIR, "exp26_pressure0448_explicit_s4_uniformity_by_interface.csv")
    with open(by_interface, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary_csv = os.path.join(OUT_DIR, "exp26_pressure0448_explicit_s4_uniformity_summary.csv")
    with open(summary_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)

    keys = ["cv", "peak_to_mean", "p95_to_mean", "gini", "top20_load_share"]
    fig, axes = plt.subplots(len(keys), 1, figsize=(13, 13), dpi=170, sharex=True)
    x = np.arange(1, 15)
    for ax, key in zip(axes, keys):
        for case in CASES:
            ax.plot(x, [m[key] for m in series_by_case[case["case"]]], marker="o", label=case["label"])
        ax.set_ylabel(key)
        ax.grid(True, axis="y", alpha=0.25)
        ax.legend(loc="best")
    axes[-1].set_xlabel("Internal interface index")
    fig.suptitle("Experiment 26 Abaqus Explicit full-integration S4 uniformity comparison")
    fig.tight_layout()
    comparison_png = os.path.join(OUT_DIR, "exp26_pressure0448_explicit_s4_uniformity_comparison.png")
    fig.savefig(comparison_png)
    plt.close(fig)

    print("wrote", by_interface)
    print("wrote", summary_csv)
    print("wrote", comparison_png)
    for item in summary:
        print(item)


if __name__ == "__main__":
    main()






