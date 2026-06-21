import httpx
import json
import re
import os
from datetime import date

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
USER_NAME = os.getenv("USER_NAME", "Pulkit")

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


def _call_gemini(prompt: str) -> str:
    url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 500, "temperature": 0.7}
    }
    with httpx.Client(timeout=30) as client:
        res = client.post(url, json=payload)
        res.raise_for_status()
        return res.json()["candidates"][0]["content"]["parts"][0]["text"]


def chat(messages: list, context: dict = None) -> dict:
    # Build full prompt
    context_str = ""
    if context:
        context_str = f"\n\nCurrent user financial data:\n{json.dumps(context, indent=2)}"

    conversation = ""
    for msg in messages:
        role = "User" if msg["role"] == "user" else "Assistant"
        conversation += f"\n{role}: {msg['content']}"

    full_prompt = f"{SYSTEM_PROMPT}{context_str}\n\nConversation:{conversation}\n\nAssistant:"

    try:
        reply_text = _call_gemini(full_prompt)
    except Exception as e:
        return {"reply": f"AI error: {str(e)}", "action": None}

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
    prompt = f"""Parse this bank/payment SMS and return ONLY a JSON object (no markdown, no extra text):
SMS: "{sms_text}"
User daily limit: {daily_limit}

Return JSON:
{{
  "type": "transaction" or "balance_update" or "unknown",
  "amount": number or null,
  "merchant": "string" or null,
  "category": "Food" or "Groceries" or "Transport" or "Bills" or "Entertainment" or "Health" or "EMI" or "Other",
  "is_unusual": true or false,
  "bank": "UCO Bank" or "Kotak Bank" or "HDFC Bank" or null,
  "balance": number or null,
  "needs_clarification": true or false
}}"""

    try:
        text = _call_gemini(prompt)
        text = re.sub(r"```json|```", "", text).strip()
        return json.loads(text)
    except:
        return {"type": "unknown", "needs_clarification": False}
