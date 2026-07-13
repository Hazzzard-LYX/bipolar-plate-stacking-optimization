param(
    [string]$PythonExe = "C:\Users\Hazzzard\miniconda3\envs\env_CV\python.exe"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& $PythonExe (Join-Path $ScriptDir "01_generate_surfaces_and_orders.py")
& $PythonExe (Join-Path $ScriptDir "02_prepare_inp.py") min natural max
Write-Host "Surface data, stack orders, and three Abaqus input files are ready. No Abaqus job was submitted."

