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

    def test_save_and_load_round_trip(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        data = {"name": "Alice", "score": 42}
        assert storage.save("test_category", "key1", data) is True
        loaded = storage.load("test_category", "key1")
        assert loaded == data

    def test_load_returns_none_for_missing_key(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        assert storage.load("nonexistent", "nope") is None

    def test_save_creates_category_directory(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        storage.save("new_category", "k", {"hello": "world"})
        assert (tmp_path / "new_category").is_dir()

    def test_overwrites_existing_data(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        storage.save("cat", "key", {"v": 1})
        storage.save("cat", "key", {"v": 2})
        loaded = storage.load("cat", "key")
        assert loaded["v"] == 2

    def test_saves_various_types(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))

        storage.save("cat", "list_key", [1, 2, 3])
        assert storage.load("cat", "list_key") == [1, 2, 3]

        storage.save("cat", "str_key", "hello")
        assert storage.load("cat", "str_key") == "hello"

        nested = {"a": {"b": {"c": 1}}}
        storage.save("cat", "nested_key", nested)
        assert storage.load("cat", "nested_key") == nested

    def test_creates_data_dir_if_missing(self, tmp_path):
        new_dir = tmp_path / "deep" / "nested"
        storage = MemoryStorage(data_dir=str(new_dir))
        assert new_dir.exists()

    def test_file_format_is_json_with_data_wrapper(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        storage.save("cat", "key", {"val": 99})
        file_path = tmp_path / "cat" / "key.json"
        with open(file_path) as f:
            raw = json.load(f)
        assert "data" in raw
        assert raw["data"]["val"] == 99



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



# MemoryModule (integration)

class TestMemoryModule:

    def test_get_user_context_for_new_user(self, tmp_path):
        module = MemoryModule(data_dir=str(tmp_path))
        ctx = module.get_user_context("brand_new")

        assert ctx["user_id"] == "brand_new"
        assert isinstance(ctx["preferences"], dict)
        assert ctx["wellbeing"]["risk_level"] == "unknown"
        assert ctx["wellbeing"]["trend"] == "insufficient_data"

    def test_get_user_context_with_data(self, tmp_path):
        module = MemoryModule(data_dir=str(tmp_path))

        module.wellbeing_tracker.add_assessment(
            WellbeingAssessment(risk_level="mild", user_id="u1")
        )

        ctx = module.get_user_context("u1")
        assert ctx["wellbeing"]["risk_level"] == "mild"
