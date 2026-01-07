package com.google.mediapipe.examples.llminference.data

import android.content.ContentValues
import android.content.Context
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.util.Log
import com.google.mediapipe.examples.llminference.AutoLifeApp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object DataExporter {
    private const val TAG = "DataExporter"

    suspend fun exportJournals(context: Context): Boolean = withContext(Dispatchers.IO) {
        try {
            val database = (context.applicationContext as AutoLifeApp).database
            val journals = database.logDao().getAllJournals()

            if (journals.isEmpty()) {
                Log.d(TAG, "No journals to export.")
                return@withContext false
            }

            val timestamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault()).format(Date())
            val fileName = "all_journals_$timestamp.txt"
            val formattedContent = formatJournals(journals)

            // 1. Export to Internal App Storage (Local Project Directory)
            val internalFile = exportToInternalStorage(context, fileName, formattedContent)
            Log.d(TAG, "Internal export: ${internalFile?.absolutePath}")

            // 2. Export to Public Download Folder
            val publicUri = exportToPublicDownloads(context, fileName, formattedContent)
            Log.d(TAG, "Public export: $publicUri")

            return@withContext internalFile != null || publicUri != null
        } catch (e: Exception) {
            Log.e(TAG, "Export failed", e)
            return@withContext false
        }
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

    private fun exportToPublicDownloads(context: Context, fileName: String, content: String): Uri? {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            // Use MediaStore for Android 10+
            val contentValues = ContentValues().apply {
                put(MediaStore.MediaColumns.DISPLAY_NAME, fileName)
                put(MediaStore.MediaColumns.MIME_TYPE, "text/plain")
                put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/AutoLife")
            }

            val resolver = context.contentResolver
            val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, contentValues)
            
            uri?.let {
                resolver.openOutputStream(it)?.use { outputStream ->
                    outputStream.write(content.toByteArray())
                }
            }
            uri
        } else {
            // Legacy way for older Android
            try {
                val downloadDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
                val autoLifeDir = File(downloadDir, "AutoLife")
                if (!autoLifeDir.exists()) autoLifeDir.mkdirs()
                
                val file = File(autoLifeDir, fileName)
                file.writeText(content)
                Uri.fromFile(file)
            } catch (e: Exception) {
                Log.e(TAG, "Public Download export failed (Legacy)", e)
                null
            }
        }
    }
}
