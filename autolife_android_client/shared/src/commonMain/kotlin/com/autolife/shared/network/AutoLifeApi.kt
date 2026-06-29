package com.autolife.shared.network

import com.autolife.shared.model.*
import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.plugins.logging.LogLevel
import io.ktor.client.plugins.logging.Logging
import io.ktor.client.plugins.HttpTimeout
import io.ktor.client.request.get
import io.ktor.client.request.header
import io.ktor.client.request.parameter
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.json.Json

/**
 * Cross-platform API client for the AutoLife backend.
 * Uses Ktor — works on Android (OkHttp engine) and iOS (Darwin engine).
 * Call [init] once at app startup with the backend base URL.
 */
object AutoLifeApi {

    private var _client: HttpClient? = null
    private var _baseUrl: String = ""
    private var _authToken: String? = null

    val isInitialized: Boolean get() = _client != null

    fun setAuthToken(token: String?) {
        _authToken = token
    }

    fun init(baseUrl: String) {
        _baseUrl = baseUrl.trimEnd('/')
        _client = HttpClient {
            install(ContentNegotiation) {
                json(Json {
                    ignoreUnknownKeys = true
                    isLenient = true
                    encodeDefaults = true
                })
            }
            install(Logging) {
                level = LogLevel.INFO
            }
            install(HttpTimeout) {
                requestTimeoutMillis = 120_000
                connectTimeoutMillis = 15_000
                socketTimeoutMillis = 120_000
            }
        }
    }

    private val client: HttpClient
        get() = _client ?: error("AutoLifeApi not initialized. Call init(baseUrl) first.")

    suspend fun enroll(request: EnrollRequest): EnrollResponse {
        return client.post("$_baseUrl/api/enroll") {
            contentType(ContentType.Application.Json)
            setBody(request)
        }.body()
    }

    suspend fun processJournals(request: ProcessJournalsRequest): ProcessJournalsResponse {
        return client.post("$_baseUrl/api/process_journals") {
            contentType(ContentType.Application.Json)
            _authToken?.let { header("Authorization", "Bearer $it") }
            setBody(request)
        }.body()
    }

    suspend fun applyCalendar(request: ApplyCalendarRequest): ApplyCalendarResponse {
        return client.post("$_baseUrl/api/apply_calendar") {
            contentType(ContentType.Application.Json)
            _authToken?.let { header("Authorization", "Bearer $it") }
            setBody(request)
        }.body()
    }

    suspend fun getMemory(userId: String = "default"): UserMemoryData {
        return client.get("$_baseUrl/api/memory") {
            _authToken?.let { header("Authorization", "Bearer $it") }
            parameter("user_id", userId)
        }.body()
    }

    suspend fun getOAuthAuthorizeUrl(userId: String = "default"): OAuthAuthorizeResponse {
        return client.get("$_baseUrl/api/oauth/authorize") {
            _authToken?.let { header("Authorization", "Bearer $it") }
            parameter("user_id", userId)
        }.body()
    }

    suspend fun getOAuthStatus(userId: String = "default"): OAuthStatusResponse {
        return client.get("$_baseUrl/api/oauth/status") {
            _authToken?.let { header("Authorization", "Bearer $it") }
            parameter("user_id", userId)
        }.body()
    }
}
