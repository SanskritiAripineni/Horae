package com.google.mediapipe.examples.llminference

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * Client for Google's Gemini 2.5 Flash Lite API.
 * Provides fast cloud-based LLM inference as an alternative to on-device Gemma.
 */
object GeminiApiClient {
    private const val TAG = "GeminiApiClient"
    private const val BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    private const val MODEL = "gemini-2.0-flash-lite"
    
    private val client = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()
    
    /**
     * Generate a response from Gemini API.
     * @param prompt The text prompt to send
     * @param apiKey Your Gemini API key
     * @return Result containing the response text or an error
     */
    suspend fun generateResponse(prompt: String, apiKey: String): Result<String> = withContext(Dispatchers.IO) {
        if (apiKey.isBlank()) {
            return@withContext Result.failure(IllegalArgumentException("API key is empty"))
        }
        
        try {
            val requestBody = JSONObject().apply {
                put("contents", JSONArray().apply {
                    put(JSONObject().apply {
                        put("parts", JSONArray().apply {
                            put(JSONObject().apply {
                                put("text", prompt)
                            })
                        })
                    })
                })
                put("generationConfig", JSONObject().apply {
                    put("maxOutputTokens", 512)
                    put("temperature", 0.7)
                })
            }
            
            val url = "$BASE_URL/$MODEL:generateContent?key=$apiKey"
            
            val request = Request.Builder()
                .url(url)
                .post(requestBody.toString().toRequestBody("application/json".toMediaType()))
                .build()
            
            Log.d(TAG, "Sending request to Gemini API")
            val startTime = System.currentTimeMillis()
            
            val response = client.newCall(request).execute()
            val elapsed = System.currentTimeMillis() - startTime
            Log.d(TAG, "API response received in ${elapsed}ms")
            
            if (!response.isSuccessful) {
                val errorBody = response.body?.string() ?: "Unknown error"
                Log.e(TAG, "API error: ${response.code} - $errorBody")
                return@withContext Result.failure(
                    RuntimeException("API error ${response.code}: $errorBody")
                )
            }
            
            val responseBody = response.body?.string() ?: ""
            val jsonResponse = JSONObject(responseBody)
            
            // Extract text from response
            val text = jsonResponse
                .getJSONArray("candidates")
                .getJSONObject(0)
                .getJSONObject("content")
                .getJSONArray("parts")
                .getJSONObject(0)
                .getString("text")
            
            Log.d(TAG, "Generated response: ${text.take(100)}...")
            Result.success(text)
            
        } catch (e: Exception) {
            Log.e(TAG, "Request failed", e)
            Result.failure(e)
        }
    }
    
    /**
     * Check if API is available (has valid key and network)
     */
    fun isAvailable(apiKey: String): Boolean {
        return apiKey.isNotBlank()
    }
}
