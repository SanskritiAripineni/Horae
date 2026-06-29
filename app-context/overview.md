# AutoLife — App Overview

## What AutoLife Is

AutoLife is a mental wellness and life-logging app that passively monitors smartphone behavioral signals (motion, location, sleep patterns, screen time, app usage, WiFi context) and fuses them with user-written journal entries. A multi-agent AI pipeline analyzes these signals, assesses the user's mental wellbeing state, and proposes specific Google Calendar changes to help build healthier habits — all grounded in peer-reviewed wellness research.

It is a research platform targeting ~100 consenting university participants. The app is the core artifact of a paper on the "LLM Scheduler RIDE" system. Current UI documentation should be read as participant-pilot readiness guidance: some screens describe the intended state after sensors, journals, calendar auth, and backend analysis are available, while the live initial runtime may begin with empty or low-confidence data.

---

## Core Purpose

1. **Passive behavioral sensing** — collect sensor-derived markers throughout the day without explicit user effort
2. **Journal narrative** — user or auto-generated text entries describing daily experience
3. **AI wellbeing assessment** — multi-layer pipeline produces a `risk_level` (minimal / mild / moderate / severe) and structured concerns/positives
4. **Research-backed recommendations** — ChromaDB retrieval against wellness research papers
5. **Calendar optimization** — propose concrete, timed events to improve mental health outcomes
6. **Feedback loop** — user accept/reject decisions personalize future suggestions

---

## End-to-End User Flow

```
1. AutoLife Service runs in background on Android
   → Collects motion, location, WiFi, app usage data
   → Every 15 min (2 min in demo mode): generates a journal entry from sensor context

2. User opens the app
   → Journal tab: see collected entries and live sensor logs, or first-run empty states
   → Agent tab: tap "Run Analysis" to trigger the backend pipeline when enough data exists

3. Backend processes the journals + sensor markers
   → 4-layer behavioral sensing pipeline
   → Gemini AI synthesizes everything into a wellbeing assessment
   → ChromaDB retrieves relevant research interventions
   → Orchestrator produces recommendations + proposed calendar events

4. User reviews results
   → Health tab: assessment, concerns, positives, recommendations, plus warmup/confidence messaging when data is sparse
   → Schedule tab: visual week calendar with proposals overlaid when proposals exist
     → Select which proposals to apply
     → Tap "Apply X changes to Calendar"

5. Backend writes selected events to Google Calendar
   → Records user's accept/reject feedback
   → Feedback informs future pipeline cycles

6. Memory tab: view personalization state
   → Work hours, goals, preferred interventions
   → Historical risk level trend
```

The mobile information architecture remains five participant-facing tabs: Agent, Health, Schedule, Journal, and Memory. Dev tools stay visible during testing through a gear/debug route so researchers can inspect service state, demo timing, backend URLs, and raw outputs; this route may later become a conventional Settings area.

---

## Participant-Pilot UX Expectations

- First-run screens must handle no journals, no sensor logs, no previous analysis result, no proposals, and no memory history without implying that live data exists.
- Empty, loading, partial, error, and ready states should be explicit in the UI, especially on Health, Schedule, Journal, and Memory.
- Confidence/warmup language should appear when baseline history is limited, sensor coverage is sparse, calendar context is unavailable, or backend responses include partial failures.
- Wellbeing output is AI-assisted study feedback, not a clinical diagnosis.
- Destructive actions such as clearing journals/logs and applying calendar writes require user confirmation and should clearly state what will change.
- Privacy-sensitive raw signals should stay aggregated or confined to debug/testing surfaces; participant-facing views should avoid exposing raw location or low-level sensor payloads.

---

## Two Major Components

### Python Backend (FastAPI, Railway-hosted)
- Runs the multi-agent pipeline
- Integrates with Gemini API, Google Calendar, ChromaDB
- Deployed at `ride-backend-production-a1fc.up.railway.app`

### Android/KMP Mobile Client
- Kotlin Multiplatform + Compose Multiplatform
- Shared business logic for Android and iOS
- Android-specific: background sensor service, Room DB
- iOS-specific: native sensor bridge, SwiftUI wrapper

---

## Key Vocabulary

| Term | Meaning |
|------|---------|
| `risk_level` | Pipeline output: minimal / mild / moderate / severe |
| `raw_days` | Daily sensor marker aggregates sent to backend |
| `proposed_changes` | Calendar events the AI recommends adding/modifying |
| `behavioral_sensing` | 4-layer pipeline analyzing sensor patterns |
| `interventions` | Research-backed actions retrieved from VectorDB |
| `suggest_only` mode | Default: agent proposes but doesn't write to calendar |
| RIDE Agent | The target Google Calendar ("RIDE Agent" calendar) |
| Layer 4 suggestions | Time-specific suggestions from the behavioral LLM layer |
| Conflict | Proposed event overlaps an existing calendar event |
| Demo mode | 2-min journal interval (vs 15-min normal), visible in Dev Dashboard during testing |
