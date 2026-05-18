# PriceLabs Playwright Download Design V1

## Purpose

This design began as the PriceLabs downloader design. The current implemented weekly workflow uses a one-session PriceLabs download-all wrapper and preserves the staging-first architecture described here.

The existing STR revenue pipeline already works from trusted raw files under:

```text
data/runs/<run_date>/raw/
```

Raw files remain the source of truth. Generated outputs are reproducible. Downloads are staged and validated before promotion to trusted raw inputs.

## Scope

Included/current:

- PriceLabs browser download approach.
- Staging-first file handling.
- Validation and promotion rules.
- Safe failure and manual fallback rules.

Excluded:

- No scheduler integration yet.
- No pipeline behavior changes yet.
- No committed or shared PriceLabs credential storage.
- No changes to email behavior.

## Required PriceLabs Download Targets

The standard PriceLabs download-all workflow stages these files:

- `priceLabs_future_export.csv`
- `price_occ.csv`
- `monthly_trends.csv`
- `bookings_report.xlsx`
- `pricelabs_settings_snapshot_from_ui.json`

This file is deprecated/manual fallback only:

- `pricelabs_settings_manual_input.json`

The UI settings snapshot is the primary settings source. It is normalized before settings comparison. The manual settings JSON remains available only if the UI snapshot is missing.

## Recommended Folder Model

Use staging first:

```text
data/runs/<run_date>/downloads_staging/
data/runs/<run_date>/raw/
data/runs/<run_date>/logs/
```

The downloader writes into `downloads_staging/` first. Only validated files are promoted or copied into `raw/`.

## Why Staging First

Staging protects the raw source-of-truth folder.

It:

- Prevents corrupt or partial downloads from becoming trusted raw inputs.
- Supports validation before promotion.
- Preserves manual fallback.
- Prevents overwriting known-good raw files.
- Gives clear troubleshooting artifacts when a download fails.

## Proposed Download Flow

Current one-session downloader flow:

1. Create the run folder structure if missing.
2. Launch Playwright with a controlled download directory.
3. Use local-only credential login fallback when explicitly requested, or manual login/MFA fallback.
4. Download each required file to `downloads_staging/`.
5. Normalize filenames in staging.
6. Validate file presence.
7. Validate basic file shape.
8. Promote validated files to `raw/` only when safe.
9. Write a download attempt log.
10. Exit with a clear success or failure status.

The standard weekly workflow command is:

```powershell
.\scripts\run_weekly_with_pricelabs_downloads.ps1 -RunDate YYYY-MM-DD -UseLocalCredentials
```

Manual login command:

```powershell
.\scripts\run_weekly_with_pricelabs_downloads.ps1 -RunDate YYYY-MM-DD
```

Windows Task Scheduler should not use this Playwright workflow until scheduler integration is separately validated.

## Validation Before Promotion

Basic validation should happen before any file is promoted to `raw/`.

CSV validation:

- File exists.
- File size is greater than `0`.
- File is readable as CSV.
- Expected key columns exist, allowing reasonable header normalization.
- File is not an HTML login or error page accidentally saved as CSV.

XLSX validation:

- File exists.
- File size is greater than `0`.
- File is readable as a workbook.
- Expected worksheet or table shape is present.
- File is not an HTML login or error page.

Detailed business validation remains in the existing transform/report pipeline. The downloader should only prove that the downloaded files are plausible inputs before promotion.

## Expected Shape Checks By File

Use cautious checks because PriceLabs export columns may evolve.

### `priceLabs_future_export.csv`

Expected to include fields related to:

- Listing ID.
- Date.
- Recommended, customized, or user price.
- Minimum stay.
- Availability or status.
- ADR or booked information when available.

### `price_occ.csv`

Expected to include fields related to:

- Date.
- Market occupancy.
- Market price percentiles.
- Median booked price or comparable market price context.

This file is market context only. It must not provide `upcoming_adr`.

### `monthly_trends.csv`

Expected to include monthly trend fields related to:

- Revenue.
- ADR.
- Occupancy.
- Booked occupancy.
- Blocked occupancy.

Monthly Trends is the primary monthly truth source for revenue, ADR, and occupancy.

### `bookings_report.xlsx`

Expected to include stay or reservation rows with:

- Stay, check-in, and check-out dates or equivalent.
- Booking source or channel.
- Revenue or booking value if available.
- Length of stay or enough dates to derive length of stay.
- Booking window when available.

Bookings Report supports cleanings/stays, LOS, source mix, and booking-window analysis.

### `pricelabs_settings_snapshot_from_ui.json`

Expected to include:

- run date and listing metadata
- captured timestamp
- PriceLabs UI source metadata
- visible settings labels and values
- optional detail text for settings where the UI exposes hover/popover detail

The settings snapshot is normalized into structured business fields before comparison. Metadata and raw UI audit fields are excluded from `settings_changes`.

## Safe Promotion Rules

Promotion from staging to raw should be conservative:

- Do not overwrite existing raw files by default.
- If a raw file already exists, the downloader should stop or require explicit force/replace mode.
- A future optional mode may archive existing raw files before replacement, but not in the first implementation.
- Promotion should be all-or-nothing where practical.
- Failed validation leaves files in staging and leaves `raw/` unchanged.
- Manual raw files remain valid trusted inputs.

