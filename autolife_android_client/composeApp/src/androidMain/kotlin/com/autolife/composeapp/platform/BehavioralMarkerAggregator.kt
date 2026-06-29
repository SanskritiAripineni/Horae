package com.autolife.composeapp.platform

import com.autolife.shared.db.DatabaseRepository
import com.autolife.shared.model.ContextLogCodec
import com.autolife.shared.model.RawDayMarkers
import java.util.Calendar
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.sqrt

/**
 * Derives StudentLife-style behavioral markers from sensor data stored in SQLDelight
 * and from Android platform APIs.
 *
 * Phase 1 — ContextLog (no permissions):
 *   mobility_entropy        Shannon entropy of location-cluster dwell distribution
 *   location_revisit_ratio  Fraction of dwell time at the top-3 most-visited clusters
 *   social_rhythm_metric    Per-day regularity of first-active-movement onset (0–1)
 *
 * Phase 2 — SLEEP_STATE events (no permissions):
 *   sleep_onset_hour        Hour when the main sleep episode began (24h float)
 *   sleep_duration_hours    Length of main sleep episode in hours
 *   sleep_regularity_index  Cross-day onset consistency, 0–100 (SRI-style)
 *
 * Phase 3 — UsageStatsManager (PACKAGE_USAGE_STATS, user-granted via Settings):
 *   total_screen_min        Total foreground app time per day
 *   late_night_screen_min   Foreground time 23:00–04:00
 *   app_switching_rate      Foreground switches per active screen minute
 *
 * coverage map is populated to communicate per-marker data availability to the backend.
 */
internal object BehavioralMarkerAggregator {

