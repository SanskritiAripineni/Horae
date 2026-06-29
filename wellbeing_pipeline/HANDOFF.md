# Wellbeing Sensing Rearchitecture — Full Context Handoff

This document replaces a long design chat. Read §0–§4 for the *why*, §5–§6 for the *what*, §8 for the *what's built*, §10 for *what to do next*. Cross-reference the rest as needed.

---

## 0. TL;DR (orientation)

The upstream exploratory project was doing binary momentary-mood classification on StudentLife + K-EmoPhone with LOSO evaluation and hitting a 55–64% balanced-accuracy ceiling. That ceiling is a well-documented property of generic population models on momentary mood from phone-only passive sensing — not a pipeline bug.

The architecture has been re-framed. The sensing pipeline no longer predicts mood. It produces **rich natural-language descriptions of behavioral deviations from each user's personal baseline**, consumed by an LLM scheduler (LLM Scheduler RIDE) which reasons about whether any observation warrants a calendar adjustment. No mood classification anywhere. No scalar salience scores. Zero-shot — no cross-user training.

A three-layer prototype exists and runs end-to-end on synthetic data. Immediate next step is writing the adapter from StudentLife's extracted features into the pipeline.

---

## 1. Starting problem

Baseline experiment: phone-only passive sensing → binary mood classification, LOSO-evaluated, 55–64% balanced accuracy. Consistent with published ceilings; not a bug.

Relevant literature anchors:
- **Apple WBM (2025)** — Wearable Behavioral Model pretrains on high-level behavioral features (not raw streams), 57 health tasks, beats raw-sensor foundation models. Suggests "behavioral derivative features, not raw sensor windows."
- **JMIR 2025** systematic reviews — 81–91% accuracy for depression *severity* from passive sensing, but on weekly/biweekly PHQ-8 labels, not momentary mood. Target choice drives accuracy, not architecture.
- **npj Digital Medicine 2024** — circadian phase shifts predict bipolar/MDD mood episodes from sleep patterns.
- **StudentLife / CrossCheck / Saeb** — weekly PHQ-8 from 2-week sensor windows → 0.75–0.85 AUC. Strong.
- **Nature Sci Reports 2024** — keystroke dynamics alone detect depressive tendency with high AUC, fully passive, zero EMA.

---

## 2. The mindset shift (three tightening frames)

**Frame 1 — Ceiling is real.** 55–64% is a fundamental SNR limit for generic population models on momentary mood from phone-only passive data. No ensemble/MoE/foundation-model trick on this problem definition reliably breaks past ~65%.

**Frame 2 — Target reframe (insufficient).** Switching to weekly PHQ-8 as the target, with circadian + sleep-regularity + mobility-entropy features and per-user baselining, hits state-of-the-art (~0.80 AUC). But this is clinically narrow — one axis of depression — and misses the project goal of rich, dimensional emotion signal for a general wellbeing population.

**Frame 3 — Stop predicting mood entirely (the commitment).** The downstream consumer in the scheduler framework is an LLM, not a human reading a label. The LLM does not need `{"mood": "anxious", "p": 0.82}`. It needs verifiable behavioral facts it can reason over:

> *Sleep onset drifted 1.5h later over the last 4 days. Screen time after midnight up 40% vs personal baseline. Mobility entropy at user's 20th percentile this week. Calendar adherence dropped from 85% to 60%.*

The LLM scheduler then reasons contextually: *"this pattern resembles low-grade depressive drift — suggest morning light-exposure blocks, protect earlier social commitments, thin out evening meeting density."*

Because the pipeline no longer classifies, the 55–64% ceiling stops constraining the system. The ML problem becomes "detect meaningful deviations from a user's personal baseline and describe them naturally" — which is statistical, not predictive, and largely solved by construction.

**This is the central design commitment. Everything below follows from it. If a future suggestion requires predicting mood labels, re-read this section.**

---

## 3. Framework integration (LLM Scheduler RIDE)

The broader framework:

- **Memory**: user preferences + mental health tracking
- **Tools**:
  - AutoLife → motion/location → Daily Journal
  - ~~K-Emo Phone → PHQ Score~~ → **replaced by behavioral state description** (three-layer pipeline below)
  - VectorDB → Top-K similar past states (personalization memory)
  - Calendar API → events, todos → Schedule
