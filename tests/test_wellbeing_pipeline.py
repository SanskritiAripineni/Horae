"""
Tests for wellbeing_pipeline/ — Layer 1 (baseline), Layer 2 (deviations /
coherent patterns), Layer 3 (state description).

Layer 4 (Anthropic call) is covered indirectly in test_wellbeing_sensor.py
via the gating tests; it is not unit-tested here because it only wraps an
external API.

We import WellbeingSensor first so it prepends wellbeing_pipeline/ to
sys.path (side-effect at import time), then import the individual layers
directly.
"""

from datetime import date, timedelta

import pytest

# Import for side-effect: adds wellbeing_pipeline/ to sys.path.
from tools.wellbeing_sensor import WellbeingSensor  # noqa: F401

from layer1 import PersonalBaseline, DayRecord, markers_from_raw
from layer2 import detect_deviations, find_coherent_patterns
from layer3 import build_state_description, render_llm_input


# ---------- Layer 1 ----------

class TestMarkersFromRaw:
    def test_all_markers_present(self):
        raw = {
            "date": date(2024, 5, 10),
            "sleep_duration_hours": 7.5,
            "mobility_entropy": 2.3,
        }
        rec = markers_from_raw(raw)

        assert rec.day == date(2024, 5, 10)
        assert rec.markers["sleep_duration_hours"] == 7.5
        assert rec.markers["mobility_entropy"] == 2.3
        assert rec.coverage["sleep_duration_hours"] == 1.0
        # Unmentioned markers land at coverage 0.
        assert rec.coverage["sleep_onset_hour"] == 0.0
        assert "sleep_onset_hour" not in rec.markers

    def test_api_date_string_is_coerced_to_date(self):
        raw = {
            "date": "2024-05-10",
            "sleep_duration_hours": 7.5,
        }
        rec = markers_from_raw(raw)

        assert rec.day == date(2024, 5, 10)

    def test_coverage_override(self):
        raw = {
            "date": date(2024, 5, 10),
            "sleep_duration_hours": 7.5,
            "_coverage": {"sleep_duration_hours": 0.4},
        }
        rec = markers_from_raw(raw)
        assert rec.coverage["sleep_duration_hours"] == 0.4

    def test_none_values_treated_as_missing(self):
        raw = {
            "date": date(2024, 5, 10),
            "sleep_duration_hours": None,
        }
        rec = markers_from_raw(raw)
        assert "sleep_duration_hours" not in rec.markers
        assert rec.coverage["sleep_duration_hours"] == 0.0


