param(
    [Parameter(Mandatory = $true)]
    [string]$RunDate
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
$inputFile = Join-Path (Join-Path $projectRoot "data\manual_inputs") "airbnb_competitor_urls_$RunDate.csv"
$logFile = Join-Path $logsDir "airbnb_competitor_url_review_wrapper_$RunDate.log"

New-Item -ItemType Directory -Path $analysisDir -Force | Out-Null
New-Item -ItemType Directory -Path $logsDir -Force | Out-Null

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
}

function Write-ReviewLog {
    param([Parameter(Mandatory = $true)][string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] $Message"
    Add-Content -Path $logFile -Value $line -Encoding utf8
    Write-Host $line
}

Write-ReviewLog "Airbnb competitor URL review wrapper started."
Write-ReviewLog "Run date: $RunDate"
Write-ReviewLog "Input file: $inputFile"
Write-ReviewLog "No PriceLabs preflight is run by this Airbnb-only diagnostic command."
Write-ReviewLog "This command does not generate weekly revenue reports or PriceLabs recommendations."

Push-Location $projectRoot
try {
    $env:PYTHONPATH = "src"
    & $pythonExe -m airbnb.airbnb_competitor_url_review --run-date $RunDate
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) {
        $exitCode = 0
    }
    if ($exitCode -ne 0) {
        Write-ReviewLog "Airbnb competitor URL review failed with exit_code=$exitCode"
        exit $exitCode
    }
}
finally {
    Pop-Location
}

$reviewPath = Join-Path $analysisDir "airbnb_competitor_url_review_$RunDate.csv"
$summaryPath = Join-Path $analysisDir "airbnb_competitor_pattern_summary_$RunDate.csv"
$gapsPath = Join-Path $analysisDir "airbnb_competitor_actionable_gaps_$RunDate.md"

Write-ReviewLog "Review output path: $reviewPath"
Write-ReviewLog "Summary output path: $summaryPath"
Write-ReviewLog "Actionable gaps output path: $gapsPath"
Write-ReviewLog "Airbnb competitor URL review wrapper finished."

Write-Host "Review output path: $reviewPath"
Write-Host "Summary output path: $summaryPath"
Write-Host "Actionable gaps output path: $gapsPath"

exit 0
