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
- [ ] Create the run folder:

```text
data/runs/<run_date>/raw/
```

- [ ] Place the real raw input files in `data/runs/<run_date>/raw/`:
  - `pricelabs_future_export.csv`
  - `price_occ.csv`
  - `pricelabs_settings_manual_input.json`
- [ ] Treat `sample_data/` as debug fixtures only, not real weekly input storage.
- [ ] Run the weekly runner from the repo root:

```powershell
.\run_weekly_pipeline.ps1 -RunDate 2026-05-03
```

## Manual Transform Only

Use this lower-level command only when running the operational transform by itself.

- [ ] Open `config/pricelabs.single-listing.example.toml`.
- [ ] Set `listing_id` to the one listing being transformed.
- [ ] Set `input_path` to the manually downloaded PriceLabs CSV.
- [ ] Keep `output_path` as `standardized/future_daily_pricing_<run_date>.csv`.
- [ ] Activate the virtual environment, or use the venv Python directly.
- [ ] Run from the repo root:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pricelabs.transform.run --config config\pricelabs.single-listing.example.toml --run-date 2026-05-03
```

## After The Run

- [ ] Confirm `data/runs/<run_date>/standardized/future_daily_pricing_<run_date>.csv` was written.
- [ ] Confirm `data/runs/<run_date>/manifest.json` was written.
- [ ] Confirm `manifest.json` has `status = "success"`.
- [ ] Confirm analysis outputs are under `data/runs/<run_date>/analysis/`.
- [ ] Confirm settings outputs are under `data/runs/<run_date>/settings/`.
- [ ] Retain `data/runs/<run_date>/raw/` with the run.
- [ ] Do not overwrite prior run folders; outputs are snapshot-based.
- [ ] Spot check the standardized CSV header:

```text
run_date,listing_id,stay_date,nightly_price,min_stay,status
```

- [ ] Confirm rows are for the configured `listing_id`.
- [ ] Confirm rows are within the next 180 days from `run_date`.

## Failed Runs

- [ ] If the command fails, inspect `manifest.json`.
- [ ] Confirm `manifest.json` was overwritten with `status = "failed"`.
- [ ] Use the terminal error plus manifest paths to identify the bad input or config.
- [ ] Fix the input/config and rerun.
