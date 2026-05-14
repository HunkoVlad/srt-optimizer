param(
    [Parameter(Mandatory = $true)]
    [string]$RunDate
)

$ErrorActionPreference = "Stop"

if ($RunDate -notmatch '^\d{4}-\d{2}-\d{2}$') {
    Write-Error "RunDate must use YYYY-MM-DD format."
    exit 1
}

$pythonExe = "python"
if (Test-Path ".\.venv\Scripts\python.exe") {
    $pythonExe = ".\.venv\Scripts\python.exe"
}

$runRoot = Join-Path "data\runs" $RunDate
$rawDir = Join-Path $runRoot "raw"
$standardizedDir = Join-Path $runRoot "standardized"
$analysisDir = Join-Path $runRoot "analysis"
$settingsDir = Join-Path $runRoot "settings"

foreach ($dir in @($rawDir, $standardizedDir, $analysisDir, $settingsDir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}

$futureExport = Join-Path $rawDir "priceLabs_future_export.csv"
$priceOcc = Join-Path $rawDir "price_occ.csv"
$settingsInput = Join-Path $rawDir "pricelabs_settings_manual_input.json"
$monthlyTrends = Join-Path $rawDir "monthly_trends.csv"
$bookingsReport = Join-Path $rawDir "bookings_report.xlsx"
$kpisOnTheBooks = Join-Path $rawDir "kpis_on_the_books.xlsx"

$missingInputs = @()
foreach ($path in @($futureExport, $priceOcc, $settingsInput, $monthlyTrends, $bookingsReport)) {
    if (-not (Test-Path $path)) {
        $missingInputs += $path
    }
}
if ($missingInputs.Count -gt 0) {
    Write-Error ("Missing required raw input file(s):`n  " + ($missingInputs -join "`n  "))
    exit 1
}

function Invoke-PythonStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    Write-Host ""
    Write-Host "== $Label =="
    & $pythonExe @Arguments
    if ($LASTEXITCODE -ne 0) {
        Write-Error "$Label failed."
        exit $LASTEXITCODE
    }
}

function Get-LatestPriorRunWithFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelativePathTemplate
    )

    $runsRoot = "data\runs"
    if (-not (Test-Path $runsRoot)) {
        return $null
    }

    $priorRuns = Get-ChildItem -Path $runsRoot -Directory |
        Where-Object { $_.Name -match '^\d{4}-\d{2}-\d{2}$' -and $_.Name -lt $RunDate } |
        Sort-Object Name -Descending

    foreach ($run in $priorRuns) {
        $relativePath = $RelativePathTemplate.Replace("<run_date>", $run.Name)
        $candidate = Join-Path $run.FullName $relativePath
        if (Test-Path $candidate) {
            return @{
                RunDate = $run.Name
                Path = $candidate
            }
        }
    }

    return $null
}

$settings = Get-Content -Raw -Path $settingsInput | ConvertFrom-Json
if (-not $settings.listing_id) {
    Write-Error "Settings input must contain listing_id: $settingsInput"
    exit 1
}
$listingId = [string]$settings.listing_id

