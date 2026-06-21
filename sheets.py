import gspread
import json
import os
from google.oauth2.service_account import Credentials
from config import SHEET_ID
from datetime import date

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def get_client():
    # On Railway, credentials are stored as environment variable
    creds_json = os.getenv("GOOGLE_CREDENTIALS")
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        # Local development fallback
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    return gspread.authorize(creds)

def get_sheet(tab_name: str):
    gc = get_client()
    sh = gc.open_by_key(SHEET_ID)
    return sh.worksheet(tab_name)

def get_all_records(tab_name: str) -> list:
    ws = get_sheet(tab_name)
    return ws.get_all_records()

def append_row(tab_name: str, row: list):
    ws = get_sheet(tab_name)
    ws.append_row(row, value_input_option="USER_ENTERED")

def get_today_limit_row() -> dict:
    records = get_all_records("Limits")
    today = str(date.today())
    for r in records:
        if r.get("date") == today:
            return r
    return None

def get_unprocessed_sms() -> list:
    records = get_all_records("SMS_Raw")
    return [(i, r) for i, r in enumerate(records)
            if str(r.get("processed", "")).strip().lower() != "yes"]

def mark_sms_processed(row_index: int):
    ws = get_sheet("SMS_Raw")
    ws.update_cell(row_index + 2, 3, "yes")
