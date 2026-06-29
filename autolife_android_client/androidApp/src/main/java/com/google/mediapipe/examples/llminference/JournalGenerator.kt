package com.google.mediapipe.examples.llminference

import android.content.Context
import android.util.Log
import com.autolife.shared.ai.AiClientProvider
import com.autolife.shared.analyzer.PromptBuilder
import com.autolife.shared.db.DatabaseRepository
import com.autolife.shared.model.ContextLogCodec
import com.autolife.shared.model.JournalEntry
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class JournalGenerator(private val context: Context) {
    companion object {
        private const val TAG = "JournalGenerator"
    }

    private val fingerprintStorage = JournalFingerprintStorage(context)

    suspend fun tryGenerateJournal(endTime: Long, periodDurationMs: Long): Boolean = withContext(Dispatchers.IO) {
        val startTime = endTime - periodDurationMs
        Log.d(TAG, "Attempting to generate journal for period: $startTime to $endTime")

        val contextLogs = DatabaseRepository.getLogsBetween(startTime, endTime)
            .filter { it.type == "CONTEXT" }
            .mapNotNull { ContextLogCodec.decode(it.content) }

        if (contextLogs.isEmpty()) {
            Log.d(TAG, "No context logs found for this period. Skipping journal.")
            return@withContext false
        }

        val refinedSegments = ContextLogRefiner.refine(contextLogs)
        if (refinedSegments.isEmpty()) {
            Log.d(TAG, "No refined segments after compression. Skipping journal.")
            return@withContext false
        }

        val fingerprint = ContextLogRefiner.fingerprint(refinedSegments)
        if (fingerprint == fingerprintStorage.get()) {
            Log.d(TAG, "Refined segments are unchanged since last journal. Skipping journal.")
            return@withContext false
        }

        val prompt = PromptBuilder.buildJournalPrompt(ContextLogRefiner.formatForPrompt(refinedSegments))
        val journalContent = runCatching { AiClientProvider.client.generate(prompt).trim() }
            .getOrElse { error ->
                Log.w(TAG, "Journal generation failed", error)
                return@withContext false
            }
            .takeIf { isGeneratedJournalContent(it) }
            ?: return@withContext false

        com.google.mediapipe.examples.llminference.data.DebugRepository.updateLastJournal(journalContent)
        DatabaseRepository.insertJournal(
            JournalEntry(
                createdTimestamp = System.currentTimeMillis(),
                periodStart = startTime,
                periodEnd = endTime,
                content = journalContent
            )
        )
        fingerprintStorage.set(fingerprint)
        true
    }

    private fun isGeneratedJournalContent(content: String): Boolean {
        if (content.isBlank()) return false
        val normalized = content.trim().lowercase()
        return normalized != "no response from gemini" &&
            normalized != "no response" &&
            !normalized.startsWith("gemini request failed")
    }
}
