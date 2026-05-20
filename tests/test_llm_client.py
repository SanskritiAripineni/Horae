"""
Tests for tools/llm_client.py — Gemini API wrapper.

All Gemini API calls are mocked. Tests cover:
- JSON parsing from model responses (with and without markdown fencing)
- Fallback behaviour when API key is missing or client is None
- generate_schedule_proposals(), generate_recommendations(), generate_calendar_changes()
- parse_user_feedback()
"""

import json
import pytest
from unittest.mock import patch, MagicMock



# Helpers

def _make_client(api_key="fake-key"):
    """Instantiate LLMClient with a mocked genai.Client."""
    with patch("tools.llm_client.genai") as mock_genai:
        mock_genai_client = MagicMock()
        mock_genai.Client.return_value = mock_genai_client
        from tools.llm_client import LLMClient
        client = LLMClient(api_key=api_key)
        client.client = mock_genai_client
        return client, mock_genai_client


def _set_generate_response(mock_genai_client, text: str):
    """Configure the mock to return *text* from models.generate_content()."""
    mock_response = MagicMock()
    mock_response.text = text
    mock_genai_client.models.generate_content.return_value = mock_response



# generate_schedule_proposals

class TestGenerateScheduleProposals:

    def _base_calendar(self):
        return {"events": [], "tasks": []}

    def test_happy_path(self):
        client, mock = _make_client()
        payload = {
            "risk_level": "mild",
            "summary": "User shows mild stress from irregular sleep.",
            "concerns": ["poor sleep"],
            "positives": ["regular exercise"],
            "recommendations": [
                {"category": "Sleep", "action": "Sleep by 10pm", "when": "nightly", "source": "study"}
            ],
            "proposed_changes": [
                {
                    "action": "add",
                    "title": "Wind-Down",
                    "description": "Relax before bed",
                    "start_time": "2026-04-22T21:00:00",
                    "end_time": "2026-04-22T21:30:00",
                    "category": "Sleep",
                    "reason": "Better sleep hygiene",
                }
            ],
        }
        _set_generate_response(mock, json.dumps(payload))

        result = client.generate_schedule_proposals(
            journal_narrative="User went to gym and studied.",
            behavioral_prose="Sleep onset shifted 90 min later this week.",
            risk_level="mild",
            calendar_summary=self._base_calendar(),
            research_context=[{"category": "Sleep", "content": "Sleep matters", "source": "paper.pdf"}],
        )

        assert result["risk_level"] == "mild"
        assert len(result["recommendations"]) == 1
        assert len(result["proposed_changes"]) == 1

    def test_behavioral_prose_included_in_prompt(self):
        client, mock = _make_client()
        _set_generate_response(mock, json.dumps({
            "risk_level": "minimal", "summary": "", "concerns": [], "positives": [],
            "recommendations": [], "proposed_changes": [],
        }))
        behavioral_prose = "Mobility entropy dropped significantly."
        client.generate_schedule_proposals(
            journal_narrative="normal day",
            behavioral_prose=behavioral_prose,
            risk_level="mild",
            calendar_summary=self._base_calendar(),
            research_context=[],
        )
        prompt = mock.models.generate_content.call_args.kwargs.get("contents", "")
        assert behavioral_prose in prompt

    def test_behavioral_state_fields_are_rendered_with_current_schema(self):
        client, mock = _make_client()
        _set_generate_response(mock, json.dumps({
            "risk_level": "minimal", "summary": "", "concerns": [], "positives": [],
            "recommendations": [], "proposed_changes": [],
        }))

        behavioral_state = {
            "baseline_state": {"days_of_history": 14, "overall_confidence": "low"},
            "deviations": [
                {
                    "marker": "sleep_duration_hours",
                    "direction": "down",
                    "magnitude": "moderate",
                    "finding": "Sleep has averaged 5.2h versus a typical 7.6h.",
                    "trajectory": "sustained-4d",
                    "coverage": "medium",
                    "recent_mean": 5.2,
                    "baseline_mean": 7.6,
                }
            ],
            "coherent_patterns": [
                {
                    "name": "fragmented-attention-with-sleep-loss",
                    "interpretation": "Attention is more fragmented while sleep is shorter.",
                    "implicated": ["app_switching_rate", "sleep_duration_hours"],
                }
            ],
            "coverage_notes": ["sleep/sleep_duration_hours: coverage low"],
        }

        client.generate_schedule_proposals(
            journal_narrative="normal day",
            behavioral_prose="behavioral prose",
            risk_level="mild",
            calendar_summary=self._base_calendar(),
            research_context=[],
            behavioral_state=behavioral_state,
        )

        prompt = mock.models.generate_content.call_args.kwargs.get("contents", "")
        assert "Sleep has averaged 5.2h versus a typical 7.6h." in prompt
        assert "trajectory=sustained-4d" in prompt
        assert "coverage=medium" in prompt
        assert "Attention is more fragmented while sleep is shorter." in prompt
        assert "signals: app_switching_rate, sleep_duration_hours" in prompt
        assert "0.20/active-min" not in prompt

    def test_raw_sensor_section_uses_active_min_units(self):
        client, mock = _make_client()
        _set_generate_response(mock, json.dumps({
            "risk_level": "minimal", "summary": "", "concerns": [], "positives": [],
            "recommendations": [], "proposed_changes": [],
        }))
        client.generate_schedule_proposals(
            journal_narrative="normal day",
            behavioral_prose="behavioral prose",
            risk_level="minimal",
            calendar_summary=self._base_calendar(),
            research_context=[],
            raw_days=[{
                "date": "2026-04-24",
                "app_switching_rate": 0.2,
            }],
        )
        prompt = mock.models.generate_content.call_args.kwargs.get("contents", "")
        assert "0.20/active-min" in prompt
        assert "/hr" not in prompt

    def test_prompt_requests_ui_summary_contract(self):
        client, mock = _make_client()
        _set_generate_response(mock, json.dumps({
            "risk_level": "minimal", "summary": "", "concerns": [], "positives": [],
            "ui_summary": {},
            "recommendations": [], "proposed_changes": [],
        }))
        client.generate_schedule_proposals(
            journal_narrative="normal day",
            behavioral_prose=None,
            risk_level="minimal",
            calendar_summary=self._base_calendar(),
            research_context=[],
        )
        prompt = mock.models.generate_content.call_args.kwargs.get("contents", "")
        assert '"ui_summary"' in prompt
        assert "evidence_chips" in prompt
        assert "protective_signals" in prompt

    def test_none_behavioral_prose_signals_no_sensor_data(self):
        client, mock = _make_client()
        _set_generate_response(mock, json.dumps({
            "risk_level": "minimal", "summary": "", "concerns": [], "positives": [],
            "recommendations": [], "proposed_changes": [],
        }))
        client.generate_schedule_proposals(
            journal_narrative="normal day",
            behavioral_prose=None,
            risk_level="minimal",
            calendar_summary=self._base_calendar(),
            research_context=[],
        )
        prompt = mock.models.generate_content.call_args.kwargs.get("contents", "")
        assert "No sensor data available" in prompt

    def test_user_preferences_in_prompt(self):
        client, mock = _make_client()
        _set_generate_response(mock, json.dumps({
            "risk_level": "minimal", "summary": "", "concerns": [], "positives": [],
            "recommendations": [], "proposed_changes": [],
        }))
        client.generate_schedule_proposals(
            journal_narrative="",
            behavioral_prose=None,
            risk_level="minimal",
            calendar_summary=self._base_calendar(),
            research_context=[],
            user_preferences=["No yoga", "Prefer running"],
        )
        prompt = mock.models.generate_content.call_args.kwargs.get("contents", "")
        assert "No yoga" in prompt
        assert "Prefer running" in prompt

    def test_returns_fallback_on_invalid_json(self):
        client, mock = _make_client()
        _set_generate_response(mock, "not json at all")

        result = client.generate_schedule_proposals(
            journal_narrative="day",
            behavioral_prose=None,
            risk_level="mild",
            calendar_summary=self._base_calendar(),
            research_context=[],
        )
        assert result["risk_level"] == "mild"
        assert isinstance(result["recommendations"], list)
        assert isinstance(result["proposed_changes"], list)

    def test_strips_markdown_fencing(self):
        client, mock = _make_client()
        payload = {
            "risk_level": "minimal", "summary": "ok", "concerns": [], "positives": [],
            "recommendations": [], "proposed_changes": [],
        }
        _set_generate_response(mock, f"```json\n{json.dumps(payload)}\n```")

        result = client.generate_schedule_proposals(
            journal_narrative="day",
            behavioral_prose=None,
            risk_level="minimal",
            calendar_summary=self._base_calendar(),
            research_context=[],
        )
        assert result["risk_level"] == "minimal"


