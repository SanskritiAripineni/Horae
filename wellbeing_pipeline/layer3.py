"""
Layer 3 — Rich behavioral-state description for the LLM scheduler.

Output is dual:
- `structured`: JSON-serializable dict the LLM reasons over reliably.
- `prose`: human-readable narrative for the Daily Journal + user-facing UI.

No scalar salience. Ranking / "what matters" is the LLM's job. Layer 3 just
arranges the findings so the LLM has everything it needs:
- what changed (natural-language finding per deviation)
- how much (qualitative magnitude)
- for how long (qualitative trajectory)
- how confident (coverage flag)
- which deviations are moving together (coherent patterns)
- what's NOT in the picture (coverage gaps stated explicitly)
"""
from __future__ import annotations
from datetime import date
from typing import Optional

from layer1 import PersonalBaseline, MARKER_SPECS
from layer2 import Deviation, CoherentPattern


def _overall_confidence(deviations: list[Deviation],
                        baseline: PersonalBaseline) -> str:
    if not baseline.is_warm():
        return "low-cold-start"
    covs = [d.coverage for d in deviations] or ["high"]
    score = sum({"high": 2, "medium": 1, "low": 0, "none": -1}.get(c, 0) for c in covs)
    if score >= 2 * len(covs):  return "high"
    if score >= len(covs):      return "medium"
    return "low"


def _coverage_notes(baseline: PersonalBaseline, as_of: date) -> list[str]:
    """Explicit callouts when specific markers have sparse data. Prevents the LLM
    from drawing confident conclusions on domains we can barely see."""
    notes = []
    for m in MARKER_SPECS:
        q = baseline.coverage_quality(m, days_back=7,
                                      end_exclusive=as_of.fromordinal(as_of.toordinal() + 1))
        if q in ("low", "none"):
            domain = MARKER_SPECS[m]["domain"]
            notes.append(
                f"{domain}/{m}: coverage {q} — LLM should discount claims in this area"
            )
    return notes


def build_state_description(baseline: PersonalBaseline,
                            deviations: list[Deviation],
                            patterns: list[CoherentPattern],
                            as_of: date) -> dict:
    warm = baseline.is_warm()
    confidence = _overall_confidence(deviations, baseline)

    structured = {
        "as_of": as_of.isoformat(),
        "baseline_state": {
            "warm": warm,
            "days_of_history": len(baseline.history),
            "overall_confidence": confidence,
        },
        "deviations": [d.to_dict() for d in deviations],
        "coherent_patterns": [p.to_dict() for p in patterns],
        "coverage_notes": _coverage_notes(baseline, as_of),
        "schema_note": (
            "All findings are descriptive, grounded in the user's own history. "
            "No mood/emotion labels are inferred. The downstream LLM should "
            "(a) reason about which findings deserve calendar action, "
            "(b) consider patterns over single findings, "
            "(c) respect coverage_notes and overall_confidence, "
            "(d) avoid clinical claims."
        ),
    }

    # -------------------- Prose rendering (the Daily Journal) --------------------
    if not warm:
        prose = (
            f"As of {as_of.isoformat()}, we have {len(baseline.history)} days of "
            f"history — still in the baseline-learning window. Observations this "
            f"week are not yet compared against a stable personal baseline."
        )
        return {"structured": structured, "prose": prose}

    if not deviations:
        prose = (
            f"As of {as_of.isoformat()}, recent patterns are within your typical "
            f"range across sleep, screen use, mobility, and communication. Nothing "
            f"stands out as worth flagging for calendar adjustment."
        )
        return {"structured": structured, "prose": prose}

    # Prose structure: opening → deviations grouped by domain → patterns → coverage
    lines = [f"As of {as_of.isoformat()}, recent behavioral observations "
             f"(overall confidence: {confidence}):"]
    lines.append("")

    by_domain: dict[str, list[Deviation]] = {}
    for d in deviations:
        by_domain.setdefault(d.domain, []).append(d)

    domain_header = {
        "sleep":    "Sleep:",
        "screen":   "Screen & attention:",
        "mobility": "Mobility & location routine:",
        "social":   "Social rhythm & communication:",
    }
    for domain in ["sleep", "screen", "mobility", "social"]:
        if domain in by_domain:
            lines.append(domain_header[domain])
            for d in by_domain[domain]:
                lines.append(f"  • {d.finding} [{d.magnitude}, coverage: {d.coverage}]")
            lines.append("")

    if patterns:
        lines.append("Coherent patterns worth noting:")
        for p in patterns:
            lines.append(f"  • {p.interpretation}")
            lines.append(f"    (signals: {', '.join(p.implicated)})")
        lines.append("")

    notes = structured["coverage_notes"]
    if notes:
        lines.append("Coverage caveats — treat claims in these areas cautiously:")
        for n in notes:
            lines.append(f"  • {n}")
        lines.append("")

    lines.append(
        "The LLM scheduler should decide which of the above are worth acting on "
        "through calendar adjustments, based on the user's preferences, upcoming "
        "commitments, and the coherence of the pattern — not on single-day magnitudes."
    )

    return {"structured": structured, "prose": "\n".join(lines)}


# -------------------- Optional: LLM reasoning prompt scaffold --------------------

SCHEDULER_SYSTEM_PROMPT = """You are a calendar-scheduling assistant that uses \
passive behavioral observations to suggest schedule changes that support the \
user's wellbeing.

Inputs you will receive:
1. A structured behavioral-state description (grounded observations from the \
user's own recent history; NOT emotion predictions).
2. The user's calendar for the next 7 days.
3. The user's stated preferences and constraints.

Your job:
- Identify which observations, if any, suggest actionable calendar changes.
- Prefer interventions supported by multiple observations (coherent patterns) \
over single-signal reactions.
- Respect coverage_notes and overall_confidence; under low confidence, propose \
gentler nudges or ask rather than recommend.
- Never infer mood, diagnose, or use clinical language.
- Every suggestion must cite which observation(s) motivated it.

Output format:
{
  "salience_reasoning": "<natural-language: which observations matter and why>",
  "suggestions": [
    {"change": "...", "rationale": "...", "grounded_in": [marker_or_pattern]}
  ],
  "questions_for_user": ["..."]   # only if uncertainty is high
}
"""


def render_llm_input(state: dict, calendar: Optional[list] = None,
                     user_prefs: Optional[dict] = None) -> dict:
    """Package the Layer 3 output plus calendar + prefs as a single LLM payload."""
    return {
        "system": SCHEDULER_SYSTEM_PROMPT,
        "behavioral_state": state["structured"],
        "behavioral_state_prose": state["prose"],
        "calendar_next_7d": calendar or [],
        "user_preferences": user_prefs or {},
    }
