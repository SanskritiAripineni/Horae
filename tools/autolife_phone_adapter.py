"""
AutoLife Phone Adapter
Extracts behavioral marker values from AutoLife journal text using Gemini,
producing raw_day dicts suitable for WellbeingSensor.analyze().
"""

import datetime
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MARKER_KEYS = [
    "sleep_onset_hour",
    "sleep_duration_hours",
    "sleep_regularity_index",
    "late_night_screen_min",
    "total_screen_min",
    "app_switching_rate",
    "mobility_entropy",
    "location_revisit_ratio",
    "social_rhythm_metric",
    "comm_reciprocity",
]

_NULL_MARKERS: Dict[str, None] = {k: None for k in _MARKER_KEYS}

_MARKER_RANGES: Dict[str, tuple] = {
    "sleep_onset_hour": (0.0, 30.0),
    "sleep_duration_hours": (0.5, 16.0),
    "sleep_regularity_index": (0.0, 100.0),
    "late_night_screen_min": (0.0, 360.0),
    "total_screen_min": (0.0, 960.0),
    "app_switching_rate": (0.0, 5.0),
    "mobility_entropy": (0.0, 3.5),
    "location_revisit_ratio": (0.0, 1.0),
    "social_rhythm_metric": (0.0, 1.0),
    "comm_reciprocity": (0.0, 1.0),
}

_EXTRACTION_PROMPT_TEMPLATE = """\
Extract behavioral markers from this daily journal. Return ONLY JSON, no markdown.

Journal entries for {date}:
{combined_journal_text}

Extract these markers (use null if not mentioned or unclear):
{{
  "sleep_onset_hour": <float, 24h clock, e.g. 23.5 for 11:30pm, 25.0 for 1am next day>,
  "sleep_duration_hours": <float, total sleep hours>,
  "sleep_regularity_index": <float 0-100, estimate regularity vs typical; 80=very regular, 50=moderate, 20=irregular>,
  "late_night_screen_min": <float, estimated minutes of screen use 11pm-4am>,
  "total_screen_min": <float, total screen-on minutes for the day>,
  "app_switching_rate": <float 0-3, estimated app switching per active minute; 0.3=focused, 1.0=moderate, 2.5=very fragmented>,
  "mobility_entropy": <float 0-2.5, location variety; 0.5=stayed home, 1.2=few places, 2.0=many distinct places>,
  "location_revisit_ratio": <float 0-1, fraction of time at familiar places; 0.9=mostly home/usual, 0.5=lots of new places>,
  "social_rhythm_metric": <float 0-1, how regular/structured the day felt; 1.0=very structured, 0.3=unstructured>,
  "comm_reciprocity": <float 0-1, outgoing vs total communication; 0.5=balanced, 0.8=mostly initiating, 0.2=mostly receiving>
}}

Be conservative — only estimate markers clearly implied by the text. Use null for markers with no textual evidence.\
"""


