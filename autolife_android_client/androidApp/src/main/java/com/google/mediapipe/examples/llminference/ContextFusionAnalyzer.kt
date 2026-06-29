package com.google.mediapipe.examples.llminference

import android.content.Context
import com.autolife.shared.ai.AiClientProvider
import com.autolife.shared.analyzer.PromptBuilder
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.Closeable

class ContextFusionAnalyzer(private val context: Context) : Closeable {
    suspend fun calibrateMotion(motionCandidates: List<String>, locationContext: String): String =
        withContext(Dispatchers.IO) {
            if (motionCandidates.size <= 1) {
                return@withContext motionCandidates.firstOrNull() ?: "stationary"
            }

            val response = runCatching {
                AiClientProvider.client.generate(
                    PromptBuilder.buildMotionCalibrationPrompt(motionCandidates, locationContext)
                )
            }.getOrNull()
            extractSummary(response) ?: motionCandidates.first()
        }

    private fun extractSummary(response: String?): String? {
        val text = response?.trim().orEmpty()
        if (text.isBlank()) return null
        val summaryLine = text.lineSequence().firstOrNull { it.trim().startsWith("Summary:", ignoreCase = true) }
        return summaryLine?.substringAfter(":")?.trim()?.takeIf { it.isNotBlank() } ?: text
    }

    override fun close() = Unit
}