- **Agent**: LLM Scheduler Agent consumes dynamic sensor data
- **Output**: daily/weekly calendar optimized for wellbeing

**Correction to the original framework diagram**: the `K-Emo Phone → PHQ Score` edge is gone. PHQ is not a continuous inference target. It may be used once at onboarding as a baseline anchor (optional) or as a biweekly check-in for evaluation, but the primary sensing output is now the Layer 3 behavioral state description.

VectorDB Top-K serves as **personalization memory**: retrieve analogous past behavioral states for this user, enabling the LLM to reason by analogy. This is where cold-start personalization lives and where scheduler-feedback signals accumulate.

---

## 4. Hard constraints (do not revisit)

1. **Phone-only.** No wearables. E4 / Apple Watch / Fitbit / Oura are all out.
2. **General wellbeing population**, not clinical.
3. **Personalization with small cold-start is acceptable.** Per-user baselining is encouraged.
4. **Minimal user input.** Ultra-minimal EMA (≤1 tap/day) is acceptable; anything heavier is not.
5. **"Accurate" matters** — redefined under the new architecture, see §7.
6. **K-EmoPhone is probably out.** Its main unique value was the E4 wearable (excluded). Remaining phone features overlap with StudentLife.

---

## 5. The new method — three-layer architecture

Zero-shot by construction. No training. Each user is their own reference.

### 5.1 Layer 1 — Personal baselines + wellbeing markers

Markers (each literature-anchored):

| Marker | Domain | Unit | Notes |
|---|---|---|---|
| `sleep_onset_hour` | sleep | hours (24h, post-midnight allowed) | |
| `sleep_duration_hours` | sleep | hours | |
| `sleep_regularity_index` | sleep | 0–100 | Phillips et al. 2017 |
| `late_night_screen_min` | screen | minutes | 23:00–04:00 window |
| `total_screen_min` | screen | minutes | |
| `app_switching_rate` | screen | switches/active-min | fragmented-attention proxy |
| `mobility_entropy` | mobility | nats | Shannon entropy of dwell time across locations |
| `location_revisit_ratio` | mobility | fraction | time at top-3 places |
| `social_rhythm_metric` | social | 0–1 | Monk et al. SRM |
| `comm_reciprocity` | social | ratio | outgoing / (out + in) |

Layer 2 is marker-agnostic. Adding/removing markers is trivial.

**`PersonalBaseline`** holds `DayRecord`s — each a `(day, markers_dict, coverage_dict)`. Computes rolling stats (mean, std, median, p20, p80) on demand over configurable windows. `warmup_days=10` minimum before baseline is "warm."

**Coverage tracking per marker is essential.** When data is missing (permission denied, phone off, weekend GPS gap), coverage drops and Layer 3 flags this rather than silently imputing.

**`markers_from_raw(raw_day)` adapter** is the single swap point for data sources. Currently a pass-through for structured dict input; the StudentLife version needs to map column names and compute derived markers.

### 5.2 Layer 2 — Deviation detection + coherent patterns

Compares recent window (default 4 days) against personal baseline window (default 28 days, ending before recent). All magnitude and trajectory outputs are **categorical strings** — the LLM reasons over them without being misled by spurious numeric precision. No scalar salience scores anywhere.

**Magnitude categories** (from internal z-score against baseline):
- `within-typical` (|z| < 1.0)
- `mild` (1.0 ≤ |z| < 1.8)
- `moderate` (1.8 ≤ |z| < 2.8)
- `pronounced` (|z| ≥ 2.8)

**Trajectory categories**:
- `acute-1d`: single-day spike
- `sustained-Nd`: all N days elevated, consistent sign
- `drift-emerging-Nd`: monotone trend, same sign
- `intermittent-Nd-of-M`: scattered across window
- `within-typical`

Each `Deviation` carries its own **natural-language finding**, templated per marker from verified numbers. Example output: *"Sleep onset has been around 00:43 (about 1.1h later than typical 23:35); sustained across the last 4d."* No hallucination surface — the template just fills in arithmetic.

