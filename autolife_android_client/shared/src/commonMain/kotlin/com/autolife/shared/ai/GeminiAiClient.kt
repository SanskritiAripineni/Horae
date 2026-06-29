package com.autolife.shared.ai

import io.ktor.client.*
import io.ktor.client.plugins.HttpTimeout
import io.ktor.client.request.*
import io.ktor.client.statement.*
import io.ktor.http.*
import kotlinx.coroutines.delay
import kotlinx.serialization.json.*
import kotlin.io.encoding.Base64
import kotlin.io.encoding.ExperimentalEncodingApi

/**
 * Cross-platform [AiClient] backed by the Gemini REST API via Ktor.
 */
class GeminiAiClient(private val apiKey: String) : AiClient {

    private val client = HttpClient {
        install(HttpTimeout) {
            requestTimeoutMillis = 30_000
            connectTimeoutMillis = 10_000
            socketTimeoutMillis = 30_000
        }
    }
    private val json = Json { ignoreUnknownKeys = true }
    private val modelName = "gemini-2.0-flash-lite"
    private val baseUrl = "https://generativelanguage.googleapis.com/v1beta/models"
    private val defaultGenerationConfig = buildJsonObject {
        put("temperature", 0.7)
        put("topK", 40)
        put("topP", 0.95)
        put("maxOutputTokens", 1024)
    }
    private val imageGenerationConfig = buildJsonObject {
        put("temperature", 0.2)
        put("topK", 20)
        put("topP", 0.8)
        put("maxOutputTokens", 256)
    }

    override suspend fun generate(prompt: String): String {
        requireUsableApiKey()
        val body = buildJsonObject {
            putJsonArray("contents") {
                addJsonObject {
                    putJsonArray("parts") {
                        addJsonObject { put("text", prompt) }
                    }
                }
            }
            put("generationConfig", defaultGenerationConfig)
        }
        val response = postWithRetry(body)
        return extractText(response.bodyAsText())
    }

    @OptIn(ExperimentalEncodingApi::class)
    override suspend fun generateWithImage(prompt: String, imageBytes: ByteArray): String {
        requireUsableApiKey()
        val b64 = Base64.encode(imageBytes)
        val body = buildJsonObject {
            putJsonArray("contents") {
                addJsonObject {
                    putJsonArray("parts") {
                        addJsonObject {
                            putJsonObject("inlineData") {
                                put("mimeType", "image/jpeg")
                                put("data", b64)
                            }
                        }
                        addJsonObject { put("text", prompt) }
                    }
                }
            }
            put("generationConfig", imageGenerationConfig)
        }
        val response = postWithRetry(body)
        return extractText(response.bodyAsText())
    }

    override fun close() {
        client.close()
    }

    private fun extractText(responseBody: String): String {
        val obj = json.parseToJsonElement(responseBody).jsonObject
        obj["error"]?.jsonObject?.get("message")?.jsonPrimitive?.contentOrNull?.let { message ->
            throw IllegalStateException("Gemini request failed: $message")
        }
        return obj["candidates"]
            ?.jsonArray?.firstOrNull()
            ?.jsonObject?.get("content")
            ?.jsonObject?.get("parts")
            ?.jsonArray?.firstOrNull()
            ?.jsonObject?.get("text")
            ?.jsonPrimitive?.content
            ?.takeIf { it.isNotBlank() }
            ?: throw IllegalStateException("Gemini returned no text")
    }

    private suspend fun postWithRetry(body: JsonObject): HttpResponse {
        var lastError: Throwable? = null
        repeat(3) { attempt ->
            try {
                val response = client.post("$baseUrl/$modelName:generateContent") {
                    parameter("key", apiKey)
                    contentType(ContentType.Application.Json)
                    setBody(body.toString())
                }
                if (response.status.value !in 500..599 && response.status.value != 429) {
                    return response
                }
                lastError = IllegalStateException("Gemini returned HTTP ${response.status.value}")
            } catch (t: Throwable) {
                lastError = t
            }
            if (attempt < 2) delay(500L * (1L shl attempt))
        }
        throw IllegalStateException("Gemini request failed after retries", lastError)
    }

    private fun requireUsableApiKey() {
        val trimmed = apiKey.trim()
        require(trimmed.isNotEmpty() && !trimmed.startsWith("$(")) {
            "Gemini API key is not configured for this build"
        }
    }
}
