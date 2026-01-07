"""
Memory Module for LLM Scheduler Agent.
"""

from .user_preferences import UserPreferencesManager
from .mental_health_tracker import MentalHealthTracker
from .storage import MemoryStorage

class MemoryModule:
    def __init__(self, data_dir: str = "data/memory"):
        self.storage = MemoryStorage(data_dir)
        self.preferences = UserPreferencesManager(self.storage)
        self.health_tracker = MentalHealthTracker(self.storage)
    
    def get_user_context(self, user_id: str = "default") -> dict:
        prefs = self.preferences.get_preferences(user_id)
        trend = self.health_tracker.get_trend(user_id)
        latest_score = self.health_tracker.get_latest_score(user_id)
        
        return {
            'user_id': user_id,
            'preferences': prefs.to_dict() if prefs else {},
            'mental_health': {
                'latest_phq4': latest_score.total if latest_score else None,
                'risk_level': latest_score.risk_level if latest_score else 'unknown',
                'trend': trend.direction if trend else 'stable'
            }
        }
