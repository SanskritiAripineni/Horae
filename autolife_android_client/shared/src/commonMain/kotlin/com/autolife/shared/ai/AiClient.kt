package com.autolife.shared.ai

/**
 * Cross-platform interface for generative AI interactions.
 * Android: backed by the Google Generative AI SDK.
 * iOS: backed by the shared Gemini REST client when remote AI is configured.
 */
interface AiClient {
    /** Generate a text response from a prompt. */
    suspend fun generate(prompt: String): String

    /** Generate a text response from a prompt + image (as raw bytes). */
    suspend fun generateWithImage(prompt: String, imageBytes: ByteArray): String

    /** Release any resources held by this client (e.g. HTTP connection pools). */
    fun close() {}
}

/**
 * Singleton holder for the platform-specific [AiClient].
 * Call [init] once at app startup.
 */
object AiClientProvider {
    private var _client: AiClient? = null

    val client: AiClient
        get() = _client ?: error("AiClient not initialized. Call AiClientProvider.init() first.")

    fun init(client: AiClient) {
        _client = client
    }

    fun shutdown() {
        _client?.close()
        _client = null
    }
}

/**
 * Fail-closed client for builds where remote AI is intentionally unavailable.
 */
class UnavailableAiClient(private val reason: String) : AiClient {
    override suspend fun generate(prompt: String): String {
        throw IllegalStateException(reason)
    }

    override suspend fun generateWithImage(prompt: String, imageBytes: ByteArray): String {
        throw IllegalStateException(reason)
    }
}
