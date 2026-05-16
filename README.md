# srt-optimizer

Python-only V1 pipeline for a weekly PriceLabs revenue workflow.

Current weekly workflow:

```text
one-session PriceLabs download-all -> downloads_staging/ -> validated raw/ -> standardized daily CSV -> analysis/settings outputs -> email-ready reports
```

V1 scope is intentionally narrow:

- PriceLabs only
- One listing only
- PriceLabs headed/manual login checkpoint for downloads
- Next 180 days only
- Scheduler integration is not enabled for the Playwright workflow yet
- No dashboards
- No Airbnb

## Inputs

Real weekly runs use dated run folders under `data/runs/<run_date>/`. Raw files are the source of truth and generated outputs are reproducible.

Required raw files for the current pipeline:

- `data/runs/<run_date>/raw/priceLabs_future_export.csv`
- `data/runs/<run_date>/raw/price_occ.csv`
- `data/runs/<run_date>/raw/monthly_trends.csv`
- `data/runs/<run_date>/raw/bookings_report.xlsx`
- `data/runs/<run_date>/raw/pricelabs_settings_snapshot_from_ui.json`

Deprecated/manual fallback:

- `data/runs/<run_date>/raw/pricelabs_settings_manual_input.json`

Current source roles:

- Monthly Trends is the primary monthly truth source for revenue, ADR, and occupancy.
- Bookings Report supplies current/future cleanings/stays, length of stay, booking source, and booking window.
- Future export supplies future calendar status, open ask, availability, min stay, and future booked proxy fallback.
- `price_occ.csv` supplies market context only.
- UI settings snapshot supplies the primary PriceLabs rule snapshot.
- Manual settings JSON is deprecated and used only as fallback if the UI snapshot is missing.
- KPI On The Books and Revenue On The Books are optional/deprecated for now.

## Real Weekly Run Folders

`sample_data/` is for debug fixtures only. Real weekly runs should use dated folders:

```text
data/runs/<run_date>/
|-- downloads_staging/
|-- raw/
|-- standardized/
|-- analysis/
|-- logs/
`-- settings/
```

`downloads_staging/` is temporary. `raw/` is the trusted validated input layer. `analysis/` and `settings/` are generated and reproducible.

The standard weekly command is:

```powershell
.\scripts\run_weekly_with_pricelabs_downloads.ps1 -RunDate YYYY-MM-DD
```

That wrapper opens one PriceLabs browser session, waits for one manual login/MFA checkpoint, downloads the five staged inputs, validates them, promotes them to `raw/`, runs the weekly pipeline, and cleans `downloads_staging/` only after the full workflow succeeds.

Trusted raw input files after promotion:

- `priceLabs_future_export.csv`
- `price_occ.csv`
- `monthly_trends.csv`
- `bookings_report.xlsx`
- `pricelabs_settings_snapshot_from_ui.json`

Raw files should be retained with the run. Analysis outputs are snapshot-based and should not overwrite prior run folders.

## Run Weekly Pipeline

Preferred weekly command:

```powershell
.\scripts\run_weekly_with_pricelabs_downloads.ps1 -RunDate 2026-05-03
```

Manual raw fallback remains available. If trusted raw files already exist, run:

```powershell
.\run_weekly_pipeline.ps1 -RunDate 2026-05-03
```

The runner writes outputs under `data/runs/<run_date>/standardized/`, `data/runs/<run_date>/analysis/`, and `data/runs/<run_date>/settings/`.

## Config

Status: Legacy transform-only reference. The current weekly workflow should use `run_weekly_pipeline.ps1` and dated `data/runs/<run_date>/` folders.

Use [config/pricelabs.single-listing.example.toml](config/pricelabs.single-listing.example.toml):

```toml
listing_id = "REPLACE_WITH_LISTING_ID"
input_path = "sample_data/pricelabs_future_export_sample.csv"
output_path = "standardized/future_daily_pricing_<run_date>.csv"
```

Set `listing_id` and `input_path` before running the transform.

## Run

Status: Legacy transform-only reference. Use the weekly runner for current reports.

Run from the repo root:

```powershell
.\run_pricelabs_transform.ps1 -RunDate 2026-05-03
```

Or run the Python module directly:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pricelabs.transform.run --config config\pricelabs.single-listing.example.toml --run-date 2026-05-03
```

Outputs:

- `data/runs/<run_date>/standardized/future_daily_pricing_<run_date>.csv`
- `data/runs/<run_date>/manifest.json`

## Run Future Enrichment

Status: Legacy manual-step reference. The weekly runner now orchestrates enrichment and downstream reports.

