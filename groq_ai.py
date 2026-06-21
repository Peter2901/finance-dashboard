import httpx
import json
import re
from config import GROQ_API_KEY, USER_NAME
from datetime import date

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json",
}

SYSTEM_PROMPT = f"""You are a smart personal finance assistant for {USER_NAME}'s finance app called "Hey {USER_NAME}!".
You can both answer questions AND perform actions on their data.

When the user asks you to DO something, respond with a JSON action block like this:
<action>
{{
  "type": "update_budget",
  "category": "Food",
  "amount": 4000
}}
</action>

Available action types:
- update_budget: {{"type": "update_budget", "category": "Food", "amount": 4000}}
- add_transaction: {{"type": "add_transaction", "amount": 500, "merchant": "Swiggy", "category": "Food", "is_one_time": false}}
- update_balance: {{"type": "update_balance", "bank": "Kotak Bank", "balance": 24000}}
- set_monthly_budget: {{"type": "set_monthly_budget", "amount": 8000}}
- delete_last_transaction: {{"type": "delete_last_transaction"}}
- update_loan: {{"type": "update_loan", "lender": "HDFC", "field": "next_deduction_date", "value": "2025-08-05"}}

For questions, just answer naturally in 1-2 sentences. Be friendly and casual.
Always confirm what action you took after doing it.
If the user writes in Hinglish or Hindi, reply in the same mix.
Today's date is {date.today().strftime('%d %B %Y')}.
"""


def _call_groq(messages: list, max_tokens: int = 500, temperature: float = 0.7) -> str:
    payload = {
        "model": "llama3-70b-8192",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    with httpx.Client(timeout=30) as client:
        res = client.post(GROQ_URL, headers=HEADERS, json=payload)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]


def chat(messages: list, context: dict = None) -> dict:
    system = SYSTEM_PROMPT
    if context:
        system += f"\n\nCurrent user data:\n{json.dumps(context, indent=2)}"

    full_messages = [{"role": "system", "content": system}] + messages

    reply_text = _call_groq(full_messages)

    # Extract action if present
    action = None
    action_match = re.search(r"<action>(.*?)</action>", reply_text, re.DOTALL)
    if action_match:
        try:
            action = json.loads(action_match.group(1).strip())
            reply_text = re.sub(r"<action>.*?</action>", "", reply_text, flags=re.DOTALL).strip()
        except:
            pass

    return {"reply": reply_text, "action": action}


def parse_sms_with_groq(sms_text: str, daily_limit: float) -> dict:
    prompt = f"""Parse this bank/payment SMS and return ONLY a JSON object (no other text):
SMS: "{sms_text}"
User's daily limit: {daily_limit}

Return JSON with these fields:
- type: "transaction" | "balance_update" | "unknown"
- amount: number (if transaction)
- merchant: string (if transaction)
- category: "Food"|"Groceries"|"Transport"|"Bills"|"Entertainment"|"Health"|"EMI"|"Other"
- is_unusual: boolean (true if amount > 5x daily limit)
- bank: "UCO Bank"|"Kotak Bank"|"HDFC Bank"|null
- balance: number (available balance if mentioned, else null)
- needs_clarification: boolean (true if unusual or unclear)
"""
    try:
        text = _call_groq([{"role": "user", "content": prompt}], max_tokens=200, temperature=0.1)
        text = re.sub(r"```json|```", "", text).strip()
        return json.loads(text)
    except:
        return {"type": "unknown", "needs_clarification": False}
