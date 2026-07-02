# WSM Monitor — Setup Guide for Ajay

Everything you need to replicate Arun's machine on yours — full monthly reports,
weekly alerts, email send, and the local dashboard. No secrets in the repo.

---

## Prerequisites (one-time)

| What | Where to get it |
|---|---|
| Python 3.9+ | `python3 --version` — comes with macOS or install via Homebrew |
| Google Cloud SDK (`gcloud`) | https://cloud.google.com/sdk/docs/install |
| Access to BigQuery project `it-security-online-marketing` | Arun can add you; you already have it |

---

## Step 1 — Clone the repo

```bash
git clone https://github.com/arun-john-alt/wsm-monitor.git
cd wsm-monitor
```

> **Note:** The repo is private. You need to be added as a collaborator first (ask Arun).
> Alternatively, Arun can add you and you generate an SSH key or use a GitHub PAT.

---

## Step 2 — Install Python dependencies

```bash
pip3 install -r requirements.txt
```

If you're on a shared machine or want isolation:
```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Step 3 — Authenticate to BigQuery (gcloud ADC)

```bash
gcloud auth application-default login
# opens a browser — log in with your @zohocorp.com account that has BQ access

gcloud auth application-default set-quota-project it-security-online-marketing
```

Verify it works:
```bash
python3 wsm_cfg.py
# Should print: month=2026-05 (May 2026)  prior=2026-04  ...  write=it-security-online-marketing.Ads_data_WSM
# If you see a credentials error, re-run the gcloud auth steps above.
```

---

## Step 4 — Place the workbook and set your paths

**Get the source workbook** — "Continuous Monitoring AKA Big Boss.xlsx" — from your shared drive
or copy it from Arun's machine. Put it somewhere convenient, e.g. `~/wsm-data/`.

```bash
mkdir -p ~/wsm-data
# Copy the workbook there — name must match exactly:
# ~/wsm-data/Continuous Monitoring AKA Big Boss.xlsx
```

**Edit `config.yaml`** — only the `paths:` section needs changing:

```yaml
paths:
  workbook_src: "~/wsm-data/Continuous Monitoring AKA Big Boss.xlsx"   # ← your local copy
  workbook_out: "~/wsm-data/Continuous Monitoring AKA Big Boss - Monitor.xlsx"
  rca_dir:     "~/wsm-data/RCA"
  weekly_dir:  "~/wsm-data/Weekly"
```

The output dirs (`RCA/`, `Weekly/`) are created automatically on first run — no action needed.

**Verify paths resolved correctly:**
```bash
python3 wsm_cfg.py
# Last line should show the full expanded path to your workbook_out
```

---

## Step 5 — Set SMTP credentials (for email send)

Copy the template:
```bash
cp set_env.example.sh set_env.sh
```

Edit `set_env.sh` and fill in the Zoho Mail credentials (the same ones used in the
`theme-report` Cloud Run job, or a new app-password if you prefer):

```bash
export WSM_SMTP_USER="ajay@zohocorp.com"     # the account that can send-as the alias
export WSM_SMTP_PASS="xxxx-xxxx-xxxx-xxxx"   # Zoho Mail app-password
```

Then load them before running the email send:
```bash
source set_env.sh
```

> `set_env.sh` is in `.gitignore` — it will never be committed. Keep it on your machine only.

**How to create a Zoho Mail app-password:**
1. Log into mail.zoho.in with your account
2. Settings → Security → App Passwords → Generate
3. Copy the generated password into `set_env.sh`

**Send-as check:** The login in `WSM_SMTP_USER` must have "Send Mail As" rights for
`wsm-online-mktg@zohocorp.com`. If the email shows your address instead of the alias,
go to Zoho Mail Settings → Send Mail As → Add address, and verify it.

---

## Step 6 — Verify end-to-end (dry run)

```bash
# 1. Check data freshness
python3 check_freshness.py monthly

# 2. Run the monthly pipeline (rebuilds BQ aggregates + all Excel tabs)
python3 run_monitor.py

# 3. Generate the email HTML body
python3 build_email.py

# 4. Preview what would be sent (no actual email)
source set_env.sh
python3 send_email.py --dry-run

