package com.google.mediapipe.examples.llminference

import android.content.Context
import android.util.Log
import com.google.mediapipe.examples.llminference.data.JournalEntry
import com.google.mediapipe.examples.llminference.data.SensorLog
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class JournalGenerator(private val context: Context) {
    companion object {
        private const val TAG = "JournalGenerator"
    }

    private val logDao = (context.applicationContext as AutoLifeApp).database.logDao()

    suspend fun tryGenerateJournal(endTime: Long, periodDurationMs: Long): Boolean = withContext(Dispatchers.IO) {
        val startTime = endTime - periodDurationMs
        
        Log.d(TAG, "Attempting to generate journal for period: $startTime to $endTime")

        val logs = logDao.getLogsBetween(startTime, endTime)
        
        if (logs.isEmpty()) {
            Log.d(TAG, "No logs found for this period. Skipping journal.")
            return@withContext false
        }

        // Filter and format logs
        // Paper mentions: "[time-1](motion, location), ..."
        // We will approximate this by groupping logs by minute
        val formattedLogs = formatLogsForPrompt(logs)

       val prompt = """
        You are an AI Life Journaling Assistant.
        Your goal is to write a semantic, objective, and accurate daily journal based on the user's context logs.

        Input:
        A list of context logs in the format: [timestamp] [context description]
        $formattedLogs

        Instructions:
        1. Synthesize the logs into a coherent narrative.
        2. Identify high-level activities (e.g., "dining out", "working", "commuting") from the low-level signals.
        3. Remove any subjective comments (e.g., avoid "The user had a productive day" or "It was a relaxing evening"). Stick to factual descriptions of behavior and context.
        4. Be concise.

        Example Journal Style:
        "In the morning, the user spent time at a local library, likely reading and researching. Around noon, the user visited a restaurant in the city center..."

        Generate the journal now.
    """.trimIndent()

        Log.d(TAG, "Sending journal prompt to Gemini...")
        val journalContent = GeminiClient.generateResponse(prompt)
        Log.d(TAG, "Generated journal: $journalContent")
        
        com.google.mediapipe.examples.llminference.data.DebugRepository.updateLastJournal(journalContent)

        logDao.insertJournal(
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
