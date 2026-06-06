# AutoLife — Architecture & Tech Stack

## System Diagram

```
┌─────────────────────────────────────────────────────┐
│                  Android Device                     │
│                                                     │
│  AutoLife Service (background)                      │
│  ├── MotionDetector       → motion markers          │
│  ├── LocationAnalyzer     → location clusters       │
│  ├── WifiScanner          → WiFi context            │
│  └── UsageStatsCollector  → screen/app usage        │
│             ↓                                       │
│  JournalGenerator (Gemini on-device)                │
│  → every 15 min (2 min demo) writes journal         │
│             ↓                                       │
│  Room DB (local SQLite)                             │
│  ├── journals table                                 │
│  └── sensor_logs table                             │
│             ↓ (on "Run Analysis")                   │
│  AutoLifeApi (Ktor HTTP client)                     │
│  POST /api/process_journals                         │
└───────────────────┬─────────────────────────────────┘
                    │ HTTPS
                    ↓
┌─────────────────────────────────────────────────────┐
│             Railway Backend                         │
│             (FastAPI + Python 3.11)                 │
│                                                     │
│  api.py → agent.py::LLMSchedulerAgent               │
│                                                     │
│  ┌─ Step 1: AutoLifeReader (journal → prose) ──┐    │
│  ├─ Step 2: CalendarAPI (Google Calendar) ─────┤    │
│  ├─ Step 3: WellbeingSensor (4-layer pipeline) ┤    │
│  │   Layer 1: PersonalBaseline                 │    │
│  │   Layer 2: DeviationDetector                │    │
│  │   Layer 3: StateDescription                 │    │
│  │   Layer 4: LLM (Gemini) → suggestions       │    │
│  ├─ Step 4: VectorDBClient (ChromaDB) ─────────┤    │
│  └─ Step 5: LLMClient (Gemini orchestrator) ───┘    │
│             ↓                                       │
│  Conflict filter + Layer 4 promotion                │
│             ↓                                       │
│  db.py → Postgres (anonymized logging)              │
│  memory/ → Filesystem (user prefs + history)        │
└─────────────────────────────────────────────────────┘
                    │
                    ↓
         External Services:
         - Gemini API (google.genai)
         - Google Calendar API (OAuth 2.0)
         - ChromaDB (embedded, local to container)
         - Railway Postgres
```

---

## Backend

| Component | Technology |
|-----------|-----------|
| Web framework | FastAPI (async) |
| Runtime | Python 3.11 |
| LLM | Gemini 3 Flash Preview (`gemini-3-flash-preview`) |
| Embedding | Gemini Embedding 2 Preview (`gemini-embedding-2-preview`) |
| LLM SDK | `google-genai` (NOT `google-generativeai`) |
| Vector store | ChromaDB (embedded, collection baked into Docker image) |
| Calendar | Google Calendar API + Tasks API (OAuth 2.0) |
| Database | Railway Postgres via `psycopg2` |
| Memory | Filesystem under `data/memory/` |
| Container | Docker (Python 3.11-slim) |
| Hosting | Railway (persistent volume at `/app/data`) |

### Key Backend Files

| File | Role |
|------|------|
| `api.py` | FastAPI server, 4 endpoints |
| `agent.py` | `LLMSchedulerAgent` — orchestrates all pipeline steps |
| `config.py` | All defaults (model names, work hours, limits) |
| `db.py` | Postgres logging with SHA-256 user ID hashing |
| `tools/llm_client.py` | Gemini API wrapper with retry + JSON parsing |
| `tools/wellbeing_sensor.py` | 4-layer behavioral sensing pipeline |
| `tools/calendar_api.py` | Google Calendar OAuth integration |
| `tools/vectordb_client.py` | ChromaDB retrieval |
| `tools/autolife_reader.py` | Journal text parsing |
| `tools/autolife_phone_adapter.py` | Sensor markers → raw_days format |
| `tools/wellbeing_feedback.py` | Accept/reject feedback recording |
| `memory/user_preferences.py` | User goal/preference management |
| `memory/wellbeing_tracker.py` | Risk level history tracking |

---

## Mobile (Android / iOS)

### Kotlin Multiplatform Compose

| Layer | Module | Description |
|-------|--------|-------------|
| Shared business logic | `:shared` | API client, repositories, models, `MotionClassifier`, `PromptBuilder` |
| Shared UI | `:composeApp` | 5-tab participant IA, Dev Dashboard/testing route, design system, navigation |
| Android host | `:androidApp` | Background service, sensors, Room DB |
| iOS host | `iosApp/` | SwiftUI wrapper, native sensor providers |

### Key Mobile Files

| File | Role |
|------|------|
| `AutoLifeNavHost.kt` | Root navigation with retained 5-tab bottom bar plus visible Dev Dashboard/testing route |
| `AgentScreen.kt` | Run analysis, tool status grid |
| `HealthScreen.kt` | Wellbeing assessment display |
| `ScheduleScreen.kt` | Visual calendar + proposal selection |
| `JournalScreen.kt` | Journal list + sensor logs |
| `MemoryScreen.kt` | Personalization data view |
| `AnalysisRepository.kt` | State management (result, loading, proposals) |
| `AutoLifeApi.kt` | Ktor HTTP client to backend |
| `AutoLifeService.kt` | Android background service |
| `DatabaseRepository.kt` | SQLite CRUD for journals + logs |

