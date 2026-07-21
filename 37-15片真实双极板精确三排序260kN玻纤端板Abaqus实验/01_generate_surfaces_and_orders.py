# -*- coding: utf-8 -*-
from __future__ import print_function

import csv
import json
import math
import os
import re
import shutil

import numpy as np

import config as cfg


HERE = os.path.dirname(os.path.abspath(__file__))
EXPERIMENT_DIR = os.path.abspath(os.path.join(HERE, os.pardir))
OUTPUT_DIR = os.path.join(EXPERIMENT_DIR, "outputs")
GENERATED_DIR = os.path.join(OUTPUT_DIR, "generated_surfaces_820x345mm")
PROJECT_ROOT = os.path.abspath(os.path.join(EXPERIMENT_DIR, os.pardir, os.pardir))


def ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def plate_number(name):
    match = re.search(r"_(\d{2,3})_", name)
    return int(match.group(1)) if match else 10 ** 9


def find_source_dir():
    explicit = os.environ.get("BIPOLAR_SOURCE_DIR", "").strip()
    if explicit:
        if not os.path.isdir(explicit):
            raise RuntimeError("BIPOLAR_SOURCE_DIR does not exist: %s" % explicit)
        return explicit
    candidates = []
    for root, _dirs, files in os.walk(PROJECT_ROOT):
        if "Abaqus有限元分析" in root:
            continue
        csv_files = [name for name in files if name.lower().endswith(".csv")]
        if "820x345mm" in root and len(csv_files) >= 15:
            score = 0 if "真实双极板曲面数据" in root else 1
            candidates.append((score, len(root), root))
    if not candidates:
        raise RuntimeError("Cannot locate the original 820x345mm surface CSV directory.")
    return sorted(candidates)[0][2]


def load_source_surfaces(source_dir):
    paths = sorted(
        [os.path.join(source_dir, name) for name in os.listdir(source_dir) if name.lower().endswith(".csv")],
        key=lambda path: plate_number(os.path.basename(path)),
    )[:15]
    if len(paths) < 15:
        raise RuntimeError("At least 15 source CSV files are required.")
    tables = []
    for path in paths:
        data = np.genfromtxt(path, delimiter=",", names=True, dtype=float, encoding="utf-8-sig")
        names = tuple(data.dtype.names or ())
        if names != ("x_mm", "y_mm", "z_mm"):
            raise RuntimeError("Unexpected CSV columns in %s: %s" % (path, names))
        tables.append((path, data["x_mm"], data["y_mm"], data["z_mm"]))
    x = tables[0][1]
    y = tables[0][2]
    for path, tx, ty, _z in tables[1:]:
        if tx.shape != x.shape or not np.allclose(tx, x) or not np.allclose(ty, y):
            raise RuntimeError("Source grid mismatch: %s" % path)
    nx = len(np.unique(x))
    ny = len(np.unique(y))
    if nx * ny != len(x):
        raise RuntimeError("Source grid is not rectangular.")
    z_stack = np.asarray([row[3].reshape(ny, nx) for row in tables], dtype=float)
    return paths, x, y, z_stack, nx, ny


def normalized_mode(values):
    values = np.asarray(values, dtype=float)
    values = values - float(np.mean(values))
    std = float(np.std(values))
    return values / std if std > 1.0e-12 else values


