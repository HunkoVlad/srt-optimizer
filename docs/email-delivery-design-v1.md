# Email Delivery Design V1

## Purpose

The pipeline already generates the email-ready revenue report:

```text
data/runs/<run_date>/analysis/email_revenue_report_<run_date>.md
```

The next delivery phase should create a reviewable Gmail draft first. It should not send automatically.

## Recommended Delivery Mode

Use Gmail draft mode first.

Draft mode is the safest transition step because it:

- Allows human review before sending.
- Protects against bad automated wording.
- Avoids accidental delivery while the report is still being refined.
- Creates a clear path toward later automation without jumping directly to sending.

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

Future implementation should:

1. Read `email_revenue_report_<run_date>.md`.
2. Extract the subject.
3. Convert the markdown body to either plain text first, or simple HTML later.
4. Create a Gmail draft addressed to the configured recipient.
5. Never send automatically in V1.
6. Print the Gmail draft creation status.

## Configuration

Future config should include:

- `recipient_email`
- Sender account handled by Gmail authentication
- Optional `cc_email`
- Optional `email_mode = draft`

Do not store secrets in the repo.

## Credential Guardrails

- No credentials committed to Git.
- Use local environment variables or OAuth token storage outside the repo.
- Update `.gitignore` if token/cache files are introduced.
- Do not log tokens.
- Do not print email credentials.

## V1 Scope

Included:

- Create Gmail draft.
- Subject extraction.
- Markdown/plain text body.
- Local manual review before send.

Excluded:

- Automatic send.
- Scheduling.
- HTML styling.
- Attachments.
- Gmail API setup details beyond design.

## Future Steps

Step 18:

- Create email config template.

Step 19:

- Implement local Gmail draft creation.

Step 20:

- Add optional scheduler after draft mode is trusted.

Step 21:

- Automate PriceLabs downloads.

## Guardrails

- Draft mode only until explicitly changed.
- No automatic email sending.
- Email content comes from generated report, not ad hoc text.
- Do not include raw CSV attachments in V1.
- Do not mix Airbnb revenue into email unless already present in the report.
- Keep report focused on revenue pace, cleaning efficiency, and PriceLabs rule-review areas.
