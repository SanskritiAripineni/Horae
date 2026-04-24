# AutoLife / Multi-Agent-LLM

Life-logging app: smartphone sensors + Gemini AI → contextual journals + calendar optimization for mental wellness. Research project, ~100-user study, SHA-256 hashed IDs.

## Two components

1. **Python backend** (repo root) — FastAPI. Pipeline: journals → behavioral sensing (Layer 1–4) → VectorDB retrieval → LLM schedule proposals. Single entry point: `agent.run_from_journals()`.
2. **KMP/CMP mobile client** (`autolife_android_client/`) — Kotlin Multiplatform targeting Android + iOS. Modules: `:shared` (business logic), `:composeApp` (shared UI), `:androidApp` (Android host), `iosApp/` (SwiftUI wrapper).

## Backend pipeline

```
POST /api/process_journals (journals + raw_days)
  → AutoLifeReader                    # narrative context
  → CalendarAPI                       # Google Calendar OAuth, 7-day window
  → WellbeingSensor (raw_days)        # Layer 1–4; skipped if raw_days absent
  → VectorDBClient                    # ChromaDB intervention retrieval
  → LLMClient                         # ONE structured-prompt Gemini call
```

`raw_days` are behavioral markers (sleep_duration_hours, app_switching_rate, mobility_entropy, etc.) derived client-side from sensor logs and sent with the API request. Android derives all 10 markers in `BehavioralMarkerAggregator.kt`. **iOS currently only derives mobility markers** — sleep/screen/comm are stubs in `PlatformActuals.ios.kt`.

## Endpoints

- `POST /api/process_journals` — full pipeline
- `POST /api/apply_calendar` — apply confirmed changes (suggest-only by default)
- `GET /api/memory?user_id=` — user prefs + wellbeing history
- `GET /health`

## Env vars

**Python** (`.env` or Railway): `GEMINI_API_KEY` (required), `MAPS_API_KEY`, `DATABASE_URL`, `GOOGLE_CREDENTIALS_JSON`, `CALENDAR_TOKEN_B64`.
**Android** (`local.properties`, gitignored): `GEMINI_API_KEY`, `MAPS_API_KEY`, optional `BACKEND_URL` (default `http://10.0.2.2:8000` for emulator).

Never commit: `.env`, `local.properties`, `credentials.json`, `data/tokens/*.json`.

## Deployment

Backend → Railway at `ride-backend-production-a1fc.up.railway.app`. `railway up --detach` to deploy. Persistent volume at `/app/data` holds user memory + OAuth refresh tokens. Metabase runs as a separate Railway service. Slash commands: `/deploy`, `/run-backend`, `/test-backend`, `/build-android`, `/verify-both`, `/status`.

## Git

Main: `main`. Active work: `ride-app`. Conventional commits.

## Live gotchas

- **Package name is `com.google.mediapipe.examples.llminference`** (legacy from MediaPipe template). Don't rename without coordination.
- **Gradle module is `:androidApp`, not `:app`.**
- **`google-genai`, not `google-generativeai`** — the old SDK bundles Ktor 2.x and conflicts with KMP's Ktor 3.x.
- **commonMain restrictions**: no `String.format()` (use `DateFormat.fmtFloat1/2/3`), no Room, no `testTagsAsResourceId`.
- **KMP → Swift**: `ByteArray` exports as `KotlinByteArray`; `suspend` becomes `async throws`.
- **Cleartext HTTP** scoped to `10.0.2.2`/`localhost`/`127.0.0.1` in `network_security_config.xml`.
- **Deep link**: `autolife://run_analysis` triggers analysis externally.

## How to work here

- Cross-platform mindset: touching `:shared` or `:composeApp` means checking both Android + iOS. `expect`/`actual` pairs especially.
- Lean on builds: `./gradlew :androidApp:assembleDebug`, `:composeApp:compileKotlinIosSimulatorArm64`, `python -c "from api import app"`.
- Execute with confidence — don't ask permission for every step. Use task lists for complex work.
- Available MCP: `android-mcp`, `xcode`, `xcodebuild`, Google Calendar, Gmail, Excalidraw.
