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
        if (ssids.isEmpty() || (ssids.size == 1 && ssids[0].contains("No visible"))) {
             return@withContext "No WiFi networks available to analyze location."
        }

        val prompt = """
            You are an AI assistant for the 'AutoLife' automatic journaling app.
            Based on the following WiFi network names (SSIDs) nearby, infer the user's current location type or specific venue (e.g., 'Home', 'Office', 'Starbucks at 5th Ave', 'Airport Terminal').
            
            SSIDs:
            ${ssids.joinToString("\n")}
            
            Provide a concise, human-readable summary of the inferred location in 1-2 sentences.
        """.trimIndent()

        Log.d(TAG, "Sending prompt to Gemini...")
        val response = GeminiClient.generateResponse(prompt)

        Log.d(TAG, "Received response from Gemini: $response")

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
