# WSM Monitor — Setup Guide

Everything you need to get monthly reports, weekly alerts, email send, and the local
dashboard running on a new machine. No secrets in the repo.

---

## Prerequisites (one-time)

| What | Where to get it |
|---|---|
| Python 3.9+ | `python3 --version` — comes with macOS; install via Homebrew if missing |
| Google Cloud SDK (`gcloud`) | https://cloud.google.com/sdk/docs/install |
| Access to BigQuery project `it-security-online-marketing` | You already have it |

---

## Step 1 — Clone the repo

The repo is **public** — no account or token needed:

```bash
git clone https://github.com/arun-john-alt/wsm-monitor.git
cd wsm-monitor
```

---

## Step 2 — Install Python dependencies

```bash
pip3 install -r requirements.txt
```

Isolated environment (optional but recommended):
```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Step 3 — Authenticate to BigQuery

```bash
gcloud auth application-default login
# opens a browser — sign in with your @zohocorp.com account

gcloud auth application-default set-quota-project it-security-online-marketing
```

Verify:
```bash
python3 wsm_cfg.py
# Prints month / path info with no errors. If you see a credentials error, repeat the two gcloud commands above.
```

---

## Step 4 — Set the target month + place the workbook

**4a. Set the target month** — open `config.yaml` and change `run.month` to the month
you're reporting on (`YYYY-MM`). Use `"auto"` if you always want last complete calendar month:

```yaml
run:
  month: "2026-06"   # ← change this to the current reporting month
```

**4b. Place the source workbook** — copy "Continuous Monitoring AKA Big Boss.xlsx" to a
local folder (e.g. `~/wsm-data/`). The filename must match **exactly**:

```
~/wsm-data/Continuous Monitoring AKA Big Boss.xlsx
```

**4c. Update paths in `config.yaml`** — edit only the `paths:` block:

```yaml
paths:
  workbook_src: "~/wsm-data/Continuous Monitoring AKA Big Boss.xlsx"
  workbook_out: "~/wsm-data/Continuous Monitoring AKA Big Boss - Monitor.xlsx"
  rca_dir:     "~/wsm-data/RCA"
  weekly_dir:  "~/wsm-data/Weekly"
```

The `~` expands to your home directory on both macOS and Windows.
Output dirs (`RCA/`, `Weekly/`) are created automatically — no action needed.

**Verify everything:**
```bash
python3 wsm_cfg.py
# Prints the configured month and the resolved (expanded) workbook paths — check them.
```

---

## Step 5 — Set SMTP credentials (for email send)

**macOS / Linux:**
```bash
cp set_env.example.sh set_env.sh
# Edit set_env.sh and fill in:
#   export WSM_SMTP_USER="ajay@zohocorp.com"
#   export WSM_SMTP_PASS="xxxx-xxxx-xxxx-xxxx"   # Zoho Mail app-password
source set_env.sh   # load into the current shell before sending
```

**Windows (PowerShell):**
```powershell
$env:WSM_SMTP_USER = "ajay@zohocorp.com"
$env:WSM_SMTP_PASS = "xxxx-xxxx-xxxx-xxxx"
```

`set_env.sh` is in `.gitignore` and will never be committed. Keep it on your machine only.

**How to create a Zoho Mail app-password:**
1. Sign in to mail.zoho.in
2. Settings → Security → App Passwords → Generate
3. Copy the password into `set_env.sh` (or PowerShell env)

**Send-as:** The account in `WSM_SMTP_USER` must have "Send Mail As" rights for
`wsm-online-mktg@zohocorp.com`. If mail shows your address as From, go to:
Zoho Mail Settings → Send Mail As → Add address → verify.

---

## Step 6 — Full end-to-end dry run

```bash
# 1. Confirm source data is fresh
python3 check_freshness.py monthly

# 2. Build BQ aggregates + all workbook tabs
python3 run_monitor.py

# 3. Generate the email HTML body
python3 build_email.py

# 4. Preview the email (no send)
source set_env.sh          # Windows: set $env vars in PowerShell first
python3 send_email.py --dry-run

