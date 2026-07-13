# -*- coding: utf-8 -*-
import csv
import importlib.util
import os

import numpy as np

EXP2_PREP = r"D:\双极板堆叠有限元分析\Abaqus有限元分析\2-15片双极板堆叠Abaqus接触分析\脚本\01_prepare_stack_inp.py"
OUT_DIR = r"D:\双极板堆叠有限元分析\Abaqus有限元分析\3-15片双极板自然顺序Abaqus接触分析\outputs"

CASES = [
    ("min_distance_sum", [1, 10, 9, 7, 11, 8, 12, 4, 14, 3, 5, 13, 15, 6, 2]),
    ("natural", list(range(1, 16))),
]


def load_prepare_module():
    spec = importlib.util.spec_from_file_location("exp2_prepare", EXP2_PREP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sample_grid(mod, grid, nx=16, ny=8):
    xs = -mod.LENGTH_M * 0.5 + (np.arange(nx) + 0.5) * (mod.LENGTH_M / nx)
    ys = -mod.WIDTH_M * 0.5 + (np.arange(ny) + 0.5) * (mod.WIDTH_M / ny)
    out = np.zeros((ny, nx), dtype=float)
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            out[j, i] = mod.interpolate_z(grid, float(x), float(y))
    return out


def pair_metrics(a, b):
    # Remove best-fit vertical offset; this measures shape mismatch rather than absolute height.
    d = a - b
    d0 = d - np.mean(d)
    abs_d = np.abs(d0)
    return {
        "rms_um": float(np.sqrt(np.mean(d0 ** 2)) * 1e6),
        "mean_abs_um": float(np.mean(abs_d) * 1e6),
        "p95_abs_um": float(np.percentile(abs_d, 95) * 1e6),
        "max_abs_um": float(np.max(abs_d) * 1e6),
    }


def main():
    mod = load_prepare_module()
    grids = {p: sample_grid(mod, mod.read_plate_grid(p)) for p in range(1, 16)}
    rows = []
    summary = []
    for case_name, order in CASES:
        values = []
        for i in range(len(order) - 1):
            m = pair_metrics(grids[order[i]], grids[order[i + 1]])
            row = {
                "case": case_name,
                "interface_index": i + 1,
                "upper_plate": order[i],
                "lower_plate": order[i + 1],
            }
            row.update(m)
            rows.append(row)
            values.append(m)
        s = {"case": case_name}
        for key in ("rms_um", "mean_abs_um", "p95_abs_um", "max_abs_um"):
            s[key + "_mean"] = float(np.mean([v[key] for v in values]))
            s[key + "_max"] = float(np.max([v[key] for v in values]))
        summary.append(s)

    out_csv = os.path.join(OUT_DIR, "exp3_vs_exp2_geometric_mismatch_by_interface.csv")
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    out_sum = os.path.join(OUT_DIR, "exp3_vs_exp2_geometric_mismatch_summary.csv")
    with open(out_sum, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)

    print("wrote", out_csv)
    print("wrote", out_sum)
    for s in summary:
        print(s)


if __name__ == "__main__":
    main()
