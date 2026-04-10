Run a full end-to-end test on the connected Android device using android-mcp.

Steps:
1. List connected devices and confirm one is available
2. Check if AutoLife is installed (package: com.google.mediapipe.examples.llminference)
3. Start the app
4. Take a screenshot to see current state
5. Navigate through each tab (Agent, Health, Schedule, Journal, Memory) using the bottom nav
6. Take a screenshot on each tab
7. Try triggering an analysis via deep link: `adb shell am start -a android.intent.action.VIEW -d "autolife://run_analysis"`
8. Wait 5 seconds, take a final screenshot
9. Report what you observed on each screen — any crashes, empty states, or errors