$standardizedFile = Join-Path $standardizedDir "future_daily_pricing_$RunDate.csv"
$manifestFile = Join-Path $runRoot "manifest.json"
$enrichedFile = Join-Path $analysisDir "future_daily_pricing_enriched_$RunDate.csv"
$monthlyTrendsNormalizedFile = Join-Path $analysisDir "monthly_trends_normalized_$RunDate.csv"
$bookingsReportNormalizedFile = Join-Path $analysisDir "bookings_report_normalized_$RunDate.csv"
$monthlyBookingMetricsFile = Join-Path $analysisDir "monthly_booking_metrics_$RunDate.csv"
$monthlyRevenuePaceFile = Join-Path $analysisDir "monthly_revenue_pace_$RunDate.csv"
$historicalMonthlyActualsFile = Join-Path $analysisDir "historical_monthly_actuals_$RunDate.csv"
$rollingRevenueViewFile = Join-Path $analysisDir "rolling_13_month_revenue_view_$RunDate.csv"
$monthlyRevenueSummaryFile = Join-Path $analysisDir "monthly_revenue_summary_$RunDate.md"
$emailRevenueReportFile = Join-Path $analysisDir "email_revenue_report_$RunDate.md"
$emailHtmlReportFile = Join-Path $analysisDir "email_revenue_report_$RunDate.html"
$emailDraftFile = Join-Path $analysisDir "email_revenue_report_$RunDate.eml"
$summaryFile = Join-Path $analysisDir "future_window_summary_$RunDate.csv"
$signalsFile = Join-Path $analysisDir "future_window_signals_$RunDate.csv"
$settingsSnapshotFile = Join-Path $settingsDir "pricelabs_settings_snapshot_$RunDate.json"
$settingsChangesFile = Join-Path $settingsDir "pricelabs_settings_changes_$RunDate.csv"
$signalReviewFile = Join-Path $analysisDir "future_signal_change_review_$RunDate.csv"
$runtimeConfig = Join-Path $settingsDir "pricelabs_transform_config.toml"

@"
listing_id = "$listingId"
input_path = "$($futureExport -replace '\\', '/')"
output_path = "$($standardizedFile -replace '\\', '/')"
"@ | Set-Content -Path $runtimeConfig -Encoding utf8

$env:PYTHONPATH = "src"

Invoke-PythonStep "Operational transform" @(
    "-m", "pricelabs.transform.run",
    "--config", $runtimeConfig,
    "--run-date", $RunDate,
    "--manifest-path", $manifestFile
)

Invoke-PythonStep "Future enrichment" @(
    "-m", "pricelabs.transform.enrich_future",
    "--run-date", $RunDate,
    "--standardized-file", $standardizedFile,
    "--price-occ-file", $priceOcc,
    "--output-file", $enrichedFile
)

Invoke-PythonStep "Monthly Trends normalization" @(
    "-m", "pricelabs.transform.monthly_trends",
    "--run-date", $RunDate,
    "--input-file", $monthlyTrends,
    "--output-file", $monthlyTrendsNormalizedFile
)

Invoke-PythonStep "Bookings Report normalization" @(
    "-m", "pricelabs.transform.bookings_report",
    "--run-date", $RunDate,
    "--input-file", $bookingsReport,
    "--normalized-output-file", $bookingsReportNormalizedFile,
    "--metrics-output-file", $monthlyBookingMetricsFile
)

Invoke-PythonStep "Monthly revenue pace" @(
    "-m", "pricelabs.transform.monthly_revenue_pace",
    "--run-date", $RunDate,
    "--enriched-file", $enrichedFile,
    "--monthly-trends-file", $monthlyTrendsNormalizedFile,
    "--booking-metrics-file", $monthlyBookingMetricsFile,
    "--output-file", $monthlyRevenuePaceFile
)

if (Test-Path $kpisOnTheBooks) {
    Invoke-PythonStep "Historical monthly actuals" @(
        "-m", "pricelabs.transform.historical_monthly_actuals",
        "--run-date", $RunDate,
        "--input-file", $kpisOnTheBooks,
        "--output-file", $historicalMonthlyActualsFile
    )
} else {
    Write-Host ""
    Write-Host "Skipping historical monthly actuals: optional KPI workbook not found at $kpisOnTheBooks."
}

if (Test-Path $historicalMonthlyActualsFile) {
    Invoke-PythonStep "Rolling 13-month revenue view" @(
        "-m", "pricelabs.transform.rolling_13_month_revenue_view",
        "--run-date", $RunDate,
        "--monthly-file", $monthlyRevenuePaceFile,
        "--historical-file", $historicalMonthlyActualsFile,
        "--output-file", $rollingRevenueViewFile
    )
} else {
    Invoke-PythonStep "Rolling 13-month revenue view" @(
        "-m", "pricelabs.transform.rolling_13_month_revenue_view",
        "--run-date", $RunDate,
        "--monthly-file", $monthlyRevenuePaceFile,
        "--output-file", $rollingRevenueViewFile
    )
}

