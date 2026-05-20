"""
Tests for api.py — FastAPI endpoint layer.

Uses fastapi.testclient.TestClient with api.agent_instance replaced by a
MagicMock so the endpoint wiring, validation, and error handling can be
exercised without running the real multi-agent pipeline.

Coverage:
- GET  /health
- POST /api/process_journals — happy path, validation (missing/empty/blank),
  empty content, 503 when agent not initialized, pipeline 500, db.log_session
  failure is swallowed (regression guard for cb9f9ac).
- POST /api/apply_calendar — happy path, empty-changes rejection, delegation,
  per-change failure containment, 503 when agent not initialized.
- GET  /api/memory — happy path, default user_id, retrieval failure → 500.
"""

from unittest.mock import MagicMock, patch
from datetime import timedelta
import json

import pytest
from fastapi.testclient import TestClient

import api


@pytest.fixture
def mock_agent():
    """Install a MagicMock at api.agent_instance for the duration of the test."""
    original = api.agent_instance
    mock = MagicMock()
    api.agent_instance = mock
    try:
        yield mock
    finally:
        api.agent_instance = original


@pytest.fixture
def client(mock_agent, monkeypatch):
    monkeypatch.setenv("API_SECRET_KEY", "test-secret")
    return TestClient(api.app)


def auth_headers(user_id="default"):
    return {"Authorization": f"Bearer {api._make_user_token(user_id)}"}


def signed_changes(changes):
    return [api._sign_change(change) for change in changes]


@pytest.fixture
def valid_journals_payload(sample_journals):
    return {"journals": sample_journals, "user_id": "test-user"}


@pytest.fixture
def sample_pipeline_result():
    return {
        "status": "completed",
        "user_id": "test-user",
        "journal_count": 2,
        "wellbeing": {"risk_level": "mild"},
        "mental_health": {"risk_level": "mild"},
        "recommendations": [],
        "proposed_changes": [],
        "behavioral_sensing": None,
        "errors": [],
        "duration_seconds": 1.0,
    }


# /health

class TestHealth:
    def test_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


# /api/process_journals

class TestProcessJournals:

    def test_happy_path(self, client, mock_agent, valid_journals_payload, sample_pipeline_result):
        mock_agent.run_from_journals.return_value = sample_pipeline_result

        with patch("api.db.log_session") as log_session:
            response = client.post(
                "/api/process_journals",
                json=valid_journals_payload,
                headers=auth_headers("test-user"),
            )

        assert response.status_code == 200
        assert response.json() == sample_pipeline_result
        mock_agent.run_from_journals.assert_called_once()
        # Args: journals list, user_id, raw_days
        args, _ = mock_agent.run_from_journals.call_args
        assert args[1] == "test-user"
        assert args[2] is None
        log_session.assert_called_once()

    def test_raw_days_forwarded(self, client, mock_agent, sample_journals, sample_pipeline_result):
        mock_agent.run_from_journals.return_value = sample_pipeline_result
        raw_days = [{"date": "2026-04-20", "sleep_onset_hour": 23.5}]
        payload = {"journals": sample_journals, "user_id": "u1", "raw_days": raw_days}

        with patch("api.db.log_session"):
            response = client.post(
                "/api/process_journals", json=payload, headers=auth_headers("u1")
            )

        assert response.status_code == 200
        args, _ = mock_agent.run_from_journals.call_args
        # model_dump() fills optional fields with None; assert the set fields only
        forwarded = args[2]
        assert forwarded is not None and len(forwarded) == 1
        assert forwarded[0]["date"] == "2026-04-20"
        assert forwarded[0]["sleep_onset_hour"] == 23.5

    def test_default_user_id(self, client, mock_agent, sample_journals, sample_pipeline_result):
        mock_agent.run_from_journals.return_value = sample_pipeline_result

        with patch("api.db.log_session"):
            response = client.post(
                "/api/process_journals",
                json={"journals": sample_journals},
                headers=auth_headers(),
            )

        assert response.status_code == 200
        args, _ = mock_agent.run_from_journals.call_args
        assert args[1] == "default"

    def test_missing_journals_key_is_422(self, client):
        response = client.post(
            "/api/process_journals", json={"user_id": "u"}, headers=auth_headers("u")
        )
        assert response.status_code == 422
        assert response.json()["error"] == "validation_error"

    def test_empty_journals_list_is_422(self, client):
        response = client.post(
            "/api/process_journals", json={"journals": []}, headers=auth_headers()
        )
        assert response.status_code == 422
        assert response.json()["error"] == "validation_error"

    def test_blank_user_id_is_422(self, client, sample_journals):
        response = client.post(
            "/api/process_journals",
            json={"journals": sample_journals, "user_id": "   "},
            headers=auth_headers(),
        )
        assert response.status_code == 422

    def test_empty_content_journal_is_422(self, client, sample_journals):
        bad = dict(sample_journals[0])
        bad["content"] = "   "
        response = client.post(
            "/api/process_journals",
            json={"journals": [bad, sample_journals[1]]},
            headers=auth_headers(),
        )
        assert response.status_code == 422
        assert "empty content" in str(response.json()["detail"]).lower()

    def test_agent_not_initialized_returns_503(self, client, valid_journals_payload):
        original = api.agent_instance
        api.agent_instance = None
        try:
            response = client.post(
                "/api/process_journals",
                json=valid_journals_payload,
                headers=auth_headers("test-user"),
            )
        finally:
            api.agent_instance = original
        assert response.status_code == 503

    def test_pipeline_exception_returns_500(self, client, mock_agent, valid_journals_payload):
        mock_agent.run_from_journals.side_effect = RuntimeError("pipeline boom")

        response = client.post(
            "/api/process_journals",
            json=valid_journals_payload,
            headers=auth_headers("test-user"),
        )

        assert response.status_code == 500
        assert response.json()["error"] == "http_error"

    def test_db_log_failure_is_swallowed(
        self, client, mock_agent, valid_journals_payload, sample_pipeline_result
    ):
        """Regression guard for cb9f9ac: Postgres outages must not break responses."""
        mock_agent.run_from_journals.return_value = sample_pipeline_result

        with patch("api.db.log_session", side_effect=Exception("DB is down")):
            response = client.post(
                "/api/process_journals",
                json=valid_journals_payload,
                headers=auth_headers("test-user"),
            )

        assert response.status_code == 200
        assert response.json() == sample_pipeline_result

    def test_timedelta_response_values_are_json_safe(
        self, client, mock_agent, valid_journals_payload, sample_pipeline_result
    ):
        result = dict(sample_pipeline_result)
        result["analysis_details"] = {"duration_seconds": timedelta(seconds=2)}
        mock_agent.run_from_journals.return_value = result

        with patch("api.db.log_session"):
            response = client.post(
                "/api/process_journals",
                json=valid_journals_payload,
                headers=auth_headers("test-user"),
            )

        assert response.status_code == 200
        assert response.json()["analysis_details"]["duration_seconds"] == 2.0


