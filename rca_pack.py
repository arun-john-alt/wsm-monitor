"""Assemble an RCA data-pack for one unit (country [+ product]). Pulls, for the down themes:
leads (engine split, YoY), impression share (IS / lost-to-rank / lost-to-budget), clicks/cost/CPL,
and change-history actions. Prints a structured brief (JSON) that feeds the one-page RCA.
Note: search volume (adg_keyword_universe) removed — that table sums the full keyword universe
which grows monthly, producing artifacts. Auction insights omitted (table empty). Usage:
  python rca_pack.py --country "United States" --product ADAP"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wsm_cfg import W, G, CUR, PRI, BASE, YOY, CH_START, CH_END, bq_client, DECLINE, BASE_FLOOR, ABS_FLOOR

ap=argparse.ArgumentParser(); ap.add_argument('--country',required=True); ap.add_argument('--product',default=None)
a=ap.parse_args(); C=a.country; P=a.product
bq=bq_client()
def q(s): return list(bq.query(s).result())
pf=f"AND product='{P}'" if P else ""

# --- leads by theme (total/google/bing) ---
L={}; GL={}; BL={}
for r in q(f"SELECT theme,ym,leads,leads_google,leads_bing FROM `{W}.monitor_leads_monthly` WHERE country='{C}' {pf}"):
    L[(r.theme,r.ym)]=r.leads or 0; GL[(r.theme,r.ym)]=r.leads_google or 0; BL[(r.theme,r.ym)]=r.leads_bing or 0
themes=sorted({t for (t,ym) in L})
def v(d,t,ym): return d.get((t,ym),0)
def a3(d,t): return sum(v(d,t,m) for m in BASE)/3.0
def pc(cur,base): return round((cur-base)/base*100) if base else None

down=[]
for t in themes:
    may=v(L,t,CUR); base=a3(L,t)
    if base >= BASE_FLOOR and may <= base*(1-DECLINE/100) and (base-may) >= ABS_FLOOR:
        down.append((t,may,base,base-may))
down.sort(key=lambda x:-x[3]); down=down[:5]

# --- raw perf/IS by theme ---
R={}
for r in q(f"SELECT theme,ym,impr,clicks,cost,ctr,sis,slir FROM `{W}.monitor_monthly_raw` WHERE country='{C}' {pf}"):
    R[(r.theme,r.ym)]=r

# --- change events by theme (Apr-May 2026) ---
CH={}
for r in q(f"""SELECT theme, category, COUNT(*) n, SUM(count) cnt, STRING_AGG(DISTINCT changed_by LIMIT 3) who
  FROM `{G}.change_events` WHERE country='{C}' {pf} AND date BETWEEN '{CH_START}' AND '{CH_END}'
  GROUP BY 1,2"""):
    CH.setdefault(r.theme,[]).append((r.category, r.n, r.who))
# notable CPC cuts
CPC={}
for r in q(f"""SELECT theme, COUNT(*) n, ROUND(AVG(SAFE_DIVIDE(new_cpc-old_cpc,old_cpc))*100,0) avg_pct
  FROM `{G}.change_events` WHERE country='{C}' {pf} AND category='cpc' AND date BETWEEN '{CH_START}' AND '{CH_END}'
    AND old_cpc>0 AND new_cpc<old_cpc GROUP BY 1"""):
    CPC[r.theme]=(r.n, r.avg_pct)

# --- assemble brief ---
prod_may=sum(v(L,t,CUR) for t in themes); prod_base=sum(a3(L,t) for t in themes); prod_yoy=sum(v(L,t,YOY) for t in themes)
brief={'unit':f'{C}'+(f' / {P}' if P else ''), 'month':CUR,
  'product_leads':{'may':round(prod_may),'avg3':round(prod_base,1),'vs_avg_pct':pc(prod_may,prod_base),'yoy_pct':pc(prod_may,prod_yoy),
                   'google':round(sum(v(GL,t,CUR) for t in themes)),'bing':round(sum(v(BL,t,CUR) for t in themes))},
  'down_themes':[]}
for t,may,base,lost in down:
    rc=R.get((t,CUR)); rp=R.get((t,PRI))
    d={'theme':t,
       'leads':{'may':round(may),'avg3':round(base,1),'vs_avg_pct':pc(may,base),'yoy_pct':pc(may,v(L,t,YOY)),
                'google':round(v(GL,t,CUR)),'bing':round(v(BL,t,CUR)),
                'google_vs_avg':pc(v(GL,t,CUR),a3(GL,t)),'bing_vs_avg':pc(v(BL,t,CUR),a3(BL,t))},
       'impression_share':{'may_pct':round((rc.sis or 0)*100) if rc else None,'apr_pct':round((rp.sis or 0)*100) if rp else None,
                'lost_to_rank_may_pct':round((rc.slir or 0)*100) if rc else None,
                'lost_to_budget_may_pct':round(max(0,1-(rc.sis or 0)-(rc.slir or 0))*100) if rc else None},
       'traffic':{'clicks_may':int(rc.clicks) if rc else None,'clicks_apr':int(rp.clicks) if rp else None,
                'ctr_may_pct':round((rc.ctr or 0)*100,1) if rc else None,'ctr_apr_pct':round((rp.ctr or 0)*100,1) if rp else None,
                'cpl_may':round((rc.cost or 0)/may) if (rc and may) else None},
       'change_history':CH.get(t,[]), 'cpc_cuts':CPC.get(t)}
    brief['down_themes'].append(d)
print(json.dumps(brief, indent=1, default=str))
