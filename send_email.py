"""Send the consolidated monthly email (Phase 3b). Credential-agnostic SMTP — works with
Ajay's theme-report sender creds OR an alias app-password, supplied via env vars only:
    WSM_SMTP_USER   (login, e.g. the account that may send as the alias)   [required]
    WSM_SMTP_PASS   (app password)                                          [required]
    WSM_SMTP_HOST   default smtp.zoho.in
    WSM_SMTP_PORT   default 465 (SSL)
    WSM_MAIL_FROM   default the alias from config.yaml (needs send-as rights on the login)
Usage:
    python3 build_email.py                  # generate body first
    python3 send_email.py --dry-run         # show what would be sent
    python3 send_email.py                   # send (attaches the workbook)
"""
import os, sys, json, argparse, smtplib, ssl
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wsm_cfg import CUR, OUT, WEEKLY_DIR, EMAIL
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

ap = argparse.ArgumentParser()
ap.add_argument('--dry-run', action='store_true')
ap.add_argument('--no-attach', action='store_true')
a = ap.parse_args()

meta_path = os.path.join(os.path.dirname(WEEKLY_DIR), 'Email', f'wsm_monthly_{CUR}.json')
if not os.path.exists(meta_path):
    sys.exit(f"No email body for {CUR}. Run build_email.py first.")
meta = json.load(open(meta_path))
body = open(meta['html']).read()

HOST = os.environ.get('WSM_SMTP_HOST', 'smtp.zoho.in')
PORT = int(os.environ.get('WSM_SMTP_PORT', '465'))
USER = os.environ.get('WSM_SMTP_USER')
PASS = os.environ.get('WSM_SMTP_PASS')
FROM = os.environ.get('WSM_MAIL_FROM', EMAIL['to'])
TO = meta['to']

msg = MIMEMultipart('mixed')
msg['Subject'] = meta['subject']; msg['From'] = f"WSM Monitor <{FROM}>"; msg['To'] = TO
msg.attach(MIMEText(body, 'html', 'utf-8'))
attached = None
if not a.no_attach and os.path.exists(OUT):
    part = MIMEBase('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    part.set_payload(open(OUT, 'rb').read()); encoders.encode_base64(part)
    fname = os.path.basename(OUT)
    part.add_header('Content-Disposition', f'attachment; filename="{fname}"')
    msg.attach(part); attached = fname

print(f"[mail] subject : {meta['subject']}")
print(f"[mail] from    : {msg['From']}")
print(f"[mail] to      : {TO}")
print(f"[mail] body    : {len(body):,} bytes html | attach: {attached or 'none'}")
print(f"[mail] via     : {HOST}:{PORT} as {USER or '<WSM_SMTP_USER not set>'}")
if a.dry_run:
    print("[dry-run] nothing sent."); sys.exit(0)
if not USER or not PASS:
    sys.exit("Set WSM_SMTP_USER / WSM_SMTP_PASS (app password) to send. See docstring.")
with smtplib.SMTP_SSL(HOST, PORT, context=ssl.create_default_context()) as s:
    s.login(USER, PASS)
    s.sendmail(FROM, [TO], msg.as_string())
print("[ok] sent.")
