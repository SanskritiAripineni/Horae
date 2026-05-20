package com.autolife.composeapp.platform

import kotlin.math.ln
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull

class BehavioralMarkerMathTest {

    @Test
    fun entropyUsesNaturalLogUnits() {
        val entropy = assertNotNull(BehavioralMarkerMath.entropyNats(listOf(3L, 1L)))
        val expected = -0.75 * ln(0.75) - 0.25 * ln(0.25)
        assertEquals(expected.toFloat(), entropy, 1e-4f)
    }

    @Test
    fun revisitRatioUsesTopThreeLocations() {
        val revisit = assertNotNull(
            BehavioralMarkerMath.topKRevisitRatio(listOf(50L, 30L, 10L, 10L), topK = 3)
        )
        assertEquals(0.9f, revisit, 1e-4f)
    }
}
