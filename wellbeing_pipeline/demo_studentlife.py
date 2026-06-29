"""
Run Layers 1→4 on 5 real StudentLife participants and print Layer 3 prose +
Layer 4 LLM output for each participant's last warm day.

Usage:
    python3.10 demo_studentlife.py
    python3.10 demo_studentlife.py --pids u00 u03 u10   # specific pids
    python3.10 demo_studentlife.py --no-llm              # skip Layer 4 API call
"""
from __future__ import annotations
import argparse
import json
from datetime import timedelta

from layer1 import PersonalBaseline, markers_from_raw
from layer2 import detect_deviations, find_coherent_patterns
from layer3 import build_state_description, render_llm_input
from studentlife_adapter import (
    build_daily_records, list_participants, load_pid_sensors,
)


DEFAULT_PIDS = ["u00", "u03", "u10", "u20", "u30"]


def hr(title: str) -> None:
    print("\n" + "=" * 78)
    print(f"  {title}")
    print("=" * 78)


def run_participant(pid: str, with_llm: bool, model: str | None) -> None:
    hr(f"Participant {pid}")

    sensors = load_pid_sensors(pid)
    raw_days = build_daily_records(pid, sensors=sensors)
    if not raw_days:
        print("  No sensor data found.")
        return

    baseline = PersonalBaseline(warmup_days=10)
    last_warm_state = None
    last_warm_devs = None
    last_warm_patterns = None
    last_warm_day = None

    for raw in raw_days:
        baseline.add(markers_from_raw(raw))
        if not baseline.is_warm():
            continue
        as_of = raw["date"]
        devs = detect_deviations(baseline, as_of=as_of,
                                 recent_days=4, baseline_days=28,
                                 min_magnitude="mild")
        patterns = find_coherent_patterns(devs)
        state = build_state_description(baseline, devs, patterns, as_of)
        last_warm_state = state
        last_warm_devs = devs
        last_warm_patterns = patterns
        last_warm_day = as_of

    if last_warm_state is None:
        print(f"  Baseline never warmed ({len(raw_days)} days of data).")
        return

    print(f"\nData range: {raw_days[0]['date']} → {raw_days[-1]['date']} "
          f"({len(raw_days)} days)")
    print(f"Evaluating as of: {last_warm_day} "
          f"(confidence: {last_warm_state['structured']['baseline_state']['overall_confidence']})")

    print(f"\nDeviations detected ({len(last_warm_devs)}):")
    if not last_warm_devs:
        print("  (none above mild)")
    for d in last_warm_devs:
        print(f"  [{d.domain}/{d.marker}] {d.magnitude} / {d.trajectory}")
        print(f"    → {d.finding}")

    print(f"\nCoherent patterns (rules-based, {len(last_warm_patterns)}):")
    if not last_warm_patterns:
        print("  (none)")
    for p in last_warm_patterns:
        print(f"  • {p.name}: {', '.join(p.implicated)}")

    print("\n--- Layer 3 prose ---")
    print(last_warm_state["prose"])

    if with_llm:
        print("\n--- Layer 4: LLM pattern detection + scheduling ---")
        from layer4_llm import call_scheduler
        payload = render_llm_input(last_warm_state, calendar=[], user_prefs={})
        result = call_scheduler(
            state=last_warm_state,
            calendar=[],
            user_prefs={},
            model=model,
        )
        meta = result.pop("_meta", {})
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"\n[tokens: in={meta.get('input_tokens')} "
              f"out={meta.get('output_tokens')} "
              f"cache_read={meta.get('cache_read_input_tokens')}]")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pids", nargs="+", default=DEFAULT_PIDS)
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    available = set(list_participants())
    pids = [p for p in args.pids if p in available]
    missing = [p for p in args.pids if p not in available]
    if missing:
        print(f"Warning: pids not found in dataset: {missing}")
    if not pids:
        print("No valid pids to run.")
        return

    for pid in pids:
        run_participant(pid, with_llm=not args.no_llm, model=args.model)


if __name__ == "__main__":
    main()
