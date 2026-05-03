# PriceLabs Pipeline Source Boundary

This directory is reserved for the weekly PriceLabs-to-CSV pipeline.

No extraction is implemented yet. The subdirectories define future ownership boundaries:

- `extract/`: acquire PriceLabs source data after the approved method is known.
- `transform/`: map source records to the V1 CSV contract.
- `export/`: write contract-compliant CSV artifacts to `standardized/future_daily_pricing_<run_date>.csv`.
- `pipeline/`: orchestrate stages, logging, validation, and run metadata.

Keep contract-specific behavior traceable to `contracts/pricelabs-weekly-csv-v1.md`.

V1 analysis must keep available-date pricing separate from booked-date value review. Daily price comparisons are allowed, but listing occupancy versus market occupancy must only be compared across aggregated 30/60/90-day windows.