**Coherent-pattern rules** (curated, four so far, in `COHERENCE_RULES`):

1. **phone-mediated-sleep-delay** — `sleep_onset_hour↑` + `late_night_screen_min↑`
2. **behavioral-withdrawal** — `mobility_entropy↓` + `location_revisit_ratio↑` (+ optional `social_rhythm_metric↓`)
3. **circadian-instability** — `sleep_regularity_index↓` (+ optional `sleep_onset_hour↑`, `social_rhythm_metric↓`)
4. **fragmented-attention-with-sleep-loss** — `app_switching_rate↑` + `sleep_duration_hours↓`

Each rule carries its own natural-language interpretation referencing the pattern, not numbers. Adding patterns is an append to the list. Future work: let the LLM itself propose patterns; learn per-user pattern relevance from scheduler feedback.

### 5.3 Layer 3 — Rich behavioral state for the LLM scheduler

Dual output:
- **`structured`** (JSON dict): LLMs reason over structure more reliably than narrative.
- **`prose`** (string): human-readable Daily Journal for the user-facing UI.

Structured fields:
- `baseline_state`: `{warm, days_of_history, overall_confidence: high|medium|low|low-cold-start}`
- `deviations`: list of per-marker findings with all fields from §5.2
- `coherent_patterns`: list of patterns with interpretations
- `coverage_notes`: explicit callouts for low-coverage markers — LLM discounts claims there
- `schema_note`: LLM behavior contract (descriptive only, no mood inference, respect coverage, prefer patterns over single signals)

**The LLM is the salience reasoner.** No ranker model, no scalar score, no top-k. The scheduler LLM receives the structured deviations + patterns and reasons about which are worth acting on given calendar, preferences, and coherence.

**`SCHEDULER_SYSTEM_PROMPT`** is provided in `layer3.py`. Key enforced rules:
- Never infer mood, never diagnose
- Prefer multi-signal patterns over single-signal reactions
- Cite which observations motivated each suggestion (`grounded_in` field)
- Gentle nudges / questions under low confidence instead of confident recommendations

**Expected scheduler output**:
```json
{
  "salience_reasoning": "natural language: which observations matter and why",
  "suggestions": [
    {"change": "...", "rationale": "...", "grounded_in": ["marker_or_pattern"]}
  ],
  "questions_for_user": ["..."]
}
```

---

## 6. Paths explicitly rejected (do not re-suggest without new information)

1. **Continuous PHQ-8 inference.** Weak target; collapses rich emotion to one axis. Onboarding/biweekly only.
2. **Wearable sensors.** Hard constraint.
3. **Mixture-of-Experts with scalar salience ranker.** Rejected in favor of LLM-driven natural-language salience.
4. **Heavy EMA.** Low compliance in wellbeing population. Implicit scheduler feedback (accept/reject/modify/no-show) is the personalization signal.
5. **Pre-training on StudentLife.** Architecture is zero-shot. StudentLife is evaluation, not training.
6. **Momentary mood classification on generic population.** This is the 55–64% ceiling.
7. **`K-Emo Phone → PHQ Score` direct pipeline.** The specific failed approach this whole rework replaces.

---

## 7. What "accurate" means under this architecture

Accuracy decomposes cleanly:

| Stage | Accuracy source | Typical |
|---|---|---|
| Layer 1 markers | Sensor engineering (sleep detection from phone, etc.) | 70–85% vs ground truth, marker-dependent |
| Layer 2 deviation detection | Deterministic stats on user's own history | Exact by construction |
| Layer 2 natural-language finding | Templated from verified numbers | No hallucination surface |
| Layer 2 coherent patterns | Curated rule correctness | As good as the rule |
| Layer 3 prose | Templated aggregation | No hallucination surface |
| LLM scheduler reasoning | Prompting + intervention library | Separable, validatable |

The 55–64% ceiling no longer applies because nothing in the pipeline classifies. Remaining failure modes: bad sensor markers (Layer 1), bad rules (Layer 2), bad LLM prompting (Layer 3b) — all independently fixable.

---

## 8. Current implementation state

