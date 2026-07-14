# -*- coding: utf-8 -*-
from __future__ import print_function

import csv
import json
import os

import matplotlib.pyplot as plt
import numpy as np

import config as cfg


HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.abspath(os.path.join(HERE, os.pardir, "outputs"))
CASES = ("min", "natural", "max")
LABELS = {"min": "Exact min", "natural": "Natural", "max": "Exact max"}
NX = cfg.GRID_CELLS_X + 1
NY = cfg.GRID_CELLS_Y + 1
TARGET_MPA = cfg.NOMINAL_PRESSURE_PA / 1.0e6


def job_name(case):
    return "exp%d_%s_%dplates" % (cfg.EXPERIMENT_ID, case, cfg.PLATE_COUNT)


def gini(values):
    values = np.maximum(np.asarray(values, dtype=float).ravel(), 0.0)
    if values.size == 0 or np.allclose(values, 0.0):
        return 0.0
    values = np.sort(values)
    count = values.size
    return float(2.0 * np.sum(np.arange(1, count + 1) * values) / (count * np.sum(values)) - (count + 1.0) / count)


def node_to_cell(grid):
    return 0.25 * (grid[:-1, :-1] + grid[:-1, 1:] + grid[1:, :-1] + grid[1:, 1:])


def load_pressure(case):
    path = os.path.join(OUTPUT_DIR, job_name(case) + "_cpress_nodes.csv")
    panels = {}
    all_node_values = []
    with open(path, "r", newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            index = int(row["interface_index"])
            panels.setdefault(index, np.zeros((NY, NX), dtype=float))
            value = max(0.0, float(row["cpress_pa"]) / 1.0e6)
            panels[index][int(row["iy"]), int(row["ix"])] = value
            all_node_values.append(value)
    cells = np.concatenate([node_to_cell(panels[index]).ravel() for index in sorted(panels)])
    return cells, np.asarray(all_node_values, dtype=float)


def read_one_row(path):
    with open(path, "r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))[-1]


def summarize(case):
    cells, nodes = load_pressure(case)
    mean = float(np.mean(cells))
    std = float(np.std(cells))
    p95 = float(np.percentile(cells, 95))
    peak = float(np.max(cells))
    cutoff = float(np.percentile(cells, 80))
    energy = read_one_row(os.path.join(OUTPUT_DIR, job_name(case) + "_energy_history.csv"))
    deformation = read_one_row(os.path.join(OUTPUT_DIR, job_name(case) + "_deformation_summary.csv"))
    return {
        "case": case,
        "label": LABELS[case],
        "plate_count": cfg.PLATE_COUNT,
        "cell_mean_mpa": mean,
        "cv": std / mean if mean > 0 else float("nan"),
        "p95_to_mean": p95 / mean if mean > 0 else float("nan"),
        "peak_to_mean": peak / mean if mean > 0 else float("nan"),
        "gini": gini(cells),
        "top20_load_share": float(np.sum(cells[cells >= cutoff]) / np.sum(cells)),
        "target_rmse_mpa": float(np.sqrt(np.mean((cells - TARGET_MPA) ** 2))),
        "positive_node_coverage": float(np.mean(nodes > 1.0e-6)),
        "absolute_peak_mpa": float(np.max(nodes)),
        "stack_shortening_mm": 1000.0 * float(deformation["stack_shortening_m"]),
        "mean_plate_warpage_u3_rms_mm": 1000.0 * float(deformation["mean_plate_warpage_u3_rms_m"]),
        "max_plate_warpage_u3_rms_mm": 1000.0 * float(deformation["max_plate_warpage_u3_rms_m"]),
        "mean_plate_warpage_u3_peak_to_peak_mm": 1000.0 * float(deformation["mean_plate_warpage_u3_peak_to_peak_m"]),
        "max_plate_warpage_u3_peak_to_peak_mm": 1000.0 * float(deformation["max_plate_warpage_u3_peak_to_peak_m"]),
        "mean_plate_deformation_3d_rms_mm": 1000.0 * float(deformation["mean_plate_deformation_3d_rms_m"]),
        "max_plate_nodal_umag_mm": 1000.0 * float(deformation["max_plate_nodal_umag_m"]),
        "ke_to_ie": float(energy["ke_to_ie"]),
        "ae_to_ie": float(energy["ae_to_ie"]),
    }


def main():
    rows = [summarize(case) for case in CASES]
    summary_path = os.path.join(OUTPUT_DIR, "exp%d_pressure_deformation_summary.csv" % cfg.EXPERIMENT_ID)
    with open(summary_path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    pressure_metrics = ("cv", "p95_to_mean", "gini", "top20_load_share", "positive_node_coverage")
    deformation_metrics = (
        "stack_shortening_mm",
        "mean_plate_warpage_u3_rms_mm",
        "max_plate_warpage_u3_rms_mm",
        "mean_plate_warpage_u3_peak_to_peak_mm",
        "max_plate_warpage_u3_peak_to_peak_mm",
    )
    colors = ("#2171b5", "#f28e2b", "#4e9f3d")
    for group, metrics in (("pressure", pressure_metrics), ("deformation", deformation_metrics)):
        fig, axes = plt.subplots(2, 3, figsize=(13, 7), dpi=170)
        for axis, metric in zip(axes.ravel(), metrics):
            axis.bar([LABELS[case] for case in CASES], [row[metric] for row in rows], color=colors)
            axis.set_title(metric)
            axis.grid(axis="y", alpha=0.25)
            axis.tick_params(axis="x", rotation=12)
        for axis in axes.ravel()[len(metrics):]:
            axis.axis("off")
        fig.suptitle("Experiment %d - %d plates - %s comparison" % (cfg.EXPERIMENT_ID, cfg.PLATE_COUNT, group))
        fig.tight_layout()
        fig.savefig(os.path.join(OUTPUT_DIR, "exp%d_%s_comparison.png" % (cfg.EXPERIMENT_ID, group)))
        plt.close(fig)
    print("wrote", summary_path)
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
