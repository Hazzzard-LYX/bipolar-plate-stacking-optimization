param(
    [string]$SourceRoot = ""
)

$ErrorActionPreference = "Stop"
$TargetRoot = $PSScriptRoot

if (-not $SourceRoot) {
    $Parent = Split-Path -Parent $TargetRoot
    $SourceRoot = Get-ChildItem -LiteralPath $Parent -Directory |
        Where-Object {
            $_.FullName -ne $TargetRoot -and
            (Get-ChildItem -LiteralPath $_.FullName -Directory |
                Where-Object { $_.Name -match "^\d+-" }).Count -ge 10
        } |
        Select-Object -First 1 -ExpandProperty FullName
}

if (-not $SourceRoot) {
    throw "Cannot locate the numbered experiment archive. Pass -SourceRoot explicitly."
}

$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
$Experiments = Get-ChildItem -LiteralPath $SourceRoot -Directory | ForEach-Object {
    if ($_.Name -match "^(\d+)-(.*)$") {
        [pscustomobject]@{
            Number = [int]$matches[1]
            Description = $matches[2]
            Source = $_.FullName
        }
    }
} | Sort-Object Number

foreach ($Experiment in $Experiments) {
    $SourceScripts = Get-ChildItem -LiteralPath $Experiment.Source -Directory |
        Where-Object {
            (Get-ChildItem -LiteralPath $_.FullName -File -Filter "*.py").Count -gt 0
        } |
        Select-Object -First 1 -ExpandProperty FullName
    if (-not $SourceScripts) {
        continue
    }
    $DestinationName = "{0:D2}-{1}" -f $Experiment.Number, $Experiment.Description
    $Destination = Join-Path $TargetRoot $DestinationName
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Get-ChildItem -LiteralPath $SourceScripts -Force |
        Where-Object { $_.Name -ne "__pycache__" } |
        ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $Destination -Recurse -Force
        }
    Write-Host "Updated $DestinationName"
}

Write-Host "Sync complete. Existing files are updated; no repository files are deleted."
