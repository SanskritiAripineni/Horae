"""
Smoke-test longitudinal behavior-aware scheduling simulation.

Presets:
  - sample: 2 participants, 7 days, 3 passive baseline days
  - medium: 5 participants, 14 days, 7 passive baseline days

The sample is intentionally small. Its purpose is to verify that simulated
profiles, calendars, sensing traces, AutoLife summaries, behavioral-state
inference, scheduler inputs, blinded outputs, and rater exports all connect.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from dataclasses import dataclass, asdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from layer1 import PersonalBaseline, markers_from_raw  # noqa: E402
from layer2 import detect_deviations, find_coherent_patterns  # noqa: E402
from layer3 import build_state_description  # noqa: E402


SIM_DIR = Path(__file__).resolve().parent
START_DATE = date(2026, 3, 2)
SEED = 20260615


@dataclass(frozen=True)
class SimulationConfig:
    name: str
    participants: int
    n_days: int
    baseline_days: int
    max_decision_days_per_participant: int


CONFIGS = {
    "sample": SimulationConfig(
        name="sample",
        participants=2,
        n_days=7,
        baseline_days=3,
        max_decision_days_per_participant=2,
    ),
    "medium": SimulationConfig(
        name="medium",
        participants=5,
        n_days=14,
        baseline_days=7,
        max_decision_days_per_participant=3,
    ),
}

ACTIVE_CONFIG = CONFIGS["sample"]
OUTPUT_DIR = SIM_DIR.parent / "simulation_outputs" / ACTIVE_CONFIG.name


def set_active_config(preset: str) -> None:
    global ACTIVE_CONFIG, OUTPUT_DIR
    ACTIVE_CONFIG = CONFIGS[preset]
    OUTPUT_DIR = SIM_DIR.parent / "simulation_outputs" / ACTIVE_CONFIG.name


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Any) -> None:
    ensure_output_dir()
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: Path, rows: list[dict]) -> None:
    ensure_output_dir()
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def daterange() -> list[date]:
    return [START_DATE + timedelta(days=i) for i in range(ACTIVE_CONFIG.n_days)]


@dataclass
class ParticipantProfile:
    participant_id: str
    archetype: str
    chronotype: str
    sleep_regularity: str
    workload: str
    schedule_flexibility: str
    mobility_pattern: str
    social_rhythm: str
    phone_use_tendency: str
    adherence_tendency: str
    stress_sensitivity: str


def path(name: str) -> Path:
    return OUTPUT_DIR / name


def _profile_pool() -> list[ParticipantProfile]:
    return [
        ParticipantProfile(
            participant_id="P001",
            archetype="late-night overloaded student",
            chronotype="evening",
            sleep_regularity="moderately variable",
            workload="heavy",
            schedule_flexibility="medium",
            mobility_pattern="campus-centered",
            social_rhythm="regular",
            phone_use_tendency="late-night-heavy",
            adherence_tendency="medium",
            stress_sensitivity="high",
        ),
        ParticipantProfile(
            participant_id="P002",
            archetype="restricted-mobility deadline week student",
            chronotype="neutral",
            sleep_regularity="stable",
            workload="heavy",
            schedule_flexibility="high",
            mobility_pattern="restricted-after-deadline",
            social_rhythm="clustered",
            phone_use_tendency="moderate",
            adherence_tendency="high",
            stress_sensitivity="medium",
        ),
        ParticipantProfile(
            participant_id="P003",
            archetype="circadian-instability student",
            chronotype="evening",
            sleep_regularity="unstable",
            workload="moderate",
            schedule_flexibility="medium",
            mobility_pattern="mixed",
            social_rhythm="irregular",
            phone_use_tendency="moderate",
            adherence_tendency="medium",
            stress_sensitivity="medium",
        ),
        ParticipantProfile(
            participant_id="P004",
            archetype="sleep-loss fragmented-attention student",
            chronotype="neutral",
            sleep_regularity="moderately variable",
            workload="heavy",
            schedule_flexibility="low",
            mobility_pattern="work-centered",
            social_rhythm="regular",
            phone_use_tendency="high",
            adherence_tendency="low",
            stress_sensitivity="high",
        ),
        ParticipantProfile(
            participant_id="P005",
            archetype="mixed late-work student",
            chronotype="neutral",
            sleep_regularity="moderately variable",
            workload="heavy",
            schedule_flexibility="high",
            mobility_pattern="campus-centered",
            social_rhythm="clustered",
            phone_use_tendency="late-night-heavy",
            adherence_tendency="medium",
            stress_sensitivity="medium",
        ),
    ]


def stage_profiles() -> None:
    profiles = _profile_pool()[:ACTIVE_CONFIG.participants]
    write_json(path("participants.json"), [asdict(p) for p in profiles])
    print(
        "Section 1 complete: generated "
        f"{ACTIVE_CONFIG.participants} simulated participant profiles."
    )
    print(f"Generated: {path('participants.json')}")


def _calendar_for_day(profile: dict, day: date, day_index: int) -> list[dict]:
    base = [
        {
            "start": "08:30",
            "end": "09:45",
            "title": "class",
            "flexibility": "fixed",
            "category": "academic",
        },
        {
            "start": "10:30",
            "end": "11:15",
            "title": "project meeting",
            "flexibility": "fixed",
            "category": "academic",
        },
        {
            "start": "15:00",
            "end": "17:00",
            "title": "study block",
            "flexibility": "flexible",
            "category": "work",
        },
    ]
    pid = profile["participant_id"]
    if pid in {"P001", "P003", "P005"}:
        base.append({
            "start": "21:00",
            "end": "22:30",
            "title": "optional work session",
            "flexibility": "flexible",
            "category": "work",
        })
    if pid == "P004":
        base.extend([
            {
                "start": "13:00",
                "end": "14:00",
                "title": "lab prep",
                "flexibility": "flexible",
                "category": "work",
            },
            {
                "start": "19:30",
                "end": "21:30",
                "title": "problem set work",
                "flexibility": "flexible",
                "category": "work",
            },
        ])
    else:
        if pid == "P002":
            base.extend([
                {
                    "start": "12:30",
                    "end": "13:15",
                    "title": "lunch outside",
                    "flexibility": "flexible",
                    "category": "restorative",
                },
                {
                    "start": "18:00",
                    "end": "19:00",
                    "title": "gym",
                    "flexibility": "flexible",
                    "category": "restorative",
                },
            ])
        if pid == "P002" and day_index > ACTIVE_CONFIG.baseline_days:
            base = [
                event for event in base
                if event["title"] not in {"lunch outside", "gym"}
            ]
            base.append({
                "start": "20:00",
                "end": "22:00",
                "title": "deadline work block",
                "flexibility": "flexible",
                "category": "work",
            })
    for event in base:
        event["date"] = day.isoformat()
    return base


def stage_calendars() -> None:
    profiles = read_json(path("participants.json"))
    rows = []
    for profile in profiles:
        for idx, day in enumerate(daterange(), start=1):
            rows.append({
                "participant_id": profile["participant_id"],
                "date": day.isoformat(),
                "day_index": idx,
                "events": _calendar_for_day(profile, day, idx),
            })
    write_jsonl(path("daily_calendars.jsonl"), rows)
    print(
        "Section 2 complete: generated "
        f"{ACTIVE_CONFIG.n_days}-day calendars for "
        f"{ACTIVE_CONFIG.participants} participants."
    )
    print(f"Generated: {path('daily_calendars.jsonl')}")


PLACES = {
    "home": (42.7280, -73.6780),
    "classroom": (42.7296, -73.6801),
    "library": (42.7302, -73.6786),
    "gym": (42.7311, -73.6767),
    "dining": (42.7287, -73.6769),
    "social": (42.7320, -73.6798),
}


def _place_for_time(profile: dict, day_index: int, hour: int) -> str:
    pid = profile["participant_id"]
    if hour < 8:
        return "home"
    if 8 <= hour < 10:
        return "classroom"
    if 10 <= hour < 12:
        return "classroom"
    if 12 <= hour < 14:
        return "dining" if not (pid == "P002" and day_index > ACTIVE_CONFIG.baseline_days) else "home"
    if 14 <= hour < 18:
        if pid == "P002" and day_index > ACTIVE_CONFIG.baseline_days:
            return "home"
        return "library"
    if 18 <= hour < 20:
        if pid in {"P001", "P003", "P005"}:
            return "dining"
        return "gym" if day_index <= ACTIVE_CONFIG.baseline_days else "home"
    if 20 <= hour < 23:
        if pid in {"P001", "P005"}:
            return "library" if day_index > ACTIVE_CONFIG.baseline_days else "social"
        if pid == "P003":
            return "social" if day_index % 2 == 0 else "home"
        if pid == "P004":
            return "library"
        return "home"
    return "home"


def _gps_points(profile: dict, day: date, day_index: int, rng: random.Random) -> list[dict]:
    points = []
    for slot in range(96):
        ts = datetime.combine(day, time(0, 0)) + timedelta(minutes=15 * slot)
        if rng.random() < 0.08:
            points.append({
                "timestamp": ts.isoformat(),
                "semantic_place": None,
                "lat": None,
                "lon": None,
                "accuracy_m": None,
                "missing": True,
            })
            continue
        place = _place_for_time(profile, day_index, ts.hour)
        lat, lon = PLACES[place]
        jitter = 0.00025
        points.append({
            "timestamp": ts.isoformat(),
            "semantic_place": place,
            "lat": round(lat + rng.uniform(-jitter, jitter), 6),
            "lon": round(lon + rng.uniform(-jitter, jitter), 6),
            "accuracy_m": rng.choice([20, 30, 35, 45, 60]),
            "missing": False,
        })
    return points


def _raw_day(profile: dict, day: date, day_index: int, rng: random.Random) -> dict:
    pid = profile["participant_id"]
    after_baseline = day_index > ACTIVE_CONFIG.baseline_days + 1

    sleep_onset = 23.1 + rng.uniform(-0.14, 0.14)
    sleep_duration = 7.7 + rng.uniform(-0.2, 0.2)
    late_screen = 28 + rng.uniform(-6, 6)
    total_screen = 240 + rng.uniform(-25, 25)
    app_switch = 1.05 + rng.uniform(-0.16, 0.16)
    mobility_entropy = 1.78 + rng.uniform(-0.09, 0.09)
    revisit = 0.61 + rng.uniform(-0.04, 0.04)
    srm = 0.80 + rng.uniform(-0.04, 0.04)
    sleep_regularity = 84 - abs(sleep_onset - 23.2) * 3 + rng.uniform(-1.5, 1.5)

    if pid == "P001":
        sleep_onset = 23.35 + rng.uniform(-0.15, 0.15)
        sleep_duration = 7.5 + rng.uniform(-0.2, 0.2)
        late_screen = 30 + rng.uniform(-6, 6)
        total_screen = 260 + rng.uniform(-30, 30)
        app_switch = 1.2 + rng.uniform(-0.2, 0.2)
        if after_baseline:
            sleep_onset = 25.15 + rng.uniform(-0.2, 0.2)
            sleep_duration = 6.25 + rng.uniform(-0.2, 0.2)
            late_screen = 105 + rng.uniform(-10, 10)
            total_screen = 350 + rng.uniform(-25, 25)
            app_switch = 1.8 + rng.uniform(-0.15, 0.2)
            sleep_regularity = 70 + rng.uniform(-3, 3)
    elif pid == "P002":
        sleep_onset = 23.0 + rng.uniform(-0.12, 0.12)
        sleep_duration = 7.8 + rng.uniform(-0.2, 0.2)
        mobility_entropy = 1.85 + rng.uniform(-0.08, 0.08)
        revisit = 0.58 + rng.uniform(-0.03, 0.03)
        srm = 0.82 + rng.uniform(-0.04, 0.04)
        if after_baseline:
            mobility_entropy = 0.75 + rng.uniform(-0.08, 0.08)
            revisit = 0.90 + rng.uniform(-0.03, 0.03)
            srm = 0.55 + rng.uniform(-0.05, 0.05)
            total_screen = 300 + rng.uniform(-25, 25)
    elif pid == "P003":
        sleep_onset = 23.4 + rng.uniform(-0.2, 0.2)
        sleep_duration = 7.4 + rng.uniform(-0.25, 0.25)
        sleep_regularity = 86 + rng.uniform(-2, 2)
        if after_baseline:
            swing = 1.2 if day_index % 2 == 0 else -0.8
            sleep_onset = 24.5 + swing + rng.uniform(-0.18, 0.18)
            sleep_duration = 7.0 + rng.uniform(-0.35, 0.25)
            sleep_regularity = 60 + rng.uniform(-4, 4)
            srm = 0.52 + rng.uniform(-0.05, 0.05)
    elif pid == "P004":
        sleep_duration = 7.6 + rng.uniform(-0.18, 0.18)
        app_switch = 1.0 + rng.uniform(-0.12, 0.12)
        if after_baseline:
            sleep_duration = 5.8 + rng.uniform(-0.25, 0.2)
            app_switch = 2.05 + rng.uniform(-0.25, 0.2)
            total_screen = 330 + rng.uniform(-30, 30)
            late_screen = 70 + rng.uniform(-10, 10)
    elif pid == "P005":
        sleep_duration = 7.5 + rng.uniform(-0.2, 0.2)
        late_screen = 35 + rng.uniform(-6, 6)
        if after_baseline:
            sleep_onset = 24.6 + rng.uniform(-0.18, 0.18)
            late_screen = 95 + rng.uniform(-12, 12)
            mobility_entropy = 1.2 + rng.uniform(-0.08, 0.08)
            revisit = 0.78 + rng.uniform(-0.04, 0.04)
            srm = 0.62 + rng.uniform(-0.05, 0.05)

    missing_screen = rng.random() < 0.05
    return {
        "participant_id": pid,
        "date": day.isoformat(),
        "day_index": day_index,
        "sleep_onset_hour": sleep_onset,
        "sleep_duration_hours": sleep_duration,
        "sleep_regularity_index": sleep_regularity,
        "late_night_screen_min": None if missing_screen else late_screen,
        "total_screen_min": None if missing_screen else total_screen,
        "app_switching_rate": app_switch,
        "mobility_entropy": mobility_entropy,
        "location_revisit_ratio": revisit,
        "social_rhythm_metric": srm,
        "comm_reciprocity": 0.55 + rng.uniform(-0.08, 0.08),
        "_coverage": {
            "sleep_onset_hour": 0.95,
            "sleep_duration_hours": 0.95,
            "sleep_regularity_index": 0.85,
            "late_night_screen_min": 0.0 if missing_screen else 0.85,
            "total_screen_min": 0.0 if missing_screen else 0.9,
            "app_switching_rate": 0.85,
            "mobility_entropy": 0.8,
            "location_revisit_ratio": 0.8,
            "social_rhythm_metric": 0.75,
            "comm_reciprocity": 0.55,
        },
        "gps_points": _gps_points(profile, day, day_index, rng),
    }


def stage_sensors() -> None:
    rng = random.Random(SEED)
    profiles = read_json(path("participants.json"))
    raw_days = []
    gps_rows = []
    for profile in profiles:
        for idx, day in enumerate(daterange(), start=1):
            raw = _raw_day(profile, day, idx, rng)
            gps_points = raw.pop("gps_points")
            raw_days.append(raw)
            for point in gps_points:
                point["participant_id"] = profile["participant_id"]
                point["date"] = day.isoformat()
                gps_rows.append(point)
    write_jsonl(path("daily_behavior_raw.jsonl"), raw_days)
    write_jsonl(path("raw_gps_15min.jsonl"), gps_rows)
    print(f"Section 3 complete: generated {ACTIVE_CONFIG.name} sensing data.")
    print(f"Generated: {path('daily_behavior_raw.jsonl')}")
    print(f"Generated: {path('raw_gps_15min.jsonl')}")


def stage_autolife() -> None:
    raw_days = read_jsonl(path("daily_behavior_raw.jsonl"))
    summaries = []
    for raw in raw_days:
        notes = []
        if raw["sleep_onset_hour"] >= 24.5:
            notes.append("went to sleep later than their earlier-week pattern")
        if raw.get("late_night_screen_min") and raw["late_night_screen_min"] > 80:
            notes.append("had frequent phone activity after midnight")
        if raw["mobility_entropy"] < 1.0:
            notes.append("spent most of the day around a small set of places")
        if raw["location_revisit_ratio"] > 0.82:
            notes.append("returned repeatedly to the same top locations")
        if not notes:
            notes.append("followed a fairly typical campus routine")
        summary = "The user " + ", and ".join(notes) + "."
        summaries.append({
            "participant_id": raw["participant_id"],
            "date": raw["date"],
            "summary": summary,
        })
    write_jsonl(path("autolife_summaries.jsonl"), summaries)
    print("Section 4 complete: generated AutoLife-style daily summaries.")
    print(f"Generated: {path('autolife_summaries.jsonl')}")


def _infer_states_for_participant(raw_days: list[dict]) -> list[dict]:
    warmup_days = max(3, min(7, ACTIVE_CONFIG.baseline_days))
    baseline = PersonalBaseline(warmup_days=warmup_days)
    states = []
    for raw in sorted(raw_days, key=lambda row: row["date"]):
        rec = markers_from_raw(raw)
        baseline.add(rec)
        as_of = rec.day
        devs = []
        patterns = []
        if baseline.is_warm():
            recent_days = 2 if ACTIVE_CONFIG.n_days <= 7 else 3
            baseline_days = max(4, ACTIVE_CONFIG.baseline_days)
            devs = detect_deviations(
                baseline,
                as_of=as_of,
                recent_days=recent_days,
                baseline_days=baseline_days,
                min_magnitude="mild",
            )
            patterns = find_coherent_patterns(devs)
        state = build_state_description(baseline, devs, patterns, as_of)
        states.append({
            "participant_id": raw["participant_id"],
            "date": raw["date"],
            "day_index": raw["day_index"],
            "is_scheduler_period": raw["day_index"] > ACTIVE_CONFIG.baseline_days,
            "markers": {
                key: raw.get(key) for key in [
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
            },
            "coverage": raw["_coverage"],
            "deviations": [d.to_dict() for d in devs],
            "patterns": [p.to_dict() for p in patterns],
            "state": state,
        })
    return states


def stage_pipeline() -> None:
    raw_days = read_jsonl(path("daily_behavior_raw.jsonl"))
    states = []
    marker_rows = []
    by_pid: dict[str, list[dict]] = {}
    for raw in raw_days:
        by_pid.setdefault(raw["participant_id"], []).append(raw)
        marker_rows.append({
            key: raw.get(key)
            for key in [
                "participant_id",
                "date",
                "day_index",
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
        })
    for participant_days in by_pid.values():
        states.extend(_infer_states_for_participant(participant_days))

    write_jsonl(path("inferred_behavior_states.jsonl"), states)
    with path("daily_behavior_markers.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(marker_rows[0].keys()))
        writer.writeheader()
        writer.writerows(marker_rows)
    print("Section 5 complete: ran Layer 1/2/3 behavior pipeline.")
    print(f"Generated: {path('daily_behavior_markers.csv')}")
    print(f"Generated: {path('inferred_behavior_states.jsonl')}")


def _load_calendars_by_key() -> dict[tuple[str, str], dict]:
    calendars = read_jsonl(path("daily_calendars.jsonl"))
    return {
        (row["participant_id"], row["date"]): row
        for row in calendars
    }


def _decision_states() -> list[dict]:
    states = read_jsonl(path("inferred_behavior_states.jsonl"))
    selected = []
    by_pid: dict[str, int] = {}
    for state in states:
        pattern_count = len(state["patterns"])
        if not state["is_scheduler_period"] or pattern_count == 0:
            continue
        pid = state["participant_id"]
        if by_pid.get(pid, 0) >= ACTIVE_CONFIG.max_decision_days_per_participant:
            continue
        selected.append(state)
        by_pid[pid] = by_pid.get(pid, 0) + 1
    return selected


def stage_scheduler_inputs() -> None:
    calendars = _load_calendars_by_key()
    decision_states = _decision_states()
    calendar_only = []
    behavior_aware = []
    prefs = {
        "protect_fixed_events": True,
        "prefer_low_burden_changes": True,
        "protect_sleep_when_possible": True,
        "avoid_clinical_language": True,
    }
    for idx, state in enumerate(decision_states, start=1):
        cal = calendars[(state["participant_id"], state["date"])]
        base = {
            "case_id": f"S{idx:03d}",
            "participant_id": state["participant_id"],
            "date": state["date"],
            "calendar": cal["events"],
            "user_preferences": prefs,
        }
        calendar_only.append({
            **base,
            "condition": "calendar_only",
        })
        behavior_aware.append({
            **base,
            "condition": "behavior_aware",
            "behavioral_state": state["state"]["structured"],
            "behavioral_state_prose": state["state"]["prose"],
        })
    write_jsonl(path("scheduler_inputs_calendar_only.jsonl"), calendar_only)
    write_jsonl(path("scheduler_inputs_behavior_aware.jsonl"), behavior_aware)
    print("Section 6 complete: built scheduler inputs for two conditions.")
    print(f"Generated: {path('scheduler_inputs_calendar_only.jsonl')}")
    print(f"Generated: {path('scheduler_inputs_behavior_aware.jsonl')}")


def _first_flexible_event(calendar: list[dict], preferred_titles: set[str] | None = None) -> dict | None:
    for event in calendar:
        if event["flexibility"] != "flexible":
            continue
        if preferred_titles and event["title"] not in preferred_titles:
            continue
        return event
    for event in calendar:
        if event["flexibility"] == "flexible":
            return event
    return None


def _variant(input_row: dict, n: int) -> int:
    key = f"{input_row['case_id']}:{input_row['participant_id']}:{input_row['date']}"
    return sum(ord(ch) for ch in key) % n


def _recommendation_from_options(input_row: dict, options: list[dict]) -> dict:
    return options[_variant(input_row, len(options))]


def _schedule_recommendation(input_row: dict) -> dict:
    calendar = input_row["calendar"]
    if input_row["condition"] == "calendar_only":
        event = _first_flexible_event(calendar)
        if not event:
            return {
                "recommendation": "Keep the schedule unchanged.",
                "calendar_action": "keep",
                "target_event": None,
                "reason": "The calendar contains mostly fixed obligations, so a low-risk change is not available.",
                "burden": "low",
                "confidence": "medium",
                "safety_note": "No fixed obligations were changed.",
            }
        return _recommendation_from_options(input_row, [
            {
                "recommendation": f"Keep {event['title']} flexible and add a 15-minute buffer before it.",
                "calendar_action": "add_buffer",
                "target_event": event["title"],
                "reason": "The calendar has several obligations; a small buffer is a low-burden adjustment.",
                "burden": "low",
                "confidence": "medium",
                "safety_note": "No behavioral or clinical inference was made.",
            },
            {
                "recommendation": f"Preserve {event['title']} but leave its exact start time adjustable.",
                "calendar_action": "keep",
                "target_event": event["title"],
                "reason": "Without behavioral context, the safest recommendation is to maintain flexibility around a non-fixed event.",
                "burden": "low",
                "confidence": "medium",
                "safety_note": "No fixed obligations were changed.",
            },
            {
                "recommendation": f"Add a short transition buffer after {event['title']} if the day feels crowded.",
                "calendar_action": "add_buffer",
                "target_event": event["title"],
                "reason": "The calendar includes multiple commitments, so a small transition buffer may reduce schedule friction.",
                "burden": "low",
                "confidence": "medium",
                "safety_note": "This suggestion is based only on calendar structure.",
            },
        ])

    patterns = {
        pattern["name"]
        for pattern in input_row["behavioral_state"].get("coherent_patterns", [])
    }
    if "phone-mediated-sleep-delay" in patterns:
        event = _first_flexible_event(calendar, {"optional work session", "deadline work block"})
        return _recommendation_from_options(input_row, [
            {
                "recommendation": f"Move {event['title']} out of the late evening if possible.",
                "calendar_action": "reduce_evening_load",
                "target_event": event["title"],
                "reason": "Recent later sleep onset and elevated late-night phone use suggest protecting the evening wind-down period.",
                "burden": "medium",
                "confidence": "medium",
                "safety_note": "The suggestion targets a flexible event and avoids changing fixed obligations.",
            },
            {
                "recommendation": f"Shorten {event['title']} and set a firm evening stop time.",
                "calendar_action": "protect_sleep",
                "target_event": event["title"],
                "reason": "The inferred pattern points to late-night activity pushing sleep later, so a clear stop time is a lower-disruption option than canceling the event.",
                "burden": "medium",
                "confidence": "medium",
                "safety_note": "The recommendation keeps the event flexible and avoids clinical claims.",
            },
            {
                "recommendation": f"Move the planning portion of {event['title']} to the afternoon and leave the evening lighter.",
                "calendar_action": "move_to_daytime",
                "target_event": event["title"],
                "reason": "Late sleep onset and late-night screen use make evening workload a plausible scheduling pressure point.",
                "burden": "medium",
                "confidence": "medium",
                "safety_note": "No fixed obligations are changed.",
            },
        ])
    if "behavioral-withdrawal" in patterns:
        event = _first_flexible_event(calendar, {"study block", "deadline work block"})
        return _recommendation_from_options(input_row, [
            {
                "recommendation": f"Add a short outdoor or campus walk before {event['title']}.",
                "calendar_action": "suggest_break",
                "target_event": event["title"],
                "reason": "Recent mobility became more restricted and concentrated around the same places, so a low-burden restorative movement block may fit.",
                "burden": "low",
                "confidence": "medium",
                "safety_note": "This is a gentle scheduling suggestion, not a diagnosis.",
            },
            {
                "recommendation": f"Move part of {event['title']} to a public campus location such as the library.",
                "calendar_action": "reschedule",
                "target_event": event["title"],
                "reason": "Location routine narrowed recently, so a flexible event can be used to reintroduce a low-effort change of place.",
                "burden": "low",
                "confidence": "medium",
                "safety_note": "The suggestion is optional and avoids interpreting mood.",
            },
            {
                "recommendation": f"Pair {event['title']} with a brief meal or coffee stop away from the usual location.",
                "calendar_action": "suggest_break",
                "target_event": event["title"],
                "reason": "The behavioral state suggests reduced location variety; a small adjacent routine change is lower burden than moving fixed obligations.",
                "burden": "low",
                "confidence": "medium",
                "safety_note": "This is framed as a scheduling nudge, not a diagnosis.",
            },
        ])
    if "circadian-instability" in patterns:
        event = _first_flexible_event(calendar, {"optional work session", "study block"})
        return _recommendation_from_options(input_row, [
            {
                "recommendation": f"Keep {event['title']} at a consistent daytime slot and avoid moving it later.",
                "calendar_action": "protect_sleep",
                "target_event": event["title"],
                "reason": "Recent sleep timing became less regular, so preserving predictable daytime anchors is a low-burden scheduling response.",
                "burden": "low",
                "confidence": "medium",
                "safety_note": "The suggestion preserves fixed obligations and avoids clinical claims.",
            },
            {
                "recommendation": f"Anchor {event['title']} around the same time as earlier in the week.",
                "calendar_action": "protect_sleep",
                "target_event": event["title"],
                "reason": "The inferred pattern is about timing instability, so the recommendation prioritizes regular schedule anchors.",
                "burden": "low",
                "confidence": "medium",
                "safety_note": "No fixed obligations are changed.",
            },
            {
                "recommendation": f"Avoid adding late-day tasks after {event['title']} and preserve a predictable evening boundary.",
                "calendar_action": "reduce_evening_load",
                "target_event": event["title"],
                "reason": "Less regular sleep timing suggests that stable evening boundaries may be more appropriate than adding new flexible work.",
                "burden": "low",
                "confidence": "medium",
                "safety_note": "The suggestion stays within calendar structure and avoids wellbeing diagnosis.",
            },
        ])
    if "fragmented-attention-with-sleep-loss" in patterns:
        event = _first_flexible_event(calendar, {"study block", "optional work session"})
        return _recommendation_from_options(input_row, [
            {
                "recommendation": f"Move the most demanding part of {event['title']} earlier in the day.",
                "calendar_action": "reschedule",
                "target_event": event["title"],
                "reason": "Shorter sleep and fragmented attention suggest protecting cognitively demanding work from late-day fatigue.",
                "burden": "medium",
                "confidence": "medium",
                "safety_note": "No fixed events were changed.",
            },
            {
                "recommendation": f"Split {event['title']} into two shorter focus blocks with a break between them.",
                "calendar_action": "add_buffer",
                "target_event": event["title"],
                "reason": "Fragmented attention plus shorter sleep suggests smaller work blocks may be more realistic than a long uninterrupted session.",
                "burden": "medium",
                "confidence": "medium",
                "safety_note": "This changes only a flexible work block.",
            },
            {
                "recommendation": f"Keep {event['title']} but move lower-priority tasks out of that block.",
                "calendar_action": "reschedule",
                "target_event": event["title"],
                "reason": "Recent sleep loss and attention fragmentation suggest preserving the block for the highest-priority work only.",
                "burden": "low",
                "confidence": "medium",
                "safety_note": "The suggestion avoids canceling commitments.",
            },
        ])
    event = _first_flexible_event(calendar)
    return {
        "recommendation": f"Keep {event['title']} flexible and add a small recovery buffer.",
        "calendar_action": "add_buffer",
        "target_event": event["title"],
        "reason": "A coherent behavioral state was detected, but the safest first step is a low-burden calendar buffer.",
        "burden": "low",
        "confidence": "low",
        "safety_note": "The suggestion is reversible and low impact.",
    }


def stage_scheduler_outputs() -> None:
    inputs = (
        read_jsonl(path("scheduler_inputs_calendar_only.jsonl"))
        + read_jsonl(path("scheduler_inputs_behavior_aware.jsonl"))
    )
    outputs = []
    rng = random.Random(SEED)
    by_case: dict[str, list[dict]] = {}
    for row in inputs:
        output = {
            "case_id": row["case_id"],
            "condition": row["condition"],
            "participant_id": row["participant_id"],
            "date": row["date"],
            **_schedule_recommendation(row),
        }
        by_case.setdefault(row["case_id"], []).append(output)

    for case_id, case_outputs in sorted(by_case.items()):
        labels = ["A", "B"]
        rng.shuffle(labels)
        for label, output in zip(labels, case_outputs):
            output["blind_label"] = label
            outputs.append(output)
    outputs.sort(key=lambda row: (row["case_id"], row["blind_label"]))
    write_jsonl(path("scheduler_outputs_blinded.jsonl"), outputs)
    print("Section 7 complete: generated blinded scheduler outputs.")
    print(f"Generated: {path('scheduler_outputs_blinded.jsonl')}")


def _adherence_probability(profile: dict, output: dict) -> float:
    base = {"high": 0.75, "medium": 0.5, "low": 0.25}.get(
        profile["adherence_tendency"], 0.5
    )
    burden_adjust = {"low": 0.15, "medium": -0.05, "high": -0.25}.get(
        output["burden"], 0.0
    )
    action_adjust = {
        "suggest_break": 0.1,
        "add_buffer": 0.1,
        "reduce_evening_load": -0.05,
        "reschedule": -0.1,
        "keep": 0.2,
    }.get(output["calendar_action"], 0.0)
    return max(0.02, min(0.95, base + burden_adjust + action_adjust))


def stage_adherence() -> None:
    profiles = {
        profile["participant_id"]: profile
        for profile in read_json(path("participants.json"))
    }
    outputs = read_jsonl(path("scheduler_outputs_blinded.jsonl"))
    rng = random.Random(SEED)
    rows = []
    for output in outputs:
        profile = profiles[output["participant_id"]]
        p = _adherence_probability(profile, output)
        followed = rng.random() < p
        rows.append({
            "case_id": output["case_id"],
            "blind_label": output["blind_label"],
            "condition": output["condition"],
            "participant_id": output["participant_id"],
            "date": output["date"],
            "calendar_action": output["calendar_action"],
            "burden": output["burden"],
            "adherence_probability": round(p, 3),
            "followed": followed,
        })
    with path("adherence_log.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print("Section 8 complete: simulated adherence for scheduler outputs.")
    print(f"Generated: {path('adherence_log.csv')}")


def stage_export_rater_sheet() -> None:
    outputs = read_jsonl(path("scheduler_outputs_blinded.jsonl"))
    states = {
        (state["participant_id"], state["date"]): state
        for state in read_jsonl(path("inferred_behavior_states.jsonl"))
    }
    calendars = _load_calendars_by_key()
    rows = []
    for output in outputs:
        key = (output["participant_id"], output["date"])
        patterns = ", ".join(
            pattern["name"] for pattern in states[key]["patterns"]
        )
        rows.append({
            "case_id": output["case_id"],
            "option": output["blind_label"],
            "participant_id": output["participant_id"],
            "date": output["date"],
            "calendar_summary": "; ".join(
                f"{event['start']} {event['title']} ({event['flexibility']})"
                for event in calendars[key]["events"]
            ),
            "inferred_patterns_for_reviewer_context": patterns,
            "recommendation": output["recommendation"],
            "reason": output["reason"],
            "burden": output["burden"],
            "safety_note": output["safety_note"],
            "relevance_1_5": "",
            "behavioral_alignment_1_5": "",
            "feasibility_1_5": "",
            "safety_1_5": "",
            "specificity_1_5": "",
            "overall_preferred_A_or_B": "",
        })
    with path("rater_sheet.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Section 9 complete: exported {ACTIVE_CONFIG.name} rater sheet.")
    print(f"Generated: {path('rater_sheet.csv')}")


def stage_summary() -> None:
    states = read_jsonl(path("inferred_behavior_states.jsonl"))
    outputs = read_jsonl(path("scheduler_outputs_blinded.jsonl"))
    pattern_rows = [
        state for state in states
        if state["is_scheduler_period"] and state["patterns"]
    ]
    pattern_counts: dict[str, int] = {}
    for state in pattern_rows:
        for pattern in state["patterns"]:
            pattern_counts[pattern["name"]] = pattern_counts.get(pattern["name"], 0) + 1

    behavior_aware = [row for row in outputs if row["condition"] == "behavior_aware"]
    calendar_only = [row for row in outputs if row["condition"] == "calendar_only"]
    summary = f"""# {ACTIVE_CONFIG.name.title()} Simulation Run

