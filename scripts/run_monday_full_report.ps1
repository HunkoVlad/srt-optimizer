param(
    [string]$RunDate = (Get-Date -Format "yyyy-MM-dd"),
    [switch]$AutoSendStayFi
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
$logsDir = Join-Path $runRoot "logs"
$analysisDir = Join-Path $runRoot "analysis"
$logFile = Join-Path $logsDir "monday_full_report_$RunDate.log"
$scheduledLogFile = Join-Path $logsDir "scheduled_pipeline_$RunDate.log"
$summaryFile = Join-Path $analysisDir "stayfi_anniversary_email_summary_$RunDate.csv"
$sendResultsFile = Join-Path $analysisDir "stayfi_anniversary_email_send_results_$RunDate.csv"
$scheduledWrapper = Join-Path $scriptRoot "run_scheduled_weekly_pipeline.ps1"
$stayfiSendWrapper = Join-Path $scriptRoot "send_stayfi_anniversary_emails.ps1"

New-Item -ItemType Directory -Path $runRoot -Force | Out-Null
New-Item -ItemType Directory -Path $logsDir -Force | Out-Null

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

function Convert-ToCount {
    param([object]$Value)

    if ($null -eq $Value) {
        return 0
    }
    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return 0
    }
    $number = 0
    if ([int]::TryParse($text, [ref]$number)) {
        return $number
    }
    return 0
}

function Get-RowValue {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Row,
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [string]$Fallback = ""
    )

    if ($Row.PSObject.Properties.Name -contains $Name) {
        $value = $Row.$Name
        if ($null -ne $value -and -not [string]::IsNullOrWhiteSpace([string]$value)) {
            return [string]$value
        }
    }
    return $Fallback
}

function Write-ResultTable {
    param(
        [Parameter(Mandatory = $true)]
        [array]$Rows,
        [Parameter(Mandatory = $true)]
        [string[]]$Columns
    )

    foreach ($row in $Rows) {
        $parts = @()
        foreach ($column in $Columns) {
            $value = Get-RowValue -Row $row -Name $column -Fallback ""
            $parts += "$column=$value"
        }
        Write-MondayLog ("  " + ($parts -join " | "))
    }
}

Write-MondayLog "Monday full report workflow started."
Write-MondayLog "Resolved RunDate: $RunDate"
Write-MondayLog "Project root: $projectRoot"
Write-MondayLog "Run folder: $runRoot"
Write-MondayLog "AutoSendStayFi enabled: $($AutoSendStayFi.IsPresent)"
Write-MondayLog "Safety: default mode never sends StayFi emails without exact SEND confirmation."
Write-MondayLog "Safety: AutoSendStayFi can send only after weekly pipeline success and a successful dry-run with sendable recipients."
Write-MondayLog "PriceLabs recommendation logic and pricing logic are not changed by this wrapper."

Push-Location $projectRoot
try {
    Write-MondayLog "started: scheduled weekly pipeline"
    & $scheduledWrapper -RunDate $RunDate 2>&1 | ForEach-Object {
        Write-MondayLog "PIPELINE: $_"
    }
    $pipelineExitCode = $LASTEXITCODE
    if ($null -eq $pipelineExitCode) {
        $pipelineExitCode = 0
    }
    if ($pipelineExitCode -ne 0) {
        Write-MondayLog "failed_blocking: scheduled weekly pipeline exit_code=$pipelineExitCode"
        if (Test-Path $scheduledLogFile) {
            Write-MondayLog "Scheduled pipeline log: $scheduledLogFile"
            foreach ($line in Get-Content -Path $scheduledLogFile) {
                Write-MondayLog "SCHEDULED_LOG: $line"
            }
        }
        Write-MondayLog "StayFi send skipped because weekly pipeline failed."
        exit $pipelineExitCode
    }
    Write-MondayLog "completed: scheduled weekly pipeline"
}
finally {
    Pop-Location
}

if (-not (Test-Path $summaryFile)) {
    Write-MondayLog "StayFi summary missing: $summaryFile"
    Write-MondayLog "No StayFi anniversary emails to send this week."
    exit 0
}

$summaryRows = @(Import-Csv -Path $summaryFile)
if ($summaryRows.Count -eq 0) {
    Write-MondayLog "StayFi summary file has no rows: $summaryFile"
    Write-MondayLog "No StayFi anniversary emails to send this week."
    exit 0
}

