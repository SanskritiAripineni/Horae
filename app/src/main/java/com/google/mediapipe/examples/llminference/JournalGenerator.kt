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
            You are an AI assistant for the 'AutoLife' automatic journaling app.
            
            Task: Generate a persistent life journal entry for the last 15 minutes.
            
            Context Logs (Time: Activity, Location):
            $formattedLogs
            
            Instructions:
            1. Analyze the sequence of activities and locations.
            2. Infer the high-level activity (e.g., "Commuting to work", "Working at desk", "Jogging in the park").
            3. Write a natural language summary (3-4 sentences).
            4. Do not mention specific coordinates or SSID names unless relevant (e.g., "Starbucks").
            5. Remove subjective comments.
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
