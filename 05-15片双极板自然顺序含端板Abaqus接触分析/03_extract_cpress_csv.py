# -*- coding: utf-8 -*-
from odbAccess import openOdb
import csv

JOB = 'exp5_stack15_natural_rigid_endplates'
STACK_ORDER = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
NX = 17
NY = 9
NODES_PER_PLATE = NX * NY


def scalar(data):
    try:
        return float(data[0])
    except Exception:
        return float(data)


odb = openOdb(path=JOB + '.odb', readOnly=True)
frame = odb.steps['Compression'].frames[-1]

rows = []
summary = []
for interface_index in range(1, len(STACK_ORDER)):
    upper_stack = interface_index
    lower_stack = interface_index + 1
    upper_plate_no = STACK_ORDER[interface_index - 1]
    lower_plate_no = STACK_ORDER[interface_index]
    field_name = 'CPRESS   P%02d_CONTACT_NODES/P%02d_TOP' % (upper_stack, lower_stack)
    field = frame.fieldOutputs[field_name]
    base = upper_stack * 100000
    vals = []
    for value in field.values:
        node_label = int(value.nodeLabel)
        local = node_label - base
        if local < 1 or local > NODES_PER_PLATE:
            continue
        ix = (local - 1) % NX
        iy = (local - 1) // NX
        p = scalar(value.data)
        vals.append(p)
        rows.append([
            interface_index,
            upper_stack,
            lower_stack,
            upper_plate_no,
            lower_plate_no,
            node_label,
            ix,
            iy,
            p,
        ])
    if vals:
        summary.append([
            interface_index,
            upper_plate_no,
            lower_plate_no,
            len(vals),
            min(vals),
            max(vals),
            sum(vals) / float(len(vals)),
        ])

with open(JOB + '_cpress_nodes.csv', 'wb') as f:
    writer = csv.writer(f)
    writer.writerow([
        'interface_index', 'upper_stack_index', 'lower_stack_index',
        'upper_plate_no', 'lower_plate_no', 'node_label', 'ix', 'iy',
        'cpress_pa',
    ])
    writer.writerows(rows)

with open(JOB + '_cpress_node_summary.csv', 'wb') as f:
    writer = csv.writer(f)
    writer.writerow([
        'interface_index', 'upper_plate_no', 'lower_plate_no', 'node_count',
        'min_pa', 'max_pa', 'mean_pa',
    ])
    writer.writerows(summary)

print('wrote', JOB + '_cpress_nodes.csv')
print('wrote', JOB + '_cpress_node_summary.csv')
print('interfaces', len(summary))
odb.close()

