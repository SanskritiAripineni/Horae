# Battery Impact Assessment for IRB

## Purpose

This document describes a simple, quick battery impact assessment for the AutoLife mobile app. The goal is not to produce a formal power engineering benchmark, but to provide a reasonable estimate of participant burden from background sensing and periodic journaling features for IRB reporting.

## Summary

The app uses location, motion/activity recognition, Wi-Fi context, and periodic analysis/journaling. These features may affect battery life. A lightweight device-level assessment can be performed on one Android phone and one iPhone using a short standardized workflow.

The app now includes an in-app `Battery Assessment` workflow in the developer dashboard that:

- Reads current battery percentage from the device
- Starts a `baseline` or `active` battery test run
- Stops the run and computes battery drop and estimated drain per hour
- Compares baseline and active runs
- Exports a short markdown battery report for study records

This is the recommended workflow for the IRB submission because it standardizes data capture and interpretation.

## Quick Test Design

### Devices

- 1 physical Android device
- 1 physical iPhone

Do not use emulators or simulators for battery assessment.

### Test Conditions

Use the following setup for each device:

- Battery charged to at least 80% before each run
- Same screen brightness setting across runs, preferably around 50%
- Same network condition across runs, preferably stable Wi-Fi
- No active charging during the test
- Low Power Mode/Battery Saver turned off
- Background apps closed as much as practical before starting

### App States to Compare

Run the following two conditions on each device:

1. Baseline condition
- App installed but not actively collecting data
- App opened, then left idle with background collection off

2. Active condition
- App opened with normal data collection enabled
- Leave the app running in its intended real-use state for the duration of the test

### Duration

- Recommended minimum: 30 minutes per condition
- Preferred if time allows: 60 minutes per condition

This is intentionally short for IRB burden estimation and is sufficient for a practical statement about whether battery impact appears minimal, modest, or notable.

## In-App Procedure

For each device:

1. Charge the device to at least 80%.
2. Open the app and go to the developer dashboard.
3. In the `Battery Assessment` section, tap `Refresh` to capture the current battery percentage.
4. Enter a brief note describing the condition, such as `baseline, screen off, Wi-Fi on` or `active collection, service on, screen off`.
5. For the baseline condition, make sure collection is off, then tap `Start Baseline`.
6. Leave the phone untouched for 30 to 60 minutes.
7. Return to the app and tap `Stop Run`.
8. For the active condition, enable the app's normal collection behavior, then tap `Start Active`.
9. Leave the phone in the intended study-use state for 30 to 60 minutes.
10. Return to the app and tap `Stop Run`.
11. Tap `Export Report` to save the generated battery assessment summary.

The app stores completed runs using the existing local log database and computes:

- Battery percentage drop
- Test duration in minutes
- Estimated battery drain per hour
- A simple interpretation comparing baseline and active use

## Manual Fallback Procedure

For each device:

1. Charge the device to at least 80%.
2. Record the starting battery percentage and time.
3. Run the baseline condition for 30 to 60 minutes.
4. Record the ending battery percentage and calculate percent drop.
5. Recharge if needed back to approximately the same starting level.
6. Record the starting battery percentage and time for the active condition.
7. Run the app with normal collection enabled for 30 to 60 minutes.
8. Record the ending battery percentage and calculate percent drop.
9. Compare the baseline and active battery drops.

## Data to Record

The in-app report captures most of the following automatically. If you need a manual worksheet, record:

- Device model
- Operating system version
- Test date
- Test duration in minutes
- Starting battery percentage
- Ending battery percentage
- Battery percentage drop
- Whether the screen was mostly on or mostly off
- Whether the app was in foreground or background during most of the run
- Any unusual events such as poor network, phone calls, navigation, or other heavy app use

## Simple Interpretation

The app classifies battery burden using a simple IRB-oriented interpretation:

- Minimal impact: active drain is within about 2 percentage points per hour of baseline
- Modest impact: active drain is about 2 to 5 percentage points per hour above baseline
- Notable impact: active drain is more than about 5 percentage points per hour above baseline

Because battery percentage is coarse and phone usage varies, the result should be described as an informal device-level assessment rather than a precise estimate of power consumption.

If only one run has been completed, the app falls back to an absolute interpretation:

- Minimal: about 4% per hour or less
- Modest: about 4% to 8% per hour
- Notable: more than about 8% per hour

This fallback is helpful during pilot testing, but the IRB statement should ideally rely on both a baseline and an active run.

## Suggested IRB Wording

Battery impact was assessed informally on physical Android and iOS devices using a short standardized device-level test embedded in the study app. Battery percentage decline was compared between an idle baseline condition and an active app condition over approximately 30 to 60 minutes. This assessment was used to estimate participant burden associated with background sensing and periodic journaling. The test was intended as a practical screening measure rather than a formal laboratory power benchmark.

## Suggested Participant Risk/ Burden Wording

Use of the app may result in some additional battery consumption because it collects contextual signals such as motion and location data. The study team performed a brief device-level battery assessment on Android and iOS to estimate this burden. Based on this assessment, battery impact is expected to be limited to routine smartphone use, though actual battery consumption may vary by device model, operating system version, connectivity, and usage patterns.

## Results Template

Complete the following after running one Android device and one iPhone:

- Android baseline: `___%/hr`
- Android active: `___%/hr`
- Android interpretation: `minimal / modest / notable`
- iPhone baseline: `___%/hr`
- iPhone active: `___%/hr`
- iPhone interpretation: `minimal / modest / notable`

Suggested one-line result sentence:

In a brief battery check on one Android device and one iPhone, the active app condition showed a `minimal / modest / notable` increase in battery use relative to baseline over a 30 to 60 minute period, suggesting `low / acceptable / potentially meaningful` added participant burden under typical use.

## Current Engineering Interpretation

Based on the app architecture, the most likely battery-impact contributors are:

- Frequent location polling
- Continuous motion/activity sensing
- Wi-Fi context collection
- Periodic AI and network requests

Before empirical testing, the safest expectation is that battery impact will be in the `modest` range rather than negligible, especially during active collection. The IRB should therefore avoid claiming minimal battery impact until the Android and iPhone runs have been completed and exported from the app.

## Important Limitations

- Battery percentage is a rough measure and varies by device
- Results from one Android device and one iPhone are not universally generalizable
- Real-world battery impact may differ based on motion, travel, signal strength, and time spent in background operation
- iOS and Android manage background work differently, so platform-specific behavior may vary

## Recommendation

For a simple IRB submission, use:

- 1 Android run: baseline and active
- 1 iPhone run: baseline and active
- 30 minutes each if time is tight

This is usually enough to support a brief statement about expected battery burden without overengineering the process. After those four runs are complete, use the exported in-app report to fill the results template above and finalize the IRB language.
