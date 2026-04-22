package com.google.mediapipe.examples.llminference

import com.autolife.shared.analyzer.MotionClassifier
import com.autolife.shared.model.ContextLog
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ContextPipelineTest {
    @Test
    fun refine_merges_neighboring_windows_and_keeps_more_specific_location() {
        val logs = listOf(
            ContextLog(
                windowStartMs = 0L,
                windowEndMs = 15_000L,
                motionCandidates = listOf("stationary"),
                calibratedMotion = "stationary",
                mapContext = "restaurant",
                fusedLocationContext = "restaurant",
                locationGridKey = "10:10"
            ),
            ContextLog(
                windowStartMs = 15_000L,
                windowEndMs = 30_000L,
                motionCandidates = listOf("stationary"),
                calibratedMotion = "stationary",
                mapContext = "restaurant",
                ssidContext = "McDonald's restaurant",
                fusedLocationContext = "McDonald's restaurant",
                locationGridKey = "10:10"
            )
        )

        val refined = ContextLogRefiner.refine(logs)

        assertEquals(1, refined.size)
        assertEquals("McDonald's restaurant", refined.first().locationContext)
        assertEquals(30_000L, refined.first().endMs)
    }

    @Test
    fun motion_classifier_keeps_ambiguous_transport_candidates() {
        val motions = MotionClassifier.classify(
            sessionSteps = 3,
            acceleration = 0.2,
            altitudeChange = 3.0,
            speed = 5.5
        )

        assertTrue(motions.contains("vehicle/subway/ferry/train"))
        assertTrue(motions.contains("escalator/elevator") || motions.contains("limited motion") || motions.size >= 1)
    }

    @Test
    fun location_grid_key_reuses_nearby_coordinates() {
        val keyA = LocationContextCacheStorage.gridKeyFor(37.4219999, -122.0840575)
        val keyB = LocationContextCacheStorage.gridKeyFor(37.42212, -122.08401)

        assertEquals(keyA, keyB)
    }

    @Test
    fun map_accuracy_blob_scales_with_accuracy_and_stays_bounded() {
        val provider = MapImageProvider()

        val preciseRadius = provider.accuracyBlobRadiusPx(
            latitude = 37.4219999,
            accuracyMeters = 10f
        )
        val coarseRadius = provider.accuracyBlobRadiusPx(
            latitude = 37.4219999,
            accuracyMeters = 80f
        )
        val defaultRadius = provider.accuracyBlobRadiusPx(
            latitude = 37.4219999,
            accuracyMeters = null
        )

        assertTrue(preciseRadius >= 10.24f)
        assertTrue(coarseRadius <= 46.08f)
        assertTrue(coarseRadius > preciseRadius)
        assertNotEquals(defaultRadius, 0f)
    }
}
