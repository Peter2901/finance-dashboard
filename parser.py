import re
from datetime import datetime

PATTERNS = [
    re.compile(r"Rs\.?\s*(?P<amount>[\d,]+(?:\.\d{1,2})?)\s+paid to\s+(?P<merchant>.+?)\s+via PhonePe", re.IGNORECASE),
    re.compile(r"(?:INR|Rs\.?)\s*(?P<amount>[\d,]+(?:\.\d{1,2})?)\s+debited.*?(?:to|at)\s+(?P<merchant>[A-Za-z0-9\s&]+)", re.IGNORECASE),
    re.compile(r"[Pp]aid\s+(?:INR|Rs\.?)\s*(?P<amount>[\d,]+(?:\.\d{1,2})?)\s+to\s+(?P<merchant>[A-Za-z0-9\s&]+)", re.IGNORECASE),
    re.compile(r"(?:INR|Rs\.?)\s*(?P<amount>[\d,]+(?:\.\d{1,2})?)\s+sent to\s+(?P<merchant>.+?)(?:\s+on|\s+via|$)", re.IGNORECASE),
]

CATEGORY_KEYWORDS = {
    "Groceries": ["dmart", "bigbasket", "grofers", "blinkit", "zepto", "reliance fresh", "jiomart"],
    "Food":      ["swiggy", "zomato", "mcdonald", "domino", "kfc", "pizza", "burger", "cafe"],
    "Transport": ["ola", "uber", "rapido", "irctc", "redbus", "metro"],
    "Bills":     ["bsnl", "jio", "airtel", "electricity", "bescom", "tata power", "gas", "water"],
    "Entertainment": ["netflix", "hotstar", "prime", "spotify", "bookmyshow", "pvr", "inox"],
    "Health":    ["pharmacy", "apollo", "medplus", "1mg", "netmeds", "hospital", "clinic"],
}

def parse_sms(raw_text: str) -> dict:
    for pattern in PATTERNS:
        m = pattern.search(raw_text)
        if m:
            amount = float(m.group("amount").replace(",", ""))
            merchant = m.group("merchant").strip().rstrip(".")
            return {
                "amount": amount,
                "merchant": merchant,
                "category": guess_category(merchant),
                "parsed_at": datetime.now().isoformat(),
            }
    return None

def guess_category(merchant: str) -> str:
    m = merchant.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(k in m for k in keywords):
            return cat
    return "Other"
