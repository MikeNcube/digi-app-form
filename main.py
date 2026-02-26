"""
Zororo Phumulani — Digital Policy Application System v3.0
==========================================================
FastAPI · SQLite · ReportLab PDF · SMTP SSL (port 465)
POPIA Compliant · FSP48558 · Underwritten by KGA Life FSP15980

SMTP:  mail.zororo-phumulani.co.za  port 465  SSL
FROM:  nomthandazo.wwfp@zororo-phumulani.co.za

Environment variables required in Railway:
  SMTP_HOST     = mail.zororo-phumulani.co.za
  SMTP_PORT     = 465
  SMTP_USER     = nomthandazo.wwfp@zororo-phumulani.co.za
  SMTP_PASS     = SPA7MW6AOYG4AVLQ
  NOTIFY_EMAIL  = mike.ncube@zororophumulani.co.za
"""

import os
import json
import uuid
import base64
import smtplib
import logging
import sqlite3
import ssl
from io import BytesIO
from datetime import datetime, date
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from typing import Optional, List
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image as RLImage, KeepTogether, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

# ─── PATHS ─────────────────────────────────────────────────────
BASE_DIR      = Path(os.path.abspath(__file__)).parent
DB_PATH       = str(BASE_DIR / "zororo.db")
UPLOAD_DIR    = BASE_DIR / "uploads"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR    = BASE_DIR / "static"
UPLOAD_DIR.mkdir(exist_ok=True)

# ─── LOGGING ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger(__name__)

# ─── T&C VERSION (bump when T&C text changes) ───────────────────
TC_VERSION = "WWF-TC-v2025.1"

# ─── BRAND COLOURS ──────────────────────────────────────────────
NAVY   = colors.HexColor("#0a1628")
BLUE   = colors.HexColor("#1a3a6e")
MID    = colors.HexColor("#2456a4")
ACCENT = colors.HexColor("#e8a020")
LTBLUE = colors.HexColor("#d6e4f7")
WHITE  = colors.white
GREY   = colors.HexColor("#6b7a99")
BGRAY  = colors.HexColor("#f5f7fb")
RED    = colors.HexColor("#c0392b")
GREEN  = colors.HexColor("#1a7a4a")

