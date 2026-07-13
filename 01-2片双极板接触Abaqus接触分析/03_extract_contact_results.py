# -*- coding: utf-8 -*-
"""
Extract Abaqus contact results from Experiment 1 ODB.

Run with Abaqus Python, for example:
  abaqus python 03_extract_contact_results.py
"""
from __future__ import print_function

import csv
import os

from odbAccess import openOdb


EXPERIMENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
OUTPUT_DIR = os.path.join(EXPERIMENT_DIR, "outputs")
JOB_NAME = "exp1_plate01_plate02_contact"
ODB_PATH = os.path.join(OUTPUT_DIR, JOB_NAME + ".odb")
CSV_PATH = os.path.join(OUTPUT_DIR, JOB_NAME + "_contact_summary.csv")


def field_values(frame, name):
    if name not in frame.fieldOutputs:
        return []
    return list(frame.fieldOutputs[name].values)


def main():
    if not os.path.exists(ODB_PATH):
        raise RuntimeError("ODB not found: %s" % ODB_PATH)

    odb = openOdb(ODB_PATH, readOnly=True)
    try:
        step = odb.steps["Compression"]
        frame = step.frames[-1]
        rows = []
        for name in ("CPRESS", "COPEN"):
            vals = field_values(frame, name)
            numeric = []
            for v in vals:
                try:
                    numeric.append(float(v.data))
                except Exception:
                    pass
            if numeric:
                rows.append(
                    {
                        "field": name,
                        "count": len(numeric),
                        "min": min(numeric),
                        "max": max(numeric),
                        "mean": sum(numeric) / float(len(numeric)),
                    }
                )
            else:
                rows.append({"field": name, "count": 0, "min": "", "max": "", "mean": ""})

        with open(CSV_PATH, "wb") as f:
            writer = csv.DictWriter(f, fieldnames=["field", "count", "min", "max", "mean"])
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

        print("Wrote contact summary:")
        print(CSV_PATH)
        for row in rows:
            print(row)
    finally:
        odb.close()


if __name__ == "__main__":
    main()
