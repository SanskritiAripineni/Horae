"""
Tests for memory module — MemoryStorage, WellbeingTracker, UserPreferencesManager.

Uses temporary directories for all file I/O. Tests cover:
- MemoryStorage save/load round-trips
- WellbeingTracker add_assessment, get_latest, get_history, get_trend
- UserPreferencesManager get/save round-trip, defaults
- MemoryModule.get_user_context() integration
"""

import json
import pytest
from pathlib import Path

from memory.storage import MemoryStorage
from memory.wellbeing_tracker import WellbeingTracker, WellbeingAssessment, TrendAnalysis
from memory.user_preferences import UserPreferencesManager, UserPreferences
from memory import MemoryModule



# MemoryStorage

class TestMemoryStorage:

    def test_load_user_memory_returns_default_shape_for_new_user(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        loaded = storage.load_user_memory("u1")
        assert loaded["user_id"] == "u1"
        assert loaded["preferences"] == {}
        assert loaded["wellbeing"]["history"] == []
        assert loaded["feedback"]["comments"] == []

    def test_save_and_load_user_memory_round_trip(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        data = {
            "user_id": "u1",
            "preferences": {"explicit_preferences": ["Avoid meditation"]},
            "wellbeing": {"history": [{"risk_level": "mild"}]},
            "feedback": {"comments": [{"raw_feedback": "Prefer walking"}]},
        }
        assert storage.save_user_memory("u1", data) is True
        loaded = storage.load_user_memory("u1")
        assert loaded["preferences"]["explicit_preferences"] == ["Avoid meditation"]
        assert loaded["wellbeing"]["history"][0]["risk_level"] == "mild"
        assert loaded["feedback"]["comments"][0]["raw_feedback"] == "Prefer walking"

    def test_save_creates_users_directory(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        storage.save_user_memory("u1", {"user_id": "u1"})
        assert (tmp_path / "users").is_dir()

    def test_update_user_memory_overwrites_existing_data(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        storage.save_user_memory("u1", {"user_id": "u1", "preferences": {"foo": "bar"}})
        storage.update_user_memory("u1", lambda memory: {**memory, "preferences": {"foo": "baz"}})
        loaded = storage.load_user_memory("u1")
        assert loaded["preferences"]["foo"] == "baz"

    def test_saves_user_file_as_plain_json_document(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        storage.save_user_memory("u1", {"user_id": "u1", "preferences": {"a": 1}})
        file_path = tmp_path / "users" / "u1.json"
        with open(file_path) as f:
            raw = json.load(f)
        assert raw["user_id"] == "u1"
        assert raw["preferences"]["a"] == 1

    def test_creates_data_dir_if_missing(self, tmp_path):
        new_dir = tmp_path / "deep" / "nested"
        storage = MemoryStorage(data_dir=str(new_dir))
        assert new_dir.exists()



# WellbeingTracker

class TestWellbeingTracker:

    def test_add_and_get_latest(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        tracker = WellbeingTracker(storage)

        tracker.add_assessment(WellbeingAssessment(risk_level="mild", user_id="u1"))
        tracker.add_assessment(WellbeingAssessment(risk_level="moderate", user_id="u1"))

        latest = tracker.get_latest("u1")
        assert latest is not None
        assert latest.risk_level == "moderate"

    def test_get_latest_returns_none_for_new_user(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        tracker = WellbeingTracker(storage)
        assert tracker.get_latest("nobody") is None

    def test_get_history(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        tracker = WellbeingTracker(storage)

        tracker.add_assessment(WellbeingAssessment(risk_level="minimal", user_id="u1"))
        tracker.add_assessment(WellbeingAssessment(risk_level="mild", user_id="u1"))

        history = tracker.get_history("u1")
        assert len(history) == 2
        assert history[0]["risk_level"] == "minimal"
        assert history[1]["risk_level"] == "mild"

    def test_get_history_returns_empty_for_unknown_user(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        tracker = WellbeingTracker(storage)
        assert tracker.get_history("ghost") == []

    def test_get_trend_returns_insufficient_data_for_new_user(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        tracker = WellbeingTracker(storage)
        trend = tracker.get_trend("u1")
        assert isinstance(trend, TrendAnalysis)
        assert trend.direction == "insufficient_data"

    def test_get_trend_returns_stable_with_enough_data(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        tracker = WellbeingTracker(storage)
        for _ in range(6):
            tracker.add_assessment(WellbeingAssessment(risk_level="mild", user_id="u1"))
        trend = tracker.get_trend("u1")
        assert trend.direction == "stable"

    def test_get_trend_detects_rising(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        tracker = WellbeingTracker(storage)
        for level in ["minimal", "minimal", "minimal", "moderate", "moderate", "moderate"]:
            tracker.add_assessment(WellbeingAssessment(risk_level=level, user_id="u1"))
        trend = tracker.get_trend("u1")
        assert trend.direction == "rising"

    def test_get_trend_detects_falling(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        tracker = WellbeingTracker(storage)
        for level in ["severe", "severe", "severe", "mild", "mild", "mild"]:
            tracker.add_assessment(WellbeingAssessment(risk_level=level, user_id="u1"))
        trend = tracker.get_trend("u1")
        assert trend.direction == "falling"

    def test_assessment_defaults(self):
        a = WellbeingAssessment(risk_level="mild")
        assert a.user_id == "default"
        assert a.timestamp  # default timestamp



# UserPreferencesManager

class TestUserPreferencesManager:

    def test_returns_defaults_for_new_user(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        mgr = UserPreferencesManager(storage)

        prefs = mgr.get_preferences("new_user")
        assert prefs.user_id == "new_user"
        assert "maintain work-life balance" in prefs.goals
        assert prefs.max_daily_hours == 8.0

    def test_save_and_load_round_trip(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        mgr = UserPreferencesManager(storage)

        prefs = UserPreferences(
            user_id="u1",
            goals=["exercise daily"],
            work_hours=(8, 16),
            preferred_interventions=["running"],
            max_daily_hours=6.0,
        )
        mgr.save_preferences(prefs)

        loaded = mgr.get_preferences("u1")
        assert loaded.goals == ["exercise daily"]
        assert loaded.max_daily_hours == 6.0
        assert loaded.preferred_interventions == ["running"]

    def test_to_dict(self):
        prefs = UserPreferences(user_id="u1")
        d = prefs.to_dict()
        assert d["user_id"] == "u1"
        assert "goals" in d
        assert "work_hours" in d

    def test_merge_feedback_updates_explicit_preferences(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        mgr = UserPreferencesManager(storage)

        mgr.merge_feedback(
            user_id="u1",
            preference="User prefers walking to meditation",
            dislikes=["meditation"],
            prefers=["walking"],
        )

        loaded = mgr.get_preferences("u1")
        assert "User prefers walking to meditation" in loaded.explicit_preferences
        assert "meditation" in loaded.disliked_activities
        assert "walking" in loaded.preferred_activities
        assert "walking" in loaded.preferred_interventions

    def test_get_prompt_preferences_returns_only_explicit_signals(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        mgr = UserPreferencesManager(storage)

        mgr.merge_feedback(
            user_id="u1",
            preference="No meditation suggestions",
            dislikes=["meditation"],
            prefers=["walking"],
        )

        prompt_prefs = mgr.get_prompt_preferences("u1")
        assert "No meditation suggestions" in prompt_prefs
        assert "Avoid: meditation" in prompt_prefs
        assert "Prefer: walking" in prompt_prefs



# MemoryModule (integration)

class TestMemoryModule:

    def test_get_user_context_for_new_user(self, tmp_path):
        module = MemoryModule(data_dir=str(tmp_path))
        ctx = module.get_user_context("brand_new")

        assert ctx["user_id"] == "brand_new"
        assert isinstance(ctx["preferences"], dict)
        assert ctx["wellbeing"]["risk_level"] == "unknown"
        assert ctx["wellbeing"]["trend"] == "insufficient_data"
        assert ctx["feedback"]["comments"] == []

    def test_get_user_context_with_data(self, tmp_path):
        module = MemoryModule(data_dir=str(tmp_path))

        module.wellbeing_tracker.add_assessment(
            WellbeingAssessment(risk_level="mild", user_id="u1")
        )

        ctx = module.get_user_context("u1")
        assert ctx["wellbeing"]["risk_level"] == "mild"

    def test_record_wellbeing_assessment_persists_history(self, tmp_path):
        module = MemoryModule(data_dir=str(tmp_path))

        module.record_wellbeing_assessment("u1", "moderate")

        history = module.wellbeing_tracker.get_history("u1")
        assert len(history) == 1
        assert history[0]["risk_level"] == "moderate"

    def test_record_feedback_updates_preferences_and_feedback_store(self, tmp_path):
        module = MemoryModule(data_dir=str(tmp_path))

        module.record_feedback(
            "u1",
            raw_feedback="I do not want meditation. Suggest walking instead.",
            parsed_feedback={
                "preference": "Avoid meditation and prefer walking",
                "dislikes": ["meditation"],
                "prefers": ["walking"],
                "should_save": True,
            },
        )

        prefs = module.preferences.get_preferences("u1")
        user_memory = module.storage.load_user_memory("u1")

        assert "Avoid meditation and prefer walking" in prefs.explicit_preferences
        assert "meditation" in prefs.disliked_activities
        assert "walking" in prefs.preferred_activities
        assert len(user_memory["feedback"]["comments"]) == 1
