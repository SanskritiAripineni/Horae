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
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
import traceback
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

import db
from agent import LLMSchedulerAgent
from tools.calendar_api import (
    calendar_token_path_for_user,
    legacy_calendar_token_path_for_user,
)

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


def _sanitize_user_id(user_id: str | None) -> str | None:
    if user_id is None:
        return None
    return re.sub(r"[^a-zA-Z0-9_-]", "_", user_id[:64])


# Short-TTL cache for OAuth state tokens: {token: (user_id, code_verifier, expires_at)}
_oauth_state: dict[str, tuple[str, str, float]] = {}
_OAUTH_STATE_TTL = 300  # seconds


def _new_oauth_state(user_id: str) -> tuple[str, str]:
    """Returns (state_token, code_verifier)."""
    import base64
    import hashlib

    token = secrets.token_hex(24)
    code_verifier = secrets.token_urlsafe(48)
    now = time.monotonic()
    _oauth_state[token] = (user_id, code_verifier, now + _OAUTH_STATE_TTL)
    expired = [k for k, v in _oauth_state.items() if v[2] < now]
    for k in expired:
        del _oauth_state[k]
    return token, code_verifier


def _consume_oauth_state(token: str) -> tuple[str, str] | None:
    """Returns (user_id, code_verifier) or None if missing/expired."""
    entry = _oauth_state.pop(token, None)
    if entry is None:
        return None
    user_id, code_verifier, expires_at = entry
    if time.monotonic() > expires_at:
        return None
    return user_id, code_verifier


# ── Auth helpers (C1) ────────────────────────────────────────────────────────
def _get_api_secret() -> bytes | None:
    s = os.environ.get("API_SECRET_KEY", "")
    return s.encode() if s else None


