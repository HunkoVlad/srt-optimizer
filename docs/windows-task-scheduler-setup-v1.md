# Windows Task Scheduler Setup V1

## Purpose

Windows Task Scheduler can run the existing safe scheduler wrapper:

```powershell
.\scripts\run_scheduled_weekly_pipeline.ps1
```

The wrapper is responsible for:

- Required raw-file checks.
- Logs.
- Calling the main pipeline.
- Safe email config summary without secrets.

This setup preserves the older safe scheduler wrapper and documents the newer PriceLabs Playwright workflow separately. Raw files remain the source of truth. The headless daily test for `.\scripts\run_weekly_with_pricelabs_downloads.ps1 -RunDate today -UseLocalCredentials -Headless` has been validated, but the weekly production switch should wait until scheduler timing, power, and MFA behavior are confirmed.

The local PriceLabs credential fallback uses `.local/pricelabs.env`; credentials must not be stored in the scheduled task action.

## Temporary Daily PriceLabs Workflow Test

The Playwright weekly workflow can be tested from Windows Task Scheduler with a separate temporary daily task. Do not replace the existing `Aloha Poconos Weekly Revenue Pipeline` task yet, and do not enable this as the weekly production schedule until the daily test, power behavior, and MFA behavior are validated.

Task name:

```text
Aloha Poconos PriceLabs Daily Test
```

Recommended trigger:

- Daily.
- Temporary validation only.
- Choose a time when the computer is awake and has internet access.
- Headless mode can run while the screen is locked.
- Sleep, hibernate, or powered-off state prevents the task from running.
- Run only when the user is logged on for initial testing; use `Run whether user is logged on or not` only after headless validation.

Action values:

Program/script:

```text
PowerShell
```

Arguments:

```text
-NoProfile -ExecutionPolicy Bypass -File "C:\Users\Volodymyr\srt-optimizer\scripts\run_weekly_with_pricelabs_downloads.ps1" -RunDate today -UseLocalCredentials -Headless
```

Start in:

```text
C:\Users\Volodymyr\srt-optimizer
```

Important: do not put quotes around the `Start in` path.

Credential and MFA notes:

- The task action does not store PriceLabs credentials.
- PriceLabs credentials remain local-only in `.local/pricelabs.env`.
- Do not paste credentials into Task Scheduler, docs, logs, Git, or chat.
- PriceLabs may still require manual MFA, which can block unattended execution.
- Gmail/send mode is unchanged by this wrapper; email delivery remains controlled by `config/email.toml`.

Validation:

- In Task Scheduler, check `Last Run Result` for `Aloha Poconos PriceLabs Daily Test`.
- Check preserved logs under `data/runs/<today>/logs/`.
- Confirm raw inputs were promoted under `data/runs/<today>/raw/`.
- Confirm reports were generated under `data/runs/<today>/analysis/`.
- If the task fails, keep `downloads_staging/` for troubleshooting.

After validation:

- Disable or delete `Aloha Poconos PriceLabs Daily Test`.
- Switch to a weekly trigger only after the daily test proves reliable and MFA behavior is understood.
- Keep the old scheduler task unchanged until this workflow is explicitly accepted as the replacement.

## Power And Wake Requirements

Task Scheduler can run the headless PriceLabs workflow while Windows is locked. It cannot run while the computer is asleep, hibernating, powered off, or offline.

Recommended task settings for the daily test and any future weekly production task:

- Enable `Wake the computer to run this task`.
- Enable `Start only if the following network connection is available` if the machine has a reliable named network profile.
- Use `Run whether user is logged on or not` only after the headless workflow has been validated under that option.
- Set a reasonable stop limit so a stuck browser run does not continue indefinitely.

Check current Windows power settings:

```powershell
powercfg /query
```

Optional plugged-in sleep prevention, only if acceptable:

```powershell
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
```

These commands affect AC plugged-in behavior. They should not be used if the computer is expected to sleep automatically while plugged in.

Confirm `WakeToRun` and network settings for the daily test task:

```powershell
(Get-ScheduledTask -TaskName "Aloha Poconos PriceLabs Daily Test").Settings |
    Select-Object WakeToRun, RunOnlyIfNetworkAvailable
```

If the workflow is later moved to a weekly production task, repeat this check with the final weekly task name.

## Recommended Schedule

Recommended timing: Monday morning after raw PriceLabs files are manually refreshed and placed in:

```text
data/runs/<run_date>/raw/
```

