# AutoLife / Multi-Agent-LLM

## What This Project Is

AutoLife is a life-logging app that uses smartphone sensors (motion, location, WiFi) with Gemini AI to generate contextual life journals and optimize calendar scheduling for mental wellness. It has two major components:

1. **Python backend** — FastAPI server that runs a multi-agent pipeline: journal analysis → wellbeing assessment (risk_level + behavioral sensing) → VectorDB research retrieval → calendar optimization
2. **KMP/CMP mobile client** — Kotlin Multiplatform + Compose Multiplatform app targeting Android and iOS, handling sensor collection, journaling, and displaying agent results

## Repository Structure

```
Multi-Agent-LLM/
├── api.py                  # FastAPI server (entry point for backend)
├── agent.py                # LLMSchedulerAgent — the "conductor" orchestrator
├── config.py               # Centralized config with env var support
├── db.py                   # Postgres logging (anonymized via SHA-256)
├── main.py                 # CLI interactive entry point
├── test_api.py             # Smoke test for the API
├── Dockerfile              # Python 3.11-slim container
├── railway.toml            # Railway deployment config
├── startup.sh              # Container entrypoint (injects secrets from env)
├── requirements.txt        # Python dependencies
├── tools/                  # Agent tool modules
│   ├── autolife_reader.py  # Parses journal entries
│   ├── llm_client.py       # Gemini API wrapper (google.genai)
│   ├── vectordb_client.py  # ChromaDB wellness paper retrieval
│   ├── calendar_api.py     # Google Calendar + Tasks OAuth integration
│   ├── wellbeing_sensor.py # Three-layer behavioral sensing pipeline
│   ├── autolife_phone_adapter.py  # Derives sensor markers from journals
│   └── wellbeing_feedback.py  # Records suggestion accept/reject feedback
├── wellbeing_pipeline/     # Layer 1–4 baselines, deviations, coherence, LLM synthesis
├── memory/                 # Python memory module (preferences, wellbeing tracking)
│   ├── storage.py          # File-based storage
│   ├── user_preferences.py # User preference management
│   └── wellbeing_tracker.py
├── vectordb/               # ChromaDB data + ingestion scripts
│   ├── chroma_db/          # Pre-built collection (committed for Docker)
│   ├── research_papers/    # Source PDFs
│   ├── app.py              # Streamlit viewer
│   └── ingest_*.py         # Ingestion scripts
├── data/                   # Runtime data (logs, tokens, models)
├── apps/
│   └── mindful-rag/        # Evaluation framework for RAG quality
├── docs/                   # Architecture diagrams, research paper
└── autolife_android_client/  # KMP/CMP mobile project
    ├── androidApp/         # Android host (sensors, service, DevDashboard)
    ├── composeApp/         # CMP shared UI (5 screens, design system)
    ├── shared/             # KMP shared business logic
    ├── iosApp/             # iOS host (SwiftUI wrapper, 6 platform services)
    ├── build.gradle.kts    # Root build file
    ├── settings.gradle.kts # Modules: :androidApp, :shared, :composeApp
    └── gradle/libs.versions.toml  # Version catalog
```

## Architecture

### Backend Pipeline (agent.py)

```
Android journals → POST /api/process_journals
  → AutoLifeReader.get_context_for_prompt()
  → LLMClient.analyze_wellbeing()             # Gemini → risk_level + concerns
  → AutoLifePhoneAdapter.journals_to_raw_days() + WellbeingSensor.analyze()
                                               # Layer 1–4 behavioral sensing
  → LLMClient.synthesize_wellbeing()          # fuse journal + sensor signals
  → CalendarAPI.get_schedule_summary()         # Google Calendar OAuth
  → VectorDBClient.get_intervention_suggestions(risk_level)  # ChromaDB retrieval
  → LLMClient.generate_recommendations()
  → LLMClient.generate_calendar_changes()     # with conflict filtering
  → Response with proposed_changes
```

