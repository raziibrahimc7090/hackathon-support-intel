# backend/batch_processor.py
# Data pipeline for batch processing. Owned by Member D.
#
# process_csv_or_json(filepath) -> list[dict]
# Reads a .csv or .json file of {conversation_id, text}, runs each conversation
# through run_customer_analysis() and run_security_analysis(), merges into the
# full API-contract shape, inserts into PostgreSQL, and returns the results.

import os
import json
import pandas as pd

from analysis_customer import run_customer_analysis
from analysis_security import run_security_analysis
from database import insert_conversation


def _load_conversations(filepath: str) -> list:
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".json":
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("JSON file must contain a top-level array of conversation objects.")
        return data

    elif ext == ".csv":
        df = pd.read_csv(filepath)
        required_cols = {"conversation_id", "text"}
        if not required_cols.issubset(set(df.columns)):
            raise ValueError(f"CSV must contain columns: {required_cols}")
        return df.to_dict(orient="records")

    else:
        raise ValueError("File must be .json or .csv")


def _build_full_result(conversation_id: str, text: str) -> dict:
    customer_result = run_customer_analysis(text)
    security_result = run_security_analysis(text)

    return {
        "conversation_id": conversation_id,
        "category": customer_result["category"],
        "sentiment": customer_result["sentiment"],
        "emotion": customer_result["emotion"],
        "priority": customer_result["priority"],
        "status": customer_result["status"],
        "summary": customer_result["summary"],
        "security": security_result,
        "text": text,  # kept for DB storage; stripped before returning API-contract response
    }


def process_csv_or_json(filepath: str, save_to_db: bool = True) -> list:
    """
    Processes every conversation in filepath through both analysis engines.
    Returns a list of results matching the exact API contract shape
    (the internal "text" field is stripped from each returned dict).
    """
    raw_conversations = _load_conversations(filepath)

    results = []
    errors = []

    for i, convo in enumerate(raw_conversations):
        conversation_id = str(convo.get("conversation_id", f"unknown_{i}"))
        text = str(convo.get("text", ""))

        if not text.strip():
            errors.append({"conversation_id": conversation_id, "error": "empty text field"})
            continue

        try:
            full_result = _build_full_result(conversation_id, text)

            if save_to_db:
                db_result = insert_conversation(full_result)
                if not db_result["success"]:
                    errors.append({"conversation_id": conversation_id, "error": db_result["error"]})

            # API-contract response excludes the internal "text" field
            api_result = {k: v for k, v in full_result.items() if k != "text"}
            results.append(api_result)

        except Exception as e:
            errors.append({"conversation_id": conversation_id, "error": str(e)})

    print(f"Processed {len(results)} conversations successfully. {len(errors)} errors.")
    if errors:
        print("Errors:", json.dumps(errors, indent=2))

    return results


if __name__ == "__main__":
    # Quick manual test — run `python batch_processor.py` from backend/
    data_path = os.path.join(os.path.dirname(__file__), "..", "data", "conversations.json")
    results = process_csv_or_json(data_path, save_to_db=True)
    print(f"\nTotal results: {len(results)}")
    if results:
        print("Sample result:", json.dumps(results[0], indent=2))
        