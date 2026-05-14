# Task Scheduler Troubleshooting V1

## Startup Failure: Last Run Result 0x1

Observed case:

- Manual wrapper execution works:

```powershell
.\scripts\run_scheduled_weekly_pipeline.ps1 -RunDate 2026-05-11
```

- Windows Task Scheduler manual run returns:

```text
Last Run Result: 0x1
```

- No new lines appear in:

```text
data/runs/2026-05-11/logs/scheduled_pipeline_2026-05-11.log
```

Meaning:

- The wrapper probably did not start.
- Focus first on Task Scheduler action settings, `Start in` folder, user context, execution policy, and Task Scheduler history.
- This is likely a scheduler launch problem, not a pipeline logic problem.

## Action Settings To Re-Check

Program/script:

```text
powershell.exe
```

Arguments:

```text
-NoProfile -ExecutionPolicy Bypass -File "C:\Users\Volodymyr\srt-optimizer\scripts\run_scheduled_weekly_pipeline.ps1"
```

Start in:

```text
C:\Users\Volodymyr\srt-optimizer
```

Important:

- `Start in` must not have quotes.
- The script path in `Arguments` should be quoted.
- The first Task Scheduler version should not pass `RunDate`; the wrapper should default to today.

## Diagnostic Smoke Test Action

Use this temporary action to confirm Task Scheduler can launch PowerShell and write to the project log folder.

Program/script:

```text
powershell.exe
```

Arguments:

```text
-NoProfile -ExecutionPolicy Bypass -Command "Get-Date | Out-File -FilePath 'C:\Users\Volodymyr\srt-optimizer\data\runs\2026-05-11\logs\task_scheduler_smoke_test.log' -Append; whoami | Out-File -FilePath 'C:\Users\Volodymyr\srt-optimizer\data\runs\2026-05-11\logs\task_scheduler_smoke_test.log' -Append; Get-Location | Out-File -FilePath 'C:\Users\Volodymyr\srt-optimizer\data\runs\2026-05-11\logs\task_scheduler_smoke_test.log' -Append"
```

Start in:

```text
C:\Users\Volodymyr\srt-optimizer
```

Purpose:

- Confirms Task Scheduler can launch PowerShell.
- Confirms which Windows user the task runs as.
- Confirms the working folder.
- Confirms the task can write to the project log folder.

Expected output:

```text
data/runs/2026-05-11/logs/task_scheduler_smoke_test.log
```

After the smoke test passes, restore the normal pipeline action.

## Event And History Checks

In Task Scheduler:

1. Enable `All Tasks History`.
2. Open the task.
3. Check the `History` tab.
4. Look for:
   - Action started.
   - Action completed.
   - Action failed.
   - Return code.

If no action-start event appears, the task may not be launching at all.

If action-start appears but no wrapper log appears, re-check script path, execution policy, and permissions.

## Common Causes

- Wrong `Start in` folder.
- Quotes used in `Start in`.
- Typo in the script path.
- Task running under an unexpected Windows user.
- Permission issue writing to the project folder.
- PowerShell path issue.
- Execution policy issue.
- Task configured to run only under conditions that are not currently true.

## What Not To Change While Debugging

- Do not modify pipeline code.
- Do not modify wrapper code unless a confirmed wrapper bug is found.
- Do not change email send mode.
- Do not add Playwright automation.
- Do not delete real raw files.
