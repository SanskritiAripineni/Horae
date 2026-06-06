from datetime import datetime, timedelta, timezone

from tools.calendar_api import CalendarAPI, calendar_token_path_for_user


def test_per_user_token_path_hashes_user_id():
    token_path = calendar_token_path_for_user("alice@example.com")

    assert "alice" not in str(token_path)
    assert "example.com" not in str(token_path)
    assert token_path.parts[-2] != "alice@example.com"
    assert token_path.name == "calendar_token.json"


class _Executable:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _CalendarList:
    def list(self):
        return _Executable({"items": [{"id": "primary"}]})


class _Events:
    def __init__(self, items):
        self.items = items
        self.list_calls = []
        self.insert_calls = []

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        return _Executable({"items": self.items})

    def insert(self, **kwargs):
        self.insert_calls.append(kwargs)
        return _Executable({"id": "created-1"})


class _CalendarService:
    def __init__(self, items):
        self.events_resource = _Events(items)

    def calendarList(self):
        return _CalendarList()

    def events(self):
        return self.events_resource


def test_private_calendar_events_are_ignored(tmp_path):
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    end = start + timedelta(hours=1)
    api = CalendarAPI(token_path=str(tmp_path / "calendar_token.json"))
    api.calendar_service = _CalendarService(
        [
            {
                "id": "private-1",
                "summary": "Sensitive appointment",
                "visibility": "private",
                "start": {"dateTime": start.isoformat()},
                "end": {"dateTime": end.isoformat()},
            },
            {
                "id": "public-1",
                "summary": "Public meeting",
                "start": {"dateTime": start.isoformat()},
                "end": {"dateTime": end.isoformat()},
            },
        ]
    )

    events = api.get_events(days=1)

    assert [event.id for event in events] == ["public-1"]


def test_get_events_uses_user_timezone_window(tmp_path):
    service = _CalendarService([])
    api = CalendarAPI(
        token_path=str(tmp_path / "calendar_token.json"),
        user_timezone="America/Phoenix",
    )
    api.calendar_service = service

    api.get_events(days=7)

    call = service.events_resource.list_calls[0]
    assert call["timeMin"].endswith("-07:00") or call["timeMin"].endswith("-06:00")
    assert call["timeMax"].endswith("-07:00") or call["timeMax"].endswith("-06:00")


def test_create_event_uses_user_timezone(tmp_path):
    service = _CalendarService([])
    api = CalendarAPI(
        token_path=str(tmp_path / "calendar_token.json"),
        user_timezone="America/Phoenix",
        suggest_only=False,
    )
    api.calendar_service = service
    api.target_calendar_id = "primary"
    from tools.calendar_api import CalendarEvent

    start = datetime(2026, 5, 1, 7, 0)
    end = datetime(2026, 5, 1, 7, 30)
    event_id = api.create_event(CalendarEvent(None, "Walk", "", start, end))

    assert event_id == "created-1"
    body = service.events_resource.insert_calls[0]["body"]
    assert body["start"]["timeZone"] == "America/Phoenix"


def test_primary_calendar_is_default_write_target(tmp_path):
    api = CalendarAPI(token_path=str(tmp_path / "calendar_token.json"))

    assert api.get_target_calendar_id() == "primary"
