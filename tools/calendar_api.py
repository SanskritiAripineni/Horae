"""
Calendar API - Google Calendar & Tasks Integration
Full OAuth 2.0 authentication with event and task management.
"""

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

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
            start_time = datetime.strptime(start_str, '%Y-%m-%d')
            end_time = datetime.strptime(end_str, '%Y-%m-%d')
        
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
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            import pickle
        except ImportError as e:
            logger.error(f"Google API libraries not installed: {e}")
            return False
        
        if self.token_path.exists():
            try:
                with open(self.token_path, 'rb') as f:
                    self.credentials = pickle.load(f)
            except:
                pass
        
        if self.credentials and self.credentials.expired and self.credentials.refresh_token:
            try:
                self.credentials.refresh(Request())
            except:
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
        
        try:
            with open(self.token_path, 'wb') as f:
                pickle.dump(self.credentials, f)
        except:
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
        """Get upcoming calendar events."""
        if not self.calendar_service:
            if not self.authenticate():
                return []
        
        try:
            now = datetime.utcnow().isoformat() + 'Z'
            end_time = (datetime.utcnow() + timedelta(days=days)).isoformat() + 'Z'
            
            events_result = self.calendar_service.events().list(
                calendarId='primary',
                timeMin=now,
                timeMax=end_time,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            logger.info(f"Retrieved {len(events)} calendar events")
            return [CalendarEvent.from_google_format(e) for e in events]
            
        except Exception as e:
            logger.error(f"Failed to get events: {e}")
            return []
    
    def get_tasks(self, max_results: int = 20) -> List[Dict[str, Any]]:
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
    
    def get_schedule_summary(self, days: int = 7) -> Dict[str, Any]:
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
