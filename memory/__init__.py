"""
Memory Module for LLM Scheduler Agent.
"""

from datetime import datetime

from .user_preferences import UserPreferencesManager
from .wellbeing_tracker import WellbeingTracker
from .wellbeing_tracker import WellbeingAssessment
from .storage import MemoryStorage

class MemoryModule:
    def __init__(self, data_dir: str = "data/memory"):
        self.storage = MemoryStorage(data_dir)
        self.preferences = UserPreferencesManager(self.storage)
        self.wellbeing_tracker = WellbeingTracker(self.storage)

    def get_user_context(self, user_id: str = "default") -> dict:
        prefs = self.preferences.get_preferences(user_id)
        trend = self.wellbeing_tracker.get_trend(user_id)
        latest = self.wellbeing_tracker.get_latest(user_id)
        user_memory = self.storage.load_user_memory(user_id)

        return {
            'user_id': user_id,
            'preferences': prefs.to_dict() if prefs else {},
            'wellbeing': {
                'risk_level': latest.risk_level if latest else 'unknown',
                'trend': trend.direction if trend else 'stable',
            },
            'feedback': user_memory.get('feedback', {}),
        }

    def record_wellbeing_assessment(self, user_id: str, risk_level: str) -> None:
        normalized = (risk_level or "").strip().lower()
        if not normalized:
            return
        self.wellbeing_tracker.add_assessment(
            WellbeingAssessment(
                risk_level=normalized,
                user_id=user_id,
            )
        )

    def record_feedback(
        self,
        user_id: str,
        raw_feedback: str,
        parsed_feedback: dict | None = None,
    ) -> None:
        parsed_feedback = parsed_feedback or {}
        timestamp = datetime.now().isoformat()
        entry = {
            "raw_feedback": raw_feedback,
            "preference": parsed_feedback.get("preference", ""),
            "dislikes": parsed_feedback.get("dislikes", []),
            "prefers": parsed_feedback.get("prefers", []),
            "should_save": parsed_feedback.get("should_save", False),
            "timestamp": timestamp,
        }
        self.storage.update_user_memory(
            user_id,
            lambda memory: self._append_feedback_comment(memory, entry),
        )
        if parsed_feedback.get("should_save", True):
            self.preferences.merge_feedback(
                user_id=user_id,
                preference=parsed_feedback.get("preference", raw_feedback),
                dislikes=parsed_feedback.get("dislikes", []),
                prefers=parsed_feedback.get("prefers", []),
            )

    def get_prompt_preferences(self, user_id: str = "default") -> list[str]:
        return self.preferences.get_prompt_preferences(user_id)

    def record_suggestion_feedback(
        self,
        user_id: str,
        suggestion: str,
        action: str,
        behavioral_state_summary: str = "",
    ) -> None:
        suggestion = suggestion.strip()
        action = action.strip().lower()
        if not suggestion or action not in {"accept", "reject"}:
            return
        entry = {
            "suggestion": suggestion,
            "behavioral_state_summary": behavioral_state_summary,
            "timestamp": datetime.now().isoformat(),
        }
        self.storage.update_user_memory(
            user_id,
            lambda memory: self._append_suggestion_feedback(memory, action, entry),
        )

    @staticmethod
    def _append_feedback_comment(memory: dict, entry: dict) -> dict:
        memory.setdefault("feedback", {})
        comments = memory["feedback"].setdefault("comments", [])
        comments.append(entry)
        return memory

    @staticmethod
    def _append_suggestion_feedback(memory: dict, action: str, entry: dict) -> dict:
        memory.setdefault("feedback", {})
        key = "accepted_suggestions" if action == "accept" else "rejected_suggestions"
        items = memory["feedback"].setdefault(key, [])
        items.append(entry)
        return memory
