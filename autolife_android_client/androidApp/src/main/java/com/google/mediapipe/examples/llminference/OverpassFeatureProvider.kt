package com.google.mediapipe.examples.llminference

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URLEncoder
import java.net.URL

class OverpassFeatureProvider {
    companion object {
        private const val TAG = "OverpassFeatureProvider"
        private const val ENDPOINT = "https://overpass-api.de/api/interpreter"
        private const val RADIUS_METERS = 120
        private const val MAX_ELEMENTS = 40
    }

    suspend fun getNearbyFeatureContext(latitude: Double, longitude: Double): String? = withContext(Dispatchers.IO) {
        val query = buildQuery(latitude, longitude)
        runCatching {
            val encoded = "data=" + URLEncoder.encode(query, "UTF-8")
            val connection = (URL(ENDPOINT).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = 5_000
                readTimeout = 5_000
                doOutput = true
                setRequestProperty("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
                setRequestProperty("User-Agent", "AutoLife/1.0 Android location-context")
            }
            connection.outputStream.use { it.write(encoded.toByteArray(Charsets.UTF_8)) }
            val body = connection.inputStream.bufferedReader().use { it.readText() }
            summarize(JSONObject(body))
        }.getOrElse { error ->
            Log.w(TAG, "OSM feature lookup failed", error)
            null
        }
    }

    private fun buildQuery(latitude: Double, longitude: Double): String =
        """
        [out:json][timeout:5];
        (
          node(around:$RADIUS_METERS,$latitude,$longitude)["amenity"];
          way(around:$RADIUS_METERS,$latitude,$longitude)["amenity"];
          relation(around:$RADIUS_METERS,$latitude,$longitude)["amenity"];
          node(around:$RADIUS_METERS,$latitude,$longitude)["leisure"];
          way(around:$RADIUS_METERS,$latitude,$longitude)["leisure"];
          relation(around:$RADIUS_METERS,$latitude,$longitude)["leisure"];
          node(around:$RADIUS_METERS,$latitude,$longitude)["natural"];
          way(around:$RADIUS_METERS,$latitude,$longitude)["natural"];
          relation(around:$RADIUS_METERS,$latitude,$longitude)["natural"];
          way(around:$RADIUS_METERS,$latitude,$longitude)["landuse"];
          relation(around:$RADIUS_METERS,$latitude,$longitude)["landuse"];
          way(around:$RADIUS_METERS,$latitude,$longitude)["building"];
          way(around:$RADIUS_METERS,$latitude,$longitude)["highway"];
        );
        out tags center $MAX_ELEMENTS;
        """.trimIndent()

    private fun summarize(json: JSONObject): String? {
        val elements = json.optJSONArray("elements") ?: return null
        val features = linkedSetOf<String>()
        val named = linkedSetOf<String>()

        for (i in 0 until elements.length()) {
            val tags = elements.optJSONObject(i)?.optJSONObject("tags") ?: continue
            tags.optString("name").takeIf { it.isNotBlank() }?.let { named += it }
            featureLabel(tags)?.let { features += it }
        }

        if (features.isEmpty() && named.isEmpty()) return null

        val parts = mutableListOf<String>()
        if (features.isNotEmpty()) {
            parts += "Nearby map features: ${features.take(8).joinToString(", ")}"
        }
        if (named.isNotEmpty()) {
            parts += "Named places/features: ${named.take(4).joinToString(", ")}"
        }
        return parts.joinToString(". ")
    }

    private fun featureLabel(tags: JSONObject): String? {
        val amenity = tags.optString("amenity")
        val leisure = tags.optString("leisure")
        val natural = tags.optString("natural")
        val landuse = tags.optString("landuse")
        val building = tags.optString("building")
        val highway = tags.optString("highway")

        return when {
            amenity == "university" || amenity == "college" || amenity == "school" -> "education/campus"
            amenity == "parking" || amenity == "parking_space" -> "parking"
            amenity == "restaurant" || amenity == "cafe" || amenity == "fast_food" -> "food venue"
            amenity == "library" -> "library"
            amenity == "gym" || amenity == "fitness_centre" -> "fitness facility"
            leisure == "swimming_pool" -> "swimming pool"
            leisure == "park" || leisure == "garden" -> "green space"
            leisure == "pitch" || leisure == "sports_centre" || leisure == "track" -> "sports/recreation area"
            natural == "water" || natural == "bay" || natural == "wetland" -> "water feature"
            natural == "wood" || natural == "tree" || natural == "tree_row" -> "trees/wooded area"
            landuse == "grass" || landuse == "meadow" || landuse == "recreation_ground" -> "grass/open green area"
            landuse == "residential" -> "residential area"
            landuse == "commercial" || landuse == "retail" -> "commercial area"
            landuse == "education" -> "education/campus"
            building.isNotBlank() -> "buildings"
            highway == "footway" || highway == "path" || highway == "pedestrian" -> "walkways/paths"
            highway.isNotBlank() -> "road network"
            else -> null
        }
    }
}
