# Weekly PriceLabs Runbook

Status: Revised V1 scaffold
Cadence: Weekly
Extraction: Not implemented

## Purpose

Run the weekly PriceLabs-to-CSV process and produce the V1 standardized daily pricing CSV.

## Preconditions

- The revised V1 contract has been added to `contracts/pricelabs-weekly-csv-v1.md`.
- Required credentials and source access have been documented outside the repository.
- The weekly reporting window is known.
- The extraction implementation exists and has been tested against non-production fixtures or approved sample data.

## Planned Weekly Flow

1. Confirm the reporting week and expected output file name: `standardized/future_daily_pricing_<run_date>.csv`.
2. Acquire PriceLabs source data through the approved extraction mechanism.
3. Store raw input in the local incoming area or configured secure storage.
4. Transform the source records into the V1 standardized dataset.
5. Validate column order, required values, formatting, status values, and comparison guardrails.
6. Export the CSV artifact.
7. Review validation output and run logs.
8. Deliver or archive the CSV according to the V1 contract.

## Planned Review Views

Available-date pricing review:

- Filter to `status = available`.
- Inspect current asking price, min-stay behavior, weekend premium, 1-night premium, and open-date market positioning.
- Use daily `nightly_price` vs `market_price` comparison only when `market_price` is present.

Booked-date value review:

- Filter to `status = booked`.
- Treat `nightly_price` as a provisional booked-value proxy, not final realized ADR.
- Prefer 30/60/90-day windows for booked-value quality trends.

Window-level review:

- Compare booked share of nights against market occupancy only at 30/60/90-day windows.
- Review booked-date proxy average vs market average for the same booked dates.
- Review available-date pricing posture by window.

## Failure Handling

Stop the run when:

- Required source data is missing or incomplete.
- Contract-required fields cannot be derived.
- CSV validation fails.
- Output file naming, encoding, or delivery rules cannot be satisfied.
- An analysis attempts daily listing occupancy vs market occupancy comparison.

Record the failure reason in the run log and keep generated artifacts local until reviewed.

## Open Items

- Confirm weekly run day and timezone.
- Confirm whether PriceLabs data is collected by API, export file, browser automation, or manual drop.
- Confirm whether PriceLabs booked-date `nightly_price` remains stable after booking.
- Define test fixtures for available-date and booked-date rows.
