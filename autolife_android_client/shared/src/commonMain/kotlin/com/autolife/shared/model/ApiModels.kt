package com.autolife.shared.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// ── Request models ──────────────────────────────────────────────────

@Serializable
data class ApiJournalEntry(
    val id: String,
    val entry_number: Int,
    val created_at: String,
    val period: String,
    val content: String,
    val timestamp: String
)

@Serializable
data class ProcessJournalsRequest(
    val journals: List<ApiJournalEntry>,
    val user_id: String = "default"
)

@Serializable
data class ApplyCalendarRequest(
    val changes: List<ProposedChange>,
    val user_comments: String = "",
    val user_id: String = "default"
)

// ── Response models ─────────────────────────────────────────────────

@Serializable
data class MentalHealthAssessment(
    val estimated_phq4: Int = 0,
    val risk_level: String = "unknown",
    val key_concerns: List<String> = emptyList(),
    val positive_indicators: List<String> = emptyList()
)

@Serializable
data class Recommendation(
    val category: String = "",
    val action: String = "",
    @SerialName("when") val when_to_do: String? = null,
    val priority: String? = null,
    val mechanism: String? = null,
    val source: String? = null
)

@Serializable
data class ProcessJournalsResponse(
    val status: String = "",
    val user_id: String = "",
    val journal_summary: String? = null,
    val mental_health: MentalHealthAssessment? = null,
    val recommendations: List<Recommendation> = emptyList(),
    val calendar_summary: CalendarSummary? = null,
    val proposed_changes: List<ProposedChange> = emptyList(),
    val errors: List<String> = emptyList()
)

@Serializable
data class ApplyCalendarResponse(
    val applied: List<ProposedChange> = emptyList(),
    val failed: List<ProposedChange> = emptyList(),
    val skipped: List<ProposedChange> = emptyList()
)

// ── Memory models ───────────────────────────────────────────────────

@Serializable
data class UserMemoryData(
    val user_id: String = "",
    val preferences: UserPrefs = UserPrefs(),
    val mental_health: MemoryHealthSummary = MemoryHealthSummary()
)

@Serializable
data class UserPrefs(
    val goals: List<String> = emptyList(),
    val work_hours: List<Int> = listOf(9, 17),
    val preferred_interventions: List<String> = emptyList(),
    val max_daily_hours: Double = 8.0
)

@Serializable
data class MemoryHealthSummary(
    val latest_phq4: Int? = null,
    val risk_level: String = "unknown",
    val trend: String = "stable",
    val history: List<HealthHistoryEntry> = emptyList()
)

@Serializable
data class HealthHistoryEntry(
    val total: Int = 0,
    val risk_level: String = "unknown",
    val timestamp: String = ""
)
