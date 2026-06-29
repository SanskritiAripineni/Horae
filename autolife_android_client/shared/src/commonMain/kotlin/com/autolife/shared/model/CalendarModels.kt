package com.autolife.shared.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class CalendarSummary(
    val event_count: Int = 0,
    val task_count: Int = 0,
    val total_hours: Double = 0.0,
    val events: List<CalendarEvent> = emptyList(),
    val tasks: List<CalendarTask> = emptyList(),
    val busy_patterns: List<String> = emptyList()
)

@Serializable
data class CalendarEvent(
    val title: String = "",
    val start: String = "",
    val end: String = "",
    val duration_hours: Double = 0.0,
    val calendar: String = ""
)

@Serializable
data class CalendarTask(
    val title: String = "",
    val due: String? = null,
    val status: String? = null,
    @SerialName("list") val list_name: String? = null
)

@Serializable
data class ProposedChange(
    val title: String? = null,
    val start_time: String? = null,
    val end_time: String? = null,
    val description: String? = null,
    val category: String? = null,
    val duration_hours: Double? = null,
    val action: String? = null,
    val reason: String? = null,
    val source: String? = null,
    val user_timezone: String? = null,
    val change_token: String? = null,
    val event_id: String? = null
)
