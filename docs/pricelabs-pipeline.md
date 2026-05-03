# Weekly PriceLabs-to-CSV Pipeline

This repository is being prepared for a weekly pipeline that converts PriceLabs data into a contract-compliant CSV export. The initial repository structure is documentation-first and intentionally does not implement PriceLabs extraction.

## Current Scope

- Establish the folder layout for a repeatable weekly pipeline.
- Reserve a canonical home for the V1 contract.
- Document pipeline stages, operational expectations, and guardrails.
- Document the revised V1 split between available-date pricing analysis and booked-date value analysis.
- Keep extraction, authentication, and PriceLabs automation out of scope.

## Pipeline Shape

```text
PriceLabs source
  -> extract      # Future: fetch or receive PriceLabs data; not implemented yet
  -> transform    # Future: normalize records to the V1 standardized dataset
  -> validate     # Future: verify required fields and comparison guardrails
  -> export       # Future: write standardized/future_daily_pricing_<run_date>.csv
  -> archive/log  # Future: retain run metadata and troubleshooting context
```

## Repository Layout

```text
srt-optimizer/
|-- contracts/
|   `-- pricelabs-weekly-csv-v1.md   # Canonical V1 contract location
|-- docs/
|   |-- pricelabs-pipeline.md        # Pipeline architecture and operating notes
|   |-- standardized-output-contract-v1.md
|   |-- pricelabs-v1-source-to-target-mapping.md
|   |-- validation-checklist-v1.md
|   `-- runbook-weekly-pricelabs.md  # Weekly runbook scaffold
|-- src/
|   `-- pricelabs/
|       |-- README.md                # Source package boundaries
|       |-- extract/                 # Future extraction module placeholder
|       |-- transform/               # Future contract mapping module placeholder
|       |-- export/                  # Future CSV writer placeholder
|       `-- pipeline/                # Future orchestration placeholder
|-- config/
|   |-- pricelabs.example.env        # Documented environment template only
|   `-- pricelabs.single-listing.example.toml
|-- standardized/
|   `-- .gitkeep                     # Future standardized CSV output directory
|-- data/
|   |-- incoming/                    # Local input drop zone; gitignored
|   |-- processed/                   # Local normalized intermediates; gitignored
|   `-- exports/                     # Local CSV outputs; gitignored
`-- logs/                            # Local run logs; gitignored
```

## Stage Responsibilities

### Extract

Planned responsibility: acquire weekly PriceLabs source data and store it in a controlled incoming area.

Initial state: not implemented. This scaffold must not make assumptions about PriceLabs UI selectors, API availability, credentials, or source format.

### Transform

Planned responsibility: map extracted records into the V1 standardized dataset, including deterministic date, currency, number, and text formatting.

Initial state: not implemented. Mapping rules should preserve the V1 split between open-night pricing and booked-night value analysis.

### Validate

Planned responsibility: enforce the V1 contract before any CSV is accepted as a weekly output.

Initial state: documented only. Expected future checks include required columns, column order, row counts, field formats, duplicate detection, empty value policy, valid `status` values, and comparison guardrails.

### Export

Planned responsibility: write a weekly CSV artifact at `standardized/future_daily_pricing_<run_date>.csv`, using the encoding required by the V1 contract.

Initial state: not implemented. The `standardized/` directory is reserved for the V1 standardized CSV and remains gitignored except for `.gitkeep`. The `data/exports/` directory is reserved for any local delivery copies or downstream exports and also remains gitignored.

## Contract Handling

The V1 contract is the source of truth. Pipeline code should keep field names, business rules, and delivery conventions traceable to `contracts/pricelabs-weekly-csv-v1.md`.

Supporting documentation:

- `docs/standardized-output-contract-v1.md` defines the V1 output artifact and required columns.
- `docs/pricelabs-v1-source-to-target-mapping.md` defines the current PriceLabs source-to-target mapping.
- `docs/validation-checklist-v1.md` defines the non-executable validation checklist.

V1 defines one standardized dataset with required fields:

- `run_date`
- `listing_id`
- `stay_date`
- `nightly_price`
- `min_stay`
- `status`

Optional later fields from the same PriceLabs export:

- `market_price`
- `market_occupancy`

## Analytical Views

### Available Dates

Filter to `status = available`.

Use this view for current asking price analysis, market positioning, weekend and 1-night premiums, min-stay review, and open-date outlier review.

Daily comparisons are allowed for price and restriction decisions, including `nightly_price` vs `market_price` when `market_price` is present.

### Booked Dates

Filter to `status = booked`.

Use this view for directional booked-value quality analysis and upcoming ADR quality. In V1, `nightly_price` on booked dates is only a proxy for booked value, and the output must label it as provisional if PriceLabs changes displayed values after booking.

Daily booked-date value inspection is allowed, but booked-value trends are more meaningful at the next 30/60/90-day windows.

## Comparison Guardrails

Allowed daily:

- Available-date `nightly_price` vs `market_price`
- Booked-date proxy value vs `market_price`
- Min-stay inspection by date

Required at 30/60/90-day windows:

- Your booked share of nights vs `market_occupancy`
- Booked-value quality trends
- Available-date pricing posture

Not allowed:

- Daily row-level comparison of listing occupancy versus market occupancy.

## Implementation Guardrails

- Do not commit secrets, downloaded PriceLabs data, generated CSV files, or logs.
- V1 configuration is for one listing only: one `listing_id`, one `input_path`, and one `output_path`.
- Keep extraction separate from transformation and validation.
- Prefer deterministic fixtures for tests once the contract is known.
- Make every generated CSV reproducible from recorded input plus configuration.
- Fail closed when contract-required fields are absent or malformed.
- Keep available-date pricing analysis separate from booked-date value analysis.
- Label booked-date `nightly_price` as a proxy, not final realized ADR.
