package com.google.mediapipe.examples.llminference

import android.annotation.SuppressLint
import android.content.Context
import android.location.Address
import android.location.Geocoder
import android.location.Location
import android.os.Build
import android.util.Log
import com.autolife.shared.ai.AiClientProvider
import com.autolife.shared.analyzer.PromptBuilder
import com.autolife.shared.model.ContextLog
import com.autolife.shared.model.LocationContextCacheEntry
import com.autolife.shared.model.LocationSnapshot
import com.autolife.shared.platform.LocationData
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.google.android.gms.tasks.CancellationTokenSource
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import java.io.Closeable
import java.util.Locale
import kotlin.coroutines.resume

data class LocationResolutionResult(
    val snapshot: LocationSnapshot?,
    val gridKey: String?,
    val mapContext: String?,
    val ssidContext: String?,
    val fusedLocationContext: String?,
    val reusedMapContext: Boolean,
    val reusedSsidContext: Boolean,
    val ssidFingerprint: String
)

@SuppressLint("MissingPermission")
suspend fun getBestLocation(
    context: Context,
    requireFresh: Boolean = false,
    highAccuracy: Boolean = false
): Location? {
    val fusedClient = LocationServices.getFusedLocationProviderClient(context)

    val lastKnown = runCatching { fusedClient.lastLocation.await() }.getOrNull()
    if (!requireFresh && lastKnown != null && isUsableLocation(lastKnown)) {
        return lastKnown
    }

    val priority = if (highAccuracy) {
        Priority.PRIORITY_HIGH_ACCURACY
    } else {
        Priority.PRIORITY_BALANCED_POWER_ACCURACY
    }

    val current = try {
        withTimeout(if (highAccuracy) 6000 else 4000) {
            fusedClient.getCurrentLocation(priority, CancellationTokenSource().token).await()
        }
    } catch (_: Exception) {
        null
    }

    return when {
        current != null && isUsableLocation(current) -> current
        lastKnown != null && isUsableLocation(lastKnown) -> lastKnown
        else -> current ?: lastKnown
    }
}

fun isUsableLocation(location: Location, maxAccuracyMeters: Float = 50f): Boolean {
    val accuracy = location.accuracy
    return !accuracy.isNaN() && accuracy <= maxAccuracyMeters
}

class LocationAnalyzer(private val context: Context) : Closeable {
    companion object {
        private const val TAG = "LocationAnalyzer"
    }

    private val fileStorage = FileStorage(context)
    private val cacheStorage = LocationContextCacheStorage(context)

    suspend fun resolveLocationContext(
        location: Location?,
        ssids: List<String>,
        previousLog: ContextLog?
    ): LocationResolutionResult = withContext(Dispatchers.IO) {
        val sanitizedSsids = ssids.map { it.trim() }.filter { it.isNotEmpty() }.distinct()
        val ssidFingerprint = sanitizedSsids.joinToString("|").hashCode().toString()
        val snapshot = location?.let {
            LocationSnapshot(
                latitude = it.latitude,
                longitude = it.longitude,
                accuracyM = it.accuracy,
                speedMps = it.speed.toDouble(),
                capturedAtMs = System.currentTimeMillis()
            )
        }
        val gridKey = location?.let(LocationContextCacheStorage::gridKeyFor)

        val previousGridMatches = previousLog?.locationGridKey == gridKey
        val previousSsidMatches = previousLog?.ssidFingerprint == ssidFingerprint

        val ssidContext = when {
            sanitizedSsids.isEmpty() -> null
            previousGridMatches && previousSsidMatches && !previousLog?.ssidContext.isNullOrBlank() -> previousLog?.ssidContext
            else -> generateSsidContext(sanitizedSsids)
        }
        val reusedSsidContext = sanitizedSsids.isNotEmpty() && previousGridMatches && previousSsidMatches && !previousLog?.ssidContext.isNullOrBlank()
        val cachedMap = gridKey?.let(cacheStorage::get)
        val reusedMapContext = cachedMap != null
        val mapContext = when {
            cachedMap != null -> cachedMap.mapContext
            location != null -> generateGeocoderContext(location, gridKey)
            else -> null
        }

        val fusedLocationContext = when {
            previousGridMatches && previousSsidMatches && !previousLog?.fusedLocationContext.isNullOrBlank() -> previousLog?.fusedLocationContext
            !ssidContext.isNullOrBlank() && !mapContext.isNullOrBlank() -> fuseLocationContexts(mapContext, ssidContext)
            !ssidContext.isNullOrBlank() -> ssidContext
            else -> mapContext
        }

        com.google.mediapipe.examples.llminference.data.DebugRepository.updateLocationMap(
            bitmap = null,
            mapImageBytes = null,
            lat = snapshot?.latitude ?: 0.0,
            lon = snapshot?.longitude ?: 0.0
        )
        com.google.mediapipe.examples.llminference.data.DebugRepository.updateLocationSSIDs(sanitizedSsids)
        com.google.mediapipe.examples.llminference.data.DebugRepository.updateLocationInference(fusedLocationContext ?: "No location context")

        fusedLocationContext?.let { fileStorage.saveLLMResponseIfChanged(it) }

        LocationResolutionResult(
            snapshot = snapshot,
            gridKey = gridKey,
            mapContext = mapContext,
            ssidContext = ssidContext,
            fusedLocationContext = fusedLocationContext,
            reusedMapContext = reusedMapContext,
            reusedSsidContext = reusedSsidContext,
            ssidFingerprint = ssidFingerprint
        )
    }

