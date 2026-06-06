package com.autolife.composeapp.platform

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import com.autolife.composeapp.ui.screens.DevDashboardScreen
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.foundation.layout.*
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.toComposeImageBitmap
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import com.autolife.shared.db.DatabaseRepository
import com.autolife.shared.model.ContextLogCodec
import com.autolife.shared.model.RawDayMarkers
import com.autolife.shared.platform.currentTimeMillis
import kotlinx.coroutines.suspendCancellableCoroutine
import org.jetbrains.skia.Image
import platform.Foundation.NSDate
import platform.Foundation.NSDateFormatter
import platform.Foundation.NSURL
import platform.Foundation.timeIntervalSince1970
import platform.HealthKit.HKCategorySample
import platform.HealthKit.HKCategoryTypeIdentifierSleepAnalysis
import platform.HealthKit.HKHealthStore
import platform.HealthKit.HKObjectType
import platform.HealthKit.HKSampleQuery
import platform.UIKit.UIApplication
import kotlin.coroutines.resume
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.sqrt

@Composable
actual fun ServiceToggle(isRunning: Boolean, onToggle: (Boolean) -> Unit) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .padding(end = 4.dp)
            .semantics {
                contentDescription = "App background collection"
                stateDescription = if (isRunning) "Collecting" else "Paused"
            }
    ) {
        Text(
            text = if (isRunning) "Collecting" else "Paused",
            style = MaterialTheme.typography.labelMedium,
            color = if (isRunning) MaterialTheme.colorScheme.secondary
                    else MaterialTheme.colorScheme.error,
        )
        Spacer(Modifier.width(6.dp))
        Switch(
            checked = isRunning,
            onCheckedChange = onToggle,
            colors = SwitchDefaults.colors(
                checkedThumbColor = MaterialTheme.colorScheme.onPrimary,
                checkedTrackColor = MaterialTheme.colorScheme.secondary,
                uncheckedThumbColor = MaterialTheme.colorScheme.error,
                uncheckedTrackColor = MaterialTheme.colorScheme.error.copy(alpha = 0.16f),
                uncheckedBorderColor = MaterialTheme.colorScheme.error.copy(alpha = 0.36f),
            ),
            modifier = Modifier.height(24.dp),
        )
    }
}

@Composable
actual fun DevDashboardRoute(onBackClick: () -> Unit) {
    DevDashboardScreen()
}

actual fun currentDateKey(): String {
    return dateKeyForMillis(currentTimeMillis())
}

@Composable
actual fun rememberLocationPreviewImage(imageBytes: ByteArray?): ImageBitmap? {
    return remember(imageBytes) {
        imageBytes?.let { bytes ->
            runCatching { Image.makeFromEncoded(bytes).toComposeImageBitmap() }.getOrNull()
        }
    }
}

actual fun openNativeCalendar() {
    val url = NSURL(string = "calshow://") ?: return
    UIApplication.sharedApplication.openURL(url)
}

private data class SleepMarkerSnapshot(
    val onset: Float?,
    val durationHours: Float?,
    val sri: Float?,
    val episodeCoverage: Float,
    val sriCoverage: Float,
)

