package com.google.mediapipe.examples.llminference.network

import com.google.mediapipe.examples.llminference.BuildConfig
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import java.util.concurrent.TimeUnit

// Request Models
data class ApiJournalEntry(
    val id: String,
    val entry_number: Int,
    val created_at: String,
    val period: String,
    val content: String,
    val timestamp: String
)

data class ProcessJournalsRequest(
    val journals: List<ApiJournalEntry>,
    val user_id: String = "default"
)

data class ApplyCalendarRequest(
    val changes: List<Map<String, Any>>,
    val user_comments: String = ""
)

// Response Models
data class MentalHealthAssessment(
    val estimated_phq4: Int,
    val risk_level: String,
    val key_concerns: List<String>,
    val positive_indicators: List<String>
)

data class Recommendation(
    val category: String,
    val action: String,
    val when_to_do: String? = null,
    val priority: String? = null,
    val mechanism: String? = null,
    val source: String? = null
)

data class ProcessJournalsResponse(
    val status: String,
    val user_id: String,
    val journal_summary: String?,
    val mental_health: MentalHealthAssessment?,
    val recommendations: List<Recommendation>,
    val calendar_summary: Map<String, Any>?,
    val proposed_changes: List<Map<String, Any>>,
    val errors: List<String>
)

data class ApplyCalendarResponse(
    val applied: List<Map<String, Any>>,
    val failed: List<Map<String, Any>>,
    val skipped: List<Map<String, Any>>
)

// Memory response models (GET /api/memory)
data class UserMemoryData(
    val user_id: String,
    val preferences: UserPrefs,
    val mental_health: MemoryHealthSummary
)

data class UserPrefs(
    val goals: List<String> = emptyList(),
    val work_hours: List<Int> = listOf(9, 17),
    val preferred_interventions: List<String> = emptyList(),
    val max_daily_hours: Double = 8.0
)

data class MemoryHealthSummary(
    val latest_phq4: Int? = null,
    val risk_level: String = "unknown",
    val trend: String = "stable",
    val history: List<HealthHistoryEntry> = emptyList()
)

data class HealthHistoryEntry(
    val total: Int,
    val risk_level: String,
    val timestamp: String
)

interface BackendApiService {
    @POST("/api/process_journals")
    suspend fun processJournals(@Body request: ProcessJournalsRequest): ProcessJournalsResponse

    @POST("/api/apply_calendar")
    suspend fun applyCalendar(@Body request: ApplyCalendarRequest): ApplyCalendarResponse

    @GET("/api/memory")
    suspend fun getMemory(@Query("user_id") userId: String = "default"): UserMemoryData
}

object BackendApiClient {
    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BODY
    }

    private val okHttpClient = OkHttpClient.Builder()
        .addInterceptor(loggingInterceptor)
        .connectTimeout(60, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .build()

    val retrofit: Retrofit = Retrofit.Builder()
        .baseUrl(BuildConfig.BACKEND_URL)
        .client(okHttpClient)
        .addConverterFactory(GsonConverterFactory.create())
        .build()

    val apiService: BackendApiService = retrofit.create(BackendApiService::class.java)
}
