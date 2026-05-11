# Weekly PriceLabs Runbook

Operator checklist for the current V1 pipeline.

## Scope

- PriceLabs only
- One listing only
- Manual CSV input only
- Next 180 days only
- No browser automation
- No scheduling
- No dashboards

## Run Checklist

- [ ] Download the PriceLabs future pricing CSV manually.
- [ ] Download or export the Price Occ benchmark CSV manually.
- [ ] Prepare the manual PriceLabs settings JSON.
- [ ] For development runs, keep email delivery in draft mode:

```toml
[email]
mode = "draft"

[smtp]
enabled = false
```

- [ ] Create the run folders:

```text
data/runs/<run_date>/raw/
data/runs/<run_date>/standardized/
data/runs/<run_date>/analysis/
data/runs/<run_date>/settings/
```

- [ ] Place the real raw input files in `data/runs/<run_date>/raw/`:
  - `priceLabs_future_export.csv`
  - `price_occ.csv`
  - `pricelabs_settings_manual_input.json`
- [ ] Treat `sample_data/` as debug fixtures only, not real weekly input storage.
- [ ] Do not use legacy top-level `analysis/` or `standardized/` folders for real outputs.
- [ ] Run the weekly runner from the repo root:

```powershell
.\run_weekly_pipeline.ps1 -RunDate YYYY-MM-DD
```

## Required Raw Files

The runner expects these exact filenames for each real run:

```text
data/runs/<run_date>/raw/priceLabs_future_export.csv
data/runs/<run_date>/raw/price_occ.csv
data/runs/<run_date>/raw/pricelabs_settings_manual_input.json
```

`priceLabs_future_export.csv` is the canonical Windows filename. Avoid creating a duplicate lowercase variant.

`priceLabs_future_export.csv` column `ADR` maps to `upcoming_adr`. `price_occ.csv` is market/context input only and must not provide `upcoming_adr`.

## After The Run

- [ ] Confirm `data/runs/<run_date>/standardized/future_daily_pricing_<run_date>.csv` was written.
- [ ] Confirm `data/runs/<run_date>/manifest.json` was written.
- [ ] Confirm `data/runs/<run_date>/manifest.json` has `status = "success"`.
- [ ] Confirm analysis outputs are under `data/runs/<run_date>/analysis/`.
- [ ] Confirm settings outputs are under `data/runs/<run_date>/settings/`.
- [ ] Confirm the email-ready report was written:

```text
data/runs/<run_date>/analysis/email_revenue_report_<run_date>.md
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

## Email Delivery Mode

The runner always generates:

```text
data/runs/<run_date>/analysis/email_revenue_report_<run_date>.md
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
