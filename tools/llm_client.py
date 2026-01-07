"""
LLM Client - Wrapper for Gemini API
Provides structured prompting and reasoning for schedule optimization.
"""

import logging
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger.warning("google-generativeai not installed. LLM features will be limited.")

@dataclass
class ScheduleContext:
    """Context for schedule reasoning."""
    current_events: List[Dict[str, Any]]
    phq4_score: int
    risk_level: str
    user_preferences: Dict[str, Any]
    mental_health_trend: str
    journal_summary: Optional[str] = None
    available_slots: List[Dict[str, Any]] = None

@dataclass
class ScheduleRecommendation:
    """LLM-generated schedule recommendation."""
    action: str  # "add_intervention", "reschedule", "remove", "no_change"
    reasoning: str
    suggestions: List[Dict[str, Any]]
    priority: str  # "high", "medium", "low"
    confidence: float

class LLMClient:
    """
    Wrapper for Gemini API calls.
    """
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name
        self.model = None
        
        if not self.api_key:
            logger.warning("No Gemini API key provided. LLM features will be limited.")
        elif GENAI_AVAILABLE:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(model_name)
                logger.info(f"Initialized LLM client with model: {model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")
    
    def generate(self, prompt: str, max_tokens: int = 1024) -> str:
        if not self.model:
            return "LLM not available."
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error: {e}"

    def reason_about_schedule(self, context: ScheduleContext) -> ScheduleRecommendation:
        # Simplified for reconstruction, can expand later
        return ScheduleRecommendation(
            action="no_change",
            reasoning="Reconstructed client - reasoning logic pending re-implementation",
            suggestions=[],
            priority="low",
            confidence=1.0
        )
    
    def generate_intervention_suggestions(self, **kwargs) -> List[Dict[str, Any]]:
        return []
