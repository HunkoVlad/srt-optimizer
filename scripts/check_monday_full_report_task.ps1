param(
    [string]$TaskName = "Aloha Poconos Monday Full Report"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $task) {
    Write-Host "Task missing: $TaskName"
    exit 1
}

$taskInfo = Get-ScheduledTaskInfo -TaskName $TaskName

Write-Host "Task exists: $TaskName"
Write-Host "State: $($task.State)"
Write-Host "Next run time: $($taskInfo.NextRunTime)"
Write-Host "Last run time: $($taskInfo.LastRunTime)"
Write-Host "Last task result: $($taskInfo.LastTaskResult)"
