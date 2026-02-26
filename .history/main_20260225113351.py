"""
Zororo Phumulani — Worldwide Funeral Plan
main.py v3 | FastAPI | Railway | SQLite | PDF Generation | Email
"""
import os, uuid, json, sqlite3, smtplib, io
from datetime import date, datetime
from typing import Optional, List
from contextlib import asynccontextmanager
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv

load_dotenv()

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR   = os.path.join(BASE_DIR, "static")
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
UPLOAD_DIR   = os.path.join(BASE_DIR, "uploads")
for d in (STATIC_DIR, TEMPLATE_DIR, UPLOAD_DIR):
    os.makedirs(d, exist_ok=True)

DB = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "zororo.db"))

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
NOTIFY_TO = os.environ.get("NOTIFY_EMAIL", "mike.ncube@zororophumulani.co.za")

def get_db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

def init_db():
    c = get_db()
    c.execute(
        "CREATE TABLE IF NOT EXISTS policies ("
        "id TEXT PRIMARY KEY,"
        "policy_number TEXT UNIQUE NOT NULL,"
        "policy_type TEXT NOT NULL,"
        "currency TEXT DEFAULT 'ZAR',"
        "policyholder_name TEXT NOT NULL,"
        "policyholder_dob TEXT NOT NULL,"
        "policyholder_id TEXT,"
        "phone TEXT,"
        "email TEXT,"
        "street TEXT,"
        "city TEXT,"
        "province TEXT,"
        "postal_code TEXT,"
        "country TEXT,"
        "coverage_amount REAL,"
        "base_premium REAL,"
        "extended_premium REAL DEFAULT 0,"
        "total_premium REAL,"
        "plan_type TEXT DEFAULT 'single',"
        "start_date TEXT,"
        "has_spouse INTEGER DEFAULT 0,"
        "spouse_name TEXT,"
        "spouse_dob TEXT,"
        "children TEXT DEFAULT '[]',"
        "extended_family TEXT DEFAULT '[]',"
        "beneficiary_name TEXT,"
        "beneficiary_phone TEXT,"
        "beneficiary_relationship TEXT,"
        "bank_name TEXT,"
        "account_holder TEXT,"
        "account_number TEXT,"
        "account_type TEXT,"
        "branch_code TEXT,"
        "deduction_date TEXT,"
        "agent_name TEXT,"
        "agent_phone TEXT,"
        "has_other_policies INTEGER DEFAULT 0,"
        "gross_income TEXT,"
        "replacing_policy INTEGER DEFAULT 0,"
        "validation_status TEXT DEFAULT 'pending',"
        "source TEXT DEFAULT 'digital_form',"
        "created_at TEXT DEFAULT (datetime('now')),"
        "raw_payload TEXT)"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS documents ("
        "id TEXT PRIMARY KEY,"
        "policy_id TEXT,"
        "document_type TEXT,"
        "file_name TEXT,"
        "file_path TEXT,"
        "file_size INTEGER,"
        "mime_type TEXT,"
        "uploaded_at TEXT DEFAULT (datetime('now')))"
    )
    c.commit(); c.close()
    print(f"DB ready: {DB}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(); yield

PLANS = {
    "Premium":   {"cover": 45000, "single": 450,  "family": 540},
    "Prestige":  {"cover": 75000, "single": 630,  "family": 720},
    "Executive": {"cover": 90000, "single": 990,  "family": 1080},
}
EXT_COVER = {2000: 60, 3000: 80, 4000: 110, 5000: 220}
FX = {"ZAR": 1.0, "USD": 0.054, "EUR": 0.050}

app = FastAPI(title="Zororo Phumulani API", version="3.0.0", docs_url="/api/docs", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class Child(BaseModel):
    name: str; dob: Optional[str]=None; is_student: bool=False; is_disabled: bool=False

class ExtMember(BaseModel):
    name: str; dob: Optional[str]=None; relationship: Optional[str]=None
    cover_amount: int=2000; premium: float=60.0

class PolicyIn(BaseModel):
    policy_number: str; policy_type: str; currency: str="ZAR"; plan_type: str="single"
    policyholder_name: str; policyholder_dob: str
    policyholder_id: Optional[str]=None; phone: Optional[str]=None; email: Optional[str]=None
    street: Optional[str]=None; city: Optional[str]=None
    province: Optional[str]=None; postal_code: Optional[str]=None; country: Optional[str]=None
    has_spouse: bool=False; spouse_name: Optional[str]=None; spouse_dob: Optional[str]=None
    children: List[Child]=Field(default_factory=list)
    extended_family: List[ExtMember]=Field(default_factory=list)
    beneficiary_name: Optional[str]=None; beneficiary_phone: Optional[str]=None
    beneficiary_relationship: Optional[str]=None
    bank_name: Optional[str]=None; account_holder: Optional[str]=None
    account_number: Optional[str]=None; account_type: Optional[str]=None
    branch_code: Optional[str]=None; deduction_date: Optional[str]=None
    agent_name: Optional[str]=None; agent_phone: Optional[str]=None
    has_other_policies: bool=False; gross_income: Optional[str]=None
    replacing_policy: bool=False; source: str="digital_form"

    @validator("policy_type")
    def vp(cls,v):
        if v not in PLANS: raise ValueError("Invalid plan")
        return v
    @validator("currency")
    def vc(cls,v):
        if v not in FX: raise ValueError("Invalid currency")
        return v

def age_years(dob):
    try: return (date.today()-datetime.strptime(dob,"%Y-%m-%d").date()).days//365
    except: return 0

def validate_policy(p: PolicyIn):
    errs=[]
    a=age_years(p.policyholder_dob)
    if not 18<=a<=65: errs.append(f"Main member age {a} must be 18-65")
    if p.has_spouse and p.spouse_dob:
        sa=age_years(p.spouse_dob)
        if not 18<=sa<=65: errs.append(f"Spouse age {sa} must be 18-65")
    for ch in p.children:
        if ch.dob:
            ca=age_years(ch.dob); mx=25 if (ch.is_student or ch.is_disabled) else 21
            if ca>mx: errs.append(f"Child '{ch.name}' age {ca} exceeds max {mx}")
    for ex in p.extended_family:
        if ex.dob:
            ea=age_years(ex.dob)
            if ea>=90: errs.append(f"Extended '{ex.name}' must be under 90")
        if ex.cover_amount not in EXT_COVER: errs.append(f"Invalid cover R{ex.cover_amount}")
    if errs: raise HTTPException(422, detail=errs)

def compute_fin(p: PolicyIn):
    plan=PLANS[p.policy_type]; rate=FX[p.currency]
    base=plan["family"] if (p.has_spouse or p.children or p.plan_type=="family") else plan["single"]
    ext=sum(EXT_COVER.get(e.cover_amount,60) for e in p.extended_family)
    return {
        "coverage_amount": round(plan["cover"]*rate,2),
        "base_premium":    round(base*rate,2),
        "extended_premium":round(ext*rate,2),
        "total_premium":   round((base+ext)*rate,2),
        "currency": p.currency,
    }

# ── PDF GENERATION ──────────────────────────────────────────────
def generate_pdf(p: PolicyIn, fin: dict, policy_number: str) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                         Table, TableStyle, HRFlowable)
        from reportlab.lib.enums import TA_CENTER, TA_LEFT

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                 leftMargin=15*mm, rightMargin=15*mm,
                                 topMargin=15*mm, bottomMargin=15*mm)

        NAVY  = colors.HexColor("#08172e")
        GOLD  = colors.HexColor("#c9a84c")
        BLUE  = colors.HexColor("#1a56db")
        LGREY = colors.HexColor("#f8fafc")
        DKGREY= colors.HexColor("#334155")

        styles = getSampleStyleSheet()
        h1  = ParagraphStyle("h1",  parent=styles["Normal"], fontSize=18, textColor=colors.white,
                              fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=2)
        h2  = ParagraphStyle("h2",  parent=styles["Normal"], fontSize=10, textColor=NAVY,
                              fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4)
        sub = ParagraphStyle("sub", parent=styles["Normal"], fontSize=8,  textColor=colors.white,
                              alignment=TA_CENTER)
        nor = ParagraphStyle("nor", parent=styles["Normal"], fontSize=9,  textColor=DKGREY)
        sml = ParagraphStyle("sml", parent=styles["Normal"], fontSize=7.5,textColor=DKGREY)
        bold= ParagraphStyle("bold",parent=styles["Normal"], fontSize=9,  fontName="Helvetica-Bold", textColor=NAVY)

        def field_table(rows):
            data = [[Paragraph("<b>"+k+"</b>", sml), Paragraph(str(v) if v else "—", nor)] for k,v in rows]
            t = Table(data, colWidths=[55*mm, 115*mm])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0,0),(-1,-1), LGREY),
                ("ROWBACKGROUNDS",(0,0),(-1,-1),[LGREY, colors.white]),
                ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#e2e8f0")),
                ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                ("TOPPADDING",(0,0),(-1,-1),4),
                ("BOTTOMPADDING",(0,0),(-1,-1),4),
                ("LEFTPADDING",(0,0),(-1,-1),6),
            ]))
            return t

        story = []

        # Header banner
        hdr_data = [[
            Paragraph("ZOROROPHUMULANI", h1),
        ]]
        hdr_sub  = [[Paragraph("WORLDWIDE FUNERAL PLAN  ·  FSP15980  ·  POLICY APPLICATION", sub)]]
        pol_line = [[Paragraph(f"Policy Number: {policy_number}  ·  Date: {date.today().strftime('%d %B %Y')}", sub)]]

        for row, bg in [(hdr_data, NAVY),(hdr_sub, colors.HexColor("#0e2244")),(pol_line, GOLD)]:
            t = Table(row, colWidths=[180*mm])
            t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),bg),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
            story.append(t)

        story.append(Spacer(1, 6*mm))

        # Section 1: Principal
        story.append(Paragraph("1. PRINCIPAL MEMBER DETAILS", h2))
        story.append(field_table([
            ("Full Name",         p.policyholder_name),
            ("Date of Birth",     p.policyholder_dob),
            ("Age",               str(age_years(p.policyholder_dob))+" years"),
            ("Phone",             p.phone),
            ("Email",             p.email),
            ("Country",           p.country),
            ("Address",           p.street),
        ]))
        story.append(Spacer(1,4*mm))

        # Section 2: Plan
        story.append(Paragraph("2. PLAN SELECTION", h2))
        story.append(field_table([
            ("Plan",              p.policy_type+" Plan"),
            ("Cover Type",        p.plan_type.title()),
            ("Cover Amount",      f"R{fin['coverage_amount']:,.0f}"),
            ("Base Premium",      f"R{fin['base_premium']:,.0f}/month"),
            ("Extended Premium",  f"R{fin['extended_premium']:,.0f}/month"),
            ("TOTAL MONTHLY",     f"R{fin['total_premium']:,.0f}/month"),
        ]))
        story.append(Spacer(1,4*mm))

        # Section 3: Spouse
        if p.has_spouse:
            story.append(Paragraph("3. SPOUSE DETAILS", h2))
            story.append(field_table([
                ("Spouse Name", p.spouse_name),
                ("Date of Birth", p.spouse_dob),
                ("Age", str(age_years(p.spouse_dob))+" years" if p.spouse_dob else "—"),
            ]))
            story.append(Spacer(1,4*mm))

        # Section 4: Children
        if p.children:
            story.append(Paragraph("4. CHILDREN / IMMEDIATE FAMILY", h2))
            ch_data = [["#","Name","Date of Birth","Age","Student","Disabled"]]
            for i,ch in enumerate(p.children,1):
                ch_data.append([
                    str(i), ch.name or "—", ch.dob or "—",
                    str(age_years(ch.dob))+" yrs" if ch.dob else "—",
                    "Yes" if ch.is_student else "No",
                    "Yes" if ch.is_disabled else "No",
                ])
            ct = Table(ch_data, colWidths=[8*mm,52*mm,35*mm,22*mm,20*mm,20*mm])
            ct.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),NAVY),("TEXTCOLOR",(0,0),(-1,0),colors.white),
                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[LGREY,colors.white]),
                ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#e2e8f0")),
                ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
                ("LEFTPADDING",(0,0),(-1,-1),5),
            ]))
            story.append(ct)
            story.append(Spacer(1,4*mm))

        # Section 5: Extended family
        if p.extended_family:
            story.append(Paragraph("5. EXTENDED FAMILY MEMBERS", h2))
            ext_data = [["#","Name","Relationship","Date of Birth","Age","Cover","Premium"]]
            for i,ex in enumerate(p.extended_family,1):
                ext_data.append([
                    str(i), ex.name or "—", ex.relationship or "—", ex.dob or "—",
                    str(age_years(ex.dob))+" yrs" if ex.dob else "—",
                    f"R{ex.cover_amount:,}",
                    f"R{EXT_COVER.get(ex.cover_amount,60)}/m",
                ])
            et = Table(ext_data, colWidths=[8*mm,40*mm,28*mm,28*mm,20*mm,22*mm,22*mm])
            et.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),NAVY),("TEXTCOLOR",(0,0),(-1,0),colors.white),
                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[LGREY,colors.white]),
                ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#e2e8f0")),
                ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
                ("LEFTPADDING",(0,0),(-1,-1),5),
            ]))
            story.append(et)
            story.append(Spacer(1,4*mm))

        # Section 6: Beneficiary
        story.append(Paragraph("6. BENEFICIARY DETAILS", h2))
        story.append(field_table([
            ("Beneficiary Name",    p.beneficiary_name),
            ("Phone",               p.beneficiary_phone),
            ("Relationship",        p.beneficiary_relationship),
        ]))
        story.append(Spacer(1,4*mm))

        # Section 7: Banking
        story.append(Paragraph("7. DEBIT ORDER AUTHORISATION", h2))
        story.append(field_table([
            ("Bank Name",           p.bank_name),
            ("Account Holder",      p.account_holder),
            ("Account Number",      p.account_number),
            ("Account Type",        p.account_type),
            ("Branch Code",         p.branch_code),
            ("Deduction Date",      p.deduction_date),
        ]))
        story.append(Spacer(1,4*mm))

        # Section 8: Needs analysis
        story.append(Paragraph("8. NEEDS ANALYSIS & DECLARATIONS", h2))
        story.append(field_table([
            ("Other Funeral Policies?",  "Yes" if p.has_other_policies else "No"),
            ("Gross Monthly Income",     p.gross_income),
            ("Replacing Existing Policy?","Yes" if p.replacing_policy else "No"),
            ("Agent Name",               p.agent_name),
            ("Agent Phone",              p.agent_phone),
        ]))
        story.append(Spacer(1,5*mm))

        # Waiting periods
        story.append(HRFlowable(width="100%", thickness=1, color=GOLD))
        story.append(Spacer(1,3*mm))
        wp_text = ("<b>WAITING PERIODS:</b> Accidental Death — Immediate | "
                   "Natural Causes (Member & Immediate Family) — 3 months | "
                   "Extended Family — 6 months | Suicide — 12 months<br/>"
                   "Claims must be submitted within 6 months of date of death. "
                   "Grace period: 60 days before policy lapses.")
        story.append(Paragraph(wp_text, sml))
        story.append(Spacer(1,8*mm))

        # Signatures
        sig_data = [
            [Paragraph("<b>Policyholder Signature</b>", sml), "", Paragraph("<b>Date</b>", sml)],
            ["_"*40, "  ", "_"*20],
            ["", "", ""],
            [Paragraph("<b>Authorised Signatory (Zororo Phumulani)</b>", sml), "", Paragraph("<b>Date</b>", sml)],
            ["_"*40, "  ", "_"*20],
        ]
        st = Table(sig_data, colWidths=[90*mm, 10*mm, 80*mm])
        st.setStyle(TableStyle([("FONTSIZE",(0,0),(-1,-1),9),("TOPPADDING",(0,0),(-1,-1),5)]))
        story.append(st)

        doc.build(story)
        return buf.getvalue()
    except Exception as e:
        print(f"PDF generation error: {e}")
        return None

