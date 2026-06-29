# Latent Longitudinal Simulation

- Seed: `20260627`
- Participants: `20`
- Days per participant: `42`
- Decision days: `29-42`
- Pipeline config: `{'warmup_days': 10, 'recent_days': 4, 'baseline_days': 21, 'min_magnitude': 'mild'}`

Schedulers never receive `hidden_profiles.json` or `hidden_daily_drivers.jsonl`. The behavior-aware arm receives the Layer 1-4 inferred state; the calendar-only arm receives the same calendar and preferences with an empty behavioral state.