class TestPersonalBaseline:
    def _populated(self, days=15, markers_overrides=None):
        b = PersonalBaseline(warmup_days=10)
        start = date(2024, 5, 1)
        for i in range(days):
            raw = {
                "date": start + timedelta(days=i),
                "sleep_duration_hours": 7.5,
                "sleep_onset_hour": 23.0,
                "total_screen_min": 240.0,
            }
            if markers_overrides and i in markers_overrides:
                raw.update(markers_overrides[i])
            b.add(markers_from_raw(raw))
        return b

    def test_is_warm_threshold(self):
        assert PersonalBaseline(warmup_days=10).is_warm() is False
        b = self._populated(days=9)
        assert b.is_warm() is False
        b = self._populated(days=10)
        assert b.is_warm() is True

    def test_add_keeps_history_sorted(self):
        """PersonalBaseline.add() must sort history even if records arrive
        out of order — Layer 2 windowing relies on chronological order."""
        b = PersonalBaseline()
        b.add(markers_from_raw({"date": date(2024, 5, 3), "sleep_duration_hours": 7.0}))
        b.add(markers_from_raw({"date": date(2024, 5, 1), "sleep_duration_hours": 7.0}))
        b.add(markers_from_raw({"date": date(2024, 5, 2), "sleep_duration_hours": 7.0}))
        days = [r.day for r in b.history]
        assert days == sorted(days)

    def test_stats_requires_min_three_points(self):
        b = self._populated(days=2)
        assert b.stats("sleep_duration_hours") is None

    def test_stats_shape(self):
        b = self._populated(days=10)
        s = b.stats("sleep_duration_hours", days_back=10)
        assert s is not None
        assert set(s.keys()) == {"n", "mean", "std", "median", "p20", "p80", "min", "max"}
        assert s["n"] == 10
        assert s["mean"] == pytest.approx(7.5)

    def test_stats_uses_robust_std_floor_for_flat_history(self):
        b = PersonalBaseline(warmup_days=10)
        start = date(2024, 5, 1)
        for i in range(10):
            b.add(markers_from_raw({
                "date": start + timedelta(days=i),
                "sleep_duration_hours": 7.5,
            }))
        s = b.stats("sleep_duration_hours", days_back=10)
        assert s is not None
        assert s["std"] == pytest.approx(0.4)

    def test_stats_returns_none_for_absent_marker(self):
        b = self._populated(days=10)
        # mobility_entropy was never populated above.
        assert b.stats("mobility_entropy") is None

    def test_coverage_quality_buckets(self):
        b = self._populated(days=7)
        # sleep_duration_hours is present every day at coverage 1.0.
        assert b.coverage_quality("sleep_duration_hours") == "high"
        # mobility_entropy never present → coverage 0.
        assert b.coverage_quality("mobility_entropy") == "none"

    def test_window_respects_range(self):
        b = self._populated(days=20)
        w = b.window(days_back=5)
        assert len(w) == 5
        last_day = b.history[-1].day
        assert all(last_day - timedelta(days=5) < r.day <= last_day for r in w)


# ---------- Layer 2 ----------

class TestDetectDeviations:
    def test_no_deviations_on_stable_history(self, warm_raw_days):
        b = PersonalBaseline(warmup_days=10)
        for raw in warm_raw_days:
            b.add(markers_from_raw(raw))
        as_of = b.history[-1].day
        devs = detect_deviations(b, as_of=as_of)
        # Stable markers ± jitter should not produce anything above "mild".
        assert all(d.magnitude != "pronounced" for d in devs)

    def test_pronounced_sleep_drop_detected(self, deviation_raw_days):
        """30 stable days + 4 days of 4h sleep should surface a sleep deviation."""
        b = PersonalBaseline(warmup_days=10)
        for raw in deviation_raw_days:
            b.add(markers_from_raw(raw))
        as_of = b.history[-1].day

        devs = detect_deviations(b, as_of=as_of, recent_days=4, baseline_days=28)
        sleep_devs = [d for d in devs if d.marker == "sleep_duration_hours"]

        assert sleep_devs, "expected a sleep_duration_hours deviation"
        d = sleep_devs[0]
        assert d.direction == "down"
        assert d.magnitude in {"moderate", "pronounced"}
        # Trajectory should flag all 4 days elevated in the same direction.
        assert "sustained" in d.trajectory or "drift" in d.trajectory

    def test_min_magnitude_filter(self, deviation_raw_days):
        b = PersonalBaseline(warmup_days=10)
        for raw in deviation_raw_days:
            b.add(markers_from_raw(raw))
        as_of = b.history[-1].day

        pronounced_only = detect_deviations(
            b, as_of=as_of, recent_days=4, baseline_days=28, min_magnitude="pronounced"
        )
        any_magnitude = detect_deviations(
            b, as_of=as_of, recent_days=4, baseline_days=28, min_magnitude="mild"
        )
        assert len(pronounced_only) <= len(any_magnitude)

    def test_flat_history_does_not_create_false_pronounced_screen_deviation(self):
        b = PersonalBaseline(warmup_days=10)
        start = date(2024, 5, 1)
        for i in range(30):
            b.add(markers_from_raw({
                "date": start + timedelta(days=i),
                "total_screen_min": 240.0,
            }))
        for i in range(30, 34):
            b.add(markers_from_raw({
                "date": start + timedelta(days=i),
                "total_screen_min": 245.0,
            }))

        devs = detect_deviations(b, as_of=b.history[-1].day, recent_days=4, baseline_days=28)
        screen_devs = [d for d in devs if d.marker == "total_screen_min"]
        assert screen_devs == []


