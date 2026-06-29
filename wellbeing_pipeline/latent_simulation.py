"""
Longitudinal latent-profile simulation for the wellbeing pipeline.

This script intentionally keeps the data-generating latent profile outside the
scheduler inputs. The behavior-aware arm receives only the state inferred by
Layers 1-4 from noisy marker-level data; the calendar-only arm receives the same
calendar and preferences with the behavioral state removed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any

import anthropic
import numpy as np

PIPELINE_DIR = Path(__file__).resolve().parent
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from layer1 import MARKER_SPECS, PersonalBaseline, markers_from_raw  # noqa: E402
from layer2 import detect_deviations, find_coherent_patterns  # noqa: E402
from layer3 import build_state_description  # noqa: E402
from layer4_llm import call_scheduler, config as layer4_config  # noqa: E402


DEFAULT_SEED = 20260627
DEFAULT_START_DATE = date(2026, 3, 2)
DEFAULT_OUTDIR = PIPELINE_DIR / "simulation_outputs" / "latent"

PIPELINE_CONFIG = {
    "warmup_days": 10,
    "recent_days": 4,
    "baseline_days": 21,
    "min_magnitude": "mild",
}

STATE_NAMES = [
    "phone-mediated-sleep-delay",
    "behavioral-withdrawal",
    "circadian-instability",
    "fragmented-attention-with-sleep-loss",
]

MARKER_COLUMNS = ["date", *MARKER_SPECS.keys(), "_coverage"]
HIGH_BURDEN_THRESHOLD = 2.5
CONSERVATIVE_BURDEN_INSTRUCTION = (
    "Prefer the minimal-burden change: modify at most one flexible event, "
    "never change fixed events, and make no change if there is no clear behavioral signal."
)

EPISODE_BASE_SHIFTS = {
    "phone-mediated-sleep-delay": {
        "sleep_onset_hour": 1.15,
        "late_night_screen_min": 70.0,
    },
    "behavioral-withdrawal": {
        "mobility_entropy": -0.36,
        "location_revisit_ratio": 0.22,
    },
    "circadian-instability": {
        "sleep_regularity_index": -18.0,
    },
    "fragmented-attention-with-sleep-loss": {
        "app_switching_rate": 0.52,
        "sleep_duration_hours": -1.05,
    },
}

EPISODE_DRIVER = {
    "phone-mediated-sleep-delay": "late-evening screen-load episode",
    "behavioral-withdrawal": "restricted-mobility routine-narrowing episode",
    "circadian-instability": "irregular anchor-time episode",
    "fragmented-attention-with-sleep-loss": "sleep-debt attention-fragmentation episode",
}


@dataclass
class LatentProfile:
    participant_id: str
    chronotype: float
    sleep_regularity: float
    workload: float
    schedule_flexibility: float
    mobility_pattern: float
    social_rhythm: float
    phone_use_tendency: float
    adherence_tendency: float
    stress_sensitivity: float
    missing_rate: float
    state_scores: dict[str, float]
    predisposed_pattern: str

    def public_traits_for_generation(self) -> dict[str, float]:
        d = asdict(self)
        for key in ("participant_id", "state_scores", "predisposed_pattern"):
            d.pop(key, None)
        return d


@dataclass
class CalendarEvent:
    event_id: str
    participant_id: str
    day_index: int
    date: str
    title: str
    event_type: str
    fixed: bool
    start: str
    end: str
    burden: float


@dataclass
class Episode:
    episode_id: str
    participant_id: str
    pattern: str
    start_day: int
    end_day: int
    driver: str
    intensity: float
    marker_shifts: dict[str, float]

    @property
    def days(self) -> list[int]:
        return list(range(self.start_day, self.end_day + 1))


def _clip(x: float, lo: float, hi: float) -> float:
    return float(min(hi, max(lo, x)))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _time_to_minutes(hhmm: str) -> int:
    h, m = [int(part) for part in hhmm.split(":")]
    return h * 60 + m


def _minutes_to_time(minutes: int) -> str:
    minutes = minutes % (24 * 60)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _duration_hours(event: dict[str, Any] | CalendarEvent) -> float:
    if isinstance(event, CalendarEvent):
        start, end = event.start, event.end
    else:
        start, end = event["start"], event["end"]
    return max(0, _time_to_minutes(end) - _time_to_minutes(start)) / 60.0


def _normalize_pattern_name(name: str | None) -> str:
    if not name:
        return ""
    n = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if "phone" in n and "sleep" in n:
        return "phone-mediated-sleep-delay"
    if ("withdraw" in n or "mobility" in n or "isolation" in n) and (
        "location" in n or "mobility" in n or "place" in n or "routine" in n
    ):
        return "behavioral-withdrawal"
    if "circadian" in n or ("sleep" in n and "regular" in n):
        return "circadian-instability"
    if ("fragment" in n or "attention" in n or "app-switch" in n) and "sleep" in n:
        return "fragmented-attention-with-sleep-loss"
    return n


def _profile_scores(vals: dict[str, float]) -> dict[str, float]:
    return {
        "phone-mediated-sleep-delay": (
            0.34 * vals["chronotype"]
            + 0.32 * vals["phone_use_tendency"]
            + 0.20 * vals["workload"]
            + 0.14 * vals["stress_sensitivity"]
        ),
        "behavioral-withdrawal": (
            0.34 * (1.0 - vals["mobility_pattern"])
            + 0.28 * (1.0 - vals["social_rhythm"])
            + 0.23 * vals["stress_sensitivity"]
            + 0.15 * vals["workload"]
        ),
        "circadian-instability": (
            0.36 * (1.0 - vals["sleep_regularity"])
            + 0.21 * vals["schedule_flexibility"]
            + 0.20 * vals["stress_sensitivity"]
            + 0.13 * vals["chronotype"]
            + 0.10 * (1.0 - vals["social_rhythm"])
        ),
        "fragmented-attention-with-sleep-loss": (
            0.31 * vals["workload"]
            + 0.25 * vals["stress_sensitivity"]
            + 0.22 * vals["phone_use_tendency"]
            + 0.14 * (1.0 - vals["sleep_regularity"])
            + 0.08 * vals["chronotype"]
        ),
    }


def sample_profiles(n: int, seed: int) -> list[LatentProfile]:
    """Sample latent profiles and keep a modest spread across the four causes."""
    min_per_state = 3 if n >= len(STATE_NAMES) * 3 else 1
    for attempt in range(400):
        rng = np.random.default_rng(seed + attempt)
        profiles: list[LatentProfile] = []
        for i in range(n):
            vals = {
                "chronotype": float(rng.beta(2.0, 2.0)),
                "sleep_regularity": float(rng.beta(2.3, 2.0)),
                "workload": float(rng.beta(2.0, 2.0)),
                "schedule_flexibility": float(rng.beta(2.0, 2.0)),
                "mobility_pattern": float(rng.beta(2.0, 2.0)),
                "social_rhythm": float(rng.beta(2.2, 2.0)),
                "phone_use_tendency": float(rng.beta(2.0, 2.0)),
                "adherence_tendency": float(rng.beta(2.0, 2.0)),
                "stress_sensitivity": float(rng.beta(2.0, 2.0)),
            }
            scores = _profile_scores(vals)
            predisposed = max(scores, key=scores.get)
            profiles.append(
                LatentProfile(
                    participant_id=f"P{i + 1:03d}",
                    missing_rate=float(rng.uniform(0.10, 0.20)),
                    state_scores=scores,
                    predisposed_pattern=predisposed,
                    **vals,
                )
            )

        counts = Counter(p.predisposed_pattern for p in profiles)
        if n < len(STATE_NAMES):
            return profiles
        if len(counts) == len(STATE_NAMES) and min(counts.values()) >= min_per_state:
            return profiles

    return profiles


def _overlaps(existing: list[CalendarEvent], start: str, end: str) -> bool:
    s = _time_to_minutes(start)
    e = _time_to_minutes(end)
    for ev in existing:
        if max(s, _time_to_minutes(ev.start)) < min(e, _time_to_minutes(ev.end)):
            return True
    return False


def _add_event(
    events: list[CalendarEvent],
    profile: LatentProfile,
    day_index: int,
    d: date,
    title: str,
    event_type: str,
    fixed: bool,
    start: str,
    end: str,
    burden: float,
) -> bool:
    if _overlaps(events, start, end):
        return False
    event_id = f"{profile.participant_id}-D{day_index:02d}-E{len(events) + 1:02d}"
    events.append(
        CalendarEvent(
            event_id=event_id,
            participant_id=profile.participant_id,
            day_index=day_index,
            date=d.isoformat(),
            title=title,
            event_type=event_type,
            fixed=fixed,
            start=start,
            end=end,
            burden=burden,
        )
    )
    return True


def _try_event(
    events: list[CalendarEvent],
    profile: LatentProfile,
    day_index: int,
    d: date,
    title: str,
    event_type: str,
    fixed: bool,
    candidates: list[tuple[str, str]],
    burden: float,
    rng: np.random.Generator,
) -> bool:
    order = list(rng.permutation(len(candidates)))
    for idx in order:
        start, end = candidates[idx]
        if _add_event(events, profile, day_index, d, title, event_type, fixed, start, end, burden):
            return True
    return False


def generate_calendar(
    profiles: list[LatentProfile],
    n_days: int,
    start_date: date,
    seed: int,
) -> dict[str, list[dict[str, Any]]]:
    rng = np.random.default_rng(seed + 101)
    calendars: dict[str, list[dict[str, Any]]] = {}

    for profile in profiles:
        p_events: list[CalendarEvent] = []
        for day_index in range(1, n_days + 1):
            d = start_date + timedelta(days=day_index - 1)
            weekday = d.weekday()
            today: list[CalendarEvent] = []
            workload = profile.workload

            if weekday < 5 and rng.random() < 0.48 + 0.30 * workload:
                _try_event(
                    today,
                    profile,
                    day_index,
                    d,
                    "class",
                    "class",
                    True,
                    [("09:00", "10:15"), ("10:30", "11:45")],
                    1.0,
                    rng,
                )

            if weekday in (1, 3) and rng.random() < 0.22 + 0.30 * workload:
                _try_event(
                    today,
                    profile,
                    day_index,
                    d,
                    "lab",
                    "lab",
                    True,
                    [("13:30", "15:30"), ("14:00", "16:00")],
                    1.5,
                    rng,
                )

            if weekday < 6 and rng.random() < 0.10 + 0.30 * workload:
                _try_event(
                    today,
                    profile,
                    day_index,
                    d,
                    "work shift",
                    "work_shift",
                    True,
                    [("16:00", "20:00"), ("18:00", "22:00")],
                    2.0,
                    rng,
                )

            if day_index in (26, 34, 41) and rng.random() < 0.35 + 0.50 * workload:
                _try_event(
                    today,
                    profile,
                    day_index,
                    d,
                    "exam",
                    "exam",
                    True,
                    [("13:00", "15:00"), ("10:00", "12:00")],
                    2.4,
                    rng,
                )

            if weekday < 5 and rng.random() < 0.12 + 0.18 * workload:
                _try_event(
                    today,
                    profile,
                    day_index,
                    d,
                    "required meeting",
                    "required_meeting",
                    True,
                    [("11:00", "12:00"), ("15:30", "16:30")],
                    1.2,
                    rng,
                )

            flex_density = 0.25 + 0.50 * workload
            if rng.random() < 0.38 + 0.48 * workload:
                _try_event(
                    today,
                    profile,
                    day_index,
                    d,
                    "study block",
                    "study_block",
                    False,
                    [("15:30", "17:00"), ("19:00", "20:30"), ("20:30", "22:00")],
                    1.1,
                    rng,
                )

            if rng.random() < 0.18 + 0.22 * (1.0 - workload):
                _try_event(
                    today,
                    profile,
                    day_index,
                    d,
                    "workout",
                    "workout",
                    False,
                    [("07:00", "07:45"), ("17:00", "17:45"), ("18:00", "18:45")],
                    0.8,
                    rng,
                )

            if rng.random() < 0.18 + 0.12 * (weekday >= 5):
                _try_event(
                    today,
                    profile,
                    day_index,
                    d,
                    "errands",
                    "errands",
                    False,
                    [("12:00", "13:00"), ("16:30", "17:30")],
                    0.8,
                    rng,
                )

            if rng.random() < flex_density * 0.55:
                _try_event(
                    today,
                    profile,
                    day_index,
                    d,
                    "optional work session",
                    "optional_work_session",
                    False,
                    [("20:30", "22:00"), ("21:00", "22:30"), ("18:30", "20:00")],
                    1.3,
                    rng,
                )

            if rng.random() < 0.13 + 0.22 * profile.social_rhythm + 0.16 * (weekday >= 4):
                _try_event(
                    today,
                    profile,
                    day_index,
                    d,
                    "social plan",
                    "social_plan",
                    False,
                    [("18:30", "20:30"), ("19:30", "21:30")],
                    0.9,
                    rng,
                )

            p_events.extend(today)

        calendars[profile.participant_id] = [asdict(ev) for ev in p_events]

    return calendars


def _calendar_day_pressure(events: list[dict[str, Any]], day_index: int) -> dict[str, float]:
    today = [e for e in events if e["day_index"] == day_index]
    fixed_hours = sum(_duration_hours(e) for e in today if e["fixed"])
    flex_hours = sum(_duration_hours(e) for e in today if not e["fixed"])
    late_flex_hours = sum(
        _duration_hours(e)
        for e in today
        if not e["fixed"] and _time_to_minutes(e["start"]) >= 20 * 60
    )
    fixed_count = sum(1 for e in today if e["fixed"])
    exam_today = any(e["event_type"] == "exam" for e in today)
    exam_near = any(
        abs(e["day_index"] - day_index) <= 2 and e["event_type"] == "exam" for e in events
    )
    return {
        "fixed_hours": fixed_hours,
        "flex_hours": flex_hours,
        "late_flex_hours": late_flex_hours,
        "fixed_count": float(fixed_count),
        "exam_today": float(exam_today),
        "exam_near": float(exam_near),
        "event_count": float(len(today)),
    }


def _episode_shifts(pattern: str, intensity: float) -> dict[str, float]:
    return {
        marker: float(shift * intensity)
        for marker, shift in EPISODE_BASE_SHIFTS[pattern].items()
    }


def _range_overlaps(start: int, end: int, episodes: list[Episode], gap: int = 1) -> bool:
    for episode in episodes:
        if start <= episode.end_day + gap and end >= episode.start_day - gap:
            return True
    return False


def _add_episode(
    episodes: list[Episode],
    profile: LatentProfile,
    start_day: int,
    length: int,
    intensity: float,
) -> None:
    end_day = start_day + length - 1
    episode_idx = len(episodes) + 1
    marker_shifts = _episode_shifts(profile.predisposed_pattern, intensity)
    episodes.append(
        Episode(
            episode_id=f"{profile.participant_id}-EP{episode_idx:02d}",
            participant_id=profile.participant_id,
            pattern=profile.predisposed_pattern,
            start_day=start_day,
            end_day=end_day,
            driver=EPISODE_DRIVER[profile.predisposed_pattern],
            intensity=float(intensity),
            marker_shifts=marker_shifts,
        )
    )


def generate_episodes(
    profile: LatentProfile,
    n_days: int,
    rng: np.random.Generator,
) -> list[Episode]:
    """Create 1-3 episodic perturbations, always leaving normal decision days."""
    episodes: list[Episode] = []
    n_episodes = int(rng.integers(1, 4))

    # Every participant gets one decision-window episode so the scheduler can be
    # tested when a true latent episode is present, while length <= 7 leaves
    # normal decision days for restraint metrics.
    decision_length = int(rng.integers(4, 8))
    decision_start = int(rng.integers(27, 39))
    decision_start = min(decision_start, n_days - decision_length + 1)
    _add_episode(
        episodes,
        profile,
        decision_start,
        decision_length,
        float(rng.uniform(1.05, 1.25)),
    )

    if n_episodes >= 2:
        pre_length = int(rng.integers(3, 7))
        pre_start = int(rng.integers(12, 23))
        pre_start = min(pre_start, n_days - pre_length + 1)
        if not _range_overlaps(pre_start, pre_start + pre_length - 1, episodes):
            _add_episode(
                episodes,
                profile,
                pre_start,
                pre_length,
                float(rng.uniform(1.00, 1.18)),
            )

    if n_episodes >= 3:
        candidate_windows = [(5, 11), (18, 25), (34, 39)]
        for window_start, window_end in rng.permutation(candidate_windows).tolist():
            length = int(rng.integers(3, 6))
            latest_start = min(window_end, n_days - length + 1)
            if latest_start < window_start:
                continue
            start_day = int(rng.integers(window_start, latest_start + 1))
            end_day = start_day + length - 1
            if _range_overlaps(start_day, end_day, episodes):
                continue
            _add_episode(
                episodes,
                profile,
                start_day,
                length,
                float(rng.uniform(1.00, 1.15)),
            )
            break

    return sorted(episodes, key=lambda e: e.start_day)


NOISE_SD = {
    "sleep_onset_hour": 0.22,
    "sleep_duration_hours": 0.30,
    "sleep_regularity_index": 3.0,
    "late_night_screen_min": 8.0,
    "total_screen_min": 22.0,
    "app_switching_rate": 0.07,
    "mobility_entropy": 0.07,
    "location_revisit_ratio": 0.035,
    "social_rhythm_metric": 0.04,
    "comm_reciprocity": 0.05,
}


def _clip_marker(marker: str, value: float) -> float:
    if marker == "sleep_onset_hour":
        return _clip(value, 20.0, 28.5)
    if marker == "sleep_duration_hours":
        return _clip(value, 3.2, 9.8)
    if marker == "sleep_regularity_index":
        return _clip(value, 0.0, 100.0)
    if marker in ("late_night_screen_min", "total_screen_min"):
        return _clip(value, 0.0, 900.0)
    if marker == "app_switching_rate":
        return _clip(value, 0.02, 2.2)
    if marker == "mobility_entropy":
        return _clip(value, 0.05, 2.4)
    if marker in ("location_revisit_ratio", "social_rhythm_metric", "comm_reciprocity"):
        return _clip(value, 0.02, 0.98)
    return value


def generate_marker_days(
    profile: LatentProfile,
    calendar_events: list[dict[str, Any]],
    n_days: int,
    start_date: date,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Generate Layer-1-shaped marker dicts plus hidden day-level drivers."""
    rng = np.random.default_rng(seed + 1000 + int(profile.participant_id[1:]))
    raw_days: list[dict[str, Any]] = []
    hidden_daily: list[dict[str, Any]] = []
    episodes = generate_episodes(profile, n_days, rng)
    episodes_by_day: dict[int, list[Episode]] = defaultdict(list)
    for episode in episodes:
        for episode_day in episode.days:
            episodes_by_day[episode_day].append(episode)

    prev_strain = 0.25 + 0.25 * profile.workload

    for day_index in range(1, n_days + 1):
        d = start_date + timedelta(days=day_index - 1)
        weekend = d.weekday() >= 5
        pressure = _calendar_day_pressure(calendar_events, day_index)
        semester_wave = _sigmoid((day_index - 26.5) / 3.1)
        density = (
            0.12 * pressure["event_count"]
            + 0.08 * pressure["fixed_hours"]
            + 0.05 * pressure["flex_hours"]
            + 0.18 * pressure["exam_near"]
        )
        shock = rng.normal(0.0, 0.09) + (0.18 if rng.random() < 0.05 + 0.09 * profile.stress_sensitivity else 0.0)
        base_strain = (
            0.12
            + 0.32 * profile.workload
            + 0.22 * profile.stress_sensitivity
            + 0.30 * density
            + 0.35 * semester_wave * (0.25 + 0.75 * profile.workload)
            + shock
        )
        strain = _clip(0.55 * prev_strain + 0.45 * base_strain, 0.0, 1.4)
        prev_strain = strain
        activation = _clip((strain - (0.55 - 0.10 * profile.stress_sensitivity)) / 0.75, 0.0, 1.0)
        active_episodes = episodes_by_day.get(day_index, [])
        active_shifts: dict[str, float] = defaultdict(float)
        for episode in active_episodes:
            for marker, shift in episode.marker_shifts.items():
                active_shifts[marker] += shift

        base_onset = 22.15 + 2.15 * profile.chronotype + (0.35 if weekend else 0.0)
        base_duration = 8.25 - 0.65 * profile.workload - 0.25 * profile.stress_sensitivity
        base_sri = 63.0 + 31.0 * profile.sleep_regularity - (4.0 if weekend else 0.0)
        base_late_screen = 6.0 + 42.0 * profile.phone_use_tendency + 16.0 * profile.chronotype
        base_total_screen = 135.0 + 155.0 * profile.phone_use_tendency + 90.0 * profile.workload
        base_app_switch = 0.28 + 0.36 * profile.phone_use_tendency + 0.26 * profile.workload
        base_mobility = 0.82 + 0.72 * profile.mobility_pattern + (0.10 if weekend else 0.0)
        base_revisit = 0.58 + 0.27 * (1.0 - profile.mobility_pattern)
        base_srm = 0.42 + 0.46 * profile.social_rhythm - (0.05 if weekend else 0.0)
        base_comm = 0.46 + 0.16 * profile.social_rhythm

        values = {
            "sleep_onset_hour": (
                base_onset
                + 0.10 * pressure["late_flex_hours"]
                + 0.08 * strain
            ),
            "sleep_duration_hours": (
                base_duration
                - 0.12 * pressure["late_flex_hours"]
                - 0.18 * strain
            ),
            "sleep_regularity_index": base_sri - 3.0 * strain,
            "late_night_screen_min": (
                base_late_screen
                + 8.0 * pressure["late_flex_hours"]
                + 4.0 * strain
            ),
            "total_screen_min": (
                base_total_screen
                + 22.0 * pressure["flex_hours"]
                + 14.0 * strain
            ),
            "app_switching_rate": base_app_switch + 0.05 * strain,
            "mobility_entropy": base_mobility - 0.03 * pressure["fixed_count"],
            "location_revisit_ratio": base_revisit + 0.015 * pressure["fixed_count"],
            "social_rhythm_metric": base_srm - 0.03 * strain,
            "comm_reciprocity": base_comm + rng.normal(0.0, 0.03),
        }
        for marker, shift in active_shifts.items():
            values[marker] += shift

        raw: dict[str, Any] = {"date": d}
        coverage: dict[str, float] = {}
        episode_required_markers = set(active_shifts)
        for marker in MARKER_SPECS:
            missing_rate = profile.missing_rate
            if marker in episode_required_markers:
                missing_rate = min(missing_rate, 0.06)
            if rng.random() < missing_rate:
                raw[marker] = None
                coverage[marker] = 0.0
                continue
            noisy_value = values[marker] + rng.normal(0.0, NOISE_SD[marker])
            if rng.random() < 0.018:
                noisy_value += float(rng.choice([-1, 1])) * rng.uniform(2.5, 4.0) * NOISE_SD[marker]
            raw[marker] = _clip_marker(marker, noisy_value)
            coverage[marker] = float(rng.uniform(0.80, 1.0))
            if rng.random() < 0.035:
                coverage[marker] = float(rng.uniform(0.45, 0.70))

        raw["_coverage"] = coverage
        raw_days.append(raw)
        hidden_daily.append(
            {
                "participant_id": profile.participant_id,
                "day_index": day_index,
                "date": d.isoformat(),
                "strain": strain,
                "activation": activation,
                "in_episode": bool(active_episodes),
                "episode_ids": [episode.episode_id for episode in active_episodes],
                "episode_patterns": [episode.pattern for episode in active_episodes],
                "episode_drivers": [episode.driver for episode in active_episodes],
                "episode_marker_shifts": dict(active_shifts),
                **pressure,
            }
        )

    episode_rows = [
        {
            **asdict(episode),
            "days": episode.days,
            "overlaps_decision_days": any(29 <= day <= 42 for day in episode.days),
        }
        for episode in episodes
    ]
    return raw_days, hidden_daily, episode_rows


