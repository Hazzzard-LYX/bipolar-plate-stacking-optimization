# -*- coding: utf-8 -*-
import csv
import os

import matplotlib.pyplot as plt
import numpy as np

ROOT = r"D:\双极板堆叠有限元分析\Abaqus有限元分析"
CASES = [
    {
        "case": "min_distance_sum",
        "label": "Min-distance-sum order",
        "folder": "2-15片双极板堆叠Abaqus接触分析",
        "job": "exp2_stack15_ordered_contact",
        "order": [1, 10, 9, 7, 11, 8, 12, 4, 14, 3, 5, 13, 15, 6, 2],
    },
    {
        "case": "natural",
        "label": "Natural order",
        "folder": "3-15片双极板自然顺序Abaqus接触分析",
        "job": "exp3_stack15_natural_contact",
        "order": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
    },
]
OUT_DIR = os.path.join(ROOT, "3-15片双极板自然顺序Abaqus接触分析", "outputs")
NX_NODES = 17
NY_NODES = 9
NX = 16
NY = 8


def node_grid_to_cell_grid(node_grid):
    return 0.25 * (
        node_grid[:-1, :-1] + node_grid[:-1, 1:] +
        node_grid[1:, :-1] + node_grid[1:, 1:]
    )


def read_case_panels(case):
    path = os.path.join(ROOT, case["folder"], "outputs", case["job"] + "_cpress_nodes.csv")
    data = {}
    with open(path, "r", newline="") as f:
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


def gini(x):
    x = np.asarray(x, dtype=float).ravel()
    x = x[np.isfinite(x)]
    if x.size == 0:
        return np.nan
    if np.allclose(x, 0.0):
        return 0.0
    x = np.sort(np.maximum(x, 0.0))
    n = x.size
    return float((2.0 * np.sum((np.arange(1, n + 1)) * x) / (n * np.sum(x))) - (n + 1.0) / n)


def metrics_for_panel(values):
    v = np.asarray(values, dtype=float).ravel()
    v = v[np.isfinite(v)]
    mean = float(np.mean(v))
    std = float(np.std(v))
    peak = float(np.max(v))
    p95 = float(np.percentile(v, 95))
    thresh = float(np.percentile(v, 80))
    top = v[v >= thresh]
    return {
        "mean_mpa": mean,
        "std_mpa": std,
        "cv": std / mean if mean > 0 else np.nan,
        "peak_mpa": peak,
        "peak_to_mean": peak / mean if mean > 0 else np.nan,
        "p95_mpa": p95,
        "p95_to_mean": p95 / mean if mean > 0 else np.nan,
        "gini": gini(v),
        "top20_load_share": float(np.sum(top) / np.sum(v)) if np.sum(v) > 0 else np.nan,
    }


def main():
    rows = []
    summary = []
    case_metric_series = {}
    for case in CASES:
        panels = read_case_panels(case)
        series = []
        for i, panel in enumerate(panels, start=1):
            m = metrics_for_panel(panel)
            label = "P%d/P%d" % (case["order"][i - 1], case["order"][i])
            row = {"case": case["case"], "case_label": case["label"], "interface_index": i, "interface_label": label}
            row.update(m)
            rows.append(row)
            series.append(m)
        case_metric_series[case["case"]] = series
        avg = {"case": case["case"], "case_label": case["label"]}
        for key in ("cv", "peak_to_mean", "p95_to_mean", "gini", "top20_load_share"):
            avg[key + "_mean"] = float(np.mean([m[key] for m in series]))
            avg[key + "_max"] = float(np.max([m[key] for m in series]))
        summary.append(avg)

    out_csv = os.path.join(OUT_DIR, "exp3_vs_exp2_abaqus_uniformity_by_interface.csv")
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    out_sum = os.path.join(OUT_DIR, "exp3_vs_exp2_abaqus_uniformity_summary.csv")
    with open(out_sum, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)

    metrics = ["cv", "peak_to_mean", "p95_to_mean", "gini", "top20_load_share"]
    fig, axes = plt.subplots(len(metrics), 1, figsize=(13, 13), dpi=170, sharex=True)
    x = np.arange(1, 15)
    for ax, key in zip(axes, metrics):
        for case in CASES:
            y = [m[key] for m in case_metric_series[case["case"]]]
            ax.plot(x, y, marker="o", label=case["label"])
        ax.set_ylabel(key)
        ax.grid(True, axis="y", alpha=0.25)
        ax.legend(loc="best")
    axes[-1].set_xlabel("Bipolar-plate interface index (14 internal interfaces)")
    fig.suptitle("Abaqus CPRESS uniformity comparison: natural order vs min-distance-sum order")
    fig.tight_layout()
    out_png = os.path.join(OUT_DIR, "exp3_vs_exp2_abaqus_uniformity_comparison.png")
    fig.savefig(out_png)
    plt.close(fig)

    print("wrote", out_csv)
    print("wrote", out_sum)
    print("wrote", out_png)
    for item in summary:
        print(item)


if __name__ == "__main__":
    main()
