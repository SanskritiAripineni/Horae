package com.autolife.composeapp.platform

import com.autolife.shared.model.ProcessJournalsResponse
import com.autolife.shared.model.UserMemoryData
import kotlinx.serialization.json.Json
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull

class ApiModelCompatibilityTest {

    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
    }

    @Test
    fun processJournalsResponseReadsBackendWellbeingField() {
        val response = json.decodeFromString<ProcessJournalsResponse>(
            """
            {
              "status": "completed",
              "user_id": "default",
              "journal_summary": "Sleep has been drifting later.",
              "wellbeing": {
                "risk_level": "mild",
                "key_concerns": ["late sleep"],
                "positive_indicators": ["daily walks"]
              },
              "recommendations": [],
              "proposed_changes": [],
              "errors": []
            }
            """.trimIndent()
        )

        val mentalHealth = assertNotNull(response.health)
        assertEquals("mild", mentalHealth.risk_level)
        assertEquals(listOf("late sleep"), mentalHealth.key_concerns)
        assertEquals(listOf("daily walks"), mentalHealth.positive_indicators)
    }

    @Test
    fun memoryResponseReadsBackendWellbeingField() {
        val memory = json.decodeFromString<UserMemoryData>(
            """
            {
              "preferences": {},
              "wellbeing": {
                "risk_level": "moderate",
                "trend": "worsening",
                "history": []
              }
            }
            """.trimIndent()
        )

        assertEquals("moderate", memory.health.risk_level)
        assertEquals("worsening", memory.health.trend)
    }

    @Test
    fun processJournalsResponseReadsProductionMentalHealthField() {
        val response = json.decodeFromString<ProcessJournalsResponse>(
            """
            {
              "status": "completed",
              "user_id": "default",
              "journal_summary": "Unable to analyze journals",
              "mental_health": {
                "estimated_phq4": 3,
                "risk_level": "mild",
                "key_concerns": [],
                "positive_indicators": []
              },
              "recommendations": [],
              "proposed_changes": [],
              "errors": []
            }
            """.trimIndent()
        )

        val mentalHealth = assertNotNull(response.health)
        assertEquals(3, mentalHealth.estimated_phq4)
        assertEquals("mild", mentalHealth.risk_level)
    }

    @Test
    fun memoryResponseReadsProductionMentalHealthField() {
        val memory = json.decodeFromString<UserMemoryData>(
            """
            {
              "preferences": {},
              "mental_health": {
                "risk_level": "mild",
                "trend": "stable",
                "history": []
              }
            }
            """.trimIndent()
        )

        assertEquals("mild", memory.health.risk_level)
        assertEquals("stable", memory.health.trend)
    }
}
