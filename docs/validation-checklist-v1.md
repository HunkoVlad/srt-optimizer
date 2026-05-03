# Validation Checklist V1

This checklist documents validation expectations for the V1 standardized PriceLabs output. It is not executable code and does not add Playwright coverage.

## File-Level Checks

- [ ] Output path matches `standardized/future_daily_pricing_<run_date>.csv`.
- [ ] Output is one CSV file for one configured listing.
- [ ] File is not empty.
- [ ] File has a header row.
- [ ] File contains only standardized output columns approved by V1.

## Required Column Checks

- [ ] Required columns are present.
- [ ] Required columns appear in this exact order:

```text
run_date,listing_id,stay_date,nightly_price,min_stay,status
```

- [ ] No required column is duplicated.
- [ ] No required column name is misspelled or renamed.

## Row-Level Checks

- [ ] `run_date` is populated for every row.
- [ ] `listing_id` is populated for every row.
- [ ] Every row uses the configured single `listing_id`.
- [ ] `stay_date` is populated for every row.
- [ ] `nightly_price` is populated for every row.
- [ ] `min_stay` is populated for every row.
- [ ] `status` is populated for every row.
- [ ] `status` values are suitable for the V1 available/booked split.

## Mapping Checks

- [ ] PriceLabs `Listing ID` maps to `listing_id`.
- [ ] PriceLabs `Date` maps to `stay_date`.
- [ ] PriceLabs `Your Price` maps to `nightly_price`.
- [ ] PriceLabs `Min Stay` maps to `min_stay`.
- [ ] PriceLabs `Status` maps to `status`.
- [ ] Pipeline metadata maps to `run_date`.

## V1 Analytical Guardrail Checks

- [ ] Available-date pricing analysis filters to `status = available`.
- [ ] Booked-date value analysis filters to `status = booked`.
- [ ] Booked-date `nightly_price` is labeled as a provisional booked-value proxy.
- [ ] No output or validation note treats booked-date `nightly_price` as final realized ADR.
- [ ] No daily row-level listing occupancy versus market occupancy comparison is produced.
- [ ] Occupancy comparisons, when added later, are restricted to aggregated 30/60/90-day windows.

## Out-of-Scope Checks

- [ ] No extraction behavior is introduced.
- [ ] No Playwright test or browser automation is introduced.
- [ ] No dashboard behavior is introduced.
- [ ] No multi-listing config or output behavior is introduced.

