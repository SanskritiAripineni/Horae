package com.google.mediapipe.examples.llminference

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import com.autolife.shared.platform.MapImageFetcher
import java.io.ByteArrayOutputStream
import java.net.URL

class MapImageProvider : MapImageFetcher {
    companion object {
        private const val TAG = "MapImageProvider"
        private const val BASE_URL = "https://maps.googleapis.com/maps/api/staticmap"
    }

    suspend fun getMapImage(latitude: Double, longitude: Double): Bitmap? = withContext(Dispatchers.IO) {
        val apiKey = BuildConfig.MAPS_API_KEY
        if (apiKey.isEmpty()) {
            Log.e(TAG, "Maps API Key is missing")
            return@withContext null
        }

        // 250x250m coverage at zoom 18 roughly fits 600x600px standard image
        // Paper says "250×250m area" and "Zoom level 18".
        val urlString = "$BASE_URL?center=$latitude,$longitude&zoom=18&size=600x600&maptype=roadmap&key=$apiKey"

        try {
            val url = URL(urlString)
            val connection = url.openConnection()
            connection.doInput = true
            connection.connect()
            connection.getInputStream().use { input ->
                BitmapFactory.decodeStream(input)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to download map image", e)
            null
        }
    }

    override suspend fun fetchMapImage(latitude: Double, longitude: Double): ByteArray? {
        val bitmap = getMapImage(latitude, longitude) ?: return null
        val stream = ByteArrayOutputStream()
        bitmap.compress(Bitmap.CompressFormat.PNG, 100, stream)
        return stream.toByteArray()
    }
}
