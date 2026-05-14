# Project Artifact Audit V1

Audit date: 2026-05-13

## Purpose

This audit identifies which project files and data artifacts are required by the current STR revenue pipeline, which are optional or deprecated, and which can be considered for later cleanup.

No files should be deleted, moved, or renamed from this audit alone. Raw run folders remain source-of-truth history and should be retained.

## Current Source Model

Current required raw inputs for a real weekly run:

- `data/runs/<run_date>/raw/priceLabs_future_export.csv`
- `data/runs/<run_date>/raw/price_occ.csv`
- `data/runs/<run_date>/raw/monthly_trends.csv`
- `data/runs/<run_date>/raw/bookings_report.xlsx`
- `data/runs/<run_date>/raw/pricelabs_settings_manual_input.json`

Current deprecated or optional raw inputs:

- `data/runs/<run_date>/raw/kpis_on_the_books.xlsx`
- Revenue On The Books exports, if present

Monthly Trends is now the primary monthly revenue, occupancy, and ADR truth source. Bookings Report is used for current/future cleanings, length of stay, booking window, and booking source mix. KPI On The Books is optional/deprecated unless a future reconciliation decision revives it.

## Raw Input Audit

| Path / Pattern | Type | Current Role | Classification | Recommended Action | Risk |
| --- | --- | --- | --- | --- | --- |
| `data/runs/<run_date>/raw/priceLabs_future_export.csv` | raw input | Required future calendar source for price, status, ADR proxy, and open ask | keep_current_pipeline | do_not_touch | High if removed; needed to reproduce reports |
| `data/runs/<run_date>/raw/price_occ.csv` | raw input | Required market/context source | keep_current_pipeline | do_not_touch | High if removed; needed for enrichment and window context |
| `data/runs/<run_date>/raw/monthly_trends.csv` | raw input | Required monthly truth source for revenue, occupancy, and ADR | keep_current_pipeline | do_not_touch | High if removed; current-month report accuracy depends on it |
| `data/runs/<run_date>/raw/bookings_report.xlsx` | raw input | Required reservation source for cleanings, LOS, booking window, and source mix | keep_current_pipeline | do_not_touch | High if removed; cleaning/source metrics depend on it |
| `data/runs/<run_date>/raw/pricelabs_settings_manual_input.json` | raw input | Required PriceLabs settings snapshot input | keep_current_pipeline | do_not_touch | High if removed; settings tracking depends on it |
| `data/runs/<run_date>/raw/kpis_on_the_books.xlsx` | raw input | Optional/deprecated historical KPI source | deprecated_candidate | archive_later | Medium; only remove after KPI path decision |
| Revenue On The Books exports | raw input | Optional/deprecated reconciliation source if present | deprecated_candidate | archive_later | Medium; may be useful for reconciliation |
| `data/runs/2026-05-03/raw/*` | raw input | Older raw run without Monthly Trends/Bookings Report | debug_optional | keep | Low; incomplete for current pipeline but useful as historical/debug source |
| `data/runs/2026-05-05/raw/*` | raw input | Older raw run without Monthly Trends/Bookings Report | debug_optional | keep | Low; incomplete for current pipeline but useful as historical/debug source |
| `data/runs/2026-05-08/raw/PriceLabs_future_export.csv` | raw input | Older run with non-canonical filename casing | unknown_needs_review | keep | Medium; do not rename without checking runner compatibility/history |
| `data/runs/2026-05-11/raw/PriceLabs_future_export.csv` | raw input | Older run with non-canonical filename casing | unknown_needs_review | keep | Medium; do not rename without checking runner compatibility/history |
| `data/runs/2026-05-12/raw/PriceLabs_future_export.csv` | raw input | Older run with non-canonical filename casing | unknown_needs_review | keep | Medium; do not rename without checking runner compatibility/history |
| `sample_data/*` | sample fixture | Debug/test fixture inputs, not operational source | debug_optional | archive_later | Low; useful for tests and examples, not real weekly source |

## Generated Output Audit

Current generated outputs under `data/runs/<run_date>/standardized/`, `data/runs/<run_date>/analysis/`, `data/runs/<run_date>/settings/`, and `data/runs/<run_date>/logs/` are reproducible from raw inputs and pipeline code. They may be deleted and regenerated only after raw files are confirmed retained.

