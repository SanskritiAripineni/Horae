"""
User Preferences - Memory Component
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass
class UserPreferences:
    user_id: str = "default"
    goals: List[str] = field(default_factory=lambda: ["maintain work-life balance"])
    work_hours: Tuple[int, int] = (9, 17)
    preferred_interventions: List[str] = field(
        default_factory=lambda: ["meditation", "walk"]
    )
    max_daily_hours: float = 8.0
    sleep_target_hours: float = 7.5
    evening_screen_limit_hour: int = 21
    explicit_preferences: List[str] = field(default_factory=list)
    disliked_activities: List[str] = field(default_factory=list)
    preferred_activities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class UserPreferencesManager:
    def __init__(self, storage):
        self.storage = storage

    def get_preferences(self, user_id: str = "default") -> UserPreferences:
        data = self.storage.load_user_memory(user_id).get("preferences", {})
        if data:
            return UserPreferences(**data)
        return UserPreferences(user_id=user_id)

    def save_preferences(self, prefs: UserPreferences):
        self.storage.update_user_memory(
            prefs.user_id,
            lambda memory: self._set_preferences(memory, prefs.to_dict()),
        )

    def merge_feedback(
        self,
        user_id: str,
        preference: str = "",
        dislikes: List[str] | None = None,
        prefers: List[str] | None = None,
    ) -> UserPreferences:
        prefs = self.get_preferences(user_id)
        self._append_unique(prefs.explicit_preferences, preference)
        for dislike in dislikes or []:
            self._append_unique(prefs.disliked_activities, dislike)
        for prefer in prefers or []:
            self._append_unique(prefs.preferred_activities, prefer)
            self._append_unique(prefs.preferred_interventions, prefer)
        self.save_preferences(prefs)
        return prefs

    def get_prompt_preferences(self, user_id: str = "default") -> List[str]:
        prefs = self.get_preferences(user_id)
        prompt_prefs: List[str] = []
        prompt_prefs.extend(self._non_empty_unique(prefs.explicit_preferences))
        if prefs.disliked_activities:
            prompt_prefs.append(
                "Avoid: " + ", ".join(self._non_empty_unique(prefs.disliked_activities))
            )
        if prefs.preferred_activities:
            prompt_prefs.append(
                "Prefer: " + ", ".join(self._non_empty_unique(prefs.preferred_activities))
            )
        return prompt_prefs

    @staticmethod
    def _append_unique(values: List[str], candidate: str) -> None:
        candidate = candidate.strip()
        if not candidate:
            return
        lowered = {value.strip().lower() for value in values}
        if candidate.lower() not in lowered:
            values.append(candidate)

    @staticmethod
    def _non_empty_unique(values: List[str]) -> List[str]:
        seen: set[str] = set()
        normalized: List[str] = []
        for value in values:
            cleaned = value.strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(cleaned)
        return normalized

    @staticmethod
    def _set_preferences(memory: Dict[str, Any], prefs: Dict[str, Any]) -> Dict[str, Any]:
        memory["preferences"] = prefs
        return memory
