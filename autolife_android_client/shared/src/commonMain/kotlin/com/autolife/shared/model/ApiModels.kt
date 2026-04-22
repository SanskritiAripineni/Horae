package com.autolife.shared.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

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
data class RawDayMarkers(
    val date: String,
    val sleep_onset_hour: Float? = null,
    val sleep_duration_hours: Float? = null,
    val sleep_regularity_index: Float? = null,
    val late_night_screen_min: Float? = null,
    val total_screen_min: Float? = null,
    val app_switching_rate: Float? = null,
    val mobility_entropy: Float? = null,
    val location_revisit_ratio: Float? = null,
    val social_rhythm_metric: Float? = null,
    val comm_reciprocity: Float? = null,
    val coverage: Map<String, Float>? = null,
)

@Serializable
data class ProcessJournalsRequest(
    val journals: List<ApiJournalEntry>,
    val raw_days: List<RawDayMarkers>? = null,
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
    val positive_indicators: List<String> = emptyList(),
    val behavioral_context: String = "",
)

@Serializable
data class SignalItem(
    val label: String = "",
    val detail: String? = null,
    val severity: String? = null,
)

@Serializable
data class SignalChip(
    val label: String = "",
    val kind: String = "neutral",
    val icon: String? = null,
)

@Serializable
data class UiSummary(
    val headline: String = "",
    val confidence_label: String = "",
    val summary: String = "",
    val evidence_chips: List<SignalChip> = emptyList(),
    val concerns: List<SignalItem> = emptyList(),
    val protective_signals: List<SignalItem> = emptyList(),
    val productive_signals: List<SignalItem> = emptyList(),
)

@Serializable
data class ResearchSource(
    val category: String = "",
    val content: String = "",
    val source: String = "",
)

@Serializable
data class AnalysisDetails(
    val journal_count: Int = 0,
    val duration_seconds: Double = 0.0,
    val behavioral_sensing: JsonElement? = null,
    val research_sources: List<ResearchSource> = emptyList(),
    val calendar_summary: CalendarSummary? = null,
    val tool_status: Map<String, String> = emptyMap(),
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
    val wellbeing: MentalHealthAssessment? = null,
    val ui_summary: UiSummary? = null,
    val analysis_details: AnalysisDetails? = null,
    val recommendations: List<Recommendation> = emptyList(),
    val calendar_summary: CalendarSummary? = null,
    val proposed_changes: List<ProposedChange> = emptyList(),
    val errors: List<String> = emptyList()
) {
    val health: MentalHealthAssessment?
        get() = mental_health ?: wellbeing
}

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
    val mental_health: MemoryHealthSummary? = null,
    val wellbeing: MemoryHealthSummary? = null
) {
    val health: MemoryHealthSummary
        get() = mental_health ?: wellbeing ?: MemoryHealthSummary()
}

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
