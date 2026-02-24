import os
import sqlite3
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

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

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/submit")
async def submit_policy(
    request: Request,
    payload: str = Form(...),
    files: list[UploadFile] = File(default=[])
):
    uploaded_files = []

    for file in files:
        contents = await file.read()
        path = f"proofs/{file.filename}"
        supabase.storage.from_("documents").upload(path, contents)
        uploaded_files.append(path)

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