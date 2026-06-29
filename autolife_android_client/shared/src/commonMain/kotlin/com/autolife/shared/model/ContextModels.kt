package com.autolife.shared.model

import kotlinx.serialization.Serializable

@Serializable
data class LocationSnapshot(
    val latitude: Double,
    val longitude: Double,
    val accuracyM: Float? = null,
    val speedMps: Double? = null,
    val capturedAtMs: Long
)

@Serializable
data class WindowFeatures(
    val windowStartMs: Long,
    val windowEndMs: Long,
    val stepCount: Int,
    val avgAcceleration: Double,
    val altitudeDelta: Double,
    val speedMps: Double? = null,
    val location: LocationSnapshot? = null,
    val accuracyM: Float? = null,
    val ssidFingerprint: String = ""
)

@Serializable
data class LocationContextCacheEntry(
    val gridKey: String,
    val mapContext: String,
    val mapSourceLat: Double,
    val mapSourceLon: Double,
    val updatedAtMs: Long,
    val osmContext: String? = null,
    val ssidContext: String? = null,
    val fusedLocationContext: String? = null,
    val ssidFingerprint: String? = null,
)

@Serializable
data class ContextLog(
    val windowStartMs: Long,
    val windowEndMs: Long,
    val motionCandidates: List<String>,
    val calibratedMotion: String,
    val mapContext: String? = null,
    val osmContext: String? = null,
    val ssidContext: String? = null,
    val fusedLocationContext: String? = null,
    val locationGridKey: String? = null,
    val ssidFingerprint: String = "",
    val reusedMapContext: Boolean = false,
    val reusedSsidContext: Boolean = false
)

@Serializable
data class RefinedContextSegment(
    val startMs: Long,
    val endMs: Long,
    val motion: String,
    val locationContext: String,
    val supportingSignalsSummary: String
)
