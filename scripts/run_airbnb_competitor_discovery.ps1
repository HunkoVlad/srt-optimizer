param(
    [Parameter(Mandatory = $true)]
    [string]$RunDate,

    [int]$MaxCards = 100,

    [int]$MaxPages = 6
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($RunDate -eq "today") {
    $RunDate = Get-Date -Format "yyyy-MM-dd"
}
elseif ($RunDate -notmatch '^\d{4}-\d{2}-\d{2}$') {
    Write-Error "RunDate must use YYYY-MM-DD format or today."
    exit 1
}

$scriptRoot = $PSScriptRoot
$projectRoot = Split-Path -Parent $scriptRoot
$runRoot = Join-Path (Join-Path $projectRoot "data\runs") $RunDate
$analysisDir = Join-Path $runRoot "analysis"
$logsDir = Join-Path $runRoot "logs"
$manualInputDir = Join-Path $projectRoot "data\manual_inputs"
$inputFile = Join-Path $manualInputDir "airbnb_competitor_urls_$RunDate.csv"
$logFile = Join-Path $logsDir "airbnb_competitor_discovery_wrapper_$RunDate.log"

New-Item -ItemType Directory -Path $analysisDir -Force | Out-Null
New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
New-Item -ItemType Directory -Path $manualInputDir -Force | Out-Null

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
}

function Write-DiscoveryLog {
    param([Parameter(Mandatory = $true)][string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] $Message"
    Add-Content -Path $logFile -Value $line -Encoding utf8
    Write-Host $line
}

Write-DiscoveryLog "Airbnb competitor discovery wrapper started."
Write-DiscoveryLog "Run date: $RunDate"
Write-DiscoveryLog "No PriceLabs preflight is run by this Airbnb-only diagnostic command."
Write-DiscoveryLog "This command does not generate weekly revenue reports or PriceLabs recommendations."
Write-DiscoveryLog "Competitor URL output path: $inputFile"

Push-Location $projectRoot
try {
    $env:PYTHONPATH = "src"
    & $pythonExe -m airbnb.airbnb_competitor_discovery --run-date $RunDate --max-cards $MaxCards --max-pages $MaxPages
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) {
        $exitCode = 0
    }
    if ($exitCode -ne 0) {
        Write-DiscoveryLog "Airbnb competitor discovery failed with exit_code=$exitCode"
        exit $exitCode
    }
}
finally {
    Pop-Location
}

$reviewPath = Join-Path $analysisDir "airbnb_competitor_url_review_$RunDate.csv"
$summaryPath = Join-Path $analysisDir "airbnb_competitor_pattern_summary_$RunDate.csv"
$gapsPath = Join-Path $analysisDir "airbnb_competitor_actionable_gaps_$RunDate.md"

Write-DiscoveryLog "Review output path: $reviewPath"
Write-DiscoveryLog "Summary output path: $summaryPath"
Write-DiscoveryLog "Actionable gaps output path: $gapsPath"
Write-DiscoveryLog "Airbnb competitor discovery wrapper finished."

Write-Host "Competitor URL input path: $inputFile"
Write-Host "Review output path: $reviewPath"
Write-Host "Summary output path: $summaryPath"
Write-Host "Actionable gaps output path: $gapsPath"

exit 0
