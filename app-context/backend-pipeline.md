# AutoLife — Backend Pipeline

## Entry Point

`POST /api/process_journals` → `agent.py::LLMSchedulerAgent.run_from_journals()`

All pipeline logic flows through this single entry point. Both the API and CLI delegate to it.

---

## Pipeline Steps (in order)

### Step 1 — Journal Narrative
- **Input:** list of journal entry dicts (up to 10 most recent)
- **Tool:** `AutoLifeReader.get_context_for_prompt(journals)`
- **Output:** prose string (max ~6,000 chars) describing recent life context
- **Role:** Background context for the orchestrator LLM — not treated as a wellbeing signal

### Step 2 — Calendar Retrieval
- **Tool:** `CalendarAPI.get_schedule_summary(days=7)`
- **Output:**
  ```json
  {
    "event_count": 5,
    "events": [{"id": "...", "title": "...", "start": "...", "end": "...", "duration_hours": 1.0}],
    "total_hours": 8.5,
    "busiest_day": "2024-01-16",
    "days_covered": 7,
    "tasks": [{"id": "...", "title": "...", "due": "...", "list": "Work"}],
    "task_count": 3
  }
  ```
- **Role:** Provides scheduling context; enables conflict detection

### Step 3 — Behavioral Sensing (4-layer pipeline)
- **Input:** `raw_days` — list of daily sensor marker dicts
- **Skipped** if `raw_days` is empty or not provided

#### Layer 1: Personal Baseline (`PersonalBaseline`)
- Computes mean/std per marker over historical window
- Tracks warmup: requires 10+ days before reliable deviations

#### Layer 2: Deviation Detection
- Compares last 4 days against baseline
- Flags deviations by severity: mild / notable / severe
- Groups by domain: sleep, social, activity, screen

#### Layer 3: State Description (`build_state_description()`)
- Produces structured JSON:
  ```json
  {
    "concerns": ["disrupted sleep onset", "elevated screen time"],
    "positives": ["consistent physical activity"],
    "categories_affected": ["sleep", "screen"],
    "severity": "moderate"
  }
  ```
- Produces prose narrative (50–300 words):
  > "Your sleep has been notably disrupted over the past 4 days, with sleep onset averaging 1.5 hours later than your baseline…"

#### Layer 4: LLM Analysis (`call_scheduler()`)
- **LLM:** Gemini (via `tools/llm_client.py`)
- **Input:** State prose + calendar summary + feedback history
- **Output:**
  ```json
  {
    "coherent_patterns": ["screen-sleep disruption cycle"],
    "suggestions": [
      {
        "start_time": "21:30",
        "end_time": "21:45",
        "change": "Screen-free wind-down ritual",
        "rationale": "Break late-night habit, restore sleep boundary"
      }
    ]
  }
  ```
- Layer 4 suggestions are **promoted** to `proposed_changes` if they have `start_time` and no conflict

### Step 4 — VectorDB Retrieval
- **Input:** `risk_level` (inferred from Layer 3 prose keywords) + journal summary
- **Tool:** `VectorDBClient.get_intervention_suggestions(risk_level, query_text)`
- **Query strategy by risk:**
  - `severe` → coping strategies, crisis support
  - `moderate` → stress management, sleep hygiene
  - `mild` → habit improvement, mindfulness
  - `minimal` → habit building, optimization
- **Output:** top-4 research snippets:
  ```json
  [
    {
      "content": "Regular aerobic exercise 3x/week reduces cortisol...",
      "category": "Physical Activity",
      "source": "Smith et al. 2022"
    }
  ]
  ```
- **VectorDB:** ChromaDB, 3072-dim Gemini Embedding 2 vectors
- **Collection:** `wellness_papers_gemini`
- **Categories:** Sleep Hygiene, Stress Management, Social Connection, Physical Activity, Mindfulness

### Step 5 — Orchestrator LLM Call
- **Tool:** `LLMClient.generate_schedule_proposals()`
- **Model:** `gemini-3-flash-preview`
- **Single unified call** — all prior pipeline outputs are bundled into one prompt
- **Input context includes:**
  - Journal narrative (Step 1)
  - Behavioral prose + Layer 4 analysis (Step 3)
  - Risk level heuristic
  - Calendar summary (Step 2)
  - Research interventions (Step 4)
  - User preferences (from memory module, if any)
  - Feedback history (last 10 accept/reject decisions)
- **Output (JSON):**
  ```json
  {
    "risk_level": "mild",
    "summary": "User shows mild sleep disruption but maintains positive exercise habits.",
    "concerns": ["below-average sleep duration", "elevated late-night screen time"],
    "positives": ["maintained physical activity", "social engagement present"],
    "recommendations": [
      {
        "category": "Sleep",
        "action": "Set device quiet hours 22:00–07:00",
        "when": "Tonight",
        "source": "Smith et al. 2022"
      }
    ],
    "proposed_changes": [
      {
        "action": "add",
        "title": "Evening Wind-Down",
        "description": "Phone-free buffer before sleep",
        "start_time": "2024-01-16T21:00:00",
        "end_time": "2024-01-16T21:30:00",
        "category": "Sleep",
        "reason": "Address late-night screen use"
      }
    ]
  }
  ```

