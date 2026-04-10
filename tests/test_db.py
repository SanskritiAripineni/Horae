"""
Tests for db.py — Postgres logging with graceful degradation.

All Postgres calls are mocked. Tests cover:
- SHA-256 anonymization (anon_id)
- Graceful no-op when DATABASE_URL is unset
- log_session() and log_calendar_accepted() with mocked pool
- init_schema() error handling
"""

import hashlib
import pytest
from unittest.mock import patch, MagicMock

import db


# ---------------------------------------------------------------------------
# anon_id — SHA-256 anonymization
# ---------------------------------------------------------------------------

class TestAnonId:

    def test_deterministic(self):
        """Same user_id always produces the same hash."""
        assert db.anon_id("alice") == db.anon_id("alice")

    def test_different_inputs_different_hashes(self):
        assert db.anon_id("alice") != db.anon_id("bob")

    def test_matches_manual_sha256(self):
        expected = hashlib.sha256("test_user".encode()).hexdigest()
        assert db.anon_id("test_user") == expected

    def test_handles_empty_string(self):
        result = db.anon_id("")
        assert isinstance(result, str)
        assert len(result) == 64  # SHA-256 hex length

    def test_handles_unicode(self):
        result = db.anon_id("user_with_unicode_\u00e9")
        assert isinstance(result, str)
        assert len(result) == 64


# ---------------------------------------------------------------------------
# get_pool — graceful degradation
# ---------------------------------------------------------------------------

class TestGetPool:

    def test_returns_none_when_database_url_unset(self):
        # Reset the module-level _pool so get_pool() actually runs
        db._pool = None
        with patch.dict("os.environ", {}, clear=True):
            pool = db.get_pool()
            assert pool is None

    @patch("db.pg_pool.ThreadedConnectionPool")
    def test_creates_pool_when_url_set(self, mock_pool_cls):
        db._pool = None
        mock_pool_instance = MagicMock()
        mock_pool_cls.return_value = mock_pool_instance

        with patch.dict("os.environ", {"DATABASE_URL": "postgres://fake"}, clear=False):
            pool = db.get_pool()
            assert pool is mock_pool_instance

        # Clean up for other tests
        db._pool = None

    @patch("db.pg_pool.ThreadedConnectionPool")
    def test_returns_none_on_connection_error(self, mock_pool_cls):
        db._pool = None
        mock_pool_cls.side_effect = Exception("connection refused")

        with patch.dict("os.environ", {"DATABASE_URL": "postgres://fake"}, clear=False):
            pool = db.get_pool()
            assert pool is None

        db._pool = None


# ---------------------------------------------------------------------------
# init_schema
# ---------------------------------------------------------------------------

class TestInitSchema:

    def test_no_op_when_pool_is_none(self):
        """Should not raise when there is no DB connection."""
        db._pool = None
        with patch.dict("os.environ", {}, clear=True):
            db.init_schema()  # should simply return without error

    @patch("db.get_pool")
    def test_executes_create_tables(self, mock_get_pool):
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        db.init_schema()

        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_pool.putconn.assert_called_once_with(mock_conn)

    @patch("db.get_pool")
    def test_rollback_on_error(self, mock_get_pool):
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("SQL error")
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        db.init_schema()  # should not raise

        mock_conn.rollback.assert_called_once()
        mock_pool.putconn.assert_called_once_with(mock_conn)


# ---------------------------------------------------------------------------
# log_session
# ---------------------------------------------------------------------------

class TestLogSession:

    def test_returns_none_when_pool_is_none(self):
        with patch("db.get_pool", return_value=None):
            result = db.log_session("user1", [], {})
            assert result is None

    @patch("db.get_pool")
    def test_logs_session_successfully(self, mock_get_pool):
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # fetchone returns None (no duplicate) for raw_journals dedup check
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        journals = [
            {"id": "j1", "entry_number": 1, "period": "Morning",
             "content": "test", "created_at": "2024-01-01"},
        ]
        result_data = {
            "journal_summary": "summary",
            "mental_health": {
                "estimated_phq4": 3,
                "risk_level": "mild",
                "key_concerns": [],
                "positive_indicators": [],
            },
            "recommendations": [
                {"category": "Sleep", "action": "sleep more",
                 "when": "night", "priority": "high",
                 "mechanism": "rest", "source": "study"},
            ],
            "proposed_changes": [{"action": "add", "title": "Walk"}],
        }

        session_id = db.log_session("user1", journals, result_data)
        assert session_id is not None
        mock_conn.commit.assert_called_once()

    @patch("db.get_pool")
    def test_returns_none_on_db_error(self, mock_get_pool):
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("insert failed")
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        result = db.log_session("user1", [], {})
        assert result is None
        mock_conn.rollback.assert_called_once()

    @patch("db.get_pool")
    def test_deduplicates_journals_by_id(self, mock_get_pool):
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # Simulate the journal already existing in DB
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        journals = [{"id": "j1", "entry_number": 1, "period": "AM",
                      "content": "x", "created_at": "2024-01-01"}]
        result_data = {"mental_health": {}, "recommendations": [], "proposed_changes": []}

        db.log_session("user1", journals, result_data)

        # The INSERT INTO raw_journals should NOT be called for the duplicate
        # Count how many times execute was called — if dedup works, it should skip the raw_journals insert
        execute_calls = mock_cursor.execute.call_args_list
        # Should have: INSERT users, INSERT journal_sessions, SELECT dedup check
        # but NOT the INSERT raw_journals
        raw_journal_inserts = [c for c in execute_calls
                               if "INSERT INTO raw_journals" in str(c)]
        assert len(raw_journal_inserts) == 0


# ---------------------------------------------------------------------------
# log_calendar_accepted
# ---------------------------------------------------------------------------

class TestLogCalendarAccepted:

    def test_no_op_when_pool_is_none(self):
        with patch("db.get_pool", return_value=None):
            db.log_calendar_accepted("user1", "looks good")  # should not raise

    @patch("db.get_pool")
    def test_updates_most_recent_proposal(self, mock_get_pool):
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        db.log_calendar_accepted("user1", "approved")

        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "UPDATE calendar_proposals" in sql
        assert "accepted = TRUE" in sql
        mock_conn.commit.assert_called_once()

    @patch("db.get_pool")
    def test_rollback_on_error(self, mock_get_pool):
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("update failed")
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        db.log_calendar_accepted("user1", "")  # should not raise
        mock_conn.rollback.assert_called_once()