def run_layers_1_to_3(
    raw_days_by_pid: dict[str, list[dict[str, Any]]],
) -> dict[tuple[str, int], dict[str, Any]]:
    states: dict[tuple[str, int], dict[str, Any]] = {}
    for pid, raw_days in raw_days_by_pid.items():
        baseline = PersonalBaseline(warmup_days=PIPELINE_CONFIG["warmup_days"])
        for day_index, raw in enumerate(raw_days, start=1):
            baseline.add(markers_from_raw(raw))
            as_of = raw["date"]
            devs = detect_deviations(
                baseline,
                as_of=as_of,
                recent_days=PIPELINE_CONFIG["recent_days"],
                baseline_days=PIPELINE_CONFIG["baseline_days"],
                min_magnitude=PIPELINE_CONFIG["min_magnitude"],
            )
            patterns = find_coherent_patterns(devs)
            state = build_state_description(baseline, devs, patterns, as_of)
            states[(pid, day_index)] = {
                "participant_id": pid,
                "day_index": day_index,
                "date": as_of.isoformat(),
                "state": state,
                "deviations": [d.to_dict() for d in devs],
                "layer_1_3_patterns": [p.to_dict() for p in patterns],
                "confidence": state["structured"]["baseline_state"]["overall_confidence"],
                "coverage": raw.get("_coverage", {}),
            }
    return states


