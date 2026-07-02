"""
Monitor v1 — signal builder. Reads Ads_data_WSM.monitor_monthly, compares the target month
vs the prior month at Product × Country × Theme, and emits ranked 'Signals' cells.

Design (mirrors Big Boss's "sources → one gate → cell"):
  - Sources = metric movements (conversions, clicks, cost, impressions, impression share, CTR).
  - Gate    = materiality (volume floor) + movement (pct AND absolute floor) → kills low-base noise.
  - Ranking = ABSOLUTE significance (clicks/conv/cost/IS-on-volume added), NOT raw % — so a
              600-conv swing outranks a 1→16 explosion.
  - 'Launched/scaled' = prior ~0 → now material: shown as 0→N (honest), not a fake giant %.
  - Output  = top-3 lines per cell, capped; TIGHT (digest) vs MEDIUM (in-cell) tiers tagged.

Writes Ads_data_WSM.monitor_signals. READ-ONLY on Google_ads_data_ajay.
Usage: python build_monitor_signals.py [--month YYYY-MM]   (default = latest month in table)
"""
import os, sys, math, argparse
import google.auth
from google.cloud import bigquery

PROJ='it-security-online-marketing'; WSM=f'{PROJ}.Ads_data_WSM'
cred,_=google.auth.default(); cred=cred.with_quota_project(PROJ)
bq=bigquery.Client(project=PROJ, credentials=cred)

ap=argparse.ArgumentParser(); ap.add_argument('--month', default=None); a=ap.parse_args()

# 1) (re)build the monthly aggregate
sql=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'monitor_monthly.sql')).read()
bq.query(sql).result(); print('[ok] rebuilt Ads_data_WSM.monitor_monthly')

# 2) resolve target + prior month
months=[r.ym for r in bq.query(f"SELECT DISTINCT ym FROM `{WSM}.monitor_monthly` ORDER BY ym").result()]
CUR=a.month or months[-1]
i=months.index(CUR); PRI=months[i-1] if i>0 else None
if not PRI: sys.exit(f"no prior month before {CUR}")
print(f"[plan] target={CUR}  prior={PRI}")

rows=list(bq.query(f"SELECT * FROM `{WSM}.monitor_monthly` WHERE ym IN ('{CUR}','{PRI}')").result())
cells={}
for r in rows: cells.setdefault((r.product,r.country,r.theme),{})[r.ym]=r

def pct(c,p):
    if p in (None,0) or c is None: return None
    return (c-p)/p*100.0

# thresholds: (pct, abs_floor) per metric for MEDIUM and TIGHT; IS in pp
M=dict(volpct=30, clk=25, imp=300, cost=20000, conv=3, isp=5.0, ctr=1.5, imprfloor=500)
T=dict(volpct=50, clk=100, imp=2000, cost=60000, conv=10, isp=8.0, ctr=2.0, imprfloor=2000)
LAUNCH_PRIOR_IMPR=50   # prior essentially off

def arrow(x): return '🔺' if x>0 else '🔻'
def fpct(p):
    """Percent, but fold-change (×) once it's silly (>1000%), so '+150908%' reads as '+1509×'."""
    if p is None: return ''
    if abs(p) >= 1000: return f"{'+' if p>0 else '-'}{abs(p)/100:.0f}×"
    return f"{p:+.0f}%"