## Configuration

- Participants: {ACTIVE_CONFIG.participants}
- Days per participant: {ACTIVE_CONFIG.n_days}
- Passive baseline days: {ACTIVE_CONFIG.baseline_days}
- Scheduler period days: {ACTIVE_CONFIG.n_days - ACTIVE_CONFIG.baseline_days}
- Max evaluated decision days per participant: {ACTIVE_CONFIG.max_decision_days_per_participant}

## Pipeline Check

- Scheduler-period days with coherent patterns: {len(pattern_rows)}
- Pattern counts: {pattern_counts}

## Scheduler Output Check

- Calendar-only outputs: {len(calendar_only)}
- Behavior-aware outputs: {len(behavior_aware)}
- Blinded rater rows: {len(outputs)}

## Initial Read

This run is considered promising if:

1. At least one coherent behavioral pattern emerges from simulated behavior.
2. The behavior-aware scheduler produces a different, pattern-grounded
   recommendation than the calendar-only scheduler.
3. Outputs avoid changing fixed obligations and include safety notes.
4. The rater sheet is understandable enough for a teammate to score.
"""
    path("simulation_summary.md").write_text(summary, encoding="utf-8")
    print(f"Section 10 complete: wrote {ACTIVE_CONFIG.name} simulation summary.")
    print(f"Generated: {path('simulation_summary.md')}")
    print(summary)


STAGES = {
    "profiles": stage_profiles,
    "calendars": stage_calendars,
    "sensors": stage_sensors,
    "autolife": stage_autolife,
    "pipeline": stage_pipeline,
    "scheduler-inputs": stage_scheduler_inputs,
    "scheduler-outputs": stage_scheduler_outputs,
    "adherence": stage_adherence,
    "export-rater-sheet": stage_export_rater_sheet,
    "summary": stage_summary,
}


ORDERED_STAGES = list(STAGES.keys())


def run_stage(stage: str) -> None:
    if stage == "all":
        for name in ORDERED_STAGES:
            STAGES[name]()
        return
    STAGES[stage]()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--preset",
        choices=sorted(CONFIGS),
        default="sample",
        help="Simulation size/configuration preset.",
    )
    parser.add_argument(
        "--stage",
        choices=["all"] + ORDERED_STAGES,
        default="all",
        help="Simulation stage to run.",
    )
    args = parser.parse_args()
    set_active_config(args.preset)
    ensure_output_dir()
    run_stage(args.stage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
