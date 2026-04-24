package com.autolife.shared.analyzer

/**
 * Centralized prompt construction for all LLM interactions.
 * Keeps prompt engineering in one place — shared across Android and iOS.
 */
object PromptBuilder {

    fun buildMotionCalibrationPrompt(motionCandidates: List<String>, locationContext: String): String =
        """
        You are an intelligent life-logging assistant.
        Input:
        - Candidate motions from sensors: ${motionCandidates.joinToString(", ")}
        - Location context: $locationContext

        Task:
        1. Select the single most probable motion given the location context.
        2. Keep the answer objective and concise.

        Format:
        Summary: <single motion label>
        """.trimIndent()

    fun buildLocationAnalysisPrompt(): String =
        """
        You are a helpful assistant that can analyze the uploaded map.
        Identify key features with the following categories:
        - transportation infrastructure
        - natural features
        - built environment

        Response format:
        Reasoning: <brief analysis>
        Summary: <brief summary of the map's central region>
        """.trimIndent()

    fun buildWifiLocationPrompt(ssids: List<String>): String =
        """
        Objective: Determine the user's surrounding conditions from Wi-Fi SSIDs.

        Task:
        Infer the most likely surrounding environment from this de-duplicated SSID list:
        ${ssids.joinToString(prefix = "[", postfix = "]")}

        Response format:
        Reasoning: <brief analysis of what the SSIDs imply>
        Summary: <short location context, or "SSID context unavailable" if the SSIDs are not informative>
        """.trimIndent()

    fun buildLocationFusionPrompt(mapContext: String?, osmContext: String?, ssidContext: String?): String =
        """
        You are fusing location context for life journaling.

        Inputs:
        - Geocoder-based location context: ${mapContext ?: "Unavailable"}
        - OpenStreetMap nearby feature context: ${osmContext ?: "Unavailable"}
        - Wi-Fi SSID-based location context: ${ssidContext ?: "Unavailable"}

        Task:
        Keep the most specific accurate location context.
        - Preserve useful geographic/address detail from the geocoder when available.
        - Use OpenStreetMap features for surrounding scene/geography such as campus, grass, water, pools, parking, paths, roads, and buildings.
        - Add Wi-Fi context when it clarifies venue type or indoor setting.
        - Do not replace a real address or road/city context with only a generic Wi-Fi label.
        - Keep the final summary concise but informative.

        Response format:
        Reasoning: <brief comparison>
        Summary: <single fused location context with geography/address plus venue/environment when available>
        """.trimIndent()

    fun buildJournalPrompt(refinedSegments: String): String =
        """
        You are an AI Life Journaling Assistant.
        Your goal is to write a semantic, objective, and accurate daily journal based on refined context segments.

        Input:
        A list of refined context segments:
        $refinedSegments

        Instructions:
        1. Synthesize the segments into a coherent narrative.
        2. Identify high-level activities (e.g., "dining out", "working", "commuting") from the low-level signals.
        3. Remove any subjective comments (e.g., avoid "The user had a productive day" or "It was a relaxing evening"). Stick to factual descriptions of behavior and context.
        4. Be concise.
        5. Prefer the most specific location detail available in the segments.

        Example Journal Style:
        "In the morning, the user spent time at a local library, likely reading and researching. Around noon, the user visited a restaurant in the city center..."

        Generate the journal now.
        """.trimIndent()
}
