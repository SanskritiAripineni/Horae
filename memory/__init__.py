"""
Memory Module for LLM Scheduler Agent.
"""

from .user_preferences import UserPreferencesManager
from .wellbeing_tracker import WellbeingTracker
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

        return {
            'user_id': user_id,
            'preferences': prefs.to_dict() if prefs else {},
            'wellbeing': {
                'risk_level': latest.risk_level if latest else 'unknown',
                'trend': trend.direction if trend else 'stable',
            }
        }
