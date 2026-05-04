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
- [ ] Place the CSV somewhere in the repo, or choose its existing path.
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

- [ ] Confirm `standardized/future_daily_pricing_<run_date>.csv` was written.
- [ ] Confirm `manifest.json` was written.
- [ ] Confirm `manifest.json` has `status = "success"`.
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