# generate_recommendations

class TestGenerateRecommendations:

    def test_happy_path(self):
        client, mock = _make_client()
        payload = {
            "recommendations": [
                {
                    "category": "Sleep",
                    "action": "Go to bed earlier",
                    "when": "10 PM",
                    "source": "Sleep Study",
                },
            ]
        }
        _set_generate_response(mock, json.dumps(payload))

        recs = client.generate_recommendations(
            journal_summary="stressed",
            risk_level="moderate",
            concerns=["poor sleep"],
            research_context=[],
        )
        assert len(recs) == 1
        assert recs[0]["category"] == "Sleep"

    def test_includes_research_context_in_prompt(self):
        client, mock = _make_client()
        _set_generate_response(mock, json.dumps({"recommendations": []}))

        research = [
            {"category": "Stress Management", "content": "Deep breathing helps", "source": "Paper A"}
        ]
        client.generate_recommendations("summary", "mild", [], research)

        call_args = mock.models.generate_content.call_args
        # generate_content is called with keyword args: model=..., contents=prompt, config=...
        prompt = call_args.kwargs.get("contents", "")
        assert "Deep breathing" in prompt

    def test_fallback_on_bad_json(self):
        client, mock = _make_client()
        _set_generate_response(mock, "not json")

        recs = client.generate_recommendations("summary", "mild", [], [])
        assert len(recs) == 1
        assert recs[0]["category"] == "General"



