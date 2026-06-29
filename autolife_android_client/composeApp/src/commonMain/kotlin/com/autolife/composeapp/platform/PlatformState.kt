package com.autolife.composeapp.platform

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

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
    val mapPreviewBytes: ByteArray? = null,
    val latitude: Double = 0.0,
    val longitude: Double = 0.0,
    val ssids: List<String> = emptyList(),
    val lastInference: String = "No inference yet",
    val geocoderContext: String? = null,
    val osmContext: String? = null,
    val wifiContext: String? = null,
    val inferenceSource: String = "Unavailable",
) {
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is LocationDisplayState) return false
        return mapPreviewBytes.contentEquals(other.mapPreviewBytes) &&
            latitude == other.latitude &&
            longitude == other.longitude &&
            ssids == other.ssids &&
            lastInference == other.lastInference &&
            geocoderContext == other.geocoderContext &&
            osmContext == other.osmContext &&
            wifiContext == other.wifiContext &&
            inferenceSource == other.inferenceSource
    }

    override fun hashCode(): Int {
        var result = mapPreviewBytes.contentHashCode()
        result = 31 * result + latitude.hashCode()
        result = 31 * result + longitude.hashCode()
        result = 31 * result + ssids.hashCode()
        result = 31 * result + lastInference.hashCode()
        result = 31 * result + geocoderContext.hashCode()
        result = 31 * result + osmContext.hashCode()
        result = 31 * result + wifiContext.hashCode()
        result = 31 * result + inferenceSource.hashCode()
        return result
    }
}

data class BatteryDisplayState(
    val currentBatteryPercent: Int? = null,
    val activeAssessment: ActiveBatteryAssessment? = null,
    val completedAssessments: List<BatteryAssessmentRecord> = emptyList(),
    val summary: BatteryAssessmentSummary = BatteryAssessmentLogic.summarize(emptyList()),
    val setupMessages: List<String> = emptyList(),
)

object PlatformStateProvider {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private val databaseDispatcher = Dispatchers.Default
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

    var isDebugBuild: Boolean = false

    var onDemoModeChanged: ((Boolean) -> Unit)? = null
    var onPermanentMotionChanged: ((Boolean) -> Unit)? = null
    var onExportRequested: (() -> Unit)? = null
    var onGenerateJournalRequested: (() -> Unit)? = null
    var onBatteryLevelRequested: (() -> Int?)? = null
    var onBatteryAssessmentExportRequested: ((String) -> Unit)? = null
    var onServiceToggleRequested: ((Boolean) -> Unit)? = null
    var onBatteryAssessmentCompleted: ((BatteryAssessmentRecord) -> Unit)? = null
    var onBatteryDeviceInfoRequested: (() -> BatteryDeviceInfo?)? = null
    var onBatteryEnvironmentRequested: (() -> BatteryRunEnvironment?)? = null

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

    fun updateLocation(
        latitude: Double,
        longitude: Double,
        ssids: List<String>,
        inference: String,
        mapPreviewBytes: ByteArray? = _locationState.value.mapPreviewBytes,
        geocoderContext: String? = _locationState.value.geocoderContext,
        osmContext: String? = _locationState.value.osmContext,
        wifiContext: String? = _locationState.value.wifiContext,
        inferenceSource: String = _locationState.value.inferenceSource,
    ) {
        _locationState.value = LocationDisplayState(
            mapPreviewBytes = mapPreviewBytes,
            latitude = latitude,
            longitude = longitude,
            ssids = ssids,
            lastInference = inference,
            geocoderContext = geocoderContext,
            osmContext = osmContext,
            wifiContext = wifiContext,
            inferenceSource = inferenceSource,
        )
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
        scope.launch {
            val records = withContext(databaseDispatcher) {
                BatteryAssessmentStore.loadAll()
            }
            _batteryState.value = _batteryState.value.copy(
                completedAssessments = records,
                summary = BatteryAssessmentLogic.summarize(records),
            )
        }
    }

    fun previewBatterySetupMessages(profile: BatteryTestProfile): List<String> {
        return BatteryAssessmentLogic.buildSetupMessages(
            records = _batteryState.value.completedAssessments,
            platform = platformName,
            profile = profile,
            currentBatteryPercent = _batteryState.value.currentBatteryPercent,
            demoModeEnabled = _serviceState.value.isDemoMode,
        )
    }

