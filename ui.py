"""WSM Monitor — local control dashboard (stdlib only, no extra deps).
    python3 ui.py          -> open http://localhost:8787
Buttons: check freshness, run weekly alerts, run monthly report (with month override + force).
Runs execute run_monitor.py as a subprocess with live log streaming; one run at a time.
"""
import os, sys, json, threading, subprocess, html
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = 8787
STATE = {'proc': None, 'log': [], 'running': False, 'exit': None, 'label': ''}

def start_run(mode, month, force):
    if STATE['running']: return False
    cmd = [sys.executable, os.path.join(ROOT, 'run_monitor.py'), '--mode', mode]
    if force: cmd.append('--force')
    env = {**os.environ, 'PYTHONWARNINGS': 'ignore', 'PYTHONUNBUFFERED': '1'}
    if month: env['WSM_MONTH'] = month
    STATE.update(log=[f"$ {' '.join(cmd)}" + (f"   (WSM_MONTH={month})" if month else '')],
                 running=True, exit=None, label=f"{mode}" + (f" · {month}" if month else ''))
    p = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, env=env)
    STATE['proc'] = p
    def reader():
        for line in p.stdout:
            STATE['log'].append(line.rstrip('\n'))
        p.wait()
        STATE['exit'] = p.returncode; STATE['running'] = False
        STATE['log'].append(f"--- finished (exit {p.returncode}) ---")
    threading.Thread(target=reader, daemon=True).start()
    return True

def freshness(mode):
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'check_freshness.py'), mode],
                       cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, 'PYTHONWARNINGS': 'ignore'})
    return dict(ok=(r.returncode == 0), text=(r.stdout + r.stderr).strip())

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>WSM Monitor</title><style>
body{font-family:-apple-system,Segoe UI,sans-serif;max-width:860px;margin:24px auto;padding:0 16px;background:#f6f7fb;color:#1c2333}
h1{color:#305496;font-size:22px;margin-bottom:2px} .sub{color:#777;font-size:13px;margin-bottom:18px}
.card{background:#fff;border:1px solid #e3e6ef;border-radius:10px;padding:16px;margin-bottom:14px;box-shadow:0 1px 3px rgba(0,0,0,.04)}
button{background:#305496;color:#fff;border:0;border-radius:8px;padding:10px 18px;font-size:14px;cursor:pointer;margin-right:10px}
button:disabled{background:#aab4cc;cursor:not-allowed}
button.secondary{background:#5b6b8c} button.run{background:#1e7a3c}
pre{background:#101522;color:#d7e0f4;border-radius:8px;padding:12px;font-size:12px;line-height:1.5;max-height:420px;overflow:auto;white-space:pre-wrap}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:600;margin-left:8px}
.ok{background:#c6efce;color:#1e5c31}.bad{background:#ffc7ce;color:#8a1c24}.busy{background:#fff2cc;color:#7a5b00}
input[type=text]{padding:8px;border:1px solid #cfd6e4;border-radius:8px;width:110px;font-size:14px}
label{font-size:13px;color:#444;margin-right:14px}
</style></head><body>
<h1>WSM Monitor</h1><div class="sub">SEM intelligence — verify data, then generate on demand. Google Ads is read-only.</div>

<div class="card"><b>1 · Data freshness</b> <span id="fbadge"></span><br><br>
<button class="secondary" onclick="fresh()">Check freshness</button>
<pre id="fout" style="display:none"></pre></div>

<div class="card"><b>2 · Generate</b> <span id="rbadge"></span><br><br>
<label>Target month <input type="text" id="month" placeholder="auto"></label>
<label><input type="checkbox" id="force"> force (ignore freshness FAIL)</label><br><br>
<button class="run" id="bw" onclick="run('weekly')">Run Weekly Alerts</button>
<button class="run" id="bm" onclick="run('monthly')">Run Monthly Report</button></div>

<div class="card"><b>3 · Run log</b><pre id="log">idle</pre></div>

<script>
const $=id=>document.getElementById(id);
async function fresh(){$('fbadge').textContent='checking…';$('fbadge').className='badge busy';
 const r=await(await fetch('/api/freshness?mode=monthly')).json();
 $('fout').style.display='block';$('fout').textContent=r.text;
 $('fbadge').textContent=r.ok?'ALL CLEAR':'BLOCKED';$('fbadge').className='badge '+(r.ok?'ok':'bad');}
async function run(mode){
 const m=$('month').value.trim(), f=$('force').checked?1:0;
 const r=await(await fetch(`/api/run?mode=${mode}&month=${m}&force=${f}`,{method:'POST'})).json();
 if(!r.started){alert('A run is already in progress');return;} poll();}
async function poll(){
 const s=await(await fetch('/api/status')).json();
 $('log').textContent=s.log.join('\\n')||'idle'; $('log').scrollTop=$('log').scrollHeight;
 $('bw').disabled=s.running;$('bm').disabled=s.running;
 if(s.running){$('rbadge').textContent='running '+s.label;$('rbadge').className='badge busy';setTimeout(poll,1500);}
 else if(s.exit!==null){$('rbadge').textContent=(s.exit===0?'done ':'FAILED ')+s.label;$('rbadge').className='badge '+(s.exit===0?'ok':'bad');}}
poll();
</script></body></html>"""

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, body, ctype='application/json'):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code); self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == '/': return self._send(200, PAGE, 'text/html; charset=utf-8')
        if u.path == '/api/status':
            return self._send(200, json.dumps(dict(running=STATE['running'], exit=STATE['exit'],
                                                   label=STATE['label'], log=STATE['log'][-400:])))
        if u.path == '/api/freshness':
            mode = parse_qs(u.query).get('mode', ['monthly'])[0]
            return self._send(200, json.dumps(freshness(mode)))
        self._send(404, '{}')
    def do_POST(self):
        u = urlparse(self.path)
        if u.path == '/api/run':
            q = parse_qs(u.query)
            started = start_run(q.get('mode', ['monthly'])[0],
                                q.get('month', [''])[0] or None,
                                q.get('force', ['0'])[0] == '1')
            return self._send(200, json.dumps(dict(started=started)))
        self._send(404, '{}')

if __name__ == '__main__':
    print(f"WSM Monitor dashboard -> http://localhost:{PORT}")
    HTTPServer(('127.0.0.1', PORT), H).serve_forever()
