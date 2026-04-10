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
import com.autolife.shared.analyzer.PromptBuilder
import com.autolife.shared.ai.AiClientProvider
import java.io.ByteArrayOutputStream
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

        val prompt = PromptBuilder.buildLocationAnalysisPrompt()

        Log.d(TAG, "Sending prompt to Gemini with Map Image: ${mapImage != null}")

        // Debug Update
        com.google.mediapipe.examples.llminference.data.DebugRepository.updateLocationMap(mapImage, loc?.latitude ?: 0.0, loc?.longitude ?: 0.0)
        com.google.mediapipe.examples.llminference.data.DebugRepository.updateLocationSSIDs(ssids)
        
        val response = if (mapImage != null) {
            val stream = ByteArrayOutputStream()
            mapImage.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, stream)
            val imageBytes = stream.toByteArray()
            AiClientProvider.client.generateWithImage(prompt, imageBytes)
        } else {
            // Fallback to text-only if map fails
            AiClientProvider.client.generate(PromptBuilder.buildLocationAnalysisPrompt() + "\n(Note: Map image processing failed, rely on SSIDs only.)")
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
