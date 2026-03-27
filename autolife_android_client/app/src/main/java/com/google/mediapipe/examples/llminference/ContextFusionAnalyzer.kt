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

    suspend fun performFusion(motionHistory: String, locationContext: String): String = withContext(Dispatchers.IO) {
        try {
            val prompt = """
            You are an intelligent life-logging assistant.
            Input:
            - Detected Motion (from sensors): $motionHistory
            - Location Context (from map analysis): $locationContext

            Task:
            1. Motion Calibration: Select the most probable motion given the location context.
            2. Present the result as a concise log entry.

            Format:
            [Motion Calibrated] in [Location Context]
            """.trimIndent()

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