| Path / Pattern | Type | Current Role | Classification | Recommended Action | Risk |
| --- | --- | --- | --- | --- | --- |
| `data/runs/<run_date>/standardized/future_daily_pricing_<run_date>.csv` | generated output | Standardized daily future calendar | keep_current_pipeline | keep | Medium; reproducible but useful for audit/debug |
| `data/runs/<run_date>/analysis/future_daily_pricing_enriched_<run_date>.csv` | generated output | Enriched daily analysis with revenue proxy fields | keep_current_pipeline | keep | Medium; reproducible but central to downstream outputs |
| `data/runs/<run_date>/analysis/monthly_trends_normalized_<run_date>.csv` | generated output | Normalized Monthly Trends truth source | keep_current_pipeline | keep | Medium; downstream monthly reporting depends on it |
| `data/runs/<run_date>/analysis/bookings_report_normalized_<run_date>.csv` | generated output | Normalized reservation-level source | keep_current_pipeline | keep | Medium; downstream booking metrics depend on it |
| `data/runs/<run_date>/analysis/monthly_booking_metrics_<run_date>.csv` | generated output | Monthly cleanings, LOS, booking window, and source mix | keep_current_pipeline | keep | Medium; downstream reports depend on it |
| `data/runs/<run_date>/analysis/monthly_revenue_pace_<run_date>.csv` | generated output | Monthly revenue pace diagnostics | keep_current_pipeline | keep | Medium; source for rolling view |
| `data/runs/<run_date>/analysis/rolling_13_month_revenue_view_<run_date>.csv` | generated output | Stable -6 to +6 monthly reporting view | keep_current_pipeline | keep | Medium; source for summaries and email reports |
| `data/runs/<run_date>/analysis/monthly_revenue_summary_<run_date>.md` | generated output | Full human-readable monthly summary | keep_current_pipeline | keep | Low; reproducible report output |
| `data/runs/<run_date>/analysis/email_revenue_report_<run_date>.md` | generated output | Email-ready markdown report | keep_current_pipeline | keep | Low; reproducible report output |
| `data/runs/<run_date>/analysis/email_revenue_report_<run_date>.html` | generated output | Readable HTML email report | keep_current_pipeline | keep | Low; reproducible report output |
| `data/runs/<run_date>/analysis/email_revenue_report_<run_date>.eml` | generated output | Local plain-text email draft copy | keep_current_pipeline | keep | Low; reproducible report output |
| `data/runs/<run_date>/analysis/future_window_summary_<run_date>.csv` | generated output | Window-level future analysis | keep_current_pipeline | keep | Low; still part of current pipeline |
| `data/runs/<run_date>/analysis/future_window_signals_<run_date>.csv` | generated output | Window-level signal labels | keep_current_pipeline | keep | Low; still part of current pipeline |
| `data/runs/<run_date>/analysis/future_signal_change_review_<run_date>.csv` | generated output | Signal trend review with settings changes | keep_current_pipeline | keep | Low; still part of current pipeline |
| `data/runs/<run_date>/settings/pricelabs_settings_snapshot_<run_date>.json` | generated output | Structured settings snapshot | keep_current_pipeline | keep | Medium; settings history/audit output |
| `data/runs/<run_date>/settings/pricelabs_settings_changes_<run_date>.csv` | generated output | Settings change log | keep_current_pipeline | keep | Medium; settings history/audit output |
| `data/runs/<run_date>/settings/pricelabs_transform_config.toml` | generated output/config copy | Per-run transform config | keep_current_pipeline | keep | Medium; helps reproduce run behavior |
| `data/runs/<run_date>/manifest.json` | generated output | Per-run manifest | keep_current_pipeline | keep | Low; reproducible but useful audit record |
| `data/runs/<run_date>/logs/scheduled_pipeline_<run_date>.log` | generated output | Scheduler wrapper log | keep_current_pipeline | keep | Low; useful operational record |
| `data/runs/2026-05-08/analysis/historical_monthly_actuals_2026-05-08.csv` | generated output | KPI-based historical actuals from deprecated optional path | deprecated_candidate | archive_later | Low; keep until KPI path is formally retired |
| `data/runs/2026-05-03/analysis/*` | generated output | Older pre-Monthly Trends reports | debug_optional | archive_later | Low; reproducible only from older input set |
| `data/runs/2026-05-05/analysis/*` | generated output | Older pre-Monthly Trends reports | debug_optional | archive_later | Low; reproducible only from older input set |
| `data/runs/2026-05-08/analysis/*` | generated output | Older KPI-era/current-pipeline transition reports | debug_optional | archive_later | Low; useful for before/after comparisons |
| `data/runs/2026-05-11/analysis/*` | generated output | Pre-Step-26 source-label reports | debug_optional | archive_later | Low; useful for scheduler debugging history |
| `data/runs/2026-05-12/analysis/*` | generated output | Pre-Step-26 source-label reports | debug_optional | archive_later | Low; useful for scheduler debugging history |
| `data/runs/2026-05-11/logs/task_scheduler_smoke_test.log` | generated output | Task Scheduler startup diagnostic log | debug_optional | delete_candidate_after_review | Low; only keep if still debugging Task Scheduler |
| `data/runs/2099-01-01/logs/scheduled_pipeline_2099-01-01.log` | generated test artifact | Test-created scheduler wrapper log | debug_optional | delete_candidate_after_review | Low; generated by tests |
| `.pytest_cache/` | generated cache | Pytest cache | deprecated_candidate | delete_candidate_after_review | Low; safe generated cache |
| `src/**/__pycache__/`, `tests/**/__pycache__/`, `*.pyc` | generated cache | Python bytecode cache | deprecated_candidate | delete_candidate_after_review | Low; safe generated cache |

