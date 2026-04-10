Start the FastAPI backend server locally for development.

Run: `python api.py`

This starts uvicorn on http://localhost:8000 with auto-reload. Requires GEMINI_API_KEY in .env or environment. DATABASE_URL is optional (Postgres logging no-ops if unset).

Endpoints:
- POST /api/process_journals — main pipeline
- POST /api/apply_calendar — apply calendar changes
- GET /api/memory — user context
- GET /health — health check
