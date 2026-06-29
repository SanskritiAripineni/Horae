package com.autolife.composeapp.platform

import com.autolife.shared.db.DatabaseRepository
import com.autolife.shared.model.SensorLog
import com.autolife.shared.platform.currentTimeMillis
import kotlin.math.abs
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

private const val BATTERY_LOG_TYPE = "BATTERY_ASSESSMENT"
private const val MIN_DURATION_FOR_PRIMARY_MINUTES = 30.0
private const val MAX_PAIR_DURATION_DELTA_MINUTES = 15.0

@Serializable
enum class BatteryTestCondition {
    BASELINE,
    ACTIVE,
}

@Serializable
enum class BatteryTestProfile {
    IDLE_BASELINE,
    TYPICAL_BACKGROUND_USE,
    ;

    fun condition(): BatteryTestCondition = when (this) {
        IDLE_BASELINE -> BatteryTestCondition.BASELINE
        TYPICAL_BACKGROUND_USE -> BatteryTestCondition.ACTIVE
    }

    fun displayName(): String = when (this) {
        IDLE_BASELINE -> "Idle baseline"
        TYPICAL_BACKGROUND_USE -> "Typical background use"
    }

    fun needsServiceEnabled(): Boolean = this == TYPICAL_BACKGROUND_USE

    fun needsPermanentMotion(): Boolean = this == TYPICAL_BACKGROUND_USE

    fun instruction(): String = when (this) {
        IDLE_BASELINE ->
            "Leave collection off and keep the phone idle under normal standby conditions."
        TYPICAL_BACKGROUND_USE ->
            "Background the app after setup so it can simulate normal background collection."
    }
}

@Serializable
enum class BatteryImpactLevel {
    MINIMAL,
    MODEST,
    NOTABLE,
    UNKNOWN,
}

@Serializable
enum class BatteryScreenIntent {
    MOSTLY_SCREEN_OFF,
    MOSTLY_SCREEN_ON,
    ;

    fun displayName(): String = when (this) {
        MOSTLY_SCREEN_OFF -> "Mostly screen off"
        MOSTLY_SCREEN_ON -> "Mostly screen on"
    }
}

@Serializable
enum class BatteryAppStateIntent {
    MOSTLY_BACKGROUND,
    MOSTLY_FOREGROUND,
    ;

    fun displayName(): String = when (this) {
        MOSTLY_BACKGROUND -> "Mostly background"
        MOSTLY_FOREGROUND -> "Mostly foreground"
    }
}

@Serializable
enum class BatteryCompletionReason {
    MANUAL_STOP,
    AUTO_STOP,
    CANCELLED,
    FAILED_SETUP,
    ;

    fun displayName(): String = when (this) {
        MANUAL_STOP -> "Manual stop"
        AUTO_STOP -> "Auto stop"
        CANCELLED -> "Cancelled"
        FAILED_SETUP -> "Failed setup"
    }
}

@Serializable
enum class BatteryRunWarning {
    START_BATTERY_BELOW_80,
    RUN_TOO_SHORT,
    LOW_POWER_MODE_DURING_RUN,
    AUTOCONFIG_INCOMPLETE,
    ;

    fun displayText(): String = when (this) {
        START_BATTERY_BELOW_80 -> "Started below 80% battery"
        RUN_TOO_SHORT -> "Run was shorter than 30 minutes"
        LOW_POWER_MODE_DURING_RUN -> "Low power mode was active during the run"
        AUTOCONFIG_INCOMPLETE -> "Automatic profile setup may not have fully applied"
    }
}

@Serializable
data class BatteryDeviceInfo(
    val platform: String = "Unknown",
    val deviceModel: String = "Unknown device",
    val osVersion: String = "Unknown OS",
    val appVersion: String = "Unknown app version",
)

@Serializable
data class BatteryRunEnvironment(
    val screenIntent: BatteryScreenIntent = BatteryScreenIntent.MOSTLY_SCREEN_OFF,
    val appStateIntent: BatteryAppStateIntent = BatteryAppStateIntent.MOSTLY_BACKGROUND,
    val networkSummary: String = "Network state unavailable",
    val lowPowerModeEnabled: Boolean? = null,
)

@Serializable
data class BatteryConfigurationSnapshot(
    val serviceEnabled: Boolean,
    val demoModeEnabled: Boolean,
    val permanentMotionEnabled: Boolean,
)

