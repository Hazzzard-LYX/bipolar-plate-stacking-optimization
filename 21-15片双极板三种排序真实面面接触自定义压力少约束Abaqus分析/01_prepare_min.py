# -*- coding: utf-8 -*-
from __future__ import print_function

import csv
import math
import os

EXPERIMENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
OUTPUT_DIR = os.path.join(EXPERIMENT_DIR, "outputs")
PROJECT_ROOT = os.path.abspath(os.path.join(EXPERIMENT_DIR, os.pardir, os.pardir))

JOB_NAME = "exp21_min_pressure0448_anchor_contact"
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
ENDPLATE_THICKNESS_M = 0.050
NOMINAL_PRESSURE_PA = 0.448e6
TOP_LOAD_N = NOMINAL_PRESSURE_PA * LENGTH_M * WIDTH_M
TOP_DISPLACEMENT_M = -0.0125
GRAVITY = 9.8
CONTACT_STIFFNESS_PA_PER_M = 5.0e7
WEAK_U3_STIFFNESS_N_PER_M = 1.0
INITIAL_CONTACT_GAP_M = 1.0e-5
SURFACE_E = 0.5e9
SURFACE_NU = 0.34
SURFACE_RHO = 4500.0
TOP_ENDPLATE_RP = 9300001
BOTTOM_ENDPLATE_RP = 9300002


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
    grid = [[0.0 for _ in range(RAW_NX)] for _ in range(RAW_NY)]
    for k, row in enumerate(rows):
        j = k // RAW_NX
        i = k % RAW_NX
        grid[j][i] = float(row["z_mm"]) / 1000.0
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


def build_rect_mesh(name, node_base, elem_base, z_mid, plate_no=None):
    xs = [(i / float(NODES_X - 1) - 0.5) * LENGTH_M for i in range(NODES_X)]
    ys = [(j / float(NODES_Y - 1) - 0.5) * WIDTH_M for j in range(NODES_Y)]
    nodes = []
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            nid = node_base + j * NODES_X + i + 1
            nodes.append((nid, x, y, z_mid))
    elems = []
    for j in range(GRID_CELLS_Y):
        for i in range(GRID_CELLS_X):
            n1 = node_base + j * NODES_X + i + 1
            n2 = node_base + j * NODES_X + i + 2
            n3 = node_base + (j + 1) * NODES_X + i + 2
            n4 = node_base + (j + 1) * NODES_X + i + 1
            elems.append((elem_base + len(elems) + 1, n1, n2, n3, n4))
    used = [n[0] for n in nodes]
    perim = []
    for j in range(NODES_Y):
        for i in range(NODES_X):
            if j in (0, NODES_Y - 1) or i in (0, NODES_X - 1):
                perim.append(node_base + j * NODES_X + i + 1)
    return {"name": name, "plate_no": plate_no, "nodes": nodes, "elems": elems, "used": used, "perim": perim}


def build_plate_mesh(grid, stack_index, plate_no, z_shift):
    xs = [(i / float(NODES_X - 1) - 0.5) * LENGTH_M for i in range(NODES_X)]
    ys = [(j / float(NODES_Y - 1) - 0.5) * WIDTH_M for j in range(NODES_Y)]
    node_base = 100000 * (stack_index + 1)
    elem_base = 100000 * (stack_index + 1)
    mesh = build_rect_mesh("P%02d" % (stack_index + 1), node_base, elem_base, 0.0, plate_no)
    mesh["nodes"] = []
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            nid = node_base + j * NODES_X + i + 1
            mesh["nodes"].append((nid, x, y, z_shift + interpolate_z(grid, x, y)))
    return mesh


def write_list(f, values, per_line=16):
    values = list(values)
    for i in range(0, len(values), per_line):
        f.write(", ".join(str(v) for v in values[i : i + per_line]) + "\n")


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
        shift = 0.0 if i == 0 else place_lower_against_upper(plates[-1], grid)
        shifts.append(shift)
        plates.append(build_plate_mesh(grid, i, STACK_ORDER[i], shift))
    return plates, shifts


def min_z(mesh):
    return min(row[3] for row in mesh["nodes"])


def max_z(mesh):
    return max(row[3] for row in mesh["nodes"])