actual suspend fun getBehavioralMarkers(nDays: Int): List<RawDayMarkers> {
    val nowMs = currentTimeMillis()
    val dayMs = 24L * 60L * 60L * 1000L
    val startMs = nowMs - nDays * dayMs

    // ── Phase 1: mobility + social rhythm (ContextLog, no extra permissions) ──

    val contextLogs = DatabaseRepository
        .getLogsBetween(startMs, nowMs)
        .filter { it.type == "CONTEXT" }
        .mapNotNull { ContextLogCodec.decode(it.content) }

    val byDay = contextLogs.groupBy { dateKeyForMillis(it.windowStartMs) }
    val dayKeys = (0 until nDays).map { offset -> dateKeyForMillis(startMs + offset * dayMs) }

    data class DayRaw(
        val date: String,
        val mobilityEntropy: Float?,
        val revisitRatio: Float?,
        val firstActiveHour: Double?,
        val mobilityCoverage: Float,
    )

    val dailyRaw = dayKeys.map { dayKey ->
        val logs = byDay[dayKey].orEmpty()
        if (logs.isEmpty()) return@map DayRaw(dayKey, null, null, null, 0f)

        val dwellMs = mutableMapOf<String, Long>()
        var totalDwell = 0L
        logs.forEach { log ->
            val key = log.locationGridKey?.takeIf { it.isNotBlank() }
                ?: log.ssidFingerprint.takeIf { it.isNotBlank() }
                ?: "unknown"
            val dwell = max(0L, log.windowEndMs - log.windowStartMs)
            dwellMs[key] = (dwellMs[key] ?: 0L) + dwell
            totalDwell += dwell
        }

        val entropy = BehavioralMarkerMath.entropyNats(dwellMs.values)
        val revisit = BehavioralMarkerMath.topKRevisitRatio(dwellMs.values, topK = 3)
        val mobilityCoverage = BehavioralMarkerMath.coverageFraction(
            totalDwell,
            12L * 60L * 60L * 1000L,
        )

        val firstActive = logs
            .filter { !it.calibratedMotion.equals("stationary", ignoreCase = true) }
            .mapNotNull { log ->
                val hour = hourOfDay(log.windowStartMs)
                if (hour >= 4.0) hour else null
            }
            .minOrNull()

        DayRaw(dayKey, entropy, revisit, firstActive, mobilityCoverage)
    }

    val validHours = dailyRaw.mapNotNull { it.firstActiveHour }
    val medianHour = if (validHours.isNotEmpty()) validHours.sorted()[validHours.size / 2] else null

    // ── Phase 2: sleep markers via HealthKit ──────────────────────────────────

    val sleepMarkers = fetchHealthKitSleepMarkers(dayKeys, startMs)

    // ── Assemble ──────────────────────────────────────────────────────────────

    return dailyRaw.map { day ->
        val socialRhythm = if (day.firstActiveHour != null && medianHour != null) {
            (1.0 - abs(day.firstActiveHour - medianHour) / 3.0).coerceIn(0.0, 1.0).toFloat()
        } else {
            null
        }

        val sleep = sleepMarkers[day.date]

        RawDayMarkers(
            date = day.date,
            mobility_entropy = day.mobilityEntropy,
            location_revisit_ratio = day.revisitRatio,
            social_rhythm_metric = socialRhythm,
            sleep_onset_hour = sleep?.onset,
            sleep_duration_hours = sleep?.durationHours,
            sleep_regularity_index = sleep?.sri,
            // iOS has no UsageStatsManager equivalent without FamilyControls UX burden
            total_screen_min = null,
            late_night_screen_min = null,
            app_switching_rate = null,
            // iOS doesn't allow third-party apps to read SMS/call logs
            comm_reciprocity = null,
            coverage = buildMap {
                put("mobility_entropy", if (day.mobilityEntropy != null) day.mobilityCoverage else 0f)
                put("location_revisit_ratio", if (day.revisitRatio != null) day.mobilityCoverage else 0f)
                put("social_rhythm_metric", if (socialRhythm != null) day.mobilityCoverage else 0f)
                put("sleep_onset_hour", sleep?.episodeCoverage ?: 0f)
                put("sleep_duration_hours", sleep?.episodeCoverage ?: 0f)
                put("sleep_regularity_index", sleep?.sriCoverage ?: 0f)
                put("total_screen_min", 0f)
                put("late_night_screen_min", 0f)
                put("app_switching_rate", 0f)
                put("comm_reciprocity", 0f)
            },
        )
    }
}

// ── HealthKit sleep ───────────────────────────────────────────────────────────

