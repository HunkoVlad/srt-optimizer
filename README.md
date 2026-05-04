# srt-optimizer

This repository currently contains a Playwright + TypeScript test framework for SRT automation experiments and the initial documentation scaffold for a weekly PriceLabs-to-CSV pipeline.

## Active Workstreams

### SRT Automation Test Framework

The existing Playwright demo validates test architecture, page-object style, and deterministic UI automation before wiring real SRT processing flows.

### Weekly PriceLabs-to-CSV Pipeline

The repository now reserves structure and documentation for a weekly pipeline that will convert PriceLabs data into a V1 contract-compliant CSV export.

Current state:

- Repository structure and documentation only.
- Revised V1 contract added at `contracts/pricelabs-weekly-csv-v1.md`.
- Extraction is intentionally not implemented.
- Local data, generated exports, and logs are gitignored.

Start with:

- `docs/pricelabs-pipeline.md` for architecture and boundaries.
- `docs/runbook-weekly-pricelabs.md` for the weekly operating scaffold.
- `docs/pricelabs-v1-source-to-target-mapping.md` for the current PriceLabs export mapping.
- `docs/standardized-output-contract-v1.md` and `docs/validation-checklist-v1.md` for output and validation documentation.
- `src/pricelabs/README.md` for source module ownership boundaries.

V1 separates two analytical views:

- Open-night pricing view for available dates.
- Booked-night value view for reserved dates, using booked-date `nightly_price` only as a provisional proxy.

Daily listing occupancy versus market occupancy comparison is explicitly out of scope; occupancy comparisons belong only to aggregated 30/60/90-day windows.

## Architectural Principles

### Pages = UI only

- No environment logic
- No credential lookup
- No test branching
- No infrastructure decisions

### Fixtures and demo data = deterministic setup only

- Sample subtitle jobs live in typed fixtures
- Reusable UI rendering helpers stay outside test orchestration
- Future environment bootstrapping should be isolated from page objects

### Tests = orchestration only

- Compose flows
- Pass typed inputs
- Assert user-visible behavior
- Keep UI internals inside page helpers

## Coding Conventions

### Locator standards

- Structural and stable elements should be exposed through well-named readonly accessors or constructor-initialized locators
- Dynamic or parameterized elements should be wrapped in small helper methods returning `Locator`
- Prefer `getByRole()` with accessible names over CSS selectors or XPath
- Use `getByTestId()` only for stable app-owned hooks where semantic selectors would be noisy or ambiguous
- Use exact matching for unique labels and `RegExp` only when text is intentionally dynamic
- Avoid `.first()` unless multiple matches are expected and the first match is deterministically correct

### Waiting strategy

- Prefer deterministic assertions such as `await expect(locator).toBeVisible()`
- Wait on stable UI state, not elapsed time
- Use enabled, visible, and text assertions to model readiness
- Never use `page.waitForTimeout()` in page helpers
- Never use `locator.isVisible()` as a wait because it returns immediately

### Method organization in page objects

- Constructor or top-level accessors: structural locators
- Private helpers: one focused UI step at a time
- Public API: high-level user flows composed from helpers

## Code Style

- TypeScript strict mode
- ES2022 target
- CommonJS modules
- Minimal comments, only where extra context meaningfully helps
- Keep tests readable enough that intent is obvious without narration

## Current Demo Scope

The current sample demonstrates:

- Typed subtitle job fixture data
- A self-contained SRT batch console rendered directly in the test
- A lightweight page-object model
- Batch preview assertions for projected cue savings and review time
- Optimization run assertions for row state and report availability

## Running Tests

Install dependencies:

```powershell
npm install
```

Run the full Playwright suite:

```powershell
npm run test:e2e
```

Run the focused SRT demo in Chromium:

```powershell
npm run test:e2e:demo
```

## Running The Manual PriceLabs V1 Transform

Place the manually downloaded PriceLabs CSV at the `input_path` from `config/pricelabs.single-listing.example.toml`, then set `listing_id` in that config for the single listing being transformed.

Run from the repo root:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pricelabs.transform.run --config config\pricelabs.single-listing.example.toml --run-date 2026-05-03
```

Outputs:

- `standardized/future_daily_pricing_<run_date>.csv`
- `manifest.json`

The transform reads only PriceLabs CSV input, filters to the configured one listing, keeps stay dates in the next 180 days from `run_date`, normalizes status values, and writes the V1 standardized columns.

## Browser Coverage

`playwright.config.ts` is configured for:

- Chromium
- Firefox
- WebKit

The focused demo command currently targets Chromium for quick iteration.

## Project Structure

```text
srt-optimizer/
|-- contracts/
|   `-- pricelabs-weekly-csv-v1.md   # Canonical V1 contract location
|-- config/
|   `-- pricelabs.single-listing.example.toml
|-- docs/
|   |-- pricelabs-pipeline.md        # Pipeline architecture and operating notes
|   |-- pricelabs-v1-source-to-target-mapping.md
|   |-- standardized-output-contract-v1.md
|   |-- validation-checklist-v1.md
|   `-- runbook-weekly-pricelabs.md  # Weekly runbook scaffold
|-- e2e/
|   |-- example.spec.ts              # Starter Playwright sample
|-- src/
|   `-- pricelabs/                   # Future PriceLabs pipeline package
|       `-- transform/               # Python transformation scaffold only
|-- standardized/
|   `-- .gitkeep                     # Future standardized CSV output directory
|-- tests/
|   |-- fixtures/
|   |   |-- srtOptimizerDemo.ts       # Sample subtitle data + demo UI renderer
|   |-- example.spec.ts              # Demo Playwright spec with page-object helpers
|-- package.json                     # Test scripts and dev dependencies
|-- package-lock.json
|-- playwright.config.ts             # Playwright projects, reporter, retries, workers
|-- README.md
`-- tsconfig.json                    # Strict TypeScript config with Node and Playwright types
```

## Near-Term Direction

As we expand this into real SRT automation and the PriceLabs pipeline, the framework should evolve toward:

- Shared page objects for subtitle upload, parsing, optimization, and export flows
- Reusable fixtures for source files, environment configuration, and cleanup
- Feature-focused tests that orchestrate flows without embedding UI details
- Stable, deterministic selectors and assertions that work across environments
- V1-contract-driven PriceLabs fixtures, transformations, validations, and CSV export tests
