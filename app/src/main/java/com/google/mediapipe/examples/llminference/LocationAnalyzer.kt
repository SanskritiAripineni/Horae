package com.google.mediapipe.examples.llminference

//import android.content.Context
//import android.util.Log
//import com.google.mediapipe.tasks.genai.llminference.LlmInference
//import java.io.Closeable
//import android.os.Build
//import java.io.File

import android.annotation.SuppressLint
import android.content.Context
import android.location.Location
import android.os.Build
import android.util.Log
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.google.android.gms.tasks.CancellationTokenSource
import com.google.mediapipe.tasks.genai.llminference.LlmInference
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import java.io.Closeable
import java.io.File


//
//import android.content.Context
//import android.util.Log
//import com.google.mediapipe.tasks.genai.llminference.LlmInference
//import java.io.Closeable
//import android.os.Build
//import java.io.File
//import android.annotation.SuppressLint
//import android.location.Location
//import com.google.android.gms.location.FusedLocationProviderClient
//import com.google.android.gms.location.LocationRequest
//import com.google.android.gms.location.LocationServices
//import com.google.android.gms.location.Priority
//import com.google.android.gms.tasks.CancellationTokenSource
//import kotlinx.coroutines.tasks.await
//import kotlinx.coroutines.withTimeout

@SuppressLint("MissingPermission")
suspend fun getBestLocation(context: Context): Location? {
    val fusedClient = LocationServices.getFusedLocationProviderClient(context)

    // Try to get a fresh fix within 6 seconds
    try {
        val fresh = withTimeout(6000) {
            fusedClient.getCurrentLocation(
                Priority.PRIORITY_HIGH_ACCURACY,
                CancellationTokenSource().token
            ).await()
        }
        if (fresh != null) return fresh
    } catch (_: Exception) {
        // ignore timeout
    }

    // Fallback to last known location
    return try {
        fusedClient.lastLocation.await()
    } catch (_: Exception) {
        null
    }
}


class LocationAnalyzer(private val context: Context) : Closeable {
    companion object {
        private const val TAG = "LocationAnalyzer"
    }

    private val fileStorage = FileStorage(context)

    // Suspend function to ensure LLM loads on background thread
    suspend fun analyzeLocation(ssids: List<String>): String = withContext(Dispatchers.IO) {
        val prompt = """
            Based on the following WiFi network names, analyze where this location might be(response in summary within 50 words:
            ${ssids.joinToString("\n")}
            Provide a brief analysis of the likely location.
        """.trimIndent()

        Log.d(TAG, "Sending prompt to LLM:")
        Log.d(TAG, prompt)

        // Load LLM on background thread
        val engine = LlmManager.safeGetInstance(context) ?: return@withContext "On-device LLM unavailable (model/runtime mismatch)."

        val response = try {
            engine.generateResponse(prompt)
        } catch (e: Exception) {
            Log.e("LocationAnalyzer", "LLM generate failed", e)
            "Failed to generate LLM response: ${e.message}"
        }

//        val response = try {
//            llmInference.generateResponse(prompt)
//        } catch (e: Exception) {
//            Log.e(TAG, "Error generating LLM response", e)
//            throw IllegalStateException("Failed to generate LLM response: ${e.message}")
//        }

        Log.d(TAG, "Location, Received response from LLM:")
        Log.d(TAG, response)

        // Save the response to file
        fileStorage.saveLLMResponse(response)

        response
    }

    /**
     * Gets the last saved LLM analysis response
     * @return The last saved response or null if none exists
     */
    fun getLastAnalysis(): String? {
        return fileStorage.getLastResponse()
    }

    /**
     * Clears any previously saved analysis results
     * @return true if successfully cleared, false otherwise
     */
    fun clearAnalysisHistory(): Boolean {
        return fileStorage.clearResponses()
    }

    override fun close() {
        // No need to close LLM instance here as it's managed by LlmManager
    }
}


object LlmManager {
    @Volatile private var llm: LlmInference? = null
    private val lock = Any()

    fun safeGetInstance(context: Context): LlmInference? = synchronized(lock) {
        llm ?: runCatching {
            // Use official Gemma 2 2B INT8 model from Google Kaggle
            val modelFile = File(
                context.getExternalFilesDir("models"),
                "gemma2-2b-it-cpu-int8.task" // Official Gemma 2 from Kaggle (no hyphen)
            )
            require(modelFile.exists() && modelFile.length() > 100_000_000L) {
                "Model not found or too small: ${modelFile.absolutePath}"
            }

            val opts = LlmInference.LlmInferenceOptions.builder()
                .setModelPath(modelFile.absolutePath)
                .setMaxTokens(512)
                .build()

            LlmInference.createFromOptions(context, opts).also { llm = it }
        }.getOrNull()
    }
}



// ----------------- LLM MANAGER FROM ORIGINAL REPO ---------------
// Add this singleton object in the same package
//object LlmManager {
//    private var llmInstance: LlmInference? = null
//    private val lock = Object()
//
////    private val g2 = "/data/local/tmp/llm/gemma-2b-it-gpu-int4.bin"
////    private val g22b = "/data/local/tmp/llm/gemma2-2b-gpu.bin"
////
////    private val fac = "/data/local/tmp/llm/falcon_gpu.bin"
////    private val stb = "/data/local/tmp/llm/stablelm_gpu.bin"
////    private val stb = "/data/local/tmp/llm/phi2_gpu.bin"
////    private val g7b = "/data/local/tmp/llm/gemma-1.1-7b-it-gpu-int8.bin"
//
//
//    fun getInstance(context: Context): LlmInference {
//        synchronized(lock) {
//            if (llmInstance == null) {
//                val options = LlmInference.LlmInferenceOptions.builder()
//                    .setModelPath("/data/local/tmp/llm/gemma-2b-it-gpu-int4.bin")
//                    .setMaxTokens(1024)
//                    .setTopK(20)  // Changed from setMaxTopK to setTopK
//                    .build()
//
//                llmInstance = LlmInference.createFromOptions(context, options)
//            }
//            return llmInstance!!
//        }
//    }
//
//}
//
