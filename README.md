# WSM Monitor

SEM campaign intelligence for ManageEngine paid search — 10+ products × 30 regions.
Monitors leads / spend / clicks / impression-share at **Product × Country × Theme** grain,
surfaces only material movements, and routes monthly lead issues to each country DRI.

Sibling to "Big Boss" (AI keyword recommendations + change history on the same
Continuous Monitoring sheet). **Google Ads is READ-ONLY — this system never mutates campaigns.**

## What a monthly run produces

One workbook (`Continuous Monitoring AKA Big Boss - Monitor.xlsx`) with:

| Tab | Purpose |
|---|---|
| `<Month>` col O "Paid-Search Monitor" | per-theme signal cells (leads-primary, top-3 lines) |
| Leads Trend (YoY) | leads matrix, 3 rows/theme (Google · Bing · All) × 18 months |
| Funnel (L·C·Spend·CPL) | Google-consistent funnel per theme, metric-aware coloring |
| Leads Issues (by DRI) | **the accountability report** — declining themes grouped DRI → country → product, with engine split + auto Comments |
| Country x Product (Leads YTD / month) | portfolio heatmaps, YoY growth, All/Google/Bing sections |

Plus (semi-automated, see `rca_pack.py` / `rca_pdf.py`): one-page RCA PDFs per unit → `RCA/`.

## Run it

```bash
# once: auth (ADC) — sign in with an account that can read the BQ project
gcloud auth application-default login
gcloud auth application-default set-quota-project it-security-online-marketing
pip install -r requirements.txt

# monthly (target month from config.yaml: run.month = "YYYY-MM" or "auto"):
python run_monitor.py            # full: rebuild BQ aggregates + all tabs
python run_monitor.py --skip-sql # tabs only
```

## Configuration — `config.yaml` (edit this, not code)
- `run.month` — target month; `auto` = last complete calendar month
- `presales_countries` — markets measured on PreSales leads (others: Sales leads)
- `dri` — country → DRI routing for the Leads Issues tab
- `issue_thresholds` / `comment_gates` — detection sensitivity
- No secrets live in this repo. BQ auth = gcloud ADC. Zoho/email creds = env vars (later phases).

## Data model (facts that matter)
- **Reads** `Google_ads_data_ajay` (Data Transfer syncs Google Ads daily; `themes_firstlast_semroi`
  = master lead fact table, `Date` is a STRING). **Writes only** to `Ads_data_WSM`.
- **Leads metric is country-dependent**: presales markets → `FS_PS_Leads` (`Mktg(SPL)Leads`);
  rest of world → `Valid_Sales_Leads_First_Source` (`All Leads`, single partition). Both First-Source.
  Engine split via `Source_Medium` (`google / cpc` / `bing / cpc`); current month has attribution lag
  (NULL medium) so All > Google+Bing until month close.
- **Perf/IS** from raw `ads_AdGroupBasicStats` (SEARCH network only) + `ads_AdGroupCrossDeviceStats`
  (IS, impression-weighted) — self-sufficient, no dependency on manually-rebuilt dashboard tables.
- **Impression share is non-additive** → theme rollup is impression-weighted (approximate).
- GAds conversions ≠ leads (noisy tracking; leads are the truth). Keyword-universe SV is NOT a
  demand signal (universe grows monthly; use active-keyword stable-set SV — TODO).
- `auction_insights_weekly` exists but is EMPTY (competitor data needs UI/script export — parked).
  Bing spend/clicks/SV ingestion — parked (Microsoft Advertising API plan documented in chat).

## Roadmap
1. ✅ Phase 1 — this repo: config-driven, one-command monthly run
2. Phase 2 — weekly layer: Country×Product anomalies + theme-wise clicks/spend alerts; `wsm_alerts` state table (dedupe, escalation)
3. Phase 3 — delivery: ONE consolidated monthly email → `wsm-online-mktg@zohocorp.com`; Zoho Sheet tab write (pending OAuth token)
4. Phase 4 — Cloud Run + Scheduler (weekly Mon / monthly ~6th)
5. Phase 5 — RCA batch automation, resolution feedback loop, auction insights + Bing ingestion, CRM close-date revenue

## Repo layout
```
config.yaml          # ALL knobs (no secrets)
wsm_cfg.py           # config loader + month-window math + BQ client
run_monitor.py       # orchestrator
build_*.py           # the five tab builders (run via orchestrator)
rca_pack.py/rca_pdf.py  # RCA data-pack + one-page PDF renderer
sql/                 # BQ aggregate builders (dataset names + presales templated)
legacy/              # superseded scripts kept for reference
```

## Dashboard (on-demand runs)
```bash
python3 ui.py   # -> http://localhost:8787
```
Check data freshness, then click **Run Weekly Alerts** / **Run Monthly Report** — with month
override and a force toggle for when you have verified the data externally. Live run log included.
Built because source syncs have irregular external dependencies (leads feed can gap 1-9 days):
human verifies, human clicks.
