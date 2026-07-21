from __future__ import print_function

import csv
import os


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXP37_DIR = os.path.dirname(SCRIPT_DIR)
ANALYSIS_ROOT = os.path.dirname(EXP37_DIR)
EXP36_DIR = os.path.join(
    ANALYSIS_ROOT,
    "36-15片真实双极板贪心三排序260kN玻纤端板Abaqus实验",
)

EXP36_CSV = os.path.join(EXP36_DIR, "outputs", "exp36_uniformity_summary_t1p9.csv")
EXP37_CSV = os.path.join(EXP37_DIR, "outputs", "exp37_uniformity_summary_t1p9.csv")
OUTPUT_CSV = os.path.join(EXP37_DIR, "outputs", "exp36_vs_exp37_exact_comparison.csv")

METRICS = (
    "cell_mean_mpa",
    "cv",
    "p95_to_mean",
    "peak_to_mean",
    "gini",
    "top20_load_share",
    "target_rmse_mpa",
    "positive_node_coverage",
    "absolute_peak_mpa",
    "ke_to_ie",
    "ae_to_ie",
    "top_endplate_u3_range_mm",
    "top_endplate_max_abs_u3_mm",
    "top_endplate_max_mises_mpa",
    "bottom_endplate_max_mises_mpa",
    "bottom_reaction_z_kn",
)


def read_by_case(path):
    with open(path, "r", encoding="utf-8-sig") as handle:
        return {row["case"]: row for row in csv.DictReader(handle)}


def main():
    greedy = read_by_case(EXP36_CSV)
    exact = read_by_case(EXP37_CSV)
    rows = []
    for case in ("min", "natural", "max"):
        for metric in METRICS:
            old = float(greedy[case][metric])
            new = float(exact[case][metric])
            difference = new - old
            relative_percent = 0.0 if old == 0.0 else difference / old * 100.0
            rows.append(
                {
                    "case": case,
                    "metric": metric,
                    "exp36_greedy": old,
                    "exp37_exact": new,
                    "difference": difference,
                    "relative_difference_percent": relative_percent,
                }
            )

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    max_row = max(rows, key=lambda row: abs(row["relative_difference_percent"]))
    print("Wrote: {}".format(OUTPUT_CSV))
    print(
        "Largest absolute relative difference: {case} {metric} = {value:.9g}%".format(
            case=max_row["case"],
            metric=max_row["metric"],
            value=max_row["relative_difference_percent"],
        )
    )


if __name__ == "__main__":
    main()
