package com.google.mediapipe.examples.llminference

import android.content.Context
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.Closeable

class ContextFusionAnalyzer(private val context: Context) : Closeable {
    companion object {
        private const val TAG = "ContextFusionAnalyzer"
    }

    suspend fun performFusion(): String = withContext(Dispatchers.IO) {
        try {
            val loc = getBestLocation(context)
            if (loc == null) return@withContext "Fusion: location unavailable. Turn on Location and retry."

            val ssids: List<String> = try {
                WifiScanner(context).getWifiNetworks()
            } catch (_: Exception) { emptyList() }

            val prompt = buildString {
                appendLine("You are an AI assistant for the 'AutoLife' automatic journaling app.")
                appendLine("Fuse the following sensor data to infer the user's current context (activity and place).")
                appendLine("- GPS Coordinates: ${loc.latitude}, ${loc.longitude}")
                if (ssids.isEmpty()) {
                    appendLine("- Nearby Wi-Fi: (none detected)")
                } else {
                    appendLine("- Nearby Wi-Fi SSIDs:")
                    ssids.take(10).forEach { appendLine("  • $it") }
                }
                appendLine("\nProvide a 50-word synthesis of the likely location and what the user is currently doing.")
            }

            Log.d(TAG, "Sending fusion prompt to Gemini...")
            val response = GeminiClient.generateResponse(prompt)
            Log.d(TAG, "Received fusion response: $response")
            
            response
        } catch (e: Exception) {
            "Fusion failed: ${e.message}"
        }
    }

    override fun close() {
    }
}
