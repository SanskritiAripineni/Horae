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

    @staticmethod
    def _text(value: Any) -> str:
        if isinstance(value, timedelta):
            return str(value)
        if value is None:
            return ""
        return str(value)

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
            content = r.get('content') or ''
            research_text += f"{i}. [{r.get('category', 'General')}] {content[:500]}...\n"
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
4. Keep recommendations realistic and actionable'''

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
            date_key = self._text(e.get('start'))[:10]
            if date_key in events_by_date:
                events_by_date[date_key].append(e)

        day_schedule_text = ""
        for d in dates:
            dt = datetime.strptime(d, '%Y-%m-%d')
            day_name = f"{dt.strftime('%A')}, {dt.strftime('%b')} {dt.day}"
            day_events = events_by_date[d]
            if day_events:
                busy_slots = "  |  ".join(
                    f"{self._text(e.get('start'))[11:16]}–{self._text(e.get('end'))[11:16]} [{self._text(e.get('title'))}]"
                    for e in sorted(day_events, key=lambda x: self._text(x.get('start')))
                )
                day_schedule_text += f"  {d} ({day_name}): {busy_slots}\n"
            else:
                day_schedule_text += f"  {d} ({day_name}): (no events — fully free)\n"

        # Format tasks
        tasks_text = ""
        if (calendar_summary or {}).get('tasks'):
            for t in calendar_summary['tasks'][:10]:
                task_due = self._text(t.get('due'))
                due = f" (due: {task_due})" if task_due != 'No due date' else ""
                tasks_text += f"- {self._text(t.get('title'))}{due}\n"
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
        wellbeing_history: Optional[Dict[str, Any]] = None,
        behavioral_state: Optional[Dict[str, Any]] = None,
        raw_days: Optional[List[Dict[str, Any]]] = None,
        llm_analysis: Optional[Dict[str, Any]] = None,
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
        for e in ((calendar_summary or {}).get('events') or []):
            date_key = self._text(e.get('start'))[:10]
            if date_key in events_by_date:
                events_by_date[date_key].append(e)

        day_schedule_text = ""
        for d in dates:
            dt = datetime.strptime(d, '%Y-%m-%d')
            day_name = f"{dt.strftime('%A')}, {dt.strftime('%b')} {dt.day}"
            day_events = events_by_date[d]
            if day_events:
                busy_slots = "  |  ".join(
                    f"{self._text(e.get('start'))[11:16]}–{self._text(e.get('end'))[11:16]} [{self._text(e.get('title'))}]"
                    for e in sorted(day_events, key=lambda x: self._text(x.get('start')))
                )
                day_schedule_text += f"  {d} ({day_name}): {busy_slots}\n"
            else:
                day_schedule_text += f"  {d} ({day_name}): (no events)\n"

        tasks_text = ""
        if (calendar_summary or {}).get('tasks'):
            for t in calendar_summary['tasks'][:10]:
                task_due = self._text(t.get('due'))
                due = f" (due: {task_due})" if task_due != 'No due date' else ""
                tasks_text += f"- {self._text(t.get('title'))}{due}\n"
        else:
            tasks_text = "No pending tasks.\n"

        research_text = ""
        for i, r in enumerate(research_context[:6], 1):
            content = r.get('content') or ''
            research_text += f"{i}. [{r.get('category', 'General')}] {content[:400]}\n"
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
                history_text = (
                    "\nPAST SUGGESTION HISTORY (most recent last — do NOT re-propose rejected items; "
                    "build on accepted categories with complementary follow-ups):\n"
                    + "\n".join(lines)
                )

        layer4_section = ""
        if llm_analysis and isinstance(llm_analysis, dict):
            sal = llm_analysis.get("salience_reasoning", "")
            l4_patterns = llm_analysis.get("coherent_patterns") or []
            l4_questions = llm_analysis.get("questions_for_user") or []
            parts = []
            if l4_patterns:
                pnames = "; ".join(
                    f"{p.get('name', '?')} ({p.get('interpretation', '')[:80]})"
                    for p in l4_patterns
                )
                parts.append(f"  Detected patterns: {pnames}")
            if sal:
                parts.append(f"  Salience reasoning: {sal}")
            if l4_questions:
                parts.append(f"  Open questions: {'; '.join(l4_questions[:3])}")
            if parts:
                layer4_section = (
                    "\nBEHAVIORAL PATTERN ANALYSIS (pre-computed by reasoning layer — "
                    "use to calibrate risk and suggestion priority):\n"
                    + "\n".join(parts)
                    + "\n"
                )

        behavioral_text = self._text(behavioral_prose)
        journal_text = self._text(journal_narrative)
        has_sensor_data = bool(behavioral_text)

        # Build raw sensor values section (absolute numbers, not z-scores)
        raw_values_section = ""
        if raw_days:
            lines = []
            for day in raw_days[-7:]:  # last 7 days
                d = day.get("date", "?")
                onset = day.get("sleep_onset_hour")
                dur = day.get("sleep_duration_hours")
                sri = day.get("sleep_regularity_index")
                screen_late = day.get("late_night_screen_min")
                screen_total = day.get("total_screen_min")
                app_sw = day.get("app_switching_rate")
                mob = day.get("mobility_entropy")
                revisit = day.get("location_revisit_ratio")
                social = day.get("social_rhythm_metric")
                comm = day.get("comm_reciprocity")

                onset_str = f"{onset:.1f}h ({int(onset)}:{int((onset%1)*60):02d})" if onset is not None else "—"
                dur_str = f"{dur:.1f}h" if dur is not None else "—"
                sri_str = f"{sri:.0f}/100" if sri is not None else "—"
                screen_late_str = f"{screen_late:.0f}min" if screen_late is not None else "—"
                screen_total_str = f"{screen_total:.0f}min" if screen_total is not None else "—"
                app_sw_str = f"{app_sw:.2f}/active-min" if app_sw is not None else "—"
                mob_str = f"{mob:.2f}" if mob is not None else "—"
                revisit_str = f"{revisit:.2f}" if revisit is not None else "—"
                social_str = f"{social:.2f}" if social is not None else "—"
                comm_str = f"{comm:.2f}" if comm is not None else "—"

                lines.append(
                    f"  {d}: sleep_onset={onset_str}, sleep_duration={dur_str}, "
                    f"sleep_regularity={sri_str}, late_night_screen={screen_late_str}, "
                    f"total_screen={screen_total_str}, app_switching={app_sw_str}, "
                    f"mobility_entropy={mob_str}, location_revisit={revisit_str}, "
                    f"social_rhythm={social_str}, comm_reciprocity={comm_str}"
                )
            raw_values_section = (
                "RAW SENSOR VALUES (absolute daily measurements — personal-baseline deviations take precedence, "
                "but flag absolute-standard violations as a secondary check when baseline is unavailable):\n"
                + "\n".join(lines)
            )

        # Build structured deviations section from Layer 2/3 output
        deviations_section = ""
        if behavioral_state and isinstance(behavioral_state, dict):
            devs = behavioral_state.get("deviations", [])
            patterns = behavioral_state.get("coherent_patterns", [])
            baseline_info = behavioral_state.get("baseline_state", {})
            coverage_notes = behavioral_state.get("coverage_notes", [])

            dev_lines = []
            for dv in devs:
                marker = dv.get("marker", "?")
                direction = dv.get("direction", "?")
                magnitude = dv.get("magnitude", "?")
                finding = dv.get("finding", "")
                recent_val = dv.get("recent_mean")
                baseline_mean = dv.get("baseline_mean")
                trajectory = dv.get("trajectory")
                coverage = dv.get("coverage")
                details = []
                if trajectory:
                    details.append(f"trajectory={trajectory}")
                if coverage:
                    details.append(f"coverage={coverage}")
                if recent_val is not None and baseline_mean is not None:
                    details.append(f"recent={recent_val:.2f}, baseline_mean={baseline_mean:.2f}")
                dev_lines.append(
                    f"  • {marker}: {direction} ({magnitude}) — {finding or 'No finding text provided.'}"
                    + (f" | {'; '.join(details)}" if details else "")
                )

            pattern_lines = []
            for pattern in patterns:
                interpretation = pattern.get("interpretation", "")
                implicated = pattern.get("implicated", [])
                pattern_lines.append(
                    f"  • {interpretation or pattern.get('name', 'Unnamed pattern')}"
                    + (f" [signals: {', '.join(implicated)}]" if implicated else "")
                )

            days_history = baseline_info.get("days_of_history", 0)
            confidence = baseline_info.get("overall_confidence", "unknown")
            deviations_section = (
                f"BEHAVIORAL DEVIATIONS (z-score analysis vs {days_history}-day personal baseline, confidence={confidence}):\n"
                + ("\n".join(dev_lines) if dev_lines else "  No significant deviations detected vs personal baseline.")
                + ("\n\nCoherent patterns:\n" + "\n".join(pattern_lines) if pattern_lines else "")
                + ("\n\nCoverage notes: " + "; ".join(coverage_notes) if coverage_notes else "")
            )

        sensing_section = ""
        if has_sensor_data:
            sensing_section = f"BEHAVIORAL SENSING PROSE (Layer 3 narrative summary):\n{behavioral_text[:2000]}"
            if raw_values_section:
                sensing_section = raw_values_section + "\n\n" + sensing_section
            if deviations_section:
                sensing_section = sensing_section + "\n\n" + deviations_section
        else:
            sensing_section = (
                "BEHAVIORAL SENSING: No sensor data available for this period. "
                "Do NOT infer or assume any behavioral patterns. "
                "Set confidence_label to 'Low confidence — no sensor data'. "
                "Only report positives/protective_signals explicitly mentioned in the journal narrative."
            )
            if raw_values_section:
                sensing_section = raw_values_section + "\n\n" + sensing_section

        history_section = ""
        if wellbeing_history and wellbeing_history.get("history"):
            _trend_labels = {
                "rising": "worsening over time",
                "falling": "improving over time",
                "stable": "stable over time",
                "insufficient_data": "not enough data yet to determine trend",
            }
            trend_dir = wellbeing_history.get("trend", "insufficient_data")
            trend_label = _trend_labels.get(trend_dir, trend_dir)
            recent = " → ".join(
                f"{e['timestamp']} ({e['risk_level']})"
                for e in wellbeing_history["history"][-5:]
            )
            history_section = (
                f"\nWELLBEING HISTORY (stored across past sessions):\n"
                f"  Trend: {trend_label}\n"
                f"  Recent assessments: {recent}\n"
            )

        prompt = f"""You are a wellness scheduling agent. Use ALL context below to produce a structured schedule proposal.

TODAY: {now.strftime('%A, %Y-%m-%d %H:%M')} (timezone: America/Chicago)

JOURNAL NARRATIVE (contextual record of the user's recent activities — not a wellbeing assessment):
{journal_text[:3000]}

{sensing_section}
{history_section}{layer4_section}
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
    "ui_summary": {{
        "headline": "Short UI headline, e.g. Mild stress",
        "confidence_label": "Short confidence label, e.g. Medium confidence",
        "summary": "One concise sentence for the mobile hero card",
        "evidence_chips": [
            {{
                "label": "Short evidence label",
                "kind": "concern/protective/productive/neutral",
                "icon": "moon/warning/heart/calendar/activity/book"
            }}
        ],
        "concerns": [
            {{
                "label": "Short concern label",
                "detail": "Optional brief explanation",
                "severity": "low/medium/high"
            }}
        ],
        "protective_signals": [
            {{
                "label": "Short protective signal",
                "detail": "Optional brief explanation",
                "severity": "positive"
            }}
        ],
        "productive_signals": [
            {{
                "label": "Short productive signal",
                "detail": "Optional brief explanation",
                "severity": "positive"
            }}
        ]
    }},
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
9. If no sensor data is available, still produce recommendations and proposals from journal + research context alone
10. ui_summary must be UI-friendly and compact; keep dense evidence in summary/recommendations/proposed_changes, not in the labels
11. positives and protective_signals MUST be grounded in sensor data (coverage ≥ 0.5) or an explicit journal mention — do NOT infer or assume positive signals not evidenced in the data
12. When judging sleep health from RAW SENSOR VALUES, use absolute standards as a secondary check (sleep_onset >2:00 AM = late, sleep_duration <6h = short), but personal-baseline deviations take precedence — flag absolute-standard violations only when deviation from baseline is also present or baseline is unknown
13. confidence_label tiers — pick the most conservative that applies:
    "High confidence" → baseline warm + ≥8 of 10 markers present
    "Medium confidence" → baseline warm but some markers missing, OR <28 days of history
    "Low confidence — learning baseline" → baseline_warm=false (still in warmup window)
    "Low confidence — no sensor data" → no sensor data at all
14. proposed_changes must use "action": "add" only — "modify", "delete", and other actions are not supported and will be silently dropped """

        response = self.generate(prompt, max_tokens=8192)
        data = self._parse_json_response(response, None)
        if isinstance(data, dict):
            return data

        logger.error("generate_schedule_proposals: failed to parse orchestrator response")
        return {
            "risk_level": risk_level,
            "summary": behavioral_text[:200] if behavioral_text else "Assessment unavailable.",
            "concerns": [],
            "positives": [],
            "ui_summary": {},
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
