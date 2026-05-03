# PriceLabs Transform Package

This package is reserved for transformation-only work for the weekly PriceLabs-to-CSV pipeline.

Current scope:

- Define module boundaries for mapping, validation, and manifest generation.
- Keep all V1 behavior traceable to `contracts/pricelabs-weekly-csv-v1.md`.
- Use `config/pricelabs.single-listing.example.toml` as the single-listing config shape.
- Avoid extraction, browser automation, scheduling, or delivery behavior.

No business logic is implemented yet.

Future modules:

- `mapping.py`: map approved source rows into the V1 standardized dataset shape.
- `validation.py`: validate required fields, status values, comparison guardrails, and output invariants.
- `manifest.py`: generate run metadata for standardized CSV outputs.