### Mobile Architecture (KMP/CMP)

- **`:shared`** (commonMain) — `AutoLifeApi`, `DatabaseRepository`, `AnalysisRepository`, `AiClient`, `GeminiAiClient`, `MotionClassifier`, `PromptBuilder`, models
- **`:composeApp`** (commonMain) — Unified UI: `AutoLifeNavHost` with 5-tab bottom bar (Agent, Health, Schedule, Journal, Memory) + DevDashboard. iOS-inspired design system in `ui/theme/`
- **`:androidApp`** — `AutoLifeService` (background sensor collection), `MotionDetector`, `WifiScanner`, `LocationAnalyzer`, `JournalGenerator`, `ContextFusionAnalyzer`, `GeminiClient`, Room DB via `:shared`
- **`iosApp/`** — SwiftUI wrapper embedding CMP via `UIViewControllerRepresentable`. Platform services: `IOSSensorServiceManager`, `IOSLocationProvider`, `IOSMotionSensorProvider`, `IOSWifiNetworkProvider`, `IOSMapImageFetcher`, `IOSDataExporter`

Package name: `com.google.mediapipe.examples.llminference` (legacy, predates rename)

## Key Versions & Dependencies

### Python
- Python 3.11 (Docker), 3.9+ (local)
- FastAPI + Uvicorn (API)
- google-genai (Gemini API — NOT google-generativeai)
- ChromaDB (vector store), gemini-embedding-2-preview (embeddings)
- psycopg2 (Postgres), google-api-python-client (Calendar OAuth)
- LLM model: `gemini-3-flash-preview`

### Android/KMP
- Kotlin 2.2.20, AGP 9.1.0, Gradle (wrapper in repo)
- Compose Multiplatform 1.10.3, Navigation 2.9.2, Lifecycle 2.10.0
- Room 2.7.0 (Android), SQLDelight 2.0.2 (KMP shared)
- Ktor 3.0.3 (networking), kotlinx-serialization 1.7.3
- Google Generative AI SDK 0.9.0 (on-device Android)
- KSP 2.3.2 (annotation processing)
- compileSdk/targetSdk = 35, minSdk = 24, Java 17

## Environment Variables & Secrets

### Python backend (.env or Railway env)
- `GEMINI_API_KEY` — Gemini API key (required)
- `MAPS_API_KEY` — Google Static Maps (optional)
- `DATABASE_URL` — Postgres connection string (optional; DB logging no-ops if unset)
- `GOOGLE_CREDENTIALS_JSON` — Google OAuth service account JSON (injected at container start)
- `CALENDAR_TOKEN_B64` — Base64-encoded calendar OAuth token (injected at container start)

### Android (local.properties — gitignored)
```properties
GEMINI_API_KEY=...
MAPS_API_KEY=...
# Optional: override for physical device testing (default: http://10.0.2.2:8000 for emulator)
BACKEND_URL=http://192.168.x.x:8000
```

**Never commit:** `.env`, `local.properties`, `credentials.json`, `data/tokens/*.json`

## Build & Run Commands

### Python backend
```bash
# Local development
pip install -r requirements.txt
python api.py                          # Starts FastAPI on :8000
python main.py                         # Interactive CLI mode
python main.py --quick --json          # Non-interactive JSON output
python test_api.py                     # Smoke test (starts server, sends payload, asserts)

# Docker
docker build -t autolife-backend .
docker run -p 8000:8000 --env-file .env autolife-backend
```

### Android
```bash
cd autolife_android_client
./gradlew :androidApp:assembleDebug                 # Build debug APK
./gradlew :androidApp:assembleDebug --stacktrace    # Build with full stack trace
./gradlew clean :androidApp:assembleDebug           # Clean build
./gradlew :composeApp:compileDebugKotlinAndroid     # Compile CMP only
```
Open `autolife_android_client/` in Android Studio for full IDE support. Target `:androidApp`, NOT `:app`.

