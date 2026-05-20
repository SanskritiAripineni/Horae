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

    def list(self, **kwargs):
        return _Executable({"items": self.items})


class _CalendarService:
    def __init__(self, items):
        self.items = items

    def calendarList(self):
        return _CalendarList()

    def events(self):
        return _Events(self.items)


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
