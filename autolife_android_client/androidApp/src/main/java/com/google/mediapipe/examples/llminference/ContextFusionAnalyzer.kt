package com.google.mediapipe.examples.llminference

import android.content.Context
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import com.autolife.shared.ai.AiClientProvider
import com.autolife.shared.analyzer.PromptBuilder
import java.io.Closeable

class ContextFusionAnalyzer(private val context: Context) : Closeable {
    companion object {
        private const val TAG = "ContextFusionAnalyzer"
    }

    suspend fun performFusion(motionHistory: String, locationContext: String): String = withContext(Dispatchers.IO) {
        try {
            val prompt = PromptBuilder.buildFusionPrompt(motionHistory, locationContext)

            Log.d(TAG, "Sending fusion prompt to Gemini...")
            val response = AiClientProvider.client.generate(prompt)
            Log.d(TAG, "Received fusion response: $response")
            
            response
        } catch (e: Exception) {
            "Fusion failed: ${e.message}"
        }
    }

    override fun close() {
    }
}
