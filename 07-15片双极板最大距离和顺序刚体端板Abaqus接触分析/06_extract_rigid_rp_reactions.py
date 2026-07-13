# -*- coding: utf-8 -*-
from odbAccess import openOdb
import csv
import os
import sys

TOP_RP = 9300001
BOTTOM_RP = 9300002

JOB = sys.argv[1]
CASE = sys.argv[2]
OUT_CSV = JOB + "_rp_reactions.csv"


def vector3(data):
    try:
        return [float(data[0]), float(data[1]), float(data[2])]
    except Exception:
        return [0.0, 0.0, 0.0]


rows = []
odb = openOdb(path=JOB + ".odb", readOnly=True)
frame = odb.steps["Compression"].frames[-1]
rf = frame.fieldOutputs["RF"]
u = frame.fieldOutputs["U"]
row = {"case": CASE, "job": JOB}
for rp_name, rp_label in (("top", TOP_RP), ("bottom", BOTTOM_RP)):
    rf_vals = [v for v in rf.values if int(v.nodeLabel) == rp_label]
    u_vals = [v for v in u.values if int(v.nodeLabel) == rp_label]
    if rf_vals:
        vals = vector3(rf_vals[0].data)
        row[rp_name + "_rf1_n"] = vals[0]
        row[rp_name + "_rf2_n"] = vals[1]
        row[rp_name + "_rf3_n"] = vals[2]
    if u_vals:
        vals = vector3(u_vals[0].data)
        row[rp_name + "_u1_m"] = vals[0]
        row[rp_name + "_u2_m"] = vals[1]
        row[rp_name + "_u3_m"] = vals[2]
rows.append(row)
odb.close()

with open(OUT_CSV, "wb") as f:
    fieldnames = [
        "case", "job",
        "top_rf1_n", "top_rf2_n", "top_rf3_n", "top_u1_m", "top_u2_m", "top_u3_m",
        "bottom_rf1_n", "bottom_rf2_n", "bottom_rf3_n", "bottom_u1_m", "bottom_u2_m", "bottom_u3_m",
    ]
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print("wrote", OUT_CSV)
for row in rows:
    print(row)