# ─── FASTAPI APP ────────────────────────────────────────────────
app = FastAPI(
    title="Zororo Phumulani Digital Application",
    version="3.0.0",
    docs_url=None,  # disable swagger in prod
    redoc_url=None
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ─── DATABASE ───────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS policies (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_number         TEXT UNIQUE NOT NULL,
            submitted_at          TEXT NOT NULL,
            submission_ip         TEXT,
            main_member_name      TEXT,
            main_member_email     TEXT,
            main_member_phone     TEXT,
            main_member_whatsapp  TEXT,
            country               TEXT,
            province              TEXT,
            postal_code           TEXT,
            plan                  TEXT,
            cover_type            TEXT,
            cover_amount          REAL,
            total_premium         REAL,
            payment_method        TEXT,
            agent_name            TEXT,
            popia_consent         INTEGER DEFAULT 0,
            terms_accepted        INTEGER DEFAULT 0,
            terms_accepted_at     TEXT,
            terms_version         TEXT,
            fais_accepted         INTEGER DEFAULT 0,
            signature_type        TEXT,
            fic_uploaded          INTEGER DEFAULT 0,
            passport_uploaded     INTEGER DEFAULT 0,
            raw_payload           TEXT,
            pdf_generated         INTEGER DEFAULT 0,
            emails_sent           INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()


def save_policy(policy_number: str, data: dict, ip: str) -> int:
    mm = data.get("main_member", {})
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO policies (
            policy_number, submitted_at, submission_ip,
            main_member_name, main_member_email, main_member_phone,
            main_member_whatsapp, country, province, postal_code,
            plan, cover_type, cover_amount, total_premium, payment_method,
            agent_name, popia_consent, terms_accepted, terms_accepted_at,
            terms_version, fais_accepted, signature_type,
            fic_uploaded, passport_uploaded, raw_payload
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        policy_number,
        datetime.now().isoformat(),
        ip,
        f"{mm.get('first_name','')} {mm.get('last_name','')}".strip(),
        mm.get("email", ""),
        mm.get("phone", ""),
        mm.get("whatsapp", ""),
        mm.get("country", ""),
        mm.get("province", ""),
        mm.get("postal_code", ""),
        data.get("plan_name", ""),
        data.get("cover_type", ""),
        data.get("cover_amount", 0),
        data.get("total_premium", 0),
        data.get("payment_method", ""),
        data.get("agent", {}).get("name", "") if data.get("agent") else "",
        1 if data.get("popia_consent") else 0,
        1 if data.get("terms_accepted") else 0,
        data.get("terms_accepted_at", ""),
        TC_VERSION,
        1 if data.get("fais_accepted") else 0,
        data.get("signature", {}).get("type", "") if data.get("signature") else "",
        1 if data.get("fic_uploaded") else 0,
        1 if data.get("passport_uploaded") else 0,
        json.dumps(data),
    ))
    row_id = c.lastrowid
    conn.commit()
    conn.close()
    return row_id


def generate_policy_number() -> str:
    ts  = datetime.now().strftime("%y%m")
    uid = str(uuid.uuid4()).upper()[:6]
    return f"ZP-{ts}-{uid}"


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ─── PYDANTIC MODELS ────────────────────────────────────────────
class MainMember(BaseModel):
    first_name:   str
    last_name:    str
    dob:          str
    gender:       Optional[str] = None
    nationality:  Optional[str] = None
    id_number:    str
    phone:        str
    whatsapp:     Optional[str] = None
    email:        str
    country:      Optional[str] = None
    country_code: Optional[str] = None
    province:     Optional[str] = None
    postal_code:  Optional[str] = None
    area_code:    Optional[str] = None
    address:      Optional[str] = None


class Dependant(BaseModel):
    first_name: str
    last_name:  str
    dob:        Optional[str]  = None
    gender:     Optional[str]  = None
    id_number:  Optional[str]  = None
    student:    Optional[bool] = False
    disabled:   Optional[bool] = False


class ExtendedFamilyMember(BaseModel):
    first_name:   str
    last_name:    str
    dob:          Optional[str] = None
    relationship: Optional[str] = None
    tier:         Optional[str] = None
    cover:        Optional[int] = 0
    premium:      Optional[int] = 0


class Beneficiary(BaseModel):
    first_name:   str
    last_name:    str
    phone:        str
    relationship: Optional[str] = None


class DebitOrder(BaseModel):
    account_holder:         Optional[str] = None
    account_holder_contact: Optional[str] = None
    bank:                   Optional[str] = None
    branch_code:            Optional[str] = None
    account_number:         Optional[str] = None
    account_type:           Optional[str] = None
    deduction_date:         Optional[str] = None
    commencement_date:      Optional[str] = None


class Declarations(BaseModel):
    has_other_policy:    Optional[bool]      = False
    other_policy_amount: Optional[str]       = None
    is_replacement:      Optional[bool]      = False
    income_range:        Optional[str]       = None
    num_dependants:      Optional[str]       = None
    monthly_expenses:    Optional[str]       = None
    available_cash:      Optional[str]       = None
    notifications:       Optional[List[str]] = []


class AgentDetails(BaseModel):
    name:        Optional[str] = None
    phone:       Optional[str] = None
    team_leader: Optional[str] = None
    province:    Optional[str] = None


class SignatureData(BaseModel):
    type: str             # digital | typed | photo
    data: Optional[str] = None   # base64 PNG
    name: Optional[str] = None   # typed name


class PolicyApplication(BaseModel):
    main_member:     MainMember
    spouse:          Optional[Dependant]              = None
    children:        Optional[List[Dependant]]        = []
    extended_family: Optional[List[ExtendedFamilyMember]] = []
    plan:            str
    plan_name:       str
    cover_type:      str
    cover_amount:    float
    base_premium:    float
    efm_premium:     float
    total_premium:   float
    beneficiary:     Beneficiary
    payment_method:  str
    debit_order:     Optional[DebitOrder]  = None
    declarations:    Optional[Declarations] = None
    agent:           Optional[AgentDetails] = None
    signature:       Optional[SignatureData] = None
    popia_consent:   bool = False
    terms_accepted:  bool = False
    terms_accepted_at: Optional[str] = None
    fais_accepted:   bool = False
    fic_uploaded:    bool = False
    passport_uploaded: bool = False
    submission_timestamp: Optional[str] = None


# ─── VALIDATION ─────────────────────────────────────────────────
def calc_age(dob_str: str) -> int:
    if not dob_str:
        return 0
    try:
        dob   = datetime.strptime(dob_str, "%Y-%m-%d").date()
        today = date.today()
        return (today.year - dob.year
                - ((today.month, today.day) < (dob.month, dob.day)))
    except Exception:
        return 0


def validate_application(data: PolicyApplication):
    # Age: 18 minimum enforced server-side
    mm_age = calc_age(data.main_member.dob)
    if mm_age < 18:
        raise HTTPException(400,
            f"Main member must be at least 18 years old (current age: {mm_age}).")
    if mm_age > 65:
        raise HTTPException(400,
            f"Main member age {mm_age} exceeds maximum entry age of 65.")

    # Family cover requires at least one dependant
    if data.cover_type == "family":
        has_deps = bool(data.spouse or (data.children and len(data.children) > 0))
        if not has_deps:
            raise HTTPException(400,
                "Family cover requires at least one dependant (spouse or child). "
                "Please add dependants or switch to Single cover.")

    # Document uploads mandatory
    if not data.fic_uploaded:
        raise HTTPException(400, "FIC document upload is required before submission.")
    if not data.passport_uploaded:
        raise HTTPException(400, "Passport / ID copy upload is required before submission.")

    # Consent gates
    if not data.popia_consent:
        raise HTTPException(400, "POPIA consent is required.")
    if not data.terms_accepted:
        raise HTTPException(400, "Terms & Conditions acceptance is required.")
    if not data.fais_accepted:
        raise HTTPException(400, "FAIS advice record acceptance is required.")

    # Spouse age
    if data.spouse:
        sp_age = calc_age(data.spouse.dob or "")
        if sp_age and (sp_age < 18 or sp_age > 65):
            raise HTTPException(400,
                f"Spouse age {sp_age} is outside permitted range 18–65.")

    # Children limits
    if data.children:
        if len(data.children) > 6:
            raise HTTPException(400, "Maximum 6 children allowed.")
        for i, ch in enumerate(data.children):
            ch_age  = calc_age(ch.dob or "")
            max_age = 25 if (ch.student or ch.disabled) else 21
            if ch_age and ch_age > max_age:
                raise HTTPException(400,
                    f"Child {i+1} age {ch_age} exceeds maximum {max_age}.")

    # Extended family
    if data.extended_family:
        if len(data.extended_family) > 6:
            raise HTTPException(400, "Maximum 6 extended family members allowed.")
        for i, efm in enumerate(data.extended_family):
            efm_age = calc_age(efm.dob or "")
            if efm_age and efm_age >= 90:
                raise HTTPException(400,
                    f"Extended family member {i+1} age {efm_age} exceeds maximum 89.")

    # Plan valid
    if data.plan not in ("premium", "prestige", "executive"):
        raise HTTPException(400, "Invalid plan selection.")


# ─── PDF GENERATION ─────────────────────────────────────────────
def build_pdf(data: PolicyApplication, policy_number: str, client_ip: str) -> bytes:
    buf = BytesIO()
    PAGE_W, PAGE_H = A4
    MARGIN = 15 * mm
    W = PAGE_W - 2 * MARGIN

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=22 * mm, bottomMargin=18 * mm,
        title=f"Zororo Phumulani Policy Application – {policy_number}",
        author="Zororo Phumulani Investments (Pty) Ltd",
        subject="Worldwide Funeral Plan Application",
    )

    # ── PARAGRAPH STYLES ─────────────────────────────────────────
    def S(name, **kw):
        return ParagraphStyle(name, **kw)

    BODY  = S("body",  fontName="Helvetica",       fontSize=9,   leading=13, textColor=NAVY)
    SMALL = S("small", fontName="Helvetica",       fontSize=7.5, leading=11, textColor=GREY)
    BOLD9 = S("bold9", fontName="Helvetica-Bold",  fontSize=9,   leading=13, textColor=NAVY)
    LABEL = S("label", fontName="Helvetica-Bold",  fontSize=7.5, leading=11, textColor=MID)
    SECW  = S("secw",  fontName="Helvetica-Bold",  fontSize=8.5, leading=12, textColor=WHITE)
    FOOT  = S("foot",  fontName="Helvetica",       fontSize=6.5, leading=10, textColor=GREY,
              alignment=TA_CENTER)
    POPIA_S = S("popia", fontName="Helvetica-Oblique", fontSize=7.5, leading=11,
                textColor=BLUE, spaceAfter=4)
    WARN  = S("warn",  fontName="Helvetica-Bold",  fontSize=7.5, leading=11, textColor=RED)

    today_str = datetime.now().strftime("%d %B %Y")
    time_str  = datetime.now().strftime("%H:%M:%S SAST")
    mm_       = data.main_member

    story = []

    # ── HELPER: section header bar ────────────────────────────────
    def sec_hdr(title):
        t = Table([[Paragraph(f"  {title.upper()}", SECW)]], colWidths=[W])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), MID),
            ("TOPPADDING",    (0,0),(-1,-1), 5),
            ("BOTTOMPADDING", (0,0),(-1,-1), 5),
            ("LEFTPADDING",   (0,0),(-1,-1), 6),
        ]))
        return t

    # ── HELPER: two-column key-value row ──────────────────────────
    def row2(k1, v1, k2=None, v2=None):
        cell1 = Paragraph(
            f'<font size="7.5" color="#2456a4"><b>{k1}</b></font><br/>'
            f'<font size="9" color="#1a1a2e">{v1 or "—"}</font>', BODY)
        if k2:
            cell2 = Paragraph(
                f'<font size="7.5" color="#2456a4"><b>{k2}</b></font><br/>'
                f'<font size="9" color="#1a1a2e">{v2 or "—"}</font>', BODY)
        else:
            cell2 = Paragraph("", BODY)
        return [cell1, cell2]

    def info_tbl(rows, cw=None):
        if cw is None:
            cw = [W/2, W/2]
        t = Table(rows, colWidths=cw)
        t.setStyle(TableStyle([
            ("VALIGN",         (0,0),(-1,-1), "TOP"),
            ("LEFTPADDING",    (0,0),(-1,-1), 6),
            ("RIGHTPADDING",   (0,0),(-1,-1), 6),
            ("TOPPADDING",     (0,0),(-1,-1), 5),
            ("BOTTOMPADDING",  (0,0),(-1,-1), 5),
            ("ROWBACKGROUNDS", (0,0),(-1,-1), [WHITE, BGRAY]),
            ("LINEABOVE",      (0,0),(-1,0),  0.5, colors.HexColor("#c8d6ea")),
            ("LINEBELOW",      (0,-1),(-1,-1),0.5, colors.HexColor("#c8d6ea")),
        ]))
        return t

    # ═══════════════════════════════════════════════════════
    # PAGE HEADER & FOOTER (called on every page by ReportLab)
    # ═══════════════════════════════════════════════════════
    def on_page(canvas, doc):
        canvas.saveState()
        # Accent stripe at top
        canvas.setFillColor(ACCENT)
        canvas.rect(0, PAGE_H - 4*mm, PAGE_W, 4*mm, fill=1, stroke=0)
        # Navy band
        canvas.setFillColor(NAVY)
        canvas.rect(0, PAGE_H - 14*mm, PAGE_W, 10*mm, fill=1, stroke=0)
        # Header text
        canvas.setFont("Helvetica-Bold", 11)
        canvas.setFillColor(WHITE)
        canvas.drawString(MARGIN, PAGE_H - 10.5*mm, "ZORORO PHUMULANI")
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#d6e4f7"))
        canvas.drawString(MARGIN, PAGE_H - 13.5*mm,
                          "Worldwide Funeral Plan  |  FSP48558  |  Underwritten by KGA Life FSP15980")
        # Policy number right-aligned
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(ACCENT)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 10.5*mm, policy_number)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#d6e4f7"))
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 13.5*mm,
                               f"Page {doc.page}  |  POPIA PROTECTED  |  CONFIDENTIAL")
        # Border
        canvas.setStrokeColor(colors.HexColor("#d6e4f7"))
        canvas.setLineWidth(0.5)
        canvas.rect(MARGIN - 2*mm, 14*mm, W + 4*mm, PAGE_H - 32*mm)
        # Footer
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(GREY)
        canvas.drawCentredString(
            PAGE_W / 2, 10*mm,
            "Zororo Phumulani Investments (Pty) Ltd  ·  FSP48558  ·  "
            "Office 102, 1st Floor Nzunza House, 28 Melle St, Braamfontein, Johannesburg  ·  "
            "+27 81 419 4980"
        )
        canvas.drawCentredString(
            PAGE_W / 2, 7*mm,
            "This document is POPIA-protected personal information. "
            "Handle and store with appropriate confidentiality controls."
        )
        canvas.restoreState()

    # ════════════════════════════════════════════════════════════
    # COVER BLOCK (title area)
    # ════════════════════════════════════════════════════════════
    story.append(Spacer(1, 2*mm))

    cover_data = [[
        Paragraph(
            '<font size="20" color="#0a1628"><b>POLICY APPLICATION FORM</b></font><br/>'
            '<font size="9" color="#6b7a99">Worldwide Funeral Plan – Digital Application</font>',
            BODY),
        Table([
            [Paragraph('<font size="7" color="#6b7a99">Policy Reference</font>', SMALL)],
            [Paragraph(f'<font size="14" color="#0a1628"><b>{policy_number}</b></font>', BODY)],
            [Paragraph(f'<font size="7" color="#6b7a99">Submitted: {today_str} at {time_str}</font>', SMALL)],
            [Paragraph(f'<font size="7" color="#6b7a99">T&amp;C Version: {TC_VERSION}</font>', SMALL)],
        ], colWidths=[W * 0.42])
    ]]
    cover_tbl = Table(cover_data, colWidths=[W * 0.58, W * 0.42])
    cover_tbl.setStyle(TableStyle([
        ("ALIGN",  (0,0),(0,0), "LEFT"),
        ("ALIGN",  (1,0),(1,0), "RIGHT"),
        ("VALIGN", (0,0),(-1,-1), "MIDDLE"),
        ("LINEBELOW", (0,0),(-1,0), 1.5, ACCENT),
        ("BOTTOMPADDING", (0,0),(-1,-1), 8),
    ]))
    story.append(cover_tbl)
    story.append(Spacer(1, 5*mm))

    # ════════════════════════════════════════════════════════════
    # SECTION 1 — MAIN MEMBER
    # ════════════════════════════════════════════════════════════
    story.append(sec_hdr("1.  Main Member Details"))
    story.append(Spacer(1, 2*mm))
    story.append(info_tbl([
        row2("Full Name",       f"{mm_.first_name} {mm_.last_name}",
             "Date of Birth",   f"{mm_.dob} (Age: {calc_age(mm_.dob)})"),
        row2("Gender",          mm_.gender,
             "Nationality",     mm_.nationality),
        row2("ID / Passport No.", mm_.id_number,
             "Contact Number",  mm_.phone),
        row2("WhatsApp Number", mm_.whatsapp or mm_.phone,
             "Email Address",   mm_.email),
        row2("Country",         mm_.country,
             "Province",        mm_.province),
        row2("Postal Code",     mm_.postal_code,
             "Area Code",       mm_.area_code),
        row2("Residential Address", mm_.address or "—"),
    ]))
    story.append(Spacer(1, 5*mm))

    # ════════════════════════════════════════════════════════════
    # SECTION 2 — COVER & PLAN
    # ════════════════════════════════════════════════════════════
    story.append(sec_hdr("2.  Cover & Plan Selection"))
    story.append(Spacer(1, 2*mm))
    story.append(info_tbl([
        row2("Plan Name",       data.plan_name,
             "Cover Type",      "Family" if data.cover_type == "family" else "Single"),
        row2("Sum Insured",     f"R{int(data.cover_amount):,}",
             "Base Premium",    f"R{int(data.base_premium):,}/month"),
        row2("Ext. Family Premium", f"R{int(data.efm_premium):,}/month" if data.efm_premium else "—",
             "TOTAL PREMIUM",   f"R{int(data.total_premium):,}/month"),
    ]))

    # Highlighted premium block
    prem_box = Table([[
        Paragraph(
            f'<font size="8" color="white">TOTAL MONTHLY PREMIUM</font><br/>'
            f'<font size="22" color="#e8a020"><b>R{int(data.total_premium):,}</b></font><br/>'
            f'<font size="8" color="rgba(255,255,255,0.75)">'
            f'{data.plan_name}  ·  '
            f'{"Family" if data.cover_type=="family" else "Single"} Cover  ·  '
            f'R{int(data.cover_amount):,} sum insured</font>',
            BODY)
    ]], colWidths=[W])
    prem_box.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), NAVY),
        ("TOPPADDING",   (0,0),(-1,-1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1), 10),
        ("LEFTPADDING",  (0,0),(-1,-1), 14),
    ]))
    story.append(Spacer(1, 3*mm))
    story.append(prem_box)
    story.append(Spacer(1, 5*mm))

    # ════════════════════════════════════════════════════════════
    # SECTION 3 — SPOUSE (if present)
    # ════════════════════════════════════════════════════════════
    if data.spouse:
        story.append(sec_hdr("3.  Spouse Details"))
        story.append(Spacer(1, 2*mm))
        sp = data.spouse
        story.append(info_tbl([
            row2("Full Name",    f"{sp.first_name} {sp.last_name}",
                 "Date of Birth", f"{sp.dob or '—'} (Age: {calc_age(sp.dob or '')})"),
            row2("Gender",       sp.gender,
                 "ID / Passport", sp.id_number or "—"),
        ]))
        story.append(Spacer(1, 5*mm))

    # ════════════════════════════════════════════════════════════
    # SECTION 4 — CHILDREN
    # ════════════════════════════════════════════════════════════
    if data.children:
        story.append(sec_hdr(f"4.  Children  ({len(data.children)} of max 6)"))
        story.append(Spacer(1, 2*mm))
        hdr = [[Paragraph("<b>Name</b>", LABEL),
                Paragraph("<b>Date of Birth (Age)</b>", LABEL),
                Paragraph("<b>Gender</b>", LABEL),
                Paragraph("<b>Special Status</b>", LABEL)]]
        rows_ch = hdr + [[
            Paragraph(f"{c.first_name} {c.last_name}", BODY),
            Paragraph(f"{c.dob or '—'}  (Age {calc_age(c.dob or '')})", BODY),
            Paragraph(c.gender or "—", BODY),
            Paragraph(("Student" if c.student else "") +
                      ("/ Disabled" if c.disabled else "") or "—", BODY),
        ] for c in data.children]
        ch_tbl = Table(rows_ch, colWidths=[W*.34, W*.26, W*.18, W*.22])
        ch_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,0), LTBLUE),
            ("FONTNAME",     (0,0),(-1,0), "Helvetica-Bold"),
            ("FONTSIZE",     (0,0),(-1,-1), 8.5),
            ("ROWBACKGROUNDS",(0,1),(-1,-1), [WHITE, BGRAY]),
            ("GRID",         (0,0),(-1,-1), 0.5, colors.HexColor("#c8d6ea")),
            ("TOPPADDING",   (0,0),(-1,-1), 5),
            ("BOTTOMPADDING",(0,0),(-1,-1), 5),
            ("LEFTPADDING",  (0,0),(-1,-1), 6),
        ]))
        story.append(ch_tbl)
        story.append(Spacer(1, 5*mm))

    # ════════════════════════════════════════════════════════════
    # SECTION 5 — EXTENDED FAMILY
    # ════════════════════════════════════════════════════════════
    if data.extended_family:
        story.append(sec_hdr(
            f"5.  Extended Family Members  ({len(data.extended_family)} of max 6)"))
        story.append(Spacer(1, 2*mm))
        hdr_ef = [[Paragraph("<b>Name</b>", LABEL),
                   Paragraph("<b>Relationship</b>", LABEL),
                   Paragraph("<b>DOB (Age)</b>", LABEL),
                   Paragraph("<b>Cover</b>", LABEL),
                   Paragraph("<b>Premium/mo</b>", LABEL)]]
        rows_ef = hdr_ef + [[
            Paragraph(f"{e.first_name} {e.last_name}", BODY),
            Paragraph(e.relationship or "—", BODY),
            Paragraph(f"{e.dob or '—'} ({calc_age(e.dob or '')})", BODY),
            Paragraph(f"R{e.cover:,}" if e.cover else "—", BODY),
            Paragraph(f"R{e.premium}" if e.premium else "—", BODY),
        ] for e in data.extended_family]
        ef_tbl = Table(rows_ef, colWidths=[W*.28, W*.20, W*.22, W*.15, W*.15])
        ef_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,0), LTBLUE),
            ("FONTNAME",     (0,0),(-1,0), "Helvetica-Bold"),
            ("FONTSIZE",     (0,0),(-1,-1), 8.5),
            ("ROWBACKGROUNDS",(0,1),(-1,-1), [WHITE, BGRAY]),
            ("GRID",         (0,0),(-1,-1), 0.5, colors.HexColor("#c8d6ea")),
            ("TOPPADDING",   (0,0),(-1,-1), 5),
            ("BOTTOMPADDING",(0,0),(-1,-1), 5),
            ("LEFTPADDING",  (0,0),(-1,-1), 6),
        ]))
        story.append(ef_tbl)
        story.append(Spacer(1, 5*mm))

    # ════════════════════════════════════════════════════════════
    # SECTION 6 — BENEFICIARY
    # ════════════════════════════════════════════════════════════
    story.append(sec_hdr("6.  Beneficiary Details"))
    story.append(Spacer(1, 2*mm))
    bn = data.beneficiary
    story.append(info_tbl([
        row2("Full Name",     f"{bn.first_name} {bn.last_name}",
             "Relationship",  bn.relationship),
        row2("Contact Number", bn.phone),
    ]))
    story.append(Spacer(1, 5*mm))

    # ════════════════════════════════════════════════════════════
    # SECTION 7 — PAYMENT
    # ════════════════════════════════════════════════════════════
    story.append(sec_hdr("7.  Payment Details"))
    story.append(Spacer(1, 2*mm))
    do = data.debit_order
    if data.payment_method == "debit_order" and do:
        story.append(info_tbl([
            row2("Payment Method",  "Debit Order",
                 "Account Holder",  do.account_holder),
            row2("Account Holder Contact", do.account_holder_contact,
                 "Bank",            do.bank),
            row2("Account Number",  do.account_number,
                 "Account Type",    do.account_type),
            row2("Branch Code",     do.branch_code,
                 "Deduction Date",  do.deduction_date),
            row2("Commencement Date", do.commencement_date),
        ]))
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(
            "I hereby authorise Zororo Phumulani Investments to debit my bank account as specified "
            "above on the deduction date indicated, commencing on the commencement date and every "
            "month thereafter. I understand that my salary credit date may change and authorise "
            "administration of premium requests accordingly. This includes any future premium increases.",
            ParagraphStyle("auth", fontName="Helvetica-Oblique", fontSize=7.5, leading=11, textColor=GREY)
        ))
    else:
        story.append(info_tbl([
            row2("Payment Method", "Online Payment via pay.zororophumulani.co.za")
        ]))
    story.append(Spacer(1, 5*mm))

    # ════════════════════════════════════════════════════════════
    # SECTION 8 — DECLARATIONS & NEEDS ANALYSIS
    # ════════════════════════════════════════════════════════════
    story.append(sec_hdr("8.  Needs Analysis & Declarations"))
    story.append(Spacer(1, 2*mm))
    decl = data.declarations
    if decl:
        story.append(info_tbl([
            row2("Has Other Funeral Policy",
                 "YES" if decl.has_other_policy else "NO",
                 "Existing Cover Amount", decl.other_policy_amount or "—"),
            row2("Is Replacement Policy",
                 "YES" if decl.is_replacement else "NO",
                 "Gross Monthly Income",  decl.income_range or "—"),
            row2("Monthly Expenses",     decl.monthly_expenses or "—",
                 "Available Cash",       decl.available_cash  or "—"),
            row2("Number of Dependants", decl.num_dependants  or "—",
                 "Notification Prefs",
                 ", ".join(decl.notifications) if decl.notifications else "Email"),
        ]))
    story.append(Spacer(1, 5*mm))

    # ════════════════════════════════════════════════════════════
    # SECTION 9 — AGENT DETAILS
    # ════════════════════════════════════════════════════════════
    if data.agent and data.agent.name:
        story.append(sec_hdr("9.  Agent / Connector Details"))
        story.append(Spacer(1, 2*mm))
        ag = data.agent
        story.append(info_tbl([
            row2("Agent / Connector Name", ag.name,
                 "Agent Contact",         ag.phone),
            row2("Team Leader",           ag.team_leader,
                 "Province",              ag.province),
        ]))
        story.append(Spacer(1, 5*mm))

    # ════════════════════════════════════════════════════════════
    # WAITING PERIODS NOTICE
    # ════════════════════════════════════════════════════════════
    wp_data = [[
        Paragraph('<font size="8.5" color="white"><b>WAITING PERIODS</b></font>', SECW),
        Paragraph('<font size="8" color="white">Accidental: <b>Immediate</b></font>', BODY),
        Paragraph('<font size="8" color="white">Natural (family): <b>3 months</b></font>', BODY),
        Paragraph('<font size="8" color="white">Ext. family: <b>6 months</b></font>', BODY),
        Paragraph('<font size="8" color="white">Suicide: <b>12 months</b></font>', BODY),
    ]]
    wp_tbl = Table(wp_data, colWidths=[W*.22, W*.20, W*.22, W*.20, W*.16])
    wp_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), BLUE),
        ("TOPPADDING",   (0,0),(-1,-1), 6),
        ("BOTTOMPADDING",(0,0),(-1,-1), 6),
        ("LEFTPADDING",  (0,0),(-1,-1), 5),
        ("VALIGN",       (0,0),(-1,-1), "MIDDLE"),
    ]))
    story.append(wp_tbl)
    story.append(Spacer(1, 5*mm))

    # ════════════════════════════════════════════════════════════
    # SECTION 10 — COMPLIANCE & CONSENT AUDIT RECORD
    # ════════════════════════════════════════════════════════════
    story.append(sec_hdr("10.  Compliance & Consent Audit Record"))
    story.append(Spacer(1, 2*mm))

    tc_at   = data.terms_accepted_at or (today_str + " " + time_str)
    sub_ts  = data.submission_timestamp or (today_str + " " + time_str)
    sig_method = {
        "digital": "Drawn digital signature (canvas)",
        "typed":   "Typed full legal name (ECT Act s.13)",
        "photo":   "Uploaded handwritten signature image",
    }.get(data.signature.type if data.signature else "", "—")

    # Document upload audit
    fic_status      = "YES — uploaded by applicant" if data.fic_uploaded      else "NOT UPLOADED"
    passport_status = "YES — uploaded by applicant" if data.passport_uploaded else "NOT UPLOADED"

    story.append(info_tbl([
        row2("Submission Timestamp",  sub_ts,
             "Submission IP Address", client_ip),
        row2("T&C Version Accepted",  TC_VERSION,
             "T&C Acceptance Time",   tc_at),
        row2("POPIA Consent",
             "YES — given by applicant" if data.popia_consent else "NOT GIVEN",
             "FAIS Advice Record",
             "ACCEPTED by applicant" if data.fais_accepted else "NOT ACCEPTED"),
        row2("T&C Confirmation",
             "ACCEPTED — 'I confirm I have read, understood and agree to all T&C'" if data.terms_accepted else "NOT ACCEPTED"),
        row2("Signature Method",      sig_method,
             "Signed By",             mm_.first_name + " " + mm_.last_name),
        row2("FIC Document Uploaded", fic_status,
             "Passport/ID Uploaded",  passport_status),
    ]))
    story.append(Spacer(1, 3*mm))

    # T&C Declaration text block
    tc_box_data = [[Paragraph(
        '<font size="7.5"><b>TERMS &amp; CONDITIONS ACCEPTANCE DECLARATION</b><br/></font>'
        '<font size="7.5">"I confirm that I have read, understood, and agree to all Terms &amp; '
        'Conditions of the Zororo Phumulani Worldwide Funeral Plan, including the waiting periods, '
        'exclusions, claims procedures, and cancellation terms. I consent to the processing of my '
        'personal information under POPIA. I accept the FAIS advice record as an accurate and '
        'complete record of the recommendations provided to me."</font>',
        ParagraphStyle("tc_decl", fontName="Helvetica", fontSize=7.5, leading=12, textColor=NAVY)
    )]]
    tc_tbl = Table(tc_box_data, colWidths=[W])
    tc_tbl.setStyle(TableStyle([
        ("BOX",          (0,0),(-1,-1), 1, MID),
        ("BACKGROUND",   (0,0),(-1,-1), colors.HexColor("#eef3fb")),
        ("TOPPADDING",   (0,0),(-1,-1), 8),
        ("BOTTOMPADDING",(0,0),(-1,-1), 8),
        ("LEFTPADDING",  (0,0),(-1,-1), 10),
    ]))
    story.append(tc_tbl)
    story.append(Spacer(1, 5*mm))

    # ════════════════════════════════════════════════════════════
    # SECTION 11 — SIGNATURE BLOCK
    # ════════════════════════════════════════════════════════════
    story.append(sec_hdr("11.  Policyholder Signature"))
    story.append(Spacer(1, 3*mm))

    sig = data.signature
    sig_cell_content = Paragraph("", BODY)

    if sig:
        if sig.type == "typed" and sig.name:
            sig_cell_content = Paragraph(
                f'<font size="7" color="#6b7a99">Electronic Signature (Typed Name)</font><br/>'
                f'<font size="16" color="#0a1628"><i>{sig.name}</i></font><br/>'
                f'<font size="7" color="#6b7a99">Accepted as binding electronic signature under '
                f'ECT Act No. 25 of 2002</font>',
                BODY)
        elif sig.type in ("digital", "photo") and sig.data:
            try:
                img_data = sig.data
                if "," in img_data:
                    img_data = img_data.split(",", 1)[1]
                img_bytes = base64.b64decode(img_data)
                img_buf   = BytesIO(img_bytes)
                sig_img   = RLImage(img_buf, width=65*mm, height=20*mm)
                sig_type_label = (
                    "Drawn digital signature" if sig.type == "digital"
                    else "Uploaded handwritten signature"
                )
                sig_cell_content = Table([
                    [sig_img],
                    [Paragraph(
                        f'<font size="7" color="#6b7a99">{sig_type_label}</font>',
                        SMALL)]
                ], colWidths=[W * 0.55])
            except Exception as exc:
                log.warning(f"Signature image embed failed: {exc}")
                sig_cell_content = Paragraph(
                    '<font size="9" color="#6b7a99">[Signature image – see original submission]</font>',
                    BODY)

    date_cell = Paragraph(
        f'<font size="7" color="#6b7a99">Date &amp; Time Signed</font><br/>'
        f'<font size="10" color="#0a1628"><b>{today_str}</b></font><br/>'
        f'<font size="8" color="#6b7a99">{time_str}</font><br/><br/>'
        f'<font size="7" color="#6b7a99">IP Address</font><br/>'
        f'<font size="9" color="#0a1628">{client_ip}</font>',
        ParagraphStyle("dc", fontName="Helvetica", fontSize=9, leading=13,
                       alignment=TA_RIGHT, textColor=NAVY))

    sig_tbl = Table([[sig_cell_content, date_cell]],
                    colWidths=[W * 0.60, W * 0.40])
    sig_tbl.setStyle(TableStyle([
        ("BOX",          (0,0),(-1,-1), 0.5, colors.HexColor("#c8d6ea")),
        ("TOPPADDING",   (0,0),(-1,-1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1), 10),
        ("LEFTPADDING",  (0,0),(-1,-1), 10),
        ("RIGHTPADDING", (0,0),(-1,-1), 10),
        ("VALIGN",       (0,0),(-1,-1), "MIDDLE"),
    ]))
    story.append(sig_tbl)
    story.append(Spacer(1, 5*mm))

    # ════════════════════════════════════════════════════════════
    # POPIA FOOTER NOTE
    # ════════════════════════════════════════════════════════════
    story.append(HRFlowable(width=W, thickness=0.5, color=colors.HexColor("#c8d6ea")))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "<b>POPIA Notice:</b> This document contains personal information processed under the "
        "Protection of Personal Information Act 4 of 2013. Responsible Party: Zororo Phumulani "
        "Investments (Pty) Ltd (FSP48558). Data shared with: KGA Life (Pty) Ltd (FSP15980) as "
        "underwriter; Doves Zimbabwe for repatriation services. Retention: minimum 5 years post "
        "policy termination. Data subject rights: info@zororo-phumulani.co.za. "
        "Compliance Officer: Moonstone Compliance — sgerald@moonstonecompliance.co.za. "
        "FAIS Ombud: 0860-324766 | info@faisombud.co.za.",
        ParagraphStyle("pfooter", fontName="Helvetica", fontSize=6.5, leading=10,
                       textColor=GREY, alignment=TA_JUSTIFY)
    ))

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()


