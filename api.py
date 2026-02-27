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
    Process a list of journal entries directly instead of reading them from the file system.
    This replaces `agent.run()`, bypassing `autolife_reader.read_journals()`.
    """
    if not agent_instance:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    # We will need to slightly replicate agent.run() specifically for handling passed-in journals
    results = {
        'status': 'running',
        'user_id': request.user_id,
        'journal_summary': None,
        'mental_health': None,
        'recommendations': [],
        'calendar_summary': None,
        'proposed_changes': [],
        'errors': []
    }

    try:
        # Convert Pydantic models to dicts
        journals_dict = [j.dict() for j in request.journals]
        
        if not journals_dict:
            results['errors'].append("No journal entries provided")
            results['status'] = 'completed_with_warnings'
            return results

        journal_text = agent_instance.autolife_reader.get_context_for_prompt(journals_dict)
        results['journal_count'] = len(journals_dict)

        # Step 2: Analyze mental health
        analysis = agent_instance.llm_client.analyze_mental_health(journal_text)
        results['journal_summary'] = analysis.get('summary', '')
        results['mental_health'] = {
            'estimated_phq4': analysis.get('phq4_estimate', 3),
            'risk_level': analysis.get('risk_level', 'minimal'),
            'key_concerns': analysis.get('concerns', []),
            'positive_indicators': analysis.get('positives', [])
        }

        # Step 3: Get calendar info
        calendar_summary = agent_instance.calendar_api.get_schedule_summary(days=7)
        results['calendar_summary'] = calendar_summary

        # Step 4: VectorDB
        phq4 = results['mental_health']['estimated_phq4']
        if agent_instance.vectordb.initialize():
            research_suggestions = agent_instance.vectordb.get_intervention_suggestions(
                phq4_score=phq4,
                journal_summary=results['journal_summary']
            )
        else:
            research_suggestions = []
            results['errors'].append("VectorDB not available")

        # Step 5: Generate recommendations
        recommendations = agent_instance.llm_client.generate_recommendations(
            journal_summary=results['journal_summary'],
            risk_level=results['mental_health']['risk_level'],
            concerns=results['mental_health']['key_concerns'],
            research_context=research_suggestions
        )
        results['recommendations'] = recommendations

        # Step 6: Generate calendar proposals
        proposed_changes = agent_instance.llm_client.generate_calendar_changes(
            recommendations=recommendations,
            calendar_summary=calendar_summary,
            mental_health=results['mental_health']
        )
        results['proposed_changes'] = proposed_changes

        results['status'] = 'completed'

    except Exception as e:
        logger.error(f"API Error processing journals: {e}")
        results['errors'].append(str(e))
        results['status'] = 'failed'

    return results

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