class AutoLifePhoneAdapter:
    """
    Converts AutoLife journal entries into raw_day dicts for WellbeingSensor.

    For each calendar date represented in the journals, a single Gemini call
    extracts approximate behavioral marker values from the narrative text.
    When Gemini is unavailable (no API key), all sensor fields are returned as
    None — WellbeingSensor handles low-coverage gracefully.
    """

    def __init__(self, llm_client: Any) -> None:
        """
        Parameters
        ----------
        llm_client:
            An LLMClient instance.  Uses llm_client.generate() and
            llm_client._parse_json_response().
        """
        self.llm_client = llm_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def journals_to_raw_days(self, journals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert a list of journal dicts to a list of raw_day dicts.

        Parameters
        ----------
        journals:
            Output of AutoLifeReader.read_journals() — each dict contains at
            minimum ``created_at`` (str "YYYY-MM-DD HH:MM:SS"), ``period``
            (str), and ``content`` (str).

        Returns
        -------
        List of raw_day dicts sorted by date ascending.  Each dict has a
        ``date`` key (datetime.date) plus the 10 behavioral marker keys.
        """
        if not journals:
            return []

        grouped = self._group_by_date(journals)

        raw_days: List[Dict[str, Any]] = []
        for date_obj, day_journals in sorted(grouped.items()):
            combined_text = self._combine_journal_text(day_journals, max_chars=2000)
            markers = self._extract_markers(date_obj, combined_text)
            raw_days.append({"date": date_obj, **markers})

        return raw_days

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _group_by_date(
        self, journals: List[Dict[str, Any]]
    ) -> Dict[datetime.date, List[Dict[str, Any]]]:
        """Group journals by calendar date parsed from created_at."""
        grouped: Dict[datetime.date, List[Dict[str, Any]]] = {}
        for journal in journals:
            created_at = journal.get("created_at", "")
            date_obj = self._parse_date(created_at)
            if date_obj is None:
                logger.warning("Could not parse date from created_at=%r, skipping entry", created_at)
                continue
            grouped.setdefault(date_obj, []).append(journal)

        # Sort entries within each day by created_at
        for date_obj in grouped:
            grouped[date_obj].sort(key=lambda j: j.get("created_at", ""))

        return grouped

    @staticmethod
    def _parse_date(created_at: str) -> Optional[datetime.date]:
        """Parse a 'YYYY-MM-DD HH:MM:SS' string to a date object."""
        if not created_at:
            return None
        try:
            return datetime.datetime.strptime(created_at.strip(), "%Y-%m-%d %H:%M:%S").date()
        except ValueError:
            # Fallback: try ISO format with T separator
            try:
                return datetime.date.fromisoformat(created_at.strip()[:10])
            except ValueError:
                return None

    @staticmethod
    def _combine_journal_text(
        day_journals: List[Dict[str, Any]], max_chars: int = 2000
    ) -> str:
        """Concatenate journal content for one day, capped at max_chars."""
        parts: List[str] = []
        total = 0
        for journal in day_journals:
            period = journal.get("period", "")
            content = journal.get("content", "").strip()
            if not content:
                continue
            segment = f"[{period}]\n{content}" if period else content
            if total + len(segment) > max_chars:
                remaining = max_chars - total
                if remaining > 50:
                    parts.append(segment[:remaining])
                break
            parts.append(segment)
            total += len(segment)
        return "\n\n".join(parts)

    def _extract_markers(
        self, date_obj: datetime.date, combined_text: str
    ) -> Dict[str, Optional[float]]:
        """Call Gemini to extract markers from journal text for one day.

        Returns a dict with all 10 marker keys.  Values are float or None.
        On any failure (no client, bad JSON, missing keys) falls back to all None.
        """
        if self.llm_client.client is None:
            logger.debug("No Gemini client available; returning null markers for %s", date_obj)
            return dict(_NULL_MARKERS)

        if not combined_text.strip():
            logger.debug("No journal text for %s; returning null markers", date_obj)
            return dict(_NULL_MARKERS)

        prompt = _EXTRACTION_PROMPT_TEMPLATE.format(
            date=date_obj.isoformat(),
            combined_journal_text=combined_text,
        )

        raw_response = self.llm_client.generate(prompt)
        if not raw_response:
            logger.warning("Empty response from Gemini for date %s", date_obj)
            return dict(_NULL_MARKERS)

        parsed = self.llm_client._parse_json_response(raw_response, default=None)
        if not isinstance(parsed, dict):
            logger.warning("Non-dict JSON response for date %s; using null markers", date_obj)
            return dict(_NULL_MARKERS)

        markers: Dict[str, Optional[float]] = {}
        for key in _MARKER_KEYS:
            raw_val = parsed.get(key)
            if raw_val is None:
                markers[key] = None
            else:
                try:
                    markers[key] = float(raw_val)
                except (TypeError, ValueError):
                    logger.debug("Non-numeric value for marker %r on %s: %r", key, date_obj, raw_val)
                    markers[key] = None

        # clamp to valid domain ranges
        for key in _MARKER_KEYS:
            if markers[key] is not None:
                lo, hi = _MARKER_RANGES[key]
                original = markers[key]
                markers[key] = max(lo, min(hi, original))
                if markers[key] != original:
                    logger.debug("Clamped marker %r from %.2f to %.2f for date %s", key, original, markers[key], date_obj)

        return markers
