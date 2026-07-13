# -*- coding: utf-8 -*-
import csv
import os

import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.abspath(os.path.join(HERE, os.pardir, "outputs"))
DISP_M = 1.0e-3
CELL_AREA_M2 = 0.820 * 0.345 / float(16 * 8)
NX = 16
NY = 8

CASES = [
    ("min_distance_sum", "Min-distance-sum", "exp10_min_spring_layer", [1, 10, 9, 7, 11, 8, 12, 4, 14, 3, 5, 13, 15, 6, 2]),
    ("natural", "Natural", "exp10_natural_spring_layer", list(range(1, 16))),
    ("max_distance_sum", "Max-distance-sum", "exp10_max_spring_layer", [11, 12, 13, 7, 14, 9, 5, 6, 8, 15, 3, 1, 2, 10, 4]),
]


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
        "cv": std / mean if mean > 0 else np.nan,
        "peak_mpa": peak,
        "peak_to_mean": peak / mean if mean > 0 else np.nan,
        "p95_to_mean": p95 / mean if mean > 0 else np.nan,
        "gini": gini(v),
        "top20_load_share": float(np.sum(top) / np.sum(v)) if np.sum(v) > 0 else np.nan,
    }


def read_panels(job):
    path = os.path.join(OUT_DIR, job + "_spring_map.csv")
    panels = {}
    rows = []
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            idx = int(row["interface_index"])
            if idx not in panels:
                panels[idx] = np.zeros((NY, NX), dtype=float)
            iy = int(row["iy"])
            ix = int(row["ix"])
            pressure_mpa = float(row["spring_k_n_per_m"]) * DISP_M / CELL_AREA_M2 / 1.0e6
            panels[idx][iy, ix] = pressure_mpa
            row = dict(row)
            row["pressure_mpa"] = pressure_mpa
            rows.append(row)
    return [panels[i] for i in sorted(panels)], rows


def draw_case(case_name, label, job, order, panels):
    fig, axes = plt.subplots(4, 4, figsize=(14, 9), dpi=170)
    axes = axes.ravel()
    vmax = max(float(np.max(p)) for p in panels)
    for i, ax in enumerate(axes):
        ax.axis("off")
        if i >= len(panels):
            continue
        im = ax.imshow(panels[i], cmap="YlOrRd", vmin=0.0, vmax=vmax, aspect="auto")
        m = metrics(panels[i])
        ax.set_title("#%d P%d/P%d\nCV %.3f peak/mean %.2f" % (
            i + 1, order[i], order[i + 1], m["cv"], m["peak_to_mean"]
        ), fontsize=8)
    cbar = fig.colorbar(im, ax=axes.tolist(), fraction=0.025, pad=0.01)
    cbar.set_label("Equivalent spring pressure / MPa")
    fig.suptitle("Experiment 10 Abaqus spring-layer pressure - %s" % label)
    fig.savefig(os.path.join(OUT_DIR, job + "_pressure_panels.png"))
    plt.close(fig)


def main():
    all_node_rows = []
    metric_rows = []
    summary = []
    series_by_case = {}
    for case_name, label, job, order in CASES:
        panels, node_rows = read_panels(job)
        draw_case(case_name, label, job, order, panels)
        all_node_rows.extend(node_rows)
        series = []
        for i, panel in enumerate(panels, start=1):
            m = metrics(panel)
            row = {
                "case": case_name,
                "case_label": label,
                "job": job,
                "interface_index": i,
                "interface_label": "P%d/P%d" % (order[i - 1], order[i]),
            }
            row.update(m)
            metric_rows.append(row)
            series.append(m)
        series_by_case[case_name] = series
        item = {"case": case_name, "case_label": label}
        for key in ("cv", "peak_to_mean", "p95_to_mean", "gini", "top20_load_share"):
            values = np.array([m[key] for m in series], dtype=float)
            item[key + "_mean"] = float(np.nanmean(values))
            item[key + "_max"] = float(np.nanmax(values))
        summary.append(item)

    with open(os.path.join(OUT_DIR, "exp10_spring_layer_pressure_nodes.csv"), "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_node_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_node_rows)

    with open(os.path.join(OUT_DIR, "exp10_spring_layer_uniformity_by_interface.csv"), "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(metric_rows[0].keys()))
        writer.writeheader()
        writer.writerows(metric_rows)

    summary_csv = os.path.join(OUT_DIR, "exp10_spring_layer_uniformity_summary.csv")
    with open(summary_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)

    keys = ["cv", "peak_to_mean", "p95_to_mean", "gini", "top20_load_share"]
    fig, axes = plt.subplots(len(keys), 1, figsize=(13, 13), dpi=170, sharex=True)
    x = np.arange(1, 15)
    for ax, key in zip(axes, keys):
        for case_name, label, _job, _order in CASES:
            ax.plot(x, [m[key] for m in series_by_case[case_name]], marker="o", label=label)
        ax.set_ylabel(key)
        ax.grid(True, axis="y", alpha=0.25)
        ax.legend(loc="best")
    axes[-1].set_xlabel("Internal interface index")
    fig.suptitle("Experiment 10 Abaqus equivalent spring-layer uniformity")
    fig.tight_layout()
    comparison_png = os.path.join(OUT_DIR, "exp10_spring_layer_uniformity_comparison.png")
    fig.savefig(comparison_png)
    plt.close(fig)

    print("wrote", summary_csv)
    print("wrote", comparison_png)
    for item in summary:
        print(item)


if __name__ == "__main__":
    main()
