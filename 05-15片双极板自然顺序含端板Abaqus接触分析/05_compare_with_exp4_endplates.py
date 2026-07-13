# -*- coding: utf-8 -*-
import csv
import os

import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EXPERIMENT_DIR = os.path.abspath(os.path.join(HERE, os.pardir))
ROOT = os.path.abspath(os.path.join(EXPERIMENT_DIR, os.pardir))
OUT_DIR = os.path.join(EXPERIMENT_DIR, "outputs")

CASES = [
    {
        "case": "min_distance_sum_with_endplates",
        "label": "Min-distance-sum + endplates",
        "folder": "4-15片双极板最小距离和顺序含端板Abaqus接触分析",
        "job": "exp4_stack15_min_with_endplates",
        "order": [1, 10, 9, 7, 11, 8, 12, 4, 14, 3, 5, 13, 15, 6, 2],
    },
    {
        "case": "natural_with_endplates",
        "label": "Natural order + endplates",
        "folder": "5-15片双极板自然顺序含端板Abaqus接触分析",
        "job": "exp5_stack15_natural_rigid_endplates",
        "order": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
    },
]

NX_NODES = 17
NY_NODES = 9


def node_grid_to_cell_grid(node_grid):
    return 0.25 * (
        node_grid[:-1, :-1] + node_grid[:-1, 1:] +
        node_grid[1:, :-1] + node_grid[1:, 1:]
    )


def read_case_panels(case):
    path = os.path.join(ROOT, case["folder"], "outputs", case["job"] + "_cpress_nodes.csv")
    data = {}
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            idx = int(row["interface_index"])
            if idx not in data:
                data[idx] = np.zeros((NY_NODES, NX_NODES), dtype=float)
            data[idx][int(row["iy"]), int(row["ix"])] = float(row["cpress_pa"]) / 1.0e6

    panels = []
    for idx in range(1, len(case["order"])):
        panels.append(node_grid_to_cell_grid(data[idx]))
    return panels


def gini(values):
    x = np.asarray(values, dtype=float).ravel()
    x = x[np.isfinite(x)]
    if x.size == 0:
        return np.nan
    x = np.maximum(x, 0.0)
    if np.allclose(x, 0.0):
        return 0.0
    x = np.sort(x)
    n = x.size
    return float((2.0 * np.sum(np.arange(1, n + 1) * x) / (n * np.sum(x))) - (n + 1.0) / n)


def metrics_for_panel(panel):
    v = np.asarray(panel, dtype=float).ravel()
    v = v[np.isfinite(v)]
    mean = float(np.mean(v))
    std = float(np.std(v))
    peak = float(np.max(v))
    p95 = float(np.percentile(v, 95))
    thresh = float(np.percentile(v, 80))
    top = v[v >= thresh]
    total = float(np.sum(v))
    return {
        "mean_mpa": mean,
        "std_mpa": std,
        "cv": std / mean if mean > 0.0 else np.nan,
        "peak_mpa": peak,
        "peak_to_mean": peak / mean if mean > 0.0 else np.nan,
        "p95_mpa": p95,
        "p95_to_mean": p95 / mean if mean > 0.0 else np.nan,
        "gini": gini(v),
        "top20_load_share": float(np.sum(top) / total) if total > 0.0 else np.nan,
    }


def main():
    rows = []
    summary = []
    series_by_case = {}

    for case in CASES:
        panels = read_case_panels(case)
        series = []
        for idx, panel in enumerate(panels, start=1):
            metrics = metrics_for_panel(panel)
            label = "P%d/P%d" % (case["order"][idx - 1], case["order"][idx])
            row = {
                "case": case["case"],
                "case_label": case["label"],
                "interface_index": idx,
                "interface_label": label,
            }
            row.update(metrics)
            rows.append(row)
            series.append(metrics)
        series_by_case[case["case"]] = series

        avg = {"case": case["case"], "case_label": case["label"]}
        for key in ("cv", "peak_to_mean", "p95_to_mean", "gini", "top20_load_share"):
            values = np.array([item[key] for item in series], dtype=float)
            avg[key + "_mean"] = float(np.nanmean(values))
            avg[key + "_max"] = float(np.nanmax(values))
        summary.append(avg)

    by_interface = os.path.join(OUT_DIR, "exp5_vs_exp4_endplate_uniformity_by_interface.csv")
    with open(by_interface, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary_csv = os.path.join(OUT_DIR, "exp5_vs_exp4_endplate_uniformity_summary.csv")
    with open(summary_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)

    metrics = ["cv", "peak_to_mean", "p95_to_mean", "gini", "top20_load_share"]
    fig, axes = plt.subplots(len(metrics), 1, figsize=(13, 13), dpi=170, sharex=True)
    x = np.arange(1, 15)
    for ax, key in zip(axes, metrics):
        for case in CASES:
            y = [item[key] for item in series_by_case[case["case"]]]
            ax.plot(x, y, marker="o", linewidth=1.8, label=case["label"])
        ax.set_ylabel(key)
        ax.grid(True, axis="y", alpha=0.25)
        ax.legend(loc="best")
    axes[-1].set_xlabel("Internal bipolar-plate interface index")
    fig.suptitle("Abaqus CPRESS uniformity comparison with endplates")
    fig.tight_layout()
    comparison_png = os.path.join(OUT_DIR, "exp5_vs_exp4_endplate_uniformity_comparison.png")
    fig.savefig(comparison_png)
    plt.close(fig)

    print("wrote", by_interface)
    print("wrote", summary_csv)
    print("wrote", comparison_png)
    for item in summary:
        print(item)


if __name__ == "__main__":
    main()

