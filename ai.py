import httpx
import json
import re
import os
from datetime import date

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
USER_NAME = os.getenv("USER_NAME", "Pulkit")

SYSTEM_PROMPT = """You are a smart personal finance assistant. 
Help track expenses, budgets, loans and bank balances.
When asked to DO something, respond with an action block like:
<action>
{"type": "update_budget", "category": "Food", "amount": 4000}
</action>

Action types:
- update_budget: {"type": "update_budget", "category": "Food", "amount": 4000}
- add_transaction: {"type": "add_transaction", "amount": 500, "merchant": "Swiggy", "category": "Food", "is_one_time": false}
- update_balance: {"type": "update_balance", "bank": "Kotak Bank", "balance": 24000}
- set_monthly_budget: {"type": "set_monthly_budget", "amount": 8000}
- delete_last_transaction: {"type": "delete_last_transaction"}

Be friendly and casual. Reply in Hinglish if user writes in Hinglish.
"""

def _call_groq(messages: list) -> str:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": messages,
        "max_tokens": 500,
        "temperature": 0.7,
    }
    with httpx.Client(timeout=30) as client:
        res = client.post(GROQ_URL, headers=headers, json=payload)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]

def chat(messages: list, context: dict = None) -> dict:
    system = SYSTEM_PROMPT
    if context:
        system += f"\n\nUser financial data:\n{json.dumps(context, indent=2)}"

    full_messages = [{"role": "system", "content": system}] + messages

    try:
        reply_text = _call_groq(full_messages)
    except Exception as e:
        return {"reply": f"AI error: {str(e)}", "action": None}

    action = None
    match = re.search(r"<action>(.*?)</action>", reply_text, re.DOTALL)
    if match:
        try:
            action = json.loads(match.group(1).strip())
            reply_text = re.sub(r"<action>.*?</action>", "", reply_text, flags=re.DOTALL).strip()
        except:
            pass

    return {"reply": reply_text, "action": action}

def parse_sms_with_groq(sms_text: str, daily_limit: float) -> dict:
    prompt = f"""Parse this SMS and return ONLY a JSON object with no extra text:
SMS: "{sms_text}"
Daily limit: {daily_limit}

JSON format:
{{"type": "transaction or balance_update or unknown", "amount": 0, "merchant": "name", "category": "Food or Groceries or Transport or Bills or Entertainment or Health or EMI or Other", "is_unusual": false, "bank": "UCO Bank or Kotak Bank or null", "balance": 0, "needs_clarification": false}}"""

    try:
        text = _call_groq([{"role": "user", "content": prompt}])
        text = re.sub(r"```json|```", "", text).strip()
        return json.loads(text)
    except:
        return {"type": "unknown", "needs_clarification": False}
