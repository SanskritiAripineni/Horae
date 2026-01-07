"""
AutoLife Reader - Tool 1
Reads and parses daily journals exported from the AutoLife Android app.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class AutoLifeReader:
    """
    Reader for AutoLife journals.
    Supports reading from local directory and parsing exported JSON.
    """
    
    def __init__(self, data_dir: str = "data/raw_logs"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized AutoLifeReader with data_dir: {self.data_dir}")

    def read_journals(self, limit: int = 7) -> List[Dict[str, Any]]:
        """
        Read journals from the data directory.
        Handles both individual .txt/.log files and the exported journals.json.
        """
        journals = []
        
        # 1. Check for journals.json (new export format)
        export_file = self.data_dir / "journals.json"
        if export_file.exists():
            try:
                with open(export_file, 'r') as f:
                    data = json.load(f)
                    # Expecting a list of journal entries
                    if isinstance(data, list):
                        journals.extend(data)
                        logger.info(f"Loaded {len(data)} journals from journals.json")
            except Exception as e:
                logger.error(f"Error reading journals.json: {e}")

        # 2. Check for individual files (legacy/manual format)
        for file_path in self.data_dir.glob("*"):
            if file_path.name == "journals.json":
                continue
            if file_path.suffix in ['.txt', '.log', '.json']:
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        journals.append({
                            'id': file_path.stem,
                            'content': content,
                            'timestamp': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                        })
                except Exception as e:
                    logger.warning(f"Failed to read {file_path.name}: {e}")

        # Sort by timestamp (descending) and limit
        journals.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return journals[:limit]

    def get_sync_command(self) -> str:
        """Return the ADB command to sync data from Android."""
        return "adb pull /sdcard/Download/AutoLife/data_export.json data/raw_logs/journals.json"

    def get_context_for_prompt(self, journals: List[Dict[str, Any]]) -> str:
        """Format journals for LLM prompt."""
        if not journals:
            return "No recent journal entries found."
        
        formatted = []
        for j in journals:
            date = j.get('timestamp', 'Unknown Date')
            content = j.get('content', j.get('text', ''))
            formatted.append(f"Date: {date}\nJournal: {content}\n")
            
        return "\n---\n".join(formatted)
