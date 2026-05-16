# Weekly PriceLabs Runbook

Operator checklist for the current V1 pipeline.

## Scope

- PriceLabs only
- One listing only
- One-session PriceLabs download-all workflow
- Next 180 days only
- One manual PriceLabs login/MFA checkpoint
- Windows Task Scheduler should not use this Playwright workflow until separately validated
- No dashboards

## Run Checklist

- [ ] Confirm the machine can open a headed browser for PriceLabs.
- [ ] Confirm no trusted raw files already exist for the same run date unless this is an intentional manual fallback run.
- [ ] For development runs, keep email delivery in draft mode:

```toml
[email]
mode = "draft"

[smtp]
enabled = false
```

- [ ] Run the standard weekly workflow from the repo root:

```powershell
.\scripts\run_weekly_with_pricelabs_downloads.ps1 -RunDate YYYY-MM-DD
```

- [ ] Complete the single manual PriceLabs login/MFA checkpoint in the opened browser.
- [ ] Let the wrapper finish the full flow:
  - download all files into `downloads_staging/`
  - validate staged files
  - promote validated files to `raw/`
  - run the weekly pipeline
  - clean `downloads_staging/` only after full success
- [ ] Confirm trusted raw files exist in `data/runs/<run_date>/raw/`:
  - `priceLabs_future_export.csv`
  - `price_occ.csv`
  - `monthly_trends.csv`
  - `bookings_report.xlsx`
  - `pricelabs_settings_snapshot_from_ui.json`
- [ ] Treat `sample_data/` as debug fixtures only, not real weekly input storage.
- [ ] Do not use legacy top-level `analysis/` or `standardized/` folders for real outputs.

## Required Raw Files

The standard wrapper creates and validates these trusted raw inputs:

```text
data/runs/<run_date>/raw/priceLabs_future_export.csv
data/runs/<run_date>/raw/price_occ.csv
data/runs/<run_date>/raw/monthly_trends.csv
data/runs/<run_date>/raw/bookings_report.xlsx
data/runs/<run_date>/raw/pricelabs_settings_snapshot_from_ui.json
```

`data/runs/<run_date>/raw/pricelabs_settings_manual_input.json` is deprecated/manual fallback only. Do not treat it as the primary settings source when the UI snapshot exists.

`priceLabs_future_export.csv` is the canonical Windows filename. Avoid creating a duplicate lowercase variant.

`priceLabs_future_export.csv` column `ADR` maps to `upcoming_adr`. `price_occ.csv` is market/context input only and must not provide `upcoming_adr`.

`monthly_trends.csv` is the primary monthly truth source for captured revenue, occupancy, and ADR. `bookings_report.xlsx` supplies current/future cleanings/stays, length of stay, booking source mix, and booking window. `kpis_on_the_books.xlsx` and Revenue On The Books exports are optional/deprecated for now and are not required for the current weekly report.

## Folder Model

```text
data/runs/<run_date>/downloads_staging/  temporary downloads, removed after full success
data/runs/<run_date>/raw/                trusted validated inputs
data/runs/<run_date>/analysis/           generated analysis and reports
data/runs/<run_date>/settings/           generated normalized settings outputs
data/runs/<run_date>/logs/               preserved logs
```

If the workflow fails, keep `downloads_staging/` for troubleshooting. If it succeeds, the wrapper cleans `downloads_staging/` after reports are generated.

## After The Run

- [ ] Confirm `data/runs/<run_date>/standardized/future_daily_pricing_<run_date>.csv` was written.
- [ ] Confirm `data/runs/<run_date>/manifest.json` was written.
- [ ] Confirm `data/runs/<run_date>/manifest.json` has `status = "success"`.
- [ ] Confirm analysis outputs are under `data/runs/<run_date>/analysis/`.
- [ ] Confirm settings outputs are under `data/runs/<run_date>/settings/`.
- [ ] Confirm Reason Review was generated:

```text
data/runs/<run_date>/analysis/performance_reason_review_<run_date>.csv
```

- [ ] Confirm reports include `Reason Review`.
- [ ] Confirm Monthly Trends was normalized:

```text
data/runs/<run_date>/analysis/monthly_trends_normalized_<run_date>.csv
```

- [ ] Confirm Bookings Report was normalized:

```text
data/runs/<run_date>/analysis/bookings_report_normalized_<run_date>.csv
data/runs/<run_date>/analysis/monthly_booking_metrics_<run_date>.csv
```

- [ ] Confirm the email-ready report was written:

```text
data/runs/<run_date>/analysis/email_revenue_report_<run_date>.md
```

- [ ] Confirm the readable HTML email report was written:

```text
data/runs/<run_date>/analysis/email_revenue_report_<run_date>.html
```