def synthesize_surfaces(z_stack, nx, ny):
    rng = np.random.default_rng(cfg.RANDOM_SEED)
    plate_means = np.mean(z_stack, axis=(1, 2))
    shapes = z_stack - plate_means[:, None, None]
    flat = shapes.reshape(len(shapes), -1)
    centered = flat - np.mean(flat, axis=0, keepdims=True)
    u, singular, _vt = np.linalg.svd(centered, full_matrices=False)
    pc1 = u[:, 0] * singular[0]
    source_order = np.argsort(pc1)

    gx = np.linspace(-1.0, 1.0, nx)[None, :]
    gy = np.linspace(-1.0, 1.0, ny)[:, None]
    modes = [
        normalized_mode(np.sin(math.pi * gx) * np.cos(math.pi * gy)),
        normalized_mode(np.cos(2.0 * math.pi * gx) * np.sin(math.pi * gy)),
        normalized_mode((gx * gx - np.mean(gx * gx)) + 0.5 * (gy * gy - np.mean(gy * gy))),
    ]
    smooth_amp = float(cfg.SMOOTH_PERTURB_MM)
    noise_amp = float(cfg.LOCAL_NOISE_MM)
    generated = []
    metadata = []
    count = int(cfg.PLATE_COUNT)
    for index in range(count):
        nominal_t = index / float(max(1, count - 1))
        jitter_t = rng.normal(0.0, cfg.LATENT_JITTER_INDEX / float(max(1, count - 1)))
        latent = float(np.clip(nominal_t + jitter_t, 0.0, 1.0))
        position = latent * (len(source_order) - 1)
        low = int(math.floor(position))
        high = min(low + 1, len(source_order) - 1)
        blend = position - low
        source_low = int(source_order[low])
        source_high = int(source_order[high])
        shape = (1.0 - blend) * shapes[source_low] + blend * shapes[source_high]
        mean_height = (1.0 - blend) * plate_means[source_low] + blend * plate_means[source_high]

        drift = smooth_amp * (2.0 * latent - 1.0) * modes[0]
        perturb = drift
        perturb += rng.normal(0.0, 0.35 * smooth_amp) * modes[1]
        perturb += rng.normal(0.0, 0.25 * smooth_amp) * modes[2]
        perturb += rng.normal(0.0, noise_amp, size=(ny, nx))
        generated.append(mean_height + shape + perturb)
        metadata.append({
            "plate_no": index + 1,
            "nominal_t": nominal_t,
            "latent_t": latent,
            "source_low": source_low + 1,
            "source_high": source_high + 1,
            "blend": blend,
        })
    return np.asarray(generated), metadata


def write_surface(path, x, y, z):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["x_mm", "y_mm", "z_mm"])
        for xv, yv, zv in zip(x, y, z.ravel()):
            writer.writerow(["%.6f" % xv, "%.6f" % yv, "%.6f" % zv])


def benchmark_vectors(surfaces):
    ny, nx = surfaces.shape[1:]
    ix = np.rint(np.linspace(0, nx - 1, cfg.GRID_CELLS_X + 1)).astype(int)
    iy = np.rint(np.linspace(0, ny - 1, cfg.GRID_CELLS_Y + 1)).astype(int)
    vectors = []
    for surface in surfaces:
        sampled = surface[np.ix_(iy, ix)].ravel()
        vectors.append(sampled - float(np.mean(sampled)))
    return np.asarray(vectors)


def distance_matrix(vectors):
    count = len(vectors)
    matrix = np.zeros((count, count), dtype=float)
    for i in range(count):
        for j in range(i + 1, count):
            value = float(np.sum(np.abs(vectors[i] - vectors[j])))
            matrix[i, j] = value
            matrix[j, i] = value
    return matrix


def path_score(path, matrix):
    return float(sum(matrix[path[i], path[i + 1]] for i in range(len(path) - 1)))


def improve_two_opt(path, matrix, maximize):
    path = list(path)
    for _iteration in range(20):
        improved = False
        for i in range(len(path) - 1):
            for j in range(i + 1, len(path)):
                old = 0.0
                new = 0.0
                if i > 0:
                    old += matrix[path[i - 1], path[i]]
                    new += matrix[path[i - 1], path[j]]
                if j < len(path) - 1:
                    old += matrix[path[j], path[j + 1]]
                    new += matrix[path[i], path[j + 1]]
                better = new > old + 1.0e-12 if maximize else new < old - 1.0e-12
                if better:
                    path[i:j + 1] = reversed(path[i:j + 1])
                    improved = True
        if not improved:
            break
    return path


def optimized_greedy_path(matrix, maximize):
    best_path = None
    best_score = -float("inf") if maximize else float("inf")
    for start in range(len(matrix)):
        unused = set(range(len(matrix)))
        unused.remove(start)
        path = [start]
        while unused:
            current = path[-1]
            next_node = max(unused, key=lambda node: matrix[current, node]) if maximize else min(
                unused, key=lambda node: matrix[current, node]
            )
            path.append(next_node)
            unused.remove(next_node)
        path = improve_two_opt(path, matrix, maximize)
        score = path_score(path, matrix)
        better = score > best_score if maximize else score < best_score
        if better:
            best_path = path
            best_score = score
    if best_path[-1] < best_path[0]:
        best_path = list(reversed(best_path))
    return best_path, best_score


