# WSM Monitor — Claude context

**Owner:** arun.john@zohocorp.com  
**Repo:** github.com/arun-john-alt/wsm-monitor  
**Local data:** `~/wsm-data/` (workbook, RCA PDFs, weekly digests, email HTML)

---

## What this is

Paid-search SEM intelligence pipeline for ManageEngine's Google Ads account (ID `5419501619`).  
Sibling to "Big Boss" (keyword-rec + change-history columns). Monitor adds a third column and separate tabs:
- **Column O "Paid-Search Monitor"** — MoM signals (leads, CPL, IS, CTR, clicks) per P×C×T cell
- **Leads Trend (YoY)** tab — 18-month leads history, Google/Bing/All rows
- **Funnel (L·C·Spend·CPL)** tab — 4-metric × 18-month view
- **Leads Issues (by DRI)** tab — issue-flagged themes grouped by country DRI
- **Leads May 2026** and **Leads YTD** tabs — Country×Product matrices (single-month + YTD)
- **Monthly email** — consolidated HTML to `wsm-online-mktg@zohocorp.com`
- **Weekly alerts** — Country×Product anomalies + theme-grain spend/clicks alerts

---

## Data sources reference

Full BQ table inventory, column semantics, ROI logic, and blocked items: **[docs/data_sources.md](docs/data_sources.md)**

---

## BigQuery layout

| Dataset | Access | Purpose |
|---|---|---|
| `it-security-online-marketing.Google_ads_data_ajay` | READ-ONLY | Source: raw `ads_*` tables + `themes_firstlast_semroi` (leads) |
| `it-security-online-marketing.Ads_data_WSM` | WRITE | Monitor's own output tables |

Key source tables:
- `ads_AdGroupBasicStats_5419501619` — daily perf (SEARCH only via `network_type`)
- `ads_AdGroupCrossDeviceStats_5419501619` — daily IS metrics (impression-weighted when rolling up)
- `themes_firstlast_semroi` — leads fact table (`Date` is STRING, `Lead_Type`, `FS_PS_Leads`, etc.)
- `change_events` — manual monthly CSV drop, used in RCA only

IS is **non-additive** — always roll up as `SUM(sis*impr)/SUM(impr)`.

---

## Leads metric — critical detail

Leads are **country-dependent** (defined in `wsm_cfg.py` `PRESALES_COUNTRIES`):
- US / India / UK / Canada / Australia → **PreSales** (`FS_PS_Leads`, `Lead_Type='Mktg(SPL)Leads'`)
- All other countries → **Sales** (`Valid_Sales_Leads_First_Source`, `Lead_Type='All Leads'` — one partition only, value repeats across 3 types)

GAds conversions (`ads_KeywordConversionStats`) ≠ leads and are noisy — **do not use as primary outcome**.

---

## Config — single source of truth

All constants in `config.yaml` (no secrets) and derived in `wsm_cfg.py`:

```yaml
bigquery:
  project: it-security-online-marketing
  dataset: Ads_data_WSM
  source_dataset: Google_ads_data_ajay
  account_id: "5419501619"
run:
  month: "2026-06"   # <-- UPDATE THIS each month before running
paths:
  workbook_src: "~/wsm-data/Continuous Monitoring AKA Big Boss.xlsx"
  workbook_out: "~/wsm-data/Continuous Monitoring AKA Big Boss - Monitor.xlsx"
  rca_dir:     "~/wsm-data/RCA"
  weekly_dir:  "~/wsm-data/Weekly"
```

Key derived constants (from `wsm_cfg.py`):
- `CUR` — target month (YYYY-MM)
- `PRI` — prior month
- `YOY` — same month prior year
- `BASE` — trailing 3-month list used for issue detection avg
- `DEADBAND` = 10 — YoY % inside which no color is applied (avoids noise)
- `DECLINE` = 25, `BASE_FLOOR` = 3, `ABS_FLOOR` = 2 — issue detection thresholds
- `W` / `G` — write / source dataset full refs
- `ACCT` — account ID string (used as `__ACCT__` placeholder in SQL)

---

## Run order (monthly)

```
python3 wsm_cfg.py               # verify paths
python3 check_freshness.py       # must pass before anything else
python3 run_monitor.py           # SQL + all 5 tab builders (~70s)
python3 build_email.py           # HTML email body
python3 send_email.py --dry-run  # preview
python3 send_email.py            # send to wsm-online-mktg@zohocorp.com
```

Or via dashboard: `python3 ui.py` → http://localhost:8787

`build_monitor_cells.py` runs FIRST inside `run_monitor.py` — it resets the output workbook via `shutil.copyfile`. Other tab builders depend on the tab it creates.

SQL placeholders substituted in `run_sql()`: `__W__`, `__G__`, `__PRESALES__`, `__ACCT__`.

---

## openpyxl rule

**Every** `load_workbook()` call must use `rich_text=True` — omitting it silently flattens existing styled cells on save.

---

## Email & SMTP

`send_email.py` reads env vars: `WSM_SMTP_USER`, `WSM_SMTP_PASS`, `WSM_SMTP_HOST` (default `smtp.zoho.in`), `WSM_SMTP_PORT` (default `465`), `WSM_MAIL_FROM`.  
Credentials are in `set_env.sh` (gitignored — copy from `set_env.example.sh`).

---

## DRI roster

| DRI | Countries |
|---|---|
| Aashiq | US |
| Ajay | India, UK, Canada, Australia |
| Indhu | MEA, APAC |
| Elanthendral | South Africa, Brazil, LATAM, Mexico, Spain, Israel |
| Kowsik | Italy, Saudi Arabia, UAE, France, Turkey |
| Sathish | Europe, Poland |
| Jude | Germany, Netherlands, Switzerland, Belgium |
| Suganesh | Singapore |

---

## Weekly alerts

`python3 run_monitor.py --mode weekly` → `detect_weekly_alerts.py`  
Latest complete ISO week vs trailing 4-week avg. State in `Ads_data_WSM.wsm_alerts` (idempotent same-week re-runs).  
Digests saved to `~/wsm-data/Weekly/weekly_alerts_<wk>.txt`.

---

## RCA

`python3 rca_pack.py --country "United States" --product ADAP` → JSON brief  
`python3 rca_pdf.py` → one-page PDF in `~/wsm-data/RCA/`  
SV (adg_keyword_universe) is excluded — table grows monthly, produces artifacts.

---

## Auth

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project it-security-online-marketing
```

ADC at `~/.config/gcloud/application_default_credentials.json`.  
`WSM_MONTH` env var overrides target month at runtime (alternative to editing config.yaml).