def _make_user_token(user_id: str) -> str:
    secret = _get_api_secret()
    if not secret:
        return ""
    sig = hmac.new(secret, user_id.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{user_id}.{sig}"


async def _require_auth(authorization: str = Header(default="")) -> str | None:
    secret = _get_api_secret()
    if not secret:
        logger.error("API_SECRET_KEY is not configured; refusing protected request")
        raise HTTPException(
            status_code=503,
            detail="API_SECRET_KEY is not configured on the server",
        )
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Missing or malformed Authorization header"
        )
    token = authorization[7:]
    try:
        uid, sig = token.rsplit(".", 1)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token format")
    expected = hmac.new(secret, uid.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    return uid


def _require_token_user(auth_uid: str | None, user_id: str | None) -> str:
    requested_uid = _sanitize_user_id(user_id) or "default"
    if auth_uid != requested_uid:
        raise HTTPException(
            status_code=403, detail="Token user does not match requested user_id"
        )
    return requested_uid


# ── Proposal signing helpers (C2) ────────────────────────────────────────────
def _sign_change(change: dict) -> dict:
    secret = _get_api_secret()
    if not secret:
        return change
    payload = {k: v for k, v in change.items() if k != "change_token"}
    sig = hmac.new(
        secret,
        json.dumps(payload, sort_keys=True, default=str).encode(),
        hashlib.sha256,
    ).hexdigest()[:24]
    return {**payload, "change_token": sig}


def _verify_change(change: dict) -> bool:
    secret = _get_api_secret()
    if not secret:
        return True
    token = change.get("change_token")
    if not token:
        return False
    payload = {k: v for k, v in change.items() if k != "change_token"}
    expected = hmac.new(
        secret,
        json.dumps(payload, sort_keys=True, default=str).encode(),
        hashlib.sha256,
    ).hexdigest()[:24]
    return hmac.compare_digest(expected, token)


def _json_safe(value: Any) -> Any:
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    return value


app = FastAPI(title="LLM Scheduler Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Streamlit vectordb viewer only
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


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
        content={
            "error": "internal_error",
            "detail": "An unexpected error occurred. Please try again.",
        },
    )


class JournalEntry(BaseModel):
    id: str
    entry_number: int
    created_at: str
    period: str
    content: str = Field(..., max_length=10_000)
    timestamp: str


class RawDayMarkers(BaseModel):
    """One day of StudentLife-style sensor markers from the Android client."""

    date: str  # "YYYY-MM-DD"
    sleep_onset_hour: Optional[float] = None  # 24h clock; e.g. 23.5 = 11:30 PM
    sleep_duration_hours: Optional[float] = None
    sleep_regularity_index: Optional[float] = None  # 0–100
    late_night_screen_min: Optional[float] = None  # 23:00–04:00 usage
    total_screen_min: Optional[float] = None
    app_switching_rate: Optional[float] = None  # switches per active minute
    mobility_entropy: Optional[float] = None  # Shannon entropy of location clusters
    location_revisit_ratio: Optional[float] = None  # fraction of time at top-1 cluster
    social_rhythm_metric: Optional[float] = None  # 0–1 regularity score
    comm_reciprocity: Optional[float] = None  # outgoing / (outgoing + incoming)
    coverage: Optional[Dict[str, float]] = None  # per-marker data coverage 0–1


class ProcessJournalsRequest(BaseModel):
    journals: List[JournalEntry] = Field(..., max_length=100)
    raw_days: Optional[List[RawDayMarkers]] = Field(None, max_length=365)
    user_id: Optional[str] = "default"

    @field_validator("journals")
    @classmethod
    def journals_not_empty(cls, v):
        if not v:
            raise ValueError("journals list must not be empty")
        return v

    @field_validator("user_id")
    @classmethod
    def user_id_valid(cls, v):
        if v is not None and not v.strip():
            raise ValueError("user_id must not be blank")
        return _sanitize_user_id(v)


class ApplyCalendarRequest(BaseModel):
    changes: List[Dict[str, Any]]
    proposed_changes: Optional[List[Dict[str, Any]]] = None
    user_comments: Optional[str] = Field("", max_length=2_000)
    user_id: Optional[str] = "default"

    @field_validator("user_id")
    @classmethod
    def user_id_valid(cls, v):
        if v is not None and not v.strip():
            raise ValueError("user_id must not be blank")
        return _sanitize_user_id(v)


class EnrollRequest(BaseModel):
    user_id: str = "default"
    consented_at: int  # epoch millis from the device
    study_id: str = "RIDE_2026"
    version: str = "1.0"

    @field_validator("user_id")
    @classmethod
    def user_id_valid(cls, v):
        if v is not None and not v.strip():
            raise ValueError("user_id must not be blank")
        return _sanitize_user_id(v)


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
        logger.info(
            f"Enrolled participant user_id={req.user_id[:8]}... study={req.study_id}"
        )
        token = _make_user_token(req.user_id)
        return {"enrolled": True, "study_id": req.study_id, "auth_token": token or None}
    except Exception as e:
        logger.error(f"Enrollment error: {e}")
        # Don't fail hard — the client-side consent record is the source of truth
        return {"enrolled": False, "detail": str(e)}


@app.get("/api/oauth/authorize")
async def oauth_authorize(user_id: str = "default"):
    """Start Google Calendar OAuth flow for a user. Returns the authorization URL."""
    user_id = _sanitize_user_id(user_id) or "default"
    import json
    import os
    from pathlib import Path

    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError:
        raise HTTPException(
            status_code=500, detail="google_auth_oauthlib not installed"
        )

    credentials_path = Path("credentials.json")
    if not credentials_path.exists():
        raise HTTPException(
            status_code=500, detail="OAuth credentials not configured on server"
        )

    SCOPES = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/tasks",
    ]
    # Use a redirect_uri that comes back to this server
    redirect_uri = os.environ.get(
        "OAUTH_REDIRECT_URI", "http://localhost:8000/api/oauth/callback"
    )

    import base64
    import hashlib

    flow = Flow.from_client_secrets_file(
        str(credentials_path),
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )
    state_token, code_verifier = _new_oauth_state(user_id)
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state_token,
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )
    return {"auth_url": auth_url, "state": state_token}


