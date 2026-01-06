package com.google.mediapipe.examples.llminference

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.URL

object GoogleStaticMapsHelper {
    suspend fun getStaticMapImage(
        lat: Double,
        lng: Double,
        zoom: Int,
        width: Int,
        height: Int,
        apiKey: String
    ): Bitmap? = withContext(Dispatchers.IO) {
        try {
            val url = "https://maps.googleapis.com/maps/api/staticmap?center=$lat,$lng&zoom=$zoom&size=${width}x${height}&maptype=roadmap&key=$apiKey"
            val connection = URL(url).openConnection()
            connection.doInput = true
            connection.connect()
            val input = connection.getInputStream()
            BitmapFactory.decodeStream(input)
        } catch (e: Exception) {
            e.printStackTrace()
            null
        }
    }
}
