"""
Memory Storage - Persistence Layer
"""

from copy import deepcopy
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class MemoryStorage:
    def __init__(self, data_dir: str = "data/memory"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.users_dir = self.data_dir / "users"
        self.users_dir.mkdir(parents=True, exist_ok=True)

    def load_user_memory(self, user_id: str) -> dict[str, Any]:
        file_path = self._user_file(user_id)
        if not file_path.exists():
            return self._default_user_memory(user_id)
        try:
            with open(file_path, "r") as f:
                raw = json.load(f)
            if isinstance(raw, dict) and "data" in raw and isinstance(raw["data"], dict):
                raw = raw["data"]
            return self._merge_with_defaults(user_id, raw if isinstance(raw, dict) else {})
        except Exception as e:
            logger.error(f"Failed to load user memory for {user_id}: {e}")
            return self._default_user_memory(user_id)

    def save_user_memory(self, user_id: str, memory: dict[str, Any]) -> bool:
        file_path = self._user_file(user_id)
        try:
            payload = self._merge_with_defaults(user_id, memory)
            payload["updated_at"] = datetime.now().isoformat()
            with open(file_path, "w") as f:
                json.dump(payload, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save user memory for {user_id}: {e}")
            return False

    def update_user_memory(
        self,
        user_id: str,
        updater: Callable[[dict[str, Any]], Optional[dict[str, Any]]],
    ) -> dict[str, Any]:
        memory = self.load_user_memory(user_id)
        updated = updater(deepcopy(memory))
        if updated is None:
            updated = memory
        self.save_user_memory(user_id, updated)
        return updated

    def save(self, category: str, key: str, data: Any) -> bool:
        if category == "preferences":
            memory = self.load_user_memory(key)
            memory["preferences"] = data if isinstance(data, dict) else {}
            return self.save_user_memory(key, memory)
        if category == "health_history":
            memory = self.load_user_memory(key)
            memory["wellbeing"]["history"] = data if isinstance(data, list) else []
            return self.save_user_memory(key, memory)
        logger.error(
            "Legacy save(%s, %s, ...) is unsupported for single-file memory storage",
            category,
            key,
        )
        return False

    def load(self, category: str, key: str) -> Optional[Any]:
        if category == "preferences":
            return self.load_user_memory(key).get("preferences")
        if category == "health_history":
            return self.load_user_memory(key).get("wellbeing", {}).get("history", [])
        logger.error(
            "Legacy load(%s, %s) is unsupported for single-file memory storage",
            category,
            key,
        )
        return None

    def _user_file(self, user_id: str) -> Path:
        safe_user_id = user_id.replace("/", "_")
        return self.users_dir / f"{safe_user_id}.json"

    def _default_user_memory(self, user_id: str) -> dict[str, Any]:
        return {
            "user_id": user_id,
            "updated_at": None,
            "preferences": {},
            "wellbeing": {
                "history": [],
            },
            "feedback": {
                "comments": [],
                "accepted_suggestions": [],
                "rejected_suggestions": [],
            },
        }

    def _merge_with_defaults(self, user_id: str, memory: dict[str, Any]) -> dict[str, Any]:
        merged = self._default_user_memory(user_id)
        if not isinstance(memory, dict):
            return merged
        merged.update({k: v for k, v in memory.items() if k not in {"preferences", "wellbeing", "feedback"}})
        if isinstance(memory.get("preferences"), dict):
            merged["preferences"].update(memory["preferences"])
        if isinstance(memory.get("wellbeing"), dict):
            merged["wellbeing"].update(memory["wellbeing"])
        if isinstance(memory.get("feedback"), dict):
            merged["feedback"].update(memory["feedback"])
        return merged