### iOS
```bash
cd autolife_android_client
./gradlew :composeApp:compileKotlinIosSimulatorArm64        # Compile CMP for iOS sim
./gradlew :composeApp:linkDebugFrameworkIosSimulatorArm64   # Link iOS framework
```
Then open `autolife_android_client/iosApp/AutoLife.xcodeproj` in Xcode. The CMP framework (`ComposeApp.framework`, static) is built via Gradle and embedded in the Xcode project.

### Emulator Networking
```bash
adb reverse tcp:8000 tcp:8000    # Forward emulator port to host for local backend
```
- Android emulator: use `10.0.2.2` to reach host machine
- iOS simulator: use `localhost` directly

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/process_journals` | Process journal entries through the full pipeline |
| POST | `/api/apply_calendar` | Apply confirmed calendar changes |
| GET | `/api/memory?user_id=` | Get user preferences and mental health history |
| GET | `/health` | Health check (Railway uses this) |

## Deployment

- **Backend:** Deployed on Railway at `ride-backend-production-a1fc.up.railway.app`
- **Health check:** `/health` endpoint, 300s timeout
- **Restart policy:** ON_FAILURE, max 3 retries
- **Secrets injection:** `startup.sh` creates `credentials.json` and `data/tokens/calendar_token.json` from env vars at container startup
- **Persistent volume:** `/app/data` on Railway — stores user memory and OAuth refresh tokens across deploys
- **Postgres:** Railway-managed, auto-injected via `DATABASE_URL`
- **Metabase:** Researcher analytics dashboard on Railway (separate service)
- **Deploy command:** `railway up --detach`
- **Verify:** `curl https://ride-backend-production-a1fc.up.railway.app/health`

## Git Workflow

- **Main branch:** `main`
- **Current work branch:** `ride-app`
- **Remote:** `origin` → `https://github.com/SanskritiAripineni/Multi-Agent-LLM.git`
- **Historical branches:** `autolife_rishi` (original Android app), `framework_rishi` (agent framework), `Formatted_VectorDB`
- **Commit style:** Conventional commits (`feat:`, `fix:`, `refactor:`, `chore:`, `docs:`)

## Known Gotchas

1. **KSP + Room:** Room 2.7.0 is required to avoid `unexpected jvm signature V` crash with KSP 2.3.2. Do not downgrade Room. Use `fallbackToDestructiveMigration(dropAllTables = true)` (not the no-arg version).
2. **AGP 9.1.0 + Ktor:** Ktor transitive deps from `:shared` are NOT propagated by AGP 9.1.0 — `:androidApp` must declare them explicitly.
3. **Emulator vs physical device:** Default `BACKEND_URL` is `http://10.0.2.2:8000` (Android emulator loopback). Physical devices need the host's LAN IP in `local.properties`. iOS simulator uses `localhost` directly.
4. **google-genai vs google-generativeai:** The Python backend uses the newer `google-genai` package (`from google import genai`), NOT the older `google-generativeai`. The `google-generativeai` SDK bundles Ktor 2.x and conflicts with Ktor 3.x used by KMP — use direct REST calls via Ktor instead.
5. **ChromaDB collection data** is committed to git so it's baked into the Docker image — this is intentional.
6. **Package name mismatch:** Android package is still `com.google.mediapipe.examples.llminference` from the original MediaPipe template. Don't rename without a coordinated migration.
7. **DB graceful degradation:** If `DATABASE_URL` is unset or Postgres is unreachable, all db.py functions no-op silently. The API still works.
8. **Calendar suggest_only mode:** The agent runs in suggest-only mode by default. `apply_calendar_changes` temporarily switches to write mode with a thread lock.
9. **`:app` vs `:androidApp`:** Gradle module was renamed from `app/` to `androidApp/` during KMP migration. Always use `:androidApp` — `:app` will fail with "project not found."
10. **KMP ByteArray → Swift:** Kotlin `ByteArray` exports as `KotlinByteArray` in Swift. Kotlin `suspend` functions become `async throws` in Swift.
11. **`String.format()` not in commonMain:** Use custom `DateFormat.fmtFloat1/2/3` helpers instead.
12. **Railway persistent volume:** Without `/app/data` mount, user memory and OAuth refresh tokens are lost on redeploy.
13. **Cleartext HTTP:** `network_security_config.xml` scopes cleartext to `10.0.2.2`/`localhost`/`127.0.0.1` only.
14. **Deep links:** `autolife://run_analysis` triggers analysis from outside the app.
15. **Demo mode:** 2-minute journal interval (vs 15 minutes normal). Toggle in DevDashboard settings.

