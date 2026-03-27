import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from contextlib import asynccontextmanager

from agent import LLMSchedulerAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache agent instance
agent_instance = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent_instance
    logger.info("Initializing LLMSchedulerAgent...")
    agent_instance = LLMSchedulerAgent(suggest_only=True)
    yield
    logger.info("Shutting down API...")

app = FastAPI(title="LLM Scheduler Agent API", lifespan=lifespan)

class JournalEntry(BaseModel):
    id: str
    entry_number: int
    created_at: str
    period: str
    content: str
    timestamp: str

class ProcessJournalsRequest(BaseModel):
    journals: List[JournalEntry]
    user_id: Optional[str] = "default"

class ApplyCalendarRequest(BaseModel):
    changes: List[Dict[str, Any]]
    user_comments: Optional[str] = ""

@app.post("/api/process_journals")
async def process_journals(request: ProcessJournalsRequest):
    """
    Process a list of journal entries sent directly from the Android client.
    Delegates to agent.run_from_journals() — no pipeline logic lives here.
    """
    if not agent_instance:
        raise HTTPException(status_code=500, detail="Agent not initialized")

    journals = [j.dict() for j in request.journals]
    return agent_instance.run_from_journals(journals, user_id=request.user_id)

@app.post("/api/apply_calendar")
async def apply_calendar(request: ApplyCalendarRequest):
    """
    Applies confirmed changes to the user's calendar.
    """
    if not agent_instance:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    results = agent_instance.apply_calendar_changes(request.changes, request.user_comments)
    return results

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
