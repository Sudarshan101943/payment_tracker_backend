from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from database import init_db, insert_tenant, insert_payment, get_tenants, get_payments_for_tenant
from gmail_parser import fetch_payments_from_gmail
import pandas as pd

app = FastAPI()

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize DB
init_db()

# Load tenants from Excel and insert into DB
tenant_df = pd.read_excel("tenant_reference.xlsx", dtype=str)
tenant_df = tenant_df.fillna('')
for _, row in tenant_df.iterrows():
    insert_tenant(row.to_dict())

# ---------------- Endpoints ----------------

# Fetch new payments from Gmail
@app.get("/fetch-payments")
def fetch_payments():
    payments = fetch_payments_from_gmail(tenant_df)
    for p in payments:
        insert_payment(p)
    return {"status": "success", "payments_added": len(payments)}

# List all tenants
@app.get("/tenants")
def list_tenants():
    tenants = get_tenants()
    return {"tenants": tenants}

# Get payment history for a specific tenant
@app.get("/tenant/{tenant_id}/payments")
def tenant_payments(tenant_id: str):
    payments = get_payments_for_tenant(tenant_id)
    return {"tenant_id": tenant_id, "payments": payments}

# Global payments endpoint
@app.get("/payments")
def all_payments():
    all_payments = []
    tenants = get_tenants()
    for t in tenants:
        payments = get_payments_for_tenant(t["tenant_id"])
        all_payments.extend(payments)
    return {"payments": all_payments}

# Mark offline payment for a tenant
@app.post("/payments/mark_paid")
def mark_paid(data: dict = Body(...)):
    tenant_id = data.get("tenant_id")
    amount = data.get("amount")
    insert_payment({
        "tenant_id": tenant_id,
        "amount": amount,
        "txn": "offline",
        "date": pd.Timestamp.now()
    })
    return {"status": "success", "tenant_id": tenant_id, "amount": amount}


from fastapi import Request

# Mark offline payment
@app.post("/payments/mark_paid")
async def mark_offline_payment(req: Request):
    data = await req.json()
    tenant_id = data.get("tenant_id")
    amount = data.get("amount")
    if not tenant_id or not amount:
        return {"status": "error", "message": "tenant_id and amount required"}

    # Insert payment
    insert_payment({
        "tenant_id": tenant_id,
        "amount": float(amount),
        "txn": "offline",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    return {"status": "success", "message": f"Marked {amount} as paid for {tenant_id}"}

