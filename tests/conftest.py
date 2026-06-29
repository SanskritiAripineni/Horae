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



# Fixtures: sample data

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
    """Typical output from LLMClient.analyze_wellbeing()."""
    return {
        "summary": "User shows signs of stress and poor sleep.",
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


# Fixtures: wellbeing pipeline inputs

def _typical_markers(day_obj):
    """One day of average markers. Shared by warm/cold fixtures."""
    return {
        "date": day_obj,
        "sleep_onset_hour": 23.5,
        "sleep_duration_hours": 7.5,
        "sleep_regularity_index": 82.0,
        "late_night_screen_min": 30.0,
        "total_screen_min": 240.0,
        "app_switching_rate": 2.0,
        "mobility_entropy": 2.5,
        "location_revisit_ratio": 0.65,
        "social_rhythm_metric": 0.78,
        "comm_reciprocity": 0.55,
    }


@pytest.fixture
def cold_raw_days():
    """5 days of markers — below the 10-day warmup threshold."""
    from datetime import date, timedelta
    start = date(2024, 5, 1)
    return [_typical_markers(start + timedelta(days=i)) for i in range(5)]


@pytest.fixture
def warm_raw_days():
    """14 days of stable markers — baseline is warm."""
    from datetime import date, timedelta
    start = date(2024, 5, 1)
    return [_typical_markers(start + timedelta(days=i)) for i in range(14)]


@pytest.fixture
def deviation_raw_days():
    """30 days of stable markers followed by 4 days of pronounced sleep loss.

    Baseline window picks up the stable ~7.5h sleep duration; the final 4
    days drop to ~4h, which Layer 2 should flag as a sustained deviation.
    """
    from datetime import date, timedelta
    start = date(2024, 5, 1)
    records = []
    for i in range(30):
        m = _typical_markers(start + timedelta(days=i))
        records.append(m)
    for i in range(30, 34):
        m = _typical_markers(start + timedelta(days=i))
        m["sleep_duration_hours"] = 4.0
        m["sleep_onset_hour"] = 2.5  # 2:30 AM, very late
        m["late_night_screen_min"] = 180.0
        records.append(m)
    return records