## Coding Conventions

- **Python:** Dataclasses for config, Pydantic for API models, logging via stdlib `logging`
- **Kotlin:** KMP expect/actual for platform abstractions, kotlinx-serialization for models, Ktor for HTTP
- **UI:** CMP with iOS-inspired design system (`AutoLifeColors`, `AutoLifeTypography`, `AutoLifeTheme`). Components in `ui/components/Components.kt` (`SurfaceCard`, `StatusPill`, `DataRow`, `MetricCard`, `EmptyState`)
- **Navigation:** `AutoLifeNavHost` with 5-tab bottom bar + `dev_dashboard` route
- **New features:** Add shared logic to `:shared`, wire UI in `:composeApp`. Platform-specific code goes in `:androidApp` or `iosApp/`
- **Platform bridging:** `PlatformStateProvider` bridges sensor data from platform to CMP UI. `IOSServiceBridge` is a Kotlin object Swift sets callbacks on.
- **Pipeline single entry point:** `agent.run_from_journals()` is the sole pipeline entry — both CLI and API delegate to it.
- **Tests:** `test_api.py` is a smoke/integration test, not unit tests. It starts a real server.

## VectorDB Re-ingestion

```bash
# Place PDFs in vectordb/research_papers/
# Update vectordb/paper_map.csv with filenames and categories
python vectordb/ingest_simple.py    # Uses gemini-embedding-2-preview, 3072-dim vectors
```

Categories: Sleep Hygiene, Stress Management, Social Connection, Physical Activity, Mindfulness

## Project Context

This is a research project — the app is the core artifact for a paper on the "LLM Scheduler RIDE" system. Planning for ~100 users with explicit consent for data collection. User IDs are SHA-256 hashed before database storage for anonymization.

## How to Work in This Repo

- **Think cross-platform.** When touching `:shared` or `:composeApp`, keep both Android and iOS in mind. Verify both compile when it makes sense — especially before wrapping up. If you change an `expect`, the `actual` on the other side probably needs attention too.
- **Lean on builds to catch mistakes.** A quick `./gradlew :androidApp:assembleDebug` or `:composeApp:compileKotlinIosSimulatorArm64` is cheap and catches a lot. For Python, `python -c "from api import app"` is a fast sanity check.
- **Avoid the known landmines.** Room/String.format()/testTagsAsResourceId don't work in `commonMain`. `google-generativeai` conflicts with Ktor 3.x in KMP modules. Python backend uses `from google import genai`, not the old SDK. These have all burned time before.
- **Execute with confidence.** When the intent is clear, just do it — don't ask permission for every step. Use task lists for complex work to stay organized.
- **Commit clean.** Conventional commits (`feat:`, `fix:`, etc.), no secrets in tracked files, no debug leftovers.
- **Use the tools available.** android-mcp and xcode MCP are there for testing UI on real devices when it'd be useful. `/verify-both` and `/status` are there for quick checks.

## MCP Servers Available

- `android-mcp` — ADB interaction with connected Android devices (screenshots, taps, UI dumps, app lifecycle)
- `xcode` — Xcode project operations (build, test, preview, grep)
- `Excalidraw` — Diagram creation
- `Google Calendar` — Calendar operations
- `Gmail` — Email operations
