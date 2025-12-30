package com.google.mediapipe.examples.llminference

import android.content.Context
import android.util.Log
import com.google.mediapipe.tasks.genai.llminference.LlmInference
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.Closeable


class ContextFusionAnalyzer(private val context: Context) : Closeable {
    companion object {
        private const val TAG = "ContextFusionAnalyzer"
    }

//    private val llmInference: LlmInference = LlmManager.getInstance(context)
    private val llmInference: LlmInference? by lazy { LlmManager.safeGetInstance(context) }

    private var motionStorage: MotionStorage? = null
    private var fileStorage: FileStorage? = null


    // ---------- ORIGINAL CODE --------------
//    suspend fun performFusion(): String = withContext(Dispatchers.IO) {
//        try {
//            motionStorage = MotionStorage(context)
//            fileStorage = FileStorage(context)
//
//            val motionHistory = motionStorage?.getMotionHistory() ?: "No motion data"
//            val locationHistory = fileStorage?.getLastResponse() ?: "No location data"
//
//            val truncatedMotion = motionHistory.takeLast(200)
//            val truncatedLocation = locationHistory.takeLast(200)
//
//            val prompt = """
//                Given the following data, describe the most likely activity in exactly 20 words:
//                Motion: $truncatedMotion
//                Location: $truncatedLocation
//            """.trimIndent()
//
//            Log.d(TAG, "Sending fusion prompt: $prompt")
//
//            val response = try {
//                llmInference.generateResponse(prompt)
//            } catch (e: Exception) {
//                Log.e(TAG, "Error generating LLM response", e)
//                "Fusion analysis failed: ${e.message}"
//            }
//
//            Log.d(TAG, "Received fusion response: $response")
//            response
//
//        } catch (e: Exception) {
//            Log.e(TAG, "Error during fusion analysis", e)
//            "Error during fusion: ${e.message}"
//        }
//    }


    suspend fun performFusion(): String = withContext(Dispatchers.IO) {
        try {
            val loc = getBestLocation(context)
            if (loc == null) return@withContext "Fusion: location unavailable. Turn on Location and retry."

            val ssids: List<String> = try {
                WifiScanner(context).getWifiNetworks()
            } catch (_: Exception) { emptyList() }

            // --- ORIGINAL CODE ----
//            val ssids = try {
//                WifiScanner(context).scanNetworks()
//            } catch (_: Exception) {
//                emptyList()
//            }

            // If you fetch a static map / reverse-geocode, make those calls nullable and check:
             // val mapBmp = mapsClient.fetchStaticMapOrNull(loc)
            val mapBmp: Any? = null // make this return null on error
            // val place = placesClient.reverseGeocodeOrNull(loc) // if you do this

            // Build a robust prompt even with missing pieces
            val prompt = buildString {
                appendLine("Fuse context from sensors:")
                appendLine("- Location: ${loc.latitude}, ${loc.longitude}")
                if (ssids.isEmpty()) appendLine("- Wi-Fi: (none visible)") else {
                    appendLine("- Wi-Fi SSIDs:")
                    ssids.take(10).forEach { appendLine("  • $it") }
                }
                if (mapBmp == null) appendLine("- Map: unavailable")
                appendLine("Give a 50-word summary of likely place and activity.")
            }

            // Use LlmProvider for API-first with on-device fallback
            val response = try {
                LlmProvider.generateResponse(context, prompt)
            } catch (e: Exception) {
                Log.e("ContextFusionAnalyzer", "LLM generate failed", e)
                "Failed to generate LLM response: ${e.message}"
            }
            response
        } catch (e: Exception) {
            "Fusion failed: ${e.message}"
        }
    }

        override fun close() {
        try {
            // No need to close LLM instance as it's managed by LlmManager
            motionStorage = null
            fileStorage = null
        } catch (e: Exception) {
            Log.e(TAG, "Error during cleanup", e)
        }
    }
}