### Design System
- `AutoLifeColors` — semantic color tokens
- `AutoLifeTypography` — type scale
- `AutoLifeTheme` — material theme wrapper
- Components: `SurfaceCard`, `StatusPill`, `DataRow`, `MetricCard`, `EmptyState`
- iOS-inspired visual style

### Participant-Pilot UI Runtime Contract
- The documented mobile mockups are readiness targets, not a guarantee that every screen has populated live data on first launch.
- The app must tolerate first-run storage with zero journals, zero logs, no memory history, no previous analysis result, no calendar proposals, and missing/expired calendar auth.
- The retained participant IA is five tabs: Agent, Health, Schedule, Journal, and Memory.
- Dev tools remain visible during testing through a gear/debug route for demo mode, service controls, backend URL override, and raw output inspection; this route may later evolve into Settings.
- UI state should distinguish loading, empty, partial, error, low-confidence/warmup, and ready states so sparse data is not oversold as a complete assessment.

---

## Key Versions

| Dependency | Version |
|-----------|---------|
| Kotlin | 2.2.20 |
| AGP (Android Gradle Plugin) | 9.1.0 |
| Compose Multiplatform | 1.10.3 |
| Navigation | 2.9.2 |
| Lifecycle | 2.10.0 |
| Room | 2.7.0 |
| SQLDelight | 2.0.2 |
| Ktor | 3.0.3 |
| kotlinx-serialization | 1.7.3 |
| KSP | 2.3.2 |
| Google Generative AI SDK (Android) | 0.9.0 |
| compileSdk / targetSdk | 35 |
| minSdk | 24 |
| Java | 17 |

---

## Deployment

| Resource | Details |
|---------|---------|
| Backend URL | `https://ride-backend-production-a1fc.up.railway.app` |
| Health check | `GET /health` → `{"status": "ok"}` |
| Persistent volume | `/app/data` — user memory + OAuth tokens survive deploys |
| Restart policy | ON_FAILURE, max 3 retries |
| Secrets injection | `startup.sh` writes `credentials.json` + `data/tokens/calendar_token.json` from env vars |

### Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `GEMINI_API_KEY` | Yes | Gemini API access |
| `MAPS_API_KEY` | No | Google Static Maps |
| `DATABASE_URL` | No | Postgres (logging no-ops if unset) |
| `GOOGLE_CREDENTIALS_JSON` | No | Google OAuth service account |
| `CALENDAR_TOKEN_B64` | No | Base64 OAuth token for Calendar |

### Android `local.properties`
```properties
GEMINI_API_KEY=...
MAPS_API_KEY=...
BACKEND_URL=http://10.0.2.2:8000   # emulator default; use LAN IP for physical device
```

---

## Security & Privacy

- **User ID hashing:** Backend SHA-256 hashes `user_id` before every Postgres write
- **Sensor data:** Only aggregated daily markers leave the device — raw GPS/accelerometer never sent
- **Journal content:** Gemini-synthesized narrative (not raw sensor dumps)
- **Memory:** Filesystem-based under `data/memory/`; acceptable for ~100 research users
- **Calendar:** `suggest_only=True` by default — apply endpoint requires explicit user action
- **Cleartext:** `network_security_config.xml` limits HTTP to `10.0.2.2` / `localhost` / `127.0.0.1` only
- **Participant UI privacy:** Raw location, accelerometer, and debug payloads should not appear in participant-facing screens; debug inspection is limited to the visible Dev Dashboard/testing surface during the pilot.
- **Destructive UX:** Clearing local journals/logs and applying calendar writes must use explicit confirmation and describe the affected scope before execution.

---

## Known Gotchas

1. **`google-genai` vs `google-generativeai`:** Backend uses `from google import genai` — the newer SDK. The old package conflicts with Ktor 3.x in KMP.
2. **AGP 9.1.0 + Ktor:** Ktor transitive deps from `:shared` are NOT auto-propagated — `:androidApp` must declare them explicitly.
3. **Room 2.7.0:** Required for KSP 2.3.2 compatibility. Do not downgrade.
4. **`String.format()` not in commonMain:** Use custom `DateFormat.fmtFloat1/2/3` helpers.
5. **Package name:** Still `com.google.mediapipe.examples.llminference` from original MediaPipe template — do not rename without coordinated migration.
6. **ChromaDB data:** Committed to git so it's baked into the Docker image — intentional.
7. **`:androidApp` vs `:app`:** Module was renamed; always use `:androidApp`.
8. **Emulator networking:** Use `10.0.2.2` for host on Android emulator; `localhost` for iOS simulator.
9. **Baseline warmup:** Behavioral sensing requires 10+ days of `raw_days` before deviations are reliable. `baseline_warm: false` in response indicates this.
10. **Calendar thread safety:** `apply_calendar` uses a thread lock when switching to write mode — concurrent requests queue.
