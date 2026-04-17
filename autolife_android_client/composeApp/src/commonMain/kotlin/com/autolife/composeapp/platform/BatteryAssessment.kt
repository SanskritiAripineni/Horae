package com.autolife.composeapp.platform

import com.autolife.shared.db.DatabaseRepository
import com.autolife.shared.model.SensorLog
import com.autolife.shared.platform.currentTimeMillis
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

private const val BATTERY_LOG_TYPE = "BATTERY_ASSESSMENT"

@Serializable
enum class BatteryTestCondition {
    BASELINE,
    ACTIVE,
}

@Serializable
enum class BatteryImpactLevel {
    MINIMAL,
    MODEST,
    NOTABLE,
    UNKNOWN,
}

@Serializable
data class BatteryAssessmentRecord(
    val platform: String,
    val condition: BatteryTestCondition,
    val startedAtMs: Long,
    val endedAtMs: Long,
    val durationMinutes: Double,
    val startBatteryPercent: Int,
    val endBatteryPercent: Int,
    val batteryDropPercent: Int,
    val drainPerHourPercent: Double,
    val serviceEnabledAtStart: Boolean,
    val demoModeAtStart: Boolean,
    val permanentMotionAtStart: Boolean,
    val notes: String = "",
)

data class ActiveBatteryAssessment(
    val platform: String,
    val condition: BatteryTestCondition,
    val startedAtMs: Long,
    val startBatteryPercent: Int,
    val serviceEnabledAtStart: Boolean,
    val demoModeAtStart: Boolean,
    val permanentMotionAtStart: Boolean,
    val autoStopAtMs: Long? = null,
    val autoDurationMinutes: Int? = null,
    val stopServiceOnCompletion: Boolean = false,
    val notes: String = "",
)

data class BatteryAssessmentSummary(
    val baseline: BatteryAssessmentRecord?,
    val active: BatteryAssessmentRecord?,
    val impactLevel: BatteryImpactLevel,
    val interpretation: String,
)

object BatteryAssessmentStore {
    private val json = Json { ignoreUnknownKeys = true }

    fun loadAll(): List<BatteryAssessmentRecord> {
        return DatabaseRepository.getLogsByType(BATTERY_LOG_TYPE).mapNotNull { log ->
            runCatching { json.decodeFromString<BatteryAssessmentRecord>(log.content) }.getOrNull()
        }
    }

    fun save(record: BatteryAssessmentRecord) {
        DatabaseRepository.insertLog(
            SensorLog(
                timestamp = record.endedAtMs,
                type = BATTERY_LOG_TYPE,
                content = json.encodeToString(record),
            )
        )
    }
}

object BatteryAssessmentLogic {
    fun startRun(
        platform: String,
        condition: BatteryTestCondition,
        batteryPercent: Int,
        serviceEnabled: Boolean,
        demoModeEnabled: Boolean,
        permanentMotionEnabled: Boolean,
        notes: String,
        autoDurationMinutes: Int? = null,
        stopServiceOnCompletion: Boolean = false,
        startedAtMs: Long = currentTimeMillis(),
    ): ActiveBatteryAssessment {
        return ActiveBatteryAssessment(
            platform = platform,
            condition = condition,
            startedAtMs = startedAtMs,
            startBatteryPercent = batteryPercent,
            serviceEnabledAtStart = serviceEnabled,
            demoModeAtStart = demoModeEnabled,
            permanentMotionAtStart = permanentMotionEnabled,
            autoStopAtMs = autoDurationMinutes?.let { startedAtMs + it * 60_000L },
            autoDurationMinutes = autoDurationMinutes,
            stopServiceOnCompletion = stopServiceOnCompletion,
            notes = notes,
        )
    }

    fun completeRun(
        activeRun: ActiveBatteryAssessment,
        endBatteryPercent: Int,
        endedAtMs: Long = currentTimeMillis(),
    ): BatteryAssessmentRecord {
        val durationMs = (endedAtMs - activeRun.startedAtMs).coerceAtLeast(60_000L)
        val durationMinutes = durationMs / 60_000.0
        val batteryDrop = (activeRun.startBatteryPercent - endBatteryPercent).coerceAtLeast(0)
        val drainPerHour = batteryDrop * (60.0 / durationMinutes)

        return BatteryAssessmentRecord(
            platform = activeRun.platform,
            condition = activeRun.condition,
            startedAtMs = activeRun.startedAtMs,
            endedAtMs = endedAtMs,
            durationMinutes = durationMinutes,
            startBatteryPercent = activeRun.startBatteryPercent,
            endBatteryPercent = endBatteryPercent.coerceAtLeast(0),
            batteryDropPercent = batteryDrop,
            drainPerHourPercent = drainPerHour,
            serviceEnabledAtStart = activeRun.serviceEnabledAtStart,
            demoModeAtStart = activeRun.demoModeAtStart,
            permanentMotionAtStart = activeRun.permanentMotionAtStart,
            notes = activeRun.notes,
        )
    }

    fun summarize(records: List<BatteryAssessmentRecord>): BatteryAssessmentSummary {
        val baseline = records.lastOrNull { it.condition == BatteryTestCondition.BASELINE }
        val active = records.lastOrNull { it.condition == BatteryTestCondition.ACTIVE }

        if (baseline == null && active == null) {
            return BatteryAssessmentSummary(
                baseline = null,
                active = null,
                impactLevel = BatteryImpactLevel.UNKNOWN,
                interpretation = "Run one baseline session and one active session to compare battery burden.",
            )
        }

        if (baseline == null || active == null) {
            val single = active ?: baseline!!
            val level = classifySingleRun(single.drainPerHourPercent)
            return BatteryAssessmentSummary(
                baseline = baseline,
                active = active,
                impactLevel = level,
                interpretation = buildSingleRunInterpretation(single, level),
            )
        }

        val delta = active.drainPerHourPercent - baseline.drainPerHourPercent
        val level = classifyDelta(delta)
        return BatteryAssessmentSummary(
            baseline = baseline,
            active = active,
            impactLevel = level,
            interpretation = buildComparisonInterpretation(baseline, active, delta, level),
        )
    }