    fun startBatteryAssessment(
        profile: BatteryTestProfile,
        screenIntent: BatteryScreenIntent,
        appStateIntent: BatteryAppStateIntent,
        notes: String = "",
        targetDurationMinutes: Int = 30,
    ): Boolean {
        if (_batteryState.value.activeAssessment != null) {
            _batteryState.value = _batteryState.value.copy(
                setupMessages = listOf("A battery assessment is already in progress."),
            )
            return false
        }

        val batteryPercent = refreshBatteryLevel() ?: _batteryState.value.currentBatteryPercent
        if (batteryPercent == null) {
            _batteryState.value = _batteryState.value.copy(
                setupMessages = listOf("Battery level is unavailable. Refresh and try again."),
            )
            return false
        }

        val currentConfig = BatteryConfigurationSnapshot(
            serviceEnabled = _serviceState.value.isRunning,
            demoModeEnabled = _serviceState.value.isDemoMode,
            permanentMotionEnabled = _isPermanentMotionEnabled.value,
        )
        val setupMessages = BatteryAssessmentLogic.buildSetupMessages(
            records = _batteryState.value.completedAssessments,
            platform = platformName,
            profile = profile,
            currentBatteryPercent = batteryPercent,
            demoModeEnabled = _serviceState.value.isDemoMode,
        )

        val autoConfigApplied = applyProfile(profile)
        val deviceInfo = onBatteryDeviceInfoRequested?.invoke()
            ?: BatteryDeviceInfo(platform = platformName)
        val runtimeEnvironment = onBatteryEnvironmentRequested?.invoke() ?: BatteryRunEnvironment()
        val environment = runtimeEnvironment.copy(
            screenIntent = screenIntent,
            appStateIntent = appStateIntent,
        )
        val active = BatteryAssessmentLogic.startRun(
            platform = platformName,
            profile = profile,
            batteryPercent = batteryPercent,
            currentConfig = currentConfig,
            autoConfigurationApplied = autoConfigApplied,
            deviceInfo = deviceInfo,
            environment = environment,
            notes = notes.trim(),
            targetDurationMinutes = targetDurationMinutes,
        )
        _batteryState.value = _batteryState.value.copy(
            activeAssessment = active,
            setupMessages = setupMessages,
        )
        scheduleAutoStop(active)
        return true
    }

    fun completeBatteryAssessment(
        notes: String = "",
        completionReason: BatteryCompletionReason = BatteryCompletionReason.MANUAL_STOP,
    ): BatteryAssessmentRecord? {
        autoStopJob?.cancel()
        autoStopJob = null
        val activeRun = _batteryState.value.activeAssessment ?: return null
        val endBatteryPercent = refreshBatteryLevel() ?: _batteryState.value.currentBatteryPercent ?: return null
        val endEnvironment = onBatteryEnvironmentRequested?.invoke()
        val finalNotes = listOf(activeRun.notes, notes.trim()).filter { it.isNotBlank() }.joinToString(" | ")
        val completed = BatteryAssessmentLogic.completeRun(
            activeRun = activeRun.copy(notes = finalNotes),
            endBatteryPercent = endBatteryPercent,
            completionReason = completionReason,
            lowPowerModeAtEnd = endEnvironment?.lowPowerModeEnabled,
        )

        restoreProfileState(activeRun.configurationSnapshotBeforeRun)
        _batteryState.value = _batteryState.value.copy(activeAssessment = null)

        scope.launch {
            val records = withContext(databaseDispatcher) {
                BatteryAssessmentStore.save(completed)
                BatteryAssessmentStore.loadAll()
            }
            _batteryState.value = _batteryState.value.copy(
                completedAssessments = records,
                summary = BatteryAssessmentLogic.summarize(records),
            )
            onBatteryAssessmentCompleted?.invoke(completed)
        }
        return completed
    }

    fun exportBatteryAssessmentReport(): Boolean {
        val records = _batteryState.value.completedAssessments
        if (records.isEmpty()) return false
        val report = BatteryAssessmentLogic.buildReport(records, _batteryState.value.summary)
        onBatteryAssessmentExportRequested?.invoke(report)
        return true
    }

    fun toggleDemoMode(enabled: Boolean) {
        val cb = onDemoModeChanged
        if (cb != null) cb(enabled)
        else _serviceState.value = _serviceState.value.copy(isDemoMode = enabled)
    }

    fun togglePermanentMotion(enabled: Boolean) {
        val cb = onPermanentMotionChanged
        if (cb != null) cb(enabled)
        else _isPermanentMotionEnabled.value = enabled
    }

    private fun applyProfile(profile: BatteryTestProfile): Boolean {
        val desiredServiceState = profile.needsServiceEnabled()
        val desiredPermanentMotion = profile.needsPermanentMotion()
        return try {
            onDemoModeChanged?.invoke(false)
            _serviceState.value = _serviceState.value.copy(isDemoMode = false)

            onPermanentMotionChanged?.invoke(desiredPermanentMotion)
            _isPermanentMotionEnabled.value = desiredPermanentMotion

            onServiceToggleRequested?.invoke(desiredServiceState)
            _serviceState.value = _serviceState.value.copy(isRunning = desiredServiceState)
            true
        } catch (_: Throwable) {
            false
        }
    }

    private fun restoreProfileState(snapshot: BatteryConfigurationSnapshot) {
        try {
            onDemoModeChanged?.invoke(snapshot.demoModeEnabled)
            _serviceState.value = _serviceState.value.copy(isDemoMode = snapshot.demoModeEnabled)

            onPermanentMotionChanged?.invoke(snapshot.permanentMotionEnabled)
            _isPermanentMotionEnabled.value = snapshot.permanentMotionEnabled

            onServiceToggleRequested?.invoke(snapshot.serviceEnabled)
            _serviceState.value = _serviceState.value.copy(isRunning = snapshot.serviceEnabled)
        } catch (_: Throwable) {
            // Best-effort restore only.
        }
    }

    private fun scheduleAutoStop(activeAssessment: ActiveBatteryAssessment) {
        autoStopJob?.cancel()
        autoStopJob = scope.launch {
            val delayMs = (activeAssessment.autoStopAtMs - com.autolife.shared.platform.currentTimeMillis()).coerceAtLeast(0L)
            delay(delayMs)
            completeBatteryAssessment("auto-completed", BatteryCompletionReason.AUTO_STOP)
        }
    }
}
