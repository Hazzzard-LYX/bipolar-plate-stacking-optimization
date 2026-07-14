param(
    [string]$AbaqusLauncher = "D:\SIMULIA\EstProducts\2023\win_b64\resources\install\cmdDirFeature\launcher.bat",
    [string[]]$Cases = @("min", "natural", "max"),
    [int]$Cpus = 1
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$OutputDir = Join-Path (Split-Path -Parent $ScriptDir) "outputs"
$Jobs = @{
    min = "exp34_exact_min_explicit_smallslip_friction_contact"
    natural = "exp34_natural_explicit_smallslip_friction_contact"
    max = "exp34_exact_max_explicit_smallslip_friction_contact"
}

Push-Location $OutputDir
try {
    foreach ($Case in $Cases) {
        $Job = $Jobs[$Case]
        if (-not $Job) { throw "Unknown case: $Case" }
        if (-not (Test-Path -LiteralPath ($Job + ".inp"))) {
            throw "Missing input file: $Job.inp. Run 00_prepare_all.ps1 first."
        }
        Write-Host "Submitting $Job"
        & $AbaqusLauncher "job=$Job" "input=$Job.inp" "cpus=$Cpus" interactive ask_delete=OFF
        if ($LASTEXITCODE -ne 0) { throw "Abaqus job failed: $Job" }
    }
}
finally {
    Pop-Location
}