def write_inp():
    ensure_dir(OUTPUT_DIR)
    grids = [read_plate_grid(p) for p in STACK_ORDER]
    plates, offsets = build_stack_meshes(grids)
    top_z = max_z(plates[0]) + 0.5 * PLATE_THICKNESS_M
    bottom_z = min_z(plates[-1]) - 0.5 * PLATE_THICKNESS_M
    top_end = build_rect_mesh("EP_TOP", 9100000, 9100000, top_z)
    bottom_end = build_rect_mesh("EP_BOTTOM", 9200000, 9200000, bottom_z)
    top_rp = (TOP_ENDPLATE_RP, 0.0, 0.0, top_z + 0.5 * ENDPLATE_THICKNESS_M)
    bottom_rp = (BOTTOM_ENDPLATE_RP, 0.0, 0.0, bottom_z - 0.5 * ENDPLATE_THICKNESS_M)

    with open(INP_PATH, "w") as f:
        f.write("*Heading\n")
        f.write("Experiment 21 - min-distance-sum surface-to-surface contact Abaqus model\n")
        f.write("*Preprint, echo=NO, model=NO, history=NO, contact=NO\n")
        f.write("** Stack order top-to-bottom: %s\n" % " -> ".join(str(p) for p in STACK_ORDER))
        f.write("*Node\n")
        for mesh in [top_end] + plates + [bottom_end]:
            for row in mesh["nodes"]:
                f.write("%d, %.10e, %.10e, %.10e\n" % row)
        f.write("%d, %.10e, %.10e, %.10e\n" % top_rp)
        f.write("%d, %.10e, %.10e, %.10e\n" % bottom_rp)
        f.write("*Element, type=R3D4, elset=EP_TOP_EALL\n")
        for row in top_end["elems"]:
            f.write("%d, %d, %d, %d, %d\n" % row)
        for i, plate in enumerate(plates):
            f.write("*Element, type=S4R, elset=P%02d_EALL\n" % (i + 1))
            for row in plate["elems"]:
                f.write("%d, %d, %d, %d, %d\n" % row)
        f.write("*Element, type=R3D4, elset=EP_BOTTOM_EALL\n")
        for row in bottom_end["elems"]:
            f.write("%d, %d, %d, %d, %d\n" % row)

        for prefix, mesh in [("EP_TOP", top_end), ("EP_BOTTOM", bottom_end)]:
            f.write("*Nset, nset=%s_USED\n" % prefix); write_list(f, mesh["used"])
            f.write("*Nset, nset=%s_PERIMETER\n" % prefix); write_list(f, mesh["perim"])
            f.write("*Elset, elset=%s_EALL\n" % prefix); write_list(f, [e[0] for e in mesh["elems"]])
        f.write("*Nset, nset=EP_TOP_RP\n%d\n" % TOP_ENDPLATE_RP)
        f.write("*Nset, nset=EP_BOTTOM_RP\n%d\n" % BOTTOM_ENDPLATE_RP)
        for i, plate in enumerate(plates):
            f.write("*Nset, nset=P%02d_USED\n" % (i + 1)); write_list(f, plate["used"])
            f.write("*Nset, nset=P%02d_PERIMETER\n" % (i + 1)); write_list(f, plate["perim"])
            anchor_a = 100000 * (i + 1) + 4 * NODES_X + 8 + 1
            anchor_b = 100000 * (i + 1) + 4 * NODES_X + 16 + 1
            f.write("*Nset, nset=P%02d_ANCHOR_A\n%d\n" % (i + 1, anchor_a))
            f.write("*Nset, nset=P%02d_ANCHOR_B\n%d\n" % (i + 1, anchor_b))
            f.write("*Elset, elset=P%02d_EALL\n" % (i + 1)); write_list(f, [e[0] for e in plate["elems"]])

        f.write("*Material, name=Ti_Bipolar_Plate\n")
        f.write("*Density\n%.10e,\n" % SURFACE_RHO)
        f.write("*Elastic\n%.10e, %.6f\n" % (SURFACE_E, SURFACE_NU))
        for i in range(len(plates)):
            f.write("*Shell Section, elset=P%02d_EALL, material=Ti_Bipolar_Plate\n" % (i + 1))
            f.write("%.10e, 5\n" % PLATE_THICKNESS_M)
        f.write("*Rigid Body, ref node=EP_TOP_RP, elset=EP_TOP_EALL\n")
        f.write("*Rigid Body, ref node=EP_BOTTOM_RP, elset=EP_BOTTOM_EALL\n")

        f.write("*Element, type=SPRING1, elset=WEAK_U3_SPRINGS\n")
        spring_id = 90000001
        for plate in plates[:-1]:
            for nid in plate["used"]:
                f.write("%d, %d\n" % (spring_id, nid))
                spring_id += 1
        f.write("*Spring, elset=WEAK_U3_SPRINGS\n3\n%.10e\n" % WEAK_U3_STIFFNESS_N_PER_M)

        f.write("*Surface, type=ELEMENT, name=EP_TOP_BOTTOM\nEP_TOP_EALL, SNEG\n")
        f.write("*Surface, type=ELEMENT, name=EP_BOTTOM_TOP\nEP_BOTTOM_EALL, SPOS\n")
        for i in range(len(plates)):
            f.write("*Surface, type=ELEMENT, name=P%02d_TOP\nP%02d_EALL, SPOS\n" % (i + 1, i + 1))
            f.write("*Surface, type=ELEMENT, name=P%02d_BOTTOM\nP%02d_EALL, SNEG\n" % (i + 1, i + 1))
            f.write("*Surface, type=NODE, name=P%02d_CONTACT_NODES\nP%02d_USED, 1.0\n" % (i + 1, i + 1))
        f.write("*Surface Interaction, name=LINEAR_FRICTIONLESS\n")
        f.write("*Surface Behavior, pressure-overclosure=LINEAR\n%.10e,\n" % CONTACT_STIFFNESS_PA_PER_M)
        f.write("*Friction\n0.0,\n")
        f.write("*Contact Pair, interaction=LINEAR_FRICTIONLESS, small sliding\n")
        f.write("P01_TOP, EP_TOP_BOTTOM\n")
        for i in range(len(plates) - 1):
            f.write("*Contact Pair, interaction=LINEAR_FRICTIONLESS, small sliding\n")
            f.write("P%02d_BOTTOM, P%02d_TOP\n" % (i + 1, i + 2))
        f.write("*Contact Pair, interaction=LINEAR_FRICTIONLESS, small sliding\n")
        f.write("P%02d_BOTTOM, EP_BOTTOM_TOP\n" % len(plates))

        f.write("*Boundary\n")
        f.write("EP_TOP_RP, 1, 2, 0.0\n")
        f.write("EP_TOP_RP, 4, 6, 0.0\n")
        f.write("EP_BOTTOM_RP, 1, 6, 0.0\n")
        for i in range(len(plates)):
            f.write("P%02d_ANCHOR_A, 1, 2, 0.0\n" % (i + 1))
            f.write("P%02d_ANCHOR_B, 2, 2, 0.0\n" % (i + 1))

        f.write("*Step, name=Compression, nlgeom=YES, inc=15000\n")
        f.write("*Static, stabilize=2.0e-2\n5.0e-4, 1.0, 1.0e-12, 2.0e-3\n")
        f.write("*Cload\n")
        f.write("EP_TOP_RP, 3, %.10e\n" % (-TOP_LOAD_N))
        f.write("*Dload\n")
        for i in range(len(plates)):
            f.write("P%02d_EALL, GRAV, %.10e, 0.0, 0.0, -1.0\n" % (i + 1, GRAVITY))
        f.write("*Output, field, time interval=0.1\n")
        f.write("*Node Output\nU, RF\n")
        f.write("*Element Output, directions=YES\nS, E\n")
        f.write("*Contact Output, variable=PRESELECT\n")
        f.write("*End Step\n")

    print("Wrote Abaqus input:")
    print(INP_PATH)
    print("Stack order:", STACK_ORDER)
    print("Endplate thickness: %.6e m" % ENDPLATE_THICKNESS_M)
    print("Nominal pressure: %.6e Pa" % NOMINAL_PRESSURE_PA)
    print("Top load: %.6e N" % TOP_LOAD_N)


if __name__ == "__main__":
    write_inp()








