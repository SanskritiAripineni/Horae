"""
User Preferences - Memory Component
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Tuple, Any
from datetime import datetime

@dataclass
class UserPreferences:
    user_id: str = "default"
    goals: List[str] = field(default_factory=lambda: ["maintain work-life balance"])
    work_hours: Tuple[int, int] = (9, 17)
    preferred_interventions: List[str] = field(default_factory=lambda: ["meditation", "walk"])
    max_daily_hours: float = 8.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class UserPreferencesManager:
    def __init__(self, storage):
        self.storage = storage
    
    def get_preferences(self, user_id: str = "default") -> UserPreferences:
        data = self.storage.load('preferences', user_id)
        if data:
            return UserPreferences(**data)
        return UserPreferences(user_id=user_id)
    
    def save_preferences(self, prefs: UserPreferences):
        self.storage.save('preferences', prefs.user_id, prefs.to_dict())
