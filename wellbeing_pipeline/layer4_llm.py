"""
Layer 4 — LLM-driven pattern detection + scheduler reasoning.

Replaces the hard-coded COHERENCE_RULES in layer2.py. One Anthropic call does both:
  (a) group deviations into coherent patterns with literature-grounded names
  (b) reason about which deserve calendar action and produce suggestions

System prompt is stable → uses prompt caching (ephemeral).
"""
from __future__ import annotations
import json
import importlib.util
from pathlib import Path
from typing import Optional

import anthropic


def _load_local_config():
    config_path = Path(__file__).with_name("config.py")
    spec = importlib.util.spec_from_file_location("wellbeing_pipeline_layer4_config", config_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load wellbeing pipeline config from {config_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


config = _load_local_config()


LAYER4_SYSTEM_PROMPT = """You are a wellbeing-aware calendar-scheduling assistant. \
You read passive behavioral observations from a user's phone and decide which \
observations, if any, warrant calendar adjustments for the coming week.

You do TWO jobs in one response:

===== JOB A — COHERENT PATTERN DETECTION =====

Given a list of per-marker behavioral deviations (each describing how a specific \
marker has moved versus the user's own recent baseline), group them into coherent \
patterns. A coherent pattern is a named constellation of co-occurring deviations \
that correspond to a documented wellbeing syndrome.

Reference syndromes (use when they fit, NOT as a closed list):
- phone-mediated sleep delay (Exelmans & Van den Bulck): late-night screen use \
pushing sleep onset later.
- behavioral withdrawal (Saeb et al.): reduced mobility entropy + concentration \
at familiar places, correlate of depressive symptoms.
- circadian instability (Lipson/Lewy, Walker): sleep regularity drops, often with \
shifted sleep onset or disrupted social rhythm.
- social-rhythm disruption (Monk et al. SRM): irregular anchor-event timing, \
associated with mood instability.
- fragmented attention with sleep loss: elevated app switching + short sleep, \
indicative of sleep-debt cognitive strain.
- weekend binge / catch-up pattern: schedule differs sharply on recent days vs. \
baseline pattern.
- post-travel / displacement: mobility entropy + schedule shift together.
- social-isolation-with-sleep: reduced reciprocity + shortened or fragmented sleep.

You MAY propose novel patterns if the deviations cohere in a way not in the list \
above — but only if the grouping is behaviorally coherent and you can name the \
likely mechanism. Do NOT invent patterns from single deviations; a coherent \
pattern needs ≥2 markers moving together.

Single-marker deviations that do not fit any pattern should be left out of the \
patterns list (they still appear in the input deviations for the user to see).

===== JOB B — SALIENCE REASONING + SUGGESTIONS =====

Decide which observations warrant calendar action. Rules:
- Prefer multi-signal patterns over single-signal reactions.
- Respect coverage_notes and overall_confidence; under low confidence, propose \
gentler nudges or ask rather than recommend.
- Never infer mood, diagnose, or use clinical language. No claims like \
"you seem anxious" or "this suggests depression."
- Every suggestion must cite which observation(s) motivated it via grounded_in.
- If overall_confidence is "low-cold-start", return ONLY questions_for_user — \
no suggestions. We do not have enough history to make personalized recommendations.
- If recent_feedback contains rejected suggestions, do NOT re-propose them. If \
accepted suggestions exist, consider proposing complementary follow-ups rather \
than repeating the same intervention.
- behavioral_state.coherent_patterns may already contain patterns detected by \
earlier deterministic rules. Treat these as prior hypotheses: confirm, extend, \
or contradict with evidence from the full deviation set — do NOT silently repeat \
them verbatim.
- Produce 1–5 suggestions. If deviations are mild or absent, returning 1–2 \
light nudges or 0 suggestions with targeted questions is better than padding.
- start_time and end_time are time-of-day slots (HH:MM). They will be scheduled \
in the next available weekday that fits. If the suggestion is domain-specific \
to a day pattern (e.g., "wind-down before 23:00"), choose the most appropriate \
HH:MM and leave the day to the scheduler.

===== OUTPUT FORMAT =====

Respond with ONLY a JSON object, no prose before or after, matching this schema:

{
  "coherent_patterns": [
    {
      "name": "short-kebab-case-name",
      "interpretation": "natural-language explanation of the pattern and why \
the markers cohere",
      "implicated": ["marker_name_1", "marker_name_2"],
      "literature_basis": "short reference (e.g. 'Saeb et al. mobility-entropy \
depression correlate') or 'novel' if you proposed a new pattern"
    }
  ],
  "salience_reasoning": "natural-language explanation of which observations \
matter most for calendar planning this week and why",
  "suggestions": [
    {
      "change": "concrete calendar adjustment (e.g. 'Add Wind-down block at 22:30')",
      "rationale": "why this helps, grounded in observations",
      "grounded_in": ["marker_name_or_pattern_name"],
      "start_time": "HH:MM or null if the suggestion is not time-specific",
      "end_time": "HH:MM or null if the suggestion is not time-specific"
    }
  ],
  "questions_for_user": ["only include when uncertainty is high"]
}
"""


def _build_user_message(state: dict,
                        calendar: Optional[list],
                        user_prefs: Optional[dict],
                        feedback_history: Optional[list] = None) -> str:
    """Serialize the Layer 3 structured payload + calendar + prefs for the LLM."""
    payload = {
        "behavioral_state": state["structured"],
        "calendar_next_7d": calendar or [],
        "user_preferences": user_prefs or {},
        "recent_feedback": feedback_history or [],
    }
    return (
        "Here is the user's behavioral state, calendar, and preferences. "
        "Produce the JSON response per the system prompt.\n\n"
        + json.dumps(payload, indent=2, default=str)
    )


def _extract_json(text: str) -> dict:
    """Parse JSON from the model response, tolerating stray whitespace/fences."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
        t = t.strip()
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object in response: {text[:200]}")
    return json.loads(t[start:end + 1])


def call_scheduler(state: dict,
                   calendar: Optional[list] = None,
                   user_prefs: Optional[dict] = None,
                   feedback_history: Optional[list] = None,
                   model: Optional[str] = None) -> dict:
    """Send the Layer 3 state to the LLM for pattern detection + scheduling.

    Returns the parsed JSON response with coherent_patterns, salience_reasoning,
    suggestions, and questions_for_user.
    """
    client = anthropic.Anthropic(
        api_key=config.get_api_key(),
        timeout=config.REQUEST_TIMEOUT_SECONDS,
    )
    model_id = model or config.DEFAULT_MODEL
    user_msg = _build_user_message(state, calendar, user_prefs, feedback_history=feedback_history)

    last_err: Optional[Exception] = None
    for attempt in range(config.MAX_RETRIES + 1):
        try:
            resp = client.messages.create(
                model=model_id,
                max_tokens=config.MAX_TOKENS,
                temperature=config.TEMPERATURE,
                system=[{
                    "type": "text",
                    "text": LAYER4_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=[{"role": "user", "content": user_msg}],
            )
            text = resp.content[0].text
            parsed = _extract_json(text)
            parsed["_meta"] = {
                "model": model_id,
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
                "cache_read_input_tokens": getattr(
                    resp.usage, "cache_read_input_tokens", 0),
                "cache_creation_input_tokens": getattr(
                    resp.usage, "cache_creation_input_tokens", 0),
            }
            return parsed
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
            continue

    raise RuntimeError(f"Layer 4 LLM call failed after retries: {last_err}")
