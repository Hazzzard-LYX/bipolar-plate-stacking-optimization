# -*- coding: utf-8 -*-
import csv
import os

import matplotlib.pyplot as plt
import numpy as np


HERE = os.path.dirname(os.path.abspath(__file__))
EXP34_DIR = os.path.abspath(os.path.join(HERE, os.pardir))
ARCHIVE_DIR = os.path.abspath(os.path.join(EXP34_DIR, os.pardir))
OUT34 = os.path.join(EXP34_DIR, "outputs")


def find_exp28_output():
    for name in os.listdir(ARCHIVE_DIR):
        if name.startswith("28-"):
            path = os.path.join(ARCHIVE_DIR, name, "outputs")
            if os.path.isdir(path):
                return path
    raise RuntimeError("Cannot find experiment 28 outputs")


def read_summary(path):
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        return dict((row["case"], row) for row in csv.DictReader(f))


def main():
    out28 = find_exp28_output()
    old = read_summary(os.path.join(out28, "exp28_pressure0448_friction_uniformity_summary.csv"))
    exact = read_summary(os.path.join(OUT34, "exp34_exact_pressure0448_friction_uniformity_summary.csv"))
    metrics = ["cv_mean", "p95_to_mean_mean", "peak_to_mean_mean", "gini_mean", "top20_load_share_mean"]
    rows = []
    for case in ("min_distance_sum", "natural", "max_distance_sum"):
        for metric in metrics:
            old_value = float(old[case][metric])
            exact_value = float(exact[case][metric])
            rows.append({
                "case": case,
                "metric": metric,
                "heuristic_exp28": old_value,
                "exact_dp_exp34": exact_value,
                "exact_change_percent": 100.0 * (exact_value / old_value - 1.0),
            })

    csv_path = os.path.join(OUT34, "exp28_vs_exp34_exact_algorithm_comparison.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    fig, axes = plt.subplots(2, 3, figsize=(14, 8), dpi=170)
    axes = axes.ravel()
    labels = ["Heuristic min", "Exact min", "Natural", "Heuristic max", "Exact max"]
    for ax, metric in zip(axes, metrics):
        values = [
            float(old["min_distance_sum"][metric]),
            float(exact["min_distance_sum"][metric]),
            float(exact["natural"][metric]),
            float(old["max_distance_sum"][metric]),
            float(exact["max_distance_sum"][metric]),
        ]
        ax.bar(np.arange(len(values)), values, color=["#70a5d8", "#1f77b4", "#777777", "#e8a16a", "#d95f02"])
        ax.set_title(metric)
        ax.set_xticks(np.arange(len(values)))
        ax.set_xticklabels(labels, rotation=25, ha="right")
        ax.grid(True, axis="y", alpha=0.25)
    axes[-1].axis("off")
    fig.suptitle("Experiment 28 heuristic orders vs Experiment 34 exact-DP orders")
    fig.tight_layout()
    png_path = os.path.join(OUT34, "exp28_vs_exp34_exact_algorithm_comparison.png")
    fig.savefig(png_path)
    plt.close(fig)
    print("wrote", csv_path)
    print("wrote", png_path)


if __name__ == "__main__":
    main()