    private suspend fun generateGeocoderContext(
        location: Location,
        gridKey: String?
    ): String? {
        Log.d(TAG, "Generating new geocoder context for grid=$gridKey")
        val response = reverseGeocodeLocation(
            context = context,
            latitude = location.latitude,
            longitude = location.longitude
        )?.trim()?.takeIf { it.isNotEmpty() }

        if (!response.isNullOrBlank() && gridKey != null) {
            cacheStorage.put(
                LocationContextCacheEntry(
                    gridKey = gridKey,
                    mapContext = response,
                    mapSourceLat = location.latitude,
                    mapSourceLon = location.longitude,
                    updatedAtMs = System.currentTimeMillis()
                )
            )
        }

        return response
    }

    private suspend fun generateSsidContext(ssids: List<String>): String? {
        val response = runCatching {
            extractSummary(AiClientProvider.client.generate(PromptBuilder.buildWifiLocationPrompt(ssids)))
        }.getOrElse { error ->
            Log.w(TAG, "SSID context generation failed", error)
            null
        }
        return response?.takeUnless { it.equals("SSID context unavailable", ignoreCase = true) }
    }

    private suspend fun fuseLocationContexts(mapContext: String?, ssidContext: String?): String? {
        val response = runCatching {
            extractSummary(AiClientProvider.client.generate(PromptBuilder.buildLocationFusionPrompt(mapContext, ssidContext)))
        }.getOrElse { error ->
            Log.w(TAG, "Location fusion failed", error)
            null
        }
        return response ?: ssidContext ?: mapContext
    }

    private fun extractSummary(response: String?): String? {
        val text = response?.trim().orEmpty()
        if (text.isBlank()) return null
        val summaryLine = text.lineSequence().firstOrNull { it.trim().startsWith("Summary:", ignoreCase = true) }
        return summaryLine?.substringAfter(":")?.trim()?.takeIf { it.isNotBlank() } ?: text
    }

    override fun close() = Unit
}

suspend fun reverseGeocodeLocation(
    context: Context,
    latitude: Double,
    longitude: Double
): String? = withContext(Dispatchers.IO) {
    if (!Geocoder.isPresent()) return@withContext null

    val geocoder = Geocoder(context, Locale.getDefault())
    val address = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        suspendCancellableCoroutine<Address?> { continuation ->
            geocoder.getFromLocation(latitude, longitude, 1) { results ->
                continuation.resume(results.firstOrNull())
            }
        }
    } else {
        @Suppress("DEPRECATION")
        runCatching { geocoder.getFromLocation(latitude, longitude, 1)?.firstOrNull() }.getOrNull()
    }

    address?.toLocationSummary()
}

private fun Address.toLocationSummary(): String? {
    val parts = listOfNotNull(
        subThoroughfare?.trim()?.takeIf { it.isNotEmpty() },
        thoroughfare?.trim()?.takeIf { it.isNotEmpty() },
        subLocality?.trim()?.takeIf { it.isNotEmpty() },
        locality?.trim()?.takeIf { it.isNotEmpty() },
        adminArea?.trim()?.takeIf { it.isNotEmpty() },
        countryName?.trim()?.takeIf { it.isNotEmpty() }
    ).distinct()

    return parts.joinToString(", ").takeIf { it.isNotBlank() }
}
