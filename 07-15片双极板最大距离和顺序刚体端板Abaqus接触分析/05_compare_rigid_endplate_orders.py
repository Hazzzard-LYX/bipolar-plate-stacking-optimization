# -*- coding: utf-8 -*-
import csv
import os

import matplotlib.pyplot as plt
import numpy as np

ROOT = r"D:\双极板堆叠有限元分析\Abaqus有限元分析"
OUT_DIR = os.path.join(ROOT, "7-15片双极板最大距离和顺序刚体端板Abaqus接触分析", "outputs")

CASES = [
    {
        "case": "natural",
        "label": "Natural order",
        "folder": "5-15片双极板自然顺序含端板Abaqus接触分析",
        "job": "exp5_stack15_natural_rigid_endplates",
        "order": list(range(1, 16)),
    },
    {
        "case": "min_distance_sum",
        "label": "Min-distance-sum order",
        "folder": "6-15片双极板最小距离和顺序刚体端板Abaqus接触分析",
        "job": "exp6_stack15_min_rigid_endplates",
        "order": [1, 10, 9, 7, 11, 8, 12, 4, 14, 3, 5, 13, 15, 6, 2],
    },
    {
        "case": "max_distance_sum",
        "label": "Max-distance-sum order",
        "folder": "7-15片双极板最大距离和顺序刚体端板Abaqus接触分析",
        "job": "exp7_stack15_max_rigid_endplates",
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
    path = os.path.join(ROOT, case["folder"], "outputs", case["job"] + "_cpress_nodes.csv")
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


def main():
    rows = []
    summary = []
    series_by_case = {}
    for case in CASES:
        series = []
        for i, panel in enumerate(read_panels(case), start=1):
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

    by_interface = os.path.join(OUT_DIR, "exp5_exp6_exp7_rigid_endplate_uniformity_by_interface.csv")
    with open(by_interface, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary_csv = os.path.join(OUT_DIR, "exp5_exp6_exp7_rigid_endplate_uniformity_summary.csv")
    with open(summary_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)

    metrics_to_plot = ["cv", "peak_to_mean", "p95_to_mean", "gini", "top20_load_share"]
    fig, axes = plt.subplots(len(metrics_to_plot), 1, figsize=(13, 13), dpi=170, sharex=True)
    x = np.arange(1, 15)
    for ax, key in zip(axes, metrics_to_plot):
        for case in CASES:
            ax.plot(x, [m[key] for m in series_by_case[case["case"]]], marker="o", label=case["label"])
        ax.set_ylabel(key)
        ax.grid(True, axis="y", alpha=0.25)
        ax.legend(loc="best")
    axes[-1].set_xlabel("Internal bipolar-plate interface index")
    fig.suptitle("Rigid-endplate CPRESS uniformity comparison")
    fig.tight_layout()
    png = os.path.join(OUT_DIR, "exp5_exp6_exp7_rigid_endplate_uniformity_comparison.png")
    fig.savefig(png)
    plt.close(fig)

    print("wrote", by_interface)
    print("wrote", summary_csv)
    print("wrote", png)
    for item in summary:
        print(item)


if __name__ == "__main__":
    main()
