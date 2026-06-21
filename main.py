from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from datetime import date
from typing import Optional, List
import os

from rollover import get_or_create_today, add_spend, get_week_history, get_month_spent, calc_base_daily
from parser import parse_sms, is_unusual
from sheets import (
    get_all, append, get_unprocessed_sms, mark_sms_processed,
    update_account_balance, update_budget_category, delete_last_transaction,
    get_monthly_budget, set_monthly_budget, get_sheet
)
from groq_ai import chat as groq_chat, parse_sms_with_groq
from config import USER_NAME

app = FastAPI(title="Hey Pulkit!")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
def root():
    return FileResponse("frontend/index.html")

@app.get("/manifest.json")
def manifest():
    return FileResponse("frontend/manifest.json")

@app.get("/sw.js")
def sw():
    return FileResponse("frontend/sw.js")


# ── Dashboard ──────────────────────────────────────────────────────

@app.get("/api/dashboard")
def dashboard():
    today    = get_or_create_today()
    accounts = get_all("Accounts")
    loans    = get_all("Loans")
    budgets  = get_all("Budgets")
    recent   = list(reversed(get_all("Transactions")[-10:]))

    upcoming_loans = sorted(
        [l for l in loans if l.get("next_deduction_date", "") >= str(date.today())],
        key=lambda x: x["next_deduction_date"]
    )[:3]

    # Check for pending unusual SMS
    pending_alerts = []
    for _, sms in get_unprocessed_sms():
        raw = sms.get("raw_text", "")
        parsed = parse_sms(raw)
        if parsed["type"] == "transaction" and is_unusual(parsed.get("amount", 0), float(today.get("effective_limit", 100))):
            pending_alerts.append({
                "raw": raw,
                "amount": parsed.get("amount"),
                "merchant": parsed.get("merchant"),
                "category": parsed.get("category"),
            })

    return {
        "user_name":          USER_NAME,
        "today":              today,
        "weekly_history":     get_week_history(7),
        "accounts":           accounts,
        "upcoming_loans":     upcoming_loans,
        "budgets":            budgets,
        "recent_transactions": recent,
        "month_spent":        get_month_spent(),
        "monthly_budget":     get_monthly_budget(),
        "base_daily":         calc_base_daily(),
        "pending_alerts":     pending_alerts,
    }


# ── SMS Processing ─────────────────────────────────────────────────

@app.post("/api/process-sms")
def process_sms():
    pending   = get_unprocessed_sms()
    processed = 0
    alerts    = []
    balance_updates = []

    today_data = get_or_create_today()
    daily_limit = float(today_data.get("effective_limit", 100))

    for i, sms in pending:
        raw    = sms.get("raw_text", "")
        parsed = parse_sms_with_groq(raw, daily_limit)

        if parsed.get("type") == "balance_update" and parsed.get("bank") and parsed.get("balance"):
            update_account_balance(parsed["bank"], parsed["balance"])
            mark_sms_processed(i)
            balance_updates.append({"bank": parsed["bank"], "balance": parsed["balance"]})
            processed += 1

        elif parsed.get("type") == "transaction":
            amount   = parsed.get("amount", 0)
            merchant = parsed.get("merchant", "Unknown")
            category = parsed.get("category", "Other")
            balance  = parsed.get("balance")
            bank     = parsed.get("bank")

            # Auto-update balance if included in SMS
            if balance and bank:
                update_account_balance(bank, balance)
                balance_updates.append({"bank": bank, "balance": balance})

            if parsed.get("needs_clarification") or is_unusual(amount, daily_limit):
                alerts.append({
                    "sms_index": i,
                    "raw": raw,
                    "amount": amount,
                    "merchant": merchant,
                    "category": category,
                })
            else:
                append("Transactions", [str(date.today()), amount, merchant, category, "SMS", ""])
                add_spend(amount)
                mark_sms_processed(i)
                processed += 1

    return {
        "processed":       processed,
        "alerts":          alerts,
        "balance_updates": balance_updates,
    }


@app.post("/api/sms/resolve")
def resolve_sms(data: dict):
    sms_index  = data.get("sms_index")
    action     = data.get("action")  # "daily" | "one-time" | "emi" | "skip"
    amount     = data.get("amount", 0)
    merchant   = data.get("merchant", "Unknown")
    category   = data.get("category", "Other")

    if action == "daily":
        append("Transactions", [str(date.today()), amount, merchant, category, "SMS", ""])
        add_spend(amount)
    elif action == "one-time":
        append("Transactions", [str(date.today()), amount, merchant, "Big Purchase", "SMS", "One-time"])
    elif action == "emi":
        append("Transactions", [str(date.today()), amount, merchant, "EMI", "SMS", "Loan payment"])

    if sms_index is not None:
        mark_sms_processed(sms_index)

    return {"status": "ok"}


# ── Transactions ───────────────────────────────────────────────────

class TxIn(BaseModel):
    amount:   float
    merchant: str
    category: str    = "Other"
    notes:    str    = ""
    is_one_time: bool = False

@app.post("/api/transactions")
def add_transaction(tx: TxIn):
    cat = "Big Purchase" if tx.is_one_time else tx.category
    append("Transactions", [str(date.today()), tx.amount, tx.merchant, cat, "Manual", tx.notes])
    if not tx.is_one_time:
        updated = add_spend(tx.amount)
        return {"status": "ok", "today": updated}
    return {"status": "ok"}

