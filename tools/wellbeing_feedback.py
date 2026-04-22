"""
WellbeingFeedback — lightweight JSONL store for suggestion outcomes.

Records whether a proposed calendar change was accepted, rejected, modified,
or never shown (no-show).  Storage is line-delimited JSON under
``data/wellbeing_feedback/{user_id}.jsonl``.

Usage
-----
    fb = WellbeingFeedback()
    fb.record("alice", "Add Wind-down block at 22:30", "accept", "behavioral-withdrawal")
    history = fb.get_history("alice", n=10)
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

# Default storage location relative to the project root.
_DEFAULT_DIR = Path(__file__).parent.parent / "data" / "wellbeing_feedback"

VALID_ACTIONS = {"accept", "reject", "modify", "no-show"}


class WellbeingFeedback:
    """Persists user feedback on wellbeing calendar suggestions.

    Parameters
    ----------
    storage_dir:
        Directory where per-user ``.jsonl`` files are stored.  Created
        automatically if it does not exist.
    """

    def __init__(self, storage_dir: Path | str | None = None):
        self.storage_dir = Path(storage_dir or _DEFAULT_DIR)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _path(self, user_id: str) -> Path:
        # Sanitise user_id so it cannot escape the storage directory.
        safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in user_id)
        return self.storage_dir / f"{safe}.jsonl"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        user_id: str,
        suggestion: str,
        action: str,
        behavioral_state_summary: str,
    ) -> None:
        """Append one feedback record to the user's JSONL file.

        Parameters
        ----------
        user_id:
            Identifier for the user (string).
        suggestion:
            The ``change`` text from the Layer 4 / calendar suggestion.
        action:
            One of ``accept``, ``reject``, ``modify``, ``no-show``.
        behavioral_state_summary:
            Short string describing the behavioral state at the time of the
            suggestion (e.g. the Layer 3 prose truncated to ~200 chars, or
            the pattern names that motivated it).
        """
        if action not in VALID_ACTIONS:
            logger.warning(
                "WellbeingFeedback.record: unknown action %r — recording anyway", action
            )

        record = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "suggestion_change": suggestion,
            "action": action,
            "behavioral_summary": behavioral_state_summary,
        }

        path = self._path(user_id)
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.error("Failed to write feedback for user %r: %s", user_id, exc)

    def get_history(self, user_id: str, n: int = 10) -> List[dict]:
        """Return the most recent *n* feedback records for a user.

        Returns an empty list if the file does not exist yet.
        """
        path = self._path(user_id)
        if not path.exists():
            return []

        records: List[dict] = []
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            logger.warning(
                                "Skipping malformed feedback line in %s", path
                            )
        except OSError as exc:
            logger.error("Failed to read feedback for user %r: %s", user_id, exc)
            return []

        # Return the last n entries (most recent).
        return records[-n:] if len(records) > n else records
