"""
backup.py - Zororo Phumulani Database Backup
Runs as Railway cron job. Schedule: 0 2 * * *
Start Command: python backup.py
"""
import os, ssl, smtplib, sqlite3, logging
from pathlib import Path
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("backup")
BASE_DIR = Path(os.path.abspath(__file__)).parent
DB_PATH  = BASE_DIR / "zororo.db"

def backup_db():
    smtp_host = os.environ.get("SMTP_HOST", "mail.zororo-phumulani.co.za")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    to_addr   = os.environ.get("NOTIFY_EMAIL", "mike.ncube@zororophumulani.co.za")
    if not smtp_user or not smtp_pass or not DB_PATH.exists():
        log.error("Missing SMTP credentials or DB file"); return
    db_bytes = DB_PATH.read_bytes()
    today    = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    filename = f"zororo_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db"
    msg = MIMEMultipart("mixed")
    msg["From"] = smtp_user; msg["To"] = to_addr
    msg["Subject"] = f"[BACKUP] Zororo DB - {today}"
    msg.attach(MIMEText(f"<html><body><p>Daily backup. Size: {len(db_bytes)//1024} KB. File: {filename}</p></body></html>", "html"))
    part = MIMEBase("application", "octet-stream")
    part.set_payload(db_bytes); encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
    msg.attach(part)
    try:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ssl.create_default_context()) as s:
            s.login(smtp_user, smtp_pass)
            s.sendmail(smtp_user, to_addr, msg.as_string())
        log.info(f"Backup sent to {to_addr}")
    except Exception as e:
        log.error(f"Backup failed: {e}")

if __name__ == "__main__":
    backup_db()
