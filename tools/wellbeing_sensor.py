"""
WellbeingSensor — three-layer behavioral sensing pipeline (wellbeing_pipeline/).

Input:  list of raw_day dicts (one per day) — phone sensor markers.
Output: {
    "behavioral_state": <Layer 3 structured JSON>,
    "prose":            <Layer 3 daily journal string>,
    "llm_analysis":     <Layer 4 dict: coherent_patterns, salience_reasoning,
                         suggestions, questions_for_user>   (None if no API key)
}
"""
from __future__ import annotations
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Make wellbeing_pipeline importable from here
_PIPELINE_DIR = Path(__file__).parent.parent / "wellbeing_pipeline"
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from layer1 import PersonalBaseline, markers_from_raw        # noqa: E402
from layer2 import detect_deviations, find_coherent_patterns  # noqa: E402
from layer3 import build_state_description, render_llm_input  # noqa: E402

logger = logging.getLogger(__name__)


class WellbeingSensor:
    """
    Runs the wellbeing pipeline (Layers 1–4) on pre-processed daily sensor data.

    Usage:
        sensor = WellbeingSensor()
        result = sensor.analyze(raw_days, calendar=[...], user_prefs={...})
        print(result["prose"])
        print(result["llm_analysis"]["suggestions"])
    """

    def __init__(self,
                 warmup_days: int = 5,
                 recent_days: int = 4,
                 baseline_days: int = 28,
                 model: Optional[str] = None):
        self.warmup_days = warmup_days
        self.recent_days = recent_days
        self.baseline_days = baseline_days
        self.model = model  # None → uses wellbeing_pipeline/config.DEFAULT_MODEL

    def analyze(self,
                raw_days: list[dict],
                calendar: Optional[list] = None,
                user_prefs: Optional[dict] = None,
                feedback_history: Optional[list] = None,
                with_llm: bool = True) -> dict:
        """
        Run Layers 1→4 on a list of raw_day dicts.

        raw_days: list of dicts with keys matching MARKER_SPECS plus a 'date'
                  field (date object). Missing markers should be None.
        calendar: list of calendar event dicts for the next 7 days (optional).
        user_prefs: dict of user preferences passed to Layer 4 (optional).
        feedback_history: list of feedback dicts for personalization (optional).
        with_llm: if False, skip the Layer 4 API call.

        Returns dict with keys: behavioral_state, prose, llm_analysis, baseline_warm.
        """
        if not raw_days:
            return {"behavioral_state": None, "prose": "", "llm_analysis": None, "baseline_warm": True}

        baseline = PersonalBaseline(warmup_days=self.warmup_days)
        for raw in raw_days:
            baseline.add(markers_from_raw(raw))

        as_of = baseline.history[-1].day
        devs = detect_deviations(
            baseline, as_of=as_of,
            recent_days=self.recent_days,
            baseline_days=self.baseline_days,
            min_magnitude="mild",
        )
        patterns = find_coherent_patterns(devs)
        state = build_state_description(baseline, devs, patterns, as_of)
        baseline_warm = baseline.is_warm()

        llm_result = None
        if with_llm and os.environ.get("ANTHROPIC_API_KEY"):
            try:
                from layer4_llm import call_scheduler
                llm_result = call_scheduler(
                    state=state,
                    calendar=calendar or [],
                    user_prefs=user_prefs or {},
                    feedback_history=feedback_history,
                    model=self.model,
                )
            except Exception as e:
                logger.warning(f"Layer 4 LLM call failed: {e}")

        return {
            "behavioral_state": state["structured"],
            "prose": state["prose"],
            "llm_analysis": llm_result,
            "baseline_warm": baseline_warm,
        }

