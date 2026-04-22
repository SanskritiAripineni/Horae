package com.google.mediapipe.examples.llminference

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import com.autolife.shared.platform.MapImageFetcher
import java.io.ByteArrayOutputStream
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.min
import kotlin.math.PI
import java.net.URL

class MapImageProvider : MapImageFetcher {
    data class AnalysisMapPreview(
        val bitmap: Bitmap,
        val imageBytes: ByteArray,
    )

    companion object {
        private const val TAG = "MapImageProvider"
        private const val BASE_URL = "https://maps.googleapis.com/maps/api/staticmap"
        private const val MAP_ZOOM = 18
        private const val MAP_SIZE_PX = 256
        private const val JPEG_QUALITY = 82
    }

    suspend fun getAnalysisMapPreview(
        latitude: Double,
        longitude: Double,
        accuracyMeters: Float? = null,
    ): AnalysisMapPreview? = withContext(Dispatchers.IO) {
        val apiKey = BuildConfig.MAPS_API_KEY
        if (apiKey.isEmpty()) {
            Log.e(TAG, "Maps API Key is missing")
            return@withContext null
        }

        // A tighter crop keeps the user's local surroundings readable for both the UI and VLM.
        val urlString =
            "$BASE_URL?center=$latitude,$longitude&zoom=$MAP_ZOOM&size=${MAP_SIZE_PX}x$MAP_SIZE_PX&scale=1&maptype=roadmap&format=jpg&key=$apiKey"

        try {
            val url = URL(urlString)
            val connection = url.openConnection()
            connection.doInput = true
            connection.connect()
            connection.getInputStream().use { input ->
                val baseBitmap = BitmapFactory.decodeStream(input) ?: return@withContext null
                val previewBitmap = overlayAccuracyBlob(
                    source = baseBitmap,
                    latitude = latitude,
                    accuracyMeters = accuracyMeters,
                )
                val stream = ByteArrayOutputStream()
                previewBitmap.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, stream)
                AnalysisMapPreview(
                    bitmap = previewBitmap,
                    imageBytes = stream.toByteArray(),
                )
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to download map image", e)
            null
        }
    }

    suspend fun getMapImage(latitude: Double, longitude: Double, accuracyMeters: Float? = null): Bitmap? {
        return getAnalysisMapPreview(latitude, longitude, accuracyMeters)?.bitmap
    }

    override suspend fun fetchMapImage(latitude: Double, longitude: Double): ByteArray? {
        return getAnalysisMapPreview(latitude, longitude)?.imageBytes
    }

    internal fun accuracyBlobRadiusPx(
        latitude: Double,
        accuracyMeters: Float?,
        zoom: Int = MAP_ZOOM,
        imageWidthPx: Int = MAP_SIZE_PX,
    ): Float {
        val safeAccuracy = (accuracyMeters ?: 20f).coerceIn(8f, 80f)
        val metersPerPixel = metersPerPixel(latitude = latitude, zoom = zoom)
        val idealRadiusPx = safeAccuracy / metersPerPixel
        return idealRadiusPx.coerceIn(
            minimumValue = imageWidthPx * 0.04f,
            maximumValue = imageWidthPx * 0.18f,
        )
    }

    internal fun metersPerPixel(latitude: Double, zoom: Int): Float {
        val latitudeRadians = latitude * PI / 180.0
        return (156543.03392 * cos(latitudeRadians) / (1 shl zoom)).toFloat()
    }

    private fun overlayAccuracyBlob(
        source: Bitmap,
        latitude: Double,
        accuracyMeters: Float?,
    ): Bitmap {
        val mutableBitmap = source.copy(Bitmap.Config.ARGB_8888, true)
        val canvas = Canvas(mutableBitmap)
        val centerX = mutableBitmap.width / 2f
        val centerY = mutableBitmap.height / 2f
        val radiusPx = accuracyBlobRadiusPx(
            latitude = latitude,
            accuracyMeters = accuracyMeters,
            imageWidthPx = mutableBitmap.width,
        )

        val blobPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.argb(88, 51, 136, 255)
            style = Paint.Style.FILL
        }
        val outlinePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.argb(190, 28, 98, 214)
            style = Paint.Style.STROKE
            strokeWidth = max(2f, mutableBitmap.width * 0.01f)
        }
        val dotPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            style = Paint.Style.FILL
        }
        val dotOutlinePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.argb(220, 28, 98, 214)
            style = Paint.Style.STROKE
            strokeWidth = max(1.5f, mutableBitmap.width * 0.006f)
        }

        canvas.drawCircle(centerX, centerY, radiusPx, blobPaint)
        canvas.drawCircle(centerX, centerY, radiusPx, outlinePaint)

        val dotRadius = min(radiusPx * 0.24f, mutableBitmap.width * 0.03f)
        canvas.drawCircle(centerX, centerY, dotRadius, dotPaint)
        canvas.drawCircle(centerX, centerY, dotRadius, dotOutlinePaint)

        return mutableBitmap
    }
}
