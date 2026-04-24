"""
Wellbeing Tracker - Memory Component

Tracks a history of wellbeing assessments (risk_level + timestamp) and
computes simple trend direction from the ordinal risk levels.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Any
from datetime import datetime

RISK_LEVELS = ("minimal", "mild", "moderate", "severe")
_RISK_RANK = {lvl: i for i, lvl in enumerate(RISK_LEVELS)}


@dataclass
class WellbeingAssessment:
    risk_level: str  # minimal / mild / moderate / severe
    user_id: str = "default"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TrendAnalysis:
    direction: str = "stable"


class WellbeingTracker:
    def __init__(self, storage):
        self.storage = storage

    def add_assessment(self, assessment: WellbeingAssessment):
        history = self._get_history(assessment.user_id)
        history.append(asdict(assessment))
        self.storage.update_user_memory(
            assessment.user_id,
            lambda memory: self._set_history(memory, history),
        )

    def get_latest(self, user_id: str = "default") -> Optional[WellbeingAssessment]:
        history = self._get_history(user_id)
        if not history:
            return None
        data = history[-1]
        return WellbeingAssessment(
            risk_level=data.get('risk_level', 'unknown'),
            user_id=data.get('user_id', user_id),
            timestamp=data.get('timestamp', ''),
        )

    def get_trend(self, user_id: str = "default") -> Optional[TrendAnalysis]:
        history = self._get_history(user_id)
        ranks = [_RISK_RANK.get(e.get('risk_level', ''), None) for e in history]
        ranks = [r for r in ranks if r is not None]

        if len(ranks) < 3:
            return TrendAnalysis(direction="insufficient_data")

        recent_3 = ranks[-3:]
        recent_avg = sum(recent_3) / len(recent_3)

        prior = ranks[:-3]
        if not prior:
            return TrendAnalysis(direction="insufficient_data")

        if len(prior) < 3:
            prior_avg = sum(prior) / len(prior)
        else:
            prior_3 = ranks[-6:-3]
            prior_avg = sum(prior_3) / len(prior_3)

        diff = recent_avg - prior_avg
        if diff > 0.5:
            return TrendAnalysis(direction="rising")
        elif diff < -0.5:
            return TrendAnalysis(direction="falling")
        else:
            return TrendAnalysis(direction="stable")

    def get_history(self, user_id: str) -> List[Any]:
        memory = self.storage.load_user_memory(user_id)
        return memory.get("wellbeing", {}).get("history", []) or []

    _get_history = get_history

    @staticmethod
    def _set_history(memory: dict, history: List[Any]) -> dict:
        memory.setdefault("wellbeing", {})
        memory["wellbeing"]["history"] = history
        return memory

