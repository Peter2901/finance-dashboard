import re
from datetime import datetime

# ── Transaction patterns ────────────────────────────────────────────
TX_PATTERNS = [
    re.compile(r"Rs\.?\s*(?P<amount>[\d,]+(?:\.\d{1,2})?)\s+paid to\s+(?P<merchant>.+?)\s+via PhonePe", re.I),
    re.compile(r"(?:INR|Rs\.?)\s*(?P<amount>[\d,]+(?:\.\d{1,2})?)\s+debited.*?(?:to|at)\s+(?P<merchant>[A-Za-z0-9\s&]+)", re.I),
    re.compile(r"[Pp]aid\s+(?:INR|Rs\.?)\s*(?P<amount>[\d,]+(?:\.\d{1,2})?)\s+to\s+(?P<merchant>[A-Za-z0-9\s&]+)", re.I),
    re.compile(r"(?:INR|Rs\.?)\s*(?P<amount>[\d,]+(?:\.\d{1,2})?)\s+sent to\s+(?P<merchant>.+?)(?:\s+on|\s+via|$)", re.I),
]

# ── Balance patterns ────────────────────────────────────────────────
BAL_PATTERNS = [
    re.compile(r"(?:Avbl|Avail(?:able)?)\s+(?:Bal(?:ance)?|Amt)\s*(?:is|:)?\s*(?:INR|Rs\.?)?\s*(?P<balance>[\d,]+(?:\.\d{1,2})?)", re.I),
    re.compile(r"(?:Available|Avbl)\s+balance\s*(?:is|:)?\s*(?:INR|Rs\.?)?\s*(?P<balance>[\d,]+(?:\.\d{1,2})?)", re.I),
    re.compile(r"balance\s+(?:is|:)?\s*(?:INR|Rs\.?)?\s*(?P<balance>[\d,]+(?:\.\d{1,2})?)", re.I),
    re.compile(r"(?:INR|Rs\.?)\s*(?P<balance>[\d,]+(?:\.\d{1,2})?)\s+(?:is\s+)?(?:your\s+)?(?:avbl|available|current)\s+bal", re.I),
]

# ── Bank detection ──────────────────────────────────────────────────
BANK_KEYWORDS = {
    "UCO Bank":   ["uco", "ucob"],
    "Kotak Bank": ["kotak", "ktk", "811"],
    "HDFC Bank":  ["hdfc"],
    "SBI":        ["sbi", "state bank"],
    "ICICI":      ["icici"],
    "Axis Bank":  ["axis"],
}

CATEGORY_KEYWORDS = {
    "Groceries":    ["dmart", "bigbasket", "blinkit", "zepto", "grofers", "jiomart", "reliance fresh"],
    "Food":         ["swiggy", "zomato", "mcdonald", "domino", "kfc", "pizza", "burger", "cafe", "restaurant"],
    "Transport":    ["ola", "uber", "rapido", "irctc", "redbus", "metro", "petrol", "fuel"],
    "Bills":        ["jio", "airtel", "bsnl", "electricity", "bescom", "tata power", "gas", "water", "recharge"],
    "Entertainment":["netflix", "hotstar", "prime", "spotify", "bookmyshow", "pvr", "inox"],
    "Health":       ["pharmacy", "apollo", "medplus", "1mg", "netmeds", "hospital", "clinic", "doctor"],
    "EMI":          ["emi", "loan", "bajaj", "hdfc loan", "moneyview"],
}


def detect_bank(text: str) -> str:
    text_lower = text.lower()
    for bank, keywords in BANK_KEYWORDS.items():
        if any(k in text_lower for k in keywords):
            return bank
    return None


def extract_balance(text: str) -> float:
    for pattern in BAL_PATTERNS:
        m = pattern.search(text)
        if m:
            return float(m.group("balance").replace(",", ""))
    return None


def parse_sms(raw: str) -> dict:
    """
    Returns dict with:
      type: 'transaction' | 'balance_update' | 'unknown'
      For transaction: amount, merchant, category
      For balance_update: bank, balance
      Both may include balance if present in SMS
    """
    result = {"type": "unknown", "raw": raw, "parsed_at": datetime.now().isoformat()}

    bank = detect_bank(raw)
    balance = extract_balance(raw)

    # Check transaction patterns
    for pat in TX_PATTERNS:
        m = pat.search(raw)
        if m:
            amount = float(m.group("amount").replace(",", ""))
            merchant = m.group("merchant").strip().rstrip(".")
            result.update({
                "type":     "transaction",
                "amount":   amount,
                "merchant": merchant,
                "category": guess_category(merchant),
                "bank":     bank,
                "balance":  balance,  # may be None or actual balance
            })
            return result

    # Pure balance update (no transaction amount)
    if balance and bank:
        result.update({
            "type":    "balance_update",
            "bank":    bank,
            "balance": balance,
        })
        return result

    return result


def guess_category(merchant: str) -> str:
    m = merchant.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(k in m for k in keywords):
            return cat
    return "Other"


def is_unusual(amount: float, daily_limit: float) -> bool:
    return amount > (daily_limit * 5)
