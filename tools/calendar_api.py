"""
Calendar API - Google Calendar & Tasks Integration
Full OAuth 2.0 authentication with event and task management.
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, TypedDict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class TaskSummary(TypedDict):
    """A normalized Google Task entry as exposed to the pipeline."""
    id: str
    title: str
    notes: str
    due: str
    list: str
    status: str


class FormattedEvent(TypedDict):
    """A calendar event flattened for the LLM prompt."""
    id: Optional[str]
    title: str
    start: str
    end: str
    duration_hours: float


class FormattedTask(TypedDict):
    """A task flattened for the LLM prompt."""
    id: str
    title: str
    due: str
    list: str


class ScheduleSummary(TypedDict):
    """Return shape of CalendarAPI.get_schedule_summary()."""
    event_count: int
    events: List[FormattedEvent]
    total_hours: float
    busiest_day: Optional[str]
    days_covered: int
    tasks: List[FormattedTask]
    task_count: int

# Google API scopes
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/tasks'
]

@dataclass
class CalendarEvent:
    """Represents a calendar event."""
    id: Optional[str]
    summary: str
    description: str
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    
    def to_google_format(self) -> Dict[str, Any]:
        return {
            'summary': self.summary,
            'description': self.description,
            'location': self.location or '',
            'start': {'dateTime': self.start_time.isoformat(), 'timeZone': 'America/Chicago'},
            'end': {'dateTime': self.end_time.isoformat(), 'timeZone': 'America/Chicago'},
        }
    
    @classmethod
    def from_google_format(cls, event: Dict[str, Any]) -> 'CalendarEvent':
        start = event.get('start', {})
        end = event.get('end', {})
        start_str = start.get('dateTime') or start.get('date')
        end_str = end.get('dateTime') or end.get('date')
        
        if 'T' in str(start_str):
            start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
        else:
            # All-day events — make timezone-aware so they can be sorted with timed events
            start_time = datetime.strptime(start_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            end_time = datetime.strptime(end_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        
        return cls(
            id=event.get('id'),
            summary=event.get('summary', 'No Title'),
            description=event.get('description', ''),
            start_time=start_time,
            end_time=end_time,
            location=event.get('location')
        )


class CalendarAPI:
    """Google Calendar & Tasks API integration with OAuth 2.0."""
    
    def __init__(
        self, 
        credentials_path: str = "credentials.json",
        token_path: str = "data/tokens/calendar_token.json",
        suggest_only: bool = True,
        target_calendar_name: str = "RIDE Agent"
    ):
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self.suggest_only = suggest_only
        self.target_calendar_name = target_calendar_name
        self.target_calendar_id = None  # Will be resolved on first use
        self.calendar_service = None
        self.tasks_service = None
        self.credentials = None
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized CalendarAPI (suggest_only={suggest_only}, target={target_calendar_name})")
    
    def authenticate(self) -> bool:
        """Authenticate with Google APIs using OAuth 2.0."""
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            import pickle
        except ImportError as e:
            logger.error(f"Google API libraries not installed: {e}")
            return False
        
        import base64, json as _json
        from google.oauth2.credentials import Credentials as OAuthCredentials

        # 1. Try CALENDAR_TOKEN_B64 env var directly (most reliable on Railway)
        token_b64 = os.environ.get("CALENDAR_TOKEN_B64", "").strip()
        if token_b64:
            try:
                token_data = _json.loads(base64.b64decode(token_b64).decode())
                self.credentials = OAuthCredentials.from_authorized_user_info(token_data, SCOPES)
                logger.info("Loaded calendar token from CALENDAR_TOKEN_B64 env var")
            except Exception as e:
                logger.warning(f"CALENDAR_TOKEN_B64 load failed: {e}")

        # 2. Fall back to token file (local dev / persistent volume)
        if not self.credentials:
            logger.info(f"Token file exists: {self.token_path.exists()} ({self.token_path.resolve()})")
            if self.token_path.exists():
                try:
                    with open(self.token_path, 'r') as f:
                        token_data = _json.load(f)
                    self.credentials = OAuthCredentials.from_authorized_user_info(token_data, SCOPES)
                    logger.info("Loaded calendar token from JSON file")
                except Exception as e:
                    logger.warning(f"JSON token file load failed: {e}")
                    try:
                        with open(self.token_path, 'rb') as f:
                            self.credentials = pickle.load(f)
                        logger.info("Loaded calendar token from pickle file")
                    except Exception as e2:
                        logger.warning(f"Pickle token file load failed: {e2}")

        if self.credentials and self.credentials.expired and self.credentials.refresh_token:
            try:
                self.credentials.refresh(Request())
                # Persist refreshed token back as JSON
                try:
                    import json
                    with open(self.token_path, 'w') as f:
                        json.dump(json.loads(self.credentials.to_json()), f)
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                self.credentials = None

        if not self.credentials or not self.credentials.valid:
            if not self.credentials_path.exists():
                logger.error(f"credentials.json not found")
                return False

            try:
                flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), SCOPES)
                self.credentials = flow.run_local_server(port=0)
            except Exception as e:
                logger.error(f"OAuth flow failed: {e}")
                return False

        # Persist as JSON (canonical format for Railway)
        try:
            import json
            with open(self.token_path, 'w') as f:
                json.dump(json.loads(self.credentials.to_json()), f)
        except Exception:
            # Fall back to pickle if to_json() not available (older google-auth)
            try:
                with open(self.token_path, 'wb') as f:
                    pickle.dump(self.credentials, f)
            except Exception:
                pass
        
        try:
            self.calendar_service = build('calendar', 'v3', credentials=self.credentials)
            self.tasks_service = build('tasks', 'v1', credentials=self.credentials)
            logger.info("Google Calendar & Tasks API connected")
            return True
        except Exception as e:
            logger.error(f"Failed to build services: {e}")
            return False
    
    def get_target_calendar_id(self) -> str:
        """Get the calendar ID for the target calendar (RIDE Agent). Falls back to primary."""
        if self.target_calendar_id:
            return self.target_calendar_id
        
        if not self.calendar_service:
            if not self.authenticate():
                return 'primary'
        
        try:
            calendar_list = self.calendar_service.calendarList().list().execute()
            for calendar in calendar_list.get('items', []):
                if calendar.get('summary', '').lower() == self.target_calendar_name.lower():
                    self.target_calendar_id = calendar.get('id')
                    logger.info(f"Found target calendar: {self.target_calendar_name} ({self.target_calendar_id})")
                    return self.target_calendar_id
            
            logger.warning(f"Calendar '{self.target_calendar_name}' not found, using primary")
            self.target_calendar_id = 'primary'
            return 'primary'
        except Exception as e:
            logger.error(f"Failed to list calendars: {e}")
            return 'primary'
    
    def get_events(self, days: int = 7, max_results: int = 50) -> List[CalendarEvent]:
        """Get calendar events from the start of the current week through the next `days` days.
        Merges events from both the primary calendar and the RIDE Agent calendar, deduplicated by id."""
        if not self.calendar_service:
            if not self.authenticate():
                return []

        try:
            # Start from the Monday of the current week so the full week is always visible
            today = datetime.utcnow()
            days_since_monday = today.weekday()  # 0 = Monday
            week_start = (today - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            time_min = week_start.isoformat() + 'Z'
            time_max = (today + timedelta(days=days)).isoformat() + 'Z'

            target_cal_id = self.get_target_calendar_id()
            calendar_ids = list(dict.fromkeys(['primary', target_cal_id]))  # deduplicate

            seen_ids: set = set()
            all_events: List[CalendarEvent] = []

            for cal_id in calendar_ids:
                try:
                    events_result = self.calendar_service.events().list(
                        calendarId=cal_id,
                        timeMin=time_min,
                        timeMax=time_max,
                        maxResults=max_results,
                        singleEvents=True,
                        orderBy='startTime'
                    ).execute()
                    for item in events_result.get('items', []):
                        event_id = item.get('id')
                        if event_id and event_id in seen_ids:
                            continue
                        if event_id:
                            seen_ids.add(event_id)
                        all_events.append(CalendarEvent.from_google_format(item))
                except Exception as e:
                    logger.warning(f"Failed to fetch events from calendar '{cal_id}': {e}")

            all_events.sort(key=lambda ev: ev.start_time)
            logger.info(f"Retrieved {len(all_events)} calendar events (merged {len(calendar_ids)} calendars)")
            return all_events

        except Exception as e:
            logger.error(f"Failed to get events: {e}")
            return []
    
    def get_tasks(self, max_results: int = 20) -> List[TaskSummary]:
        """Get Google Tasks."""
        if not self.tasks_service:
            if not self.authenticate():
                return []
        
        try:
            # Get task lists
            tasklists = self.tasks_service.tasklists().list(maxResults=10).execute()
            all_tasks = []
            
            for tasklist in tasklists.get('items', []):
                list_id = tasklist['id']
                list_title = tasklist['title']
                
                # Get tasks in this list
                tasks_result = self.tasks_service.tasks().list(
                    tasklist=list_id,
                    maxResults=max_results,
                    showCompleted=False
                ).execute()
                
                for task in tasks_result.get('items', []):
                    all_tasks.append({
                        'id': task.get('id'),
                        'title': task.get('title', 'Untitled'),
                        'notes': task.get('notes', ''),
                        'due': task.get('due', ''),
                        'list': list_title,
                        'status': task.get('status', 'needsAction')
                    })
            
            logger.info(f"Retrieved {len(all_tasks)} tasks")
            return all_tasks
            
        except Exception as e:
            logger.error(f"Failed to get tasks: {e}")
            return []
    
    def create_event(self, event: CalendarEvent) -> Optional[str]:
        """Create a new calendar event in the RIDE Agent calendar."""
        if self.suggest_only:
            logger.info(f"[SUGGEST] Would create: {event.summary}")
            return "suggested_id"
        
        if not self.calendar_service:
            if not self.authenticate():
                return None
        
        try:
            calendar_id = self.get_target_calendar_id()
            result = self.calendar_service.events().insert(
                calendarId=calendar_id,
                body=event.to_google_format()
            ).execute()
            logger.info(f"Created event: {result.get('id')}")
            return result.get('id')
        except Exception as e:
            logger.error(f"Failed to create event: {e}")
            return None
    
    def get_schedule_summary(self, days: int = 7) -> ScheduleSummary:
        """Get a summary of schedule for LLM analysis."""
        events = self.get_events(days=days)
        tasks = self.get_tasks()
        
        # Calculate metrics
        total_hours = 0
        events_by_day = {}
        
        for event in events:
            day = event.start_time.strftime('%Y-%m-%d')
            if day not in events_by_day:
                events_by_day[day] = []
            events_by_day[day].append(event)
            duration = (event.end_time - event.start_time).total_seconds() / 3600
            total_hours += duration
        
        busiest_day = max(events_by_day.keys(), key=lambda d: len(events_by_day[d])) if events_by_day else None
        
        # Format for LLM
        formatted_events = []
        for event in events[:20]:
            formatted_events.append({
                "id": event.id,
                "title": event.summary,
                "start": event.start_time.strftime('%Y-%m-%d %H:%M'),
                "end": event.end_time.strftime('%H:%M'),
                "duration_hours": round((event.end_time - event.start_time).total_seconds() / 3600, 1)
            })
        
        formatted_tasks = []
        for task in tasks[:10]:
            formatted_tasks.append({
                "id": task['id'],
                "title": task['title'],
                "due": task['due'][:10] if task['due'] else 'No due date',
                "list": task['list']
            })
        
        return {
            "event_count": len(events),
            "events": formatted_events,
            "total_hours": round(total_hours, 1),
            "busiest_day": busiest_day,
            "days_covered": len(events_by_day),
            "tasks": formatted_tasks,
            "task_count": len(tasks)
        }
