"""
Tests for agent.py — LLMSchedulerAgent orchestrator.

All tool dependencies (LLMClient, VectorDBClient, CalendarAPI, AutoLifeReader,
MemoryModule, WellbeingSensor) are mocked. Tests cover:
- run_from_journals() happy path (journal-only and with raw_days)
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
         patch("agent.WellbeingSensor"), \
         patch("agent.VectorDBClient"), \
         patch("agent.CalendarAPI"), \
         patch("agent.LLMClient"), \
         patch("agent.WellbeingFeedback"), \
         patch("agent.MemoryModule"):
        agent = LLMSchedulerAgent(suggest_only=True)

    # Sensible mock return values
    agent.autolife_reader.get_context_for_prompt.return_value = "Journal narrative text"
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
    agent.llm_client.generate_schedule_proposals.return_value = {
        "risk_level": "mild",
        "summary": "User shows mild stress indicators from behavioral data.",
        "concerns": ["irregular sleep"],
        "positives": ["regular exercise"],
        "recommendations": [
            {"category": "Sleep", "action": "Sleep by 10pm", "when": "nightly", "source": "study"},
        ],
        "proposed_changes": [
            {
                "action": "add",
                "title": "Evening Wind-Down",
                "description": "Relax before bed",
                "start_time": (datetime.now() + timedelta(days=1)).replace(hour=21, minute=0).strftime("%Y-%m-%dT%H:%M:%S"),
                "end_time": (datetime.now() + timedelta(days=1)).replace(hour=21, minute=30).strftime("%Y-%m-%dT%H:%M:%S"),
                "category": "Sleep",
                "reason": "Better sleep hygiene",
            }
        ],
    }
    return agent


# run_from_journals

class TestRunFromJournals:

    def test_happy_path(self, sample_journals):
        agent = _make_agent()
        result = agent.run_from_journals(sample_journals, user_id="test")

        assert result["status"] == "completed"
        assert result["user_id"] == "test"
        assert result["journal_count"] == 2
        assert result["wellbeing"]["risk_level"] == "mild"
        assert result["ui_summary"]["headline"] == "Mild stress"
        assert result["analysis_details"]["journal_count"] == 2
        assert result["analysis_details"]["research_sources"][0]["source"] == "sleep_study.pdf"
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

    def test_journals_only_no_raw_days(self, sample_journals):
        """When no raw_days are provided, behavioral_sensing is None and
        the orchestrator still runs using journal narrative + VectorDB + calendar."""
        agent = _make_agent()
        result = agent.run_from_journals(sample_journals, raw_days=None)

        assert result["status"] == "completed"
        assert result["behavioral_sensing"] is None
        agent.wellbeing_sensor.analyze.assert_not_called()
        agent.llm_client.generate_schedule_proposals.assert_called_once()
        # behavioral_prose arg should be None
        call_kwargs = agent.llm_client.generate_schedule_proposals.call_args.kwargs
        assert call_kwargs.get("behavioral_prose") is None

    def test_with_raw_days_runs_behavioral_sensing(self, sample_journals):
        """When raw_days are provided, WellbeingSensor runs and its prose reaches
        the orchestrator."""
        agent = _make_agent()
        behavioral_prose = "Sleep regularity has declined over the past week."
        agent.wellbeing_sensor.analyze.return_value = {
            "prose": behavioral_prose,
            "llm_analysis": {"suggestions": []},
            "baseline_warm": True,
        }

        raw_days = [{"date": "2026-04-20", "sleep_onset_hour": 23.5,
                     "sleep_duration_hours": 6.0, "mobility_entropy": 1.2}]
        result = agent.run_from_journals(sample_journals, raw_days=raw_days)

        assert result["status"] == "completed"
        assert result["behavioral_sensing"]["prose"] == behavioral_prose
        agent.wellbeing_sensor.analyze.assert_called_once()
        call_kwargs = agent.llm_client.generate_schedule_proposals.call_args.kwargs
        assert call_kwargs.get("behavioral_prose") == behavioral_prose

    def test_baseline_not_warm_note_added(self, sample_journals):
        agent = _make_agent()
        agent.wellbeing_sensor.analyze.return_value = {
            "prose": "Patterns observed.",
            "llm_analysis": {},
            "baseline_warm": False,
        }
        raw_days = [{"date": "2026-04-20"}]
        result = agent.run_from_journals(sample_journals, raw_days=raw_days)

        assert "baseline_note" in result["behavioral_sensing"]

    def test_pipeline_exception_sets_failed_status(self, sample_journals):
        agent = _make_agent()
        agent.llm_client.generate_schedule_proposals.side_effect = RuntimeError("API down")

        result = agent.run_from_journals(sample_journals)

        assert result["status"] == "failed"
        assert any("API down" in e for e in result["errors"])

    def test_calls_tools_in_order(self, sample_journals):
        agent = _make_agent()
        agent.run_from_journals(sample_journals)

        agent.autolife_reader.get_context_for_prompt.assert_called_once()
        agent.calendar_api.get_schedule_summary.assert_called_once()
        agent.vectordb.initialize.assert_called_once()
        agent.vectordb.get_intervention_suggestions.assert_called_once()
        agent.llm_client.generate_schedule_proposals.assert_called_once()

    def test_default_user_id(self, sample_journals):
        agent = _make_agent()
        agent.user_id = "agent_default"
        result = agent.run_from_journals(sample_journals)
        assert result["user_id"] == "agent_default"

    def test_mental_health_alias(self, sample_journals):
        """mental_health key is a backward-compat alias for wellbeing."""
        agent = _make_agent()
        result = agent.run_from_journals(sample_journals)
        assert result["mental_health"] == result["wellbeing"]

    def test_ui_summary_falls_back_when_model_omits_it(self, sample_journals):
        agent = _make_agent()
        agent.llm_client.generate_schedule_proposals.return_value["ui_summary"] = "not a dict"

        result = agent.run_from_journals(sample_journals)

        assert result["ui_summary"]["headline"] == "Mild stress"
        assert result["ui_summary"]["concerns"][0]["label"] == "irregular sleep"
        assert result["ui_summary"]["protective_signals"][0]["label"] == "regular exercise"

    def test_ui_summary_uses_model_structured_fields(self, sample_journals):
        agent = _make_agent()
        agent.llm_client.generate_schedule_proposals.return_value["ui_summary"] = {
            "headline": "Mild sleep strain",
            "confidence_label": "Medium confidence",
            "summary": "Late nights are nudging recovery down.",
            "evidence_chips": [{"label": "Late screen", "kind": "concern", "icon": "moon"}],
            "concerns": [{"label": "Late-night screen", "detail": "Repeated after 11 PM"}],
            "protective_signals": [{"label": "Still active"}],
        }

        result = agent.run_from_journals(sample_journals)

        assert result["ui_summary"]["headline"] == "Mild sleep strain"
        assert result["ui_summary"]["confidence_label"] == "Medium confidence"
        assert result["ui_summary"]["evidence_chips"][0]["label"] == "Late screen"


# Conflict filtering

class TestConflictFiltering:

    def test_filters_overlapping_proposals(self, sample_journals):
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

        # Proposed event overlaps: 10:30-11:30
        agent.llm_client.generate_schedule_proposals.return_value = {
            "risk_level": "mild", "summary": "", "concerns": [], "positives": [],
            "recommendations": [],
            "proposed_changes": [
                {
                    "action": "add",
                    "title": "Walk",
                    "start_time": tomorrow.replace(hour=10, minute=30).strftime("%Y-%m-%dT%H:%M:%S"),
                    "end_time": tomorrow.replace(hour=11, minute=30).strftime("%Y-%m-%dT%H:%M:%S"),
                }
            ],
        }

        result = agent.run_from_journals(sample_journals)
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
        agent.llm_client.generate_schedule_proposals.return_value = {
            "risk_level": "mild", "summary": "", "concerns": [], "positives": [],
            "recommendations": [],
            "proposed_changes": [
                {
                    "action": "add",
                    "title": "Meditation",
                    "start_time": tomorrow.replace(hour=7, minute=0).strftime("%Y-%m-%dT%H:%M:%S"),
                    "end_time": tomorrow.replace(hour=7, minute=30).strftime("%Y-%m-%dT%H:%M:%S"),
                }
            ],
        }

        result = agent.run_from_journals(sample_journals)
        assert len(result["proposed_changes"]) == 1

    def test_handles_malformed_proposal_times(self, sample_journals):
        agent = _make_agent()
        agent.calendar_api.get_schedule_summary.return_value = {"events": [], "tasks": []}
        agent.llm_client.generate_schedule_proposals.return_value = {
            "risk_level": "minimal", "summary": "", "concerns": [], "positives": [],
            "recommendations": [],
            "proposed_changes": [
                {
                    "action": "add",
                    "title": "Bad Times",
                    "start_time": "not-a-date",
                    "end_time": "also-not-a-date",
                }
            ],
        }

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
        agent.llm_client.generate_schedule_proposals.return_value = {
            "risk_level": "minimal", "summary": "", "concerns": [], "positives": [],
            "recommendations": [],
            "proposed_changes": [
                {
                    "action": "add",
                    "title": "Good",
                    "start_time": tomorrow.replace(hour=8).strftime("%Y-%m-%dT%H:%M:%S"),
                    "end_time": tomorrow.replace(hour=9).strftime("%Y-%m-%dT%H:%M:%S"),
                }
            ],
        }

        result = agent.run_from_journals(sample_journals)
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