def calendar_window(events: list[dict[str, Any]], day_index: int, horizon_days: int = 7) -> list[dict[str, Any]]:
    return [
        e
        for e in events
        if day_index <= int(e["day_index"]) < day_index + horizon_days
    ]


def calendar_summary(events: list[dict[str, Any]]) -> str:
    parts = []
    for e in sorted(events, key=lambda x: (x["date"], x["start"], x["title"])):
        kind = "fixed" if e["fixed"] else "flexible"
        parts.append(f"{e['date']} {e['start']} {e['title']} ({kind})")
    return "; ".join(parts)


def user_preferences() -> dict[str, Any]:
    return {
        "scheduler_instruction": CONSERVATIVE_BURDEN_INSTRUCTION,
    }


def calendar_only_state(as_of: str, days_of_history: int) -> dict[str, Any]:
    structured = {
        "as_of": as_of,
        "baseline_state": {
            "warm": True,
            "days_of_history": days_of_history,
            "overall_confidence": "no-behavioral-state-provided",
        },
        "deviations": [],
        "coherent_patterns": [],
        "coverage_notes": [],
        "schema_note": (
            "Calendar-only arm. No behavioral state, deviations, marker evidence, "
            "or inferred pattern is provided. Reason only from the calendar and "
            "the user's stated scheduling preferences."
        ),
    }
    return {
        "structured": structured,
        "prose": "No behavioral state was provided for this arm.",
    }


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=_json_default) + "\n")