def exact_held_karp_path(matrix, maximize):
    """Solve the open Hamiltonian path exactly for the supplied distance matrix."""
    count = len(matrix)
    state_count = 1 << count
    costs = [[None] * count for _ in range(state_count)]
    predecessors = [[-1] * count for _ in range(state_count)]
    for end in range(count):
        costs[1 << end][end] = 0.0

    for mask in range(1, state_count):
        for end in range(count):
            if not (mask & (1 << end)):
                continue
            previous_mask = mask ^ (1 << end)
            if previous_mask == 0:
                continue
            best_cost = None
            best_previous = -1
            for previous in range(count):
                previous_cost = costs[previous_mask][previous]
                if previous_cost is None:
                    continue
                candidate = previous_cost + float(matrix[previous, end])
                better = best_cost is None or (candidate > best_cost if maximize else candidate < best_cost)
                if better or (candidate == best_cost and previous < best_previous):
                    best_cost = candidate
                    best_previous = previous
            costs[mask][end] = best_cost
            predecessors[mask][end] = best_previous

    full_mask = state_count - 1
    best_end = -1
    best_score = None
    for end in range(count):
        candidate = costs[full_mask][end]
        better = best_score is None or (candidate > best_score if maximize else candidate < best_score)
        if better or (candidate == best_score and end < best_end):
            best_score = candidate
            best_end = end

    path = []
    mask = full_mask
    end = best_end
    while end >= 0:
        path.append(end)
        previous = predecessors[mask][end]
        mask ^= 1 << end
        end = previous
    path.reverse()
    if path[-1] < path[0]:
        path.reverse()
    return path, float(best_score)


def main():
    ensure_dir(OUTPUT_DIR)
    ensure_dir(GENERATED_DIR)
    source_dir = find_source_dir()
    source_paths, x, y, z_stack, nx, ny = load_source_surfaces(source_dir)

    if cfg.USE_ORIGINAL_SURFACES:
        if cfg.PLATE_COUNT > len(source_paths):
            raise RuntimeError("USE_ORIGINAL_SURFACES cannot exceed the source plate count.")
        surfaces = z_stack[:cfg.PLATE_COUNT]
        metadata = [{"plate_no": i + 1, "source_file": source_paths[i]} for i in range(cfg.PLATE_COUNT)]
    else:
        surfaces, metadata = synthesize_surfaces(z_stack, nx, ny)

    for index, surface in enumerate(surfaces, start=1):
        name = "bipolar_plate_%03d_820x345mm.csv" % index
        write_surface(os.path.join(GENERATED_DIR, name), x, y, surface)

    matrix = distance_matrix(benchmark_vectors(surfaces))
    min_path, min_score = exact_held_karp_path(matrix, maximize=False)
    max_path, max_score = exact_held_karp_path(matrix, maximize=True)
    natural_path = list(range(len(surfaces)))
    natural_score = path_score(natural_path, matrix)
    if min_path[-1] < min_path[0]:
        min_path = list(reversed(min_path))
    if max_path[-1] < max_path[0]:
        max_path = list(reversed(max_path))
    orders = {
        "algorithm": "exact Held-Karp dynamic programming",
        "distance_metric": "17x9 centered-height L1 distance, identical to Experiment 36",
        "min": [value + 1 for value in min_path],
        "natural": [value + 1 for value in natural_path],
        "max": [value + 1 for value in max_path],
        "distance_sum_mm": {
            "min": min_score,
            "natural": natural_score,
            "max": max_score,
        },
    }
    with open(os.path.join(OUTPUT_DIR, "stack_orders.json"), "w", encoding="utf-8") as handle:
        json.dump(orders, handle, ensure_ascii=False, indent=2)
    with open(os.path.join(OUTPUT_DIR, "surface_generation_metadata.json"), "w", encoding="utf-8") as handle:
        json.dump({"source_dir": source_dir, "plates": metadata}, handle, ensure_ascii=False, indent=2)
    with open(os.path.join(OUTPUT_DIR, "stack_order_summary.csv"), "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case", "plate_count", "adjacent_distance_sum_mm", "order"])
        for case in ("min", "natural", "max"):
            writer.writerow([case, len(surfaces), orders["distance_sum_mm"][case], "-".join(map(str, orders[case]))])
    print("Generated %d surfaces in %s" % (len(surfaces), GENERATED_DIR))
    print(json.dumps(orders, indent=2))


if __name__ == "__main__":
    main()
