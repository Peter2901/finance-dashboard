from datetime import date, timedelta, datetime
import calendar
from sheets import get_all, append, get_today_limit, get_sheet, get_monthly_budget
from config import BASE_DAILY_LIMIT


def days_remaining_in_month() -> int:
    today = date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]
    return last_day - today.day + 1  # include today


def total_days_in_month() -> int:
    today = date.today()
    return calendar.monthrange(today.year, today.month)[1]


def calc_base_daily() -> float:
    monthly = get_monthly_budget()
    if monthly > 0:
        return round(monthly / total_days_in_month(), 2)
    return BASE_DAILY_LIMIT


def get_or_create_today() -> dict:
    today_row = get_today_limit()
    if today_row:
        return today_row

    today = date.today()
    records = get_all("Limits")
    base_daily = calc_base_daily()
    rollover = 0.0

    if records:
        yesterday = str(today - timedelta(days=1))
        prev = next((r for r in records if r.get("date") == yesterday), None)
        if prev:
            remaining = float(prev.get("remaining", 0))
            # Spread over remaining days (both over and underspend)
            days_left = days_remaining_in_month()
            if days_left > 1:
                rollover = round(remaining / (days_left - 1), 2) if remaining != 0 else 0
            else:
                rollover = remaining

    effective = max(0, base_daily + rollover)

    new_row = {
        "date":              str(today),
        "base_limit":        base_daily,
        "rollover_from_prev": rollover,
        "effective_limit":   effective,
        "spent":             0.0,
        "remaining":         effective,
    }

    append("Limits", [
        new_row["date"],
        new_row["base_limit"],
        new_row["rollover_from_prev"],
        new_row["effective_limit"],
        new_row["spent"],
        new_row["remaining"],
    ])
    return new_row


def add_spend(amount: float) -> dict:
    ws = get_sheet("Limits")
    records = ws.get_all_records()
    today = str(date.today())

    for i, row in enumerate(records):
        if row.get("date") == today:
            new_spent     = float(row["spent"]) + amount
            new_remaining = float(row["effective_limit"]) - new_spent
            row_num = i + 2
            ws.update(f"E{row_num}:F{row_num}", [[new_spent, new_remaining]])
            return {**row, "spent": new_spent, "remaining": new_remaining}

    get_or_create_today()
    return add_spend(amount)


def get_week_history(days: int = 7) -> list:
    records = get_all("Limits")
    return records[-days:] if len(records) >= days else records


def get_month_spent() -> float:
    records = get_all("Transactions")
    today = date.today()
    total = 0.0
    for r in records:
        try:
            tx_date = date.fromisoformat(str(r.get("date", "")))
            if tx_date.year == today.year and tx_date.month == today.month:
                total += float(r.get("amount", 0))
        except:
            pass
    return round(total, 2)
