"""
Calendar API - Google Calendar & Tasks Integration
Full OAuth 2.0 authentication with event and task management.
"""

import logging
import os
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, TypedDict
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
    user_timezone: str

# Google API scopes
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/tasks'
]


def calendar_token_path_for_user(
    user_id: str = "default",
    default_token_path: str = "data/tokens/calendar_token.json",
) -> Path:
    """Return the canonical token path without embedding raw user ids."""
    normalized = (user_id or "default").strip() or "default"
    if normalized == "default":
        return Path(default_token_path)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]
    return Path("data/tokens/users") / digest / "calendar_token.json"


def legacy_calendar_token_path_for_user(user_id: str = "default") -> Path:
    """Previous per-user path, used only for backward-compatible reads/deletes."""
    normalized = (user_id or "default").strip() or "default"
    if normalized == "default":
        return Path("data/tokens/default/calendar_token.json")
    return Path("data/tokens") / normalized / "calendar_token.json"


def _token_json_without_client_secret(credentials: Any) -> Dict[str, Any]:
    import json

    data = json.loads(credentials.to_json())
    data.pop("client_secret", None)
    return data


def _load_client_config(credentials_path: Path) -> Dict[str, Any]:
    import json

    with open(credentials_path) as f:
        config = json.load(f)
    return config.get("web") or config.get("installed") or {}


def _with_client_secret_for_google(
    token_data: Dict[str, Any],
    credentials_path: Path,
) -> Dict[str, Any]:
    """Add client metadata in memory for google-auth refreshes, not on disk."""
    if token_data.get("client_secret") and token_data.get("client_id"):
        return token_data
    try:
        client_config = _load_client_config(credentials_path)
    except Exception as e:
        logger.warning(f"OAuth client config load failed: {e}")
        return token_data

    hydrated = dict(token_data)
    if not hydrated.get("client_id") and client_config.get("client_id"):
        hydrated["client_id"] = client_config["client_id"]
    if not hydrated.get("client_secret") and client_config.get("client_secret"):
        hydrated["client_secret"] = client_config["client_secret"]
    return hydrated

@dataclass
class CalendarEvent:
    """Represents a calendar event."""
    id: Optional[str]
    summary: str
    description: str
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    
    def to_google_format(self, timezone_name: str = "UTC") -> Dict[str, Any]:
        return {
            'summary': self.summary,
            'description': self.description,
            'location': self.location or '',
            'start': {'dateTime': self.start_time.isoformat(), 'timeZone': timezone_name},
            'end': {'dateTime': self.end_time.isoformat(), 'timeZone': timezone_name},
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
        target_calendar_name: str = "primary",
        user_id: str = "default",
        user_timezone: str = "UTC",
    ):
        self.credentials_path = Path(credentials_path)
        self.token_path = calendar_token_path_for_user(user_id, token_path)
        self.legacy_token_path = legacy_calendar_token_path_for_user(user_id)
        self.user_id = user_id
        self.user_timezone = self._coerce_timezone(user_timezone)
        self.suggest_only = suggest_only
        self.target_calendar_name = target_calendar_name
        self.target_calendar_id = None  # Will be resolved on first use
        self.calendar_service = None
        self.tasks_service = None
        self.credentials = None
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized CalendarAPI (suggest_only={suggest_only}, target={target_calendar_name})")

    @staticmethod
    def _coerce_timezone(user_timezone: str) -> str:
        try:
            ZoneInfo(user_timezone)
            return user_timezone
        except (ZoneInfoNotFoundError, TypeError):
            logger.warning("Invalid timezone %r, falling back to UTC", user_timezone)
            return "UTC"
    
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

        # 1. Try CALENDAR_TOKEN_B64 env var directly (most reliable on Railway).
        #    Scoped to the server's own "default" user — never leak the shared
        #    token to per-user pipeline calls (see oauth/status bug, Apr 2026).
        token_b64 = os.environ.get("CALENDAR_TOKEN_B64", "").strip()
        if token_b64 and self.user_id == "default":
            try:
                token_data = _json.loads(base64.b64decode(token_b64).decode())
                self.credentials = OAuthCredentials.from_authorized_user_info(token_data, SCOPES)
                logger.info("Loaded calendar token from CALENDAR_TOKEN_B64 env var")
            except Exception as e:
                logger.warning(f"CALENDAR_TOKEN_B64 load failed: {e}")

        # 2. Fall back to token file (local dev / persistent volume)
        if not self.credentials:
            logger.info(f"Token file exists: {self.token_path.exists()} ({self.token_path.resolve()})")
            candidate_paths = [self.token_path]
            if self.legacy_token_path != self.token_path:
                candidate_paths.append(self.legacy_token_path)

            for candidate_path in candidate_paths:
                if not candidate_path.exists():
                    continue
                try:
                    with open(candidate_path, 'r') as f:
                        token_data = _json.load(f)
                    token_data = _with_client_secret_for_google(
                        token_data, self.credentials_path
                    )
                    self.credentials = OAuthCredentials.from_authorized_user_info(token_data, SCOPES)
                    logger.info("Loaded calendar token from JSON file")
                    break
                except Exception as e:
                    logger.warning(f"JSON token file load failed: {e}")
                    try:
                        with open(candidate_path, 'rb') as f:
                            self.credentials = pickle.load(f)
                        logger.info("Loaded calendar token from pickle file")
                        break
                    except Exception as e2:
                        logger.warning(f"Pickle token file load failed: {e2}")

        if self.credentials and self.credentials.expired and self.credentials.refresh_token:
            try:
                self.credentials.refresh(Request())
                # Persist refreshed token back as JSON
                try:
                    with open(self.token_path, 'w') as f:
                        _json.dump(_token_json_without_client_secret(self.credentials), f)
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
            with open(self.token_path, 'w') as f:
                _json.dump(_token_json_without_client_secret(self.credentials), f)
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
        """Get the calendar ID for writes. Defaults to the user's primary calendar."""
        if self.target_calendar_id:
            return self.target_calendar_id

        if self.target_calendar_name.lower() in {"", "primary"}:
            self.target_calendar_id = "primary"
            return "primary"
        
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
            # Proposal correctness depends on seeing the actual future window,
            # not the whole current week with past events competing for slots.
            now = datetime.now(ZoneInfo(self.user_timezone))
            time_min = now.isoformat()
            time_max = (now + timedelta(days=days)).isoformat()

            # Fetch all calendars the user has access to
            try:
                cal_list = self.calendar_service.calendarList().list().execute()
                calendar_ids = [c['id'] for c in cal_list.get('items', []) if c.get('id')]
                logger.info(f"Fetching events from {len(calendar_ids)} calendars")
            except Exception as e:
                logger.warning(f"Failed to list calendars, falling back to primary: {e}")
                target_cal_id = self.get_target_calendar_id()
                calendar_ids = list(dict.fromkeys(['primary', target_cal_id]))

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
                        if item.get('visibility') == 'private':
                            continue
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
                body=event.to_google_format(self.user_timezone)
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
        for event in events:
            formatted_events.append({
                "id": event.id,
                "title": event.summary,
                "start": event.start_time.isoformat(timespec="minutes"),
                "end": event.end_time.isoformat(timespec="minutes"),
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
            "task_count": len(tasks),
            "user_timezone": self.user_timezone,
        }