@Serializable
data class BatteryAssessmentRecord(
    val platform: String,
    val condition: BatteryTestCondition,
    val profile: BatteryTestProfile = when (condition) {
        BatteryTestCondition.BASELINE -> BatteryTestProfile.IDLE_BASELINE
        BatteryTestCondition.ACTIVE -> BatteryTestProfile.TYPICAL_BACKGROUND_USE
    },
    val startedAtMs: Long,
    val endedAtMs: Long,
    val durationMinutes: Double,
    val targetDurationMinutes: Int? = null,
    val startBatteryPercent: Int,
    val endBatteryPercent: Int,
    val batteryDropPercent: Int,
    val drainPerHourPercent: Double,
    val serviceEnabledAtStart: Boolean,
    val demoModeAtStart: Boolean,
    val permanentMotionAtStart: Boolean,
    val autoConfigurationApplied: Boolean = true,
    val deviceInfo: BatteryDeviceInfo = BatteryDeviceInfo(platform = platform),
    val environment: BatteryRunEnvironment = BatteryRunEnvironment(),
    val completionReason: BatteryCompletionReason = BatteryCompletionReason.MANUAL_STOP,
    val warningFlags: List<BatteryRunWarning> = emptyList(),
    val notes: String = "",
)

data class ActiveBatteryAssessment(
    val platform: String,
    val condition: BatteryTestCondition,
    val profile: BatteryTestProfile,
    val startedAtMs: Long,
    val startBatteryPercent: Int,
    val targetDurationMinutes: Int,
    val serviceEnabledAtStart: Boolean,
    val demoModeAtStart: Boolean,
    val permanentMotionAtStart: Boolean,
    val autoConfigurationApplied: Boolean,
    val deviceInfo: BatteryDeviceInfo,
    val environment: BatteryRunEnvironment,
    val configurationSnapshotBeforeRun: BatteryConfigurationSnapshot,
    val autoStopAtMs: Long,
    val notes: String = "",
)

data class BatteryAssessmentPair(
    val platform: String,
    val baseline: BatteryAssessmentRecord,
    val typicalUse: BatteryAssessmentRecord,
    val deltaPerHourPercent: Double,
    val impactLevel: BatteryImpactLevel,
    val confidenceLabel: String,
    val narrative: String,
)

