# -*- coding: utf-8 -*-
from __future__ import print_function

import csv
import math
import os


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXP39_DIR = os.path.dirname(SCRIPT_DIR)
ANALYSIS_ROOT = os.path.dirname(EXP39_DIR)
EXP38_DIR = os.path.join(
    ANALYSIS_ROOT,
    "38-15片真实双极板实验34精确序列260kN玻纤端板Abaqus实验",
)
OLD_CSV = os.path.join(EXP38_DIR, "outputs", "exp38_uniformity_summary_t1p9.csv")
NEW_CSV = os.path.join(EXP39_DIR, "outputs", "exp39_uniformity_summary_t1p9.csv")
OUTPUT_CSV = os.path.join(EXP39_DIR, "outputs", "exp38_vs_exp39_endplate_comparison.csv")

METRICS = (
    "cell_mean_mpa", "cv", "p95_to_mean", "peak_to_mean", "gini",
    "top20_load_share", "target_rmse_mpa", "positive_node_coverage",
    "absolute_peak_mpa", "ke_to_ie", "ae_to_ie", "top_endplate_u3_range_mm",
    "top_endplate_max_abs_u3_mm", "top_endplate_max_mises_mpa",
    "bottom_endplate_max_mises_mpa", "bottom_reaction_z_kn",
)


def read_by_case(path):
    with open(path, "r", encoding="utf-8-sig") as handle:
        return {row["case"]: row for row in csv.DictReader(handle)}


def relative_difference(old, difference):
    if not math.isfinite(old) or not math.isfinite(difference) or old == 0.0:
        return float("nan")
    return difference / old * 100.0


def main():
    exp38 = read_by_case(OLD_CSV)
    exp39 = read_by_case(NEW_CSV)
    rows = []
    for case in ("min", "natural", "max"):
        for metric in METRICS:
            old = float(exp38[case][metric])
            new = float(exp39[case][metric])
            difference = new - old
            rows.append({
                "case": case,
                "metric": metric,
                "exp38_deformable_gfrp": old,
                "exp39_rigid": new,
                "difference": difference,
                "relative_difference_percent": relative_difference(old, difference),
            })
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print("Wrote: {}".format(OUTPUT_CSV))


if __name__ == "__main__":
    main()
