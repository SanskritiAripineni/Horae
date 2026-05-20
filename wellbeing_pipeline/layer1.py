"""
Layer 1 — Personal baseline + wellbeing-validated daily markers.

Key ideas:
- No cross-user training. Each user is their own reference.
- Markers are standard constructs from the sleep/chronobiology/passive-sensing
  literature (SRI, mobility entropy, social rhythm metric, etc.), so the
  claims the LLM builds on are grounded, not speculative.
- Coverage is tracked per marker so downstream layers can reason about
  uncertainty instead of silently imputing.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional
import numpy as np

# Wellbeing-relevant markers with literature anchors.
# Add/replace freely; Layer 2 is marker-agnostic.
MARKER_SPECS = {
    "sleep_onset_hour":        {"domain": "sleep",    "unit": "hour_of_day",
                                "note": "Fractional hour [0,24); values >24 allowed for post-midnight",
                                "min_robust_std": 0.5},
    "sleep_duration_hours":    {"domain": "sleep",    "unit": "hours",
                                "min_robust_std": 0.4},
    "sleep_regularity_index":  {"domain": "sleep",    "unit": "0-100",
                                "note": "Phillips et al. 2017; higher = more consistent",
                                "min_robust_std": 5.0},
    "late_night_screen_min":   {"domain": "screen",   "unit": "minutes",
                                "note": "Screen-on time 23:00–04:00",
                                "min_robust_std": 15.0},
    "total_screen_min":        {"domain": "screen",   "unit": "minutes",
                                "min_robust_std": 30.0},
    "app_switching_rate":      {"domain": "screen",   "unit": "switches/active-min",
                                "note": "Fragmented attention proxy",
                                "min_robust_std": 0.25},
    "mobility_entropy":        {"domain": "mobility", "unit": "nats",
                                "note": "Shannon entropy of dwell time across locations",
                                "min_robust_std": 0.15},
    "location_revisit_ratio":  {"domain": "mobility", "unit": "fraction",
                                "note": "Fraction of time at top-3 most-visited places",
                                "min_robust_std": 0.08},
    "social_rhythm_metric":    {"domain": "social",   "unit": "0-1",
                                "note": "Monk et al. SRM; consistency of routine event times",
                                "min_robust_std": 0.08},
    "comm_reciprocity":        {"domain": "social",   "unit": "ratio",
                                "note": "outgoing / (outgoing + incoming) messages",
                                "min_robust_std": 0.1},
}

DOMAIN_OF = {m: spec["domain"] for m, spec in MARKER_SPECS.items()}


def _scaled_mad(values: np.ndarray) -> float:
    med = float(np.median(values))
    mad = float(np.median(np.abs(values - med)))
    return 1.4826 * mad


@dataclass
class DayRecord:
    day: date
    markers: dict           # {marker_name: float}
    coverage: dict          # {marker_name: float in [0,1]}

    def has(self, marker: str, min_cov: float = 0.5) -> bool:
        return marker in self.markers and self.coverage.get(marker, 0.0) >= min_cov


class PersonalBaseline:
    """Holds one user's daily history. Computes stats on demand, no training."""
    def __init__(self, warmup_days: int = 10):
        self.history: list[DayRecord] = []
        self.warmup_days = warmup_days

    def add(self, rec: DayRecord) -> None:
        self.history.append(rec)
        self.history.sort(key=lambda r: r.day)

    def is_warm(self) -> bool:
        return len(self.history) >= self.warmup_days

    def window(self, days_back: int, end_exclusive: Optional[date] = None) -> list[DayRecord]:
        if not self.history:
            return []
        if end_exclusive is None:
            end_exclusive = self.history[-1].day + timedelta(days=1)
        start = end_exclusive - timedelta(days=days_back)
        return [r for r in self.history if start <= r.day < end_exclusive]

    def stats(self, marker: str, days_back: int = 28,
              end_exclusive: Optional[date] = None) -> Optional[dict]:
        recs = self.window(days_back, end_exclusive)
        vals = [r.markers[marker] for r in recs if r.has(marker)]
        if len(vals) < 3:
            return None
        a = np.array(vals, dtype=float)
        std = float(a.std())
        robust_std = _scaled_mad(a)
        min_std = float(MARKER_SPECS.get(marker, {}).get("min_robust_std", 1e-3))
        return {
            "n": len(vals), "mean": float(a.mean()),
            "std": float(max(std, robust_std, min_std)),
            "median": float(np.median(a)), "p20": float(np.percentile(a, 20)),
            "p80": float(np.percentile(a, 80)), "min": float(a.min()), "max": float(a.max()),
        }

    def coverage_quality(self, marker: str, days_back: int = 7,
                         end_exclusive: Optional[date] = None) -> str:
        recs = self.window(days_back, end_exclusive)
        if not recs:
            return "none"
        avg = np.mean([r.coverage.get(marker, 0.0) for r in recs])
        if avg >= 0.75: return "high"
        if avg >= 0.45: return "medium"
        if avg > 0.0:   return "low"
        return "none"


# ---------- Interface for plugging in StudentLife / K-EmoPhone / live data ----------

def _coerce_day(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    if hasattr(value, "date"):
        maybe_date = value.date()
        if isinstance(maybe_date, date):
            return maybe_date
    raise TypeError(f"Unsupported raw day date value: {value!r}")


def markers_from_raw(raw_day: dict) -> DayRecord:
    """
    Adapter: map a dict of raw/extracted per-day features into a DayRecord.

    In your pipeline, replace the body with calls into studentlife_extract.py
    outputs (for StudentLife) or live phone sensor aggregations.

    Expected input shape (everything optional; missing → coverage 0):
        {
            'date': datetime.date,
            'sleep_onset_hour': float,
            'sleep_duration_hours': float,
            'sleep_regularity_index': float,
            'late_night_screen_min': float,
            'total_screen_min': float,
            'app_switching_rate': float,
            'mobility_entropy': float,
            'location_revisit_ratio': float,
            'social_rhythm_metric': float,
            'comm_reciprocity': float,
            '_coverage': {marker: 0..1, ...}   # optional per-marker coverage
        }
    """
    day = _coerce_day(raw_day["date"])
    markers, coverage = {}, {}
    cov_override = raw_day.get("coverage") or raw_day.get("_coverage") or {}
    for m in MARKER_SPECS:
        if m in raw_day and raw_day[m] is not None:
            markers[m] = float(raw_day[m])
            coverage[m] = float(cov_override.get(m, 1.0))
        else:
            coverage[m] = 0.0
    return DayRecord(day=day, markers=markers, coverage=coverage)
