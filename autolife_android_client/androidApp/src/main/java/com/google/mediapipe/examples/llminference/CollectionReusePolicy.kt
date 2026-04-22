package com.google.mediapipe.examples.llminference

import android.location.Location
import com.autolife.shared.model.ContextLog

data class MotionCollectionPolicy(
    val minDurationMs: Long,
    val checkIntervalMs: Long = 1000L,
    val maxStepDelta: Int = 0,
    val maxAvgAcceleration: Double = 0.35,
    val maxAltitudeDeltaM: Double = 0.75,
    val maxSpeedMps: Double = 0.8
)

data class SignalReuseState(
    val location: Location? = null,
    val locationCapturedAtMs: Long = 0L,
    val ssids: List<String> = emptyList(),
    val ssidFingerprint: String = "",
    val wifiCapturedAtMs: Long = 0L,
    val stationaryStreak: Int = 0
) {
    fun canReuseLocation(nowMs: Long, ttlMs: Long): Boolean =
        location != null && nowMs - locationCapturedAtMs <= ttlMs

    fun canReuseWifi(nowMs: Long, ttlMs: Long): Boolean =
        ssids.isNotEmpty() && nowMs - wifiCapturedAtMs <= ttlMs

    fun isStableStationary(previousLog: ContextLog?, requiredStreak: Int): Boolean =
        previousLog?.calibratedMotion?.equals("stationary", ignoreCase = true) == true &&
            stationaryStreak >= requiredStreak

    fun withLocation(location: Location?, capturedAtMs: Long): SignalReuseState {
        val copiedLocation = location?.let(::Location)
        return copy(
            location = copiedLocation,
            locationCapturedAtMs = if (copiedLocation != null) capturedAtMs else 0L
        )
    }

    fun withWifi(ssids: List<String>, fingerprint: String, capturedAtMs: Long): SignalReuseState =
        copy(
            ssids = ssids.toList(),
            ssidFingerprint = fingerprint,
            wifiCapturedAtMs = if (ssids.isNotEmpty()) capturedAtMs else 0L
        )

    fun withMotion(calibratedMotion: String): SignalReuseState =
        copy(stationaryStreak = if (calibratedMotion.equals("stationary", ignoreCase = true)) stationaryStreak + 1 else 0)

    fun clearLocation(): SignalReuseState =
        copy(location = null, locationCapturedAtMs = 0L)

    fun clearWifi(): SignalReuseState =
        copy(ssids = emptyList(), ssidFingerprint = "", wifiCapturedAtMs = 0L)
}
