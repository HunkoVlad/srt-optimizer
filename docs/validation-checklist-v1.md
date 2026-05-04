# Validation Checklist V1

Implementation-oriented checklist for the current Python V1 PriceLabs transform.

## Happy Path

- [ ] Manually downloaded PriceLabs CSV can be read.
- [ ] Leading `#` note/comment lines before the header are ignored.
- [ ] Required source columns are present:
  - `Listing ID`
  - `Date`
  - `Your Price`
  - `Min Stay`
  - `Status`
- [ ] Output file is written to `standardized/future_daily_pricing_<run_date>.csv`.
- [ ] `manifest.json` is written with `status = "success"`.

## Standardized Output

- [ ] Output columns are present in this exact order:

```text
run_date,listing_id,stay_date,nightly_price,min_stay,status
```

- [ ] PriceLabs `Listing ID` maps to `listing_id`.
- [ ] PriceLabs `Date` maps to `stay_date`.
- [ ] PriceLabs `Your Price` maps to `nightly_price`.
- [ ] PriceLabs `Min Stay` maps to `min_stay`.
- [ ] Normalized PriceLabs status maps to `status`.
- [ ] Pipeline run date maps to `run_date`.

## Implemented Validation

- [ ] Missing input file fails the run.
- [ ] Missing required source column fails the run.
- [ ] Missing `Min Stay` source column fails the run.
- [ ] Duplicate primary key fails the run.
- [ ] Primary key is `run_date`, `listing_id`, `stay_date`.
- [ ] Output `status` is one of:
  - `available`
  - `booked`
  - `blocked`
  - `unavailable`

## Tested Status Normalization

- [ ] `Status` containing `available` -> `available`.
- [ ] `Status` containing `reserved` -> `booked`.
- [ ] `Status` containing `booked` -> `booked`.
- [ ] `Status` containing `blocked` -> `blocked`.
- [ ] Blank or unmapped `Status` with `Available=True` -> `available`.
- [ ] Blank or unmapped `Status` with `Available=False` -> `unavailable`.
- [ ] Otherwise -> `unavailable`.

## 180-Day Filter

- [ ] Rows before `run_date` are excluded.
- [ ] Rows from `run_date` through `run_date + 179 days` are included.
- [ ] Rows on or after `run_date + 180 days` are excluded.

## Failed-Run Manifest

- [ ] A failed run writes `manifest.json`.
- [ ] A failed run overwrites any previous success manifest.
- [ ] Failed manifest has `status = "failed"`.
- [ ] Failed manifest preserves available values:
  - `run_date`
  - `listing_id`
  - `source_file`
  - `standardized_file`
  - `raw_row_count`
  - `standardized_row_count`
- [ ] Failed manifest uses `null` for values unavailable at failure time.

## Out Of Scope

- [ ] No browser automation.
- [ ] No scheduling.
- [ ] No dashboards.
- [ ] No Airbnb.
- [ ] No multi-listing support.
