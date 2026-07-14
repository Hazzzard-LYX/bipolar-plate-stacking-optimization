# -*- coding: utf-8 -*-
from __future__ import print_function

import csv
import hashlib
import json
import os
import re
import time

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csr_matrix, vstack

import config as cfg


HERE = os.path.dirname(os.path.abspath(__file__))
EXPERIMENT_DIR = os.path.abspath(os.path.join(HERE, os.pardir))
OUTPUT_DIR = os.path.join(EXPERIMENT_DIR, "outputs")
DATA_DIR = os.path.join(OUTPUT_DIR, "generated_surfaces_820x345mm")
PROJECT_ROOT = os.path.abspath(os.path.join(EXPERIMENT_DIR, os.pardir, os.pardir))


def plate_number(name):
    match = re.search(r"_(\d{3})_", name)
    if not match:
        raise RuntimeError("Cannot parse plate number: %s" % name)
    return int(match.group(1))


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_surfaces():
    paths = sorted(
        [os.path.join(DATA_DIR, name) for name in os.listdir(DATA_DIR) if name.lower().endswith(".csv")],
        key=lambda path: plate_number(os.path.basename(path)),
    )
    if len(paths) != cfg.PLATE_COUNT:
        raise RuntimeError("Expected %d copied surfaces, found %d." % (cfg.PLATE_COUNT, len(paths)))
    surfaces = []
    xy = None
    nx = ny = None
    for path in paths:
        data = np.genfromtxt(path, delimiter=",", names=True, dtype=float, encoding="utf-8-sig")
        names = tuple(data.dtype.names or ())
        if names != ("x_mm", "y_mm", "z_mm"):
            raise RuntimeError("Unexpected CSV columns in %s: %s" % (path, names))
        current_xy = np.column_stack([data["x_mm"], data["y_mm"]])
        if xy is None:
            xy = current_xy
            nx = len(np.unique(data["x_mm"]))
            ny = len(np.unique(data["y_mm"]))
        elif current_xy.shape != xy.shape or not np.allclose(current_xy, xy):
            raise RuntimeError("Surface grid mismatch: %s" % path)
        surfaces.append(data["z_mm"].reshape(ny, nx))
    return paths, np.asarray(surfaces, dtype=float)


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


def selected_components(node_count, edges, solution):
    adjacency = [[] for _ in range(node_count)]
    selected = []
    for edge_index, (i, j) in enumerate(edges):
        if solution[edge_index] > 0.5:
            adjacency[i].append(j)
            adjacency[j].append(i)
            selected.append((i, j))
    if any(len(neighbors) != 2 for neighbors in adjacency):
        raise RuntimeError("MILP solution violates degree-two constraints.")
    unseen = set(range(node_count))
    components = []
    while unseen:
        root = next(iter(unseen))
        stack = [root]
        component = set()
        while stack:
            node = stack.pop()
            if node in component:
                continue
            component.add(node)
            unseen.discard(node)
            stack.extend(adjacency[node])
        components.append(component)
    return adjacency, components, selected


def canonical_cut(component, node_count):
    left = tuple(sorted(component))
    right = tuple(sorted(set(range(node_count)) - set(component)))
    return min(left, right, key=lambda values: (len(values), values))


def extract_open_path(adjacency, dummy):
    start = min(adjacency[dummy])
    path = []
    previous = dummy
    current = start
    while current != dummy:
        path.append(current)
        choices = [node for node in adjacency[current] if node != previous]
        if len(choices) != 1:
            raise RuntimeError("Cannot extract Hamiltonian path from exact cycle.")
        previous, current = current, choices[0]
    if len(path) != dummy or len(set(path)) != dummy:
        raise RuntimeError("Extracted path is not Hamiltonian.")
    if path[-1] < path[0]:
        path.reverse()
    return path


