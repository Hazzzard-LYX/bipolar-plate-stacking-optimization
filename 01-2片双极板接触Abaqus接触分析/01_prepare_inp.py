# -*- coding: utf-8 -*-
"""
Experiment 1: two real bipolar plates contact analysis, Abaqus input generator.

This script is intentionally plain Python so it can run outside Abaqus. It reads
plate 1 and plate 2 height grids, downsamples them, places them using the same
zero-gap stack convention as the original project, and writes an Abaqus/Standard
input file into ../outputs.

Units in the generated Abaqus model:
  length: m
  force: N
  stress: Pa
  density: kg/m^3
"""
from __future__ import print_function

import csv
import math
import os


EXPERIMENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
OUTPUT_DIR = os.path.join(EXPERIMENT_DIR, "outputs")

PROJECT_ROOT = os.path.abspath(os.path.join(EXPERIMENT_DIR, os.pardir, os.pardir))


def find_data_dir():
    for root, dirs, _files in os.walk(PROJECT_ROOT):
        if "820x345mm" in root:
            csv_count = len([n for n in os.listdir(root) if n.lower().endswith(".csv")])
            if csv_count >= 15:
                return root
    raise RuntimeError("Cannot find real plate height grid directory containing 820x345mm CSV files.")


DATA_DIR = find_data_dir()
JOB_NAME = "exp1_plate01_plate02_contact"
INP_PATH = os.path.join(OUTPUT_DIR, JOB_NAME + ".inp")

# Original project defaults.
LENGTH_M = 0.820
WIDTH_M = 0.345
RAW_NX = 201
RAW_NY = 85
PLATE_THICKNESS_M = 0.0002
TOP_LOAD_N = 100000.0
GRAVITY = 9.8
CONTACT_STIFFNESS_PA_PER_M = 5.0e8

SURFACE_E = 110.0e9
SURFACE_NU = 0.34
SURFACE_RHO = 4500.0

# Keep this small for the first Abaqus contact experiment. Increase after the
# two-plate workflow is stable.
DOWNSAMPLED_NX = 41
DOWNSAMPLED_NY = 18

# The first Abaqus baseline keeps the shell mesh connected. Applying the
# original opening mask on this coarse grid can split the plate into many
# disconnected islands, which creates rigid-body modes during contact closure.
APPLY_OPENING_MASK = False
INITIAL_CONTACT_GAP_M = 1.0e-5


def ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def linspace_indices(n_src, n_dst):
    if n_dst <= 1:
        return [0]
    out = []
    for k in range(n_dst):
        idx = int(round(k * (n_src - 1) / float(n_dst - 1)))
        if out and idx <= out[-1]:
            idx = out[-1] + 1
        out.append(min(idx, n_src - 1))
    return out


def read_plate_grid(plate_index):
    matches = [name for name in os.listdir(DATA_DIR) if name.lower().endswith(".csv") and ("_%02d_" % plate_index) in name]
    if not matches:
        raise RuntimeError("Cannot find CSV for plate %02d in %s" % (plate_index, DATA_DIR))
    path = os.path.join(DATA_DIR, sorted(matches)[0])
    values = []
    with open(path, "rb") as f:
        text = f.read()
    if text.startswith(b"\xef\xbb\xbf"):
        text = text[3:]
    rows = text.decode("utf-8").splitlines()
    reader = csv.DictReader(rows)
    for row in reader:
        values.append(float(row["z_mm"]) / 1000.0)
    if len(values) != RAW_NX * RAW_NY:
        raise RuntimeError("Unexpected grid size for plate %s: %s values" % (plate_index, len(values)))
    grid = []
    for j in range(RAW_NY):
        row = values[j * RAW_NX : (j + 1) * RAW_NX]
        # Match the original project: rendered real plates mirror the source grid along X.
        grid.append(list(reversed(row)))
    return grid


def is_in_opening(x_m, y_m):
    """Approximate openings with the same coarse ranges used by the original code.

    To keep this experiment script readable, we import the original project's
    opening-mask function when available. If that import ever fails in a bare
    Abaqus environment, we fall back to a solid rectangular plate.
    """
    if not APPLY_OPENING_MASK:
        return False
    try:
        import sys

        program_dir = os.path.join(SOURCE_PROJECT, "绋嬪簭")
        if program_dir not in sys.path:
            sys.path.insert(0, program_dir)
        from contact_area_tolerance_sweep import is_in_real_bipolar_plate_opening_xy

        return bool(is_in_real_bipolar_plate_opening_xy(float(x_m), float(y_m)))
    except Exception:
        return False


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


