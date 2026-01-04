package com.google.mediapipe.examples.llminference

import com.google.ai.client.generativeai.GenerativeModel
import com.google.ai.client.generativeai.type.generationConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

object GeminiClient {
    private val apiKey = BuildConfig.GEMINI_API_KEY
    
    private val model = GenerativeModel(
        modelName = "gemini-2.5-flash-lite",
        apiKey = apiKey,
        generationConfig = generationConfig {
            temperature = 0.7f
            topK = 40
            topP = 0.95f
            maxOutputTokens = 1024
        }
    )

    suspend fun generateResponse(prompt: String): String = withContext(Dispatchers.IO) {
        try {
            val response = model.generateContent(prompt)
            response.text ?: "No response from Gemini"
        } catch (e: Exception) {
            "Error calling Gemini: ${e.message}"
        }
    }
}
