package com.google.mediapipe.examples.llminference.data

import android.graphics.Bitmap
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

object DebugRepository {
    // Motion Data
    data class MotionStats(
        val acceleration: Double = 0.0,
        val stepCount: Int = 0,
        val speed: Double = 0.0,
        val altitude: Double = 0.0,
        val detectedClass: String = "Wait..."
    )

    private val _motionStats = MutableStateFlow(MotionStats())
    val motionStats: StateFlow<MotionStats> = _motionStats.asStateFlow()

    // Location Data
    data class LocationDebugInfo(
        val mapImage: Bitmap? = null,
        val latitude: Double = 0.0,
        val longitude: Double = 0.0,
        val ssids: List<String> = emptyList(),
        val lastInference: String = "No inference yet"
    )

    private val _locationInfo = MutableStateFlow(LocationDebugInfo())
    val locationInfo: StateFlow<LocationDebugInfo> = _locationInfo.asStateFlow()

    // Journal Data
    private val _lastJournal = MutableStateFlow<String?>(null)
    val lastJournal: StateFlow<String?> = _lastJournal.asStateFlow()

    // Config
    private val _isDemoMode = MutableStateFlow(false)
    val isDemoMode: StateFlow<Boolean> = _isDemoMode.asStateFlow()

    private val _isServiceRunning = MutableStateFlow(false)
    val isServiceRunning: StateFlow<Boolean> = _isServiceRunning.asStateFlow()

    // --- Updaters ---

    fun updateMotion(accel: Double, steps: Int, speed: Double, alt: Double, clazz: String?) {
        _motionStats.value = _motionStats.value.copy(
            acceleration = accel,
            stepCount = steps,
            speed = speed,
            altitude = alt,
            detectedClass = clazz ?: _motionStats.value.detectedClass
        )
    }

    fun updateLocationMap(bitmap: Bitmap?, lat: Double, lon: Double) {
        _locationInfo.value = _locationInfo.value.copy(
            mapImage = bitmap,
            latitude = lat,
            longitude = lon
        )
    }

    fun updateLocationSSIDs(ssids: List<String>) {
        _locationInfo.value = _locationInfo.value.copy(ssids = ssids)
    }

    fun updateLocationInference(text: String) {
        _locationInfo.value = _locationInfo.value.copy(lastInference = text)
    }

    fun updateLastJournal(journal: String) {
        _lastJournal.value = journal
    }

    fun setDemoMode(enabled: Boolean) {
        _isDemoMode.value = enabled
    }

    fun setServiceRunning(isRunning: Boolean) {
        _isServiceRunning.value = isRunning
    }
}