def plate_z_extents(grid):
    z_min = None
    z_max = None
    for j in range(RAW_NY):
        y = (j / float(RAW_NY - 1) - 0.5) * WIDTH_M
        for i in range(RAW_NX):
            x = (i / float(RAW_NX - 1) - 0.5) * LENGTH_M
            if is_in_opening(x, y):
                continue
            z_mid = grid[j][i]
            bot = z_mid - PLATE_THICKNESS_M * 0.5
            top = z_mid + PLATE_THICKNESS_M * 0.5
            z_min = bot if z_min is None else min(z_min, bot)
            z_max = top if z_max is None else max(z_max, top)
    if z_min is None or z_max is None:
        raise RuntimeError("No solid points found for plate.")
    return z_min, z_max


def stack_world_offsets(grids):
    z_mins = []
    z_maxs = []
    base_z = []
    for grid in grids:
        zmin, zmax = plate_z_extents(grid)
        z_mins.append(zmin)
        z_maxs.append(zmax)
        base_z.append(-(zmin + zmax) * 0.5)

    offsets = [0.0 for _ in grids]
    for i in range(1, len(grids)):
        offsets[i] = offsets[i - 1] + z_mins[i - 1] - z_maxs[i]
    anchor = -offsets[-1] if offsets else 0.0
    return [base_z[i] + offsets[i] + anchor for i in range(len(grids))]


def build_plate_mesh(grid, plate_id, z_shift):
    ix = linspace_indices(RAW_NX, DOWNSAMPLED_NX)
    iy = linspace_indices(RAW_NY, DOWNSAMPLED_NY)
    xs = [(i / float(RAW_NX - 1) - 0.5) * LENGTH_M for i in ix]
    ys = [(j / float(RAW_NY - 1) - 0.5) * WIDTH_M for j in iy]

    node_base = 100000 * plate_id
    elem_base = 100000 * plate_id
    nodes = []
    node_id = {}
    for jj, y in enumerate(ys):
        for ii, x in enumerate(xs):
            nid = node_base + jj * DOWNSAMPLED_NX + ii + 1
            node_id[(jj, ii)] = nid
            z = z_shift + interpolate_z(grid, x, y)
            nodes.append((nid, x, y, z))

    elements = []
    used_nodes = set()
    for jj in range(DOWNSAMPLED_NY - 1):
        for ii in range(DOWNSAMPLED_NX - 1):
            xc = 0.25 * (xs[ii] + xs[ii + 1] + xs[ii] + xs[ii + 1])
            yc = 0.25 * (ys[jj] + ys[jj] + ys[jj + 1] + ys[jj + 1])
            if is_in_opening(xc, yc):
                continue
            n1 = node_id[(jj, ii)]
            n2 = node_id[(jj, ii + 1)]
            n3 = node_id[(jj + 1, ii + 1)]
            n4 = node_id[(jj + 1, ii)]
            eid = elem_base + len(elements) + 1
            elements.append((eid, n1, n2, n3, n4))
            used_nodes.update([n1, n2, n3, n4])

    perimeter_nodes = []
    for jj in range(DOWNSAMPLED_NY):
        for ii in range(DOWNSAMPLED_NX):
            if jj in (0, DOWNSAMPLED_NY - 1) or ii in (0, DOWNSAMPLED_NX - 1):
                nid = node_id[(jj, ii)]
                if nid in used_nodes:
                    perimeter_nodes.append(nid)
    return nodes, elements, sorted(used_nodes), sorted(set(perimeter_nodes))


def write_list(f, values, per_line=16):
    values = list(values)
    for i in range(0, len(values), per_line):
        f.write(", ".join(str(v) for v in values[i : i + per_line]) + "\n")


