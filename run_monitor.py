"""WSM Monitor — orchestrator. One command per month:
    python run_monitor.py                 # full monthly: rebuild BQ aggregates + all workbook tabs
    python run_monitor.py --skip-sql      # tabs only (aggregates already fresh)
    python run_monitor.py --only tabs/sql # run just one stage
Target month comes from config.yaml (run.month: "YYYY-MM" or "auto").
Order matters: build_monitor_cells RESETS the workbook from the pristine source, so it runs first.
"""
import os, sys, argparse, runpy, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wsm_cfg as cfg

ROOT = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument('--mode', choices=['monthly', 'weekly'], default='monthly')
ap.add_argument('--skip-sql', action='store_true')
ap.add_argument('--only', choices=['sql', 'tabs'], default=None)
ap.add_argument('--force', action='store_true', help='run even if freshness preflight FAILs')
a = ap.parse_args()

def run_sql(fname):
    sql = open(os.path.join(ROOT, 'sql', fname)).read()
    presales = ", ".join(f"'{c}'" for c in cfg.PRESALES_COUNTRIES)
    sql = (sql.replace('__W__', cfg.W).replace('__G__', cfg.G)
              .replace('__PRESALES__', presales).replace('__ACCT__', cfg.ACCT))
    cfg.bq_client().query(sql).result()
    print(f"[ok] sql/{fname}")

def run_py(fname):
    t0 = time.time()
    sys.argv = [fname]
    runpy.run_path(os.path.join(ROOT, fname), run_name='__main__')
    print(f"     ({fname} took {time.time()-t0:.0f}s)")

print("=" * 70)
print(f"WSM Monitor [{a.mode}] — target month {cfg.CUR} ({cfg.CUR_LABEL})   write={cfg.W}")
print("=" * 70)

from check_freshness import run_checks
if not run_checks(a.mode) and not a.force:
    sys.exit("ABORTED: source data not fresh enough (see above). Use --force to override.")

if a.mode == 'weekly':
    if not a.skip_sql:
        print("\n[1/2] Weekly aggregate")
        run_sql('monitor_weekly_raw.sql')
    print("\n[2/2] Detect + digest")
    run_py('detect_weekly_alerts.py')
    print("\n=== weekly run complete ===")
    sys.exit(0)

if a.only != 'tabs' and not a.skip_sql:
    print("\n[1/2] BQ aggregates")
    run_sql('monitor_monthly_raw.sql')
    run_sql('monitor_leads_monthly.sql')
if a.only != 'sql':
    print("\n[2/2] Workbook tabs")
    for f in ['build_monitor_cells.py',      # FIRST: resets workbook from source
              'build_leads_trend_tab.py',
              'build_funnel_tab.py',
              'build_leads_issues_tab.py',
              'build_matrix_tab.py']:
        run_py(f)
print("\n=== monitor run complete ===")
print(f"workbook: {cfg.OUT}")
