param(
    [Parameter(Mandatory = $true)]
    [string]$RunDate,
    [switch]$KeepStaging,
    [switch]$UsePersistentSession
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
$stagingDir = Join-Path $runRoot "downloads_staging"
$logsDir = Join-Path $runRoot "logs"
$wrapperLog = Join-Path $logsDir "weekly_with_pricelabs_downloads_$RunDate.log"

New-Item -ItemType Directory -Path $logsDir -Force | Out-Null

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
}

function Write-WrapperLog {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] $Message"
    Add-Content -Path $wrapperLog -Value $line -Encoding utf8
    Write-Host $line
}

function Invoke-WorkflowStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "== $Label =="
    Write-WrapperLog "Starting step: $Label"
    & $Command
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) {
        $exitCode = 0
    }
    if ($exitCode -ne 0) {
        Write-WrapperLog "Step failed: $Label. Exit code: $exitCode"
        exit $exitCode
    }
    Write-WrapperLog "Step completed: $Label"
}

Write-WrapperLog "Weekly PriceLabs download + promote + pipeline workflow started."
Write-WrapperLog "Run date: $RunDate"
Write-WrapperLog "Project root: $projectRoot"
Write-WrapperLog "Python executable: $pythonExe"
Write-WrapperLog "Gmail/send mode is not changed by this wrapper."
if ($UsePersistentSession) {
    Write-WrapperLog "Using gitignored local PriceLabs browser profile for session reuse."
}

Push-Location $projectRoot
try {
    $env:PYTHONPATH = "src"

    Invoke-WorkflowStep "PriceLabs download-all" {
        $downloadArgs = @("-m", "pricelabs.download.pricelabs_downloader", "--run-date", $RunDate, "--download-all")
        if ($UsePersistentSession) {
            $downloadArgs += "--use-persistent-session"
        }
        & $pythonExe @downloadArgs
    }

    Invoke-WorkflowStep "Promote staged PriceLabs files to raw" {
        & $pythonExe -m pricelabs.download.pricelabs_downloader --run-date $RunDate --promote-to-raw
    }

    Invoke-WorkflowStep "Weekly revenue pipeline" {
        & (Join-Path $projectRoot "run_weekly_pipeline.ps1") -RunDate $RunDate
    }

    if ($KeepStaging) {
        Write-WrapperLog "KeepStaging requested; downloads_staging preserved."
    }
    elseif (Test-Path $stagingDir) {
        Remove-Item -LiteralPath $stagingDir -Recurse -Force
        Write-WrapperLog "Cleaned downloads_staging after successful workflow."
    }
    else {
        Write-WrapperLog "downloads_staging not found after successful workflow; nothing to clean."
    }
}
finally {
    Pop-Location
}

Write-WrapperLog "Weekly PriceLabs download + promote + pipeline workflow completed successfully."
exit 0
