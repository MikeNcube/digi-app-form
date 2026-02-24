from fastapi import FastAPI, Form
from fastapi.responses import JSONResponse
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
import sqlite3
import re
import os

app = FastAPI()

# ---------------- DATABASE ----------------
conn = sqlite3.connect("policies.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    dob TEXT NOT NULL,
    age INTEGER NOT NULL,
    plan_type TEXT NOT NULL,
    plan_price TEXT NOT NULL,
    premium INTEGER NOT NULL,
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
    filename = f"policy_{safe_name}.pdf"

    doc = SimpleDocTemplate(filename)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("Zororo Digi Funeral Policy", styles["Heading1"]))
    elements.append(Spacer(1, 0.3 * inch))

    elements.append(Paragraph(f"Full Name: {data['full_name']}", styles["Normal"]))
    elements.append(Paragraph(f"DOB: {data['dob']}", styles["Normal"]))
    elements.append(Paragraph(f"Age: {data['age']}", styles["Normal"]))
    elements.append(Paragraph(f"Plan Type: {data['plan_type']}", styles["Normal"]))
    elements.append(Paragraph(f"Plan Price: {data['plan_price']}", styles["Normal"]))
    elements.append(Paragraph(f"Monthly Premium: R{data['premium']}", styles["Normal"]))

    doc.build(elements)
    return filename


# ---------------- SUBMIT POLICY ----------------
@app.post("/submit")
async def submit_policy(
    full_name: str = Form(...),
    dob: str = Form(...),
    plan_type: str = Form(...),
    plan_price: str = Form(...)
):

    # Clean Inputs
    full_name = full_name.strip()
    dob = dob.strip()
    plan_type = plan_type.strip()
    plan_price = plan_price.strip()

    # ---------------- AGE VALIDATION ----------------
    age = calculate_age(dob)

    if age is None:
        return JSONResponse(
            status_code=400,
            content={"error": "DOB must be in format YYYY-MM-DD"}
        )

    if age < 18 or age > 65:
        return JSONResponse(
            status_code=400,
            content={"error": "Principal must be between 18 and 65 years old."}
        )

    # ---------------- PREMIUM CLEANING ----------------
    premium_numbers = re.sub(r"[^\d]", "", plan_price)

    if not premium_numbers:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid plan price format."}
        )

    premium = int(premium_numbers)

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ---------------- SAVE TO DATABASE ----------------
    cursor.execute("""
        INSERT INTO policies 
        (full_name, dob, age, plan_type, plan_price, premium, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (full_name, dob, age, plan_type, plan_price, premium, created_at))

    conn.commit()

    # ---------------- GENERATE PDF ----------------
    pdf_file = generate_pdf({
        "full_name": full_name,
        "dob": dob,
        "age": age,
        "plan_type": plan_type,
        "plan_price": plan_price,
        "premium": premium
    })

    return {
        "message": "Policy submitted successfully.",
        "pdf_generated": pdf_file
    }


# ---------------- ADMIN DASHBOARD ----------------
@app.get("/admin")
def admin_dashboard():
    cursor.execute("SELECT * FROM policies ORDER BY id DESC")
    rows = cursor.fetchall()

    formatted = [
        {
            "id": r[0],
            "full_name": r[1],
            "dob": r[2],
            "age": r[3],
            "plan_type": r[4],
            "plan_price": r[5],
            "premium": r[6],
            "created_at": r[7]
        }
        for r in rows
    ]

    return {
        "total_policies": len(rows),
        "policies": formatted
    }


# ---------------- ROOT ----------------
@app.get("/")
def root():
    return {"message": "Zororo Digi Funeral Backend Running"}