"""
Database module — Postgres connection pool, schema init, and event logging.
All user_ids are SHA-256 hashed before storage (anonymized).
If DATABASE_URL is not set or Postgres is unreachable, all functions no-op
so the API keeps working even if the DB is down.

RESEARCH-READINESS AUDIT (2026-04-10):
  Anonymization coverage:
    - log_session(): hashes user_id at entry → used for users, journal_sessions,
      mental_health_assessments, raw_journals, and calendar_proposals tables. OK.
    - log_calendar_accepted(): hashes user_id at entry → used for UPDATE query. OK.
    - anon_id() is deterministic (SHA-256 of raw string) — same user always maps
      to same hash. OK.
  PII in other columns:
    - raw_journals.content: Gemini-generated narrative from sensor fusion, not raw
      sensor data. May contain place names inferred by the LLM but no coordinates.
    - journal_sessions.journal_summary: LLM-generated summary. Same as above.
    - recommendations: clinical action items, no user PII.
    - calendar_proposals.proposed_changes: event titles/times, no direct PII.
    - calendar_proposals.user_comments: free-text from user — could theoretically
      contain self-identifying info. Acceptable for informed-consent research.
  No code path stores raw (unhashed) user_id in any database column.
"""

import hashlib
import json
import logging
import os
import uuid
from typing import List, Dict, Any, Optional

import psycopg2
from psycopg2 import pool as pg_pool

logger = logging.getLogger(__name__)

_pool: Optional[pg_pool.ThreadedConnectionPool] = None


def get_pool() -> Optional[pg_pool.ThreadedConnectionPool]:
    global _pool
    if _pool is not None:
        return _pool
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.warning("DATABASE_URL not set — data logging disabled")
        return None
    try:
        _pool = pg_pool.ThreadedConnectionPool(1, 10, db_url)
        logger.info("DB connection pool created")
    except Exception as e:
        logger.error(f"Failed to create DB pool: {e}")
    return _pool


def anon_id(user_id: str) -> str:
    """One-way SHA-256 hash of user_id — same user always gets same anon_id."""
    return hashlib.sha256(user_id.encode()).hexdigest()


