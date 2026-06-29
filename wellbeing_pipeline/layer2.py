"""
Layer 2 — Deviation detection + coherent-pattern grouping.

Output shape: structured list of Deviation objects, each carrying its OWN
natural-language finding. No scalar salience score. Ranking/importance is
deferred to Layer 3 (LLM reasoning).

Design choices:
- Compare recent window (last N days) to personal baseline (prior M days).
- Classify trajectory: acute / sustained / drift / intermittent. Trajectory
  is often what distinguishes "noise" from "worth mentioning" — it's encoded
  as a string, not a number, so the LLM can reason about it.
- Tag magnitude qualitatively: mild / moderate / pronounced.
- Detect coherent patterns: groups of deviations moving together.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from typing import Optional
import numpy as np

from layer1 import PersonalBaseline, DOMAIN_OF, MARKER_SPECS


# -------- Magnitude / trajectory helpers (all categorical outputs) --------

def _magnitude_cat(z: float) -> str:
    az = abs(z)
    if az < 1.0:  return "within-typical"
    if az < 1.8:  return "mild"
    if az < 2.8:  return "moderate"
    return "pronounced"

def _trajectory(z_series: list[float]) -> str:
    """z_series: oldest→newest z-scores over the recent window."""
    n = len(z_series)
    if n == 0:
        return "no-data"
    if n == 1:
        return "acute-1d" if abs(z_series[0]) >= 1.0 else "within-typical"
    elevated = [abs(z) >= 1.0 for z in z_series]
    n_el = sum(elevated)
    if n_el == 0:
        return "within-typical"
    # All-elevated with consistent sign → sustained
    if n_el == n and len({z > 0 for z in z_series}) == 1:
        return f"sustained-{n}d"
    # Monotone same-sign trend → drift
    if n >= 3:
        signs_all_same = len({z > 0 for z in z_series}) == 1
        magnitudes = [abs(z) for z in z_series]
        monotone = all(magnitudes[i] <= magnitudes[i + 1] + 0.2 for i in range(n - 1))
        if signs_all_same and monotone and abs(z_series[-1]) >= 1.0:
            return f"drift-emerging-{n}d"
    # Last day is the elevated one
    if elevated[-1] and n_el == 1:
        return "acute-1d"
    return f"intermittent-{n_el}d-of-{n}"


# -------- Natural-language finding templates --------

def _hm(h: float) -> str:
    h_mod = h % 24
    hh = int(h_mod)
    mm = int(round((h_mod - hh) * 60))
    if mm == 60:
        hh, mm = (hh + 1) % 24, 0
    return f"{hh:02d}:{mm:02d}"

def _direction_word(delta: float, increase_word: str, decrease_word: str) -> str:
    return increase_word if delta > 0 else decrease_word

def _render_finding(marker: str, recent_mean: float, baseline_mean: float,
                    trajectory: str, magnitude: str) -> str:
    delta = recent_mean - baseline_mean
    traj_suffix = {
        "acute-1d":               "(yesterday only)",
        "within-typical":         "",
    }
    # Generic suffix for sustained / drift / intermittent
    if trajectory.startswith("sustained-"):
        days = trajectory.split("-")[1]
        suffix = f"sustained across the last {days}"
    elif trajectory.startswith("drift-emerging-"):
        days = trajectory.split("-")[2]
        suffix = f"drifting over the last {days}"
    elif trajectory.startswith("intermittent-"):
        suffix = f"intermittently ({trajectory.split('-',1)[1].replace('-', ' ')})"
    else:
        suffix = traj_suffix.get(trajectory, "")

    if marker == "sleep_onset_hour":
        verb = _direction_word(delta, "later", "earlier")
        return (f"Sleep onset has been around {_hm(recent_mean)} "
                f"(about {abs(delta):.1f}h {verb} than typical {_hm(baseline_mean)}); {suffix}").strip("; ")
    if marker == "sleep_duration_hours":
        verb = _direction_word(delta, "longer", "shorter")
        return (f"Sleep has averaged {recent_mean:.1f}h "
                f"({abs(delta):.1f}h {verb} than typical {baseline_mean:.1f}h); {suffix}").strip("; ")
    if marker == "sleep_regularity_index":
        verb = _direction_word(delta, "more", "less")
        return (f"Sleep schedule has been {verb} consistent "
                f"(SRI {recent_mean:.0f} vs typical {baseline_mean:.0f}); {suffix}").strip("; ")
    if marker == "late_night_screen_min":
        pct = (delta / max(baseline_mean, 1.0)) * 100
        verb = _direction_word(delta, "up", "down")
        return (f"Late-night screen use {verb} {abs(pct):.0f}% vs personal baseline "
                f"({recent_mean:.0f}min vs typical {baseline_mean:.0f}min); {suffix}").strip("; ")
    if marker == "total_screen_min":
        pct = (delta / max(baseline_mean, 1.0)) * 100
        verb = _direction_word(delta, "elevated", "reduced")
        return (f"Total screen time {verb} ({recent_mean:.0f}min/day vs typical "
                f"{baseline_mean:.0f}min, {'+' if delta>0 else '-'}{abs(pct):.0f}%); {suffix}").strip("; ")
    if marker == "app_switching_rate":
        verb = _direction_word(delta, "more fragmented", "more focused")
        return (f"Attention pattern {verb} than baseline "
                f"({recent_mean:.1f} vs {baseline_mean:.1f} switches/active-min); {suffix}").strip("; ")
    if marker == "mobility_entropy":
        verb = _direction_word(delta, "more varied", "more restricted")
        return (f"Location routine {verb} than baseline "
                f"(entropy {recent_mean:.2f} vs {baseline_mean:.2f}); {suffix}").strip("; ")
    if marker == "location_revisit_ratio":
        verb = _direction_word(delta, "more time", "less time")
        return (f"{verb.capitalize()} at top-3 frequent places "
                f"({recent_mean*100:.0f}% vs typical {baseline_mean*100:.0f}%); {suffix}").strip("; ")
    if marker == "social_rhythm_metric":
        verb = _direction_word(delta, "more", "less")
        return (f"Daily routine timing {verb} regular "
                f"(SRM {recent_mean:.2f} vs typical {baseline_mean:.2f}); {suffix}").strip("; ")
    if marker == "comm_reciprocity":
        verb = _direction_word(delta, "more outgoing-heavy", "more incoming-heavy")
        return (f"Messaging {verb} than baseline "
                f"({recent_mean:.2f} vs {baseline_mean:.2f}); {suffix}").strip("; ")

    verb = _direction_word(delta, "elevated", "reduced")
    return (f"{marker} {verb} vs baseline "
            f"({recent_mean:.2f} vs {baseline_mean:.2f}); {suffix}").strip("; ")


# ------------------------------- Data class ------------------------------- #

@dataclass
class Deviation:
    marker: str
    domain: str
    finding: str                      # natural-language description (the primary payload)
    magnitude: str                    # within-typical / mild / moderate / pronounced
    trajectory: str                   # acute-1d / sustained-Nd / drift-emerging-Nd / intermittent-...
    direction: str                    # "up" / "down"
    coverage: str                     # high / medium / low
    recent_mean: float
    baseline_mean: float
    baseline_std: float
    recent_days: int

    def to_dict(self) -> dict:
        return asdict(self)


# ------------------------------- Detection ------------------------------- #

def detect_deviations(baseline: PersonalBaseline,
                      as_of: date,
                      recent_days: int = 4,
                      baseline_days: int = 28,
                      min_magnitude: str = "mild") -> list[Deviation]:
    """Scan each marker; return deviations above `min_magnitude`."""
    order = {"within-typical": 0, "mild": 1, "moderate": 2, "pronounced": 3}
    min_rank = order[min_magnitude]
    out: list[Deviation] = []

    # Baseline window ends just before the recent window
    recent_end = as_of + timedelta(days=1)
    recent_start = recent_end - timedelta(days=recent_days)

    for marker in MARKER_SPECS:
        base = baseline.stats(marker, days_back=baseline_days,
                              end_exclusive=recent_start)
        if base is None:
            continue

        recent_recs = [r for r in baseline.window(recent_days, recent_end)
                       if r.has(marker)]
        if len(recent_recs) < max(2, recent_days // 2):
            continue

        recent_vals = np.array([r.markers[marker] for r in recent_recs], dtype=float)
        z_series = [(v - base["mean"]) / base["std"] for v in recent_vals]
        recent_mean = float(recent_vals.mean())
        overall_z = (recent_mean - base["mean"]) / base["std"]

        mag = _magnitude_cat(overall_z)
        if order[mag] < min_rank:
            continue

        traj = _trajectory(z_series)
        direction = "up" if overall_z > 0 else "down"
        finding = _render_finding(marker, recent_mean, base["mean"], traj, mag)

        out.append(Deviation(
            marker=marker,
            domain=DOMAIN_OF[marker],
            finding=finding,
            magnitude=mag,
            trajectory=traj,
            direction=direction,
            coverage=baseline.coverage_quality(marker, days_back=recent_days,
                                               end_exclusive=recent_end),
            recent_mean=recent_mean,
            baseline_mean=base["mean"],
            baseline_std=base["std"],
            recent_days=len(recent_recs),
        ))
    return out


# -------------------------- Coherent-pattern grouping -------------------------- #

# Coherence rules are curated, not learned — each rule embodies a documented
# wellbeing pattern and produces a natural-language interpretation for the LLM.
COHERENCE_RULES = [
    {
        "name": "phone-mediated-sleep-delay",
        "required": [
            ("sleep_onset_hour", "up"),
            ("late_night_screen_min", "up"),
        ],
        "interpretation": (
            "Sleep onset is drifting later alongside increased late-night screen use — "
            "a phone-mediated sleep-delay pattern. Evening calendar density and "
            "wind-down timing are plausible leverage points."
        ),
    },
    {
        "name": "behavioral-withdrawal",
        "required": [
            ("mobility_entropy", "down"),
            ("location_revisit_ratio", "up"),
        ],
        "optional": [("social_rhythm_metric", "down")],
        "interpretation": (
            "Location routine has narrowed and time concentrated at frequent places — "
            "a behavioral-withdrawal pattern often associated with lower mood and "
            "reduced third-place engagement."
        ),
    },
    {
        "name": "circadian-instability",
        "required": [
            ("sleep_regularity_index", "down"),
        ],
        "optional": [
            ("sleep_onset_hour", "up"),
            ("social_rhythm_metric", "down"),
        ],
        "interpretation": (
            "Sleep schedule consistency has dropped; circadian rhythm is less stable "
            "than typical. Anchoring morning wake time and fixed daily events can help."
        ),
    },
    {
        "name": "fragmented-attention-with-sleep-loss",
        "required": [
            ("app_switching_rate", "up"),
            ("sleep_duration_hours", "down"),
        ],
        "interpretation": (
            "Attention is more fragmented while sleep is shorter — attention costs "
            "typically rise when sleep debt accumulates. Worth protecting sleep "
            "opportunity over discretionary evening commitments."
        ),
    },
]


@dataclass
class CoherentPattern:
    name: str
    interpretation: str
    implicated: list[str]  # marker names involved

    def to_dict(self) -> dict:
        return asdict(self)


def find_coherent_patterns(deviations: list[Deviation],
                           circadian_min_markers: int = 1) -> list[CoherentPattern]:
    by_marker = {d.marker: d for d in deviations}
    found: list[CoherentPattern] = []
    for rule in COHERENCE_RULES:
        if not all(
            m in by_marker and by_marker[m].direction == dir_
            and by_marker[m].magnitude != "within-typical"
            for (m, dir_) in rule["required"]
        ):
            continue
        implicated = [m for (m, _) in rule["required"]]
        for (m, dir_) in rule.get("optional", []):
            if m in by_marker and by_marker[m].direction == dir_:
                implicated.append(m)
        if rule["name"] == "circadian-instability" and len(implicated) < circadian_min_markers:
            continue
        found.append(CoherentPattern(
            name=rule["name"],
            interpretation=rule["interpretation"],
            implicated=implicated,
        ))
    return found
