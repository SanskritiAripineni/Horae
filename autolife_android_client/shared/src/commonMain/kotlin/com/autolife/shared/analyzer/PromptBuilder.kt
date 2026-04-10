package com.autolife.shared.analyzer

/**
 * Centralized prompt construction for all LLM interactions.
 * Keeps prompt engineering in one place — shared across Android and iOS.
 */
object PromptBuilder {

    fun buildFusionPrompt(motionHistory: String, locationContext: String): String =
        """
        You are an intelligent life-logging assistant.
        Input:
        - Detected Motion (from sensors): $motionHistory
        - Location Context (from map analysis): $locationContext

        Task:
        1. Motion Calibration: Select the most probable motion given the location context.
        2. Present the result as a concise log entry.

        Format:
        [Motion Calibrated] in [Location Context]
        """.trimIndent()

    fun buildLocationAnalysisPrompt(): String =
        """
        You are a helpful assistant that can analyze the uploaded map.
        Identify key features with the following categories:
        - transportation infrastructure
        - natural features
        - built environment

        Provide a brief summary of the map's central region.
        """.trimIndent()

    fun buildJournalPrompt(formattedLogs: String): String =
        """
        You are an AI Life Journaling Assistant.
        Your goal is to write a semantic, objective, and accurate daily journal based on the user's context logs.

        Input:
        A list of context logs in the format: [timestamp] [context description]
        $formattedLogs

        Instructions:
        1. Synthesize the logs into a coherent narrative.
        2. Identify high-level activities (e.g., "dining out", "working", "commuting") from the low-level signals.
        3. Remove any subjective comments (e.g., avoid "The user had a productive day" or "It was a relaxing evening"). Stick to factual descriptions of behavior and context.
        4. Be concise.

        Example Journal Style:
        "In the morning, the user spent time at a local library, likely reading and researching. Around noon, the user visited a restaurant in the city center..."

        Generate the journal now.
        """.trimIndent()
}
