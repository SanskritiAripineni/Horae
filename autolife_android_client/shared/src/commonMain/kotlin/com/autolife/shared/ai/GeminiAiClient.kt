package com.autolife.shared.ai

import io.ktor.client.*
import io.ktor.client.request.*
import io.ktor.client.statement.*
import io.ktor.http.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.*
import kotlin.io.encoding.Base64
import kotlin.io.encoding.ExperimentalEncodingApi

/**
 * Cross-platform [AiClient] backed by the Gemini REST API via Ktor.
 */
class GeminiAiClient(private val apiKey: String) : AiClient {

    private val client = HttpClient()
    private val json = Json { ignoreUnknownKeys = true }
    private val modelName = "gemini-2.0-flash-lite"
    private val baseUrl = "https://generativelanguage.googleapis.com/v1beta/models"

    override suspend fun generate(prompt: String): String {
        val body = buildJsonObject {
            putJsonArray("contents") {
                addJsonObject {
                    putJsonArray("parts") {
                        addJsonObject { put("text", prompt) }
                    }
                }
            }
            putJsonObject("generationConfig") {
                put("temperature", 0.7)
                put("topK", 40)
                put("topP", 0.95)
                put("maxOutputTokens", 1024)
            }
        }
        val response = client.post("$baseUrl/$modelName:generateContent") {
            parameter("key", apiKey)
            contentType(ContentType.Application.Json)
            setBody(body.toString())
        }
        return extractText(response.bodyAsText())
    }

    @OptIn(ExperimentalEncodingApi::class)
    override suspend fun generateWithImage(prompt: String, imageBytes: ByteArray): String {
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
            putJsonObject("generationConfig") {
                put("temperature", 0.7)
                put("topK", 40)
                put("topP", 0.95)
                put("maxOutputTokens", 1024)
            }
        }
        val response = client.post("$baseUrl/$modelName:generateContent") {
            parameter("key", apiKey)
            contentType(ContentType.Application.Json)
            setBody(body.toString())
        }
        return extractText(response.bodyAsText())
    }

    override fun close() {
        client.close()
    }

    private fun extractText(responseBody: String): String {
        val obj = json.parseToJsonElement(responseBody).jsonObject
        return obj["candidates"]
            ?.jsonArray?.firstOrNull()
            ?.jsonObject?.get("content")
            ?.jsonObject?.get("parts")
            ?.jsonArray?.firstOrNull()
            ?.jsonObject?.get("text")
            ?.jsonPrimitive?.content
            ?: "No response from Gemini"
    }
}
