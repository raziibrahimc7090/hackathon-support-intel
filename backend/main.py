# backend/main.py

import json
from typing import List

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import init_db, insert_conversation, get_dashboard_stats
from analysis_customer import run_customer_analysis
from analysis_security import run_security_analysis


app = FastAPI(
    title="Customer Support Intelligence & Phishing Detection API"
)


# ---------- CORS ----------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Startup ----------

@app.on_event("startup")
def on_startup():
    init_db()


# ---------- Request Models ----------

class AnalyzeRequest(BaseModel):
    conversation_id: str
    text: str


# ---------- Analysis ----------

def build_analysis_result(conversation_id: str, text: str) -> dict:
    """
    Run customer intelligence and security analysis,
    then combine both results into the API response.
    """

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


# ---------- Health ----------

@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }


# ---------- Single Analysis ----------

@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    try:
        result = build_analysis_result(
            request.conversation_id,
            request.text
        )

        # Store the complete result in the database
        insert_conversation({
            **result,
            "text": request.text
        })

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )


# ---------- Batch Analysis ----------

@app.post("/analyze-batch")
async def analyze_batch(file: UploadFile = File(...)):
    try:
        raw = await file.read()

        # JSON input
        if file.filename and file.filename.lower().endswith(".json"):
            conversations = json.loads(raw)

        # CSV input
        elif file.filename and file.filename.lower().endswith(".csv"):
            import pandas as pd
            import io

            df = pd.read_csv(io.BytesIO(raw))
            conversations = df.to_dict(orient="records")

        else:
            raise HTTPException(
                status_code=400,
                detail="File must be .json or .csv"
            )

        if not isinstance(conversations, list):
            raise HTTPException(
                status_code=400,
                detail="Input file must contain a list of conversations."
            )

        results: List[dict] = []

        for i, convo in enumerate(conversations):

            conversation_id = str(
                convo.get(
                    "conversation_id",
                    f"unknown_{i}"
                )
            )

            text = str(
                convo.get(
                    "text",
                    ""
                )
            )

            if not text.strip():
                continue

            result = build_analysis_result(
                conversation_id,
                text
            )

            insert_conversation({
                **result,
                "text": text
            })

            results.append(result)

        return results

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Batch analysis failed: {str(e)}"
        )


# ---------- Dashboard ----------

@app.get("/dashboard-data")
def dashboard_data():
    try:
        return get_dashboard_stats()

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch dashboard data: {str(e)}"
        )


# ---------- Run Directly ----------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )