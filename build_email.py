"""Monthly consolidated email body (Phase 3). Renders email-safe HTML (tables + inline CSS):
  1. Leads Issues (by DRI)  — WITHOUT the Comments column (user preference)
  2. Country x Product (target month, YoY) — ALL-engines matrix
Saves to <weekly_dir>/../Email/wsm_monthly_<month>.html. Sending (SMTP) wired separately.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wsm_cfg import (W, CUR, YOY, BASE, CUR_LABEL, CUR_MON, DECLINE, BASE_FLOOR, ABS_FLOOR,
                     DEADBAND, WEEKLY_DIR, EMAIL, dri, label, bq_client)
from collections import defaultdict
import html as H

bq = bq_client()
L = {}; GL = {}; BL = {}
for r in bq.query(f"SELECT product,country,theme,ym,leads,leads_google,leads_bing FROM `{W}.monitor_leads_monthly`").result():
    k = (r.product, r.country, r.theme, r.ym); L[k] = (r.leads or 0); GL[k] = (r.leads_google or 0); BL[k] = (r.leads_bing or 0)
def v(d, k, ym): return d.get((*k, ym), 0)
def a3(d, k): return sum(v(d, k, m) for m in BASE) / 3.0
def pctc(c, b): return ((c-b)/b*100) if b else None

# ---------- shared style ----------
NAVY = '#305496'; GREEN = '#c6efce'; RED = '#ffc7ce'; GREY = '#ededed'; DRIF = '#ddebf7'
TD = "padding:4px 8px;border:1px solid #d9d9d9;font-size:12px;"
TH = TD + f"background:{NAVY};color:#fff;font-weight:bold;"
def small(p): return f' <span style="font-size:9px;color:#808080">({p:+.0f}%)</span>' if p is not None else ''
def valcell(val, p, fill=None, bold=False):
    s = TD + (f"background:{fill};" if fill else '') + ("font-weight:bold;" if bold else '') + "text-align:center;"
    return f'<td style="{s}">{val}{small(p)}</td>'

# ---------- 1) Leads Issues by DRI (no Comments) ----------
themes_by = defaultdict(list)
for (p, c, t, ym) in list(L.keys()): themes_by[(c, p)].append((p, c, t))
groups = {}
for (c, p), keys in themes_by.items():
    keys = list(set(keys)); issues = []
    for k in keys:
        may = v(L, k, CUR); base = a3(L, k)
        if base >= BASE_FLOOR and may <= base*(1-DECLINE/100) and (base-may) >= ABS_FLOOR:
            issues.append((k, may, base, v(L, k, YOY)))
    if not issues: continue
    issues.sort(key=lambda x: -(x[2]-x[1]))
    groups[(c, p)] = dict(issues=issues, keys=keys, impact=sum(b-m for _, m, b, _ in issues))
dimp = defaultdict(float); cimp = defaultdict(float)
for (c, p), g in groups.items(): dimp[dri(c)] += g['impact']; cimp[c] += g['impact']
order = sorted(groups.keys(), key=lambda cp: (-dimp[dri(cp[0])], dri(cp[0]), -cimp[cp[0]], cp[0], -groups[cp]['impact']))

_heads = ["DRI", "Country", "Product", "Theme", f"Leads ({CUR_MON}, YoY)", "Google", "Bing", "3-mo avg", "vs 3-mo"]
rows = ['<tr>' + ''.join('<th style="' + TH + '">' + h + '</th>' for h in _heads) + '</tr>']
last = None
for (c, p) in order:
    g = groups[(c, p)]; d = dri(c); keys = g['keys']
    if d != last:
        rows.append(f'<tr><td colspan="9" style="{TD}background:{DRIF};font-weight:bold">&#9660; {H.escape(d)}</td></tr>')
        last = d
    pmay = sum(v(L, k, CUR) for k in keys); pbase = sum(a3(L, k) for k in keys); pyoy = sum(v(L, k, YOY) for k in keys)
    pg = sum(v(GL, k, CUR) for k in keys); pgb = sum(a3(GL, k) for k in keys)
    pb = sum(v(BL, k, CUR) for k in keys); pbb = sum(a3(BL, k) for k in keys)
    pyoyp = pctc(pmay, pyoy)
    gb = f"{TD}background:{GREY};font-weight:bold;"
    rows.append('<tr>' + ''.join(f'<td style="{gb}">{H.escape(str(x))}</td>' for x in [d, c, p, '■ ALL THEMES (product)'])
        + valcell(round(pmay), pyoyp, GREEN if (pyoyp or 0) >= 0 else RED, bold=True)
        + valcell(round(pg), pctc(pg, pgb), GREY) + valcell(round(pb), pctc(pb, pbb), GREY)
        + f'<td style="{gb}text-align:center">{pbase:.1f}</td>'
        + valcell('', pctc(pmay, pbase), GREY) + '</tr>')
    for k, may, base, yy in g['issues']:
        rows.append('<tr>' + ''.join(f'<td style="{TD}">{H.escape(str(x))}</td>' for x in [d, c, p, ' '+k[2]])
            + valcell(round(may), pctc(may, yy), RED)
            + valcell(round(v(GL, k, CUR)), pctc(v(GL, k, CUR), a3(GL, k)))
            + valcell(round(v(BL, k, CUR)), pctc(v(BL, k, CUR), a3(BL, k)))
            + f'<td style="{TD}text-align:center">{base:.1f}</td>'
            + valcell('', pctc(may, base)) + '</tr>')
issues_tbl = f'<table cellspacing="0" style="border-collapse:collapse">{"".join(rows)}</table>'
n_issues = sum(len(g['issues']) for g in groups.values())

# ---------- 2) Country x Product matrix (target month, ALL engines) ----------
cm = defaultdict(float); pm = defaultdict(float)
ytd = defaultdict(float)
for (p, c, t, ym), val in L.items():
    if ym == CUR: cm[(c, p)] += val
    elif ym == YOY: pm[(c, p)] += val
    if ym.startswith(CUR[:4]) and ym <= CUR: ytd[(c, p)] += val
countries = sorted({c for c, p in list(cm)+list(pm)}, key=lambda c: -sum(ytd.get((c, p), 0) for p in {p for _, p in ytd}))
products = sorted({p for c, p in list(cm)+list(pm)}, key=lambda p: -sum(ytd.get((c, p), 0) for c in countries))
countries = [c for c in countries if any(cm.get((c, p), 0) or pm.get((c, p), 0) for p in products)]
products = [p for p in products if any(cm.get((c, p), 0) or pm.get((c, p), 0) for c in countries)]
def mcell(cv, pv):
    if cv < 1 and pv < 1: return f'<td style="{TD}"></td>'
    if pv < 1: return f'<td style="{TD}background:{GREEN};text-align:center">NEW{small(None) or ""}<span style="font-size:9px;color:#808080"> ({cv:.0f})</span></td>'
    g = (cv-pv)/pv*100
    fill = GREEN if g >= DEADBAND else (RED if g <= -DEADBAND else None)
    s = TD + (f"background:{fill};" if fill else '') + "text-align:center;"
    return f'<td style="{s}">{g:+.0f}%<span style="font-size:9px;color:#808080"> ({cv:.0f})</span></td>'
mrows = ['<tr><th style="'+TH+'">Country \\ Product</th>' + ''.join(f'<th style="{TH}">{H.escape(p)}</th>' for p in products) + f'<th style="{TH}">All</th></tr>']
for c in countries:
    cells = ''.join(mcell(cm.get((c, p), 0), pm.get((c, p), 0)) for p in products)
    tot = mcell(sum(cm.get((c, p), 0) for p in products), sum(pm.get((c, p), 0) for p in products))
    mrows.append(f'<tr><td style="{TD}">{H.escape(c)}</td>{cells}{tot}</tr>')
mrows.append(f'<tr><td style="{TD}background:{GREY};font-weight:bold">All countries</td>'
    + ''.join(mcell(sum(cm.get((c, p), 0) for c in countries), sum(pm.get((c, p), 0) for c in countries)) for p in products)
    + mcell(sum(cm.values()), sum(pm.values())) + '</tr>')
matrix_tbl = f'<table cellspacing="0" style="border-collapse:collapse">{"".join(mrows)}</table>'

# ---------- assemble ----------
body = f"""<div style="font-family:Calibri,Arial,sans-serif;max-width:960px">
<h2 style="color:{NAVY};margin:0 0 2px">WSM Monitor &mdash; {CUR_LABEL}</h2>
<div style="font-size:12px;color:#666;margin-bottom:14px">Consolidated monthly report &middot; leads = presales (US/IN/UK/CA/AU) / sales (rest) &middot; Google Ads read-only</div>
<h3 style="color:{NAVY};margin:14px 0 4px">1 &middot; Leads Issues (by DRI) &mdash; {n_issues} themes need review</h3>
<div style="font-size:11px;color:#666;margin-bottom:6px">Themes &ge;{DECLINE:.0f}% below their trailing 3-month average. Product rollup row shows overall health; red rows are the issues to resolve.</div>
{issues_tbl}
<h3 style="color:{NAVY};margin:18px 0 4px">2 &middot; Country &times; Product &mdash; {CUR_LABEL} leads vs {label(YOY)}</h3>
<div style="font-size:11px;color:#666;margin-bottom:6px">All engines (Google + Bing). Green &ge; +{DEADBAND:.0f}%, red &le; &minus;{DEADBAND:.0f}%. Grey count = {CUR_MON} leads.</div>
{matrix_tbl}
<div style="font-size:10px;color:#999;margin-top:16px;border-top:1px solid #ddd;padding-top:6px">
Generated by WSM Monitor. Full detail (Leads Trend, Funnel, engine-split matrices, per-theme signals) in the Continuous Monitoring workbook. Reply to this alias for threshold/roster changes.</div>
</div>"""

outdir = os.path.join(os.path.dirname(WEEKLY_DIR), 'Email')
os.makedirs(outdir, exist_ok=True)
path = os.path.join(outdir, f'wsm_monthly_{CUR}.html')
open(path, 'w').write(body)
print(f"[ok] email body -> {path}")
print(f"     subject: WSM Monitor — {CUR_LABEL}: {n_issues} lead issues across {len({c for c,p in order})} countries | to: {EMAIL['to']}")