Avoid overwriting trusted raw files. If replacement is needed, it should be explicit and auditable.

## Failure Handling

Expected failure cases:

- Login failure.
- MFA required.
- Session expired.
- Download button or page layout changed.
- Partial download.
- Wrong file downloaded.
- File validation failure.
- Network or browser timeout.
- PriceLabs unavailable.

Expected behavior:

- Fail clearly.
- Write a useful high-level log.
- Preserve current raw files.
- Do not silently continue with bad inputs.
- Do not create misleading reports from invalid or missing files.

## Login Options

Manual login remains valid and is the safest fallback.

Optional local credential fallback uses:

```text
.local/pricelabs.env
```

Format:

```text
PRICELABS_EMAIL=your_pricelabs_email
PRICELABS_PASSWORD=your_pricelabs_password
```

This file must stay local and gitignored. Do not commit it, paste it into chat, or include real values in docs or logs. Avoid `git add .`; use explicit `git add <path>` commands.

With `-UseLocalCredentials`, the downloader can fill the PriceLabs login form. MFA may still require manual completion in the opened browser.

Persistent browser session support exists, but testing showed PriceLabs may still return to the login page. The local credential fallback is the preferred optional convenience path; manual login remains available.

## Manual Fallback

Manual download remains valid.

The user can still place files directly in:

```text
data/runs/<run_date>/raw/
```

The existing raw-file pipeline continues to work without Playwright if trusted raw files are placed manually. The one-session wrapper is the current standard manual weekly workflow, but scheduler use is not recommended until separately validated.

## Logging

Future download log location:

```text
data/runs/<run_date>/logs/pricelabs_download_<run_date>.log
```

The log should include:

- `run_date`.
- Attempted files.
- Staging paths.
- Promoted raw paths.
- Validation result per file.
- High-level failure reason.

The log must not include:

- Passwords.
- Session cookies.
- Auth tokens.
- MFA codes.
- Full sensitive browser state.

## Secrets And Authentication

Secrets must stay outside Git, docs, logs, and chat.

Rules:

- No credentials in Git.
- No credentials in TOML.
- No real credentials in docs.
- No credentials in logs.
- `.local/pricelabs.env` may contain local-only PriceLabs credentials and must remain gitignored.
- Saved browser state, if used, must remain gitignored.
- MFA may require headed/manual completion.

The Gmail app password is unrelated to PriceLabs download automation and must remain environment-only. PriceLabs credentials, session details, cookies, and browser state must also remain outside Git/docs/logs/chat.

## Scheduler Integration Design

Scheduler integration is future work only.

The scheduler wrapper may eventually call the downloader before the pipeline. The downloader must fail safely.

If the downloader fails, the future scheduler behavior should be one of:

- Stop before analysis.
- Optionally run only if trusted raw files already exist and the user explicitly allows fallback.

Current scheduler behavior should not change in Step 27.

## Business Guardrails

- Do not blindly follow market 75th percentile.
- Market percentile is context only.
- Monthly Trends is primary monthly truth for revenue, ADR, and occupancy.
- Bookings Report supports cleanings/stays, LOS, source mix, and booking-window analysis.
- Future export supports future calendar, open ask, availability, min stay, and future booked proxy fallback.
- `price_occ.csv` is market context only.
- Raw files are trusted inputs.
- Generated outputs can be regenerated.

## Proposed Future Steps

Step 28 - Playwright downloader skeleton.

Step 29 - Download one PriceLabs file safely.

Step 29c update: the future export download should use the PriceLabs UI flow, not a direct download URL. The expected path is:

1. Open `https://app.pricelabs.co/customization`.
2. Use local-only credential fallback if explicitly enabled, otherwise let the user complete headed/manual login or MFA if needed.
3. Find the Lodgify account row or card.
4. Open its three-dot menu.
5. Click `Download CSV Prices`.
6. Capture the browser download into staging as `priceLabs_future_export.csv`.
7. Validate the staged CSV.

Do not depend on a direct `PRICELABS_FUTURE_EXPORT_URL` for the normal workflow.

Step 30 - Add all required downloads.

Step 31 - Add staging validation and promote-to-raw.

Step 32 - Add bookings report download target.

Step 33 - Add PriceLabs UI settings snapshot target.

Step 34 - Promote validated staged files to raw.

Step 35 - Use UI settings snapshot as primary settings input.

Step 36 - Add one-command and one-session weekly workflow.

Step 37 - Add Reason Review.

Future - Optional scheduler integration only after separate validation.

## Acceptance Criteria

This design step is complete when:

- `docs/pricelabs-playwright-download-design-v1.md` exists.
- The document clearly recommends staging-first download.
- The document identifies the five staged PriceLabs inputs.
- The document keeps `pricelabs_settings_manual_input.json` as deprecated/manual fallback.
- The document explains validation before promotion.
- The document explains no-overwrite raw safety.
- The document explains login, MFA, and download failure handling.
- The document preserves manual fallback.
- The document explains secrets handling.
- No code files are changed.
- No tests are required unless documentation linting exists.
