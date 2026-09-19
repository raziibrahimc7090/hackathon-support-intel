# backend/analysis_customer.py
# Customer Intelligence module. Owned by Member B.
#
# run_customer_analysis(text) -> dict with:
#   category, sentiment, emotion, priority, status, summary
#
# - sentiment comes from VADER (local, no API call)
# - category/emotion/priority/status/summary come from ONE Gemini 1.5 Flash call
# - Gemini is prompted to return raw JSON only (no markdown fences)
# - try/except fallback returns safe contract-valid defaults on any parse failure
 
import os
import json
import re
 
import google.generativeai as genai
from dotenv import load_dotenv
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
 
load_dotenv()
 
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set. Check your .env file.")
 
genai.configure(api_key=GEMINI_API_KEY)
_model = genai.GenerativeModel("gemini-1.5-flash") 
_vader = SentimentIntensityAnalyzer()
 
# STRICT VALUES — must match the API contract exactly
VALID_CATEGORIES = {"Billing", "Login", "Delivery", "Refund", "Technical", "Security", "Other"}
VALID_EMOTIONS = {"Frustration", "Anger", "Confusion", "Urgency", "Satisfaction", "None"}
VALID_PRIORITIES = {"Low", "Medium", "High", "Critical"}
VALID_STATUSES = {"Resolved", "Unresolved"}
 
FALLBACK_RESULT = {
    "category": "Other",
    "emotion": "None",
    "priority": "Medium",
    "status": "Unresolved",
    "summary": "Unable to generate summary due to a processing error.",
}
 
_GEMINI_PROMPT_TEMPLATE = """You are a customer support ticket classifier.
Analyze the customer message below and return ONLY a raw JSON object — no markdown code fences, no explanation, no extra text before or after.
 
The JSON object must have exactly these keys with these exact allowed values:
- "category": one of ["Billing", "Login", "Delivery", "Refund", "Technical", "Security", "Other"]
- "emotion": one of ["Frustration", "Anger", "Confusion", "Urgency", "Satisfaction", "None"]
- "priority": one of ["Low", "Medium", "High", "Critical"]
- "status": one of ["Resolved", "Unresolved"]
- "summary": a one-line summary of the message, under 20 words
 
Customer message:
\"\"\"{text}\"\"\"
 
Return ONLY the JSON object.
"""
 
 
def _strip_markdown_fences(raw: str) -> str:
    """Safety net: strips ```json ... ``` or ``` ... ``` wrapping if Gemini adds it anyway."""
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()
 
 
def _validate_gemini_result(parsed: dict) -> dict:
    """Ensures every field is present and within STRICT VALUES; falls back per-field if not."""
    category = parsed.get("category")
    emotion = parsed.get("emotion")
    priority = parsed.get("priority")
    status = parsed.get("status")
    summary = parsed.get("summary")
 
    return {
        "category": category if category in VALID_CATEGORIES else FALLBACK_RESULT["category"],
        "emotion": emotion if emotion in VALID_EMOTIONS else FALLBACK_RESULT["emotion"],
        "priority": priority if priority in VALID_PRIORITIES else FALLBACK_RESULT["priority"],
        "status": status if status in VALID_STATUSES else FALLBACK_RESULT["status"],
        "summary": summary if isinstance(summary, str) and summary.strip() else FALLBACK_RESULT["summary"],
    }
 
 
def _get_sentiment(text: str) -> str:
    """VADER-based sentiment — Positive / Neutral / Negative, no API call."""
    scores = _vader.polarity_scores(text)
    compound = scores["compound"]
    if compound >= 0.05:
        return "Positive"
    elif compound <= -0.05:
        return "Negative"
    return "Neutral"
 
 
def _call_gemini(text: str) -> dict:
    prompt = _GEMINI_PROMPT_TEMPLATE.format(text=text)
    response = _model.generate_content(prompt)
    raw_output = response.text
    cleaned = _strip_markdown_fences(raw_output)
    parsed = json.loads(cleaned)
    return _validate_gemini_result(parsed)
 
 
def run_customer_analysis(text: str) -> dict:
    """
    Main entrypoint. Returns:
    {
      "category": str, "sentiment": str, "emotion": str,
      "priority": str, "status": str, "summary": str
    }
    """
    sentiment = _get_sentiment(text)
 
    try:
        gemini_result = _call_gemini(text)
    except (json.JSONDecodeError, KeyError, AttributeError, Exception):
        gemini_result = FALLBACK_RESULT
 
    return {
        "category": gemini_result["category"],
        "sentiment": sentiment,
        "emotion": gemini_result["emotion"],
        "priority": gemini_result["priority"],
        "status": gemini_result["status"],
        "summary": gemini_result["summary"],
    }
 
 
if __name__ == "__main__":
    # Quick manual test — run `python analysis_customer.py` from backend/
    test_messages = [
        "My package was supposed to arrive 5 days ago and I still have nothing. This is unacceptable!",
        "Thanks so much for fixing my login issue so quickly, really appreciate it.",
        "I was charged twice for my subscription this month, please refund the extra charge immediately.",
        "I can't log into my account, it keeps saying invalid password even though I reset it.",
        "URGENT: your account will be suspended in 24 hours unless you verify your password at this link.",
    ]
 
    for i, msg in enumerate(test_messages, start=1):
        result = run_customer_analysis(msg)
        print(f"--- Message {i} ---")
        print("Text:", msg)
        print("Result:", json.dumps(result, indent=2))
        print()