## Source Module Audit

| Path / Pattern | Type | Current Role | Classification | Recommended Action | Risk |
| --- | --- | --- | --- | --- | --- |
| `src/pricelabs/transform/run.py` | source module | Operational transform entry point | active_required | keep | High if removed |
| `src/pricelabs/transform/mapping.py` | source module | Raw-to-standardized mapping rules | active_required | keep | High if removed |
| `src/pricelabs/transform/validation.py` | source module | Shared validation helpers | active_required | keep | High if removed |
| `src/pricelabs/transform/manifest.py` | source module | Manifest writer | active_required | keep | Medium if removed |
| `src/pricelabs/transform/enrich_future.py` | source module | Daily enrichment and Step 1 revenue proxy fields | active_required | keep | High if removed |
| `src/pricelabs/transform/monthly_trends.py` | source module | Monthly Trends normalizer | active_required | keep | High if removed |
| `src/pricelabs/transform/bookings_report.py` | source module | Bookings Report normalizer and monthly metrics/source mix | active_required | keep | High if removed |
| `src/pricelabs/transform/monthly_revenue_pace.py` | source module | Monthly revenue pace diagnostics | active_required | keep | High if removed |
| `src/pricelabs/transform/rolling_13_month_revenue_view.py` | source module | Rolling 13-month view and source labels | active_required | keep | High if removed |
| `src/pricelabs/transform/monthly_revenue_summary.py` | source module | Full markdown monthly summary | active_required | keep | Medium if removed |
| `src/pricelabs/transform/email_revenue_report.py` | source module | Email-ready markdown report | active_required | keep | Medium if removed |
| `src/pricelabs/transform/email_html_report.py` | source module | HTML email report conversion | active_required | keep | Medium if removed |
| `src/pricelabs/transform/email_draft_file.py` | source module | Local `.eml` draft generation | active_required | keep | Medium if removed |
| `src/pricelabs/transform/email_sender.py` | source module | Optional explicit SMTP send mode | active_required | keep | Medium if removed |
| `src/pricelabs/transform/summarize_future.py` | source module | Window summary generation | active_required | keep | Medium if removed |
| `src/pricelabs/transform/signal_future.py` | source module | Window signal generation | active_required | keep | Medium if removed |
| `src/pricelabs/transform/review_signal_changes.py` | source module | Signal change review | active_required | keep | Medium if removed |
| `src/pricelabs/transform/settings_snapshot.py` | source module | Settings snapshot generation | active_required | keep | Medium if removed |
| `src/pricelabs/transform/settings_changes.py` | source module | Settings diff generation | active_required | keep | Medium if removed |
| `src/pricelabs/transform/historical_monthly_actuals.py` | source module | Optional/deprecated KPI historical normalizer | legacy_optional | archive_later | Medium; remove only after KPI tests and docs are retired |
| `src/pricelabs/transform/README.md` | source doc | Module-level transform notes | unknown_needs_review | keep_but_update_docs | Low; review for stale pipeline wording |
| `run_weekly_pipeline.ps1` | script | Main manual pipeline runner | active_required | keep | High if removed |
| `scripts/run_scheduled_weekly_pipeline.ps1` | script | Safe scheduler wrapper | active_required | keep | High for scheduled local runs |
| `run_pricelabs_transform.ps1` | script | Older transform-only helper | legacy_optional | archive_later | Low; may still help narrow debugging |

