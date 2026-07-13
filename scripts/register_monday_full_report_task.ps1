param(
    [string]$TaskName = "Aloha Poconos Monday Full Report",
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$Time = "09:00",
    [ValidateSet("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")]
    [string]$DayOfWeek = "Monday",
    [switch]$AutoSendStayFi,
    [switch]$DisableAutoSendStayFi,
    [switch]$Force,
    [switch]$WhatIf
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-RequiredPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    if (-not (Test-Path $Path)) {
        throw "$Label not found: $Path"
    }
}

function Quote-ForPowerShellSingleString {
    param([Parameter(Mandatory = $true)][string]$Value)
    return "'" + ($Value -replace "'", "''") + "'"
}

$resolvedProjectRoot = (Resolve-Path -Path $ProjectRoot).Path
$activatePath = Join-Path $resolvedProjectRoot ".venv\Scripts\Activate.ps1"
$workflowScript = Join-Path $resolvedProjectRoot "scripts\run_monday_full_report.ps1"
$stayfiSource = Join-Path $resolvedProjectRoot "data\source\stayfi\stayfi_guests_2026.csv"
$gmailClient = Join-Path $resolvedProjectRoot "config\gmail_oauth_client.json"
$gmailToken = Join-Path $resolvedProjectRoot ".local\gmail_token.json"

Test-RequiredPath -Path $resolvedProjectRoot -Label "Project root"
Test-RequiredPath -Path $activatePath -Label "Virtual environment activation script"
Test-RequiredPath -Path $workflowScript -Label "Monday full report workflow script"
Test-RequiredPath -Path $stayfiSource -Label "StayFi source CSV"
Test-RequiredPath -Path $gmailClient -Label "Gmail OAuth client config"

if (-not (Test-Path $gmailToken)) {
    Write-Warning "Gmail OAuth token not found: $gmailToken. First unattended Gmail send may fail until OAuth token exists."
}

$autoSendEnabled = -not $DisableAutoSendStayFi.IsPresent
if ($AutoSendStayFi.IsPresent) {
    $autoSendEnabled = $true
}

$workflowArgs = @()
if ($autoSendEnabled) {
    $workflowArgs += "-AutoSendStayFi"
}

$quotedProjectRoot = Quote-ForPowerShellSingleString -Value $resolvedProjectRoot
$scheduledTaskLogDir = "logs\scheduled_tasks"
$workflowInvocation = ".\scripts\run_monday_full_report.ps1"
if ($workflowArgs.Count -gt 0) {
    $workflowInvocation = "$workflowInvocation $($workflowArgs -join ' ')"
}
$workflowCommand = "cd $quotedProjectRoot; New-Item -ItemType Directory -Path '$scheduledTaskLogDir' -Force | Out-Null; `$scheduledTaskLog = Join-Path '$scheduledTaskLogDir' ('monday_full_report_' + (Get-Date -Format 'yyyy-MM-dd_HHmmss') + '.log'); & { .\.venv\Scripts\Activate.ps1; $workflowInvocation } *> `$scheduledTaskLog"
$actionArguments = "-NoProfile -ExecutionPolicy Bypass -Command " + '"' + $workflowCommand + '"'

Write-Host "Monday full report scheduled task setup"
Write-Host "Task name: $TaskName"
Write-Host "Project root: $resolvedProjectRoot"
Write-Host "Schedule: $DayOfWeek at $Time"
Write-Host "AutoSendStayFi enabled: $autoSendEnabled"
Write-Host "Task logon type: Interactive token. Run only when user is logged on."
Write-Host "Run with highest privileges: enabled."
Write-Host "Scheduled task log folder: logs\scheduled_tasks"
Write-Host "Scheduled task log pattern: logs\scheduled_tasks\monday_full_report_<yyyy-MM-dd_HHmmss>.log"
Write-Host "Command:"
Write-Host "powershell.exe $actionArguments"
Write-Host "No secrets are printed or inspected."

if ($WhatIf.IsPresent) {
    Write-Host "WhatIf: scheduled task was not registered."
    exit 0
}

$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask -and -not $Force.IsPresent) {
    $confirmation = Read-Host "Scheduled task '$TaskName' already exists. Type REPLACE to replace it"
    if ($confirmation -ne "REPLACE") {
        Write-Host "Registration skipped by user."
        exit 0
    }
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $actionArguments -WorkingDirectory $resolvedProjectRoot
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $DayOfWeek -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew
$principalUser = if ($env:USERDOMAIN) { "$env:USERDOMAIN\$env:USERNAME" } else { $env:USERNAME }
$principal = New-ScheduledTaskPrincipal -UserId $principalUser -LogonType Interactive -RunLevel Highest
$description = "Runs Aloha Poconos weekly SRT report and StayFi anniversary workflow. StayFi auto-send follows dry-run and duplicate-log safety checks."

try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Description $description `
        -Force `
        -ErrorAction Stop | Out-Null
}
catch {
    Write-Error "Failed to register scheduled task '$TaskName': $($_.Exception.Message). Rerun PowerShell as Administrator and retry this command."
    exit 1
}

Write-Host "Registered scheduled task: $TaskName"