def nearest_used_node(nodes, used_nodes, target_x, target_y):
    used = set(used_nodes)
    best = None
    best_dist2 = None
    for nid, x, y, _z in nodes:
        if nid not in used:
            continue
        dist2 = (x - target_x) ** 2 + (y - target_y) ** 2
        if best is None or dist2 < best_dist2:
            best = nid
            best_dist2 = dist2
    if best is None:
        raise RuntimeError("Cannot find a used node for anchor constraint.")
    return best


def align_upper_plate_to_mesh_gap(p1_nodes, p1_used, grid2, p2_shift):
    used = set(p1_used)
    min_gap = None
    for nid, x, y, z in p1_nodes:
        if nid not in used:
            continue
        lower_top_z = p2_shift + interpolate_z(grid2, x, y) + PLATE_THICKNESS_M * 0.5
        gap = z - lower_top_z
        min_gap = gap if min_gap is None else min(min_gap, gap)
    if min_gap is None:
        raise RuntimeError("Cannot compute upper/lower mesh gap.")
    dz = INITIAL_CONTACT_GAP_M - min_gap
    shifted = [(nid, x, y, z + dz) for nid, x, y, z in p1_nodes]
    return shifted, min_gap, dz


def write_inp():
    ensure_dir(OUTPUT_DIR)
    grid1 = read_plate_grid(1)
    grid2 = read_plate_grid(2)
    shifts = stack_world_offsets([grid1, grid2])

    p1_nodes, p1_elems, p1_used, p1_perim = build_plate_mesh(grid1, 1, shifts[0])
    p2_nodes, p2_elems, p2_used, p2_perim = build_plate_mesh(grid2, 2, shifts[1])
    p1_nodes, mesh_min_gap, upper_z_adjust = align_upper_plate_to_mesh_gap(
        p1_nodes, p1_used, grid2, shifts[1]
    )
    p1_anchor_a = nearest_used_node(p1_nodes, p1_used, 0.0, 0.0)
    p1_anchor_b = nearest_used_node(p1_nodes, p1_used, LENGTH_M * 0.25, 0.0)
    nodal_load = -TOP_LOAD_N / float(len(p1_used))

    with open(INP_PATH, "w") as f:
        f.write("*Heading\n")
        f.write("Experiment 1 - Plate 1 / Plate 2 contact, generated from project CSV grids\n")
        f.write("*Preprint, echo=NO, model=NO, history=NO, contact=NO\n")
        f.write("** Units: m, N, Pa, kg/m3\n")
        f.write("** Downsampled mesh: %d x %d nodes per plate\n" % (DOWNSAMPLED_NX, DOWNSAMPLED_NY))
        f.write("** Top load: %.6g N distributed to upper plate used nodes\n" % TOP_LOAD_N)
        f.write("** Upper plate z-adjust for Abaqus mesh initial gap: %.6g m\n" % upper_z_adjust)
        f.write("*Node\n")
        for row in p1_nodes + p2_nodes:
            f.write("%d, %.10e, %.10e, %.10e\n" % row)
        f.write("*Element, type=S4R, elset=P1_EALL\n")
        for row in p1_elems:
            f.write("%d, %d, %d, %d, %d\n" % row)
        f.write("*Element, type=S4R, elset=P2_EALL\n")
        for row in p2_elems:
            f.write("%d, %d, %d, %d, %d\n" % row)
        f.write("*Nset, nset=P1_USED\n")
        write_list(f, p1_used)
        f.write("*Nset, nset=P2_USED\n")
        write_list(f, p2_used)
        f.write("*Nset, nset=P2_PERIMETER\n")
        write_list(f, p2_perim)
        f.write("*Nset, nset=P1_ANCHOR_A\n")
        write_list(f, [p1_anchor_a])
        f.write("*Nset, nset=P1_ANCHOR_B\n")
        write_list(f, [p1_anchor_b])
        f.write("*Elset, elset=P1_EALL\n")
        write_list(f, [e[0] for e in p1_elems])
        f.write("*Elset, elset=P2_EALL\n")
        write_list(f, [e[0] for e in p2_elems])
        f.write("*Material, name=Ti_Bipolar_Plate\n")
        f.write("*Density\n")
        f.write("%.10e,\n" % SURFACE_RHO)
        f.write("*Elastic\n")
        f.write("%.10e, %.6f\n" % (SURFACE_E, SURFACE_NU))
        f.write("*Shell Section, elset=P1_EALL, material=Ti_Bipolar_Plate\n")
        f.write("%.10e, 5\n" % PLATE_THICKNESS_M)
        f.write("*Shell Section, elset=P2_EALL, material=Ti_Bipolar_Plate\n")
        f.write("%.10e, 5\n" % PLATE_THICKNESS_M)
        f.write("*Surface, type=ELEMENT, name=P1_TOP\n")
        f.write("P1_EALL, SPOS\n")
        f.write("*Surface, type=ELEMENT, name=P1_BOTTOM\n")
        f.write("P1_EALL, SNEG\n")
        f.write("*Surface, type=ELEMENT, name=P2_TOP\n")
        f.write("P2_EALL, SPOS\n")
        f.write("*Surface, type=NODE, name=P1_CONTACT_NODES\n")
        f.write("P1_USED, 1.0\n")
        f.write("*Surface Interaction, name=FRICTIONLESS_HARD\n")
        f.write("*Surface Behavior, pressure-overclosure=LINEAR\n")
        f.write("%.10e,\n" % CONTACT_STIFFNESS_PA_PER_M)
        f.write("*Friction\n")
        f.write("0.0,\n")
        f.write("*Contact Pair, interaction=FRICTIONLESS_HARD, type=NODE TO SURFACE, small sliding\n")
        # Use upper-plate nodes against the lower-plate top shell surface for
        # the first Abaqus baseline. This avoids the severe shell-to-shell
        # initialization issue while still solving normal contact pressure.
        f.write("P1_CONTACT_NODES, P2_TOP\n")
        f.write("*Boundary\n")
        f.write("P2_PERIMETER, 1, 6, 0.0\n")
        # Minimal in-plane anchors keep the upper plate from drifting without
        # overconstraining every contact node against the contact normal.
        f.write("P1_ANCHOR_A, 1, 2, 0.0\n")
        f.write("P1_ANCHOR_B, 2, 2, 0.0\n")
        f.write("P1_USED, 4, 6, 0.0\n")
        f.write("P2_USED, 4, 6, 0.0\n")
        f.write("*Step, name=Compression, nlgeom=YES, inc=1200\n")
        # The upper plate has an initial geometric gap before the 100 kN load
        # closes contact. Automatic stabilization avoids a free-flight singular
        # tangent in the first few increments of this baseline model.
        f.write("*Static, stabilize=2.0e-4\n")
        f.write("1.0e-5, 1.0, 1.0e-12, 1.0e-3\n")
        f.write("*Cload\n")
        for nid in p1_used:
            f.write("%d, 3, %.10e\n" % (nid, nodal_load))
        f.write("*Dload\n")
        f.write("P1_EALL, GRAV, %.10e, 0.0, 0.0, -1.0\n" % GRAVITY)
        f.write("P2_EALL, GRAV, %.10e, 0.0, 0.0, -1.0\n" % GRAVITY)
        f.write("*Output, field, frequency=1\n")
        f.write("*Node Output\n")
        f.write("U, RF\n")
        f.write("*Element Output, directions=YES\n")
        f.write("S, E\n")
        # Abaqus/Standard contact-pair output availability depends on the
        # contact formulation. PRESELECT lets Abaqus choose valid contact
        # variables for this shell-to-shell contact pair; the extractor then
        # reports whichever pressure/opening fields are present in the ODB.
        f.write("*Contact Output, variable=PRESELECT\n")
        f.write("*Output, history, frequency=1\n")
        f.write("*Energy Output\n")
        f.write("ALLIE, ALLSE, ALLWK\n")
        f.write("*End Step\n")

    print("Wrote Abaqus input:")
    print(INP_PATH)
    print("Plate 1 elements: %d, used nodes: %d" % (len(p1_elems), len(p1_used)))
    print("Plate 2 elements: %d, used nodes: %d" % (len(p2_elems), len(p2_used)))
    print("Upper plate anchor nodes: %d, %d" % (p1_anchor_a, p1_anchor_b))
    print("Original Abaqus mesh minimum node/top gap: %.6e m" % mesh_min_gap)
    print("Upper plate z-adjust: %.6e m" % upper_z_adjust)
    print("Distributed top nodal load: %.6e N/node" % nodal_load)


if __name__ == "__main__":
    write_inp()






