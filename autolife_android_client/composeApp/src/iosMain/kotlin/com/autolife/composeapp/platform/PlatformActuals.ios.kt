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
import com.autolife.shared.db.DatabaseRepository
import com.autolife.shared.model.ContextLogCodec
import com.autolife.shared.model.RawDayMarkers
import com.autolife.shared.platform.currentTimeMillis
import org.jetbrains.skia.Image
import platform.Foundation.NSDate
import platform.Foundation.NSDateFormatter
import platform.Foundation.timeIntervalSince1970
import kotlin.math.abs
import kotlin.math.ln
import kotlin.math.max

@Composable
actual fun ServiceToggle(isRunning: Boolean, onToggle: (Boolean) -> Unit) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.padding(end = 4.dp)
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

actual suspend fun getBehavioralMarkers(nDays: Int): List<RawDayMarkers> {
    val nowMs = currentTimeMillis()
    val dayMs = 24L * 60L * 60L * 1000L
    val startMs = nowMs - nDays * dayMs

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
    )

    val dailyRaw = dayKeys.map { dayKey ->
        val logs = byDay[dayKey].orEmpty()
        if (logs.isEmpty()) return@map DayRaw(dayKey, null, null, null)

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

        val entropy = when {
            totalDwell > 0 && dwellMs.size > 1 -> {
                var h = 0.0
                dwellMs.values.forEach { dwell ->
                    val p = dwell.toDouble() / totalDwell
                    if (p > 0.0) h -= p * (ln(p) / ln(2.0))
                }
                h.toFloat().coerceIn(0f, 10f)
            }
            totalDwell > 0 -> 0f
            else -> null
        }

        val revisit = if (totalDwell > 0) {
            (dwellMs.values.max().toDouble() / totalDwell).toFloat().coerceIn(0f, 1f)
        } else {
            null
        }

        val firstActive = logs
            .filter { !it.calibratedMotion.equals("stationary", ignoreCase = true) }
            .mapNotNull { log ->
                val hour = hourOfDay(log.windowStartMs)
                if (hour >= 4.0) hour else null
            }
            .minOrNull()

        DayRaw(dayKey, entropy, revisit, firstActive)
    }

    val validHours = dailyRaw.mapNotNull { it.firstActiveHour }
    val medianHour = if (validHours.isNotEmpty()) validHours.sorted()[validHours.size / 2] else null

    return dailyRaw.map { day ->
        val socialRhythm = if (day.firstActiveHour != null && medianHour != null) {
            (1.0 - abs(day.firstActiveHour - medianHour) / 3.0).coerceIn(0.0, 1.0).toFloat()
        } else {
            null
        }

        RawDayMarkers(
            date = day.date,
            mobility_entropy = day.mobilityEntropy,
            location_revisit_ratio = day.revisitRatio,
            social_rhythm_metric = socialRhythm,
            coverage = mapOf(
                "mobility_entropy" to if (day.mobilityEntropy != null) 1f else 0f,
                "location_revisit_ratio" to if (day.revisitRatio != null) 1f else 0f,
                "social_rhythm_metric" to if (socialRhythm != null) 1f else 0f,
            ),
        )
    }
}

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
