"""
LLM Client - Gemini API Wrapper (using google.genai)
Provides mental health analysis, recommendations, and calendar optimization.
"""

import logging
import os
import json
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

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
    
    def generate(self, prompt: str, max_tokens: int = 8192) -> str:
        """Generate text from a prompt."""
        if not self.client:
            return ""
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
            logger.error(f"Generation failed: {e}")
            return ""

    def analyze_mental_health(self, journal_text: str) -> Dict[str, Any]:
        """Analyze journal entries to estimate mental health state."""
        prompt = f'''Analyze these journal entries to assess the user's mental health state.

JOURNAL ENTRIES:
{journal_text[:4000]}

Respond in this exact JSON format (no markdown, just JSON):
{{
    "summary": "Brief 2-sentence summary of the user's recent activities and state",
    "phq4_estimate": <number 0-12 estimating PHQ-4 score based on anxiety/depression indicators>,
    "risk_level": "<minimal/mild/moderate/severe>",
    "concerns": ["list", "of", "key", "concerns"],
    "positives": ["list", "of", "positive", "indicators"]
}}

PHQ-4 scoring guide:
- 0-2: Minimal (healthy, normal functioning)
- 3-5: Mild (some stress indicators)
- 6-8: Moderate (intervention recommended)
- 9-12: Severe (immediate support needed)

Base your assessment on:
- Motion patterns (stationary vs. active)
- Location variety (same place vs. multiple locations)
- Time patterns (regular schedule vs. irregular)
- Any emotional indicators in the text'''

        response = self.generate(prompt)
        
        try:
            cleaned = re.sub(r'```json\s*|\s*```', '', response).strip()
            return json.loads(cleaned)
        except:
            return {
                "summary": "Unable to analyze journals",
                "phq4_estimate": 3,
                "risk_level": "mild",
                "concerns": [],
                "positives": []
            }

    def generate_recommendations(
        self,
        journal_summary: str,
        risk_level: str,
        concerns: List[str],
        research_context: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
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
        
        try:
            cleaned = re.sub(r'```json\s*|\s*```', '', response).strip()
            data = json.loads(cleaned)
            return data.get('recommendations', [])
        except:
            return [{
                "category": "General",
                "action": "Consider taking a short break for self-care",
                "when": "When feeling stressed",
                "source": "General wellness advice"
            }]

    def generate_calendar_changes(
        self,
        recommendations: List[Dict[str, Any]],
        calendar_summary: Dict[str, Any],
        mental_health: Dict[str, Any],
        user_preferences: List[str] = None
    ) -> List[Dict[str, Any]]:
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

        # Format events — include full start+end so model can see occupied slots
        events_text = ""
        if calendar_summary.get('events'):
            for e in calendar_summary['events'][:20]:
                events_text += f"- {e['start']} → {e['end']}: {e['title']} ({e['duration_hours']:.1f}h)\n"
        else:
            events_text = "No events scheduled.\n"

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

        prompt = f'''Based on the user's mental health, schedule, and tasks, suggest calendar optimizations.

TODAY: {now.strftime('%A, %Y-%m-%d %H:%M')} (timezone: America/Chicago)

MENTAL STATE:
- Risk Level: {mental_health.get('risk_level', 'unknown')}
- PHQ-4 Estimate: {mental_health.get('estimated_phq4', '?')}/12
- Concerns: {', '.join(mental_health.get('key_concerns', [])[:3])}

CURRENT CALENDAR (this week + next 7 days) — DO NOT schedule on top of these:
{events_text}
Total: {calendar_summary.get('total_hours', 0)} hours across {calendar_summary.get('event_count', 0)} events

PENDING TASKS:
{tasks_text}

WELLNESS RECOMMENDATIONS:
{recs_text}
{pref_text}
AVAILABLE DATES (schedule only within these): {', '.join(dates)}

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

Rules:
1. Suggest 3-5 calendar additions spread across different days
2. NEVER place a suggestion at the same time as an existing event — check each slot carefully
3. Schedule wellness breaks in gaps between existing events
4. Find optimal times for pending tasks based on workload
5. Set appropriate durations: wellness activities 15-30 min, study/work tasks 1-2 hours
6. Use realistic times - mornings (8-10am), afternoons (12-4pm), evenings (6-8pm)
7. No emojis in titles
8. STRICTLY respect user preferences - do NOT suggest activities the user dislikes
9. ALWAYS set end_time after start_time with correct duration
10. Only use dates from AVAILABLE DATES — never suggest events in the past'''

        response = self.generate(prompt)
        
        try:
            cleaned = re.sub(r'```json\s*|\s*```', '', response).strip()
            data = json.loads(cleaned)
            return data.get('proposed_changes', [])
        except Exception as e:
            logger.error(f"Failed to parse calendar changes: {e}")
            return []

    def parse_user_feedback(self, raw_feedback: str) -> Dict[str, Any]:
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
        
        try:
            cleaned = re.sub(r'```json\s*|\s*```', '', response).strip()
            return json.loads(cleaned)
        except:
            return {
                "preference": raw_feedback,
                "dislikes": [],
                "prefers": [],
                "should_save": True
            }
