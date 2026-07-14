# -*- coding: utf-8 -*-
from __future__ import print_function

import csv
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


def job_name(case):
    return "exp%d_%s_%dplates" % (cfg.EXPERIMENT_ID, case, cfg.PLATE_COUNT)


def load_case(case):
    grids = {}
    plate_numbers = {}
    path = os.path.join(OUTPUT_DIR, job_name(case) + "_displacement_nodes.csv")
    with open(path, "r", newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            stack = int(row["stack_index"])
            grids.setdefault(stack, np.zeros((NY, NX), dtype=float))
            grids[stack][int(row["iy"]), int(row["ix"])] = 1000.0 * float(row["u3_m"])
            plate_numbers[stack] = int(row["plate_no"])
    centered = {stack: grid - np.mean(grid) for stack, grid in grids.items()}
    return centered, plate_numbers


def load_plate_summary(case):
    path = os.path.join(OUTPUT_DIR, job_name(case) + "_displacement_plate_summary.csv")
    with open(path, "r", newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    return {
        "rms": np.asarray([1000.0 * float(row["warpage_u3_rms_m"]) for row in rows]),
        "ptp": np.asarray([1000.0 * float(row["warpage_u3_peak_to_peak_m"]) for row in rows]),
    }


def main():
    loaded = {case: load_case(case) for case in CASES}
    all_values = np.concatenate([
        grid.ravel()
        for case in CASES
        for grid in loaded[case][0].values()
    ])
    limit = float(np.percentile(np.abs(all_values), 99.0))
    for case in CASES:
        grids, plate_numbers = loaded[case]
        fig, axes = plt.subplots(4, 6, figsize=(15, 8.2), dpi=170)
        image = None
        for stack, axis in enumerate(axes.ravel(), start=1):
            grid = grids[stack]
            image = axis.imshow(grid, cmap="coolwarm", vmin=-limit, vmax=limit, origin="lower", aspect="auto")
            axis.set_title("S%02d / P%02d" % (stack, plate_numbers[stack]), fontsize=8)
            axis.set_xticks([])
            axis.set_yticks([])
        fig.suptitle("Experiment %d - %s - centered U3 deformation (mm)" % (cfg.EXPERIMENT_ID, LABELS[case]))
        fig.subplots_adjust(left=0.035, right=0.91, bottom=0.04, top=0.92, wspace=0.16, hspace=0.35)
        color_axis = fig.add_axes([0.93, 0.10, 0.015, 0.78])
        fig.colorbar(image, cax=color_axis, label="U3 minus plate mean (mm)")
        fig.savefig(os.path.join(OUTPUT_DIR, "exp%d_deformation_u3_maps_%s.png" % (cfg.EXPERIMENT_ID, case)))
        plt.close(fig)

    summaries = {case: load_plate_summary(case) for case in CASES}
    x = np.arange(1, cfg.PLATE_COUNT + 1)
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), dpi=170, sharex=True)
    colors = {"min": "#2171b5", "natural": "#f28e2b", "max": "#4e9f3d"}
    for case in CASES:
        axes[0].plot(x, summaries[case]["rms"], marker="o", markersize=3, label=LABELS[case], color=colors[case])
        axes[1].plot(x, summaries[case]["ptp"], marker="o", markersize=3, label=LABELS[case], color=colors[case])
    axes[0].set_ylabel("Centered U3 RMS (mm)")
    axes[1].set_ylabel("Centered U3 peak-to-peak (mm)")
    axes[1].set_xlabel("Stack position (top to bottom)")
    axes[1].set_xticks(x)
    for axis in axes:
        axis.grid(alpha=0.25)
        axis.legend()
    fig.suptitle("Experiment %d - plate deformation along stack" % cfg.EXPERIMENT_ID)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "exp%d_deformation_along_stack.png" % cfg.EXPERIMENT_ID))
    plt.close(fig)
    print("wrote deformation maps and stack profile")


if __name__ == "__main__":
    main()
