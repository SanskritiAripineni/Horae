package com.autolife.composeapp.platform

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

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

data class BatteryDisplayState(
    val currentBatteryPercent: Int? = null,
    val activeAssessment: ActiveBatteryAssessment? = null,
    val completedAssessments: List<BatteryAssessmentRecord> = emptyList(),
    val summary: BatteryAssessmentSummary = BatteryAssessmentLogic.summarize(emptyList()),
)

object PlatformStateProvider {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var autoStopJob: Job? = null

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

    private val _batteryState = MutableStateFlow(BatteryDisplayState())
    val batteryState: StateFlow<BatteryDisplayState> = _batteryState.asStateFlow()

    private var platformName: String = "Unknown"

    // Action callbacks — set by the host app (androidApp / iosApp)
    var onDemoModeChanged: ((Boolean) -> Unit)? = null
    var onPermanentMotionChanged: ((Boolean) -> Unit)? = null
    var onExportRequested: (() -> Unit)? = null
    var onGenerateJournalRequested: (() -> Unit)? = null
    var onBatteryLevelRequested: (() -> Int?)? = null
    var onBatteryAssessmentExportRequested: ((String) -> Unit)? = null
    var onServiceToggleRequested: ((Boolean) -> Unit)? = null
    var onBatteryAssessmentCompleted: ((BatteryAssessmentRecord) -> Unit)? = null

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

    fun setPlatformName(name: String) {
        platformName = name
    }

    fun refreshBatteryLevel(): Int? {
        val level = onBatteryLevelRequested?.invoke()
        _batteryState.value = _batteryState.value.copy(currentBatteryPercent = level)
        return level
    }

    fun loadBatteryAssessments() {
        val records = BatteryAssessmentStore.loadAll()
        _batteryState.value = _batteryState.value.copy(
            completedAssessments = records,
            summary = BatteryAssessmentLogic.summarize(records),
        )
    }

    fun startBatteryAssessment(
        condition: BatteryTestCondition,
        notes: String = "",
        autoDurationMinutes: Int? = null,
    ): Boolean {
        val batteryPercent = refreshBatteryLevel() ?: _batteryState.value.currentBatteryPercent ?: return false
        val serviceEnabledAtStart = _serviceState.value.isRunning
        val desiredServiceState = condition == BatteryTestCondition.ACTIVE
        if (autoDurationMinutes != null) {
            onServiceToggleRequested?.invoke(desiredServiceState)
            updateServiceState(isRunning = desiredServiceState)
        }
        val active = BatteryAssessmentLogic.startRun(
            platform = platformName,
            condition = condition,
            batteryPercent = batteryPercent,
            serviceEnabled = serviceEnabledAtStart,
            demoModeEnabled = _serviceState.value.isDemoMode,
            permanentMotionEnabled = _isPermanentMotionEnabled.value,
            notes = notes.trim(),
            autoDurationMinutes = autoDurationMinutes,
            stopServiceOnCompletion = autoDurationMinutes != null && desiredServiceState,
        )
        _batteryState.value = _batteryState.value.copy(activeAssessment = active)
        scheduleAutoStop(active)
        return true
    }

    fun completeBatteryAssessment(notes: String = ""): BatteryAssessmentRecord? {
        autoStopJob?.cancel()
        autoStopJob = null
        val activeRun = _batteryState.value.activeAssessment ?: return null
        val endBatteryPercent = refreshBatteryLevel() ?: _batteryState.value.currentBatteryPercent ?: return null
        val finalNotes = listOf(activeRun.notes, notes.trim()).filter { it.isNotBlank() }.joinToString(" | ")
        val completed = BatteryAssessmentLogic.completeRun(
            activeRun = activeRun.copy(notes = finalNotes),
            endBatteryPercent = endBatteryPercent,
        )
        BatteryAssessmentStore.save(completed)
        if (activeRun.stopServiceOnCompletion) {
            onServiceToggleRequested?.invoke(false)
            updateServiceState(isRunning = false)
        }
        val records = BatteryAssessmentStore.loadAll()
        _batteryState.value = _batteryState.value.copy(
            activeAssessment = null,
            completedAssessments = records,
            summary = BatteryAssessmentLogic.summarize(records),
        )
        onBatteryAssessmentCompleted?.invoke(completed)
        return completed
    }

    fun exportBatteryAssessmentReport(): Boolean {
        val records = _batteryState.value.completedAssessments
        if (records.isEmpty()) return false
        val report = BatteryAssessmentLogic.buildReport(records, _batteryState.value.summary)
        onBatteryAssessmentExportRequested?.invoke(report)
        return true
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

    private fun scheduleAutoStop(activeAssessment: ActiveBatteryAssessment) {
        autoStopJob?.cancel()
        val autoStopAtMs = activeAssessment.autoStopAtMs ?: return
        autoStopJob = scope.launch {
            val delayMs = (autoStopAtMs - com.autolife.shared.platform.currentTimeMillis()).coerceAtLeast(0L)
            delay(delayMs)
            completeBatteryAssessment("auto-completed")
        }
    }
}