$summary = $summaryRows[0]
$windowStart = Get-RowValue -Row $summary -Name "anniversary_audience_window_start"
$windowEnd = Get-RowValue -Row $summary -Name "anniversary_audience_window_end"
$rowsInAudienceWindow = Convert-ToCount (Get-RowValue -Row $summary -Name "rows_in_audience_window")
$eligibleGuests = Convert-ToCount (Get-RowValue -Row $summary -Name "eligible_guests")
$draftsPrepared = Convert-ToCount (Get-RowValue -Row $summary -Name "drafts_prepared_csv" -Fallback (Get-RowValue -Row $summary -Name "drafts_created"))
$skippedDuplicates = Convert-ToCount (Get-RowValue -Row $summary -Name "skipped_duplicates_from_log" -Fallback (Get-RowValue -Row $summary -Name "skipped_duplicates"))
$excludedNoOptIn = Convert-ToCount (Get-RowValue -Row $summary -Name "excluded_no_opt_in")
$excludedBadRating = Convert-ToCount (Get-RowValue -Row $summary -Name "excluded_bad_rating")
$dateParseFailures = Convert-ToCount (Get-RowValue -Row $summary -Name "date_parse_failed")

Write-MondayLog "StayFi anniversary summary:"
Write-MondayLog "  anniversary audience window: $windowStart to $windowEnd"
Write-MondayLog "  rows in audience window: $rowsInAudienceWindow"
Write-MondayLog "  eligible guests: $eligibleGuests"
Write-MondayLog "  draft-ready CSV records prepared: $draftsPrepared"
Write-MondayLog "  skipped duplicates from permanent log: $skippedDuplicates"
Write-MondayLog "  excluded no opt-in: $excludedNoOptIn"
Write-MondayLog "  excluded bad rating: $excludedBadRating"
Write-MondayLog "  date parse failures: $dateParseFailures"

if ($eligibleGuests -eq 0 -or $draftsPrepared -eq 0) {
    Write-MondayLog "No StayFi anniversary emails to send this week."
    exit 0
}

Push-Location $projectRoot
try {
    Write-MondayLog "started: StayFi anniversary email dry-run"
    & $stayfiSendWrapper -RunDate $RunDate -DryRun 2>&1 | ForEach-Object {
        Write-MondayLog "STAYFI_DRY_RUN: $_"
    }
    $dryRunExitCode = $LASTEXITCODE
    if ($null -eq $dryRunExitCode) {
        $dryRunExitCode = 0
    }
    if ($dryRunExitCode -ne 0) {
        Write-MondayLog "failed_blocking: StayFi anniversary email dry-run exit_code=$dryRunExitCode"
        exit $dryRunExitCode
    }
    Write-MondayLog "completed: StayFi anniversary email dry-run"
}
finally {
    Pop-Location
}

if (-not (Test-Path $sendResultsFile)) {
    Write-MondayLog "Dry-run result file missing: $sendResultsFile"
    Write-MondayLog "Dry-run found no sendable recipients."
    exit 0
}

$dryRunRows = @(Import-Csv -Path $sendResultsFile)
$sendableRows = @($dryRunRows | Where-Object { $_.send_status -eq "dry_run_would_send" })

Write-MondayLog "StayFi dry-run recipient list:"
Write-ResultTable -Rows $dryRunRows -Columns @("email", "subject", "send_status")

if ($sendableRows.Count -eq 0) {
    Write-MondayLog "Dry-run found no sendable recipients."
    exit 0
}

if ($AutoSendStayFi.IsPresent) {
    Write-MondayLog "AutoSendStayFi enabled; sending StayFi anniversary emails after successful dry-run."
}
else {
    $confirmation = Read-Host "Send these StayFi anniversary emails now? Type SEND to continue"
    if ($confirmation -ne "SEND") {
        Write-MondayLog "Send skipped by user. Dry-run results are available for review."
        exit 0
    }
}

Push-Location $projectRoot
try {
    Write-MondayLog "started: StayFi anniversary email real send"
    & $stayfiSendWrapper -RunDate $RunDate 2>&1 | ForEach-Object {
        Write-MondayLog "STAYFI_SEND: $_"
    }
    $sendExitCode = $LASTEXITCODE
    if ($null -eq $sendExitCode) {
        $sendExitCode = 0
    }
    if ($sendExitCode -ne 0) {
        Write-MondayLog "failed_blocking: StayFi anniversary email real send exit_code=$sendExitCode"
        exit $sendExitCode
    }
    Write-MondayLog "completed: StayFi anniversary email real send"
}
finally {
    Pop-Location
}

if (Test-Path $sendResultsFile) {
    $sendRows = @(Import-Csv -Path $sendResultsFile)
    Write-MondayLog "StayFi final send results:"
    Write-ResultTable -Rows $sendRows -Columns @("email", "send_status", "gmail_message_id", "sent_at", "error_message")
    Write-MondayLog "StayFi final send result path: $sendResultsFile"
}

Write-MondayLog "Monday full report workflow finished."
exit 0