@Suppress("UNCHECKED_CAST")
private suspend fun fetchHealthKitSleepMarkers(
    dayKeys: List<String>,
    startMs: Long,
): Map<String, SleepMarkerSnapshot> = runCatching {
    if (!HKHealthStore.isHealthDataAvailable()) return@runCatching emptyMap()

    val store = HKHealthStore()
    val sleepType = HKObjectType.categoryTypeForIdentifier(HKCategoryTypeIdentifierSleepAnalysis)
        ?: return@runCatching emptyMap()

    val authorized = suspendCancellableCoroutine<Boolean> { cont ->
        store.requestAuthorizationToShareTypes(
            typesToShare = null,
            readTypes = setOf(sleepType),
        ) { success, _ -> cont.resume(success) }
    }
    if (!authorized) return@runCatching emptyMap()

    val extendedStartMs = startMs - 24L * 60L * 60L * 1000L
    val nowMs = currentTimeMillis()

    // Kotlin/Native does not consistently expose HKQuery's date predicate helper,
    // so keep the existing local date filter but never issue an unbounded query.
    val rawSamples = suspendCancellableCoroutine<List<HKCategorySample>> { cont ->
        val query = HKSampleQuery(
            sampleType = sleepType,
            predicate = null,
            limit = 512u,
            sortDescriptors = null,
        ) { _, results, _ ->
            val typed = (results as? List<*>)
                ?.filterIsInstance<HKCategorySample>()
                ?.filter { sample ->
                    val sMs = (sample.startDate.timeIntervalSince1970 * 1000.0).toLong()
                    val eMs = (sample.endDate.timeIntervalSince1970 * 1000.0).toLong()
                    eMs > extendedStartMs && sMs < nowMs
                }
                ?: emptyList()
            cont.resume(typed)
        }
        store.executeQuery(query)
    }

    // HKCategoryValueSleepAnalysis: 0=inBed, 1=asleepUnspecified, 2=awake, 3=core, 4=deep, 5=REM
    val sleepIntervals = rawSamples
        .filter { it.value.toInt() !in listOf(0, 2) }
        .map { sample ->
            Pair(
                (sample.startDate.timeIntervalSince1970 * 1000.0).toLong(),
                (sample.endDate.timeIntervalSince1970 * 1000.0).toLong(),
            )
        }
        .sortedBy { it.first }

    data class SleepEpisode(val onset: Double, val durationHours: Double, val coverage: Float)

    val episodesByDay = mutableMapOf<String, SleepEpisode>()
    for (dayKey in dayKeys) {
        val (nightStart, nightEnd) = nightWindowMs(dayKey)
        val overlapping = sleepIntervals.filter { (s, e) -> s < nightEnd && e > nightStart }
        if (overlapping.isEmpty()) continue

        val clipped = overlapping.map { (s, e) -> Pair(maxOf(s, nightStart), minOf(e, nightEnd)) }
        val merged = mergeIntervals(clipped)
        val main = merged.maxByOrNull { (s, e) -> e - s } ?: continue
        val durationMs = main.second - main.first
        if (durationMs < 60L * 60L * 1000L) continue
        val observedMs = clipped.sumOf { (s, e) -> maxOf(0L, e - s) }
        val episodeCoverage = BehavioralMarkerMath.coverageFraction(observedMs, nightEnd - nightStart)

        episodesByDay[dayKey] = SleepEpisode(
            onset = hourOfDay(main.first),
            durationHours = durationMs.toDouble() / (60.0 * 60.0 * 1000.0),
            coverage = episodeCoverage,
        )
    }

    val onsets = episodesByDay.values.map { it.onset }
    val sri: Float? = if (onsets.size >= 2) {
        val mean = onsets.average()
        val variance = onsets.map { (it - mean) * (it - mean) }.average()
        (100.0 * (1.0 - sqrt(variance) / 4.0)).coerceIn(0.0, 100.0).toFloat()
    } else null

    val sriCoverage = BehavioralMarkerMath.coverageFraction(
        episodesByDay.size.toLong(),
        dayKeys.size.toLong().coerceAtLeast(1L),
    )

    dayKeys.associateWith { dayKey ->
        val ep = episodesByDay[dayKey]
        SleepMarkerSnapshot(
            onset = ep?.onset?.toFloat(),
            durationHours = ep?.durationHours?.toFloat()?.coerceIn(0f, 16f),
            sri = sri,
            episodeCoverage = ep?.coverage ?: 0f,
            sriCoverage = if (sri != null) sriCoverage else 0f,
        )
    }
}.getOrDefault(emptyMap())

// Night window: previous day 19:00 → current day 12:00 (noon - 17h = 7pm prior day)
private fun nightWindowMs(dayKey: String): Pair<Long, Long> {
    val formatter = NSDateFormatter().apply { dateFormat = "yyyy-MM-dd HH:mm:ss" }
    val noon = formatter.dateFromString("$dayKey 12:00:00") ?: return Pair(0L, 0L)
    val noonMs = (noon.timeIntervalSince1970 * 1000.0).toLong()
    val prev7pmMs = noonMs - 17L * 60L * 60L * 1000L
    return Pair(prev7pmMs, noonMs)
}

private fun mergeIntervals(intervals: List<Pair<Long, Long>>): List<Pair<Long, Long>> {
    if (intervals.isEmpty()) return emptyList()
    val sorted = intervals.sortedBy { it.first }
    val merged = mutableListOf(sorted[0])
    for (i in 1 until sorted.size) {
        val last = merged.last()
        val curr = sorted[i]
        if (curr.first <= last.second) {
            merged[merged.size - 1] = Pair(last.first, maxOf(last.second, curr.second))
        } else {
            merged.add(curr)
        }
    }
    return merged
}

// ── Date/time helpers ─────────────────────────────────────────────────────────

private fun dateKeyForMillis(ms: Long): String {
    val formatter = NSDateFormatter().apply {
        dateFormat = "yyyy-MM-dd"
    }
    return formatter.stringFromDate(nsDateFromEpochMillis(ms))
}

private fun hourOfDay(ms: Long): Double {
    val formatter = NSDateFormatter().apply {
        dateFormat = "H:mm"
    }
    val parts = formatter
        .stringFromDate(nsDateFromEpochMillis(ms))
        .split(":")
    val hour = parts.getOrNull(0)?.toDoubleOrNull() ?: return 0.0
    val minute = parts.getOrNull(1)?.toDoubleOrNull() ?: return hour
    return hour + minute / 60.0
}

private fun nsDateFromEpochMillis(ms: Long): NSDate {
    val secondsFromUnixEpoch = ms.toDouble() / 1000.0
    val appleReferenceOffsetSeconds = 978307200.0
    return NSDate(timeIntervalSinceReferenceDate = secondsFromUnixEpoch - appleReferenceOffsetSeconds)
}