If raw files are not present, the wrapper should fail safely and log the missing files.

Do not hard-code this timing as mandatory. Choose a weekly time after raw files are normally available.

## Task Scheduler Settings

### General

- Name: `Aloha Poconos Weekly Revenue Pipeline`
- Run only when user is logged on, at least for initial testing.
- Configure for Windows 10/11.

### Trigger

- Weekly.
- Monday morning.
- Time chosen by user after raw files are normally available.

### Action

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

Important: the first Task Scheduler version should not pass `RunDate`. The wrapper should default to today’s date.

Manual testing with a fixed run date can still use:

```powershell
.\scripts\run_scheduled_weekly_pipeline.ps1 -RunDate 2026-05-08
```

## Conditions And Settings

Recommended:

- Do not require AC power unless the machine is a laptop and that behavior is wanted.
- Enable `Wake the computer to run this task` for unattended runs.
- Keep the machine awake during the scheduled window; locked is fine for headless mode, sleep/hibernate is not.
- Use `Start only if network is available` if the network profile is reliable.
- Allow task to be run on demand.
- Stop task if it runs longer than a reasonable limit, such as 30 minutes.
- If the task fails, allow retry once after a short delay.

## Manual Validation Steps

### A. Confirm Local Manual Wrapper Works

```powershell
.\scripts\run_scheduled_weekly_pipeline.ps1 -RunDate 2026-05-08
```

### B. Prepare A Test Run Folder

Create a new run folder for a test date only if raw files are copied there:

```text
data/runs/<test_date>/raw/
```

Required raw files:

```text
priceLabs_future_export.csv
price_occ.csv
monthly_trends.csv
bookings_report.xlsx
pricelabs_settings_snapshot_from_ui.json
```

Optional/deprecated for the current monthly reporting flow:

```text
kpis_on_the_books.xlsx
```

`monthly_trends.csv` is required because it is the monthly revenue, occupancy, and ADR truth source. `bookings_report.xlsx` is required because it supplies reservation-level cleaning, length-of-stay, and booking-window metrics. `pricelabs_settings_manual_input.json` is deprecated/manual fallback only and is not the primary settings source when the UI snapshot exists.

### C. Run The Task Manually

Use Task Scheduler’s `Run` action for the task.

### D. Check The Log

```text
data/runs/<today>/logs/scheduled_pipeline_<today>.log
```

### E. Confirm Outputs

```text
data/runs/<today>/analysis/email_revenue_report_<today>.html
data/runs/<today>/analysis/email_revenue_report_<today>.md
data/runs/<today>/analysis/monthly_revenue_summary_<today>.md
```

## Failure Validation

To confirm safe failure, temporarily test with a run date where required raw files are missing.

Expected behavior:

- Wrapper stops before pipeline execution.
- Log lists missing files.
- No misleading report is generated.

Do not delete real data to test this. Use a test date with no raw files instead.

## Email Safety

For scheduled testing, `config/email.toml` should stay:

```toml
[email]
mode = "draft"

[smtp]
enabled = false

[report]
format = "html"
```

Only later, after scheduler reliability is confirmed, send mode can be consciously enabled.

## Troubleshooting

For startup failures where Task Scheduler returns `0x1` and no wrapper log lines appear, see:

```text
docs/task-scheduler-troubleshooting-v1.md
```

PowerShell execution policy:

- Use `-ExecutionPolicy Bypass` in the task action arguments.

Wrong `Start in` folder:

- Set `Start in` to `C:\Users\Volodymyr\srt-optimizer`.
- A wrong working folder can prevent relative paths from resolving correctly.

Missing raw files:

- Confirm required files exist in `data/runs/<run_date>/raw/`.
- The wrapper should log exactly which required files are missing.

Virtual environment path/access issue:

- The pipeline uses `.venv\Scripts\python.exe` when present.
- If Task Scheduler runs under a different account, that account may not have access to the virtual environment.

Gmail App Password missing:

- This matters only if send mode is enabled.
- Draft mode does not require `ALOHA_GMAIL_APP_PASSWORD`.

Different Windows user account:

- Task Scheduler may run under a different user account than the interactive shell.
- That account needs access to the repo, raw files, virtual environment, and any user-level environment variables required for send mode.

## Guardrails

- No email send mode change in this step.
- Do not replace the old weekly task until the daily headless test is accepted as production-ready.
- Keep scheduled testing draft-first.
- Keep raw files as the source of truth.