class TestCoherentPatterns:
    def test_empty_deviations_returns_empty(self):
        assert find_coherent_patterns([]) == []

    def test_runs_on_real_deviations(self, deviation_raw_days):
        """Smoke: find_coherent_patterns must not crash on real Layer 2 output."""
        b = PersonalBaseline(warmup_days=10)
        for raw in deviation_raw_days:
            b.add(markers_from_raw(raw))
        devs = detect_deviations(b, as_of=b.history[-1].day)
        patterns = find_coherent_patterns(devs)
        assert isinstance(patterns, list)


# ---------- Layer 3 ----------

class TestBuildStateDescription:
    def test_cold_baseline_prose_mentions_warmup(self, cold_raw_days):
        b = PersonalBaseline(warmup_days=10)
        for raw in cold_raw_days:
            b.add(markers_from_raw(raw))
        state = build_state_description(b, deviations=[], patterns=[], as_of=b.history[-1].day)

        assert state["structured"]["baseline_state"]["warm"] is False
        assert "baseline-learning" in state["prose"].lower() or "learning window" in state["prose"].lower()

    def test_warm_no_deviations_says_typical(self, warm_raw_days):
        b = PersonalBaseline(warmup_days=10)
        for raw in warm_raw_days:
            b.add(markers_from_raw(raw))
        state = build_state_description(b, deviations=[], patterns=[], as_of=b.history[-1].day)

        assert state["structured"]["baseline_state"]["warm"] is True
        assert state["structured"]["deviations"] == []
        assert "typical" in state["prose"].lower() or "stands out" in state["prose"].lower()

    def test_warm_with_deviations_produces_structured_findings(self, deviation_raw_days):
        b = PersonalBaseline(warmup_days=10)
        for raw in deviation_raw_days:
            b.add(markers_from_raw(raw))
        devs = detect_deviations(b, as_of=b.history[-1].day, recent_days=4, baseline_days=28)
        patterns = find_coherent_patterns(devs)

        state = build_state_description(b, deviations=devs, patterns=patterns, as_of=b.history[-1].day)

        assert state["structured"]["baseline_state"]["warm"] is True
        assert len(state["structured"]["deviations"]) == len(devs)
        assert isinstance(state["prose"], str) and state["prose"]
        assert "as_of" in state["structured"]

    def test_low_coverage_generates_caveats_and_low_confidence(self):
        b = PersonalBaseline(warmup_days=7)
        start = date(2024, 5, 1)
        for i in range(7):
            b.add(markers_from_raw({
                "date": start + timedelta(days=i),
                "sleep_duration_hours": 7.0 + (0.1 if i >= 4 else 0.0),
                "_coverage": {"sleep_duration_hours": 0.2},
            }))
        devs = detect_deviations(b, as_of=b.history[-1].day, recent_days=4, baseline_days=3)
        state = build_state_description(b, deviations=devs, patterns=[], as_of=b.history[-1].day)

        assert state["structured"]["baseline_state"]["overall_confidence"] == "low"
        notes = state["structured"]["coverage_notes"]
        assert any("sleep/sleep_duration_hours: coverage low" in note for note in notes)


class TestRenderLLMInput:
    def test_shape_includes_state(self, warm_raw_days):
        b = PersonalBaseline(warmup_days=10)
        for raw in warm_raw_days:
            b.add(markers_from_raw(raw))
        state = build_state_description(b, [], [], b.history[-1].day)
        rendered = render_llm_input(state, calendar=[{"title": "foo"}], user_prefs={"x": 1})
        assert isinstance(rendered, dict)
