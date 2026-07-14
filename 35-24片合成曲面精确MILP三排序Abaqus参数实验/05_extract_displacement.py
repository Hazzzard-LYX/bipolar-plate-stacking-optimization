# -*- coding: utf-8 -*-
from __future__ import print_function

from odbAccess import openOdb
import csv
import json
import math
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.abspath(os.path.join(HERE, os.pardir, "outputs"))
JOB = sys.argv[1]
CASE = sys.argv[2]
NX = int(sys.argv[3])
NY = int(sys.argv[4])
NODES_PER_PLATE = NX * NY
TOP_ENDPLATE_RP = 9300001
BOTTOM_ENDPLATE_RP = 9300002

with open(os.path.join(OUTPUT_DIR, "stack_orders.json"), "r") as handle:
    orders = json.load(handle)
STACK_ORDER = [int(value) for value in orders[CASE]]


def stats(values):
    count = len(values)
    mean = sum(values) / float(count)
    variance = sum((value - mean) ** 2 for value in values) / float(count)
    return mean, math.sqrt(variance), min(values), max(values)


odb = openOdb(path=os.path.join(OUTPUT_DIR, JOB + ".odb"), readOnly=True)
frame = odb.steps["Compression"].frames[-1]
field = frame.fieldOutputs["U"]
by_label = {}
for value in field.values:
    by_label[int(value.nodeLabel)] = tuple(float(component) for component in value.data)

node_rows = []
plate_rows = []
for stack_index, plate_no in enumerate(STACK_ORDER, start=1):
    base = stack_index * 100000
    u1_values = []
    u2_values = []
    u3_values = []
    magnitudes = []
    for local in range(1, NODES_PER_PLATE + 1):
        node_label = base + local
        if node_label not in by_label:
            raise KeyError("Missing U for node %d" % node_label)
        u1, u2, u3 = by_label[node_label]
        magnitude = math.sqrt(u1 * u1 + u2 * u2 + u3 * u3)
        u1_values.append(u1)
        u2_values.append(u2)
        u3_values.append(u3)
        magnitudes.append(magnitude)
        node_rows.append([
            stack_index,
            plate_no,
            node_label,
            (local - 1) % NX,
            (local - 1) // NX,
            u1,
            u2,
            u3,
            magnitude,
        ])
    mean_u3, std_u3, min_u3, max_u3 = stats(u3_values)
    mean_u1, std_u1, _min_u1, _max_u1 = stats(u1_values)
    mean_u2, std_u2, _min_u2, _max_u2 = stats(u2_values)
    centered_3d_rms = math.sqrt(sum(
        (u1 - mean_u1) ** 2 + (u2 - mean_u2) ** 2 + (u3 - mean_u3) ** 2
        for u1, u2, u3 in zip(u1_values, u2_values, u3_values)
    ) / float(NODES_PER_PLATE))
    plate_rows.append([
        stack_index,
        plate_no,
        NODES_PER_PLATE,
        mean_u3,
        std_u3,
        min_u3,
        max_u3,
        max_u3 - min_u3,
        max(abs(value) for value in u3_values),
        max(magnitudes),
        centered_3d_rms,
        std_u1,
        std_u2,
    ])

node_path = os.path.join(OUTPUT_DIR, JOB + "_displacement_nodes.csv")
with open(node_path, "wb") as handle:
    writer = csv.writer(handle)
    writer.writerow(["stack_index", "plate_no", "node_label", "ix", "iy", "u1_m", "u2_m", "u3_m", "umag_m"])
    writer.writerows(node_rows)

summary_path = os.path.join(OUTPUT_DIR, JOB + "_displacement_plate_summary.csv")
with open(summary_path, "wb") as handle:
    writer = csv.writer(handle)
    writer.writerow([
        "stack_index", "plate_no", "node_count", "mean_u3_m", "warpage_u3_rms_m",
        "min_u3_m", "max_u3_m", "warpage_u3_peak_to_peak_m", "max_abs_u3_m",
        "max_umag_m", "deformation_3d_rms_m", "u1_centered_rms_m", "u2_centered_rms_m",
    ])
    writer.writerows(plate_rows)

top_u3 = by_label.get(TOP_ENDPLATE_RP, (0.0, 0.0, float("nan")))[2]
bottom_u3 = by_label.get(BOTTOM_ENDPLATE_RP, (0.0, 0.0, float("nan")))[2]
stack_row = {
    "case": CASE,
    "top_endplate_u3_m": top_u3,
    "bottom_endplate_u3_m": bottom_u3,
    "stack_shortening_m": bottom_u3 - top_u3,
    "mean_plate_warpage_u3_rms_m": sum(row[4] for row in plate_rows) / float(len(plate_rows)),
    "max_plate_warpage_u3_rms_m": max(row[4] for row in plate_rows),
    "mean_plate_warpage_u3_peak_to_peak_m": sum(row[7] for row in plate_rows) / float(len(plate_rows)),
    "max_plate_warpage_u3_peak_to_peak_m": max(row[7] for row in plate_rows),
    "mean_plate_deformation_3d_rms_m": sum(row[10] for row in plate_rows) / float(len(plate_rows)),
    "max_plate_deformation_3d_rms_m": max(row[10] for row in plate_rows),
    "max_plate_nodal_umag_m": max(row[9] for row in plate_rows),
}
stack_path = os.path.join(OUTPUT_DIR, JOB + "_deformation_summary.csv")
with open(stack_path, "wb") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(stack_row.keys()))
    writer.writeheader()
    writer.writerow(stack_row)

print("wrote", node_path)
print("wrote", summary_path)
print("wrote", stack_path)
odb.close()
