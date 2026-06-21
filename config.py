import os
from dotenv import load_dotenv

load_dotenv()

SHEET_ID         = os.getenv("SHEET_ID", "1Lnt5EplBURfGtEqDOnbXN7zkc9nUCQBFo5z14LH_sT8")
BASE_DAILY_LIMIT = float(os.getenv("BASE_DAILY_LIMIT", "100"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
USER_NAME        = os.getenv("USER_NAME", "Pulkit")
