"""
AutoLife Reader - Tool 1
Reads and parses daily journals exported from the AutoLife Android app.
"""

import os
import json
import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class AutoLifeReader:
    """
    Reader for AutoLife journals.
    Supports reading from local directory and parsing exported text files.
    """
    
    def __init__(self, data_dir: str = "data/raw_logs"):
        self.data_dir = Path(data_dir)
        self.autolife_dir = self.data_dir / "AutoLife"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized AutoLifeReader with data_dir: {self.data_dir}")

    def read_journals(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Read journals from the data directory.
        Parses the exported text files with multiple journal entries.
        """
        journals = []
        
        # Find the most recent export file
        search_dirs = [self.autolife_dir, self.data_dir]
        export_files = []
        
        for search_dir in search_dirs:
            if search_dir.exists():
                for f in search_dir.glob("all_journals_*.txt"):
                    if not f.name.startswith('.'):  # Skip trashed files
                        export_files.append(f)
        
        if not export_files:
            logger.warning("No journal export files found")
            return journals
        
        # Sort by modification time, get most recent
        export_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        latest_file = export_files[0]
        logger.info(f"Reading journals from: {latest_file.name}")
        
        # Parse the export file
        try:
            with open(latest_file, 'r') as f:
                content = f.read()
            
            # Parse individual journal entries
            # Format: ========\nJOURNAL ENTRY #N\nCreated At: ...\nPeriod: ...\n--------\n\n<content>
            entries = re.split(r'={40,}', content)
            
            for entry in entries:
                entry = entry.strip()
                if not entry or 'JOURNAL ENTRY' not in entry:
                    continue
                
                # Extract entry number
                match = re.search(r'JOURNAL ENTRY #(\d+)', entry)
                entry_num = match.group(1) if match else '0'
                
                # Extract created timestamp
                created_match = re.search(r'Created At: ([\d\-: ]+)', entry)
                created_at = created_match.group(1) if created_match else ''
                
                # Extract period
                period_match = re.search(r'Period: (.+)', entry)
                period = period_match.group(1) if period_match else ''
                
                # Extract content (after the dashed line)
                content_match = re.search(r'-{20,}\s*\n\n(.+)', entry, re.DOTALL)
                content = content_match.group(1).strip() if content_match else entry
                
                journals.append({
                    'id': f'entry_{entry_num}',
                    'entry_number': int(entry_num),
                    'created_at': created_at,
                    'period': period,
                    'content': content,
                    'timestamp': created_at
                })
            
            logger.info(f"Parsed {len(journals)} journal entries")
            
        except Exception as e:
            logger.error(f"Error reading journal file: {e}")
        
        # Sort by entry number descending and limit
        journals.sort(key=lambda x: x.get('entry_number', 0), reverse=True)
        return journals[:limit]

    def get_context_for_prompt(self, journals: List[Dict[str, Any]], max_chars: int = 6000) -> str:
        """Format journals for LLM prompt."""
        if not journals:
            return "No recent journal entries found."
        
        formatted = []
        total_chars = 0
        
        for j in journals:
            date = j.get('created_at', j.get('timestamp', 'Unknown'))
            period = j.get('period', '')
            content = j.get('content', '')
            
            entry = f"[{date}] ({period})\n{content}"
            
            if total_chars + len(entry) > max_chars:
                break
            
            formatted.append(entry)
            total_chars += len(entry)
        
        return "\n\n---\n\n".join(formatted)
