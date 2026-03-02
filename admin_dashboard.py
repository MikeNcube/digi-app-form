"""
Zororo Phumulani — Admin Analytics & Monitoring Dashboard
=========================================================
Completely separate module — mounts onto the main FastAPI app
as an APIRouter. Zero modification to application logic.

Routes added:
  GET  /admin/dashboard        ← Dashboard UI (password-protected)
  POST /admin/login            ← Authentication
  GET  /admin/logout           ← Clear session
  POST /api/analytics/event    ← Event tracking (called from form JS)
  GET  /admin/api/overview     ← Summary metrics
  GET  /admin/api/submissions  ← Paginated submissions table
  GET  /admin/api/abandoned    ← Abandoned sessions
  GET  /admin/api/events       ← Event log with filters
  GET  /admin/api/health       ← System health checks
  GET  /admin/api/anomalies    ← Anomaly detection
  GET  /admin/api/export/csv   ← CSV export

Analytics DB: analytics.db (separate from zororo.db)
Auth: session token in cookie (ADMIN_PASS environment variable)
"""

import os
import json
import time
import hmac
import hashlib
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, Response, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

# ── PATHS ────────────────────────────────────────────────────────
BASE_DIR       = Path(os.path.abspath(__file__)).parent
ANALYTICS_DB   = str(BASE_DIR / "analytics.db")
MAIN_DB        = str(BASE_DIR / "zororo.db")
TEMPLATES_DIR  = BASE_DIR / "templates"

# ── CONFIG ───────────────────────────────────────────────────────
ADMIN_PASS     = os.environ.get("ADMIN_PASS", "ZoroAdmin2025!")
SESSION_SECRET = os.environ.get("SESSION_SECRET", "zororo-dash-secret-key-2025")
SESSION_TTL    = 8 * 3600   # 8 hours

router = APIRouter()

# ── ANALYTICS DATABASE ───────────────────────────────────────────
def init_analytics_db():
    conn = sqlite3.connect(ANALYTICS_DB)
    c = conn.cursor()
    # Event log — every trackable user action
    c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            ts            TEXT    NOT NULL,
            session_id    TEXT,
            masked_ip     TEXT,
            country       TEXT,
            event_type    TEXT    NOT NULL,
            step          INTEGER,
            field         TEXT,
            detail        TEXT,
            user_agent    TEXT
        )
    """)
    # Session tracking — one row per form session
    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id    TEXT    PRIMARY KEY,
            started_at    TEXT    NOT NULL,
            last_seen_at  TEXT    NOT NULL,
            country       TEXT,
            max_step      INTEGER DEFAULT 0,
            completed     INTEGER DEFAULT 0,
            policy_number TEXT,
            masked_ip     TEXT
        )
    """)
    # System health snapshots — recorded periodically
    c.execute("""
        CREATE TABLE IF NOT EXISTS health_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            ts            TEXT    NOT NULL,
            db_ok         INTEGER DEFAULT 1,
            db_rows       INTEGER DEFAULT 0,
            smtp_ok       INTEGER DEFAULT 0,
            fx_ok         INTEGER DEFAULT 0,
            pdf_ok        INTEGER DEFAULT 0,
            emails_sent_24h  INTEGER DEFAULT 0,
            emails_failed_24h INTEGER DEFAULT 0
        )
    """)
    # Anomaly log
    c.execute("""
        CREATE TABLE IF NOT EXISTS anomalies (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            ts            TEXT    NOT NULL,
            anomaly_type  TEXT    NOT NULL,
            severity      TEXT    DEFAULT 'warning',
            detail        TEXT,
            masked_ip     TEXT,
            resolved      INTEGER DEFAULT 0
        )
    """)
    # Admin audit log
    c.execute("""
        CREATE TABLE IF NOT EXISTS admin_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            ts            TEXT    NOT NULL,
            action        TEXT    NOT NULL,
            masked_ip     TEXT,
            detail        TEXT
        )
    """)
    conn.commit()
    conn.close()

init_analytics_db()

# ── HELPERS ──────────────────────────────────────────────────────
def mask_ip(ip: str) -> str:
    """Mask last octet of IPv4 for POPIA compliance."""
    if not ip:
        return "unknown"
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.{parts[2]}.xxx"
    return ip[:8] + "..."

def make_token(user: str) -> str:
    expires = int(time.time()) + SESSION_TTL
    payload = f"{user}:{expires}"
    sig = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"

