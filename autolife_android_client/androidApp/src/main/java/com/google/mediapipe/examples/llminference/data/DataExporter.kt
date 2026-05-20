package com.google.mediapipe.examples.llminference.data

import android.content.Context
import android.util.Log
import com.autolife.shared.db.DatabaseRepository
import com.autolife.shared.model.JournalEntry
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object DataExporter {
    private const val TAG = "DataExporter"

    suspend fun exportJournals(context: Context): Boolean = withContext(Dispatchers.IO) {
        try {
            val journals = DatabaseRepository.getAllJournals()

            if (journals.isEmpty()) {
                Log.d(TAG, "No journals to export.")
                return@withContext false
            }

            val timestamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault()).format(Date())
            val fileName = "all_journals_$timestamp.txt"
            val formattedContent = formatJournals(journals)

            val internalFile = exportToInternalStorage(context, fileName, formattedContent)
            Log.d(TAG, "Internal export: ${internalFile?.absolutePath}")

            return@withContext internalFile != null
        } catch (e: Exception) {
            Log.e(TAG, "Export failed", e)
            return@withContext false
        }
    }

    suspend fun exportBatteryReport(context: Context, content: String): Boolean = withContext(Dispatchers.IO) {
        exportText(
            context = context,
            fileNamePrefix = "battery_assessment",
            content = content,
        )
    }

    private fun formatJournals(journals: List<JournalEntry>): String {
        val sb = StringBuilder()
        val dateFormat = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault())

        journals.forEachIndexed { index, journal ->
            val createdDate = dateFormat.format(Date(journal.createdTimestamp))
            val periodStartDate = dateFormat.format(Date(journal.periodStart))
            val periodEndDate = dateFormat.format(Date(journal.periodEnd))

            sb.append("========================================\n")
            sb.append("JOURNAL ENTRY #${index + 1}\n")
            sb.append("Created At: $createdDate\n")
            sb.append("Period: $periodStartDate TO $periodEndDate\n")
            sb.append("----------------------------------------\n\n")
            sb.append(journal.content)
            sb.append("\n\n")
        }
        return sb.toString()
    }

    private fun exportToInternalStorage(context: Context, fileName: String, content: String): File? {
        return try {
            val exportDir = File(context.filesDir, "AutoLifeExports")
            if (!exportDir.exists()) exportDir.mkdirs()
            
            val file = File(exportDir, fileName)
            file.writeText(content)
            file
        } catch (e: Exception) {
            Log.e(TAG, "Internal storage export failed", e)
            null
        }
    }

    private suspend fun exportText(
        context: Context,
        fileNamePrefix: String,
        content: String,
    ): Boolean = withContext(Dispatchers.IO) {
        return@withContext try {
            val timestamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault()).format(Date())
            val fileName = "${fileNamePrefix}_$timestamp.md"
            val internalFile = exportToInternalStorage(context, fileName, content)
            internalFile != null
        } catch (e: Exception) {
            Log.e(TAG, "Text export failed", e)
            false
        }
    }
}
