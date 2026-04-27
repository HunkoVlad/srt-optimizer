# srt-optimizer - Unified E2E Test Framework

End-to-end Playwright tests for SRT automation and subtitle optimization workflows.

This repository currently contains a self-contained Playwright + TypeScript demo used to validate test architecture, page-object style, and deterministic UI automation before wiring real SRT processing flows.

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

## Browser Coverage

`playwright.config.ts` is configured for:

- Chromium
- Firefox
- WebKit

The focused demo command currently targets Chromium for quick iteration.

## Project Structure

```text
srt-optimizer/
|-- e2e/
|   |-- example.spec.ts              # Starter Playwright sample
|-- tests/
|   |-- fixtures/
|   |   |-- srtOptimizerDemo.ts      # Sample subtitle data + demo UI renderer
|   |-- example.spec.ts              # Demo Playwright spec with page-object helpers
|-- package.json                     # Test scripts and dev dependencies
|-- package-lock.json
|-- playwright.config.ts             # Playwright projects, reporter, retries, workers
|-- README.md
`-- tsconfig.json                    # Strict TypeScript config with Node and Playwright types
```

## Near-Term Direction

As we expand this into real SRT automation, the framework should evolve toward:

- Shared page objects for subtitle upload, parsing, optimization, and export flows
- Reusable fixtures for source files, environment configuration, and cleanup
- Feature-focused tests that orchestrate flows without embedding UI details
- Stable, deterministic selectors and assertions that work across environments