- [ ] Confirm the local email draft file was written:

```text
data/runs/<run_date>/analysis/email_revenue_report_<run_date>.eml
```

- [ ] Retain `data/runs/<run_date>/raw/` with the run.
- [ ] Do not overwrite prior run folders; outputs are snapshot-based.
- [ ] Spot check the standardized CSV header:

```text
run_date,listing_id,stay_date,nightly_price,min_stay,status,upcoming_adr,analysis_status,status_confidence,status_reason
```

- [ ] Confirm rows are for the configured `listing_id`.
- [ ] Confirm rows are within the next 180 days from `run_date`.
- [ ] Confirm the enriched daily file was written:

```text
data/runs/<run_date>/analysis/future_daily_pricing_enriched_<run_date>.csv
```

- [ ] Confirm the enriched daily header includes the Step 1 revenue-proxy fields:
  - `upcoming_adr`
  - `booked_revenue_proxy`
  - `open_revenue_ask`
  - `previous_status`
  - `previous_upcoming_adr`
  - `booked_stay_start_proxy`
  - `booked_stay_id_proxy`
- [ ] Treat market 75th percentile fields as context only. Revenue pace is the business goal.

## Reason Review

The pipeline classifies likely reasons before recommendations:

- `market_weakness`: monitor; no PriceLabs rule change.
- `insufficient_data`: no recommendation.
- `listing_or_conversion_issue`: investigate listing/conversion before changing pricing.
- `price_or_rule_issue`: a PriceLabs rule-area change may be considered.
- `settings_change_impact`: evaluate the setting impact before changing again.

Recommendations should be read through this gate. Do not jump from weak revenue directly to a price/rule change without the likely reason classification.

## Email Delivery Mode

The runner always generates:

```text
data/runs/<run_date>/analysis/email_revenue_report_<run_date>.md
data/runs/<run_date>/analysis/email_revenue_report_<run_date>.html
data/runs/<run_date>/analysis/email_revenue_report_<run_date>.eml
```

SMTP send mode is optional and explicit. The default development mode should be:

```toml
[email]
mode = "draft"

[smtp]
enabled = false
```

Real send requires both:

```toml
[email]
mode = "send"

[smtp]
enabled = true
```

Gmail App Password must be stored in environment variable:

```text
ALOHA_GMAIL_APP_PASSWORD
```

Do not store the password in `config/email.toml` and do not commit credentials. A persistent Windows user environment variable can be used later for scheduled automation.

If send mode is enabled and the password environment variable is missing, the pipeline fails clearly at `Email send mode`. For development, switch back to draft mode to avoid sending test emails.

SMTP body format is controlled by:

```toml
[report]
format = "markdown"
```

Use `format = "html"` to send the readable HTML report. Use `format = "markdown"` to send plain text.

To test in draft mode:

1. Set local `config/email.toml` to:

```toml
[email]
mode = "draft"

[smtp]
enabled = false

[report]
format = "html"
```

2. Run:

```powershell
.\scripts\run_weekly_with_pricelabs_downloads.ps1 -RunDate YYYY-MM-DD
```

3. Confirm `.md`, `.html`, and `.eml` outputs exist under `data/runs/<run_date>/analysis/`.
4. Confirm the pipeline prints `Email mode: draft — send skipped.`

To test one real HTML send:

1. Confirm `config/email.toml` has the intended `recipient_email` and `sender_email`.
2. Confirm `ALOHA_GMAIL_APP_PASSWORD` is available in the current PowerShell session or as a persistent Windows user environment variable.
3. Set local `config/email.toml` to:

```toml
[email]
mode = "send"

[smtp]
enabled = true

[report]
format = "html"
```

4. Run the weekly pipeline once.
5. Confirm the terminal prints `Email sent to <recipient>.`
6. Immediately switch back to draft mode for development:

```toml
[email]
mode = "draft"

[smtp]
enabled = false
```

## Validation

Run the test suite after changing pipeline code or before relying on a regenerated run:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pytest
```

## Cleanup Rule

- [ ] Keep `data/runs/<run_date>/raw/`; raw files are the source of truth.
- [ ] Generated folders can be deleted and recreated by the runner:
  - `data/runs/<run_date>/standardized/`
  - `data/runs/<run_date>/analysis/`
  - `data/runs/<run_date>/settings/`
- [ ] Do not delete raw files unless replacing them with corrected source exports for the same run.

## Failed Runs

- [ ] If the command fails, inspect `data/runs/<run_date>/manifest.json`.
- [ ] Confirm `data/runs/<run_date>/manifest.json` was overwritten with `status = "failed"` when the operational transform ran far enough to write it.
- [ ] Use the terminal error plus manifest paths to identify the bad input or config.
- [ ] Fix the input/config and rerun.