# /api/apply_calendar

class TestApplyCalendar:

    def test_happy_path(self, client, mock_agent):
        mock_agent.apply_calendar_changes.return_value = {
            "applied": [{"action": "created", "event_id": "e1"}],
            "failed": [],
            "skipped": [],
        }
        changes = [
            {
                "action": "add",
                "title": "Meditate",
                "start_time": "2026-05-01T07:00:00",
                "end_time": "2026-05-01T07:15:00",
            }
        ]
        signed = signed_changes(changes)

        with patch("api.db.log_calendar_accepted") as log_cal:
            response = client.post(
                "/api/apply_calendar",
                json={
                    "changes": signed,
                    "user_id": "u1",
                    "user_comments": "thanks",
                },
                headers=auth_headers("u1"),
            )

        assert response.status_code == 200
        assert response.json()["applied"][0]["event_id"] == "e1"
        mock_agent.apply_calendar_changes.assert_called_once_with(
            signed,
            "thanks",
            None,
            user_id="u1",
        )
        log_cal.assert_called_once()

    def test_empty_changes_is_422(self, client):
        response = client.post(
            "/api/apply_calendar", json={"changes": []}, headers=auth_headers()
        )
        assert response.status_code == 422

    def test_missing_changes_is_422(self, client):
        response = client.post(
            "/api/apply_calendar", json={"user_id": "u"}, headers=auth_headers("u")
        )
        assert response.status_code == 422

    def test_per_change_failures_do_not_500(self, client, mock_agent):
        """If the calendar reports a per-change failure, the endpoint still returns 200."""
        mock_agent.apply_calendar_changes.return_value = {
            "applied": [],
            "failed": [{"error": "calendar offline", "change": {}}],
            "skipped": [],
        }

        with patch("api.db.log_calendar_accepted"):
            response = client.post(
                "/api/apply_calendar",
                json={"changes": signed_changes([{"action": "add"}])},
                headers=auth_headers(),
            )

        assert response.status_code == 200
        assert len(response.json()["failed"]) == 1

    def test_agent_not_initialized_returns_503(self, client):
        original = api.agent_instance
        api.agent_instance = None
        try:
            response = client.post(
                "/api/apply_calendar",
                json={"changes": signed_changes([{"action": "add"}])},
                headers=auth_headers(),
            )
        finally:
            api.agent_instance = original
        assert response.status_code == 503

    def test_apply_exception_returns_500(self, client, mock_agent):
        mock_agent.apply_calendar_changes.side_effect = RuntimeError("calendar api down")
        response = client.post(
            "/api/apply_calendar",
            json={"changes": signed_changes([{"action": "add"}])},
            headers=auth_headers(),
        )
        assert response.status_code == 500

    def test_db_log_failure_is_swallowed(self, client, mock_agent):
        mock_agent.apply_calendar_changes.return_value = {"applied": [], "failed": [], "skipped": []}

        with patch("api.db.log_calendar_accepted", side_effect=Exception("DB down")):
            response = client.post(
                "/api/apply_calendar",
                json={"changes": signed_changes([{"action": "add"}])},
                headers=auth_headers(),
            )

        assert response.status_code == 200


