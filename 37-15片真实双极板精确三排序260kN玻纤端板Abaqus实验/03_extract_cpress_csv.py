# -*- coding: utf-8 -*-
from __future__ import print_function

from odbAccess import openOdb
import csv
import json
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.abspath(os.path.join(HERE, os.pardir, "outputs"))
JOB = sys.argv[1]
CASE = sys.argv[2]
NX = int(sys.argv[3])
NY = int(sys.argv[4])
FRAME_INDEX = int(sys.argv[5]) if len(sys.argv) > 5 else -1
OUTPUT_SUFFIX = sys.argv[6] if len(sys.argv) > 6 else ""
NODES_PER_PLATE = NX * NY

with open(os.path.join(OUTPUT_DIR, "stack_orders.json"), "r") as handle:
    orders = json.load(handle)
STACK_ORDER = [int(value) for value in orders[CASE]]


def scalar(data):
    try:
        return float(data[0])
    except Exception:
        return float(data)


odb = openOdb(path=os.path.join(OUTPUT_DIR, JOB + ".odb"), readOnly=True)
frame = odb.steps["Compression"].frames[FRAME_INDEX]
rows = []
summary = []
for interface_index in range(1, len(STACK_ORDER)):
    upper_stack = interface_index
    lower_stack = interface_index + 1
    candidates = [
        "CPRESS   P%03d_BOTTOM/P%03d_TOP" % (upper_stack, lower_stack),
        "CPRESS   P%03d_TOP/P%03d_BOTTOM" % (lower_stack, upper_stack),
    ]
    field_name = None
    for name in candidates:
        if name in frame.fieldOutputs:
            field_name = name
            break
    if field_name is None:
        matches = [name for name in frame.fieldOutputs.keys()
                   if name.startswith("CPRESS") and
                   ("P%03d_" % upper_stack) in name and
                   ("P%03d_" % lower_stack) in name]
        if matches:
            field_name = matches[0]
    if field_name is None:
        available = [name for name in frame.fieldOutputs.keys() if name.startswith("CPRESS")]
        raise KeyError("Cannot find CPRESS for interface %d; available=%s" % (interface_index, available))

    buckets = []
    for base in (upper_stack * 100000, lower_stack * 100000):
        bucket = []
        for value in frame.fieldOutputs[field_name].values:
            node_label = int(value.nodeLabel)
            local = node_label - base
            if 1 <= local <= NODES_PER_PLATE:
                bucket.append((value, node_label, local))
        buckets.append(bucket)
    selected = max(buckets, key=len)
    values = []
    for value, node_label, local in selected:
        pressure = scalar(value.data)
        values.append(pressure)
        rows.append([
            interface_index,
            upper_stack,
            lower_stack,
            STACK_ORDER[interface_index - 1],
            STACK_ORDER[interface_index],
            node_label,
            (local - 1) % NX,
            (local - 1) // NX,
            pressure,
        ])
    if values:
        summary.append([
            interface_index,
            STACK_ORDER[interface_index - 1],
            STACK_ORDER[interface_index],
            len(values),
            min(values),
            max(values),
            sum(values) / float(len(values)),
        ])

nodes_path = os.path.join(OUTPUT_DIR, JOB + OUTPUT_SUFFIX + "_cpress_nodes.csv")
with open(nodes_path, "wb") as handle:
    writer = csv.writer(handle)
    writer.writerow(["interface_index", "upper_stack_index", "lower_stack_index",
                     "upper_plate_no", "lower_plate_no", "node_label", "ix", "iy", "cpress_pa"])
    writer.writerows(rows)
summary_path = os.path.join(OUTPUT_DIR, JOB + OUTPUT_SUFFIX + "_cpress_node_summary.csv")
with open(summary_path, "wb") as handle:
    writer = csv.writer(handle)
    writer.writerow(["interface_index", "upper_plate_no", "lower_plate_no", "node_count",
                     "min_pa", "max_pa", "mean_pa"])
    writer.writerows(summary)
print("wrote", nodes_path)
print("interfaces", len(summary))
odb.close()