Five files, location to be decided (now represented in this repository under `wellbeing_pipeline/`):

### `layer1.py`
- `MARKER_SPECS` dict (10 markers with domain, unit, notes)
- `DOMAIN_OF` lookup
- `DayRecord` dataclass
- `PersonalBaseline` class: `add`, `is_warm`, `window`, `stats`, `coverage_quality`
- `markers_from_raw(raw_day) → DayRecord` — **the swap point for real data**

### `layer2.py`
- `_magnitude_cat(z)`, `_trajectory(z_series)` — categorical helpers
- Per-marker natural-language template renderers (`_render_finding`)
- `Deviation` dataclass (marker, domain, finding, magnitude, trajectory, direction, coverage, recent/baseline stats)
- `detect_deviations(baseline, as_of, recent_days=4, baseline_days=28, min_magnitude="mild")`
- `COHERENCE_RULES` (the four rules above)
- `CoherentPattern` dataclass
- `find_coherent_patterns(deviations) → list[CoherentPattern]`

### `layer3.py`
- `build_state_description(baseline, deviations, patterns, as_of) → {structured, prose}`
- `SCHEDULER_SYSTEM_PROMPT` (complete, ready for Anthropic API)
- `render_llm_input(state, calendar, user_prefs) → payload dict`

### `synthetic.py`
- `generate_user_days(n_days=30, seed=42)`
- Days 0–19: stable baseline (sleep ~23:24, SRI ~82, screen ~240min, mobility entropy ~1.22)
- Days 20–29: gradual drift (sleep onset → 00:45 by day 25, late-night screen ~3x, mobility narrowing, attention fragmenting)
- Realistic coverage gaps for mobility (10% of days) and social (20% of days)

### `demo.py`
- Runs pipeline at days 14, 22, 29
- Prints deviations, coherent patterns, prose, structured payload

**Verified pipeline behavior on synthetic data:**
- **Day 14 (warm-up)**: a few low-level flags, no coherent patterns, `confidence=medium` — appropriately conservative
- **Day 22 (drift starting)**: `late_night_screen_min` +24%, no patterns yet — correct conservatism
- **Day 29 (drift established)**: 9 deviations across all 4 domains, 4 coherent patterns fire, rich prose output

**No LLM call wired up.** `render_llm_input` produces the payload; needs an Anthropic client call. Recommend Sonnet 4.7 for cost, compare Opus 4.7 for reasoning quality.

---

## 9. Known limitations and risks

