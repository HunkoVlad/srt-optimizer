param(
    [Parameter(Mandatory = $true)]
    [string]$RunDate,

    [string]$ConfigFile = "config\email.toml"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($RunDate -notmatch '^\d{4}-\d{2}-\d{2}$') {
    Write-Error "RunDate must use YYYY-MM-DD format."
    exit 1
}

$scriptRoot = $PSScriptRoot
$projectRoot = Split-Path -Parent $scriptRoot
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
}

$analysisDir = Join-Path (Join-Path (Join-Path $projectRoot "data\runs") $RunDate) "analysis"
$reportFile = Join-Path $analysisDir "email_revenue_report_$RunDate.md"
$htmlFile = Join-Path $analysisDir "email_revenue_report_$RunDate.html"
$resultFile = Join-Path $analysisDir "email_revenue_report_send_result_$RunDate.csv"

Push-Location $projectRoot
try {
    & $pythonExe -m pricelabs.transform.email_sender `
        --run-date $RunDate `
        --report-file $reportFile `
        --html-file $htmlFile `
        --config-file $ConfigFile `
        --result-file $resultFile `
        --explicit-send
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}

exit 0
