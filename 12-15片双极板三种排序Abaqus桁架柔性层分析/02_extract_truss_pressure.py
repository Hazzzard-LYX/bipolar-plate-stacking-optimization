# -*- coding: utf-8 -*-
from odbAccess import openOdb
import csv
import sys

JOB = sys.argv[1]
CELL_AREA_M2 = 0.820 * 0.345 / float(16 * 8)

map_path = JOB + "_truss_map.csv"
out_path = JOB + "_pressure_nodes.csv"

meta_by_upper = {}
with open(map_path, "r") as f:
    for row in csv.DictReader(f):
        if "\xef\xbb\xbfcase" in row:
            row["case"] = row["\xef\xbb\xbfcase"]
        meta_by_upper[int(row["upper_node"])] = row

odb = openOdb(path=JOB + ".odb", readOnly=True)
frame = odb.steps["Compression"].frames[-1]
rf = frame.fieldOutputs["RF"]

rows = []
for value in rf.values:
    node = int(value.nodeLabel)
    if node not in meta_by_upper:
        continue
    meta = meta_by_upper[node]
    rf3 = float(value.data[2])
    pressure_pa = abs(rf3) / CELL_AREA_M2
    row = {
        "case": meta["case"],
        "job": JOB,
        "interface_index": meta["interface_index"],
        "upper_plate": meta["upper_plate"],
        "lower_plate": meta["lower_plate"],
        "ix": meta["ix"],
        "iy": meta["iy"],
        "upper_node": node,
        "rf3_n": rf3,
        "pressure_pa": pressure_pa,
        "spring_k_n_per_m": meta["spring_k_n_per_m"],
        "truss_area_m2": meta["truss_area_m2"],
        "spread_mismatch_um": meta["spread_mismatch_um"],
    }
    rows.append(row)
odb.close()

with open(out_path, "wb") as f:
    fieldnames = [
        "case", "job", "interface_index", "upper_plate", "lower_plate",
        "ix", "iy", "upper_node", "rf3_n", "pressure_pa",
        "spring_k_n_per_m", "truss_area_m2", "spread_mismatch_um",
    ]
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print("wrote", out_path)
