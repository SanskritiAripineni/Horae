"""
Tests for tools/llm_client.py — Gemini API wrapper.

All Gemini API calls are mocked. Tests cover:
- JSON parsing from model responses (with and without markdown fencing)
- Fallback behaviour when API key is missing or client is None
- analyze_mental_health(), generate_recommendations(), generate_calendar_changes()
- parse_user_feedback()
"""

import json
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# analyze_mental_health
# ---------------------------------------------------------------------------

class TestAnalyzeMentalHealth:

    def test_parses_clean_json(self):
        client, mock = _make_client()
        payload = {
            "summary": "User is stressed",
            "phq4_estimate": 7,
            "risk_level": "moderate",
            "concerns": ["poor sleep"],
            "positives": ["exercise"],
        }
        _set_generate_response(mock, json.dumps(payload))

        result = client.analyze_mental_health("Some journal text")

        assert result["phq4_estimate"] == 7
        assert result["risk_level"] == "moderate"
        assert "poor sleep" in result["concerns"]

    def test_strips_markdown_fencing(self):
        client, mock = _make_client()
        payload = {
            "summary": "ok",
            "phq4_estimate": 2,
            "risk_level": "minimal",
            "concerns": [],
            "positives": ["active"],
        }
        fenced = f"```json\n{json.dumps(payload)}\n```"
        _set_generate_response(mock, fenced)

        result = client.analyze_mental_health("journal text")
        assert result["phq4_estimate"] == 2

    def test_returns_fallback_on_invalid_json(self):
        client, mock = _make_client()
        _set_generate_response(mock, "This is not JSON at all")

        result = client.analyze_mental_health("journal text")
        assert result["phq4_estimate"] == 3
        assert result["risk_level"] == "mild"
        assert result["summary"] == "Unable to analyze journals"

    def test_returns_fallback_when_client_is_none(self):
        """When no API key is set the client attribute is None."""
        from tools.llm_client import LLMClient
        with patch.dict("os.environ", {}, clear=False):
            with patch("tools.llm_client.GENAI_AVAILABLE", True):
                client = LLMClient.__new__(LLMClient)
                client.api_key = None
                client.model_name = "test"
                client.client = None

        result = client.analyze_mental_health("journal")
        assert result["phq4_estimate"] == 3
        assert result["risk_level"] == "mild"

    def test_returns_fallback_on_api_exception(self):
        client, mock = _make_client()
        mock.models.generate_content.side_effect = Exception("API quota exceeded")

        result = client.analyze_mental_health("journal text")
        assert result["phq4_estimate"] == 3


# ---------------------------------------------------------------------------
# generate_recommendations
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# generate_calendar_changes
# ---------------------------------------------------------------------------

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
            mental_health={"risk_level": "moderate", "estimated_phq4": 6, "key_concerns": []},
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
            mental_health={"risk_level": "mild", "estimated_phq4": 3, "key_concerns": []},
            user_preferences=["No yoga", "Prefer running"],
        )

        call_args = mock.models.generate_content.call_args
        prompt = call_args.kwargs.get("contents", "")
        assert "No yoga" in prompt
        assert "Prefer running" in prompt


# ---------------------------------------------------------------------------
# parse_user_feedback
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# generate (low-level)
# ---------------------------------------------------------------------------

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