# ─── EMAIL ──────────────────────────────────────────────────────
def send_email_ssl(to_addr: str, subject: str, html_body: str,
                   pdf_bytes: bytes, pdf_filename: str) -> bool:
    """Send via SSL on port 465 (Zororo mail server)."""
    smtp_host = os.environ.get("SMTP_HOST", "mail.zororo-phumulani.co.za")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")

    if not smtp_user or not smtp_pass:
        log.warning(f"SMTP credentials not set — skipping email to {to_addr}")
        return False

    msg = MIMEMultipart("mixed")
    msg["From"]    = smtp_user
    msg["To"]      = to_addr
    msg["Subject"] = subject

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    if pdf_bytes:
        part = MIMEBase("application", "pdf")
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition",
                        f'attachment; filename="{pdf_filename}"')
        msg.attach(part)

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ctx) as s:
            s.login(smtp_user, smtp_pass)
            s.sendmail(smtp_user, to_addr, msg.as_string())
        log.info(f"Email delivered → {to_addr}")
        return True
    except Exception as exc:
        log.error(f"Email FAILED → {to_addr}: {exc}")
        return False


def _email_client(policy_number, name, plan, premium, today_str) -> str:
    return f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#f5f7fb;font-family:Arial,sans-serif;">
<div style="max-width:600px;margin:32px auto;border-radius:10px;overflow:hidden;
            box-shadow:0 4px 24px rgba(0,0,0,0.10);">
  <div style="background:linear-gradient(135deg,#0a1628,#1a3a6e);padding:28px 32px;">
    <h1 style="color:#fff;font-size:22px;margin:0 0 6px;">Zororo Phumulani</h1>
    <p style="color:rgba(255,255,255,0.65);margin:0;font-size:13px;">
      Worldwide Funeral Plan — Application Received</p>
  </div>
  <div style="background:#fff;padding:28px 32px;">
    <p style="font-size:15px;color:#1a1a2e;">Dear <b>{name}</b>,</p>
    <p style="color:#4a5568;font-size:14px;line-height:1.7;">
      Your policy application has been successfully received and saved.
      Your completed application form is attached to this email as a PDF.
      Please keep it for your records.</p>
    <div style="background:#f5f7fb;border-left:4px solid #e8a020;border-radius:6px;
                padding:18px 20px;margin:20px 0;">
      <p style="margin:0 0 4px;font-size:11px;color:#6b7a99;font-weight:bold;
                text-transform:uppercase;letter-spacing:0.08em;">Policy Reference Number</p>
      <p style="margin:0;font-size:24px;font-weight:bold;color:#0a1628;">{policy_number}</p>
      <p style="margin:8px 0 0;font-size:13px;color:#6b7a99;">
        {plan} &nbsp;·&nbsp; R{int(premium):,}/month &nbsp;·&nbsp; Applied {today_str}</p>
    </div>
    <p style="font-size:14px;font-weight:bold;color:#0a1628;margin-bottom:8px;">
      What happens next?</p>
    <ul style="color:#4a5568;font-size:13px;line-height:1.9;padding-left:20px;">
      <li>Your application will be verified within <b>2 business days</b></li>
      <li>You will receive a formal policy schedule by email</li>
      <li>Cover commences on the <b>1st of the month</b> after first premium is received</li>
      <li>For immediate assistance call <b>+27 81 419 4980</b></li>
    </ul>
    <p style="margin-top:24px;font-size:13px;color:#4a5568;">
      Queries: <a href="mailto:info@zororo-phumulani.co.za" style="color:#2456a4;">
      info@zororo-phumulani.co.za</a> &nbsp;|&nbsp; +27 81 419 4980</p>
  </div>
  <div style="background:#0a1628;padding:14px 32px;text-align:center;">
    <p style="color:rgba(255,255,255,0.4);font-size:10px;margin:0;">
      Zororo Phumulani Investments (Pty) Ltd &nbsp;·&nbsp; FSP48558
      &nbsp;·&nbsp; Underwritten by KGA Life FSP15980<br/>
      This email and attachment contain POPIA-protected personal information.
      If received in error, please delete immediately.</p>
  </div>
