package com.google.mediapipe.examples.llminference

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.util.Log

/**
 * Unified LLM provider that uses Gemini API with on-device Gemma fallback.
 * 
 * Priority order:
 * 1. Gemini API (if API key configured and network available)
 * 2. On-device Gemma (fallback for offline or API failure)
 */
object LlmProvider {
    private const val TAG = "LlmProvider"
    
    /**
     * Generate a response using the best available LLM backend.
     * Tries Gemini API first, falls back to on-device Gemma if unavailable.
     */
    suspend fun generateResponse(context: Context, prompt: String): String {
        val apiKey = BuildConfig.GEMINI_API_KEY
        
        // Try Gemini API first if configured and online
        if (apiKey.isNotBlank() && isNetworkAvailable(context)) {
            Log.d(TAG, "Attempting Gemini API request")
            val result = GeminiApiClient.generateResponse(prompt, apiKey)
            
            if (result.isSuccess) {
                Log.d(TAG, "Gemini API request successful")
                return result.getOrThrow()
            } else {
                Log.w(TAG, "Gemini API failed, falling back to on-device LLM", 
                    result.exceptionOrNull())
            }
        } else {
            if (apiKey.isBlank()) {
                Log.d(TAG, "No API key configured, using on-device LLM")
            } else {
                Log.d(TAG, "No network available, using on-device LLM")
            }
        }
        
        // Fallback to on-device Gemma
        return generateOnDevice(context, prompt)
    }
    
    /**
     * Generate response using on-device Gemma model.
     */
    private fun generateOnDevice(context: Context, prompt: String): String {
        Log.d(TAG, "Using on-device Gemma model")
        val engine = LlmManager.safeGetInstance(context)
            ?: return "On-device LLM unavailable (model/runtime mismatch)"
        
        return try {
            engine.generateResponse(prompt)
        } catch (e: Exception) {
            Log.e(TAG, "On-device LLM failed", e)
            "Failed to generate response: ${e.message}"
        }
    }
    
    /**
     * Check if network is available for API calls.
     */
    private fun isNetworkAvailable(context: Context): Boolean {
        val connectivityManager = context.getSystemService(Context.CONNECTIVITY_SERVICE) 
            as ConnectivityManager
        val network = connectivityManager.activeNetwork ?: return false
        val capabilities = connectivityManager.getNetworkCapabilities(network) ?: return false
        
        return capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
               capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
    }
    
    /**
     * Check which backend will be used for inference.
     */
    fun getActiveBackend(context: Context): String {
        val apiKey = BuildConfig.GEMINI_API_KEY
        return when {
            apiKey.isNotBlank() && isNetworkAvailable(context) -> "Gemini API"
            LlmManager.safeGetInstance(context) != null -> "On-device Gemma"
            else -> "None available"
        }
    }
}
