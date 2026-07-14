param(
    [string]$PythonExe = "C:\Users\Hazzzard\miniconda3\envs\env_CV\python.exe"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

foreach ($Case in @("min", "natural", "max")) {
    & $PythonExe (Join-Path $ScriptDir ("01_prepare_" + $Case + ".py"))
    if ($LASTEXITCODE -ne 0) { throw "INP preparation failed: $Case" }
}