data class BatteryAssessmentSummary(
    val latestPairs: List<BatteryAssessmentPair>,
    val preliminaryRuns: List<BatteryAssessmentRecord>,
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
        profile: BatteryTestProfile,
        batteryPercent: Int,
        currentConfig: BatteryConfigurationSnapshot,
        autoConfigurationApplied: Boolean,
        deviceInfo: BatteryDeviceInfo,
        environment: BatteryRunEnvironment,
        notes: String,
        targetDurationMinutes: Int = 30,
        startedAtMs: Long = currentTimeMillis(),
    ): ActiveBatteryAssessment {
        return ActiveBatteryAssessment(
            platform = platform,
            condition = profile.condition(),
            profile = profile,
            startedAtMs = startedAtMs,
            startBatteryPercent = batteryPercent,
            targetDurationMinutes = targetDurationMinutes,
            serviceEnabledAtStart = currentConfig.serviceEnabled,
            demoModeAtStart = currentConfig.demoModeEnabled,
            permanentMotionAtStart = currentConfig.permanentMotionEnabled,
            autoConfigurationApplied = autoConfigurationApplied,
            deviceInfo = deviceInfo,
            environment = environment,
            configurationSnapshotBeforeRun = currentConfig,
            autoStopAtMs = startedAtMs + targetDurationMinutes * 60_000L,
            notes = notes,
        )
    }

    fun completeRun(
        activeRun: ActiveBatteryAssessment,
        endBatteryPercent: Int,
        completionReason: BatteryCompletionReason,
        lowPowerModeAtEnd: Boolean?,
        endedAtMs: Long = currentTimeMillis(),
    ): BatteryAssessmentRecord {
        val durationMs = (endedAtMs - activeRun.startedAtMs).coerceAtLeast(60_000L)
        val durationMinutes = durationMs / 60_000.0
        val batteryDrop = (activeRun.startBatteryPercent - endBatteryPercent).coerceAtLeast(0)
        val drainPerHour = batteryDrop * (60.0 / durationMinutes)
        val warnings = buildList {
            if (activeRun.startBatteryPercent < 80) add(BatteryRunWarning.START_BATTERY_BELOW_80)
            if (durationMinutes < MIN_DURATION_FOR_PRIMARY_MINUTES) add(BatteryRunWarning.RUN_TOO_SHORT)
            if (activeRun.environment.lowPowerModeEnabled == true || lowPowerModeAtEnd == true) {
                add(BatteryRunWarning.LOW_POWER_MODE_DURING_RUN)
            }
            if (!activeRun.autoConfigurationApplied) add(BatteryRunWarning.AUTOCONFIG_INCOMPLETE)
        }

        return BatteryAssessmentRecord(
            platform = activeRun.platform,
            condition = activeRun.condition,
            profile = activeRun.profile,
            startedAtMs = activeRun.startedAtMs,
            endedAtMs = endedAtMs,
            durationMinutes = durationMinutes,
            targetDurationMinutes = activeRun.targetDurationMinutes,
            startBatteryPercent = activeRun.startBatteryPercent,
            endBatteryPercent = endBatteryPercent.coerceAtLeast(0),
            batteryDropPercent = batteryDrop,
            drainPerHourPercent = drainPerHour,
            serviceEnabledAtStart = activeRun.serviceEnabledAtStart,
            demoModeAtStart = activeRun.demoModeAtStart,
            permanentMotionAtStart = activeRun.permanentMotionAtStart,
            autoConfigurationApplied = activeRun.autoConfigurationApplied,
            deviceInfo = activeRun.deviceInfo,
            environment = activeRun.environment.copy(
                lowPowerModeEnabled = lowPowerModeAtEnd ?: activeRun.environment.lowPowerModeEnabled,
            ),
            completionReason = completionReason,
            warningFlags = warnings,
            notes = activeRun.notes,
        )
    }

    fun summarize(records: List<BatteryAssessmentRecord>): BatteryAssessmentSummary {
        if (records.isEmpty()) {
            return BatteryAssessmentSummary(
                latestPairs = emptyList(),
                preliminaryRuns = emptyList(),
                impactLevel = BatteryImpactLevel.UNKNOWN,
                interpretation = "Run an idle baseline and a typical background use assessment to compare battery burden.",
            )
        }

        val pairs = buildLatestPairs(records)
        val pairPlatforms = pairs.map { it.platform }.toSet()
        val preliminaryRuns = records
            .sortedByDescending { it.endedAtMs }
            .filter { it.platform !in pairPlatforms }
            .distinctBy { it.platform }

        val impactLevel = when {
            pairs.isNotEmpty() -> pairs.maxByOrNull { severityRank(it.impactLevel) }?.impactLevel ?: BatteryImpactLevel.UNKNOWN
            preliminaryRuns.isNotEmpty() -> preliminaryRuns
                .map { classifySingleRun(it.drainPerHourPercent) }
                .maxByOrNull { severityRank(it) } ?: BatteryImpactLevel.UNKNOWN
            else -> BatteryImpactLevel.UNKNOWN
        }

        val interpretation = buildSummaryInterpretation(pairs, preliminaryRuns)

        return BatteryAssessmentSummary(
            latestPairs = pairs,
            preliminaryRuns = preliminaryRuns,
            impactLevel = impactLevel,
            interpretation = interpretation,
        )
    }

    fun buildReport(records: List<BatteryAssessmentRecord>, summary: BatteryAssessmentSummary): String {
        val sb = StringBuilder()
        sb.append("# App Battery Assessment Report\n\n")
        sb.append("Generated: ").append(formatTimestamp(currentTimeMillis())).append("\n\n")

        if (records.isEmpty()) {
            sb.append("No completed battery assessment runs are available yet.\n")
            return sb.toString()
        }

        sb.append("## Protocol Summary\n\n")
        sb.append("- Profiles used: idle baseline and typical background use\n")
        sb.append("- Recommended duration: 30 minutes or longer per run\n")
        sb.append("- Intended audience: study team / IRB burden assessment\n")
        sb.append("- Interpretation category: ")
            .append(summary.impactLevel.name.lowercase())
            .append("\n\n")

        sb.append("## Interpretation\n\n")
        sb.append(summary.interpretation).append("\n\n")

        sb.append("## Latest Paired Results\n\n")
        if (summary.latestPairs.isEmpty()) {
            sb.append("No valid paired baseline + typical-use comparisons are available yet.\n\n")
        } else {
            summary.latestPairs.forEach { pair ->
                appendPair(sb, pair)
            }
        }

        sb.append("## Preliminary Or Unpaired Runs\n\n")
        if (summary.preliminaryRuns.isEmpty()) {
            sb.append("All latest platform results currently have paired comparisons.\n\n")
        } else {
            summary.preliminaryRuns.forEach { record ->
                sb.append("- ")
                    .append(record.platform)
                    .append(": ")
                    .append(buildSingleRunInterpretation(record, classifySingleRun(record.drainPerHourPercent)))
                    .append("\n")
            }
            sb.append("\n")
        }

        sb.append("## Run Details\n\n")
        records.sortedByDescending { it.endedAtMs }.forEach { record ->
            appendRun(sb, record)
        }

        sb.append("## Limitations\n\n")
        sb.append("- This is an informal device-level assessment, not a laboratory power benchmark.\n")
        sb.append("- Battery percentage is coarse and may vary by device model, OS version, signal strength, and background policies.\n")
        sb.append("- iOS and Android can expose different background behavior and metadata, so results should be interpreted comparatively rather than as exact power use.\n")

        return sb.toString()
    }

    fun buildSetupMessages(
        records: List<BatteryAssessmentRecord>,
        platform: String,
        profile: BatteryTestProfile,
        currentBatteryPercent: Int?,
        demoModeEnabled: Boolean,
    ): List<String> {
        val messages = mutableListOf<String>()
        if (currentBatteryPercent == null) {
            messages += "Refresh battery level before starting an assessment."
        } else if (currentBatteryPercent < 80) {
            messages += "Battery is below 80%; IRB runs are more defensible when they start at 80% or higher."
        }
        if (demoModeEnabled) {
            messages += "Demo mode will be turned off automatically for IRB assessment runs."
        }
        val counterpartProfile = when (profile) {
            BatteryTestProfile.IDLE_BASELINE -> BatteryTestProfile.TYPICAL_BACKGROUND_USE
            BatteryTestProfile.TYPICAL_BACKGROUND_USE -> BatteryTestProfile.IDLE_BASELINE
        }
        val hasCounterpart = records.any { it.platform == platform && it.profile == counterpartProfile }
        if (!hasCounterpart) {
            messages += "No paired ${counterpartProfile.displayName().lowercase()} run has been recorded for $platform yet."
        }
        return messages
    }

    private fun buildLatestPairs(records: List<BatteryAssessmentRecord>): List<BatteryAssessmentPair> {
        return records
            .map { it.platform }
            .distinct()
            .mapNotNull { platform ->
                val platformRuns = records
                    .filter { it.platform == platform }
                    .sortedByDescending { it.endedAtMs }
                val latestBaseline = platformRuns.firstOrNull { it.profile == BatteryTestProfile.IDLE_BASELINE }
                val latestTypical = platformRuns.firstOrNull { it.profile == BatteryTestProfile.TYPICAL_BACKGROUND_USE }
                if (latestBaseline == null || latestTypical == null) return@mapNotNull null
                if (!areComparable(latestBaseline, latestTypical)) return@mapNotNull null
                val delta = latestTypical.drainPerHourPercent - latestBaseline.drainPerHourPercent
                val level = classifyDelta(delta)
                val confidence = if (latestBaseline.durationMinutes >= MIN_DURATION_FOR_PRIMARY_MINUTES &&
                    latestTypical.durationMinutes >= MIN_DURATION_FOR_PRIMARY_MINUTES
                ) {
                    "Paired 30+ minute comparison"
                } else {
                    "Paired comparison, but one or both runs were shorter than 30 minutes"
                }
                BatteryAssessmentPair(
                    platform = platform,
                    baseline = latestBaseline,
                    typicalUse = latestTypical,
                    deltaPerHourPercent = delta,
                    impactLevel = level,
                    confidenceLabel = confidence,
                    narrative = buildComparisonInterpretation(latestBaseline, latestTypical, delta, level),
                )
            }
            .sortedBy { it.platform }
    }

    private fun areComparable(
        baseline: BatteryAssessmentRecord,
        typical: BatteryAssessmentRecord,
    ): Boolean {
        return abs(baseline.durationMinutes - typical.durationMinutes) <= MAX_PAIR_DURATION_DELTA_MINUTES
    }

    private fun appendPair(sb: StringBuilder, pair: BatteryAssessmentPair) {
        sb.append("### ").append(pair.platform).append("\n\n")
        sb.append("- Device: ").append(pair.typicalUse.deviceInfo.deviceModel)
            .append(" / ").append(pair.typicalUse.deviceInfo.osVersion).append("\n")
        sb.append("- App version: ").append(pair.typicalUse.deviceInfo.appVersion).append("\n")
        sb.append("- Baseline drain: ").append(formatDecimal(pair.baseline.drainPerHourPercent)).append("%/hr\n")
        sb.append("- Typical-use drain: ").append(formatDecimal(pair.typicalUse.drainPerHourPercent)).append("%/hr\n")
        sb.append("- Delta: ").append(formatDecimal(pair.deltaPerHourPercent)).append("%/hr\n")
        sb.append("- Duration: ")
            .append(formatDecimal(pair.baseline.durationMinutes))
            .append(" min baseline / ")
            .append(formatDecimal(pair.typicalUse.durationMinutes))
            .append(" min typical use\n")
        sb.append("- Confidence: ").append(pair.confidenceLabel).append("\n")
        sb.append("- Narrative: ").append(pair.narrative).append("\n\n")
    }

    private fun appendRun(sb: StringBuilder, record: BatteryAssessmentRecord) {
        sb.append("### ")
            .append(record.platform)
            .append(" ")
            .append(record.profile.displayName())
            .append("\n\n")
        sb.append("- Time: ").append(formatTimestamp(record.startedAtMs))
            .append(" to ")
            .append(formatTimestamp(record.endedAtMs))
            .append("\n")
        sb.append("- Battery: ").append(record.startBatteryPercent).append("% -> ")
            .append(record.endBatteryPercent).append("%\n")
        sb.append("- Drop: ").append(record.batteryDropPercent).append("%\n")
        sb.append("- Estimated drain per hour: ").append(formatDecimal(record.drainPerHourPercent)).append("%/hr\n")
        sb.append("- Target duration: ").append(record.targetDurationMinutes ?: 0).append(" min\n")
        sb.append("- Completion: ").append(record.completionReason.displayName()).append("\n")
        sb.append("- Device: ").append(record.deviceInfo.deviceModel)
            .append(" / ").append(record.deviceInfo.osVersion).append("\n")
        sb.append("- App version: ").append(record.deviceInfo.appVersion).append("\n")
        sb.append("- Environment: ")
            .append(record.environment.screenIntent.displayName())
            .append(", ")
            .append(record.environment.appStateIntent.displayName())
            .append(", network: ")
            .append(record.environment.networkSummary)
            .append("\n")
        sb.append("- Service enabled at start: ").append(if (record.serviceEnabledAtStart) "yes" else "no").append("\n")
        sb.append("- Demo mode at start: ").append(if (record.demoModeAtStart) "yes" else "no").append("\n")
        sb.append("- Permanent motion at start: ").append(if (record.permanentMotionAtStart) "yes" else "no").append("\n")
        sb.append("- Auto-config applied: ").append(if (record.autoConfigurationApplied) "yes" else "no").append("\n")
        if (record.warningFlags.isNotEmpty()) {
            sb.append("- Warnings: ")
                .append(record.warningFlags.joinToString(", ") { it.displayText() })
                .append("\n")
        }
        if (record.notes.isNotBlank()) {
            sb.append("- Notes: ").append(record.notes).append("\n")
        }
        sb.append("\n")
    }

    private fun buildSummaryInterpretation(
        pairs: List<BatteryAssessmentPair>,
        preliminaryRuns: List<BatteryAssessmentRecord>,
    ): String {
        if (pairs.isNotEmpty()) {
            return pairs.joinToString(" ") { pair ->
                "${pair.platform}: ${pair.narrative} Confidence: ${pair.confidenceLabel.lowercase()}."
            }
        }
        if (preliminaryRuns.isNotEmpty()) {
            return preliminaryRuns.joinToString(" ") { record ->
                "${record.platform}: ${buildSingleRunInterpretation(record, classifySingleRun(record.drainPerHourPercent))}"
            }
        }
        return "Run an idle baseline and a typical background use assessment to compare battery burden."
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
        val severity = level.name.lowercase()
        return "Only a preliminary ${record.profile.displayName().lowercase()} run is available so far. " +
            "It showed an estimated battery drain of ${formatDecimal(record.drainPerHourPercent)}% per hour, " +
            "which suggests $severity battery impact. Add the paired comparison run for a clearer IRB statement."
    }

    private fun buildComparisonInterpretation(
        baseline: BatteryAssessmentRecord,
        typical: BatteryAssessmentRecord,
        deltaPerHourPercent: Double,
        level: BatteryImpactLevel,
    ): String {
        val severity = level.name.lowercase()
        return "Compared with idle baseline, the typical background use condition increased estimated battery drain " +
            "from ${formatDecimal(baseline.drainPerHourPercent)}%/hr to ${formatDecimal(typical.drainPerHourPercent)}%/hr " +
            "(delta ${formatDecimal(deltaPerHourPercent)}%/hr), which suggests $severity added battery burden for participants."
    }

    private fun severityRank(level: BatteryImpactLevel): Int = when (level) {
        BatteryImpactLevel.UNKNOWN -> 0
        BatteryImpactLevel.MINIMAL -> 1
        BatteryImpactLevel.MODEST -> 2
        BatteryImpactLevel.NOTABLE -> 3
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