## Documentation Audit

| Path / Pattern | Type | Current Role | Classification | Recommended Action | Risk |
| --- | --- | --- | --- | --- | --- |
| `contracts/pricelabs-weekly-csv-v1.md` | contract doc | Main pipeline/output contract | needs_update | keep_but_update_docs | Medium; still contains KPI-era sections that should reflect Monthly Trends primary source |
| `docs/data-source-strategy-v1.md` | design doc | Source ownership strategy | current | keep | Low; already reflects Monthly Trends/Bookings as primary |
| `docs/weekly-scheduling-design-v1.md` | design doc | Scheduling safety design | current | keep | Low; reflects required Monthly Trends/Bookings files |
| `docs/windows-task-scheduler-setup-v1.md` | runbook doc | Task Scheduler setup guide | current | keep | Low; reflects required Monthly Trends/Bookings files |
| `docs/task-scheduler-troubleshooting-v1.md` | troubleshooting doc | 0x1 startup diagnostics | current | keep | Low |
| `docs/email-delivery-design-v1.md` | design doc | Email draft/SMTP/HTML behavior | current | keep | Low |
| `docs/recommendation-rules-v1.md` | design doc | Recommendation matrix design | current | keep | Low |
| `docs/runbook-weekly-pricelabs.md` | runbook doc | Weekly manual runbook | needs_update | keep_but_update_docs | Medium; verify required raw-file list includes Monthly Trends and Bookings |
| `docs/pricelabs-pipeline.md` | old pipeline doc | Early pipeline design and sample-data references | deprecated_candidate | archive_later | Low; contains old top-level `standardized/` and sample-data framing |
| `docs/pricelabs-v1-source-to-target-mapping.md` | old mapping doc | Early source mapping with sample-data paths | deprecated_candidate | archive_later | Low; likely superseded by current contract/code |
| `docs/source-triage-for-analysis.md` | old analysis doc | Source triage with sample-data paths | needs_update | keep_but_update_docs | Low; useful conceptually but stale operational paths |
| `docs/standardized-output-contract-v1.md` | old contract doc | Standardized daily output contract | needs_update | keep_but_update_docs | Low; still references top-level `standardized/` and sample data |
| `docs/validation-checklist-v1.md` | checklist doc | Earlier validation checklist | needs_update | keep_but_update_docs | Low; still references old output paths |
| `README.md` | project overview | General project guidance | needs_update | keep_but_update_docs | Medium; still contains sample-data and top-level standardized examples |

## Config Audit

| Path / Pattern | Type | Current Role | Classification | Recommended Action | Risk |
| --- | --- | --- | --- | --- | --- |
| `config/email.example.toml` | config template | Safe committed email config template | active_required | keep | Low; should stay draft/safe |
| `config/email.toml` | local config | Local ignored email config | active_required | do_not_touch | High; may contain local personal addresses; never commit secrets |
| `config/pricelabs.example.env` | config template | PriceLabs environment example | legacy_optional | keep_but_update_docs | Low; review before download automation |
| `config/pricelabs.single-listing.example.toml` | config template | Single-listing transform example | legacy_optional | keep_but_update_docs | Low; review against current run folder model |
| `.gitignore` | repo config | Ignores `config/email.toml`, `data/runs/**`, Python caches | active_required | keep | Low |

No secrets should be stored in committed config, docs, logs, or generated reports. `config/email.toml` should remain local and ignored.

## Test Audit

