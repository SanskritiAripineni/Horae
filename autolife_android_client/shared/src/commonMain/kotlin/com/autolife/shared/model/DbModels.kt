package com.autolife.shared.model

import kotlinx.serialization.Serializable

@Serializable
data class SensorLog(
    val id: Long = 0,
    val timestamp: Long,
    val type: String,
    val content: String
)

@Serializable
data class JournalEntry(
    val id: Long = 0,
    val createdTimestamp: Long,
    val periodStart: Long,
    val periodEnd: Long,
    val content: String
)