# ── EMAIL ────────────────────────────────────────────────────────
def send_email(policy_number: str, pdf_bytes: bytes, p: PolicyIn, fin: dict):
    if not SMTP_USER or not SMTP_PASS:
        print("SMTP not configured — skipping email")
        return False
    try:
        msg = MIMEMultipart()
        msg["From"]    = SMTP_USER
        msg["To"]      = NOTIFY_TO
        msg["Subject"] = f"New Policy Application — {policy_number}"

        body = f"""New Zororo Phumulani Funeral Plan Application

Policy Number : {policy_number}
Applicant     : {p.policyholder_name}
Plan          : {p.policy_type} ({p.plan_type.title()})
Monthly Premium: R{fin['total_premium']:,.0f}
Cover Amount   : R{fin['coverage_amount']:,.0f}
Phone          : {p.phone}
Email          : {p.email}
Country        : {p.country}
Submitted      : {datetime.utcnow().strftime('%d %B %Y %H:%M')} UTC

Please see attached PDF for full application details.

— Zororo Phumulani Digital Portal
"""
        msg.attach(MIMEText(body, "plain"))
        if pdf_bytes:
            att = MIMEApplication(pdf_bytes, _subtype="pdf")
            att.add_header("Content-Disposition", "attachment", filename=f"{policy_number}.pdf")
            msg.attach(att)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        print(f"Email sent for {policy_number}")
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

