# TESTING.md — Integration Test Checklist

Run through this checklist before merging to `dev` and again before the final `dev` → `main` merge.

## 1. Server Start
- [ ] `venv` activated
- [ ] `cd backend && uvicorn main:app --reload` starts with no errors
- [ ] `http://localhost:8000/docs` loads (interactive API docs)

## 2. Database Connection
- [ ] `python database.py` connects and prints dashboard stats with no errors
- [ ] `conversations` table exists (`\dt` in `psql`, or visible in pgAdmin)

## 3. Single Analyze (`POST /analyze`)
- [ ] Normal message returns valid `category`/`sentiment`/`emotion`/`priority`/`status`/`summary`
- [ ] Phishing message returns `security.threat_detected: true`, correct `threat_type`, `risk_level`
- [ ] All returned values match STRICT VALUES casing exactly (spot-check against the contract)
- [ ] Row appears in `conversations` table after each call

## 4. Batch Analyze (`POST /analyze-batch`)
- [ ] Uploading `data/conversations.json` returns an array of contract-shaped results
- [ ] Result count matches input count (minus any explicitly skipped empty-text entries)
- [ ] Mix of `threat_detected: true/false` present, roughly matching the ~30% phishing generation ratio
- [ ] All rows persisted to PostgreSQL (`SELECT COUNT(*) FROM conversations;`)

## 5. Dashboard Data (`GET /dashboard-data`)
- [ ] `total_conversations` matches DB row count
- [ ] `sentiment_distribution` keys are exactly `Positive`/`Neutral`/`Negative`, sums to total
- [ ] `category_distribution` keys are exactly the 7 STRICT VALUES categories
- [ ] `critical_count`, `unresolved_count`, `threats_detected` are non-negative integers and look plausible

## 6. Frontend Load
- [ ] `frontend/index.html` opens and loads without console errors
- [ ] KPI cards populate from `/dashboard-data`
- [ ] Charts render (sentiment + category)
- [ ] Security Alerts panel shows flagged conversations
- [ ] Conversation table populates with color-coded priority/risk badges
- [ ] Live "Analyze" input box successfully calls `/analyze` and displays the result

## 7. Contract Compliance (run before every PR merge into `dev`)
- [ ] No lowercase/misspelled values anywhere in a response (e.g. `phishing` instead of `Phishing`)
- [ ] All list fields (`urls_found`, `suspicious_urls`, etc.) are `[]` when empty, never `null`
- [ ] All booleans are `true`/`false` (JSON), never `"true"`/`"false"` strings
- [ ] Field names match exactly — no `conversationId`, `threatDetected`, etc. camelCase drift

## 8. Run the automated pipeline test
```cmd
cd backend
python test_pipeline.py
```
- [ ] `/health` returns 200
- [ ] All sample conversations (including the 2 phishing examples) return sensible results
- [ ] Batch upload succeeds and prints sentiment/risk distributions
- [ ] `/dashboard-data` reflects the newly inserted data

