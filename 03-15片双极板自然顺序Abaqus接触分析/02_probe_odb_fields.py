# -*- coding: utf-8 -*-
from odbAccess import openOdb

odb = openOdb(path='exp3_stack15_natural_contact.odb', readOnly=True)
step = odb.steps['Compression']
frame = step.frames[-1]
print('frames:', len(step.frames))
print('last frame value:', frame.frameValue)
print('field outputs:', sorted(frame.fieldOutputs.keys()))

for name in ('CPRESS', 'CSTATUS', 'CSHEAR1', 'CSHEAR2', 'U', 'RF'):
    if name not in frame.fieldOutputs:
        continue
    field = frame.fieldOutputs[name]
    print('FIELD', name, 'values', len(field.values))
    n = min(10, len(field.values))
    for i in range(n):
        value = field.values[i]
        attrs = []
        for attr in ('instance', 'nodeLabel', 'elementLabel', 'integrationPoint', 'face'):
            if hasattr(value, attr):
                try:
                    attrs.append('%s=%s' % (attr, getattr(value, attr)))
                except Exception:
                    attrs.append('%s=?' % attr)
        print(' ', i, ', '.join(attrs), 'data=', value.data)

odb.close()
