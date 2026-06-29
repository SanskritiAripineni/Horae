"""
Measure Layer-4 behavioral-state payload size versus raw daily inputs.

This script is intentionally offline: it reconstructs StudentLife participant-days
from local CSVs, runs Layers 1-3, selects deterministic confident pattern-fired
days, and reports JSON byte sizes for:
  1. the scheduler-facing behavioral_state object,
  2. the RawDayMarkers object produced by the StudentLife adapter,
  3. reachable raw StudentLife sensor rows for the same participant-day.

No LLM/API/device experiment is run.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from layer1 import PersonalBaseline, markers_from_raw  # noqa: E402
from layer2 import detect_deviations, find_coherent_patterns  # noqa: E402
from layer3 import build_state_description  # noqa: E402
from studentlife_adapter import (  # noqa: E402
    APP_USAGE,
    CALL_LOG,
    DATASET_ROOT,
    LOCAL_TZ,
    SENSING,
    SMS_DIR,
    build_daily_records,
    list_participants,
    load_pid_sensors,
)
from tools.wellbeing_sensor import WellbeingSensor  # noqa: E402


CONFIDENT = {"high", "medium"}
JSON_METHOD = {
    "function": "json.dumps",
    "encoding": "utf-8",
    "ensure_ascii": False,
    "sort_keys": True,
    "separators": [",", ":"],
    "date_datetime": "isoformat",
    "numpy_scalars": "converted to Python scalars",
}
_CSV_CACHE: dict[Path, pd.DataFrame] = {}


def jsonable(obj: Any) -> Any:
    if isinstance(obj, (datetime, date, pd.Timestamp)):
        return obj.isoformat()
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        value = float(obj)
        return None if np.isnan(value) else value
    if isinstance(obj, np.ndarray):
        return [jsonable(v) for v in obj.tolist()]
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    if pd.isna(obj) if not isinstance(obj, (str, bytes, bytearray)) else False:
        return None
    return obj


def json_bytes(obj: Any) -> bytes:
    return json.dumps(
        jsonable(obj),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def byte_count(obj: Any) -> int:
    return len(json_bytes(obj))


def gzip_count(obj: Any) -> int:
    return len(gzip.compress(json_bytes(obj), compresslevel=9, mtime=0))


def local_epoch(dt: datetime) -> float:
    return dt.replace(tzinfo=LOCAL_TZ).timestamp()


def day_windows(day: date) -> dict[str, tuple[datetime, datetime]]:
    return {
        "sleep": (
            datetime.combine(day - timedelta(days=1), dt_time(20, 0)),
            datetime.combine(day, dt_time(11, 0)),
        ),
        "late_night_screen": (
            datetime.combine(day - timedelta(days=1), dt_time(23, 0)),
            datetime.combine(day, dt_time(4, 0)),
        ),
        "day": (
            datetime.combine(day, dt_time(4, 0)),
            datetime.combine(day + timedelta(days=1), dt_time(4, 0)),
        ),
        "screen_union": (
            datetime.combine(day - timedelta(days=1), dt_time(20, 0)),
            datetime.combine(day + timedelta(days=1), dt_time(4, 0)),
        ),
    }


def read_csv_rows(path: Path) -> pd.DataFrame:
    if path in _CSV_CACHE:
        return _CSV_CACHE[path]
    if not path.exists():
        _CSV_CACHE[path] = pd.DataFrame()
        return _CSV_CACHE[path]
    try:
        # Some StudentLife CSVs have trailing delimiters. Without index_col=False,
        # pandas can silently treat the timestamp column as the index.
        _CSV_CACHE[path] = pd.read_csv(
            path,
            encoding="utf-8-sig",
            low_memory=False,
            index_col=False,
        )
    except Exception:
        _CSV_CACHE[path] = pd.DataFrame()
    return _CSV_CACHE[path]


def point_rows(path: Path, timestamp_col: str, lo: datetime, hi: datetime,
               multiplier: float = 1.0) -> list[dict]:
    df = read_csv_rows(path)
    if df.empty or timestamp_col not in df.columns:
        return []
    ts = pd.to_numeric(df[timestamp_col], errors="coerce") / multiplier
    lo_s, hi_s = local_epoch(lo), local_epoch(hi)
    seg = df[(ts >= lo_s) & (ts < hi_s)].copy()
    return jsonable(seg.to_dict(orient="records"))


def interval_rows(path: Path, lo: datetime, hi: datetime) -> list[dict]:
    df = read_csv_rows(path)
    if df.empty or "start" not in df.columns or "end" not in df.columns:
        return []
    start_s = pd.to_numeric(df["start"], errors="coerce")
    end_s = pd.to_numeric(df["end"], errors="coerce")
    lo_s, hi_s = local_epoch(lo), local_epoch(hi)
    seg = df[(end_s > lo_s) & (start_s < hi_s)].copy()
    return jsonable(seg.to_dict(orient="records"))


def raw_sensor_records(pid: str, day: date) -> dict:
    """Reachable StudentLife records for the participant-day.

    The marker adapter assigns sleep and late-night screen across midnight, so
    interval-based screen/dark streams use those assignment windows. Point-event
    streams use the adapter's daily 04:00-to-04:00 window.
    """
    w = day_windows(day)
    day_lo, day_hi = w["day"]
    sleep_lo, sleep_hi = w["sleep"]
    screen_lo, screen_hi = w["screen_union"]

    return {
        "participant_id": pid,
        "date": day,
        "windows": w,
        "streams": {
            "phonelock": interval_rows(
                SENSING / "phonelock" / f"phonelock_{pid}.csv", screen_lo, screen_hi
            ),
            "dark": interval_rows(SENSING / "dark" / f"dark_{pid}.csv", sleep_lo, sleep_hi),
            "wifi_location": point_rows(
                SENSING / "wifi_location" / f"wifi_location_{pid}.csv", "time", day_lo, day_hi
            ),
            "running_app": point_rows(
                APP_USAGE / f"running_app_{pid}.csv", "timestamp", day_lo, day_hi
            ),
            "sms": point_rows(SMS_DIR / f"sms_{pid}.csv", "MESSAGES_date", day_lo, day_hi, 1000.0),
            "call_log": point_rows(
                CALL_LOG / f"call_log_{pid}.csv", "CALLS_date", day_lo, day_hi, 1000.0
            ),
            "gps": point_rows(SENSING / "gps" / f"gps_{pid}.csv", "time", day_lo, day_hi),
            "activity": point_rows(
                SENSING / "activity" / f"activity_{pid}.csv", "timestamp", day_lo, day_hi
            ),
        },
    }


def state_field_paths(state: Any, prefix: str = "") -> set[str]:
    paths: set[str] = set()
    if isinstance(state, dict):
        for key, value in state.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            paths.add(path)
            paths.update(state_field_paths(value, path))
    elif isinstance(state, list):
        item_prefix = f"{prefix}[]" if prefix else "[]"
        paths.add(item_prefix)
        for value in state:
            paths.update(state_field_paths(value, item_prefix))
    return paths


def collect_candidates() -> tuple[list[dict], Counter]:
    candidates: list[dict] = []
    confidence_counts: Counter = Counter()

    for pid in list_participants():
        sensors = load_pid_sensors(pid)
        raw_days = build_daily_records(pid, sensors)
        baseline = PersonalBaseline(warmup_days=10)
        for raw_day in raw_days:
            baseline.add(markers_from_raw(raw_day))
            if not baseline.is_warm():
                continue
            as_of = raw_day["date"]
            devs = detect_deviations(
                baseline,
                as_of=as_of,
                recent_days=4,
                baseline_days=21,
                min_magnitude="mild",
            )
            patterns = find_coherent_patterns(devs)
            if not patterns:
                continue
            state = build_state_description(baseline, devs, patterns, as_of)
            confidence = state["structured"]["baseline_state"]["overall_confidence"]
            confidence_counts[confidence] += 1
            if confidence not in CONFIDENT:
                continue
            candidates.append(
                {
                    "participant_id": pid,
                    "date": as_of,
                    "raw_day_markers": raw_day,
                    "state_structured": state["structured"],
                    "state_prose": state["prose"],
                    "n_deviations": len(devs),
                    "n_patterns": len(patterns),
                    "pattern_names": [p.name for p in patterns],
                    "overall_confidence": confidence,
                }
            )

    candidates.sort(key=lambda r: (r["participant_id"], r["date"].isoformat()))
    return candidates, confidence_counts


def summarize(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "median": 0.0}
    return {
        "mean": float(statistics.fmean(values)),
        "median": float(statistics.median(values)),
    }


def time_offline_wellbeing_sensor(sample: dict, repeats: int = 100) -> dict:
    pid = sample["participant_id"]
    target_day = sample["date"]
    raw_days = build_daily_records(pid, load_pid_sensors(pid))
    raw_days = [r for r in raw_days if r["date"] <= target_day]
    sensor = WellbeingSensor(warmup_days=10, recent_days=4, baseline_days=21)

    timings = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        sensor.analyze(raw_days, with_llm=False)
        timings.append((time.perf_counter() - t0) * 1000.0)
    return {
        "method": "WellbeingSensor.analyze(raw_days_up_to_selected_day, with_llm=False)",
        "note": "CPU/offline Layer 1-3 runtime; excludes StudentLife CSV loading, raw sensor aggregation, device runtime, and LLM/API calls.",
        "participant_id": pid,
        "date": target_day.isoformat(),
        "repeats": repeats,
        "mean_ms": float(statistics.fmean(timings)),
        "median_ms": float(statistics.median(timings)),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "participant_id",
        "date",
        "overall_confidence",
        "pattern_names",
        "n_deviations",
        "n_patterns",
        "state_bytes",
        "raw_markers_bytes",
        "raw_sensor_records_bytes",
        "state_gzip_bytes",
        "raw_markers_gzip_bytes",
        "raw_sensor_records_gzip_bytes",
        "raw_markers_to_state_ratio",
        "raw_sensor_records_to_state_ratio",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row[k] for k in fields})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample-size", type=int, default=51)
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "simulation_outputs" / "payload_size",
    )
    ap.add_argument("--timing-repeats", type=int, default=100)
    args = ap.parse_args()

    candidates, confidence_counts = collect_candidates()
    sample = candidates[: args.sample_size]
    if not sample:
        raise SystemExit("No confident pattern-fired participant-days found.")

    rows: list[dict] = []
    all_field_paths: set[str] = set()
    stream_counts: Counter = Counter()
    stream_nonempty_days: Counter = Counter()

    for item in sample:
        raw_sensors = raw_sensor_records(item["participant_id"], item["date"])
        for stream_name, records in raw_sensors["streams"].items():
            stream_counts[stream_name] += len(records)
            if len(records) > 0:
                stream_nonempty_days[stream_name] += 1

        state_b = byte_count(item["state_structured"])
        markers_b = byte_count(item["raw_day_markers"])
        sensors_b = byte_count(raw_sensors)
        state_gz = gzip_count(item["state_structured"])
        markers_gz = gzip_count(item["raw_day_markers"])
        sensors_gz = gzip_count(raw_sensors)

        all_field_paths.update(state_field_paths(item["state_structured"]))
        rows.append(
            {
                "participant_id": item["participant_id"],
                "date": item["date"].isoformat(),
                "overall_confidence": item["overall_confidence"],
                "pattern_names": "|".join(item["pattern_names"]),
                "n_deviations": item["n_deviations"],
                "n_patterns": item["n_patterns"],
                "state_bytes": state_b,
                "raw_markers_bytes": markers_b,
                "raw_sensor_records_bytes": sensors_b,
                "state_gzip_bytes": state_gz,
                "raw_markers_gzip_bytes": markers_gz,
                "raw_sensor_records_gzip_bytes": sensors_gz,
                "raw_markers_to_state_ratio": markers_b / state_b if state_b else None,
                "raw_sensor_records_to_state_ratio": sensors_b / state_b if state_b else None,
            }
        )

    state_values = [r["state_bytes"] for r in rows]
    marker_values = [r["raw_markers_bytes"] for r in rows]
    sensor_values = [r["raw_sensor_records_bytes"] for r in rows]
    state_gz_values = [r["state_gzip_bytes"] for r in rows]
    marker_gz_values = [r["raw_markers_gzip_bytes"] for r in rows]
    sensor_gz_values = [r["raw_sensor_records_gzip_bytes"] for r in rows]
    marker_ratios = [r["raw_markers_to_state_ratio"] for r in rows]
    sensor_ratios = [r["raw_sensor_records_to_state_ratio"] for r in rows]

    timing = time_offline_wellbeing_sensor(sample[0], repeats=args.timing_repeats)

    report = {
        "summary": {
            "sample_size": len(sample),
            "candidate_days_confident_pattern_fired": len(candidates),
            "candidate_selection": (
                "warm participant-days with >=1 Layer-2 coherent pattern and "
                "Layer-3 overall_confidence in {'high','medium'}, sorted by "
                "participant_id then date; first N selected"
            ),
            "all_pattern_fired_confidence_counts": dict(confidence_counts),
            "dataset_root": str(DATASET_ROOT),
            "json_serialization": JSON_METHOD,
            "gzip_serialization": {
                "function": "gzip.compress",
                "compresslevel": 9,
                "mtime": 0,
                "input": "same UTF-8 JSON bytes",
            },
            "pipeline_parameters": {
                "warmup_days": 10,
                "recent_days": 4,
                "baseline_days": 21,
                "min_magnitude": "mild",
            },
            "state_object_measured": (
                "Layer 3 state['structured'], which layer4_llm._build_user_message "
                "places under payload['behavioral_state'] for the scheduler call"
            ),
            "raw_day_markers_measured": (
                "StudentLife adapter raw_day dict from build_daily_records(), "
                "including marker values and _coverage"
            ),
            "raw_sensor_records_measured": {
                "streams": [
                    "phonelock",
                    "dark",
                    "wifi_location",
                    "running_app",
                    "sms",
                    "call_log",
                    "gps",
                    "activity",
                ],
                "windows": {
                    "phonelock": "overlaps [D-1 20:00, D+1 04:00) local",
                    "dark": "overlaps [D-1 20:00, D 11:00) local",
                    "wifi_location/running_app/sms/call_log/gps/activity": (
                        "timestamps in [D 04:00, D+1 04:00) local"
                    ),
                },
            },
        },
        "headline_uncompressed_bytes": {
            "behavioral_state": summarize(state_values),
            "raw_day_markers": summarize(marker_values),
            "raw_sensor_records": summarize(sensor_values),
        },
        "reference_gzipped_bytes": {
            "behavioral_state": summarize(state_gz_values),
            "raw_day_markers": summarize(marker_gz_values),
            "raw_sensor_records": summarize(sensor_gz_values),
        },
        "reduction_ratios": {
            "raw_day_markers_over_behavioral_state": {
                "ratio_of_means": float(statistics.fmean(marker_values) / statistics.fmean(state_values)),
                **summarize(marker_ratios),
            },
            "raw_sensor_records_over_behavioral_state": {
                "ratio_of_means": float(statistics.fmean(sensor_values) / statistics.fmean(state_values)),
                **summarize(sensor_ratios),
            },
            "raw_day_markers_gzip_over_behavioral_state_gzip": {
                "ratio_of_means": float(statistics.fmean(marker_gz_values) / statistics.fmean(state_gz_values)),
            },
            "raw_sensor_records_gzip_over_behavioral_state_gzip": {
                "ratio_of_means": float(statistics.fmean(sensor_gz_values) / statistics.fmean(state_gz_values)),
            },
        },
        "state_summary_fields": sorted(all_field_paths),
        "raw_sensor_stream_record_counts_in_sample": {
            "total_records_by_stream": dict(stream_counts),
            "nonempty_days_by_stream": dict(stream_nonempty_days),
        },
        "offline_cpu_runtime": timing,
        "sampled_days": [
            {
                "participant_id": r["participant_id"],
                "date": r["date"],
                "overall_confidence": r["overall_confidence"],
                "pattern_names": r["pattern_names"].split("|") if r["pattern_names"] else [],
            }
            for r in rows
        ],
        "per_day_size_rows_csv": str(args.output_dir / "payload_size_rows.csv"),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "payload_size_report.json"
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")
    write_csv(args.output_dir / "payload_size_rows.csv", rows)
    print(json.dumps({
        "report": str(report_path),
        "rows_csv": str(args.output_dir / "payload_size_rows.csv"),
        "headline_uncompressed_bytes": report["headline_uncompressed_bytes"],
        "reduction_ratios": report["reduction_ratios"],
        "offline_cpu_runtime": report["offline_cpu_runtime"],
    }, indent=2))


if __name__ == "__main__":
    main()
