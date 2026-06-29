package com.google.mediapipe.examples.llminference

import android.content.Context
import android.location.Location
import com.autolife.shared.model.LocationContextCacheEntry
import kotlinx.serialization.builtins.MapSerializer
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.Json
import java.io.File
import kotlin.math.cos
import kotlin.math.floor

class LocationContextCacheStorage(context: Context) {
    private val file = File(context.filesDir, "location_context_cache.json")
    private val json = Json { ignoreUnknownKeys = true; prettyPrint = true }
    private val serializer = MapSerializer(String.serializer(), LocationContextCacheEntry.serializer())

    fun get(gridKey: String): LocationContextCacheEntry? = readCache()[gridKey]

    fun put(entry: LocationContextCacheEntry) {
        val cache = readCache().toMutableMap()
        if (cache[entry.gridKey] == entry) return
        cache[entry.gridKey] = entry
        file.writeText(json.encodeToString(serializer, cache))
    }

    private fun readCache(): Map<String, LocationContextCacheEntry> {
        if (!file.exists()) return emptyMap()
        val content = file.readText()
        if (content.isBlank()) return emptyMap()
        return runCatching { json.decodeFromString(serializer, content) }.getOrElse { emptyMap() }
    }

    companion object {
        private const val GRID_METERS = 100.0

        fun gridKeyFor(location: Location): String = gridKeyFor(location.latitude, location.longitude)

        fun gridKeyFor(latitude: Double, longitude: Double): String {
            val latMetersPerDegree = 111_320.0
            val lonMetersPerDegree = 111_320.0 * cos(Math.toRadians(latitude)).coerceAtLeast(0.1)
            val latBucket = floor((latitude * latMetersPerDegree) / GRID_METERS).toLong()
            val lonBucket = floor((longitude * lonMetersPerDegree) / GRID_METERS).toLong()
            return "$latBucket:$lonBucket"
        }
    }
}
