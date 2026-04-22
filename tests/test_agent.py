"""
Tests for agent.py — LLMSchedulerAgent orchestrator.

All tool dependencies (LLMClient, VectorDBClient, CalendarAPI, AutoLifeReader,
MemoryModule) are mocked. Tests cover:
- run_from_journals() happy path and error cases
- Server-side conflict filtering logic
- apply_calendar_changes() with add/update/delete/unknown actions
- Empty journals edge case
- Thread-safe suggest_only toggling
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, PropertyMock

from agent import LLMSchedulerAgent



# Helpers

def _make_agent():
    """Instantiate an agent with all tools mocked out."""
    with patch("agent.AutoLifeReader"), \
         patch("agent.AutoLifePhoneAdapter"), \
         patch("agent.WellbeingSensor"), \
         patch("agent.VectorDBClient"), \
         patch("agent.CalendarAPI"), \
         patch("agent.LLMClient"), \
         patch("agent.WellbeingFeedback"), \
         patch("agent.MemoryModule"):
        agent = LLMSchedulerAgent(suggest_only=True)

    # Provide sensible mock return values
    agent.autolife_reader.get_context_for_prompt.return_value = "Journal text here"
    # Ensure phone adapter returns no raw days so behavioral sensing is skipped
    agent.phone_adapter.journals_to_raw_days.return_value = []
    agent.llm_client.analyze_wellbeing.return_value = {
        "summary": "User is doing okay",
        "risk_level": "mild",
        "concerns": [],
        "positives": ["regular schedule"],
    }
    agent.calendar_api.get_schedule_summary.return_value = {
        "event_count": 0,
        "events": [],
        "total_hours": 0,
        "busiest_day": None,
        "days_covered": 0,
        "tasks": [],
        "task_count": 0,
    }
    agent.vectordb.initialize.return_value = True
    agent.vectordb.get_intervention_suggestions.return_value = [
        {"category": "Sleep", "content": "Go to bed at 10pm", "source": "sleep_study.pdf"},
    ]
    agent.llm_client.generate_recommendations.return_value = [
        {"category": "Sleep", "action": "Sleep by 10pm", "when": "nightly", "source": "study"},
    ]
    agent.llm_client.generate_calendar_changes.return_value = [
        {
            "action": "add",
            "title": "Evening Wind-Down",
            "description": "Relax before bed",
            "start_time": (datetime.now() + timedelta(days=1)).replace(hour=21, minute=0).strftime("%Y-%m-%dT%H:%M:%S"),
            "end_time": (datetime.now() + timedelta(days=1)).replace(hour=21, minute=30).strftime("%Y-%m-%dT%H:%M:%S"),
            "category": "Sleep",
            "reason": "Better sleep hygiene",
        }
    ]
    return agent



# run_from_journals

class TestRunFromJournals:

    def test_happy_path(self, sample_journals):
        agent = _make_agent()
        result = agent.run_from_journals(sample_journals, user_id="test")

        assert result["status"] == "completed"
        assert result["user_id"] == "test"
        assert result["journal_count"] == 2
        assert result["journal_summary"] == "User is doing okay"
        assert result["wellbeing"]["risk_level"] == "mild"
        assert isinstance(result["recommendations"], list)
        assert isinstance(result["proposed_changes"], list)
        assert "duration_seconds" in result

    def test_empty_journals(self):
        agent = _make_agent()
        result = agent.run_from_journals([])

        assert result["status"] == "completed_with_warnings"
        assert "No journal entries" in result["errors"][0]

    def test_vectordb_unavailable(self, sample_journals):
        agent = _make_agent()
        agent.vectordb.initialize.return_value = False

        result = agent.run_from_journals(sample_journals)

        assert result["status"] == "completed"
        assert any("VectorDB not available" in e for e in result["errors"])

    def test_behavioral_summary_replaces_journal_fallback(self, sample_journals):
        agent = _make_agent()
        behavioral_summary = "Behavioral wellbeing signal is available from recent app data."
        agent.llm_client.analyze_wellbeing.return_value = {
            "summary": "Unable to analyze journals",
            "risk_level": "mild",
            "concerns": [],
            "positives": [],
        }
        agent.phone_adapter.journals_to_raw_days.return_value = [
            {
                "date": "2026-04-21",
                "activity": {"steps": 1200},
                "mobility": {},
                "screen": {},
                "environment": {},
            }
        ]
        agent.wellbeing_sensor.analyze.return_value = {
            "prose": behavioral_summary,
            "llm_analysis": None,
        }

        result = agent.run_from_journals(sample_journals)

        assert result["status"] == "completed"
        assert result["journal_summary"] == behavioral_summary
        assert result["wellbeing"]["behavioral_context"] == behavioral_summary
        assert result["mental_health"] == result["wellbeing"]
        agent.llm_client.synthesize_wellbeing.assert_not_called()

    def test_pipeline_exception_sets_failed_status(self, sample_journals):
        agent = _make_agent()
        agent.llm_client.analyze_wellbeing.side_effect = RuntimeError("API down")

        result = agent.run_from_journals(sample_journals)

        assert result["status"] == "failed"
        assert any("API down" in e for e in result["errors"])

    def test_calls_tools_in_order(self, sample_journals):
        agent = _make_agent()
        agent.run_from_journals(sample_journals)

        agent.autolife_reader.get_context_for_prompt.assert_called_once()
        agent.llm_client.analyze_wellbeing.assert_called_once()
        agent.calendar_api.get_schedule_summary.assert_called_once()
        agent.vectordb.initialize.assert_called_once()
        agent.vectordb.get_intervention_suggestions.assert_called_once()
        agent.llm_client.generate_recommendations.assert_called_once()
        agent.llm_client.generate_calendar_changes.assert_called_once()

    def test_default_user_id(self, sample_journals):
        agent = _make_agent()
        agent.user_id = "agent_default"
        result = agent.run_from_journals(sample_journals)
        # When user_id is None, falls back to agent.user_id
        assert result["user_id"] == "agent_default"



# Conflict filtering

class TestConflictFiltering:

    def test_filters_overlapping_proposals(self, sample_journals):
        agent = _make_agent()

        tomorrow = datetime.now() + timedelta(days=1)
        # Existing event: 10:00-11:00
        agent.calendar_api.get_schedule_summary.return_value = {
            "events": [
                {
                    "id": "existing1",
                    "title": "Meeting",
                    "start": tomorrow.replace(hour=10, minute=0).strftime("%Y-%m-%dT%H:%M:%S"),
                    "end": tomorrow.replace(hour=11, minute=0).strftime("%Y-%m-%dT%H:%M:%S"),
                }
            ],
            "tasks": [],
        }

        # Proposed event overlaps: 10:30-11:30
        agent.llm_client.generate_calendar_changes.return_value = [
            {
                "action": "add",
                "title": "Walk",
                "start_time": tomorrow.replace(hour=10, minute=30).strftime("%Y-%m-%dT%H:%M:%S"),
                "end_time": tomorrow.replace(hour=11, minute=30).strftime("%Y-%m-%dT%H:%M:%S"),
            }
        ]

        result = agent.run_from_journals(sample_journals)
        # The overlapping proposal should be filtered out
        assert len(result["proposed_changes"]) == 0

    def test_keeps_non_overlapping_proposals(self, sample_journals):
        agent = _make_agent()

        tomorrow = datetime.now() + timedelta(days=1)
        agent.calendar_api.get_schedule_summary.return_value = {
            "events": [
                {
                    "id": "existing1",
                    "title": "Meeting",
                    "start": tomorrow.replace(hour=10, minute=0).strftime("%Y-%m-%dT%H:%M:%S"),
                    "end": tomorrow.replace(hour=11, minute=0).strftime("%Y-%m-%dT%H:%M:%S"),
                }
            ],
            "tasks": [],
        }

        # Proposed event does NOT overlap: 07:00-07:30
        agent.llm_client.generate_calendar_changes.return_value = [
            {
                "action": "add",
                "title": "Meditation",
                "start_time": tomorrow.replace(hour=7, minute=0).strftime("%Y-%m-%dT%H:%M:%S"),
                "end_time": tomorrow.replace(hour=7, minute=30).strftime("%Y-%m-%dT%H:%M:%S"),
            }
        ]

        result = agent.run_from_journals(sample_journals)
        assert len(result["proposed_changes"]) == 1

    def test_handles_malformed_proposal_times(self, sample_journals):
        agent = _make_agent()

        agent.calendar_api.get_schedule_summary.return_value = {"events": [], "tasks": []}
        agent.llm_client.generate_calendar_changes.return_value = [
            {
                "action": "add",
                "title": "Bad Times",
                "start_time": "not-a-date",
                "end_time": "also-not-a-date",
            }
        ]

        result = agent.run_from_journals(sample_journals)
        # Malformed proposals are NOT considered conflicts (_has_server_conflict returns False)
        assert len(result["proposed_changes"]) == 1

    def test_handles_malformed_event_times(self, sample_journals):
        agent = _make_agent()

        agent.calendar_api.get_schedule_summary.return_value = {
            "events": [{"id": "e1", "title": "Bad", "start": "nope", "end": "nope"}],
            "tasks": [],
        }
        tomorrow = datetime.now() + timedelta(days=1)
        agent.llm_client.generate_calendar_changes.return_value = [
            {
                "action": "add",
                "title": "Good",
                "start_time": tomorrow.replace(hour=8).strftime("%Y-%m-%dT%H:%M:%S"),
                "end_time": tomorrow.replace(hour=9).strftime("%Y-%m-%dT%H:%M:%S"),
            }
        ]

        result = agent.run_from_journals(sample_journals)
        # Malformed events are skipped during conflict check
        assert len(result["proposed_changes"]) == 1



# apply_calendar_changes

class TestApplyCalendarChanges:

    def test_add_action(self):
        agent = _make_agent()
        agent.calendar_api.create_event.return_value = "new_event_id"

        changes = [
            {
                "action": "add",
                "title": "Meditation",
                "description": "10 min meditation",
                "start_time": "2024-06-01T08:00:00",
                "end_time": "2024-06-01T08:15:00",
            }
        ]

        results = agent.apply_calendar_changes(changes)
        assert len(results["applied"]) == 1
        assert results["applied"][0]["action"] == "created"
        assert results["applied"][0]["event_id"] == "new_event_id"

    def test_add_action_failure(self):
        agent = _make_agent()
        agent.calendar_api.create_event.return_value = None

        changes = [
            {
                "action": "add",
                "title": "Meditation",
                "start_time": "2024-06-01T08:00:00",
                "end_time": "2024-06-01T08:15:00",
            }
        ]

        results = agent.apply_calendar_changes(changes)
        assert len(results["failed"]) == 1

    def test_update_action(self):
        agent = _make_agent()
        agent.calendar_api.update_event = MagicMock(return_value=True)

        changes = [
            {
                "action": "update",
                "event_id": "evt123",
                "updates": {"summary": "New Title"},
            }
        ]

        results = agent.apply_calendar_changes(changes)
        assert len(results["applied"]) == 1
        assert results["applied"][0]["action"] == "updated"

    def test_delete_action(self):
        agent = _make_agent()
        agent.calendar_api.delete_event = MagicMock(return_value=True)

        changes = [{"action": "delete", "event_id": "evt456"}]

        results = agent.apply_calendar_changes(changes)
        assert len(results["applied"]) == 1
        assert results["applied"][0]["action"] == "deleted"

    def test_unknown_action_skipped(self):
        agent = _make_agent()
        changes = [{"action": "teleport", "title": "Unknown"}]

        results = agent.apply_calendar_changes(changes)
        assert len(results["skipped"]) == 1

    def test_suggest_only_toggled_and_restored(self):
        agent = _make_agent()
        agent.calendar_api.suggest_only = True
        agent.calendar_api.create_event.return_value = "id"

        changes = [
            {
                "action": "add",
                "title": "Test",
                "start_time": "2024-06-01T08:00:00",
                "end_time": "2024-06-01T08:15:00",
            }
        ]

        agent.apply_calendar_changes(changes)
        # After apply, suggest_only should be restored to True
        assert agent.calendar_api.suggest_only is True

    def test_suggest_only_restored_on_exception(self):
        agent = _make_agent()
        agent.calendar_api.suggest_only = True
        agent.calendar_api.create_event.side_effect = Exception("boom")

        changes = [
            {
                "action": "add",
                "title": "Fail",
                "start_time": "2024-06-01T08:00:00",
                "end_time": "2024-06-01T08:15:00",
            }
        ]

        # The exception is caught per-change, so it won't propagate
        results = agent.apply_calendar_changes(changes)
        assert agent.calendar_api.suggest_only is True
        assert len(results["failed"]) == 1

    def test_saves_user_comments_to_memory(self):
        agent = _make_agent()
        agent.apply_calendar_changes([], user_comments="I prefer mornings")
        agent.memory.storage.save.assert_called_once()

    def test_no_memory_save_without_comments(self):
        agent = _make_agent()
        agent.apply_calendar_changes([])
        agent.memory.storage.save.assert_not_called()

    def test_mixed_actions(self):
        agent = _make_agent()
        agent.calendar_api.create_event.return_value = "new_id"
        agent.calendar_api.update_event = MagicMock(return_value=True)
        agent.calendar_api.delete_event = MagicMock(return_value=True)

        changes = [
            {"action": "add", "title": "Walk", "start_time": "2024-06-01T08:00:00",
             "end_time": "2024-06-01T08:30:00"},
            {"action": "update", "event_id": "e1", "updates": {"summary": "Updated"}},
            {"action": "delete", "event_id": "e2"},
            {"action": "unknown_action"},
        ]

        results = agent.apply_calendar_changes(changes)
        assert len(results["applied"]) == 3
        assert len(results["skipped"]) == 1
        assert len(results["failed"]) == 0
