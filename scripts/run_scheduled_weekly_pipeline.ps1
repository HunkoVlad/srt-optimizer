param(
    [string]$RunDate = (Get-Date -Format "yyyy-MM-dd")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($RunDate -notmatch '^\d{4}-\d{2}-\d{2}$') {
    Write-Error "RunDate must use YYYY-MM-DD format."
    exit 1
}

$scriptRoot = $PSScriptRoot
$projectRoot = Split-Path -Parent $scriptRoot
$runRoot = Join-Path (Join-Path $projectRoot "data\runs") $RunDate
$rawDir = Join-Path $runRoot "raw"
$logDir = Join-Path $runRoot "logs"
$logFile = Join-Path $logDir "scheduled_pipeline_$RunDate.log"

New-Item -ItemType Directory -Path $logDir -Force | Out-Null

function Write-Log {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] $Message"
    Add-Content -Path $logFile -Value $line -Encoding utf8
    Write-Host $line
}

function Read-EmailConfigSummary {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ConfigPath
    )

    if (-not (Test-Path $ConfigPath)) {
        return "config/email.toml not found; email defaults handled by pipeline."
    }

    $mode = "<not set>"
    $smtpEnabled = "<not set>"
    $reportFormat = "<not set>"
    $section = ""

    foreach ($line in Get-Content -Path $ConfigPath) {
        $trimmed = $line.Trim()
        if ($trimmed -match '^\[(.+)\]$') {
            $section = $Matches[1]
            continue
        }
        if ($section -eq "email" -and $trimmed -match '^mode\s*=\s*"?([^"#]+)"?') {
            $mode = $Matches[1].Trim()
        }
        if ($section -eq "smtp" -and $trimmed -match '^enabled\s*=\s*([^#]+)') {
            $smtpEnabled = $Matches[1].Trim()
        }
        if ($section -eq "report" -and $trimmed -match '^format\s*=\s*"?([^"#]+)"?') {
            $reportFormat = $Matches[1].Trim()
        }
    }

    return "config/email.toml found; email.mode=$mode; smtp.enabled=$smtpEnabled; report.format=$reportFormat; secrets not inspected."
}

Write-Log "Scheduled weekly pipeline wrapper started."
Write-Log "Run date: $RunDate"
Write-Log "Project root: $projectRoot"
Write-Log "Raw folder: $rawDir"

$requiredRawFiles = @(
    (Join-Path $rawDir "priceLabs_future_export.csv"),
    (Join-Path $rawDir "price_occ.csv"),
    (Join-Path $rawDir "pricelabs_settings_manual_input.json"),
    (Join-Path $rawDir "monthly_trends.csv"),
    (Join-Path $rawDir "bookings_report.xlsx")
)
$optionalKpiFile = Join-Path $rawDir "kpis_on_the_books.xlsx"

$missingRequired = @()
foreach ($path in $requiredRawFiles) {
    if (-not (Test-Path $path)) {
        $missingRequired += $path
    }
}

if ($missingRequired.Count -gt 0) {
    Write-Log "Required file check failed. Missing required raw file(s):"
    foreach ($path in $missingRequired) {
        Write-Log "  $path"
    }
    Write-Log "Pipeline not executed because required inputs are incomplete."
    Write-Log "Scheduled weekly pipeline wrapper failed. Exit code: 2"
    Write-Log "End time: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")"
    exit 2
}

Write-Log "Required file check passed."

if (Test-Path $optionalKpiFile) {
    Write-Log "Optional KPI file found: $optionalKpiFile"
} else {
    Write-Log "Optional KPI file missing; continuing without historical KPI input: $optionalKpiFile"
}

$emailConfigPath = Join-Path (Join-Path $projectRoot "config") "email.toml"
Write-Log (Read-EmailConfigSummary -ConfigPath $emailConfigPath)

$pipelineScript = Join-Path $projectRoot "run_weekly_pipeline.ps1"
$pipelineCommand = ".\run_weekly_pipeline.ps1 -RunDate $RunDate"
Write-Log "Pipeline command executed: $pipelineCommand"

$exitCode = 0
try {
    Push-Location $projectRoot
    $pipelineOutput = & $pipelineScript -RunDate $RunDate 2>&1
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) {
        $exitCode = 0
    }
    foreach ($line in $pipelineOutput) {
        Write-Log "PIPELINE: $line"
    }
} catch {
    $exitCode = 1
    Write-Log "Pipeline failed with exception: $($_.Exception.Message)"
} finally {
    Pop-Location
}

if ($exitCode -eq 0) {
    Write-Log "Pipeline completed successfully."
    $expectedOutputs = @(
        (Join-Path $runRoot "standardized\future_daily_pricing_$RunDate.csv"),
        (Join-Path $runRoot "analysis\future_daily_pricing_enriched_$RunDate.csv"),
        (Join-Path $runRoot "analysis\monthly_revenue_summary_$RunDate.md"),
        (Join-Path $runRoot "analysis\email_revenue_report_$RunDate.md"),
        (Join-Path $runRoot "analysis\email_revenue_report_$RunDate.html"),
        (Join-Path $runRoot "analysis\email_revenue_report_$RunDate.eml")
    )
    Write-Log "Output file check:"
    foreach ($path in $expectedOutputs) {
        if (Test-Path $path) {
            Write-Log "  exists: $path"
        } else {
            Write-Log "  missing: $path"
        }
    }
} else {
    Write-Log "Pipeline failed. Exit code: $exitCode"
}

Write-Log "Scheduled weekly pipeline wrapper finished."
Write-Log "End time: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")"
exit $exitCode
