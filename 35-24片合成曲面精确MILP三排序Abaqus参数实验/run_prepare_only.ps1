param(
    [string]$PythonExe = "C:\Users\Hazzzard\miniconda3\envs\env_CV\python.exe"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& $PythonExe (Join-Path $ScriptDir "01_prepare_exact_orders.py")
if ($LASTEXITCODE -ne 0) { throw "Exact MILP ordering failed." }
& $PythonExe (Join-Path $ScriptDir "02_prepare_inp.py") min natural max
if ($LASTEXITCODE -ne 0) { throw "Abaqus input preparation failed." }
Write-Host "Exact stack orders and three Abaqus input files are ready. No Abaqus job was submitted."
