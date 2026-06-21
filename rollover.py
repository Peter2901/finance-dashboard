from datetime import date, timedelta
from sheets import get_all_records, append_row, get_today_limit_row, get_sheet
from config import BASE_DAILY_LIMIT

def get_or_create_today_limit() -> dict:
    today_row = get_today_limit_row()
    if today_row:
        return today_row

    records = get_all_records("Limits")
    today = date.today()
    rollover = 0.0

    if records:
        yesterday = str(today - timedelta(days=1))
        yesterday_row = next((r for r in records if r.get("date") == yesterday), None)
        if yesterday_row:
            rollover = float(yesterday_row.get("remaining", 0))

    effective = max(0, BASE_DAILY_LIMIT + rollover)

    new_row = {
        "date": str(today),
        "base_limit": BASE_DAILY_LIMIT,
        "rollover_from_prev": rollover,
        "effective_limit": effective,
        "spent": 0.0,
        "remaining": effective,
    }

    append_row("Limits", [
        new_row["date"],
        new_row["base_limit"],
        new_row["rollover_from_prev"],
        new_row["effective_limit"],
        new_row["spent"],
        new_row["remaining"],
    ])

    return new_row

def add_spend_to_today(amount: float) -> dict:
    ws = get_sheet("Limits")
    records = ws.get_all_records()
    today = str(date.today())

    for i, row in enumerate(records):
        if row.get("date") == today:
            new_spent = float(row["spent"]) + amount
            new_remaining = float(row["effective_limit"]) - new_spent
            row_number = i + 2
            ws.update(f"E{row_number}:F{row_number}", [[new_spent, new_remaining]])
            return {**row, "spent": new_spent, "remaining": new_remaining}

    get_or_create_today_limit()
    return add_spend_to_today(amount)

def get_weekly_history() -> list:
    records = get_all_records("Limits")
    return records[-7:] if len(records) >= 7 else records
