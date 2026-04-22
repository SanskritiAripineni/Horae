"""
LLM Scheduler Agent - The "Conductor"
Orchestrates journal analysis, wellbeing assessment, and calendar optimization.
"""

import logging
import threading
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

# Import config FIRST to load .env
from config import config

from tools.autolife_reader import AutoLifeReader
from tools.vectordb_client import VectorDBClient
from tools.calendar_api import CalendarAPI, CalendarEvent
from tools.llm_client import LLMClient
from tools.wellbeing_sensor import WellbeingSensor
from tools.wellbeing_feedback import WellbeingFeedback
from memory import MemoryModule

logger = logging.getLogger(__name__)


def _infer_risk_from_prose(prose: str) -> str:
    """Heuristic risk label from Layer 3 behavioral prose for VectorDB query."""
    if not prose:
        return "minimal"
    lower = prose.lower()
    if any(w in lower for w in ["severe", "critical", "crisis", "significant deterioration"]):
        return "moderate"
    if any(w in lower for w in ["notable", "above average", "elevated", "concerning", "irregular", "deviation"]):
        return "mild"
    return "minimal"


class LLMSchedulerAgent:
    """
    Main agent that orchestrates the mental health analysis and calendar optimization.
    """
    
    def __init__(self, suggest_only: bool = True, user_id: str = "default"):
        self.suggest_only = suggest_only
        self.user_id = user_id

        self.autolife_reader = AutoLifeReader()
        self.vectordb = VectorDBClient()
        self.calendar_api = CalendarAPI(suggest_only=suggest_only, user_id=self.user_id)
        self.llm_client = LLMClient()
        self.wellbeing_sensor = WellbeingSensor()
        self.memory = MemoryModule()
        self._calendar_lock = threading.Lock()

        logger.info("LLMSchedulerAgent initialized")

    def run_from_journals(
        self,
        journals: List[Dict[str, Any]],
        user_id: Optional[str] = None,
        raw_days: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Run the analysis pipeline with pre-loaded journal entries.

        Parameters
        ----------
        journals:
            AutoLife journal entries — treated as narrative context only, not a
            wellbeing signal.
        user_id:
            Override the instance-level user_id for this run.
        raw_days:
            Real phone-sensor marker dicts (one per day) for the WellbeingSensor
            pipeline (Layer 1–4).  This is the sole wellbeing signal source.
            When absent, the orchestrator works from journal narrative + calendar
            + VectorDB only and notes the absence of behavioral data.
        """
        start_time = datetime.now()
        effective_user_id = user_id or self.user_id

        results = {
            'status': 'running',
            'user_id': effective_user_id,
            'journal_summary': None,
            'wellbeing': None,
            'recommendations': [],
            'calendar_summary': None,
            'proposed_changes': [],
            'behavioral_sensing': None,
            'errors': []
        }

        try:
            if not journals:
                results['errors'].append("No journal entries provided")
                results['status'] = 'completed_with_warnings'
                return results

            # 1. Journal narrative — context only, not assessment
            journal_narrative = self.autolife_reader.get_context_for_prompt(journals)
            results['journal_count'] = len(journals)

            # 2. Calendar — use per-request CalendarAPI keyed to the actual user
            logger.info("Getting calendar information...")
            request_calendar = CalendarAPI(suggest_only=True, user_id=effective_user_id)
            calendar_summary = request_calendar.get_schedule_summary(days=7)
            results['calendar_summary'] = calendar_summary
            calendar_events = calendar_summary.get('events', []) if calendar_summary else []

            # 3. Behavioral sensing — the sole wellbeing signal
            behavioral_prose: Optional[str] = None
            risk_level: str = "minimal"
            feedback_history: List[Dict[str, Any]] = []
            llm_analysis: Dict[str, Any] = {}

            if raw_days:
                logger.info("Running WellbeingSensor pipeline (Layer 1-4)...")
                feedback = WellbeingFeedback()
                feedback_history = feedback.get_history(effective_user_id, n=10)

                sensing_result = self.wellbeing_sensor.analyze(
                    raw_days,
                    calendar=calendar_events,
                    user_prefs=None,
                    feedback_history=feedback_history,
                    with_llm=True,
                )
                behavioral_prose = sensing_result.get("prose", "") or None
                baseline_warm = sensing_result.get("baseline_warm", True)
                llm_analysis = sensing_result.get("llm_analysis") or {}

                results['behavioral_sensing'] = {
                    "prose": behavioral_prose,
                    "llm_analysis": llm_analysis,
                }
                if not baseline_warm:
                    results['behavioral_sensing']['baseline_note'] = (
                        "Baseline still building — behavioral patterns will be more reliable after ~10 days of data."
                    )

                # Heuristic risk estimate from Layer 3 prose for VectorDB query
                risk_level = _infer_risk_from_prose(behavioral_prose or "")
            else:
                logger.info("No raw_days provided — proceeding without behavioral sensing.")

            # 4. VectorDB
            logger.info("Querying VectorDB for interventions...")
            vectordb_summary = behavioral_prose or journal_narrative
            if self.vectordb.initialize():
                research_suggestions = self.vectordb.get_intervention_suggestions(
                    risk_level=risk_level,
                    journal_summary=vectordb_summary,
                )
            else:
                research_suggestions = []
                results['errors'].append("VectorDB not available")

            # 5. Orchestrator: one structured-prompt call over all tool outputs
            logger.info("Running orchestrator (schedule proposals)...")
            proposals = self.llm_client.generate_schedule_proposals(
                journal_narrative=journal_narrative,
                behavioral_prose=behavioral_prose,
                risk_level=risk_level,
                calendar_summary=calendar_summary,
                research_context=research_suggestions,
                user_preferences=None,
                feedback_history=feedback_history,
            )

            final_risk = proposals.get('risk_level', risk_level)
            results['journal_summary'] = proposals.get('summary', behavioral_prose or journal_narrative)
            results['wellbeing'] = {
                'risk_level': final_risk,
                'key_concerns': proposals.get('concerns', []),
                'positive_indicators': proposals.get('positives', []),
                'behavioral_context': behavioral_prose or "",
            }
            results['recommendations'] = proposals.get('recommendations', [])
            proposed_changes = proposals.get('proposed_changes', [])

            # Server-side conflict filtering: remove proposals that overlap existing events
            existing_events = calendar_summary.get('events', []) if calendar_summary else []

            def _parse_naive(dt_str: str) -> datetime:
                """Parse ISO datetime and strip timezone to avoid naive/aware comparison errors."""
                dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                return dt.replace(tzinfo=None)

            def _has_server_conflict(proposal: dict) -> bool:
                try:
                    p_start = _parse_naive(proposal['start_time'])
                    p_end   = _parse_naive(proposal['end_time'])
                except (ValueError, KeyError, TypeError):
                    return False
                for ev in existing_events:
                    try:
                        e_start = _parse_naive(ev['start'])
                        e_end   = _parse_naive(ev['end'])
                    except (ValueError, KeyError, TypeError):
                        continue
                    if p_start < e_end - timedelta(minutes=1) and e_start < p_end - timedelta(minutes=1):
                        return True
                return False

            safe_changes = [p for p in proposed_changes if p.get("action", "add") == "add"]
            unsafe_count = len(proposed_changes) - len(safe_changes)
            if unsafe_count:
                logger.warning("Dropped %d non-add proposal(s) from LLM output (prompt injection guard)", unsafe_count)
            filtered_changes = [p for p in safe_changes if not _has_server_conflict(p)]
            conflict_count = len(safe_changes) - len(filtered_changes)
            if conflict_count:
                logger.info(f"Filtered {conflict_count} conflicting proposal(s) server-side")

            # ----------------------------------------------------------------
            # Promote Layer 4 suggestions with start_time → proposed_changes
            # ----------------------------------------------------------------
            # Build a set of (title-ish) keys already present so we don't duplicate.
            gemini_titles = {
                c.get('title', '').strip().lower()
                for c in filtered_changes
            }

            def _find_free_date(time_str: str, duration_min: int = 30) -> str:
                """Return YYYY-MM-DD for the nearest conflict-free day for a HH:MM slot."""
                today = datetime.now().date()
                for offset in range(1, 8):
                    candidate = today + timedelta(days=offset)
                    candidate_str = candidate.strftime('%Y-%m-%d')
                    start_iso = f"{candidate_str}T{time_str}:00"
                    end_dt = _parse_naive(start_iso) + timedelta(minutes=duration_min)
                    end_iso = end_dt.strftime('%Y-%m-%dT%H:%M:%S')
                    probe = {'start_time': start_iso, 'end_time': end_iso}
                    if not _has_server_conflict(probe):
                        return candidate_str
                return (today + timedelta(days=1)).strftime('%Y-%m-%d')

            layer4_additions: List[Dict[str, Any]] = []
            sensing = results.get('behavioral_sensing') or {}
            llm_analysis = sensing.get('llm_analysis') or {}
            for suggestion in llm_analysis.get('suggestions', []):
                start_t = suggestion.get('start_time')
                end_t = suggestion.get('end_time')
                if not start_t:
                    continue  # not time-specific — skip calendar conversion

                # Build full ISO datetimes using the next conflict-free day within 7 days
                def _to_iso(time_str: str) -> str:
                    # Accept "HH:MM" or already a full ISO string
                    if 'T' in time_str or len(time_str) > 8:
                        return time_str
                    best_date = _find_free_date(time_str)
                    return f"{best_date}T{time_str}:00"

                try:
                    start_iso = _to_iso(start_t)
                    end_iso = _to_iso(end_t) if end_t else None

                    # Default end_time: 30 minutes after start if not provided
                    if not end_iso:
                        start_dt = _parse_naive(start_iso)
                        end_iso = (start_dt + timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M:%S')
                    else:
                        start_dt = _parse_naive(start_iso)
                        end_dt = _parse_naive(end_iso)
                        if end_dt <= start_dt:
                            end_iso = (end_dt + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S')
                except (ValueError, TypeError):
                    logger.warning("Layer 4 suggestion has unparseable times: %s", suggestion)
                    continue

                change_text = suggestion.get('change', '')
                # Simple de-duplication: skip if a Gemini change with the same
                # leading words already exists in the filtered set.
                change_key = change_text.strip().lower()[:40]
                if any(change_key in t for t in gemini_titles):
                    continue

                entry: Dict[str, Any] = {
                    'action': 'add',
                    'title': change_text,
                    'description': suggestion.get('rationale', ''),
                    'start_time': start_iso,
                    'end_time': end_iso,
                    'category': 'Wellness',
                    'reason': suggestion.get('rationale', ''),
                    'source': 'behavioral_sensing',
                }
                if not _has_server_conflict(entry):
                    layer4_additions.append(entry)
                else:
                    logger.info("Layer 4 suggestion conflicts with existing event, skipping: %s", change_text)

            if layer4_additions:
                logger.info("Adding %d Layer 4 suggestion(s) to proposed_changes", len(layer4_additions))

            results['proposed_changes'] = filtered_changes + layer4_additions
            results['mental_health'] = results['wellbeing']  # Backward-compatible alias for deployed clients.

            results['status'] = 'completed'

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            results['errors'].append(str(e))
            results['status'] = 'failed'

        results['duration_seconds'] = (datetime.now() - start_time).total_seconds()
        return results

    def run(self, mode: str = "daily") -> Dict[str, Any]:
        """Run the full agent workflow, reading journals from the filesystem."""
        logger.info(f"Running agent in {mode} mode")
        start_time = datetime.now()

        logger.info("Reading journals...")
        journals = self.autolife_reader.read_journals(limit=10)

        results = self.run_from_journals(journals)
        results['mode'] = mode
        results['timestamp'] = start_time.isoformat()
        return results

    def apply_calendar_changes(
        self,
        changes: List[Dict[str, Any]],
        user_comments: str = "",
        proposed_changes: Optional[List[Dict[str, Any]]] = None,
        behavioral_state_summary: str = "",
        user_id: str = "default",
    ) -> Dict[str, Any]:
        """
        Apply proposed calendar changes.

        Parameters
        ----------
        changes:
            List of proposed changes to apply (subset or all of proposed_changes).
        user_comments:
            Optional user comments to consider.
        proposed_changes:
            Full list of proposed changes from the pipeline run (used to detect
            which suggestions were *not* applied so they can be recorded as
            rejected in the feedback store).
        behavioral_state_summary:
            Short string describing the current behavioral state — stored
            alongside each feedback record for future personalisation.
        """
        logger.info("Applying calendar changes...")

        # Save user comments to memory if provided
        if user_comments:
            self.memory.storage.save('user_feedback', f'calendar_{datetime.now().strftime("%Y%m%d")}', {
                'comments': user_comments,
                'timestamp': datetime.now().isoformat()
            })
            logger.info("Saved user comments to memory")

        results = {
            'applied': [],
            'failed': [],
            'skipped': []
        }

        feedback = WellbeingFeedback()

        # Per-request CalendarAPI avoids shared suggest_only state mutation
        with self._calendar_lock:
            request_calendar = CalendarAPI(suggest_only=False, user_id=user_id)
            try:
                applied_titles: set = set()

                for change in changes:
                    action = change.get('action', 'add')
                    change_title = change.get('title', 'Wellness Activity')

                    try:
                        if action == 'add':
                            start_time = datetime.fromisoformat(change.get('start_time'))
                            end_time = datetime.fromisoformat(change.get('end_time'))

                            event = CalendarEvent(
                                id=None,
                                summary=change_title,
                                description=change.get('description', ''),
                                start_time=start_time,
                                end_time=end_time
                            )

                            event_id = request_calendar.create_event(event)
                            if event_id:
                                results['applied'].append({
                                    'action': 'created',
                                    'title': event.summary,
                                    'event_id': event_id
                                })
                                applied_titles.add(change_title.strip().lower())
                                feedback.record(
                                    user_id,
                                    suggestion=change_title,
                                    action='accept',
                                    behavioral_state_summary=behavioral_state_summary,
                                )
                            else:
                                results['failed'].append(change)

                        elif action == 'update':
                            event_id = change.get('event_id')
                            updates = change.get('updates', {})

                            if request_calendar.update_event(event_id, updates):
                                results['applied'].append({
                                    'action': 'updated',
                                    'event_id': event_id,
                                    'updates': updates
                                })
                                applied_titles.add(change_title.strip().lower())
                                feedback.record(
                                    user_id,
                                    suggestion=change_title,
                                    action='accept',
                                    behavioral_state_summary=behavioral_state_summary,
                                )
                            else:
                                results['failed'].append(change)

                        elif action == 'delete':
                            event_id = change.get('event_id')

                            if request_calendar.delete_event(event_id):
                                results['applied'].append({
                                    'action': 'deleted',
                                    'event_id': event_id
                                })
                                applied_titles.add(change_title.strip().lower())
                                feedback.record(
                                    user_id,
                                    suggestion=change_title,
                                    action='accept',
                                    behavioral_state_summary=behavioral_state_summary,
                                )
                            else:
                                results['failed'].append(change)
                        else:
                            results['skipped'].append(change)

                    except Exception as e:
                        logger.error(f"Failed to apply change: {e}")
                        change['error'] = str(e)
                        results['failed'].append(change)

            finally:
                pass  # request_calendar is local; no teardown needed

        # Best-effort: record proposals that were NOT in the applied set as
        # rejected (only if the caller passed the full proposed_changes list).
        if proposed_changes:
            for proposal in proposed_changes:
                title = proposal.get('title', '').strip().lower()
                if title and title not in applied_titles:
                    feedback.record(
                        user_id,
                        suggestion=proposal.get('title', ''),
                        action='reject',
                        behavioral_state_summary=behavioral_state_summary,
                    )

        return results


# Backwards compatibility
Agent = LLMSchedulerAgent
