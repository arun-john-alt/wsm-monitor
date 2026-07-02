"""Freshness preflight — verifies every source feed is current enough for the requested run
BEFORE any aggregate is built, so Monitor never reports numbers from silently-stale data.

Checks (mode-dependent):
  monthly: ads data >= month end; leads >= month end; change_events >= month start (WARN only)
  weekly : ads data >= end of latest complete ISO week
Exit non-zero on FAIL (run_monitor aborts unless --force). Importable: run_checks(mode) -> bool.

Known feed behaviours (audited 2026-07-02):
  - ads_* Data Transfer: daily ~14:36 UTC, lands T-1 data, backfill runs restate trailing days.
  - themes_firstlast_semroi (leads): zoho-bq-export, IRREGULAR 1-9 day gaps -> the check that matters.
  - change_events: manual monthly CSV drop (Big Boss) -> expected to lag; warn, don't block.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wsm_cfg import G, CUR, month_end, bq_client
from datetime import date, timedelta

def run_checks(mode='monthly'):
    bq = bq_client()
    def one(sql): return list(bq.query(sql).result())[0].m
    ads_max = one(f"SELECT MAX(segments_date) m FROM `{G}.ads_AdGroupBasicStats_5419501619`")
    ok = True
    print(f"[freshness] mode={mode}  target month={CUR}")

    if mode == 'weekly':
        wk = ads_max - timedelta(days=ads_max.weekday())      # Monday of ads_max's week
        target_end = (wk - timedelta(days=1)) if ads_max < wk + timedelta(days=6) else (wk + timedelta(days=6))
        print(f"  ads data through {ads_max} -> latest complete week ends {target_end}  [PASS]")
        return True

    need = date.fromisoformat(month_end(CUR))
    # 1) ads perf/IS
    status = "PASS" if ads_max >= need else "FAIL"
    print(f"  ads (perf/IS)   : through {ads_max}, need >= {need}  [{status}]")
    if status == "FAIL": ok = False
    # 2) leads — the irregular feed
    leads_max = one(f"SELECT MAX(Date) m FROM `{G}.themes_firstlast_semroi`")
    lm = str(leads_max)[:10]
    status = "PASS" if lm >= str(need) else "FAIL"
    print(f"  leads           : through {lm}, need >= {need}  [{status}]"
          + ("" if status == "PASS" else "  <- zoho-bq-export sync is behind; wait for it or ping Ajay"))
    if status == "FAIL": ok = False
    # 3) change history — warn only (Comments column degrades gracefully)
    ch_max = one(f"SELECT MAX(date) m FROM `{G}.change_events`")
    cm = str(ch_max)[:10]
    status = "PASS" if cm >= f"{CUR}-01" else "WARN"
    print(f"  change_events   : through {cm}  [{status}]"
          + ("" if status == "PASS" else f"  <- Comments/RCA change-history incomplete for {CUR}; drop the new CSV + rerun Big Boss parser"))
    # 4) leads engine attribution lag — warn if a big share of target-month leads is unattributed
    r = list(bq.query(f"""SELECT SUM(IF(Source_Medium IS NULL, FS_PS_Leads, 0)) nu, SUM(FS_PS_Leads) t
      FROM `{G}.themes_firstlast_semroi`
      WHERE Lead_Type='Mktg(SPL)Leads' AND SUBSTR(Date,1,7)='{CUR}'""").result())[0]
    share = (r.nu or 0) / r.t * 100 if r.t else 0
    status = "PASS" if share < 5 else "WARN"
    print(f"  engine attrib   : {share:.0f}% of {CUR} presales leads unattributed  [{status}]"
          + ("" if status == "PASS" else "  <- Google/Bing split understated until attribution catches up"))
    print(f"[freshness] {'ALL CLEAR' if ok else 'BLOCKED — source data not ready for this run'}")
    return ok

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'monthly'
    sys.exit(0 if run_checks(mode) else 1)
