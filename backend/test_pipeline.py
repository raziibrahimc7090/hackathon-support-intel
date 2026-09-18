# backend/test_pipeline.py
# Integration test script. Owned by Member D.
# Posts sample conversations to /analyze, then uploads data/conversations.json to /analyze-batch.
# Run this AFTER starting the server: `uvicorn main:app --reload`

import os
import json
import requests

BASE_URL = "http://localhost:8000"

SAMPLE_CONVERSATIONS = [
    {"conversation_id": "test_001", "text": "My order #8821 hasn't arrived and it's been 10 days."},
    {"conversation_id": "test_002", "text": "Thank you for resolving my billing issue so fast!"},
    {"conversation_id": "test_003", "text": "I can't log in, it says my password is wrong every time."},
    {"conversation_id": "test_004", "text": "I want a refund for my last two charges, this is ridiculous."},
    {"conversation_id": "test_005", "text": "The app keeps crashing whenever I try to check out."},
    # Phishing examples
    {"conversation_id": "test_006", "text": (
        "URGENT: Your account will be suspended in 24 hours. Verify your password immediately "
        "at http://paypa1-secure.com/verify or contact billing@paypa1-support.net"
    )},
    {"conversation_id": "test_007", "text": (
        "Please confirm your card number at http://192.168.1.5/login or use this link bit.ly/3xJk9Q"
    )},
]


def test_health():
    print("=== /health ===")
    resp = requests.get(f"{BASE_URL}/health")
    print(resp.status_code, resp.json())
    assert resp.status_code == 200


def test_analyze_single():
    print("\n=== POST /analyze (single conversations) ===")
    for convo in SAMPLE_CONVERSATIONS:
        resp = requests.post(f"{BASE_URL}/analyze", json=convo)
        if resp.status_code != 200:
            print(f"FAILED [{convo['conversation_id']}]: {resp.status_code} {resp.text}")
            continue

        result = resp.json()
        print(
            f"[{result['conversation_id']}] "
            f"category={result['category']} sentiment={result['sentiment']} "
            f"priority={result['priority']} status={result['status']} | "
            f"threat={result['security']['threat_detected']} "
            f"type={result['security']['threat_type']} "
            f"risk={result['security']['risk_level']}"
        )


def test_analyze_batch():
    print("\n=== POST /analyze-batch (conversations.json) ===")
    data_path = os.path.join(os.path.dirname(__file__), "..", "data", "conversations.json")

    if not os.path.exists(data_path):
        print(f"SKIPPED — {data_path} not found. Run generate_synthetic_data.py first.")
        return

    with open(data_path, "rb") as f:
        resp = requests.post(
            f"{BASE_URL}/analyze-batch",
            files={"file": ("conversations.json", f, "application/json")},
        )

    if resp.status_code != 200:
        print(f"FAILED: {resp.status_code} {resp.text}")
        return

    results = resp.json()
    print(f"Batch processed: {len(results)} conversations")

    threats = [r for r in results if r["security"]["threat_detected"]]
    print(f"Threats detected: {len(threats)} / {len(results)}")

    sentiment_counts = {}
    for r in results:
        sentiment_counts[r["sentiment"]] = sentiment_counts.get(r["sentiment"], 0) + 1
    print("Sentiment distribution:", sentiment_counts)

    risk_counts = {}
    for r in results:
        risk_counts[r["security"]["risk_level"]] = risk_counts.get(r["security"]["risk_level"], 0) + 1
    print("Risk level distribution:", risk_counts)


def test_dashboard_data():
    print("\n=== GET /dashboard-data ===")
    resp = requests.get(f"{BASE_URL}/dashboard-data")
    print(resp.status_code, json.dumps(resp.json(), indent=2))
    assert resp.status_code == 200


if __name__ == "__main__":
    test_health()
    test_analyze_single()
    test_analyze_batch()
    test_dashboard_data()
    print("\n=== Pipeline test complete ===")

    