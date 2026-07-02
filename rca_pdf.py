"""Render a one-page RCA PDF from a content dict. Reusable per unit; sample content = US x ADAP.
ASCII-only text (INR, ->, pp) to avoid font issues. Output: Downloads/Monitor/RCA/<unit>.pdf"""
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem, HRFlowable

NAVY=colors.HexColor('#305496'); RED=colors.HexColor('#C00000'); GREY=colors.HexColor('#666666')
ss=getSampleStyleSheet()
H1=ParagraphStyle('H1',parent=ss['Normal'],fontName='Helvetica-Bold',fontSize=15,textColor=NAVY,spaceAfter=2)
SUB=ParagraphStyle('SUB',parent=ss['Normal'],fontName='Helvetica',fontSize=9.5,textColor=GREY,spaceAfter=6)
SUMM=ParagraphStyle('SUMM',parent=ss['Normal'],fontName='Helvetica',fontSize=10,leading=13,spaceAfter=8)
TH=ParagraphStyle('TH',parent=ss['Normal'],fontName='Helvetica-Bold',fontSize=11.5,textColor=NAVY,spaceBefore=6,spaceAfter=1)
DELTA=ParagraphStyle('DELTA',parent=ss['Normal'],fontName='Helvetica-Bold',fontSize=9.5,textColor=RED,spaceAfter=3)
BUL=ParagraphStyle('BUL',parent=ss['Normal'],fontName='Helvetica',fontSize=9.3,leading=12)
CA=ParagraphStyle('CA',parent=ss['Normal'],fontName='Helvetica',fontSize=9.3,leading=12,spaceBefore=2,leftIndent=2)
FOOT=ParagraphStyle('FOOT',parent=ss['Normal'],fontName='Helvetica-Oblique',fontSize=7.3,textColor=GREY,spaceBefore=8)

def render_rca(c, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    doc=SimpleDocTemplate(path, pagesize=letter, topMargin=0.6*inch, bottomMargin=0.5*inch, leftMargin=0.7*inch, rightMargin=0.7*inch)
    F=[]
    F.append(Paragraph("Paid-Search Leads &mdash; Root-Cause Analysis", H1))
    F.append(Paragraph(f"{c['unit']} &nbsp;|&nbsp; {c['month']} &nbsp;|&nbsp; DRI: {c['dri']}", SUB))
    F.append(HRFlowable(width='100%', thickness=1, color=NAVY, spaceAfter=6))
    F.append(Paragraph(c['summary'], SUMM))
    for t in c['themes']:
        F.append(Paragraph(t['name'], TH))
        F.append(Paragraph(t['delta'], DELTA))
        F.append(ListFlowable([ListItem(Paragraph(b, BUL), leftIndent=10, value='bulletchar') for b in t['findings']],
                              bulletType='bullet', start='disc', leftIndent=12, spaceAfter=1))
        F.append(Paragraph(f"<b>Likely cause:</b> {t['cause']}", CA))
        F.append(Paragraph(f"<b>Recommended:</b> {t['action']}", CA))
    F.append(HRFlowable(width='100%', thickness=0.5, color=GREY, spaceBefore=8))
    F.append(Paragraph(c['footer'], FOOT))
    doc.build(F)
    print(f"[ok] wrote {path}")

# ---- sample content: US x ADAP, May 2026 (composed from rca_pack brief) ----
content={
 'unit':'United States &middot; ADAP','month':'May 2026','dri':'Aashiq',
 'summary':("ADAP&middot;US leads held roughly flat at the product level &mdash; <b>117 in May</b> vs a 117 three-month "
   "average (+2%), &minus;3% YoY (Google 82 / Bing 35). But two themes are dragging and warrant a DRI review:"),
 'themes':[
  {'name':'1. Branding',
   'delta':'Leads 12 &nbsp;(&minus;32% vs 3-mo avg &middot; &minus;20% YoY) &nbsp;&mdash;&nbsp; Google 7 (&minus;43%) &middot; Bing 5 (&minus;6%)',
   'findings':[
     "<b>Demand is intact</b> &mdash; keyword search volume flat (+1% vs 3-mo). Not a demand problem.",
     "<b>Traffic actually rose</b> &mdash; clicks 267 -&gt; 356 &mdash; but CTR fell 19.1% -&gt; 15.7% and impression share slipped 73% -&gt; 69%.",
     "Heavy Apr&ndash;May activity on this theme: 88 max-CPC changes, 18 keywords added, 8 removed, 7 ad-text edits (manoj.ramadoss, vignesh.es)."],
   'cause':("More clicks and steady demand but fewer, lower-CTR leads &mdash; concentrated on <b>Google</b> (&minus;43% vs Bing &minus;6%). "
     "Points to ad-relevance / landing-page / lead-quality, likely disturbed by the heavy ad-text &amp; keyword churn &mdash; not demand or budget."),
   'action':"Review the Apr&ndash;May Google Branding ad-text and keyword changes; check landing-page relevance and lead quality. The demand is there to recover."},
  {'name':'2. Competitor',
   'delta':'Leads 5 &nbsp;(&minus;50% vs 3-mo avg &middot; +25% YoY) &nbsp;&mdash;&nbsp; Google 3 (&minus;40%) &middot; Bing 2 (&minus;60%)',
   'findings':[
     "<b>Losing the auction on rank</b> &mdash; impression share 55% -&gt; 45%, with 55% of impressions lost to rank.",
     "<b>Spend up but not converting</b> &mdash; clicks 252 -&gt; 743 (approx 3x) while leads halved; cost per lead INR 2.8 lakh.",
     "Auction-insights competitor detail unavailable (auction_insights_weekly not yet populated)."],
   'cause':("Pouring more clicks into competitor terms while losing rank position, at an unsustainable INR 2.8L per lead &mdash; "
     "classic competitor-term inefficiency."),
   'action':"Reassess competitor-term bids / rank strategy and budget; current spend isn't converting &mdash; consider trimming or refocusing to higher-intent terms."},
 ],
 'footer':("Factors considered: leads (presales, US), impression share, search volume (Google, monthly), traffic/CTR/CPL, change history (to Jun 5). "
   "Auction insights pending data population. Search volume &amp; terms are Google-only. Source: Ads_data_WSM. Generated automatically."),
}
if __name__ == '__main__':
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from wsm_cfg import RCA_DIR, CUR
    os.makedirs(RCA_DIR, exist_ok=True)
    render_rca(content, os.path.join(RCA_DIR, f'US_ADAP_{CUR}.pdf'))
