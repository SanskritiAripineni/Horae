"""
LLM Client - Gemini API Wrapper (using google.genai)
Provides behavioral assessment synthesis and calendar schedule proposals.
"""

import logging
import os
import json
import re
import time
from typing import Dict, Any, Optional, List, TypedDict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class Recommendation(TypedDict):
    """A single wellness recommendation produced by generate_recommendations()."""
    category: str
    action: str
    when: str
    source: str


class CalendarChange(TypedDict, total=False):
    """A proposed calendar change from generate_calendar_changes()."""
    action: str  # add / update / delete
    title: str
    description: str
    start_time: str
    end_time: str
    category: str
    reason: str
    event_id: str
    updates: Dict[str, Any]


class UserFeedback(TypedDict):
    """Structured output of parse_user_feedback()."""
    preference: str
    dislikes: List[str]
    prefers: List[str]
    should_save: bool

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds, doubles each attempt

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger.warning("google-genai not installed. Run: pip install google-genai")


class LLMClient:
    """Wrapper for Gemini API calls with mental health and calendar optimization prompts."""
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-3-flash-preview"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name
        self.client = None
        
        if not self.api_key:
            logger.warning("No Gemini API key provided. LLM features will be limited.")
        elif GENAI_AVAILABLE:
            try:
                self.client = genai.Client(api_key=self.api_key)
                logger.info(f"Initialized LLM client with model: {model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")
    
    def _is_retryable(self, error: Exception) -> bool:
        """Check if an error is transient and worth retrying."""
        error_str = str(error).lower()
        # Rate limit errors (HTTP 429)
        if "429" in error_str or "rate" in error_str or "quota" in error_str:
            return True
        # Server errors (5xx)
        if any(code in error_str for code in ["500", "502", "503", "504"]):
            return True
        # Network / connection errors
        if any(kw in error_str for kw in [
            "timeout", "connection", "network", "unavailable",
            "reset", "broken pipe", "eof",
        ]):
            return True
        # google-genai may raise specific API errors with retryable status
        error_type = type(error).__name__
        if "ServiceUnavailable" in error_type or "ResourceExhausted" in error_type:
            return True
        return False

    @staticmethod
    def _parse_json_response(response: str, default: Any) -> Any:
        """Strip optional ```json fences from a model response and parse JSON.

        Returns `default` on any parse error — callers supply the shape they
        need so the pipeline keeps moving on malformed output.
        """
        try:
            cleaned = re.sub(r'```json\s*|\s*```', '', response).strip()
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError, KeyError):
            return default

    def generate(self, prompt: str, max_tokens: int = 8192) -> str:
        """Generate text from a prompt with exponential-backoff retry."""
        if not self.client:
            return ""

        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        max_output_tokens=max_tokens
                    )
                )
                return response.text
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES and self._is_retryable(e):
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        f"Gemini API call failed (attempt {attempt + 1}/{MAX_RETRIES + 1}), "
                        f"retrying in {delay:.1f}s: {e}"
                    )
                    time.sleep(delay)
                else:
                    break

        logger.error(f"Generation failed after {MAX_RETRIES + 1} attempts: {last_error}")
        return ""

    def generate_recommendations(
        self,
        journal_summary: str,
        risk_level: str,
        concerns: List[str],
        research_context: List[Dict[str, Any]]
    ) -> List[Recommendation]:
        """Generate personalized recommendations based on analysis and research."""
        research_text = ""
        for i, r in enumerate(research_context[:6], 1):
            research_text += f"{i}. [{r.get('category', 'General')}] {r.get('content', '')[:500]}...\n"
            research_text += f"   Source: {r.get('source', 'Unknown')}\n\n"
        
        prompt = f'''Generate 3-4 personalized wellness recommendations.

USER CONTEXT:
- Summary: {journal_summary}
- Risk Level: {risk_level}
- Concerns: {', '.join(concerns) if concerns else 'None identified'}

RESEARCH EVIDENCE:
{research_text if research_text else 'No research context available.'}

Respond in this exact JSON format (no markdown, just JSON):
{{
    "recommendations": [
        {{
            "category": "<Sleep/Stress/Social/Physical/Mindfulness>",
            "action": "Specific actionable recommendation",
            "when": "When to do this (e.g., 'Before bed', 'During lunch break')",
            "source": "Research paper name if applicable"
        }}
    ]
}}

Rules:
1. Be specific and actionable
2. Match recommendations to the user's concerns
3. Base suggestions on the research evidence when available
4. Keep recommendations realistic for a college student'''

        response = self.generate(prompt)
        data = self._parse_json_response(response, None)
        if isinstance(data, dict) and 'recommendations' in data:
            return data.get('recommendations', [])
        return [{
            "category": "General",
            "action": "Consider taking a short break for self-care",
            "when": "When feeling stressed",
            "source": "General wellness advice"
        }]

    def generate_calendar_changes(
        self,
        recommendations: List[Recommendation],
        calendar_summary: Dict[str, Any],
        mental_health: Dict[str, Any],
        user_preferences: Optional[List[str]] = None
    ) -> List[CalendarChange]:
        """Generate proposed calendar changes based on recommendations, schedule, tasks, and user preferences."""
        now = datetime.now()
        tomorrow = now + timedelta(days=1)
        dates = [(tomorrow + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]

        # Format user preferences
        pref_text = ""
        if user_preferences:
            pref_text = "\nUSER PREFERENCES (MUST RESPECT):\n"
            for p in user_preferences:
                pref_text += f"- {p}\n"

        # Group existing events by date so the model can see per-day busy windows
        events_by_date: Dict[str, list] = {d: [] for d in dates}
        for e in (calendar_summary.get('events') or []):
            date_key = e['start'][:10]
            if date_key in events_by_date:
                events_by_date[date_key].append(e)

        day_schedule_text = ""
        for d in dates:
            dt = datetime.strptime(d, '%Y-%m-%d')
            day_name = f"{dt.strftime('%A')}, {dt.strftime('%b')} {dt.day}"
            day_events = events_by_date[d]
            if day_events:
                busy_slots = "  |  ".join(
                    f"{e['start'][11:16]}–{e['end'][11:16]} [{e['title']}]"
                    for e in sorted(day_events, key=lambda x: x['start'])
                )
                day_schedule_text += f"  {d} ({day_name}): {busy_slots}\n"
            else:
                day_schedule_text += f"  {d} ({day_name}): (no events — fully free)\n"

        # Format tasks
        tasks_text = ""
        if calendar_summary.get('tasks'):
            for t in calendar_summary['tasks'][:10]:
                due = f" (due: {t['due']})" if t['due'] != 'No due date' else ""
                tasks_text += f"- {t['title']}{due}\n"
        else:
            tasks_text = "No pending tasks.\n"

        recs_text = "\n".join([f"- [{r['category']}] {r['action']} ({r['when']})"
                               for r in recommendations[:4]])

        prompt = f'''Based on the user's mental health, schedule, and tasks, suggest wellness calendar events.

TODAY: {now.strftime('%A, %Y-%m-%d %H:%M')} (timezone: America/Chicago)

WELLBEING STATE:
- Risk Level: {mental_health.get('risk_level', 'unknown')}
- Concerns: {', '.join(mental_health.get('key_concerns', [])[:3])}

SCHEDULE FOR THE NEXT 7 DAYS (busy slots listed per day — DO NOT overlap these):
{day_schedule_text}
PENDING TASKS:
{tasks_text}
WELLNESS RECOMMENDATIONS:
{recs_text}
{pref_text}
Respond in JSON format (no markdown):
{{
    "proposed_changes": [
        {{
            "action": "add",
            "title": "Event title",
            "description": "Brief description",
            "start_time": "YYYY-MM-DDTHH:MM:SS",
            "end_time": "YYYY-MM-DDTHH:MM:SS",
            "category": "Sleep/Stress/Physical/Mindfulness/Social/Task",
            "reason": "Why this helps"
        }}
    ]
}}

STRICT RULES — follow every one exactly:
1. Spread proposals across the full 7-day window — aim for coverage on most days, not clustering on 2-3 days
2. For each proposal, look at that day's busy slots above and pick a time that does NOT overlap ANY of them
3. A conflict means your proposed start_time or end_time falls inside an existing [start–end] range — avoid this completely
4. Prefer morning gaps (7–9 AM), lunch gaps (12–1 PM), or evening gaps (7–9 PM) when a day is busy
5. On fully free days, pick a realistic time between 8 AM and 9 PM
6. Durations: wellness/mindfulness 15–30 min, physical activity 30–45 min, study/work tasks 60–90 min
7. No emojis in titles
8. STRICTLY respect user preferences — do NOT suggest activities the user dislikes
9. ALWAYS set end_time strictly after start_time
10. Base the number and type of proposals on the wellness recommendations and research context — quality over quantity'''

        response = self.generate(prompt)
        data = self._parse_json_response(response, None)
        if isinstance(data, dict):
            return data.get('proposed_changes', [])
        logger.error("Failed to parse calendar changes from model response")
        return []

    def generate_schedule_proposals(
        self,
        journal_narrative: str,
        behavioral_prose: Optional[str],
        risk_level: str,
        calendar_summary: Dict[str, Any],
        research_context: List[Dict[str, Any]],
        user_preferences: Optional[List[str]] = None,
        feedback_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Orchestrator call: compose journal narrative + behavioral sensing + calendar
        + research evidence into a complete schedule proposal.

        This is the single entry point for the orchestrating LLM. It receives all
        tool outputs as context and returns a unified JSON with risk assessment,
        recommendations, and proposed calendar changes.

        Returns dict with keys: risk_level, summary, concerns, positives,
        recommendations, proposed_changes.
        """
        now = datetime.now()
        tomorrow = now + timedelta(days=1)
        dates = [(tomorrow + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]

        # Per-day busy slots
        events_by_date: Dict[str, list] = {d: [] for d in dates}
        for e in (calendar_summary.get('events') or []):
            date_key = e['start'][:10]
            if date_key in events_by_date:
                events_by_date[date_key].append(e)

        day_schedule_text = ""
        for d in dates:
            dt = datetime.strptime(d, '%Y-%m-%d')
            day_name = f"{dt.strftime('%A')}, {dt.strftime('%b')} {dt.day}"
            day_events = events_by_date[d]
            if day_events:
                busy_slots = "  |  ".join(
                    f"{e['start'][11:16]}–{e['end'][11:16]} [{e['title']}]"
                    for e in sorted(day_events, key=lambda x: x['start'])
                )
                day_schedule_text += f"  {d} ({day_name}): {busy_slots}\n"
            else:
                day_schedule_text += f"  {d} ({day_name}): (no events)\n"

        tasks_text = ""
        if calendar_summary.get('tasks'):
            for t in calendar_summary['tasks'][:10]:
                due = f" (due: {t['due']})" if t['due'] != 'No due date' else ""
                tasks_text += f"- {t['title']}{due}\n"
        else:
            tasks_text = "No pending tasks.\n"

        research_text = ""
        for i, r in enumerate(research_context[:6], 1):
            research_text += f"{i}. [{r.get('category', 'General')}] {r.get('content', '')[:400]}\n"
            research_text += f"   Source: {r.get('source', 'Unknown')}\n\n"

        pref_text = ""
        if user_preferences:
            pref_text = "\nUSER PREFERENCES (MUST RESPECT):\n"
            for p in user_preferences:
                pref_text += f"- {p}\n"

        history_text = ""
        if feedback_history:
            lines = []
            for rec in (feedback_history or [])[-10:]:
                action = rec.get("action", "?")
                change = rec.get("suggestion_change", "")
                ts = rec.get("timestamp", "")[:10]
                lines.append(f"  [{ts}] {change!r} — {action}")
            if lines:
                history_text = "\nPAST SUGGESTION HISTORY (most recent last):\n" + "\n".join(lines)

        sensing_section = (
            f"BEHAVIORAL SENSING (objective phone sensor assessment from Layer 1-4 pipeline):\n{behavioral_prose[:3000]}"
            if behavioral_prose
            else "BEHAVIORAL SENSING: No sensor data available for this period."
        )

        prompt = f"""You are a wellness scheduling agent. Use ALL context below to produce a structured schedule proposal.

TODAY: {now.strftime('%A, %Y-%m-%d %H:%M')} (timezone: America/Chicago)

JOURNAL NARRATIVE (contextual record of the user's recent activities — not a wellbeing assessment):
{journal_narrative[:3000]}

{sensing_section}

PRELIMINARY RISK ESTIMATE (from behavioral sensing heuristic): {risk_level}
Risk guide: minimal=healthy normal functioning | mild=some stress indicators | moderate=intervention recommended | severe=immediate support needed

RESEARCH-BACKED INTERVENTIONS:
{research_text if research_text else "No research context available."}

CALENDAR — NEXT 7 DAYS (DO NOT overlap existing busy slots):
{day_schedule_text}
PENDING TASKS:
{tasks_text}{pref_text}{history_text}

Respond in this EXACT JSON format (no markdown, just JSON):
{{
    "risk_level": "<minimal/mild/moderate/severe>",
    "summary": "2-3 sentence overall assessment grounded in sensor data if available, otherwise journal narrative",
    "concerns": ["list of key wellbeing concerns identified"],
    "positives": ["list of positive behavioral indicators"],
    "recommendations": [
        {{
            "category": "<Sleep/Stress/Social/Physical/Mindfulness>",
            "action": "Specific actionable recommendation",
            "when": "When to do this",
            "source": "Research paper name if applicable, else General wellness"
        }}
    ],
    "proposed_changes": [
        {{
            "action": "add",
            "title": "Event title (no emojis)",
            "description": "Brief description",
            "start_time": "YYYY-MM-DDTHH:MM:SS",
            "end_time": "YYYY-MM-DDTHH:MM:SS",
            "category": "Sleep/Stress/Physical/Mindfulness/Social/Task",
            "reason": "Why this helps based on the sensing or journal context"
        }}
    ]
}}

STRICT RULES:
1. risk_level MUST be driven by sensor data when available; use journal narrative only as secondary context
2. Produce 3-4 recommendations grounded in the research interventions above
3. Produce 4-7 proposed_changes spread across the full 7-day window
4. For each proposed_change, check that day's busy slots — DO NOT overlap any existing [start–end] range
5. Prefer gaps: mornings (7–9 AM), lunch (12–1 PM), evenings (7–9 PM) on busy days; any 8 AM–9 PM slot on free days
6. Durations: mindfulness 15–30 min, physical 30–45 min, study/work 60–90 min
7. STRICTLY respect user preferences — never suggest activities the user dislikes
8. end_time must be strictly after start_time
9. If no sensor data is available, still produce recommendations and proposals from journal + research context alone"""

        response = self.generate(prompt, max_tokens=8192)
        data = self._parse_json_response(response, None)
        if isinstance(data, dict):
            return data

        logger.error("generate_schedule_proposals: failed to parse orchestrator response")
        return {
            "risk_level": risk_level,
            "summary": behavioral_prose[:200] if behavioral_prose else "Assessment unavailable.",
            "concerns": [],
            "positives": [],
            "recommendations": [{
                "category": "General",
                "action": "Consider taking a short break for self-care",
                "when": "When feeling stressed",
                "source": "General wellness advice",
            }],
            "proposed_changes": [],
        }

    def parse_user_feedback(self, raw_feedback: str) -> UserFeedback:
        """Parse raw user feedback into structured preferences."""
        prompt = f'''Parse this user feedback into a structured preference statement.

USER FEEDBACK: "{raw_feedback}"

Respond in JSON format (no markdown):
{{
    "preference": "A clear, concise preference statement (e.g., 'User prefers workout over meditation')",
    "dislikes": ["list of things user dislikes"],
    "prefers": ["list of things user prefers instead"],
    "should_save": true/false (false if feedback is just 'ok', 'go ahead', etc.)
}}

Keep the preference statement professional and actionable for future recommendations.'''

        response = self.generate(prompt, max_tokens=500)
        return self._parse_json_response(response, {
            "preference": raw_feedback,
            "dislikes": [],
            "prefers": [],
            "should_save": True
        })
