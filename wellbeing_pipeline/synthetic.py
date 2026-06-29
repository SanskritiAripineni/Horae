"""
Synthetic 30-day single-user dataset for immediate viability testing.

User profile: 28yo, office job, apartment.
- Days 1–20: stable baseline routine
- Days 21–30: gradual drift — sleep onset later, late-night screen up,
              mobility slightly narrows, attention fragments

This gives Layer 2 something real to find, and lets us eyeball whether
Layer 3's prose reflects what we'd expect a thoughtful human observer to say.
"""
from __future__ import annotations
from datetime import date, timedelta
import numpy as np

def _rng(seed=42):
    return np.random.default_rng(seed)

def generate_user_days(n_days: int = 30, start: date = date(2026, 3, 18),
                       seed: int = 42) -> list[dict]:
    rng = _rng(seed)
    days = []
    for i in range(n_days):
        d = start + timedelta(days=i)

        # Regime: baseline (0-19) vs drift (20-29)
        in_drift = i >= 20
        drift_t = max(0.0, (i - 19) / 10.0)  # 0 → 1 across drift window

        # Weekday vs weekend (Sat=5, Sun=6)
        weekend = d.weekday() >= 5

        # ----- Sleep -----
        base_onset = 23.4 + (0.4 if weekend else 0.0)
        onset = base_onset + rng.normal(0, 0.35) + (drift_t * 1.5 if in_drift else 0.0)
        duration = 7.9 + rng.normal(0, 0.4) - (drift_t * 0.8 if in_drift else 0.0)
        # SRI: 0-100, high when schedule is consistent
        sri = 82 + rng.normal(0, 3) - (drift_t * 12 if in_drift else 0.0)

        # ----- Screen -----
        late_night = max(0, rng.normal(22, 6) + (drift_t * 55 if in_drift else 0.0))
        total_screen = max(60, rng.normal(240, 25) + (drift_t * 40 if in_drift else 0.0))
        app_switch = 38 / 60.0 + rng.normal(0, 0.08) + (drift_t * 0.25 if in_drift else 0.0)

        # ----- Mobility -----
        mob_entropy = 1.22 + rng.normal(0, 0.08) - (drift_t * 0.18 if in_drift else 0.0)
        if weekend:
            mob_entropy += 0.15
        revisit = np.clip(0.78 + rng.normal(0, 0.04) + (drift_t * 0.08 if in_drift else 0.0), 0, 1)

        # ----- Social rhythm / comm -----
        srm = np.clip(0.74 + rng.normal(0, 0.04) - (drift_t * 0.06 if in_drift else 0.0), 0, 1)
        reciprocity = np.clip(0.52 + rng.normal(0, 0.05), 0, 1)

        # Coverage: occasional gaps in mobility/social (realistic)
        cov = {
            "sleep_onset_hour": 1.0,
            "sleep_duration_hours": 1.0,
            "sleep_regularity_index": 1.0,
            "late_night_screen_min": 1.0,
            "total_screen_min": 1.0,
            "app_switching_rate": 0.95,
            "mobility_entropy": 0.85 if rng.random() > 0.1 else 0.3,
            "location_revisit_ratio": 0.85,
            "social_rhythm_metric": 0.7 if rng.random() > 0.2 else 0.3,
            "comm_reciprocity": 0.9,
        }

        days.append({
            "date": d,
            "sleep_onset_hour": float(onset),
            "sleep_duration_hours": float(max(3.0, duration)),
            "sleep_regularity_index": float(np.clip(sri, 0, 100)),
            "late_night_screen_min": float(late_night),
            "total_screen_min": float(total_screen),
            "app_switching_rate": float(max(0.0, app_switch)),
            "mobility_entropy": float(max(0.0, mob_entropy)),
            "location_revisit_ratio": float(revisit),
            "social_rhythm_metric": float(srm),
            "comm_reciprocity": float(reciprocity),
            "_coverage": cov,
        })
    return days
