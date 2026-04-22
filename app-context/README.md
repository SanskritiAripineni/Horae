# AutoLife — App Context for AI Agents

This folder provides thorough documentation of the AutoLife app for AI agents that need to understand the system from screenshots or other context.

## Files

| File | What it covers |
|------|---------------|
| [overview.md](overview.md) | What the app is, who uses it, end-to-end user flow, key vocabulary |
| [mobile-ui.md](mobile-ui.md) | All 5 screens in detail — what each element is, what it does |
| [backend-pipeline.md](backend-pipeline.md) | Multi-agent pipeline steps, all API endpoints with request/response shapes |
| [data-models.md](data-models.md) | Every data structure with field-level annotations |
| [architecture.md](architecture.md) | Tech stack, deployment, module layout, known gotchas |

## Quick Summary

AutoLife is a **mental wellness + life-logging research app**. It passively collects smartphone sensor data (motion, sleep, screen time, location, app usage), fuses it with user journal entries, and sends everything to a **Gemini-powered multi-agent backend**. The backend produces:

- A **risk level** (minimal / mild / moderate / severe)
- **Recommendations** backed by wellness research papers (ChromaDB / RAG)
- **Proposed calendar events** to help build healthier habits

The user reviews proposals in the **Schedule tab**, selects which to apply, and the backend writes them to **Google Calendar**. Feedback (accept/reject) personalizes future cycles.

The mobile client is **Kotlin Multiplatform + Compose Multiplatform** (Android + iOS). The backend is **FastAPI on Railway**.