def verify_token(token: str) -> bool:
    try:
        parts = token.rsplit(":", 1)
        if len(parts) != 2:
            return False
        payload, sig = parts
        expected = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return False
        _, expires = payload.rsplit(":", 1)
        return int(time.time()) < int(expires)
    except Exception:
        return False

def require_auth(request: Request):
    token = request.cookies.get("adm_token", "")
    if not token or not verify_token(token):
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})
    return True

def log_event_async(data: dict):
    """Write analytics event in background thread — no overhead on request."""
    def _write():
        try:
            conn = sqlite3.connect(ANALYTICS_DB)
            conn.execute("""
                INSERT INTO events (ts, session_id, masked_ip, country,
                                    event_type, step, field, detail, user_agent)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                datetime.now().isoformat(),
                data.get("session_id"),
                mask_ip(data.get("ip", "")),
                data.get("country"),
                data.get("event_type"),
                data.get("step"),
                data.get("field"),
                data.get("detail"),
                data.get("user_agent"),
            ))
            conn.commit()
            conn.close()
        except Exception:
            pass  # Analytics must never crash the main app
    threading.Thread(target=_write, daemon=True).start()

def upsert_session_async(data: dict):
    """Update session record in background — non-blocking."""
    def _write():
        try:
            conn = sqlite3.connect(ANALYTICS_DB)
            existing = conn.execute(
                "SELECT max_step, completed FROM sessions WHERE session_id=?",
                (data["session_id"],)
            ).fetchone()
            now = datetime.now().isoformat()
            if existing:
                new_step = max(existing[0] or 0, data.get("step", 0))
                completed = existing[1] or data.get("completed", 0)
                conn.execute("""
                    UPDATE sessions SET last_seen_at=?, max_step=?, completed=?,
                    country=?, policy_number=?
                    WHERE session_id=?
                """, (now, new_step, completed,
                      data.get("country"), data.get("policy_number"),
                      data["session_id"]))
            else:
                conn.execute("""
                    INSERT INTO sessions (session_id, started_at, last_seen_at,
                                          country, max_step, completed, masked_ip)
                    VALUES (?,?,?,?,?,?,?)
                """, (data["session_id"], now, now,
                      data.get("country"),
                      data.get("step", 0),
                      data.get("completed", 0),
                      mask_ip(data.get("ip", ""))))
            conn.commit()
            conn.close()
        except Exception:
            pass
    threading.Thread(target=_write, daemon=True).start()

def check_anomalies_async(event_type: str, ip: str, session_id: str):
    """Run anomaly detection in background."""
    def _check():
        try:
            conn = sqlite3.connect(ANALYTICS_DB)
            now  = datetime.now()
            m5   = (now - timedelta(minutes=5)).isoformat()
            m1   = (now - timedelta(minutes=1)).isoformat()
            masked = mask_ip(ip)

            # Rapid submissions from same IP
            rapid = conn.execute(
                "SELECT COUNT(*) FROM events WHERE masked_ip=? AND event_type='form_submitted' AND ts > ?",
                (masked, m5)
            ).fetchone()[0]
            if rapid >= 3:
                conn.execute(
                    "INSERT INTO anomalies (ts, anomaly_type, severity, detail, masked_ip) VALUES (?,?,?,?,?)",
                    (now.isoformat(), "rapid_submissions", "high",
                     f"{rapid} submissions from {masked} in 5 minutes", masked)
                )

            # Repeated validation bypass
            bypass = conn.execute(
                "SELECT COUNT(*) FROM events WHERE masked_ip=? AND event_type='validation_error' AND ts > ?",
                (masked, m5)
            ).fetchone()[0]
            if bypass >= 10:
                conn.execute(
                    "INSERT INTO anomalies (ts, anomaly_type, severity, detail, masked_ip) VALUES (?,?,?,?,?)",
                    (now.isoformat(), "validation_bypass_attempt", "medium",
                     f"{bypass} validation errors from {masked} in 5 minutes", masked)
                )

            # Unusual spike — many form starts in 1 min
            spike = conn.execute(
                "SELECT COUNT(DISTINCT session_id) FROM events WHERE event_type='form_started' AND ts > ?",
                (m1,)
            ).fetchone()[0]
            if spike >= 10:
                conn.execute(
                    "INSERT INTO anomalies (ts, anomaly_type, severity, detail, masked_ip) VALUES (?,?,?,?,?)",
                    (now.isoformat(), "submission_spike", "medium",
                     f"{spike} new form sessions started in the last 1 minute", "multiple")
                )

            conn.commit()
            conn.close()
        except Exception:
            pass
    threading.Thread(target=_check, daemon=True).start()


# ── PYDANTIC MODELS ──────────────────────────────────────────────
class LoginRequest(BaseModel):
    password: str

class EventPayload(BaseModel):
    session_id: str
    event_type: str
    step:       Optional[int]   = None
    field:      Optional[str]   = None
    detail:     Optional[str]   = None
    country:    Optional[str]   = None


# ── AUTH ROUTES ──────────────────────────────────────────────────
@router.get("/admin/login", response_class=HTMLResponse)
async def login_page():
    return HTMLResponse(_login_html())

@router.post("/admin/login")
async def do_login(req: LoginRequest, request: Request, response: Response):
    if req.password != ADMIN_PASS:
        # Log failed attempt
        threading.Thread(
            target=lambda: _audit("failed_login", mask_ip(request.client.host if request.client else ""), "Wrong password"),
            daemon=True
        ).start()
        raise HTTPException(401, "Invalid password")
    token = make_token("admin")
    resp  = JSONResponse({"ok": True})
    resp.set_cookie("adm_token", token, httponly=True, samesite="strict",
                    max_age=SESSION_TTL)
    threading.Thread(
        target=lambda: _audit("login_success", mask_ip(request.client.host if request.client else ""), "Admin logged in"),
        daemon=True
    ).start()
    return resp

@router.get("/admin/logout")
async def logout(response: Response):
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("adm_token")
    return resp


# ── EVENT TRACKING ───────────────────────────────────────────────
@router.post("/api/analytics/event")
async def track_event(payload: EventPayload, request: Request):
    """
    Called from the form JS on every trackable user action.
    Completely async — returns immediately, writes in background.
    """
    ip = request.headers.get("x-forwarded-for", "")
    if ip:
        ip = ip.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else ""

    ua = request.headers.get("user-agent", "")[:200]

    log_event_async({
        "session_id": payload.session_id,
        "event_type": payload.event_type,
        "step":       payload.step,
        "field":      payload.field,
        "detail":     payload.detail,
        "country":    payload.country,
        "ip":         ip,
        "user_agent": ua,
    })
    upsert_session_async({
        "session_id":    payload.session_id,
        "step":          payload.step or 0,
        "country":       payload.country,
        "ip":            ip,
        "completed":     1 if payload.event_type == "form_submitted" else 0,
        "policy_number": payload.detail if payload.event_type == "form_submitted" else None,
    })
    check_anomalies_async(payload.event_type, ip, payload.session_id)
    return {"ok": True}


# ── ADMIN API ROUTES ─────────────────────────────────────────────
@router.get("/admin/api/overview")
async def api_overview(_: bool = Depends(require_auth)):
    conn_m = sqlite3.connect(MAIN_DB)
    conn_a = sqlite3.connect(ANALYTICS_DB)
    now    = datetime.now()
    today  = now.strftime("%Y-%m-%d")
    week   = (now - timedelta(days=7)).isoformat()
    month  = (now - timedelta(days=30)).isoformat()
    day    = (now - timedelta(days=1)).isoformat()

    def mq(sql, *args):
        return conn_m.execute(sql, args).fetchone()[0]

    def aq(sql, *args):
        return conn_a.execute(sql, args).fetchone()[0]

    total       = mq("SELECT COUNT(*) FROM policies")
    today_c     = mq("SELECT COUNT(*) FROM policies WHERE submitted_at LIKE ?", today + "%")
    week_c      = mq("SELECT COUNT(*) FROM policies WHERE submitted_at > ?", week)
    month_c     = mq("SELECT COUNT(*) FROM policies WHERE submitted_at > ?", month)
    pdf_ok      = mq("SELECT COUNT(*) FROM policies WHERE pdf_generated=1")
    email_ok    = mq("SELECT COUNT(*) FROM policies WHERE emails_sent > 0")
    email_full  = mq("SELECT COUNT(*) FROM policies WHERE emails_sent >= 2")
    email_fail  = mq("SELECT COUNT(*) FROM policies WHERE emails_sent=0")
    avg_prem    = conn_m.execute("SELECT AVG(total_premium) FROM policies").fetchone()[0] or 0
    total_prem  = conn_m.execute("SELECT SUM(total_premium) FROM policies").fetchone()[0] or 0

    # Plan distribution
    plans = conn_m.execute("""
        SELECT plan, COUNT(*) FROM policies GROUP BY plan
    """).fetchall()

    # Country distribution
    countries = conn_m.execute("""
        SELECT country, COUNT(*) FROM policies GROUP BY country ORDER BY COUNT(*) DESC LIMIT 10
    """).fetchall()

    # Daily submissions for last 30 days
    daily = conn_m.execute("""
        SELECT substr(submitted_at,1,10) as day, COUNT(*) as cnt
        FROM policies WHERE submitted_at > ?
        GROUP BY day ORDER BY day
    """, (month,)).fetchall()

    # Sessions
    sessions_total    = aq("SELECT COUNT(*) FROM sessions")
    sessions_complete = aq("SELECT COUNT(*) FROM sessions WHERE completed=1")
    sessions_abandon  = sessions_total - sessions_complete
    conv_rate = round((sessions_complete / sessions_total * 100), 1) if sessions_total > 0 else 0

    # Avg step abandoned at
    avg_abandon_step = conn_a.execute("""
        SELECT AVG(max_step) FROM sessions WHERE completed=0 AND max_step > 0
    """).fetchone()[0] or 0

    # Event counts last 24h
    events_24h = aq("SELECT COUNT(*) FROM events WHERE ts > ?", day)
    errors_24h = aq("SELECT COUNT(*) FROM events WHERE event_type='validation_error' AND ts > ?", day)

    # Anomaly count
    open_anomalies = aq("SELECT COUNT(*) FROM anomalies WHERE resolved=0")

    conn_m.close()
    conn_a.close()

    return {
        "submissions": {
            "total": total, "today": today_c,
            "this_week": week_c, "this_month": month_c
        },
        "financials": {
            "avg_premium": round(avg_prem, 2),
            "total_premium_value": round(total_prem, 2)
        },
        "emails": {
            "at_least_one_sent": email_ok,
            "all_sent": email_full,
            "zero_sent": email_fail,
            "success_rate": round(email_ok / total * 100, 1) if total else 0
        },
        "pdf": {
            "generated": pdf_ok,
            "failed": total - pdf_ok,
            "rate": round(pdf_ok / total * 100, 1) if total else 0
        },
        "sessions": {
            "total": sessions_total,
            "completed": sessions_complete,
            "abandoned": sessions_abandon,
            "conversion_rate": conv_rate,
            "avg_abandon_step": round(avg_abandon_step, 1)
        },
        "events": {"last_24h": events_24h, "errors_24h": errors_24h},
        "anomalies": {"open": open_anomalies},
        "charts": {
            "daily_submissions": [{"date": r[0], "count": r[1]} for r in daily],
            "plan_distribution": [{"plan": r[0] or "unknown", "count": r[1]} for r in plans],
            "country_distribution": [{"country": r[0] or "unknown", "count": r[1]} for r in countries],
        }
    }


@router.get("/admin/api/submissions")
async def api_submissions(
    page: int = 1, per_page: int = 20,
    plan: str = "", country: str = "", search: str = "",
    _: bool = Depends(require_auth)
):
    conn = sqlite3.connect(MAIN_DB)
    conn.row_factory = sqlite3.Row
    offset = (page - 1) * per_page

    where, params = [], []
    if plan:
        where.append("plan=?");    params.append(plan)
    if country:
        where.append("country=?"); params.append(country)
    if search:
        where.append("(main_member_name LIKE ? OR policy_number LIKE ? OR main_member_email LIKE ?)")
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]

    clause = ("WHERE " + " AND ".join(where)) if where else ""

    total = conn.execute(f"SELECT COUNT(*) FROM policies {clause}", params).fetchone()[0]
    rows  = conn.execute(f"""
        SELECT policy_number, submitted_at, main_member_name, main_member_email,
               country, plan, cover_type, total_premium, payment_method,
               agent_name, pdf_generated, emails_sent, signature_type,
               popia_consent, terms_accepted, passport_uploaded
        FROM policies {clause}
        ORDER BY id DESC LIMIT ? OFFSET ?
    """, params + [per_page, offset]).fetchall()
    conn.close()

    return {
        "total": total, "page": page, "per_page": per_page,
        "pages": max(1, (total + per_page - 1) // per_page),
        "rows": [dict(r) for r in rows]
    }


@router.get("/admin/api/submission/{ref}")
async def api_submission_detail(ref: str, _: bool = Depends(require_auth)):
    conn = sqlite3.connect(MAIN_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM policies WHERE policy_number=?", (ref,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Policy not found")
    result = dict(row)
    if result.get("raw_payload"):
        result["data"] = json.loads(result.pop("raw_payload"))
    # Redact sensitive fields for dashboard display
    if "data" in result and "main_member" in result["data"]:
        mm = result["data"]["main_member"]
        if mm.get("id_number"):
            mm["id_number"] = mm["id_number"][:4] + "****" + mm["id_number"][-2:]
    return result


@router.get("/admin/api/abandoned")
async def api_abandoned(_: bool = Depends(require_auth)):
    conn = sqlite3.connect(ANALYTICS_DB)
    conn.row_factory = sqlite3.Row
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
    rows = conn.execute("""
        SELECT session_id, started_at, last_seen_at, country,
               max_step, masked_ip,
               ROUND((julianday(last_seen_at) - julianday(started_at)) * 1440) as mins_spent
        FROM sessions
        WHERE completed=0 AND max_step > 0 AND started_at > ?
        ORDER BY last_seen_at DESC LIMIT 100
    """, (cutoff,)).fetchall()
    conn.close()

    step_names = {
        1: "Main Member", 2: "Documents", 3: "Cover & Plan",
        4: "Family", 5: "Payment", 6: "Declarations", 7: "Review & Sign"
    }

    result = []
    for r in rows:
        d = dict(r)
        d["last_step_name"] = step_names.get(d["max_step"], f"Step {d['max_step']}")
        result.append(d)
    return {"abandoned": result, "count": len(result)}


@router.get("/admin/api/events")
async def api_events(
    event_type: str = "", session_id: str = "",
    hours: int = 24, limit: int = 200,
    _: bool = Depends(require_auth)
):
    conn = sqlite3.connect(ANALYTICS_DB)
    conn.row_factory = sqlite3.Row
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

    where, params = ["ts > ?"], [cutoff]
    if event_type:
        where.append("event_type=?"); params.append(event_type)
    if session_id:
        where.append("session_id LIKE ?"); params.append(f"%{session_id}%")

    rows = conn.execute(f"""
        SELECT ts, session_id, masked_ip, country, event_type, step, field, detail
        FROM events WHERE {" AND ".join(where)}
        ORDER BY id DESC LIMIT ?
    """, params + [limit]).fetchall()

    # Hourly distribution
    hourly = conn.execute("""
        SELECT substr(ts,1,13) as hr, COUNT(*) FROM events WHERE ts > ?
        GROUP BY hr ORDER BY hr
    """, (cutoff,)).fetchall()

    # Error breakdown
    errors = conn.execute("""
        SELECT field, COUNT(*) as cnt FROM events
        WHERE event_type='validation_error' AND ts > ?
        GROUP BY field ORDER BY cnt DESC LIMIT 20
    """, (cutoff,)).fetchall()

    conn.close()
    return {
        "events":  [dict(r) for r in rows],
        "hourly":  [{"hour": r[0], "count": r[1]} for r in hourly],
        "top_errors": [{"field": r[0] or "unknown", "count": r[1]} for r in errors],
        "count":   len(rows)
    }


@router.get("/admin/api/health")
async def api_health(_: bool = Depends(require_auth)):
    results = {}
    now = datetime.now().isoformat()

    # Database health
    try:
        conn = sqlite3.connect(MAIN_DB)
        rows = conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0]
        conn.close()
        results["database"] = {"status": "healthy", "icon": "🟢",
                                "detail": f"{rows} policies stored", "rows": rows}
    except Exception as e:
        results["database"] = {"status": "critical", "icon": "🔴", "detail": str(e)}

    # SMTP configuration
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    if smtp_user and smtp_pass:
        results["smtp"] = {"status": "configured", "icon": "🟢",
                           "detail": f"Configured as {smtp_user}"}
    else:
        results["smtp"] = {"status": "warning", "icon": "🟡",
                           "detail": "SMTP credentials not set in environment"}

    # PDF library
    try:
        from reportlab.lib.pagesizes import A4
        results["pdf_engine"] = {"status": "healthy", "icon": "🟢",
                                  "detail": "ReportLab available"}
    except ImportError:
        results["pdf_engine"] = {"status": "critical", "icon": "🔴",
                                  "detail": "ReportLab not installed"}

    # Exchange rate API (lightweight check)
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://open.er-api.com/v6/latest/ZAR",
            headers={"User-Agent": "ZororoHealth/1.0"}
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read())
            if data.get("result") == "success":
                results["fx_api"] = {"status": "healthy", "icon": "🟢",
                                      "detail": f"Live rates available · Updated {data.get('time_last_update_utc','')[:16]}"}
            else:
                results["fx_api"] = {"status": "warning", "icon": "🟡",
                                      "detail": "API reachable but returned non-success"}
    except Exception as e:
        results["fx_api"] = {"status": "warning", "icon": "🟡",
                              "detail": f"Fallback rates in use ({str(e)[:60]})"}

    # Email stats last 24h
    try:
        conn_m = sqlite3.connect(MAIN_DB)
        day    = (datetime.now() - timedelta(days=1)).isoformat()
        sent   = conn_m.execute("SELECT COUNT(*) FROM policies WHERE emails_sent > 0 AND submitted_at > ?", (day,)).fetchone()[0]
        failed = conn_m.execute("SELECT COUNT(*) FROM policies WHERE emails_sent = 0 AND submitted_at > ?", (day,)).fetchone()[0]
        conn_m.close()
        icon = "🟢" if failed == 0 else ("🟡" if failed < 3 else "🔴")
        results["email_delivery"] = {
            "status": "healthy" if failed == 0 else "warning",
            "icon": icon,
            "detail": f"{sent} delivered, {failed} failed in last 24h",
            "sent_24h": sent, "failed_24h": failed
        }
    except Exception as e:
        results["email_delivery"] = {"status": "unknown", "icon": "🟡", "detail": str(e)}

    # Anomaly summary
    try:
        conn_a = sqlite3.connect(ANALYTICS_DB)
        open_a = conn_a.execute("SELECT COUNT(*) FROM anomalies WHERE resolved=0").fetchone()[0]
        conn_a.close()
        icon = "🟢" if open_a == 0 else ("🟡" if open_a < 5 else "🔴")
        results["anomaly_monitor"] = {
            "status": "healthy" if open_a == 0 else "warning",
            "icon": icon,
            "detail": f"{open_a} open anomaly alert(s)"
        }
    except Exception:
        results["anomaly_monitor"] = {"status": "unknown", "icon": "🟡", "detail": "Analytics DB unavailable"}

    return {"health": results, "timestamp": now}


@router.get("/admin/api/anomalies")
async def api_anomalies(_: bool = Depends(require_auth)):
    conn = sqlite3.connect(ANALYTICS_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, ts, anomaly_type, severity, detail, masked_ip, resolved
        FROM anomalies ORDER BY id DESC LIMIT 100
    """).fetchall()
    conn.close()

    severity_icons = {"high": "🔴", "medium": "🟡", "low": "🟢", "info": "ℹ️"}
    result = []
    for r in rows:
        d = dict(r)
        d["icon"] = severity_icons.get(d["severity"], "🟡")
        result.append(d)
    return {"anomalies": result, "count": len(result)}