### Step 6 — Conflict Filtering
- Filters proposed_changes that overlap existing calendar events (1-minute tolerance)
- Conflicting proposals are still returned in response but flagged — mobile UI shows them as unselectable

### Step 7 — Layer 4 Promotion
- For each Layer 4 suggestion with `start_time`:
  - Finds the next free day within 7 days
  - Builds ISO timestamp: `YYYY-MM-DDTHH:MM:SS`
  - Deduplicates by title prefix (prevents double-adding same suggestion)
  - Appends to `proposed_changes` if no conflict

---

## Pipeline Result Structure

```json
{
  "status": "completed",
  "user_id": "user@example.com",
  "journal_count": 3,
  "journal_summary": "User had reduced sleep but compensated with morning exercise.",
  "health": {
    "risk_level": "mild",
    "key_concerns": ["below-average sleep duration"],
    "positive_indicators": ["maintained physical activity"],
    "behavioral_context": "Recent sleep disruption likely due to screen use..."
  },
  "recommendations": [
    {
      "category": "Sleep",
      "action": "Set device quiet hours 22:00–07:00",
      "when_to_do": "Tonight",
      "priority": "high"
    }
  ],
  "proposed_changes": [
    {
      "action": "add",
      "title": "Evening Wind-Down",
      "description": "...",
      "start_time": "2024-01-16T21:00:00",
      "end_time": "2024-01-16T21:30:00",
      "category": "Sleep",
      "reason": "..."
    }
  ],
  "calendar_summary": { "event_count": 3, "total_hours": 2.5, ... },
  "behavioral_sensing": {
    "prose": "Sleep disruption detected...",
    "llm_analysis": { "coherent_patterns": [], "suggestions": [] }
  },
  "errors": [],
  "duration_seconds": 3.45
}
```

---

## API Endpoints

### `POST /api/process_journals`
Run the full pipeline.

**Request:**
```json
{
  "journals": [
    {
      "id": "entry_1",
      "entry_number": 1,
      "created_at": "2024-01-15 10:00",
      "period": "Morning",
      "content": "Woke up tired. Had coffee and went for a run...",
      "timestamp": "2024-01-15 10:00"
    }
  ],
  "raw_days": [
    {
      "date": "2024-01-15",
      "sleep_onset_hour": 23.5,
      "sleep_duration_hours": 6.5,
      "sleep_regularity_index": 72.0,
      "late_night_screen_min": 60.0,
      "total_screen_min": 300.0,
      "app_switching_rate": 2.8,
      "mobility_entropy": 0.70,
      "location_revisit_ratio": 0.68,
      "social_rhythm_metric": 0.75,
      "comm_reciprocity": 0.50,
      "coverage": { "sleep_onset_hour": 1.0, "sleep_duration_hours": 1.0 }
    }
  ],
  "user_id": "user@example.com"
}
```

**Response:** Full pipeline result (see above).

---

### `POST /api/apply_calendar`
Apply user-selected proposals to Google Calendar.

**Request:**
```json
{
  "changes": [
    {
      "action": "add",
      "title": "Evening Wind-Down",
      "description": "Phone-free buffer before sleep",
      "start_time": "2024-01-16T21:00:00",
      "end_time": "2024-01-16T21:30:00"
    }
  ],
  "user_comments": "Great suggestion",
  "user_id": "user@example.com"
}
```

**Response:**
```json
{
  "applied": [{ "action": "created", "title": "Evening Wind-Down", "event_id": "google_event_123" }],
  "failed": [],
  "skipped": []
}
```

**Behavior:** Temporarily lifts `suggest_only` mode (thread-safe lock), creates/updates/deletes events in the "RIDE Agent" Google Calendar, records feedback.

---

### `GET /api/memory?user_id=...`
Retrieve personalization state for a user.

**Response:**
```json
{
  "preferences": {
    "work_hours": [9, 17],
    "max_daily_hours": 8.0,
    "goals": ["improve sleep", "reduce stress"],
    "preferred_interventions": ["yoga", "meditation"]
  },
  "wellbeing": {
    "risk_level": "mild",
    "trend": "stable",
    "history": [{ "timestamp": "2024-01-15", "risk_level": "mild" }]
  }
}
```

---

### `GET /health`
Railway health check. Returns `{"status": "ok"}`.

---

## Configuration Defaults

| Key | Value |
|-----|-------|
| LLM model | `gemini-3-flash-preview` |
| Embedding model | `gemini-embedding-2-preview` |
| Embedding dimensions | 3072 |
| VectorDB collection | `wellness_papers_gemini` |
| Calendar timezone | Required `user_timezone` request field |
| Work hours | 9:00 – 17:00 |
| Max daily hours | 8.0 |
| Calendar look-ahead | 7 days |
| VectorDB top-K | 5 |
| Feedback history window | 10 entries |
| LLM temperature | 0.7 |
| LLM max tokens | 8192 |
