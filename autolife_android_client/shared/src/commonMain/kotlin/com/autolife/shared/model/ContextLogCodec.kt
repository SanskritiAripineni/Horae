package com.autolife.shared.model

import kotlinx.serialization.json.Json

object ContextLogCodec {
    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
    }

    fun encode(log: ContextLog): String = json.encodeToString(ContextLog.serializer(), log)

    fun decode(content: String): ContextLog? = runCatching {
        json.decodeFromString(ContextLog.serializer(), content)
    }.getOrNull()
}