# ── ROUTES ───────────────────────────────────────────────────────
@app.get("/debug")
async def debug():
    def ls(p):
        try: return os.listdir(p)
        except Exception as e: return [str(e)]
    return {"cwd":os.getcwd(),"BASE_DIR":BASE_DIR,"static_files":ls(STATIC_DIR),
            "template_files":ls(TEMPLATE_DIR),"styles_css_exists":os.path.exists(os.path.join(STATIC_DIR,"styles.css"))}

@app.get("/api")
async def health():
    c=get_db(); n=c.execute("SELECT COUNT(*) FROM policies").fetchone()[0]; c.close()
    return {"status":"online","version":"3.0.0","policies":n,"email_configured":bool(SMTP_USER)}

@app.get("/api/v1/rates")
async def rates():
    return {"plans":PLANS,"extended_covers":EXT_COVER,"fx_rates":FX}

@app.post("/api/v1/policies")
async def create_policy(p: PolicyIn):
    validate_policy(p)
    fin  = compute_fin(p)
    pid  = str(uuid.uuid4())
    c    = get_db()
    try:
        c.execute(
            "INSERT INTO policies (id,policy_number,policy_type,currency,plan_type,"
            "policyholder_name,policyholder_dob,policyholder_id,phone,email,"
            "street,city,province,postal_code,country,"
            "coverage_amount,base_premium,extended_premium,total_premium,"
            "start_date,has_spouse,spouse_name,spouse_dob,"
            "children,extended_family,"
            "beneficiary_name,beneficiary_phone,beneficiary_relationship,"
            "bank_name,account_holder,account_number,account_type,branch_code,deduction_date,"
            "agent_name,agent_phone,has_other_policies,gross_income,replacing_policy,"
            "source,raw_payload) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (pid,p.policy_number,p.policy_type,p.currency,p.plan_type,
             p.policyholder_name,p.policyholder_dob,p.policyholder_id,p.phone,p.email,
             p.street,p.city,p.province,p.postal_code,p.country,
             fin["coverage_amount"],fin["base_premium"],fin["extended_premium"],fin["total_premium"],
             date.today().isoformat(),1 if p.has_spouse else 0,p.spouse_name,p.spouse_dob,
             json.dumps([ch.dict() for ch in p.children]),
             json.dumps([ex.dict() for ex in p.extended_family]),
             p.beneficiary_name,p.beneficiary_phone,p.beneficiary_relationship,
             p.bank_name,p.account_holder,p.account_number,p.account_type,p.branch_code,p.deduction_date,
             p.agent_name,p.agent_phone,1 if p.has_other_policies else 0,p.gross_income,
             1 if p.replacing_policy else 0,
             p.source,p.json())
        )
        c.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(409,"Policy number already exists")
    finally:
        c.close()

    # Generate PDF & email
    pdf = generate_pdf(p, fin, p.policy_number)
    email_sent = send_email(p.policy_number, pdf, p, fin)

    return {
        "message":       "Policy created",
        "policy_id":     pid,
        "policy_number": p.policy_number,
        "financials":    fin,
        "email_sent":    email_sent,
        "pdf_generated": pdf is not None,
    }

@app.get("/api/v1/policies")
async def list_policies(limit:int=50,offset:int=0):
    c=get_db()
    rows=c.execute("SELECT * FROM policies ORDER BY created_at DESC LIMIT ? OFFSET ?",(limit,offset)).fetchall()
    total=c.execute("SELECT COUNT(*) FROM policies").fetchone()[0]; c.close()
    return {"policies":[dict(r) for r in rows],"total":total}

@app.get("/api/v1/policies/{policy_id}")
async def get_policy(policy_id:str):
    c=get_db()
    row=c.execute("SELECT * FROM policies WHERE id=? OR policy_number=?",(policy_id,policy_id)).fetchone()
    c.close()
    if not row: raise HTTPException(404,"Not found")
    return dict(row)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", include_in_schema=False)
async def root():
    p=os.path.join(TEMPLATE_DIR,"index.html")
    if os.path.exists(p): return FileResponse(p)
    return JSONResponse({"error":"index.html not found","tip":"visit /debug"},404)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app",host="0.0.0.0",port=int(os.environ.get("PORT",8000)),reload=True)
