"""
Smoke-test longitudinal behavior-aware scheduling simulation.

Default sample:
  - 2 simulated participants
  - 7 days
  - first 3 days passive baseline
  - days 4-7 scheduler period

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
OUTPUT_DIR = SIM_DIR.parent / "simulation_outputs" / "sample"
START_DATE = date(2026, 3, 2)
N_DAYS = 7
BASELINE_DAYS = 3
SEED = 20260615


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
    return [START_DATE + timedelta(days=i) for i in range(N_DAYS)]


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


def stage_profiles() -> None:
    profiles = [
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
    ]
    write_json(path("participants.json"), [asdict(p) for p in profiles])
    print("Section 1 complete: generated 2 simulated participant profiles.")
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
    if profile["participant_id"] == "P001":
        base.append({
            "start": "21:00",
            "end": "22:30",
            "title": "optional work session",
            "flexibility": "flexible",
            "category": "work",
        })
    else:
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
        if day_index >= 4:
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
    print("Section 2 complete: generated 7-day calendars for 2 participants.")
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
        return "dining" if not (pid == "P002" and day_index >= 5) else "home"
    if 14 <= hour < 18:
        if pid == "P002" and day_index >= 5:
            return "home"
        return "library"
    if 18 <= hour < 20:
        if pid == "P001":
            return "dining"
        return "gym" if day_index < 5 else "home"
    if 20 <= hour < 23:
        if pid == "P001":
            return "library" if day_index >= 5 else "social"
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
    after_baseline = day_index > BASELINE_DAYS + 1

    if pid == "P001":
        sleep_onset = 23.35 + rng.uniform(-0.15, 0.15)
        sleep_duration = 7.5 + rng.uniform(-0.2, 0.2)
        late_screen = 30 + rng.uniform(-6, 6)
        total_screen = 260 + rng.uniform(-30, 30)
        app_switch = 1.2 + rng.uniform(-0.2, 0.2)
        mobility_entropy = 1.75 + rng.uniform(-0.1, 0.1)
        revisit = 0.64 + rng.uniform(-0.04, 0.04)
        srm = 0.78 + rng.uniform(-0.05, 0.05)
        if after_baseline:
            sleep_onset = 25.15 + rng.uniform(-0.2, 0.2)
            sleep_duration = 6.25 + rng.uniform(-0.2, 0.2)
            late_screen = 105 + rng.uniform(-10, 10)
            total_screen = 350 + rng.uniform(-25, 25)
            app_switch = 1.8 + rng.uniform(-0.15, 0.2)
    else:
        sleep_onset = 23.0 + rng.uniform(-0.12, 0.12)
        sleep_duration = 7.8 + rng.uniform(-0.2, 0.2)
        late_screen = 25 + rng.uniform(-5, 5)
        total_screen = 230 + rng.uniform(-25, 25)
        app_switch = 1.0 + rng.uniform(-0.15, 0.15)
        mobility_entropy = 1.85 + rng.uniform(-0.08, 0.08)
        revisit = 0.58 + rng.uniform(-0.03, 0.03)
        srm = 0.82 + rng.uniform(-0.04, 0.04)
        if after_baseline:
            mobility_entropy = 0.75 + rng.uniform(-0.08, 0.08)
            revisit = 0.90 + rng.uniform(-0.03, 0.03)
            srm = 0.55 + rng.uniform(-0.05, 0.05)
            total_screen = 300 + rng.uniform(-25, 25)

    missing_screen = rng.random() < 0.05
    return {
        "participant_id": pid,
        "date": day.isoformat(),
        "day_index": day_index,
        "sleep_onset_hour": sleep_onset,
        "sleep_duration_hours": sleep_duration,
        "sleep_regularity_index": 82 - abs(sleep_onset - 23.4) * 5 + rng.uniform(-2, 2),
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
    print("Section 3 complete: generated sample sensing data.")
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
    baseline = PersonalBaseline(warmup_days=3)
    states = []
    for raw in sorted(raw_days, key=lambda row: row["date"]):
        rec = markers_from_raw(raw)
        baseline.add(rec)
        as_of = rec.day
        devs = []
        patterns = []
        if baseline.is_warm():
            devs = detect_deviations(
                baseline,
                as_of=as_of,
                recent_days=2,
                baseline_days=4,
                min_magnitude="mild",
            )
            patterns = find_coherent_patterns(devs)
        state = build_state_description(baseline, devs, patterns, as_of)
        states.append({
            "participant_id": raw["participant_id"],
            "date": raw["date"],
            "day_index": raw["day_index"],
            "is_scheduler_period": raw["day_index"] > BASELINE_DAYS,
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
    for state in states:
        pattern_count = len(state["patterns"])
        if state["day_index"] >= 5 and pattern_count > 0:
            selected.append(state)
    # Keep the smoke test intentionally tiny.
    return selected[:4]


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
        return {
            "recommendation": f"Keep {event['title']} flexible and add a 15-minute buffer before it.",
            "calendar_action": "add_buffer",
            "target_event": event["title"],
            "reason": "The calendar has several obligations; a small buffer is a low-burden adjustment.",
            "burden": "low",
            "confidence": "medium",
            "safety_note": "No behavioral or clinical inference was made.",
        }

    patterns = {
        pattern["name"]
        for pattern in input_row["behavioral_state"].get("coherent_patterns", [])
    }
    if "phone-mediated-sleep-delay" in patterns:
        event = _first_flexible_event(calendar, {"optional work session", "deadline work block"})
        return {
            "recommendation": f"Move {event['title']} out of the late evening if possible.",
            "calendar_action": "reduce_evening_load",
            "target_event": event["title"],
            "reason": "Recent later sleep onset and elevated late-night phone use suggest protecting the evening wind-down period.",
            "burden": "medium",
            "confidence": "medium",
            "safety_note": "The suggestion targets a flexible event and avoids changing fixed obligations.",
        }
    if "behavioral-withdrawal" in patterns:
        event = _first_flexible_event(calendar, {"study block", "deadline work block"})
        return {
            "recommendation": f"Add a short outdoor or campus walk before {event['title']}.",
            "calendar_action": "suggest_break",
            "target_event": event["title"],
            "reason": "Recent mobility became more restricted and concentrated around the same places, so a low-burden restorative movement block may fit.",
            "burden": "low",
            "confidence": "medium",
            "safety_note": "This is a gentle scheduling suggestion, not a diagnosis.",
        }
    if "fragmented-attention-with-sleep-loss" in patterns:
        event = _first_flexible_event(calendar, {"study block", "optional work session"})
        return {
            "recommendation": f"Move the most demanding part of {event['title']} earlier in the day.",
            "calendar_action": "reschedule",
            "target_event": event["title"],
            "reason": "Shorter sleep and fragmented attention suggest protecting cognitively demanding work from late-day fatigue.",
            "burden": "medium",
            "confidence": "medium",
            "safety_note": "No fixed events were changed.",
        }
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
    print("Section 9 complete: exported sample rater sheet.")
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
    summary = f"""# Sample Simulation Smoke Test

## Configuration

- Participants: 2
- Days per participant: 7
- Passive baseline days: {BASELINE_DAYS}
- Scheduler period days: {N_DAYS - BASELINE_DAYS}

## Pipeline Check

- Scheduler-period days with coherent patterns: {len(pattern_rows)}
- Pattern counts: {pattern_counts}

## Scheduler Output Check

- Calendar-only outputs: {len(calendar_only)}
- Behavior-aware outputs: {len(behavior_aware)}
- Blinded rater rows: {len(outputs)}

## Initial Read

This smoke test is considered promising if:

1. At least one coherent behavioral pattern emerges from simulated behavior.
2. The behavior-aware scheduler produces a different, pattern-grounded
   recommendation than the calendar-only scheduler.
3. Outputs avoid changing fixed obligations and include safety notes.
4. The rater sheet is understandable enough for a teammate to score.
"""
    path("simulation_summary.md").write_text(summary, encoding="utf-8")
    print("Section 10 complete: wrote sample simulation summary.")
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
        "--stage",
        choices=["all"] + ORDERED_STAGES,
        default="all",
        help="Simulation stage to run.",
    )
    args = parser.parse_args()
    ensure_output_dir()
    run_stage(args.stage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