# 5. Send for real
python3 send_email.py
```

---

## Step 7 — Use the dashboard (recommended)

The dashboard lets you verify data freshness before triggering runs — no command line needed:

```bash
python3 ui.py
# Open http://localhost:8787 in your browser
```

**Dashboard buttons:**
- **Check freshness** — confirms ads & leads data covers the target month before you run
- **Run Weekly Alerts** — generates `~/wsm-data/Weekly/weekly_alerts_<week>.txt`
- **Run Monthly Report** — rebuilds all BigQuery aggregates + all Excel tabs
- **Month override field** — type `2026-05` to target a specific month (overrides `config.yaml`)
- **Force toggle** — bypasses freshness FAIL (use when you've manually verified data)

After "Run Monthly Report" finishes:
1. Open `~/wsm-data/Continuous Monitoring AKA Big Boss - Monitor.xlsx`
2. Run `build_email.py` to regenerate the email body with that month's data
3. Run `send_email.py` (or add a "Send Email" button — see below)

---

## What each script does

| Script | What it does |
|---|---|
| `run_monitor.py` | Main orchestrator. Runs freshness check, fires SQL queries, then all 5 tab builders in order. |
| `check_freshness.py` | Preflight: ads data covers month-end? leads data fresh? Returns exit 0=OK / 1=FAIL. |
| `build_monitor_cells.py` | **Runs first** — copies source workbook → output, writes column O signal cells. |
| `build_leads_trend_tab.py` | "Leads Trend (YoY)" tab — 3 rows/theme (Google/Bing/All) × 18 months. |
| `build_funnel_tab.py` | "Funnel (L·C·Spend·CPL)" tab — Google-only end-to-end funnel. |
| `build_leads_issues_tab.py` | "Leads Issues (by DRI)" tab — declining themes, grouped by DRI. |
| `build_matrix_tab.py` | Two "Country × Product" heatmap tabs (YTD + single-month). |
| `build_email.py` | Renders email-safe HTML body + saves JSON sidecar (subject/to/path). |
| `send_email.py` | SMTP send via smtp.zoho.in:465. Reads creds from env vars only. |
| `detect_weekly_alerts.py` | Weekly anomaly detector — writes digest + updates `wsm_alerts` BQ table. |
| `rca_pack.py` | Pulls RCA data for one country×product unit from BQ → JSON. |
| `rca_pdf.py` | Renders a one-page RCA PDF from the JSON. |
| `ui.py` | Local dashboard at localhost:8787. |
| `wsm_cfg.py` | Config loader — every script imports constants from here. Run directly to verify setup. |

---

## Changing the target month

Three ways, in priority order:
1. **Dashboard**: type the month in the "Target month" field before clicking Run.
2. **Env var**: `WSM_MONTH=2026-06 python3 run_monitor.py` — overrides config without editing.
3. **config.yaml**: change `run.month: "2026-06"` — the default.

---

## Repo layout

```
config.yaml              # ALL knobs. Edit this — not the code.
wsm_cfg.py               # config loader + month math + BQ client
run_monitor.py           # orchestrator
check_freshness.py       # preflight data quality check
build_monitor_cells.py   # tab builder 1 (must run FIRST — resets workbook)
build_leads_trend_tab.py # tab builder 2
build_funnel_tab.py      # tab builder 3
build_leads_issues_tab.py# tab builder 4
build_matrix_tab.py      # tab builder 5
build_email.py           # email HTML generator
send_email.py            # SMTP sender
detect_weekly_alerts.py  # weekly anomaly detector
rca_pack.py              # RCA data assembler
rca_pdf.py               # RCA PDF renderer
ui.py                    # local dashboard (localhost:8787)
requirements.txt         # pip dependencies
set_env.example.sh       # env var template — copy to set_env.sh and fill in
sql/
  monitor_monthly_raw.sql   # perf + IS from raw daily tables
  monitor_leads_monthly.sql # leads (presales/sales + engine split)
  monitor_weekly_raw.sql    # weekly ISO-week aggregate
legacy/                  # superseded scripts — reference only, do not run
```

---

## Troubleshooting

**`google.auth.exceptions.DefaultCredentialsError`**
→ Run `gcloud auth application-default login` and `set-quota-project` again.

**`File not found: .../Continuous Monitoring AKA Big Boss.xlsx`**
→ The source workbook is missing or path in config.yaml is wrong. Check `python3 wsm_cfg.py` output.

**`openpyxl` warnings about rich text**
→ Safe to ignore if output is correct. All `load_workbook()` calls already use `rich_text=True`.

**Email: `SMTPAuthenticationError`**
→ The app-password in `set_env.sh` is wrong or expired. Generate a new one in Zoho Mail Settings.

**Email: From shows your address instead of the alias**
→ Your login doesn't have send-as rights for `wsm-online-mktg@zohocorp.com`. Add it in Zoho Mail.

**`BigQuery: Table ... not found`**
→ The BQ aggregate tables in `Ads_data_WSM` haven't been built yet. Run `python3 run_monitor.py` first
(this creates them). If it's `Google_ads_data_ajay` tables missing, ping Ajay — Data Transfer may
have lagged.

**Green triangle warnings in Excel ("number stored as text")**
→ Already fixed in the codebase. If you see them, ensure you have the latest code (`git pull`).

---

## What to ask Arun / what's still pending

- **SMTP creds** — WSM_SMTP_USER + WSM_SMTP_PASS: either reuse from the `theme-report` Cloud Run
  job, or you mint a new Zoho Mail app-password on the account with send-as rights.
- **Zoho Sheet write** (col O + tabs) — needs the Big Boss OAuth token (`ZOHO_CLIENT_ID`,
  `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN`). Corporate policy blocked self-service OAuth apps.
  This is Phase 3 / pending.
- **GitHub collaborator access** — ask Arun to add `your-github-username` to
  `github.com/arun-john-alt/wsm-monitor` (Settings → Collaborators).