@app.get("/api/transactions")
def list_transactions(limit: int = 50):
    records = get_all("Transactions")
    return list(reversed(records[-limit:]))

@app.delete("/api/transactions/last")
def remove_last():
    deleted = delete_last_transaction()
    return {"status": "ok", "deleted": deleted}


# ── Loans ──────────────────────────────────────────────────────────

class LoanIn(BaseModel):
    lender:               str
    principal:            float
    outstanding:          float
    emi:                  float
    next_deduction_date:  str
    foreclosure_amount:   float = 0.0
    notes:                str   = ""

@app.get("/api/loans")
def list_loans():
    return get_all("Loans")

@app.post("/api/loans")
def add_loan(loan: LoanIn):
    append("Loans", [loan.lender, loan.principal, loan.outstanding,
                     loan.emi, loan.next_deduction_date, loan.foreclosure_amount, loan.notes])
    return {"status": "ok"}


# ── Accounts ───────────────────────────────────────────────────────

class AccountIn(BaseModel):
    bank:    str
    balance: float

@app.get("/api/accounts")
def list_accounts():
    return get_all("Accounts")

@app.post("/api/accounts/update")
def update_account(data: AccountIn):
    update_account_balance(data.bank, data.balance)
    return {"status": "ok"}


# ── Budgets ────────────────────────────────────────────────────────

class BudgetIn(BaseModel):
    category:       str
    monthly_budget: float

class MonthlyBudgetIn(BaseModel):
    amount: float

@app.get("/api/budgets")
def list_budgets():
    return get_all("Budgets")

@app.post("/api/budgets/update")
def update_budget(data: BudgetIn):
    update_budget_category(data.category, data.monthly_budget)
    return {"status": "ok"}

@app.post("/api/budgets/monthly")
def set_budget(data: MonthlyBudgetIn):
    set_monthly_budget(data.amount)
    return {"status": "ok", "daily": round(data.amount / 30, 2)}

@app.post("/api/budgets/save-all")
def save_all_budgets(budgets: list):
    ws = get_sheet("Budgets")
    ws.clear()
    ws.append_row(["category", "monthly_budget", "spent_this_month"])
    for b in budgets:
        ws.append_row([b.get("category"), b.get("monthly_budget", 0), b.get("spent_this_month", 0)])
    return {"status": "ok"}


# ── Groq AI Chat ───────────────────────────────────────────────────

class ChatIn(BaseModel):
    messages: List[dict]

@app.post("/api/chat")
def ai_chat(data: ChatIn):
    # Build context
    try:
        today   = get_or_create_today()
        budgets = get_all("Budgets")
        loans   = get_all("Loans")
        accounts = get_all("Accounts")
        context = {
            "today_limit":    today.get("effective_limit"),
            "today_spent":    today.get("spent"),
            "today_remaining": today.get("remaining"),
            "rollover":       today.get("rollover_from_prev"),
            "month_spent":    get_month_spent(),
            "monthly_budget": get_monthly_budget(),
            "budgets":        budgets,
            "loans":          loans,
            "accounts":       accounts,
        }
    except:
        context = {}

    result = groq_chat(data.messages, context)

    # Execute action if Groq returned one
    action_result = None
    if result.get("action"):
        action_result = execute_action(result["action"])

    return {
        "reply":         result["reply"],
        "action":        result.get("action"),
        "action_result": action_result,
    }


def execute_action(action: dict) -> dict:
    t = action.get("type")
    try:
        if t == "update_budget":
            update_budget_category(action["category"], action["amount"])
            return {"success": True, "message": f"Budget updated for {action['category']}"}

        elif t == "add_transaction":
            amount   = action.get("amount", 0)
            merchant = action.get("merchant", "Unknown")
            category = action.get("category", "Other")
            is_one   = action.get("is_one_time", False)
            cat      = "Big Purchase" if is_one else category
            append("Transactions", [str(date.today()), amount, merchant, cat, "Groq AI", ""])
            if not is_one:
                add_spend(amount)
            return {"success": True, "message": f"Transaction ₹{amount} at {merchant} added"}

        elif t == "update_balance":
            update_account_balance(action["bank"], action["balance"])
            return {"success": True, "message": f"{action['bank']} balance updated to ₹{action['balance']}"}

        elif t == "set_monthly_budget":
            set_monthly_budget(action["amount"])
            return {"success": True, "message": f"Monthly budget set to ₹{action['amount']}"}

        elif t == "delete_last_transaction":
            deleted = delete_last_transaction()
            return {"success": True, "message": f"Deleted: {deleted}"}

        elif t == "update_loan":
            from sheets import update_cell_by_key
            field_map = {
                "next_deduction_date": 5,
                "outstanding":         3,
                "foreclosure_amount":  6,
            }
            col = field_map.get(action.get("field"), 5)
            update_cell_by_key("Loans", "lender", action["lender"], col, action["value"])
            return {"success": True}

    except Exception as e:
        return {"success": False, "error": str(e)}

    return {"success": False, "error": "Unknown action"}


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
        return {"raw_text": text.strip(), "detected_amounts": [float(a.replace(",", "")) for a in amounts]}
    except Exception as e:
        return {"error": str(e), "raw_text": "", "detected_amounts": []}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
