# Email Report Evidence Attachments v1

## Purpose

Weekly email reports should stay concise, but investigation signals should have the supporting evidence close at hand. This design defines future attachment categories for the weekly PriceLabs report without changing current recommendation logic, pricing rules, or email sending behavior.

PriceLabs remains the source of truth for revenue, occupancy, ADR, booked nights, booking totals, cleaning count, and monthly revenue pace. Airbnb files are diagnostic only and must be labeled as visibility/conversion context, not portfolio performance truth.

## Current Email Capability

Current email generation is body-only:

- `src/pricelabs/transform/email_revenue_report.py` writes `analysis/email_revenue_report_<run_date>.md`.
- `src/pricelabs/transform/email_html_report.py` writes `analysis/email_revenue_report_<run_date>.html`.
- `src/pricelabs/transform/email_draft_file.py` writes a local `.eml` draft with plain-text body only.
- `src/pricelabs/transform/email_sender.py` can send markdown/plain text and optional HTML body, but does not attach files.
- `config/email.toml` currently has `email.mode = "draft"`, `smtp.enabled = false`, and `include_attachments = false`.

Attachments are therefore not active yet. Any implementation should preserve draft mode by default and require explicit enablement.

## Proposed Evidence Bundle

Before attaching files, future implementation should copy selected files into:

`data/runs/<run_date>/analysis/evidence_bundle_<run_date>/`

This keeps email attachments deterministic, auditable, and separated from raw pipeline folders. The email sender should attach from the bundle only, not directly from `raw/`, `settings/`, or scattered analysis paths.

Suggested copied filename format:

`<run_date>__<category>__<original_filename>`

Examples:

- `2026-05-20__report__email_revenue_report_2026-05-20.md`
- `2026-05-20__pricelabs_core__future_window_signals_2026-05-20.csv`
- `2026-05-20__airbnb_diagnostic__airbnb_similar_listing_summary_2026-05-20.csv`
- `2026-05-20__settings__pricelabs_settings_changes_2026-05-20.csv`

## Always Attach

Attach these on every weekly report when present:

- `data/runs/<run_date>/analysis/email_revenue_report_<run_date>.md`
- `data/runs/<run_date>/analysis/rolling_13_month_revenue_view_<run_date>.csv`
- `data/runs/<run_date>/analysis/monthly_revenue_summary_<run_date>.md`
- `data/runs/<run_date>/analysis/performance_reason_review_<run_date>.csv`
- `data/runs/<run_date>/analysis/future_window_summary_<run_date>.csv`
- `data/runs/<run_date>/analysis/future_window_signals_<run_date>.csv`
- `data/runs/<run_date>/analysis/combined_market_listing_signal_<run_date>.csv`

These files explain the core weekly recommendation context and preserve the PriceLabs/core analysis trail.

## Attach For High Investigation Priority

Attach these only when investigation priority is `high` or `urgent`, or when the email includes pricing-efficiency risk context:

- `data/runs/<run_date>/analysis/airbnb_weekly_history_comparison_<run_date>.csv`
- `data/runs/<run_date>/analysis/airbnb_similar_listing_summary_<run_date>.csv`
- `data/runs/<run_date>/analysis/airbnb_daily_similar_listing_comparison_<run_date>.csv`
- `data/runs/<run_date>/settings/pricelabs_settings_snapshot_<run_date>.json`
- `data/runs/<run_date>/settings/pricelabs_settings_changes_<run_date>.csv`

Airbnb files should be labeled `airbnb_diagnostic` in the evidence bundle. They can support visibility and conversion investigation, but cannot create PriceLabs rule recommendations by themselves.

## Do Not Attach

Do not attach by default:

- Raw PriceLabs downloads from `raw/`.
- Temporary browser downloads from `downloads_staging/`.
- PriceLabs or Airbnb HTML captures.
- Browser screenshots, DOM dumps, Playwright logs, or authentication artifacts.
- `bookings_report.xlsx` unless a later workflow explicitly needs booking-level audit evidence.
- Very large daily files such as `future_daily_pricing_enriched_<run_date>.csv` unless a size cap and explicit trigger are added.
- Any file containing credentials, cookies, tokens, MFA codes, browser state, or local secrets.

## Trigger Rules

Default bundle:

- Build when the weekly email report is created.
- Include always-attach files that exist.

High-priority bundle additions:

- Add high-priority investigation files when `combined_market_listing_signal_<run_date>.csv` has `investigation_priority` of `high` or `urgent`.
- Add high-priority investigation files when Recommendation Review includes `Pricing efficiency risk:`.
- Add high-priority investigation files when `performance_reason_review_<run_date>.csv` includes `recommendation_allowed=true` or `likely_reason` of `price_or_rule_issue` or `settings_change_impact`.

Airbnb-only trigger:

- Airbnb diagnostics may add Airbnb diagnostic evidence, but must not add PriceLabs rule-change language or alter recommendation logic.

## Missing Attachment Behavior

Missing evidence files should not fail report generation or email draft creation.

Recommended behavior:

- Copy existing files into the evidence bundle.
- Write a manifest: `evidence_manifest_<run_date>.csv`.
- Manifest columns: `run_date`, `attachment_category`, `source_path`, `bundle_path`, `status`, `notes`.
- Use `status=missing` for expected-but-missing optional files.
- Fail only if the email report body itself is missing.

## Size And Noise Controls

Future implementation should enforce a conservative total attachment size cap, for example 10 MB.

If the bundle exceeds the cap:

- Keep the report markdown and core summary CSVs.
- Prefer compact summaries over detailed daily rows.
- Omit large files first.
- Record omissions in the evidence manifest.

## Future Implementation Plan

1. Add an evidence bundle builder module, for example:
   `src/pricelabs/transform/email_evidence_bundle.py`
2. Add CLI:
   `python -m pricelabs.transform.email_evidence_bundle --run-date <run_date>`
3. Run it after `email_revenue_report` and before `email_draft_file`.
4. Add optional config:
   - `email.include_attachments = true`
   - `email.attachment_mode = "bundle"`
   - `email.max_attachment_mb = 10`
5. Update `email_draft_file.py` to optionally attach bundle files to the `.eml`.
6. Update `email_sender.py` to optionally attach the same bundle files when send mode is explicitly enabled.
7. Keep default behavior unchanged: draft mode, no attachments.

## Tests Needed Later

- Evidence bundle includes always-attach files when present.
- High-priority signal adds Airbnb/settings diagnostic files.
- Missing optional files are recorded in manifest and do not fail the report.
- Raw files, HTML captures, screenshots, logs, and staging files are not bundled.
- Airbnb files are labeled diagnostic.
- `.eml` draft includes attachments only when `include_attachments=true`.
- SMTP sender includes attachments only when both `mode=send` and `include_attachments=true`.
- Total attachment size cap is enforced.
- No credentials or local secrets are attached or logged.