@router.post("/admin/api/anomaly/{anomaly_id}/resolve")
async def resolve_anomaly(anomaly_id: int, _: bool = Depends(require_auth)):
    conn = sqlite3.connect(ANALYTICS_DB)
    conn.execute("UPDATE anomalies SET resolved=1 WHERE id=?", (anomaly_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/admin/api/export/csv")
async def export_csv(days: int = 30, _: bool = Depends(require_auth)):
    conn = sqlite3.connect(MAIN_DB)
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    rows = conn.execute("""
        SELECT policy_number, submitted_at, main_member_name, country,
               plan, cover_type, total_premium, payment_method,
               agent_name, pdf_generated, emails_sent, signature_type
        FROM policies WHERE submitted_at > ?
        ORDER BY submitted_at DESC
    """, (cutoff,)).fetchall()
    conn.close()

    import io, csv
    buf = io.StringIO()
    w   = csv.writer(buf)
    w.writerow(["Policy Number","Submitted At","Applicant Name","Country",
                "Plan","Cover Type","Total Premium (ZAR)","Payment Method",
                "Agent","PDF Generated","Emails Sent","Signature Type"])
    for r in rows:
        w.writerow(r)

    buf.seek(0)
    filename = f"zororo_submissions_{datetime.now().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ── MAIN DASHBOARD ROUTE ─────────────────────────────────────────
@router.get("/admin/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    token = request.cookies.get("adm_token", "")
    if not token or not verify_token(token):
        return HTMLResponse(_login_html())
    return HTMLResponse(content=(TEMPLATES_DIR / "admin.html").read_text(encoding="utf-8"))


# ── ADMIN AUDIT HELPER ───────────────────────────────────────────
def _audit(action: str, masked_ip: str, detail: str = ""):
    try:
        conn = sqlite3.connect(ANALYTICS_DB)
        conn.execute(
            "INSERT INTO admin_log (ts, action, masked_ip, detail) VALUES (?,?,?,?)",
            (datetime.now().isoformat(), action, masked_ip, detail)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# ── LOGIN PAGE HTML ──────────────────────────────────────────────
def _login_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Admin Login — Zororo Phumulani</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{
    min-height:100vh;display:flex;align-items:center;justify-content:center;
    background:#060d1a;
    background-image:radial-gradient(ellipse at 20% 50%,rgba(36,86,164,.25) 0%,transparent 60%),
                     radial-gradient(ellipse at 80% 20%,rgba(232,160,32,.12) 0%,transparent 50%);
    font-family:'DM Sans',sans-serif;
  }
  .box{
    background:rgba(255,255,255,.04);
    border:1px solid rgba(255,255,255,.08);
    border-radius:20px;
    padding:48px 44px 44px;
    width:100%;max-width:400px;
    backdrop-filter:blur(20px);
    box-shadow:0 32px 80px rgba(0,0,0,.5);
  }
  .logo{
    width:48px;height:48px;border-radius:12px;
    background:linear-gradient(135deg,#2456a4,#e8a020);
    display:flex;align-items:center;justify-content:center;
    font-size:22px;margin-bottom:24px;
  }
  h1{color:#fff;font-size:1.4rem;font-weight:600;margin-bottom:6px}
  .sub{color:rgba(255,255,255,.4);font-size:.84rem;margin-bottom:32px}
  label{display:block;color:rgba(255,255,255,.6);font-size:.78rem;
        font-weight:500;letter-spacing:.06em;text-transform:uppercase;margin-bottom:8px}
  input[type=password]{
    width:100%;padding:13px 16px;border-radius:10px;
    border:1.5px solid rgba(255,255,255,.1);
    background:rgba(255,255,255,.06);color:#fff;
    font-family:'DM Mono',monospace;font-size:.9rem;
    outline:none;transition:border-color .2s;
  }
  input[type=password]:focus{border-color:#2456a4}
  input[type=password]::placeholder{color:rgba(255,255,255,.2)}
  button{
    margin-top:20px;width:100%;padding:14px;border:none;border-radius:10px;
    background:linear-gradient(135deg,#2456a4,#1a3a6e);
    color:#fff;font-family:'DM Sans',sans-serif;font-size:.92rem;font-weight:600;
    cursor:pointer;transition:opacity .2s;
  }
  button:hover{opacity:.88}
  .err{color:#ff6b6b;font-size:.8rem;margin-top:12px;display:none;text-align:center}
  .footer{margin-top:28px;text-align:center;color:rgba(255,255,255,.2);font-size:.74rem}
</style>
</head>
<body>
<div class="box">
  <div class="logo">🛡️</div>
  <h1>Admin Access</h1>
  <p class="sub">Zororo Phumulani · Analytics Dashboard</p>
  <label for="pw">Password</label>
  <input type="password" id="pw" placeholder="Enter admin password" autofocus/>
  <button onclick="login()">Sign In →</button>
  <p class="err" id="err">Incorrect password. Please try again.</p>
  <p class="footer">Restricted access · POPIA compliant · All access logged</p>
</div>
<script>
async function login(){
  const pw=document.getElementById('pw').value;
  if(!pw)return;
  const r=await fetch('/admin/login',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({password:pw})});
  if(r.ok){window.location='/admin/dashboard';}
  else{document.getElementById('err').style.display='block';}
}
document.getElementById('pw').addEventListener('keydown',e=>{if(e.key==='Enter')login();});
</script>
</body>
</html>"""
