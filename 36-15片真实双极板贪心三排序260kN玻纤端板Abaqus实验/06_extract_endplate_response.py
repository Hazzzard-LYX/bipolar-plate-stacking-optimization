# -*- coding: utf-8 -*-
from __future__ import print_function

from odbAccess import openOdb
import csv
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.abspath(os.path.join(HERE, os.pardir, "outputs"))
JOB = sys.argv[1]

TOP_NODE_MIN, TOP_NODE_MAX = 9100001, 9109999
BOTTOM_NODE_MIN, BOTTOM_NODE_MAX = 9200001, 9209999
TOP_ELEM_MIN, TOP_ELEM_MAX = 9100001, 9109999
BOTTOM_ELEM_MIN, BOTTOM_ELEM_MAX = 9200001, 9209999


def in_range(value, low, high):
    return low <= int(value) <= high


odb = openOdb(path=os.path.join(OUTPUT_DIR, JOB + ".odb"), readOnly=True)
frame = odb.steps["Compression"].frames[-1]
top_u3 = []
bottom_u3 = []
for value in frame.fieldOutputs["U"].values:
    label = int(value.nodeLabel)
    if in_range(label, TOP_NODE_MIN, TOP_NODE_MAX):
        top_u3.append(float(value.data[2]))
    elif in_range(label, BOTTOM_NODE_MIN, BOTTOM_NODE_MAX):
        bottom_u3.append(float(value.data[2]))

bottom_reaction_z = 0.0
for value in frame.fieldOutputs["RF"].values:
    if in_range(value.nodeLabel, BOTTOM_NODE_MIN, BOTTOM_NODE_MAX):
        bottom_reaction_z += float(value.data[2])

reaction_tail = []
all_frames = odb.steps["Compression"].frames
for frame_index in range(max(0, len(all_frames) - 5), len(all_frames)):
    sample_frame = all_frames[frame_index]
    total = 0.0
    for value in sample_frame.fieldOutputs["RF"].values:
        if in_range(value.nodeLabel, BOTTOM_NODE_MIN, BOTTOM_NODE_MAX):
            total += float(value.data[2])
    reaction_tail.append(total)

top_mises = []
bottom_mises = []
for value in frame.fieldOutputs["S"].values:
    label = int(value.elementLabel)
    try:
        mises = float(value.mises)
    except Exception:
        continue
    if in_range(label, TOP_ELEM_MIN, TOP_ELEM_MAX):
        top_mises.append(mises)
    elif in_range(label, BOTTOM_ELEM_MIN, BOTTOM_ELEM_MAX):
        bottom_mises.append(mises)

if not top_u3 or not bottom_u3:
    odb.close()
    raise RuntimeError("Endplate displacement values were not found in the final frame.")

path = os.path.join(OUTPUT_DIR, JOB + "_endplate_response.csv")
with open(path, "wb") as handle:
    writer = csv.writer(handle)
    writer.writerow([
        "job", "top_u3_min_m", "top_u3_max_m", "top_u3_range_m", "top_max_abs_u3_m",
        "bottom_u3_min_m", "bottom_u3_max_m", "bottom_u3_range_m", "bottom_max_abs_u3_m",
        "top_max_mises_pa", "bottom_max_mises_pa", "bottom_reaction_z_n",
        "bottom_reaction_tail_mean_n", "bottom_reaction_tail_min_n", "bottom_reaction_tail_max_n",
    ])
    writer.writerow([
        JOB,
        min(top_u3), max(top_u3), max(top_u3) - min(top_u3), max(abs(v) for v in top_u3),
        min(bottom_u3), max(bottom_u3), max(bottom_u3) - min(bottom_u3), max(abs(v) for v in bottom_u3),
        max(top_mises) if top_mises else "", max(bottom_mises) if bottom_mises else "",
        bottom_reaction_z,
        sum(reaction_tail) / float(len(reaction_tail)), min(reaction_tail), max(reaction_tail),
    ])
print("wrote", path)
odb.close()
