# GitHub Issue Resolution - 2026-05-20

This pass addresses the actionable app hardening issues filed from the iOS, Android, backend, and RAG review.

## Resolved Issues

- #12: Google Calendar private events are skipped before events are returned to agent context.
- #13: OAuth status and token endpoints now require API authentication.
- #14: API authentication fails closed when `API_SECRET_KEY` is not configured.
- #15: Consent and privacy copy no longer claims fully on-device AI behavior while Gemini/server processing can occur.
- #16: Calendar token storage no longer uses raw user IDs in paths and no longer persists `client_secret` in token files.
- #17: Android exports are written to app-private storage instead of public Downloads.
- #18: iOS no longer declares or requests background/Always location when collection is foreground/on-demand only.
- #19: Android analysis database work is dispatched off the main thread.
- #20: Android collection state is initialized pessimistically and updated from service start/stop outcomes.
- #21: The iOS KMP framework build script selects simulator/device targets by architecture and builds successfully from Xcode.
- #22: iOS HealthKit sleep reads are capped and the unused clinical-records entitlement was removed.
- #23: Android Wi-Fi `forceRefresh` now attempts a scan refresh and waits for the scan broadcast before reading results.
- #24: Android foreground-service restart behavior is guarded for Android 14+ and uses a non-sticky restart policy.
- #25: Embedded AI keys fail closed when placeholders or blank values are present.
- #26: Android Compose controls and navigation now expose stable accessibility labels/test tags.
- #27: The RAG app uses a deterministic Chroma directory next to `vectordb/app.py` and honors the configured collection name.
- #28: Deprecated Android Gradle plugin flags were removed and KMP modules were migrated to the AGP 9 KMP library DSL.
- #29: The failing Python tests were updated with the corrected feedback/tool behavior and new auth expectations.

## Verification

- `pytest -q`: 182 passed.
- `python3 -m py_compile api.py tools/calendar_api.py vectordb/app.py`: passed.
- `./gradlew :composeApp:allTests :shared:compileKotlinIosSimulatorArm64 :composeApp:compileKotlinIosSimulatorArm64 --console=plain`: passed.
- `./gradlew :androidApp:compileDebugKotlin :composeApp:compileAndroidMain :shared:compileAndroidMain --console=plain`: passed.
- `./gradlew :androidApp:assembleDebug :androidApp:testDebugUnitTest --console=plain`: passed.
- XcodeBuildMCP `build_run_sim` for `AutoLife` on iPhone 17: passed with no diagnostics.
- iOS simulator UI snapshot after location reset shows the standard When In Use location prompt, not the old Always/background prompt.
- Android emulator `Pixel_9` install and launch succeeded; cold-start after `pm clear` opens the consent flow, and an existing collecting state was confirmed against a real running foreground service.

## Notes

Direct GitHub issue comments/closure could not be performed from this session because the GitHub connector write tools were not exposed and the `gh` CLI is not installed locally. This document is intended to be committed or referenced from the eventual PR so the issue trail has a durable resolution record.
