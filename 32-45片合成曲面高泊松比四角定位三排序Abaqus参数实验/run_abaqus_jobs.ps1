param(
    [string]$AbaqusLauncher = "D:\SIMULIA\EstProducts\2023\win_b64\resources\install\cmdDirFeature\launcher.bat",
    [string[]]$Cases = @("min", "natural", "max"),
    [int]$Cpus = 1
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExperimentDir = Split-Path -Parent $ScriptDir
$OutputDir = Join-Path $ExperimentDir "outputs"
$ConfigText = Get-Content -LiteralPath (Join-Path $ScriptDir "config.py") -Raw
$ExperimentId = [regex]::Match($ConfigText, "EXPERIMENT_ID\s*=\s*(\d+)").Groups[1].Value
$PlateCount = [regex]::Match($ConfigText, "PLATE_COUNT\s*=\s*(\d+)").Groups[1].Value

Push-Location $OutputDir
try {
    foreach ($Case in $Cases) {
        $Job = "exp${ExperimentId}_${Case}_${PlateCount}plates"
        if (-not (Test-Path -LiteralPath ($Job + ".inp"))) {
            throw "Missing input file: $Job.inp. Run run_prepare_only.ps1 first."
        }
        Write-Host "Submitting $Job"
        & $AbaqusLauncher "job=$Job" "input=$Job.inp" "cpus=$Cpus" interactive ask_delete=OFF
        if ($LASTEXITCODE -ne 0) {
            throw "Abaqus job failed: $Job"
        }
    }
}
finally {
    Pop-Location
}

