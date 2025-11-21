"""
AutoLife Reader - Tool 1
Parses generated journals from AutoLife data collection.
"""

import logging
from typing import List, Dict, Any
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class AutoLifeReader:
    """
    Reads and parses AutoLife journal entries.
    Input: Raw sensor logs and journals from Android app
    Output: Structured journal data for processing
    """
    
    def __init__(self, data_dir: str = "data/raw_logs"):
        """
        Initialize the AutoLife reader.
        
        Args:
            data_dir: Directory containing raw log files
        """
        self.data_dir = Path(data_dir)
        logger.info(f"Initialized AutoLifeReader with data_dir: {self.data_dir}")
    
    def read_journals(self, limit: int = None) -> List[Dict[str, Any]]:
        """
        Read journal entries from the data directory.
        
        Args:
            limit: Maximum number of journals to read (None = all)
            
        Returns:
            List of journal dictionaries
        """
        journals = []
        
        if not self.data_dir.exists():
            logger.warning(f"Data directory does not exist: {self.data_dir}")
            return journals
        
        # Find all journal files
        journal_files = sorted(self.data_dir.glob("journal_*.json"))
        
        if limit:
            journal_files = journal_files[:limit]
        
        logger.info(f"Found {len(journal_files)} journal files")
        
        for journal_file in journal_files:
            try:
                with open(journal_file, 'r') as f:
                    journal_data = json.load(f)
                    journals.append(journal_data)
            except Exception as e:
                logger.error(f"Error reading journal {journal_file}: {e}")
        
        return journals
    
    def parse_sensor_data(self, raw_log_file: str) -> Dict[str, Any]:
        """
        Parse raw sensor log data into structured format.
        
        Args:
            raw_log_file: Path to raw sensor log file
            
        Returns:
            Dictionary containing parsed sensor data
        """
        # TODO: Implement sensor data parsing
        # This should parse accelerometer, gyroscope, GPS, WiFi, etc.
        logger.info(f"Parsing sensor data from: {raw_log_file}")
        return {}
    
    def extract_context(self, journal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract motion and location context from journal entry.
        
        Args:
            journal: Journal dictionary
            
        Returns:
            Dictionary containing extracted context information
        """
        context = {
            'motion': journal.get('motion_context', 'unknown'),
            'location': journal.get('location_context', 'unknown'),
            'timestamp': journal.get('timestamp', None),
            'duration': journal.get('duration_seconds', 0)
        }
        
        return context
