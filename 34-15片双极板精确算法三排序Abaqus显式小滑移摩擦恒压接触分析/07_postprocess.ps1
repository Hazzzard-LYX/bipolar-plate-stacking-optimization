param(
    [string]$AbaqusLauncher = "D:\SIMULIA\EstProducts\2023\win_b64\resources\install\cmdDirFeature\launcher.bat",
    [string]$PythonExe = "C:\Users\Hazzzard\miniconda3\envs\env_CV\python.exe"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$OutputDir = Join-Path (Split-Path -Parent $ScriptDir) "outputs"
$Cases = @(
    @{ Job = "exp34_exact_min_explicit_smallslip_friction_contact"; Order = "[2,14,3,5,4,12,11,8,13,1,10,7,9,15,6]" },
    @{ Job = "exp34_natural_explicit_smallslip_friction_contact"; Order = "[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]" },
    @{ Job = "exp34_exact_max_explicit_smallslip_friction_contact"; Order = "[11,1,2,10,14,9,13,7,5,6,3,15,8,4,12]" }
)

Push-Location $OutputDir
try {
    foreach ($Case in $Cases) {
        & $AbaqusLauncher python (Join-Path $ScriptDir "03_extract_cpress_csv.py") $Case.Job $Case.Order
        if ($LASTEXITCODE -ne 0) { throw "CPRESS extraction failed: $($Case.Job)" }
        & $AbaqusLauncher python (Join-Path $ScriptDir "06_extract_energy.py") $Case.Job
        if ($LASTEXITCODE -ne 0) { throw "Energy extraction failed: $($Case.Job)" }
    }
}
finally {
    Pop-Location
}

& $PythonExe (Join-Path $ScriptDir "05_compare_exp34_exact_contact.py")
if ($LASTEXITCODE -ne 0) { throw "Uniformity comparison failed" }
& $PythonExe (Join-Path $ScriptDir "08_compare_exp28_exp34.py")
if ($LASTEXITCODE -ne 0) { throw "Experiment 28/34 comparison failed" }
