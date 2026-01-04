package com.google.mediapipe.examples.llminference

import android.annotation.SuppressLint
import android.content.Context
import android.location.Location
import android.os.Build
import android.util.Log
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.google.android.gms.tasks.CancellationTokenSource
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import java.io.Closeable
import java.io.File


@SuppressLint("MissingPermission")
suspend fun getBestLocation(context: Context): Location? {
    val fusedClient = LocationServices.getFusedLocationProviderClient(context)

    // Try to get a fresh fix within 6 seconds
    try {
        val fresh = withTimeout(6000) {
            fusedClient.getCurrentLocation(
                Priority.PRIORITY_HIGH_ACCURACY,
                CancellationTokenSource().token
            ).await()
        }
        if (fresh != null) return fresh
    } catch (_: Exception) {
        // ignore timeout
    }

    // Fallback to last known location
    return try {
        fusedClient.lastLocation.await()
    } catch (_: Exception) {
        null
    }
}


class LocationAnalyzer(private val context: Context) : Closeable {
    companion object {
        private const val TAG = "LocationAnalyzer"
    }

    private val fileStorage = FileStorage(context)

    // Suspend function to ensure LLM loads on background thread
    suspend fun analyzeLocation(ssids: List<String>): String = withContext(Dispatchers.IO) {
        // 1. Get current location for Map
        val loc = getBestLocation(context)
        val mapImage = if (loc != null) {
            MapImageProvider().getMapImage(loc.latitude, loc.longitude)
        } else {
            null
        }

        val ssidList = if (ssids.isEmpty() || (ssids.size == 1 && ssids[0].contains("No visible"))) {
             "(None detected)"
        } else {
            ssids.joinToString(", ")
        }

        val prompt = """
            You are an AI assistant for the 'AutoLife' automatic journaling app.
            
            Task: Infer the user's specific location context (e.g., 'Residential Home', 'City Park', 'Office Building', 'Coffee Shop').
            
            Input Data:
            1. Nearby WiFi SSIDs: $ssidList
            2. Satellite/Map View of the current location (attached image).
            
            Instructions:
            - Analyze the map image for visual cues (building density, green spaces, road types).
            - Analyze the SSIDs for semantic clues (e.g., 'Starbucks_Free', 'Corporate_Guest').
            - Fuse these to predict the most likely venue type or specific place.
            - Output ONLY a concise 1-sentence description.
        """.trimIndent()

        Log.d(TAG, "Sending prompt to Gemini with Map Image: ${mapImage != null}")

        // Debug Update
        com.google.mediapipe.examples.llminference.data.DebugRepository.updateLocationMap(mapImage)
        com.google.mediapipe.examples.llminference.data.DebugRepository.updateLocationSSIDs(ssids)
        
        val response = if (mapImage != null) {
            GeminiClient.generateResponse(prompt, mapImage)
        } else {
            // Fallback to text-only if map fails
            GeminiClient.generateResponse(prompt + "\n(Note: Map image processing failed, rely on SSIDs only.)")
        }

        Log.d(TAG, "Received response from Gemini: $response")
        
        com.google.mediapipe.examples.llminference.data.DebugRepository.updateLocationInference(response)

        // Save the response to file (legacy support)
        fileStorage.saveLLMResponse(response)

        response
    }

    /**
     * Gets the last saved LLM analysis response
     * @return The last saved response or null if none exists
     */
    fun getLastAnalysis(): String? {
        return fileStorage.getLastResponse()
    }

    /**
     * Clears any previously saved analysis results
     * @return true if successfully cleared, false otherwise
     */
    fun clearAnalysisHistory(): Boolean {
        return fileStorage.clearResponses()
    }

    override fun close() {
    }
}
