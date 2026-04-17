package com.autolife.composeapp.platform

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class BatteryAssessmentLogicTest {

    @Test
    fun completeRunComputesDropAndDrainPerHour() {
        val active = BatteryAssessmentLogic.startRun(
            platform = "Android",
            condition = BatteryTestCondition.ACTIVE,
            batteryPercent = 90,
            serviceEnabled = true,
            demoModeEnabled = false,
            permanentMotionEnabled = true,
            notes = "screen off",
            startedAtMs = 0L,
        )

        val completed = BatteryAssessmentLogic.completeRun(
            activeRun = active,
            endBatteryPercent = 86,
            endedAtMs = 30 * 60_000L,
        )

        assertEquals(4, completed.batteryDropPercent)
        assertEquals(30.0, completed.durationMinutes)
        assertEquals(8.0, completed.drainPerHourPercent)
        assertEquals("screen off", completed.notes)
    }

    @Test
    fun summaryComparesBaselineAndActiveRuns() {
        val baseline = BatteryAssessmentRecord(
            platform = "Android",
            condition = BatteryTestCondition.BASELINE,
            startedAtMs = 0L,
            endedAtMs = 30 * 60_000L,
            durationMinutes = 30.0,
            startBatteryPercent = 95,
            endBatteryPercent = 94,
            batteryDropPercent = 1,
            drainPerHourPercent = 2.0,
            serviceEnabledAtStart = false,
            demoModeAtStart = false,
            permanentMotionAtStart = false,
            notes = "",
        )
        val active = baseline.copy(
            condition = BatteryTestCondition.ACTIVE,
            endBatteryPercent = 91,
            batteryDropPercent = 4,
            drainPerHourPercent = 8.0,
            serviceEnabledAtStart = true,
        )

        val summary = BatteryAssessmentLogic.summarize(listOf(baseline, active))

        assertEquals(BatteryImpactLevel.NOTABLE, summary.impactLevel)
        assertTrue(summary.interpretation.contains("delta 6.0%/hr"))
    }

    @Test
    fun reportIncludesInterpretationAndRuns() {
        val baseline = BatteryAssessmentRecord(
            platform = "iOS",
            condition = BatteryTestCondition.BASELINE,
            startedAtMs = 0L,
            endedAtMs = 60 * 60_000L,
            durationMinutes = 60.0,
            startBatteryPercent = 80,
            endBatteryPercent = 78,
            batteryDropPercent = 2,
            drainPerHourPercent = 2.0,
            serviceEnabledAtStart = false,
            demoModeAtStart = false,
            permanentMotionAtStart = false,
            notes = "screen off",
        )
        val summary = BatteryAssessmentLogic.summarize(listOf(baseline))

        val report = BatteryAssessmentLogic.buildReport(listOf(baseline), summary)

        assertTrue(report.contains("AutoLife Battery Assessment Report"))
        assertTrue(report.contains("suggests minimal battery impact"))
        assertTrue(report.contains("Platform: iOS"))
    }
}