def _append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, default=_json_default) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not fieldnames:
        keys: list[str] = []
        for row in rows:
            for key in row.keys():
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _cache_key(case_id: str, arm: str, state: dict[str, Any], events: list[dict[str, Any]], prefs: dict[str, Any]) -> str:
    h = hashlib.sha256()
    h.update(
        json.dumps(
            {"case_id": case_id, "arm": arm, "state": state, "events": events, "prefs": prefs},
            sort_keys=True,
            default=_json_default,
        ).encode("utf-8")
    )
    return h.hexdigest()[:16]


def run_scheduler_cached(
    cache_dir: Path,
    case_id: str,
    arm: str,
    state: dict[str, Any],
    events: list[dict[str, Any]],
    prefs: dict[str, Any],
    model: str | None,
) -> dict[str, Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    digest = _cache_key(case_id, arm, state, events, prefs)
    cache_path = cache_dir / f"{case_id}_{arm}_{digest}.json"
    if cache_path.exists():
        cached = json.loads(cache_path.read_text())
        cached["cache_hit"] = True
        return cached

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            result = call_scheduler(
                state=state,
                calendar=events,
                user_prefs=prefs,
                feedback_history=[],
                model=model,
            )
            break
        except Exception as exc:  # network and rate-limit errors are retried here.
            last_error = exc
            if attempt == 2:
                raise
            time.sleep(2.0 * (attempt + 1))
    else:
        raise RuntimeError(f"Scheduler call failed: {last_error}")

    payload = {
        "case_id": case_id,
        "arm": arm,
        "input_digest": digest,
        "cache_hit": False,
        "result": result,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(cache_path, payload)
    return payload


def suggestion_text(result: dict[str, Any]) -> str:
    suggestions = result.get("suggestions") or []
    parts = []
    for i, suggestion in enumerate(suggestions, start=1):
        change = str(suggestion.get("change", "")).strip()
        rationale = str(suggestion.get("rationale", "")).strip()
        grounded = suggestion.get("grounded_in") or []
        parts.append(
            f"{i}. {change}"
            + (f" Rationale: {rationale}" if rationale else "")
            + (f" Grounded in: {', '.join(map(str, grounded))}" if grounded else "")
        )
    if not parts and result.get("questions_for_user"):
        parts.append("Questions: " + "; ".join(map(str, result.get("questions_for_user") or [])))
    return " ".join(parts)


MECHANISM_KEYWORDS = {
    "phone-mediated-sleep-delay": [
        "late-night screen",
        "screen use",
        "screen exposure",
        "phone",
        "device",
        "blue light",
        "screen spillover",
    ],
    "behavioral-withdrawal": [
        "behavioral withdrawal",
        "reduced mobility",
        "mobility entropy",
        "location routine",
        "familiar places",
        "third place",
        "outside",
        "walk",
    ],
    "circadian-instability": [
        "circadian",
        "sleep regularity",
        "regularity",
        "consistent wake",
        "wake time",
        "anchor",
        "social rhythm",
        "routine timing",
    ],
    "fragmented-attention-with-sleep-loss": [
        "fragmented attention",
        "app switching",
        "attention",
        "focus",
        "sleep loss",
        "sleep debt",
        "cognitive strain",
    ],
}

LEVER_MARKERS = {
    "phone-mediated-sleep-delay": ["sleep_onset_hour", "late_night_screen_min"],
    "behavioral-withdrawal": ["mobility_entropy", "location_revisit_ratio", "social_rhythm_metric"],
    "circadian-instability": ["sleep_regularity_index", "sleep_onset_hour", "social_rhythm_metric"],
    "fragmented-attention-with-sleep-loss": ["app_switching_rate", "sleep_duration_hours"],
}

PATTERN_REQUIREMENTS = {
    "phone-mediated-sleep-delay": [
        ("sleep_onset_hour", "up"),
        ("late_night_screen_min", "up"),
    ],
    "behavioral-withdrawal": [
        ("mobility_entropy", "down"),
        ("location_revisit_ratio", "up"),
    ],
    "circadian-instability": [
        ("sleep_regularity_index", "down"),
    ],
    "fragmented-attention-with-sleep-loss": [
        ("app_switching_rate", "up"),
        ("sleep_duration_hours", "down"),
    ],
}

BEHAVIOR_AWARE_ACTION_KEYWORDS = {
    "phone-mediated-sleep-delay": ["wind-down", "no screens", "screen", "phone"],
    "behavioral-withdrawal": ["walk", "outside", "social", "third place", "workout"],
    "circadian-instability": ["wake", "morning", "anchor", "routine", "light"],
    "fragmented-attention-with-sleep-loss": ["focus", "deep work", "study block", "sleep"],
}

def _modifies_fixed_event(text: str, title: str) -> bool:
    escaped = re.escape(title.lower())
    verb = r"(move|moving|reschedule|cancel|shorten|replace|delay|push|cap|skip|drop)"
    patterns = [
        rf"\b{verb}\b.{{0,48}}\b{escaped}\b",
        rf"\b{escaped}\b.{{0,48}}\b{verb}\b",
    ]
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _all_recommendation_text(result: dict[str, Any]) -> str:
    bits = [str(result.get("salience_reasoning", "")), suggestion_text(result)]
    return " ".join(bits).lower()


def addresses_expected_lever(
    pattern: str,
    result: dict[str, Any],
    arm: str = "behavior_aware",
    received_relevant_evidence: bool = False,
) -> bool:
    text = _all_recommendation_text(result)
    suggestions = result.get("suggestions") or []
    grounded = " ".join(
        str(item)
        for suggestion in suggestions
        for item in (suggestion.get("grounded_in") or [])
    ).lower()
    if arm == "behavior_aware" and received_relevant_evidence:
        if pattern in grounded or any(marker in grounded for marker in LEVER_MARKERS[pattern]):
            return True

    # Calendar-only, and behavior-aware on days without relevant inferred
    # evidence, should not get credit for generic sleep/wind-down guesses.
    # They need to name the actual latent mechanism.
    if any(keyword in text for keyword in MECHANISM_KEYWORDS[pattern]):
        return True
    if arm == "behavior_aware" and received_relevant_evidence:
        return any(keyword in text for keyword in BEHAVIOR_AWARE_ACTION_KEYWORDS[pattern])
    return False


def flexible_event_pass(result: dict[str, Any], events: list[dict[str, Any]]) -> tuple[bool, str]:
    text = _all_recommendation_text(result)
    if not text.strip():
        return False, "no recommendation text"

    fixed_mentions = [
        e["title"]
        for e in events
        if e["fixed"] and e["title"].lower() in text and _modifies_fixed_event(text, e["title"])
    ]
    if fixed_mentions:
        return False, "appears to modify fixed event: " + ", ".join(sorted(set(fixed_mentions)))

    flexible_titles = [
        e["title"].lower()
        for e in events
        if not e["fixed"]
    ]
    flexible_types = [
        str(e["event_type"]).replace("_", " ").lower()
        for e in events
        if not e["fixed"]
    ]
    mentions_flexible = any(title in text for title in flexible_titles) or any(
        event_type in text for event_type in flexible_types
    )
    adds_buffer = any(
        phrase in text
        for phrase in (
            "add",
            "buffer",
            "wind-down",
            "walk",
            "block",
            "break",
            "light",
        )
    )
    if mentions_flexible or adds_buffer:
        return True, "targets flexible event or adds non-conflicting support block"
    return False, "does not clearly target a flexible event"


def recommendation_burden(result: dict[str, Any]) -> float:
    score = 0.0
    for suggestion in result.get("suggestions") or []:
        change = str(suggestion.get("change", "")).lower()
        if any(word in change for word in ("cancel", "drop", "skip", "replace")):
            score += 1.3
        if any(word in change for word in ("move", "reschedule", "shift", "delay", "push")):
            score += 1.0
        if any(word in change for word in ("add", "insert", "schedule", "protect")):
            score += 0.7
        if any(word in change for word in ("cap", "shorten", "trim")):
            score += 0.5
        start = suggestion.get("start_time")
        end = suggestion.get("end_time")
        if isinstance(start, str) and isinstance(end, str) and re.match(r"^\d\d:\d\d$", start) and re.match(r"^\d\d:\d\d$", end):
            minutes = max(0, _time_to_minutes(end) - _time_to_minutes(start))
            if minutes <= 20:
                score += 0.2
            elif minutes <= 45:
                score += 0.45
            elif minutes <= 90:
                score += 0.8
            else:
                score += 1.2
    return round(score, 3)


def suggestion_count(result: dict[str, Any]) -> int:
    return len(result.get("suggestions") or [])


def no_change_recommended(result: dict[str, Any]) -> bool:
    suggestions = result.get("suggestions") or []
    return len(suggestions) == 0


def high_burden_change(result: dict[str, Any]) -> bool:
    return recommendation_burden(result) >= HIGH_BURDEN_THRESHOLD


def specificity_pass(result: dict[str, Any], events: list[dict[str, Any]]) -> bool:
    suggestions = result.get("suggestions") or []
    if not suggestions:
        return False

    flexible_names = {
        str(e["title"]).lower()
        for e in events
        if not e["fixed"]
    } | {
        str(e["event_type"]).replace("_", " ").lower()
        for e in events
        if not e["fixed"]
    }

    for suggestion in suggestions:
        change = str(suggestion.get("change", "")).lower()
        if not change.strip():
            continue
        has_time = all(
            isinstance(suggestion.get(key), str)
            and re.match(r"^\d\d:\d\d$", suggestion.get(key, ""))
            for key in ("start_time", "end_time")
        )
        names_event = any(name and name in change for name in flexible_names)
        if has_time or names_event:
            return True
    return False


def burden_appropriate(score: float, adherence_tendency: float) -> bool:
    tolerance = 0.65 + 2.15 * adherence_tendency
    return score <= tolerance


def evaluate_arm(
    arm: str,
    latent_pattern: str,
    adherence_tendency: float,
    result: dict[str, Any],
    events: list[dict[str, Any]],
    received_relevant_evidence: bool = False,
) -> dict[str, Any]:
    lever = addresses_expected_lever(
        latent_pattern,
        result,
        arm=arm,
        received_relevant_evidence=received_relevant_evidence,
    )
    flexible, flexible_reason = flexible_event_pass(result, events)
    burden = recommendation_burden(result)
    burden_ok = burden_appropriate(burden, adherence_tendency)
    n_suggestions = suggestion_count(result)
    return {
        "arm": arm,
        "lever_pass": lever,
        "flexible_event_pass": flexible,
        "flexible_event_reason": flexible_reason,
        "burden_score": burden,
        "burden_pass": burden_ok,
        "specificity_pass": specificity_pass(result, events),
        "n_suggestions": n_suggestions,
        "no_change_recommended": n_suggestions == 0,
        "high_burden_change": burden >= HIGH_BURDEN_THRESHOLD,
        "all_three_pass": lever and flexible and burden_ok,
    }


def layer4_pattern_names(result: dict[str, Any]) -> list[str]:
    names = []
    for pattern in result.get("coherent_patterns") or []:
        if isinstance(pattern, dict):
            names.append(_normalize_pattern_name(str(pattern.get("name", ""))))
        else:
            names.append(_normalize_pattern_name(str(pattern)))
    return [n for n in names if n]


def correct_required_markers(state: dict[str, Any], pattern: str) -> list[str]:
    deviations = {
        d.get("marker"): d
        for d in state["structured"].get("deviations") or []
    }
    correct = []
    for marker, expected_direction in PATTERN_REQUIREMENTS[pattern]:
        dev = deviations.get(marker)
        if dev and dev.get("direction") == expected_direction:
            correct.append(marker)
    return correct


def relevant_evidence_type(state: dict[str, Any], inferred_patterns: list[str], pattern: str) -> str:
    if pattern in inferred_patterns:
        return "pattern"
    if correct_required_markers(state, pattern):
        return "partial_marker"
    return "none"


def _metric_mean(rows: list[dict[str, Any]], col: str) -> float | None:
    vals = [float(row[col]) for row in rows if row.get(col) not in ("", None)]
    return round(mean(vals), 3) if vals else None


RATER_SYSTEM_PROMPT = """You are a blinded evaluator of calendar recommendations.

You will receive cases with an inferred behavioral state from a passive-sensing
pipeline, protected/flexible calendar events, and two anonymized recommendations
named A and B. Rate each option from 1 to 5 on:
- relevance: useful for the calendar situation
- behavioral_alignment: uses the inferred behavioral state appropriately
- feasibility: realistic and low-friction
- safety: avoids clinical claims and does not modify fixed events
- specificity: concrete enough to act on

You do not know which option is behavior-aware. Use only the inferred state and
calendar shown in the case. Do not use hidden latent causes. Output only JSON:
{"ratings":[{"case_id":"...","A":{"relevance":1,"behavioral_alignment":1,
"feasibility":1,"safety":1,"specificity":1},"B":{...},"preferred":"A"}]}.
"""


def _extract_json_object(text: str) -> dict[str, Any]:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
        t = t.strip()
    start = t.find("{")
    end = t.rfind("}")
    if start < 0 or end < 0:
        raise ValueError(f"No JSON object in rater response: {text[:200]}")
    return json.loads(t[start : end + 1])


def _state_brief(log: dict[str, Any]) -> str:
    state = log["inferred_state"]["structured"]
    deviations = state.get("deviations") or []
    layer3_patterns = [p.get("name") for p in state.get("coherent_patterns") or []]
    layer4_patterns = log.get("layer4_patterns") or []
    dev_bits = [
        f"{d.get('marker')} {d.get('direction')} {d.get('magnitude')} ({d.get('trajectory')})"
        for d in deviations[:8]
    ]
    return (
        f"confidence={state.get('baseline_state', {}).get('overall_confidence')}; "
        f"Layer1-3 patterns={layer3_patterns}; Layer4 patterns={layer4_patterns}; "
        f"deviations={dev_bits}; coverage_notes={state.get('coverage_notes')[:4]}"
    )


def build_blinded_rows(decision_logs: list[dict[str, Any]], seed: int) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
    rng = np.random.default_rng(seed + 303)
    rows: list[dict[str, Any]] = []
    option_maps: dict[str, dict[str, str]] = {}
    for log in decision_logs:
        case_id = log["case_id"]
        ba = log["recommendations"]["behavior_aware"]
        co = log["recommendations"]["calendar_only"]
        if rng.random() < 0.5:
            option_maps[case_id] = {"A": "behavior_aware", "B": "calendar_only"}
            options = {"A": ba, "B": co}
        else:
            option_maps[case_id] = {"A": "calendar_only", "B": "behavior_aware"}
            options = {"A": co, "B": ba}

        for option, result in options.items():
            suggestions = result.get("suggestions") or []
            grounded = sorted(
                {
                    str(item)
                    for suggestion in suggestions
                    for item in (suggestion.get("grounded_in") or [])
                }
            )
            rows.append(
                {
                    "case_id": case_id,
                    "option": option,
                    "participant_id": log["participant_id"],
                    "date": log["date"],
                    "calendar_summary": calendar_summary(log["calendar_window"]),
                    "inferred_state_for_context": _state_brief(log),
                    "recommendation": suggestion_text(result),
                    "reason": result.get("salience_reasoning", ""),
                    "grounded_in": ", ".join(grounded),
                    "safety_note": "Fixed events were labeled protected; flexible events were labeled movable.",
                    "relevance_1_5": "",
                    "behavioral_alignment_1_5": "",
                    "feasibility_1_5": "",
                    "safety_1_5": "",
                    "specificity_1_5": "",
                    "overall_preferred_A_or_B": "",
                }
            )
    return rows, option_maps


def rate_blinded_cases(
    rows: list[dict[str, Any]],
    cache_dir: Path,
    model: str | None,
    chunk_size: int = 8,
) -> list[dict[str, Any]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_case[row["case_id"]].append(row)

    case_ids = sorted(by_case)
    ratings_by_case: dict[str, dict[str, Any]] = {}
    client = anthropic.Anthropic(api_key=layer4_config.get_api_key())
    model_id = model or layer4_config.DEFAULT_MODEL

    for chunk_start in range(0, len(case_ids), chunk_size):
        chunk_ids = case_ids[chunk_start : chunk_start + chunk_size]
        cases = []
        for case_id in chunk_ids:
            options = {row["option"]: row for row in by_case[case_id]}
            cases.append(
                {
                    "case_id": case_id,
                    "calendar": options["A"]["calendar_summary"],
                    "inferred_state": options["A"]["inferred_state_for_context"],
                    "A": {
                        "recommendation": options["A"]["recommendation"],
                        "reason": options["A"]["reason"],
                        "grounded_in": options["A"]["grounded_in"],
                    },
                    "B": {
                        "recommendation": options["B"]["recommendation"],
                        "reason": options["B"]["reason"],
                        "grounded_in": options["B"]["grounded_in"],
                    },
                }
            )
        digest = hashlib.sha256(json.dumps(cases, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        cache_path = cache_dir / f"rater_{chunk_start:04d}_{digest}.json"
        if cache_path.exists():
            parsed = json.loads(cache_path.read_text())
        else:
            resp = client.messages.create(
                model=model_id,
                max_tokens=4096,
                temperature=0.0,
                system=RATER_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": "Rate these blinded cases:\n\n"
                        + json.dumps({"cases": cases}, indent=2, default=_json_default),
                    }
                ],
            )
            parsed = _extract_json_object(resp.content[0].text)
            parsed["_meta"] = {
                "model": model_id,
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            _write_json(cache_path, parsed)

        for item in parsed.get("ratings") or []:
            ratings_by_case[item["case_id"]] = item

    rated_rows: list[dict[str, Any]] = []
    for row in rows:
        rated = dict(row)
        item = ratings_by_case.get(row["case_id"], {})
        opt_rating = item.get(row["option"], {})
        rated["relevance_1_5"] = opt_rating.get("relevance", "")
        rated["behavioral_alignment_1_5"] = opt_rating.get("behavioral_alignment", "")
        rated["feasibility_1_5"] = opt_rating.get("feasibility", "")
        rated["safety_1_5"] = opt_rating.get("safety", "")
        rated["specificity_1_5"] = opt_rating.get("specificity", "")
        rated["overall_preferred_A_or_B"] = item.get("preferred", "")
        rated_rows.append(rated)
    return rated_rows


def summarize_rater(rated_rows: list[dict[str, Any]], option_maps: dict[str, dict[str, str]]) -> dict[str, Any]:
    scored: list[dict[str, Any]] = []
    for row in rated_rows:
        arm = option_maps[row["case_id"]][row["option"]]
        with_arm = dict(row)
        with_arm["arm"] = arm
        scored.append(with_arm)

    metrics = [
        "relevance_1_5",
        "behavioral_alignment_1_5",
        "feasibility_1_5",
        "safety_1_5",
        "specificity_1_5",
    ]
    by_arm = {}
    for arm in ("behavior_aware", "calendar_only"):
        sub = [row for row in scored if row["arm"] == arm]
        by_arm[arm] = {metric: _metric_mean(sub, metric) for metric in metrics}

    preferred_counts = Counter()
    seen_cases = set()
    for row in scored:
        case_id = row["case_id"]
        if case_id in seen_cases:
            continue
        seen_cases.add(case_id)
        preferred = row.get("overall_preferred_A_or_B")
        if preferred in ("A", "B"):
            preferred_counts[option_maps[case_id][preferred]] += 1

    return {
        "means_by_arm": by_arm,
        "preferred_counts": dict(preferred_counts),
        "behavior_aware_preference_rate": round(
            preferred_counts["behavior_aware"] / max(1, sum(preferred_counts.values())), 3
        ),
        "scored_rows": scored,
    }


def summarize_programmatic(check_rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for arm in ("behavior_aware", "calendar_only"):
        rows = [r for r in check_rows if r["arm"] == arm]
        summary[arm] = {
            "n": len(rows),
            "lever_pass_rate": round(mean(float(r["lever_pass"]) for r in rows), 3) if rows else None,
            "flexible_event_pass_rate": round(mean(float(r["flexible_event_pass"]) for r in rows), 3) if rows else None,
            "burden_pass_rate": round(mean(float(r["burden_pass"]) for r in rows), 3) if rows else None,
            "specificity_pass_rate": round(mean(float(r["specificity_pass"]) for r in rows), 3) if rows else None,
            "high_burden_change_rate": round(mean(float(r["high_burden_change"]) for r in rows), 3) if rows else None,
            "no_change_rate": round(mean(float(r["no_change_recommended"]) for r in rows), 3) if rows else None,
            "all_three_pass_rate": round(mean(float(r["all_three_pass"]) for r in rows), 3) if rows else None,
            "mean_burden_score": round(mean(float(r["burden_score"]) for r in rows), 3) if rows else None,
        }
    return summary


def _rate(rows: list[dict[str, Any]], key: str) -> float | None:
    return round(mean(float(r[key]) for r in rows), 3) if rows else None


def summarize_detection_sensitivity(decision_logs: list[dict[str, Any]]) -> dict[str, Any]:
    episode_logs = [log for log in decision_logs if log["ground_truth"]["active_episode"]]
    by_pattern = {}
    for pattern in STATE_NAMES:
        sub = [
            log for log in episode_logs
            if log["ground_truth"]["predisposed_pattern"] == pattern
        ]
        by_pattern[pattern] = {
            "episode_decision_days": len(sub),
            "detected_days": sum(
                1 for log in sub
                if log["ground_truth"]["predisposed_pattern"] in log["inferred_patterns_union"]
            ),
            "sensitivity": round(
                mean(
                    float(log["ground_truth"]["predisposed_pattern"] in log["inferred_patterns_union"])
                    for log in sub
                ),
                3,
            ) if sub else None,
        }
    return {
        "definition": "P(full pipeline emits predisposed pattern | decision day is inside a ground-truth episode)",
        "overall": {
            "episode_decision_days": len(episode_logs),
            "detected_days": sum(
                1 for log in episode_logs
                if log["ground_truth"]["predisposed_pattern"] in log["inferred_patterns_union"]
            ),
            "sensitivity": round(
                mean(
                    float(log["ground_truth"]["predisposed_pattern"] in log["inferred_patterns_union"])
                    for log in episode_logs
                ),
                3,
            ) if episode_logs else None,
        },
        "by_pattern": by_pattern,
    }


def summarize_conditional_quality(check_rows: list[dict[str, Any]]) -> dict[str, Any]:
    detected_case_ids = {
        r["case_id"]
        for r in check_rows
        if r["arm"] == "behavior_aware" and r["pipeline_detected_predisposed_pattern"]
    }
    out: dict[str, Any] = {
        "definition": "quality on non-handed dimensions for cases where the full pipeline emitted the predisposed pattern",
        "n_cases": len(detected_case_ids),
    }
    for arm in ("behavior_aware", "calendar_only"):
        rows = [r for r in check_rows if r["arm"] == arm and r["case_id"] in detected_case_ids]
        out[arm] = {
            "n": len(rows),
            "burden_appropriate_rate": _rate(rows, "burden_pass"),
            "flexible_fixed_protection_rate": _rate(rows, "flexible_event_pass"),
            "specificity_rate": _rate(rows, "specificity_pass"),
            "high_burden_change_rate": _rate(rows, "high_burden_change"),
            "mean_burden_score": round(mean(float(r["burden_score"]) for r in rows), 3) if rows else None,
        }
    return out


def summarize_normal_day_restraint(check_rows: list[dict[str, Any]]) -> dict[str, Any]:
    normal_case_ids = {
        r["case_id"]
        for r in check_rows
        if r["arm"] == "behavior_aware" and not r["active_episode"]
    }
    out: dict[str, Any] = {
        "definition": "restraint on normal decision days outside any ground-truth episode; lower high_burden_change_rate is better",
        "n_cases": len(normal_case_ids),
    }
    for arm in ("behavior_aware", "calendar_only"):
        rows = [r for r in check_rows if r["arm"] == arm and r["case_id"] in normal_case_ids]
        out[arm] = {
            "n": len(rows),
            "high_burden_change_rate": _rate(rows, "high_burden_change"),
            "no_change_rate": _rate(rows, "no_change_recommended"),
            "mean_burden_score": round(mean(float(r["burden_score"]) for r in rows), 3) if rows else None,
            "mean_suggestions": round(mean(float(r["n_suggestions"]) for r in rows), 3) if rows else None,
            "burden_appropriate_rate": _rate(rows, "burden_pass"),
        }
    return out


def summarize_lever_credit_by_detection(check_rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "definition": "diagnostic only; raw latent-cause credit is de-emphasized because behavior-aware is handed inferred behavioral evidence on detected days",
    }
    for arm in ("behavior_aware", "calendar_only"):
        rows = [r for r in check_rows if r["arm"] == arm]
        detected = [r for r in rows if r["received_relevant_evidence"]]
        non_detected = [r for r in rows if not r["received_relevant_evidence"]]
        overall = _rate(rows, "lever_pass")
        detected_rate = _rate(detected, "lever_pass")
        non_detected_rate = _rate(non_detected, "lever_pass")
        weighted = None
        if detected_rate is not None and non_detected_rate is not None and rows:
            weighted = round(
                (detected_rate * len(detected) + non_detected_rate * len(non_detected)) / len(rows),
                3,
            )
        out[arm] = {
            "overall": overall,
            "detected_or_marker_evidence_subset": detected_rate,
            "non_detected_subset": non_detected_rate,
            "n_detected_or_marker_evidence": len(detected),
            "n_non_detected": len(non_detected),
            "weighted_reconstruction": weighted,
            "weighted_matches_overall": (
                abs((weighted or 0.0) - (overall or 0.0)) <= 0.002
                if weighted is not None and overall is not None else None
            ),
            "overall_between_subsets": (
                min(detected_rate, non_detected_rate) <= overall <= max(detected_rate, non_detected_rate)
                if detected_rate is not None and non_detected_rate is not None and overall is not None else None
            ),
        }
    return out


def diagnose_detection_misses(
    decision_logs: list[dict[str, Any]],
) -> dict[str, Any]:
    missed_logs = [
        log for log in decision_logs
        if log["ground_truth"]["active_episode"]
        and log["ground_truth"]["predisposed_pattern"] not in log["inferred_patterns_union"]
    ]
    reason_counts: Counter[str] = Counter()
    by_pattern: dict[str, Counter[str]] = defaultdict(Counter)
    marker_missing_counts: Counter[str] = Counter()
    marker_correct_counts: Counter[str] = Counter()
    marker_wrong_counts: Counter[str] = Counter()

    for log in missed_logs:
        pattern = log["ground_truth"]["predisposed_pattern"]
        deviations = {
            d.get("marker"): d
            for d in log["inferred_state"]["structured"].get("deviations") or []
        }
        correct = []
        wrong_direction = []
        absent = []
        for marker, expected_direction in PATTERN_REQUIREMENTS[pattern]:
            dev = deviations.get(marker)
            if not dev:
                absent.append(marker)
                marker_missing_counts[marker] += 1
                continue
            if dev.get("direction") == expected_direction:
                correct.append(marker)
                marker_correct_counts[marker] += 1
            else:
                wrong_direction.append(marker)
                marker_wrong_counts[marker] += 1

        if not correct and absent:
            reason = "no_required_marker_crossed_layer2_threshold"
        elif correct and absent:
            reason = "partial_required_markers_only_coherence_rule_not_satisfied"
        elif wrong_direction:
            reason = "required_marker_deviated_wrong_direction"
        else:
            reason = "layer4_did_not_name_latent_pattern"
        reason_counts[reason] += 1
        by_pattern[pattern][reason] += 1

    total_misses = len(missed_logs)
    return {
        "detection_note": (
            "Misses are counted only on ground-truth episode decision days. The generator now injects "
            "episodic required-marker shifts, but early episode days can still miss because Layer 2 uses "
            "a 4-day recent window against a 21-day rolling baseline; missing marker-days can also leave "
            "only a partial coherent-pattern signature."
        ),
        "n_episode_missed_cases": total_misses,
        "reason_counts": dict(reason_counts),
        "reason_rates": {
            reason: round(count / total_misses, 3) if total_misses else None
            for reason, count in reason_counts.items()
        },
        "by_pattern": {
            pattern: {
                "n": sum(counter.values()),
                "reason_counts": dict(counter),
            }
            for pattern, counter in by_pattern.items()
        },
        "required_marker_absent_counts": dict(marker_missing_counts),
        "required_marker_correct_but_incomplete_counts": dict(marker_correct_counts),
        "required_marker_wrong_direction_counts": dict(marker_wrong_counts),
    }


def write_marker_csv(path: Path, raw_days_by_pid: dict[str, list[dict[str, Any]]]) -> None:
    rows: list[dict[str, Any]] = []
    for pid, raw_days in raw_days_by_pid.items():
        for day_index, raw in enumerate(raw_days, start=1):
            row = {"participant_id": pid, "day_index": day_index}
            for col in MARKER_COLUMNS:
                value = raw.get(col)
                if col == "date" and isinstance(value, date):
                    value = value.isoformat()
                if col == "_coverage":
                    value = json.dumps(value, sort_keys=True)
                row[col] = value
            rows.append(row)
    _write_csv(path, rows, fieldnames=["participant_id", "day_index", *MARKER_COLUMNS])


def write_detection_sensitivity_csv(path: Path, summary: dict[str, Any]) -> None:
    rows = [{
        "pattern": "overall",
        **summary["overall"],
    }]
    for pattern, values in summary["by_pattern"].items():
        rows.append({"pattern": pattern, **values})
    _write_csv(path, rows)


def write_arm_metric_csv(path: Path, summary: dict[str, Any]) -> None:
    rows = []
    for arm in ("behavior_aware", "calendar_only"):
        if arm in summary:
            rows.append({"arm": arm, **summary[arm]})
    _write_csv(path, rows)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--n-participants", type=int, default=20)
    parser.add_argument("--n-days", type=int, default=42)
    parser.add_argument("--decision-start-day", type=int, default=29)
    parser.add_argument("--decision-end-day", type=int, default=42)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    parser.add_argument("--model", default=None, help="Scheduler model override.")
    parser.add_argument("--rater-model", default=None, help="Rater model override.")
    parser.add_argument("--scheduler-workers", type=int, default=4)
    parser.add_argument("--no-rater", action="store_true", help="Skip the secondary LLM rater.")
    parser.add_argument(
        "--max-decision-cases",
        type=int,
        default=None,
        help="Development/testing limit. Omit for the full 20 x 14 run.",
    )
    args = parser.parse_args(argv)

    outdir: Path = args.outdir.resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    cache_dir = outdir / "cache"

    profiles = sample_profiles(args.n_participants, args.seed)
    calendars = generate_calendar(profiles, args.n_days, DEFAULT_START_DATE, args.seed)

    raw_days_by_pid: dict[str, list[dict[str, Any]]] = {}
    hidden_daily: list[dict[str, Any]] = []
    hidden_episodes: list[dict[str, Any]] = []
    for profile in profiles:
        raw_days, hidden_rows, episode_rows = generate_marker_days(
            profile,
            calendars[profile.participant_id],
            args.n_days,
            DEFAULT_START_DATE,
            args.seed,
        )
        raw_days_by_pid[profile.participant_id] = raw_days
        hidden_daily.extend(hidden_rows)
        hidden_episodes.extend(episode_rows)
    hidden_by_key = {
        (row["participant_id"], row["day_index"]): row
        for row in hidden_daily
    }

    states = run_layers_1_to_3(raw_days_by_pid)

    _write_json(
        outdir / "run_config.json",
        {
            "seed": args.seed,
            "n_participants": args.n_participants,
            "n_days": args.n_days,
            "decision_days": [args.decision_start_day, args.decision_end_day],
            "pipeline_config": PIPELINE_CONFIG,
            "start_date": DEFAULT_START_DATE.isoformat(),
        },
    )
    _write_json(outdir / "hidden_profiles.json", [asdict(p) for p in profiles])
    _append_jsonl(outdir / "hidden_daily_drivers.jsonl", hidden_daily)
    _write_json(outdir / "hidden_episodes.json", hidden_episodes)
    write_marker_csv(outdir / "marker_days.csv", raw_days_by_pid)
    _append_jsonl(
        outdir / "calendar_events.jsonl",
        [event for pid in sorted(calendars) for event in calendars[pid]],
    )
    _append_jsonl(
        outdir / "layer_state_daily.jsonl",
        [
            {
                "participant_id": pid,
                "day_index": day_index,
                "date": rec["date"],
                "confidence": rec["confidence"],
                "coverage": rec["coverage"],
                "deviations": rec["deviations"],
                "layer_1_3_patterns": rec["layer_1_3_patterns"],
                "state": rec["state"]["structured"],
                "prose": rec["state"]["prose"],
            }
            for (pid, day_index), rec in sorted(states.items())
        ],
    )

    prefs = user_preferences()
    decision_specs: list[dict[str, Any]] = []
    cases_planned = 0
    for profile in profiles:
        for day_index in range(args.decision_start_day, args.decision_end_day + 1):
            if args.max_decision_cases is not None and cases_planned >= args.max_decision_cases:
                break
            case_id = f"{profile.participant_id}-D{day_index:02d}"
            state_rec = states[(profile.participant_id, day_index)]
            events = calendar_window(calendars[profile.participant_id], day_index)
            decision_specs.append(
                {
                    "case_id": case_id,
                    "profile": profile,
                    "day_index": day_index,
                    "state_rec": state_rec,
                    "events": events,
                    "calendar_only_state": calendar_only_state(state_rec["date"], day_index),
                }
            )
            cases_planned += 1
        if args.max_decision_cases is not None and cases_planned >= args.max_decision_cases:
            break

    scheduler_results: dict[tuple[str, str], dict[str, Any]] = {}
    scheduler_tasks = []
    for spec in decision_specs:
        scheduler_tasks.append(
            (
                spec["case_id"],
                "behavior_aware",
                spec["state_rec"]["state"],
                spec["events"],
            )
        )
        scheduler_tasks.append(
            (
                spec["case_id"],
                "calendar_only",
                spec["calendar_only_state"],
                spec["events"],
            )
        )

    completed = 0
    with ThreadPoolExecutor(max_workers=max(1, args.scheduler_workers)) as executor:
        future_to_task = {
            executor.submit(
                run_scheduler_cached,
                cache_dir / "scheduler",
                case_id,
                arm,
                state,
                events,
                prefs,
                args.model,
            ): (case_id, arm)
            for case_id, arm, state, events in scheduler_tasks
        }
        for future in as_completed(future_to_task):
            case_id, arm = future_to_task[future]
            scheduler_results[(case_id, arm)] = future.result()
            completed += 1
            print(
                f"[scheduler] {completed}/{len(scheduler_tasks)} {case_id} {arm} "
                f"cache={scheduler_results[(case_id, arm)].get('cache_hit')}",
                flush=True,
            )

    decision_logs: list[dict[str, Any]] = []
    check_rows: list[dict[str, Any]] = []
    layer4_raw_rows: list[dict[str, Any]] = []

    for spec in decision_specs:
        profile = spec["profile"]
        day_index = spec["day_index"]
        case_id = spec["case_id"]
        state_rec = spec["state_rec"]
        inferred_state = state_rec["state"]
        events = spec["events"]
        ba_payload = scheduler_results[(case_id, "behavior_aware")]
        co_payload = scheduler_results[(case_id, "calendar_only")]
        ba_result = ba_payload["result"]
        co_result = co_payload["result"]

        l13_patterns = [
            _normalize_pattern_name(p.get("name"))
            for p in inferred_state["structured"].get("coherent_patterns") or []
        ]
        l4_patterns = layer4_pattern_names(ba_result)
        inferred_patterns = sorted(set(p for p in [*l13_patterns, *l4_patterns] if p))
        gt_day = hidden_by_key[(profile.participant_id, day_index)]
        pipeline_detected_predisposed = profile.predisposed_pattern in inferred_patterns
        evidence_type = relevant_evidence_type(
            inferred_state,
            inferred_patterns,
            profile.predisposed_pattern,
        )
        received_relevant_evidence = evidence_type != "none"

        log = {
            "case_id": case_id,
            "participant_id": profile.participant_id,
            "day_index": day_index,
            "date": state_rec["date"],
            "calendar_window": events,
            "user_preferences": prefs,
            "inferred_state": inferred_state,
            "layer_1_3_patterns": l13_patterns,
            "layer4_patterns": l4_patterns,
            "inferred_patterns_union": inferred_patterns,
            "ground_truth": {
                "predisposed_pattern": profile.predisposed_pattern,
                "active_episode": bool(gt_day["in_episode"]),
                "episode_ids": gt_day["episode_ids"],
                "episode_patterns": gt_day["episode_patterns"],
                "episode_drivers": gt_day["episode_drivers"],
                "episode_marker_shifts": gt_day["episode_marker_shifts"],
            },
            "recommendations": {
                "behavior_aware": ba_result,
                "calendar_only": co_result,
            },
        }
        decision_logs.append(log)
        layer4_raw_rows.extend(
            [
                {
                    "case_id": case_id,
                    "arm": "behavior_aware",
                    "payload": ba_payload,
                },
                {
                    "case_id": case_id,
                    "arm": "calendar_only",
                    "payload": co_payload,
                },
            ]
        )

        for arm, result in (("behavior_aware", ba_result), ("calendar_only", co_result)):
            row = {
                "case_id": case_id,
                "participant_id": profile.participant_id,
                "day_index": day_index,
                "date": state_rec["date"],
                "latent_predisposed_pattern": profile.predisposed_pattern,
                "active_episode": bool(gt_day["in_episode"]),
                "episode_ids": "|".join(gt_day["episode_ids"]),
                "episode_drivers": "|".join(gt_day["episode_drivers"]),
                "inferred_patterns_union": "|".join(inferred_patterns),
                "pipeline_detected_predisposed_pattern": pipeline_detected_predisposed,
                "pipeline_recovered_latent": pipeline_detected_predisposed,
                "relevant_evidence_type": evidence_type,
                "received_relevant_evidence": (
                    arm == "behavior_aware" and received_relevant_evidence
                ),
                **evaluate_arm(
                    arm,
                    profile.predisposed_pattern,
                    profile.adherence_tendency,
                    result,
                    events,
                    received_relevant_evidence=(
                        arm == "behavior_aware" and received_relevant_evidence
                    ),
                ),
            }
            check_rows.append(row)

    _append_jsonl(outdir / "decision_logs.jsonl", decision_logs)
    _append_jsonl(outdir / "layer4_raw_outputs.jsonl", layer4_raw_rows)
    _write_csv(outdir / "programmatic_checks.csv", check_rows)

    recovery_rows = [r for r in check_rows if r["arm"] == "behavior_aware"]
    recovery_by_pattern = {}
    for pattern in STATE_NAMES:
        sub = [r for r in recovery_rows if r["latent_predisposed_pattern"] == pattern]
        recovery_by_pattern[pattern] = {
            "n": len(sub),
            "agreement_rate": round(mean(float(r["pipeline_recovered_latent"]) for r in sub), 3) if sub else None,
        }

    participant_recovery = {}
    for profile in profiles:
        sub = [r for r in recovery_rows if r["participant_id"] == profile.participant_id]
        if sub:
            participant_recovery[profile.participant_id] = any(r["pipeline_recovered_latent"] for r in sub)

    programmatic_summary = summarize_programmatic(check_rows)
    detection_sensitivity = summarize_detection_sensitivity(decision_logs)
    conditional_quality = summarize_conditional_quality(check_rows)
    normal_day_restraint = summarize_normal_day_restraint(check_rows)
    lever_credit_by_detection = summarize_lever_credit_by_detection(check_rows)
    detection_diagnostics = diagnose_detection_misses(decision_logs)
    rater_summary: dict[str, Any] | None = None
    if not args.no_rater and decision_logs:
        blinded_rows, option_maps = build_blinded_rows(decision_logs, args.seed)
        _write_csv(outdir / "rater_sheet_blinded.csv", blinded_rows)
        rated_rows = rate_blinded_cases(blinded_rows, cache_dir / "rater", args.rater_model)
        _write_csv(outdir / "rater_sheet_scored_blinded.csv", rated_rows)
        rater_summary = summarize_rater(rated_rows, option_maps)
        scored_rows = rater_summary.pop("scored_rows")
        _write_csv(outdir / "rater_sheet_scored_with_arm.csv", scored_rows)

    summary = {
        "seed": args.seed,
        "n_participants": len(profiles),
        "n_days_per_participant": args.n_days,
        "decision_days": [args.decision_start_day, args.decision_end_day],
        "n_decision_cases": len(decision_logs),
        "pipeline_config": PIPELINE_CONFIG,
        "profile_counts": dict(Counter(p.predisposed_pattern for p in profiles)),
        "pipeline_recovery": {
            "case_agreement_rate": round(
                mean(float(r["pipeline_recovered_latent"]) for r in recovery_rows), 3
            )
            if recovery_rows
            else None,
            "participant_recovered_any_rate": round(
                mean(float(v) for v in participant_recovery.values()), 3
            )
            if participant_recovery
            else None,
            "by_pattern": recovery_by_pattern,
        },
        "detection_sensitivity": detection_sensitivity,
        "conditional_on_detection_quality": conditional_quality,
        "normal_day_restraint": normal_day_restraint,
        "lever_credit_by_detection": lever_credit_by_detection,
        "detection_diagnostics": detection_diagnostics,
        "programmatic_consistency": programmatic_summary,
        "llm_rater": rater_summary,
        "artifacts": {
            "run_config": str(outdir / "run_config.json"),
            "hidden_profiles": str(outdir / "hidden_profiles.json"),
            "hidden_episodes": str(outdir / "hidden_episodes.json"),
            "hidden_daily_drivers": str(outdir / "hidden_daily_drivers.jsonl"),
            "marker_days": str(outdir / "marker_days.csv"),
            "calendar_events": str(outdir / "calendar_events.jsonl"),
            "layer_state_daily": str(outdir / "layer_state_daily.jsonl"),
            "decision_logs": str(outdir / "decision_logs.jsonl"),
            "programmatic_checks": str(outdir / "programmatic_checks.csv"),
            "detection_sensitivity": str(outdir / "detection_sensitivity.json"),
            "detection_sensitivity_table": str(outdir / "detection_sensitivity.csv"),
            "conditional_on_detection_quality": str(outdir / "conditional_on_detection_quality.json"),
            "conditional_on_detection_quality_table": str(outdir / "conditional_on_detection_quality.csv"),
            "normal_day_restraint": str(outdir / "normal_day_restraint.json"),
            "normal_day_restraint_table": str(outdir / "normal_day_restraint.csv"),
            "lever_credit_by_detection": str(outdir / "lever_credit_by_detection.json"),
            "detection_diagnostics": str(outdir / "detection_diagnostics.json"),
            "summary": str(outdir / "summary.json"),
        },
    }
    if rater_summary is not None:
        summary["artifacts"].update(
            {
                "rater_sheet_blinded": str(outdir / "rater_sheet_blinded.csv"),
                "rater_sheet_scored_blinded": str(outdir / "rater_sheet_scored_blinded.csv"),
                "rater_sheet_scored_with_arm": str(outdir / "rater_sheet_scored_with_arm.csv"),
            }
        )

    _write_json(outdir / "programmatic_summary.json", programmatic_summary)
    _write_json(outdir / "detection_sensitivity.json", detection_sensitivity)
    write_detection_sensitivity_csv(outdir / "detection_sensitivity.csv", detection_sensitivity)
    _write_json(outdir / "conditional_on_detection_quality.json", conditional_quality)
    write_arm_metric_csv(outdir / "conditional_on_detection_quality.csv", conditional_quality)
    _write_json(outdir / "normal_day_restraint.json", normal_day_restraint)
    write_arm_metric_csv(outdir / "normal_day_restraint.csv", normal_day_restraint)
    _write_json(outdir / "lever_credit_by_detection.json", lever_credit_by_detection)
    _write_json(outdir / "detection_diagnostics.json", detection_diagnostics)
    _write_json(outdir / "summary.json", summary)
    readme = (
        "# Latent Longitudinal Simulation\n\n"
        f"- Seed: `{args.seed}`\n"
        f"- Participants: `{len(profiles)}`\n"
        f"- Days per participant: `{args.n_days}`\n"
        f"- Decision days: `{args.decision_start_day}-{args.decision_end_day}`\n"
        f"- Pipeline config: `{PIPELINE_CONFIG}`\n\n"
        "Schedulers never receive `hidden_profiles.json` or `hidden_daily_drivers.jsonl`. "
        "The behavior-aware arm receives the Layer 1-4 inferred state; the calendar-only "
        "arm receives the same calendar and preferences with an empty behavioral state.\n"
    )
    (outdir / "README.md").write_text(readme)
    print(json.dumps(summary, indent=2, default=_json_default))


if __name__ == "__main__":
    main()
