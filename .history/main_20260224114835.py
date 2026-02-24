from fastapi import FastAPI, Form
from fastapi.responses import JSONResponse
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from typing import Optional
import sqlite3
import re
import json

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
    dependents TEXT,
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
    plan_price: str = Form(...),
    dependents: Optional[str] = Form(None)
):

    # -------- CLEAN INPUTS --------
    full_name = full_name.strip()
    dob = dob.strip()
    plan_type = plan_type.strip()
    plan_price = plan_price.strip()

    # -------- PRINCIPAL AGE VALIDATION --------
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

    # -------- DEPENDENT VALIDATION --------
    validated_dependents = []

    if dependents:
        try:
            dep_list = json.loads(dependents)
        except:
            return JSONResponse(status_code=400, content={"error": "Invalid dependents format"})

        for dep in dep_list:
            relation = dep.get("relation")
            dob_value = dep.get("dob")

            if not relation or not dob_value:
                return JSONResponse(status_code=400, content={"error": "Dependent missing relation or DOB"})

            dep_age = calculate_age(dob_value)

            if dep_age is None:
                return JSONResponse(status_code=400, content={"error": "Dependent DOB must be YYYY-MM-DD"})

            disabled = dep.get("disabled", False)
            student = dep.get("student", False)
            disability_proof = dep.get("disability_proof")

            # ----- SPOUSE RULE (18–65) -----
            if relation == "Spouse":
                if dep_age < 18 or dep_age > 65:
                    return JSONResponse(
                        status_code=400,
                        content={"error": "Spouse must be between 18 and 65 years old."}
                    )

            # ----- CHILD RULE -----
            elif relation == "Child":

                # Disabled child allowed at any age BUT proof required
                if disabled:
                    if not disability_proof:
                        return JSONResponse(
                            status_code=400,
                            content={"error": "Disabled child must have disability proof selected."}
                        )

                # 0–21 auto covered
                elif dep_age <= 21:
                    pass

                # 22–25 only if student
                elif 22 <= dep_age <= 25:
                    if not student:
                        return JSONResponse(
                            status_code=400,
                            content={"error": "Child aged 22–25 must be a registered student."}
                        )

                # Over 25 must be disabled
                else:
                    return JSONResponse(
                        status_code=400,
                        content={"error": "Child over 25 must be disabled with proof."}
                    )

            else:
                return JSONResponse(
                    status_code=400,
                    content={"error": f"Unknown dependent relation: {relation}"}
                )

            validated_dependents.append(dep)

    # -------- PREMIUM EXTRACTION --------
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
        (full_name, dob, age, plan_type, plan_price, premium, dependents, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        full_name,
        dob,
        age,
        plan_type,
        plan_price,
        premium,
        json.dumps(validated_dependents),
        created_at
    ))
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