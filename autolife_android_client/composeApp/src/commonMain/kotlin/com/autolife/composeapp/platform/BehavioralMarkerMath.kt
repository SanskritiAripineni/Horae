package com.autolife.composeapp.platform

import kotlin.math.ln

internal object BehavioralMarkerMath {

    fun entropyNats(dwellValues: Collection<Long>): Float? {
        val positive = dwellValues.filter { it > 0L }
        val total = positive.sum()
        if (total <= 0L) return null
        if (positive.size <= 1) return 0f

        var entropy = 0.0
        for (dwell in positive) {
            val p = dwell.toDouble() / total.toDouble()
            if (p > 0.0) {
                entropy -= p * ln(p)
            }
        }
        return entropy.toFloat().coerceIn(0f, 10f)
    }

    fun topKRevisitRatio(dwellValues: Collection<Long>, topK: Int = 3): Float? {
        val positive = dwellValues.filter { it > 0L }
        val total = positive.sum()
        if (total <= 0L) return null
        val top = positive.sortedDescending().take(topK).sum()
        return (top.toDouble() / total.toDouble()).toFloat().coerceIn(0f, 1f)
    }

    fun coverageFraction(observedMs: Long, fullScaleMs: Long): Float {
        if (observedMs <= 0L || fullScaleMs <= 0L) return 0f
        return (observedMs.toDouble() / fullScaleMs.toDouble()).toFloat().coerceIn(0f, 1f)
    }
}
