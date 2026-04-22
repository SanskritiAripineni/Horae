"""
FastAPI server for the LLM Scheduler Agent.

RESEARCH-READINESS NOTES (audit 2026-04-10):
  - user_id is SHA-256 hashed in db.py before any database write.
  - The API response echoes the raw user_id back to the calling client only
    (returned over HTTPS to the same device that sent it; never stored
    server-side in plaintext — db.py always hashes first).
  - The /api/memory endpoint uses raw user_id as a file-system key under
    data/memory/. On the Railway persistent volume this means filenames
    contain the raw user_id. Acceptable for ~100 research users on a
    non-publicly-accessible volume, but for larger deployments the memory
    module should hash its keys.
  - No PII beyond user_id enters the database: journal content is Gemini-
    generated narrative (no raw coordinates); sensor logs stay on-device.
"""

import asyncio
import logging
import traceback
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, field_validator
import uvicorn
from contextlib import asynccontextmanager

from agent import LLMSchedulerAgent
import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

agent_instance = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent_instance
    logger.info("Initializing LLMSchedulerAgent...")
    agent_instance = LLMSchedulerAgent(suggest_only=True)
    db.init_schema()
    yield
    logger.info("Shutting down API...")

app = FastAPI(title="LLM Scheduler Agent API", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return a clear JSON body for malformed / invalid requests."""
    errors = []
    for err in exc.errors():
        field = " -> ".join(str(loc) for loc in err.get("loc", []))
        errors.append({"field": field, "message": err.get("msg", "")})
    return JSONResponse(
        status_code=422,
        content={"error": "validation_error", "detail": errors},
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "http_error", "detail": exc.detail},
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all so clients always get JSON, never raw 500 HTML."""
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    logger.debug(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": "An unexpected error occurred. Please try again."},
    )


class JournalEntry(BaseModel):
    id: str
    entry_number: int
    created_at: str
    period: str
    content: str
    timestamp: str


class RawDayMarkers(BaseModel):
    """One day of StudentLife-style sensor markers from the Android client."""
    date: str                                      # "YYYY-MM-DD"
    sleep_onset_hour: Optional[float] = None       # 24h clock; e.g. 23.5 = 11:30 PM
    sleep_duration_hours: Optional[float] = None
    sleep_regularity_index: Optional[float] = None # 0–100
    late_night_screen_min: Optional[float] = None  # 23:00–04:00 usage
    total_screen_min: Optional[float] = None
    app_switching_rate: Optional[float] = None     # switches per active minute
    mobility_entropy: Optional[float] = None       # Shannon entropy of location clusters
    location_revisit_ratio: Optional[float] = None # fraction of time at top-1 cluster
    social_rhythm_metric: Optional[float] = None   # 0–1 regularity score
    comm_reciprocity: Optional[float] = None       # outgoing / (outgoing + incoming)
    coverage: Optional[Dict[str, float]] = None    # per-marker data coverage 0–1


class ProcessJournalsRequest(BaseModel):
    journals: List[JournalEntry]
    raw_days: Optional[List[RawDayMarkers]] = None  # real sensor markers from device
    user_id: Optional[str] = "default"

    @field_validator("journals")
    @classmethod
    def journals_not_empty(cls, v):
        if not v:
            raise ValueError("journals list must not be empty")
        return v

    @field_validator("user_id")
    @classmethod
    def user_id_not_blank(cls, v):
        if v is not None and not v.strip():
            raise ValueError("user_id must not be blank")
        return v

class ApplyCalendarRequest(BaseModel):
    changes: List[Dict[str, Any]]
    user_comments: Optional[str] = ""
    user_id: Optional[str] = "default"


class EnrollRequest(BaseModel):
    user_id: str = "default"
    consented_at: int  # epoch millis from the device
    study_id: str = "RIDE_2026"
    version: str = "1.0"


@app.post("/api/enroll")
async def enroll_participant(req: EnrollRequest):
    """Record study enrollment / consent server-side for IRB audit trail."""
    try:
        db.log_enrollment(
            user_id=req.user_id,
            consented_at=req.consented_at,
            study_id=req.study_id,
            version=req.version,
        )
        logger.info(f"Enrolled participant user_id={req.user_id[:8]}... study={req.study_id}")
        return {"enrolled": True, "study_id": req.study_id}
    except Exception as e:
        logger.error(f"Enrollment error: {e}")
        # Don't fail hard — the client-side consent record is the source of truth
        return {"enrolled": False, "detail": str(e)}


@app.get("/api/oauth/authorize")
async def oauth_authorize(user_id: str = "default"):
    """Start Google Calendar OAuth flow for a user. Returns the authorization URL."""
    import json, os
    from pathlib import Path
    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError:
        raise HTTPException(status_code=500, detail="google_auth_oauthlib not installed")

    credentials_path = Path("credentials.json")
    if not credentials_path.exists():
        raise HTTPException(status_code=500, detail="OAuth credentials not configured on server")

    SCOPES = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/tasks",
    ]
    # Use a redirect_uri that comes back to this server
    redirect_uri = os.environ.get("OAUTH_REDIRECT_URI", "http://localhost:8000/api/oauth/callback")

    flow = Flow.from_client_secrets_file(
        str(credentials_path),
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=user_id,  # carry user_id through the flow as state
    )
    return {"auth_url": auth_url, "state": state}


