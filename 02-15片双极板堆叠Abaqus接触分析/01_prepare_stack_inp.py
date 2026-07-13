# -*- coding: utf-8 -*-
"""Experiment 2: 15-plate stack Abaqus input generator.

Generates a coarse 16 x 8 contact-grid FE baseline for trend comparison with
the original spring-model pressure maps.
"""
from __future__ import print_function

import csv
import math
import os

EXPERIMENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
OUTPUT_DIR = os.path.join(EXPERIMENT_DIR, "outputs")
PROJECT_ROOT = os.path.abspath(os.path.join(EXPERIMENT_DIR, os.pardir, os.pardir))

JOB_NAME = "exp2_stack15_ordered_contact"
INP_PATH = os.path.join(OUTPUT_DIR, JOB_NAME + ".inp")

STACK_ORDER = [1, 10, 9, 7, 11, 8, 12, 4, 14, 3, 5, 13, 15, 6, 2]
LENGTH_M = 0.820
WIDTH_M = 0.345
RAW_NX = 201
RAW_NY = 85
GRID_CELLS_X = 16
GRID_CELLS_Y = 8
NODES_X = GRID_CELLS_X + 1
NODES_Y = GRID_CELLS_Y + 1
PLATE_THICKNESS_M = 0.0002
TOP_LOAD_N = 100000.0
GRAVITY = 9.8
CONTACT_STIFFNESS_PA_PER_M = 5.0e8
WEAK_U3_STIFFNESS_N_PER_M = 1.0
INITIAL_CONTACT_GAP_M = 1.0e-5
SURFACE_E = 110.0e9
SURFACE_NU = 0.34
SURFACE_RHO = 4500.0


def ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def find_data_dir():
    for root, _dirs, files in os.walk(PROJECT_ROOT):
        if "820x345mm" in root:
            if len([n for n in files if n.lower().endswith(".csv")]) >= 15:
                return root
    raise RuntimeError("Cannot find real plate height grid directory containing 820x345mm CSV files.")


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
    rows = text.decode("utf-8").splitlines()
    values = [float(row["z_mm"]) / 1000.0 for row in csv.DictReader(rows)]
    if len(values) != RAW_NX * RAW_NY:
        raise RuntimeError("Unexpected grid size for plate %s: %s values" % (plate_index, len(values)))
    grid = []
    for j in range(RAW_NY):
        row = values[j * RAW_NX : (j + 1) * RAW_NX]
        grid.append(list(reversed(row)))
    return grid


def interpolate_z(grid, x_m, y_m):
    fx = (x_m / LENGTH_M + 0.5) * (RAW_NX - 1)
    fy = (y_m / WIDTH_M + 0.5) * (RAW_NY - 1)
    i0 = max(0, min(RAW_NX - 2, int(math.floor(fx))))
    j0 = max(0, min(RAW_NY - 2, int(math.floor(fy))))
    u = fx - i0
    v = fy - j0
    a = grid[j0][i0]
    b = grid[j0][i0 + 1]
    c = grid[j0 + 1][i0]
    d = grid[j0 + 1][i0 + 1]
    if u + v <= 1.0:
        return a + u * (b - a) + v * (c - a)
    return b * (1.0 - v) + c * (1.0 - u) + d * (u + v - 1.0)


def grid_extents(grid):
    zmin = None
    zmax = None
    for j in range(RAW_NY):
        y = (j / float(RAW_NY - 1) - 0.5) * WIDTH_M
        for i in range(RAW_NX):
            x = (i / float(RAW_NX - 1) - 0.5) * LENGTH_M
            z = interpolate_z(grid, x, y)
            zmin = z if zmin is None else min(zmin, z)
            zmax = z if zmax is None else max(zmax, z)
    return zmin - 0.5 * PLATE_THICKNESS_M, zmax + 0.5 * PLATE_THICKNESS_M


def stack_offsets(grids):
    offsets = [0.0]
    for i in range(1, len(grids)):
        prev_min, _prev_max = grid_extents(grids[i - 1])
        _cur_min, cur_max = grid_extents(grids[i])
        offsets.append(offsets[-1] + prev_min - cur_max + INITIAL_CONTACT_GAP_M)
    return offsets


