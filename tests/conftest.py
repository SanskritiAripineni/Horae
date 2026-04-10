"""
Shared fixtures for backend unit tests.
"""

import os
import sys
import json
import tempfile
import pytest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# Ensure project root is on sys.path so imports work
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Fixtures: sample data
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_journals():
    """Two sample journal entries matching the Android export format."""
    return [
        {
            "id": "1",
            "entry_number": 1,
            "created_at": "2024-05-10 08:00:00",
            "period": "Morning",
            "content": "Barely slept. Very anxious about the project deadline approaching.",
            "timestamp": "2024-05-10 08:00:00",
        },
        {
            "id": "2",
            "entry_number": 2,
            "created_at": "2024-05-10 14:00:00",
            "period": "Afternoon",
            "content": "Skipped lunch, stayed at desk all day. Feeling overwhelmed.",
            "timestamp": "2024-05-10 14:00:00",
        },
    ]


@pytest.fixture
def sample_analysis():
    """Typical output from LLMClient.analyze_mental_health()."""
    return {
        "summary": "User shows signs of stress and poor sleep.",
        "phq4_estimate": 6,
        "risk_level": "moderate",
        "concerns": ["poor sleep", "anxiety", "skipping meals"],
        "positives": ["still attending class"],
    }


@pytest.fixture
def sample_recommendations():
    """Typical output from LLMClient.generate_recommendations()."""
    return [
        {
            "category": "Sleep",
            "action": "Establish a consistent bedtime routine",
            "when": "Before bed",
            "source": "Sleep Hygiene Study",
        },
        {
            "category": "Stress",
            "action": "Try a 10-minute guided meditation",
            "when": "During lunch break",
            "source": "Mindfulness Meta-Analysis",
        },
    ]


@pytest.fixture
def sample_calendar_summary():
    """Typical output from CalendarAPI.get_schedule_summary()."""
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    return {
        "event_count": 2,
        "events": [
            {
                "id": "evt1",
                "title": "Team Meeting",
                "start": tomorrow.strftime("%Y-%m-%d 10:00"),
                "end": "11:00",
                "duration_hours": 1.0,
            },
            {
                "id": "evt2",
                "title": "Lunch",
                "start": tomorrow.strftime("%Y-%m-%d 12:00"),
                "end": "13:00",
                "duration_hours": 1.0,
            },
        ],
        "total_hours": 2.0,
        "busiest_day": tomorrow.strftime("%Y-%m-%d"),
        "days_covered": 1,
        "tasks": [
            {
                "id": "task1",
                "title": "Finish report",
                "due": tomorrow.strftime("%Y-%m-%d"),
                "list": "My Tasks",
            }
        ],
        "task_count": 1,
    }


@pytest.fixture
def sample_proposed_changes():
    """Typical output from LLMClient.generate_calendar_changes()."""
    tomorrow = datetime.now() + timedelta(days=1)
    return [
        {
            "action": "add",
            "title": "Morning Meditation",
            "description": "10-minute guided meditation",
            "start_time": tomorrow.replace(hour=7, minute=0).strftime("%Y-%m-%dT%H:%M:%S"),
            "end_time": tomorrow.replace(hour=7, minute=15).strftime("%Y-%m-%dT%H:%M:%S"),
            "category": "Mindfulness",
            "reason": "Helps reduce morning anxiety",
        },
    ]


@pytest.fixture
def temp_data_dir(tmp_path):
    """Provide a temporary directory for file-based storage tests."""
    return str(tmp_path / "test_memory")
