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

This setup preserves the older safe scheduler wrapper for reference and documents the production PriceLabs Playwright workflow. Raw files remain the source of truth. The headless PriceLabs task has been validated from Windows Task Scheduler with `LastTaskResult = 0`.

The local PriceLabs credential fallback uses `.local/pricelabs.env`; credentials must not be stored in the scheduled task action.

## Production Weekly PriceLabs Headless Task

The production task should use a clear weekly name. If the active task still has a test name such as `Aloha Poconos PriceLabs Daily Headless Test`, rename or recreate it as the production task below.

Task name:

```text
Aloha Poconos Weekly PriceLabs Headless Pipeline
```

The older manual/raw task should remain disabled:

```text
Aloha Poconos Weekly Revenue Pipeline
```

Trigger:

- Weekly.
- Monday 9:00 AM.
- Repeat every 1 week.
- Choose a time when the computer is awake and has internet access.
- Headless mode can run while the screen is locked.
- Sleep, hibernate, or powered-off state prevents the task from running.
- Use `Run whether user is logged on or not` only after validating it under the same Windows account.

Action values:

Program/script:

```text
PowerShell.exe
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

- In Task Scheduler, check `Last Run Result` for `Aloha Poconos Weekly PriceLabs Headless Pipeline`.
- Confirm `LastTaskResult = 0` with:

```powershell
Get-ScheduledTaskInfo -TaskName "Aloha Poconos Weekly PriceLabs Headless Pipeline"
```

- Check preserved logs under `data/runs/<today>/logs/`.
- Confirm raw inputs were promoted under `data/runs/<today>/raw/`.
- Confirm all 5 trusted raw inputs exist:
  - `priceLabs_future_export.csv`
  - `price_occ.csv`
  - `monthly_trends.csv`
  - `bookings_report.xlsx`
  - `pricelabs_settings_snapshot_from_ui.json`
- Confirm `downloads_staging/` is absent after success.
- Confirm reports were generated under `data/runs/<today>/analysis/`.
- Confirm settings files were generated under `data/runs/<today>/settings/`.
- If the task fails, keep `downloads_staging/` for troubleshooting.

## Power And Wake Requirements

Task Scheduler can run the headless PriceLabs workflow while Windows is locked. It cannot run while the computer is asleep, hibernating, powered off, or offline.

Recommended task settings for the production weekly task:

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

Confirm `WakeToRun` and network settings for the weekly task:

```powershell
(Get-ScheduledTask -TaskName "Aloha Poconos Weekly PriceLabs Headless Pipeline").Settings |
    Select-Object WakeToRun, RunOnlyIfNetworkAvailable
```

## Recommended Schedule

Recommended timing for the production headless workflow:

- Monday 9:00 AM.
- Weekly, interval 1.
- The wrapper downloads, validates, promotes raw inputs, runs the pipeline, and cleans staging after success.

## Legacy Manual Raw Scheduler Task

The old manual/raw scheduler task is retained only as a disabled fallback/reference.

Name:

```text
Aloha Poconos Weekly Revenue Pipeline
```

Status:

```text
Disabled
```

Original action:

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

Note: this legacy task is disabled. It is kept only as a manual/raw fallback reference.

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

### A. Confirm Production Wrapper Works

```powershell
.\scripts\run_weekly_with_pricelabs_downloads.ps1 -RunDate today -UseLocalCredentials -Headless
```

### B. Confirm Raw Inputs

The successful production wrapper run should promote these files:

```text
data/runs/<today>/raw/priceLabs_future_export.csv
data/runs/<today>/raw/price_occ.csv
data/runs/<today>/raw/monthly_trends.csv
data/runs/<today>/raw/bookings_report.xlsx
data/runs/<today>/raw/pricelabs_settings_snapshot_from_ui.json
```

Optional/deprecated for the current monthly reporting flow:

```text
kpis_on_the_books.xlsx
```

`monthly_trends.csv` is required because it is the monthly revenue, occupancy, and ADR truth source. `bookings_report.xlsx` is required because it supplies reservation-level cleaning, length-of-stay, and booking-window metrics. `pricelabs_settings_manual_input.json` is deprecated/manual fallback only and is not the primary settings source when the UI snapshot exists.

### C. Run The Scheduler Task Manually

Use Task Scheduler’s `Run` action for the task.

### D. Check Last Run Result

```powershell
Get-ScheduledTaskInfo -TaskName "Aloha Poconos Weekly PriceLabs Headless Pipeline"
```

Expected: `LastTaskResult = 0`.

### E. Check The Log

```text
data/runs/<today>/logs/
```

### F. Confirm Outputs

```text
data/runs/<today>/analysis/email_revenue_report_<today>.html
data/runs/<today>/analysis/email_revenue_report_<today>.md
data/runs/<today>/analysis/monthly_revenue_summary_<today>.md
data/runs/<today>/settings/pricelabs_settings_snapshot_<today>.json
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
- Keep `Aloha Poconos Weekly Revenue Pipeline` disabled unless intentionally falling back to manual/raw inputs.
- Keep scheduled testing draft-first.
- Keep raw files as the source of truth.
