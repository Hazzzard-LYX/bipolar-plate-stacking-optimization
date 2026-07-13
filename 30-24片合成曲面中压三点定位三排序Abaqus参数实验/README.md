# Distributed Abaqus experiment scripts

This folder is self-contained except for the original 15 measured surface CSV files and the installed Python/Abaqus executables.

## Preparation only

Run `run_prepare_only.ps1`. It creates or copies the requested surface CSV files, calculates the min-distance, natural, and max-distance orders, and writes three Abaqus `.inp` files. It does not submit Abaqus jobs.

The source surface directory is discovered below the project root. On another computer, set `BIPOLAR_SOURCE_DIR` to the directory containing the 15 original `820x345mm` CSV files when automatic discovery is unavailable.

## Abaqus execution

Run `run_abaqus_jobs.ps1` after preparation. Use the `Cases` argument to distribute individual orderings to different computers, for example:

```powershell
.\run_abaqus_jobs.ps1 -Cases min
```

The default runs all three cases sequentially with one CPU per job.

## Postprocessing

After all three `.odb` files are in `outputs`, run `run_postprocess.ps1`. It extracts CPRESS and whole-model energies, checks uniformity metrics, and writes a summary CSV and comparison PNG.

## Validity checks

Use results only when all jobs complete successfully, late-stage `KE/IE` is small, `AE/IE` is preferably below 10%, and contact coverage is physically reasonable. Do not select a result only because its ranking matches the expected trend.
