# Weekly Scheduling Design V1

## Purpose

This document defines the design for safe weekly local automation of the STR revenue pipeline.

The future scheduler should run the existing pipeline safely and repeatably, but raw files remain the source of truth. Scheduling should not replace source-file review, and it should not create reports from incomplete inputs.

This is design only. It does not add a scheduler wrapper, browser automation, or Playwright download automation.

## Current Pipeline Command

Manual weekly pipeline command:

```powershell
.\run_weekly_pipeline.ps1 -RunDate YYYY-MM-DD
```

Validation command:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pytest
```

## Expected Run Folder Structure

Each run should use:

```text
data/runs/<run_date>/raw/
data/runs/<run_date>/standardized/
data/runs/<run_date>/analysis/
data/runs/<run_date>/settings/
```

Future scheduler logging should add:

```text
data/runs/<run_date>/logs/
```

## Required Raw Inputs

Required:

```text
data/runs/<run_date>/raw/priceLabs_future_export.csv
data/runs/<run_date>/raw/price_occ.csv
data/runs/<run_date>/raw/monthly_trends.csv
data/runs/<run_date>/raw/bookings_report.xlsx
data/runs/<run_date>/raw/pricelabs_settings_snapshot_from_ui.json
```

Optional:

```text
data/runs/<run_date>/raw/kpis_on_the_books.xlsx
```

The optional KPI file may be missing. Missing `kpis_on_the_books.xlsx` should not fail the run, and it is deprecated for the current monthly reporting flow unless reconciliation is needed. `pricelabs_settings_manual_input.json` is deprecated/manual fallback only if the UI settings snapshot is unavailable.

`monthly_trends.csv` is the primary monthly revenue/occupancy/ADR truth source. `bookings_report.xlsx` is the reservation-level source for cleaning, length-of-stay, and booking-window metrics.

## Scheduling Safety Rules

Scheduled automation must default to draft mode.

Scheduled automation must not send email unless local `config/email.toml` explicitly has:

```toml
[email]
mode = "send"

[smtp]
enabled = true
```

Development/default mode should remain:

```toml
[email]
mode = "draft"

[smtp]
enabled = false

[report]
format = "html"
```

Gmail App Password must only come from the `ALOHA_GMAIL_APP_PASSWORD` environment variable.

The password must never be stored in TOML files, logs, docs, or Git.

## Missing-File Behavior

Future scheduler wrapper behavior:

- If required raw files are missing, stop before running the pipeline.
- Write a clear log message listing missing files.
- Do not create misleading reports from incomplete inputs.
- Continue when only the optional KPI file is missing.

## Logging Design

Future log location:

```text
data/runs/<run_date>/logs/
```

Expected future log file:

```text
scheduled_pipeline_<run_date>.log
```

The log should include:

- Start time.
- Run date.
- Config mode summary, without secrets.
- Required file check result.
- Pipeline command executed.
- Success/failure status.
- Output files created.
- Error message if failed.

Logs must not include passwords, tokens, Gmail App Password values, or raw credential material.

## Recommended Weekly Timing

Run weekly after raw files are refreshed manually.

Recommended timing: Sunday or Monday morning, after PriceLabs data is refreshed and raw exports are placed into the run folder.

Do not hard-code a schedule yet.

## Future Implementation Sequence

Step 24 — Create safe scheduler wrapper script.

Step 25 — Test with Windows Task Scheduler using manually placed raw files.

Step 26 — Require Monthly Trends and Bookings Report for accurate current-month reporting.

Step 27 — Add Playwright PriceLabs download automation.

Current manual standard:

```powershell
.\scripts\run_weekly_with_pricelabs_downloads.ps1 -RunDate YYYY-MM-DD
```

This one-session workflow is not yet approved for Windows Task Scheduler. Task Scheduler should continue using the separately documented safe wrapper until Playwright scheduling is explicitly validated.

Step 28 — Add Airbnb/listing conversion data later.

## Business Rationale

This order protects revenue reporting reliability:

1. Safe inputs.
2. Reproducible report.
3. Controlled email behavior.
4. Logs.
5. Browser automation only after the manual pipeline is stable.

The scheduler should make a trusted process repeatable. It should not hide missing files, skip source review, or introduce browser automation before the raw-file workflow is dependable.

## Step 24 Implementation Note

Wrapper script:

```text
scripts/run_scheduled_weekly_pipeline.ps1
```

Manual test command:

```powershell
.\scripts\run_scheduled_weekly_pipeline.ps1 -RunDate YYYY-MM-DD
```

The wrapper checks required raw files before calling:

```powershell
.\run_weekly_pipeline.ps1 -RunDate YYYY-MM-DD
```

Log file location:

```text
data/runs/<run_date>/logs/scheduled_pipeline_<run_date>.log
```

The wrapper logs safe run metadata, required-file checks, optional KPI status, email config mode summary without secrets, the pipeline command, success/failure status, expected output checks, and errors.

Windows Task Scheduler is still not configured.

Playwright is still not involved.

## Step 25 Design Note

Windows Task Scheduler setup is documented in:

```text
docs/windows-task-scheduler-setup-v1.md
```

The documented setup runs the existing safe wrapper:

```powershell
.\scripts\run_scheduled_weekly_pipeline.ps1
```

The first Task Scheduler version should not pass `RunDate`; the wrapper should default to today’s date. Manual testing with a fixed date can still use:

```powershell
.\scripts\run_scheduled_weekly_pipeline.ps1 -RunDate 2026-05-08
```

Playwright is still not involved.
