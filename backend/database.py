# backend/database.py
# SQLAlchemy engine, session, ORM model, and DB helper functions
# for the `conversations` table. Owned by Member A.

import os
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Boolean, DateTime, JSON, func
)
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set. Check your .env file.")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(255), unique=True, nullable=False, index=True)
    text = Column(Text, nullable=False)

    # Customer Intelligence fields
    category = Column(String(50), nullable=False)
    sentiment = Column(String(20), nullable=False)
    emotion = Column(String(20), nullable=False)
    priority = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False)
    summary = Column(Text, nullable=False)

    # Security Intelligence fields (flattened)
    threat_detected = Column(Boolean, nullable=False, default=False)
    threat_type = Column(String(30), nullable=False, default="None")
    risk_level = Column(String(20), nullable=False, default="Low")

    urls_found = Column(JSON, nullable=False, default=list)
    suspicious_urls = Column(JSON, nullable=False, default=list)
    emails_found = Column(JSON, nullable=False, default=list)
    suspicious_emails = Column(JSON, nullable=False, default=list)
    social_engineering_flags = Column(JSON, nullable=False, default=list)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


def init_db():
    """Create tables if they don't exist. Call once on app startup."""
    Base.metadata.create_all(bind=engine)


def get_session():
    """Yield a DB session — use as a FastAPI dependency or context manager."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def insert_conversation(analysis_result: dict) -> dict:
    """
    Takes a full API-contract-shaped result (with nested "security" dict)
    and flattens + inserts it into the conversations table.
    Uses upsert-like behavior: if conversation_id exists, updates it instead.

    Returns {"success": bool, "error": Optional[str]}
    """
    session = SessionLocal()
    try:
        security = analysis_result.get("security", {})

        existing = session.query(Conversation).filter_by(
            conversation_id=analysis_result["conversation_id"]
        ).first()

        if existing:
            row = existing
        else:
            row = Conversation(conversation_id=analysis_result["conversation_id"])
            session.add(row)

        row.text = analysis_result.get("text", "")
        row.category = analysis_result["category"]
        row.sentiment = analysis_result["sentiment"]
        row.emotion = analysis_result["emotion"]
        row.priority = analysis_result["priority"]
        row.status = analysis_result["status"]
        row.summary = analysis_result["summary"]

        row.threat_detected = bool(security.get("threat_detected", False))
        row.threat_type = security.get("threat_type", "None")
        row.risk_level = security.get("risk_level", "Low")
        row.urls_found = security.get("urls_found", [])
        row.suspicious_urls = security.get("suspicious_urls", [])
        row.emails_found = security.get("emails_found", [])
        row.suspicious_emails = security.get("suspicious_emails", [])
        row.social_engineering_flags = security.get("social_engineering_flags", [])

        session.commit()
        return {"success": True, "error": None}

    except SQLAlchemyError as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def get_dashboard_stats() -> dict:
    """
    Returns aggregated stats matching the GET /dashboard-data contract:
    {
      "total_conversations": int,
      "sentiment_distribution": {"Positive": int, "Neutral": int, "Negative": int},
      "category_distribution": {category: count},
      "top_issues": [{"issue": str, "count": int}],
      "critical_count": int, "unresolved_count": int, "threats_detected": int
    }
    """
    session = SessionLocal()
    try:
        total = session.query(Conversation).count()

        sentiment_rows = (
            session.query(Conversation.sentiment, func.count(Conversation.id))
            .group_by(Conversation.sentiment)
            .all()
        )
        sentiment_distribution = {"Positive": 0, "Neutral": 0, "Negative": 0}
        for sentiment, count in sentiment_rows:
            if sentiment in sentiment_distribution:
                sentiment_distribution[sentiment] = count

        category_rows = (
            session.query(Conversation.category, func.count(Conversation.id))
            .group_by(Conversation.category)
            .all()
        )
        category_distribution = {category: count for category, count in category_rows}

        # top_issues: reuse category distribution as a stand-in for "frequently reported issues"
        # (Member D's batch_processor may enrich this further with keyword frequency)
        top_issues = [
            {"issue": category, "count": count}
            for category, count in sorted(category_rows, key=lambda x: x[1], reverse=True)[:5]
        ]

        critical_count = session.query(Conversation).filter(
            Conversation.priority == "Critical"
        ).count()

        unresolved_count = session.query(Conversation).filter(
            Conversation.status == "Unresolved"
        ).count()

        threats_detected = session.query(Conversation).filter(
            Conversation.threat_detected == True  # noqa: E712
        ).count()

        recent_rows = (
            session.query(Conversation)
            .order_by(Conversation.id.desc())
            .limit(50)
            .all()
        )

        recent_conversations = [
            {
                "conversation_id": row.conversation_id,
                "text": row.text,
                "category": row.category,
                "sentiment": row.sentiment,
                "emotion": row.emotion,
                "priority": row.priority,
                "status": row.status,
                "summary": row.summary,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "security": {
                    "threat_detected": row.threat_detected,
                    "threat_type": row.threat_type,
                    "risk_level": row.risk_level,
                    "urls_found": row.urls_found or [],
                    "suspicious_urls": row.suspicious_urls or [],
                    "emails_found": row.emails_found or [],
                    "suspicious_emails": row.suspicious_emails or [],
                    "social_engineering_flags": row.social_engineering_flags or [],
                },
            }
            for row in recent_rows
        ]

        return {
            "total_conversations": total,
            "sentiment_distribution": sentiment_distribution,
            "category_distribution": category_distribution,
            "top_issues": top_issues,
            "critical_count": critical_count,
            "unresolved_count": unresolved_count,
            "threats_detected": threats_detected,
            "recent_conversations": recent_conversations,
        }
    finally:
        session.close()


if __name__ == "__main__":
    # Quick manual test: run `python database.py` from backend/ to verify connection
    print("Connecting to:", DATABASE_URL.split("@")[-1])
    init_db()
    print("Tables created (or already exist). Connection OK.")
    print("Dashboard stats:", get_dashboard_stats())