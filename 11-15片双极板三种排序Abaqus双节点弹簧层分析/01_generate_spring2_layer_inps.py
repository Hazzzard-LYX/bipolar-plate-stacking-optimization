# -*- coding: utf-8 -*-
from __future__ import print_function

import csv
import math
import os

import numpy as np

EXPERIMENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
OUTPUT_DIR = os.path.join(EXPERIMENT_DIR, "outputs")
PROJECT_ROOT = os.path.abspath(os.path.join(EXPERIMENT_DIR, os.pardir, os.pardir))

LENGTH_M = 0.820
WIDTH_M = 0.345
RAW_NX = 201
RAW_NY = 85
NX = 16
NY = 8
TARGET_MEAN_MPA = 0.448
PRESCRIBED_U3_M = -1.0e-3
SIGMA_CELLS = 1.15
ALPHA = 1.35
POWER = 1.20
CELL_AREA_M2 = LENGTH_M * WIDTH_M / float(NX * NY)
BASE_K_N_PER_M = TARGET_MEAN_MPA * 1.0e6 * CELL_AREA_M2 / abs(PRESCRIBED_U3_M)

CASES = [
    ("min_distance_sum", "exp11_min_spring2_layer", [1, 10, 9, 7, 11, 8, 12, 4, 14, 3, 5, 13, 15, 6, 2]),
    ("natural", "exp11_natural_spring2_layer", list(range(1, 16))),
    ("max_distance_sum", "exp11_max_spring2_layer", [11, 12, 13, 7, 14, 9, 5, 6, 8, 15, 3, 1, 2, 10, 4]),
]


def ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def find_data_dir():
    for root, _dirs, files in os.walk(PROJECT_ROOT):
        if "820x345mm" in root:
            if len([n for n in files if n.lower().endswith(".csv")]) >= 15:
                return root
    raise RuntimeError("Cannot find 820x345mm CSV data directory under %s" % PROJECT_ROOT)


DATA_DIR = find_data_dir()


def read_plate_grid(plate_index):
    token = "_%02d_" % plate_index
    matches = [name for name in os.listdir(DATA_DIR) if name.lower().endswith(".csv") and token in name]
    if not matches:
        raise RuntimeError("Cannot find CSV for plate %02d in %s" % (plate_index, DATA_DIR))
    path = os.path.join(DATA_DIR, sorted(matches)[0])
    with open(path, "rb") as f:
        text = f.read()
    if text.startswith(b"\xef\xbb\xbf"):
        text = text[3:]
    rows = list(csv.DictReader(text.decode("utf-8").splitlines()))
    grid = np.zeros((RAW_NY, RAW_NX), dtype=float)
    for k, row in enumerate(rows):
        j = k // RAW_NX
        i = k % RAW_NX
        grid[j, i] = float(row["z_mm"]) / 1000.0
    return grid


def interpolate_z(grid, x_m, y_m):
    fx = (x_m / LENGTH_M + 0.5) * (RAW_NX - 1)
    fy = (y_m / WIDTH_M + 0.5) * (RAW_NY - 1)
    i0 = max(0, min(RAW_NX - 2, int(math.floor(fx))))
    j0 = max(0, min(RAW_NY - 2, int(math.floor(fy))))
    u = fx - i0
    v = fy - j0
    a = grid[j0, i0]
    b = grid[j0, i0 + 1]
    c = grid[j0 + 1, i0]
    d = grid[j0 + 1, i0 + 1]
    if u + v <= 1.0:
        return a + u * (b - a) + v * (c - a)
    return b * (1.0 - v) + c * (1.0 - u) + d * (u + v - 1.0)


def sample_plate(grid):
    xs = -LENGTH_M * 0.5 + (np.arange(NX) + 0.5) * (LENGTH_M / NX)
    ys = -WIDTH_M * 0.5 + (np.arange(NY) + 0.5) * (WIDTH_M / NY)
    out = np.zeros((NY, NX), dtype=float)
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            out[j, i] = interpolate_z(grid, float(x), float(y))
    return out


def gaussian_kernel(sigma):
    radius = max(1, int(math.ceil(3.0 * sigma)))
    ys, xs = np.mgrid[-radius:radius + 1, -radius:radius + 1]
    kernel = np.exp(-(xs ** 2 + ys ** 2) / (2.0 * sigma ** 2))
    kernel /= np.sum(kernel)
    return kernel


def convolve_edge(values, kernel):
    ky, kx = kernel.shape
    ry = ky // 2
    rx = kx // 2
    padded = np.pad(values, ((ry, ry), (rx, rx)), mode="edge")
    out = np.zeros_like(values, dtype=float)
    for j in range(values.shape[0]):
        for i in range(values.shape[1]):
            out[j, i] = float(np.sum(padded[j:j + ky, i:i + kx] * kernel))
    return out


def interface_spread(upper, lower, kernel):
    diff = upper - lower
    diff = diff - np.mean(diff)
    mismatch_um = np.abs(diff) * 1.0e6
    return convolve_edge(mismatch_um, kernel)


def write_list(f, values, per_line=16):
    for i in range(0, len(values), per_line):
        f.write(", ".join(str(v) for v in values[i:i + per_line]) + "\n")


def main():
    ensure_dir(OUTPUT_DIR)
    kernel = gaussian_kernel(SIGMA_CELLS)
    sampled = {p: sample_plate(read_plate_grid(p)) for p in range(1, 16)}

    all_means = []
    for i in range(1, 16):
        for j in range(1, 16):
            if i != j:
                all_means.append(float(np.mean(interface_spread(sampled[i], sampled[j], kernel))))
    global_scale_um = float(np.mean(all_means))

    xs = -LENGTH_M * 0.5 + (np.arange(NX) + 0.5) * (LENGTH_M / NX)
    ys = -WIDTH_M * 0.5 + (np.arange(NY) + 0.5) * (WIDTH_M / NY)

    for case_name, job, order in CASES:
        inp_path = os.path.join(OUTPUT_DIR, job + ".inp")
        map_path = os.path.join(OUTPUT_DIR, job + "_spring2_map.csv")
        nodes = []
        elems = []
        spring_rows = []
        upper_nodes = []
        lower_nodes = []
        node_id = 1
        elem_id = 1
        for iface in range(1, len(order)):
            spread = interface_spread(sampled[order[iface - 1]], sampled[order[iface]], kernel)
            normalized = (spread / global_scale_um) ** POWER
            k_grid = BASE_K_N_PER_M * (1.0 + ALPHA * normalized)
            z = -0.002 * iface
            for j, y in enumerate(ys):
                for i, x in enumerate(xs):
                    lower = node_id
                    upper = node_id + 1
                    nodes.append((lower, x, y, z))
                    nodes.append((upper, x, y, z + 1.0e-4))
                    lower_nodes.append(lower)
                    upper_nodes.append(upper)
                    elems.append((elem_id, lower, upper, float(k_grid[j, i])))
                    spring_rows.append({
                        "case": case_name,
                        "job": job,
                        "interface_index": iface,
                        "upper_plate": order[iface - 1],
                        "lower_plate": order[iface],
                        "ix": i,
                        "iy": j,
                        "lower_node": lower,
                        "upper_node": upper,
                        "element": elem_id,
                        "spring_k_n_per_m": float(k_grid[j, i]),
                        "spread_mismatch_um": float(spread[j, i]),
                    })
                    node_id += 2
                    elem_id += 1

        with open(inp_path, "w") as f:
            f.write("*Heading\n")
            f.write("Experiment 11 - Abaqus SPRING2 equivalent compliant layer: %s\n" % case_name)
            f.write("*Preprint, echo=NO, model=NO, history=NO, contact=NO\n")
            f.write("** Stack order: %s\n" % " -> ".join(str(x) for x in order))
            f.write("*Node\n")
            for row in nodes:
                f.write("%d, %.10e, %.10e, %.10e\n" % row)
            f.write("*Nset, nset=LOWER_NODES\n")
            write_list(f, lower_nodes)
            f.write("*Nset, nset=UPPER_NODES\n")
            write_list(f, upper_nodes)
            for eid, n1, n2, k in elems:
                f.write("*Element, type=SPRING2, elset=E%d\n" % eid)
                f.write("%d, %d, %d\n" % (eid, n1, n2))
                f.write("*Spring, elset=E%d\n3, 3\n%.10e\n" % (eid, k))
            f.write("*Boundary\n")
            f.write("LOWER_NODES, 1, 3, 0.0\n")
            f.write("UPPER_NODES, 1, 2, 0.0\n")
            f.write("*Step, name=Compression, nlgeom=NO\n")
            f.write("*Static\n1.0, 1.0\n")
            f.write("*Boundary\n")
            f.write("UPPER_NODES, 3, 3, %.10e\n" % PRESCRIBED_U3_M)
            f.write("*Output, field\n")
            f.write("*Node Output\nU, RF\n")
            f.write("*End Step\n")

        with open(map_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(spring_rows[0].keys()))
            writer.writeheader()
            writer.writerows(spring_rows)
        print("wrote", inp_path)
        print("wrote", map_path)


if __name__ == "__main__":
    main()
