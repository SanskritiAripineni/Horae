package com.google.mediapipe.examples.llminference

import android.content.Context
import android.util.Log
import com.google.mediapipe.examples.llminference.data.LogDao
import com.google.mediapipe.examples.llminference.data.SensorLog
import com.google.mediapipe.examples.llminference.data.JournalEntry
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
                     // We skip Fusion for the Service loop usually, but here we can just finish or do Fusion.
                     // For AutoLife, we collect logs continuously, and fusion usually happens periodically or on-demand.
                     // The original flow did Fusion immediately. I will keep it but maybe we only want to LOG separately?
                     // Actually let's keep the flow: Motion -> Location -> (Done). Fusion can be a separate Dashboard action or periodic.
                     // For now, let's just finish after Location to satisfy "Data Collection".
                    // startFusionPhase(callback) 
                    // CHANGE: Just finish after location for background data collection efficiency?
                    // The paper says "Context Fusion" cleans up stream.
                    // But typically verification means we see RAW logs first.
                    // Let's keep the chain but maybe skip heavy LLM fusion in the background loop every minute?
                    // Since I set interval to 1 min, doing LLM fusion every min is expensive.
                    // Let's just finishAnalysis here.
                    finishAnalysis(callback)
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
                true
            }
        } catch (e: Exception) {
            callback("Location analysis failed: ${e.message}", AnalysisPhase.LOCATION)
            false
        }
    }


    // ------------- ORIGINAL CODE ------------
//    private suspend fun runLocationAnalysis(context: Context, callback: (String, AnalysisPhase) -> Unit): Boolean {
////        return try {
//////            withContext(Dispatchers.IO) {
//////                locationAnalyzer = LocationAnalyzer(context)
//////                val wifiScanner = WifiScanner(context)
//////                val networks = wifiScanner.getWifiNetworks()
//////                val response = locationAnalyzer?.analyzeLocation(networks)
//////                callback("Location analysis complete: $response", AnalysisPhase.LOCATION)
//////                true
//////            }
////        } catch (e: Exception) {
////            Log.e(TAG, "Location analysis error", e)
////            false
////        } finally {
////            locationAnalyzer?.close()
////            locationAnalyzer = null
////            System.gc()
////        }
//        try {
//            // 1) Try to get a usable location (fresh fix with timeout, else cached)
//            val loc = getBestLocation(context)
//            if (loc == null) {
//                callback("Location unavailable. Turn on Location or step outside.", AnalysisPhase.COMPLETE)
//                return
//            }
//
//            // 2) Wi-Fi SSIDs (don’t crash if empty on some devices)
//            val ssids: List<String> = try {
//                WifiScanner(context).scanNetworks()              // your existing call
//            } catch (e: Exception) {
//                emptyList()
//            }
//
//            // 3) If there are no SSIDs, still proceed with a minimal prompt
//            val locationAnalyzer = LocationAnalyzer(context)
//            val result = if (ssids.isNotEmpty()) {
//                locationAnalyzer.analyzeLocation(ssids)
//            } else {
//                // Minimal prompt when Wi-Fi is empty
//                locationAnalyzer.analyzeLocation(listOf("No visible Wi-Fi SSIDs"))
//            }
//
//            callback(result, AnalysisPhase.COMPLETE)
//        } catch (e: Exception) {
//            callback("Location analysis failed: ${e.message}", AnalysisPhase.COMPLETE)
//        }
//    }

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
        val result = contextFusionAnalyzer.performFusion()
        
        // Save to DB as a "Journal" entry if it's a high-level fusion
        logDao.insertJournal(
            JournalEntry(
                createdTimestamp = System.currentTimeMillis(),
                periodStart = System.currentTimeMillis() - 60000, // Roughly last minute
                periodEnd = System.currentTimeMillis(),
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
