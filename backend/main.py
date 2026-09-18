# backend/main.py
# FastAPI entrypoint. Owned by Member A.
# Routes: POST /analyze, POST /analyze-batch, GET /dashboard-data, GET /health
# run_customer_analysis() and run_security_analysis() are stubbed here so the
# server is runnable end-to-end before Phases 4-5 replace the stubs with real logic.

import json
from typing import List

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import init_db, insert_conversation, get_dashboard_stats

app = FastAPI(title="Customer Support Intelligence & Phishing Detection API")

# CORS: allow the local frontend (index.html opened via file:// or a local static server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # hackathon scope — tighten if time allows
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


# ---------- Request/Response models ----------

class AnalyzeRequest(BaseModel):
    conversation_id: str
    text: str


# ---------- STUBBED analysis functions ----------
# Member B replaces run_customer_analysis() in analysis_customer.py (Phase 4)
# Member C replaces run_security_analysis() in analysis_security.py (Phase 5)
# Until then, these dummy implementations return contract-shaped data.

def run_customer_analysis(text: str) -> dict:
    """STUB — replaced by backend/analysis_customer.py in Phase 4."""
    return {
        "category": "Other",
        "sentiment": "Neutral",
        "emotion": "None",
        "priority": "Low",
        "status": "Unresolved",
        "summary": "Stubbed summary — customer intelligence module not yet wired in.",
    }


def run_security_analysis(text: str) -> dict:
    """STUB — replaced by backend/analysis_security.py in Phase 5."""
    return {
        "threat_detected": False,
        "threat_type": "None",
        "urls_found": [],
        "suspicious_urls": [],
        "emails_found": [],
        "suspicious_emails": [],
        "social_engineering_flags": [],
        "risk_level": "Low",
    }


def build_analysis_result(conversation_id: str, text: str) -> dict:
    """Combines customer + security analysis into the exact API contract shape."""
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
    }


# ---------- Routes ----------

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    try:
        result = build_analysis_result(request.conversation_id, request.text)

        # Persist to DB — include raw text for storage (not part of the API response contract)
        insert_conversation({**result, "text": request.text})

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/analyze-batch")
async def analyze_batch(file: UploadFile = File(...)):
    try:
        raw = await file.read()

        if file.filename.endswith(".json"):
            conversations = json.loads(raw)
        elif file.filename.endswith(".csv"):
            import pandas as pd
            import io
            df = pd.read_csv(io.BytesIO(raw))
            conversations = df.to_dict(orient="records")
        else:
            raise HTTPException(status_code=400, detail="File must be .json or .csv")

        results: List[dict] = []
        for convo in conversations:
            conversation_id = str(convo.get("conversation_id"))
            text = str(convo.get("text", ""))

            result = build_analysis_result(conversation_id, text)
            insert_conversation({**result, "text": text})
            results.append(result)

        return results

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch analysis failed: {str(e)}")


@app.get("/dashboard-data")
def dashboard_data():
    try:
        return get_dashboard_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch dashboard data: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)