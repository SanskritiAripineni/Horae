package com.google.mediapipe.examples.llminference

import android.content.Context
import android.util.Log
import com.autolife.shared.model.JournalEntry
import com.autolife.shared.model.SensorLog
import com.autolife.shared.db.DatabaseRepository
import com.autolife.shared.analyzer.PromptBuilder
import com.autolife.shared.ai.AiClientProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class JournalGenerator(private val context: Context) {
    companion object {
        private const val TAG = "JournalGenerator"
    }

    suspend fun tryGenerateJournal(endTime: Long, periodDurationMs: Long): Boolean = withContext(Dispatchers.IO) {
        val startTime = endTime - periodDurationMs
        
        Log.d(TAG, "Attempting to generate journal for period: $startTime to $endTime")

        val logs = DatabaseRepository.getLogsBetween(startTime, endTime)
        
        if (logs.isEmpty()) {
            Log.d(TAG, "No logs found for this period. Skipping journal.")
            return@withContext false
        }

        // Filter and format logs
        // Paper mentions: "[time-1](motion, location), ..."
        // We will approximate this by groupping logs by minute
        val formattedLogs = formatLogsForPrompt(logs)

        val prompt = PromptBuilder.buildJournalPrompt(formattedLogs)

        Log.d(TAG, "Sending journal prompt to Gemini...")
        val journalContent = AiClientProvider.client.generate(prompt)
        Log.d(TAG, "Generated journal: $journalContent")
        
        com.google.mediapipe.examples.llminference.data.DebugRepository.updateLastJournal(journalContent)

        DatabaseRepository.insertJournal(
            JournalEntry(
                createdTimestamp = System.currentTimeMillis(),
                periodStart = startTime,
                periodEnd = endTime,
                content = journalContent
            )
        )
        true
    }

    private fun formatLogsForPrompt(logs: List<SensorLog>): String {
        return logs.joinToString(separator = "\n") { log ->
            val time = java.text.SimpleDateFormat("HH:mm", java.util.Locale.getDefault()).format(java.util.Date(log.timestamp))
            "[$time] (${log.type}): ${log.content}"
        }
    }
}
