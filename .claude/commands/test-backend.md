Run the Python backend smoke test. This starts a local uvicorn server, sends a sample journal payload to /api/process_journals, and asserts the response structure.

Steps:
1. Ensure GEMINI_API_KEY is set (check .env or environment)
2. Run `python test_api.py`
3. Report results — all assertions should pass