</div>
</body></html>"""


def _email_admin(policy_number, applicant_name, plan, premium,
                 agent_name, today_str, client_ip) -> str:
    return f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#f5f7fb;font-family:Arial,sans-serif;">
<div style="max-width:600px;margin:32px auto;border-radius:10px;overflow:hidden;
            box-shadow:0 4px 24px rgba(0,0,0,0.10);">
  <div style="background:linear-gradient(135deg,#0a1628,#2456a4);padding:24px 32px;">
    <h1 style="color:#fff;font-size:20px;margin:0 0 4px;">New Policy Application</h1>
    <p style="color:rgba(255,255,255,0.6);margin:0;font-size:13px;">
      Admin Notification &nbsp;·&nbsp; {today_str}</p>
  </div>
  <div style="background:#fff;padding:24px 32px;">
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <tr style="background:#f5f7fb;">
        <td style="padding:10px 8px;color:#6b7a99;font-weight:bold;width:40%;">
          Policy Number</td>
        <td style="padding:10px 8px;font-weight:bold;font-size:18px;color:#0a1628;">
          {policy_number}</td></tr>
      <tr><td style="padding:10px 8px;color:#6b7a99;font-weight:bold;">Applicant</td>
          <td style="padding:10px 8px;color:#1a1a2e;">{applicant_name}</td></tr>
      <tr style="background:#f5f7fb;">
        <td style="padding:10px 8px;color:#6b7a99;font-weight:bold;">Plan</td>
        <td style="padding:10px 8px;color:#1a1a2e;">{plan}</td></tr>
      <tr><td style="padding:10px 8px;color:#6b7a99;font-weight:bold;">
          Monthly Premium</td>
          <td style="padding:10px 8px;font-weight:bold;color:#e8a020;font-size:16px;">
          R{int(premium):,}</td></tr>
      <tr style="background:#f5f7fb;">
        <td style="padding:10px 8px;color:#6b7a99;font-weight:bold;">Agent</td>
        <td style="padding:10px 8px;color:#1a1a2e;">
          {agent_name or "Direct application"}</td></tr>
      <tr><td style="padding:10px 8px;color:#6b7a99;font-weight:bold;">
          Submission IP</td>
          <td style="padding:10px 8px;color:#1a1a2e;">{client_ip}</td></tr>
    </table>
    <p style="margin-top:18px;font-size:13px;color:#4a5568;">
      The completed POPIA-compliant PDF application is attached.
      Please file and process accordingly.</p>
    <div style="background:#fff3cd;border:1px solid #e8a020;border-radius:6px;
                padding:12px 16px;margin-top:14px;">
      <p style="margin:0;font-size:12px;color:#7a5500;">
        <b>POPIA Notice:</b> This email contains personal information protected under
        the Protection of Personal Information Act 4 of 2013.
        Handle and store with appropriate confidentiality controls.</p>
    </div>
  </div>
  <div style="background:#0a1628;padding:14px 32px;text-align:center;">
    <p style="color:rgba(255,255,255,0.4);font-size:10px;margin:0;">
      Zororo Phumulani Investments (Pty) Ltd &nbsp;·&nbsp; FSP48558</p>
  </div>
</div>
</body></html>"""