Invoke-PythonStep "Monthly revenue summary" @(
    "-m", "pricelabs.transform.monthly_revenue_summary",
    "--run-date", $RunDate,
    "--rolling-file", $rollingRevenueViewFile,
    "--output-file", $monthlyRevenueSummaryFile
)

Invoke-PythonStep "Email revenue report" @(
    "-m", "pricelabs.transform.email_revenue_report",
    "--run-date", $RunDate,
    "--rolling-file", $rollingRevenueViewFile,
    "--summary-file", $monthlyRevenueSummaryFile,
    "--output-file", $emailRevenueReportFile
)

Invoke-PythonStep "Email HTML report" @(
    "-m", "pricelabs.transform.email_html_report",
    "--run-date", $RunDate,
    "--report-file", $emailRevenueReportFile,
    "--output-file", $emailHtmlReportFile
)

Invoke-PythonStep "Email draft file" @(
    "-m", "pricelabs.transform.email_draft_file",
    "--run-date", $RunDate,
    "--report-file", $emailRevenueReportFile,
    "--config-file", "config\email.toml",
    "--output-file", $emailDraftFile
)

Invoke-PythonStep "Email send mode" @(
    "-m", "pricelabs.transform.email_sender",
    "--run-date", $RunDate,
    "--report-file", $emailRevenueReportFile,
    "--html-file", $emailHtmlReportFile,
    "--config-file", "config\email.toml"
)

Invoke-PythonStep "Future window summary" @(
    "-m", "pricelabs.transform.summarize_future",
    "--run-date", $RunDate,
    "--enriched-file", $enrichedFile,
    "--output-file", $summaryFile
)

Invoke-PythonStep "Future window signals" @(
    "-m", "pricelabs.transform.signal_future",
    "--run-date", $RunDate,
    "--summary-file", $summaryFile,
    "--output-file", $signalsFile
)

Invoke-PythonStep "Settings snapshot" @(
    "-m", "pricelabs.transform.settings_snapshot",
    "--run-date", $RunDate,
    "--input-file", $settingsInput,
    "--output-file", $settingsSnapshotFile
)

$priorSnapshot = Get-LatestPriorRunWithFile "settings\pricelabs_settings_snapshot_<run_date>.json"
if ($priorSnapshot) {
    Invoke-PythonStep "Settings changes" @(
        "-m", "pricelabs.transform.settings_changes",
        "--run-date", $RunDate,
        "--prior-run-date", $priorSnapshot.RunDate,
        "--current-snapshot-file", $settingsSnapshotFile,
        "--prior-snapshot-file", $priorSnapshot.Path,
        "--output-file", $settingsChangesFile
    )
} else {
    Write-Host ""
    Write-Host "Skipping settings changes: no prior settings snapshot found under data/runs."
}

$priorSignal = Get-LatestPriorRunWithFile "analysis\future_window_signals_<run_date>.csv"
if ($priorSignal -and (Test-Path $settingsChangesFile)) {
    Invoke-PythonStep "Signal change review" @(
        "-m", "pricelabs.transform.review_signal_changes",
        "--run-date", $RunDate,
        "--prior-run-date", $priorSignal.RunDate,
        "--current-signal-file", $signalsFile,
        "--prior-signal-file", $priorSignal.Path,
        "--settings-changes-file", $settingsChangesFile,
        "--output-file", $signalReviewFile
    )
} elseif (-not $priorSignal) {
    Write-Host ""
    Write-Host "Skipping signal change review: no prior signal file found under data/runs."
} else {
    Write-Host ""
    Write-Host "Skipping signal change review: settings changes file was not created."
}

Write-Host ""
Write-Host "Weekly pipeline complete."
Write-Host "Run folder: $runRoot"
Write-Host "Raw inputs retained in: $rawDir"
Write-Host "Standardized outputs: $standardizedDir"
Write-Host "Analysis outputs: $analysisDir"
Write-Host "Settings outputs: $settingsDir"
