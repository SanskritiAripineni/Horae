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
    fun processJournalsResponseReadsUiSummaryAndAnalysisDetails() {
        val response = json.decodeFromString<ProcessJournalsResponse>(
            """
            {
              "status": "completed",
              "ui_summary": {
                "headline": "Mild sleep strain",
                "confidence_label": "Medium confidence",
                "summary": "Late nights are affecting recovery.",
                "evidence_chips": [{"label": "Late screen", "kind": "concern", "icon": "moon"}],
                "concerns": [{"label": "Late-night screen", "detail": "Repeated after 11 PM"}],
                "protective_signals": [{"label": "Consistent journaling"}],
                "productive_signals": [{"label": "Regular engagement"}]
              },
              "analysis_details": {
                "journal_count": 10,
                "duration_seconds": 2.5,
                "behavioral_sensing": {"prose": "Sleep shifted later."},
                "research_sources": [{"category": "Sleep", "content": "Sleep matters.", "source": "paper.pdf"}],
                "tool_status": {"research": "ready"}
              },
              "proposed_changes": [
                {
                  "title": "Wind-down",
                  "reason": "Reduce late screen use",
                  "source": "behavioral_sensing",
                  "change_token": "signed"
                }
              ]
            }
            """.trimIndent()
        )

        assertEquals("Mild sleep strain", response.ui_summary?.headline)
        assertEquals("Late screen", response.ui_summary?.evidence_chips?.first()?.label)
        assertEquals("Consistent journaling", response.ui_summary?.protective_signals?.first()?.label)
        assertEquals(10, response.analysis_details?.journal_count)
        assertEquals("paper.pdf", response.analysis_details?.research_sources?.first()?.source)
        assertEquals("Reduce late screen use", response.proposed_changes.first().reason)
        assertEquals("behavioral_sensing", response.proposed_changes.first().source)
        assertEquals("signed", response.proposed_changes.first().change_token)
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
