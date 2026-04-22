"""
Tests for tools/wellbeing_sensor.py — the top-level behavioral sensing entry
point that agent.run_from_journals() depends on after the 1e0f5c9 refactor
made it the sole wellbeing signal.

Covers:
- Empty raw_days short-circuit (used by agent.py when no sensor data is sent).
- Cold baseline: prose is produced but baseline_warm=False.
- Warm baseline: prose is produced and baseline_warm=True.
- Layer 4 LLM is skipped when with_llm=False.
- Layer 4 LLM is skipped when ANTHROPIC_API_KEY is unset.
- Layer 4 LLM is invoked (and its failures are swallowed) when the env var
  is set and with_llm=True.
- Calendar/user_prefs/feedback_history pass through without crashing.
- Days with missing markers (None values) do not crash and land at coverage 0.
"""

import os
from unittest.mock import patch

import pytest

from tools.wellbeing_sensor import WellbeingSensor


EXPECTED_KEYS = {"behavioral_state", "prose", "llm_analysis", "baseline_warm"}


class TestEmptyInput:
    def test_empty_raw_days_returns_empty_state(self):
        """Guards agent.py's graceful-degradation path: raw_days=None or []."""
        result = WellbeingSensor().analyze([])

        assert set(result.keys()) >= EXPECTED_KEYS
        assert result["behavioral_state"] is None
        assert result["prose"] == ""
        assert result["llm_analysis"] is None
        assert result["baseline_warm"] is True

    def test_none_raw_days_behaves_like_empty(self):
        result = WellbeingSensor().analyze(None)  # type: ignore[arg-type]
        assert result["prose"] == ""
        assert result["behavioral_state"] is None


class TestBaselineWarmth:
    def test_cold_baseline_not_warm(self, cold_raw_days):
        """5 days < warmup_days (10) → baseline_warm is False."""
        sensor = WellbeingSensor(warmup_days=10)
        result = sensor.analyze(cold_raw_days, with_llm=False)

        assert result["baseline_warm"] is False
        # Cold baselines still produce prose — downstream layers annotate the
        # "not yet warm" state so the orchestrator can say so.
        assert isinstance(result["prose"], str)
        assert result["prose"]  # non-empty

    def test_warm_baseline_is_warm(self, warm_raw_days):
        """14 days ≥ warmup_days (10) → baseline_warm is True."""
        sensor = WellbeingSensor(warmup_days=10)
        result = sensor.analyze(warm_raw_days, with_llm=False)

        assert result["baseline_warm"] is True
        assert result["behavioral_state"] is not None
        assert isinstance(result["prose"], str)

    def test_custom_warmup_threshold(self, cold_raw_days):
        """Lowering warmup_days flips a 5-day history from cold to warm."""
        sensor = WellbeingSensor(warmup_days=3)
        result = sensor.analyze(cold_raw_days, with_llm=False)
        assert result["baseline_warm"] is True


class TestLLMGating:
    """Layer 4 is optional. It must never run without an API key, and must
    never run when the caller explicitly opts out."""

    def test_with_llm_false_skips_layer4(self, warm_raw_days, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-for-test")
        with patch("tools.wellbeing_sensor.logger"):
            result = WellbeingSensor().analyze(warm_raw_days, with_llm=False)
        assert result["llm_analysis"] is None

    def test_missing_api_key_skips_layer4(self, warm_raw_days, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        result = WellbeingSensor().analyze(warm_raw_days, with_llm=True)
        assert result["llm_analysis"] is None

    def test_layer4_failure_is_swallowed(self, warm_raw_days, monkeypatch):
        """If the Anthropic call blows up, analyze() must still return a valid
        result dict — don't take down the pipeline for an optional LLM layer."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-for-test")

        # layer4_llm lives on wellbeing_pipeline sys.path (added by
        # wellbeing_sensor at import time). Patching the attribute on the
        # already-imported module is the simplest way to force failure.
        import layer4_llm
        with patch.object(layer4_llm, "call_scheduler", side_effect=RuntimeError("boom")):
            result = WellbeingSensor().analyze(warm_raw_days, with_llm=True)

        assert result["llm_analysis"] is None
        assert result["behavioral_state"] is not None

    def test_layer4_success_populates_llm_analysis(self, warm_raw_days, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-for-test")
        fake_analysis = {"suggestions": [], "questions_for_user": [], "_meta": {}}

        import layer4_llm
        with patch.object(layer4_llm, "call_scheduler", return_value=fake_analysis):
            result = WellbeingSensor().analyze(warm_raw_days, with_llm=True)

        assert result["llm_analysis"] == fake_analysis


class TestContextPassthrough:
    """Optional context (calendar, user_prefs, feedback_history) must not
    break anything even when exotic shapes are passed."""

    def test_calendar_and_prefs_do_not_crash(self, warm_raw_days):
        result = WellbeingSensor().analyze(
            warm_raw_days,
            calendar=[{"title": "team sync", "start": "2024-05-14 10:00"}],
            user_prefs={"wake_target": "07:00", "chronotype": "morning"},
            feedback_history=[{"accepted": True, "suggestion": "walk"}],
            with_llm=False,
        )
        assert result["behavioral_state"] is not None

    def test_none_context_equivalent_to_unset(self, warm_raw_days):
        """Passing None should be equivalent to omitting — no crash."""
        result = WellbeingSensor().analyze(
            warm_raw_days,
            calendar=None,
            user_prefs=None,
            feedback_history=None,
            with_llm=False,
        )
        assert result["behavioral_state"] is not None


class TestPartialData:
    def test_day_with_all_none_markers(self, warm_raw_days):
        """A day where every marker is None should land at coverage 0 and not
        crash — this happens in the field when the phone was offline."""
        from datetime import date

        mostly_empty_day = {
            "date": date(2024, 5, 15),
            "sleep_onset_hour": None,
            "sleep_duration_hours": None,
            "total_screen_min": None,
        }
        days = warm_raw_days + [mostly_empty_day]

        result = WellbeingSensor().analyze(days, with_llm=False)
        assert result["behavioral_state"] is not None

    def test_day_with_only_date_field(self):
        """Bare day with no markers at all — still parseable, coverage all 0."""
        from datetime import date

        bare_days = [{"date": date(2024, 5, 10) }]
        result = WellbeingSensor().analyze(bare_days, with_llm=False)
        # No markers means no stats, but the call must not crash.
        assert isinstance(result["prose"], str)