# /api/memory

class TestMemory:

    def test_happy_path(self, client, mock_agent):
        mock_agent.memory.get_user_context.return_value = {
            "preferences": {"work_hours": "9-5"},
            "wellbeing": {"latest_risk_level": "minimal"},
        }
        mock_agent.memory.wellbeing_tracker.get_history.return_value = [
            {"date": "2026-04-20", "risk_level": "minimal"},
        ]

        response = client.get(
            "/api/memory", params={"user_id": "u1"}, headers=auth_headers("u1")
        )

        assert response.status_code == 200
        body = response.json()
        assert body["preferences"]["work_hours"] == "9-5"
        assert body["wellbeing"]["history"][0]["date"] == "2026-04-20"
        mock_agent.memory.get_user_context.assert_called_once_with("u1")
        mock_agent.memory.wellbeing_tracker.get_history.assert_called_once_with("u1")

    def test_default_user_id(self, client, mock_agent):
        mock_agent.memory.get_user_context.return_value = {"wellbeing": {}}
        mock_agent.memory.wellbeing_tracker.get_history.return_value = []

        response = client.get("/api/memory", headers=auth_headers())

        assert response.status_code == 200
        mock_agent.memory.get_user_context.assert_called_once_with("default")

    def test_agent_not_initialized_returns_503(self, client):
        original = api.agent_instance
        api.agent_instance = None
        try:
            response = client.get(
                "/api/memory", params={"user_id": "u1"}, headers=auth_headers("u1")
            )
        finally:
            api.agent_instance = original
        assert response.status_code == 503

    def test_retrieval_failure_returns_500(self, client, mock_agent):
        mock_agent.memory.get_user_context.side_effect = RuntimeError("memory store broken")
        response = client.get(
            "/api/memory", params={"user_id": "u1"}, headers=auth_headers("u1")
        )
        assert response.status_code == 500


class TestAuth:

    def test_protected_endpoint_requires_server_secret(self, client, monkeypatch):
        monkeypatch.delenv("API_SECRET_KEY", raising=False)

        response = client.get("/api/memory", params={"user_id": "u1"})

        assert response.status_code == 503
        assert "API_SECRET_KEY" in response.json()["detail"]

    def test_token_user_must_match_body_user(self, client, sample_journals):
        response = client.post(
            "/api/process_journals",
            json={"journals": sample_journals, "user_id": "u2"},
            headers=auth_headers("u1"),
        )

        assert response.status_code == 403


class TestOAuthTokenRoutes:

    def test_status_requires_matching_token_user(self, client):
        response = client.get(
            "/api/oauth/status",
            params={"user_id": "u2"},
            headers=auth_headers("u1"),
        )

        assert response.status_code == 403

    def test_status_uses_hashed_token_path(self, client, tmp_path):
        token_path = tmp_path / "hashed" / "calendar_token.json"
        token_path.parent.mkdir()
        token_path.write_text("{}")
        legacy_path = tmp_path / "legacy" / "calendar_token.json"

        with patch("api.calendar_token_path_for_user", return_value=token_path), patch(
            "api.legacy_calendar_token_path_for_user", return_value=legacy_path
        ):
            response = client.get(
                "/api/oauth/status",
                params={"user_id": "u1"},
                headers=auth_headers("u1"),
            )

        assert response.status_code == 200
        assert response.json() == {"connected": True}

    def test_token_delete_removes_canonical_and_legacy_paths(self, client, tmp_path):
        token_path = tmp_path / "hashed" / "calendar_token.json"
        legacy_path = tmp_path / "legacy" / "calendar_token.json"
        token_path.parent.mkdir()
        legacy_path.parent.mkdir()
        token_path.write_text("{}")
        legacy_path.write_text("{}")

        with patch("api.calendar_token_path_for_user", return_value=token_path), patch(
            "api.legacy_calendar_token_path_for_user", return_value=legacy_path
        ):
            response = client.delete(
                "/api/oauth/token",
                params={"user_id": "u1"},
                headers=auth_headers("u1"),
            )

        assert response.status_code == 200
        assert not token_path.exists()
        assert not legacy_path.exists()

    def test_callback_stores_token_without_client_secret_or_raw_user_dir(
        self, client, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "credentials.json").write_text(
            json.dumps(
                {
                    "web": {
                        "client_id": "client-id",
                        "client_secret": "client-secret",
                    }
                }
            )
        )
        user_id = api._sanitize_user_id("alice@example.com")
        state, _ = api._new_oauth_state(user_id)

        token_response = MagicMock()
        token_response.json.return_value = {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "scope": "https://www.googleapis.com/auth/calendar",
        }
        with patch("httpx.post", return_value=token_response):
            response = client.get(
                "/api/oauth/callback",
                params={"code": "code", "state": state},
            )

        assert response.status_code == 200
        token_path = tmp_path / api.calendar_token_path_for_user(user_id)
        token_data = json.loads(token_path.read_text())
        assert token_data["client_id"] == "client-id"
        assert "client_secret" not in token_data
        assert user_id not in str(token_path.relative_to(tmp_path))
