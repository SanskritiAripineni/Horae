package com.google.mediapipe.examples.llminference

import android.content.Context
import android.util.Log
import kotlinx.coroutines.*
import java.io.Closeable
import java.lang.ref.WeakReference

class MotionLocationAnalyzer(context: Context) : Closeable {
    companion object {
        private const val TAG = "MotionLocationAnalyzer"
        private const val MOTION_DETECTION_DURATION = 10000L // 10 seconds
    }

    private val contextRef = WeakReference(context)
    // Use Default dispatcher for sensor/CPU work; only post results to Main
    private val analyzerScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var currentJob: Job? = null
    private var isAnalyzing = false

    fun startAnalysis(callback: (String) -> Unit) {
        if (isAnalyzing) {
            Log.w(TAG, "Analysis already in progress")
            return
        }

        val context = contextRef.get() ?: run {
            callback("Error: Context no longer available")
            return
        }

        isAnalyzing = true
        currentJob = analyzerScope.launch {
            try {
                callback("Starting motion detection phase...")
                val motionSuccess = runMotionDetection(context, callback)
                if (motionSuccess) {
                    callback("Starting location analysis phase...")
                    val locationSuccess = runLocationAnalysis(context, callback)
                    if (locationSuccess) {
                        callback("Retrieving combined results...")
                        val results = retrieveCombinedResults(context)
                        withContext(Dispatchers.Main) { callback(results) }
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error during analysis", e)
                callback("Error during analysis: ${e.message}")
            } finally {
                isAnalyzing = false
            }
        }
    }

    private suspend fun runMotionDetection(context: Context, callback: (String) -> Unit): Boolean {
        var motionDetector: MotionDetector? = null
        return try {
            // Initialize and start on Main thread (requires Looper)
            withContext(Dispatchers.Main) {
                motionDetector = MotionDetector(context)
                motionDetector?.startDetection { motions ->
                    // Throttle updates to main thread
                    analyzerScope.launch(Dispatchers.Main) {
                        callback("Current motions: ${motions.joinToString(", ")}")
                    }
                }
            }
            val start = System.nanoTime()
            delay(MOTION_DETECTION_DURATION)
            val elapsedMs = (System.nanoTime() - start) / 1_000_000
            withContext(Dispatchers.Main) { callback("Motion phase elapsed: ${elapsedMs}ms") }
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

    private suspend fun runLocationAnalysis(context: Context, callback: (String) -> Unit): Boolean {
        var locationAnalyzer: LocationAnalyzer? = null
        return try {
            withContext(Dispatchers.IO) {
                locationAnalyzer = LocationAnalyzer(context)
                val wifiScanner = WifiScanner(context)
                val networks = wifiScanner.getWifiNetworks()
                locationAnalyzer?.analyzeLocation(networks)
                true
            }
        } catch (e: Exception) {
            Log.e(TAG, "Location analysis error", e)
            false
        } finally {
            locationAnalyzer?.close()
            locationAnalyzer = null
        }
    }

    private fun retrieveCombinedResults(context: Context): String {
        val resultBuilder = StringBuilder()

        try {
            // Get motion results
            resultBuilder.append("=== Motion Analysis Results ===\n")
            val motionStorage = MotionStorage(context)
            val motionHistory = motionStorage.getMotionHistory()
            resultBuilder.append(motionHistory ?: "No motion data available")
            resultBuilder.append("\n\n")

            // Get location results
            resultBuilder.append("=== Location Analysis Results ===\n")
            val fileStorage = FileStorage(context)
            val locationHistory = fileStorage.getLastResponse()
            resultBuilder.append(locationHistory ?: "No location data available")
        } catch (e: Exception) {
            Log.e(TAG, "Error retrieving results", e)
            resultBuilder.append("Error retrieving results: ${e.message}")
        }

        return resultBuilder.toString()
    }

    fun stopAnalysis() {
        currentJob?.cancel()
        currentJob = null
        isAnalyzing = false
    }

    override fun close() {
        stopAnalysis()
        analyzerScope.cancel()
    }
}
