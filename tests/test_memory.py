"""
Tests for memory module — MemoryStorage, MentalHealthTracker, UserPreferencesManager.

Uses temporary directories for all file I/O. Tests cover:
- MemoryStorage save/load round-trips
- MentalHealthTracker add_assessment, get_latest_score, get_history, get_trend
- UserPreferencesManager get/save round-trip, defaults
- MemoryModule.get_user_context() integration
"""

import json
import pytest
from pathlib import Path

from memory.storage import MemoryStorage
from memory.mental_health_tracker import MentalHealthTracker, PHQ4Score, TrendAnalysis
from memory.user_preferences import UserPreferencesManager, UserPreferences
from memory import MemoryModule


# ---------------------------------------------------------------------------
# MemoryStorage
# ---------------------------------------------------------------------------

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

        # List
        storage.save("cat", "list_key", [1, 2, 3])
        assert storage.load("cat", "list_key") == [1, 2, 3]

        # String
        storage.save("cat", "str_key", "hello")
        assert storage.load("cat", "str_key") == "hello"

        # Nested dict
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


# ---------------------------------------------------------------------------
# MentalHealthTracker
# ---------------------------------------------------------------------------

class TestMentalHealthTracker:

    def test_add_and_get_latest_score(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        tracker = MentalHealthTracker(storage)

        score1 = PHQ4Score(total=3, user_id="u1", risk_level="mild")
        score2 = PHQ4Score(total=7, user_id="u1", risk_level="moderate")

        tracker.add_assessment(score1)
        tracker.add_assessment(score2)

        latest = tracker.get_latest_score("u1")
        assert latest is not None
        assert latest.total == 7
        assert latest.risk_level == "moderate"

    def test_get_latest_score_returns_none_for_new_user(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        tracker = MentalHealthTracker(storage)
        assert tracker.get_latest_score("nobody") is None

    def test_get_history(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        tracker = MentalHealthTracker(storage)

        tracker.add_assessment(PHQ4Score(total=2, user_id="u1", risk_level="minimal"))
        tracker.add_assessment(PHQ4Score(total=5, user_id="u1", risk_level="mild"))

        history = tracker.get_history("u1")
        assert len(history) == 2
        assert history[0]["total"] == 2
        assert history[1]["total"] == 5

    def test_get_history_returns_empty_for_unknown_user(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        tracker = MentalHealthTracker(storage)
        assert tracker.get_history("ghost") == []

    def test_get_trend_returns_insufficient_data_for_new_user(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        tracker = MentalHealthTracker(storage)
        trend = tracker.get_trend("u1")
        assert isinstance(trend, TrendAnalysis)
        assert trend.direction == "insufficient_data"

    def test_get_trend_returns_stable_with_enough_data(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        tracker = MentalHealthTracker(storage)
        # Need at least 6 scores for a meaningful comparison (3 recent vs 3 prior)
        for score_val in [4, 4, 4, 4, 4, 4]:
            tracker.add_assessment(PHQ4Score(total=score_val, user_id="u1", risk_level="mild"))
        trend = tracker.get_trend("u1")
        assert trend.direction == "stable"

    def test_get_trend_detects_rising(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        tracker = MentalHealthTracker(storage)
        # Prior 3 scores low, recent 3 scores high
        for score_val in [2, 2, 2, 6, 6, 6]:
            tracker.add_assessment(PHQ4Score(total=score_val, user_id="u1", risk_level="mild"))
        trend = tracker.get_trend("u1")
        assert trend.direction == "rising"

    def test_get_trend_detects_falling(self, tmp_path):
        storage = MemoryStorage(data_dir=str(tmp_path))
        tracker = MentalHealthTracker(storage)
        # Prior 3 scores high, recent 3 scores low
        for score_val in [8, 8, 8, 3, 3, 3]:
            tracker.add_assessment(PHQ4Score(total=score_val, user_id="u1", risk_level="mild"))
        trend = tracker.get_trend("u1")
        assert trend.direction == "falling"

    def test_phq4_score_defaults(self):
        score = PHQ4Score(total=5)
        assert score.user_id == "default"
        assert score.risk_level == "unknown"
        assert score.timestamp  # should have a default timestamp


# ---------------------------------------------------------------------------
# UserPreferencesManager
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# MemoryModule (integration)
# ---------------------------------------------------------------------------

class TestMemoryModule:

    def test_get_user_context_for_new_user(self, tmp_path):
        module = MemoryModule(data_dir=str(tmp_path))
        ctx = module.get_user_context("brand_new")

        assert ctx["user_id"] == "brand_new"
        assert isinstance(ctx["preferences"], dict)
        assert ctx["mental_health"]["latest_phq4"] is None
        assert ctx["mental_health"]["trend"] == "insufficient_data"

    def test_get_user_context_with_data(self, tmp_path):
        module = MemoryModule(data_dir=str(tmp_path))

        # Store some data first
        score = PHQ4Score(total=4, user_id="u1", risk_level="mild")
        module.health_tracker.add_assessment(score)

        ctx = module.get_user_context("u1")
        assert ctx["mental_health"]["latest_phq4"] == 4
        assert ctx["mental_health"]["risk_level"] == "mild"
