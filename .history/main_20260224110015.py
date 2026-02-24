import os
import sqlite3
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

app = FastAPI()

# Mount static and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ==========================
# SUPABASE (OPTIONAL LOCAL)
# ==========================

SUPABASE_URL = os.getenv("https://supabase.com/dashboard/project/puidycccmzpawipmcqeb")
SUPABASE_KEY = os.getenv("")

supabase = None

if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase connected")
    except Exception as e:
        print("⚠️ Supabase connection failed:", e)
        supabase = None
else:
    print("ℹ️ Supabase not configured (running local mode)")

# ==========================
# SQLITE DATABASE
# ==========================

DB = "policies.db"

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ==========================
# ROUTES
# ==========================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/submit")
async def submit_policy(
    payload: str = Form(...),
    files: list[UploadFile] = File(default=[])
):
    uploaded_files = []

    # Handle file uploads
    for file in files:
        contents = await file.read()

        if supabase:
            try:
                path = f"proofs/{file.filename}"
                supabase.storage.from_("documents").upload(path, contents)
                uploaded_files.append(path)
            except Exception as e:
                print("Upload failed:", e)

    # Save policy JSON into SQLite
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO policies (data) VALUES (?)", (payload,))
    conn.commit()
    conn.close()

    return JSONResponse({
        "status": "success",
        "message": "Policy submitted successfully.",
        "files_uploaded": uploaded_files
    })