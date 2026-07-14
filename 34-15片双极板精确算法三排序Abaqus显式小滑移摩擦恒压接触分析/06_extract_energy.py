# -*- coding: utf-8 -*-
from __future__ import print_function

from odbAccess import openOdb
import csv
import sys


JOB = sys.argv[1]
VARIABLES = ("ALLKE", "ALLIE", "ALLAE", "ALLVD", "ALLWK")


odb = openOdb(path=JOB + ".odb", readOnly=True)
step = odb.steps["Compression"]
series = {}

for region in step.historyRegions.values():
    for name in VARIABLES:
        if name in region.historyOutputs and name not in series:
            series[name] = list(region.historyOutputs[name].data)

if not series:
    odb.close()
    raise RuntimeError("No whole-model energy history was found in %s.odb" % JOB)

times = sorted(set(t for values in series.values() for t, _value in values))
lookup = dict((name, dict(values)) for name, values in series.items())
path = JOB + "_energy_history.csv"
with open(path, "wb") as f:
    writer = csv.writer(f)
    writer.writerow(["time_s"] + list(VARIABLES) + ["ke_to_ie"])
    for time in times:
        values = [lookup.get(name, {}).get(time, "") for name in VARIABLES]
        ke = lookup.get("ALLKE", {}).get(time, 0.0)
        ie = lookup.get("ALLIE", {}).get(time, 0.0)
        ratio = ke / abs(ie) if abs(ie) > 1.0e-30 else ""
        writer.writerow([time] + values + [ratio])

print("wrote", path)
for name in VARIABLES:
    if name in series:
        print(name, series[name][-1])
if "ALLKE" in series and "ALLIE" in series:
    ke = series["ALLKE"][-1][1]
    ie = series["ALLIE"][-1][1]
    print("final_KE_over_abs_IE", ke / abs(ie) if abs(ie) > 1.0e-30 else None)
odb.close()