# ─── ROUTES ─────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def serve_form():
    html_path = TEMPLATES_DIR / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Form not found — please redeploy</h1>", status_code=404)


@app.get("/api")
async def health():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM policies")
    count = c.fetchone()[0]
    conn.close()
    smtp_user = os.environ.get("SMTP_USER", "")
    return {
        "status":        "ok",
        "service":       "Zororo Phumulani Application API",
        "version":       "3.0.0",
        "policy_count":  count,
        "tc_version":    TC_VERSION,
        "smtp_configured": bool(smtp_user),
        "smtp_host":     os.environ.get("SMTP_HOST", "mail.zororo-phumulani.co.za"),
    }


@app.get("/api/v1/rates")
async def get_rates():
    return {
        "plans": {
            "premium":   {"cover": 45000, "single": 450,  "family": 540},
            "prestige":  {"cover": 75000, "single": 630,  "family": 720},
            "executive": {"cover": 90000, "single": 990,  "family": 1080},
        },
        "extended_family_tiers": {
            "t1": {"cover": 2000, "premium": 60},
            "t2": {"cover": 3000, "premium": 80},
            "t3": {"cover": 4000, "premium": 110},
            "t4": {"cover": 5000, "premium": 220},
        },
    }


@app.post("/api/v1/policies")
async def submit_policy(payload: PolicyApplication, request: Request):
    # Record IP before validation so audit trail is complete
    client_ip = get_client_ip(request)

    # Server-side validation (mirrors front-end but authoritative)
    validate_application(payload)

    policy_number = generate_policy_number()
    today_str     = datetime.now().strftime("%d %B %Y")

    # Stamp the submission timestamp and IP on the payload
    payload.submission_timestamp = datetime.now().isoformat()

    # Persist to DB
    try:
        save_policy(policy_number, payload.dict(), client_ip)
    except Exception as exc:
        log.error(f"DB save error: {exc}")
        raise HTTPException(500, "Failed to save application to database.")

    # Generate PDF
    pdf_bytes = None
    try:
        pdf_bytes = build_pdf(payload, policy_number, client_ip)
    except Exception as exc:
        log.error(f"PDF generation error: {exc}")

    # Send emails
    mm_          = payload.main_member
    agent_name   = payload.agent.name if payload.agent and payload.agent.name else ""
    pdf_filename = f"ZP_Application_{policy_number}.pdf"
    emails_sent  = 0

    if pdf_bytes:
        # ① Client email
        if mm_.email:
            ok = send_email_ssl(
                mm_.email,
                f"Your Zororo Phumulani Application – {policy_number}",
                _email_client(policy_number, mm_.first_name,
                              payload.plan_name, payload.total_premium, today_str),
                pdf_bytes,
                pdf_filename,
            )
            if ok:
                emails_sent += 1

        # ② Admin / agent email
        notify_email = os.environ.get(
            "NOTIFY_EMAIL", "mike.ncube@zororophumulani.co.za")
        if notify_email:
            ok = send_email_ssl(
                notify_email,
                f"NEW APPLICATION: {policy_number} – {mm_.first_name} {mm_.last_name}",
                _email_admin(
                    policy_number,
                    f"{mm_.first_name} {mm_.last_name}",
                    payload.plan_name,
                    payload.total_premium,
                    agent_name,
                    today_str,
                    client_ip,
                ),
                pdf_bytes,
                pdf_filename,
            )
            if ok:
                emails_sent += 1

        # Update email counter in DB
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "UPDATE policies SET pdf_generated=1, emails_sent=? "
                "WHERE policy_number=?",
                (emails_sent, policy_number),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    return {
        "success":       True,
        "policy_number": policy_number,
        "message":       (
            f"Application submitted successfully. "
            f"{emails_sent} email(s) sent."
        ),
        "emails_sent":   emails_sent,
        "pdf_generated": bool(pdf_bytes),
    }


