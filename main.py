from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from datetime import date
import os

from rollover import get_or_create_today_limit, add_spend_to_today, get_weekly_history
from parser import parse_sms
from sheets import get_all_records, append_row, get_unprocessed_sms, mark_sms_processed

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
def root():
    return FileResponse("frontend/index.html")

# ── Dashboard ──────────────────────────────────────────────────────

@app.get("/api/dashboard")
def dashboard():
    today = get_or_create_today_limit()
    accounts = get_all_records("Accounts")
    loans = get_all_records("Loans")
    upcoming = sorted(
        [l for l in loans if l.get("next_deduction_date", "") >= str(date.today())],
        key=lambda x: x["next_deduction_date"]
    )[:3]
    budgets = get_all_records("Budgets")
    recent_tx = get_all_records("Transactions")[-10:]

    return {
        "today": today,
        "weekly_history": get_weekly_history(),
        "accounts": accounts,
        "upcoming_loans": upcoming,
        "budgets": budgets,
        "recent_transactions": list(reversed(recent_tx)),
    }

# ── SMS Processing ─────────────────────────────────────────────────

@app.post("/api/process-sms")
def process_sms():
    pending = get_unprocessed_sms()
    processed = 0
    failed = []

    for i, sms in pending:
        parsed = parse_sms(sms.get("raw_text", ""))
        if parsed:
            append_row("Transactions", [
                str(date.today()),
                parsed["amount"],
                parsed["merchant"],
                parsed["category"],
                "SMS",
                "",
            ])
            add_spend_to_today(parsed["amount"])
            mark_sms_processed(i)
            processed += 1
        else:
            failed.append(sms.get("raw_text", ""))

    return {"processed": processed, "failed": failed}

# ── Transactions ───────────────────────────────────────────────────

class TxIn(BaseModel):
    amount: float
    merchant: str
    category: str = "Other"
    notes: str = ""

@app.post("/api/transactions")
def add_transaction(tx: TxIn):
    append_row("Transactions", [
        str(date.today()), tx.amount, tx.merchant, tx.category, "Manual", tx.notes
    ])
    updated = add_spend_to_today(tx.amount)
    return {"status": "ok", "today": updated}

@app.get("/api/transactions")
def list_transactions():
    return get_all_records("Transactions")

# ── Loans ──────────────────────────────────────────────────────────

class LoanIn(BaseModel):
    lender: str
    principal: float
    outstanding: float
    emi: float
    next_deduction_date: str
    foreclosure_amount: float = 0.0
    notes: str = ""

@app.get("/api/loans")
def list_loans():
    return get_all_records("Loans")

@app.post("/api/loans")
def add_loan(loan: LoanIn):
    append_row("Loans", [
        loan.lender, loan.principal, loan.outstanding,
        loan.emi, loan.next_deduction_date, loan.foreclosure_amount, loan.notes
    ])
    return {"status": "ok"}

# ── Accounts ───────────────────────────────────────────────────────

class AccountIn(BaseModel):
    account_name: str
    balance: float

@app.post("/api/accounts/update")
def update_account(data: AccountIn):
    from sheets import get_sheet
    from datetime import datetime
    ws = get_sheet("Accounts")
    records = ws.get_all_records()
    for i, row in enumerate(records):
        if row["account_name"] == data.account_name:
            ws.update_cell(i + 2, 3, data.balance)
            ws.update_cell(i + 2, 4, datetime.now().strftime("%Y-%m-%d %H:%M"))
            return {"status": "updated"}
    append_row("Accounts", [data.account_name, "", data.balance,
                             datetime.now().strftime("%Y-%m-%d %H:%M")])
    return {"status": "created"}

@app.get("/api/accounts")
def list_accounts():
    return get_all_records("Accounts")

# ── OCR ────────────────────────────────────────────────────────────

@app.post("/api/ocr")
async def ocr_upload(file: UploadFile = File(...)):
    try:
        import pytesseract
        from PIL import Image
        import io, re
        contents = await file.read()
        img = Image.open(io.BytesIO(contents))
        w, h = img.size
        img = img.resize((w * 2, h * 2))
        text = pytesseract.image_to_string(img)
        amounts = re.findall(r"(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d{1,2})?)", text)
        amounts_f = [float(a.replace(",", "")) for a in amounts]
        return {"raw_text": text.strip(), "detected_amounts": amounts_f}
    except Exception as e:
        return {"error": str(e), "raw_text": "", "detected_amounts": []}

# ── Budgets ────────────────────────────────────────────────────────

@app.get("/api/budgets")
def list_budgets():
    return get_all_records("Budgets")