# generate_calendar_changes

class TestGenerateCalendarChanges:

    def test_happy_path(self):
        client, mock = _make_client()
        payload = {
            "proposed_changes": [
                {
                    "action": "add",
                    "title": "Walk",
                    "description": "30 min walk",
                    "start_time": "2024-06-01T08:00:00",
                    "end_time": "2024-06-01T08:30:00",
                    "category": "Physical",
                    "reason": "helps stress",
                }
            ]
        }
        _set_generate_response(mock, json.dumps(payload))

        changes = client.generate_calendar_changes(
            recommendations=[{"category": "Physical", "action": "walk", "when": "morning"}],
            calendar_summary={"events": [], "tasks": []},
            mental_health={"risk_level": "moderate", "key_concerns": []},
        )
        assert len(changes) == 1
        assert changes[0]["title"] == "Walk"

    def test_returns_empty_on_parse_error(self):
        client, mock = _make_client()
        _set_generate_response(mock, "completely invalid")

        changes = client.generate_calendar_changes(
            recommendations=[],
            calendar_summary={"events": [], "tasks": []},
            mental_health={},
        )
        assert changes == []

    def test_user_preferences_included_in_prompt(self):
        client, mock = _make_client()
        _set_generate_response(mock, json.dumps({"proposed_changes": []}))

        client.generate_calendar_changes(
            recommendations=[],
            calendar_summary={"events": [], "tasks": []},
            mental_health={"risk_level": "mild", "key_concerns": []},
            user_preferences=["No yoga", "Prefer running"],
        )

        call_args = mock.models.generate_content.call_args
        prompt = call_args.kwargs.get("contents", "")
        assert "No yoga" in prompt
        assert "Prefer running" in prompt



# parse_user_feedback

class TestParseUserFeedback:

    def test_happy_path(self):
        client, mock = _make_client()
        payload = {
            "preference": "User prefers running over yoga",
            "dislikes": ["yoga"],
            "prefers": ["running"],
            "should_save": True,
        }
        _set_generate_response(mock, json.dumps(payload))

        result = client.parse_user_feedback("I hate yoga, I like running")
        assert result["should_save"] is True
        assert "yoga" in result["dislikes"]

    def test_fallback_on_bad_json(self):
        client, mock = _make_client()
        _set_generate_response(mock, "gibberish")

        result = client.parse_user_feedback("some feedback")
        assert result["preference"] == "some feedback"
        assert result["should_save"] is True



# generate (low-level)

class TestGenerate:

    def test_returns_empty_string_when_client_is_none(self):
        from tools.llm_client import LLMClient
        client = LLMClient.__new__(LLMClient)
        client.client = None
        assert client.generate("hello") == ""

    def test_returns_empty_string_on_exception(self):
        client, mock = _make_client()
        mock.models.generate_content.side_effect = RuntimeError("boom")
        assert client.generate("hello") == ""
