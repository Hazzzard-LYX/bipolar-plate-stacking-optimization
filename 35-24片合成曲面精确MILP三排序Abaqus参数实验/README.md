# Experiment 35 scripts

This experiment repeats Experiment 30 with identical surface CSV files and Abaqus physics. The only algorithmic change is that the minimum and maximum open Hamiltonian paths are solved exactly with a MILP and iterative subtour cuts.

## Run order

1. `01_prepare_exact_orders.py`: read the copied Experiment 30 surfaces and prove exact min/max orders.
2. `02_prepare_inp.py`: generate the three Abaqus input files.
3. `run_abaqus_jobs.ps1`: run `min`, `natural`, and `max` sequentially.
4. `run_postprocess.ps1`: extract CPRESS, energy, and displacement, then build summary plots.
5. `07_plot_deformation_maps.py`: generate centered U3 maps and stack-position profiles.

The Python environment is `env_CV`; the finite-element analyses use Abaqus/Explicit 2023.
