package com.autolife.composeapp.platform

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class MotionDisplayState(
    val acceleration: Double = 0.0,
    val stepCount: Int = 0,
    val speed: Double = 0.0,
    val altitude: Double = 0.0,
    val detectedClass: String = "Idle",
)

data class ServiceDisplayState(
    val isRunning: Boolean = false,
    val isDemoMode: Boolean = false,
)

data class LocationDisplayState(
    val latitude: Double = 0.0,
    val longitude: Double = 0.0,
    val ssids: List<String> = emptyList(),
    val lastInference: String = "No inference yet",
)

object PlatformStateProvider {
    private val _motionState = MutableStateFlow(MotionDisplayState())
    val motionState: StateFlow<MotionDisplayState> = _motionState.asStateFlow()

    private val _serviceState = MutableStateFlow(ServiceDisplayState())
    val serviceState: StateFlow<ServiceDisplayState> = _serviceState.asStateFlow()

    private val _locationState = MutableStateFlow(LocationDisplayState())
    val locationState: StateFlow<LocationDisplayState> = _locationState.asStateFlow()

    private val _lastJournal = MutableStateFlow<String?>(null)
    val lastJournal: StateFlow<String?> = _lastJournal.asStateFlow()

    private val _isPermanentMotionEnabled = MutableStateFlow(false)
    val isPermanentMotionEnabled: StateFlow<Boolean> = _isPermanentMotionEnabled.asStateFlow()

    // Action callbacks — set by the host app (androidApp / iosApp)
    var onDemoModeChanged: ((Boolean) -> Unit)? = null
    var onPermanentMotionChanged: ((Boolean) -> Unit)? = null
    var onExportRequested: (() -> Unit)? = null
    var onGenerateJournalRequested: (() -> Unit)? = null

    fun updateMotion(
        acceleration: Double,
        stepCount: Int,
        speed: Double,
        altitude: Double,
        detectedClass: String,
    ) {
        _motionState.value = MotionDisplayState(acceleration, stepCount, speed, altitude, detectedClass)
    }

    fun updateServiceState(isRunning: Boolean, isDemoMode: Boolean = _serviceState.value.isDemoMode) {
        _serviceState.value = ServiceDisplayState(isRunning, isDemoMode)
    }

    fun updateLocation(latitude: Double, longitude: Double, ssids: List<String>, inference: String) {
        _locationState.value = LocationDisplayState(latitude, longitude, ssids, inference)
    }

    fun updateLocationSsids(ssids: List<String>) {
        _locationState.value = _locationState.value.copy(ssids = ssids)
    }

    fun updateLocationInference(inference: String) {
        _locationState.value = _locationState.value.copy(lastInference = inference)
    }

    fun updateLastJournal(journal: String?) {
        _lastJournal.value = journal
    }

    fun updatePermanentMotion(enabled: Boolean) {
        _isPermanentMotionEnabled.value = enabled
    }

    /** Called by UI — triggers host callback or falls back to direct state update. */
    fun toggleDemoMode(enabled: Boolean) {
        val cb = onDemoModeChanged
        if (cb != null) cb(enabled)
        else _serviceState.value = _serviceState.value.copy(isDemoMode = enabled)
    }

    /** Called by UI — triggers host callback or falls back to direct state update. */
    fun togglePermanentMotion(enabled: Boolean) {
        val cb = onPermanentMotionChanged
        if (cb != null) cb(enabled)
        else _isPermanentMotionEnabled.value = enabled
    }
}