    fun aggregate(nDays: Int): List<RawDayMarkers> {
        val nowMs = System.currentTimeMillis()
        val startMs = nowMs - nDays * 24L * 60 * 60 * 1000

        // ── Phase 1: mobility markers ─────────────────────────────────────────

        val contextLogs = DatabaseRepository
            .getLogsBetween(startMs, nowMs)
            .filter { it.type == "CONTEXT" }
            .mapNotNull { ContextLogCodec.decode(it.content) }

        val byDay = contextLogs.groupBy { msToDateKey(it.windowStartMs) }

        val dayKeys = (0 until nDays).map { offset ->
            msToDateKey(nowMs - (nDays - 1 - offset) * 24L * 60 * 60 * 1000)
        }

        data class DayRaw(
            val date: String,
            val mobilityEntropy: Float?,
            val revisitRatio: Float?,
            val firstActiveHour: Double?,
            val mobilityCoverage: Float,
        )

        val dailyRaw = dayKeys.map { dayKey ->
            val logs = byDay[dayKey] ?: emptyList()
            if (logs.isEmpty()) return@map DayRaw(dayKey, null, null, null, 0f)

            val dwellMs = mutableMapOf<String, Long>()
            var totalDwell = 0L
            for (log in logs) {
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
                .filter { it.calibratedMotion != "stationary" }
                .mapNotNull { log ->
                    val cal = Calendar.getInstance().apply { timeInMillis = log.windowStartMs }
                    val h = cal.get(Calendar.HOUR_OF_DAY) + cal.get(Calendar.MINUTE) / 60.0
                    if (h >= 4.0) h else null
                }
                .minOrNull()

            DayRaw(dayKey, entropy, revisit, firstActive, mobilityCoverage)
        }

        val validHours = dailyRaw.mapNotNull { it.firstActiveHour }
        val medianHour = if (validHours.isNotEmpty())
            validHours.sorted()[validHours.size / 2]
        else null

        // ── Phase 2: sleep markers ────────────────────────────────────────────

        val sleepMarkers = computeSleepMarkers(dayKeys, startMs)

        // ── Phase 3: screen-time markers ─────────────────────────────────────

        val ctx = AppContextHolder.context
        val screenByDay: Map<String, UsageStatsCollector.ScreenMarkers?> =
            if (ctx != null) dayKeys.associateWith { UsageStatsCollector.computeForDay(ctx, it) }
            else emptyMap()
        val hasUsageStats = ctx != null && UsageStatsCollector.hasPermission(ctx)

        // ── Phase 4: comm reciprocity ─────────────────────────────────────────

        val commByDay: Map<String, CommLogReader.CommMarkers?> =
            if (ctx != null) dayKeys.associateWith { CommLogReader.computeForDay(ctx, it) }
            else emptyMap()

        // ── Assemble final markers per day ────────────────────────────────────

        return dailyRaw.map { day ->
            val srm: Float? = if (day.firstActiveHour != null && medianHour != null)
                (1.0 - abs(day.firstActiveHour - medianHour) / 3.0)
                    .coerceIn(0.0, 1.0).toFloat()
            else null

            val sleep = sleepMarkers[day.date]

            val screen = screenByDay[day.date]
            val comm = commByDay[day.date]

            val coverage = buildMap {
                put("mobility_entropy", if (day.mobilityEntropy != null) day.mobilityCoverage else 0f)
                put("location_revisit_ratio", if (day.revisitRatio != null) day.mobilityCoverage else 0f)
                put("social_rhythm_metric", if (srm != null) day.mobilityCoverage else 0f)
                put("sleep_onset_hour", sleep?.episodeCoverage ?: 0f)
                put("sleep_duration_hours", sleep?.episodeCoverage ?: 0f)
                put("sleep_regularity_index", sleep?.sriCoverage ?: 0f)
                put("total_screen_min", screen?.totalCoverage ?: 0f)
                put("late_night_screen_min", screen?.lateNightCoverage ?: 0f)
                put("app_switching_rate", screen?.totalCoverage ?: 0f)
                put("comm_reciprocity", comm?.coverage ?: 0f)
            }

            RawDayMarkers(
                date = day.date,
                sleep_onset_hour = sleep?.onset,
                sleep_duration_hours = sleep?.durationHours,
                sleep_regularity_index = sleep?.sri,
                total_screen_min = screen?.totalScreenMin,
                late_night_screen_min = screen?.lateNightScreenMin,
                app_switching_rate = screen?.appSwitchingRate,
                mobility_entropy = day.mobilityEntropy,
                location_revisit_ratio = day.revisitRatio,
                social_rhythm_metric = srm,
                comm_reciprocity = comm?.reciprocity,
                coverage = coverage,
            )
        }
    }

    // ─────────────────────── sleep helpers ───────────────────────────────────

    private data class SleepMarkerSnapshot(
        val onset: Float?,
        val durationHours: Float?,
        val sri: Float?,
        val episodeCoverage: Float,
        val sriCoverage: Float,
    )

    private fun computeSleepMarkers(
        dayKeys: List<String>,
        startMs: Long,
    ): Map<String, SleepMarkerSnapshot> {
        val extendedStart = startMs - 24L * 60 * 60 * 1000
        val nowMs = System.currentTimeMillis()

        val rawEvents = DatabaseRepository
            .getLogsBetween(extendedStart, nowMs)
            .filter { it.type == "SLEEP_STATE" }
            .mapNotNull { parseSleepEvent(it.content) }
            .sortedBy { it.second }

        data class OffInterval(val start: Long, val end: Long, val lux: Float?)

        val offIntervals = mutableListOf<OffInterval>()
        var lastOff: Pair<Long, Float?>? = null
        for ((event, ts, lux) in rawEvents) {
            when (event) {
                "screen_off" -> lastOff = Pair(ts, lux)
                "screen_on"  -> {
                    lastOff?.let { (s, l) -> offIntervals.add(OffInterval(s, ts, l)) }
                    lastOff = null
                }
            }
        }
        lastOff?.let { (s, l) -> offIntervals.add(OffInterval(s, nowMs, l)) }

        data class SleepEpisode(val onset: Double, val durationHours: Double, val coverage: Float)

        val episodesByDay = mutableMapOf<String, SleepEpisode>()
        for (dayKey in dayKeys) {
            val (nightStart, nightEnd) = nightWindowMs(dayKey)
            val nightEvents = rawEvents.filter { (_, ts, _) -> ts in nightStart until nightEnd }
            val candidates = offIntervals.filter { iv ->
                iv.start < nightEnd && iv.end > nightStart &&
                    (iv.end - iv.start) >= 60 * 60 * 1000L
            }
            val sleep = candidates
                .sortedWith(
                    compareByDescending<OffInterval> { if (it.lux == null || it.lux < 20f) 1 else 0 }
                        .thenByDescending { it.end - it.start }
                )
                .firstOrNull()

            if (sleep == null && nightEvents.isEmpty()) {
                continue
            }

            val observedSpanMs = if (nightEvents.isNotEmpty()) {
                nightEvents.last().second - nightEvents.first().second
            } else {
                minOf(sleep!!.end, nightEnd) - maxOf(sleep.start, nightStart)
            }
            val episodeCoverage = BehavioralMarkerMath.coverageFraction(
                observedSpanMs,
                nightEnd - nightStart,
            )

            if (sleep != null) {
                val onset = msToHourOfDay(sleep.start)
                val duration = (sleep.end - sleep.start).toDouble() / (60 * 60 * 1000)
                episodesByDay[dayKey] = SleepEpisode(onset, duration, episodeCoverage)
            }
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

        return dayKeys.associateWith { dayKey ->
            val ep = episodesByDay[dayKey]
            SleepMarkerSnapshot(
                onset = ep?.onset?.toFloat(),
                durationHours = ep?.durationHours?.toFloat()?.coerceIn(0f, 16f),
                sri = sri,
                episodeCoverage = ep?.coverage ?: 0f,
                sriCoverage = if (sri != null) sriCoverage else 0f,
            )
        }
    }

    private fun parseSleepEvent(content: String): Triple<String, Long, Float?>? = runCatching {
        val event = Regex(""""event"\s*:\s*"(\w+)"""")
            .find(content)?.groupValues?.get(1) ?: return@runCatching null
        val ts = Regex(""""ts"\s*:\s*(\d+)""")
            .find(content)?.groupValues?.get(1)?.toLong() ?: return@runCatching null
        val lux = Regex(""""lux"\s*:\s*([\d.]+)""")
            .find(content)?.groupValues?.get(1)?.toFloatOrNull()
        Triple(event, ts, lux)
    }.getOrNull()

    private fun nightWindowMs(dayKey: String): Pair<Long, Long> {
        val parts = dayKey.split("-")
        val cal = Calendar.getInstance()
        cal.set(parts[0].toInt(), parts[1].toInt() - 1, parts[2].toInt(), 12, 0, 0)
        cal.set(Calendar.MILLISECOND, 0)
        val noonMs = cal.timeInMillis

        cal.add(Calendar.DAY_OF_MONTH, -1)
        cal.set(Calendar.HOUR_OF_DAY, 19)
        cal.set(Calendar.MINUTE, 0); cal.set(Calendar.SECOND, 0); cal.set(Calendar.MILLISECOND, 0)
        val prev7pmMs = cal.timeInMillis

        return Pair(prev7pmMs, noonMs)
    }

    private fun msToHourOfDay(ms: Long): Double {
        val cal = Calendar.getInstance().apply { timeInMillis = ms }
        return cal.get(Calendar.HOUR_OF_DAY) + cal.get(Calendar.MINUTE) / 60.0
    }

    private fun msToDateKey(ms: Long): String {
        val cal = Calendar.getInstance().apply { timeInMillis = ms }
        return "%04d-%02d-%02d".format(
            cal.get(Calendar.YEAR),
            cal.get(Calendar.MONTH) + 1,
            cal.get(Calendar.DAY_OF_MONTH),
        )
    }
}
