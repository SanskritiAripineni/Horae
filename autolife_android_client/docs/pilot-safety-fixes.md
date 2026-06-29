# Pilot Safety Fixes

Branch: `codex/bug-issue-fixes`

Base branch: `origin/ride-app`

## Issue #39: Android lint build gate

What changed:

- Added a direct `androidx.fragment:fragment:1.3.6` dependency in `androidApp` so Activity Result APIs are not paired with the old transitive Fragment `1.1.0`.
- Added the Android `tools` namespace in `AndroidManifest.xml`.
- Suppressed `ProtectedPermissions` only on `PACKAGE_USAGE_STATS`, which is a deliberate special-access permission for usage stats.

Verification:

```bash
ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew :androidApp:lintDebug --console=plain
ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew :androidApp:assembleDebug --console=plain
ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew :androidApp:testDebugUnitTest --console=plain
ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew :androidApp:check --console=plain
```

## Issue #42: Calendar writes require confirmation

What changed:

- Added `CalendarWriteConfirmationDialog`.
- Schedule tab now opens the dialog before applying selected proposals or all clear proposals.
- Agent tab now opens the same dialog before applying all proposed changes.
- Calendar writes still use the existing `ProposalApplier`; the change is an explicit user confirmation step before calling it.

Expected reviewer behavior:

- Clicking an apply button shows a confirmation dialog.
- Clicking `Cancel` makes no calendar API call.
- Clicking `Confirm & Apply` proceeds with the existing calendar apply request.

Verification:

- Covered by Android compile, lint, unit test, and debug assembly.
- Covered by iOS Kotlin compilation and arm64 simulator Xcode build.

## Issue #41: iOS decline is no longer a no-op

What changed:

- `AutoLifeApp` now tracks a declined consent state and shows a `NotEnrolledScreen`.
- iOS `MainViewController` now wires `onDecline` to stop background service collection.
- Android still exits through `finishAffinity()`, preserving existing behavior.

Expected reviewer behavior:

- Tapping `Exit Without Joining` no longer leaves the user in an ambiguous consent state.
- The app shows that the user is not enrolled and says no study collection was started.

Verification:

```bash
ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew :composeApp:compileKotlinIosSimulatorArm64 --console=plain
xcodebuild -project iosApp/AutoLife.xcodeproj -scheme AutoLife -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' ARCHS=arm64 ONLY_ACTIVE_ARCH=YES build
```

Note: Xcode needs a local ignored `iosApp/AutoLife/Secrets.xcconfig`. For local verification this was created from `Secrets.xcconfig.template` with empty keys and was not committed.

## Issue #40: Permission denial behavior matches consent copy more closely

What changed:

- Android runtime permissions are split into required and optional groups.
- Required: location and activity recognition on Android versions that require activity recognition runtime permission.
- Optional: notifications and nearby Wi-Fi devices on Android 13+.
- Denying optional permissions no longer marks background collection as stopped.
- Denying required permissions blocks collection and shows a clear message.
- iOS no longer marks collection active before location authorization is granted.

Verification target:

- Denying optional Android permissions should show limited coverage while collection can continue.
- Denying required Android permissions should prevent collection.
- iOS should remain paused while waiting for location authorization.

Verification:

- Added `PermissionPolicyTest` for required-vs-optional Android permission grouping.
- `:androidApp:testDebugUnitTest` passes.
- `:androidApp:lintDebug` and `:androidApp:assembleDebug` pass.
- `:composeApp:compileKotlinIosSimulatorArm64` and the arm64 simulator Xcode build pass.

## Read for Review

This branch keeps the current app code isolated from `ride-app` and `main`. The fixes are intentionally small: calendar writes now require a confirmation dialog, consent decline now has a clear not-enrolled path, Android permissions are split into required and optional categories, iOS no longer reports collection as active before location authorization, and Android lint/build gates pass. The local ignored `Secrets.xcconfig` and unrelated untracked data files should not be committed.
