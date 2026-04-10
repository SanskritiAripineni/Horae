"""
LLM Scheduler Agent - The "Conductor"
Orchestrates journal analysis, mental health assessment, and calendar optimization.
"""

import logging
import threading
from typing import Any, Dict, List
from datetime import datetime, timedelta

# Import config FIRST to load .env
from config import config

from tools.autolife_reader import AutoLifeReader
from tools.vectordb_client import VectorDBClient
from tools.calendar_api import CalendarAPI, CalendarEvent
from tools.llm_client import LLMClient
from memory import MemoryModule

logger = logging.getLogger(__name__)


class LLMSchedulerAgent:
    """
    Main agent that orchestrates the mental health analysis and calendar optimization.
    """
    
    def __init__(self, suggest_only: bool = True, user_id: str = "default"):
        self.suggest_only = suggest_only
        self.user_id = user_id
        
        # Initialize tools
        self.autolife_reader = AutoLifeReader()
        self.vectordb = VectorDBClient()
        self.calendar_api = CalendarAPI(suggest_only=suggest_only)
        self.llm_client = LLMClient()
        self.memory = MemoryModule()
        self._calendar_lock = threading.Lock()

        logger.info("LLMSchedulerAgent initialized")

    def run_from_journals(self, journals: List[Dict[str, Any]], user_id: str = None) -> Dict[str, Any]:
        """Run the analysis pipeline with pre-loaded journal entries."""
        start_time = datetime.now()

        results = {
            'status': 'running',
            'user_id': user_id or self.user_id,
            'journal_summary': None,
            'mental_health': None,
            'recommendations': [],
            'calendar_summary': None,
            'proposed_changes': [],
            'errors': []
        }

        try:
            if not journals:
                results['errors'].append("No journal entries provided")
                results['status'] = 'completed_with_warnings'
                return results

            journal_text = self.autolife_reader.get_context_for_prompt(journals)
            results['journal_count'] = len(journals)

            logger.info("Analyzing mental health...")
            analysis = self.llm_client.analyze_mental_health(journal_text)
            results['journal_summary'] = analysis.get('summary', '')
            results['mental_health'] = {
                'estimated_phq4': analysis.get('phq4_estimate', 3),
                'risk_level': analysis.get('risk_level', 'minimal'),
                'key_concerns': analysis.get('concerns', []),
                'positive_indicators': analysis.get('positives', [])
            }

            logger.info("Getting calendar information...")
            calendar_summary = self.calendar_api.get_schedule_summary(days=7)
            results['calendar_summary'] = calendar_summary

            logger.info("Querying VectorDB for interventions...")
            phq4 = results['mental_health']['estimated_phq4']
            if self.vectordb.initialize():
                research_suggestions = self.vectordb.get_intervention_suggestions(
                    phq4_score=phq4,
                    journal_summary=results['journal_summary']
                )
            else:
                research_suggestions = []
                results['errors'].append("VectorDB not available")

            logger.info("Generating recommendations...")
            recommendations = self.llm_client.generate_recommendations(
                journal_summary=results['journal_summary'],
                risk_level=results['mental_health']['risk_level'],
                concerns=results['mental_health']['key_concerns'],
                research_context=research_suggestions
            )
            results['recommendations'] = recommendations

            logger.info("Generating calendar optimization proposals...")
            proposed_changes = self.llm_client.generate_calendar_changes(
                recommendations=recommendations,
                calendar_summary=calendar_summary,
                mental_health=results['mental_health']
            )

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

            filtered_changes = [p for p in proposed_changes if not _has_server_conflict(p)]
            conflict_count = len(proposed_changes) - len(filtered_changes)
            if conflict_count:
                logger.info(f"Filtered {conflict_count} conflicting proposal(s) server-side")
            results['proposed_changes'] = filtered_changes

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

    def apply_calendar_changes(self, changes: List[Dict[str, Any]], user_comments: str = "") -> Dict[str, Any]:
        """
        Apply proposed calendar changes.
        
        Args:
            changes: List of proposed changes from generate_calendar_changes
            user_comments: Optional user comments to consider
            
        Returns:
            Results of applying the changes
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

        # Lock to prevent concurrent requests from interleaving suggest_only state
        with self._calendar_lock:
            self.calendar_api.suggest_only = False
            try:
                for change in changes:
                    action = change.get('action', 'add')

                    try:
                        if action == 'add':
                            start_time = datetime.fromisoformat(change.get('start_time'))
                            end_time = datetime.fromisoformat(change.get('end_time'))

                            event = CalendarEvent(
                                id=None,
                                summary=change.get('title', 'Wellness Activity'),
                                description=change.get('description', ''),
                                start_time=start_time,
                                end_time=end_time
                            )

                            event_id = self.calendar_api.create_event(event)
                            if event_id:
                                results['applied'].append({
                                    'action': 'created',
                                    'title': event.summary,
                                    'event_id': event_id
                                })
                            else:
                                results['failed'].append(change)

                        elif action == 'update':
                            event_id = change.get('event_id')
                            updates = change.get('updates', {})

                            if self.calendar_api.update_event(event_id, updates):
                                results['applied'].append({
                                    'action': 'updated',
                                    'event_id': event_id,
                                    'updates': updates
                                })
                            else:
                                results['failed'].append(change)

                        elif action == 'delete':
                            event_id = change.get('event_id')

                            if self.calendar_api.delete_event(event_id):
                                results['applied'].append({
                                    'action': 'deleted',
                                    'event_id': event_id
                                })
                            else:
                                results['failed'].append(change)
                        else:
                            results['skipped'].append(change)

                    except Exception as e:
                        logger.error(f"Failed to apply change: {e}")
                        change['error'] = str(e)
                        results['failed'].append(change)
            finally:
                self.calendar_api.suggest_only = True

        return results


# Backwards compatibility
Agent = LLMSchedulerAgent
