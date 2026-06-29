package com.google.mediapipe.examples.llminference

import android.content.Context
import android.util.Log
import java.io.File
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class FileStorage(private val context: Context) {
    companion object {
        private const val TAG = "FileStorage"
        private const val FILENAME = "llm_responses.txt"
    }

    private val file: File by lazy {
        File(context.filesDir, FILENAME)
    }

    /**
     * Saves the LLM response to a file, clearing previous content
     * @param response The LLM response to save
     * @return true if save was successful, false otherwise
     */
    fun saveLLMResponse(response: String): Boolean {
        return try {
            val timestamp = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault())
                .format(Date())
            val content = "[$timestamp]\n$response\n\n"
            file.writeText(content)

            Log.d(TAG, "Successfully saved LLM response to file")
            true
        } catch (e: IOException) {
            Log.e(TAG, "Error saving LLM response to file", e)
            false
        }
    }

    /**
     * Saves only when the semantic response changed, avoiding repeated churn from identical outputs.
     */
    fun saveLLMResponseIfChanged(response: String): Boolean {
        val previousResponse = extractSavedResponse(getLastResponse())
        if (previousResponse == response) {
            Log.d(TAG, "Skipping LLM response write because content is unchanged")
            return false
        }
        return saveLLMResponse(response)
    }

    /**
     * Reads the last saved LLM response from the file
     * @return The last saved response or null if no response exists or error occurs
     */
    fun getLastResponse(): String? {
        return try {
            if (!file.exists()) {
                Log.d(TAG, "No saved responses found")
                return null
            }

            val content = file.readText()
            if (content.isEmpty()) {
                Log.d(TAG, "File exists but is empty")
                return null
            }

            content
        } catch (e: IOException) {
            Log.e(TAG, "Error reading LLM response from file", e)
            null
        }
    }

    /**
     * Clears all saved responses from the file
     * @return true if clear was successful, false otherwise
     */
    fun clearResponses(): Boolean {
        return try {
            if (file.exists()) {
                file.writeText("")
                Log.d(TAG, "Successfully cleared saved responses")
                true
            } else {
                Log.d(TAG, "No file exists to clear")
                false
            }
        } catch (e: IOException) {
            Log.e(TAG, "Error clearing saved responses", e)
            false
        }
    }

    private fun extractSavedResponse(content: String?): String? {
        if (content.isNullOrBlank()) return null
        return content
            .lineSequence()
            .dropWhile { it.startsWith("[") && it.endsWith("]") }
            .joinToString("\n")
            .trim()
            .ifBlank { null }
    }
}