def build_plate_mesh(grid, stack_index, plate_no, z_shift):
    xs = [(i / float(NODES_X - 1) - 0.5) * LENGTH_M for i in range(NODES_X)]
    ys = [(j / float(NODES_Y - 1) - 0.5) * WIDTH_M for j in range(NODES_Y)]
    node_base = 100000 * (stack_index + 1)
    elem_base = 100000 * (stack_index + 1)
    nodes = []
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            nid = node_base + j * NODES_X + i + 1
            nodes.append((nid, x, y, z_shift + interpolate_z(grid, x, y)))
    elems = []
    for j in range(GRID_CELLS_Y):
        for i in range(GRID_CELLS_X):
            n1 = node_base + j * NODES_X + i + 1
            n2 = node_base + j * NODES_X + i + 2
            n3 = node_base + (j + 1) * NODES_X + i + 2
            n4 = node_base + (j + 1) * NODES_X + i + 1
            eid = elem_base + len(elems) + 1
            elems.append((eid, n1, n2, n3, n4))
    used = [n[0] for n in nodes]
    perim = []
    for j in range(NODES_Y):
        for i in range(NODES_X):
            if j in (0, NODES_Y - 1) or i in (0, NODES_X - 1):
                perim.append(node_base + j * NODES_X + i + 1)
    return {"plate_no": plate_no, "nodes": nodes, "elems": elems, "used": used, "perim": perim}


def write_list(f, values, per_line=16):
    values = list(values)
    for i in range(0, len(values), per_line):
        f.write(", ".join(str(v) for v in values[i : i + per_line]) + "\n")


def nearest_node(nodes, target_x, target_y):
    best = None
    best_dist2 = None
    for nid, x, y, _z in nodes:
        dist2 = (x - target_x) ** 2 + (y - target_y) ** 2
        if best is None or dist2 < best_dist2:
            best = nid
            best_dist2 = dist2
    return best



def place_lower_against_upper(upper_plate, lower_grid):
    best_shift = None
    for _nid, x, y, upper_z in upper_plate["nodes"]:
        lower_top_without_shift = interpolate_z(lower_grid, x, y) + 0.5 * PLATE_THICKNESS_M
        candidate = upper_z - lower_top_without_shift - INITIAL_CONTACT_GAP_M
        best_shift = candidate if best_shift is None else min(best_shift, candidate)
    if best_shift is None:
        raise RuntimeError("Cannot compute sequential stack offset.")
    return best_shift


def build_stack_meshes(grids):
    plates = []
    shifts = []
    for i, grid in enumerate(grids):
        if i == 0:
            shift = 0.0
        else:
            shift = place_lower_against_upper(plates[-1], grid)
        shifts.append(shift)
        plates.append(build_plate_mesh(grid, i, STACK_ORDER[i], shift))
    return plates, shifts

