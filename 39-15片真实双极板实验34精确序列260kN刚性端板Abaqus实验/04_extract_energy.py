# -*- coding: utf-8 -*-
from __future__ import print_function

from odbAccess import openOdb
import csv
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.abspath(os.path.join(HERE, os.pardir, "outputs"))
JOB = sys.argv[1]
VARIABLES = ("ALLKE", "ALLIE", "ALLAE", "ALLVD", "ALLWK")

odb = openOdb(path=os.path.join(OUTPUT_DIR, JOB + ".odb"), readOnly=True)
step = odb.steps["Compression"]
series = {}
for region in step.historyRegions.values():
    for name in VARIABLES:
        if name in region.historyOutputs and name not in series:
            series[name] = list(region.historyOutputs[name].data)
if not series:
    odb.close()
    raise RuntimeError("No whole-model energy history was found.")

times = sorted(set(time for values in series.values() for time, _value in values))
lookup = dict((name, dict(values)) for name, values in series.items())
path = os.path.join(OUTPUT_DIR, JOB + "_energy_history.csv")
with open(path, "wb") as handle:
    writer = csv.writer(handle)
    writer.writerow(["time_s"] + list(VARIABLES) + ["ke_to_ie", "ae_to_ie"])
    for time in times:
        values = [lookup.get(name, {}).get(time, "") for name in VARIABLES]
        ke = lookup.get("ALLKE", {}).get(time, 0.0)
        ie = lookup.get("ALLIE", {}).get(time, 0.0)
        ae = lookup.get("ALLAE", {}).get(time, 0.0)
        ke_ratio = ke / abs(ie) if abs(ie) > 1.0e-30 else ""
        ae_ratio = ae / abs(ie) if abs(ie) > 1.0e-30 else ""
        writer.writerow([time] + values + [ke_ratio, ae_ratio])
print("wrote", path)
if "ALLKE" in series and "ALLIE" in series:
    print("final KE/IE", series["ALLKE"][-1][1] / abs(series["ALLIE"][-1][1]))
if "ALLAE" in series and "ALLIE" in series:
    print("final AE/IE", series["ALLAE"][-1][1] / abs(series["ALLIE"][-1][1]))
odb.close()

