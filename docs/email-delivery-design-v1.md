# Email Delivery Design V1

## Purpose

The pipeline already generates the email-ready revenue report:

```text
data/runs/<run_date>/analysis/email_revenue_report_<run_date>.md
```

The pipeline now creates a local `.eml` draft file, a readable HTML report, and can optionally send through Gmail SMTP only when explicitly enabled in local config.

## Recommended Delivery Mode

Use draft mode for development.

Draft mode is the safest default because it:

- Allows human review before sending.
- Protects against bad automated wording.
- Avoids accidental delivery while the report is still being refined.
- Keeps local report and `.eml` generation available even when SMTP is not configured.

## Email Source

Source file:

```text
data/runs/<run_date>/analysis/email_revenue_report_<run_date>.md
```

Subject source:

- First line beginning with `Subject:`

Example:

```text
Subject: Aloha Poconos Weekly Revenue Snapshot — 2026-05-08
```

Body source:

- Remaining markdown content after the subject line.

## Draft Output Behavior

Current draft behavior:

1. Read `email_revenue_report_<run_date>.md`.
2. Extract the subject.
3. Use the remaining markdown body as plain text.
4. Write `email_revenue_report_<run_date>.eml`.
5. Write `email_revenue_report_<run_date>.html`.
6. Keep the `.eml` file as a local reviewable copy even when SMTP send mode is enabled.

## Configuration

Config should include:

- `recipient_email`
- Sender account handled by Gmail authentication
- Optional `cc_email`
- `mode = "draft"` for development

Config files:

- `config/email.example.toml` is committed as a safe template.
- `config/email.toml` is local-only and ignored by Git.

`config/email.example.toml` should define:

- `[email] mode = "draft"`
- `[email] recipient_email`
- `[email] cc_email`
- `[email] subject_prefix`
- `[email] include_attachments = false`
- `[smtp] enabled = false`
- `[smtp] host = "smtp.gmail.com"`
- `[smtp] port = 587`
- `[smtp] sender_email`
- `[smtp] password_env_var = "ALOHA_GMAIL_APP_PASSWORD"`
- `[smtp] use_tls = true`
- `[report] source = "email_revenue_report"`
- `[report] format = "markdown"` or `"html"`

Do not store secrets in either file. Gmail OAuth/token files must stay outside the repo or be ignored later if introduced.

## SMTP Send Mode

The pipeline always generates:

```text
data/runs/<run_date>/analysis/email_revenue_report_<run_date>.md
data/runs/<run_date>/analysis/email_revenue_report_<run_date>.eml
data/runs/<run_date>/analysis/email_revenue_report_<run_date>.html
```

SMTP send mode is optional and explicit. Default development mode should be:

```toml
[email]
mode = "draft"

[smtp]
enabled = false
```

Real send requires both:

```toml
[email]
mode = "send"

[smtp]
enabled = true
```

The Gmail App Password must be loaded from the environment variable named by `password_env_var`, currently:

```text
ALOHA_GMAIL_APP_PASSWORD
```

No password should be committed to Git or stored in `config/email.toml`. A persistent Windows user environment variable can be used for scheduled automation later.

If send mode is enabled and the password environment variable is missing, the pipeline fails clearly at `Email send mode`. For development, switch back to draft mode to avoid sending test emails. Draft/file generation remains the safe fallback.

## HTML Email Formatting

The HTML report is generated from:

```text
data/runs/<run_date>/analysis/email_revenue_report_<run_date>.md
```

Output:

```text
data/runs/<run_date>/analysis/email_revenue_report_<run_date>.html
```

Purpose: readable HTML version of the weekly revenue email report for Gmail/SMTP delivery.

Rules:

- Markdown report is still generated.
- Plain-text `.eml` draft is still generated.
- HTML report is generated for readable email delivery.
- HTML uses simple inline/internal styling.
- No external CSS.
- No images.
- No scripts.

SMTP body selection:

- If `[report].format = "html"`, SMTP sends the HTML report with a plain-text fallback.
- If `[report].format = "markdown"`, SMTP sends the markdown report as plain text.
- Draft mode still skips sending.
- Send mode still requires `[email].mode = "send"`, `[smtp].enabled = true`, and `ALOHA_GMAIL_APP_PASSWORD` available in the environment.

## Credential Guardrails

- No credentials committed to Git.
- Use local environment variables or OAuth token storage outside the repo.
- Update `.gitignore` if token/cache files are introduced.
- Do not log tokens.
- Do not print email credentials.

## V1 Scope

Included:

- Create local `.eml` draft file.
- Create readable HTML email report.
- Optional explicit Gmail SMTP send mode.
- Subject extraction.
- Markdown/plain text body.
- Local manual review before send.

Excluded:

- Scheduling.
- Attachments.
- Gmail API/OAuth integration.

## Future Steps

Step 18:

- Create email config template.

Step 19:

- Implement local `.eml` draft creation.

Step 20:

- Add optional scheduler after send mode is trusted.

Step 21:

- Implement explicit Gmail SMTP send mode.

Later:

- Add scheduled automation.
- Automate PriceLabs downloads.

## Guardrails

- Draft mode is the development default.
- No automatic email sending unless `[email].mode = "send"` and `[smtp].enabled = true`.
- Email content comes from generated report, not ad hoc text.
- Do not include raw CSV attachments in V1.
- Do not mix Airbnb revenue into email unless already present in the report.
- Keep report focused on revenue pace, cleaning efficiency, and PriceLabs rule-review areas.
