package com.google.mediapipe.examples.llminference

import com.autolife.shared.model.ContextLog
import kotlin.math.max

internal class AdaptiveAnalysisScheduler(
    private val baseIntervalMs: Long,
    private val demoIntervalMs: Long
) {
    private var consecutiveStableIdleCycles = 0
    private var lastIdleSignature: String? = null

    fun nextDelayMs(result: ContextLog?, cycleDurationMs: Long, isDemoMode: Boolean): Long {
        val targetIntervalMs = when {
            isDemoMode -> demoIntervalMs
            result.isStableIdleComparedTo(lastIdleSignature) -> stableIdleIntervalMs()
            else -> {
                consecutiveStableIdleCycles = 0
                lastIdleSignature = result.materialContextSignature()
                baseIntervalMs
            }
        }

        if (isDemoMode) {
            consecutiveStableIdleCycles = 0
            lastIdleSignature = result.materialContextSignature()
        }

        return max(MIN_DELAY_AFTER_CYCLE_MS, targetIntervalMs - cycleDurationMs)
    }

    private fun ContextLog?.isStableIdleComparedTo(previousSignature: String?): Boolean {
        val signature = materialContextSignature() ?: return false
        val stationary = isStationary() ?: return false
        val sameContext = previousSignature != null && previousSignature == signature
        if (stationary && sameContext) {
            consecutiveStableIdleCycles += 1
            lastIdleSignature = signature
            return true
        }
        consecutiveStableIdleCycles = 0
        lastIdleSignature = signature
        return false
    }

    private fun stableIdleIntervalMs(): Long {
        return when {
            consecutiveStableIdleCycles >= 6 -> 5 * 60_000L
            consecutiveStableIdleCycles >= 4 -> 3 * 60_000L
            consecutiveStableIdleCycles >= 2 -> 2 * 60_000L
            else -> baseIntervalMs
        }
    }

    private fun ContextLog?.isStationary(): Boolean? {
        val motion = this?.calibratedMotion?.trim()?.lowercase() ?: return null
        return motion == "stationary" || motion == "still" || motion == "idle"
    }

    companion object {
        private const val MIN_DELAY_AFTER_CYCLE_MS = 15_000L
    }
}

internal class JournalAttemptThrottle(
    private val baseRetryMs: Long,
    private val demoRetryMs: Long
) {
    private var lastSuccessfulJournalAtMs = 0L
    private var lastJournalSignature: String? = null
    private var lastAttemptSignature: String? = null
    private var repeatedUnchangedAttempts = 0
    private var nextAttemptNotBeforeMs = 0L

    fun shouldAttempt(
        nowMs: Long,
        journalIntervalMs: Long,
        contextSignature: String?,
        isDemoMode: Boolean
    ): Boolean {
        if (nowMs < nextAttemptNotBeforeMs) return false
        if (lastSuccessfulJournalAtMs == 0L) return true
        if (nowMs - lastSuccessfulJournalAtMs < journalIntervalMs) return false
        if (contextSignature == null) return true
        if (contextSignature != lastJournalSignature) return true
        return nowMs >= nextAttemptNotBeforeMs
    }

    fun onAttemptFinished(
        nowMs: Long,
        success: Boolean,
        contextSignature: String?,
        journalIntervalMs: Long,
        isDemoMode: Boolean
    ) {
        if (success) {
            lastSuccessfulJournalAtMs = nowMs
            lastJournalSignature = contextSignature
            lastAttemptSignature = contextSignature
            repeatedUnchangedAttempts = 0
            nextAttemptNotBeforeMs = nowMs + journalIntervalMs
            return
        }

        val unchangedSinceLastJournal = contextSignature != null && contextSignature == lastJournalSignature
        val unchangedSinceLastAttempt = contextSignature != null && contextSignature == lastAttemptSignature
        repeatedUnchangedAttempts = if (unchangedSinceLastJournal || unchangedSinceLastAttempt) {
            repeatedUnchangedAttempts + 1
        } else {
            0
        }
        lastAttemptSignature = contextSignature

        val retryDelayMs = when {
            isDemoMode -> demoRetryMs
            repeatedUnchangedAttempts >= 3 -> journalIntervalMs
            repeatedUnchangedAttempts >= 1 -> 10 * 60_000L
            else -> baseRetryMs
        }
        nextAttemptNotBeforeMs = nowMs + retryDelayMs
    }
}

internal fun ContextLog?.materialContextSignature(): String? {
    this ?: return null
    val locationAnchor = listOf(
        locationGridKey,
        fusedLocationContext,
        ssidContext,
        mapContext,
        ssidFingerprint.takeIf { it.isNotBlank() }
    ).firstOrNull { !it.isNullOrBlank() }?.trim()?.lowercase()
    val motion = calibratedMotion.trim().lowercase().ifBlank { motionCandidates.firstOrNull()?.trim()?.lowercase().orEmpty() }
    if (motion.isBlank() && locationAnchor.isNullOrBlank()) return null
    return listOf(motion.ifBlank { "unknown-motion" }, locationAnchor ?: "unknown-location").joinToString("|")
}
