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
$rawDir = Join-Path $runRoot "raw"
$logsDir = Join-Path $runRoot "logs"
$analysisDir = Join-Path $runRoot "analysis"
$logFile = Join-Path $logsDir "monday_full_report_$RunDate.log"

New-Item -ItemType Directory -Path $runRoot -Force | Out-Null
New-Item -ItemType Directory -Path $rawDir -Force | Out-Null
New-Item -ItemType Directory -Path $logsDir -Force | Out-Null

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
}

function Write-MondayLog {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] $Message"
    Add-Content -Path $logFile -Value $line -Encoding utf8
    Write-Host $line
}

function Invoke-MondayStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,
        [bool]$Blocking = $true
    )

    Write-Host ""
    Write-Host "== $Label =="
    Write-MondayLog "started: $Label"
    $script:LastMondayStepSuccess = $false
    try {
        & $Command
        $exitCode = $LASTEXITCODE
        if ($null -eq $exitCode) {
            $exitCode = 0
        }
        if ($exitCode -eq 0) {
            Write-MondayLog "completed: $Label"
            $script:LastMondayStepSuccess = $true
            return
        }
        if ($Blocking) {
            Write-MondayLog "failed_blocking: $Label exit_code=$exitCode"
            exit $exitCode
        }
        Write-MondayLog "failed_nonblocking: $Label exit_code=$exitCode"
        return
    }
    catch {
        if ($Blocking) {
            Write-MondayLog "failed_blocking: $Label exception=$($_.Exception.Message)"
            exit 1
        }
        Write-MondayLog "failed_nonblocking: $Label exception=$($_.Exception.Message)"
        return
    }
}

Write-MondayLog "Monday full report workflow started."
Write-MondayLog "Run date: $RunDate"
Write-MondayLog "Project root: $projectRoot"
Write-MondayLog "Run folder: $runRoot"
Write-MondayLog "Python executable: $pythonExe"
Write-MondayLog "Airbnb remains diagnostic only; PriceLabs remains source of truth for pricing/revenue metrics."
Write-MondayLog "Persistent Airbnb browser profile is local-only and must not be copied to evidence: .local/browser_profiles/airbnb"

$requiredRawFiles = @(
    (Join-Path $rawDir "priceLabs_future_export.csv"),
    (Join-Path $rawDir "price_occ.csv"),
    (Join-Path $rawDir "monthly_trends.csv"),
    (Join-Path $rawDir "bookings_report.xlsx")
)

$missingRequired = @()
foreach ($path in $requiredRawFiles) {
    if (-not (Test-Path $path)) {
        $missingRequired += $path
    }
}

if ($missingRequired.Count -gt 0) {
    Write-MondayLog "failed_blocking: PriceLabs required raw input preflight."
    Write-MondayLog "Missing required raw file(s):"
    foreach ($path in $missingRequired) {
        Write-MondayLog "  $path"
    }
    Write-MondayLog "Weekly report not executed because PriceLabs required inputs are incomplete."
    exit 2
}
Write-MondayLog "completed: PriceLabs required raw input preflight."

$airbnbSearchSuccess = $false
$airbnbCaptureSuccess = $false
$airbnbPromoteSuccess = $false
$airbnbDiagnosticsSuccess = $false
$weeklyReportSuccess = $false

Push-Location $projectRoot
try {
    $env:PYTHONPATH = "src"

    Invoke-MondayStep "Airbnb search screening" {
        & $pythonExe -m airbnb.airbnb_search_screening --run-date $RunDate --include-filtered-scenarios
    } -Blocking $false
    $airbnbSearchSuccess = $script:LastMondayStepSuccess

    Write-MondayLog "Airbnb funnel capture uses persistent profile with manual MFA fallback when Airbnb requires login."
    Invoke-MondayStep "Airbnb funnel capture" {
        & $pythonExe -m airbnb.download_diagnostics --run-date $RunDate --mode capture-headed-and-validate --use-persistent-profile
    } -Blocking $false
    $airbnbCaptureSuccess = $script:LastMondayStepSuccess

    Invoke-MondayStep "Promote Airbnb staged diagnostics" {
        & $pythonExe -m airbnb.download_diagnostics --run-date $RunDate --mode promote-staged
    } -Blocking $false
    $airbnbPromoteSuccess = $script:LastMondayStepSuccess

    Invoke-MondayStep "Airbnb diagnostics" {
        & $pythonExe -m airbnb.run_diagnostics --run-date $RunDate
    } -Blocking $false
    $airbnbDiagnosticsSuccess = $script:LastMondayStepSuccess

    Invoke-MondayStep "Weekly pipeline and report generation" {
        & (Join-Path $projectRoot "run_weekly_pipeline.ps1") -RunDate $RunDate
    } -Blocking $true
    $weeklyReportSuccess = $script:LastMondayStepSuccess
}
finally {
    Pop-Location
}

$emailMarkdownPath = Join-Path $analysisDir "email_revenue_report_$RunDate.md"
$emailHtmlPath = Join-Path $analysisDir "email_revenue_report_$RunDate.html"
$evidenceBundlePath = Join-Path $analysisDir "evidence_bundle_$RunDate"
$emailDraftPath = Join-Path $analysisDir "email_revenue_report_$RunDate.eml"

Write-Host ""
Write-Host "Monday full report completed."
Write-MondayLog "Monday full report completed."
Write-MondayLog "PriceLabs core: success"
Write-MondayLog "Airbnb search screening: $(if ($airbnbSearchSuccess) { 'success' } else { 'failure_nonblocking' })"
Write-MondayLog "Airbnb funnel diagnostics: $(if ($airbnbCaptureSuccess -and $airbnbPromoteSuccess -and $airbnbDiagnosticsSuccess) { 'success' } else { 'failure_nonblocking_or_unavailable' })"
Write-MondayLog "Weekly report: $(if ($weeklyReportSuccess) { 'success' } else { 'failure' })"

Write-Host "PriceLabs core: success"
Write-Host "Airbnb search screening: $(if ($airbnbSearchSuccess) { 'success' } else { 'failure_nonblocking' })"
Write-Host "Airbnb funnel diagnostics: $(if ($airbnbCaptureSuccess -and $airbnbPromoteSuccess -and $airbnbDiagnosticsSuccess) { 'success' } else { 'failure_nonblocking_or_unavailable' })"
Write-Host "Weekly report: $(if ($weeklyReportSuccess) { 'success' } else { 'failure' })"
Write-Host "Report path: $emailMarkdownPath"
Write-Host "HTML report path: $emailHtmlPath"
Write-Host "Evidence bundle path: $evidenceBundlePath"
if (Test-Path $emailDraftPath) {
    Write-Host "Email draft path: $emailDraftPath"
}

Write-MondayLog "Report path: $emailMarkdownPath"
Write-MondayLog "HTML report path: $emailHtmlPath"
Write-MondayLog "Evidence bundle path: $evidenceBundlePath"
if (Test-Path $emailDraftPath) {
    Write-MondayLog "Email draft path: $emailDraftPath"
}
Write-MondayLog "Monday full report workflow finished."

exit 0