@app.get("/api/oauth/callback")
async def oauth_callback(code: str, state: str = "default"):
    """Handle Google OAuth callback. Exchanges code for tokens and stores per-user."""
    import json
    import os
    from pathlib import Path

    credentials_path = Path("credentials.json")
    if not credentials_path.exists():
        raise HTTPException(
            status_code=500, detail="OAuth credentials not configured on server"
        )

    redirect_uri = os.environ.get(
        "OAUTH_REDIRECT_URI", "http://localhost:8000/api/oauth/callback"
    )

    try:
        # Recover user_id + code_verifier before fetching token (state is consumed here)
        result = _consume_oauth_state(state)
        if result is None:
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired OAuth state. Please restart the authorization flow.",
            )
        user_id, code_verifier = result

        # Exchange code for tokens directly — bypasses google_auth_oauthlib's
        # strict scope-equality check (Google often returns extra scopes).
        import httpx

        with open(credentials_path) as f:
            client_config = json.load(f).get("web", {})
        token_resp = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_config["client_id"],
                "client_secret": client_config["client_secret"],
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
            },
        )
        token_data = token_resp.json()
        if "error" in token_data:
            logger.error(f"Token exchange error: {token_data}")
            raise HTTPException(
                status_code=400,
                detail=f"Token exchange failed: {token_data.get('error_description', token_data['error'])}",
            )

        user_id = _sanitize_user_id(user_id) or "default"
        token_path = calendar_token_path_for_user(user_id)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        # Store in the format google.oauth2.credentials.Credentials.from_authorized_user_info expects
        scopes = token_data.get("scope", "")
        scope_list = (
            scopes.split()
            if isinstance(scopes, str) and scopes.strip()
            else (scopes or SCOPES)
        )
        token_file = {
            "token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": client_config["client_id"],
            "scopes": scope_list,
        }
        with open(token_path, "w") as f:
            json.dump(token_file, f)

        logger.info(f"OAuth token stored for user_id={user_id[:8]}...")
        from fastapi.responses import HTMLResponse

        return HTMLResponse(
            content="""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>AutoLife</title></head>
<body>
<script>try { window.location.href = 'autolife://oauth/success'; } catch(e) {}</script>
<p style="font-family:sans-serif;text-align:center;margin-top:60px;font-size:18px;">
  &#x2705; Google Calendar connected!<br><br>
  <span style="font-size:14px;color:#666;">You can close this tab and return to AutoLife.</span>
</p>
</body></html>"""
        )
    except Exception as e:
        logger.error(f"OAuth callback failed: {e}")
        raise HTTPException(
            status_code=400, detail="OAuth authorization failed. Please try again."
        )


@app.get("/api/oauth/status")
async def oauth_status(
    user_id: str = "default", _auth_uid: str | None = Depends(_require_auth)
):
    """Check if a user has a stored Google Calendar OAuth token."""
    user_id = _require_token_user(_auth_uid, user_id)
    token_path = calendar_token_path_for_user(user_id)
    legacy_token_path = legacy_calendar_token_path_for_user(user_id)
    return {"connected": token_path.exists() or legacy_token_path.exists()}


@app.delete("/api/oauth/token")
async def oauth_reset(
    user_id: str = "default", _auth_uid: str | None = Depends(_require_auth)
):
    """Delete stored OAuth token for a user, forcing re-authentication."""
    user_id = _require_token_user(_auth_uid, user_id)
    token_paths = [
        calendar_token_path_for_user(user_id),
        legacy_calendar_token_path_for_user(user_id),
    ]
    deleted = False
    for token_path in dict.fromkeys(token_paths):
        if token_path.exists():
            token_path.unlink()
            deleted = True
    if deleted:
        logger.info(f"OAuth token deleted for user_id={user_id[:8]}...")
        return {"message": "Token deleted. OAuth flow will restart on next authorize."}
    return {"message": "No token found for this user."}


