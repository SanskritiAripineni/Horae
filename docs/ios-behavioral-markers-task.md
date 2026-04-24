# Task: Implement iOS behavioral marker aggregation

## Problem

The wellbeing pipeline (Layer 1–4 in `wellbeing_pipeline/`) relies on `raw_days` — a list of daily behavioral markers — sent from the mobile client. On Android these are fully derived; on iOS they're mostly stubs, so iOS users get graceful degradation (no behavioral sensing, just journal + calendar + VectorDB).

## Reference implementation (Android, fully working)

`autolife_android_client/composeApp/src/androidMain/kotlin/com/autolife/composeapp/platform/BehavioralMarkerAggregator.kt`

Derives all 10 markers from SQLDelight sensor logs + Android OS APIs:
- **Phase 1** (from `ContextLog` table): `mobility_entropy`, `location_revisit_ratio`, `social_rhythm_metric`
- **Phase 2** (from `SLEEP_STATE` events): `sleep_onset_hour`, `sleep_duration_hours`, `sleep_regularity_index`
- **Phase 3** (from `UsageStatsManager`): `total_screen_min`, `late_night_screen_min`, `app_switching_rate`
- **Phase 4** (from SMS/call logs): `comm_reciprocity`

Each marker is serialized into a `RawDayMarkers` record with a `coverage` map indicating which markers are reliable for that day.

## What needs to happen on iOS

File to fix: `autolife_android_client/composeApp/src/iosMain/kotlin/com/autolife/composeapp/platform/PlatformActuals.ios.kt` (lines ~74–161).

Currently returns only mobility markers. Need to add:
- **Sleep** — use HealthKit (`HKCategoryTypeIdentifierSleepAnalysis`). Requires adding HealthKit entitlement and `NSHealthShareUsageDescription` to `iosApp/iosApp/Info.plist`.
- **Screen time** — iOS doesn't expose per-app usage like Android's `UsageStatsManager`. Options: (a) use `FamilyControls` + `DeviceActivity` frameworks (requires user authorization, iOS 15+), or (b) leave these markers absent and set `coverage["total_screen_min"] = 0` so Layer 1 ignores them. Pragmatic default: option (b), document the gap.
- **Comm reciprocity** — iOS does **not** let third-party apps read SMS/call logs. Set `coverage["comm_reciprocity"] = 0` and skip.

## Schema (what backend expects)

See `api.py` → `RawDayMarkers` Pydantic model. Marker keys must match Layer 1's `MARKER_SPECS` in `wellbeing_pipeline/layer1.py`. Missing markers should be absent from the dict, AND their `coverage` value should be 0, so Layer 1 short-circuits cleanly.

## Data entry point

`AgentScreen.kt` (commonMain) calls `getBehavioralMarkers(14)` which dispatches through `expect`/`actual`. The iOS `actual` is in `PlatformActuals.ios.kt`. Android's version reads SQLDelight; iOS should do the same for mobility/social (already does) and add HealthKit + optional DeviceActivity for the rest.

## Verification

1. `./gradlew :composeApp:compileKotlinIosSimulatorArm64` — must compile.
2. Build and run in Xcode, trigger analysis from iOS simulator, confirm `/api/process_journals` receives `raw_days` with sleep markers populated (check backend logs or add a breakpoint in `agent.run_from_journals()`).
3. Backend log should show "WellbeingSensor analyzing N days" instead of "No raw_days provided — proceeding without behavioral sensing".

## Out of scope

Don't refactor the Android aggregator. Don't touch Layer 1–4 on the backend — they're working. Just bring iOS marker coverage closer to parity, accepting that comm + detailed screen-time aren't achievable on iOS without major UX tradeoffs.