@app.get("/api/oauth/callback")
async def oauth_callback(code: str, state: str = "default"):
    """Handle Google OAuth callback. Exchanges code for tokens and stores per-user."""
    import json, os
    from pathlib import Path
    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError:
        raise HTTPException(status_code=500, detail="google_auth_oauthlib not installed")

    credentials_path = Path("credentials.json")
    if not credentials_path.exists():
        raise HTTPException(status_code=500, detail="OAuth credentials not configured on server")

    SCOPES = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/tasks",
    ]
    redirect_uri = os.environ.get("OAUTH_REDIRECT_URI", "http://localhost:8000/api/oauth/callback")

    try:
        flow = Flow.from_client_secrets_file(
            str(credentials_path),
            scopes=SCOPES,
            redirect_uri=redirect_uri,
            state=state,
        )
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Store per-user token
        user_id = state  # state carries the user_id
        token_path = Path(f"data/tokens/{user_id}/calendar_token.json")
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "w") as f:
            json.dump(json.loads(credentials.to_json()), f)

        logger.info(f"OAuth token stored for user_id={user_id[:8]}...")
        return {
            "status": "connected",
            "user_id": user_id,
            "message": "Calendar connected successfully. You can close this window.",
        }
    except Exception as e:
        logger.error(f"OAuth callback failed: {e}")
        raise HTTPException(status_code=400, detail=f"OAuth failed: {e}")


@app.post("/api/process_journals")
async def process_journals(request: ProcessJournalsRequest):
    """
    Process a list of journal entries sent directly from the Android client.
    Delegates to agent.run_from_journals() — no pipeline logic lives here.
    """
    if not agent_instance:
        raise HTTPException(status_code=503, detail="Agent not initialized — server is starting up")

    # Validate that journal entries have non-empty content
    empty_content = [j.id for j in request.journals if not j.content.strip()]
    if empty_content:
        raise HTTPException(
            status_code=422,
            detail=f"Journal entries with empty content: {empty_content}"
        )

    journals = [j.model_dump() for j in request.journals]
    raw_days = [r.model_dump() for r in request.raw_days] if request.raw_days else None

    try:
        result = await asyncio.to_thread(
            agent_instance.run_from_journals, journals, request.user_id, raw_days
        )
    except Exception as e:
        logger.error(f"Pipeline error for user {db.anon_id(request.user_id)[:12]}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Journal processing failed. The pipeline encountered an error."
        )

    try:
        db.log_session(request.user_id, journals, result)
    except Exception as e:
        logger.warning(f"DB log failed (non-fatal): {e}")
    return result


@app.post("/api/apply_calendar")
async def apply_calendar(request: ApplyCalendarRequest):
    """
    Applies confirmed changes to the user's calendar.
    """
    if not agent_instance:
        raise HTTPException(status_code=503, detail="Agent not initialized — server is starting up")

    if not request.changes:
        raise HTTPException(status_code=422, detail="No calendar changes provided")

    try:
        results = await asyncio.to_thread(
            agent_instance.apply_calendar_changes, request.changes, request.user_comments
        )
    except Exception as e:
        logger.error(f"Calendar apply error for user {db.anon_id(request.user_id)[:12]}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to apply calendar changes."
        )

    try:
        db.log_calendar_accepted(request.user_id, request.user_comments or "")
    except Exception as e:
        logger.warning(f"DB log failed (non-fatal): {e}")
    return results

@app.get("/api/memory")
async def get_memory(user_id: str = "default"):
    """
    Returns user preferences and mental health history from the memory module.
    Used by the Android Memory screen to display stored context.
    """
    if not agent_instance:
        raise HTTPException(status_code=503, detail="Agent not initialized — server is starting up")

    try:
        ctx = agent_instance.memory.get_user_context(user_id)
        ctx["wellbeing"]["history"] = agent_instance.memory.wellbeing_tracker.get_history(user_id)
        return ctx
    except Exception as e:
        logger.error(f"Memory retrieval error for user {db.anon_id(user_id)[:12]}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve user memory."
        )

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
