param(
    [string]$AbaqusCommand = "abaqus",
    [switch]$Interactive
)

$ErrorActionPreference = "Stop"

$ExperimentDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$OutputDir = Join-Path $ExperimentDir "outputs"
$JobName = "exp1_plate01_plate02_contact"
$InpPath = Join-Path $OutputDir ($JobName + ".inp")

if (-not (Test-Path $InpPath)) {
    throw "Input file not found: $InpPath. Run 01_prepare_inp.py first."
}

Push-Location $OutputDir
try {
    $mode = "interactive"
    if (-not $Interactive) {
        $mode = "background"
    }
    & $AbaqusCommand job=$JobName input=$InpPath $mode ask_delete=OFF
}
finally {
    Pop-Location
}