def write_inp():
    ensure_dir(OUTPUT_DIR)
    grids = [read_plate_grid(p) for p in STACK_ORDER]
    plates, offsets = build_stack_meshes(grids)
    nodal_load = -TOP_LOAD_N / float(len(plates[0]["used"]))

    with open(INP_PATH, "w") as f:
        f.write("*Heading\n")
        f.write("Experiment 2 - 15 plate ordered stack contact baseline\n")
        f.write("*Preprint, echo=NO, model=NO, history=NO, contact=NO\n")
        f.write("** Stack order top-to-bottom: %s\n" % " -> ".join(str(p) for p in STACK_ORDER))
        f.write("** Units: m, N, Pa, kg/m3\n")
        f.write("** Contact grid: %d x %d cells\n" % (GRID_CELLS_X, GRID_CELLS_Y))
        f.write("*Node\n")
        for plate in plates:
            for row in plate["nodes"]:
                f.write("%d, %.10e, %.10e, %.10e\n" % row)
        for i, plate in enumerate(plates):
            f.write("*Element, type=S4R, elset=P%02d_EALL\n" % (i + 1))
            for row in plate["elems"]:
                f.write("%d, %d, %d, %d, %d\n" % row)
        for i, plate in enumerate(plates):
            f.write("*Nset, nset=P%02d_USED\n" % (i + 1)); write_list(f, plate["used"])
            f.write("*Nset, nset=P%02d_PERIMETER\n" % (i + 1)); write_list(f, plate["perim"])
            f.write("*Elset, elset=P%02d_EALL\n" % (i + 1)); write_list(f, [e[0] for e in plate["elems"]])
        for i, plate in enumerate(plates):
            a = nearest_node(plate["nodes"], 0.0, 0.0)
            b = nearest_node(plate["nodes"], LENGTH_M * 0.25, 0.0)
            f.write("*Nset, nset=P%02d_ANCHOR_A\n%d\n" % (i + 1, a))
            f.write("*Nset, nset=P%02d_ANCHOR_B\n%d\n" % (i + 1, b))
        f.write("*Material, name=Ti_Bipolar_Plate\n")
        f.write("*Density\n%.10e,\n" % SURFACE_RHO)
        f.write("*Elastic\n%.10e, %.6f\n" % (SURFACE_E, SURFACE_NU))
        for i in range(len(plates)):
            f.write("*Shell Section, elset=P%02d_EALL, material=Ti_Bipolar_Plate\n" % (i + 1))
            f.write("%.10e, 5\n" % PLATE_THICKNESS_M)
        f.write("*Element, type=SPRING1, elset=WEAK_U3_SPRINGS\n")
        spring_id = 90000001
        for plate in plates[:-1]:
            for nid in plate["used"]:
                f.write("%d, %d\n" % (spring_id, nid))
                spring_id += 1
        f.write("*Spring, elset=WEAK_U3_SPRINGS\n")
        f.write("3\n")
        f.write("%.10e\n" % WEAK_U3_STIFFNESS_N_PER_M)
        for i in range(len(plates)):
            f.write("*Surface, type=ELEMENT, name=P%02d_TOP\nP%02d_EALL, SPOS\n" % (i + 1, i + 1))
            f.write("*Surface, type=ELEMENT, name=P%02d_BOTTOM\nP%02d_EALL, SNEG\n" % (i + 1, i + 1))
            f.write("*Surface, type=NODE, name=P%02d_CONTACT_NODES\nP%02d_USED, 1.0\n" % (i + 1, i + 1))
        f.write("*Surface Interaction, name=LINEAR_FRICTIONLESS\n")
        f.write("*Surface Behavior, pressure-overclosure=LINEAR\n%.10e,\n" % CONTACT_STIFFNESS_PA_PER_M)
        f.write("*Friction\n0.0,\n")
        for i in range(len(plates) - 1):
            f.write("*Contact Pair, interaction=LINEAR_FRICTIONLESS, type=NODE TO SURFACE, small sliding\n")
            f.write("P%02d_CONTACT_NODES, P%02d_TOP\n" % (i + 1, i + 2))
        f.write("*Boundary\n")
        f.write("P%02d_PERIMETER, 1, 6, 0.0\n" % len(plates))
        for i in range(len(plates)):
            f.write("P%02d_USED, 1, 2, 0.0\n" % (i + 1))
            f.write("P%02d_USED, 4, 6, 0.0\n" % (i + 1))
        f.write("*Step, name=Compression, nlgeom=YES, inc=1200\n")
        f.write("*Static, stabilize=2.0e-4\n1.0e-4, 1.0, 1.0e-12, 1.0e-3\n")
        f.write("*Cload\n")
        for nid in plates[0]["used"]:
            f.write("%d, 3, %.10e\n" % (nid, nodal_load))
        f.write("*Dload\n")
        for i in range(len(plates)):
            f.write("P%02d_EALL, GRAV, %.10e, 0.0, 0.0, -1.0\n" % (i + 1, GRAVITY))
        f.write("*Output, field, frequency=1\n")
        f.write("*Node Output\nU, RF\n")
        f.write("*Element Output, directions=YES\nS, E\n")
        f.write("*Contact Output, variable=PRESELECT\n")
        f.write("*End Step\n")

    print("Wrote Abaqus input:")
    print(INP_PATH)
    print("Stack order:", STACK_ORDER)
    print("Plates: %d, nodes/plate: %d, elems/plate: %d" % (len(plates), len(plates[0]["nodes"]), len(plates[0]["elems"])))
    print("Layer shifts:", ["%.6e" % v for v in offsets])
    print("Top nodal load: %.6e N/node" % nodal_load)


if __name__ == "__main__":
    write_inp()


