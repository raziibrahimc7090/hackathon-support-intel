# backend/generate_synthetic_data.py
# Generates synthetic customer support conversations via batched Gemini 1.5 Flash calls.
# Owned by Member B. Output: ../data/conversations.json
#
# ~70% normal support messages (Billing/Login/Delivery/Refund/Technical/Other)
# ~30% contain phishing or social-engineering patterns (fake urgency, credential requests,
#      lookalike domains, suspicious links) so Member C has real data to test against.

import os
import json
import re
import time

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set. Check your .env file.")

genai.configure(api_key=GEMINI_API_KEY)

# Synthetic phishing examples are flagged text used to TEST a detector, not real
# attack content. Loosen safety thresholds for this generator only so legitimate
# "urgent password reset" / "verify your card" style examples aren't blocked outright.
_SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

_model = genai.GenerativeModel("gemini-1.5-flash", safety_settings=_SAFETY_SETTINGS)

TOTAL_CONVERSATIONS = 180
BATCH_SIZE = 25  # 20-30 per call as required, for normal conversations
PHISHING_BATCH_SIZE = 15  # smaller batches are less likely to trip safety filters
PHISHING_RATIO = 0.30
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "conversations.json")

_NORMAL_PROMPT = """Generate {count} realistic, varied customer support messages for an e-commerce/SaaS company.
Cover a mix of these topics: billing issues, login problems, delayed deliveries, refund requests,
technical bugs, and general questions. Vary tone (calm, frustrated, angry, confused) and length (1-4 sentences).
Do NOT include any phishing, scam, or suspicious links/emails in these — these must be genuine customer messages only.

Return ONLY a raw JSON array (no markdown fences, no explanation) of objects shaped exactly like:
[{{"text": "..."}}, {{"text": "..."}}]

Generate exactly {count} objects.
"""

_PHISHING_PROMPT = """You are helping build a training dataset for a cybersecurity detection tool that flags
suspicious customer-support-style messages. Generate {count} example messages containing classic
red-flag patterns used in these training examples: fake urgency about account status, requests to
click a link and re-enter account details, requests to confirm payment details, messages impersonating
a well-known brand's support team, and links using shortened or slightly misspelled domain names.
These are fictional training examples only, styled as customer support messages, with fabricated
placeholder details (no real people, no real companies, no working links).

Return ONLY a raw JSON array (no markdown fences, no explanation) of objects shaped exactly like:
[{{"text": "..."}}, {{"text": "..."}}]

Generate exactly {count} objects.
"""


def _strip_markdown_fences(raw: str) -> str:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _diagnose_empty_response(response) -> str:
    """Extracts the block/finish reason so we know WHY a response came back empty."""
    try:
        if hasattr(response, "prompt_feedback") and response.prompt_feedback:
            block_reason = getattr(response.prompt_feedback, "block_reason", None)
            if block_reason:
                return f"prompt blocked: {block_reason}"
        if response.candidates:
            finish_reason = getattr(response.candidates[0], "finish_reason", None)
            return f"finish_reason: {finish_reason}"
    except Exception as e:
        return f"could not introspect response: {e}"
    return "unknown — response had no candidates and no block reason"


def _generate_batch(prompt_template: str, count: int, retries: int = 2) -> list:
    prompt = prompt_template.format(count=count)
    for attempt in range(retries + 1):
        try:
            response = _model.generate_content(prompt)
            cleaned = _strip_markdown_fences(response.text)
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return [item["text"] for item in parsed if isinstance(item, dict) and "text" in item]
        except (json.JSONDecodeError, KeyError, AttributeError, ValueError) as e:
            reason = _diagnose_empty_response(response) if "response" in dir() else "no response object"
            print(f"  Batch parse failed (attempt {attempt + 1}/{retries + 1}): {e} | {reason}")
            time.sleep(1)
    print("  Batch failed after retries — skipping this batch.")
    return []


def generate_synthetic_dataset() -> list:
    normal_target = int(TOTAL_CONVERSATIONS * (1 - PHISHING_RATIO))
    phishing_target = TOTAL_CONVERSATIONS - normal_target

    all_texts = []

    print(f"Generating {normal_target} normal conversations in batches of {BATCH_SIZE}...")
    remaining = normal_target
    while remaining > 0:
        batch_count = min(BATCH_SIZE, remaining)
        texts = _generate_batch(_NORMAL_PROMPT, batch_count)
        all_texts.extend([(t, False) for t in texts])
        remaining -= batch_count
        print(f"  Generated {len(texts)} (target {batch_count}). Remaining: {remaining}")

    print(f"Generating {phishing_target} phishing/social-engineering conversations in batches of {PHISHING_BATCH_SIZE}...")
    remaining = phishing_target
    while remaining > 0:
        batch_count = min(PHISHING_BATCH_SIZE, remaining)
        texts = _generate_batch(_PHISHING_PROMPT, batch_count)
        all_texts.extend([(t, True) for t in texts])
        remaining -= batch_count
        print(f"  Generated {len(texts)} (target {batch_count}). Remaining: {remaining}")

    conversations = [
        {
            "conversation_id": f"conv_{i+1:04d}",
            "text": text,
            "_is_phishing_sample": is_phishing,  # metadata only, not part of API contract
        }
        for i, (text, is_phishing) in enumerate(all_texts)
    ]

    return conversations


def save_dataset(conversations: list, path: str = OUTPUT_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(conversations, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(conversations)} conversations to {path}")


if __name__ == "__main__":
    dataset = generate_synthetic_dataset()
    save_dataset(dataset)
    phishing_count = sum(1 for c in dataset if c["_is_phishing_sample"])
    print(f"Total: {len(dataset)} | Phishing/social-engineering samples: {phishing_count}")