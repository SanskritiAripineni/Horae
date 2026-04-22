package com.google.mediapipe.examples.llminference

import android.content.Context
import android.location.Location
import android.util.Log
import com.autolife.shared.analyzer.MotionClassifier
import com.autolife.shared.db.DatabaseRepository
import com.autolife.shared.model.ContextLog
import com.autolife.shared.model.ContextLogCodec
import com.autolife.shared.model.SensorLog
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.Closeable
import java.lang.ref.WeakReference

class SequentialMotionLocationAnalyzer(
    context: Context
) : Closeable {
    companion object {
        private const val TAG = "SequentialAnalyzer"
        private const val MOTION_DURATION_MS = 15_000L
        private const val STATIONARY_MIN_MOTION_DURATION_MS = 5_000L
        private const val LOCATION_REUSE_TTL_MS = 10 * 60_000L
        private const val WIFI_REUSE_TTL_MS = 5 * 60_000L
        private const val STATIONARY_STREAK_FOR_REUSE = 2
    }

    private val contextRef = WeakReference(context)
    private val analyzerScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var isAnalyzing = false
    private var currentPhase = AnalysisPhase.NONE
    private var lastContextLog: ContextLog? = null
    private var signalReuseState = SignalReuseState()

    enum class AnalysisPhase {
        NONE,
        MOTION,
        LOCATION,
        FUSION,
        COMPLETE
    }

    suspend fun analyzeOnce(
        sharedMotionDetector: MotionDetector? = null,
        callback: ((String, AnalysisPhase) -> Unit)? = null
    ): ContextLog? {
        if (isAnalyzing) {
            callback?.invoke("Analysis already in progress", currentPhase)
            return null
        }

        val context = contextRef.get() ?: return null
        isAnalyzing = true

        try {
            currentPhase = AnalysisPhase.MOTION
            callback?.invoke("Collecting window features...", currentPhase)

            val nowMs = System.currentTimeMillis()
            val stableStationary = signalReuseState.isStableStationary(
                previousLog = lastContextLog,
                requiredStreak = STATIONARY_STREAK_FOR_REUSE
            )

            val location = when {
                stableStationary && signalReuseState.canReuseLocation(nowMs, LOCATION_REUSE_TTL_MS) -> {
                    callback?.invoke("Reusing recent location snapshot", currentPhase)
                    signalReuseState.location?.let(::Location)
                }
                else -> getBestLocation(context, requireFresh = false, highAccuracy = false)
            }
            val ssids = when {
                stableStationary && signalReuseState.canReuseWifi(nowMs, WIFI_REUSE_TTL_MS) -> {
                    callback?.invoke("Reusing recent Wi-Fi context", currentPhase)
                    signalReuseState.ssids
                }
                stableStationary -> WifiScanner(context).getWifiNetworks(maxAgeMs = WIFI_REUSE_TTL_MS)
                else -> WifiScanner(context).getWifiNetworks(forceRefresh = true)
            }
            val ssidFingerprint = WifiScanner.createFingerprint(ssids)
            val speedMps = location
                ?.takeIf { isUsableLocation(it) }
                ?.speed
                ?.toDouble()
            val motionPolicy = if (stableStationary) {
                MotionCollectionPolicy(minDurationMs = STATIONARY_MIN_MOTION_DURATION_MS)
            } else {
                null
            }

            val windowFeatures = collectWindowFeatures(
                context = context,
                sharedMotionDetector = sharedMotionDetector,
                speedMps = speedMps,
                ssidFingerprint = ssidFingerprint,
                motionPolicy = motionPolicy,
                callback = callback
            )

            val motionCandidates = MotionClassifier.classify(
                sessionSteps = windowFeatures.stepCount,
                acceleration = windowFeatures.avgAcceleration,
                altitudeChange = windowFeatures.altitudeDelta,
                speed = windowFeatures.speedMps ?: 0.0
            )

            currentPhase = AnalysisPhase.LOCATION
            callback?.invoke("Resolving location context...", currentPhase)

            val locationAnalyzer = LocationAnalyzer(context)
            val locationResult = locationAnalyzer.resolveLocationContext(
                location = location,
                ssids = ssids,
                previousLog = lastContextLog
            )

            currentPhase = AnalysisPhase.FUSION
            callback?.invoke("Calibrating motion if needed...", currentPhase)

            val calibratedMotion = if (motionCandidates.size > 1 && !locationResult.fusedLocationContext.isNullOrBlank()) {
                ContextFusionAnalyzer(context).calibrateMotion(motionCandidates, locationResult.fusedLocationContext)
            } else {
                motionCandidates.firstOrNull() ?: "stationary"
            }

            val contextLog = ContextLog(
                windowStartMs = windowFeatures.windowStartMs,
                windowEndMs = windowFeatures.windowEndMs,
                motionCandidates = motionCandidates,
                calibratedMotion = calibratedMotion,
                mapContext = locationResult.mapContext,
                ssidContext = locationResult.ssidContext,
                fusedLocationContext = locationResult.fusedLocationContext,
                locationGridKey = locationResult.gridKey,
                ssidFingerprint = locationResult.ssidFingerprint,
                reusedMapContext = locationResult.reusedMapContext,
                reusedSsidContext = locationResult.reusedSsidContext
            )

            appendContextLog(contextLog)
            lastContextLog = contextLog
            signalReuseState = signalReuseState
                .let { state ->
                    when {
                        location != null -> state.withLocation(location, nowMs)
                        stableStationary -> state
                        else -> state.clearLocation()
                    }
                }
                .let { state ->
                    when {
                        ssids.isNotEmpty() -> state.withWifi(ssids, ssidFingerprint, nowMs)
                        stableStationary -> state
                        else -> state.clearWifi()
                    }
                }
                .withMotion(calibratedMotion)

            currentPhase = AnalysisPhase.COMPLETE
            callback?.invoke(buildSummary(contextLog), currentPhase)
            return contextLog
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.e(TAG, "Analysis failed", e)
            callback?.invoke("Analysis failed: ${e.message}", currentPhase)
            return null
        } finally {
            isAnalyzing = false
            currentPhase = AnalysisPhase.NONE
        }
    }

    fun startAnalysis(callback: (String, AnalysisPhase) -> Unit) {
        analyzerScope.launch {
            analyzeOnce(callback = callback)
        }
    }

    private suspend fun collectWindowFeatures(
        context: Context,
        sharedMotionDetector: MotionDetector?,
        speedMps: Double?,
        ssidFingerprint: String,
        motionPolicy: MotionCollectionPolicy?,
        callback: ((String, AnalysisPhase) -> Unit)?
    ) = withContext(Dispatchers.Main) {
        val detector = sharedMotionDetector ?: MotionDetector(context)
        val localStart = System.currentTimeMillis()
        val features = detector.collectWindowFeatures(
            windowDurationMs = MOTION_DURATION_MS,
            speedMps = speedMps,
            ssidFingerprint = ssidFingerprint,
            motionPolicy = motionPolicy
        ) { motions ->
            callback?.invoke("Motion candidates: ${motions.joinToString(", ")}", AnalysisPhase.MOTION)
        }
        callback?.invoke("Collected motion window in ${System.currentTimeMillis() - localStart}ms", AnalysisPhase.MOTION)
        features
    }

    private fun appendContextLog(contextLog: ContextLog) {
        DatabaseRepository.insertLog(
            SensorLog(
                timestamp = contextLog.windowEndMs,
                type = "CONTEXT",
                content = ContextLogCodec.encode(contextLog)
            )
        )
    }

    private fun buildSummary(contextLog: ContextLog): String {
        val location = contextLog.fusedLocationContext
            ?: contextLog.ssidContext
            ?: contextLog.mapContext
            ?: "Unknown location"
        return "${contextLog.calibratedMotion} @ $location"
    }

    fun getCurrentPhase(): AnalysisPhase = currentPhase

    fun stopAnalysis() {
        isAnalyzing = false
    }

    override fun close() {
        stopAnalysis()
    }
}
