"""
Run the full Layer 1 → Layer 2 → Layer 3 pipeline on synthetic data.

Shows outputs at three timestamps:
  Day 14 — still in baseline-learning / warm-up phase
  Day 22 — drift just beginning
  Day 29 — drift clearly established

This mimics what a deployed app would produce each evening for the user's
scheduler LLM to consume.
"""
import argparse
import json
from datetime import date, timedelta

from layer1 import PersonalBaseline, markers_from_raw
from layer2 import detect_deviations, find_coherent_patterns
from layer3 import build_state_description, render_llm_input
from synthetic import generate_user_days


def run_pipeline_at(all_days, as_of_index):
    baseline = PersonalBaseline(warmup_days=10)
    for raw in all_days[: as_of_index + 1]:
        baseline.add(markers_from_raw(raw))
    as_of = all_days[as_of_index]["date"]
    devs = detect_deviations(baseline, as_of=as_of, recent_days=4,
                             baseline_days=21, min_magnitude="mild")
    patterns = find_coherent_patterns(devs)
    state = build_state_description(baseline, devs, patterns, as_of)
    return baseline, devs, patterns, state


def hr(title):
    print("\n" + "=" * 78)
    print(f"  {title}")
    print("=" * 78)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-llm", action="store_true",
                        help="Call Layer 4 (Anthropic API) on Day 29 output.")
    parser.add_argument("--model", default=None,
                        help="Override model id (default: config.DEFAULT_MODEL).")
    args = parser.parse_args()

    all_days = generate_user_days(n_days=30, seed=42)

    for label, idx in [("Day 14 — warm-up window", 13),
                       ("Day 22 — early drift", 21),
                       ("Day 29 — drift established", 28)]:
        hr(label)
        baseline, devs, patterns, state = run_pipeline_at(all_days, idx)
        print(f"History: {len(baseline.history)} days | "
              f"Baseline warm: {baseline.is_warm()} | "
              f"Confidence: {state['structured']['baseline_state']['overall_confidence']}")

        print("\n--- Layer 2 output: deviations (raw) ---")
        if not devs:
            print("  (no deviations above mild)")
        for d in devs:
            print(f"  [{d.domain}/{d.marker}] {d.magnitude} / {d.trajectory} / cov:{d.coverage}")
            print(f"    → {d.finding}")

        print("\n--- Layer 2 output: coherent patterns ---")
        if not patterns:
            print("  (none)")
        for p in patterns:
            print(f"  • {p.name}: {p.interpretation}")
            print(f"    signals: {p.implicated}")

        print("\n--- Layer 3 output: prose (the Daily Journal) ---")
        print(state["prose"])

    # Show a compact example of the structured LLM payload for the last day
    hr("Structured payload for LLM scheduler — Day 29")
    _, _, _, state = run_pipeline_at(all_days, 28)
    payload = render_llm_input(state,
                               calendar=[{"note": "placeholder — plug in real calendar"}],
                               user_prefs={"preferred_wake": "07:00",
                                           "willing_to_shift_evenings": True})
    # Print only the behavioral_state part compactly; system prompt is long.
    print(json.dumps(payload["behavioral_state"], indent=2, default=str))

    if args.with_llm:
        hr("Layer 4 — LLM pattern detection + scheduler reasoning (Day 29)")
        from layer4_llm import call_scheduler
        result = call_scheduler(
            state=state,
            calendar=payload["calendar_next_7d"],
            user_prefs=payload["user_preferences"],
            model=args.model,
        )
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
