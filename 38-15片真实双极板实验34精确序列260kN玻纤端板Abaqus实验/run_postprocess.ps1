param(
    [string]$AbaqusLauncher = "D:\SIMULIA\EstProducts\2023\win_b64\resources\install\cmdDirFeature\launcher.bat",
    [string]$PythonExe = "C:\Users\Hazzzard\miniconda3\envs\env_CV\python.exe"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigText = Get-Content -LiteralPath (Join-Path $ScriptDir "config.py") -Raw
$ExperimentId = [regex]::Match($ConfigText, "EXPERIMENT_ID\s*=\s*(\d+)").Groups[1].Value
$PlateCount = [regex]::Match($ConfigText, "PLATE_COUNT\s*=\s*(\d+)").Groups[1].Value

foreach ($Case in @("min", "natural", "max")) {
    $Job = "exp${ExperimentId}_${Case}_${PlateCount}plates"
    & $AbaqusLauncher python (Join-Path $ScriptDir "03_extract_cpress_csv.py") $Job $Case 17 9
    if ($LASTEXITCODE -ne 0) { throw "CPRESS extraction failed: $Job" }
    & $AbaqusLauncher python (Join-Path $ScriptDir "04_extract_energy.py") $Job
    if ($LASTEXITCODE -ne 0) { throw "Energy extraction failed: $Job" }
    & $AbaqusLauncher python (Join-Path $ScriptDir "06_extract_endplate_response.py") $Job
    if ($LASTEXITCODE -ne 0) { throw "Endplate response extraction failed: $Job" }
}
& $PythonExe (Join-Path $ScriptDir "05_compare_results.py")
