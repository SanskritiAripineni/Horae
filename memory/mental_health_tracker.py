"""
Mental Health Tracker - Memory Component
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Any
from datetime import datetime

@dataclass
class PHQ4Score:
    total: int
    user_id: str = "default"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    risk_level: str = "unknown"

@dataclass
class TrendAnalysis:
    direction: str = "stable"

class MentalHealthTracker:
    def __init__(self, storage):
        self.storage = storage
    
    def add_assessment(self, score: PHQ4Score):
        history = self._get_history(score.user_id)
        history.append(asdict(score))
        self.storage.save('health_history', score.user_id, history)
    
    def get_latest_score(self, user_id: str = "default") -> Optional[PHQ4Score]:
        history = self._get_history(user_id)
        if not history: return None
        data = history[-1]
        return PHQ4Score(total=data['total'], user_id=data['user_id'], timestamp=data['timestamp'], risk_level=data['risk_level'])
    
    def get_trend(self, user_id: str = "default") -> Optional[TrendAnalysis]:
        return TrendAnalysis(direction="stable")
    
    def _get_history(self, user_id: str) -> List[Any]:
        return self.storage.load('health_history', user_id) or []
