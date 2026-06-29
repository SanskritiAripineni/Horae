package com.google.mediapipe.examples.llminference

import com.autolife.shared.model.ContextLog
import com.autolife.shared.model.RefinedContextSegment
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object ContextLogRefiner {
    fun refine(logs: List<ContextLog>): List<RefinedContextSegment> {
        if (logs.isEmpty()) return emptyList()

        val refined = mutableListOf<RefinedContextSegment>()
        var current: RefinedContextSegment? = null

        for (log in logs.sortedBy { it.windowStartMs }) {
            val motion = log.calibratedMotion.ifBlank { log.motionCandidates.firstOrNull() ?: "stationary" }
            val location = bestLocation(log)
            val summary = buildSummary(log)

            if (current != null &&
                current.motion == motion &&
                sameLocationFamily(current.locationContext, location)
            ) {
                current = current.copy(
                    endMs = log.windowEndMs,
                    locationContext = preferMoreSpecific(location, current.locationContext),
                    supportingSignalsSummary = preferMoreSpecific(current.supportingSignalsSummary, summary)
                )
            } else {
                current?.let(refined::add)
                current = RefinedContextSegment(
                    startMs = log.windowStartMs,
                    endMs = log.windowEndMs,
                    motion = motion,
                    locationContext = location,
                    supportingSignalsSummary = summary
                )
            }
        }

        current?.let(refined::add)
        return refined
    }

    fun formatForPrompt(segments: List<RefinedContextSegment>): String {
        val formatter = SimpleDateFormat("HH:mm", Locale.getDefault())
        return segments.joinToString(separator = "\n") { segment ->
            val start = formatter.format(Date(segment.startMs))
            val end = formatter.format(Date(segment.endMs))
            "[$start-$end] Motion=${segment.motion}; Location=${segment.locationContext}; Notes=${segment.supportingSignalsSummary}"
        }
    }

    fun fingerprint(segments: List<RefinedContextSegment>): String =
        segments.joinToString(separator = "|") { "${it.motion}:${it.locationContext}:${it.startMs / 60000}:${it.endMs / 60000}" }

    private fun bestLocation(log: ContextLog): String =
        preferMoreSpecific(log.ssidContext, preferMoreSpecific(log.fusedLocationContext, preferMoreSpecific(log.osmContext, log.mapContext)))
            .ifBlank { "Unknown location" }

    private fun buildSummary(log: ContextLog): String {
        val parts = mutableListOf<String>()
        if (log.motionCandidates.size > 1) {
            parts += "candidates=${log.motionCandidates.joinToString("/")}"
        }
        log.mapContext?.takeIf { it.isNotBlank() }?.let { parts += "map=$it" }
        log.osmContext?.takeIf { it.isNotBlank() }?.let { parts += "osm=$it" }
        log.ssidContext?.takeIf { it.isNotBlank() }?.let { parts += "ssid=$it" }
        if (log.reusedMapContext) parts += "reused-map"
        if (log.reusedSsidContext) parts += "reused-ssid"
        return parts.joinToString("; ").ifBlank { "window context" }
    }

    private fun preferMoreSpecific(primary: String?, fallback: String?): String {
        val a = primary?.trim().orEmpty()
        val b = fallback?.trim().orEmpty()
        return when {
            a.isBlank() -> b
            b.isBlank() -> a
            a.length >= b.length -> a
            else -> b
        }
    }

    private fun sameLocationFamily(first: String, second: String): Boolean {
        val a = first.lowercase(Locale.getDefault())
        val b = second.lowercase(Locale.getDefault())
        return a == b || a.contains(b) || b.contains(a)
    }
}