def build(cur, pri, G):
    """Return (lines, severity). Lines already sorted by impact, not yet capped."""
    out=[]
    dclk_a=(cur.clicks or 0)-(pri.clicks or 0); dimp_a=(cur.impr or 0)-(pri.impr or 0)
    dco_a=(cur.cost or 0)-(pri.cost or 0); dcv_a=(cur.conv or 0)-(pri.conv or 0)
    # 'launched/scaled' = prior essentially idle in impressions OR spend, now material
    prior_idle = (pri.impr or 0) < LAUNCH_PRIOR_IMPR or (pri.cost or 0) < 500
    launched = prior_idle and ((cur.impr or 0) >= G['imprfloor'] or (cur.clicks or 0) >= G['clk'])
    if launched:
        bits=[f"{int(cur.impr)} impr", f"{int(cur.clicks)} clicks"]
        if (cur.conv or 0)>=1: bits.append(f"{cur.conv:.0f} conv")
        out.append((cur.clicks*1.5+ (cur.conv or 0)*80, f"🆕 launched/scaled — now {', '.join(bits)} (was idle)"))
        sev=out[0][0]; return out, sev
    dcv,dclk,dimp,dco,dcpc = pct(cur.conv,pri.conv),pct(cur.clicks,pri.clicks),pct(cur.impr,pri.impr),pct(cur.cost,pri.cost),pct(cur.cpc,pri.cpc)
    dcpa=pct(cur.cpa,pri.cpa)
    dctr=(cur.ctr-pri.ctr)*100 if cur.ctr is not None and pri.ctr is not None else None
    dsis=(cur.sis-pri.sis)*100 if cur.sis is not None and pri.sis is not None else None
    dslir=(cur.slir-pri.slir)*100 if cur.slir is not None and pri.slir is not None else None
    # conversions (money-closest → highest weight)
    if dcv is not None and abs(dcv)>=G['volpct'] and abs(dcv_a)>=G['conv']:
        out.append((100*abs(dcv_a), f"{arrow(dcv_a)} conversions {fpct(dcv)} ({pri.conv:.0f}→{cur.conv:.0f})"))
    if dcpa is not None and abs(dcpa)>=G['volpct'] and max(cur.conv or 0,pri.conv or 0)>=G['conv']:
        out.append((50*abs(dcv_a)+5, f"{'🔻' if dcpa>0 else '🔺'} CPA {fpct(dcpa)} (cost/conv {'up'if dcpa>0 else'down'})"))
    # clicks / cost / impressions — pct AND absolute floor; clicks lead, cost/impr secondary
    if dclk is not None and abs(dclk)>=G['volpct'] and abs(dclk_a)>=G['clk']:
        out.append((abs(dclk_a), f"{arrow(dclk_a)} clicks {fpct(dclk)} ({int(pri.clicks)}→{int(cur.clicks)})"))
    if dco is not None and abs(dco)>=G['volpct'] and abs(dco_a)>=G['cost']:
        out.append((abs(dco_a)/500, f"{arrow(dco_a)} cost {fpct(dco)}"))
    if dimp is not None and abs(dimp)>=G['volpct'] and abs(dimp_a)>=G['imp']:
        out.append((abs(dimp_a)/50, f"{arrow(dimp_a)} impressions {fpct(dimp)}"))
    # impression share — one coherent narrative (headline move + rank/budget driver)
    if dsis is not None and abs(dsis)>=G['isp'] and max(cur.impr or 0,pri.impr or 0)>=G['imprfloor']:
        lb_c=max(0.0,1-(cur.sis or 0)-(cur.slir or 0)); lb_p=max(0.0,1-(pri.sis or 0)-(pri.slir or 0)); dbud=(lb_c-lb_p)*100
        if dsis<0: drv = "losing to rank" if (dslir or 0)>=dbud and (dslir or 0)>0 else ("losing to budget" if dbud>0 else "")
        else:      drv = "less rank loss" if (dslir or 0)<0 else ("budget freed up" if dbud<0 else "")
        out.append((abs(dsis)*math.sqrt(max(cur.impr or 1,1))/4, f"{arrow(dsis)} search IS {dsis:+.0f}pp ({pri.sis*100:.0f}%→{cur.sis*100:.0f}%){' — '+drv if drv else ''}"))
    if dctr is not None and abs(dctr)>=G['ctr'] and max(cur.impr or 0,pri.impr or 0)>=G['imprfloor']:
        out.append((abs(dctr)*math.sqrt(max(cur.impr or 1,1))/6, f"{arrow(dctr)} CTR {dctr:+.1f}pp ({pri.ctr*100:.1f}%→{cur.ctr*100:.1f}%)"))
    out.sort(key=lambda x:-x[0]); sev=out[0][0] if out else 0
    return out, sev

results=[]
for key,m in cells.items():
    cur,pri=m.get(CUR),m.get(PRI)
    if not cur or not pri: continue
    mlines,msev=build(cur,pri,M)
    if not mlines: continue
    tlines,tsev=build(cur,pri,T)
    is_tight=bool(tlines)
    cell_text="\n".join("- "+t for _,t in mlines[:3])
    results.append(dict(product=key[0],country=key[1],theme=key[2],ym=CUR,prior_ym=PRI,
        severity=round(msev,1), is_tight=is_tight, n_signals=len(mlines), cell_text=cell_text))

import pandas as pd
df=pd.DataFrame(results)
total=sum(1 for k,m in cells.items() if CUR in m and PRI in m)
print(f"\nactive cells both months: {total}")
print(f"  MEDIUM (in-cell) signals : {len(df)}  ({len(df)/total*100:.0f}% of active)")
print(f"  TIGHT (digest) signals   : {int(df.is_tight.sum())}  ({df.is_tight.sum()/total*100:.0f}% of active)")

bq.load_table_from_dataframe(df, f"{WSM}.monitor_signals",
    job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")).result()
print(f"[ok] wrote {len(df)} rows -> {WSM}.monitor_signals")

# ---- TIGHT 'Top Movers' digest, STRATIFIED so every country surfaces (visibility everywhere) ----
PER_COUNTRY=3
tight=df[df.is_tight].copy()
tight['rk']=tight.groupby('country')['severity'].rank(ascending=False, method='first')
digest=tight[tight.rk<=PER_COUNTRY].drop(columns=['rk']).sort_values(['country','severity'],ascending=[True,False])
bq.load_table_from_dataframe(digest, f"{WSM}.monitor_top_movers",
    job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")).result()
ncty=digest.country.nunique()
print(f"[ok] wrote {len(digest)} rows -> {WSM}.monitor_top_movers  (top {PER_COUNTRY}/country across {ncty} countries)\n")

order=tight.groupby('country')['severity'].max().sort_values(ascending=False).index
print(f"===== TIGHT 'Top Movers' — stratified by country (showing first 12 of {ncty}) =====")
for ctry in list(order)[:12]:
    sub=digest[digest.country==ctry]
    if sub.empty: continue
    print(f"\n■ {ctry}")
    for r in sub.itertuples():
        print(f"  {r.product} · {r.theme}")
        for ln in r.cell_text.split("\n"): print("     "+ln)