After the standardized CSV exists, run the manual enrichment step:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pricelabs.transform.enrich_future --run-date 2026-05-03
```

Output:

- `data/runs/<run_date>/analysis/future_daily_pricing_enriched_<run_date>.csv`

## Run Future Window Summary

After the enriched daily CSV exists, run the window summary step:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pricelabs.transform.summarize_future --run-date 2026-05-03
```

Output:

- `analysis/future_window_summary_<run_date>.csv`

## Run Settings Snapshot

Use `data/runs/<run_date>/raw/pricelabs_settings_snapshot_from_ui.json` for operational runs. The UI snapshot is normalized into structured business fields before comparison. `data/runs/<run_date>/raw/pricelabs_settings_manual_input.json` is deprecated/manual fallback only.

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pricelabs.transform.settings_snapshot --run-date 2026-05-03
```

Output:

- `data/runs/<run_date>/settings/pricelabs_settings_snapshot_<run_date>.json`

## Run Settings Changes

After current and prior settings snapshots exist, compare them with:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pricelabs.transform.settings_changes --run-date 2026-05-03 --prior-run-date 2026-04-26
```

Output:

- `data/runs/<run_date>/settings/pricelabs_settings_changes_<run_date>.csv`

## Run Signal Change Review

After current/prior signal files and current settings changes exist, run:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pricelabs.transform.review_signal_changes --run-date 2026-05-03 --prior-run-date 2026-04-26
```

Output:

- `analysis/future_signal_change_review_<run_date>.csv`

Note: synthetic prior signal files may be created for pipeline debugging only. Do not use synthetic signal rows for business interpretation.

## Run Performance Reason Review

The weekly pipeline creates:

```text
data/runs/<run_date>/analysis/performance_reason_review_<run_date>.csv
```

Reports include a concise `Reason Review` section that classifies what happened, likely why, and whether a PriceLabs rule change is justified. Recommendation gating uses these categories:

- `market_weakness`: monitor; no PriceLabs rule change.
- `insufficient_data`: no recommendation.
- `listing_or_conversion_issue`: investigate listing or conversion before pricing.
- `price_or_rule_issue`: PriceLabs rule change may be considered.
- `settings_change_impact`: evaluate the impact before changing again.

## Validated V1 Behavior

- Validates required source columns.
- Maps PriceLabs fields to the standardized V1 columns.
- Filters to the configured one listing.
- Keeps stay dates within the next 180 days from `run_date`.
- Normalizes status values:
  - `Status` containing `available` -> `available`
  - `Status` containing `reserved` or `booked` -> `booked`
  - `Status` containing `blocked` -> `blocked`
  - blank or unmapped `Status` falls back to `Available=True` -> `available`
  - blank or unmapped `Status` with `Available=False` -> `unavailable`
  - otherwise -> `unavailable`
- Validates unique primary key: `run_date`, `listing_id`, `stay_date`.
- Writes `manifest.json` with `status = "success"` on success.
- Overwrites `manifest.json` with `status = "failed"` on failed runs.

## Standardized Output

Required output columns, in order:

```text
run_date,listing_id,stay_date,nightly_price,min_stay,status,upcoming_adr,analysis_status,status_confidence,status_reason
```

Field mapping:

- `run_date` <- pipeline run date
- `listing_id` <- PriceLabs `Listing ID`
- `stay_date` <- PriceLabs `Date`
- `nightly_price` <- PriceLabs `Your Price`
- `min_stay` <- PriceLabs `Min Stay`
- `status` <- raw/source-driven normalized PriceLabs `Status` with `Available` fallback
- `upcoming_adr` <- PriceLabs future export `ADR`
- `analysis_status` <- analysis-aware status from `Status` plus `Available`
- `status_confidence` <- `high`, `medium`, or `low`
- `status_reason` <- stable reason code for the analysis status

## Project Structure

```text
srt-optimizer/
|-- config/
|   `-- pricelabs.single-listing.example.toml
|-- contracts/
|   `-- pricelabs-weekly-csv-v1.md
|-- docs/
|   |-- pricelabs-pipeline.md
|   |-- pricelabs-v1-source-to-target-mapping.md
|   |-- runbook-weekly-pricelabs.md
|   |-- standardized-output-contract-v1.md
|   `-- validation-checklist-v1.md
|-- sample_data/
|-- src/
|   `-- pricelabs/
|       `-- transform/
|-- AGENTS.md
|-- README.md
`-- pyproject.toml
```

## Useful Docs

- [contracts/pricelabs-weekly-csv-v1.md](contracts/pricelabs-weekly-csv-v1.md)
- [docs/source-triage-for-analysis.md](docs/source-triage-for-analysis.md)
- [docs/runbook-weekly-pricelabs.md](docs/runbook-weekly-pricelabs.md)
- [docs/validation-checklist-v1.md](docs/validation-checklist-v1.md)
