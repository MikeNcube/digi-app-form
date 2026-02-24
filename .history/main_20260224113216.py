from fastapi import FastAPI, Form
from fastapi.responses import JSONResponse
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
import sqlite3
import re

app = FastAPI()

# ---------------- DATABASE ----------------
conn = sqlite3.connect("policies.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT,
    dob TEXT,
    age INTEGER,
    plan_type TEXT,
    plan_price TEXT,
    premium INTEGER,
    created_at TEXT
)
""")
conn.commit()

# ---------------- AGE ----------------
def calculate_age(dob: str):
    try:
        birth = datetime.strptime(dob.strip(), "%Y-%m-%d")
    except ValueError:
        return None

    today = datetime.today()
    return today.year - birth.year - (
        (today.month, today.day) < (birth.month, birth.day)
    )

# ---------------- PDF ----------------
def generate_pdf(data):
    safe_name = data["full_name"].strip().replace(" ", "_")
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

# ---------------- SUBMIT ----------------
@app.post("/submit")
async def submit_policy(
    full_name: str = Form(...),
    dob: str = Form(...),
    plan_type: str = Form(...),
    plan_price: str = Form(...)
):

    # 🔹 Trim inputs
    full_name = full_name.strip()
    dob = dob.strip()
    plan_type = plan_type.strip()
    plan_price = plan_price.strip()

    # 🔹 Age validation
    age = calculate_age(dob)

    if age is None:
        return JSONResponse(
            status_code=400,
            content={"error": "DOB must be in format YYYY-MM-DD"}
        )

    if age < 18 or age > 75:
        return JSONResponse(
            status_code=400,
            content={"error": "Principal must be between 18 and 75 years old."}
        )

    # 🔹 Extract numeric premium safely
    premium_numbers = re.sub(r"[^\d]", "", plan_price)

    if not premium_numbers:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid plan price format."}
        )

    premium = int(premium_numbers)

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO policies 
        (full_name, dob, age, plan_type, plan_price, premium, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (full_name, dob, age, plan_type, plan_price, premium, created_at))
    conn.commit()

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

# ---------------- ADMIN ----------------
@app.get("/admin")
def admin_dashboard():
    cursor.execute("SELECT * FROM policies ORDER BY id DESC")
    rows = cursor.fetchall()

    return {
        "total_policies": len(rows),
        "policies": rows
    }

# ---------------- ROOT ----------------
@app.get("/")
def root():
    return {"message": "Zororo Digi Funeral Backend Running"}