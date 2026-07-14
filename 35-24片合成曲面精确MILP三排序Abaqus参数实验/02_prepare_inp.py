# -*- coding: utf-8 -*-
from __future__ import print_function

import csv
import json
import math
import os
import sys

import config as cfg


HERE = os.path.dirname(os.path.abspath(__file__))
EXPERIMENT_DIR = os.path.abspath(os.path.join(HERE, os.pardir))
OUTPUT_DIR = os.path.join(EXPERIMENT_DIR, "outputs")
DATA_DIR = os.path.join(OUTPUT_DIR, "generated_surfaces_820x345mm")
ORDERS_PATH = os.path.join(OUTPUT_DIR, "stack_orders.json")

LENGTH_M = 0.820
WIDTH_M = 0.345
RAW_NX = 201
RAW_NY = 85
NODES_X = cfg.GRID_CELLS_X + 1
NODES_Y = cfg.GRID_CELLS_Y + 1
TOP_ENDPLATE_RP = 9300001
BOTTOM_ENDPLATE_RP = 9300002


def ensure_inputs():
    if not os.path.isfile(ORDERS_PATH) or not os.path.isdir(DATA_DIR):
        raise RuntimeError("Run 01_generate_surfaces_and_orders.py before preparing input files.")


def read_orders():
    with open(ORDERS_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def read_plate_grid(plate_index):
    token = "_%03d_" % plate_index
    matches = [name for name in os.listdir(DATA_DIR) if name.lower().endswith(".csv") and token in name]
    if not matches:
        raise RuntimeError("Cannot find generated CSV for plate %03d." % plate_index)
    path = os.path.join(DATA_DIR, sorted(matches)[0])
    grid = [[0.0 for _ in range(RAW_NX)] for _ in range(RAW_NY)]
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != RAW_NX * RAW_NY:
        raise RuntimeError("Unexpected row count in %s: %d" % (path, len(rows)))
    for index, row in enumerate(rows):
        j = index // RAW_NX
        i = index % RAW_NX
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
            nodes.append((node_base + j * NODES_X + i + 1, x, y, z_mid))
    elements = []
    for j in range(cfg.GRID_CELLS_Y):
        for i in range(cfg.GRID_CELLS_X):
            n1 = node_base + j * NODES_X + i + 1
            n2 = n1 + 1
            n4 = node_base + (j + 1) * NODES_X + i + 1
            n3 = n4 + 1
            elements.append((elem_base + len(elements) + 1, n1, n2, n3, n4))
    used = [row[0] for row in nodes]
    perimeter = []
    for j in range(NODES_Y):
        for i in range(NODES_X):
            if i in (0, NODES_X - 1) or j in (0, NODES_Y - 1):
                perimeter.append(node_base + j * NODES_X + i + 1)
    return {
        "name": name,
        "plate_no": plate_no,
        "node_base": node_base,
        "nodes": nodes,
        "elems": elements,
        "used": used,
        "perimeter": perimeter,
    }


def build_plate_mesh(grid, stack_index, plate_no, z_shift):
    node_base = 100000 * (stack_index + 1)
    elem_base = node_base
    mesh = build_rect_mesh("P%03d" % (stack_index + 1), node_base, elem_base, 0.0, plate_no)
    mesh["nodes"] = []
    for j in range(NODES_Y):
        y = (j / float(NODES_Y - 1) - 0.5) * WIDTH_M
        for i in range(NODES_X):
            x = (i / float(NODES_X - 1) - 0.5) * LENGTH_M
            nid = node_base + j * NODES_X + i + 1
            mesh["nodes"].append((nid, x, y, z_shift + interpolate_z(grid, x, y)))
    return mesh


def place_lower_against_upper(upper_plate, lower_grid):
    best_shift = None
    for _nid, x, y, upper_z in upper_plate["nodes"]:
        upper_bottom = upper_z - 0.5 * cfg.PLATE_THICKNESS_M
        lower_top = interpolate_z(lower_grid, x, y) + 0.5 * cfg.PLATE_THICKNESS_M
        candidate = upper_bottom - lower_top - cfg.INITIAL_CONTACT_GAP_M
        best_shift = candidate if best_shift is None else min(best_shift, candidate)
    return best_shift


def build_stack(grids, order):
    plates = []
    shifts = []
    for index, grid in enumerate(grids):
        shift = 0.0 if index == 0 else place_lower_against_upper(plates[-1], grid)
        shifts.append(shift)
        plates.append(build_plate_mesh(grid, index, order[index], shift))
    return plates, shifts


def write_list(handle, values, per_line=16):
    values = list(values)
    for index in range(0, len(values), per_line):
        handle.write(", ".join(str(value) for value in values[index:index + per_line]) + "\n")


def node_at(plate, i, j):
    return plate["node_base"] + j * NODES_X + i + 1


def constraint_sets(plate):
    mode = cfg.CONSTRAINT_MODE
    if mode == "two_anchor":
        return [
            ("ANCHOR_A", [node_at(plate, NODES_X // 2, NODES_Y // 2)], 1, 2),
            ("ANCHOR_B", [node_at(plate, NODES_X - 1, NODES_Y // 2)], 2, 2),
        ]
    if mode == "corner_kinematic":
        return [
            ("CORNER_A", [node_at(plate, 0, 0)], 1, 2),
            ("CORNER_B", [node_at(plate, NODES_X - 1, 0)], 2, 2),
        ]
    if mode == "three_point":
        return [
            ("POINT_A", [node_at(plate, 0, 0)], 1, 2),
            ("POINT_B", [node_at(plate, NODES_X - 1, 0)], 2, 2),
            ("POINT_C", [node_at(plate, 0, NODES_Y - 1)], 1, 1),
        ]
    if mode == "four_corner":
        corners = [
            node_at(plate, 0, 0),
            node_at(plate, NODES_X - 1, 0),
            node_at(plate, 0, NODES_Y - 1),
            node_at(plate, NODES_X - 1, NODES_Y - 1),
        ]
        return [("FOUR_CORNERS", corners, 1, 2)]
    if mode == "edge_guide":
        return [("EDGE_GUIDE", plate["perimeter"], 1, 2)]
    raise RuntimeError("Unknown CONSTRAINT_MODE: %s" % mode)


def write_input(case, order):
    if len(order) != cfg.PLATE_COUNT:
        raise RuntimeError("Order length does not match PLATE_COUNT.")
    grids = [read_plate_grid(plate_no) for plate_no in order]
    plates, offsets = build_stack(grids, order)
    top_z = max(node[3] for node in plates[0]["nodes"]) + 0.5 * cfg.PLATE_THICKNESS_M
    bottom_z = min(node[3] for node in plates[-1]["nodes"]) - 0.5 * cfg.PLATE_THICKNESS_M
    top_end = build_rect_mesh("EP_TOP", 9100000, 9100000, top_z)
    bottom_end = build_rect_mesh("EP_BOTTOM", 9200000, 9200000, bottom_z)
    top_rp = (TOP_ENDPLATE_RP, 0.0, 0.0, top_z + 0.5 * cfg.ENDPLATE_THICKNESS_M)
    bottom_rp = (BOTTOM_ENDPLATE_RP, 0.0, 0.0, bottom_z - 0.5 * cfg.ENDPLATE_THICKNESS_M)
    top_load = cfg.NOMINAL_PRESSURE_PA * LENGTH_M * WIDTH_M
    top_mass = LENGTH_M * WIDTH_M * cfg.ENDPLATE_THICKNESS_M * cfg.ENDPLATE_DENSITY
    job_name = "exp%d_%s_%dplates" % (cfg.EXPERIMENT_ID, case, cfg.PLATE_COUNT)
    inp_path = os.path.join(OUTPUT_DIR, job_name + ".inp")

    with open(inp_path, "w", encoding="ascii", newline="") as handle:
        handle.write("*Heading\n")
        handle.write("Experiment %d %s: %s\n" % (cfg.EXPERIMENT_ID, case, cfg.DESCRIPTION))
        handle.write("*Preprint, echo=NO, model=NO, history=NO, contact=NO\n")
        handle.write("** Stack order: %s\n" % " -> ".join(map(str, order)))
        handle.write("*Node\n")
        for mesh in [top_end] + plates + [bottom_end]:
            for row in mesh["nodes"]:
                handle.write("%d, %.10e, %.10e, %.10e\n" % row)
        handle.write("%d, %.10e, %.10e, %.10e\n" % top_rp)
        handle.write("%d, %.10e, %.10e, %.10e\n" % bottom_rp)

        handle.write("*Element, type=R3D4, elset=EP_TOP_EALL\n")
        for row in top_end["elems"]:
            handle.write("%d, %d, %d, %d, %d\n" % row)
        for index, plate in enumerate(plates, start=1):
            handle.write("*Element, type=S4, elset=P%03d_EALL\n" % index)
            for row in plate["elems"]:
                handle.write("%d, %d, %d, %d, %d\n" % row)
        handle.write("*Element, type=R3D4, elset=EP_BOTTOM_EALL\n")
        for row in bottom_end["elems"]:
            handle.write("%d, %d, %d, %d, %d\n" % row)
        handle.write("*Element, type=MASS, elset=EP_TOP_MASS\n9400001, %d\n" % TOP_ENDPLATE_RP)
        handle.write("*Mass, elset=EP_TOP_MASS\n%.10e\n" % top_mass)

        for prefix, mesh in (("EP_TOP", top_end), ("EP_BOTTOM", bottom_end)):
            handle.write("*Nset, nset=%s_USED\n" % prefix)
            write_list(handle, mesh["used"])
            handle.write("*Elset, elset=%s_EALL\n" % prefix)
            write_list(handle, [row[0] for row in mesh["elems"]])
        handle.write("*Nset, nset=EP_TOP_RP\n%d\n" % TOP_ENDPLATE_RP)
        handle.write("*Nset, nset=EP_BOTTOM_RP\n%d\n" % BOTTOM_ENDPLATE_RP)

        all_constraints = []
        for index, plate in enumerate(plates, start=1):
            handle.write("*Nset, nset=P%03d_USED\n" % index)
            write_list(handle, plate["used"])
            handle.write("*Elset, elset=P%03d_EALL\n" % index)
            write_list(handle, [row[0] for row in plate["elems"]])
            for suffix, nodes, first_dof, last_dof in constraint_sets(plate):
                set_name = "P%03d_%s" % (index, suffix)
                handle.write("*Nset, nset=%s\n" % set_name)
                write_list(handle, nodes)
                all_constraints.append((set_name, first_dof, last_dof))

        handle.write("*Material, name=BIPOLAR_PLATE\n")
        handle.write("*Density\n%.10e,\n" % cfg.SURFACE_RHO)
        handle.write("*Elastic\n%.10e, %.8f\n" % (cfg.SURFACE_E, cfg.SURFACE_NU))
        handle.write("*Damping, alpha=%.10e\n" % cfg.DAMPING_ALPHA)
        for index in range(1, len(plates) + 1):
            handle.write("*Shell Section, elset=P%03d_EALL, material=BIPOLAR_PLATE\n" % index)
            handle.write("%.10e, 5\n" % cfg.PLATE_THICKNESS_M)
        handle.write("*Rigid Body, ref node=EP_TOP_RP, elset=EP_TOP_EALL\n")
        handle.write("*Rigid Body, ref node=EP_BOTTOM_RP, elset=EP_BOTTOM_EALL\n")

        handle.write("*Surface, type=ELEMENT, name=EP_TOP_BOTTOM\nEP_TOP_EALL, SNEG\n")
        handle.write("*Surface, type=ELEMENT, name=EP_BOTTOM_TOP\nEP_BOTTOM_EALL, SPOS\n")
        for index in range(1, len(plates) + 1):
            handle.write("*Surface, type=ELEMENT, name=P%03d_TOP\nP%03d_EALL, SPOS\n" % (index, index))
            handle.write("*Surface, type=ELEMENT, name=P%03d_BOTTOM\nP%03d_EALL, SNEG\n" % (index, index))
        handle.write("*Surface Interaction, name=FRICTIONAL_CONTACT\n")
        handle.write("*Surface Behavior, pressure-overclosure=LINEAR\n%.10e,\n" % cfg.CONTACT_STIFFNESS_PA_PER_M)
        handle.write("*Contact Damping, definition=DAMPING COEFFICIENT\n%.10e\n" % cfg.CONTACT_DAMPING_PA_S_PER_M)
        handle.write("*Friction\n%.8f,\n" % cfg.FRICTION_COEFFICIENT)

        handle.write("*Boundary\n")
        handle.write("EP_TOP_RP, 1, 2, 0.0\nEP_TOP_RP, 4, 6, 0.0\n")
        handle.write("EP_BOTTOM_RP, 1, 6, 0.0\n")
        for set_name, first_dof, last_dof in all_constraints:
            handle.write("%s, %d, %d, 0.0\n" % (set_name, first_dof, last_dof))

        handle.write("*Amplitude, name=SMOOTH_PRESSURE, definition=SMOOTH STEP\n")
        handle.write("0.0, 0.0, %.10e, 1.0, %.10e, 1.0\n" % (cfg.RAMP_TIME_S, cfg.STEP_TIME_S))
        handle.write("*Step, name=Compression, nlgeom=YES\n*Dynamic, Explicit\n, %.10e\n" % cfg.STEP_TIME_S)
        handle.write("*Contact Pair, interaction=FRICTIONAL_CONTACT, small sliding\nP001_TOP, EP_TOP_BOTTOM\n")
        for index in range(1, len(plates)):
            handle.write("*Contact Pair, interaction=FRICTIONAL_CONTACT, small sliding\n")
            handle.write("P%03d_BOTTOM, P%03d_TOP\n" % (index, index + 1))
        handle.write("*Contact Pair, interaction=FRICTIONAL_CONTACT, small sliding\n")
        handle.write("P%03d_BOTTOM, EP_BOTTOM_TOP\n" % len(plates))
        handle.write("*Cload, amplitude=SMOOTH_PRESSURE\nEP_TOP_RP, 3, %.10e\n" % (-top_load))
        handle.write("*Dload, amplitude=SMOOTH_PRESSURE\n")
        for index in range(1, len(plates) + 1):
            handle.write("P%03d_EALL, GRAV, %.10e, 0.0, 0.0, -1.0\n" % (index, cfg.GRAVITY))
        handle.write("*Output, field, number interval=20\n")
        handle.write("*Node Output\nU, RF\n")
        handle.write("*Element Output, directions=YES\nS, LE\n")
        handle.write("*Contact Output, variable=PRESELECT\n")
        handle.write("*Output, history, time interval=1.0e-2\n*Energy Output\n")
        handle.write("ALLIE, ALLKE, ALLAE, ALLVD, ALLWK\n*End Step\n")

    manifest = {
        "job": job_name,
        "case": case,
        "order": order,
        "plate_count": cfg.PLATE_COUNT,
        "nominal_pressure_pa": cfg.NOMINAL_PRESSURE_PA,
        "top_load_n": top_load,
        "elastic_modulus_pa": cfg.SURFACE_E,
        "poisson_ratio": cfg.SURFACE_NU,
        "plate_thickness_m": cfg.PLATE_THICKNESS_M,
        "friction_coefficient": cfg.FRICTION_COEFFICIENT,
        "constraint_mode": cfg.CONSTRAINT_MODE,
        "step_time_s": cfg.STEP_TIME_S,
        "offsets_m": offsets,
    }
    with open(os.path.join(OUTPUT_DIR, job_name + "_manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
    print("Wrote", inp_path)
    return job_name


def main():
    ensure_inputs()
    orders = read_orders()
    requested = sys.argv[1:] or ["min", "natural", "max"]
    for case in requested:
        if case not in ("min", "natural", "max"):
            raise RuntimeError("Unknown case: %s" % case)
        write_input(case, [int(value) for value in orders[case]])


if __name__ == "__main__":
    main()
