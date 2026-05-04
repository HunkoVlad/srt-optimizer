# srt-optimizer

Python-only V1 pipeline for a weekly PriceLabs-to-CSV workflow.

Current flow:

```text
manual PriceLabs CSV -> Python transform -> standardized CSV -> manifest.json
```

V1 scope is intentionally narrow:

- PriceLabs only
- One listing only
- Manual CSV input only
- Next 180 days only
- No browser automation
- No scheduling
- No dashboards
- No Airbnb

## Inputs

The user manually downloads a PriceLabs CSV and points the config to that file.

Required PriceLabs source columns:

- `Listing ID`
- `Date`
- `Your Price`
- `Min Stay`
- `Status`

The reader also supports PriceLabs exports with leading `#` note/comment lines before the real header.

## Config

Use [config/pricelabs.single-listing.example.toml](C:/Users/Volodymyr/srt-optimizer/config/pricelabs.single-listing.example.toml):

```toml
listing_id = "REPLACE_WITH_LISTING_ID"
input_path = "data/incoming/pricelabs_export.csv"
output_path = "standardized/future_daily_pricing_<run_date>.csv"
```

Set `listing_id` and `input_path` before running the transform.

## Run

Run from the repo root:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pricelabs.transform.run --config config\pricelabs.single-listing.example.toml --run-date 2026-05-03
```

Outputs:

- `standardized/future_daily_pricing_<run_date>.csv`
- `manifest.json`

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
run_date,listing_id,stay_date,nightly_price,min_stay,status
```

Field mapping:

- `run_date` <- pipeline run date
- `listing_id` <- PriceLabs `Listing ID`
- `stay_date` <- PriceLabs `Date`
- `nightly_price` <- PriceLabs `Your Price`
- `min_stay` <- PriceLabs `Min Stay`
- `status` <- normalized PriceLabs `Status` with `Available` fallback

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
|-- standardized/
|   `-- .gitkeep
|-- AGENTS.md
|-- README.md
`-- pyproject.toml
```

## Useful Docs

- [contracts/pricelabs-weekly-csv-v1.md](C:/Users/Volodymyr/srt-optimizer/contracts/pricelabs-weekly-csv-v1.md)
- [docs/runbook-weekly-pricelabs.md](C:/Users/Volodymyr/srt-optimizer/docs/runbook-weekly-pricelabs.md)
- [docs/validation-checklist-v1.md](C:/Users/Volodymyr/srt-optimizer/docs/validation-checklist-v1.md)
