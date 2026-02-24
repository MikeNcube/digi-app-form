# FORCE RAILWAY FULL REBUILD 23-02-2026
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from datetime import date
import os

from database import engine
from models import Base

app = FastAPI(title="Zororo Phumulani API")

# Create tables on startup
Base.metadata.create_all(bind=engine)

# --------------------------------------------------
# Static Files Setup (PRODUCTION SAFE)
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# --------------------------------------------------
# Routes
# --------------------------------------------------

@app.get("/")
async def serve_home():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

# --------------------------------------------------
# Policy Model & Submission
# --------------------------------------------------

class PolicyCreate(BaseModel):
    tenant_id: str
    policy_number: str
    policy_type: str
    policyholder_name: str
    policyholder_dob: date
    coverage_amount: float
    premium_amount: float
    start_date: date


@app.post("/api/submit")
async def create_policy(policy: PolicyCreate):
    print(f"Received Policy: {policy.policy_number} for {policy.policyholder_name}")

    return {
        "success": True,
        "message": "Policy recorded in system logs",
        "policy_id": policy.policy_number
    }


@app.get("/api/health")
async def health():
    return {"status": "Zororo Phumulani API running"}


# --------------------------------------------------
# DEBUG ROUTE (TEMPORARY)
# --------------------------------------------------

@app.get("/debug")
async def debug():
    return {
        "base_dir": BASE_DIR,
        "static_dir": STATIC_DIR,
        "base_contents": os.listdir(BASE_DIR),
        "static_exists": os.path.exists(STATIC_DIR)
    }