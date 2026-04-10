#!/bin/bash
# Stop hook: when Claude finishes a task, inject a reminder to verify builds
cat <<'JSON'
{
  "systemMessage": "Before finishing: if you edited Kotlin files in :shared or :composeApp, verify BOTH Android (./gradlew :androidApp:assembleDebug) and iOS (./gradlew :composeApp:compileKotlinIosSimulatorArm64) still compile. If you edited Python backend files, verify the API still starts (python -c 'from api import app'). Don't skip this — cross-platform parity is critical."
}
JSON
