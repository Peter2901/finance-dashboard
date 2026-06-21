import gspread
import json
import os
from google.oauth2.service_account import Credentials
from config import SHEET_ID
from datetime import date, datetime

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def get_client():
    creds_json = os.getenv("GOOGLE_CREDENTIALS")
    if creds_json:
        creds = Credentials.from_service_account_info(json.loads(creds_json), scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    return gspread.authorize(creds)

def get_sheet(tab: str):
    return get_client().open_by_key(SHEET_ID).worksheet(tab)

def get_all(tab: str) -> list:
    return get_sheet(tab).get_all_records()

def append(tab: str, row: list):
    get_sheet(tab).append_row(row, value_input_option="USER_ENTERED")

def get_today_limit() -> dict:
    today = str(date.today())
    for r in get_all("Limits"):
        if r.get("date") == today:
            return r
    return None

def get_unprocessed_sms() -> list:
    return [(i, r) for i, r in enumerate(get_all("SMS_Raw"))
            if str(r.get("processed", "")).strip().lower() != "yes"]

def mark_sms_processed(idx: int):
    get_sheet("SMS_Raw").update_cell(idx + 2, 3, "yes")

def update_cell_by_key(tab: str, key_col: str, key_val: str, update_col: int, value):
    ws = get_sheet(tab)
    records = ws.get_all_records()
    for i, row in enumerate(records):
        if str(row.get(key_col, "")).strip().lower() == str(key_val).strip().lower():
            ws.update_cell(i + 2, update_col, value)
            return True
    return False

def update_account_balance(bank_name: str, balance: float):
    ws = get_sheet("Accounts")
    records = ws.get_all_records()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    for i, row in enumerate(records):
        if bank_name.lower() in str(row.get("bank", "")).lower():
            ws.update_cell(i + 2, 3, balance)
            ws.update_cell(i + 2, 4, now)
            return True
    append("Accounts", [bank_name, bank_name, balance, now])
    return True

def update_budget_category(category: str, new_budget: float):
    ws = get_sheet("Budgets")
    records = ws.get_all_records()
    for i, row in enumerate(records):
        if str(row.get("category", "")).lower() == category.lower():
            ws.update_cell(i + 2, 2, new_budget)
            return True
    append("Budgets", [category, new_budget, 0])
    return True

def delete_last_transaction():
    ws = get_sheet("Transactions")
    records = ws.get_all_records()
    if records:
        ws.delete_rows(len(records) + 1)
        return records[-1]
    return None

def get_monthly_budget() -> float:
    try:
        records = get_all("Settings")
        for r in records:
            if r.get("key") == "monthly_budget":
                return float(r.get("value", 0))
    except:
        pass
    return 0.0

def set_monthly_budget(amount: float):
    try:
        ws = get_sheet("Settings")
        records = ws.get_all_records()
        for i, row in enumerate(records):
            if row.get("key") == "monthly_budget":
                ws.update_cell(i + 2, 2, amount)
                return
        ws.append_row(["monthly_budget", amount])
    except:
        append("Settings", ["monthly_budget", amount])