    fun buildReport(records: List<BatteryAssessmentRecord>, summary: BatteryAssessmentSummary): String {
        val sb = StringBuilder()
        sb.append("# AutoLife Battery Assessment Report\n\n")
        sb.append("Generated: ").append(formatTimestamp(currentTimeMillis())).append("\n\n")

        if (records.isEmpty()) {
            sb.append("No completed battery assessment runs are available yet.\n")
            return sb.toString()
        }

        sb.append("## Latest Interpretation\n\n")
        sb.append(summary.interpretation).append("\n\n")

        summary.baseline?.let { baseline ->
            sb.append("## Baseline Run\n\n")
            appendRun(sb, baseline)
        }

        summary.active?.let { active ->
            sb.append("## Active Run\n\n")
            appendRun(sb, active)
        }

        sb.append("## All Completed Runs\n\n")
        records.sortedByDescending { it.endedAtMs }.forEach { record ->
            sb.append("- ")
                .append(record.platform)
                .append(" ")
                .append(record.condition.name.lowercase())
                .append(": ")
                .append(record.startBatteryPercent)
                .append("% -> ")
                .append(record.endBatteryPercent)
                .append("% over ")
                .append(formatDecimal(record.durationMinutes))
                .append(" min (")
                .append(formatDecimal(record.drainPerHourPercent))
                .append("%/hr)\n")
        }

        return sb.toString()
    }

    private fun appendRun(sb: StringBuilder, record: BatteryAssessmentRecord) {
        sb.append("- Platform: ").append(record.platform).append("\n")
        sb.append("- Condition: ").append(record.condition.name.lowercase()).append("\n")
        sb.append("- Time: ").append(formatTimestamp(record.startedAtMs))
            .append(" to ")
            .append(formatTimestamp(record.endedAtMs))
            .append("\n")
        sb.append("- Battery: ").append(record.startBatteryPercent).append("% -> ")
            .append(record.endBatteryPercent).append("%\n")
        sb.append("- Drop: ").append(record.batteryDropPercent).append("%\n")
        sb.append("- Estimated drain per hour: ").append(formatDecimal(record.drainPerHourPercent)).append("%/hr\n")
        sb.append("- Service enabled at start: ").append(if (record.serviceEnabledAtStart) "yes" else "no").append("\n")
        sb.append("- Demo mode at start: ").append(if (record.demoModeAtStart) "yes" else "no").append("\n")
        sb.append("- Permanent motion at start: ").append(if (record.permanentMotionAtStart) "yes" else "no").append("\n")
        if (record.notes.isNotBlank()) {
            sb.append("- Notes: ").append(record.notes).append("\n")
        }
        sb.append("\n")
    }

    private fun classifySingleRun(drainPerHourPercent: Double): BatteryImpactLevel {
        return when {
            drainPerHourPercent <= 4.0 -> BatteryImpactLevel.MINIMAL
            drainPerHourPercent <= 8.0 -> BatteryImpactLevel.MODEST
            else -> BatteryImpactLevel.NOTABLE
        }
    }

    private fun classifyDelta(deltaPerHourPercent: Double): BatteryImpactLevel {
        return when {
            deltaPerHourPercent <= 2.0 -> BatteryImpactLevel.MINIMAL
            deltaPerHourPercent <= 5.0 -> BatteryImpactLevel.MODEST
            else -> BatteryImpactLevel.NOTABLE
        }
    }

    private fun buildSingleRunInterpretation(
        record: BatteryAssessmentRecord,
        level: BatteryImpactLevel,
    ): String {
        val severity = when (level) {
            BatteryImpactLevel.MINIMAL -> "minimal"
            BatteryImpactLevel.MODEST -> "modest"
            BatteryImpactLevel.NOTABLE -> "notable"
            BatteryImpactLevel.UNKNOWN -> "unknown"
        }
        return "Only a ${record.condition.name.lowercase()} run is available so far. " +
            "It showed an estimated battery drain of ${formatDecimal(record.drainPerHourPercent)}% per hour, " +
            "which suggests $severity battery impact. Add the matching comparison run for a clearer IRB statement."
    }

    private fun buildComparisonInterpretation(
        baseline: BatteryAssessmentRecord,
        active: BatteryAssessmentRecord,
        deltaPerHourPercent: Double,
        level: BatteryImpactLevel,
    ): String {
        val severity = when (level) {
            BatteryImpactLevel.MINIMAL -> "minimal"
            BatteryImpactLevel.MODEST -> "modest"
            BatteryImpactLevel.NOTABLE -> "notable"
            BatteryImpactLevel.UNKNOWN -> "unknown"
        }
        return "Compared with baseline, the active condition increased estimated battery drain " +
            "from ${formatDecimal(baseline.drainPerHourPercent)}%/hr to ${formatDecimal(active.drainPerHourPercent)}%/hr " +
            "(delta ${formatDecimal(deltaPerHourPercent)}%/hr). This suggests $severity added battery burden for participants."
    }

    private fun formatTimestamp(timestampMs: Long): String {
        val seconds = timestampMs / 1000
        val minutes = (seconds / 60) % 60
        val hours = (seconds / 3600) % 24
        val days = seconds / 86_400
        return "epoch-day $days ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}"
    }

    private fun formatDecimal(value: Double): String = ((value * 10).toInt() / 10.0).toString()
}