def solve_exact_open_path(matrix, maximize=False):
    real_count = len(matrix)
    dummy = real_count
    node_count = real_count + 1
    edges = [(i, j) for i in range(node_count) for j in range(i + 1, node_count)]
    edge_index = {edge: index for index, edge in enumerate(edges)}
    costs = np.zeros(len(edges), dtype=float)
    for index, (i, j) in enumerate(edges):
        if i < real_count and j < real_count:
            costs[index] = matrix[i, j]
    objective = -costs if maximize else costs

    degree_rows = []
    degree_cols = []
    degree_data = []
    for node in range(node_count):
        for index, (i, j) in enumerate(edges):
            if node == i or node == j:
                degree_rows.append(node)
                degree_cols.append(index)
                degree_data.append(1.0)
    degree_matrix = csr_matrix((degree_data, (degree_rows, degree_cols)), shape=(node_count, len(edges)))
    cut_rows = []
    cut_keys = set()
    history = []
    started = time.time()

    for iteration in range(1, 200):
        matrices = [degree_matrix] + cut_rows
        constraint_matrix = vstack(matrices, format="csr")
        lower = np.concatenate([
            np.full(node_count, 2.0),
            np.full(len(cut_rows), 2.0),
        ])
        upper = np.concatenate([
            np.full(node_count, 2.0),
            np.full(len(cut_rows), np.inf),
        ])
        result = milp(
            c=objective,
            integrality=np.ones(len(edges), dtype=int),
            bounds=Bounds(np.zeros(len(edges)), np.ones(len(edges))),
            constraints=LinearConstraint(constraint_matrix, lower, upper),
            options={
                "disp": False,
                "presolve": True,
                "time_limit": float(cfg.EXACT_SOLVER_TIME_LIMIT_S),
                "mip_rel_gap": float(cfg.EXACT_SOLVER_MIP_GAP),
            },
        )
        if result.x is None or result.status != 0:
            raise RuntimeError("Exact MILP did not prove optimality: status=%s message=%s" % (result.status, result.message))
        adjacency, components, selected = selected_components(node_count, edges, result.x)
        history.append({
            "iteration": iteration,
            "component_count": len(components),
            "cut_count": len(cut_rows),
            "solver_objective": float(result.fun),
            "mip_gap": float(getattr(result, "mip_gap", 0.0)),
            "mip_node_count": int(getattr(result, "mip_node_count", 0)),
        })
        print("%s iteration %d: components=%d cuts=%d objective=%.9f" % (
            "MAX" if maximize else "MIN", iteration, len(components), len(cut_rows), float(result.fun)
        ))
        if len(components) == 1:
            path = extract_open_path(adjacency, dummy)
            score = path_score(path, matrix)
            return path, score, {
                "method": "exact_undirected_milp_dummy_node_iterative_subtour_cuts",
                "proved_optimal": True,
                "maximize": bool(maximize),
                "elapsed_s": time.time() - started,
                "iterations": history,
                "selected_cycle_edges": [[int(i), int(j)] for i, j in selected],
                "final_message": str(result.message),
            }
        added = 0
        for component in components:
            key = canonical_cut(component, node_count)
            if key in cut_keys:
                continue
            cut_keys.add(key)
            inside = set(key)
            columns = []
            for i in inside:
                for j in range(node_count):
                    if j not in inside:
                        columns.append(edge_index[(min(i, j), max(i, j))])
            row = csr_matrix((np.ones(len(columns)), ([0] * len(columns), columns)), shape=(1, len(edges)))
            cut_rows.append(row)
            added += 1
        if added == 0:
            raise RuntimeError("No new subtour cuts could be added.")
    raise RuntimeError("Exact MILP exceeded subtour-cut iteration limit.")


def main():
    if not os.path.isdir(DATA_DIR):
        raise RuntimeError("Copied Experiment 30 surfaces are missing: %s" % DATA_DIR)
    paths, surfaces = load_surfaces()
    matrix = distance_matrix(benchmark_vectors(surfaces))
    min_path, min_score, min_metadata = solve_exact_open_path(matrix, maximize=False)
    max_path, max_score, max_metadata = solve_exact_open_path(matrix, maximize=True)
    natural_path = list(range(len(surfaces)))
    natural_score = path_score(natural_path, matrix)

    orders = {
        "algorithm": "exact MILP open Hamiltonian path",
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
    with open(os.path.join(OUTPUT_DIR, "exact_solver_metadata.json"), "w", encoding="utf-8") as handle:
        json.dump({"min": min_metadata, "max": max_metadata}, handle, ensure_ascii=False, indent=2)
    with open(os.path.join(OUTPUT_DIR, "surface_hashes_sha256.csv"), "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["plate_no", "file", "sha256"])
        for path in paths:
            writer.writerow([plate_number(os.path.basename(path)), os.path.basename(path), sha256(path)])
    with open(os.path.join(OUTPUT_DIR, "stack_order_summary.csv"), "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case", "plate_count", "adjacent_distance_sum_mm", "order", "proved_optimal"])
        for case in ("min", "natural", "max"):
            writer.writerow([case, len(surfaces), orders["distance_sum_mm"][case], "-".join(map(str, orders[case])), case != "natural"])
    print(json.dumps(orders, indent=2))


if __name__ == "__main__":
    main()
