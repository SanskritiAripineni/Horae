package com.google.mediapipe.examples.llminference

import android.content.Context
import android.util.Log
import com.google.mediapipe.examples.llminference.data.LogDao
import com.google.mediapipe.examples.llminference.data.SensorLog
import kotlinx.coroutines.*
import java.io.Closeable
import java.lang.ref.WeakReference
import com.google.mediapipe.examples.llminference.getBestLocation

class SequentialMotionLocationAnalyzer(
    context: Context
) : Closeable {
    companion object {
        private const val TAG = "SequentialAnalyzer"
        private const val MOTION_DURATION = 15000L // 15 seconds
    }

    private val contextRef = WeakReference(context)
    private val logDao: LogDao = (context.applicationContext as AutoLifeApp).database.logDao()
    
    // Use Default for background sequencing; hop to Main only for callbacks
    private val analyzerScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var currentJob: Job? = null
    private var isAnalyzing = false
    private var currentPhase = AnalysisPhase.NONE
    private var motionDetector: MotionDetector? = null

    private var locationAnalyzer: LocationAnalyzer? = null
    private var lastLocationContext: String? = null

    enum class AnalysisPhase {
        NONE,
        MOTION,
        LOCATION,
        FUSION,
        COMPLETE
    }

    fun startAnalysis(callback: (String, AnalysisPhase) -> Unit) {
        if (isAnalyzing) {
            callback("Analysis already in progress", currentPhase)
            return
        }

        val context = contextRef.get() ?: run {
            callback("Context no longer available", AnalysisPhase.NONE)
            return
        }

        startMotionPhase(callback)
    }

    private suspend fun runMotionDetection(context: Context, callback: (String, AnalysisPhase) -> Unit): Boolean {
        return try {
            // Initialize MotionDetector and start sensors on Main thread (requires Looper)
            withContext(Dispatchers.Main) {
                motionDetector = MotionDetector(context)
                motionDetector?.startDetection { motions ->
                    // Callback invoked on sensor thread; post to Main for UI updates
                    analyzerScope.launch(Dispatchers.Main) {
                        callback("Current motions: ${motions.joinToString(", ")}", AnalysisPhase.MOTION)
                    }
                }
            }
            // Wait for motion detection on Default dispatcher
            val start = System.nanoTime()
            delay(MOTION_DURATION)
            val elapsedMs = (System.nanoTime() - start) / 1_000_000
            withContext(Dispatchers.Main) { callback("Motion phase elapsed: ${elapsedMs}ms", AnalysisPhase.MOTION) }
            true
        } catch (e: Exception) {
            Log.e(TAG, "Motion detection error", e)
            false
        } finally {
            withContext(Dispatchers.Main) {
                motionDetector?.stopDetection()
            }
            motionDetector = null
        }
    }

    private fun startMotionPhase(callback: (String, AnalysisPhase) -> Unit) {
        isAnalyzing = true
        currentPhase = AnalysisPhase.MOTION

        val context = contextRef.get() ?: run {
            cleanup()
            callback("Context no longer available", AnalysisPhase.NONE)
            return
        }

        currentJob = analyzerScope.launch {
            try {
                val motionSuccess = runMotionDetection(context, callback)
                if (motionSuccess) {
                    finishMotionPhase(callback)
                } else {
                    cleanup()
                    callback("Motion detection failed", AnalysisPhase.MOTION)
                }
            } catch (e: CancellationException) {
                cleanup()
                throw e
            }
        }
    }


    private fun finishMotionPhase(callback: (String, AnalysisPhase) -> Unit) {
        val context = contextRef.get() ?: run {
            cleanup()
            callback("Context no longer available", AnalysisPhase.NONE)
            return
        }

        val motionStorage = MotionStorage(context)
        val motionHistory = motionStorage.getMotionHistory() ?: "No motion detected"

        // Save to DB
        analyzerScope.launch {
            logDao.insertLog(
                SensorLog(
                    timestamp = System.currentTimeMillis(),
                    type = "MOTION",
                    content = motionHistory
                )
            )
        }

        // Stop detector on Main thread
        analyzerScope.launch(Dispatchers.Main) {
            motionDetector?.stopDetection()
            motionDetector = null
        }

        startLocationPhase(callback)
    }

    private fun startLocationPhase(callback: (String, AnalysisPhase) -> Unit) {
        currentPhase = AnalysisPhase.LOCATION
        callback("Starting location analysis...", AnalysisPhase.LOCATION)

        val context = contextRef.get() ?: run {
            cleanup()
            callback("Context no longer available", AnalysisPhase.NONE)
            return
        }

        currentJob = analyzerScope.launch {
            try {
                val locationSuccess = runLocationAnalysis(context, callback)
                if (locationSuccess) {
                    startFusionPhase(callback)
                } else {
                    cleanup()
                    callback("Location analysis failed", AnalysisPhase.LOCATION)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error in location analysis", e)
                callback("Error in location analysis: ${e.message}", AnalysisPhase.LOCATION)
                cleanup()
            }
        }
    }


    private suspend fun runLocationAnalysis(
        context: Context,
        callback: (String, AnalysisPhase) -> Unit
    ): Boolean {
        return try {
            val loc = getBestLocation(context)
            if (loc == null) {
                callback("Location unavailable. Turn on Location or step outside.", AnalysisPhase.LOCATION)
                false
            } else {
                val ssids: List<String> = try {
                    WifiScanner(context).getWifiNetworks()
                } catch (_: Exception) { emptyList() }

                val locationAnalyzer = LocationAnalyzer(context)
                val result = if (ssids.isNotEmpty()) {
                    locationAnalyzer.analyzeLocation(ssids)
                } else {
                    locationAnalyzer.analyzeLocation(listOf("No visible Wi-Fi SSIDs"))
                }

                // Log to DB
                logDao.insertLog(
                    SensorLog(
                        timestamp = System.currentTimeMillis(),
                        type = "LOCATION",
                        content = result
                    )
                )

                callback("Location analysis complete: $result", AnalysisPhase.LOCATION)
                lastLocationContext = result
                true
            }
        } catch (e: Exception) {
            callback("Location analysis failed: ${e.message}", AnalysisPhase.LOCATION)
            false
        }
    }


    private fun startFusionPhase(callback: (String, AnalysisPhase) -> Unit) {
        currentPhase = AnalysisPhase.FUSION
        callback("Starting context fusion...", AnalysisPhase.FUSION)

        locationAnalyzer?.close()
        locationAnalyzer = null
        // Removed forced GC to avoid UI pauses

        currentJob = analyzerScope.launch {
            try {
                withContext(Dispatchers.IO) {
                    val context = contextRef.get() ?: run {
                        cleanup()
                        callback("Context no longer available", AnalysisPhase.NONE)
                        return@withContext
                    }

                    val result = performContextFusion(context)
                    withContext(Dispatchers.Main) {
                        callback(result, AnalysisPhase.FUSION)
                    }
                }
                finishAnalysis(callback)
            } catch (e: Exception) {
                Log.e(TAG, "Error in fusion phase", e)
                callback("Error in fusion analysis: ${e.message}", AnalysisPhase.FUSION)
                cleanup()
            }
        }
    }

    private suspend fun performContextFusion(context: Context): String {
        val contextFusionAnalyzer = ContextFusionAnalyzer(context)
        
        val motionStorage = MotionStorage(context)
        val motionHistory = motionStorage.getMotionHistory() ?: "Unknown Motion"
        val locationContext = lastLocationContext ?: "Unknown Location"
        
        val result = contextFusionAnalyzer.performFusion(motionHistory, locationContext)

        logDao.insertLog(
            SensorLog(
                timestamp = System.currentTimeMillis(),
                type = "FUSION",
                content = result
            )
        )
        
        return result
    }

    private fun finishAnalysis(callback: (String, AnalysisPhase) -> Unit) {
        currentPhase = AnalysisPhase.COMPLETE
        val results = getCombinedResults()
        callback(results, AnalysisPhase.COMPLETE)
        cleanup()
    }

    private fun getCombinedResults(): String {
        val context = contextRef.get() ?: return "Context no longer available"

        val resultBuilder = StringBuilder()

        resultBuilder.append("=== Motion Analysis Results ===\n")
        val motionStorage = MotionStorage(context)
        val motionHistory = motionStorage.getMotionHistory()
        resultBuilder.append(motionHistory ?: "No motion data available")
        resultBuilder.append("\n\n")

        resultBuilder.append("=== Location Analysis Results ===\n")
        val fileStorage = FileStorage(context)
        val locationHistory = fileStorage.getLastResponse()
        resultBuilder.append(locationHistory ?: "No location data available")

        return resultBuilder.toString()
    }

    fun getCurrentPhase(): AnalysisPhase = currentPhase

    fun stopAnalysis() {
        currentJob?.cancel()
        cleanup()
    }

    private fun cleanup() {
        currentJob?.cancel()
        currentJob = null
        // Stop motion detector on Main thread
        analyzerScope.launch(Dispatchers.Main) {
            motionDetector?.stopDetection()
            motionDetector = null
        }
        locationAnalyzer?.close()
        locationAnalyzer = null
        isAnalyzing = false
        currentPhase = AnalysisPhase.NONE
        // Removed forced GC
    }

    override fun close() {
        stopAnalysis()
        analyzerScope.cancel()
            // Removed forced GC to reduce STW pauses
    }
}
