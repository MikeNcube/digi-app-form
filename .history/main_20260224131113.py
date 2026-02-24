from fastapi import FastAPI, Form
from fastapi.responses import JSONResponse
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
import sqlite3
import re
import json
import os
import uvicorn

app = FastAPI()

# ---------------- DATABASE ----------------

def get_db():
    conn = sqlite3.connect("policies.db")
    conn.row_factory = sqlite3.Row
    return conn

# Create table at startup
with get_db() as conn:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS policies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        dob TEXT NOT NULL,
        age INTEGER NOT NULL,
        plan_type TEXT NOT NULL,
        plan_price TEXT NOT NULL,
        premium INTEGER NOT NULL,
        dependents TEXT,
        waiting_period TEXT,
        created_at TEXT NOT NULL
    )
    """)
    conn.commit()


# ---------------- AGE CALCULATION ----------------

def calculate_age(dob: str):
    try:
        birth = datetime.strptime(dob.strip(), "%Y-%m-%d")
    except ValueError:
        return None

    today = datetime.today()
    return today.year - birth.year - (
        (today.month, today.day) < (birth.month, birth.day)
    )


# ---------------- PDF GENERATION ----------------

def generate_pdf(data):
    safe_name = re.sub(r"[^a-zA-Z0-9_]", "", data["full_name"].replace(" ", "_"))
    filename = f"/tmp/policy_{safe_name}.pdf"   # Railway safe path

    doc = SimpleDocTemplate(filename)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("Zororo Digi Funeral Policy", styles["Heading1"]))
    elements.append(Spacer(1, 0.3 * inch))

    elements.append(Paragraph(f"Full Name: {data['full_name']}", styles["Normal"]))
    elements.append(Paragraph(f"Age: {data['age']}", styles["Normal"]))
    elements.append(Paragraph(f"Plan: {data['plan_type']} - {data['plan_price']}", styles["Normal"]))
    elements.append(Paragraph(f"Premium: R{data['premium']}", styles["Normal"]))
    elements.append(Paragraph(f"Waiting Period: {data['waiting_period']}", styles["Normal"]))

    doc.build(elements)
    return filename


# ---------------- SUBMIT POLICY ----------------

@app.post("/submit")
async def submit_policy(
    full_name: str = Form(...),
    dob: str = Form(...),
    plan_type: str = Form(...),
    plan_price: str = Form(...),
    dependents: str = Form("[]")
):

    age = calculate_age(dob)
    if age is None:
        return JSONResponse(status_code=400, content={"error": "DOB must be YYYY-MM-DD"})

    if age < 18 or age > 65:
        return JSONResponse(status_code=400, content={"error": "Principal must be 18–65."})

    # Parse dependents
    try:
        dependents_list = json.loads(dependents)
        if not isinstance(dependents_list, list):
            raise ValueError
    except:
        return JSONResponse(status_code=400, content={"error": "Dependents must be valid JSON array."})

    spouse_count = 0
    child_count = 0

    for dep in dependents_list:
        relation = dep.get("relation")
        dep_dob = dep.get("dob")
        is_student = dep.get("is_student", False)
        is_disabled = dep.get("is_disabled", False)

        if not relation or not dep_dob:
            return JSONResponse(status_code=400, content={"error": "Each dependent needs relation and dob."})

        dep_age = calculate_age(dep_dob)
        if dep_age is None:
            return JSONResponse(status_code=400, content={"error": f"Invalid DOB for {relation}."})

        if relation == "Spouse":
            spouse_count += 1
            if spouse_count > 1:
                return JSONResponse(status_code=400, content={"error": "Only 1 spouse allowed."})
            if dep_age < 18 or dep_age > 65:
                return JSONResponse(status_code=400, content={"error": "Spouse must be 18–65."})

        elif relation == "Child":
            child_count += 1
            if child_count > 6:
                return JSONResponse(status_code=400, content={"error": "Maximum 6 children allowed."})

            if is_disabled:
                continue

            if dep_age <= 21:
                continue

            if 22 <= dep_age <= 25 and is_student:
                continue

            return JSONResponse(status_code=400, content={"error": "Child over 25 must be disabled."})

        else:
            return JSONResponse(status_code=400, content={"error": "Relation must be Spouse or Child."})

    # Premium calculation
    premium_numbers = re.sub(r"[^\d]", "", plan_price)
    if not premium_numbers:
        return JSONResponse(status_code=400, content={"error": "Invalid plan price."})

    base_premium = int(premium_numbers)
    spouse_loading = 80 if spouse_count == 1 else 0
    child_loading = child_count * 30
    total_premium = base_premium + spouse_loading + child_loading

    waiting_period = "3 months natural causes | 12 months suicide"
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        conn.execute("""
            INSERT INTO policies 
            (full_name, dob, age, plan_type, plan_price, premium, dependents, waiting_period, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            full_name,
            dob,
            age,
            plan_type,
            plan_price,
            total_premium,
            json.dumps(dependents_list),
            waiting_period,
            created_at
        ))
        conn.commit()

    pdf_file = generate_pdf({
        "full_name": full_name,
        "age": age,
        "plan_type": plan_type,
        "plan_price": plan_price,
        "premium": total_premium,
        "waiting_period": waiting_period
    })

    return {
        "message": "Policy submitted successfully.",
        "total_premium": total_premium,
        "waiting_period": waiting_period,
        "pdf_generated": pdf_file
    }


# ---------------- ADMIN DASHBOARD ----------------

@app.get("/admin")
def admin_dashboard():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM policies ORDER BY id DESC").fetchall()

    formatted = [dict(row) for row in rows]

    return {
        "total_policies": len(rows),
        "policies": formatted
    }


# ---------------- ROOT ----------------

@app.get("/")
def root():
    return {"message": "Zororo Digi Funeral Backend Running"}


# ---------------- RAILWAY FIX ----------------
# THIS IS CRITICAL

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)