| Path / Pattern | Type | Current Role | Classification | Recommended Action | Risk |
| --- | --- | --- | --- | --- | --- |
| `tests/test_enrich_future.py` | test | Daily enrichment and revenue proxy tests | active_required | keep | Medium |
| `tests/test_monthly_trends.py` | test | Monthly Trends normalization tests | active_required | keep | Medium |
| `tests/test_bookings_report.py` | test | Bookings Report normalization, metrics, and source mix tests | active_required | keep | Medium |
| `tests/test_monthly_revenue_pace.py` | test | Monthly pace diagnostics tests | active_required | keep | Medium |
| `tests/test_rolling_13_month_revenue_view.py` | test | Rolling view, source label, and historical/data availability tests | active_required | keep | Medium |
| `tests/test_monthly_revenue_summary.py` | test | Full markdown summary tests | active_required | keep | Medium |
| `tests/test_email_revenue_report.py` | test | Email markdown report tests | active_required | keep | Medium |
| `tests/test_email_html_report.py` | test | HTML email report tests | active_required | keep | Medium |
| `tests/test_email_draft_file.py` | test | `.eml` draft generation tests | active_required | keep | Medium |
| `tests/test_email_sender.py` | test | Optional SMTP send-mode tests with mocked SMTP | active_required | keep | Medium |
| `tests/test_scheduled_wrapper.py` | test | Scheduler wrapper safety tests | active_required | keep | Medium |
| `tests/test_historical_monthly_actuals.py` | test | Optional/deprecated KPI historical normalizer tests | legacy_but_still_valid | archive_later | Low; remove only if KPI path is formally retired |
| `tests/__pycache__/`, `*.pyc` | generated cache | Python bytecode cache | deprecated_candidate | delete_candidate_after_review | Low |

## Cleanup Recommendations

| Path / Pattern | Type | Current Role | Classification | Recommended Action | Risk |
| --- | --- | --- | --- | --- | --- |
| Required raw files in `data/runs/<run_date>/raw/` | raw input | Source of truth | keep_current_pipeline | do_not_touch | High |
| Older raw run folders | raw input | Historical/debug source | debug_optional | keep | Medium |
| Current generated outputs for 2026-05-13 | generated output | Current pipeline examples | keep_current_pipeline | keep | Low |
| Older generated outputs for 2026-05-03 through 2026-05-12 | generated output | Pre-current-contract snapshots | debug_optional | archive_later | Low |
| KPI-only artifacts and `historical_monthly_actuals_*` | generated output/source module/tests | Deprecated optional KPI path | deprecated_candidate | archive_later | Medium |
| `sample_data/*` | fixture data | Debug/test fixtures | debug_optional | archive_later | Low |
| `data/runs/2099-01-01/` | generated test artifact | Scheduler wrapper test output | debug_optional | delete_candidate_after_review | Low |
| `.pytest_cache/`, `__pycache__/`, `*.pyc` | generated cache | Local test/runtime cache | deprecated_candidate | delete_candidate_after_review | Low |
| Stale docs with top-level `standardized/` or sample-data-as-primary references | documentation | Historical docs | needs_update | keep_but_update_docs | Medium |
| `config/email.toml` | local config | Local email mode/recipient config | active_required | do_not_touch | High |

## Proposed Cleanup Sequence

Step 26h - Documentation cleanup:

- Update or retire docs that still frame `sample_data/`, top-level `standardized/`, or KPI On The Books as primary.
- Bring the main contract and runbook fully in line with Monthly Trends and Bookings Report as required weekly sources.

Step 26i - Remove deprecated generated artifacts from sample/test areas only:

- Remove Python caches and pytest cache.
- Consider deleting generated test artifacts such as `data/runs/2099-01-01/` after confirming tests recreate them as needed.
- Do not remove raw run folders.

Step 26j - Remove deprecated code only if tests prove unused:

- Decide whether the KPI historical normalizer path remains as an optional reconciliation tool.
- If retired, remove `historical_monthly_actuals.py` and its tests in one focused change.

Step 27 - Playwright download design:

- Design browser/download automation only after required raw-file contracts and cleanup decisions are stable.

## Guardrails

- Do not delete raw run folders.
- Do not treat generated reports as source of truth.
- Do not commit `config/email.toml` or credentials.
- Do not mix deprecated KPI/Revenue On The Books logic back into the primary monthly truth path unless a future design explicitly calls for it.
- Do not add Playwright automation as part of cleanup.
