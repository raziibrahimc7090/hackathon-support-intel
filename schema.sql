-- schema.sql
-- Single table storing every analyzed conversation (customer intelligence + security results merged)
-- Run manually once via psql, or auto-created by SQLAlchemy in database.py

CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(255) NOT NULL UNIQUE,
    text TEXT NOT NULL,

    -- Customer Intelligence fields (Member B)
    category VARCHAR(50) NOT NULL,
    sentiment VARCHAR(20) NOT NULL,
    emotion VARCHAR(20) NOT NULL,
    priority VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    summary TEXT NOT NULL,

    -- Security Intelligence fields (Member C) — stored flattened for simple querying
    threat_detected BOOLEAN NOT NULL DEFAULT FALSE,
    threat_type VARCHAR(30) NOT NULL DEFAULT 'None',
    risk_level VARCHAR(20) NOT NULL DEFAULT 'Low',

    -- JSON columns for list-type security fields (urls, emails, flags)
    urls_found JSONB NOT NULL DEFAULT '[]',
    suspicious_urls JSONB NOT NULL DEFAULT '[]',
    emails_found JSONB NOT NULL DEFAULT '[]',
    suspicious_emails JSONB NOT NULL DEFAULT '[]',
    social_engineering_flags JSONB NOT NULL DEFAULT '[]',

    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Index for dashboard queries filtering by threat/priority
CREATE INDEX IF NOT EXISTS idx_conversations_threat_detected ON conversations(threat_detected);
CREATE INDEX IF NOT EXISTS idx_conversations_priority ON conversations(priority);
CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations(status);