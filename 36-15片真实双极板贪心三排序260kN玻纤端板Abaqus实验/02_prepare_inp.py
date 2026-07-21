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

LENGTH_M = cfg.PLATE_LENGTH_M
WIDTH_M = cfg.PLATE_WIDTH_M
RAW_NX = 201
RAW_NY = 85
NODES_X = cfg.GRID_CELLS_X + 1
NODES_Y = cfg.GRID_CELLS_Y + 1


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
        raise RuntimeError("Cannot find surface CSV for plate %03d." % plate_index)
    path = os.path.join(DATA_DIR, sorted(matches)[0])
    grid = [[0.0 for _ in range(RAW_NX)] for _ in range(RAW_NY)]
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != RAW_NX * RAW_NY:
        raise RuntimeError("Unexpected row count in %s: %d" % (path, len(rows)))
    for index, row in enumerate(rows):
        grid[index // RAW_NX][index % RAW_NX] = float(row["z_mm"]) / 1000.0
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


def plate_node_id(plate, i, j):
    return plate["node_base"] + j * NODES_X + i + 1


def build_plate_mesh(grid, stack_index, plate_no, z_shift):
    node_base = 100000 * (stack_index + 1)
    nodes = []
    for j in range(NODES_Y):
        y = (j / float(NODES_Y - 1) - 0.5) * WIDTH_M
        for i in range(NODES_X):
            x = (i / float(NODES_X - 1) - 0.5) * LENGTH_M
            nid = node_base + j * NODES_X + i + 1
            nodes.append((nid, x, y, z_shift + interpolate_z(grid, x, y)))
    elems = []
    for j in range(cfg.GRID_CELLS_Y):
        for i in range(cfg.GRID_CELLS_X):
            n1 = node_base + j * NODES_X + i + 1
            n2 = n1 + 1
            n4 = node_base + (j + 1) * NODES_X + i + 1
            n3 = n4 + 1
            elems.append((node_base + len(elems) + 1, n1, n2, n3, n4))
    perimeter = []
    for j in range(NODES_Y):
        for i in range(NODES_X):
            if i in (0, NODES_X - 1) or j in (0, NODES_Y - 1):
                perimeter.append(node_base + j * NODES_X + i + 1)
    return {
        "name": "P%03d" % (stack_index + 1),
        "plate_no": plate_no,
        "node_base": node_base,
        "nodes": nodes,
        "elems": elems,
        "used": [row[0] for row in nodes],
        "perimeter": perimeter,
    }


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


def solid_node_id(node_base, i, j, k):
    return node_base + k * NODES_X * NODES_Y + j * NODES_X + i + 1


def build_solid_endplate(name, node_base, elem_base, z_start, z_end):
    nz = int(cfg.ENDPLATE_CELLS_Z)
    nodes = []
    for k in range(nz + 1):
        z = z_start + (z_end - z_start) * k / float(nz)
        for j in range(NODES_Y):
            y = (j / float(NODES_Y - 1) - 0.5) * WIDTH_M
            for i in range(NODES_X):
                x = (i / float(NODES_X - 1) - 0.5) * LENGTH_M
                nodes.append((solid_node_id(node_base, i, j, k), x, y, z))
    elems = []
    bottom_elems = []
    top_elems = []
    for k in range(nz):
        for j in range(cfg.GRID_CELLS_Y):
            for i in range(cfg.GRID_CELLS_X):
                n1 = solid_node_id(node_base, i, j, k)
                n2 = solid_node_id(node_base, i + 1, j, k)
                n3 = solid_node_id(node_base, i + 1, j + 1, k)
                n4 = solid_node_id(node_base, i, j + 1, k)
                n5 = solid_node_id(node_base, i, j, k + 1)
                n6 = solid_node_id(node_base, i + 1, j, k + 1)
                n7 = solid_node_id(node_base, i + 1, j + 1, k + 1)
                n8 = solid_node_id(node_base, i, j + 1, k + 1)
                eid = elem_base + len(elems) + 1
                elems.append((eid, n1, n2, n3, n4, n5, n6, n7, n8))
                if k == 0:
                    bottom_elems.append(eid)
                if k == nz - 1:
                    top_elems.append(eid)
    bottom_nodes = [solid_node_id(node_base, i, j, 0) for j in range(NODES_Y) for i in range(NODES_X)]
    top_nodes = [solid_node_id(node_base, i, j, nz) for j in range(NODES_Y) for i in range(NODES_X)]
    return {
        "name": name,
        "node_base": node_base,
        "nodes": nodes,
        "elems": elems,
        "bottom_elems": bottom_elems,
        "top_elems": top_elems,
        "bottom_nodes": bottom_nodes,
        "top_nodes": top_nodes,
        "guide_a": solid_node_id(node_base, NODES_X // 2, NODES_Y // 2, nz),
        "guide_b": solid_node_id(node_base, NODES_X - 1, NODES_Y // 2, nz),
    }


def write_list(handle, values, per_line=16):
    values = list(values)
    for index in range(0, len(values), per_line):
        handle.write(", ".join(str(value) for value in values[index:index + per_line]) + "\n")


def constraint_sets(plate):
    if cfg.CONSTRAINT_MODE != "three_point":
        raise RuntimeError("Experiment 36 inherits Experiment 30 three-point plate constraints.")
    return [
        ("POINT_A", [plate_node_id(plate, 0, 0)], 1, 2),
        ("POINT_B", [plate_node_id(plate, NODES_X - 1, 0)], 2, 2),
        ("POINT_C", [plate_node_id(plate, 0, NODES_Y - 1)], 1, 1),
    ]


def write_endplate_sets(handle, mesh):
    prefix = mesh["name"]
    handle.write("*Nset, nset=%s_BOTTOM_NODES\n" % prefix)
    write_list(handle, mesh["bottom_nodes"])
    handle.write("*Nset, nset=%s_TOP_NODES\n" % prefix)
    write_list(handle, mesh["top_nodes"])
    handle.write("*Elset, elset=%s_BOTTOM_ELEMS\n" % prefix)
    write_list(handle, mesh["bottom_elems"])
    handle.write("*Elset, elset=%s_TOP_ELEMS\n" % prefix)
    write_list(handle, mesh["top_elems"])


def write_input(case, order):
    if len(order) != cfg.PLATE_COUNT:
        raise RuntimeError("Order length does not match PLATE_COUNT.")
    grids = [read_plate_grid(plate_no) for plate_no in order]
    plates, offsets = build_stack(grids, order)
    top_z = max(node[3] for node in plates[0]["nodes"]) + 0.5 * cfg.PLATE_THICKNESS_M
    bottom_z = min(node[3] for node in plates[-1]["nodes"]) - 0.5 * cfg.PLATE_THICKNESS_M
    top_end = build_solid_endplate("EP_TOP", 9100000, 9100000, top_z, top_z + cfg.ENDPLATE_THICKNESS_M)
    bottom_end = build_solid_endplate("EP_BOTTOM", 9200000, 9200000, bottom_z - cfg.ENDPLATE_THICKNESS_M, bottom_z)
    job_name = "exp%d_%s_%dplates" % (cfg.EXPERIMENT_ID, case, cfg.PLATE_COUNT)
    inp_path = os.path.join(OUTPUT_DIR, job_name + ".inp")

    with open(inp_path, "w", encoding="ascii", newline="") as handle:
        handle.write("*Heading\n")
        handle.write("Experiment %d %s: %s\n" % (cfg.EXPERIMENT_ID, case, cfg.DESCRIPTION))
        handle.write("*Preprint, echo=NO, model=NO, history=NO, contact=NO\n")
        handle.write("** Stack order top-to-bottom: %s\n" % " -> ".join(map(str, order)))
        handle.write("** Total force: %.3f N; equivalent pressure: %.6f Pa\n" % (cfg.TOTAL_LOAD_N, cfg.NOMINAL_PRESSURE_PA))
        handle.write("*Node\n")
        for mesh in [top_end] + plates + [bottom_end]:
            for row in mesh["nodes"]:
                handle.write("%d, %.10e, %.10e, %.10e\n" % row)

        handle.write("*Element, type=C3D8R, elset=EP_TOP_EALL\n")
        for row in top_end["elems"]:
            handle.write("%d, %d, %d, %d, %d, %d, %d, %d, %d\n" % row)
        for index, plate in enumerate(plates, start=1):
            handle.write("*Element, type=S4, elset=P%03d_EALL\n" % index)
            for row in plate["elems"]:
                handle.write("%d, %d, %d, %d, %d\n" % row)
        handle.write("*Element, type=C3D8R, elset=EP_BOTTOM_EALL\n")
        for row in bottom_end["elems"]:
            handle.write("%d, %d, %d, %d, %d, %d, %d, %d, %d\n" % row)

        write_endplate_sets(handle, top_end)
        write_endplate_sets(handle, bottom_end)
        handle.write("*Nset, nset=EP_TOP_GUIDE_A\n%d\n" % top_end["guide_a"])
        handle.write("*Nset, nset=EP_TOP_GUIDE_B\n%d\n" % top_end["guide_b"])

        all_constraints = []
        for index, plate in enumerate(plates, start=1):
            handle.write("*Nset, nset=P%03d_USED\n" % index)
            write_list(handle, plate["used"])
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

        handle.write("*Material, name=GFRP_ENDPLATE\n")
        handle.write("*Density\n%.10e,\n" % cfg.ENDPLATE_RHO)
        handle.write("*Elastic\n%.10e, %.8f\n" % (cfg.ENDPLATE_E, cfg.ENDPLATE_NU))
        handle.write("*Damping, alpha=%.10e\n" % cfg.DAMPING_ALPHA)
        handle.write("*Solid Section, elset=EP_TOP_EALL, material=GFRP_ENDPLATE\n,\n")
        handle.write("*Solid Section, elset=EP_BOTTOM_EALL, material=GFRP_ENDPLATE\n,\n")

        handle.write("*Surface, type=ELEMENT, name=EP_TOP_BOTTOM\nEP_TOP_BOTTOM_ELEMS, S1\n")
        handle.write("*Surface, type=ELEMENT, name=EP_TOP_OUTER\nEP_TOP_TOP_ELEMS, S2\n")
        handle.write("*Surface, type=ELEMENT, name=EP_BOTTOM_OUTER\nEP_BOTTOM_BOTTOM_ELEMS, S1\n")
        handle.write("*Surface, type=ELEMENT, name=EP_BOTTOM_TOP\nEP_BOTTOM_TOP_ELEMS, S2\n")
        for index in range(1, len(plates) + 1):
            handle.write("*Surface, type=ELEMENT, name=P%03d_TOP\nP%03d_EALL, SPOS\n" % (index, index))
            handle.write("*Surface, type=ELEMENT, name=P%03d_BOTTOM\nP%03d_EALL, SNEG\n" % (index, index))
        handle.write("*Surface Interaction, name=FRICTIONAL_CONTACT\n")
        handle.write("*Surface Behavior, pressure-overclosure=LINEAR\n%.10e,\n" % cfg.CONTACT_STIFFNESS_PA_PER_M)
        handle.write("*Contact Damping, definition=DAMPING COEFFICIENT\n%.10e\n" % cfg.CONTACT_DAMPING_PA_S_PER_M)
        handle.write("*Friction\n%.8f,\n" % cfg.FRICTION_COEFFICIENT)

        handle.write("*Boundary\n")
        handle.write("EP_BOTTOM_BOTTOM_NODES, 1, 3, 0.0\n")
        handle.write("EP_TOP_GUIDE_A, 1, 2, 0.0\n")
        handle.write("EP_TOP_GUIDE_B, 2, 2, 0.0\n")
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
        handle.write("*Dsload, amplitude=SMOOTH_PRESSURE\nEP_TOP_OUTER, P, %.10e\n" % cfg.NOMINAL_PRESSURE_PA)
        handle.write("*Dload, amplitude=SMOOTH_PRESSURE\n")
        for index in range(1, len(plates) + 1):
            handle.write("P%03d_EALL, GRAV, %.10e, 0.0, 0.0, -1.0\n" % (index, cfg.GRAVITY))
        handle.write("EP_TOP_EALL, GRAV, %.10e, 0.0, 0.0, -1.0\n" % cfg.GRAVITY)
        handle.write("EP_BOTTOM_EALL, GRAV, %.10e, 0.0, 0.0, -1.0\n" % cfg.GRAVITY)
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
        "total_load_n": cfg.TOTAL_LOAD_N,
        "nominal_pressure_pa": cfg.NOMINAL_PRESSURE_PA,
        "plate_elastic_modulus_pa": cfg.SURFACE_E,
        "plate_poisson_ratio": cfg.SURFACE_NU,
        "plate_thickness_m": cfg.PLATE_THICKNESS_M,
        "friction_coefficient": cfg.FRICTION_COEFFICIENT,
        "constraint_mode": cfg.CONSTRAINT_MODE,
        "step_time_s": cfg.STEP_TIME_S,
        "endplate_material": "equivalent-isotropic G10/FR-4",
        "endplate_thickness_m": cfg.ENDPLATE_THICKNESS_M,
        "endplate_cells_z": cfg.ENDPLATE_CELLS_Z,
        "endplate_elastic_modulus_pa": cfg.ENDPLATE_E,
        "endplate_poisson_ratio": cfg.ENDPLATE_NU,
        "endplate_density_kg_m3": cfg.ENDPLATE_RHO,
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

