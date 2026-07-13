# -*- coding: utf-8 -*-
import csv
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

EXP_DIR = r"D:\双极板堆叠有限元分析\Abaqus有限元分析\2-15片双极板堆叠Abaqus接触分析"
OUT_DIR = os.path.join(EXP_DIR, "outputs")
JOB = "exp2_stack15_ordered_contact"
ORIG_PROG = r"D:\双极板堆叠有限元分析\大幅面双极板堆叠优化分析-20260624\大幅面双极板堆叠优化分析\程序"
STACK_ORDER_PLATES = [1, 10, 9, 7, 11, 8, 12, 4, 14, 3, 5, 13, 15, 6, 2]
STACK_ORDER_ZERO = [p - 1 for p in STACK_ORDER_PLATES]
NX_NODES = 17
NY_NODES = 9
NX = 16
NY = 8
TARGET_MEAN_MPA = 0.448


def setup_fonts():
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def pearson(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 3:
        return np.nan
    aa = a[ok] - np.mean(a[ok])
    bb = b[ok] - np.mean(b[ok])
    den = np.sqrt(np.sum(aa * aa) * np.sum(bb * bb))
    return float(np.sum(aa * bb) / den) if den > 0 else np.nan


def ranks(x):
    order = np.argsort(x)
    r = np.empty_like(order, dtype=float)
    r[order] = np.arange(len(x), dtype=float)
    return r


def spearman(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 3:
        return np.nan
    return pearson(ranks(a[ok]), ranks(b[ok]))


def hotspot_iou(a, b, mask, q=0.80):
    ok = np.isfinite(a) & np.isfinite(b) & mask
    if ok.sum() < 3:
        return np.nan
    av = a[ok]
    bv = b[ok]
    ath = np.quantile(av, q)
    bth = np.quantile(bv, q)
    ah = (a >= ath) & ok
    bh = (b >= bth) & ok
    union = np.logical_or(ah, bh).sum()
    return float(np.logical_and(ah, bh).sum() / union) if union else np.nan


def normalize_mean(x, mask):
    out = np.array(x, dtype=float, copy=True)
    ok = np.isfinite(out) & mask
    mean = float(out[ok].mean()) if ok.any() else 0.0
    if mean > 0:
        out[ok] = out[ok] / mean
    return out


def node_grid_to_cell_grid(node_grid):
    return 0.25 * (
        node_grid[:-1, :-1] + node_grid[:-1, 1:] +
        node_grid[1:, :-1] + node_grid[1:, 1:]
    )


def read_abaqus_panels():
    data = {}
    csv_path = os.path.join(OUT_DIR, JOB + "_cpress_nodes.csv")
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            idx = int(row["interface_index"])
            if idx not in data:
                data[idx] = np.zeros((NY_NODES, NX_NODES), dtype=float)
            data[idx][int(row["iy"]), int(row["ix"])] = float(row["cpress_pa"]) / 1.0e6

    panels = []
    for idx in range(1, len(STACK_ORDER_PLATES)):
        cell = node_grid_to_cell_grid(data[idx])
        mean = float(np.mean(cell))
        if mean > 0:
            cell = cell * (TARGET_MEAN_MPA / mean)
        panels.append(cell)
    return panels


def compute_original_panels():
    sys.path.insert(0, ORIG_PROG)
    import interlayer_contact_pressure_mosaic as orig

    grids = orig.load_plate_grids()
    vertex_mask = orig.build_solid_vertex_mask()
    grid_mask = orig.build_grid_solid_mask(orig.GRID_NX, orig.GRID_NY)
    area_each = orig.solid_footprint_area()
    areas = [area_each] * orig.PLATE_COUNT
    forces_16, _ = orig.compute_interface_forces(
        areas, top_load_n=orig.TOP_LOAD_KN * 1000.0, end_plates=True
    )
    cell_area = (orig.LENGTH_M / orig.GRID_NX) * (orig.WIDTH_M / orig.GRID_NY)
    ordered = [grids[i] for i in STACK_ORDER_ZERO]
    panels = orig.build_panels_for_order(
        STACK_ORDER_ZERO, ordered, forces_16, grid_mask, cell_area
    )
    return [np.array(p["pressures_mpa"], dtype=float) for p in panels[1:-1]], grid_mask


def main():
    setup_fonts()
    abaqus = read_abaqus_panels()
    original, solid_mask = compute_original_panels()

    rows = []
    for i, (orig_map, abq_map) in enumerate(zip(original, abaqus), start=1):
        valid_mask = np.isfinite(orig_map) & solid_mask
        full_mask = np.ones_like(valid_mask, dtype=bool)
        orig_full = np.nan_to_num(orig_map, nan=0.0)
        abq_full = np.nan_to_num(abq_map, nan=0.0)
        orig_norm = normalize_mean(orig_map, valid_mask)
        abq_norm = normalize_mean(abq_map, valid_mask)
        rmse_norm = np.sqrt(np.nanmean(((orig_norm - abq_norm)[valid_mask]) ** 2))
        rows.append({
            "interface": i,
            "label": "板%d/板%d" % (STACK_ORDER_PLATES[i - 1], STACK_ORDER_PLATES[i]),
            "pearson_valid": pearson(orig_map, abq_map),
            "spearman_valid": spearman(orig_map, abq_map),
            "hotspot_iou_valid_top20": hotspot_iou(orig_map, abq_map, valid_mask),
            "rmse_mean_normalized_valid": float(rmse_norm),
            "pearson_full_zero_filled": pearson(orig_full, abq_full),
            "spearman_full_zero_filled": spearman(orig_full, abq_full),
            "hotspot_iou_full_top20": hotspot_iou(orig_full, abq_full, full_mask),
            "original_peak_mpa": float(np.nanmax(orig_map)),
            "abaqus_scaled_peak_mpa": float(np.nanmax(abq_map)),
        })

    out_csv = os.path.join(OUT_DIR, JOB + "_original_vs_abaqus_similarity.csv")
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    pvals = np.array([r["pearson_valid"] for r in rows], dtype=float)
    svals = np.array([r["spearman_valid"] for r in rows], dtype=float)
    ious = np.array([r["hotspot_iou_valid_top20"] for r in rows], dtype=float)
    rmses = np.array([r["rmse_mean_normalized_valid"] for r in rows], dtype=float)
    print("wrote", out_csv)
    print("Pearson valid mean/min/max:", np.nanmean(pvals), np.nanmin(pvals), np.nanmax(pvals))
    print("Spearman valid mean/min/max:", np.nanmean(svals), np.nanmin(svals), np.nanmax(svals))
    print("Hotspot IoU valid mean/min/max:", np.nanmean(ious), np.nanmin(ious), np.nanmax(ious))
    print("Mean-normalized RMSE valid mean/min/max:", np.nanmean(rmses), np.nanmin(rmses), np.nanmax(rmses))

    labels = [r["label"] for r in rows]
    x = np.arange(len(rows))
    fig, ax = plt.subplots(figsize=(14, 5.6), dpi=180)
    ax.plot(x, pvals, marker="o", label="Pearson 相关")
    ax.plot(x, svals, marker="s", label="Spearman 秩相关")
    ax.plot(x, ious, marker="^", label="热点重合度 Top20% IoU")
    ax.axhline(0.5, color="#999999", lw=0.8, ls="--")
    ax.set_xticks(x)
    ax.set_xticklabels(["#%d\n%s" % (i + 2, labels[i]) for i in range(len(labels))], rotation=0, fontsize=8)
    ax.set_ylim(-0.35, 1.0)
    ax.set_ylabel("相似度")
    ax.set_title("原弹塑性压力模型 vs Abaqus CPRESS：逐界面趋势相似度（有效实体网格）")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(loc="lower left", ncol=3)
    fig.tight_layout()
    out_png = os.path.join(OUT_DIR, JOB + "_original_vs_abaqus_similarity.png")
    fig.savefig(out_png)
    plt.close(fig)
    print("wrote", out_png)


if __name__ == "__main__":
    main()
