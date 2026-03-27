"""
Memory Storage - Persistence Layer
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

class MemoryStorage:
    def __init__(self, data_dir: str = "data/memory"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def save(self, category: str, key: str, data: Any) -> bool:
        category_dir = self.data_dir / category
        category_dir.mkdir(parents=True, exist_ok=True)
        file_path = category_dir / f"{key}.json"
        try:
            with open(file_path, 'w') as f:
                json.dump({'data': data}, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save {category}/{key}: {e}")
            return False

    def load(self, category: str, key: str) -> Optional[Any]:
        file_path = self.data_dir / category / f"{key}.json"
        if not file_path.exists():
            return None
        try:
            with open(file_path, 'r') as f:
                return json.load(f).get('data')
        except Exception as e:
            logger.error(f"Failed to load {category}/{key}: {e}")
            return None