@app.post("/api/process_journals")
async def process_journals(
    request: ProcessJournalsRequest, _auth_uid: str | None = Depends(_require_auth)
):
    """
    Process a list of journal entries sent directly from the Android client.
    Delegates to agent.run_from_journals() — no pipeline logic lives here.
    """
    if not agent_instance:
        raise HTTPException(
            status_code=503, detail="Agent not initialized — server is starting up"
        )

    _require_token_user(_auth_uid, request.user_id)

    # Validate that journal entries have non-empty content
    empty_content = [j.id for j in request.journals if not j.content.strip()]
    if empty_content:
        raise HTTPException(
            status_code=422,
            detail=f"Journal entries with empty content: {empty_content}",
        )

    journals = [j.model_dump() for j in request.journals]
    raw_days = [r.model_dump() for r in request.raw_days] if request.raw_days else None

    try:
        result = await asyncio.to_thread(
            agent_instance.run_from_journals, journals, request.user_id, raw_days
        )
        result = _json_safe(result)
    except Exception as e:
        logger.error(f"Pipeline error for user {db.anon_id(request.user_id)[:12]}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Journal processing failed. The pipeline encountered an error.",
        )

    try:
        db.log_session(request.user_id, journals, result)
    except Exception as e:
        logger.warning(f"DB log failed (non-fatal): {e}")
    # Sign proposed changes so apply_calendar can reject unsolicited/tampered ones (C2)
    if isinstance(result.get("proposed_changes"), list):
        result["proposed_changes"] = [
            _sign_change(c) for c in result["proposed_changes"]
        ]
    return result


@app.post("/api/apply_calendar")
async def apply_calendar(
    request: ApplyCalendarRequest, _auth_uid: str | None = Depends(_require_auth)
):
    """
    Applies confirmed changes to the user's calendar.
    """
    if not agent_instance:
        raise HTTPException(
            status_code=503, detail="Agent not initialized — server is starting up"
        )

    _require_token_user(_auth_uid, request.user_id)

    if not request.changes:
        raise HTTPException(status_code=422, detail="No calendar changes provided")

    # Reject changes that weren't signed by process_journals (C2)
    if _get_api_secret():
        invalid_idx = [
            i for i, c in enumerate(request.changes) if not _verify_change(c)
        ]
        if invalid_idx:
            raise HTTPException(
                status_code=403,
                detail=f"Unsigned or tampered calendar changes at positions {invalid_idx}. Re-fetch proposals from /api/process_journals.",
            )

    try:
        results = await asyncio.to_thread(
            agent_instance.apply_calendar_changes,
            request.changes,
            request.user_comments,
            request.proposed_changes,
            user_id=request.user_id or "default",
        )
    except Exception as e:
        logger.error(
            f"Calendar apply error for user {db.anon_id(request.user_id)[:12]}: {e}"
        )
        raise HTTPException(status_code=500, detail="Failed to apply calendar changes.")

    try:
        db.log_calendar_accepted(request.user_id, request.user_comments or "")
    except Exception as e:
        logger.warning(f"DB log failed (non-fatal): {e}")
    return results


@app.get("/api/memory")
async def get_memory(
    user_id: str = "default", _auth_uid: str | None = Depends(_require_auth)
):
    """
    Returns user preferences and mental health history from the memory module.
    Used by the Android Memory screen to display stored context.
    """
    if not agent_instance:
        raise HTTPException(
            status_code=503, detail="Agent not initialized — server is starting up"
        )

    user_id = _require_token_user(_auth_uid, user_id)

    try:
        ctx = agent_instance.memory.get_user_context(user_id)
        prefs = agent_instance.memory.preferences.get_preferences(user_id)
        history = agent_instance.memory.wellbeing_tracker.get_history(user_id)
        ctx["wellbeing"]["history"] = history
        ctx["total_items"] = (
            len(prefs.goals) + len(prefs.preferred_interventions) + len(history) + 1
        )
        ctx["updated_today"] = min(2, len(history))
        return ctx
    except Exception as e:
        logger.error(f"Memory retrieval error for user {db.anon_id(user_id)[:12]}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve user memory.")


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