1. **Phone-only sleep detection ≈ 70–85% vs PSG.** Claims in sleep findings should stay conservative. Avoid strong arousal claims (can't measure HRV).
2. **No direct arousal signal.** Arousal is inferred indirectly via activity patterns. Weaker than wearable-based.
3. **Cold start (first 10–14 days).** Baseline inert, personalization can't kick in. Retention-risk window. Onboarding UX needs explicit "we're learning your patterns" messaging.
4. **LLM intervention quality unverified.** Safety layer needed: expert-validated intervention library the LLM selects from, at minimum for sleep / isolation / activity / social suggestions.
5. **Warm-up false-positive feel.** Days 10–14 sometimes flag minor noise. Fix: raise `min_magnitude="moderate"` automatically during warm-up, or require `sustained-3d` minimum.
6. **Curated pattern rules.** Four rules cover common archetypes, not everything. Short term: add literature-grounded rules (seasonal shift, post-travel, weekend binge). Long term: LLM proposes patterns; learn per-user relevance from feedback.
7. **Evaluation story is partially open.** Retrospective on StudentLife (do surfaced deviations precede EMA/PHQ dips?) is cheap. Prospective (does acting on suggestions improve trajectory?) requires a pilot study.

---

## 10. Open implementation questions — pick one to start

Priority order:

**(a) StudentLife adapter — recommended first step.**
Implement `markers_from_raw` body to consume StudentLife extract output. Map column names to `MARKER_SPECS` keys. Compute markers not already extracted (SRM, mobility entropy) from raw GPS/call/SMS streams. Run pipeline on 3–5 StudentLife participants. Inspect Layer 3 prose for face validity. Smallest surface area of change; transitions from "works on synthetic" to "works on real data" with minimum risk.

**(b) LLM scheduler call.**
Wire `render_llm_input` output to Anthropic API. Test Day 29 synthetic payload with Sonnet 4.7 vs Opus 4.7. Validate: does the LLM respect coverage notes? Does it cite grounding? Does it prefer multi-signal patterns? Does it avoid mood language?

**(c) Feedback-loop personalization.**
Design the signal: `(suggestion, user_action ∈ {accept, reject, modify, no-show, snooze})`. Store in VectorDB keyed by the preceding behavioral state. Retrieval at new-suggestion time: "what happened last time this user saw analogous deviations?" This is the closed-loop personalization layer.

**(d) Cold-start UX.**
First 10 days design: population priors with heavy uncertainty caveats? Onboarding questionnaire bootstrap? Hybrid? This is retention-critical.

**(e) Intervention safety library.**
Curated calendar-change templates with evidence-quality tags. LLM picks from library rather than free-generating for clinically-shadowed domains.

---

## 11. Research framing (NeurIPS 2026)

**Proposed contribution**: *LLM-mediated behavioral feedback loop for wellbeing*.

Novel composition — pieces exist in literature individually, not assembled this way:
- Zero-shot per-user deviation detection with natural-language findings
- Curated + LLM-extensible coherent pattern grouping
- LLM as salience reasoner (no separate ranker)
- Closed-loop personalization via scheduler feedback (not EMA)
- Uncertainty-aware dimensional output (not classification)

Target track: **Datasets & Benchmarks** or **Applications**.

Evaluation axes:
- **Retrospective on StudentLife**: do detected deviation-patterns correlate with subsequent EMA / PHQ-8 dips?
- **Face validity**: do clinicians judge Layer 3 prose as faithful to the underlying data?
- **Prospective pilot**: wellbeing trajectory vs sham-schedule control (stretch goal, IRB-dependent)

Abstract deadline: **May 4, 2026**. Full paper deadline: **May 6, 2026 AoE**.

---

## 12. Dataset strategy

- **StudentLife**: primary eval dataset. Phone-only, multi-week, paired with EMA + PHQ + sleep + grades. Use for validating that pipeline surfaces meaningful deviations. Extraction already exists via `studentlife_extract.py`.
- **K-EmoPhone**: deprioritize. E4 wearable (main unique value) excluded by constraint. Phone features overlap with StudentLife. Keep only if pursuing Korean-working-adults vs US-undergrads domain adaptation as a secondary research angle.
- **User's own Android phone**: viable later for live-data testing. Not needed for initial viability.
- **Raw data**: gitignored. Processed outputs in `box_upload/` with downstream-ML-ready `.pkl` files.

---

## 13. Pointers into existing project

- Project root: this repository
- Previous extraction pipeline: `studentlife_extract.py`, `analysis.py`
- `CLAUDE.md` has session logs through 2026-04-16; **append to Session Log on session end** (hook enforces)
- `README.md` and `.gitignore` already in place; git repo initialized
- Old classification code — **do not delete**, mark as superseded. Results there are the baseline that this rework supersedes.
- Suggested new location for this pipeline: `wellbeing_pipeline/` subdirectory alongside the old code

---

## 14. Default next action for Claude Code

Unless the user says otherwise, begin with **§10 option (a) — the StudentLife adapter**. Start by:

1. Inspecting `studentlife_extract.py` to understand its output schema.
2. Reading one processed participant's `.pkl` file to see available columns.
3. Writing the mapping from StudentLife column names → `MARKER_SPECS` keys.
4. Implementing any missing derived markers (likely: SRM, mobility entropy — small number of lines each).
5. Running the pipeline on 3–5 participants and printing Layer 3 prose output per participant per week.
6. Inspecting outputs for face validity — does the narrative match what you'd expect from glancing at each participant's raw feature time series?

Report back with a sample of Layer 3 outputs across participants before investing in downstream work (LLM call, feedback loop, etc.).

**Do not re-open the classification-accuracy discussion.** That ceiling is acknowledged, the reframe is committed, and the new architecture does not depend on it.
