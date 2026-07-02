"""Weekly alert detector (Phase 2). Compares the latest COMPLETE week vs the trailing 4-week
average, at two grains:
  - Country×Product : spend/clicks moves, search-IS drops, CTR drops
  - Theme           : clicks & spend moves only (leads too sparse weekly)
Maintains state in Ads_data_WSM.wsm_alerts (alert_key, first/last week, weeks_open, status):
  new -> open (re-detected next week) -> resolved (not re-detected). Prints + saves a per-DRI digest.
Run via: python run_monitor.py --mode weekly   (or standalone)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wsm_cfg import W, G, WEEKLY, WEEKLY_DIR, DRI_MAP, dri, bq_client
from datetime import date, timedelta, datetime, timezone
from collections import defaultdict
import pandas as pd
from google.cloud import bigquery

bq = bq_client()
CFGW = WEEKLY
LOOKBACK = int(CFGW['lookback_weeks'])

# --- resolve target week = latest COMPLETE ISO week in the daily data ---
maxd = list(bq.query(f"SELECT MAX(segments_date) d FROM `{G}.ads_AdGroupBasicStats_5419501619`").result())[0].d
wk_of_maxd = maxd - timedelta(days=maxd.weekday())          # Monday of max-date's week
target = wk_of_maxd - timedelta(days=7) if maxd < wk_of_maxd + timedelta(days=6) else wk_of_maxd
base_weeks = [target - timedelta(days=7*(i+1)) for i in range(LOOKBACK)]
print(f"[plan] data through {maxd} -> target week {target} (Mon) vs avg of {base_weeks[-1]}..{base_weeks[0]}")

wk_list = "','".join(str(w) for w in [target] + base_weeks)
rows = list(bq.query(f"""SELECT product,country,theme,week_start,impr,clicks,cost,ctr,sis
  FROM `{W}.monitor_weekly_raw` WHERE week_start IN ('{wk_list}')""").result())

# --- aggregate to the two grains ---
cp = defaultdict(lambda: defaultdict(lambda: dict(clicks=0.0, cost=0.0, impr=0.0, wsis=0.0, wimp=0.0)))
th = defaultdict(lambda: defaultdict(lambda: dict(clicks=0.0, cost=0.0)))
for r in rows:
    wk = r.week_start
    a = cp[(r.country, r.product)][wk]
    a['clicks'] += (r.clicks or 0); a['cost'] += (r.cost or 0); a['impr'] += (r.impr or 0)
    if r.sis is not None and (r.impr or 0) > 0:
        a['wsis'] += r.sis * r.impr; a['wimp'] += r.impr
    t = th[(r.country, r.product, r.theme)][wk]
    t['clicks'] += (r.clicks or 0); t['cost'] += (r.cost or 0)

def avg(vals): return sum(vals)/len(vals) if vals else None
def pct(c, b): return (c-b)/b*100 if b else None
def inr(v):
    if v >= 1e7: return f'Rs {v/1e7:.1f}Cr'
    if v >= 1e5: return f'Rs {v/1e5:.1f}L'
    return f'Rs {v/1e3:.0f}k'

alerts = []   # dicts: grain,country,product,theme,metric,direction,cur,base,change,detail
def add(grain, c, p, t, metric, direction, cur, base, change, detail):
    alerts.append(dict(grain=grain, country=c, product=p, theme=t or '', metric=metric,
                       direction=direction, cur_value=round(cur, 2), base_value=round(base, 2),
                       change=round(change, 1), detail=detail))

# --- Country×Product detections ---
for (c, p), wkd in cp.items():
    curw = wkd.get(target)
    if not curw: continue
    bclk = avg([wkd[w]['clicks'] for w in base_weeks if w in wkd])
    bcost = avg([wkd[w]['cost'] for w in base_weeks if w in wkd])
    if bclk is None or bclk < CFGW['cp_min_clicks']: continue    # unit too small to alert weekly
    d = pct(curw['clicks'], bclk)
    if d is not None and abs(d) >= CFGW['cp_wow_pct']:
        add('country_product', c, p, None, 'clicks', 'down' if d < 0 else 'up', curw['clicks'], bclk, d,
            f"clicks {d:+.0f}% ({curw['clicks']:.0f} vs {bclk:.0f}/wk avg)")
    d = pct(curw['cost'], bcost) if bcost else None
    if d is not None and abs(d) >= CFGW['cp_wow_pct']:
        add('country_product', c, p, None, 'spend', 'down' if d < 0 else 'up', curw['cost'], bcost, d,
            f"spend {d:+.0f}% ({inr(curw['cost'])} vs {inr(bcost)}/wk avg)")
    cur_sis = curw['wsis']/curw['wimp'] if curw['wimp'] else None
    bsis_v = [wkd[w]['wsis']/wkd[w]['wimp'] for w in base_weeks if w in wkd and wkd[w]['wimp']]
    bsis = avg(bsis_v)
    if cur_sis is not None and bsis is not None and (bsis-cur_sis)*100 >= CFGW['cp_is_drop_pp']:
        add('country_product', c, p, None, 'impression_share', 'down', cur_sis*100, bsis*100, (cur_sis-bsis)*100,
            f"search IS {(cur_sis-bsis)*100:+.0f}pp ({cur_sis*100:.0f}% vs {bsis*100:.0f}% avg)")
    cur_ctr = curw['clicks']/curw['impr'] if curw['impr'] else None
    bctr_v = [wkd[w]['clicks']/wkd[w]['impr'] for w in base_weeks if w in wkd and wkd[w]['impr']]
    bctr = avg(bctr_v)
    if cur_ctr is not None and bctr is not None and (bctr-cur_ctr)*100 >= CFGW['cp_ctr_drop_pp']:
        add('country_product', c, p, None, 'ctr', 'down', cur_ctr*100, bctr*100, (cur_ctr-bctr)*100,
            f"CTR {(cur_ctr-bctr)*100:+.1f}pp ({cur_ctr*100:.1f}% vs {bctr*100:.1f}% avg)")

# --- Theme detections (clicks & spend only) ---
for (c, p, t), wkd in th.items():
    curw = wkd.get(target)
    if not curw: continue
    bclk = avg([wkd[w]['clicks'] for w in base_weeks if w in wkd])
    bcost = avg([wkd[w]['cost'] for w in base_weeks if w in wkd])
    if bclk is not None and bclk >= CFGW['theme_min_clicks']:
        d = pct(curw['clicks'], bclk)
        if d is not None and abs(d) >= CFGW['theme_wow_pct']:
            add('theme', c, p, t, 'clicks', 'down' if d < 0 else 'up', curw['clicks'], bclk, d,
                f"clicks {d:+.0f}% ({curw['clicks']:.0f} vs {bclk:.0f}/wk avg)")
    if bcost is not None and bcost >= CFGW['theme_min_spend_inr']:
        d = pct(curw['cost'], bcost)
        if d is not None and abs(d) >= CFGW['theme_wow_pct']:
            add('theme', c, p, t, 'spend', 'down' if d < 0 else 'up', curw['cost'], bcost, d,
                f"spend {d:+.0f}% ({inr(curw['cost'])} vs {inr(bcost)}/wk avg)")

print(f"[detect] {len(alerts)} raw detections "
      f"(CP={sum(1 for a in alerts if a['grain']=='country_product')}, theme={sum(1 for a in alerts if a['grain']=='theme')})")

# --- state merge with wsm_alerts ---
def keyof(a): return f"{a['grain']}|{a['country']}|{a['product']}|{a['theme']}|{a['metric']}|{a['direction']}"
try:
    prior = {r.alert_key: dict(r.items()) for r in bq.query(f"SELECT * FROM `{W}.wsm_alerts`").result()}
except Exception:
    prior = {}
now = datetime.now(timezone.utc).isoformat()
state = []
detected = set()
for a in alerts:
    k = keyof(a); detected.add(k)
    pr = prior.get(k)
    if pr and pr['status'] in ('new', 'open') and str(pr['last_week']) >= str(target - timedelta(days=7)):
        state.append(dict(alert_key=k, **{f: a[f] for f in ('grain','country','product','theme','metric','direction','cur_value','base_value','change','detail')},
                          first_week=str(pr['first_week']), last_week=str(target),
                          weeks_open=int(pr['weeks_open'])+1, status='open', updated_at=now))
    else:
        state.append(dict(alert_key=k, **{f: a[f] for f in ('grain','country','product','theme','metric','direction','cur_value','base_value','change','detail')},
                          first_week=str(target), last_week=str(target),
                          weeks_open=1, status='new', updated_at=now))
resolved = 0
for k, pr in prior.items():
    if k not in detected and pr['status'] in ('new', 'open'):
        pr = dict(pr); pr['status'] = 'resolved'; pr['updated_at'] = now
        pr['first_week'] = str(pr['first_week']); pr['last_week'] = str(pr['last_week'])
        state.append(pr); resolved += 1
    elif k not in detected:
        pr = dict(pr); pr['first_week'] = str(pr['first_week']); pr['last_week'] = str(pr['last_week'])
        state.append(pr)
df = pd.DataFrame(state)
bq.load_table_from_dataframe(df, f"{W}.wsm_alerts",
    job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")).result()
print(f"[ok] wsm_alerts: {len(df)} rows ({sum(1 for s in state if s['status']=='new')} new, "
      f"{sum(1 for s in state if s['status']=='open')} open, {resolved} newly resolved)")

# --- per-DRI digest ---
active = [s for s in state if s['status'] in ('new', 'open')]
bydri = defaultdict(list)
for a in active: bydri[dri(a['country'])].append(a)
cap = int(CFGW['max_alerts_per_dri'])
lines = [f"WSM Weekly Alerts — week of {target} to {target+timedelta(days=6)} (vs trailing {LOOKBACK}-wk avg)", ""]
for d in sorted(bydri, key=lambda x: -len(bydri[x])):
    items = sorted(bydri[d], key=lambda a: (0 if a['direction'] == 'down' else 1,   # issues before surges
                                            -a['weeks_open'], -abs(a['change'])))[:cap]
    lines.append(f"■ {d}  ({len(bydri[d])} active alerts)")
    for a in items:
        tag = 'NEW' if a['status'] == 'new' else f"OPEN {a['weeks_open']}w"
        arrow = 'v' if a['direction'] == 'down' else '^'
        unit = f"{a['country']} × {a['product']}" + (f" · {a['theme']}" if a['theme'] else '')
        lines.append(f"  [{tag}] {arrow} {unit} — {a['detail']}")
    if len(bydri[d]) > cap: lines.append(f"  … +{len(bydri[d])-cap} more")
    lines.append("")
lines.append(f"Resolved this week: {resolved}")
digest = "\n".join(lines)
os.makedirs(WEEKLY_DIR, exist_ok=True)
path = os.path.join(WEEKLY_DIR, f"weekly_alerts_{target}.txt")
open(path, 'w').write(digest)
print(f"[ok] digest -> {path}\n")
print(digest)
