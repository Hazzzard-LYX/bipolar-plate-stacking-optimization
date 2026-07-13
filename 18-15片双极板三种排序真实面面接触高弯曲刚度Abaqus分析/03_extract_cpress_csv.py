# -*- coding: utf-8 -*-
from odbAccess import openOdb
import csv
import sys

JOB = sys.argv[1] if len(sys.argv) > 1 else 'exp18_max_bendstiff_contact'
STACK_ORDER = eval(sys.argv[2]) if len(sys.argv) > 2 else [11, 12, 13, 7, 14, 9, 5, 6, 8, 15, 3, 1, 2, 10, 4]
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
    candidates = [
        'CPRESS   P%02d_BOTTOM/P%02d_TOP' % (upper_stack, lower_stack),
        'CPRESS   P%02d_CONTACT_NODES/P%02d_TOP' % (upper_stack, lower_stack),
    ]
    field_name = None
    for name in candidates:
        if name in frame.fieldOutputs:
            field_name = name
            break
    if field_name is None:
        matches = [name for name in frame.fieldOutputs.keys()
                   if name.startswith('CPRESS') and
                   ('P%02d_' % upper_stack) in name and
                   ('P%02d_TOP' % lower_stack) in name]
        if matches:
            field_name = matches[0]
    if field_name is None:
        raise KeyError('Cannot find CPRESS output for interface %d. Available CPRESS fields: %s' %
                       (interface_index, [name for name in frame.fieldOutputs.keys() if name.startswith('CPRESS')]))
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





