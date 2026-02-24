import os, uuid, json, sqlite3
from datetime import date, datetime
from typing import Optional, List
from contextlib import asynccontextmanager
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

supabase = None

DB = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "zororo.db"))

def get_db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

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
        "coverage_amount REAL,"
        "base_premium REAL,"
        "extended_premium REAL DEFAULT 0,"
        "total_premium REAL,"
        "start_date TEXT,"
        "has_spouse INTEGER DEFAULT 0,"
        "spouse_name TEXT,"
        "spouse_dob TEXT,"
        "children TEXT DEFAULT '[]',"
        "extended_family TEXT DEFAULT '[]',"
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
    c.commit()
    c.close()
    print("DB ready")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

PLANS = {
    "Premium":   {"cover": 45000, "single": 450,  "family": 540,  "label": "Premium Plan"},
    "Prestige":  {"cover": 75000, "single": 630,  "family": 720,  "label": "Prestige Plan"},
    "Executive": {"cover": 90000, "single": 990,  "family": 1080, "label": "Executive Plan"},
}
EXT_COVER = {2000: 60, 3000: 80, 4000: 110, 5000: 220}
FX = {"ZAR": 1.0, "USD": 0.054, "EUR": 0.050}

app = FastAPI(title="Zororo Phumulani API", version="2.0.0", docs_url="/api/docs", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class Child(BaseModel):
    name: str
    dob: Optional[str] = None
    is_student: bool = False
    is_disabled: bool = False

class ExtMember(BaseModel):
    name: str
    dob: Optional[str] = None
    cover_amount: int = 2000
    premium: float = 60.0

class PolicyIn(BaseModel):
    policy_number: str
    policy_type: str
    currency: str = "ZAR"
    policyholder_name: str
    policyholder_dob: str
    policyholder_id: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    has_spouse: bool = False
    spouse_name: Optional[str] = None
    spouse_dob: Optional[str] = None
    children: List[Child] = Field(default_factory=list)
    extended_family: List[ExtMember] = Field(default_factory=list)
    source: str = "digital_form"

    @validator("policy_type")
    def vp(cls, v):
        if v not in PLANS: raise ValueError("Invalid plan")
        return v
    @validator("currency")
    def vc(cls, v):
        if v not in FX: raise ValueError("Invalid currency")
        return v

def age_years(dob):
    try: return (date.today() - datetime.strptime(dob, "%Y-%m-%d").date()).days // 365
    except: return 0

def validate_policy(p):
    errs = []
    a = age_years(p.policyholder_dob)
    if not 18 <= a <= 65: errs.append(f"Main member age {a} must be 18-65")
    if p.has_spouse and p.spouse_dob:
        sa = age_years(p.spouse_dob)
        if not 18 <= sa <= 65: errs.append(f"Spouse age {sa} must be 18-65")
    for ch in p.children:
        if ch.dob:
            ca = age_years(ch.dob)
            mx = 25 if (ch.is_student or ch.is_disabled) else 21
            if ca > mx: errs.append(f"Child {ch.name} age {ca} exceeds max {mx}")
    for ex in p.extended_family:
        if ex.dob:
            ea = age_years(ex.dob)
            if ea >= 90: errs.append(f"Extended {ex.name} must be under 90")
        if ex.cover_amount not in EXT_COVER: errs.append(f"Invalid cover {ex.cover_amount}")
    if errs: raise HTTPException(422, detail=errs)

def compute_fin(p):
    plan = PLANS[p.policy_type]
    rate = FX[p.currency]
    base = plan["family"] if (p.has_spouse or p.children) else plan["single"]
    ext  = sum(EXT_COVER.get(e.cover_amount, 60) for e in p.extended_family)
    sym  = {"ZAR":"R","USD":"$","EUR":""}[p.currency]
    return {
        "coverage_amount":  round(plan["cover"] * rate, 2),
        "base_premium":     round(base * rate, 2),
        "extended_premium": round(ext * rate, 2),
        "total_premium":    round((base+ext) * rate, 2),
        "currency": p.currency, "currency_symbol": sym,
    }

@app.get("/debug")
async def debug():
    def ls(p):
        try: return os.listdir(p)
        except Exception as e: return [str(e)]
    return {"cwd": os.getcwd(), "BASE_DIR": BASE_DIR,
            "static_files": ls(STATIC_DIR), "template_files": ls(TEMPLATE_DIR),
            "styles_css_exists": os.path.exists(os.path.join(STATIC_DIR,"styles.css")),
            "index_html_exists": os.path.exists(os.path.join(TEMPLATE_DIR,"index.html"))}

@app.get("/api")
async def health():
    c = get_db()
    n = c.execute("SELECT COUNT(*) FROM policies").fetchone()[0]
    c.close()
    return {"status": "online", "version": "2.0.0", "policies": n}

@app.get("/api/v1/rates")
async def rates():
    return {"plans": PLANS, "extended_covers": EXT_COVER, "fx_rates": FX}

@app.post("/api/v1/policies")
async def create_policy(p: PolicyIn):
    validate_policy(p)
    fin = compute_fin(p)
    pid = str(uuid.uuid4())
    c = get_db()
    try:
        c.execute(
            "INSERT INTO policies (id,policy_number,policy_type,currency,"
            "policyholder_name,policyholder_dob,policyholder_id,phone,email,"
            "street,city,province,postal_code,coverage_amount,base_premium,"
            "extended_premium,total_premium,start_date,has_spouse,spouse_name,"
            "spouse_dob,children,extended_family,source,raw_payload) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (pid,p.policy_number,p.policy_type,p.currency,
             p.policyholder_name,p.policyholder_dob,p.policyholder_id,
             p.phone,p.email,p.street,p.city,p.province,p.postal_code,
             fin["coverage_amount"],fin["base_premium"],fin["extended_premium"],
             fin["total_premium"],date.today().isoformat(),
             1 if p.has_spouse else 0,p.spouse_name,p.spouse_dob,
             json.dumps([ch.dict() for ch in p.children]),
             json.dumps([ex.dict() for ex in p.extended_family]),
             p.source,p.json())
        )
        c.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Policy number already exists")
    finally:
        c.close()
    return {"message":"Policy created","policy_id":pid,"policy_number":p.policy_number,"financials":fin}

@app.get("/api/v1/policies")
async def list_policies(limit:int=50,offset:int=0):
    c = get_db()
    rows = c.execute("SELECT * FROM policies ORDER BY created_at DESC LIMIT ? OFFSET ?",(limit,offset)).fetchall()
    total = c.execute("SELECT COUNT(*) FROM policies").fetchone()[0]
    c.close()
    return {"policies":[dict(r) for r in rows],"total":total}

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", include_in_schema=False)
async def root():
    p = os.path.join(TEMPLATE_DIR, "index.html")
    if os.path.exists(p): return FileResponse(p)
    return JSONResponse({"error":"index.html not found","tip":"visit /debug"}, 404)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT",8000)), reload=True)