@app.get("/api/v1/policies")
async def list_policies():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT policy_number, submitted_at, submission_ip,
               main_member_name, main_member_email, main_member_phone,
               country, province, plan, cover_type, total_premium,
               payment_method, agent_name, popia_consent, terms_accepted,
               terms_version, fic_uploaded, passport_uploaded,
               pdf_generated, emails_sent
        FROM policies ORDER BY id DESC LIMIT 200
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return {"policies": rows, "count": len(rows)}


@app.get("/api/v1/policies/{ref}")
async def get_policy(ref: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM policies WHERE policy_number=?", (ref,))
    row = c.fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, f"Policy {ref} not found.")
    result = dict(row)
    if result.get("raw_payload"):
        result["data"] = json.loads(result.pop("raw_payload"))
    return result


@app.get("/debug")
async def debug_info():
    return {
        "base_dir":   str(BASE_DIR),
        "templates":  [f.name for f in TEMPLATES_DIR.iterdir()] if TEMPLATES_DIR.exists() else [],
        "static":     [f.name for f in STATIC_DIR.iterdir()]    if STATIC_DIR.exists()    else [],
        "uploads":    [f.name for f in UPLOAD_DIR.iterdir()]    if UPLOAD_DIR.exists()    else [],
        "db_exists":  Path(DB_PATH).exists(),
        "smtp_host":  os.environ.get("SMTP_HOST", "NOT SET"),
        "smtp_user":  os.environ.get("SMTP_USER", "NOT SET"),
        "smtp_pass_set": bool(os.environ.get("SMTP_PASS", "")),
    }