def init_schema() -> None:
    """Create all tables if they don't exist. Called once at API startup."""
    p = get_pool()
    if not p:
        return
    conn = p.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    anon_id     TEXT PRIMARY KEY,
                    created_at  TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS journal_sessions (
                    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_anon_id    TEXT REFERENCES users(anon_id),
                    journal_count   INT,
                    journal_summary TEXT,
                    created_at      TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS mental_health_assessments (
                    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id          UUID REFERENCES journal_sessions(id),
                    user_anon_id        TEXT REFERENCES users(anon_id),
                    phq4_score          INT,
                    risk_level          TEXT,
                    key_concerns        JSONB,
                    positive_indicators JSONB,
                    created_at          TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS recommendations (
                    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id  UUID REFERENCES journal_sessions(id),
                    category    TEXT,
                    action      TEXT,
                    when_to_do  TEXT,
                    priority    TEXT,
                    mechanism   TEXT,
                    source      TEXT,
                    created_at  TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS calendar_proposals (
                    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id       UUID,
                    user_anon_id     TEXT,
                    proposed_changes JSONB,
                    accepted         BOOLEAN DEFAULT FALSE,
                    user_comments    TEXT,
                    created_at       TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS raw_journals (
                    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id       UUID REFERENCES journal_sessions(id),
                    user_anon_id     TEXT,
                    journal_id       TEXT,
                    entry_number     INT,
                    period           TEXT,
                    content          TEXT,
                    entry_created_at TEXT,
                    created_at       TIMESTAMPTZ DEFAULT NOW()
                );

                -- Migration: add journal_id to existing tables if not present
                ALTER TABLE raw_journals ADD COLUMN IF NOT EXISTS journal_id TEXT;

                -- Deduplicate by original journal ID per user
                CREATE UNIQUE INDEX IF NOT EXISTS raw_journals_dedup_idx
                    ON raw_journals(user_anon_id, journal_id)
                    WHERE journal_id IS NOT NULL;
            """)
        conn.commit()
        logger.info("DB schema initialized")
    except Exception as e:
        conn.rollback()
        logger.error(f"Schema init failed: {e}")
    finally:
        p.putconn(conn)


def log_session(user_id: str, journals: List[Dict], result: Dict) -> Optional[str]:
    """
    Log a full journal processing session to Postgres.
    Returns the session UUID (used to link calendar acceptance later).
    """
    p = get_pool()
    if not p:
        return None

    uid = anon_id(user_id)
    session_id = str(uuid.uuid4())
    conn = p.getconn()
    try:
        with conn.cursor() as cur:
            # Ensure user exists
            cur.execute(
                "INSERT INTO users (anon_id) VALUES (%s) ON CONFLICT DO NOTHING",
                (uid,)
            )

            # Session row
            cur.execute(
                """INSERT INTO journal_sessions (id, user_anon_id, journal_count, journal_summary)
                   VALUES (%s, %s, %s, %s)""",
                (session_id, uid, len(journals), result.get("journal_summary"))
            )

            # Mental health assessment
            mh = result.get("mental_health") or {}
            if mh:
                cur.execute(
                    """INSERT INTO mental_health_assessments
                           (session_id, user_anon_id, phq4_score, risk_level,
                            key_concerns, positive_indicators)
                       VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb)""",
                    (
                        session_id, uid,
                        mh.get("estimated_phq4"), mh.get("risk_level"),
                        json.dumps(mh.get("key_concerns", [])),
                        json.dumps(mh.get("positive_indicators", [])),
                    )
                )

            # Recommendations
            for rec in result.get("recommendations", []):
                cur.execute(
                    """INSERT INTO recommendations
                           (session_id, category, action, when_to_do,
                            priority, mechanism, source)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        session_id,
                        rec.get("category"), rec.get("action"), rec.get("when") or rec.get("when_to_do"),
                        rec.get("priority"), rec.get("mechanism"), rec.get("source"),
                    )
                )

            # Raw journal entries — skip if already stored (dedup by journal_id)
            for j in journals:
                journal_id = j.get("id")
                if journal_id:
                    cur.execute(
                        "SELECT 1 FROM raw_journals WHERE user_anon_id = %s AND journal_id = %s",
                        (uid, journal_id)
                    )
                    if cur.fetchone():
                        continue
                cur.execute(
                    """INSERT INTO raw_journals
                           (session_id, user_anon_id, journal_id, entry_number,
                            period, content, entry_created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        session_id, uid, journal_id,
                        j.get("entry_number"), j.get("period"),
                        j.get("content"), j.get("created_at"),
                    )
                )

            # Calendar proposals (marked not-yet-accepted)
            proposed = result.get("proposed_changes", [])
            if proposed:
                cur.execute(
                    """INSERT INTO calendar_proposals
                           (session_id, user_anon_id, proposed_changes, accepted)
                       VALUES (%s, %s, %s::jsonb, FALSE)""",
                    (session_id, uid, json.dumps(proposed))
                )

        conn.commit()
        logger.info(f"Logged session {session_id} for anon user {uid[:12]}…")
        return session_id

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to log session: {e}")
        return None
    finally:
        p.putconn(conn)


def log_calendar_accepted(user_id: str, user_comments: str) -> None:
    """
    Mark the most recent calendar proposal for this user as accepted.
    Called when the user confirms calendar changes from the Android app.
    """
    p = get_pool()
    if not p:
        return

    uid = anon_id(user_id)
    conn = p.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE calendar_proposals
                   SET accepted = TRUE, user_comments = %s
                   WHERE id = (
                       SELECT id FROM calendar_proposals
                       WHERE user_anon_id = %s
                       ORDER BY created_at DESC
                       LIMIT 1
                   )""",
                (user_comments, uid)
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to log calendar acceptance: {e}")
    finally:
        p.putconn(conn)
