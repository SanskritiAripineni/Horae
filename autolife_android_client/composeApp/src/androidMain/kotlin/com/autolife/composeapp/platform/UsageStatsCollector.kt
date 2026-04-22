package com.autolife.composeapp.platform

import android.app.AppOpsManager
import android.app.usage.UsageEvents
import android.app.usage.UsageStatsManager
import android.content.Context
import android.os.Process
import java.util.Calendar

/**
 * Queries UsageStatsManager for per-day screen-time markers.
 *
 * Requires PACKAGE_USAGE_STATS (granted via Settings → Apps → Special access → Usage access).
 * Returns null for any day where the permission is absent or no data is recorded.
 *
 * Markers produced:
 *   total_screen_min       Total foreground app time during the day
 *   late_night_screen_min  Foreground time between 23:00 and 04:00 (next day)
 *   app_switching_rate     MOVE_TO_FOREGROUND events per active screen minute
 */
internal object UsageStatsCollector {

    data class ScreenMarkers(
        val totalScreenMin: Float,
        val lateNightScreenMin: Float,
        val appSwitchingRate: Float,
    )

    fun hasPermission(context: Context): Boolean {
        val appOps = context.getSystemService(Context.APP_OPS_SERVICE) as AppOpsManager
        val mode = appOps.checkOpNoThrow(
            AppOpsManager.OPSTR_GET_USAGE_STATS,
            Process.myUid(),
            context.packageName,
        )
        return mode == AppOpsManager.MODE_ALLOWED
    }

    fun computeForDay(context: Context, dayKey: String): ScreenMarkers? {
        if (!hasPermission(context)) return null

        val usm = context.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager

        val parts = dayKey.split("-")
        val cal = Calendar.getInstance()
        cal.set(parts[0].toInt(), parts[1].toInt() - 1, parts[2].toInt(), 0, 0, 0)
        cal.set(Calendar.MILLISECOND, 0)
        val dayStart = cal.timeInMillis
        val dayEnd = dayStart + 24L * 60 * 60 * 1000

        // Late-night = 23:00 on this day to 04:00 next day
        cal.set(Calendar.HOUR_OF_DAY, 23)
        cal.set(Calendar.MINUTE, 0); cal.set(Calendar.SECOND, 0); cal.set(Calendar.MILLISECOND, 0)
        val lateNightStart = cal.timeInMillis
        val lateNightEnd = dayStart + 28L * 60 * 60 * 1000   // +28h = 04:00 next day

        val events = usm.queryEvents(dayStart, minOf(dayEnd, System.currentTimeMillis()))
            ?: return null

        val lastForeground = mutableMapOf<String, Long>()  // pkg → MOVE_TO_FOREGROUND timestamp
        var totalMs = 0L
        var lateNightMs = 0L
        var switchCount = 0

        val ev = UsageEvents.Event()
        while (events.hasNextEvent()) {
            events.getNextEvent(ev)
            when (ev.eventType) {
                UsageEvents.Event.MOVE_TO_FOREGROUND -> {
                    lastForeground[ev.packageName] = ev.timeStamp
                    switchCount++
                }
                UsageEvents.Event.MOVE_TO_BACKGROUND -> {
                    val foreStart = lastForeground.remove(ev.packageName) ?: continue
                    accumulateDwell(foreStart, ev.timeStamp, lateNightStart, lateNightEnd,
                        onTotal = { totalMs += it },
                        onLateNight = { lateNightMs += it })
                }
            }
        }
        // Close any apps still foregrounded at end of window
        for (foreStart in lastForeground.values) {
            accumulateDwell(foreStart, dayEnd, lateNightStart, lateNightEnd,
                onTotal = { totalMs += it },
                onLateNight = { lateNightMs += it })
        }

        val totalMin = totalMs / 60_000f
        val lateNightMin = lateNightMs / 60_000f
        val switchRate = if (totalMin > 0f) switchCount / totalMin else 0f

        return ScreenMarkers(
            totalScreenMin = totalMin,
            lateNightScreenMin = lateNightMin,
            appSwitchingRate = switchRate,
        )
    }

    private inline fun accumulateDwell(
        start: Long, end: Long,
        lateStart: Long, lateEnd: Long,
        onTotal: (Long) -> Unit,
        onLateNight: (Long) -> Unit,
    ) {
        if (end <= start) return
        onTotal(end - start)
        val overlapStart = maxOf(start, lateStart)
        val overlapEnd = minOf(end, lateEnd)
        if (overlapEnd > overlapStart) onLateNight(overlapEnd - overlapStart)
    }
}