# 5. Send for real
python3 send_email.py
```

---

## Step 7 — Use the dashboard (recommended for day-to-day)

```bash
python3 ui.py
# → http://localhost:8787
```

**Buttons:**
- **Check freshness** — verifies ads & leads data covers the target month before you run
- **Run Weekly Alerts** — generates `~/wsm-data/Weekly/weekly_alerts_<week>.txt`
- **Run Monthly Report** — rebuilds BQ aggregates + all Excel tabs
- **Month override** — type `2026-06` to target a specific month without editing `config.yaml`
- **Force** — bypasses freshness FAIL when you've manually confirmed the data is ready

After "Run Monthly Report" completes:
1. Open `~/wsm-data/Continuous Monitoring AKA Big Boss - Monitor.xlsx`
2. `python3 build_email.py` — generates the HTML email body for that month
3. `python3 send_email.py` — sends to `wsm-online-mktg@zohocorp.com`

---

## What each script does

| Script | Purpose |
|---|---|
| `run_monitor.py` | Orchestrator: freshness check → SQL → all 5 tab builders in order |
| `check_freshness.py` | Preflight: are ads + leads data current? exit 0 = clear, exit 1 = blocked |
| `build_monitor_cells.py` | **Must run first** — copies source workbook → output, writes col O signal cells |
| `build_leads_trend_tab.py` | "Leads Trend (YoY)" — 3 rows/theme (Google/Bing/All) × 18 months |
| `build_funnel_tab.py` | "Funnel (L·C·Spend·CPL)" — Google end-to-end funnel, metric-aware coloring |
| `build_leads_issues_tab.py` | "Leads Issues (by DRI)" — declining themes, DRI → Country → Product |
| `build_matrix_tab.py` | Two Country × Product heatmaps (YTD + single month) |
| `build_email.py` | Renders email-safe HTML + JSON sidecar; run after the monthly pipeline |
| `send_email.py` | SMTP send via smtp.zoho.in:465; reads creds from env vars only |
| `detect_weekly_alerts.py` | Weekly anomaly detector; updates `wsm_alerts` BQ table |
| `rca_pack.py` | RCA data for one country×product → JSON |
| `rca_pdf.py` | One-page RCA PDF from the JSON |
| `ui.py` | Local dashboard at localhost:8787 |
| `wsm_cfg.py` | Config loader — run directly to verify setup |

---

## Changing the target month

Three ways (highest priority first):
1. **Dashboard** — type the month in the "Target month" field before clicking Run
2. **Env var** — `WSM_MONTH=2026-06 python3 run_monitor.py`
3. **config.yaml** — `run.month: "2026-06"` (the standing default)

---

## Repo layout

```
config.yaml              # ALL knobs — edit this, not the code
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
set_env.example.sh       # env var template — copy to set_env.sh, fill in, never commit
sql/
  monitor_monthly_raw.sql   # perf + IS from raw daily tables
  monitor_leads_monthly.sql # leads with presales/sales + engine split
  monitor_weekly_raw.sql    # weekly ISO-week aggregate
legacy/                  # superseded scripts — reference only, do not run
```

---

## Troubleshooting

**`google.auth.exceptions.DefaultCredentialsError`**
→ Run `gcloud auth application-default login` and `set-quota-project` again.

**`[abort] Tab 'Jun 2026' not found in ...xlsx`**
→ The output workbook is stale or missing. Run `python3 build_monitor_cells.py` (or the full `run_monitor.py`) first — it copies the source workbook and creates that tab.

**`[abort] target month 2026-06 not found in Ads_data_WSM.monitor_monthly_raw`**
→ The BQ aggregate hasn't been built for this month yet. Run `python3 run_monitor.py` (not `--skip-sql`).

**`File not found: .../Continuous Monitoring AKA Big Boss.xlsx`**
→ Source workbook missing or path in `config.yaml` is wrong. Check `python3 wsm_cfg.py` output.

**Email: `SMTPAuthenticationError`**
→ App-password wrong or expired. Generate a new one in Zoho Mail Settings → Security → App Passwords.

**Email: From shows your address instead of the alias**
→ Your login lacks send-as rights for `wsm-online-mktg@zohocorp.com`. Add it in Zoho Mail Settings → Send Mail As.

**`BigQuery: Table ... not found` on a source table**
→ If it's in `Google_ads_data_ajay`: Data Transfer may have lagged — check the BQ console.
   If it's in `Ads_data_WSM`: run `python3 run_monitor.py` to build the aggregates first.

---

## What's still pending

- **SMTP creds** — `WSM_SMTP_USER` + `WSM_SMTP_PASS`: use the login from the `theme-report`
  Cloud Run job, or generate a fresh Zoho Mail app-password on an account with send-as rights.
- **Zoho Sheet write** (col O + tabs written back to the live sheet) — needs the Big Boss OAuth
  token (`ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN`). Corporate policy blocked
  self-service OAuth apps; pending.
