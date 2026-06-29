package com.autolife.composeapp.platform

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class BatteryAssessmentLogicTest {

    @Test
    fun startRunStoresProfileAndMetadata() {
        val deviceInfo = BatteryDeviceInfo(
            platform = "Android",
            deviceModel = "Pixel",
            osVersion = "Android 14",
            appVersion = "1.0 (1)",
        )
        val environment = BatteryRunEnvironment(
            screenIntent = BatteryScreenIntent.MOSTLY_SCREEN_OFF,
            appStateIntent = BatteryAppStateIntent.MOSTLY_BACKGROUND,
            networkSummary = "Wi-Fi, internet",
            lowPowerModeEnabled = false,
        )

        val active = BatteryAssessmentLogic.startRun(
            platform = "Android",
            profile = BatteryTestProfile.TYPICAL_BACKGROUND_USE,
            batteryPercent = 90,
            currentConfig = BatteryConfigurationSnapshot(
                serviceEnabled = false,
                demoModeEnabled = true,
                permanentMotionEnabled = false,
            ),
            autoConfigurationApplied = true,
            deviceInfo = deviceInfo,
            environment = environment,
            notes = "screen off",
            targetDurationMinutes = 30,
            startedAtMs = 0L,
        )

        assertEquals(BatteryTestProfile.TYPICAL_BACKGROUND_USE, active.profile)
        assertEquals(30, active.targetDurationMinutes)
        assertEquals("Pixel", active.deviceInfo.deviceModel)
        assertEquals("Wi-Fi, internet", active.environment.networkSummary)
    }

    @Test
    fun completeRunComputesWarningsAndCompletionReason() {
        val active = BatteryAssessmentLogic.startRun(
            platform = "Android",
            profile = BatteryTestProfile.TYPICAL_BACKGROUND_USE,
            batteryPercent = 75,
            currentConfig = BatteryConfigurationSnapshot(
                serviceEnabled = false,
                demoModeEnabled = false,
                permanentMotionEnabled = false,
            ),
            autoConfigurationApplied = false,
            deviceInfo = BatteryDeviceInfo(platform = "Android"),
            environment = BatteryRunEnvironment(lowPowerModeEnabled = false),
            notes = "screen off",
            targetDurationMinutes = 30,
            startedAtMs = 0L,
        )

        val completed = BatteryAssessmentLogic.completeRun(
            activeRun = active,
            endBatteryPercent = 72,
            completionReason = BatteryCompletionReason.AUTO_STOP,
            lowPowerModeAtEnd = true,
            endedAtMs = 20 * 60_000L,
        )

        assertEquals(BatteryCompletionReason.AUTO_STOP, completed.completionReason)
        assertTrue(completed.warningFlags.contains(BatteryRunWarning.START_BATTERY_BELOW_80))
        assertTrue(completed.warningFlags.contains(BatteryRunWarning.RUN_TOO_SHORT))
        assertTrue(completed.warningFlags.contains(BatteryRunWarning.LOW_POWER_MODE_DURING_RUN))
        assertTrue(completed.warningFlags.contains(BatteryRunWarning.AUTOCONFIG_INCOMPLETE))
    }

    @Test
    fun summaryBuildsPairedComparisonForSamePlatform() {
        val baseline = BatteryAssessmentRecord(
            platform = "Android",
            condition = BatteryTestCondition.BASELINE,
            profile = BatteryTestProfile.IDLE_BASELINE,
            startedAtMs = 0L,
            endedAtMs = 30 * 60_000L,
            durationMinutes = 30.0,
            targetDurationMinutes = 30,
            startBatteryPercent = 95,
            endBatteryPercent = 94,
            batteryDropPercent = 1,
            drainPerHourPercent = 2.0,
            serviceEnabledAtStart = false,
            demoModeAtStart = false,
            permanentMotionAtStart = false,
            deviceInfo = BatteryDeviceInfo(platform = "Android", deviceModel = "Pixel"),
            environment = BatteryRunEnvironment(networkSummary = "Wi-Fi"),
        )
        val active = baseline.copy(
            condition = BatteryTestCondition.ACTIVE,
            profile = BatteryTestProfile.TYPICAL_BACKGROUND_USE,
            endedAtMs = 61 * 60_000L,
            endBatteryPercent = 91,
            batteryDropPercent = 4,
            drainPerHourPercent = 8.0,
            serviceEnabledAtStart = true,
        )

        val summary = BatteryAssessmentLogic.summarize(listOf(baseline, active))

        assertEquals(1, summary.latestPairs.size)
        assertEquals(BatteryImpactLevel.NOTABLE, summary.impactLevel)
        assertTrue(summary.interpretation.contains("Android"))
        assertTrue(summary.interpretation.contains("delta 6.0%/hr"))
    }

    @Test
    fun reportIncludesProtocolAndRunDetails() {
        val baseline = BatteryAssessmentRecord(
            platform = "iOS",
            condition = BatteryTestCondition.BASELINE,
            profile = BatteryTestProfile.IDLE_BASELINE,
            startedAtMs = 0L,
            endedAtMs = 60 * 60_000L,
            durationMinutes = 60.0,
            targetDurationMinutes = 60,
            startBatteryPercent = 80,
            endBatteryPercent = 78,
            batteryDropPercent = 2,
            drainPerHourPercent = 2.0,
            serviceEnabledAtStart = false,
            demoModeAtStart = false,
            permanentMotionAtStart = false,
            deviceInfo = BatteryDeviceInfo(
                platform = "iOS",
                deviceModel = "iPhone",
                osVersion = "iOS 18",
                appVersion = "1.0 (1)",
            ),
            environment = BatteryRunEnvironment(
                networkSummary = "Office Wi-Fi",
                lowPowerModeEnabled = false,
            ),
            notes = "screen off",
        )
        val summary = BatteryAssessmentLogic.summarize(listOf(baseline))

        val report = BatteryAssessmentLogic.buildReport(listOf(baseline), summary)

        assertTrue(report.contains("Protocol Summary"))
        assertTrue(report.contains("Preliminary Or Unpaired Runs"))
        assertTrue(report.contains("Device: iPhone / iOS 18"))
        assertTrue(report.contains("Limitations"))
    }
}
