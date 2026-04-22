"""
Configuration for LLM Scheduler Agent.
Centralizes all configuration settings with environment variable support.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

@dataclass
class Config:
    """
    Configuration settings for the LLM Scheduler Agent.
    """
    
    # API Keys
    GEMINI_API_KEY: Optional[str] = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY")
    )
    MAPS_API_KEY: Optional[str] = field(
        default_factory=lambda: os.getenv("MAPS_API_KEY")
    )
    
    # Paths
    PROJECT_ROOT: Path = field(
        default_factory=lambda: Path(__file__).parent
    )
    DATA_DIR: str = field(
        default_factory=lambda: os.getenv("LLM_SCHEDULER_DATA_DIR", "data")
    )
    CREDENTIALS_PATH: str = "credentials.json"
    TOKEN_PATH: str = "data/tokens/calendar_token.json"
    
    # User settings
    DEFAULT_USER_ID: str = field(
        default_factory=lambda: os.getenv("LLM_SCHEDULER_USER_ID", "default")
    )
    
    # Calendar settings
    CALENDAR_TIMEZONE: str = "America/Chicago"
    CALENDAR_SUGGEST_ONLY: bool = True
    
    # Workload settings
    MAX_DAILY_HOURS: float = 8.0
    WORK_HOURS_START: int = 9
    WORK_HOURS_END: int = 17
    
    # Embedding / VectorDB settings
    EMBEDDING_MODEL: str = "gemini-embedding-2-preview"
    VECTORDB_COLLECTION: str = "wellness_papers_gemini"

    # LLM settings
    LLM_MODEL: str = "gemini-3-flash-preview"
    LLM_MAX_TOKENS: int = 1024
    LLM_TEMPERATURE: float = 0.7
    
    def get_data_path(self, *parts: str) -> Path:
        """Get a path within the data directory."""
        return self.PROJECT_ROOT / self.DATA_DIR / Path(*parts)
    
    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        directories = [
            self.get_data_path("raw_logs"),
            self.get_data_path("tokens"),
            self.get_data_path("memory"),
            self.get_data_path("memory", "preferences"),
            self.get_data_path("memory", "health_history"),
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

# Global config instance
config = Config()
config.ensure_directories()
