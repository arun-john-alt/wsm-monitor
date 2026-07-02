"""WSM Monitor — config loader. All modules import constants from here; edit config.yaml, not code.
Derives all month windows from run.month so a new month = one config value (or 'auto')."""
import os, calendar
from datetime import date
import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
_c = yaml.safe_load(open(os.path.join(ROOT, 'config.yaml')))

# --- BigQuery ---
PROJ = _c['bigquery']['project']
W = f"{PROJ}.{_c['bigquery']['dataset']}"           # write dataset (Ads_data_WSM)
G = f"{PROJ}.{_c['bigquery']['source_dataset']}"    # read-only source

def bq_client():
    import google.auth
    from google.cloud import bigquery
    cred, _ = google.auth.default()
    if hasattr(cred, 'with_quota_project'):
        cred = cred.with_quota_project(PROJ)
    return bigquery.Client(project=PROJ, credentials=cred)

# --- month math ---
def shift(ym, n):
    """ym 'YYYY-MM' shifted by n months."""
    y, m = int(ym[:4]), int(ym[5:7])
    t = y * 12 + (m - 1) + n
    return f"{t // 12}-{t % 12 + 1:02d}"

_MN = {1:'Jan',2:'Feb',3:'Mar',4:'Apr',5:'May',6:'Jun',7:'Jul',8:'Aug',9:'Sep',10:'Oct',11:'Nov',12:'Dec'}
def label(ym):  return f"{_MN[int(ym[5:7])]} {ym[:4]}"   # '2026-05' -> 'May 2026'
def mon(ym):    return _MN[int(ym[5:7])]                  # -> 'May'
def month_end(ym):
    y, m = int(ym[:4]), int(ym[5:7])
    return f"{ym}-{calendar.monthrange(y, m)[1]:02d}"

_m = _c['run']['month']
if _m == 'auto':   # last complete calendar month
    t = date.today().replace(day=1)
    CUR = shift(f"{t.year}-{t.month:02d}", -1)
else:
    CUR = str(_m)
PRI  = shift(CUR, -1)
YOY  = shift(CUR, -12)
BASE = [shift(CUR, -3), shift(CUR, -2), shift(CUR, -1)]   # trailing 3-month norm
CUR_LABEL, CUR_MON, PRI_MON = label(CUR), mon(CUR), mon(PRI)

# YTD windows (Jan..CUR of this year vs same months prior year)
YTD_CUR = [f"{CUR[:4]}-{m:02d}" for m in range(1, int(CUR[5:7]) + 1)]
YTD_PRI = [shift(ym, -12) for ym in YTD_CUR]

# Trend window, most-recent-first (includes the current partial month by default)
_ts = str(_c['run']['trend_start'])
_te = _c['run']['trend_end']
TREND_END = shift(CUR, 1) if _te == 'auto' else str(_te)
TREND_MONTHS = []
_ym = TREND_END
while _ym >= _ts:
    TREND_MONTHS.append(_ym)
    _ym = shift(_ym, -1)

# change-history window for Comments/RCA (prior + current month)
CH_START = f"{PRI}-01"
CH_END   = month_end(CUR)
CH_LABEL = f"{PRI_MON}–{CUR_MON}"   # e.g. 'Apr–May'

# --- paths ---
XLSX_SRC = _c['paths']['workbook_src']
OUT      = _c['paths']['workbook_out']
RCA_DIR  = _c['paths']['rca_dir']

# --- business config ---
PRESALES_COUNTRIES = list(_c['presales_countries'])
DRI_MAP = dict(_c['dri'])
def dri(country): return DRI_MAP.get(country, 'Unassigned')

_t = _c['issue_thresholds']
DECLINE, BASE_FLOOR, ABS_FLOOR = float(_t['decline_pct']), float(_t['base_floor']), float(_t['abs_floor'])
DEADBAND = float(_t['deadband_pct'])
CG = _c['comment_gates']
EMAIL = _c['email']; WEEKLY = _c['weekly']

if __name__ == '__main__':
    print(f"month={CUR} ({CUR_LABEL})  prior={PRI}  yoy={YOY}  base={BASE}")
    print(f"ytd={YTD_CUR[0]}..{YTD_CUR[-1]}  trend={TREND_MONTHS[-1]}..{TREND_MONTHS[0]} ({len(TREND_MONTHS)} mo)")
    print(f"write={W}  read={G}")
    print(f"out={OUT}")
    print(f"DRIs={len(DRI_MAP)} countries  presales={len(PRESALES_COUNTRIES)}")
