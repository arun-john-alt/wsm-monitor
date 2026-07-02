#!/usr/bin/env bash
# WSM Monitor — environment variable template
# Copy to set_env.sh, fill in values, then: source set_env.sh
# Never commit set_env.sh (it's in .gitignore).

# ── SMTP (Phase 3b: monthly email send) ─────────────────────────────────────
# Get these from Ajay's theme-report Cloud Run job, or mint a new Zoho app-password.
# The login must have "send as" rights on wsm-online-mktg@zohocorp.com.
export WSM_SMTP_USER=""          # e.g. ajay@zohocorp.com
export WSM_SMTP_PASS=""          # Zoho Mail app-password (not login password)
export WSM_SMTP_HOST="smtp.zoho.in"   # default — usually unchanged
export WSM_SMTP_PORT="465"            # default — usually unchanged
# Optional: override the From address (defaults to the alias in config.yaml)
# export WSM_MAIL_FROM="wsm-online-mktg@zohocorp.com"

# ── Month override (optional) ────────────────────────────────────────────────
# Override config.yaml run.month without editing the file.
# Used automatically by ui.py when you enter a month in the dashboard.
# export WSM_MONTH="2026-06"
